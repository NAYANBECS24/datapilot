"""Tests for query_tool.py"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.query_tool import execute_query, validate_query, clear_uploads, csv_to_table

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "db", "sample_ecommerce.db")


class TestValidateQuery(unittest.TestCase):
    def test_valid_select(self):
        r = validate_query("SELECT * FROM products")
        self.assertTrue(r["valid"])

    def test_valid_with_cte(self):
        r = validate_query("WITH cte AS (SELECT 1) SELECT * FROM cte")
        self.assertTrue(r["valid"])

    def test_blocks_delete(self):
        r = validate_query("DELETE FROM orders")
        self.assertFalse(r["valid"])
        self.assertIn("only read-only", r["reason"].lower())

    def test_blocks_insert(self):
        r = validate_query("INSERT INTO customers VALUES (1, 'a', 'a@a.com', 'city', '2024-01-01')")
        self.assertFalse(r["valid"])

    def test_blocks_drop(self):
        r = validate_query("DROP TABLE products")
        self.assertFalse(r["valid"])
        self.assertIn("only read-only", r["reason"].lower())

    def test_blocks_update(self):
        r = validate_query("UPDATE products SET price = 0")
        self.assertFalse(r["valid"])

    def test_blocks_alter(self):
        r = validate_query("ALTER TABLE products ADD COLUMN test TEXT")
        self.assertFalse(r["valid"])

    def test_auto_adds_limit(self):
        r = validate_query("SELECT * FROM products")
        self.assertIn("LIMIT", r["sql"].upper())

    def test_preserves_existing_limit(self):
        r = validate_query("SELECT * FROM products LIMIT 5")
        self.assertIn("LIMIT 5", r["sql"])


class TestExecuteQuery(unittest.TestCase):
    def setUp(self):
        self.assertTrue(os.path.exists(DB_PATH))

    def test_valid_query_returns_success(self):
        r = execute_query(DB_PATH, "SELECT COUNT(*) AS cnt FROM products")
        self.assertTrue(r["success"])
        self.assertEqual(r["rows"][0]["cnt"], 53)

    def test_returns_columns(self):
        r = execute_query(DB_PATH, "SELECT name, price FROM products LIMIT 1")
        self.assertIn("columns", r)
        self.assertIn("name", r["columns"])
        self.assertIn("price", r["columns"])

    def test_blocks_write_query(self):
        r = execute_query(DB_PATH, "DELETE FROM orders")
        self.assertFalse(r["success"])
        self.assertIn("only read-only", r["error"].lower())

    def test_returns_latency(self):
        r = execute_query(DB_PATH, "SELECT 1")
        self.assertIn("latency_ms", r)
        self.assertGreater(r["latency_ms"], 0)

    def test_broken_sql_returns_error(self):
        r = execute_query(DB_PATH, "SELECT nonexistent_column FROM products")
        self.assertFalse(r["success"])

    def test_row_count_matches(self):
        r = execute_query(DB_PATH, "SELECT * FROM customers")
        self.assertEqual(r["row_count"], len(r["rows"]))

    def test_json_serializable(self):
        r = execute_query(DB_PATH, "SELECT * FROM products LIMIT 3")
        dumped = json.dumps(r, default=str)
        self.assertIsInstance(dumped, str)

    def test_can_query_personal_uploaded_table_alias(self):
        username = "__test_query_upload__"
        clear_uploads(username=username)
        csv_path = os.path.join(os.path.dirname(__file__), "_tmp_upload.csv")
        try:
            with open(csv_path, "w", encoding="utf-8") as f:
                f.write("name,amount\nA,10\nB,20\n")
            imported = csv_to_table(csv_path, "sales_upload", username=username)
            self.assertTrue(imported["success"])

            r = execute_query(
                DB_PATH,
                "SELECT SUM(amount) AS total FROM my.sales_upload",
                username=username,
            )
            self.assertTrue(r["success"])
            self.assertEqual(r["rows"][0]["total"], 30)
        finally:
            if os.path.exists(csv_path):
                os.remove(csv_path)
            clear_uploads(username=username)


class TestExecuteQueryJoin(unittest.TestCase):
    def test_join_works(self):
        r = execute_query(
            DB_PATH,
            "SELECT c.name, o.order_id FROM customers c JOIN orders o ON c.customer_id = o.customer_id LIMIT 5",
        )
        self.assertTrue(r["success"])
        self.assertGreater(r["row_count"], 0)
        self.assertIn("name", r["columns"])
        self.assertIn("order_id", r["columns"])

    def test_aggregation_works(self):
        r = execute_query(
            DB_PATH,
            "SELECT p.category, COUNT(*) AS cnt FROM products p GROUP BY p.category",
        )
        self.assertTrue(r["success"])
        self.assertGreater(r["row_count"], 0)

    def test_subquery_works(self):
        r = execute_query(
            DB_PATH,
            "SELECT name FROM products WHERE product_id IN (SELECT product_id FROM order_items LIMIT 3)",
        )
        self.assertTrue(r["success"])


class TestEdgeCases(unittest.TestCase):
    def test_empty_query(self):
        r = execute_query(DB_PATH, "")
        self.assertFalse(r["success"])

    def test_nonexistent_db(self):
        r = execute_query("/nonexistent/db.db", "SELECT 1")
        self.assertFalse(r["success"])

    def test_clear_uploads_no_error(self):
        try:
            clear_uploads()
        except PermissionError:
            pass


if __name__ == "__main__":
    unittest.main()
