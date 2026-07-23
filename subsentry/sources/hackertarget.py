"""HackerTarget host search integration for SubSentry."""

import urllib.request
import urllib.error
import logging

from subsentry.sources.base import SubdomainSource
from subsentry.config import SOURCE_TIMEOUT

logger = logging.getLogger("subsentry")


class HackerTargetSource(SubdomainSource):
    """HackerTarget — Host search lookup API (Native Python)."""

    name = "hackertarget"
    command = ""
    description = "HackerTarget Host Search passive DNS API"
    url = "https://hackertarget.com"

    def is_available(self) -> bool:
        """API-based source, always available without external binaries."""
        return True

    def enumerate(self, domain: str) -> set:
        """Query HackerTarget API and return discovered subdomains."""
        subdomains = set()
        endpoint = f"https://api.hackertarget.com/hostsearch/?q={domain}"

        req = urllib.request.Request(
            endpoint,
            headers={
                "User-Agent": "SubSentry/1.0 (Subdomain Monitoring Suite)"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=min(SOURCE_TIMEOUT, 30)) as resp:
                if resp.status == 200:
                    text = resp.read().decode('utf-8', errors='ignore')
                    if "error" not in text.lower() and "API count exceeded" not in text:
                        for line in text.splitlines():
                            parts = line.strip().split(",")
                            if parts:
                                hostname = parts[0].strip().lower()
                                if hostname.endswith(f".{domain}") or hostname == domain:
                                    if "." in hostname:
                                        subdomains.add(hostname)

            logger.debug(f"[hackertarget] Found {len(subdomains)} subdomains")

        except (urllib.error.URLError, TimeoutError) as e:
            logger.warning(f"[hackertarget] API request failed: {e}")
        except Exception as e:
            logger.error(f"[hackertarget] Unexpected error: {e}")

        return subdomains
