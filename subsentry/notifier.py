"""Notifier — sends alerts via ProjectDiscovery's notify tool."""

import subprocess
import logging

from subsentry.utils import is_tool_installed, Colors
from subsentry.config import SOURCE_TIMEOUT

logger = logging.getLogger("subsentry")


class Notifier:
    """Sends notifications through ProjectDiscovery's notify tool."""

    def __init__(self, provider_config=None, notify_id=None):
        """
        Args:
            provider_config: Path to custom provider-config.yaml (optional)
            notify_id: Specific provider ID to use (optional)
        """
        self.provider_config = provider_config
        self.notify_id = notify_id

    def is_available(self):
        """Check if notify is installed."""
        return is_tool_installed("notify")

    def send(self, message):
        """
        Send a message through notify.

        The message is piped to notify's stdin.

        Returns:
            bool: True if notification was sent successfully
        """
        if not message or not message.strip():
            logger.debug("No message to send, skipping notification")
            return True

        if not self.is_available():
            logger.warning(
                f"{Colors.YELLOW}notify tool not found.{Colors.RESET} "
                "Install: go install -v github.com/projectdiscovery/notify/cmd/notify@latest"
            )
            logger.info("Message that would have been sent:")
            print(message)
            return False

        cmd = ["notify", "-silent", "-bulk"]

        if self.provider_config:
            cmd.extend(["-provider-config", str(self.provider_config)])

        if self.notify_id:
            cmd.extend(["-id", self.notify_id])

        try:
            result = subprocess.run(
                cmd,
                input=message,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                logger.info(
                    f"  {Colors.GREEN}✓{Colors.RESET} Notification sent successfully"
                )
                return True
            else:
                logger.error(
                    f"  {Colors.RED}✗{Colors.RESET} notify failed: {result.stderr.strip()}"
                )
                return False

        except subprocess.TimeoutExpired:
            logger.error("notify timed out")
            return False
        except Exception as e:
            logger.error(f"notify error: {e}")
            return False

    def send_new_subdomains(self, diff_result, domain):
        """
        Send a formatted notification about newly discovered subdomains.

        Args:
            diff_result: Output from diff.compute_diff()
            domain: The target domain
        """
        from subsentry.diff import format_diff_notify

        message = format_diff_notify(diff_result, domain)
        if message:
            return self.send(message)
        else:
            logger.debug("No new subdomains to notify about")
            return True
