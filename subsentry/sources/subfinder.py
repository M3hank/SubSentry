"""Subfinder integration for SubSentry."""

import subprocess
import logging

from subsentry.sources.base import SubdomainSource
from subsentry.config import SOURCE_TIMEOUT

logger = logging.getLogger("subsentry")


class SubfinderSource(SubdomainSource):
    """ProjectDiscovery's Subfinder — fast passive subdomain enumeration."""

    name = "subfinder"
    command = "subfinder"
    description = "Fast passive subdomain enumeration tool by ProjectDiscovery"
    url = "https://github.com/projectdiscovery/subfinder"

    def enumerate(self, domain):
        """Run subfinder and return discovered subdomains."""
        subdomains = set()

        try:
            result = subprocess.run(
                ["subfinder", "-d", domain, "-silent", "-all"],
                capture_output=True,
                text=True,
                timeout=SOURCE_TIMEOUT,
            )

            if result.returncode != 0 and result.stderr:
                logger.warning(f"[subfinder] stderr: {result.stderr.strip()}")

            for line in result.stdout.strip().splitlines():
                line = line.strip().lower()
                if line and not line.startswith("[") and "." in line:
                    subdomains.add(line)

            logger.debug(f"[subfinder] Found {len(subdomains)} subdomains")

        except subprocess.TimeoutExpired:
            logger.warning(f"[subfinder] Timed out after {SOURCE_TIMEOUT}s")
        except FileNotFoundError:
            logger.error("[subfinder] Not found in PATH. Install: go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest")
        except Exception as e:
            logger.error(f"[subfinder] Error: {e}")

        return subdomains
