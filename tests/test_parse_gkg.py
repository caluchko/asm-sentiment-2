"""Unit tests for GKG field parsing. Run: .venv/bin/python -m unittest discover tests"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from extract import parse_gkg as p  # noqa: E402


class TestParseV2Tone(unittest.TestCase):
    def test_full(self):
        out = p.parse_v2tone("5.24,6.29,1.04,7.34,24.1,0,513")
        self.assertAlmostEqual(out["tone"], 5.24)
        self.assertAlmostEqual(out["neg_score"], 1.04)
        self.assertEqual(out["word_count"], 513)

    def test_empty(self):
        self.assertIsNone(p.parse_v2tone("")["tone"])
        self.assertIsNone(p.parse_v2tone(None)["tone"])


class TestSubjectCountries(unittest.TestCase):
    def test_extract(self):
        loc = ("4#Araxa, Minas Gerais, Brazil#BR#BR15#40197#-19.5#-46.9#-625944#1727;"
               "1#Italian#IT#IT##42.8#12.8#IT#2194")
        self.assertEqual(p.extract_subject_countries(loc), ["BR", "IT"])

    def test_empty(self):
        self.assertEqual(p.extract_subject_countries(""), [])
        self.assertEqual(p.extract_subject_countries(None), [])


class TestLanguage(unittest.TestCase):
    def test_por(self):
        self.assertEqual(p.extract_language("srclc:por;eng:GT-POR 1.0"), "por")

    def test_default_english(self):
        self.assertEqual(p.extract_language(""), "eng")
        self.assertEqual(p.extract_language(None), "eng")


class TestMinerals(unittest.TestCase):
    def test_gold(self):
        self.assertIn("gold", p.identify_minerals("WB_2936_GOLD,1991;TAX_FNCACT_MINERS,36"))

    def test_unspecified(self):
        self.assertEqual(p.identify_minerals("TAX_FNCACT_MANAGER,3167"), ["unspecified"])
        self.assertEqual(p.identify_minerals(None), ["unspecified"])


class TestDate(unittest.TestCase):
    def test_parse(self):
        ts = p.parse_date("20250702231500")
        self.assertEqual((ts.year, ts.month, ts.day, ts.hour), (2025, 7, 2, 23))


if __name__ == "__main__":
    unittest.main()
