"""Tests for flowchart_tool.py"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.flowchart_tool import generate_flowchart

SAMPLE_SCHEMA = {
    "tables": {
        "customers": {
            "columns": [
                {"name": "customer_id", "type": "INTEGER", "primary_key": True},
                {"name": "name", "type": "TEXT", "primary_key": False},
            ],
            "foreign_keys": [],
        },
        "orders": {
            "columns": [
                {"name": "order_id", "type": "INTEGER", "primary_key": True},
                {"name": "customer_id", "type": "INTEGER", "primary_key": False},
            ],
            "foreign_keys": [{"column": "customer_id", "references_table": "customers", "references_column": "customer_id"}],
        },
    },
    "relationships": [{"from_table": "orders", "to_table": "customers", "via": "customer_id"}],
}


class TestGenerateFlowchart(unittest.TestCase):
    def test_er_diagram_with_schema(self):
        r = generate_flowchart("er_diagram", schema=SAMPLE_SCHEMA)
        self.assertTrue(r["success"])
        self.assertIn("mermaid_code", r)
        self.assertIn("erDiagram", r["mermaid_code"])

    def test_er_diagram_includes_tables(self):
        r = generate_flowchart("er_diagram", schema=SAMPLE_SCHEMA)
        code = r["mermaid_code"]
        self.assertIn("customers", code)
        self.assertIn("orders", code)

    def test_er_diagram_includes_relationships(self):
        r = generate_flowchart("er_diagram", schema=SAMPLE_SCHEMA)
        code = r["mermaid_code"]
        self.assertIn("customers ||--o{ orders", code)

    def test_er_diagram_includes_primary_key_marker(self):
        r = generate_flowchart("er_diagram", schema=SAMPLE_SCHEMA)
        code = r["mermaid_code"]
        self.assertIn("PK", code)

    def test_process_flow_default(self):
        r = generate_flowchart(
            "process_flow",
            steps=["Order Placed", "Confirmed", "Shipped", "Delivered"],
        )
        self.assertTrue(r["success"])
        code = r["mermaid_code"]
        self.assertIn("flowchart TD", code)
        self.assertIn("Order Placed", code)
        self.assertIn("Delivered", code)

    def test_process_flow_with_decision_points(self):
        r = generate_flowchart(
            "process_flow",
            steps=["Placed", "Confirmed", "Shipped"],
            decision_points={"Confirmed": ["Cancelled"]},
        )
        self.assertTrue(r["success"])
        code = r["mermaid_code"]
        self.assertIn("Cancelled", code)
        self.assertIn("branch", code)

    def test_er_diagram_no_schema(self):
        r = generate_flowchart("er_diagram")
        self.assertFalse(r["success"])

    def test_process_flow_no_steps(self):
        r = generate_flowchart("process_flow")
        self.assertFalse(r["success"])

    def test_invalid_diagram_type(self):
        r = generate_flowchart("invalid_type")
        self.assertFalse(r["success"])

    def test_json_string_schema(self):
        r = generate_flowchart("er_diagram", schema=json.dumps(SAMPLE_SCHEMA))
        self.assertTrue(r["success"])

    def test_schema_with_success_wrapper(self):
        r = generate_flowchart("er_diagram", schema={"success": True, "schema": SAMPLE_SCHEMA})
        self.assertTrue(r["success"])

    def test_process_flow_sequential_arrows(self):
        r = generate_flowchart("process_flow", steps=["A", "B", "C"])
        code = r["mermaid_code"]
        self.assertIn("S0 --> S1", code)
        self.assertIn("S1 --> S2", code)

    def test_empty_steps_list(self):
        r = generate_flowchart("process_flow", steps=[])
        self.assertFalse(r["success"])


if __name__ == "__main__":
    unittest.main()
