from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
ML_DIR = ROOT / "ml"
API_DIR = ROOT / "api"
PUBLIC_DIR = ROOT / "public"

for path in (str(ROOT), str(API_DIR), str(ML_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)

import export_firebase_history  # noqa: E402
import predict_energy  # noqa: E402
from main import app  # noqa: E402

from fastapi.testclient import TestClient


HISTORY_REAL = ML_DIR / "data" / "history_real.csv"
HISTORY_LIVE = ML_DIR / "data" / "history_live.csv"
MODEL_PATH = ML_DIR / "output" / "random_forest_model.joblib"
ML_DATA_DIR = ML_DIR / "data"


def csv_to_records(path: Path, limit: int | None = None) -> dict:
    records = {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader):
            if limit is not None and index >= limit:
                break
            ts = int(row["timestamp"])
            record = {"timestamp": ts}
            for key in ("voltage", "current", "power", "energy_kwh", "frequency", "power_factor"):
                raw = row.get(key, "")
                record[key] = float(raw) if raw not in ("", None) else None
            records[str(ts)] = record
    return records


class GeneratePredictionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not HISTORY_REAL.exists():
            raise unittest.SkipTest("history_real.csv missing")
        if not MODEL_PATH.exists():
            raise unittest.SkipTest("random_forest_model.joblib missing")

    def test_missing_data_raises_prediction_error_not_systemexit(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing.csv"
            output = Path(tmp) / "out.json"
            with self.assertRaises(predict_energy.PredictionError):
                predict_energy.generate_prediction(data_path=missing, output_path=output)

    def test_legacy_default_paths_point_to_research_files(self):
        source = inspect_default_paths()
        self.assertTrue(str(source["data_path"]).replace("\\", "/").endswith("ml/data/history_real.csv"))
        self.assertTrue(str(source["output_path"]).replace("\\", "/").endswith("ml/output/prediction.json"))

    def test_legacy_generate_prediction_default_still_works(self):
        output = ML_DIR / "output" / "prediction.json"
        backup = output.read_text(encoding="utf-8") if output.exists() else None
        try:
            result = predict_energy.generate_prediction()
            self.assertTrue(output.exists())
            self.assertEqual(result["model_version"], "RF-v1")
            self.assertIsInstance(result["predicted_next_hour_kwh"], float)
        finally:
            if backup is not None:
                output.write_text(backup, encoding="utf-8")

    def test_legacy_explicit_research_path_does_not_require_live_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "prediction.json"
            result = predict_energy.generate_prediction(
                data_path=HISTORY_REAL,
                output_path=output,
            )
            self.assertTrue(output.exists())
            self.assertNotEqual(output.resolve(), (ML_DIR / "output" / "prediction.json").resolve())
        self.assertEqual(result["model_version"], "RF-v1")
        self.assertIn("predicted_next_hour_kwh", result)

    def test_live_path_uses_separate_output(self):
        source = HISTORY_LIVE if HISTORY_LIVE.exists() else HISTORY_REAL
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "prediction_live.json"
            before = HISTORY_REAL.read_bytes()
            result = predict_energy.generate_prediction(data_path=source, output_path=output)
            after = HISTORY_REAL.read_bytes()
            self.assertTrue(output.exists())
        self.assertEqual(before, after)
        self.assertIsInstance(result["predicted_next_hour_kwh"], float)
        self.assertEqual(result["model_version"], "RF-v1")


def inspect_default_paths():
    import inspect
    source = inspect.getsource(predict_energy.generate_prediction)
    return {
        "data_path": "ml/data/history_real.csv" if "history_real.csv" in source else None,
        "output_path": "ml/output/prediction.json" if "prediction.json" in source else None,
    }


class ExportCsvTests(unittest.TestCase):
    def test_export_csv_writes_sorted_rows(self):
        records = {
            "200": {"timestamp": 200, "voltage": 220, "current": 0.1, "power": 20, "energy_kwh": 1.2, "frequency": 50, "power_factor": 0.9},
            "100": {"timestamp": 100, "voltage": 221, "current": 0.2, "power": 30, "energy_kwh": 1.1, "frequency": 50, "power_factor": 0.8},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.csv"
            rows, stats = export_firebase_history.export_csv(records, path)
            self.assertTrue(path.exists())
        self.assertEqual(stats["valid_rows"], 2)
        self.assertEqual(rows[0]["timestamp"], 100)
        self.assertEqual(rows[1]["timestamp"], 200)


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        self.assertTrue(body["model_exists"])

    def test_model_info(self):
        response = self.client.get("/api/model-info")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["model_type"], "RandomForestRegressor")
        self.assertEqual(body["n_estimators"], 200)
        self.assertEqual(body["n_features_in"], 10)

    def test_predict_missing_auth_401(self):
        response = self.client.post("/api/predict")
        self.assertEqual(response.status_code, 401)

    def test_predict_invalid_scheme_401(self):
        response = self.client.post("/api/predict", headers={"Authorization": "Token abc"})
        self.assertEqual(response.status_code, 401)

    def test_predict_invalid_token_401(self):
        with patch("main.verify_firebase_id_token", side_effect=lambda token: (_ for _ in ()).throw(
            __import__("fastapi").HTTPException(status_code=401, detail="Invalid or expired Firebase ID token.")
        )):
            response = self.client.post("/api/predict", headers={"Authorization": "Bearer fake-token"})
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("fake-token", response.text)

    def test_predict_mocked_history_does_not_touch_research_csv(self):
        if not HISTORY_REAL.exists():
            self.skipTest("history_real.csv missing")
        records = csv_to_records(HISTORY_REAL)
        before = HISTORY_REAL.read_bytes()
        with patch("main.verify_firebase_id_token", return_value=None) as verify_token, \
             patch("export_firebase_history.fetch_history", return_value=records):
            response = self.client.post("/api/predict", headers={"Authorization": "Bearer test-token"})
        after = HISTORY_REAL.read_bytes()
        self.assertEqual(before, after)
        verify_token.assert_called_once()
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["source"], "firebase_rtdb")
        prediction = body["prediction"]
        self.assertEqual(prediction["model_version"], "RF-v1")
        self.assertIsInstance(prediction["predicted_next_hour_kwh"], float)
        self.assertTrue(prediction["predicted_next_hour_kwh"] >= 0)
        self.assertIn("evaluation", prediction)
        self.assertNotIn("test-token", json.dumps(body))

    def test_predict_uses_tempdir_not_shared_files(self):
        if not HISTORY_REAL.exists():
            self.skipTest("history_real.csv missing")
        records = csv_to_records(HISTORY_REAL)
        shared_csv = ML_DATA_DIR / "history_live.csv"
        shared_json = (ML_DIR / "output") / "prediction_live.json"
        csv_mtime_before = shared_csv.stat().st_mtime if shared_csv.exists() else None
        json_mtime_before = shared_json.stat().st_mtime if shared_json.exists() else None
        with patch("main.verify_firebase_id_token", return_value=None), \
             patch("export_firebase_history.fetch_history", return_value=records):
            self.client.post("/api/predict", headers={"Authorization": "Bearer x"})
        if shared_csv.exists():
            self.assertEqual(shared_csv.stat().st_mtime, csv_mtime_before,
                             "endpoint must not modify shared history_live.csv")
        if shared_json.exists():
            self.assertEqual(shared_json.stat().st_mtime, json_mtime_before,
                             "endpoint must not modify shared prediction_live.json")

    def test_two_separate_requests_use_different_tempdirs(self):
        if not HISTORY_REAL.exists():
            self.skipTest("history_real.csv missing")
        records = csv_to_records(HISTORY_REAL)
        tempdirs = []
        original_td = __import__("tempfile").TemporaryDirectory

        class CaptureTD(original_td):
            def __init__(self, *a, **kw):
                super().__init__(*a, **kw)
                tempdirs.append(self.name)

        with patch("main.verify_firebase_id_token", return_value=None), \
             patch("export_firebase_history.fetch_history", return_value=records), \
             patch("tempfile.TemporaryDirectory", CaptureTD):
            r1 = self.client.post("/api/predict", headers={"Authorization": "Bearer a"})
            r2 = self.client.post("/api/predict", headers={"Authorization": "Bearer b"})
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(len(tempdirs), 2)
        self.assertNotEqual(tempdirs[0], tempdirs[1])


class FrontendStaticTests(unittest.TestCase):
    def test_html_ids_unique(self):
        html = (PUBLIC_DIR / "index.html").read_text(encoding="utf-8")
        ids = []
        token = 'id="'
        start = 0
        while True:
            idx = html.find(token, start)
            if idx == -1:
                break
            end = html.find('"', idx + len(token))
            ids.append(html[idx + len(token):end])
            start = end + 1
        duplicates = sorted({item for item in ids if ids.count(item) > 1})
        self.assertEqual(duplicates, [])
        for required in ("runPredictionBtn", "predictionRunStatus", "predictionGeneratedAt", "predictionSourceAge"):
            self.assertIn(required, ids)

    def test_js_has_auth_header_and_no_hardcoded_token(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("getIdToken()", js)
        self.assertIn("Authorization", js)
        self.assertIn("Bearer", js)
        self.assertIn("setPredictionState(prediction)", js)
        self.assertNotIn("localhost:8000/api/predict", js)
        self.assertNotRegex(js, r"eyJ[A-Za-z0-9_-]{20,}")

    def test_production_api_url_configured(self):
        config = (PUBLIC_DIR / "firebase-config.js").read_text(encoding="utf-8")
        self.assertIn("PREDICT_API_BASE_URL", config)
        self.assertIn("smart-energy-firebase-complete-production.up.railway.app", config)
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("PREDICT_API_BASE_URL", js)
        self.assertIn("import", js.split("\n")[3])  # line 4 has the import

    def test_localhost_fallback_preserved(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn('return "http://127.0.0.1:8000/api/predict"', js)
        self.assertIn('host === "localhost"', js)

    def test_no_accuracy_claim(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        html = (PUBLIC_DIR / "index.html").read_text(encoding="utf-8")
        combined = js + html
        self.assertIn("belum mengungguli persistence baseline", combined)
        self.assertNotIn("sangat akurat", combined)
        self.assertNotIn("lebih akurat", combined)


if __name__ == "__main__":
    unittest.main()
