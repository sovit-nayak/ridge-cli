"""
Pattern detection — finds recurring focus and distraction patterns
in your historical browsing data using statistical analysis.
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional
import tzlocal

RIDGE_DIR = Path.home() / ".ridge"
DB_PATH = RIDGE_DIR / "data.db"
LOCAL_TZ = tzlocal.get_localzone()
MIN_DAYS = 7


def _load_gemini_labels() -> dict:
    """Load Gemini-labeled categories keyed by event_id."""
    labels = {}
    training_path = RIDGE_DIR / "training_data.jsonl"
    if not training_path.exists():
        return labels
    import json
    with open(training_path) as f:
        for line in f:
            try:
                record = json.loads(line)
                if record.get("source") == "gemini" and record.get("event_id"):
                    labels[record["event_id"]] = record.get("label", "shallow")
            except Exception:
                continue
    return labels


def _load_events(days: int = 60):
    """Load events from the last N days, enriched with Gemini labels where available."""
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    rows = conn.execute(
        "SELECT * FROM events WHERE ts >= ? ORDER BY ts", (since,)
    ).fetchall()
    conn.close()

    # Enrich with Gemini labels
    gemini_labels = _load_gemini_labels()
    if not gemini_labels:
        return rows

    # Convert to dicts so we can override category
    enriched = []
    for row in rows:
        d = dict(row)
        if d["id"] in gemini_labels:
            d["category"] = gemini_labels[d["id"]]
            d["ai_labeled"] = True
        else:
            d["ai_labeled"] = False
        enriched.append(d)
    return enriched


def _to_local(ts_str: str) -> datetime:
    """Convert UTC ISO string to local datetime."""
    dt = datetime.fromisoformat(ts_str).replace(tzinfo=None)
    from zoneinfo import ZoneInfo
    utc = dt.replace(tzinfo=ZoneInfo("UTC"))
    return utc.astimezone(LOCAL_TZ)


def _calc_day_score(events: list) -> int:
    """Calculate focus score for a list of events."""
    if not events:
        return 0
    total = len(events)
    deep = sum(1 for e in events if e["category"] == "deep")
    escape = sum(1 for e in events if e["category"] == "escape")
    apps = [e["app"] for e in events if e["app"]]
    switches = sum(1 for i in range(1, len(apps)) if apps[i] != apps[i-1])
    deep_score = (deep / total) * 70
    switch_score = max(0, 20 - (switches * 0.67))
    escape_score = max(0, 10 - ((escape / total) * 50))
    return min(100, max(0, round(deep_score + switch_score + escape_score)))


def analyze_patterns(days: int = 60) -> dict:
    """
    Main pattern analysis function.
    Returns a dict of detected patterns with confidence scores.
    """
    events = _load_events(days)

    if not events:
        return {"error": "no_data", "min_days": MIN_DAYS}

    # Parse events with local timestamps
    parsed = []
    for e in events:
        try:
            local_dt = _to_local(e["ts"])
            parsed.append({
                "ts": local_dt,
                "hour": local_dt.hour,
                "weekday": local_dt.weekday(),  # 0=Mon, 6=Sun
                "date": local_dt.date(),
                "category": e["category"] or "shallow",
                "domain": e["domain"] or "",
                "app": e["app"] or "",
            })
        except Exception:
            continue

    if len(parsed) < 20:
        return {"error": "insufficient_data", "min_days": MIN_DAYS, "current_events": len(parsed)}

    patterns = []

    # ── PATTERN 1: Hourly escape tendency ──
    hour_escape = defaultdict(int)
    hour_total = defaultdict(int)
    for e in parsed:
        hour_total[e["hour"]] += 1
        if e["category"] == "escape":
            hour_escape[e["hour"]] += 1

    worst_hour = None
    worst_rate = 0
    for h in range(24):
        if hour_total[h] >= 5:
            rate = hour_escape[h] / hour_total[h]
            if rate > worst_rate:
                worst_rate = rate
                worst_hour = h

    if worst_hour is not None and worst_rate > 0.4:
        patterns.append({
            "type": "escape_hour",
            "title": f"You consistently drift at {worst_hour}:00",
            "detail": f"Escape sites make up {round(worst_rate*100)}% of your activity at {worst_hour}:00 — your highest distraction window.",
            "confidence": min(99, round(worst_rate * 120)),
            "hour": worst_hour,
            "escape_rate": round(worst_rate * 100),
            "recommendation": f"Protect {worst_hour}:00–{worst_hour+1}:00. Close all social tabs before this window opens.",
            "severity": "high" if worst_rate > 0.6 else "medium",
        })

    # ── PATTERN 2: Best focus hour ──
    hour_deep = defaultdict(int)
    for e in parsed:
        if e["category"] == "deep":
            hour_deep[e["hour"]] += 1

    best_hour = max(hour_deep, key=hour_deep.get) if hour_deep else None
    if best_hour is not None and hour_deep[best_hour] >= 5:
        deep_rate = hour_deep[best_hour] / max(hour_total[best_hour], 1)
        patterns.append({
            "type": "peak_hour",
            "title": f"{best_hour}:00 is your peak focus window",
            "detail": f"You do your best deep work at {best_hour}:00. {round(deep_rate*100)}% of activity in this hour is deep work.",
            "confidence": min(95, round(deep_rate * 110)),
            "hour": best_hour,
            "deep_rate": round(deep_rate * 100),
            "recommendation": f"Schedule your hardest tasks at {best_hour}:00. Guard it from meetings.",
            "severity": "positive",
        })

    # ── PATTERN 3: Weekday patterns ──
    day_scores = defaultdict(list)
    by_date = defaultdict(list)
    for e in parsed:
        by_date[e["date"]].append(e)

    for date, day_events in by_date.items():
        score = _calc_day_score(day_events)
        weekday = list(day_events)[0]["weekday"]
        day_scores[weekday].append(score)

    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    best_day = None
    worst_day = None
    best_avg = 0
    worst_avg = 100

    for wd, scores in day_scores.items():
        if len(scores) >= 2:
            avg = sum(scores) / len(scores)
            if avg > best_avg:
                best_avg = avg
                best_day = wd
            if avg < worst_avg:
                worst_avg = avg
                worst_day = wd

    if best_day is not None:
        patterns.append({
            "type": "best_weekday",
            "title": f"{day_names[best_day]} is your strongest day",
            "detail": f"Your average focus score on {day_names[best_day]} is {round(best_avg)}/100 — your weekly peak.",
            "confidence": 85,
            "day": day_names[best_day],
            "avg_score": round(best_avg),
            "recommendation": f"Schedule deep work and important deliverables on {day_names[best_day]}.",
            "severity": "positive",
        })

    if worst_day is not None and worst_day != best_day:
        patterns.append({
            "type": "worst_weekday",
            "title": f"{day_names[worst_day]} is your weakest day",
            "detail": f"Your average focus score on {day_names[worst_day]} is {round(worst_avg)}/100 — your weekly low.",
            "confidence": 85,
            "day": day_names[worst_day],
            "avg_score": round(worst_avg),
            "recommendation": f"Don't schedule deep work on {day_names[worst_day]}. Use it for meetings, admin, and reviews.",
            "severity": "medium",
        })

    # ── PATTERN 4: Domain spiral detection ──
    domain_visits = defaultdict(int)
    domain_time = defaultdict(int)
    for e in parsed:
        if e["domain"] and e["category"] == "escape":
            domain_visits[e["domain"]] += 1

    top_escape = sorted(domain_visits.items(), key=lambda x: -x[1])[:3]
    for domain, visits in top_escape:
        if visits >= 5:
            avg_session = round(visits * 0.5)
            patterns.append({
                "type": "domain_spiral",
                "title": f"You underestimate your time on {domain}",
                "detail": f"You visited {domain} {visits} times this period. Each visit likely runs far longer than planned.",
                "confidence": 82,
                "domain": domain,
                "visits": visits,
                "est_minutes": avg_session,
                "recommendation": f"Before opening {domain}, set a 5-minute timer. You'll see the spiral in real time.",
                "severity": "high" if visits > 15 else "medium",
            })

    # ── PATTERN 5: Context switch load ──
    daily_switches = []
    for date, day_events in by_date.items():
        apps = [e["app"] for e in day_events if e["app"]]
        switches = sum(1 for i in range(1, len(apps)) if apps[i] != apps[i-1])
        daily_switches.append(switches)

    if daily_switches:
        avg_switches = sum(daily_switches) / len(daily_switches)
        if avg_switches > 20:
            patterns.append({
                "type": "context_switching",
                "title": f"High context switching — avg {round(avg_switches)} switches/day",
                "detail": f"You average {round(avg_switches)} app/tab switches per day. Research shows each switch costs ~15 min of recovery time.",
                "confidence": 90,
                "avg_switches": round(avg_switches),
                "est_daily_cost_mins": round(avg_switches * 2),
                "recommendation": "Try working in 90-minute blocks with notifications off. Close all tabs except the one you need.",
                "severity": "high" if avg_switches > 30 else "medium",
            })

    # ── SUMMARY STATS ──
    all_scores = [_calc_day_score(v) for v in by_date.values()]
    total_deep = sum(1 for e in parsed if e["category"] == "deep")
    total_escape = sum(1 for e in parsed if e["category"] == "escape")

    return {
        "patterns": sorted(patterns, key=lambda x: x["confidence"], reverse=True),
        "summary": {
            "days_analyzed": len(by_date),
            "total_events": len(parsed),
            "avg_score": round(sum(all_scores) / len(all_scores)) if all_scores else 0,
            "best_score": max(all_scores) if all_scores else 0,
            "worst_score": min(all_scores) if all_scores else 0,
            "deep_pct": round((total_deep / len(parsed)) * 100) if parsed else 0,
            "escape_pct": round((total_escape / len(parsed)) * 100) if parsed else 0,
        }
    }