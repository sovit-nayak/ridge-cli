"""
Anomaly detection — flags unusual days using IsolationForest.
Detects both negative anomalies (crash days) and positive ones (exceptional days).
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

DB_PATH = Path.home() / ".ridge" / "data.db"
MIN_DAYS = 14


def _load_daily_features() -> list[dict]:
    """Load daily feature vectors for anomaly detection."""
    if not DB_PATH.exists():
        return []

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT date(ts) as day, category, app, domain FROM events ORDER BY ts"
    ).fetchall()
    conn.close()

    by_day = defaultdict(list)
    for r in rows:
        by_day[r["day"]].append({
            "category": r["category"] or "shallow",
            "app": r["app"] or "",
            "domain": r["domain"] or "",
        })

    daily = []
    for day, events in sorted(by_day.items()):
        total = len(events)
        if total < 5:
            continue

        deep = sum(1 for e in events if e["category"] == "deep")
        escape = sum(1 for e in events if e["category"] == "escape")
        shallow = sum(1 for e in events if e["category"] == "shallow")
        apps = [e["app"] for e in events if e["app"]]
        switches = sum(1 for i in range(1, len(apps)) if apps[i] != apps[i-1])

        score = min(100, max(0, round(
            (deep/total)*70 + max(0, 20-(switches*0.67)) + max(0, 10-((escape/total)*50))
        )))

        daily.append({
            "date": day,
            "score": score,
            "total_events": total,
            "deep_pct": round((deep/total)*100),
            "escape_pct": round((escape/total)*100),
            "shallow_pct": round((shallow/total)*100),
            "context_switches": switches,
        })

    return daily


def detect_anomalies() -> dict:
    """
    Run IsolationForest on daily feature vectors.
    Returns list of anomalous days with explanations.
    """
    daily = _load_daily_features()

    if len(daily) < MIN_DAYS:
        return {
            "error": "insufficient_data",
            "days_available": len(daily),
            "days_needed": MIN_DAYS,
            "message": f"Need {MIN_DAYS} days to detect anomalies. You have {len(daily)}."
        }

    try:
        import numpy as np
        from sklearn.ensemble import IsolationForest
        from sklearn.preprocessing import StandardScaler

        features = np.array([
            [d["score"], d["deep_pct"], d["escape_pct"], d["context_switches"]]
            for d in daily
        ])

        scaler = StandardScaler()
        features_scaled = scaler.fit_transform(features)

        clf = IsolationForest(contamination=0.1, random_state=42)
        predictions = clf.fit_predict(features_scaled)
        scores = clf.score_samples(features_scaled)

        anomalies = []
        avg_score = sum(d["score"] for d in daily) / len(daily)
        avg_escape = sum(d["escape_pct"] for d in daily) / len(daily)
        avg_switches = sum(d["context_switches"] for d in daily) / len(daily)

        for i, (pred, day) in enumerate(zip(predictions, daily)):
            if pred == -1:  # Anomaly detected
                is_positive = day["score"] > avg_score + 15
                is_negative = day["score"] < avg_score - 15

                if is_positive:
                    atype = "positive"
                    title = f"Exceptional day — {day['score']}/100"
                    detail = (
                        f"This was one of your best days. "
                        f"Deep work: {day['deep_pct']}% · Escape: {day['escape_pct']}% · "
                        f"Switches: {day['context_switches']}. "
                        f"What made this day different? Try to replicate it."
                    )
                elif is_negative:
                    atype = "negative"
                    title = f"Crash day — {day['score']}/100"
                    causes = []
                    if day["escape_pct"] > avg_escape + 20:
                        causes.append(f"high escape ({day['escape_pct']}%)")
                    if day["context_switches"] > avg_switches * 1.5:
                        causes.append(f"high switching ({day['context_switches']} switches)")
                    if day["deep_pct"] < 10:
                        causes.append("almost no deep work")
                    detail = (
                        f"Significantly below your average of {round(avg_score)}. "
                        f"Likely causes: {', '.join(causes) if causes else 'unusual activity pattern'}."
                    )
                else:
                    atype = "unusual"
                    title = f"Unusual pattern — {day['score']}/100"
                    detail = f"This day had an unusual activity pattern compared to your normal behavior."

                anomalies.append({
                    "date": day["date"],
                    "type": atype,
                    "title": title,
                    "detail": detail,
                    "score": day["score"],
                    "avg_score": round(avg_score),
                    "deep_pct": day["deep_pct"],
                    "escape_pct": day["escape_pct"],
                    "context_switches": day["context_switches"],
                    "anomaly_score": round(float(scores[i]), 3),
                })

        anomalies.sort(key=lambda x: x["date"], reverse=True)

        return {
            "anomalies": anomalies,
            "days_analyzed": len(daily),
            "avg_score": round(avg_score),
            "anomaly_count": len(anomalies),
            "positive_count": sum(1 for a in anomalies if a["type"] == "positive"),
            "negative_count": sum(1 for a in anomalies if a["type"] == "negative"),
        }

    except ImportError:
        return {
            "error": "sklearn_not_installed",
            "message": "Run: pip install scikit-learn"
        }
    except Exception as e:
        return {
            "error": "detection_failed",
            "message": str(e)
        }