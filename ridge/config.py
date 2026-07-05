"""
Ridge CLI — Configuration Management
Reads and writes ~/.ridge/config.json
"""

import json
from pathlib import Path
from typing import Optional

RIDGE_DIR = Path.home() / ".ridge"
CONFIG_PATH = RIDGE_DIR / "config.json"

DEFAULTS = {
    "ai_provider": "rules",        # "ollama" | "gemini" | "rules"
    "ollama_model": "llama3.2:3b", # default model
    "gemini_api_key": None,
    "anthropic_api_key": None,
    "data_retention_days": 90,
    "timezone": "auto",
    "setup_complete": False,
}

VALID_PROVIDERS = ["ollama", "gemini", "rules"]
VALID_MODELS = ["gemma2:2b", "llama3.2:3b", "mistral:7b"]


def load() -> dict:
    """Load config from disk, merging with defaults."""
    RIDGE_DIR.mkdir(exist_ok=True)
    if not CONFIG_PATH.exists():
        save(DEFAULTS.copy())
        return DEFAULTS.copy()
    try:
        with open(CONFIG_PATH) as f:
            stored = json.load(f)
        # Merge with defaults so new keys always exist
        merged = {**DEFAULTS, **stored}
        return merged
    except Exception:
        return DEFAULTS.copy()


def save(config: dict):
    """Write config to disk."""
    RIDGE_DIR.mkdir(exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def get(key: str):
    """Get a single config value."""
    return load().get(key, DEFAULTS.get(key))


def set_value(key: str, value: str) -> tuple[bool, str]:
    """
    Set a config value with validation.
    Returns (success, message).
    """
    config = load()

    # Validate known keys
    if key == "ai_provider":
        if value not in VALID_PROVIDERS:
            return False, f"Invalid provider '{value}'. Choose from: {', '.join(VALID_PROVIDERS)}"
        config["ai_provider"] = value

    elif key == "ollama_model":
        if value not in VALID_MODELS:
            return False, f"Invalid model '{value}'. Choose from: {', '.join(VALID_MODELS)}"
        config["ollama_model"] = value

    elif key == "gemini_api_key":
        config["gemini_api_key"] = value
        if config["ai_provider"] == "rules":
            config["ai_provider"] = "gemini"

    elif key == "anthropic_api_key":
        config["anthropic_api_key"] = value

    elif key == "data_retention_days":
        try:
            days = int(value)
            if days < 7 or days > 365:
                return False, "Retention must be between 7 and 365 days."
            config["data_retention_days"] = days
        except ValueError:
            return False, f"Invalid number: {value}"

    elif key == "timezone":
        config["timezone"] = value

    else:
        return False, f"Unknown config key: '{key}'. Run 'ridge config show' to see valid keys."

    save(config)
    return True, f"Set {key} = {value}"


def reset():
    """Reset config to defaults."""
    save(DEFAULTS.copy())


def show() -> dict:
    """Return current config for display."""
    config = load()
    # Mask API keys
    display = config.copy()
    for key in ["gemini_api_key", "anthropic_api_key"]:
        if display.get(key):
            display[key] = display[key][:8] + "..." + display[key][-4:]
    return display


def is_setup_complete() -> bool:
    return get("setup_complete") is True


def mark_setup_complete():
    config = load()
    config["setup_complete"] = True
    save(config)