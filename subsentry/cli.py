"""CLI interface for SubSentry."""

import sys
import time
import signal
import argparse
import logging

from subsentry import __version__
from subsentry.db import Database
from subsentry.diff import compute_diff, format_diff_terminal
from subsentry.notifier import Notifier
from subsentry.sources import run_all_sources, get_source_status
from subsentry.utils import (
    Colors,
    print_banner,
    print_success,
    print_error,
    print_info,
    print_warning,
    validate_domain,
    format_timestamp,
    setup_logging,
)


# ── Graceful Shutdown ─────────────────────────────────────────────────────────

_running = True


def _signal_handler(sig, frame):
    global _running
    _running = False
    print(f"\n\n  {Colors.YELLOW}Caught interrupt, shutting down...{Colors.RESET}\n")


signal.signal(signal.SIGINT, _signal_handler)


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_init(args):
    """Initialize baseline for a domain."""
    domain = validate_domain(args.domain)
    db = Database()

    print_info(f"Initializing baseline for {Colors.CYAN}{Colors.BOLD}{domain}{Colors.RESET}")
    print()

    # Run all sources
    subdomains, sources_used, per_source = run_all_sources(domain)

    if not subdomains:
        print()
        print_warning("No subdomains found. Check that your tools are installed (run: subsentry sources)")
        return

    # Store baseline
    db.add_domain(domain)
    db.add_subdomains(domain, subdomains, source=",".join(sources_used))
    db.add_scan_record(domain, len(subdomains), len(subdomains), sources_used)

    print()
    print_success(
        f"Baseline set: {Colors.BOLD}{len(subdomains)}{Colors.RESET} "
        f"subdomains stored for {Colors.CYAN}{domain}{Colors.RESET}"
    )
    print()


def cmd_scan(args):
    """Run a scan and diff against baseline."""
    domain = validate_domain(args.domain)
    db = Database()

    # Check if baseline exists
    baseline = db.get_baseline(domain)
    if not baseline:
        print_warning(
            f"No baseline found for {Colors.CYAN}{domain}{Colors.RESET}. "
            f"Run {Colors.BOLD}subsentry init {domain}{Colors.RESET} first."
        )
        return

    print_info(
        f"Scanning {Colors.CYAN}{Colors.BOLD}{domain}{Colors.RESET} "
        f"(baseline: {len(baseline)} subdomains)"
    )
    print()

    # Run all sources
    current, sources_used, per_source = run_all_sources(domain)

    if not current:
        print_warning("No subdomains found in this scan. Skipping diff.")
        return

    # Compute diff
    diff_result = compute_diff(baseline, current)

    # Display results
    print(format_diff_terminal(diff_result, domain))

    # Update database with new subdomains
    if diff_result["new"]:
        db.add_subdomains(domain, current, source=",".join(sources_used))

    # Record scan
    db.add_scan_record(domain, diff_result["total_current"], diff_result["new_count"], sources_used)

    # Send notification if enabled and there are new subdomains
    if args.notify and diff_result["new"]:
        notifier = Notifier(
            provider_config=getattr(args, "provider_config", None),
            notify_id=getattr(args, "notify_id", None),
        )
        notifier.send_new_subdomains(diff_result, domain)
    elif args.notify and not diff_result["new"]:
        print_info("No new subdomains — notification skipped")


def cmd_monitor(args):
    """Continuously monitor a domain at a set interval."""
    domain = validate_domain(args.domain)
    db = Database()
    interval = args.interval

    # Check if baseline exists, if not, initialize
    baseline = db.get_baseline(domain)
    if not baseline:
        print_warning(f"No baseline found. Running initial scan to set baseline...")
        print()

        subdomains, sources_used, _ = run_all_sources(domain)
        if subdomains:
            db.add_domain(domain)
            db.add_subdomains(domain, subdomains, source=",".join(sources_used))
            db.add_scan_record(domain, len(subdomains), len(subdomains), sources_used)
            print()
            print_success(f"Baseline set: {len(subdomains)} subdomains")
        else:
            print_error("No subdomains found. Cannot start monitoring.")
            return

    print()
    print_info(
        f"Monitoring {Colors.CYAN}{Colors.BOLD}{domain}{Colors.RESET} "
        f"every {Colors.BOLD}{interval}s{Colors.RESET} "
        f"(Ctrl+C to stop)"
    )
    print()

    scan_count = 0

    while _running:
        scan_count += 1
        baseline = db.get_baseline(domain)

        print(f"  {Colors.DIM}{'─' * 50}{Colors.RESET}")
        print(
            f"  {Colors.DIM}Scan #{scan_count} "
            f"| Baseline: {len(baseline)} subdomains{Colors.RESET}"
        )
        print()

        # Run scan
        current, sources_used, _ = run_all_sources(domain)

        if current:
            diff_result = compute_diff(baseline, current)
            print(format_diff_terminal(diff_result, domain))

            # Update baseline with new finds
            if diff_result["new"]:
                db.add_subdomains(domain, current, source=",".join(sources_used))

                # Notify
                if args.notify:
                    notifier = Notifier(
                        provider_config=getattr(args, "provider_config", None),
                        notify_id=getattr(args, "notify_id", None),
                    )
                    notifier.send_new_subdomains(diff_result, domain)

            db.add_scan_record(
                domain, diff_result["total_current"],
                diff_result["new_count"], sources_used,
            )
        else:
            print_warning("Scan returned no results")

        # Wait for next interval
        print_info(f"Next scan in {interval}s...")
        print()

        # Interruptible sleep
        for _ in range(interval):
            if not _running:
                break
            time.sleep(1)

    print_info("Monitoring stopped.")


def cmd_list(args):
    """List all known subdomains for a domain."""
    domain = validate_domain(args.domain)
    db = Database()

    subs = db.get_subdomains_detail(domain)

    if not subs:
        print_warning(
            f"No subdomains stored for {Colors.CYAN}{domain}{Colors.RESET}. "
            f"Run {Colors.BOLD}subsentry init {domain}{Colors.RESET} first."
        )
        return

    print()
    print_info(
        f"Known subdomains for {Colors.CYAN}{Colors.BOLD}{domain}{Colors.RESET} "
        f"({Colors.BOLD}{len(subs)}{Colors.RESET} total)"
    )
    print()

    if args.json:
        import json
        print(json.dumps(subs, indent=2))
    else:
        # Table header
        print(f"  {'Subdomain':<50} {'First Seen':<22} {'Source'}")
        print(f"  {'─' * 50} {'─' * 22} {'─' * 20}")
        for s in subs:
            first_seen = format_timestamp(s["first_seen"])
            source = s.get("source", "unknown")
            print(f"  {Colors.GREEN}{s['subdomain']:<50}{Colors.RESET} {Colors.DIM}{first_seen:<22}{Colors.RESET} {source}")

    print()


def cmd_sources(args):
    """Show status of all enumeration sources."""
    statuses = get_source_status()

    print()
    print_info(f"Enumeration Sources")
    print()

    available_count = sum(1 for s in statuses if s["available"])

    for s in statuses:
        status_icon = s["icon"]
        name = f"{Colors.BOLD}{s['name']}{Colors.RESET}"
        desc = f"{Colors.DIM}{s['description']}{Colors.RESET}"
        url = f"{Colors.DIM}{s['url']}{Colors.RESET}"

        if s["available"]:
            print(f"  {status_icon} {name}  {desc}")
        else:
            print(f"  {status_icon} {name}  {Colors.RED}NOT INSTALLED{Colors.RESET}")
            print(f"    {url}")

    print()
    print_info(f"{available_count}/{len(statuses)} sources available")

    # Check notify
    from subsentry.utils import is_tool_installed
    if is_tool_installed("notify"):
        print(f"  {Colors.GREEN}✓{Colors.RESET} {Colors.BOLD}notify{Colors.RESET}  {Colors.DIM}Notification delivery{Colors.RESET}")
    else:
        print(f"  {Colors.RED}✗{Colors.RESET} {Colors.BOLD}notify{Colors.RESET}  {Colors.RED}NOT INSTALLED{Colors.RESET}")
        print(f"    {Colors.DIM}https://github.com/projectdiscovery/notify{Colors.RESET}")

    print()


def cmd_history(args):
    """Show scan history for a domain."""
    domain = validate_domain(args.domain)
    db = Database()

    history = db.get_scan_history(domain, limit=args.limit)

    if not history:
        print_warning(f"No scan history for {Colors.CYAN}{domain}{Colors.RESET}")
        return

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


def cmd_delete(args):
    """Delete target domain and all associated subdomains and history."""
    domain = validate_domain(args.domain)
    db = Database()

    if not args.force:
        confirm = input(f"Are you sure you want to delete {domain} and all its baseline data? (y/N): ")
        if confirm.lower() not in ["y", "yes"]:
            print_info("Deletion cancelled.")
            return

    deleted = db.delete_domain(domain)
    if deleted:
        print_success(f"Successfully deleted {Colors.CYAN}{Colors.BOLD}{domain}{Colors.RESET} from database.")
    else:
        print_warning(f"Domain {Colors.CYAN}{domain}{Colors.RESET} not found in database.")


# ── Argument Parser ───────────────────────────────────────────────────────────

def build_parser():
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="subsentry",
        description="SubSentry — Subdomain Monitoring & Alerting Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  subsentry init example.com           Set baseline for a domain
  subsentry scan example.com --notify  Scan and alert on new subdomains
  subsentry monitor example.com -n     Continuously monitor (1h interval)
  subsentry monitor example.com -i 300 Monitor every 5 minutes
  subsentry list example.com           Show all known subdomains
  subsentry delete example.com         Delete target domain and history
  subsentry sources                    Check which tools are installed
  subsentry history example.com        View scan history
        """,
    )

    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable debug logging"
    )
    parser.add_argument(
        "-V", "--version", action="version", version=f"SubSentry v{__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # ── init ──
    p_init = subparsers.add_parser("init", help="Initialize baseline for a domain")
    p_init.add_argument("domain", help="Target domain (e.g., example.com)")

    # ── scan ──
    p_scan = subparsers.add_parser("scan", help="Scan and diff against baseline")
    p_scan.add_argument("domain", help="Target domain")
    p_scan.add_argument(
        "-n", "--notify", action="store_true",
        help="Send Discord notification for new subdomains",
    )
    p_scan.add_argument(
        "--provider-config", help="Path to notify provider-config.yaml"
    )
    p_scan.add_argument("--notify-id", help="Notify provider ID to use")

    # ── monitor ──
    p_monitor = subparsers.add_parser("monitor", help="Continuously monitor a domain")
    p_monitor.add_argument("domain", help="Target domain")
    p_monitor.add_argument(
        "-i", "--interval", type=int, default=3600,
        help="Scan interval in seconds (default: 3600)",
    )
    p_monitor.add_argument(
        "-n", "--notify", action="store_true",
        help="Send Discord notification for new subdomains",
    )
    p_monitor.add_argument(
        "--provider-config", help="Path to notify provider-config.yaml"
    )
    p_monitor.add_argument("--notify-id", help="Notify provider ID to use")

    # ── list ──
    p_list = subparsers.add_parser("list", help="List known subdomains")
    p_list.add_argument("domain", help="Target domain")
    p_list.add_argument(
        "--json", action="store_true", help="Output as JSON"
    )

    # ── delete ──
    p_delete = subparsers.add_parser("delete", help="Delete target domain and baseline data")
    p_delete.add_argument("domain", help="Target domain")
    p_delete.add_argument(
        "-f", "--force", action="store_true", help="Skip confirmation prompt"
    )

    # ── sources ──
    subparsers.add_parser("sources", help="Show enumeration source status")

    # ── history ──
    p_history = subparsers.add_parser("history", help="Show scan history")
    p_history.add_argument("domain", help="Target domain")
    p_history.add_argument(
        "-l", "--limit", type=int, default=20,
        help="Number of history entries to show (default: 20)",
    )

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
}


def main():
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args()

    # Setup
    setup_logging(verbose=args.verbose)
    print_banner()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    handler = COMMAND_MAP.get(args.command)
    if handler:
        try:
            handler(args)
        except ValueError as e:
            print_error(str(e))
            sys.exit(1)
        except KeyboardInterrupt:
            print(f"\n  {Colors.YELLOW}Interrupted.{Colors.RESET}\n")
            sys.exit(0)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
