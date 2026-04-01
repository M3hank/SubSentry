"""Source registry and parallel runner for SubSentry."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

from subsentry.config import MAX_WORKERS
from subsentry.sources.subfinder import SubfinderSource
from subsentry.sources.findomain import FindomainSource
from subsentry.sources.assetfinder import AssetfinderSource
from subsentry.utils import Colors

logger = logging.getLogger("subsentry")

# ── Source Registry ───────────────────────────────────────────────────────────

ALL_SOURCES = [
    SubfinderSource(),
    FindomainSource(),
    AssetfinderSource(),
]


def get_available_sources():
    """Return only sources whose CLI tools are installed."""
    return [s for s in ALL_SOURCES if s.is_available()]


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

def run_all_sources(domain, sources=None):
    """
    Run all available sources in parallel and aggregate results.

    Returns:
        tuple: (aggregated_subdomains: set, sources_used: list[str], per_source_results: dict)
    """
    if sources is None:
        sources = get_available_sources()

    if not sources:
        logger.error("No enumeration sources available! Install at least one tool.")
        return set(), [], {}

    aggregated = set()
    sources_used = []
    per_source = {}

    logger.info(
        f"Running {Colors.CYAN}{len(sources)}{Colors.RESET} sources: "
        f"{', '.join(s.name for s in sources)}"
    )

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_source = {
            executor.submit(source.enumerate, domain): source
            for source in sources
        }

        for future in as_completed(future_to_source):
            source = future_to_source[future]
            try:
                results = future.result()
                per_source[source.name] = results
                aggregated.update(results)
                sources_used.append(source.name)
                logger.info(
                    f"  {Colors.GREEN}✓{Colors.RESET} {source.name}: "
                    f"{Colors.BOLD}{len(results)}{Colors.RESET} subdomains"
                )
            except Exception as e:
                logger.error(f"  {Colors.RED}✗{Colors.RESET} {source.name}: {e}")
                per_source[source.name] = set()

    logger.info(
        f"Total unique: {Colors.BOLD}{Colors.CYAN}{len(aggregated)}{Colors.RESET} subdomains"
    )

    return aggregated, sources_used, per_source
