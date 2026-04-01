"""Configuration and defaults for SubSentry."""

import os
from pathlib import Path


# Default data directory
DATA_DIR = Path(os.environ.get("SUBSENTRY_DATA_DIR", Path.home() / ".subsentry"))

# Database path
DB_PATH = DATA_DIR / "subsentry.db"

# Default monitoring interval in seconds (1 hour)
DEFAULT_INTERVAL = 3600

# Subprocess timeout for each source (seconds)
SOURCE_TIMEOUT = 300

# Max concurrent source threads
MAX_WORKERS = 3


def ensure_data_dir():
    """Create the data directory if it doesn't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
