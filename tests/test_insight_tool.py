"""Tests for insight_tool.py"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.insight_tool import detect_anomalies, prepare_explanation_context, generate_auto_insights

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "sample_ecommerce.db")

SAMPLE_SERIES = [
    {"day": "Mon", "revenue": 10000},
    {"day": "Tue", "revenue": 10500},
    {"day": "Wed", "revenue": 9800},
    {"day": "Thu", "revenue": 41000},
    {"day": "Fri", "revenue": 10200},
]


class TestDetectAnomalies(unittest.TestCase):
    def test_detects_spike(self):
        r = detect_anomalies(SAMPLE_SERIES, value_key="revenue", label_key="day")
        self.assertIn("anomalies", r)
        self.assertGreater(len(r["anomalies"]), 0)
        anomaly_labels = [a["label"] for a in r["anomalies"]]
        self.assertIn("Thu", anomaly_labels)

    def test_returns_mean_and_stdev(self):
        r = detect_anomalies(SAMPLE_SERIES, value_key="revenue", label_key="day")
        self.assertIn("mean", r)
        self.assertIn("stdev", r)
        self.assertGreater(r["mean"], 0)

    def test_no_anomalies_in_uniform_data(self):
        uniform = [{"v": 100} for _ in range(5)]
        r = detect_anomalies(uniform, value_key="v", label_key="v")
        self.assertEqual(len(r["anomalies"]), 0)

    def test_too_few_points(self):
        r = detect_anomalies([{"v": 1}, {"v": 2}], value_key="v", label_key="v")
        self.assertEqual(len(r["anomalies"]), 0)
        self.assertTrue(r["success"])

    def test_direction_field(self):
        r = detect_anomalies(SAMPLE_SERIES, value_key="revenue", label_key="day")
        for a in r["anomalies"]:
            self.assertIn(a["direction"], ("spike", "drop"))

    def test_z_score_is_float(self):
        r = detect_anomalies(SAMPLE_SERIES, value_key="revenue", label_key="day")
        for a in r["anomalies"]:
            self.assertIsInstance(a["z_score"], float)


class TestPrepareExplanationContext(unittest.TestCase):
    def test_returns_success(self):
        r = prepare_explanation_context(SAMPLE_SERIES, "How did we do this week?")
        self.assertTrue(r["success"])

    def test_returns_row_count(self):
        r = prepare_explanation_context(SAMPLE_SERIES, "Q")
        self.assertEqual(r["row_count"], 5)

    def test_computes_numeric_summary(self):
        r = prepare_explanation_context(SAMPLE_SERIES, "Q")
        self.assertIn("revenue", r["numeric_summary"])
        self.assertIn("total", r["numeric_summary"]["revenue"])
        self.assertIn("mean", r["numeric_summary"]["revenue"])
        self.assertIn("min", r["numeric_summary"]["revenue"])
        self.assertIn("max", r["numeric_summary"]["revenue"])

    def test_empty_data(self):
        r = prepare_explanation_context([], "Q")
        self.assertFalse(r["success"])

    def test_executive_persona(self):
        r = prepare_explanation_context(SAMPLE_SERIES, "Q", persona="executive")
        self.assertEqual(r["persona"], "executive")

    def test_analyst_persona(self):
        r = prepare_explanation_context(SAMPLE_SERIES, "Q", persona="analyst")
        self.assertEqual(r["persona"], "analyst")

    def test_returns_instruction(self):
        r = prepare_explanation_context(SAMPLE_SERIES, "Q")
        self.assertIn("instruction", r)


class TestGenerateAutoInsights(unittest.TestCase):
    def setUp(self):
        self.assertTrue(os.path.exists(DB_PATH))

    def test_returns_metrics(self):
        r = generate_auto_insights(DB_PATH)
        self.assertIn("metrics", r)
        self.assertGreater(r["metrics"]["total_revenue"], 0)
        self.assertGreater(r["metrics"]["total_orders"], 0)

    def test_returns_trends(self):
        r = generate_auto_insights(DB_PATH)
        self.assertIn("trends", r)
        self.assertIn("monthly_revenue", r["trends"])
        self.assertIn("category_revenue", r["trends"])
        self.assertIn("order_status", r["trends"])
        self.assertIn("top_products", r["trends"])

    def test_returns_summary(self):
        r = generate_auto_insights(DB_PATH)
        self.assertIn("summary", r)
        self.assertGreater(len(r["summary"]), 10)

    def test_returns_recommendations(self):
        r = generate_auto_insights(DB_PATH)
        self.assertIn("recommendations", r)
        self.assertGreater(len(r["recommendations"]), 0)

    def test_json_serializable(self):
        r = generate_auto_insights(DB_PATH)
        dumped = json.dumps(r, indent=2, default=str)
        self.assertIsInstance(dumped, str)

    def test_error_on_bad_path(self):
        r = generate_auto_insights("/nonexistent/db.db")
        self.assertIn("error", r)


if __name__ == "__main__":
    unittest.main()
