import sys
import os
import json
from pathlib import Path
import pandas as pd
import numpy as np
import joblib
from datetime import datetime

MAX_PREDICTION_STALENESS_HOURS = 2.0

# Import train_random_forest for exact preprocessing reuse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import train_random_forest as trf
from consumption_category import compute_consumption_category

MODEL_REGISTRY = {
    "RF-v1": {
        "model_path": "random_forest_model.joblib",
        "metrics_path": "metrics.json",
        "features": trf.FEATURE_SETS["RF-v1"],
        "include_lag_24h": True,
    },
    "RF-v2": {
        "model_path": "random_forest_model_rfv2.joblib",
        "metrics_path": "metrics_rfv2.json",
        "features": trf.FEATURE_SETS["RF-v2"],
        "include_lag_24h": False,
    },
}

DEFAULT_MODEL_VERSION = "RF-v1"


class PredictionError(RuntimeError):
    """Raised when inference cannot be completed. Safe for API callers; CLI maps this to exit 1."""


def _resolve_model_version(explicit: str | None = None) -> str:
    version = explicit or os.environ.get("SMART_ENERGY_MODEL_VERSION") or DEFAULT_MODEL_VERSION
    if version not in MODEL_REGISTRY:
        raise PredictionError(f"Unknown model version: {version!r}. Valid: {list(MODEL_REGISTRY)}")
    return version


def _validate_model(model, expected_features: list[str], version: str) -> None:
    actual = getattr(model, "n_features_in_", None)
    if actual is not None and actual != len(expected_features):
        raise PredictionError(
            f"{version} feature contract mismatch: "
            f"model expects {actual} features, registry defines {len(expected_features)}."
        )
    names = getattr(model, "feature_names_in_", None)
    if names is not None and list(names) != expected_features:
        raise PredictionError(
            f"{version} feature order mismatch: "
            f"model={list(names)}, expected={expected_features}."
        )


def generate_prediction(data_path=None, output_path=None, model_version=None):
    base_dir = Path(__file__).parent.parent
    version = _resolve_model_version(model_version)
    reg = MODEL_REGISTRY[version]

    data_path = Path(data_path) if data_path is not None else base_dir / "ml" / "data" / "history_real.csv"
    model_path = base_dir / "ml" / "output" / reg["model_path"]
    metrics_path = base_dir / "ml" / "output" / reg["metrics_path"]
    output_path = Path(output_path) if output_path is not None else base_dir / "ml" / "output" / "prediction.json"
    features = reg["features"]

    if not data_path.exists():
        raise PredictionError(f"Data file not found: {data_path}")
    if not model_path.exists():
        raise PredictionError(f"Model file not found: {model_path}")

    print("Loading and preprocessing data...")
    df = trf.load_csv(data_path)
    raw_df, quality = trf.clean_rows(df)

    if len(raw_df) < 2:
        raise PredictionError("Error: Not enough raw rows to perform hourly aggregation.")

    hourly = trf.aggregate_hourly(raw_df)
    hourly = trf.build_features(hourly, include_lag_24h=reg["include_lag_24h"])

    # Filter for valid rows with required features
    model_df = hourly.dropna(subset=features).copy()
    model_df = model_df[(model_df["coverage_flag"] == False) & (model_df["observed_hour"] == True)].copy()

    if len(model_df) == 0:
        raise PredictionError(
            f"Error: No valid rows with complete features found. "
            f"{version} requires {len(features)} features."
        )

    # Get the latest valid row for prediction
    latest_row = model_df.iloc[-1]
    latest_ts = latest_row["hour"]
    prediction_feature_timestamp = latest_ts
    prediction_target_timestamp = prediction_feature_timestamp + pd.Timedelta(hours=1)

    print(f"Predicting next hour for latest valid feature timestamp: {prediction_feature_timestamp.isoformat()}")

    # Load model with guard rails
    model = joblib.load(model_path)
    _validate_model(model, features, version)

    X = latest_row[features].to_frame().T
    pred = float(model.predict(X)[0])

    # Clamp negative predictions
    if pred < 0:
        print(f"Note: Model predicted {pred:.6f} kWh. Clamping to 0.0 kWh.")
        pred = 0.0

    # ── Consumption category (Method F) ──
    category_result = compute_consumption_category(
        predicted_kwh=pred,
        prediction_target_timestamp=prediction_target_timestamp,
        hourly_dataframe=hourly,
    )

    # Filter valid data specifically for the current month
    month_data = hourly[
        (hourly["hour"].dt.year == latest_ts.year) &
        (hourly["hour"].dt.month == latest_ts.month)
    ]

    valid_month_data = month_data[month_data["observed_hour"] == True]

    if valid_month_data.empty:
        raise PredictionError("Error: No valid observation found in the current month.")

    # Extract exact raw timestamps for precise duration
    obs_start_hour = valid_month_data["hour"].min()
    obs_end_hour = valid_month_data["hour"].max()

    mask = (raw_df["timestamp"] >= obs_start_hour) & (raw_df["timestamp"] < obs_end_hour + pd.Timedelta(hours=1)) & (raw_df["energy_kwh"].notna())
    span_raw = raw_df[mask].sort_values("timestamp")

    first_valid_raw_timestamp = span_raw.iloc[0]["timestamp"]
    last_valid_raw_timestamp = span_raw.iloc[-1]["timestamp"]

    observed_duration_hours = (last_valid_raw_timestamp - first_valid_raw_timestamp).total_seconds() / 3600.0
    prediction_staleness_hours = (last_valid_raw_timestamp - prediction_feature_timestamp).total_seconds() / 3600.0
    prediction_fresh = prediction_staleness_hours <= MAX_PREDICTION_STALENESS_HOURS
    prediction_status = "fresh" if prediction_fresh else "stale"

    # Category validity depends on freshness
    category_result["category_valid_for_current_state"] = prediction_fresh

    # Calculate observed metrics
    observed_energy_kwh = float(valid_month_data["energy_kwh_hourly"].sum())

    if observed_duration_hours > 0:
        average_observed_hourly_kwh = observed_energy_kwh / observed_duration_hours
    else:
        average_observed_hourly_kwh = 0.0

    # ML Pipeline hourly bucket metrics
    observation_span_hours = int((obs_end_hour - obs_start_hour).total_seconds() / 3600) + 1
    observed_valid_hour_count = int(len(valid_month_data))
    missing_hourly_bucket_count = observation_span_hours - observed_valid_hour_count
    raw_reading_gap_event_count = int(month_data["gap_count"].fillna(0).sum())

    if missing_hourly_bucket_count > 0:
        print(f"Gap Analysis: {missing_hourly_bucket_count} missing hourly buckets detected within the {observation_span_hours}-hour bucket span.")
        print("Methodology Note: Cumulative meter delta processing ensures that energy consumption during gaps is absorbed in the next valid hourly reading.")

    # Time boundaries and projection math (continuous, no rounding)
    month_start = first_valid_raw_timestamp.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if month_start.month == 12:
        month_end = month_start.replace(year=month_start.year+1, month=1)
    else:
        month_end = month_start.replace(month=month_start.month+1)

    month_total_hours = (month_end - month_start).total_seconds() / 3600.0

    unobserved_hours_before_dataset = (first_valid_raw_timestamp - month_start).total_seconds() / 3600.0
    unobserved_hours_before_dataset = max(0.0, unobserved_hours_before_dataset)

    remaining_hours_from_latest_observation = (month_end - last_valid_raw_timestamp).total_seconds() / 3600.0
    remaining_hours_from_latest_observation = max(0.0, remaining_hours_from_latest_observation)

    # Proof of continuity
    total_split_hours = unobserved_hours_before_dataset + observed_duration_hours + remaining_hours_from_latest_observation
    assert abs(total_split_hours - month_total_hours) < 1e-5, f"Time split mismatch: {total_split_hours} vs {month_total_hours}"

    estimated_unobserved_past_energy_kwh = unobserved_hours_before_dataset * average_observed_hourly_kwh

    # Future projection calculations
    rf_used_in_monthly_projection = bool(prediction_fresh and remaining_hours_from_latest_observation >= 1.0)
    if rf_used_in_monthly_projection:
        projected_remaining_energy_kwh = pred + (remaining_hours_from_latest_observation - 1.0) * average_observed_hourly_kwh
    else:
        projected_remaining_energy_kwh = remaining_hours_from_latest_observation * average_observed_hourly_kwh

    # Total Monthly Projection
    projected_monthly_energy_kwh = (
        estimated_unobserved_past_energy_kwh +
        observed_energy_kwh +
        projected_remaining_energy_kwh
    )

    coverage_from_month_start = bool(unobserved_hours_before_dataset == 0.0)

    # Status and Warnings Configuration
    status = "preliminary"
    monthly_projection_status = "preliminary"
    warnings_list = []
    model_version_label = version
    research_minimum_met = False

    if not coverage_from_month_start:
        warnings_list.append("Dataset tidak mencakup awal bulan. Konsumsi sebelum observation_start diestimasi menggunakan rata-rata konsumsi per jam dari data aktual yang tersedia. Proyeksi bulanan bersifat preliminary.")

    if not prediction_fresh:
        warnings_list.append(
            f"Prediksi Random Forest terbaru menggunakan feature timestamp {prediction_feature_timestamp.isoformat()} "
            "dan bersifat stale terhadap data mentah terbaru. Prediksi tersebut tidak digunakan dalam proyeksi bulanan saat ini."
        )

    if metrics_path.exists():
        with open(metrics_path, "r", encoding="utf-8") as f:
            metrics_data = json.load(f)
            model_version_label = metrics_data.get("model_version", version)
            research_minimum_met = bool(metrics_data.get("research_minimum_met", False))
            if not research_minimum_met:
                warnings_list.append("Dataset belum memenuhi minimum penelitian. Proyeksi hanya digunakan untuk verifikasi pipeline dan belum merupakan hasil akhir penelitian.")

    warning_str = " | ".join(warnings_list) if warnings_list else None

    projection_method = (
        "Short-term Random Forest prediction (1 hour) is generated from the latest complete feature row. "
        "The average observed hourly consumption rate uses precise raw timestamp duration. "
        "If the RF prediction is stale, monthly projection uses the observed average rate for the entire remaining period; RF does not directly predict the monthly total."
    )

    # Construct Output JSON
    out = {
        "generated_at": datetime.now(latest_ts.tz).isoformat(),
        "model_version": model_version_label,
        "research_minimum_met": research_minimum_met,
        "status": status,
        "prediction_status": prediction_status,
        "monthly_projection_status": monthly_projection_status,
        "predicted_next_hour_kwh": pred,
        "prediction_feature_timestamp": prediction_feature_timestamp.isoformat(),
        "prediction_target_timestamp": prediction_target_timestamp.isoformat(),
        "prediction_staleness_hours": prediction_staleness_hours,
        "prediction_fresh": prediction_fresh,
        "rf_used_in_monthly_projection": rf_used_in_monthly_projection,

        "first_valid_raw_timestamp": first_valid_raw_timestamp.isoformat(),
        "last_valid_raw_timestamp": last_valid_raw_timestamp.isoformat(),

        "unobserved_hours_before_dataset": unobserved_hours_before_dataset,
        "estimated_unobserved_past_energy_kwh": estimated_unobserved_past_energy_kwh,

        "observation_start": obs_start_hour.isoformat(),
        "observation_end": obs_end_hour.isoformat(),
        "observation_span_hours": observation_span_hours,
        "observed_duration_hours": observed_duration_hours,
        "observed_valid_hour_count": observed_valid_hour_count,
        "missing_hourly_bucket_count": missing_hourly_bucket_count,
        "raw_reading_gap_event_count": raw_reading_gap_event_count,
        "observed_energy_kwh": observed_energy_kwh,

        "month_total_hours": month_total_hours,
        "remaining_hours_from_latest_observation": remaining_hours_from_latest_observation,
        "average_observed_hourly_kwh": average_observed_hourly_kwh,

        "projected_remaining_energy_kwh": projected_remaining_energy_kwh,
        "projected_monthly_energy_kwh": projected_monthly_energy_kwh,

        "coverage_from_month_start": coverage_from_month_start,
        "projection_method": projection_method,

        # Category fields (additive)
        **category_result,
    }

    if warning_str:
        out["warning"] = warning_str

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print(f"Prediction generated successfully at {output_path}")
    return out

if __name__ == "__main__":
    try:
        generate_prediction()
    except PredictionError as exc:
        print(str(exc))
        sys.exit(1)
