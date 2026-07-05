"""
Ridge CLI — Gemini API Classifier
Uses Google Gemini Flash (free tier) to classify focus events.
User provides their own API key — zero cost to Ridge.
"""

import json
import time
import urllib.request
import urllib.error
from typing import Optional
from ridge import config as cfg

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

CATEGORY_MAP = {
    "deep": "deep",
    "shallow": "shallow",
    "escape": "escape",
    "interruption": "escape",
}


def _strip_markdown(text: str) -> str:
    """Strip markdown code fences that Gemini always adds."""
    text = text.strip()
    if "```" not in text:
        return text
    parts = text.split("```")
    # parts[1] is content between first and second ```
    inner = parts[1] if len(parts) > 1 else parts[0]
    # Remove language tag on first line (e.g. "json\n")
    lines = inner.split("\n")
    if lines and lines[0].strip().isalpha():
        inner = "\n".join(lines[1:])
    return inner.strip()


def _call_api(prompt: str, api_key: str, retries: int = 3) -> Optional[str]:
    """Call Gemini API with retry on rate limit."""
    url = f"{GEMINI_API_URL}?key={api_key}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 500},
    }).encode("utf-8")

    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries - 1:
                time.sleep(5 * (attempt + 1))
                continue
            return None
        except Exception:
            return None
    return None


def _build_prompt(event: dict) -> str:
    """Build classification prompt from event features."""
    prev_app = event.get("previous_app", "unknown")
    curr_app = event.get("app", "unknown")
    domain = event.get("domain", "")
    duration_prev = event.get("time_in_previous_app", 0)
    duration_curr = event.get("duration_in_app", 0)
    hour = event.get("hour", 12)
    switches_30min = event.get("switches_in_last_30min", 0)
    next_app = event.get("next_app", "unknown")
    domain_part = f"visiting {domain}" if domain else f"using {curr_app}"

    return f"""Classify computer activity. Reply ONLY with JSON like: {{"category":"deep","confidence":85,"reason":"brief"}}

Activity: {domain_part}, prev={prev_app}, hour={hour}
Categories: deep=productive work, shallow=email/comms, escape=distraction/entertainment
JSON only, no markdown:"""


def classify_event(event: dict) -> Optional[dict]:
    """Classify a single event using Gemini API."""
    api_key = cfg.get("gemini_api_key")
    if not api_key:
        return None

    text = _call_api(_build_prompt(event), api_key)
    if not text:
        return None

    try:
        clean = _strip_markdown(text)
        result = json.loads(clean)
        category = CATEGORY_MAP.get(result.get("category", "shallow"), "shallow")
        confidence = int(result.get("confidence", 70))
        reason = result.get("reason", "")
        return {
            "category": category,
            "confidence": confidence,
            "reason": reason,
            "source": "gemini",
        }
    except Exception:
        return None


def classify_batch(events: list) -> list:
    """Classify multiple events, returning results list."""
    return [classify_event(e) for e in events]


def test_connection() -> tuple:
    """Test that the Gemini API key is valid and working."""
    api_key = cfg.get("gemini_api_key")
    if not api_key:
        return False, "No Gemini API key configured. Run: ridge setup"

    text = _call_api("Reply with only the word: hello", api_key, retries=2)
    if text:
        return True, f"Connected. Gemini replied: {text[:50]}"
    return False, "Connection failed. Rate limited or invalid key. Wait 60 seconds and try again."
