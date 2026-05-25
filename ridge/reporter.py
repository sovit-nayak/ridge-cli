from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule
from rich import box
from ridge.scorer import summarize_events, score_label
from ridge.categorizer import CATEGORY_COLOR
from ridge.sites import DEEP, SHALLOW, ESCAPE

console = Console()


def print_welcome():
    console.print()
    console.print(Panel.fit(
        "[bold yellow]Ridge CLI[/bold yellow] [dim]v0.1.0[/dim]\n"
        "[dim]Own your attention. Track your focus locally.[/dim]",
        border_style="dim",
        padding=(1, 3),
    ))
    console.print()


def print_report(events: list, period: str = "Today"):
    if not events:
        console.print(f"\n[dim]No data for {period.lower()} yet. Run [bold]ridge start[/bold] to begin tracking.[/dim]\n")
        return

    s = summarize_events(events)
    score = s["score"]
    label, color = score_label(score)

    console.print()
    console.rule(f"[bold]{period}'s Focus Report[/bold]  ·  {datetime.now().strftime('%A, %b %d')}", style="dim")
    console.print()

    # Score banner
    score_text = Text()
    score_text.append(f"  {score}", style=f"bold {color}")
    score_text.append("/100  ", style=f"bold {color}")
    score_text.append(f"{label}", style=f"{color}")
    console.print(score_text)
    console.print()

    # Category bars
    total = max(s["total_count"], 1)
    bar_width = 28

    def make_bar(count, color):
        filled = round((count / total) * bar_width)
        return f"[{color}]{'█' * filled}[/{color}][dim]{'░' * (bar_width - filled)}[/dim]"

    console.print(f"  [green]🟢 Deep Work[/green]   {make_bar(s['deep_count'], 'green')}  [bold]{s['deep_time']}[/bold]")
    console.print(f"  [yellow]🟡 Shallow[/yellow]     {make_bar(s['shallow_count'], 'yellow')}  [bold]{s['shallow_time']}[/bold]")
    console.print(f"  [red]🔴 Escape[/red]      {make_bar(s['escape_count'], 'red')}  [bold]{s['escape_time']}[/bold]")
    console.print()

    # Stats row
    console.print(f"  [dim]Context switches:[/dim]  [bold]{s['context_switches']}[/bold]")
    console.print()

    # Top sites table
    if s["top_domains"]:
        from ridge.categorizer import categorize_domain
        table = Table(
            show_header=True, header_style="bold dim",
            box=box.SIMPLE, padding=(0, 1),
            title="Top Sites", title_style="dim"
        )
        table.add_column("#", style="dim", width=3)
        table.add_column("Domain", min_width=24)
        table.add_column("Visits", justify="right", width=7)
        table.add_column("Category", width=14)

        for i, (domain, count) in enumerate(s["top_domains"], 1):
            cat = categorize_domain(domain)
            color = CATEGORY_COLOR.get(cat, "white")
            cat_label = {"deep": "🟢 Deep", "shallow": "🟡 Shallow", "escape": "🔴 Escape"}.get(cat, cat)
            table.add_row(str(i), domain, str(count), f"[{color}]{cat_label}[/{color}]")

        console.print(table)

    console.print()
    console.rule(style="dim")
    console.print()


def print_week_report(sessions: list, events: list):
    if not events:
        console.print("\n[dim]No data this week. Run [bold]ridge start[/bold] to begin tracking.[/dim]\n")
        return

    from collections import defaultdict
    from ridge.sites import DEEP, SHALLOW, ESCAPE

    # Group events by day
    by_day: dict[str, list] = defaultdict(list)
    for e in events:
        day = e["ts"][:10]
        by_day[day].append(e)

    console.print()
    console.rule("[bold]Weekly Summary[/bold]", style="dim")
    console.print()

    table = Table(show_header=True, header_style="bold dim", box=box.SIMPLE, padding=(0, 2))
    table.add_column("Day", min_width=12)
    table.add_column("Score", justify="center", width=8)
    table.add_column("Deep", justify="right", width=8)
    table.add_column("Escape", justify="right", width=8)
    table.add_column("Switches", justify="right", width=10)
    table.add_column("", width=20)

    scores = []
    for day_str, day_events in sorted(by_day.items()):
        s = summarize_events(day_events)
        score = s["score"]
        scores.append(score)
        label, color = score_label(score)
        day_fmt = datetime.strptime(day_str, "%Y-%m-%d").strftime("%a %b %d")
        bar_filled = round(score / 5)
        bar = f"[{color}]{'█' * bar_filled}[/{color}][dim]{'░' * (20 - bar_filled)}[/dim]"
        table.add_row(
            day_fmt,
            f"[bold {color}]{score}[/bold {color}]",
            s["deep_time"],
            s["escape_time"],
            str(s["context_switches"]),
            bar,
        )

    console.print(table)

    if scores:
        avg = round(sum(scores) / len(scores))
        label, color = score_label(avg)
        console.print(f"\n  [dim]Weekly average:[/dim]  [bold {color}]{avg}/100  {label}[/bold {color}]")

    console.print()
    console.rule(style="dim")
    console.print()


def print_status(session_id: int, task: str, events: list):
    s = summarize_events(events) if events else {}
    score = s.get("score", 0)
    label, color = score_label(score)

    console.print()
    console.rule("[bold]Current Session[/bold]", style="dim")
    console.print(f"\n  [dim]Task[/dim]      [bold]{task or 'No task set'}[/bold]")
    console.print(f"  [dim]Score[/dim]     [bold {color}]{score}/100  {label}[/bold {color}]")
    if s:
        console.print(f"  [dim]Deep[/dim]      [green]{s.get('deep_time','0h 00m')}[/green]")
        console.print(f"  [dim]Escape[/dim]    [red]{s.get('escape_time','0h 00m')}[/red]")
        console.print(f"  [dim]Switches[/dim]  {s.get('context_switches', 0)}")
    console.print()
    console.rule(style="dim")
    console.print()


def print_sites(events: list, period: str = "Today"):
    from collections import defaultdict
    from ridge.categorizer import categorize_domain, CATEGORY_COLOR

    if not events:
        console.print(f"\n[dim]No site data for {period.lower()} yet.[/dim]\n")
        return

    domain_counts: dict[str, int] = defaultdict(int)
    for e in events:
        if e["domain"]:
            domain_counts[e["domain"]] += 1

    console.print()
    console.rule(f"[bold]Top Sites — {period}[/bold]", style="dim")
    console.print()

    table = Table(show_header=True, header_style="bold dim", box=box.SIMPLE, padding=(0, 2))
    table.add_column("#", width=4, style="dim")
    table.add_column("Domain", min_width=28)
    table.add_column("Visits", justify="right", width=8)
    table.add_column("Category", width=16)

    for i, (domain, count) in enumerate(sorted(domain_counts.items(), key=lambda x: -x[1])[:20], 1):
        cat = categorize_domain(domain)
        color = CATEGORY_COLOR.get(cat, "white")
        cat_label = {"deep": "🟢 Deep Work", "shallow": "🟡 Shallow", "escape": "🔴 Escape"}.get(cat, cat)
        table.add_row(str(i), domain, str(count), f"[{color}]{cat_label}[/{color}]")

    console.print(table)
    console.print()


def print_first_run():
    console.print()
    console.print(Panel(
        "[bold yellow]Welcome to Ridge CLI![/bold yellow] 👋\n\n"
        "Your focus tracking tool is ready.\n\n"
        "[dim]Data stored at:[/dim] [bold]~/.ridge/data.db[/bold]\n"
        "[dim]Zero cloud. Zero telemetry. Fully yours.[/dim]\n\n"
        "Get started:\n"
        "  [bold]ridge start[/bold]          Start a focus session\n"
        "  [bold]ridge start \"task\"[/bold]   Start with a task name\n"
        "  [bold]ridge report[/bold]         See today's report\n"
        "  [bold]ridge help[/bold]           All commands",
        title="[bold]Ridge CLI[/bold]",
        border_style="yellow",
        padding=(1, 3),
    ))
    console.print()