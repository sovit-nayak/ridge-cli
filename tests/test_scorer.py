from ridge.scorer import calculate_score, score_label

def test_empty_events():
    assert calculate_score([]) == 0

def test_all_deep_work():
    events = [{"category": "deep", "app": "Chrome"} for _ in range(10)]
    score = calculate_score(events)
    assert score > 70

def test_all_escape():
    events = [{"category": "escape", "app": "Chrome"} for _ in range(10)]
    score = calculate_score(events)
    assert score < 30

def test_score_label():
    assert score_label(90)[0] == "Exceptional"
    assert score_label(75)[0] == "Good"
    assert score_label(60)[0] == "Average"
    assert score_label(45)[0] == "Scattered"
    assert score_label(20)[0] == "Distracted"