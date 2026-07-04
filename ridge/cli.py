import typer
import sys
import time
from pathlib import Path
from typing import Optional
from rich.console import Console
from ridge import __version__
from ridge.storage import (
    RIDGE_DIR, start_session, end_session,
    get_active_session_id, get_today_events,
    get_week_events, get_today_sessions, get_week_sessions,
)
from ridge.daemon import start_daemon_process, stop_daemon, is_daemon_running
from ridge.scorer import summarize_events, calculate_score
from ridge.reporter import (
    print_report, print_week_report, print_status,
    print_sites, print_first_run, print_welcome, console
)

app = typer.Typer(
    name="ridge",
    help="Ridge CLI — Own your attention. Track focus habits locally.",
    add_completion=False,
    rich_markup_mode="rich",
    no_args_is_help=False,
)

# ── FIRST RUN CHECK ───────────────────────────────────────────

def _check_first_run():
    marker = RIDGE_DIR / ".welcomed"
    if not marker.exists():
        RIDGE_DIR.mkdir(exist_ok=True)
        print_first_run()
        marker.touch()


# ── COMMANDS ─────────────────────────────────────────────────

@app.command()
def start(
    task: Optional[str] = typer.Argument(None, help="What are you working on?"),
):
    """Start a focus session. Ridge begins tracking silently."""
    _check_first_run()

    if is_daemon_running():
        console.print("[yellow]A session is already running.[/yellow] Use [bold]ridge stop[/bold] first.")
        raise typer.Exit(1)
    stop_file = RIDGE_DIR / "stop"
    if stop_file.exists():
        stop_file.unlink()

    task_name = task or ""
    session_id = start_session(task_name)
    task_name = task or ""
    session_id = start_session(task_name)

    console.print()
    console.print(f"  [bold green]⚡ Session started[/bold green]")
    if task_name:
        console.print(f"  [dim]Task[/dim]     [bold]{task_name}[/bold]")
    console.print(f"  [dim]Session[/dim]  #{session_id}")
    console.print(f"  [dim]Storage[/dim]  ~/.ridge/data.db")
    console.print(f"  [dim]Polling[/dim]  every 30 seconds")
    console.print()
    console.print("  [dim]Ridge CLI is now watching silently.[/dim]")
    console.print("  [dim]Run [bold]ridge status[/bold] to check in. [bold]ridge stop[/bold] to end.[/dim]")
    console.print()

    # Start daemon in background thread, keep process alive
    t = start_daemon_process(session_id)

    try:
        # Keep the process alive so the daemon thread keeps running
        while is_daemon_running() or t.is_alive():
            time.sleep(2)
    except KeyboardInterrupt:
        console.print("\n  [dim]Stopping session...[/dim]")
        _do_stop()


@app.command()
def stop():
    """Stop the current focus session and save results."""
    session_id = get_active_session_id()
    if not session_id:
        console.print("[dim]No active session found.[/dim]")
        raise typer.Exit(0)
    _do_stop()


def _do_stop():
    session_id = get_active_session_id()
    if not session_id:
        return

    stop_daemon()

    # Calculate final score from today's events
    events = get_today_events()
    score = calculate_score(list(events))
    end_session(session_id, score)

    console.print()
    console.print(f"  [bold]Session ended.[/bold]")
    console.print(f"  [dim]Final score:[/dim]  [bold]{score}/100[/bold]")
    console.print(f"  [dim]Run [bold]ridge report[/bold] to see the full breakdown.[/dim]")
    console.print()


@app.command()
def status():
    """Show live stats for the current session."""
    session_id = get_active_session_id()
    if not session_id:
        console.print("\n[dim]No active session. Run [bold]ridge start[/bold] to begin.[/dim]\n")
        raise typer.Exit(0)

    # Get task name from DB
    from ridge.storage import get_db
    conn = get_db()
    row = conn.execute("SELECT task FROM sessions WHERE id=?", (session_id,)).fetchone()
    conn.close()
    task = row["task"] if row else ""

    events = get_today_events()
    print_status(session_id, task, list(events))


@app.command()
def report():
    """Show today's full focus report."""
    events = get_today_events()
    print_report(list(events), period="Today")


@app.command()
def week():
    """Show a 7-day summary with trends."""
    sessions = get_week_sessions()
    events = get_week_events()
    print_week_report(list(sessions), list(events))


@app.command()
def sites(
    period: str = typer.Option("today", "--period", "-p", help="today or week"),
):
    """Show top sites broken down by category."""
    if period == "week":
        events = get_week_events()
        print_sites(list(events), period="This Week")
    else:
        events = get_today_events()
        print_sites(list(events), period="Today")

@app.command()
def dashboard():
    """Open the local Streamlit dashboard."""
    import subprocess
    import sys
    dashboard_path = Path(__file__).parent / "dashboard.py"
    console.print("\n  [bold green]🚀 Launching Ridge CLI Dashboard...[/bold green]")
    console.print("  [dim]Opening at http://localhost:8501[/dim]")
    console.print("  [dim]Press Ctrl+C to stop[/dim]\n")
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(dashboard_path)])

@app.command()
def version():
    """Show Ridge CLI version."""
    console.print(f"\n  [bold]Ridge CLI[/bold] v{__version__}\n")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Ridge CLI — Own your attention."""
    if ctx.invoked_subcommand is None:
        _check_first_run()
        print_welcome()
        console.print("  Run [bold]ridge help[/bold] to see all commands.\n")