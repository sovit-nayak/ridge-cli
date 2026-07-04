"""
AI coaching letter — uses Claude API to write a weekly coaching letter
based on your actual focus patterns. Opt-in only.
"""

import sqlite3
import os
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

DB_PATH = Path.home() / ".ridge" / "data.db"
CONFIG_PATH = Path.home() / ".ridge" / "config.json"
MIN_DAYS = 7


def _load_week_summary(days: int = 7) -> dict:
    """Build a structured summary of the past week for the AI."""
    if not DB_PATH.exists():
        return {}

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()
    events = conn.execute(
        "SELECT date(ts) as day, category, domain, app FROM events WHERE ts >= ? ORDER BY ts",
        (since,)
    ).fetchall()
    sessions = conn.execute(
        "SELECT task, started_at, focus_score FROM sessions WHERE started_at >= ? ORDER BY started_at",
        (since,)
    ).fetchall()
    conn.close()

    by_day = defaultdict(list)
    for e in events:
        by_day[e["day"]].append(dict(e))

    day_summaries = []
    all_scores = []
    top_escape_domains = defaultdict(int)
    top_deep_domains = defaultdict(int)

    for day, day_events in sorted(by_day.items()):
        total = len(day_events)
        deep = sum(1 for e in day_events if e["category"] == "deep")
        escape = sum(1 for e in day_events if e["category"] == "escape")
        apps = [e["app"] for e in day_events if e["app"]]
        switches = sum(1 for i in range(1, len(apps)) if apps[i] != apps[i-1])
        score = min(100, max(0, round(
            (deep/total)*70 + max(0, 20-(switches*0.67)) + max(0, 10-((escape/total)*50))
        )))
        all_scores.append(score)

        for e in day_events:
            if e["category"] == "escape" and e["domain"]:
                top_escape_domains[e["domain"]] += 1
            if e["category"] == "deep" and e["domain"]:
                top_deep_domains[e["domain"]] += 1

        weekday = datetime.strptime(day, "%Y-%m-%d").strftime("%A")
        day_summaries.append({
            "date": day,
            "weekday": weekday,
            "score": score,
            "deep_pct": round((deep/total)*100) if total else 0,
            "escape_pct": round((escape/total)*100) if total else 0,
            "context_switches": switches,
        })

    top_escape = sorted(top_escape_domains.items(), key=lambda x: -x[1])[:3]
    top_deep = sorted(top_deep_domains.items(), key=lambda x: -x[1])[:3]
    task_names = [s["task"] for s in sessions if s["task"]]

    return {
        "days": day_summaries,
        "avg_score": round(sum(all_scores) / len(all_scores)) if all_scores else 0,
        "best_day": max(day_summaries, key=lambda x: x["score"]) if day_summaries else None,
        "worst_day": min(day_summaries, key=lambda x: x["score"]) if day_summaries else None,
        "top_escape_sites": top_escape,
        "top_deep_sites": top_deep,
        "tasks": task_names[:5],
        "total_sessions": len(sessions),
    }


def _build_prompt(summary: dict) -> str:
    """Build the prompt for Claude from the week summary."""
    days_text = "\n".join([
        f"  {d['weekday']} {d['date']}: score {d['score']}/100 | "
        f"deep {d['deep_pct']}% | escape {d['escape_pct']}% | switches {d['context_switches']}"
        for d in summary.get("days", [])
    ])

    escape_text = ", ".join([f"{d} ({c} visits)" for d, c in summary.get("top_escape_sites", [])])
    deep_text = ", ".join([f"{d} ({c} visits)" for d, c in summary.get("top_deep_sites", [])])

    return f"""You are Ridge CLI's AI coach. Write a weekly coaching letter based on this user's real focus data.

WEEK DATA:
{days_text}

Average score: {summary.get('avg_score', 0)}/100
Best day: {summary.get('best_day', {}).get('weekday', 'N/A')} at {summary.get('best_day', {}).get('score', 0)}/100
Worst day: {summary.get('worst_day', {}).get('weekday', 'N/A')} at {summary.get('worst_day', {}).get('score', 0)}/100
Top escape sites: {escape_text or 'none'}
Top deep work sites: {deep_text or 'none'}
Tasks worked on: {', '.join(summary.get('tasks', [])) or 'not specified'}

Write a coaching letter that:
1. Opens with an honest 1-sentence summary of the week
2. Highlights the best day and what made it work
3. Calls out ONE specific distraction pattern with the actual data
4. Gives ONE concrete, specific thing to try next week
5. Ends with next week's prediction based on the pattern

Tone: Direct, honest, encouraging. Like a coach who respects you enough to tell the truth.
Length: 150-200 words maximum.
Format: Plain prose, no headers, no bullet points.
Do not mention Ridge CLI or that you are an AI."""


def generate_coaching_letter(days: int = 7) -> dict:
    """
    Generate a weekly coaching letter using Claude API.
    Requires ANTHROPIC_API_KEY environment variable or ~/.ridge/config.json.
    """
    summary = _load_week_summary(days)

    if not summary or len(summary.get("days", [])) < MIN_DAYS:
        return {
            "error": "insufficient_data",
            "message": f"Need {MIN_DAYS} days of data for coaching. You have {len(summary.get('days', []))}."
        }

    # Get API key from env or config
    api_key = os.environ.get("ANTHROPIC_API_KEY")

    if not api_key and CONFIG_PATH.exists():
        import json
        try:
            config = json.loads(CONFIG_PATH.read_text())
            api_key = config.get("anthropic_api_key")
        except Exception:
            pass

    if not api_key:
        return {
            "error": "no_api_key",
            "message": (
                "Set your Anthropic API key to use AI coaching:\n"
                "  export ANTHROPIC_API_KEY=your_key_here\n"
                "  OR run: ridge config set anthropic_api_key your_key_here"
            )
        }

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        message = client.messages.create(
            model="claude-opus-4-6",
            max_tokens=500,
            messages=[{"role": "user", "content": _build_prompt(summary)}]
        )

        letter = message.content[0].text

        return {
            "letter": letter,
            "week_avg": summary["avg_score"],
            "best_day": summary.get("best_day", {}),
            "worst_day": summary.get("worst_day", {}),
            "days_analyzed": len(summary.get("days", [])),
        }

    except ImportError:
        return {
            "error": "anthropic_not_installed",
            "message": "Run: pip install anthropic"
        }
    except Exception as e:
        return {
            "error": "api_error",
            "message": str(e)
        }