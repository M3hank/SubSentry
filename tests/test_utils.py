"""Utility tests."""

import pytest

from subsentry.utils import format_timestamp, normalize_domain, validate_domain


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("example.com", "example.com"),
        ("Example.COM", "example.com"),
        ("https://example.com/path?q=1", "example.com"),
        ("http://sub.example.com:8080", "sub.example.com"),
        ("*.example.com", "example.com"),
        ("example.com.", "example.com"),
    ],
)
def test_normalize_domain(value, expected):
    assert normalize_domain(value) == expected


@pytest.mark.parametrize("value", ["", "localhost", "not_a_domain", "-bad.com", "example..com"])
def test_validate_domain_rejects_garbage(value):
    with pytest.raises(ValueError):
        validate_domain(value)


def test_format_timestamp_handles_garbage():
    assert format_timestamp("not-a-date") == "not-a-date"
