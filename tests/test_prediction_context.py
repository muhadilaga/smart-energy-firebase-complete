"""Tests for prediction context resolution (Phase 5C)."""
import sys
import os
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from main import resolve_prediction_context, LOCATION_ALLOWLIST

FT_ISO = "2026-09-30T01:00:00+00:00"
_ft = datetime.fromisoformat(FT_ISO)
FT_MS = int(_ft.timestamp() * 1000)


def _reading(loc="", sess="", ts=None):
    if ts is None:
        ts = FT_MS
    r = {"timestamp": ts, "voltage": 220.0, "current": 0.5, "power": 100.0, "energy_kwh": 1.0, "frequency": 50.0, "power_factor": 0.8}
    if loc:
        r["location_code"] = loc
    if sess:
        r["session_id"] = sess
    return r


class TestContextResolution(unittest.TestCase):
    def test_single_purity(self):
        records = {
            "1": _reading(loc="ruang_kerja", sess="esp32-01_ruang_kerja_A", ts=FT_MS),
            "2": _reading(loc="ruang_kerja", sess="esp32-01_ruang_kerja_A", ts=FT_MS + 30000),
        }
        ctx = resolve_prediction_context(records, FT_ISO)
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx["purity"], "SINGLE")
        self.assertEqual(ctx["location_code"], "ruang_kerja")
        self.assertEqual(ctx["location_label"], "Ruang Kerja")
        self.assertEqual(ctx["session_id"], "esp32-01_ruang_kerja_A")

    def test_mixed_purity(self):
        records = {
            "1": _reading(loc="ruang_kerja", sess="esp32-01_ruang_kerja_A", ts=FT_MS),
            "2": _reading(loc="kamar_tidur", sess="esp32-01_kamar_tidur_B", ts=FT_MS + 30000),
        }
        ctx = resolve_prediction_context(records, FT_ISO)
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx["purity"], "MIXED")
        self.assertIsNone(ctx["location_code"])
        self.assertIsNone(ctx["location_label"])
        self.assertIsNone(ctx["session_id"])
        self.assertEqual(set(ctx["location_codes"]), {"kamar_tidur", "ruang_kerja"})

    def test_partial_purity(self):
        records = {
            "1": _reading(loc="ruang_kerja", sess="esp32-01_ruang_kerja_A", ts=FT_MS),
            "2": _reading(loc="", sess="", ts=FT_MS + 30000),
        }
        ctx = resolve_prediction_context(records, FT_ISO)
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx["purity"], "PARTIAL")
        self.assertEqual(ctx["location_code"], "ruang_kerja")
        self.assertEqual(ctx["location_label"], "Ruang Kerja")
        self.assertEqual(ctx["session_id"], "esp32-01_ruang_kerja_A")

    def test_unknown_purity(self):
        records = {
            "1": _reading(loc="", sess="", ts=FT_MS),
            "2": _reading(loc="", sess="", ts=FT_MS + 30000),
        }
        ctx = resolve_prediction_context(records, FT_ISO)
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx["purity"], "UNKNOWN")
        self.assertIsNone(ctx["location_code"])
        self.assertIsNone(ctx["location_label"])

    def test_no_readings_returns_none(self):
        records = {"1": _reading(loc="ruang_kerja", sess="A", ts=FT_MS + 4_000_000)}
        ctx = resolve_prediction_context(records, FT_ISO)
        self.assertIsNone(ctx)

    def test_empty_records_returns_none(self):
        ctx = resolve_prediction_context({}, FT_ISO)
        self.assertIsNone(ctx)

    def test_none_records_returns_none(self):
        ctx = resolve_prediction_context(None, FT_ISO)
        self.assertIsNone(ctx)


class TestBoundaryBehavior(unittest.TestCase):
    def test_lower_boundary_included(self):
        records = {"1": _reading(loc="ruang_kerja", sess="A", ts=FT_MS)}
        ctx = resolve_prediction_context(records, FT_ISO)
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx["purity"], "SINGLE")

    def test_upper_boundary_excluded(self):
        records = {"1": _reading(loc="ruang_kerja", sess="A", ts=FT_MS + 3_600_000)}
        ctx = resolve_prediction_context(records, FT_ISO)
        self.assertIsNone(ctx)

    def test_reading_just_before_upper(self):
        records = {"1": _reading(loc="ruang_kerja", sess="A", ts=FT_MS + 3_599_000)}
        ctx = resolve_prediction_context(records, FT_ISO)
        self.assertIsNotNone(ctx)


class TestInvalidLocation(unittest.TestCase):
    def test_invalid_code_in_single(self):
        records = {"1": _reading(loc="unknown_room", sess="esp32-01_unknown_room_A", ts=FT_MS)}
        ctx = resolve_prediction_context(records, FT_ISO)
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx["purity"], "SINGLE")
        self.assertEqual(ctx["location_code"], "unknown_room")
        self.assertEqual(ctx["location_label"], "Lokasi tidak diketahui")


class TestMixedWithIncomplete(unittest.TestCase):
    def test_mixed_takes_precedence(self):
        records = {
            "1": _reading(loc="ruang_kerja", sess="A", ts=FT_MS),
            "2": _reading(loc="kamar_tidur", sess="B", ts=FT_MS + 10000),
            "3": _reading(loc="", sess="", ts=FT_MS + 20000),
        }
        ctx = resolve_prediction_context(records, FT_ISO)
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx["purity"], "MIXED")


class TestAllowlistIntegrity(unittest.TestCase):
    def test_allowlist_codes(self):
        expected = {"ruang_kerja", "kamar_tidur", "ruang_tamu", "dapur"}
        self.assertEqual(set(LOCATION_ALLOWLIST.keys()), expected)

    def test_all_labels_are_strings(self):
        for code, label in LOCATION_ALLOWLIST.items():
            self.assertIsInstance(label, str)
            self.assertGreater(len(label), 0)


if __name__ == "__main__":
    unittest.main()
