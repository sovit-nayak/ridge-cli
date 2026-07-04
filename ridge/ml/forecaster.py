"""
Focus score forecasting using Facebook Prophet.
Predicts next 7 days of focus scores based on personal history.
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional

DB_PATH = Path.home() / ".ridge" / "data.db"
MIN_DAYS = 14


def _load_daily_scores() -> list[dict]:
    """Load daily focus scores from DB."""
    if not DB_PATH.exists():
        return []

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT date(ts) as day, category, app FROM events ORDER BY ts"
    ).fetchall()
    conn.close()

    by_day = defaultdict(list)
    for r in rows:
        by_day[r["day"]].append({"category": r["category"], "app": r["app"]})

    daily = []
    for day, events in sorted(by_day.items()):
        total = len(events)
        if total == 0:
            continue
        deep = sum(1 for e in events if e["category"] == "deep")
        escape = sum(1 for e in events if e["category"] == "escape")
        apps = [e["app"] for e in events if e["app"]]
        switches = sum(1 for i in range(1, len(apps)) if apps[i] != apps[i-1])
        score = min(100, max(0, round(
            (deep/total)*70 + max(0, 20-(switches*0.67)) + max(0, 10-((escape/total)*50))
        )))
        daily.append({"ds": day, "y": float(score)})

    return daily


def forecast_scores(periods: int = 7) -> dict:
    """
    Forecast focus scores for the next N days using Prophet.
    Returns forecast dict with predictions and confidence intervals.
    """
    daily = _load_daily_scores()

    if len(daily) < MIN_DAYS:
        return {
            "error": "insufficient_data",
            "days_available": len(daily),
            "days_needed": MIN_DAYS,
            "message": f"Need {MIN_DAYS} days of data to forecast. You have {len(daily)}."
        }

    try:
        import pandas as pd
        from prophet import Prophet
        import warnings
        warnings.filterwarnings("ignore")

        df = pd.DataFrame(daily)
        df["ds"] = pd.to_datetime(df["ds"])

        model = Prophet(
            daily_seasonality=False,
            weekly_seasonality=True,
            yearly_seasonality=False,
            changepoint_prior_scale=0.3,
            seasonality_prior_scale=5.0,
            interval_width=0.8,
        )
        model.fit(df)

        future = model.make_future_dataframe(periods=periods)
        forecast = model.predict(future)

        # Get only future predictions
        future_preds = forecast[forecast["ds"] > df["ds"].max()].tail(periods)

        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        predictions = []
        for _, row in future_preds.iterrows():
            score = int(min(100, max(0, round(row["yhat"]))))
            lower = int(min(100, max(0, round(row["yhat_lower"]))))
            upper = int(min(100, max(0, round(row["yhat_upper"]))))
            weekday = row["ds"].weekday()
            predictions.append({
                "date": row["ds"].strftime("%b %d"),
                "day": day_names[weekday],
                "score": score,
                "lower": lower,
                "upper": upper,
                "label": _score_label(score),
                "warning": score < 55,
            })

        # Historical accuracy — backtest last 7 days
        historical = forecast[forecast["ds"] <= df["ds"].max()].tail(7)
        actual_last7 = df.tail(7)
        if len(actual_last7) == len(historical):
            errors = abs(historical["yhat"].values - actual_last7["y"].values)
            accuracy = max(0, round(100 - errors.mean()))
        else:
            accuracy = None

        # Trend direction
        first_half = [d["y"] for d in daily[:len(daily)//2]]
        second_half = [d["y"] for d in daily[len(daily)//2:]]
        trend = "improving" if (sum(second_half)/len(second_half)) > (sum(first_half)/len(first_half)) else "declining"

        return {
            "predictions": predictions,
            "days_of_data": len(daily),
            "accuracy": accuracy,
            "trend": trend,
            "avg_historical": round(sum(d["y"] for d in daily) / len(daily)),
        }

    except ImportError:
        return {
            "error": "prophet_not_installed",
            "message": "Run: pip install prophet"
        }
    except Exception as e:
        return {
            "error": "forecast_failed",
            "message": str(e)
        }


def _score_label(score: int) -> str:
    if score >= 85: return "Strong"
    if score >= 70: return "Good"
    if score >= 55: return "Average"
    if score >= 40: return "Weak"
    return "Low"