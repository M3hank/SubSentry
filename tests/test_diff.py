"""Diff engine tests."""

from subsentry.diff import compute_diff, format_diff_notify, format_diff_terminal


def test_compute_diff_counts():
    result = compute_diff({"a.example.com", "b.example.com"}, {"b.example.com", "c.example.com"})
    assert result["new"] == ["c.example.com"]
    assert result["removed"] == ["a.example.com"]
    assert result["new_count"] == 1
    assert result["removed_count"] == 1
    assert result["total_current"] == 2
    assert result["total_baseline"] == 2


def test_compute_diff_handles_none():
    result = compute_diff(None, None)
    assert result["new_count"] == 0
    assert result["total_current"] == 0


def test_notify_is_empty_without_new_assets():
    assert format_diff_notify(compute_diff({"a.test"}, {"a.test"}), "test") == ""


def test_notify_lists_new_assets():
    message = format_diff_notify(compute_diff({"a.test"}, {"a.test", "b.test"}), "test")
    assert "b.test" in message
    assert "1 new subdomain" in message


def test_terminal_output_mentions_domain():
    text = format_diff_terminal(compute_diff(set(), {"a.test"}), "test")
    assert "test" in text
    assert "a.test" in text
