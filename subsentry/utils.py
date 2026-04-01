"""Utility functions for SubSentry."""

import re
import shutil
import logging
from datetime import datetime, timezone


# ── ANSI Color Codes ──────────────────────────────────────────────────────────

class Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"

    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"


def colorize(text, color):
    """Wrap text in ANSI color codes."""
    return f"{color}{text}{Colors.RESET}"


# ── Logging ───────────────────────────────────────────────────────────────────

def setup_logging(verbose=False):
    """Configure logging for SubSentry."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format=f"{Colors.DIM}%(asctime)s{Colors.RESET} %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger("subsentry")


logger = logging.getLogger("subsentry")


# ── Domain Validation ─────────────────────────────────────────────────────────

DOMAIN_REGEX = re.compile(
    r"^(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+"
    r"[a-zA-Z]{2,}$"
)


def validate_domain(domain):
    """Validate that a string looks like a valid domain name."""
    domain = domain.strip().lower()
    if not DOMAIN_REGEX.match(domain):
        raise ValueError(
            f"Invalid domain: '{domain}'. "
            "Expected format: example.com or sub.example.com"
        )
    return domain


# ── Tool Detection ────────────────────────────────────────────────────────────

def is_tool_installed(name):
    """Check if a CLI tool is available in PATH."""
    return shutil.which(name) is not None


# ── Display Helpers ───────────────────────────────────────────────────────────

BANNER = rf"""
{Colors.CYAN}{Colors.BOLD}
   ___       _    ___            _              
  / __| _  _| |__/ __| ___ _ _ | |_  _ _  _  _ 
  \__ \| || | '_ \__ \/ -_) ' \|  _|| '_|| || |
  |___/ \_,_|_.__/___/\___|_||_|\__||_|   \_, |
                                           |__/ 
{Colors.RESET}{Colors.DIM}  Subdomain Monitoring & Alerting Tool v1.0.0{Colors.RESET}
{Colors.DIM}  By m3hank{Colors.RESET}
"""


def print_banner():
    """Print the SubSentry ASCII banner."""
    print(BANNER)


def print_status(icon, message, color=Colors.WHITE):
    """Print a status message with an icon."""
    print(f"  {color}{icon}{Colors.RESET} {message}")


def print_success(message):
    print_status("✓", message, Colors.GREEN)


def print_error(message):
    print_status("✗", message, Colors.RED)


def print_warning(message):
    print_status("!", message, Colors.YELLOW)


def print_info(message):
    print_status("→", message, Colors.BLUE)


def print_new_subdomain(subdomain):
    print_status("+", subdomain, Colors.GREEN)


def timestamp_now():
    """Return current UTC timestamp as ISO string."""
    return datetime.now(timezone.utc).isoformat()


def format_timestamp(iso_str):
    """Format an ISO timestamp for display."""
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, TypeError):
        return iso_str
