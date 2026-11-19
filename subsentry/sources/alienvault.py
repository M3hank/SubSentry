"""AlienVault OTX Passive DNS integration for SubSentry."""

import json
import logging
import urllib.error
import urllib.request

from subsentry.config import SOURCE_TIMEOUT
from subsentry.sources.base import SubdomainSource

logger = logging.getLogger("subsentry")


class AlienVaultSource(SubdomainSource):
    """AlienVault OTX — Open Threat Exchange Passive DNS API (Native Python)."""

    name = "alienvault"
    command = ""
    description = "AlienVault OTX Open Threat Exchange Passive DNS"
    url = "https://otx.alienvault.com"

    def is_available(self) -> bool:
        """API-based source, always available without external binaries."""
        return True

    def enumerate(self, domain: str) -> set:
        """Query AlienVault OTX API and return discovered subdomains."""
        subdomains = set()
        endpoint = f"https://otx.alienvault.com/api/v1/indicators/domain/{domain}/passive_dns"

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
                    for entry in data.get("passive_dns", []):
                        hostname = entry.get("hostname", "").strip().lower()
                        if hostname.startswith("*."):
                            hostname = hostname[2:]
                        if hostname.endswith(f".{domain}") or hostname == domain:
                            if "." in hostname and not hostname.startswith("*"):
                                subdomains.add(hostname)

            logger.debug(f"[alienvault] Found {len(subdomains)} subdomains")

        except (urllib.error.URLError, TimeoutError) as e:
            logger.warning(f"[alienvault] API request failed: {e}")
        except json.JSONDecodeError:
            logger.warning("[alienvault] Invalid JSON response from API")
        except Exception as e:
            logger.error(f"[alienvault] Unexpected error: {e}")

        return subdomains
