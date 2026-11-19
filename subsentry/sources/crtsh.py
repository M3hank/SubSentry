"""crt.sh Certificate Transparency integration for SubSentry."""

import json
import logging
import urllib.error
import urllib.request

from subsentry.config import SOURCE_TIMEOUT
from subsentry.sources.base import SubdomainSource

logger = logging.getLogger("subsentry")


class CrtshSource(SubdomainSource):
    """crt.sh — Certificate Transparency log search API (Native Python)."""

    name = "crt.sh"
    command = ""
    description = "Certificate Transparency log search API"
    url = "https://crt.sh"

    def is_available(self) -> bool:
        """API-based source, always available without external binaries."""
        return True

    def enumerate(self, domain: str) -> set:
        """Query crt.sh API and return discovered subdomains."""
        subdomains = set()
        endpoint = f"https://crt.sh/?q=%.{domain}&output=json"

        req = urllib.request.Request(
            endpoint,
            headers={
                "User-Agent": "SubSentry/1.0 (Subdomain Monitoring Suite)"
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=min(SOURCE_TIMEOUT, 45)) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode('utf-8', errors='ignore'))
                    for entry in data:
                        name_value = entry.get("name_value", "")
                        for line in name_value.splitlines():
                            line = line.strip().lower()
                            if line.startswith("*."):
                                line = line[2:]
                            if line.endswith(f".{domain}") or line == domain:
                                if "." in line and not line.startswith("*"):
                                    subdomains.add(line)

            logger.debug(f"[crt.sh] Found {len(subdomains)} subdomains")

        except (urllib.error.URLError, TimeoutError) as e:
            logger.warning(f"[crt.sh] API request failed: {e}")
        except json.JSONDecodeError:
            logger.warning("[crt.sh] Invalid JSON response from API")
        except Exception as e:
            logger.error(f"[crt.sh] Unexpected error: {e}")

        return subdomains
