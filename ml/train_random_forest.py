from __future__ import annotations

import argparse
import json
from pathlib import Path
from dataclasses import dataclass

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

FEATURES = [
    "voltage_mean",
    "current_mean",
    "power_mean",
    "frequency_mean",
    "power_factor_mean",
    "hour_of_day",
    "day_of_week",
    "energy_current_hour_kwh",
    "energy_lag_1h",
    "energy_lag_24h",
]

LOCAL_TZ = "Asia/Jakarta"

RAW_COLUMNS = [
    "timestamp",
    "voltage",
    "current",
    "power",
    "energy_kwh",
    "frequency",
    "power_factor",
]


def valid_number(value):
    if value is None or value == "":
        return None
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return n if np.isfinite(n) else None


def parse_args():
    parser = argparse.ArgumentParser(
        description="Train Random Forest from Firebase history CSV"
    )

    parser.add_argument(
        "--input",
        required=True,
        help="CSV history export with Firebase readings",
    )

    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parent / "output"),
        help="Output folder",
    )

    return parser.parse_args()


def load_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in RAW_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns: {', '.join(missing)}")
    df = df[RAW_COLUMNS].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True, errors="coerce").dt.tz_convert(LOCAL_TZ)
    for col in RAW_COLUMNS[1:]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def clean_rows(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    raw_rows = len(df)
    df = df.dropna(subset=["timestamp"]).copy()
    df = df.sort_values("timestamp")
    df = df.drop_duplicates(subset=["timestamp"], keep="last")
    data_quality = {
        "raw_rows": raw_rows,
        "rows_after_timestamp_drop": len(df),
        "timestamp_start": df["timestamp"].min().isoformat() if len(df) else None,
        "timestamp_end": df["timestamp"].max().isoformat() if len(df) else None,
        "missing_values": {c: int(df[c].isna().sum()) for c in df.columns},
    }
    return df, data_quality


def aggregate_hourly(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = df.sort_values("timestamp").reset_index(drop=True)
    df["hour"] = df["timestamp"].dt.floor("h")
    df["reading_gap_seconds"] = df["timestamp"].diff().dt.total_seconds()
    df["meter_delta"] = df["energy_kwh"].diff()
    df["meter_delta_valid"] = df["meter_delta"].where((df["meter_delta"].notna()) & (df["meter_delta"] >= 0))
    df["meter_reset_flag"] = df["meter_delta"].lt(0)
    df["meter_delta_invalid_flag"] = df["meter_delta"].isna() | df["meter_delta"].lt(0)
    rows = []
    for hour, group in df.groupby("hour", sort=True):
        group = group.sort_values("timestamp")
        valid_energy = group["energy_kwh"].dropna()
        hourly_consumption = float(group["meter_delta_valid"].sum()) if len(group) else None
        if hourly_consumption == 0 and group["meter_delta_valid"].notna().sum() == 0:
            hourly_consumption = None
        reset_count = int(group["meter_reset_flag"].fillna(False).sum())
        invalid_delta_count = int(group["meter_delta_invalid_flag"].fillna(False).sum())
        gap_count = int((group["reading_gap_seconds"] > 180).fillna(False).sum())
        coverage_flag = bool(gap_count > 0 or len(group) < 2 or reset_count > 0)
        row = {
            "hour": hour,
            "voltage_mean": group["voltage"].mean(),
            "current_mean": group["current"].mean(),
            "power_mean": group["power"].mean(),
            "frequency_mean": group["frequency"].mean(),
            "power_factor_mean": group["power_factor"].mean(),
            "energy_kwh_hourly": hourly_consumption,
            "reading_count": int(len(group)),
            "reset_count": reset_count,
            "invalid_delta_count": invalid_delta_count,
            "gap_count": gap_count,
            "coverage_flag": coverage_flag,
            "first_energy_kwh": valid_energy.iloc[0] if len(valid_energy) else None,
            "last_energy_kwh": valid_energy.iloc[-1] if len(valid_energy) else None,
        }
        rows.append(row)
    hourly = pd.DataFrame(rows)
    hourly = hourly.sort_values("hour").reset_index(drop=True)
    full_index = pd.date_range(start=hourly["hour"].min(), end=hourly["hour"].max(), freq="h", tz=LOCAL_TZ)
    hourly = hourly.set_index("hour").reindex(full_index)
    hourly.index.name = "hour"
    hourly = hourly.reset_index()
    hourly["observed_hour"] = hourly["energy_kwh_hourly"].notna()
    return hourly


def build_features(hourly: pd.DataFrame) -> pd.DataFrame:
    hourly = hourly.copy()
    hourly["hour_of_day"] = hourly["hour"].dt.hour
    hourly["day_of_week"] = hourly["hour"].dt.dayofweek
    hourly["energy_current_hour_kwh"] = hourly["energy_kwh_hourly"]
    hourly["energy_lag_1h"] = hourly["energy_current_hour_kwh"].shift(1)
    hourly["energy_lag_24h"] = hourly["energy_current_hour_kwh"].shift(24)
    hourly["energy_next_hour_kwh"] = hourly["energy_current_hour_kwh"].shift(-1)
    return hourly


def split_train_test(df: pd.DataFrame):
    df = df.dropna(subset=FEATURES + ["energy_next_hour_kwh"]).copy()
    df = df.reset_index(drop=True)
    if len(df) < 10:
        return df.iloc[:0], df.iloc[:0]
    split_idx = int(len(df) * 0.8)
    split_idx = max(1, min(split_idx, len(df) - 1))
    train = df.iloc[:split_idx].copy()
    test = df.iloc[split_idx:].copy()
    return train, test


def metrics(y_true, y_pred):
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))

    if len(y_true) >= 2:
        r2 = float(r2_score(y_true, y_pred))
    else:
        r2 = None

    return {
        "mae": mae,
        "rmse": rmse,
        "r2": r2,
    }


def main():
    args = parse_args()
    input_path = Path(args.input)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = load_csv(input_path)
    df, quality = clean_rows(df)

    print(json.dumps({"stage": "load", **quality}, default=str, ensure_ascii=False, indent=2))

    if len(df) < 2:
        print("Not enough raw rows to build hourly data.")
        return 0

    hourly = aggregate_hourly(df)
    hourly = build_features(hourly)

    quality.update({
        "hourly_rows": int(len(hourly)),
        "negative_energy_delta_rows": int(hourly["reset_count"].fillna(0).sum()),
        "invalid_delta_rows": int(hourly["invalid_delta_count"].fillna(0).sum()),
        "hourly_gap_count": int(hourly["gap_count"].fillna(0).sum()),
        "coverage_flagged_rows": int(hourly["coverage_flag"].fillna(False).sum()),
    })
    print(json.dumps({"stage": "hourly", **quality}, default=str, ensure_ascii=False, indent=2))

    model_df = hourly.dropna(subset=FEATURES + ["energy_current_hour_kwh", "energy_next_hour_kwh"]).copy()
    model_df = model_df[(model_df["coverage_flag"] == False) & (model_df["observed_hour"] == True)].copy()
    model_df = model_df.reset_index(drop=True)

    technical_minimum = len(model_df) >= 10
    research_minimum = len(model_df) >= 48
    if not technical_minimum:
        print("Dataset not sufficient for training after feature engineering.")
        print("Technical minimum: at least 10 usable hourly rows.")
        print("Research adequacy: several days or more recommended; 24h lag needs broader coverage.")
        return 0
    if not research_minimum:
        print("Warning: dataset meets technical minimum but is not yet adequate for research-grade training.")

    train, test = split_train_test(model_df)
    if len(train) == 0 or len(test) == 0:
        print("Dataset not sufficient for chronological split.")
        return 0

    X_train = train[FEATURES]
    y_train = train["energy_next_hour_kwh"]
    X_test = test[FEATURES]
    y_test = test["energy_next_hour_kwh"]

    baseline_pred = test["energy_current_hour_kwh"].to_numpy()
    baseline_metrics = metrics(y_test, baseline_pred)

    model = RandomForestRegressor(
        n_estimators=200,
        random_state=42,
        n_jobs=-1,
        max_depth=None,
        min_samples_leaf=1,
    )
    model.fit(X_train, y_train)
    rf_pred = model.predict(X_test)
    rf_metrics = metrics(y_test, rf_pred)

    feature_importance = pd.DataFrame({
        "feature": FEATURES,
        "importance": model.feature_importances_,
    }).sort_values("importance", ascending=False)

    metrics_json = {
        "model": "RandomForestRegressor",
        "model_version": "RF-v1",
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "raw_rows": int(quality["raw_rows"]),
        "hourly_rows": int(len(hourly)),
        "technical_minimum_met": technical_minimum,
        "research_minimum_met": research_minimum,
        "baseline": baseline_metrics,
        "random_forest": rf_metrics,
        "data_quality": quality,
    }

    joblib.dump(model, output_dir / "random_forest_model.joblib")
    (output_dir / "metrics.json").write_text(json.dumps(metrics_json, indent=2, ensure_ascii=False), encoding="utf-8")
    feature_importance.to_csv(output_dir / "feature_importance.csv", index=False)

    print(json.dumps(metrics_json, indent=2, ensure_ascii=False))
    print(f"Saved model to {output_dir / 'random_forest_model.joblib'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
