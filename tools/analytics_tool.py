import json
from typing import Any, Dict, List


def _json_default(o):
    if hasattr(o, 'tolist'):
        return o.tolist()
    try:
        return str(o)
    except Exception:
        return None


def generate_forecast(data: List[Dict[str, Any]], date_col: str = "", value_col: str = "", periods: int = 5) -> Dict[str, Any]:
    if not data or not date_col or not value_col:
        return {"success": False, "error": "data, date_col, and value_col are required."}
    try:
        dates = [row.get(date_col, "") for row in data]
        values = []
        for row in data:
            v = row.get(value_col)
            if v is None:
                return {"success": False, "error": f"Missing value in column '{value_col}'."}
            values.append(float(v))
        if len(values) < 3:
            return {"success": False, "error": "Need at least 3 data points for forecast."}

        import numpy as np
        x = np.arange(len(values))
        y = np.array(values)
        coeffs = np.polyfit(x, y, min(2, len(values) - 1))
        poly = np.poly1d(coeffs)
        future_x = np.arange(len(values), len(values) + periods)
        forecasted = [round(float(poly(i)), 2) for i in future_x]

        last_date = dates[-1] if dates else ""
        future_dates = [f"Period +{i+1}" for i in range(periods)]
        if last_date and " " not in last_date and "-" in str(last_date):
            from datetime import datetime, timedelta
            try:
                ref = datetime.strptime(str(last_date)[:10], "%Y-%m-%d")
                future_dates = [(ref + timedelta(days=30 * (i + 1))).strftime("%Y-%m-%d") for i in range(periods)]
            except ValueError:
                pass

        hist = [{"date": d, "value": v} for d, v in zip(dates, values)]
        fcast = [{"date": d, "value": v} for d, v in zip(future_dates, forecasted)]

        import plotly.graph_objects as go
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=[p["date"] for p in hist], y=[p["value"] for p in hist],
            mode="lines+markers", name="Historical", line=dict(color="#00d4aa"),
        ))
        fig.add_trace(go.Scatter(
            x=[p["date"] for p in fcast], y=[p["value"] for p in fcast],
            mode="lines+markers", name="Forecast", line=dict(color="#7c3aed", dash="dash"),
        ))
        fig.update_layout(
            title=f"Forecast ({'up' if coeffs[0] > 0 else 'down'} trend)",
            xaxis_title=date_col, yaxis_title=value_col,
            hovermode="x unified",
        )

        raw_fig = fig.to_dict()
        figure = json.loads(json.dumps(raw_fig, default=_json_default))
        return {
            "success": True,
            "historical": hist,
            "forecast": fcast,
            "coefficients": [round(float(c), 4) for c in coeffs],
            "trend": "up" if coeffs[0] > 0 else ("down" if coeffs[0] < 0 else "flat"),
            "next_prediction": forecasted[0],
            "figure": figure,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def compare_segments(data_a: List[Dict[str, Any]], data_b: List[Dict[str, Any]],
                     label_a: str = "A", label_b: str = "B",
                     value_col: str = "", category_col: str = "") -> Dict[str, Any]:
    if not data_a or not data_b or not value_col:
        return {"success": False, "error": "Both data_a, data_b and value_col are required."}
    try:
        def summarize(d):
            vals = [float(r.get(value_col, 0) or 0) for r in d]
            cats = {}
            for r in d:
                k = r.get(category_col, "Unknown") if category_col else "All"
                v = float(r.get(value_col, 0) or 0)
                cats[k] = cats.get(k, 0) + v
            top = sorted(cats.items(), key=lambda x: -x[1])[:5] if cats else []
            return {
                "total": round(sum(vals), 2),
                "avg": round(sum(vals) / len(vals), 2) if vals else 0,
                "max": round(max(vals), 2) if vals else 0,
                "min": round(min(vals), 2) if vals else 0,
                "count": len(vals),
                "top_categories": [{"name": k, "value": round(v, 2)} for k, v in top],
            }

        summary_a = summarize(data_a)
        summary_b = summarize(data_b)

        pct_diff = round(
            ((summary_b["total"] - summary_a["total"]) / summary_a["total"]) * 100 if summary_a["total"] else 0, 2
        )

        return {
            "success": True,
            "segment_a": {**summary_a, "label": label_a},
            "segment_b": {**summary_b, "label": label_b},
            "change": {
                "absolute": round(summary_b["total"] - summary_a["total"], 2),
                "percent": pct_diff,
                "direction": "up" if pct_diff > 0 else ("down" if pct_diff < 0 else "flat"),
            },
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
