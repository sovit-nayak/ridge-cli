import time
import threading
from pathlib import Path
from ridge.storage import RIDGE_DIR, get_active_session_id, log_event
from ridge.tracker import get_active_app

POLL_INTERVAL = 30  # seconds
DAEMON_PID_FILE = RIDGE_DIR / "daemon.pid"
_stop_event = threading.Event()


def _poll(session_id: int, last_poll_ts: list):
    """Single poll — reads URLs visited since last poll timestamp."""
    from ridge.tracker import get_urls_since

    app = get_active_app()
    since = last_poll_ts[0]
    urls = get_urls_since(since_ts=since)

    # Update last poll time to now
    last_poll_ts[0] = time.time()

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

    # Look back 5 minutes from session start to catch recent browsing
    last_poll_ts = [time.time() - 300]

    while not _stop_event.is_set():
        if stop_file.exists():
            stop_file.unlink(missing_ok=True)
            break
        if not get_active_session_id():
            break
        try:
            _poll(session_id, last_poll_ts)
        except Exception:
            pass  # Never crash the daemon
        _stop_event.wait(timeout=POLL_INTERVAL)

    if DAEMON_PID_FILE.exists():
        DAEMON_PID_FILE.unlink(missing_ok=True)


def start_daemon_process(session_id: int):
    """Launch daemon in a background thread."""
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