from pathlib import Path
import json
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

MODEL_PATH = ML_DIR / "output" / "random_forest_model.joblib"
METRICS_PATH = ML_DIR / "output" / "metrics.json"

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


def attach_evaluation(prediction: dict) -> dict:
    payload = dict(prediction)
    if not METRICS_PATH.exists():
        return payload
    try:
        metrics = json.loads(METRICS_PATH.read_text(encoding="utf-8"))
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
    return {
        "status": "ok",
        "service": "smart-energy-random-forest-api",
        "model_exists": MODEL_PATH.exists()
    }


@app.get("/api/model-info")
def model_info():
    if not MODEL_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail="Random Forest model file not found."
        )

    model = joblib.load(MODEL_PATH)

    return {
        "status": "ok",
        "model_type": type(model).__name__,
        "n_estimators": getattr(model, "n_estimators", None),
        "n_features_in": getattr(model, "n_features_in_", None)
    }


@app.post("/api/predict")
def run_prediction(
    authorization: str | None = Header(default=None)
):
    token = get_bearer_token(authorization)
    verify_firebase_id_token(token)

    if not MODEL_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail="Random Forest model not found."
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
