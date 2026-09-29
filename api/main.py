from pathlib import Path
import json
import os
import sys
import tempfile

import joblib
import requests
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware

ROOT_DIR = Path(__file__).resolve().parents[1]
ML_DIR = ROOT_DIR / "ml"

if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

import export_firebase_history
import predict_energy
from train_random_forest import FEATURE_SETS

MODEL_REGISTRY = predict_energy.MODEL_REGISTRY
DEFAULT_MODEL_VERSION = predict_energy.DEFAULT_MODEL_VERSION


def _resolve_model_version() -> str:
    v = os.environ.get("SMART_ENERGY_MODEL_VERSION") or DEFAULT_MODEL_VERSION
    if v not in MODEL_REGISTRY:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid SMART_ENERGY_MODEL_VERSION: {v!r}. Valid: {list(MODEL_REGISTRY)}"
        )
    return v


def _model_paths():
    v = _resolve_model_version()
    reg = MODEL_REGISTRY[v]
    return v, ML_DIR / "output" / reg["model_path"], ML_DIR / "output" / reg["metrics_path"]


ALLOWED_ORIGINS = [
    "https://energy.muhadilaga.my.id",
    "https://smart-energy-monitoring-1e14f.web.app",
    "https://smart-energy-monitoring-1e14f.firebaseapp.com",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app = FastAPI(
    title="Smart Energy Random Forest API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


def get_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization header is required."
        )

    scheme, _, token = authorization.partition(" ")

    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=401,
            detail="Authorization must use Bearer token."
        )

    return token.strip()


def verify_firebase_id_token(id_token: str) -> None:
    try:
        api_key = export_firebase_history.pick_api_key()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Firebase API key is not configured."
        ) from exc

    url = f"https://identitytoolkit.googleapis.com/v1/accounts:lookup?key={api_key}"
    try:
        resp = requests.post(url, json={"idToken": id_token}, timeout=20)
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=503,
            detail="Unable to verify Firebase ID token."
        ) from exc

    if resp.status_code != 200:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired Firebase ID token."
        )

    try:
        users = resp.json().get("users") or []
    except ValueError as exc:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired Firebase ID token."
        ) from exc

    if not users:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired Firebase ID token."
        )


LOCATION_ALLOWLIST = {
    "ruang_kerja": "Ruang Kerja",
    "kamar_tidur": "Kamar Tidur",
    "ruang_tamu": "Ruang Tamu",
    "dapur": "Dapur",
}


def resolve_prediction_context(raw_records: dict, prediction_feature_timestamp: str) -> dict | None:
    """Resolve prediction source location/session metadata from raw Firebase records.

    Classifies context purity based on metadata completeness in the source
    feature hour (the hour of prediction_feature_timestamp).

    Purity states:
      SINGLE  — all source readings complete, exactly one (location, session) pair
      MIXED   — multiple distinct complete (location, session) pairs
      PARTIAL — at least one complete pair and at least one incomplete reading
      UNKNOWN — source readings exist but none have complete metadata
      null    — no source readings map to the feature hour
    """
    from datetime import datetime, timedelta, timezone

    if not raw_records or not prediction_feature_timestamp:
        return None

    # Parse feature timestamp to milliseconds epoch
    try:
        ft = datetime.fromisoformat(prediction_feature_timestamp)
        if ft.tzinfo is None:
            ft = ft.replace(tzinfo=timezone.utc)
        hour_start_ms = int(ft.timestamp() * 1000)
        hour_end_ms = hour_start_ms + 3_600_000
    except (ValueError, OSError):
        return None

    def _parse_ts(key: str, record: dict):
        ts = record.get("timestamp")
        if ts is not None:
            try:
                return int(float(ts))
            except (TypeError, ValueError):
                pass
        if key.isdigit():
            return int(key)
        return None

    # Collect readings in the feature hour
    source_readings = []
    for key, record in raw_records.items():
        if not isinstance(record, dict):
            continue
        ts = _parse_ts(str(key), record)
        if ts is not None and hour_start_ms <= ts < hour_end_ms:
            source_readings.append(record)

    if not source_readings:
        return None

    # Classify metadata completeness per reading
    complete_pairs = set()
    has_incomplete = False
    for r in source_readings:
        loc = (r.get("location_code") or "").strip()
        sess = (r.get("session_id") or "").strip()
        if loc and sess:
            complete_pairs.add((loc, sess))
        else:
            has_incomplete = True

    all_location_codes = set()
    all_session_ids = set()
    for r in source_readings:
        loc = (r.get("location_code") or "").strip()
        sess = (r.get("session_id") or "").strip()
        if loc:
            all_location_codes.add(loc)
        if sess:
            all_session_ids.add(sess)

    sorted_location_codes = sorted(all_location_codes)
    sorted_session_ids = sorted(all_session_ids)

    if not complete_pairs:
        if has_incomplete:
            # readings exist but none have complete metadata
            purity = "UNKNOWN"
        else:
            purity = "UNKNOWN"
    elif len(complete_pairs) > 1:
        purity = "MIXED"
    else:
        # exactly one complete pair
        if has_incomplete:
            purity = "PARTIAL"
        else:
            purity = "SINGLE"

    result = {
        "purity": purity,
        "location_codes": sorted_location_codes,
        "session_ids": sorted_session_ids,
    }

    if purity == "SINGLE":
        loc_code, sess_id = next(iter(complete_pairs))
        label = LOCATION_ALLOWLIST.get(loc_code, "Lokasi tidak diketahui")
        result["location_code"] = loc_code
        result["location_label"] = label
        result["session_id"] = sess_id
    elif purity == "PARTIAL" and len(complete_pairs) == 1:
        loc_code, sess_id = next(iter(complete_pairs))
        label = LOCATION_ALLOWLIST.get(loc_code, "Lokasi tidak diketahui")
        result["location_code"] = loc_code
        result["location_label"] = label
        result["session_id"] = sess_id
    else:
        result["location_code"] = None
        result["location_label"] = None
        result["session_id"] = None

    return result


def attach_evaluation(prediction: dict) -> dict:
    payload = dict(prediction)
    version = _resolve_model_version()
    reg = MODEL_REGISTRY[version]
    metrics_path = ML_DIR / "output" / reg["metrics_path"]
    if not metrics_path.exists():
        return payload
    try:
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return payload
    if not isinstance(metrics, dict):
        return payload
    payload["evaluation"] = {
        "train_rows": metrics.get("train_rows"),
        "test_rows": metrics.get("test_rows"),
        "raw_rows": metrics.get("raw_rows"),
        "hourly_rows": metrics.get("hourly_rows"),
        "technical_minimum_met": metrics.get("technical_minimum_met"),
        "research_minimum_met": metrics.get("research_minimum_met"),
        "baseline": metrics.get("baseline"),
        "random_forest": metrics.get("random_forest"),
    }
    return payload


@app.get("/health")
def health():
    version, model_path, _ = _model_paths()
    return {
        "status": "ok",
        "service": "smart-energy-random-forest-api",
        "model_version": version,
        "model_exists": model_path.exists()
    }


@app.get("/api/model-info")
def model_info():
    version, model_path, _ = _model_paths()
    if not model_path.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Random Forest model file not found for {version}."
        )

    model = joblib.load(model_path)
    features = FEATURE_SETS[version]

    return {
        "status": "ok",
        "model_version": version,
        "model_type": type(model).__name__,
        "n_estimators": getattr(model, "n_estimators", None),
        "n_features_in": getattr(model, "n_features_in_", None),
        "features": features,
    }


@app.post("/api/predict")
def run_prediction(
    authorization: str | None = Header(default=None)
):
    token = get_bearer_token(authorization)
    verify_firebase_id_token(token)

    version, model_path, _ = _model_paths()
    if not model_path.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Random Forest model not found for {version}."
        )

    try:
        with tempfile.TemporaryDirectory() as tmp:
            live_csv = Path(tmp) / "history_live.csv"
            live_json = Path(tmp) / "prediction_live.json"

            records = export_firebase_history.fetch_history(
                token,
                export_firebase_history.DEFAULT_NODE
            )

            if not records:
                raise HTTPException(
                    status_code=422,
                    detail="Firebase history is empty."
                )

            rows, export_stats = export_firebase_history.export_csv(
                records,
                live_csv
            )

            if len(rows) < 2:
                raise HTTPException(
                    status_code=422,
                    detail="Not enough Firebase history for prediction."
                )

            prediction = predict_energy.generate_prediction(
                data_path=live_csv,
                output_path=live_json
            )

            # Resolve prediction source context from raw records
            try:
                prediction_context = resolve_prediction_context(
                    records,
                    prediction.get("prediction_feature_timestamp", ""),
                )
            except Exception:
                prediction_context = None
            prediction["prediction_context"] = prediction_context

            prediction = attach_evaluation(prediction)

            return {
                "status": "ok",
                "source": "firebase_rtdb",
                "node": export_firebase_history.DEFAULT_NODE,
                "live_dataset": live_csv.name,
                "prediction_output": live_json.name,
                "export": export_stats,
                "prediction": prediction
            }

    except HTTPException:
        raise

    except predict_energy.PredictionError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc)
        ) from exc

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Firebase history retrieval or prediction failed."
        )
