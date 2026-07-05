"""
Ridge CLI — Event Labeler
Labels historical events using the AI router and stores
them as training data for the future local HuggingFace model.

Training data stored at: ~/.ridge/training_data.jsonl
Each line is one labeled event.
"""

import json
import sqlite3
import time
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Optional
import tzlocal

RIDGE_DIR = Path.home() / ".ridge"
DB_PATH = RIDGE_DIR / "data.db"
TRAINING_DATA_PATH = RIDGE_DIR / "training_data.jsonl"
LOCAL_TZ = tzlocal.get_localzone()


def _load_unlabeled_events(limit: int = 50) -> list[dict]:
    """
    Load events that haven't been labeled yet.
    Looks back 30 days, skips already-labeled events.
    """
    if not DB_PATH.exists():
        return []

    # Load already-labeled event IDs
    labeled_ids = set()
    if TRAINING_DATA_PATH.exists():
        with open(TRAINING_DATA_PATH) as f:
            for line in f:
                try:
                    record = json.loads(line)
                    if "event_id" in record:
                        labeled_ids.add(record["event_id"])
                except Exception:
                    continue

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    since = (datetime.utcnow() - timedelta(days=30)).isoformat()

    rows = conn.execute(
        """SELECT e.*, 
           LAG(e.app) OVER (ORDER BY e.ts) as previous_app,
           LAG(e.ts) OVER (ORDER BY e.ts) as previous_ts,
           LEAD(e.app) OVER (ORDER BY e.ts) as next_app
           FROM events e 
           WHERE e.ts >= ? 
           ORDER BY e.ts
           LIMIT ?""",
        (since, limit * 3)  # load more, filter down
    ).fetchall()
    conn.close()

    events = []
    for r in rows:
        if r["id"] in labeled_ids:
            continue
        if len(events) >= limit:
            break

        # Build feature vector
        try:
            curr_ts = datetime.fromisoformat(r["ts"])
            prev_ts = datetime.fromisoformat(r["previous_ts"]) if r["previous_ts"] else curr_ts
            time_in_prev = (curr_ts - prev_ts).total_seconds()
        except Exception:
            time_in_prev = 0

        event = {
            "event_id": r["id"],
            "ts": r["ts"],
            "app": r["app"] or "",
            "domain": r["domain"] or "",
            "url": r["url"] or "",
            "category": r["category"] or "shallow",
            "previous_app": r["previous_app"] or "",
            "next_app": r["next_app"] or "",
            "time_in_previous_app": time_in_prev,
            "hour": curr_ts.hour,
        }
        events.append(event)

    return events


def _save_labeled_event(event: dict, label: dict):
    """Append a labeled event to training_data.jsonl."""
    RIDGE_DIR.mkdir(exist_ok=True)
    record = {
        "event_id": event.get("event_id"),
        "ts": event.get("ts"),
        "features": {
            "app": event.get("app"),
            "domain": event.get("domain"),
            "previous_app": event.get("previous_app"),
            "next_app": event.get("next_app"),
            "time_in_previous_app": event.get("time_in_previous_app"),
            "hour": event.get("hour"),
        },
        "label": label.get("category"),
        "confidence": label.get("confidence"),
        "reason": label.get("reason"),
        "source": label.get("source"),
        "labeled_at": datetime.utcnow().isoformat(),
    }
    with open(TRAINING_DATA_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")


def label_recent_events(limit: int = 50, verbose: bool = False) -> dict:
    """
    Label recent unlabeled events using the AI router.
    Returns summary of what was labeled.
    """
    from ridge.ml.router import classify

    events = _load_unlabeled_events(limit=limit)

    if not events:
        return {"labeled": 0, "message": "No new events to label"}

    labeled = 0
    by_source = defaultdict(int)
    by_category = defaultdict(int)

    for event in events:
        try:
            # Enrich event with defaults for missing fields
            enriched = {
                "app": event.get("app", ""),
                "domain": event.get("domain", ""),
                "previous_app": event.get("previous_app", "unknown"),
                "next_app": event.get("next_app", "unknown"),
                "time_in_previous_app": event.get("time_in_previous_app", 300),
                "duration_in_app": event.get("duration_in_app", 120),
                "hour": event.get("hour", 12),
                "switches_in_last_30min": event.get("switches_in_last_30min", 0),
            }
            # Try Gemini directly first, fall back to router
            from ridge.ml.gemini import classify_event as gemini_classify
            label = gemini_classify(enriched)
            if not label:
                from ridge.ml.router import classify
                label = classify(enriched)
            _save_labeled_event(event, label)
            labeled += 1
            by_source[label.get("source", "unknown")] += 1
            by_category[label.get("category", "unknown")] += 1

            if verbose:
                src = label.get("source", "?")
                cat = label.get("category", "?")
                conf = label.get("confidence", 0)
                domain = event.get("domain") or event.get("app") or "?"
                print(f"  [{src}] {domain} → {cat} ({conf}%)")

            # Delay to avoid Gemini rate limiting (15 req/min free tier)
            time.sleep(4)

        except Exception as e:
            if verbose:
                print(f"  Error labeling event {event.get('event_id')}: {e}")
            continue

    return {
        "labeled": labeled,
        "by_source": dict(by_source),
        "by_category": dict(by_category),
        "training_data_size": count_training_samples(),
    }


def count_training_samples() -> int:
    """Count total labeled training samples."""
    if not TRAINING_DATA_PATH.exists():
        return 0
    with open(TRAINING_DATA_PATH) as f:
        return sum(1 for line in f if line.strip())


def get_training_summary() -> dict:
    """Get summary of training data collected so far."""
    if not TRAINING_DATA_PATH.exists():
        return {"total": 0, "by_source": {}, "by_category": {}}

    total = 0
    by_source = defaultdict(int)
    by_category = defaultdict(int)

    with open(TRAINING_DATA_PATH) as f:
        for line in f:
            try:
                record = json.loads(line)
                total += 1
                by_source[record.get("source", "unknown")] += 1
                by_category[record.get("label", "unknown")] += 1
            except Exception:
                continue

    return {
        "total": total,
        "by_source": dict(by_source),
        "by_category": dict(by_category),
        "ready_for_training": total >= 100,
        "samples_until_training": max(0, 100 - total),
    }


def enrich_patterns_with_labels() -> dict:
    """
    Re-analyze patterns using AI-labeled data instead of raw categories.
    Returns enriched pattern dict for use in ridge insights.
    """
    summary = get_training_summary()
    if summary["total"] < 20:
        return {"enriched": False, "reason": "Not enough labeled data yet"}

    # Load labeled data
    records = []
    if TRAINING_DATA_PATH.exists():
        with open(TRAINING_DATA_PATH) as f:
            for line in f:
                try:
                    records.append(json.loads(line))
                except Exception:
                    continue

    # Find AI-overridden classifications
    # Where AI label differs from original rule-based category
    overrides = [
        r for r in records
        if r.get("source") in ("gemini", "ollama:gemma2:2b", "ollama:llama3.2:3b", "ollama:mistral:7b")
    ]

    return {
        "enriched": True,
        "total_labeled": summary["total"],
        "ai_labeled": len(overrides),
        "by_category": summary["by_category"],
        "by_source": summary["by_source"],
    }