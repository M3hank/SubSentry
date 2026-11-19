"""CLI interface for SubSentry."""

from __future__ import annotations

import argparse
import json
import logging
import random
import signal
import sys
import time
from datetime import datetime, timezone

from subsentry import __version__
from subsentry.config import DEFAULT_INTERVAL, MAX_WORKERS, SOURCE_RETRIES
from subsentry.db import Database
from subsentry.diff import compute_diff, format_diff_terminal
from subsentry.notifier import Notifier
from subsentry.sources import get_source_status, run_all_sources
from subsentry.utils import (
    Colors,
    format_timestamp,
    print_banner,
    print_error,
    print_info,
    print_success,
    print_warning,
    setup_logging,
    validate_domain,
)

logger = logging.getLogger("subsentry")

# ── Graceful Shutdown ─────────────────────────────────────────────────────────

_running = True


def _signal_handler(sig, frame):  # pragma: no cover - signal path
    global _running
    _running = False
    print(f"\n\n  {Colors.YELLOW}Caught interrupt, shutting down...{Colors.RESET}\n")


EXIT_OK = 0
EXIT_ERROR = 1
EXIT_NEW_FOUND = 2


# ── Shared helpers ────────────────────────────────────────────────────────────

def _quiet(args) -> bool:
    return bool(getattr(args, "quiet", False))


def _info(args, message):
    if not _quiet(args):
        print_info(message)


def _success(args, message):
    if not _quiet(args):
        print_success(message)


def _warning(args, message):
    print_warning(message)


def _scan(args, db, domain):
    """Run sources once and return (diff_result, sources_used, current, per_source)."""
    current, sources_used, per_source = run_all_sources(
        domain,
        only=getattr(args, "source", None),
        exclude=getattr(args, "exclude_source", None),
        workers=getattr(args, "workers", None),
        retries=getattr(args, "retries", None),
    )
    baseline = db.get_baseline(domain)
    diff_result = compute_diff(baseline, current)
    return diff_result, sources_used, current, per_source


def _notifier(args) -> Notifier:
    return Notifier(
        provider_config=getattr(args, "provider_config", None),
        notify_id=getattr(args, "notify_id", None),
        webhook=getattr(args, "webhook", None),
        kind=getattr(args, "notify_kind", None),
    )


def _write_scan_json(path, domain, diff_result, sources_used):
    payload = {
        "tool": "subsentry",
        "version": __version__,
        "domain": domain,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "sources": sources_used,
        **diff_result,
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    return payload


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_init(args):
    """Initialize baseline for a domain."""
    domain = validate_domain(args.domain)
    db = Database(getattr(args, "db", None))

    _info(args, f"Initializing baseline for {Colors.CYAN}{Colors.BOLD}{domain}{Colors.RESET}")
    print()

    subdomains, sources_used, _ = run_all_sources(
        domain,
        only=getattr(args, "source", None),
        exclude=getattr(args, "exclude_source", None),
        workers=getattr(args, "workers", None),
        retries=getattr(args, "retries", None),
    )

    if not subdomains:
        print()
        _warning(args, "No subdomains found. Check that your tools are installed (run: subsentry sources)")
        return EXIT_ERROR

    db.add_domain(domain)
    db.add_subdomains(domain, subdomains, source=",".join(sources_used))
    db.add_scan_record(domain, len(subdomains), len(subdomains), sources_used)

    print()
    _success(
        args,
        f"Baseline set: {Colors.BOLD}{len(subdomains)}{Colors.RESET} "
        f"subdomains stored for {Colors.CYAN}{domain}{Colors.RESET}",
    )
    print()
    return EXIT_OK


def cmd_scan(args):
    """Run a scan and diff against baseline."""
    domain = validate_domain(args.domain)
    db = Database(getattr(args, "db", None))

    baseline = db.get_baseline(domain)
    if not baseline:
        _warning(
            args,
            f"No baseline found for {Colors.CYAN}{domain}{Colors.RESET}. "
            f"Run {Colors.BOLD}subsentry init {domain}{Colors.RESET} first.",
        )
        return EXIT_ERROR

    _info(
        args,
        f"Scanning {Colors.CYAN}{Colors.BOLD}{domain}{Colors.RESET} "
        f"(baseline: {len(baseline)} subdomains)",
    )
    print()

    diff_result, sources_used, current, _ = _scan(args, db, domain)

    if not current:
        _warning(args, "No subdomains found in this scan. Skipping diff.")
        return EXIT_ERROR

    if not _quiet(args):
        print(format_diff_terminal(diff_result, domain))

    if diff_result["new"]:
        db.add_subdomains(domain, current, source=",".join(sources_used))

    db.add_scan_record(domain, diff_result["total_current"], diff_result["new_count"], sources_used)

    if getattr(args, "json", None):
        _write_scan_json(args.json, domain, diff_result, sources_used)
        _info(args, f"JSON written to {Colors.CYAN}{args.json}{Colors.RESET}")

    if args.notify and diff_result["new"]:
        _notifier(args).send_new_subdomains(diff_result, domain)
    elif args.notify and not diff_result["new"]:
        _info(args, "No new subdomains — notification skipped")

    if getattr(args, "fail_on_new", False) and diff_result["new"]:
        return EXIT_NEW_FOUND
    return EXIT_OK


def cmd_monitor(args):
    """Continuously monitor a domain at a set interval."""
    domain = validate_domain(args.domain)
    db = Database(getattr(args, "db", None))
    interval = max(30, args.interval)
    jitter = max(0, args.jitter)

    baseline = db.get_baseline(domain)
    if not baseline:
        _warning(args, "No baseline found. Running initial scan to set baseline...")
        print()

        subdomains, sources_used, _ = run_all_sources(
            domain,
            only=getattr(args, "source", None),
            exclude=getattr(args, "exclude_source", None),
            workers=getattr(args, "workers", None),
            retries=getattr(args, "retries", None),
        )
        if not subdomains:
            print_error("No subdomains found. Cannot start monitoring.")
            return EXIT_ERROR

        db.add_domain(domain)
        db.add_subdomains(domain, subdomains, source=",".join(sources_used))
        db.add_scan_record(domain, len(subdomains), len(subdomains), sources_used)
        print()
        _success(args, f"Baseline set: {len(subdomains)} subdomains")

    print()
    _info(
        args,
        f"Monitoring {Colors.CYAN}{Colors.BOLD}{domain}{Colors.RESET} "
        f"every {Colors.BOLD}{interval}s{Colors.RESET} (Ctrl+C to stop)",
    )
    print()

    if getattr(args, "json_dir", None):
        from pathlib import Path

        Path(args.json_dir).mkdir(parents=True, exist_ok=True)

    notifier = _notifier(args) if args.notify else None
    scan_count = 0
    max_scans = getattr(args, "max_scans", 0) or 0

    while _running:
        scan_count += 1
        diff_result, sources_used, current, _ = _scan(args, db, domain)

        print(f"  {Colors.DIM}{'─' * 50}{Colors.RESET}")
        print(
            f"  {Colors.DIM}Scan #{scan_count} "
            f"| Baseline: {diff_result['total_baseline']} subdomains{Colors.RESET}"
        )
        print()

        if current:
            if not _quiet(args):
                print(format_diff_terminal(diff_result, domain))

            if diff_result["new"]:
                db.add_subdomains(domain, current, source=",".join(sources_used))
                if notifier:
                    notifier.send_new_subdomains(diff_result, domain)

            db.add_scan_record(
                domain, diff_result["total_current"],
                diff_result["new_count"], sources_used,
            )
            if getattr(args, "json_dir", None):
                path = f"{args.json_dir.rstrip('/')}/{domain}-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}.json"
                _write_scan_json(path, domain, diff_result, sources_used)
        else:
            _warning(args, "Scan returned no results")

        if max_scans and scan_count >= max_scans:
            break

        sleep_for = interval + (random.uniform(0, jitter) if jitter else 0)
        _info(args, f"Next scan in {int(sleep_for)}s...")
        print()

        for _ in range(int(sleep_for)):
            if not _running:
                break
            time.sleep(1)

    print_info("Monitoring stopped.")
    return EXIT_OK


def cmd_list(args):
    """List all known subdomains for a domain."""
    domain = validate_domain(args.domain)
    db = Database(getattr(args, "db", None))

    subs = db.get_subdomains_detail(domain)

    if not subs:
        _warning(
            args,
            f"No subdomains stored for {Colors.CYAN}{domain}{Colors.RESET}. "
            f"Run {Colors.BOLD}subsentry init {domain}{Colors.RESET} first.",
        )
        return EXIT_ERROR

    if args.json:
        print(json.dumps(subs, indent=2))
        return EXIT_OK

    print()
    _info(
        args,
        f"Known subdomains for {Colors.CYAN}{Colors.BOLD}{domain}{Colors.RESET} "
        f"({Colors.BOLD}{len(subs)}{Colors.RESET} total)",
    )
    print()

    print(f"  {'Subdomain':<50} {'First Seen':<22} {'Source'}")
    print(f"  {'─' * 50} {'─' * 22} {'─' * 20}")
    for s in subs:
        first_seen = format_timestamp(s["first_seen"])
        source = s.get("source", "unknown")
        print(f"  {Colors.GREEN}{s['subdomain']:<50}{Colors.RESET} {Colors.DIM}{first_seen:<22}{Colors.RESET} {source}")

    print()
    return EXIT_OK


def cmd_sources(args):
    """Show status of all enumeration sources."""
    statuses = get_source_status()

    print()
    print_info("Enumeration Sources")
    print()

    available_count = sum(1 for s in statuses if s["available"])

    for s in statuses:
        name = f"{Colors.BOLD}{s['name']}{Colors.RESET}"
        desc = f"{Colors.DIM}{s['description']}{Colors.RESET}"

        if s["available"]:
            print(f"  {s['icon']} {name}  {desc}")
        else:
            print(f"  {s['icon']} {name}  {Colors.RED}NOT INSTALLED{Colors.RESET}")
            print(f"    {s['url']}")

    print()
    print_info(f"{available_count}/{len(statuses)} sources available")

    notifier = Notifier().describe()
    if notifier["available"]:
        print(f"  {Colors.GREEN}✓{Colors.RESET} {Colors.BOLD}notifier{Colors.RESET}  {Colors.DIM}{notifier['kind']}{Colors.RESET}")
    else:
        print(f"  {Colors.RED}✗{Colors.RESET} {Colors.BOLD}notifier{Colors.RESET}  {Colors.RED}NOT CONFIGURED{Colors.RESET}")
        print(f"    {Colors.DIM}Set SUBSENTRY_DISCORD_WEBHOOK or install projectdiscovery/notify{Colors.RESET}")

    print()
    return EXIT_OK


def cmd_history(args):
    """Show scan history for a domain."""
    domain = validate_domain(args.domain)
    db = Database(getattr(args, "db", None))

    history = db.get_scan_history(domain, limit=args.limit)

    if not history:
        _warning(args, f"No scan history for {Colors.CYAN}{domain}{Colors.RESET}")
        return EXIT_ERROR

    if args.json:
        print(json.dumps(history, indent=2))
        return EXIT_OK

    print()
    print_info(f"Scan history for {Colors.CYAN}{Colors.BOLD}{domain}{Colors.RESET}")
    print()

    print(f"  {'Timestamp':<22} {'Total':<8} {'New':<8} {'Sources'}")
    print(f"  {'─' * 22} {'─' * 8} {'─' * 8} {'─' * 30}")

    for h in history:
        ts = format_timestamp(h["scanned_at"])
        new_color = Colors.GREEN if h["new_found"] > 0 else Colors.DIM
        print(
            f"  {Colors.DIM}{ts:<22}{Colors.RESET} "
            f"{h['total_found']:<8} "
            f"{new_color}{h['new_found']:<8}{Colors.RESET} "
            f"{Colors.DIM}{h['sources_used']}{Colors.RESET}"
        )

    print()
    return EXIT_OK


def cmd_stats(args):
    """Show per-domain statistics for the local database."""
    db = Database(getattr(args, "db", None))
    rows = db.get_stats()

    if not rows:
        _warning(args, "Database is empty. Run subsentry init <domain> first.")
        return EXIT_ERROR

    if args.json:
        print(json.dumps(rows, indent=2))
        return EXIT_OK

    print()
    print_info("Tracked domains")
    print()
    print(f"  {'Domain':<40} {'Subdomains':<12} {'Last scanned'}")
    print(f"  {'─' * 40} {'─' * 12} {'─' * 22}")
    for row in rows:
        print(
            f"  {Colors.GREEN}{row['domain']:<40}{Colors.RESET} "
            f"{row['subdomains']:<12} "
            f"{Colors.DIM}{format_timestamp(row['last_scanned'])}{Colors.RESET}"
        )
    print()
    return EXIT_OK


def cmd_delete(args):
    """Delete target domain and all associated subdomains and history."""
    domain = validate_domain(args.domain)
    db = Database(getattr(args, "db", None))

    if not args.force:
        confirm = input(f"Are you sure you want to delete {domain} and all its baseline data? (y/N): ")
        if confirm.lower() not in ["y", "yes"]:
            print_info("Deletion cancelled.")
            return EXIT_OK

    deleted = db.delete_domain(domain)
    if deleted:
        _success(args, f"Successfully deleted {Colors.CYAN}{Colors.BOLD}{domain}{Colors.RESET} from database.")
        return EXIT_OK
    _warning(args, f"Domain {Colors.CYAN}{domain}{Colors.RESET} not found in database.")
    return EXIT_ERROR


def cmd_export(args):
    """Export one domain, or the whole database, to JSON."""
    db = Database(getattr(args, "db", None))

    if args.all:
        count = db.to_json(args.output)
        _success(args, f"Exported {count} domain(s) to {Colors.CYAN}{args.output}{Colors.RESET}")
        return EXIT_OK

    domain = validate_domain(args.domain)
    payload = db.export_domain(domain)
    if payload is None:
        _warning(args, f"Domain {Colors.CYAN}{domain}{Colors.RESET} not found in database.")
        return EXIT_ERROR

    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    _success(
        args,
        f"Exported {len(payload['subdomains'])} subdomains for {Colors.CYAN}{domain}{Colors.RESET} "
        f"to {Colors.CYAN}{args.output}{Colors.RESET}",
    )
    return EXIT_OK


def cmd_import(args):
    """Import a domain export back into the database."""
    db = Database(getattr(args, "db", None))
    with open(args.path, encoding="utf-8") as fh:
        payload = json.load(fh)

    entries = payload if isinstance(payload, list) else [payload]
    total_added = 0
    for entry in entries:
        added, _ = db.import_domain(entry)
        total_added += added

    _success(args, f"Imported {len(entries)} domain(s), {total_added} new subdomain(s).")
    return EXIT_OK


# ── Argument Parser ───────────────────────────────────────────────────────────

def _common():
    # SUPPRESS keeps a value given before the subcommand from being reset by
    # the subparser's default.
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--db", default=argparse.SUPPRESS, help="Path to the SQLite database (default: ~/.subsentry/subsentry.db)")
    parser.add_argument("-q", "--quiet", action="store_true", default=argparse.SUPPRESS, help="Suppress human-readable status output")
    return parser


def _source_filters(parser):
    parser.add_argument("--source", action="append", metavar="NAME", help="Only use this source (repeatable)")
    parser.add_argument("--exclude-source", action="append", metavar="NAME", help="Skip this source (repeatable)")
    parser.add_argument("--workers", type=int, default=MAX_WORKERS, help=f"Concurrent sources (default: {MAX_WORKERS})")
    parser.add_argument("--retries", type=int, default=SOURCE_RETRIES, help=f"Retries per failing source (default: {SOURCE_RETRIES})")


def _notify_args(parser):
    parser.add_argument("-n", "--notify", action="store_true", help="Send an alert when new subdomains appear")
    parser.add_argument("--provider-config", help="Path to a ProjectDiscovery notify provider-config.yaml")
    parser.add_argument("--notify-id", help="ProjectDiscovery notify provider ID")
    parser.add_argument("--webhook", help="Explicit webhook URL (Discord/Slack/generic JSON)")
    parser.add_argument("--notify-kind", choices=["discord", "slack", "telegram"], help="Force a notification transport")


def build_parser():
    """Build the argument parser."""
    common = _common()
    parser = argparse.ArgumentParser(
        prog="subsentry",
        description="SubSentry — Subdomain Monitoring & Alerting Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  subsentry init example.com                 Set baseline for a domain
  subsentry scan example.com --notify        Scan and alert on new subdomains
  subsentry scan example.com --json out.json Output machine-readable results
  subsentry scan example.com --fail-on-new   Exit 2 when new assets appear (CI)
  subsentry monitor example.com -n           Continuously monitor (1h interval)
  subsentry list example.com --json          Show all known subdomains
  subsentry export example.com -o acme.json  Snapshot a domain
  subsentry import acme.json                 Restore a snapshot
  subsentry stats                            Per-domain database overview
        """,
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument("-V", "--version", action="version", version=f"SubSentry v{__version__}")
    parser.add_argument("--db", help="Path to the SQLite database (default: ~/.subsentry/subsentry.db)")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress human-readable status output")

    sub = parser.add_subparsers(dest="command", help="Available commands")

    p_init = sub.add_parser("init", parents=[common], help="Initialize baseline for a domain")
    p_init.add_argument("domain", help="Target domain (e.g., example.com)")
    _source_filters(p_init)
    p_init.set_defaults(func=cmd_init)

    p_scan = sub.add_parser("scan", parents=[common], help="Scan and diff against baseline")
    p_scan.add_argument("domain", help="Target domain")
    p_scan.add_argument("--json", metavar="PATH", help="Write the scan result as JSON")
    p_scan.add_argument("--fail-on-new", action="store_true", help="Exit with code 2 when new subdomains are found")
    _source_filters(p_scan)
    _notify_args(p_scan)
    p_scan.set_defaults(func=cmd_scan)

    p_monitor = sub.add_parser("monitor", parents=[common], help="Continuously monitor a domain")
    p_monitor.add_argument("domain", help="Target domain")
    p_monitor.add_argument("-i", "--interval", type=int, default=DEFAULT_INTERVAL, help=f"Scan interval in seconds (default: {DEFAULT_INTERVAL})")
    p_monitor.add_argument("--jitter", type=int, default=0, help="Random jitter added to each interval (seconds)")
    p_monitor.add_argument("--max-scans", type=int, default=0, help="Stop after N scans (0 = forever)")
    p_monitor.add_argument("--json-dir", help="Write every scan result to this directory")
    _source_filters(p_monitor)
    _notify_args(p_monitor)
    p_monitor.set_defaults(func=cmd_monitor)

    p_list = sub.add_parser("list", parents=[common], help="List known subdomains")
    p_list.add_argument("domain", help="Target domain")
    p_list.add_argument("--json", action="store_true", help="Output as JSON")
    p_list.set_defaults(func=cmd_list)

    p_delete = sub.add_parser("delete", parents=[common], help="Delete target domain and baseline data")
    p_delete.add_argument("domain", help="Target domain")
    p_delete.add_argument("-f", "--force", action="store_true", help="Skip confirmation prompt")
    p_delete.set_defaults(func=cmd_delete)

    sub.add_parser("sources", parents=[common], help="Show enumeration source status").set_defaults(func=cmd_sources)

    p_history = sub.add_parser("history", parents=[common], help="Show scan history")
    p_history.add_argument("domain", help="Target domain")
    p_history.add_argument("-l", "--limit", type=int, default=20, help="Number of history entries to show (default: 20)")
    p_history.add_argument("--json", action="store_true", help="Output as JSON")
    p_history.set_defaults(func=cmd_history)

    p_stats = sub.add_parser("stats", parents=[common], help="Database overview")
    p_stats.add_argument("--json", action="store_true", help="Output as JSON")
    p_stats.set_defaults(func=cmd_stats)

    p_export = sub.add_parser("export", parents=[common], help="Export a domain to JSON")
    p_export.add_argument("domain", nargs="?", help="Target domain")
    p_export.add_argument("--all", action="store_true", help="Export every tracked domain")
    p_export.add_argument("-o", "--output", default="subsentry-export.json", help="Output file")
    p_export.set_defaults(func=cmd_export)

    p_import = sub.add_parser("import", parents=[common], help="Import a JSON export")
    p_import.add_argument("path", help="Path to a subsentry export file")
    p_import.set_defaults(func=cmd_import)

    return parser


# ── Main ──────────────────────────────────────────────────────────────────────

COMMAND_MAP = {
    "init": cmd_init,
    "scan": cmd_scan,
    "monitor": cmd_monitor,
    "list": cmd_list,
    "delete": cmd_delete,
    "sources": cmd_sources,
    "history": cmd_history,
    "stats": cmd_stats,
    "export": cmd_export,
    "import": cmd_import,
}


def main(argv=None):
    """Main entry point. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    setup_logging(verbose=getattr(args, "verbose", False))
    if not getattr(args, "quiet", False):
        print_banner()

    if not args.command:
        parser.print_help()
        return EXIT_OK

    if getattr(args, "verbose", False):
        args.quiet = getattr(args, "quiet", False)

    try:
        signal.signal(signal.SIGINT, _signal_handler)
    except (ValueError, AttributeError):  # not in main thread
        pass

    handler = COMMAND_MAP.get(args.command)
    if handler is None:
        parser.print_help()
        return EXIT_ERROR

    try:
        return handler(args) or EXIT_OK
    except ValueError as exc:
        print_error(str(exc))
        return EXIT_ERROR
    except FileNotFoundError as exc:
        print_error(f"File not found: {exc.filename}")
        return EXIT_ERROR
    except KeyboardInterrupt:  # pragma: no cover
        print(f"\n  {Colors.YELLOW}Interrupted.{Colors.RESET}\n")
        return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
