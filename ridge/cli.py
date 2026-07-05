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


# ── ADD THESE COMMANDS TO ridge/cli.py ──────────────────────
# Paste each command into cli.py after the existing `sites` command

@app.command()
def insights():
    """Analyze your focus patterns using ML."""
    from ridge.ml.patterns import analyze_patterns

    console.print("\n  [bold]Running pattern analysis...[/bold]\n")
    result = analyze_patterns(days=60)

    if "error" in result:
        if result["error"] == "insufficient_data":
            console.print(f"  [yellow]Not enough data yet.[/yellow]")
            console.print(f"  [dim]Need {result['min_days']} days minimum. Keep using Ridge and check back.[/dim]\n")
        else:
            console.print(f"  [red]Error:[/red] {result.get('message', result['error'])}\n")
        return

    s = result["summary"]
    console.print(f"  [dim]Analyzed {s['days_analyzed']} days · {s['total_events']} events · avg score {s['avg_score']}/100[/dim]\n")
    console.rule("[bold]Patterns Detected[/bold]", style="dim")
    console.print()

    if not result["patterns"]:
        console.print("  [dim]No strong patterns detected yet. Check back after 2+ weeks of data.[/dim]\n")
        return

    severity_colors = {"high": "red", "medium": "yellow", "positive": "green"}

    for i, p in enumerate(result["patterns"], 1):
        color = severity_colors.get(p.get("severity", "medium"), "yellow")
        console.print(f"  [{color}]Pattern {i}[/{color}]  [bold]{p['title']}[/bold]")
        console.print(f"  [dim]{p['detail']}[/dim]")
        console.print(f"  [bold]Confidence:[/bold] {p['confidence']}%")
        if "recommendation" in p:
            console.print(f"  [green]→ {p['recommendation']}[/green]")
        console.print()

    console.rule(style="dim")
    console.print()


@app.command()
def forecast():
    """Predict your focus scores for the next 7 days."""
    from ridge.ml.forecaster import forecast_scores

    console.print("\n  [bold]Running forecast model...[/bold]\n")
    result = forecast_scores(periods=7)

    if "error" in result:
        if result["error"] == "insufficient_data":
            console.print(f"  [yellow]Not enough data yet.[/yellow]")
            console.print(f"  [dim]Have {result['days_available']} days, need {result['days_needed']}.[/dim]\n")
        elif result["error"] == "prophet_not_installed":
            console.print(f"  [yellow]Prophet not installed.[/yellow]")
            console.print(f"  [dim]Run: pip install prophet[/dim]\n")
        else:
            console.print(f"  [red]Error:[/red] {result.get('message', result['error'])}\n")
        return

    console.print(f"  [dim]Based on {result['days_of_data']} days of data · historical avg {result['avg_historical']}/100[/dim]")
    if result.get("accuracy"):
        console.print(f"  [dim]Model accuracy: {result['accuracy']}% on last 7 days[/dim]")
    console.print(f"  [dim]Trend: {result['trend']}[/dim]\n")
    console.rule("[bold]Next 7 Days Forecast[/bold]", style="dim")
    console.print()

    for p in result["predictions"]:
        score = p["score"]
        bar_filled = round(score / 5)
        color = "green" if score >= 70 else "yellow" if score >= 50 else "red"
        bar = f"[{color}]{'█' * bar_filled}[/{color}][dim]{'░' * (20 - bar_filled)}[/dim]"
        warning = "  [yellow]⚠[/yellow]" if p["warning"] else ""
        console.print(f"  [bold]{p['day']} {p['date']}[/bold]  {bar}  [{color}]{score}[/{color}]  [dim]{p['label']}[/dim]{warning}")

    console.print()
    console.rule(style="dim")
    console.print()


@app.command()
def anomaly():
    """Detect unusual days in your focus history."""
    from ridge.ml.anomaly import detect_anomalies

    console.print("\n  [bold]Running anomaly detection...[/bold]\n")
    result = detect_anomalies()

    if "error" in result:
        if result["error"] == "insufficient_data":
            console.print(f"  [yellow]Not enough data yet.[/yellow]")
            console.print(f"  [dim]Have {result['days_available']} days, need {result['days_needed']}.[/dim]\n")
        else:
            console.print(f"  [red]Error:[/red] {result.get('message', result['error'])}\n")
        return

    console.print(f"  [dim]Analyzed {result['days_analyzed']} days · avg score {result['avg_score']}/100[/dim]")
    console.print(f"  [dim]Found {result['anomaly_count']} anomalies ({result['positive_count']} positive, {result['negative_count']} negative)[/dim]\n")
    console.rule("[bold]Anomalies Detected[/bold]", style="dim")
    console.print()

    if not result["anomalies"]:
        console.print("  [green]No anomalies detected.[/green] Your focus is remarkably consistent.\n")
        return

    for a in result["anomalies"]:
        color = "green" if a["type"] == "positive" else "red" if a["type"] == "negative" else "yellow"
        icon = "★" if a["type"] == "positive" else "⚠" if a["type"] == "negative" else "?"
        console.print(f"  [{color}]{icon}[/{color}]  [bold]{a['date']}[/bold]  [{color}]{a['title']}[/{color}]")
        console.print(f"  [dim]{a['detail']}[/dim]")
        console.print()

    console.rule(style="dim")
    console.print()


@app.command()
def coach():
    """Generate an AI weekly coaching letter based on your data."""
    from ridge.ml.coach import generate_coaching_letter

    console.print("\n  [bold]Generating coaching letter...[/bold]\n")
    result = generate_coaching_letter(days=7)

    if "error" in result:
        if result["error"] == "no_api_key":
            console.print(f"  [yellow]Anthropic API key required for AI coaching.[/yellow]\n")
            console.print(f"  [dim]{result['message']}[/dim]\n")
        elif result["error"] == "insufficient_data":
            console.print(f"  [yellow]{result['message']}[/yellow]\n")
        else:
            console.print(f"  [red]Error:[/red] {result.get('message', result['error'])}\n")
        return

    console.print(f"  [dim]Week avg: {result['week_avg']}/100 · {result['days_analyzed']} days analyzed[/dim]\n")
    console.rule("[bold]Weekly Coaching Letter[/bold]", style="dim")
    console.print()
    console.print(f"  {result['letter']}")
    console.print()
    console.rule(style="dim")
    console.print()


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

@app.command()
def setup(
    force: bool = typer.Option(False, "--force", help="Re-run setup even if already configured")
):
    """Run the setup wizard to configure Ridge CLI."""
    from ridge.setup import run_setup
    run_setup(force=force)


@app.command()
def config(
    action: str = typer.Argument("show", help="show | set | reset"),
    key: Optional[str] = typer.Argument(None, help="Config key to set"),
    value: Optional[str] = typer.Argument(None, help="Value to set"),
):
    """View or update Ridge CLI configuration."""
    from ridge import config as cfg

    if action == "show":
        settings = cfg.show()
        console.print()
        console.rule("[bold]Ridge CLI Configuration[/bold]", style="dim")
        console.print()
        for k, v in settings.items():
            val_display = str(v) if v is not None else "[dim]not set[/dim]"
            console.print(f"  [dim]{k:<25}[/dim] [bold]{val_display}[/bold]")
        console.print()
        console.rule(style="dim")
        console.print()

    elif action == "set":
        if not key or not value:
            console.print("[red]Usage: ridge config set <key> <value>[/red]")
            raise typer.Exit(1)
        success, msg = cfg.set_value(key, value)
        if success:
            console.print(f"\n  [green]✓[/green] {msg}\n")
        else:
            console.print(f"\n  [red]✗[/red] {msg}\n")

    elif action == "reset":
        cfg.reset()
        console.print("\n  [green]✓ Configuration reset to defaults.[/green]\n")

    else:
        console.print(f"[red]Unknown action: {action}. Use show, set, or reset.[/red]")

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Ridge CLI — Own your attention."""
    if ctx.invoked_subcommand is None:
        _check_first_run()
        print_welcome()
        console.print("  Run [bold]ridge help[/bold] to see all commands.\n")