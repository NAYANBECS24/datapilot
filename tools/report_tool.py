from typing import Any, Dict, List


def generate_report(data: List[Dict[str, Any]], columns: List[str],
                    question: str = "", chart_titles: List[str] = None) -> Dict[str, Any]:
    if not data or not columns:
        return {"success": False, "error": "data and columns are required."}
    try:
        rows = len(data)
        numeric_cols = []
        text_cols = []
        for c in columns:
            vals = [r.get(c) for r in data[:20]]
            if any(isinstance(v, (int, float)) for v in vals if v is not None):
                numeric_cols.append(c)
            else:
                text_cols.append(c)

        summary_parts = [f"Analysis of {rows} record(s)"]
        if question:
            summary_parts.append(f"\nQuestion: {question}")

        if numeric_cols:
            summary_parts.append(f"\n**Numeric columns:** {', '.join(numeric_cols)}")
            for c in numeric_cols:
                vals = [float(r[c]) for r in data if r.get(c) is not None]
                if vals:
                    summary_parts.append(
                        f"- {c}: avg={sum(vals)/len(vals):.1f}, "
                        f"min={min(vals):.1f}, max={max(vals):.1f}, total={sum(vals):.1f}"
                    )

        if text_cols:
            summary_parts.append(f"\n**Categorical columns:** {', '.join(text_cols)}")
            for c in text_cols[:2]:
                vals = [str(r[c]) for r in data if r.get(c)]
                if vals:
                    from collections import Counter
                    top = Counter(vals).most_common(3)
                    summary_parts.append(f"- {c}: {', '.join(f'{k}({v})' for k, v in top)}")

        insights = []
        for c in numeric_cols:
            vals = [float(r[c]) for r in data if r.get(c) is not None]
            if len(vals) > 1:
                insights.append(f"{c} ranges from {min(vals):.1f} to {max(vals):.1f}")

        if chart_titles:
            summary_parts.append("\n**Visualizations included:**")
            for t in chart_titles:
                summary_parts.append(f"- {t}")

        return {
            "success": True,
            "summary": "\n".join(summary_parts),
            "insights": insights,
            "metric_count": len(numeric_cols),
            "row_count": rows,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}
