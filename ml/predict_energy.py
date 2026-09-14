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
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import train_random_forest as trf

def generate_prediction():
    base_dir = Path(__file__).parent.parent
    data_path = base_dir / "ml" / "data" / "history_real.csv"
    model_path = base_dir / "ml" / "output" / "random_forest_model.joblib"
    metrics_path = base_dir / "ml" / "output" / "metrics.json"
    output_path = base_dir / "ml" / "output" / "prediction.json"
    
    if not data_path.exists():
        print(f"Data file not found: {data_path}")
        sys.exit(1)
    if not model_path.exists():
        print(f"Model file not found: {model_path}")
        sys.exit(1)
        
    print("Loading and preprocessing data...")
    df = trf.load_csv(data_path)
    # Get cleaned raw data for precise timestamps
    raw_df, quality = trf.clean_rows(df)
    
    if len(raw_df) < 2:
        print("Error: Not enough raw rows to perform hourly aggregation.")
        sys.exit(1)
        
    hourly = trf.aggregate_hourly(raw_df)
    hourly = trf.build_features(hourly)
    
    # Filter for valid rows that can be predicted (features available)
    model_df = hourly.dropna(subset=trf.FEATURES).copy()
    model_df = model_df[(model_df["coverage_flag"] == False) & (model_df["observed_hour"] == True)].copy()
    
    if len(model_df) == 0:
        print("Error: No valid rows with complete features found. Lag 24h might not be fulfilled.")
        sys.exit(1)
        
    # Get the latest valid row for prediction
    latest_row = model_df.iloc[-1]
    latest_ts = latest_row["hour"]
    prediction_feature_timestamp = latest_ts
    prediction_target_timestamp = prediction_feature_timestamp + pd.Timedelta(hours=1)
    
    print(f"Predicting next hour for latest valid feature timestamp: {prediction_feature_timestamp.isoformat()}")
    
    # Load model and predict next hour
    model = joblib.load(model_path)
    X = latest_row[trf.FEATURES].to_frame().T
    pred = float(model.predict(X)[0])
    
    # Clamp negative predictions
    if pred < 0:
        print(f"Note: Model predicted {pred:.6f} kWh. Clamping to 0.0 kWh.")
        pred = 0.0
        
    # Filter valid data specifically for the current month
    month_data = hourly[
        (hourly["hour"].dt.year == latest_ts.year) & 
        (hourly["hour"].dt.month == latest_ts.month)
    ]
    
    valid_month_data = month_data[month_data["observed_hour"] == True]
    
    if valid_month_data.empty:
        print("Error: No valid observation found in the current month.")
        sys.exit(1)
        
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
    
    # Calculate observed metrics
    # Observed energy is sum of validated hourly deltas, which inherently captures energy consumed during gaps
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
    # RF prediction is only used in monthly projection when the feature row is fresh.
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
    model_version = "unknown"
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
            metrics = json.load(f)
            model_version = metrics.get("model_version", "RF-v1")
            research_minimum_met = bool(metrics.get("research_minimum_met", False))
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
        "model_version": model_version,
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
        "projection_method": projection_method
    }
    
    if warning_str:
        out["warning"] = warning_str
        
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        
    print(f"Prediction generated successfully at {output_path}")

if __name__ == "__main__":
    generate_prediction()
