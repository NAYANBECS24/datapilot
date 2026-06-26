import json
from typing import Any, Dict, List, Optional, Union

import plotly.express as px

SUPPORTED_TYPES = {"bar", "line", "pie", "scatter", "auto"}


def _normalize_data(data: Union[str, List[Dict[str, Any]]]) -> Optional[List[Dict[str, Any]]]:
    if isinstance(data, str):
        try:
            parsed = json.loads(data)
            if isinstance(parsed, list):
                return parsed
            if isinstance(parsed, dict) and "rows" in parsed:
                return parsed["rows"]
        except (json.JSONDecodeError, TypeError):
            return None
    if isinstance(data, list):
        return data
    return None


def _recommend_chart_type(data: List[Dict[str, Any]], x: Optional[str], y: Optional[str]) -> str:
    if not data or not x or not y:
        return "bar"

    x_values = [row.get(x) for row in data if row.get(x) is not None]
    y_values = [row.get(y) for row in data if row.get(y) is not None]

    if not x_values or not y_values:
        return "bar"

    unique_x = len(set(x_values))

    import re
    date_patterns = [r"\d{4}-\d{2}-\d{2}", r"\d{2}/\d{2}/\d{4}", r"\d{4}-\d{2}"]
    looks_like_time_series = (
        unique_x > 1
        and x_values
        and any(re.match(p, str(x_values[0])) for p in date_patterns)
    )
    if looks_like_time_series:
        return "line"

    if unique_x <= 8 and unique_x >= 2:
        numeric_y = [v for v in y_values if isinstance(v, (int, float)) and v >= 0]
        if numeric_y and max(numeric_y) > 0:
            return "pie"

    if all(isinstance(v, (int, float)) for v in x_values) and unique_x >= 5:
        return "scatter"

    return "bar"


def generate_chart(
    data: Union[str, List[Dict[str, Any]]],
    chart_type: str,
    x: Optional[str] = None,
    y: Optional[str] = None,
    title: str = "",
) -> Dict[str, Any]:
    chart_type = (chart_type or "auto").lower()
    if chart_type not in SUPPORTED_TYPES:
        return {"success": False, "error": f"Unsupported chart_type '{chart_type}'. Use one of {sorted(SUPPORTED_TYPES)}."}

    data = _normalize_data(data)
    if not data:
        return {"success": False, "error": "No valid data rows provided to chart. Data must be a list of row dicts or a JSON string."}

    if chart_type == "auto":
        recommended = _recommend_chart_type(data, x, y)
        chart_type = recommended
        note = f"Auto-selected {recommended} chart based on data characteristics."
    else:
        note = ""

    try:
        fig = None
        if chart_type == "bar":
            fig = px.bar(data, x=x, y=y, title=title, color=x, color_discrete_sequence=px.colors.qualitative.Set2)
        elif chart_type == "line":
            fig = px.line(data, x=x, y=y, title=title, markers=True, color_discrete_sequence=px.colors.qualitative.Set2)
        elif chart_type == "pie":
            fig = px.pie(data, names=x, values=y, title=title, color_discrete_sequence=px.colors.qualitative.Set2)
        elif chart_type == "scatter":
            fig = px.scatter(data, x=x, y=y, title=title, trendline="lowess" if 5 <= len(data) <= 100 else None)

        if fig is not None:
            fig.update_layout(
                margin=dict(l=20, r=20, t=50, b=20),
                template="plotly_white",
                hovermode="x unified",
            )

        return {
            "success": True,
            "chart_type": chart_type,
            "figure": fig.to_dict() if fig else {},
            "recommendation_note": note,
        }
    except Exception as e:
        return {"success": False, "error": f"Chart generation failed: {e}"}
