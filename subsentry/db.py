"""SQLite database layer for SubSentry baseline storage."""

import sqlite3
from contextlib import contextmanager

from subsentry.config import DB_PATH, ensure_data_dir
from subsentry.utils import timestamp_now


SCHEMA = """
CREATE TABLE IF NOT EXISTS domains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT UNIQUE NOT NULL,
    first_seen TEXT NOT NULL,
    last_scanned TEXT
);

CREATE TABLE IF NOT EXISTS subdomains (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subdomain TEXT NOT NULL,
    domain TEXT NOT NULL,
    source TEXT,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    UNIQUE(subdomain, domain)
);

CREATE TABLE IF NOT EXISTS scan_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,
    scanned_at TEXT NOT NULL,
    total_found INTEGER DEFAULT 0,
    new_found INTEGER DEFAULT 0,
    sources_used TEXT
);

CREATE INDEX IF NOT EXISTS idx_subdomains_domain ON subdomains(domain);
CREATE INDEX IF NOT EXISTS idx_scan_history_domain ON scan_history(domain);
"""


class Database:
    """SQLite database for storing subdomain baselines and scan history."""

    def __init__(self, db_path=None):
        self.db_path = db_path or DB_PATH
        ensure_data_dir()
        self._init_db()

    @contextmanager
    def _connect(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self):
        """Initialize the database schema."""
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    # ── Domain Operations ─────────────────────────────────────────────────

    def add_domain(self, domain):
        """Register a domain for tracking."""
        now = timestamp_now()
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO domains (domain, first_seen) VALUES (?, ?)",
                (domain, now),
            )

    def get_domains(self):
        """Get all tracked domains."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT domain, first_seen, last_scanned FROM domains ORDER BY domain"
            ).fetchall()
            return [dict(r) for r in rows]

    def delete_domain(self, domain):
        """Delete a domain and all its associated subdomains and scan history."""
        with self._connect() as conn:
            c1 = conn.execute("DELETE FROM subdomains WHERE domain = ?", (domain,))
            c2 = conn.execute("DELETE FROM scan_history WHERE domain = ?", (domain,))
            c3 = conn.execute("DELETE FROM domains WHERE domain = ?", (domain,))
            return c3.rowcount > 0 or c1.rowcount > 0


    # ── Subdomain Operations ──────────────────────────────────────────────

    def get_baseline(self, domain):
        """Get all known subdomains for a domain."""
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT subdomain FROM subdomains WHERE domain = ?",
                (domain,),
            ).fetchall()
            return {row["subdomain"] for row in rows}

    def add_subdomains(self, domain, subdomains, source="unknown"):
        """Add subdomains to the database. Returns the set of newly added subdomains."""
        now = timestamp_now()
        new_subs = set()

        with self._connect() as conn:
            for sub in subdomains:
                cursor = conn.execute(
                    """
                    INSERT INTO subdomains (subdomain, domain, source, first_seen, last_seen)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(subdomain, domain) DO UPDATE SET
                        last_seen = excluded.last_seen
                    """,
                    (sub, domain, source, now, now),
                )
                if cursor.lastrowid and cursor.rowcount == 1:
                    # Check if this was actually an INSERT (not UPDATE)
                    existing = conn.execute(
                        "SELECT first_seen FROM subdomains WHERE subdomain = ? AND domain = ?",
                        (sub, domain),
                    ).fetchone()
                    if existing and existing["first_seen"] == now:
                        new_subs.add(sub)

            # Update domain last_scanned
            conn.execute(
                "UPDATE domains SET last_scanned = ? WHERE domain = ?",
                (now, domain),
            )

        return new_subs

    def get_subdomains_detail(self, domain):
        """Get detailed subdomain info for a domain."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT subdomain, source, first_seen, last_seen
                FROM subdomains
                WHERE domain = ?
                ORDER BY subdomain
                """,
                (domain,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Scan History ──────────────────────────────────────────────────────

    def add_scan_record(self, domain, total_found, new_found, sources_used):
        """Record a scan in the history."""
        now = timestamp_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO scan_history (domain, scanned_at, total_found, new_found, sources_used)
                VALUES (?, ?, ?, ?, ?)
                """,
                (domain, now, total_found, new_found, ",".join(sources_used)),
            )

    def get_scan_history(self, domain, limit=20):
        """Get recent scan history for a domain."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT scanned_at, total_found, new_found, sources_used
                FROM scan_history
                WHERE domain = ?
                ORDER BY scanned_at DESC
                LIMIT ?
                """,
                (domain, limit),
            ).fetchall()
            return [dict(r) for r in rows]
