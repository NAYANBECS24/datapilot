"""Tests for chart_tool.py"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.chart_tool import generate_chart

SAMPLE_DATA = [
    {"product": "Widget A", "revenue": 12000},
    {"product": "Widget B", "revenue": 8500},
    {"product": "Widget C", "revenue": 6200},
    {"product": "Widget D", "revenue": 4100},
]

SAMPLE_TIME_DATA = [
    {"month": "2026-01", "sales": 10000},
    {"month": "2026-02", "sales": 12500},
    {"month": "2026-03", "sales": 11800},
]


class TestGenerateChart(unittest.TestCase):
    def test_bar_chart_success(self):
        r = generate_chart(SAMPLE_DATA, "bar", x="product", y="revenue", title="Test Bar")
        self.assertTrue(r["success"])
        self.assertEqual(r["chart_type"], "bar")

    def test_bar_returns_figure_dict(self):
        r = generate_chart(SAMPLE_DATA, "bar", x="product", y="revenue")
        self.assertIn("figure", r)
        self.assertIsInstance(r["figure"], dict)

    def test_line_chart(self):
        r = generate_chart(SAMPLE_TIME_DATA, "line", x="month", y="sales")
        self.assertTrue(r["success"])
        self.assertEqual(r["chart_type"], "line")

    def test_pie_chart(self):
        r = generate_chart(SAMPLE_DATA, "pie", x="product", y="revenue")
        self.assertTrue(r["success"])
        self.assertEqual(r["chart_type"], "pie")

    def test_scatter_chart(self):
        r = generate_chart(SAMPLE_DATA, "scatter", x="revenue", y="product")
        self.assertTrue(r["success"])
        self.assertEqual(r["chart_type"], "scatter")

    def test_auto_detects_time_series_as_line(self):
        r = generate_chart(SAMPLE_TIME_DATA, "auto", x="month", y="sales")
        self.assertTrue(r["success"])
        self.assertEqual(r["chart_type"], "line")

    def test_auto_detects_pie_for_small_categories(self):
        r = generate_chart(SAMPLE_DATA, "auto", x="product", y="revenue")
        self.assertEqual(r["chart_type"], "pie")

    def test_invalid_chart_type(self):
        r = generate_chart(SAMPLE_DATA, "invalid_type", x="product", y="revenue")
        self.assertFalse(r["success"])

    def test_empty_data(self):
        r = generate_chart([], "bar", x="product", y="revenue")
        self.assertFalse(r["success"])

    def test_json_string_data(self):
        r = generate_chart(json.dumps(SAMPLE_DATA), "bar", x="product", y="revenue")
        self.assertTrue(r["success"])

    def test_figure_has_data(self):
        r = generate_chart(SAMPLE_DATA, "bar", x="product", y="revenue")
        self.assertIn("data", r["figure"])
        self.assertGreater(len(r["figure"]["data"]), 0)

    def test_recommendation_note_on_auto(self):
        r = generate_chart(SAMPLE_TIME_DATA, "auto", x="month", y="sales")
        self.assertIn("recommendation_note", r)
        self.assertIn("Auto-selected", r["recommendation_note"])

    def test_no_recommendation_note_on_explicit(self):
        r = generate_chart(SAMPLE_DATA, "bar", x="product", y="revenue")
        self.assertEqual(r["recommendation_note"], "")


if __name__ == "__main__":
    unittest.main()
