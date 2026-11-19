"""Source registry and parallel runner for SubSentry."""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from subsentry import config
from subsentry.sources.alienvault import AlienVaultSource
from subsentry.sources.anubis import AnubisSource
from subsentry.sources.assetfinder import AssetfinderSource
from subsentry.sources.crtsh import CrtshSource
from subsentry.sources.findomain import FindomainSource
from subsentry.sources.hackertarget import HackerTargetSource
from subsentry.sources.subfinder import SubfinderSource
from subsentry.utils import Colors

logger = logging.getLogger("subsentry")

# ── Source Registry ───────────────────────────────────────────────────────────

ALL_SOURCES = [
    SubfinderSource(),
    FindomainSource(),
    AssetfinderSource(),
    CrtshSource(),
    AlienVaultSource(),
    HackerTargetSource(),
    AnubisSource(),
]

NAME_MAP = {source.name.lower(): source for source in ALL_SOURCES}


def get_available_sources(only=None, exclude=None):
    """Return available sources, optionally filtered by name."""
    only_set = {n.lower() for n in only or []}
    exclude_set = {n.lower() for n in exclude or []}
    matches = []
    for source in ALL_SOURCES:
        name = source.name.lower()
        if only_set and name not in only_set:
            continue
        if name in exclude_set:
            continue
        if source.is_available():
            matches.append(source)
    return matches


def get_source_status():
    """Return status info for all sources."""
    status = []
    for source in ALL_SOURCES:
        available = source.is_available()
        status.append({
            "name": source.name,
            "available": available,
            "description": source.description,
            "url": source.url,
            "icon": f"{Colors.GREEN}✓{Colors.RESET}" if available else f"{Colors.RED}✗{Colors.RESET}",
        })
    return status


# ── Parallel Runner ───────────────────────────────────────────────────────────

def _run_one(source, domain, retries, backoff):
    """Run a single source, retrying only on unexpected exceptions."""
    attempts = retries + 1
    last_error = None
    started = time.monotonic()

    for attempt in range(1, attempts + 1):
        try:
            results = source.enumerate(domain)
            elapsed = time.monotonic() - started
            return set(results or set()), None, elapsed, attempt
        except Exception as exc:  # noqa: BLE001 - a broken source must not kill the run
            last_error = exc
            logger.debug(f"[{source.name}] attempt {attempt}/{attempts} failed: {exc}")
            if attempt < attempts:
                time.sleep(backoff * attempt)

    return set(), last_error, time.monotonic() - started, attempts


def run_all_sources(domain, sources=None, only=None, exclude=None,
                    workers=None, retries=None, backoff=None):
    """Run available sources in parallel and aggregate results.

    Args:
        domain: Target domain.
        sources: Explicit source objects (overrides only/exclude).
        only: Iterable of source names to include.
        exclude: Iterable of source names to skip.
        workers: Max concurrent sources (defaults to config.MAX_WORKERS).
        retries: Retry attempts per failing source.
        backoff: Base backoff between retries in seconds.

    Returns:
        tuple: (aggregated_subdomains: set, sources_used: list[str],
                per_source_results: dict[str, set])
    """
    if sources is None:
        sources = get_available_sources(only=only, exclude=exclude)

    workers = max(1, workers or config.MAX_WORKERS)
    retries = config.SOURCE_RETRIES if retries is None else max(0, retries)
    backoff = config.RETRY_BACKOFF if backoff is None else max(0.0, backoff)

    if not sources:
        logger.error("No enumeration sources available!")
        return set(), [], {}

    aggregated = set()
    sources_used = []
    per_source = {}

    logger.info(
        f"Running {Colors.CYAN}{len(sources)}{Colors.RESET} sources: "
        f"{', '.join(s.name for s in sources)}"
    )

    with ThreadPoolExecutor(max_workers=min(workers, len(sources))) as executor:
        future_to_source = {
            executor.submit(_run_one, source, domain, retries, backoff): source
            for source in sources
        }

        for future in as_completed(future_to_source):
            source = future_to_source[future]
            results, error, elapsed, attempts = future.result()
            per_source[source.name] = results

            if error is not None:
                logger.error(
                    f"  {Colors.RED}✗{Colors.RESET} {source.name}: {error} "
                    f"{Colors.DIM}({elapsed:.1f}s, {attempts} attempt(s)){Colors.RESET}"
                )
                continue

            aggregated.update(results)
            sources_used.append(source.name)
            logger.info(
                f"  {Colors.GREEN}✓{Colors.RESET} {source.name}: "
                f"{Colors.BOLD}{len(results)}{Colors.RESET} subdomains "
                f"{Colors.DIM}({elapsed:.1f}s){Colors.RESET}"
            )

    sources_used.sort(key=str.lower)
    logger.info(
        f"Total unique: {Colors.BOLD}{Colors.CYAN}{len(aggregated)}{Colors.RESET} subdomains"
    )

    return aggregated, sources_used, per_source
