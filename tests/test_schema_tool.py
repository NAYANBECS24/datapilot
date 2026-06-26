"""Tests for schema_tool.py"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.schema_tool import get_schema

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "sample_ecommerce.db")


class TestGetSchema(unittest.TestCase):
    def setUp(self):
        self.assertTrue(os.path.exists(DB_PATH), "Sample DB must exist. Run db/seed_db.py first.")

    def test_returns_success(self):
        result = get_schema(DB_PATH)
        self.assertTrue(result["success"])

    def test_has_tables(self):
        result = get_schema(DB_PATH)
        schema = result["schema"]
        self.assertIn("tables", schema)
        self.assertGreater(len(schema["tables"]), 0)

    def test_required_tables_present(self):
        result = get_schema(DB_PATH)
        tables = result["schema"]["tables"]
        for table in ("customers", "products", "orders", "order_items", "inventory"):
            self.assertIn(table, tables)

    def test_columns_have_required_keys(self):
        result = get_schema(DB_PATH)
        for table, meta in result["schema"]["tables"].items():
            for col in meta["columns"]:
                self.assertIn("name", col)
                self.assertIn("type", col)
                self.assertIn("primary_key", col)

    def test_relationships(self):
        result = get_schema(DB_PATH)
        rels = result["schema"].get("relationships", [])
        self.assertGreater(len(rels), 0, "Expected at least some foreign-key relationships")
        valid = {"from_table", "to_table", "via"}
        for r in rels:
            self.assertTrue(valid.issubset(r.keys()))

    def test_primary_keys_detected(self):
        result = get_schema(DB_PATH)
        customers = result["schema"]["tables"]["customers"]
        pk_cols = [c["name"] for c in customers["columns"] if c["primary_key"]]
        self.assertIn("customer_id", pk_cols)

    def test_products_has_name_and_price(self):
        result = get_schema(DB_PATH)
        products = result["schema"]["tables"]["products"]
        col_names = [c["name"] for c in products["columns"]]
        self.assertIn("name", col_names)
        self.assertIn("price", col_names)

    def test_error_for_nonexistent_db(self):
        result = get_schema("/nonexistent/path.db")
        self.assertFalse(result["success"])

    def test_json_serializable(self):
        result = get_schema(DB_PATH)
        dumped = json.dumps(result, indent=2)
        self.assertIsInstance(dumped, str)

    def test_orders_has_foreign_keys(self):
        result = get_schema(DB_PATH)
        orders = result["schema"]["tables"]["orders"]
        fk_cols = [fk["column"] for fk in orders["foreign_keys"]]
        self.assertIn("customer_id", fk_cols)

    def test_inventory_references_products(self):
        result = get_schema(DB_PATH)
        rels = result["schema"].get("relationships", [])
        inventory_fks = [r for r in rels if r["from_table"] == "inventory"]
        self.assertTrue(
            any(r["to_table"] == "products" for r in inventory_fks),
            "inventory should reference products",
        )


if __name__ == "__main__":
    unittest.main()
