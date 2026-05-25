import sqlite3
import shutil
import tempfile
import platform
from pathlib import Path
from datetime import datetime, timezone
from ridge.categorizer import categorize_url

OS = platform.system()  # "Darwin", "Linux", "Windows"


# ── BROWSER HISTORY ──────────────────────────────────────────

def _chrome_paths() -> list[Path]:
    if OS == "Darwin":
        base = Path.home() / "Library/Application Support/Google/Chrome"
    elif OS == "Linux":
        base = Path.home() / ".config/google-chrome"
    elif OS == "Windows":
        base = Path.home() / "AppData/Local/Google/Chrome/User Data"
    else:
        return []
    paths = []
    for profile in ["Default", "Profile 1", "Profile 2", "Profile 3"]:
        p = base / profile / "History"
        if p.exists():
            paths.append(p)
    return paths


def _brave_paths() -> list[Path]:
    if OS == "Darwin":
        base = Path.home() / "Library/Application Support/BraveSoftware/Brave-Browser"
    elif OS == "Linux":
        base = Path.home() / ".config/BraveSoftware/Brave-Browser"
    elif OS == "Windows":
        base = Path.home() / "AppData/Local/BraveSoftware/Brave-Browser/User Data"
    else:
        return []
    paths = []
    for profile in ["Default", "Profile 1"]:
        p = base / profile / "History"
        if p.exists():
            paths.append(p)
    return paths


def _firefox_paths() -> list[Path]:
    if OS == "Darwin":
        base = Path.home() / "Library/Application Support/Firefox/Profiles"
    elif OS == "Linux":
        base = Path.home() / ".mozilla/firefox"
    elif OS == "Windows":
        base = Path.home() / "AppData/Roaming/Mozilla/Firefox/Profiles"
    else:
        return []
    if not base.exists():
        return []
    return list(base.glob("*.default*/places.sqlite"))


def _read_chromium_history(db_path: Path, since_ts: float) -> list[dict]:
    """Read Chrome/Brave history since a Unix timestamp in microseconds."""
    results = []
    try:
        # Copy to temp file — Chrome locks the DB while open
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp_path = tmp.name
        shutil.copy2(db_path, tmp_path)
        conn = sqlite3.connect(tmp_path)
        # Chrome stores time as microseconds since 1601-01-01
        # Convert our unix ts to Chrome ts
        chrome_epoch_offset = 11644473600  # seconds between 1601 and 1970
        chrome_ts = int((since_ts + chrome_epoch_offset) * 1_000_000)
        rows = conn.execute(
            "SELECT url, title, last_visit_time FROM urls WHERE last_visit_time > ? ORDER BY last_visit_time",
            (chrome_ts,)
        ).fetchall()
        conn.close()
        Path(tmp_path).unlink(missing_ok=True)
        for url, title, _ in rows:
            domain, category = categorize_url(url)
            results.append({"url": url, "domain": domain, "category": category})
    except Exception:
        pass
    return results


def _read_firefox_history(db_path: Path, since_ts: float) -> list[dict]:
    results = []
    try:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp_path = tmp.name
        shutil.copy2(db_path, tmp_path)
        conn = sqlite3.connect(tmp_path)
        # Firefox stores time as microseconds since Unix epoch
        ff_ts = int(since_ts * 1_000_000)
        rows = conn.execute(
            "SELECT url FROM moz_places WHERE last_visit_date > ? ORDER BY last_visit_date",
            (ff_ts,)
        ).fetchall()
        conn.close()
        Path(tmp_path).unlink(missing_ok=True)
        for (url,) in rows:
            domain, category = categorize_url(url)
            results.append({"url": url, "domain": domain, "category": category})
    except Exception:
        pass
    return results


def get_recent_urls(since_seconds: int = 35) -> list[dict]:
    """Return URLs visited in the last N seconds across all browsers."""
    since_ts = datetime.now(timezone.utc).timestamp() - since_seconds
    urls = []
    for path in _chrome_paths() + _brave_paths():
        urls.extend(_read_chromium_history(path, since_ts))
    for path in _firefox_paths():
        urls.extend(_read_firefox_history(path, since_ts))
    return urls


# ── ACTIVE APP ───────────────────────────────────────────────

def get_active_app() -> str:
    """Return the name of the currently focused application."""
    try:
        import psutil
        if OS == "Darwin":
            import subprocess
            result = subprocess.run(
                ["osascript", "-e",
                 'tell application "System Events" to get name of first application process whose frontmost is true'],
                capture_output=True, text=True, timeout=2
            )
            return result.stdout.strip() or "Unknown"
        elif OS == "Linux":
            import subprocess
            result = subprocess.run(
                ["xdotool", "getactivewindow", "getwindowname"],
                capture_output=True, text=True, timeout=2
            )
            return result.stdout.strip() or "Unknown"
        elif OS == "Windows":
            import ctypes
            hwnd = ctypes.windll.user32.GetForegroundWindow()
            length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
            return buf.value or "Unknown"
    except Exception:
        pass
    return "Unknown"