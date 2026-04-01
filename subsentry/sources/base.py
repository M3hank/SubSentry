"""Abstract base class for subdomain enumeration sources."""

from abc import ABC, abstractmethod

from subsentry.utils import is_tool_installed


class SubdomainSource(ABC):
    """Base class for all subdomain enumeration sources."""

    name: str = "unknown"
    command: str = "unknown"
    description: str = ""
    url: str = ""

    def is_available(self) -> bool:
        """Check if this source's CLI tool is installed."""
        return is_tool_installed(self.command)

    @abstractmethod
    def enumerate(self, domain: str) -> set:
        """
        Enumerate subdomains for the given domain.
        Returns a set of discovered subdomain strings.
        """
        pass

    def __repr__(self):
        status = "✓" if self.is_available() else "✗"
        return f"<{self.name} [{status}]>"
