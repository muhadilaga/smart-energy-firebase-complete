from __future__ import annotations

import csv
import getpass
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

API_KEY = None
DATABASE_URL = "https://smart-energy-monitoring-1e14f-default-rtdb.asia-southeast1.firebasedatabase.app"
DEFAULT_NODE = "readings/esp32-01"

RAW_COLUMNS = ["timestamp", "voltage", "current", "power", "energy_kwh", "frequency", "power_factor"]


def pick_api_key() -> str:
    try:
        from firebase_config import firebaseConfig  # type: ignore
        api_key = firebaseConfig.get("apiKey")
        if api_key:
            return api_key
    except Exception:
        pass

    cfg = Path(__file__).resolve().parent.parent / "public" / "firebase-config.js"
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
    data = resp.json()
    token = data.get("idToken")
    if not token:
        raise RuntimeError("Auth berhasil tapi idToken tidak ada")
    return token


def fetch_history(id_token: str, node_path: str = DEFAULT_NODE) -> dict[str, Any]:
    url = f"{DATABASE_URL}/{node_path}.json"
    params = {"auth": id_token}
    try:
        resp = requests.get(url, params=params, timeout=30)
    except requests.RequestException as exc:
        raise RuntimeError(f"RTDB request gagal: {exc}") from exc
    if resp.status_code != 200:
        raise RuntimeError(f"RTDB read gagal: HTTP {resp.status_code}")
    data = resp.json()
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise RuntimeError("RTDB payload bukan object")
    return data


def to_number(value):
    if value is None or value == "":
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if n == n else None


def parse_timestamp(key: str, record: dict[str, Any]):
    ts = record.get("timestamp")
    ts_num = to_number(ts)
    if ts_num is not None:
        return int(ts_num)
    if key.isdigit():
        return int(key)
    return None


def export_csv(records: dict[str, Any], output_path: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows = []
    missing_counter = Counter()
    child_count = len(records)

    for key, record in records.items():
        if not isinstance(record, dict):
            continue
        ts = parse_timestamp(str(key), record)
        if ts is None:
            missing_counter["timestamp"] += 1
            continue
        row = {"timestamp": ts}
        for col in RAW_COLUMNS[1:]:
            val = to_number(record.get(col))
            if val is None:
                missing_counter[col] += 1
            row[col] = val
        rows.append(row)

    rows.sort(key=lambda r: r["timestamp"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RAW_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in RAW_COLUMNS})

    duplicates = 0
    seen = set()
    for row in rows:
        ts = row["timestamp"]
        if ts in seen:
            duplicates += 1
        seen.add(ts)

    stats = {
        "child_count": child_count,
        "valid_rows": len(rows),
        "duplicate_timestamp_count": duplicates,
        "missing_field_count": sum(missing_counter.values()),
    }
    return rows, stats


def print_summary(rows: list[dict[str, Any]], stats: dict[str, int]):
    if rows:
        earliest = datetime.fromtimestamp(rows[0]["timestamp"] / 1000, tz=timezone.utc).astimezone()
        latest = datetime.fromtimestamp(rows[-1]["timestamp"] / 1000, tz=timezone.utc).astimezone()
        coverage_ms = rows[-1]["timestamp"] - rows[0]["timestamp"]
        coverage_hours = coverage_ms / 1000 / 3600
    else:
        earliest = latest = None
        coverage_hours = 0

    report = {
        **stats,
        "timestamp_earliest": earliest.isoformat() if earliest else None,
        "timestamp_latest": latest.isoformat() if latest else None,
        "coverage_hours": round(coverage_hours, 3),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Export Firebase RTDB history to CSV using Firebase Auth email/password")
    parser.add_argument("--node", default=DEFAULT_NODE, help="RTDB node path, default readings/esp32-01")
    parser.add_argument("--output", default="ml/data/history_real.csv", help="Output CSV path")
    args = parser.parse_args()

    api_key = pick_api_key()
    email = input("Firebase email: ").strip()
    if not email:
        raise SystemExit("Email kosong")
    password = getpass.getpass("Firebase password: ")
    if not password:
        raise SystemExit("Password kosong")

    id_token = auth_with_firebase(api_key, email, password)
    records = fetch_history(id_token, args.node)
    rows, stats = export_csv(records, Path(args.output))
    print_summary(rows, stats)
    print(f"Saved: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
