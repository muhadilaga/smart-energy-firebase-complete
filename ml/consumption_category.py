"""Consumption category: Method F hybrid threshold (post-prediction).

Kategori konsumsi berbasis threshold terhadap hasil prediksi
Random Forest Regression — bukan classifier.
"""
from __future__ import annotations

import numpy as np


def compute_consumption_category(
    predicted_kwh: float | None,
    prediction_target_timestamp,
    hourly_dataframe,
    min_bin_samples: int = 8,
) -> dict:
    """Method F hybrid: per-hour-of-day median+MAD with P90 global floor.

    Parameters
    ----------
    predicted_kwh : float or None
        Output of RF regression for next-hour energy.
    prediction_target_timestamp : datetime with tz
        Target hour (feature + 1 hour). NOT the feature timestamp.
    hourly_dataframe : DataFrame
        Output of aggregate_hourly() + build_features().
        Must have columns: hour, energy_kwh_hourly, observed_hour, coverage_flag.
    min_bin_samples : int
        Minimum observations in same-hour bin to use per-hour method.

    Returns
    -------
    dict with consumption_category fields (JSON-safe Python natives).
    """
    # --- Valid population: historical observations BEFORE target ---
    if hourly_dataframe is None or len(hourly_dataframe) == 0:
        return _empty_result(prediction_target_timestamp, "no hourly data provided")

    valid = hourly_dataframe[
        (hourly_dataframe["observed_hour"] == True)
        & (hourly_dataframe["coverage_flag"] == False)
        & (hourly_dataframe["energy_kwh_hourly"].notna())
        & (hourly_dataframe["hour"] < prediction_target_timestamp)
    ].copy()

    values = valid["energy_kwh_hourly"].to_numpy(dtype=float)

    if len(values) == 0:
        return _empty_result(prediction_target_timestamp, "no valid historical observations before target")

    # --- Invalid prediction → TIDAK_TERSEDIA ---
    if predicted_kwh is None or not np.isfinite(predicted_kwh):
        p90 = float(np.percentile(values, 90))
        return {
            "consumption_category": "TIDAK_TERSEDIA",
            "category_threshold_kwh": None,
            "category_baseline_kwh": None,
            "category_baseline_samples": 0,
            "category_mad": None,
            "category_p90_global": _safe_float(p90),
            "category_method": "hybrid_median_mad_p90",
            "category_scope": "unavailable",
            "category_note": "predicted value is None or non-finite",
            "category_target_hour": int(prediction_target_timestamp.hour),
            "category_valid_for_current_state": False,
        }

    # --- Global P90 ---
    p90_global = float(np.percentile(values, 90))

    # --- Hour-of-day subset ---
    target_hod = prediction_target_timestamp.hour
    hod_mask = valid["hour"].dt.hour == target_hod
    hod_values = valid.loc[hod_mask, "energy_kwh_hourly"].to_numpy(dtype=float)
    n_h = len(hod_values)

    if n_h >= min_bin_samples:
        median_h = float(np.median(hod_values))
        mad_h = float(np.median(np.abs(hod_values - median_h)))
        per_hour_threshold = median_h + 1.5 * mad_h
        threshold = max(p90_global, per_hour_threshold)
        scope = "hour_of_day"
        baseline = median_h
        baseline_samples = int(n_h)
        note = (
            f"n_bin={n_h} >= {min_bin_samples}, "
            f"threshold=max(P90={p90_global:.4f}, median+1.5MAD={per_hour_threshold:.4f}) "
            f"= {threshold:.4f}"
        )
    else:
        threshold = p90_global
        scope = "global_p90_fallback"
        baseline = float(np.median(values))
        baseline_samples = int(len(values))
        mad_h = None
        note = f"n_bin={n_h} < {min_bin_samples}, fallback P90 global={p90_global:.4f}"

    # --- Category ---
    if predicted_kwh > threshold:
        category = "BOROS"
    else:
        category = "NORMAL"

    return {
        "consumption_category": category,
        "category_threshold_kwh": _safe_float(threshold),
        "category_baseline_kwh": _safe_float(baseline),
        "category_baseline_samples": baseline_samples,
        "category_mad": _safe_float(mad_h) if mad_h is not None else None,
        "category_p90_global": _safe_float(p90_global),
        "category_method": "hybrid_median_mad_p90",
        "category_scope": scope,
        "category_note": note,
        "category_target_hour": int(target_hod),
        "category_valid_for_current_state": True,
    }


def _empty_result(target_ts, reason: str) -> dict:
    return {
        "consumption_category": "TIDAK_TERSEDIA",
        "category_threshold_kwh": None,
        "category_baseline_kwh": None,
        "category_baseline_samples": 0,
        "category_mad": None,
        "category_p90_global": None,
        "category_method": "hybrid_median_mad_p90",
        "category_scope": "unavailable",
        "category_note": reason,
        "category_target_hour": int(target_ts.hour) if target_ts is not None else None,
        "category_valid_for_current_state": False,
    }


def _safe_float(v):
    """Convert to Python float, raising on NaN/None."""
    if v is None:
        return None
    f = float(v)
    if not np.isfinite(f):
        return None
    return f
