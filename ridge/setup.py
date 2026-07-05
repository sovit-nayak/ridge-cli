"""
Ridge CLI — Setup Wizard
Guides users through first-run configuration:
- AI provider selection (Ollama / Gemini / Rules)
- Ollama model selection based on available RAM
- API key configuration
"""

import subprocess
import sys
import psutil
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich import box
from rich.table import Table
from ridge import config as cfg

console = Console()

MODELS = [
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
        "recommended_for": "16 GB RAM",
    },
]


def get_available_ram_gb() -> float:
    """Return available RAM in GB."""
    return psutil.virtual_memory().total / (1024 ** 3)


def recommend_model(ram_gb: float) -> dict:
    """Return the best model for the available RAM."""
    if ram_gb >= 16:
        return MODELS[2]
    elif ram_gb >= 8:
        return MODELS[1]
    else:
        return MODELS[0]


def is_ollama_installed() -> bool:
    """Check if Ollama is installed."""
    try:
        result = subprocess.run(
            ["ollama", "--version"],
            capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def is_model_pulled(model_name: str) -> bool:
    """Check if an Ollama model is already downloaded."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True, text=True, timeout=5
        )
        return model_name in result.stdout
    except Exception:
        return False


def pull_model(model_name: str) -> bool:
    """Pull an Ollama model, showing progress."""
    console.print(f"\n  [dim]Pulling {model_name}...[/dim]")
    try:
        result = subprocess.run(
            ["ollama", "pull", model_name],
            timeout=600  # 10 min max
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        console.print("  [red]Download timed out. Try again with a faster connection.[/red]")
        return False
    except Exception as e:
        console.print(f"  [red]Failed to pull model: {e}[/red]")
        return False


def run_setup(force: bool = False):
    """
    Run the full setup wizard.
    If force=False, skips if setup already complete.
    """
    if not force and cfg.is_setup_complete():
        return

    console.print()
    console.print(Panel.fit(
        "[bold yellow]ridge.[/bold yellow] [bold]Setup Wizard[/bold]\n"
        "[dim]Let's configure your AI focus assistant.[/dim]",
        border_style="dim",
        padding=(1, 3),
    ))
    console.print()

    # ── STEP 1: Choose AI Provider ──────────────────────────
    console.print("  [bold]Step 1 of 3 — Choose your AI provider[/bold]\n")
    console.print("  [dim]How Ridge classifies your focus patterns:[/dim]\n")

    provider_table = Table(box=box.SIMPLE, show_header=True, header_style="bold dim")
    provider_table.add_column("#", width=3)
    provider_table.add_column("Option", min_width=22)
    provider_table.add_column("Cost", width=10)
    provider_table.add_column("Privacy", width=14)
    provider_table.add_column("Description")

    provider_table.add_row("1", "[bold]Local AI (Ollama)[/bold]", "Free", "100% local",
                           "Runs on your machine, no internet needed — [green]recommended[/green]")
    provider_table.add_row("2", "Gemini API", "Free tier", "Google sees data",
                           "Uses your own Google API key")
    provider_table.add_row("3", "Rules only", "Free", "100% local",
                           "No AI — pattern matching only")

    console.print(provider_table)
    console.print()

    choice = Prompt.ask(
        "  Select provider",
        choices=["1", "2", "3"],
        default="1"
    )

    provider_map = {"1": "ollama", "2": "gemini", "3": "rules"}
    provider = provider_map[choice]

    # ── STEP 2: Provider-specific config ────────────────────
    console.print()

    if provider == "ollama":
        console.print("  [bold]Step 2 of 3 — Select your Ollama model[/bold]\n")

        ram_gb = get_available_ram_gb()
        recommended = recommend_model(ram_gb)
        console.print(f"  [dim]Detected RAM: {round(ram_gb)}GB · Recommended: {recommended['name']}[/dim]\n")

        model_table = Table(box=box.SIMPLE, show_header=True, header_style="bold dim")
        model_table.add_column("#", width=3)
        model_table.add_column("Model", width=16)
        model_table.add_column("Size", width=8)
        model_table.add_column("Quality", width=10)
        model_table.add_column("Min RAM", width=10)
        model_table.add_column("Description")

        for i, m in enumerate(MODELS, 1):
            is_rec = m["name"] == recommended["name"]
            rec_tag = " [green]← recommended[/green]" if is_rec else ""
            model_table.add_row(
                str(i),
                f"[bold]{m['name']}[/bold]" if is_rec else m["name"],
                f"{m['size_gb']}GB",
                m["quality"],
                m["recommended_for"],
                m["label"] + rec_tag
            )

        console.print(model_table)
        console.print()

        default_choice = str(MODELS.index(recommended) + 1)
        model_choice = Prompt.ask(
            "  Select model",
            choices=["1", "2", "3"],
            default=default_choice
        )
        selected_model = MODELS[int(model_choice) - 1]

        # Check Ollama installation
        if not is_ollama_installed():
            console.print()
            console.print("  [yellow]Ollama is not installed.[/yellow]")
            console.print("  [dim]Install it first:[/dim]")
            console.print("  [bold]brew install ollama[/bold]  [dim](macOS)[/dim]")
            console.print("  [bold]curl https://ollama.ai/install.sh | sh[/bold]  [dim](Linux)[/dim]")
            console.print()
            install_later = Confirm.ask("  Continue with Rules only for now?", default=True)
            if install_later:
                provider = "rules"
                cfg.set_value("ai_provider", "rules")
                console.print("  [dim]You can switch to Ollama later with: ridge config set ai_provider ollama[/dim]")
            else:
                console.print("  [dim]Run ridge setup again after installing Ollama.[/dim]")
                return
        else:
            cfg.set_value("ollama_model", selected_model["name"])
            cfg.set_value("ai_provider", "ollama")

            # Pull model if not already downloaded
            if not is_model_pulled(selected_model["name"]):
                console.print()
                console.print(f"  [dim]Model {selected_model['name']} not found locally.[/dim]")
                do_pull = Confirm.ask(
                    f"  Download {selected_model['name']} ({selected_model['size_gb']}GB) now?",
                    default=True
                )
                if do_pull:
                    success = pull_model(selected_model["name"])
                    if success:
                        console.print(f"  [green]✓ {selected_model['name']} ready[/green]")
                    else:
                        console.print("  [yellow]Download failed. Falling back to rules.[/yellow]")
                        cfg.set_value("ai_provider", "rules")
                else:
                    console.print(f"  [dim]Run later: ollama pull {selected_model['name']}[/dim]")
            else:
                console.print(f"  [green]✓ {selected_model['name']} already installed[/green]")

    elif provider == "gemini":
        console.print("  [bold]Step 2 of 3 — Configure Gemini API[/bold]\n")
        console.print("  [dim]Get a free API key at: console.cloud.google.com[/dim]")
        console.print("  [dim]Free tier: 1M tokens/day, 15 requests/minute[/dim]\n")

        api_key = Prompt.ask("  Paste your Gemini API key", password=True)
        if api_key:
            cfg.set_value("gemini_api_key", api_key)
            cfg.set_value("ai_provider", "gemini")
            console.print("  [green]✓ Gemini API key saved[/green]")
        else:
            console.print("  [yellow]No key provided. Using rules only.[/yellow]")
            provider = "rules"
            cfg.set_value("ai_provider", "rules")

    else:
        console.print("  [dim]Step 2 of 3 — Skipped (rules only)[/dim]")
        cfg.set_value("ai_provider", "rules")

    # ── STEP 3: Optional Anthropic key for coaching ─────────
    console.print()
    console.print("  [bold]Step 3 of 3 — AI Coaching (optional)[/bold]\n")
    console.print("  [dim]ridge coach uses Claude to write your weekly letter.[/dim]")
    console.print("  [dim]Requires an Anthropic API key. Skip to set up later.[/dim]\n")

    add_anthropic = Confirm.ask("  Add Anthropic API key now?", default=False)
    if add_anthropic:
        key = Prompt.ask("  Paste your Anthropic API key", password=True)
        if key:
            cfg.set_value("anthropic_api_key", key)
            console.print("  [green]✓ Anthropic key saved[/green]")

    # ── DONE ────────────────────────────────────────────────
    cfg.mark_setup_complete()
    console.print()

    final_config = cfg.show()
    console.print(Panel(
        f"[bold green]Ridge CLI is configured.[/bold green]\n\n"
        f"  [dim]AI Provider[/dim]   [bold]{final_config['ai_provider']}[/bold]\n"
        f"  [dim]Model[/dim]         [bold]{final_config.get('ollama_model', 'N/A')}[/bold]\n"
        f"  [dim]Coaching[/dim]      [bold]{'enabled' if final_config.get('anthropic_api_key') else 'not configured'}[/bold]\n\n"
        f"  [dim]Change anytime:[/dim] [bold]ridge config set <key> <value>[/bold]",
        border_style="green",
        padding=(1, 3),
    ))
    console.print()
    console.print("  [bold]Get started:[/bold]")
    console.print("  [yellow]ridge start \"deep work\"[/yellow]")
    console.print()