# SubSentry

> Subdomain monitoring with persistent baselines, delta detection and native alerts.
> Stop re-running recon by hand — get told the moment a new asset appears.

[![CI](https://github.com/M3hank/SubSentry/actions/workflows/ci.yml/badge.svg)](https://github.com/M3hank/SubSentry/actions/workflows/ci.yml)

---

## What it does

1. **Collects** subdomains from CLI tools (subfinder, findomain, assetfinder) and native APIs (crt.sh, AlienVault OTX, HackerTarget, Anubis) in parallel.
2. **Stores** a baseline per domain in SQLite (`~/.subsentry/subsentry.db` by default).
3. **Diffs** every scan against the baseline and reports new / disappeared assets.
4. **Alerts** through Discord, Slack, Telegram or any generic webhook — no extra binaries required.

## Install

```bash
git clone https://github.com/M3hank/SubSentry.git
cd SubSentry
pip install -e .            # runtime has zero Python dependencies
# optional:
pip install -e ".[dev]"     # pytest + ruff
```

The native API sources work out of the box. Installing the CLI tools increases coverage:

```bash
go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
go install github.com/tomnomnom/assetfinder@latest
# findomain: https://github.com/Findomain/Findomain/releases
```

## Quick start

```bash
subsentry init example.com                  # first baseline
subsentry scan example.com --notify         # diff + alert on new assets
subsentry monitor example.com -i 900 -n     # keep watching every 15 min
subsentry list example.com                  # everything known
subsentry stats                             # all tracked domains
```

## Alerts

Set one of these environment variables and `--notify` starts working immediately:

| Transport | Variables |
|-----------|-----------|
| Discord | `SUBSENTRY_DISCORD_WEBHOOK` |
| Slack | `SUBSENTRY_SLACK_WEBHOOK` |
| Telegram | `SUBSENTRY_TELEGRAM_BOT_TOKEN` + `SUBSENTRY_TELEGRAM_CHAT_ID` |
| Generic JSON webhook | `SUBSENTRY_WEBHOOK_URL` |

```bash
export SUBSENTRY_DISCORD_WEBHOOK="https://discord.com/api/webhooks/..."
subsentry scan example.com --notify
```

ProjectDiscovery's `notify` is still supported and is used automatically when
`--provider-config` / `--notify-id` is passed (or when `notify` is installed and
no native webhook is configured). Messages longer than Discord's limit are
chunked automatically.

## Automation / CI

```bash
# Machine-readable output
subsentry scan example.com --json scan.json

# Exit 2 when new subdomains appear — useful for cron + alerting pipelines
subsentry scan example.com --fail-on-new -q

# Watch loop with jitter and per-scan JSON snapshots
subsentry monitor example.com -i 3600 --jitter 300 --json-dir ./snapshots -n
```

Exit codes: `0` success, `1` error (no baseline, no results, bad input), `2` new
subdomains with `--fail-on-new`.

## Snapshots

```bash
subsentry export example.com -o acme.json   # one domain
subsentry export --all -o backup.json       # entire database
subsentry import acme.json                  # merge into another machine/db
```

## Commands

| Command | Purpose |
|---------|---------|
| `init <domain>` | Create/refresh the baseline |
| `scan <domain>` | Diff against baseline, optionally alert |
| `monitor <domain>` | Continuous scans with interval + jitter |
| `list <domain>` | Known subdomains (`--json`) |
| `history <domain>` | Scan history (`--json`) |
| `stats` | Per-domain database overview |
| `export` / `import` | JSON snapshots |
| `sources` | Source + notifier availability |
| `delete <domain>` | Remove a target and its data |

Shared flags: `--db PATH`, `-q/--quiet`, `--source NAME`, `--exclude-source NAME`,
`--workers N`, `--retries N`.

## Configuration

| Variable | Default | Meaning |
|----------|---------|---------|
| `SUBSENTRY_DATA_DIR` | `~/.subsentry` | Data directory |
| `SUBSENTRY_DB` | `<data>/subsentry.db` | Database path |
| `SUBSENTRY_INTERVAL` | `3600` | Default monitor interval |
| `SUBSENTRY_MAX_WORKERS` | `3` | Concurrent sources |
| `SUBSENTRY_SOURCE_TIMEOUT` | `300` | Per-source timeout (s) |
| `SUBSENTRY_SOURCE_RETRIES` | `1` | Retries per failing source |
| `NO_COLOR` | unset | Disable ANSI colours |

## Development

```bash
pip install -e ".[dev]"
pytest -q
ruff check .
```

The suite covers the database UPSERT semantics, diffing, notifier payloads,
source retries and the full CLI flow with the network layer mocked.

## License

MIT — see [LICENSE](LICENSE).
