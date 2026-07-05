"""
Ridge CLI — AI Router
Routes classification requests to the right engine based on:
1. User config (ollama / gemini / rules)
2. Model confidence threshold
3. Availability (Ollama running? Gemini key set?)

Routing priority:
  Ollama (local, free, private) → highest priority if configured
  Gemini (cloud, free tier, BYOK) → fallback if Ollama unavailable
  Rules (always works) → final fallback
"""

import subprocess
from typing import Optional
from ridge import config as cfg


CONFIDENCE_THRESHOLD = 0.75  # local model must exceed this to skip Gemini


def _ollama_available() -> bool:
    """Check if Ollama is running and responsive."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True, text=True, timeout=3
        )
        return result.returncode == 0
    except Exception:
        return False


def _model_is_pulled(model_name: str) -> bool:
    """Check if the configured Ollama model is downloaded."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True, text=True, timeout=3
        )
        return model_name in result.stdout
    except Exception:
        return False


def _classify_with_ollama(event: dict) -> Optional[dict]:
    """Classify event using local Ollama model."""
    try:
        from ridge.ml.ollama import classify_event, _is_ollama_running, _model_is_available
        model = cfg.get("ollama_model") or "llama3.2:3b"
        if not _is_ollama_running():
            return None
        if not _model_is_available(model):
            return None
        return classify_event(event)
    except Exception:
        return None


def _classify_with_gemini(event: dict) -> Optional[dict]:
    """Classify event using Gemini API."""
    try:
        from ridge.ml.gemini import classify_event
        return classify_event(event)
    except Exception:
        return None


def _classify_with_rules(event: dict) -> dict:
    """
    Rule-based classification — always works, no dependencies.
    Uses domain lookup and app name heuristics.
    """
    domain = (event.get("domain") or "").lower()
    app = (event.get("app") or "").lower()

    # Import site lookup
    try:
        from ridge.sites import lookup
        if domain:
            category = lookup(domain)
            return {
                "category": category,
                "confidence": 70,
                "reason": f"Rule-based: {domain} matches known category",
                "source": "rules",
            }
    except Exception:
        pass

    # App-based fallback
    deep_apps = ["code", "visual studio code", "pycharm", "cursor", "xcode",
                 "terminal", "iterm2", "vim", "neovim", "emacs",
                 "tableau", "excel", "jupyter", "rstudio"]
    escape_apps = ["youtube", "netflix", "spotify", "reddit", "twitter",
                   "instagram", "tiktok", "twitch", "discord"]
    shallow_apps = ["slack", "outlook", "teams", "mail", "messages",
                    "zoom", "calendar", "notion", "jira"]

    for a in deep_apps:
        if a in app:
            return {"category": "deep", "confidence": 65, "reason": f"App '{app}' is a deep work tool", "source": "rules"}
    for a in escape_apps:
        if a in app:
            return {"category": "escape", "confidence": 65, "reason": f"App '{app}' is an escape/entertainment app", "source": "rules"}
    for a in shallow_apps:
        if a in app:
            return {"category": "shallow", "confidence": 65, "reason": f"App '{app}' is a communication tool", "source": "rules"}

    return {
        "category": "shallow",
        "confidence": 40,
        "reason": "Unknown app/domain — defaulting to shallow",
        "source": "rules",
    }


def classify(event: dict) -> dict:
    """
    Main routing function — picks the right classifier and returns result.
    Always returns a valid classification dict.
    """
    provider = cfg.get("ai_provider") or "rules"
    model = cfg.get("ollama_model") or "llama3.2:3b"

    # ── Try Ollama first (if configured) ──
    if provider == "ollama":
        if _ollama_available() and _model_is_pulled(model):
            result = _classify_with_ollama(event)
            if result and result.get("confidence", 0) >= (CONFIDENCE_THRESHOLD * 100):
                result["source"] = f"ollama:{model}"
                return result
            # Low confidence — fall through to Gemini

    # ── Try Gemini (if configured) ──
    if provider == "gemini" or (provider == "ollama" and cfg.get("gemini_api_key")):
        gemini_result = _classify_with_gemini(event)
        if gemini_result and "error" not in gemini_result:
            return gemini_result

    # ── Always fall back to rules ──
    return _classify_with_rules(event)


def classify_batch(events: list) -> list[dict]:
    """Classify a list of events using the router."""
    return [classify(e) for e in events]


def get_active_provider() -> str:
    """Return a human-readable description of the active provider."""
    provider = cfg.get("ai_provider") or "rules"
    model = cfg.get("ollama_model") or "llama3.2:3b"

    if provider == "ollama":
        if _ollama_available() and _model_is_pulled(model):
            return f"Ollama ({model})"
        return "Rules (Ollama configured but not running)"
    elif provider == "gemini":
        if cfg.get("gemini_api_key"):
            return "Gemini Flash (free tier)"
        return "Rules (Gemini key not set)"
    return "Rules (no AI configured)"