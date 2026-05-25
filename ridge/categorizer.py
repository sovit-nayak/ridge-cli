from urllib.parse import urlparse
from ridge.sites import lookup, DEEP, SHALLOW, ESCAPE
from ridge.storage import get_db


def categorize_url(url: str) -> tuple[str, str]:
    """Returns (domain, category) for a given URL."""
    try:
        parsed = urlparse(url if "://" in url else "https://" + url)
        domain = parsed.netloc.lower().replace("www.", "")
        if not domain:
            domain = url.lower().replace("www.", "").split("/")[0]
    except Exception:
        domain = url

    # Check user overrides first
    conn = get_db()
    row = conn.execute(
        "SELECT category FROM site_overrides WHERE domain=?", (domain,)
    ).fetchone()
    conn.close()
    if row:
        return domain, row["category"]

    return domain, lookup(domain)


def categorize_domain(domain: str) -> str:
    domain = domain.lower().replace("www.", "")
    conn = get_db()
    row = conn.execute(
        "SELECT category FROM site_overrides WHERE domain=?", (domain,)
    ).fetchone()
    conn.close()
    if row:
        return row["category"]
    return lookup(domain)


def set_override(domain: str, category: str):
    assert category in (DEEP, SHALLOW, ESCAPE), f"Invalid category: {category}"
    conn = get_db()
    conn.execute(
        "INSERT OR REPLACE INTO site_overrides (domain, category) VALUES (?, ?)",
        (domain, category)
    )
    conn.commit()
    conn.close()


CATEGORY_LABEL = {
    DEEP:    "🟢 Deep Work",
    SHALLOW: "🟡 Shallow",
    ESCAPE:  "🔴 Escape",
}

CATEGORY_COLOR = {
    DEEP:    "green",
    SHALLOW: "yellow",
    ESCAPE:  "red",
}