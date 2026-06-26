import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List


@dataclass
class TraceEvent:
    step: int
    tool_name: str
    input_summary: str
    success: bool
    latency_ms: float
    detail: str = ""


class AgentTracer:
    def __init__(self) -> None:
        self._events: List[TraceEvent] = []
        self._step = 0

    def log_tool_call(self, tool_name: str, tool_input: Dict[str, Any], result: Dict[str, Any], latency_ms: float) -> TraceEvent:
        self._step += 1
        success = bool(result.get("success", True))
        detail = result.get("error", "") if not success else ""
        event = TraceEvent(
            step=self._step,
            tool_name=tool_name,
            input_summary=_summarize(tool_input),
            success=success,
            latency_ms=round(latency_ms, 1),
            detail=detail,
        )
        self._events.append(event)
        return event

    def events_for_turn(self) -> List[Dict[str, Any]]:
        return [asdict(e) for e in self._events]

    def reset(self) -> None:
        self._events = []
        self._step = 0


def _summarize(tool_input: Dict[str, Any], max_len: int = 80) -> str:
    text = ", ".join(f"{k}={v!r}" for k, v in tool_input.items())
    return text if len(text) <= max_len else text[: max_len - 3] + "..."


class timed:

    def __enter__(self):
        self._start = time.perf_counter()
        self.ms = 0.0
        return self

    def __exit__(self, *exc):
        self.ms = (time.perf_counter() - self._start) * 1000
        return False
