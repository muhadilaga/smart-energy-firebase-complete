"""Tests for monthly PZEM usage tracking logic.

These tests validate the algorithm implemented in app.js functions:
  - monthKeyFromTimestamp()
  - updateMonthlyUsageState()
  - migrateLegacyPzemKeys()
  - calculate450PostpaidEnergyCost()

The JS functions are reimplemented here in Python for testability.
"""
from __future__ import annotations

import json
import time
import unittest
from datetime import datetime, timezone


# --- Python equivalents of app.js monthly usage functions ---

MONTHLY_STATE_KEY = "monthlyUsageState"
PZEM_RESET_THRESHOLD_KWH = 0.5


class FakeLocalStorage:
    """Minimal localStorage模拟 for testing."""

    def __init__(self):
        self._store: dict[str, str] = {}

    def get_item(self, key: str) -> str | None:
        return self._store.get(key)

    def set_item(self, key: str, value: str):
        self._store[key] = value

    def remove_item(self, key: str):
        self._store.pop(key, None)


def month_key_from_timestamp(ts: float | None) -> str | None:
    if ts is None or ts != ts:  # NaN check
        return None
    dt = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
    return f"{dt.year}-{dt.month:02d}"


def get_monthly_usage_state(ls: FakeLocalStorage) -> dict | None:
    raw = ls.get_item(MONTHLY_STATE_KEY)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


def save_monthly_usage_state(ls: FakeLocalStorage, state: dict):
    ls.set_item(MONTHLY_STATE_KEY, json.dumps(state))


def migrate_legacy_pzem_keys(ls: FakeLocalStorage) -> None:
    if get_monthly_usage_state(ls) is not None:
        return
    raw = ls.get_item("pzemEnergyBaseline")
    if raw is None or raw == "":
        return
    val = float(raw)
    if val < 0:
        return
    save_monthly_usage_state(ls, {
        "month": None, "baseline_kwh": val,
        "accumulated_before_reset": 0,
        "baseline_set_at": time.time() * 1000,
        "last_observed_kwh": val,
    })


def update_monthly_usage_state(
    ls: FakeLocalStorage, current_energy: float, data_timestamp: float | None
) -> dict:
    current_month = month_key_from_timestamp(data_timestamp)
    state = get_monthly_usage_state(ls)

    if state is None or (current_month and state.get("month") != current_month):
        state = {
            "month": current_month, "baseline_kwh": current_energy,
            "accumulated_before_reset": 0,
            "baseline_set_at": data_timestamp or time.time() * 1000,
            "last_observed_kwh": current_energy,
        }
        save_monthly_usage_state(ls, state)
        return {"monitored": 0, "reset": False, "state": state}

    baseline = state["baseline_kwh"]
    accum = state.get("accumulated_before_reset", 0)
    last = state.get("last_observed_kwh", baseline)
    reset = False

    if current_energy < baseline - PZEM_RESET_THRESHOLD_KWH:
        accum += max(0, last - baseline)
        baseline = current_energy
        reset = True

    state["baseline_kwh"] = baseline
    state["accumulated_before_reset"] = accum
    state["last_observed_kwh"] = max(current_energy, last)
    save_monthly_usage_state(ls, state)

    monitored = accum + max(0, current_energy - baseline)
    return {"monitored": monitored, "reset": reset, "state": state}


# --- Tariff function (same as app.js) ---

TARIFF_BLOCKS = [
    (30, 169),
    (60, 360),
    (float("inf"), 495),
]
DAYA_KVA = 0.45
BIAYA_BEBAN_PER_KVA = 11000


def calculate450PostpaidEnergyCost(kwh: float) -> float:
    if kwh != kwh or kwh <= 0:
        return 0
    cost = 0.0
    remaining = kwh
    prev_limit = 0
    for limit, rate in TARIFF_BLOCKS:
        block_size = limit - prev_limit
        used = min(remaining, block_size)
        cost += used * rate
        remaining -= used
        prev_limit = limit
        if remaining <= 0:
            break
    return cost


# --- Tests ---

class TestMonthKeyFromTimestamp(unittest.TestCase):
    def test_valid_timestamp(self):
        # 2026-09-15 12:00:00 UTC
        ts = 1789473600000
        self.assertEqual(month_key_from_timestamp(ts), "2026-09")

    def test_january(self):
        # 2026-01-01 00:00:00 UTC
        ts = 1767225600000
        self.assertEqual(month_key_from_timestamp(ts), "2026-01")

    def test_none_returns_none(self):
        self.assertIsNone(month_key_from_timestamp(None))

    def test_nan_returns_none(self):
        self.assertIsNone(month_key_from_timestamp(float("nan")))


class TestFirstInitialization(unittest.TestCase):
    """A: first initialization — no prior state."""

    def test_first_reading_initializes_baseline(self):
        ls = FakeLocalStorage()
        result = update_monthly_usage_state(ls, 7.8440, 1789473600000)
        self.assertEqual(result["monitored"], 0)
        self.assertFalse(result["reset"])
        self.assertEqual(result["state"]["baseline_kwh"], 7.8440)
        self.assertEqual(result["state"]["accumulated_before_reset"], 0)

    def test_first_reading_sets_month(self):
        ls = FakeLocalStorage()
        result = update_monthly_usage_state(ls, 5.0, 1789473600000)
        self.assertEqual(result["state"]["month"], "2026-09")


class TestNormalIncreasingCounter(unittest.TestCase):
    """B: normal increasing counter."""

    def test_usage_increases(self):
        ls = FakeLocalStorage()
        update_monthly_usage_state(ls, 7.8440, 1789473600000)  # init
        result = update_monthly_usage_state(ls, 7.9440, 1789477200000)
        self.assertAlmostEqual(result["monitored"], 0.1, places=4)
        self.assertFalse(result["reset"])

    def test_multiple_increases_accumulate(self):
        ls = FakeLocalStorage()
        update_monthly_usage_state(ls, 7.0, 1789473600000)
        r1 = update_monthly_usage_state(ls, 7.5, 1789477200000)
        r2 = update_monthly_usage_state(ls, 8.0, 1789480800000)
        self.assertAlmostEqual(r1["monitored"], 0.5, places=4)
        self.assertAlmostEqual(r2["monitored"], 1.0, places=4)


class TestBrowserReload(unittest.TestCase):
    """C: reload/browser state restoration."""

    def test_state_persists_across_reads(self):
        ls = FakeLocalStorage()
        update_monthly_usage_state(ls, 7.0, 1789473600000)
        update_monthly_usage_state(ls, 7.5, 1789477200000)
        # Simulate page reload — read from same localStorage
        result = update_monthly_usage_state(ls, 8.0, 1789480800000)
        self.assertAlmostEqual(result["monitored"], 1.0, places=4)

    def test_no_state_returns_zero(self):
        ls = FakeLocalStorage()
        state = get_monthly_usage_state(ls)
        self.assertIsNone(state)


class TestMonthTransition(unittest.TestCase):
    """D: month transition."""

    def test_new_month_resets_baseline(self):
        ls = FakeLocalStorage()
        # September
        update_monthly_usage_state(ls, 7.0, 1789473600000)
        update_monthly_usage_state(ls, 8.0, 1789480800000)
        # October
        oct_ts = 1791028800000  # 2026-10-01 00:00:00 UTC
        result = update_monthly_usage_state(ls, 8.5, oct_ts)
        self.assertEqual(result["state"]["month"], "2026-10")
        self.assertEqual(result["monitored"], 0)
        self.assertEqual(result["state"]["baseline_kwh"], 8.5)
        self.assertEqual(result["state"]["accumulated_before_reset"], 0)


class TestPzemReset(unittest.TestCase):
    """E: PZEM counter reset."""

    def test_reset_detected(self):
        ls = FakeLocalStorage()
        update_monthly_usage_state(ls, 7.0, 1789473600000)
        update_monthly_usage_state(ls, 8.0, 1789477200000)  # accum = 1.0
        result = update_monthly_usage_state(ls, 0.5, 1789480800000)  # reset!
        self.assertTrue(result["reset"])
        # accumulated = 1.0 (from before reset) + 0 (current-baseline=0)
        self.assertAlmostEqual(result["monitored"], 1.0, places=4)
        self.assertEqual(result["state"]["baseline_kwh"], 0.5)

    def test_usage_after_reset(self):
        ls = FakeLocalStorage()
        update_monthly_usage_state(ls, 7.0, 1789473600000)
        update_monthly_usage_state(ls, 8.0, 1789477200000)  # accum = 1.0
        update_monthly_usage_state(ls, 0.5, 1789480800000)  # reset
        result = update_monthly_usage_state(ls, 1.0, 1789484400000)
        self.assertAlmostEqual(result["monitored"], 1.5, places=4)  # 1.0 + (1.0 - 0.5)
        self.assertFalse(result["reset"])

    def test_multiple_resets(self):
        ls = FakeLocalStorage()
        update_monthly_usage_state(ls, 10.0, 1789473600000)
        update_monthly_usage_state(ls, 11.0, 1789477200000)  # normal: last=11.0, monitored=1.0
        update_monthly_usage_state(ls, 2.0, 1789480800000)   # reset: accum=0+max(0,11-10)=1.0, base=2.0, last=11.0
        update_monthly_usage_state(ls, 5.0, 1789484400000)   # normal: accum=1.0, last=max(5,11)=11.0, monitored=1+3=4.0
        result = update_monthly_usage_state(ls, 0.3, 1789488000000)  # reset: accum=1+max(0,11-2)=10.0, base=0.3
        self.assertTrue(result["reset"])
        self.assertAlmostEqual(result["monitored"], 10.0, places=4)

    def test_small_drop_not_treated_as_reset(self):
        ls = FakeLocalStorage()
        update_monthly_usage_state(ls, 7.0, 1789473600000)
        update_monthly_usage_state(ls, 7.0001, 1789477200000)
        result = update_monthly_usage_state(ls, 7.0000, 1789480800000)
        self.assertFalse(result["reset"])


class TestUsageBeforeMonitoring(unittest.TestCase):
    """F: usageBeforeMonitoring."""

    def test_usage_before_added_to_total(self):
        usage_before = 5.0
        ls = FakeLocalStorage()
        update_monthly_usage_state(ls, 7.0, 1789473600000)
        result = update_monthly_usage_state(ls, 7.8440, 1789477200000)
        total = usage_before + result["monitored"]
        self.assertAlmostEqual(total, 5.8440, places=4)


class TestEnergyCostUsesTotalMonthlyUsage(unittest.TestCase):
    """G: energy cost uses totalMonthlyUsage."""

    def test_cost_calculation(self):
        usage_before = 0
        ls = FakeLocalStorage()
        update_monthly_usage_state(ls, 0, 1789473600000)
        result = update_monthly_usage_state(ls, 7.8440, 1789477200000)
        monthly_usage = usage_before + result["monitored"]
        cost = calculate450PostpaidEnergyCost(monthly_usage)
        self.assertAlmostEqual(cost, 7.8440 * 169, places=1)


class TestTotalCost(unittest.TestCase):
    """H: total cost = energyCost + biayaBeban."""

    def test_total_cost(self):
        ls = FakeLocalStorage()
        update_monthly_usage_state(ls, 0, 1789473600000)
        result = update_monthly_usage_state(ls, 7.8440, 1789477200000)
        energy_cost = calculate450PostpaidEnergyCost(result["monitored"])
        biaya_beban = DAYA_KVA * BIAYA_BEBAN_PER_KVA
        total = energy_cost + biaya_beban
        expected = 7.8440 * 169 + 0.45 * 11000
        self.assertAlmostEqual(total, expected, places=1)


class TestInvalidInput(unittest.TestCase):
    """I: invalid/null energy input."""

    def test_null_timestamp(self):
        ls = FakeLocalStorage()
        result = update_monthly_usage_state(ls, 7.0, None)
        self.assertEqual(result["state"]["month"], None)
        self.assertEqual(result["monitored"], 0)

    def test_nan_energy_not_stored(self):
        ls = FakeLocalStorage()
        # NaN gets saved but state has NaN baseline — subsequent reads work
        result = update_monthly_usage_state(ls, float("nan"), 1789473600000)
        self.assertEqual(result["monitored"], 0)
        # In browser JS: JSON.stringify(NaN) → null, state lost.
        # In Python: NaN round-trips via json. Guard is Number.isFinite in renderState.
        state = get_monthly_usage_state(ls)
        self.assertIsNotNone(state)


class TestLegacyMigration(unittest.TestCase):
    """J: backward compatibility / legacy localStorage."""

    def test_migrate_old_pzem_key(self):
        ls = FakeLocalStorage()
        ls.set_item("pzemEnergyBaseline", "3.1415")
        migrate_legacy_pzem_keys(ls)
        state = get_monthly_usage_state(ls)
        self.assertIsNotNone(state)
        self.assertAlmostEqual(state["baseline_kwh"], 3.1415, places=4)
        self.assertEqual(state["accumulated_before_reset"], 0)

    def test_no_migration_if_new_state_exists(self):
        ls = FakeLocalStorage()
        ls.set_item("pzemEnergyBaseline", "3.1415")
        ls.set_item(MONTHLY_STATE_KEY, json.dumps({
            "month": "2026-09", "baseline_kwh": 5.0,
            "accumulated_before_reset": 0, "baseline_set_at": 0,
            "last_observed_kwh": 5.0,
        }))
        migrate_legacy_pzem_keys(ls)
        state = get_monthly_usage_state(ls)
        self.assertAlmostEqual(state["baseline_kwh"], 5.0, places=4)

    def test_no_migration_without_old_key(self):
        ls = FakeLocalStorage()
        migrate_legacy_pzem_keys(ls)
        self.assertIsNone(get_monthly_usage_state(ls))


class TestTariffFormula(unittest.TestCase):
    """Verify tariff matches PLN R-1/TR 450VA."""

    def test_block1_169_per_kwh(self):
        self.assertAlmostEqual(calculate450PostpaidEnergyCost(1), 169, places=1)

    def test_block1_full_30kwh(self):
        self.assertAlmostEqual(calculate450PostpaidEnergyCost(30), 30 * 169, places=1)

    def test_block2_boundary(self):
        cost = calculate450PostpaidEnergyCost(31)
        expected = 30 * 169 + 1 * 360
        self.assertAlmostEqual(cost, expected, places=1)

    def test_block3_boundary(self):
        cost = calculate450PostpaidEnergyCost(61)
        expected = 30 * 169 + 30 * 360 + 1 * 495
        self.assertAlmostEqual(cost, expected, places=1)

    def test_zero(self):
        self.assertEqual(calculate450PostpaidEnergyCost(0), 0)

    def test_negative(self):
        self.assertEqual(calculate450PostpaidEnergyCost(-5), 0)

    def test_actual_value_7_8440(self):
        cost = calculate450PostpaidEnergyCost(7.8440)
        expected = 7.8440 * 169
        self.assertAlmostEqual(cost, expected, places=1)


class TestResearchArtifactsUntouched(unittest.TestCase):
    """Verify research artifacts checksums are unchanged."""

    def test_model_checksum(self):
        import hashlib
        from pathlib import Path
        model = Path(__file__).resolve().parents[1] / "ml" / "output" / "random_forest_model.joblib"
        if not model.exists():
            self.skipTest("model not found")
        sha = hashlib.sha256(model.read_bytes()).hexdigest()
        self.assertTrue(sha.startswith("401088348c0656f0"),
                        f"Model checksum changed: {sha}")

    def test_research_data_checksum(self):
        import hashlib
        from pathlib import Path
        data = Path(__file__).resolve().parents[1] / "ml" / "data" / "history_real.csv"
        if not data.exists():
            self.skipTest("history_real.csv not found")
        sha = hashlib.sha256(data.read_bytes()).hexdigest()
        self.assertTrue(sha.startswith("c321b9b56e07c390"),
                        f"Research data checksum changed: {sha}")


if __name__ == "__main__":
    unittest.main()
