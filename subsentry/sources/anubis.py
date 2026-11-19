"""Anubis Subdomain Database integration for SubSentry."""

import json
import logging
import urllib.error
import urllib.request

from subsentry.config import SOURCE_TIMEOUT
from subsentry.sources.base import SubdomainSource

logger = logging.getLogger("subsentry")


class AnubisSource(SubdomainSource):
    """Anubis DB — Passive subdomain lookup API (Native Python)."""

    name = "anubis"
    command = ""
    description = "Anubis DB Subdomain Enumeration API"
    url = "https://jldc.me"

    def is_available(self) -> bool:
        """API-based source, always available without external binaries."""
        return True

    def enumerate(self, domain: str) -> set:
        """Query Anubis API and return discovered subdomains."""
        subdomains = set()
        endpoint = f"https://jldc.me/anubis/subdomains/{domain}"

        req = urllib.request.Request(
            endpoint,
            headers={
                "User-Agent": "SubSentry/1.0 (Subdomain Monitoring Suite)"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=min(SOURCE_TIMEOUT, 30)) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode('utf-8', errors='ignore'))
                    if isinstance(data, list):
                        for hostname in data:
                            hostname = str(hostname).strip().lower()
                            if hostname.startswith("*."):
                                hostname = hostname[2:]
                            if hostname.endswith(f".{domain}") or hostname == domain:
                                if "." in hostname and not hostname.startswith("*"):
                                    subdomains.add(hostname)

            logger.debug(f"[anubis] Found {len(subdomains)} subdomains")

        except (urllib.error.URLError, TimeoutError) as e:
            logger.warning(f"[anubis] API request failed: {e}")
        except json.JSONDecodeError:
            logger.warning("[anubis] Invalid JSON response from API")
        except Exception as e:
            logger.error(f"[anubis] Unexpected error: {e}")

        return subdomains
