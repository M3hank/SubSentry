"""SQLite database layer for SubSentry baseline storage."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from subsentry.config import DB_PATH, ensure_data_dir
from subsentry.utils import timestamp_now

SCHEMA_VERSION = 2

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
        self.db_path = Path(db_path) if db_path else DB_PATH
        if db_path is None:
            ensure_data_dir()
        else:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _connect(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA busy_timeout=30000")
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
            conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

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
            conn.execute("DELETE FROM scan_history WHERE domain = ?", (domain,))
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
        """Add subdomains to the database.

        Returns the set of subdomains that were not present before this call.
        Uses INSERT ... ON CONFLICT DO NOTHING so a row is only reported as new
        when the INSERT actually happened (the previous implementation compared
        timestamps and could double-report within the same second).
        """
        now = timestamp_now()
        new_subs = set()
        cleaned = sorted({s.strip().lower() for s in subdomains if s and s.strip()})

        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO domains (domain, first_seen) VALUES (?, ?)",
                (domain, now),
            )
            for sub in cleaned:
                cursor = conn.execute(
                    """
                    INSERT INTO subdomains (subdomain, domain, source, first_seen, last_seen)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(subdomain, domain) DO NOTHING
                    """,
                    (sub, domain, source, now, now),
                )
                if cursor.rowcount == 1:
                    new_subs.add(sub)
                else:
                    conn.execute(
                        "UPDATE subdomains SET last_seen = ? WHERE subdomain = ? AND domain = ?",
                        (now, sub, domain),
                    )

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

    # ── Export / Import / Stats ───────────────────────────────────────────

    def export_domain(self, domain):
        """Serialise a domain, its subdomains and history to a plain dict."""
        with self._connect() as conn:
            domain_row = conn.execute(
                "SELECT domain, first_seen, last_scanned FROM domains WHERE domain = ?",
                (domain,),
            ).fetchone()
            if domain_row is None:
                return None
            subs = conn.execute(
                "SELECT subdomain, source, first_seen, last_seen FROM subdomains WHERE domain = ? ORDER BY subdomain",
                (domain,),
            ).fetchall()
            history = conn.execute(
                "SELECT scanned_at, total_found, new_found, sources_used FROM scan_history WHERE domain = ? ORDER BY scanned_at",
                (domain,),
            ).fetchall()
        return {
            "schema_version": SCHEMA_VERSION,
            "exported_at": timestamp_now(),
            "domain": dict(domain_row),
            "subdomains": [dict(r) for r in subs],
            "history": [dict(r) for r in history],
        }

    def import_domain(self, payload):
        """Merge an exported payload back into the database.

        Existing subdomains keep their original metadata. Imported rows keep the
        ``source``/``first_seen``/``last_seen`` values from the snapshot instead
        of collapsing everything to "unknown"/now. Returns ``(added, skipped)``.
        """
        domain = payload.get("domain", {}).get("domain") or payload.get("domain_name")
        if not domain:
            raise ValueError("Import payload is missing domain.domain")

        now = timestamp_now()
        self.add_domain(domain)
        subs = payload.get("subdomains") or []
        added = 0

        with self._connect() as conn:
            for item in subs:
                sub = (item.get("subdomain") or "").strip().lower()
                if not sub:
                    continue
                cursor = conn.execute(
                    """
                    INSERT INTO subdomains (subdomain, domain, source, first_seen, last_seen)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(subdomain, domain) DO NOTHING
                    """,
                    (
                        sub,
                        domain,
                        item.get("source") or "unknown",
                        item.get("first_seen") or now,
                        item.get("last_seen") or now,
                    ),
                )
                if cursor.rowcount == 1:
                    added += 1

            for row in payload.get("history") or []:
                conn.execute(
                    """INSERT INTO scan_history (domain, scanned_at, total_found, new_found, sources_used)
                       VALUES (?, ?, ?, ?, ?)""",
                    (
                        domain,
                        row.get("scanned_at") or now,
                        int(row.get("total_found", 0)),
                        int(row.get("new_found", 0)),
                        row.get("sources_used", ""),
                    ),
                )

        return added, max(0, len(subs) - added)

    def get_stats(self):
        """Return per-domain counts used by the ``stats`` command."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT d.domain,
                       d.first_seen,
                       d.last_scanned,
                       COUNT(s.id) AS subdomains
                FROM domains d
                LEFT JOIN subdomains s ON s.domain = d.domain
                GROUP BY d.domain
                ORDER BY subdomains DESC, d.domain
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def to_json(self, path):
        """Write the entire database to a JSON file."""
        with self._connect() as conn:
            domains = [
                r["domain"]
                for r in conn.execute("SELECT domain FROM domains ORDER BY domain").fetchall()
            ]
        payload = [self.export_domain(d) for d in domains if d]
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        return len(payload)
