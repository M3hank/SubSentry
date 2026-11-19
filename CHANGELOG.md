# Changelog

## 2.0.0

### Added
- Native notification transports: Discord, Slack, Telegram and generic JSON
  webhook (zero extra binaries). ProjectDiscovery `notify` remains supported.
- `scan --json PATH` machine-readable results and `--fail-on-new` (exit code 2)
  for cron/CI pipelines.
- `monitor --jitter`, `--max-scans` and `--json-dir` for long-running supervision.
- `export` / `import` commands plus `stats` overview.
- Per-source include/exclude filters (`--source`, `--exclude-source`),
  configurable workers and retries, per-source timing.
- Full pytest suite (47 tests) and GitHub Actions CI across Python 3.9–3.13.
- `NO_COLOR` support; colour is only emitted to a real terminal.

### Fixed
- Snapshot `import` discarded each subdomain's `source`, `first_seen` and
  `last_seen`, so a restore looked like a brand-new baseline. Import now
  preserves metadata and never overwrites existing rows.
- New-subdomain detection double-reported assets rescanned within the same
  second. Inserts now use `ON CONFLICT DO NOTHING` and only report rows that
  were actually inserted.
- Subdomain inserts could create orphan rows when the domain was not registered.
- Registering a SIGINT handler happened at import time, breaking library use
  and tests. It now happens in `main()`.
- SQLite now uses WAL + busy timeout, so a monitor and a manual scan can run at
  the same time without `database is locked` failures.
- Domain validation accepts schemes, wildcards, ports and trailing dots.
- Exit codes are meaningful (0/1/2) instead of always 0.

### Changed
- Packaging moved to `pyproject.toml`; the `requests` dependency was dropped
  (the project uses the standard library only).
- `Database(db_path=...)` accepts an explicit path; all commands accept `--db`.
