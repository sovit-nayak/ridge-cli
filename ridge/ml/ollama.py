"""
Ridge CLI — Ollama Local LLM Classifier
Runs classification entirely on the user's machine.
Zero API cost. Zero internet required. 100% private.

Requires Ollama installed: brew install ollama
Model pulled: ollama pull gemma2:2b (or llama3.2:3b, mistral:7b)
"""

import json
import urllib.request
import urllib.error
from typing import Optional
from ridge import config as cfg

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_API_URL = f"{OLLAMA_BASE_URL}/api/generate"

CATEGORY_MAP = {
    "deep": "deep",
    "shallow": "shallow",
    "escape": "escape",
    "interruption": "escape",
    "distraction": "escape",
    "productive": "deep",
    "communication": "shallow",
}


def _is_ollama_running() -> bool:
    """Check if Ollama server is running."""
    try:
        req = urllib.request.Request(
            f"{OLLAMA_BASE_URL}/api/tags",
            method="GET"
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def _model_is_available(model_name: str) -> bool:
    """Check if a specific model is pulled and ready."""
    try:
        req = urllib.request.Request(
            f"{OLLAMA_BASE_URL}/api/tags",
            method="GET"
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            models = [m["name"] for m in data.get("models", [])]
            # Check both exact name and name:latest
            return model_name in models or f"{model_name}:latest" in models
    except Exception:
        return False


def _build_prompt(event: dict) -> str:
    """Build a concise classification prompt for local models."""
    domain = event.get("domain", "")
    app = event.get("app", "")
    prev_app = event.get("previous_app", "unknown")
    hour = event.get("hour", 12)
    activity = f"visiting {domain}" if domain else f"using {app}"

    return f"""Classify this computer activity. Reply with JSON only.

Activity: {activity}
Previous app: {prev_app}
Hour: {hour}:00

Categories:
- deep: productive work (code, docs, design, data tools, learning)
- shallow: necessary comms (email, calendar, brief messaging)  
- escape: distraction (social media, entertainment, news)

Reply with only this JSON format:
{{"category": "deep", "confidence": 85, "reason": "brief reason"}}"""


def classify_event(event: dict) -> Optional[dict]:
    """
    Classify a single event using local Ollama model.
    Returns dict with category, confidence, reason or None on failure.
    """
    model = cfg.get("ollama_model") or "llama3.2:3b"

    if not _is_ollama_running():
        return None

    if not _model_is_available(model):
        return None

    prompt = _build_prompt(event)

    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 100,
        }
    }).encode("utf-8")

    try:
        req = urllib.request.Request(
            OLLAMA_API_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            text = data.get("response", "").strip()

        # Parse JSON from response
        clean = text.strip()

        # Strip markdown if present
        if "```" in clean:
            parts = clean.split("```")
            clean = parts[1] if len(parts) > 1 else parts[0]
            lines = clean.split("\n")
            if lines and lines[0].strip().lower() in ("json", ""):
                clean = "\n".join(lines[1:])
        clean = clean.strip()

        # Extract JSON if embedded in text
        if "{" in clean and "}" in clean:
            start = clean.index("{")
            end = clean.rindex("}") + 1
            clean = clean[start:end]

        result = json.loads(clean)
        category = result.get("category", "shallow").lower()
        category = CATEGORY_MAP.get(category, "shallow")
        confidence = int(result.get("confidence", 70))
        reason = result.get("reason", "")

        return {
            "category": category,
            "confidence": confidence,
            "reason": reason,
            "source": f"ollama:{model}",
        }

    except Exception:
        return None


def classify_batch(events: list) -> list:
    """Classify multiple events using local Ollama model."""
    return [classify_event(e) for e in events]


def test_connection() -> tuple:
    """
    Test that Ollama is running and the configured model is available.
    Returns (success, message).
    """
    model = cfg.get("ollama_model") or "llama3.2:3b"

    if not _is_ollama_running():
        return False, (
            "Ollama is not running. Start it with:\n"
            "  ollama serve\n"
            "Or it starts automatically when you run: ollama run " + model
        )

    if not _model_is_available(model):
        return False, (
            f"Model '{model}' is not pulled. Download it with:\n"
            f"  ollama pull {model}"
        )

    # Test with a simple classification
    result = classify_event({
        "app": "Google Chrome",
        "domain": "github.com",
        "previous_app": "Terminal",
        "hour": 10,
    })

    if result:
        return True, (
            f"Connected. Model: {model}\n"
            f"Test: github.com → {result['category']} ({result['confidence']}% confidence)"
        )

    return False, f"Model {model} is available but classification failed. Try: ollama run {model}"


def get_available_models() -> list:
    """Return list of pulled models available for use."""
    if not _is_ollama_running():
        return []
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


def list_recommended_models() -> list:
    """Return recommended models with metadata."""
    return [
        {
            "name": "gemma2:2b",
            "size_gb": 1.6,
            "min_ram_gb": 4,
            "quality": "Good",
            "label": "Lightweight — best for older machines",
            "recommended_for": "4 GB RAM",
        },
        {
            "name": "llama3.2:3b",
            "size_gb": 2.0,
            "min_ram_gb": 8,
            "quality": "Great",
            "label": "Balanced — best for most machines",
            "recommended_for": "8 GB RAM",
        },
        {
            "name": "mistral:7b",
            "size_gb": 4.0,
            "min_ram_gb": 16,
            "quality": "Best",
            "label": "Full power — best for modern machines",
            "recommended_for": "16 GB+ RAM",
        },
    ]