"""Findomain integration for SubSentry."""

import subprocess
import logging

from subsentry.sources.base import SubdomainSource
from subsentry.config import SOURCE_TIMEOUT

logger = logging.getLogger("subsentry")


class FindomainSource(SubdomainSource):
    """Findomain — fast cross-platform subdomain enumerator."""

    name = "findomain"
    command = "findomain"
    description = "Cross-platform subdomain enumerator written in Rust"
    url = "https://github.com/Findomain/Findomain"

    def enumerate(self, domain):
        """Run findomain and return discovered subdomains."""
        subdomains = set()

        try:
            result = subprocess.run(
                ["findomain", "-t", domain, "-q"],
                capture_output=True,
                text=True,
                timeout=SOURCE_TIMEOUT,
            )

            if result.returncode != 0 and result.stderr:
                logger.warning(f"[findomain] stderr: {result.stderr.strip()}")

            for line in result.stdout.strip().splitlines():
                line = line.strip().lower()
                if line and "." in line:
                    subdomains.add(line)

            logger.debug(f"[findomain] Found {len(subdomains)} subdomains")

        except subprocess.TimeoutExpired:
            logger.warning(f"[findomain] Timed out after {SOURCE_TIMEOUT}s")
        except FileNotFoundError:
            logger.error("[findomain] Not found in PATH. Install from: https://github.com/Findomain/Findomain/releases")
        except Exception as e:
            logger.error(f"[findomain] Error: {e}")

        return subdomains
