from __future__ import annotations

import csv
import json
import os
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
        self.assertEqual(body["model_version"], "RF-v1")

    def test_model_info(self):
        response = self.client.get("/api/model-info")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["model_type"], "RandomForestRegressor")
        self.assertEqual(body["n_estimators"], 200)
        self.assertEqual(body["n_features_in"], 10)
        self.assertEqual(body["model_version"], "RF-v1")
        self.assertEqual(len(body["features"]), 10)
        self.assertIn("energy_lag_24h", body["features"])

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

    def test_category_elements_exist(self):
        html = (PUBLIC_DIR / "index.html").read_text(encoding="utf-8")
        for required_id in ("predictionCategoryCard", "predictionCategoryValue",
                            "predictionCategoryThreshold", "predictionCategoryNote"):
            self.assertIn(f'id="{required_id}"', html)

    def test_category_ids_unique(self):
        html = (PUBLIC_DIR / "index.html").read_text(encoding="utf-8")
        cat_ids = ["predictionCategoryCard", "predictionCategoryValue",
                   "predictionCategoryThreshold", "predictionCategoryNote"]
        for cid in cat_ids:
            self.assertEqual(html.count(f'id="{cid}"'), 1, f"Duplicate or missing: {cid}")

    def test_js_references_category_elements(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("predictionCategoryCard", js)
        self.assertIn("predictionCategoryValue", js)
        self.assertIn("predictionCategoryThreshold", js)
        self.assertIn("predictionCategoryNote", js)
        self.assertIn("consumption_category", js)
        self.assertIn("category_valid_for_current_state", js)
        self.assertIn("category_threshold_kwh", js)

    def test_category_not_in_required_payload(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        # hasPredictionPayload required list should NOT include category fields
        idx = js.find("function hasPredictionPayload")
        func_body = js[idx:idx+500]
        self.assertNotIn("consumption_category", func_body)
        self.assertNotIn("category_threshold_kwh", func_body)

    def test_category_stale_path_exists(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("prediction-card--stale", js)
        self.assertIn("prediction-card--boros", js)
        self.assertIn("prediction-card--normal", js)
        self.assertIn("prediction-card--unavailable", js)

    def test_no_hardcoded_rf_v1_explanatory_text(self):
        html = (PUBLIC_DIR / "index.html").read_text(encoding="utf-8")
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        combined = html + js
        self.assertNotIn("inference model RF-v1", combined)
        self.assertNotIn("inference RF-v1", combined)
        self.assertIn("model Random Forest yang aktif", html)

    def test_monthly_projection_separated_from_rf_prediction(self):
        html = (PUBLIC_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn("Proyeksi Bulan Berjalan", html)
        self.assertIn("Prediksi Random Forest 1 jam hanya digunakan", html)
        self.assertIn("Estimasi Data Awal Bulan", html)
        self.assertNotIn("Data Tidak Mencakup Awal Bulan", html)

    def test_stale_warning_user_facing(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("Prediksi menggunakan data historis", js)
        self.assertIn("tidak digunakan dalam proyeksi bulan berjalan", js)
        idx = js.find("els.predictionProjectionMethod.textContent")
        method_block = js[idx:idx + 900]
        self.assertNotIn("prediction_fresh bernilai", method_block)
        self.assertNotIn("jika prediction_fresh", method_block)

    def test_national_standard_disclaimer_remains(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("bukan standar konsumsi rumah tangga nasional", js)
        self.assertNotIn("mengklasifikasikan", js)
        self.assertNotIn("standar PLN", js)

    def test_existing_prediction_ids_remain(self):
        html = (PUBLIC_DIR / "index.html").read_text(encoding="utf-8")
        for required_id in (
            "predictionEnergyNextHour",
            "predictionFeatureTimestamp",
            "predictionTargetTimestamp",
            "predictionStaleness",
            "predictionSourceAge",
            "predictionRfUsed",
            "predictionCoverageWarning",
            "predictionProjectionMethod",
            "predictionWarning",
        ):
            self.assertIn(f'id="{required_id}"', html)


class VersionAwareApiTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_health_rf_v1_default(self):
        response = self.client.get("/health")
        body = response.json()
        self.assertEqual(body["model_version"], "RF-v1")
        self.assertTrue(body["model_exists"])

    def test_model_info_rf_v1_default(self):
        response = self.client.get("/api/model-info")
        body = response.json()
        self.assertEqual(body["model_version"], "RF-v1")
        self.assertEqual(body["n_features_in"], 10)

    @patch.dict(os.environ, {"SMART_ENERGY_MODEL_VERSION": "RF-v2"})
    def test_health_rf_v2(self):
        response = self.client.get("/health")
        body = response.json()
        self.assertEqual(body["model_version"], "RF-v2")
        self.assertTrue(body["model_exists"])

    @patch.dict(os.environ, {"SMART_ENERGY_MODEL_VERSION": "RF-v2"})
    def test_model_info_rf_v2(self):
        response = self.client.get("/api/model-info")
        body = response.json()
        self.assertEqual(body["model_version"], "RF-v2")
        self.assertEqual(body["n_features_in"], 9)
        self.assertNotIn("energy_lag_24h", body["features"])

    @patch.dict(os.environ, {"SMART_ENERGY_MODEL_VERSION": "INVALID"})
    def test_invalid_version_fails(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 500)

    def test_prediction_has_category_fields(self):
        if not HISTORY_REAL.exists():
            self.skipTest("history_real.csv missing")
        records = csv_to_records(HISTORY_REAL)
        with patch("main.verify_firebase_id_token", return_value=None), \
             patch("export_firebase_history.fetch_history", return_value=records):
            response = self.client.post("/api/predict", headers={"Authorization": "Bearer x"})
        self.assertEqual(response.status_code, 200)
        prediction = response.json()["prediction"]
        self.assertIn("consumption_category", prediction)
        self.assertIn("category_threshold_kwh", prediction)
        self.assertIn("category_valid_for_current_state", prediction)
        self.assertIn(prediction["consumption_category"], ("NORMAL", "BOROS", "TIDAK_TERSEDIA"))


FIRMWARE_DIR = Path(r"D:\Backup 160326\Documents\Arduino\PZEM_FIREBASE")


class LocationRegistryTests(unittest.TestCase):
    def test_location_allowlist_in_firebase_config(self):
        js = (PUBLIC_DIR / "firebase-config.js").read_text(encoding="utf-8")
        self.assertIn("LOCATION_ALLOWLIST", js)
        for code in ("ruang_kerja", "kamar_tidur", "ruang_tamu", "dapur"):
            self.assertIn(code, js)
        self.assertIn("LOCATION_UNKNOWN_LABEL", js)
        self.assertIn("Lokasi tidak diketahui", js)

    def test_location_unknown_label_in_app_js(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("LOCATION_UNKNOWN_LABEL", js)
        self.assertIn("resolveLocationLabel", js)

    def test_location_allowlist_imported_in_app_js(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        import_lines = [l for l in js.split("\n") if l.startswith("import")]
        combined_imports = " ".join(import_lines)
        self.assertIn("LOCATION_ALLOWLIST", combined_imports)

    def test_location_allowlist_has_four_entries(self):
        js = (PUBLIC_DIR / "firebase-config.js").read_text(encoding="utf-8")
        import re
        m = re.search(r"LOCATION_ALLOWLIST\s*=\s*\{([^}]+)\}", js)
        self.assertIsNotNone(m)
        body = m.group(1)
        for code in ("ruang_kerja", "kamar_tidur", "ruang_tamu", "dapur"):
            self.assertIn(code, body)


class SettingsLocationUITests(unittest.TestCase):
    def test_location_select_exists(self):
        html = (PUBLIC_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="locationSelect"', html)

    def test_location_select_has_four_options(self):
        html = (PUBLIC_DIR / "index.html").read_text(encoding="utf-8")
        import re
        m = re.search(r'id="locationSelect"[^>]*>(.*?)</select>', html, re.DOTALL)
        self.assertIsNotNone(m)
        body = m.group(1)
        self.assertIn("ruang_kerja", body)
        self.assertIn("kamar_tidur", body)
        self.assertIn("ruang_tamu", body)
        self.assertIn("dapur", body)
        self.assertIn("Lokasi tidak diketahui", body)

    def test_save_location_button_exists(self):
        html = (PUBLIC_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="saveLocationBtn"', html)

    def test_location_message_element_exists(self):
        html = (PUBLIC_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="locationMsg"', html)

    def test_settings_location_value_display(self):
        html = (PUBLIC_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="settingsLocationValue"', html)

    def test_settings_session_value_display(self):
        html = (PUBLIC_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="settingsSessionValue"', html)

    def test_location_description_text(self):
        html = (PUBLIC_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn("Lokasi digunakan untuk memberi konteks pada data pengukuran baru", html)


class HistoryLocationUITests(unittest.TestCase):
    def test_history_table_has_location_header(self):
        html = (PUBLIC_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn("<th>Lokasi</th>", html)

    def test_history_location_filter_exists(self):
        html = (PUBLIC_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="historyLocationFilter"', html)

    def test_history_location_filter_has_options(self):
        html = (PUBLIC_DIR / "index.html").read_text(encoding="utf-8")
        import re
        m = re.search(r'id="historyLocationFilter"[^>]*>(.*?)</select>', html, re.DOTALL)
        self.assertIsNotNone(m)
        body = m.group(1)
        self.assertIn("Semua Lokasi", body)
        self.assertIn("unknown", body)
        self.assertIn("ruang_kerja", body)
        self.assertIn("kamar_tidur", body)
        self.assertIn("ruang_tamu", body)
        self.assertIn("dapur", body)


class DashboardLocationUITests(unittest.TestCase):
    def test_device_location_chip_exists(self):
        html = (PUBLIC_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="deviceLocationChip"', html)

    def test_monitor_location_value_exists(self):
        html = (PUBLIC_DIR / "index.html").read_text(encoding="utf-8")
        self.assertIn('id="monitorLocationValue"', html)


class AppJsLocationLogicTests(unittest.TestCase):
    def test_location_state_exists(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("deviceLocationState", js)
        self.assertIn("locationFilter", js)

    def test_resolve_location_label_function(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("function resolveLocationLabel", js)

    def test_generate_session_id_function(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("function generateSessionId", js)

    def test_read_device_config_function(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("function readDeviceConfig", js)

    def test_write_device_config_function(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("function writeDeviceConfig", js)

    def test_create_session_function(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("function createSession", js)

    def test_save_location_function(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("function saveLocation", js)

    def test_update_device_location_display_function(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("function updateDeviceLocationDisplay", js)

    def test_location_filter_event_handler(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("historyLocationFilter", js)
        self.assertIn("locationFilter", js)

    def test_save_location_event_handler(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("saveLocationBtn", js)

    def test_read_device_config_called_on_auth(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        # Find the event handler call (not the import)
        idx = js.find("onAuthStateChanged(auth,")
        self.assertGreater(idx, -1)
        auth_block = js[idx:idx+600]
        self.assertIn("readDeviceConfig", auth_block)

    def test_update_device_location_display_called_in_render(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("updateDeviceLocationDisplay()", js)

    def test_parse_history_includes_location_code(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("location_code: val.location_code", js)

    def test_filter_history_includes_location_key(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("filterHistoryRecords(all, historyState.filter, historyState.locationFilter)", js)

    def test_csv_export_includes_location_columns(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("location_code,location_label,session_id", js)

    def test_same_location_no_new_session(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("Lokasi sama, tidak ada perubahan", js)

    def test_firebase_database_imports_set_get(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("fbSet", js)
        self.assertIn("fbGet", js)


class FirmwareLocationTests(unittest.TestCase):
    def _read_firmware(self):
        fw = FIRMWARE_DIR / "PZEM_FIREBASE.ino"
        if not fw.exists():
            self.skipTest("Firmware file not found")
        return fw.read_text(encoding="utf-8", errors="replace")

    def test_location_state_globals(self):
        fw = self._read_firmware()
        self.assertIn("String currentLocationCode", fw)
        self.assertIn("String currentSessionId", fw)

    def test_location_allowlist(self):
        fw = self._read_firmware()
        self.assertIn("ruang_kerja", fw)
        self.assertIn("kamar_tidur", fw)
        self.assertIn("ruang_tamu", fw)
        self.assertIn("dapur", fw)
        self.assertIn("isValidLocation", fw)

    def test_config_poll_function(self):
        fw = self._read_firmware()
        self.assertIn("pollDeviceConfig", fw)
        self.assertIn("CONFIG_POLL_INTERVAL", fw)
        self.assertIn("30000", fw)

    def test_config_poll_in_loop(self):
        fw = self._read_firmware()
        self.assertIn("pollDeviceConfig()", fw.split("void loop()")[1] if "void loop()" in fw else "")

    def test_location_stamp_in_latest(self):
        fw = self._read_firmware()
        latest_section = fw.split("KIRIM DATA TERBARU KE FIREBASE")[1] if "KIRIM DATA TERBARU KE FIREBASE" in fw else ""
        self.assertIn("location_code", latest_section)
        self.assertIn("session_id", latest_section)

    def test_location_stamp_in_history(self):
        fw = self._read_firmware()
        history_section = fw.split("SIMPAN DATA HISTORY")[1] if "SIMPAN DATA HISTORY" in fw else ""
        self.assertIn("location_code", history_section)
        self.assertIn("session_id", history_section)

    def test_config_read_does_not_block_pzem(self):
        fw = self._read_firmware()
        config_fn = fw.split("void pollDeviceConfig")[1].split("void ")[0] if "void pollDeviceConfig" in fw else ""
        self.assertIn("WiFi.status()", config_fn)
        self.assertIn("app.ready()", config_fn)

    def test_config_poll_timer_in_loop(self):
        fw = self._read_firmware()
        loop_section = fw.split("void loop()")[1] if "void loop()" in fw else ""
        self.assertIn("lastConfigPoll", loop_section)
        self.assertIn("CONFIG_POLL_INTERVAL", loop_section)

    def test_no_credentials_in_location_code(self):
        fw = self._read_firmware()
        # Check that no password/API key literals appear in the location session section
        # (the section after "LOCATION / SESSION STATE")
        loc_section_start = fw.find("LOCATION / SESSION STATE")
        if loc_section_start < 0:
            self.skipTest("Location section not found")
        loc_section = fw[loc_section_start:loc_section_start+2000]
        self.assertNotIn("adiberlaga", loc_section)
        self.assertNotIn("Adiberlaga", loc_section)
        self.assertNotIn("AIza", loc_section)


class RegressionPhase5BTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_rf_v2_features_unchanged(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        py = (ML_DIR / "train_random_forest.py").read_text(encoding="utf-8")
        self.assertIn("energy_lag_24h", py)
        self.assertNotIn("location_code", py.split("FEATURE_SETS")[1].split("}")[0] if "FEATURE_SETS" in py else "")

    def test_method_f_unchanged(self):
        cat = (ML_DIR / "consumption_category.py").read_text(encoding="utf-8")
        self.assertIn("median_h", cat)
        self.assertIn("1.5", cat)
        self.assertNotIn("location_code", cat.split("def ")[1].split("}")[0] if "def " in cat else "")

    def test_monthly_formula_unchanged(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("projected_monthly_energy_kwh", js)
        self.assertNotIn("location_scope", js)

    def test_phase4e_wording_preserved(self):
        html = (PUBLIC_DIR / "index.html").read_text(encoding="utf-8")
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("model Random Forest yang aktif", html)
        self.assertIn("Data prediksi tidak terkini", js)
        self.assertIn("Estimasi Data Awal Bulan", html)

    def test_prediction_has_category_fields(self):
        if not HISTORY_REAL.exists():
            self.skipTest("history_real.csv missing")
        records = csv_to_records(HISTORY_REAL)
        with patch("main.verify_firebase_id_token", return_value=None), \
             patch("export_firebase_history.fetch_history", return_value=records):
            response = self.client.post("/api/predict", headers={"Authorization": "Bearer x"})
        self.assertEqual(response.status_code, 200)
        prediction = response.json()["prediction"]
        self.assertIn("consumption_category", prediction)
        self.assertIn("category_threshold_kwh", prediction)

    def test_history_real_csv_frozen(self):
        import hashlib
        expected = "c321b9b56e07c390"
        actual = hashlib.sha256(HISTORY_REAL.read_bytes()).hexdigest()[:16]
        self.assertEqual(actual, expected, "history_real.csv checksum mismatch!")

    def test_history_live_csv_frozen(self):
        import hashlib
        expected = "6f6c461cb4b101cc"
        actual = hashlib.sha256(HISTORY_LIVE.read_bytes()).hexdigest()[:16]
        self.assertEqual(actual, expected, "history_live.csv checksum mismatch!")

    def test_rf_v2_model_frozen(self):
        import hashlib
        rf_v2 = ML_DIR / "output" / "random_forest_model_rfv2.joblib"
        if not rf_v2.exists():
            self.skipTest("RF-v2 model not found")
        expected = "47e2ae4406470a76"
        actual = hashlib.sha256(rf_v2.read_bytes()).hexdigest()[:16]
        self.assertEqual(actual, expected, "RF-v2 model checksum mismatch!")

    def test_rf_v1_model_frozen(self):
        import hashlib
        expected = "401088348c0656f0"
        actual = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()[:16]
        self.assertEqual(actual, expected, "RF-v1 model checksum mismatch!")


class LocationResetGuardTests(unittest.TestCase):
    def test_empty_reset_prevented_when_location_set(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("Gunakan salah satu lokasi yang tersedia", js)
        self.assertIn("Tidak bisa direset ke tidak diketahui", js)

    def test_empty_first_assignment_allowed(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("Lokasi pertama kali ditetapkan", js)

    def test_no_location_reset_message(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertNotIn("Lokasi direset", js)


class SessionIdParsingTests(unittest.TestCase):
    def test_parse_history_includes_session_id(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("session_id: val.session_id", js)

    def test_csv_exports_session_id_from_record(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("r.session_id", js)

    def test_csv_header_has_session_id(self):
        js = (PUBLIC_DIR / "app.js").read_text(encoding="utf-8")
        self.assertIn("location_code,location_label,session_id", js)


class FirmwareGetApiTests(unittest.TestCase):
    def _read_firmware(self):
        fw = FIRMWARE_DIR / "PZEM_FIREBASE.ino"
        if not fw.exists():
            self.skipTest("Firmware not found")
        return fw.read_text(encoding="utf-8", errors="replace")

    def test_uses_get_string_not_firebase_json(self):
        fw = self._read_firmware()
        self.assertIn('Database.get<String>', fw)
        self.assertNotIn('FirebaseJson *json = Database.get', fw)
        self.assertNotIn('json->get(data,', fw)

    def test_json_extract_helper_exists(self):
        fw = self._read_firmware()
        self.assertIn("jsonExtractString", fw)
        self.assertIn("String jsonExtractString", fw)

    def test_config_read_error_handling(self):
        fw = self._read_firmware()
        self.assertIn("lastError().code()", fw)
        self.assertIn("Config read error", fw)

    def test_immediate_first_fetch(self):
        fw = self._read_firmware()
        self.assertIn("configFetchAttempted", fw)
        loop = fw.split("void loop()")[1] if "void loop()" in fw else ""
        self.assertIn("!configFetchAttempted", loop)
        self.assertIn("configFetchAttempted = true", loop)

    def test_normal_poll_after_first(self):
        fw = self._read_firmware()
        loop = fw.split("void loop()")[1] if "void loop()" in fw else ""
        self.assertIn("CONFIG_POLL_INTERVAL", loop)


if __name__ == "__main__":
    unittest.main()
