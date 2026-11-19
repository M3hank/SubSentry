"""Assetfinder integration for SubSentry."""

import logging
import subprocess

from subsentry.config import SOURCE_TIMEOUT
from subsentry.sources.base import SubdomainSource

logger = logging.getLogger("subsentry")


class AssetfinderSource(SubdomainSource):
    """Assetfinder — find domains and subdomains related to a given domain."""

    name = "assetfinder"
    command = "assetfinder"
    description = "Find domains and subdomains potentially related to a given domain"
    url = "https://github.com/tomnomnom/assetfinder"

    def enumerate(self, domain):
        """Run assetfinder and return discovered subdomains."""
        subdomains = set()

        try:
            result = subprocess.run(
                ["assetfinder", "--subs-only", domain],
                capture_output=True,
                text=True,
                timeout=SOURCE_TIMEOUT,
            )

            if result.returncode != 0 and result.stderr:
                logger.warning(f"[assetfinder] stderr: {result.stderr.strip()}")

            for line in result.stdout.strip().splitlines():
                line = line.strip().lower()
                if line and "." in line:
                    # Filter: only keep results that are actually subdomains of target
                    if line.endswith(f".{domain}") or line == domain:
                        subdomains.add(line)

            logger.debug(f"[assetfinder] Found {len(subdomains)} subdomains")

        except subprocess.TimeoutExpired:
            logger.warning(f"[assetfinder] Timed out after {SOURCE_TIMEOUT}s")
        except FileNotFoundError:
            logger.error("[assetfinder] Not found in PATH. Install: go install github.com/tomnomnom/assetfinder@latest")
        except Exception as e:
            logger.error(f"[assetfinder] Error: {e}")

        return subdomains
