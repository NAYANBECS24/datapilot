import json
import os
import sqlite3
from typing import Any, Dict, List, Optional, Union

import numpy as np
import pandas as pd
import plotly.graph_objects as go


def auto_ml_forecast(
    db_path: str,
    table: str,
    target_col: str,
    date_col: Optional[str] = None,
    periods: int = 6,
    conn_str: str = "",
) -> Dict[str, Any]:
    try:
        if conn_str and (conn_str.startswith("postgresql") or conn_str.startswith("postgres")):
            return _forecast_pg(conn_str, table, target_col, date_col, periods)

        if not os.path.exists(db_path):
            return {"success": False, "error": f"Database not found: {db_path}"}

        conn = sqlite3.connect(db_path)
        query = f'SELECT * FROM "{table}"'
        df = pd.read_sql_query(query, conn)
        conn.close()

        if df.empty:
            return {"success": False, "error": f"Table '{table}' is empty."}

        if target_col not in df.columns:
            return {"success": False, "error": f"Column '{target_col}' not in table."}

        df = df.dropna(subset=[target_col])
        if len(df) < 5:
            return {"success": False, "error": f"Need at least 5 rows with values, got {len(df)}."}

        y_raw = df[target_col].values.astype(float)

        if date_col and date_col in df.columns:
            dates = pd.to_datetime(df[date_col], errors="coerce")
            df = df.dropna(subset=[date_col])
            df = df.sort_values(date_col)
            y_raw = df[target_col].values.astype(float)
            last_date = dates.max()
        else:
            last_date = None

        X = np.arange(len(y_raw)).reshape(-1, 1)
        y = y_raw

        from sklearn.linear_model import LinearRegression
        model = LinearRegression()
        model.fit(X, y)
        y_pred = model.predict(X)

        residuals = y - y_pred
        std_err = np.std(residuals) if len(residuals) > 1 else 0.0

        future_X = np.arange(len(y), len(y) + periods).reshape(-1, 1)
        future_y = model.predict(future_X)
        conf_int = 1.96 * std_err

        past_df = pd.DataFrame({
            "index": list(range(len(y))),
            "value": y,
            "predicted": y_pred,
        })
        if date_col and last_date is not None:
            freq = _infer_freq(dates)
            last_date_pd = pd.to_datetime(last_date)
            future_dates = pd.date_range(start=last_date_pd + freq, periods=periods, freq=freq)
            past_df["label"] = dates.values if len(dates) == len(y) else past_df["index"]
            future_labels = [str(d.date()) for d in future_dates]
        else:
            future_labels = [f"Step {i+1}" for i in range(periods)]

        future_df = pd.DataFrame({
            "label": future_labels,
            "forecast": future_y,
            "ci_lower": future_y - conf_int,
            "ci_upper": future_y + conf_int,
        })

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=past_df.get("label", past_df["index"]),
            y=past_df["value"],
            mode="lines+markers",
            name="Actual",
            line=dict(color="#00d4aa", width=2),
        ))
        fig.add_trace(go.Scatter(
            x=future_df["label"],
            y=future_df["forecast"],
            mode="lines+markers",
            name="Forecast",
            line=dict(color="#7c3aed", width=2, dash="dash"),
        ))
        fig.add_trace(go.Scatter(
            x=list(future_df["label"]) + list(future_df["label"])[::-1],
            y=list(future_df["ci_upper"]) + list(future_df["ci_lower"])[::-1],
            fill="toself",
            fillcolor="rgba(124, 58, 237, 0.15)",
            line=dict(color="rgba(255,255,255,0)"),
            name="95% CI",
            showlegend=True,
        ))
        fig.update_layout(
            title=f"ML Forecast: {target_col}",
            template="plotly_white",
            margin=dict(l=20, r=20, t=50, b=20),
            hovermode="x unified",
        )

        r2 = model.score(X, y)

        return {
            "success": True,
            "figure": fig.to_dict(),
            "metrics": {
                "r2_score": round(r2, 4),
                "std_error": round(std_err, 2),
                "training_rows": len(y),
                "forecast_periods": periods,
            },
            "forecast": future_df.to_dict(orient="records"),
            "summary": (
                f"Trained LinearRegression on {len(y)} rows (R²={r2:.3f}). "
                f"Predicted next {periods} periods with 95% CI ±${conf_int:,.0f}."
            ),
        }
    except ImportError:
        return {"success": False, "error": "scikit-learn not installed. Run: pip install scikit-learn"}
    except Exception as e:
        return {"success": False, "error": f"ML forecast failed: {e}"}


def _forecast_pg(
    conn_str: str, table: str, target_col: str, date_col: Optional[str], periods: int
) -> Dict[str, Any]:
    try:
        import psycopg2
        from tools.db_manager import parse_connection_string

        params = parse_connection_string(conn_str)
        pg_params = {k: v for k, v in params.items() if k != "type"}
        conn = psycopg2.connect(**pg_params)
        df = pd.read_sql_query(f'SELECT * FROM "{table}"', conn)
        conn.close()

        if df.empty:
            return {"success": False, "error": f"Table '{table}' is empty."}

        df = df.dropna(subset=[target_col])
        y_raw = df[target_col].values.astype(float)
        X = np.arange(len(y_raw)).reshape(-1, 1)

        from sklearn.linear_model import LinearRegression
        model = LinearRegression()
        model.fit(X, y_raw)
        y_pred = model.predict(X)
        residuals = y_raw - y_pred
        std_err = np.std(residuals) if len(residuals) > 1 else 0.0

        future_X = np.arange(len(y_raw), len(y_raw) + periods).reshape(-1, 1)
        future_y = model.predict(future_X)
        conf_int = 1.96 * std_err

        future_df = pd.DataFrame({
            "label": [f"Step {i+1}" for i in range(periods)],
            "forecast": future_y,
            "ci_lower": future_y - conf_int,
            "ci_upper": future_y + conf_int,
        })

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=list(range(len(y_raw))), y=y_raw, mode="lines+markers", name="Actual", line=dict(color="#00d4aa", width=2)))
        fig.add_trace(go.Scatter(x=list(range(len(y_raw), len(y_raw)+periods)), y=future_y, mode="lines+markers", name="Forecast", line=dict(color="#7c3aed", width=2, dash="dash")))
        fig.add_trace(go.Scatter(
            x=list(range(len(y_raw), len(y_raw)+periods)) + list(range(len(y_raw)+periods-1, len(y_raw)-1, -1)),
            y=list(future_y + conf_int) + list(future_y - conf_int)[::-1],
            fill="toself", fillcolor="rgba(124, 58, 237, 0.15)", line=dict(color="rgba(255,255,255,0)"), name="95% CI",
        ))
        fig.update_layout(title=f"ML Forecast: {target_col}", template="plotly_white", margin=dict(l=20, r=20, t=50, b=20))

        return {"success": True, "figure": fig.to_dict(), "metrics": {"r2_score": round(model.score(X, y_raw), 4), "training_rows": len(y_raw), "forecast_periods": periods}, "forecast": future_df.to_dict(orient="records")}
    except ImportError:
        return {"success": False, "error": "psycopg2 or scikit-learn not installed."}
    except Exception as e:
        return {"success": False, "error": f"PG ML forecast failed: {e}"}


def _infer_freq(dates: pd.Series) -> pd.DateOffset:
    diffs = pd.Series(dates).diff().dropna()
    if len(diffs) == 0:
        return pd.DateOffset(months=1)
    avg = diffs.dt.days.mean()
    if avg <= 2:
        return pd.DateOffset(days=1)
    elif avg <= 20:
        return pd.DateOffset(weeks=1)
    elif avg <= 45:
        return pd.DateOffset(months=1)
    elif avg <= 80:
        return pd.DateOffset(months=3)
    else:
        return pd.DateOffset(years=1)
