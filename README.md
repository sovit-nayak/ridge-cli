# Ridge CLI

> Own your attention. Track your focus habits locally — no cloud, no extensions, no subscriptions.

![Version](https://img.shields.io/badge/version-1.0.0-f5a623?style=flat-square)
![Python](https://img.shields.io/badge/python-3.9+-blue?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey?style=flat-square)

---

## What is Ridge CLI?

Ridge CLI runs silently in your terminal, reads your browser history directly from disk, and builds a precise picture of your real focus habits. Every 30 seconds it logs what you're doing, categorizes it, and calculates a focus score — all stored locally in SQLite. Nothing leaves your machine.

```
ridge start "deep work"     # Start tracking
ridge status                # Live session stats
ridge report                # Today's full focus report
ridge week                  # 7-day summary
ridge sites                 # Top sites by category
ridge stop                  # End session
```

---

## Install

```bash
pip install ridge-cli
```

**Requirements**
- Python 3.9+
- macOS, Linux, or Windows
- Chrome, Firefox, or Safari

That's it. No database to install. No config files. No account.

---

## Quick Start

**1. Start a session**
```bash
ridge start "building new feature"
```

**2. Browse normally** — Ridge CLI tracks silently in the background

**3. Check your score anytime**
```bash
ridge status
```

**4. See the full report**
```bash
ridge report
```

**5. Stop when done**
```bash
ridge stop
```

---

## Commands

| Command | Description |
|---|---|
| `ridge start` | Start a focus session |
| `ridge start "task"` | Start with a task name |
| `ridge stop` | End the current session |
| `ridge status` | Live stats for current session |
| `ridge report` | Full focus report for today |
| `ridge week` | 7-day summary with trends |
| `ridge sites` | Top sites broken down by category |
| `ridge version` | Show version |

---

## How It Works

Ridge CLI reads browser history files directly from your local machine — no extension needed.

| Browser | Path |
|---|---|
| Chrome | `~/Library/Application Support/Google/Chrome/Default/History` |
| Firefox | `~/.mozilla/firefox/*.default/places.sqlite` |
| Safari | `~/Library/Safari/History.db` |

Every 30 seconds the daemon:
1. Reads new URLs from your browser history
2. Detects your active app via `psutil`
3. Categorizes each domain as **Deep Work**, **Shallow**, or **Escape**
4. Calculates a focus score (0–100)
5. Logs everything to `~/.ridge/data.db`

---

## Focus Score

Your score is calculated from three factors:

| Factor | Weight | Description |
|---|---|---|
| Deep work % | 70 pts | % of time on productive sites |
| Context switches | 20 pts | Fewer switches = higher score |
| Escape time | 10 pts | Less escape = higher score |

| Score | Label |
|---|---|
| 85–100 | Exceptional |
| 70–84 | Good |
| 55–69 | Average |
| 40–54 | Scattered |
| 0–39 | Distracted |

---

## Site Categories

Ridge CLI ships with 200+ pre-categorized domains:

**🟢 Deep Work** — github.com, notion.so, figma.com, stackoverflow.com, linear.app, docs.google.com, vercel.com, and more

**🟡 Shallow** — gmail.com, slack.com, zoom.us, calendar.google.com, linkedin.com, and more

**🔴 Escape** — youtube.com, reddit.com, twitter.com, instagram.com, netflix.com, tiktok.com, and more

Unknown sites are classified using keyword matching. Ridge CLI learns your patterns over time.

---

## Privacy

- ✅ All data stored in `~/.ridge/data.db` on your machine
- ✅ Zero network calls by default
- ✅ No telemetry, no analytics, no tracking
- ✅ Delete your data anytime: `rm -rf ~/.ridge`
- ✅ Fully open source — read every line

---

## macOS Permissions

On macOS, you need to grant Full Disk Access to Terminal (or VS Code) so Ridge CLI can read browser history:

1. **System Settings** → **Privacy & Security** → **Full Disk Access**
2. Click **+** and add **Terminal** (or your terminal app)
3. Toggle **ON**
4. Restart your terminal

---

## Data Storage

```
~/.ridge/
├── data.db          # All sessions and events (SQLite)
├── active_session   # Current session ID (deleted on stop)
└── .welcomed        # First-run marker
```

---

## Roadmap

| Version | Target | Features |
|---|---|---|
| **v1.0** | **May 2026 ✅** | **CLI tracking, focus score, daily/weekly reports** |
| v1.5 | Q3 2026 | Streamlit dashboard, HuggingFace ML insights, Prophet forecasting, AI coaching |
| v2.0 | Q4 2026 | Browser extension (Chrome + Firefox), syncs with CLI |
| v3.0 | Q2 2027 | Web SaaS, team dashboards, mobile PWA, accountability mode |

---

## Tech Stack

| Layer | Technology |
|---|---|
| CLI framework | [Typer](https://typer.tiangolo.com/) |
| Terminal UI | [Rich](https://rich.readthedocs.io/) |
| Browser history | `sqlite3` (stdlib) |
| App tracking | [psutil](https://psutil.readthedocs.io/) |
| Background daemon | `threading` |
| Storage | SQLite via `sqlite3` (stdlib) |
| Packaging | setuptools + PyPI |

---

## Project Structure

```
ridge/
├── ridge/
│   ├── __init__.py       # Version
│   ├── cli.py            # Typer commands
│   ├── daemon.py         # Background polling loop
│   ├── tracker.py        # Browser history + app reader
│   ├── categorizer.py    # Site classification
│   ├── scorer.py         # Focus score algorithm
│   ├── reporter.py       # Rich terminal output
│   ├── storage.py        # SQLite read/write
│   └── sites.py          # 200+ domain seed list
├── docs/
│   └── index.html        # Landing page
├── pyproject.toml
└── README.md
```

---

## Contributing

Contributions welcome. Please branch off `dev` and open a PR.

```bash
git clone https://github.com/sovit-nayak/ridge-cli.git
cd ridge-cli
pip install -e .
git checkout -b feature/your-feature dev
```

---

## License

MIT — free forever, open source forever.

---

<p align="center">Built by <a href="https://github.com/sovit-nayak">Sovit Nayak</a> · <a href="https://sovit-nayak.github.io/ridge-cli">Landing Page</a></p>