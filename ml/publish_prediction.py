from __future__ import annotations

import getpass
import json
import sys
from pathlib import Path
from typing import Any

import requests

DATABASE_URL = "https://smart-energy-monitoring-1e14f-default-rtdb.asia-southeast1.firebasedatabase.app"
DEVICE_ID = "esp32-01"
PREDICTION_NODE = f"predictions/{DEVICE_ID}/latest"

REQUIRED_PREDICTION_FIELDS = [
    "generated_at",
    "model_version",
    "research_minimum_met",
    "status",
    "prediction_status",
    "monthly_projection_status",
    "predicted_next_hour_kwh",
    "prediction_feature_timestamp",
    "prediction_target_timestamp",
    "prediction_staleness_hours",
    "prediction_fresh",
    "rf_used_in_monthly_projection",
    "first_valid_raw_timestamp",
    "last_valid_raw_timestamp",
    "estimated_unobserved_past_energy_kwh",
    "observed_energy_kwh",
    "average_observed_hourly_kwh",
    "projected_remaining_energy_kwh",
    "projected_monthly_energy_kwh",
    "coverage_from_month_start",
    "missing_hourly_bucket_count",
    "raw_reading_gap_event_count",
    "projection_method",
    "warning",
]


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def pick_api_key() -> str:
    try:
        from firebase_config import firebaseConfig  # type: ignore
        api_key = firebaseConfig.get("apiKey")
        if api_key:
            return api_key
    except Exception:
        pass

    cfg = project_root() / "public" / "firebase-config.js"
    text = cfg.read_text(encoding="utf-8")
    marker = 'apiKey: "'
    start = text.find(marker)
    if start == -1:
        raise RuntimeError("apiKey tidak ditemukan di public/firebase-config.js")
    start += len(marker)
    end = text.find('"', start)
    if end == -1:
        raise RuntimeError("apiKey parse gagal")
    api_key = text[start:end].strip()
    if not api_key:
        raise RuntimeError("apiKey kosong")
    return api_key


def auth_with_firebase(api_key: str, email: str, password: str) -> str:
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
    payload = {"email": email, "password": password, "returnSecureToken": True}
    try:
        resp = requests.post(url, json=payload, timeout=20)
    except requests.RequestException as exc:
        raise RuntimeError(f"Auth request gagal: {exc}") from exc
    if resp.status_code != 200:
        try:
            msg = resp.json().get("error", {}).get("message", "AUTH_FAILED")
        except Exception:
            msg = "AUTH_FAILED"
        raise RuntimeError(f"Auth gagal: {msg}")
    token = resp.json().get("idToken")
    if not token:
        raise RuntimeError("Auth berhasil tapi idToken tidak ada")
    return token


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise RuntimeError(f"File tidak ditemukan: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"JSON tidak valid: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"JSON root harus object: {path}")
    return data


def validate_prediction(data: dict[str, Any]) -> None:
    missing = [field for field in REQUIRED_PREDICTION_FIELDS if field not in data]
    if missing:
        raise RuntimeError(
            "Field prediction wajib tidak ada: " + ", ".join(missing)
        )

    if data.get("prediction_status") != "fresh":
        raise RuntimeError(
            "Publish ditolak: prediction_status bukan 'fresh' "
            f"(aktual: {data.get('prediction_status')!r})"
        )

    if data.get("prediction_fresh") is not True:
        raise RuntimeError(
            "Publish ditolak: prediction_fresh harus true "
            f"(aktual: {data.get('prediction_fresh')!r})"
        )

    staleness = data.get("prediction_staleness_hours")
    if not isinstance(staleness, (int, float)):
        raise RuntimeError(
            "Publish ditolak: prediction_staleness_hours tidak valid"
        )

    if staleness < 0:
        raise RuntimeError(
            "Publish ditolak: prediction_staleness_hours bernilai negatif"
        )

    if staleness > 1:
        raise RuntimeError(
            "Publish ditolak: prediction terlalu stale "
            f"({staleness:.2f} jam > batas 1 jam)"
        )


def build_payload(prediction: dict[str, Any], metrics: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(prediction)
    if metrics:
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


def publish_payload(id_token: str, payload: dict[str, Any]) -> None:
    url = f"{DATABASE_URL}/{PREDICTION_NODE}.json"
    params = {"auth": id_token}
    try:
        resp = requests.put(url, params=params, json=payload, timeout=30)
    except requests.RequestException as exc:
        raise RuntimeError(f"RTDB publish gagal: {exc}") from exc
    if resp.status_code != 200:
        raise RuntimeError(f"RTDB publish gagal: HTTP {resp.status_code}: {resp.text[:200]}")


def main() -> int:
    root = project_root()
    prediction_path = root / "ml" / "output" / "prediction.json"
    metrics_path = root / "ml" / "output" / "metrics.json"

    prediction = load_json(prediction_path)
    validate_prediction(prediction)
    metrics = load_json(metrics_path) if metrics_path.exists() else None
    payload = build_payload(prediction, metrics)

    print("Ringkasan publish prediction:")
    print(json.dumps({
        "device_id": DEVICE_ID,
        "node": PREDICTION_NODE,
        "prediction_status": payload.get("prediction_status"),
        "prediction_fresh": payload.get("prediction_fresh"),
        "prediction_feature_timestamp": payload.get("prediction_feature_timestamp"),
        "last_valid_raw_timestamp": payload.get("last_valid_raw_timestamp"),
        "projected_monthly_energy_kwh": payload.get("projected_monthly_energy_kwh"),
    }, indent=2, ensure_ascii=False))

    confirm = input("Publish prediction ini ke Firebase? [y/N] ").strip().lower()
    if confirm != "y":
        print("Publish dibatalkan. Tidak ada write ke Firebase.")
        return 0

    api_key = pick_api_key()
    email = input("Firebase email: ").strip()
    if not email:
        raise SystemExit("Email kosong")
    password = getpass.getpass("Firebase password: ")
    if not password:
        raise SystemExit("Password kosong")

    token = auth_with_firebase(api_key, email, password)
    publish_payload(token, payload)
    print(f"Publish sukses: {PREDICTION_NODE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
