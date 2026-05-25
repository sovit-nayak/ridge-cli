from ridge.sites import DEEP, SHALLOW, ESCAPE


def calculate_score(events: list) -> int:
    """
    Focus score 0-100 based on:
    - 70 pts: deep work % of total browsing time
    - 20 pts: context switch penalty
    - 10 pts: escape site penalty
    """
    if not events:
        return 0

    category_counts = {DEEP: 0, SHALLOW: 0, ESCAPE: 0}
    context_switches = 0
    prev_app = None

    for e in events:
        cat = e["category"] if e["category"] else SHALLOW
        if cat in category_counts:
            category_counts[cat] += 1

        app = e["app"]
        if app and app != prev_app and prev_app is not None:
            context_switches += 1
        if app:
            prev_app = app

    total = sum(category_counts.values())
    if total == 0:
        return 0

    # Deep work component (0-70)
    deep_pct = category_counts[DEEP] / total
    deep_score = deep_pct * 70

    # Context switch penalty (0-20)
    # 0 switches = 20 pts, 30+ switches = 0 pts
    switch_score = max(0, 20 - (context_switches * 0.67))

    # Escape penalty (0-10)
    escape_pct = category_counts[ESCAPE] / total
    escape_score = max(0, 10 - (escape_pct * 50))

    raw = deep_score + switch_score + escape_score
    return min(100, max(0, round(raw)))


def score_label(score: int) -> tuple[str, str]:
    """Returns (label, color) for a focus score."""
    if score >= 85:
        return "Exceptional", "bright_green"
    elif score >= 70:
        return "Good", "green"
    elif score >= 55:
        return "Average", "yellow"
    elif score >= 40:
        return "Scattered", "orange3"
    else:
        return "Distracted", "red"


def summarize_events(events: list) -> dict:
    """Summarize events into time buckets per category."""
    from collections import defaultdict
    from ridge.sites import DEEP, SHALLOW, ESCAPE

    counts = defaultdict(int)
    domains: dict[str, int] = defaultdict(int)
    context_switches = 0
    prev_app = None

    for e in events:
        cat = e["category"] or SHALLOW
        counts[cat] += 1
        if e["domain"]:
            domains[e["domain"]] += 1
        app = e["app"]
        if app and app != prev_app and prev_app is not None:
            context_switches += 1
        if app:
            prev_app = app

    total = sum(counts.values())
    # Each event ≈ 30 seconds of tracking
    def to_hm(n):
        mins = round(n * 0.5)
        return f"{mins // 60}h {mins % 60:02d}m"

    return {
        "deep_count": counts[DEEP],
        "shallow_count": counts[SHALLOW],
        "escape_count": counts[ESCAPE],
        "total_count": total,
        "deep_time": to_hm(counts[DEEP]),
        "shallow_time": to_hm(counts[SHALLOW]),
        "escape_time": to_hm(counts[ESCAPE]),
        "context_switches": context_switches,
        "top_domains": sorted(domains.items(), key=lambda x: -x[1])[:10],
        "score": calculate_score(list(events)),
    }