"""Configuration and defaults for SubSentry.

Every value can be overridden with an environment variable so the tool works
unchanged in cron jobs, systemd units and CI pipelines.
"""

from __future__ import annotations

import os
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# ── Paths ─────────────────────────────────────────────────────────────────────

DATA_DIR = Path(os.environ.get("SUBSENTRY_DATA_DIR", Path.home() / ".subsentry"))
DB_PATH = Path(os.environ.get("SUBSENTRY_DB", DATA_DIR / "subsentry.db"))

# ── Scanning ──────────────────────────────────────────────────────────────────

# Default monitoring interval in seconds (1 hour)
DEFAULT_INTERVAL = _env_int("SUBSENTRY_INTERVAL", 3600)

# Subprocess / API timeout for a single source (seconds)
SOURCE_TIMEOUT = _env_int("SUBSENTRY_SOURCE_TIMEOUT", 300)

# Max concurrent source threads
MAX_WORKERS = max(1, _env_int("SUBSENTRY_MAX_WORKERS", 3))

# How many times a source is retried after an unexpected failure
SOURCE_RETRIES = max(0, _env_int("SUBSENTRY_SOURCE_RETRIES", 1))

# Backoff between retries (seconds)
RETRY_BACKOFF = _env_float("SUBSENTRY_RETRY_BACKOFF", 2.0)

# ── HTTP ──────────────────────────────────────────────────────────────────────

HTTP_TIMEOUT = _env_int("SUBSENTRY_HTTP_TIMEOUT", 30)
USER_AGENT = "SubSentry/2.0 (+https://github.com/M3hank/SubSentry)"

# ── Notifications ─────────────────────────────────────────────────────────────

DISCORD_WEBHOOK = os.environ.get("SUBSENTRY_DISCORD_WEBHOOK", "")
SLACK_WEBHOOK = os.environ.get("SUBSENTRY_SLACK_WEBHOOK", "")
TELEGRAM_BOT_TOKEN = os.environ.get("SUBSENTRY_TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("SUBSENTRY_TELEGRAM_CHAT_ID", "")
GENERIC_WEBHOOK = os.environ.get("SUBSENTRY_WEBHOOK_URL", "")


def ensure_data_dir() -> None:
    """Create the data directory if it doesn't exist (and the DB parent)."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
