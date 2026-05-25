import time
import threading
import sys
from pathlib import Path
from ridge.storage import RIDGE_DIR, get_active_session_id, log_event
from ridge.tracker import get_active_app

POLL_INTERVAL = 30  # seconds
DAEMON_PID_FILE = RIDGE_DIR / "daemon.pid"
_stop_event = threading.Event()


def _poll(session_id: int):
    """Single poll — called every POLL_INTERVAL seconds."""
    app = get_active_app()
    urls = get_recent_urls(since_seconds=POLL_INTERVAL + 5)

    if urls:
        for entry in urls:
            log_event(
                session_id=session_id,
                event_type="url",
                app=app,
                url=entry["url"],
                domain=entry["domain"],
                category=entry["category"],
            )
    else:
        # Log app activity even with no new URLs
        log_event(
            session_id=session_id,
            event_type="app",
            app=app,
        )


def run_daemon(session_id: int):
    """Main daemon loop — runs until stop file appears or session ends."""
    RIDGE_DIR.mkdir(exist_ok=True)
    DAEMON_PID_FILE.write_text(str(session_id))

    stop_file = RIDGE_DIR / "stop"

    # NOTE: signal handlers must be set in main thread only
    # Daemon uses stop file and stop event for clean shutdown

    import time
    # Start from session start — captures any browsing from last 5 minutes
    last_poll_ts = [time.time() - 300]

    while not _stop_event.is_set():
        if stop_file.exists():
            stop_file.unlink(missing_ok=True)
            break
        if not get_active_session_id():
            break
        try:
            _poll(session_id, last_poll_ts)
        except Exception as e:
            pass  # Never crash the daemon
        _stop_event.wait(timeout=POLL_INTERVAL)

    if DAEMON_PID_FILE.exists():
        DAEMON_PID_FILE.unlink(missing_ok=True)


def start_daemon_process(session_id: int):
    """Launch daemon in a background thread (foreground process stays alive)."""
    t = threading.Thread(target=run_daemon, args=(session_id,), daemon=True)
    t.start()
    return t


def stop_daemon():
    """Signal the daemon to stop by writing a stop file."""
    stop_file = RIDGE_DIR / "stop"
    stop_file.touch()
    if DAEMON_PID_FILE.exists():
        DAEMON_PID_FILE.unlink(missing_ok=True)


def is_daemon_running() -> bool:
    return DAEMON_PID_FILE.exists() and get_active_session_id() is not None