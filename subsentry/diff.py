"""Diff engine — compares current scan against stored baseline."""

from __future__ import annotations

from subsentry.utils import Colors


def compute_diff(baseline, current):
    """Compare current scan results against the stored baseline.

    Args:
        baseline: set of previously known subdomains
        current: set of subdomains from the current scan

    Returns:
        dict with 'new', 'removed', and summary stats
    """
    baseline = set(baseline or set())
    current = set(current or set())
    new = current - baseline
    removed = baseline - current

    return {
        "new": sorted(new),
        "removed": sorted(removed),
        "total_current": len(current),
        "total_baseline": len(baseline),
        "new_count": len(new),
        "removed_count": len(removed),
    }


def format_diff_terminal(diff_result, domain):
    """Format the diff result for terminal display."""
    lines = []

    lines.append("")
    lines.append(f"  {Colors.BOLD}── Scan Results for {Colors.CYAN}{domain}{Colors.RESET}{Colors.BOLD} ──{Colors.RESET}")
    lines.append("")
    lines.append(
        f"  Baseline: {Colors.DIM}{diff_result['total_baseline']}{Colors.RESET}  |  "
        f"Current: {Colors.CYAN}{diff_result['total_current']}{Colors.RESET}  |  "
        f"New: {Colors.GREEN}{Colors.BOLD}{diff_result['new_count']}{Colors.RESET}  |  "
        f"Gone: {Colors.RED}{diff_result['removed_count']}{Colors.RESET}"
    )
    lines.append("")

    if diff_result["new"]:
        lines.append(f"  {Colors.GREEN}{Colors.BOLD}▶ New Subdomains ({diff_result['new_count']}){Colors.RESET}")
        for sub in diff_result["new"]:
            lines.append(f"    {Colors.GREEN}+ {sub}{Colors.RESET}")
        lines.append("")

    if diff_result["removed"]:
        lines.append(f"  {Colors.RED}▶ No Longer Seen ({diff_result['removed_count']}){Colors.RESET}")
        for sub in diff_result["removed"]:
            lines.append(f"    {Colors.DIM}- {sub}{Colors.RESET}")
        lines.append("")

    if not diff_result["new"] and not diff_result["removed"]:
        lines.append(f"  {Colors.DIM}No changes detected.{Colors.RESET}")
        lines.append("")

    return "\n".join(lines)


def format_diff_notify(diff_result, domain):
    """Format the diff result for chat notifications (plain text).

    Returns an empty string when nothing new was found.
    """
    if not diff_result["new"]:
        return ""

    lines = []
    lines.append(f"🔔 SubSentry Alert — {domain}")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"📊 {diff_result['new_count']} new subdomain(s) discovered!")
    lines.append("")

    for sub in diff_result["new"]:
        lines.append(f"  ➜ {sub}")

    lines.append("")
    lines.append(f"Total known: {diff_result['total_current']} | Previously: {diff_result['total_baseline']}")

    return "\n".join(lines)
