from ridge.categorizer import categorize_url, categorize_domain

def test_known_deep_site():
    domain, cat = categorize_url("https://github.com/user/repo")
    assert domain == "github.com"
    assert cat == "deep"

def test_known_escape_site():
    domain, cat = categorize_url("https://youtube.com/watch?v=123")
    assert domain == "youtube.com"
    assert cat == "escape"

def test_known_shallow_site():
    domain, cat = categorize_url("https://slack.com")
    assert domain == "slack.com"
    assert cat == "shallow"

def test_domain_lookup():
    assert categorize_domain("github.com") == "deep"
    assert categorize_domain("reddit.com") == "escape"
    assert categorize_domain("gmail.com") == "shallow"