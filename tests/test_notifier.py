"""Notifier tests (no real network access)."""

import json

import pytest

from subsentry import config
from subsentry.notifier import Notifier, _chunk


@pytest.fixture(autouse=True)
def clean_config(monkeypatch):
    for name in [
        "DISCORD_WEBHOOK",
        "SLACK_WEBHOOK",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "GENERIC_WEBHOOK",
    ]:
        monkeypatch.setattr(config, name, "", raising=False)
    monkeypatch.setattr("subsentry.notifier.is_tool_installed", lambda _name: False)


def test_no_transport_prints_message(capsys):
    notifier = Notifier()
    assert notifier.is_available() is False
    assert notifier.send("hello") is False
    assert "hello" in capsys.readouterr().out


def test_explicit_webhook_wins(monkeypatch):
    monkeypatch.setattr(config, "DISCORD_WEBHOOK", "https://discord.test/hook", raising=False)
    notifier = Notifier(webhook="https://generic.test/hook")
    assert notifier.detect() == ("webhook", "https://generic.test/hook")


def test_discord_detected_from_env(monkeypatch):
    monkeypatch.setattr(config, "DISCORD_WEBHOOK", "https://discord.test/hook", raising=False)
    assert Notifier().detect() == ("discord", "https://discord.test/hook")


def test_telegram_requires_both_values(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token", raising=False)
    assert Notifier().detect() == (None, None)
    monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "42", raising=False)
    assert Notifier().detect() == ("telegram", "token")


def test_discord_payload_is_valid_json(monkeypatch, capsys):
    monkeypatch.setattr(config, "DISCORD_WEBHOOK", "https://discord.test/hook", raising=False)
    captured = {}

    def fake_post(url, payload, timeout=10, headers=None):
        captured["url"] = url
        captured["payload"] = payload
        return True

    monkeypatch.setattr("subsentry.notifier._post_json", fake_post)
    assert Notifier().send("a.example.com") is True
    assert captured["url"] == "https://discord.test/hook"
    json.dumps(captured["payload"])  # must be serialisable
    assert captured["payload"]["content"] == "a.example.com"


def test_discord_message_is_chunked(monkeypatch):
    monkeypatch.setattr(config, "DISCORD_WEBHOOK", "https://discord.test/hook", raising=False)
    sent = []

    def fake_post(url, payload, timeout=10, headers=None):
        sent.append(payload["content"])
        return True

    monkeypatch.setattr("subsentry.notifier._post_json", fake_post)
    long_message = "\n".join(f"sub{i}.example.com" for i in range(200))
    assert Notifier().send(long_message) is True
    assert len(sent) > 1
    assert all(len(chunk) <= 2000 for chunk in sent)


def test_chunk_keeps_short_messages_whole():
    assert _chunk("short") == ["short"]


def test_failed_post_returns_false(monkeypatch):
    monkeypatch.setattr(config, "DISCORD_WEBHOOK", "https://discord.test/hook", raising=False)
    monkeypatch.setattr("subsentry.notifier._post_json", lambda *a, **k: False)
    assert Notifier().send("x") is False
