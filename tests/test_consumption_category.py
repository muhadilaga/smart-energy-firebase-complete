"""Tests for ml/consumption_category.py — Method F hybrid threshold."""
from __future__ import annotations

import json
import sys
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ML_DIR = ROOT / "ml"
if str(ML_DIR) not in sys.path:
    sys.path.insert(0, str(ML_DIR))

from consumption_category import compute_consumption_category

JKT = timezone(timedelta(hours=7))


def _make_hourly(values_by_hod: dict[int, float], base_date="2026-09-10") -> pd.DataFrame:
    """Build minimal hourly DataFrame for testing."""
    rows = []
    for hod, val in values_by_hod.items():
        ts = pd.Timestamp(f"{base_date} {hod:02d}:00", tz=JKT)
        rows.append({
            "hour": ts,
            "energy_kwh_hourly": val,
            "observed_hour": True,
            "coverage_flag": False,
        })
    return pd.DataFrame(rows)


def _target(hour: int, date="2026-09-11") -> pd.Timestamp:
    return pd.Timestamp(f"{date} {hour:02d}:00", tz=JKT)


class TestNormalBoros(unittest.TestCase):
    def test_below_threshold_normal(self):
        hourly = _make_hourly({i: 0.02 for i in range(24)})
        result = compute_consumption_category(0.01, _target(12), hourly)
        self.assertEqual(result["consumption_category"], "NORMAL")

    def test_above_threshold_boros(self):
        hourly = _make_hourly({i: 0.02 for i in range(24)})
        result = compute_consumption_category(0.10, _target(12), hourly)
        self.assertEqual(result["consumption_category"], "BOROS")

    def test_equal_threshold_normal(self):
        # Build 8 samples at 0.05 for hour 12
        rows = []
        for d in range(1, 9):
            rows.append({
                "hour": pd.Timestamp(f"2026-09-{d:02d} 12:00", tz=JKT),
                "energy_kwh_hourly": 0.05,
                "observed_hour": True,
                "coverage_flag": False,
            })
        hourly = pd.DataFrame(rows)
        # predicted == 0.05, threshold == 0.05 → NORMAL
        result = compute_consumption_category(0.05, _target(12), hourly)
        self.assertEqual(result["consumption_category"], "NORMAL")


class TestFallback(unittest.TestCase):
    def test_n7_fallback_global(self):
        # 7 samples for hour 12 (below min_bin=8)
        rows = []
        for d in range(1, 8):
            rows.append({
                "hour": pd.Timestamp(f"2026-09-{d:02d} 12:00", tz=JKT),
                "energy_kwh_hourly": 0.03,
                "observed_hour": True,
                "coverage_flag": False,
            })
        hourly = pd.DataFrame(rows)
        result = compute_consumption_category(0.04, _target(12), hourly)
        self.assertEqual(result["category_scope"], "global_p90_fallback")

    def test_n8_per_hour(self):
        rows = []
        for d in range(1, 9):
            rows.append({
                "hour": pd.Timestamp(f"2026-09-{d:02d} 12:00", tz=JKT),
                "energy_kwh_hourly": 0.03,
                "observed_hour": True,
                "coverage_flag": False,
            })
        hourly = pd.DataFrame(rows)
        result = compute_consumption_category(0.04, _target(12), hourly)
        self.assertEqual(result["category_scope"], "hour_of_day")


class TestMidnight(unittest.TestCase):
    def test_midnight_uses_target_hour_00(self):
        # Feature at 23:00, target at 00:00
        rows = []
        for d in range(1, 10):
            rows.append({
                "hour": pd.Timestamp(f"2026-09-{d:02d} 00:00", tz=JKT),
                "energy_kwh_hourly": 0.02,
                "observed_hour": True,
                "coverage_flag": False,
            })
        hourly = pd.DataFrame(rows)
        result = compute_consumption_category(0.03, _target(0), hourly)
        self.assertEqual(result["category_target_hour"], 0)


class TestEdgeCases(unittest.TestCase):
    def test_empty_history(self):
        empty = pd.DataFrame(columns=["hour", "energy_kwh_hourly", "observed_hour", "coverage_flag"])
        result = compute_consumption_category(0.03, _target(12), empty)
        self.assertEqual(result["consumption_category"], "TIDAK_TERSEDIA")

    def test_nan_prediction(self):
        hourly = _make_hourly({i: 0.02 for i in range(24)})
        result = compute_consumption_category(float("nan"), _target(12), hourly)
        self.assertEqual(result["consumption_category"], "TIDAK_TERSEDIA")

    def test_none_prediction(self):
        hourly = _make_hourly({i: 0.02 for i in range(24)})
        result = compute_consumption_category(None, _target(12), hourly)
        self.assertEqual(result["consumption_category"], "TIDAK_TERSEDIA")

    def test_all_zero_history(self):
        hourly = _make_hourly({i: 0.0 for i in range(24)})
        result = compute_consumption_category(0.0, _target(12), hourly)
        self.assertEqual(result["consumption_category"], "NORMAL")

    def test_all_zero_history_nonzero_pred(self):
        hourly = _make_hourly({i: 0.0 for i in range(24)})
        result = compute_consumption_category(0.01, _target(12), hourly)
        self.assertEqual(result["consumption_category"], "BOROS")

    def test_future_observations_excluded(self):
        """Data at or after target_ts must not affect threshold."""
        rows = []
        # Past: low consumption
        for d in range(1, 9):
            rows.append({
                "hour": pd.Timestamp(f"2026-09-{d:02d} 12:00", tz=JKT),
                "energy_kwh_hourly": 0.02,
                "observed_hour": True,
                "coverage_flag": False,
            })
        # Future: high consumption (should be excluded)
        rows.append({
            "hour": pd.Timestamp("2026-09-12 12:00", tz=JKT),
            "energy_kwh_hourly": 0.99,
            "observed_hour": True,
            "coverage_flag": False,
        })
        hourly = pd.DataFrame(rows)
        target = pd.Timestamp("2026-09-11 12:00", tz=JKT)
        result = compute_consumption_category(0.03, target, hourly)
        # If future 0.99 were included, P90 would be ~0.99 → NORMAL.
        # Since future is excluded, P90=0.02 and pred 0.03 > 0.02 → BOROS.
        # BOROS proves future observations were correctly excluded.
        self.assertEqual(result["consumption_category"], "BOROS")


class TestJSONSafe(unittest.TestCase):
    def test_json_serializable(self):
        hourly = _make_hourly({i: 0.03 for i in range(24)})
        result = compute_consumption_category(0.04, _target(12), hourly)
        dumped = json.dumps(result)
        self.assertIsInstance(dumped, str)

    def test_no_numpy_types(self):
        hourly = _make_hourly({i: 0.03 for i in range(24)})
        result = compute_consumption_category(0.04, _target(12), hourly)
        for k, v in result.items():
            self.assertNotIsInstance(v, (np.floating, np.integer),
                                     f"{k} has numpy type {type(v)}")


class TestStalePolicy(unittest.TestCase):
    def test_fresh_sets_valid_true(self):
        """valid_for_current_state defaults to True; caller overrides for stale."""
        hourly = _make_hourly({i: 0.02 for i in range(24)})
        result = compute_consumption_category(0.01, _target(12), hourly)
        self.assertTrue(result["category_valid_for_current_state"])

    def test_caller_can_set_false(self):
        hourly = _make_hourly({i: 0.02 for i in range(24)})
        result = compute_consumption_category(0.01, _target(12), hourly)
        result["category_valid_for_current_state"] = False
        self.assertFalse(result["category_valid_for_current_state"])


class TestReturnContract(unittest.TestCase):
    def test_all_expected_keys_present(self):
        hourly = _make_hourly({i: 0.02 for i in range(24)})
        result = compute_consumption_category(0.01, _target(12), hourly)
        expected_keys = {
            "consumption_category", "category_threshold_kwh", "category_baseline_kwh",
            "category_baseline_samples", "category_mad", "category_p90_global",
            "category_method", "category_scope", "category_note",
            "category_target_hour", "category_valid_for_current_state",
        }
        self.assertTrue(expected_keys.issubset(set(result.keys())),
                        f"Missing keys: {expected_keys - set(result.keys())}")

    def test_method_is_hybrid(self):
        hourly = _make_hourly({i: 0.02 for i in range(24)})
        result = compute_consumption_category(0.01, _target(12), hourly)
        self.assertEqual(result["category_method"], "hybrid_median_mad_p90")


if __name__ == "__main__":
    unittest.main()
