"""Tests for trace/tracer.py"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from trace.tracer import AgentTracer, timed


class TestAgentTracer(unittest.TestCase):
    def setUp(self):
        self.tracer = AgentTracer()

    def test_log_tool_call_returns_event(self):
        ev = self.tracer.log_tool_call("get_schema", {}, {"success": True}, 12.3)
        self.assertEqual(ev.tool_name, "get_schema")
        self.assertTrue(ev.success)
        self.assertEqual(ev.latency_ms, 12.3)
        self.assertEqual(ev.step, 1)

    def test_step_increments(self):
        self.tracer.log_tool_call("tool_a", {}, {"success": True}, 1)
        ev2 = self.tracer.log_tool_call("tool_b", {}, {"success": True}, 2)
        self.assertEqual(ev2.step, 2)

    def test_logs_error_detail(self):
        ev = self.tracer.log_tool_call("execute_query", {"sql": "SELECT bad"}, {"success": False, "error": "syntax error"}, 5.0)
        self.assertFalse(ev.success)
        self.assertIn("syntax", ev.detail)

    def test_events_for_turn(self):
        self.tracer.log_tool_call("t1", {}, {"success": True}, 1.0)
        self.tracer.log_tool_call("t2", {}, {"success": False, "error": "e"}, 2.0)
        events = self.tracer.events_for_turn()
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["tool_name"], "t1")
        self.assertEqual(events[1]["tool_name"], "t2")

    def test_reset(self):
        self.tracer.log_tool_call("t1", {}, {"success": True}, 1.0)
        self.tracer.reset()
        self.assertEqual(len(self.tracer.events_for_turn()), 0)
        self.assertEqual(self.tracer._step, 0)


class TestTimed(unittest.TestCase):
    def test_measures_time(self):
        with timed() as t:
            x = 0
            for i in range(100_000):
                x += i
        self.assertGreater(t.ms, 0)

    def test_returns_context(self):
        with timed() as t:
            pass
        self.assertIsInstance(t.ms, float)


if __name__ == "__main__":
    unittest.main()
