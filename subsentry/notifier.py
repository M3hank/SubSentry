"""Notifier — delivers alerts through native webhooks or ProjectDiscovery's notify.

Native delivery (zero extra binaries):
    * Discord   SUBSENTRY_DISCORD_WEBHOOK
    * Slack     SUBSENTRY_SLACK_WEBHOOK
    * Telegram  SUBSENTRY_TELEGRAM_BOT_TOKEN + SUBSENTRY_TELEGRAM_CHAT_ID
    * Generic   SUBSENTRY_WEBHOOK_URL  (JSON POST)

If ``--provider-config``/``--notify-id`` is supplied the legacy ``notify``
binary is used instead, so existing setups keep working.
"""

from __future__ import annotations

import json
import logging
import subprocess
import urllib.error
import urllib.request

from subsentry import config
from subsentry.utils import Colors, is_tool_installed

logger = logging.getLogger("subsentry")

DISCORD_LIMIT = 1900  # leave room for the "[1/3]" prefix


def _chunk(text, limit=DISCORD_LIMIT):
    """Split a message into chunks without breaking mid-line when possible."""
    if len(text) <= limit:
        return [text]
    chunks, current = [], ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > limit:
            if current:
                chunks.append(current.rstrip("\n"))
            current = line
        else:
            current += line
    if current:
        chunks.append(current.rstrip("\n"))
    return chunks


def _post_json(url, payload, timeout=10, headers=None):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "User-Agent": config.USER_AGENT, **(headers or {})},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return 200 <= resp.status < 300


class Notifier:
    """Sends notifications through the best available transport."""

    def __init__(self, provider_config=None, notify_id=None, webhook=None,
                 kind=None, timeout=10):
        self.provider_config = provider_config
        self.notify_id = notify_id
        self.webhook = webhook
        self.kind = kind
        self.timeout = timeout

    # ── transport selection ───────────────────────────────────────────────

    def detect(self):
        """Return ``(kind, target)`` for the first configured transport."""
        if self.provider_config or self.notify_id:
            return "notify", None
        if self.webhook:
            return "webhook", self.webhook
        if self.kind == "discord" and config.DISCORD_WEBHOOK:
            return "discord", config.DISCORD_WEBHOOK
        if self.kind == "slack" and config.SLACK_WEBHOOK:
            return "slack", config.SLACK_WEBHOOK
        if self.kind == "telegram" and config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
            return "telegram", config.TELEGRAM_BOT_TOKEN
        if config.DISCORD_WEBHOOK:
            return "discord", config.DISCORD_WEBHOOK
        if config.SLACK_WEBHOOK:
            return "slack", config.SLACK_WEBHOOK
        if config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID:
            return "telegram", config.TELEGRAM_BOT_TOKEN
        if config.GENERIC_WEBHOOK:
            return "webhook", config.GENERIC_WEBHOOK
        if is_tool_installed("notify"):
            return "notify", None
        return None, None

    def describe(self):
        kind, _ = self.detect()
        return {
            "kind": kind or "none",
            "available": kind is not None,
            "notify_binary": is_tool_installed("notify"),
        }

    def is_available(self):
        return self.detect()[0] is not None

    # ── sending ───────────────────────────────────────────────────────────

    def send(self, message, subject="SubSentry Alert"):
        """Send a plain-text message through the selected transport."""
        if not message or not message.strip():
            logger.debug("No message to send, skipping notification")
            return True

        kind, target = self.detect()

        if kind is None:
            logger.warning(
                f"{Colors.YELLOW}No notification transport configured.{Colors.RESET} "
                "Set SUBSENTRY_DISCORD_WEBHOOK (or Slack/Telegram/webhook) "
                "or install ProjectDiscovery's notify."
            )
            logger.info("Message that would have been sent:")
            print(message)
            return False

        try:
            if kind == "notify":
                return self._send_notify(message)
            if kind == "discord":
                return self._send_discord(target, message)
            if kind == "slack":
                return self._send_slack(target, message)
            if kind == "telegram":
                return self._send_telegram(message)
            if kind == "webhook":
                return self._send_webhook(target, message, subject)
        except Exception as exc:  # pragma: no cover - network dependent
            logger.error(f"  {Colors.RED}✗{Colors.RESET} notification failed: {exc}")
            return False

        return False

    def _send_notify(self, message):
        cmd = ["notify", "-silent", "-bulk"]
        if self.provider_config:
            cmd.extend(["-provider-config", str(self.provider_config)])
        if self.notify_id:
            cmd.extend(["-id", self.notify_id])

        result = subprocess.run(cmd, input=message, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            logger.info(f"  {Colors.GREEN}✓{Colors.RESET} Notification sent (notify)")
            return True
        logger.error(f"  {Colors.RED}✗{Colors.RESET} notify failed: {result.stderr.strip()}")
        return False

    def _send_discord(self, url, message):
        ok = True
        chunks = _chunk(message)
        for idx, chunk in enumerate(chunks, 1):
            prefix = f"[{idx}/{len(chunks)}]\n" if len(chunks) > 1 else ""
            ok = _post_json(
                url,
                {"content": f"{prefix}{chunk}", "username": "SubSentry"},
                timeout=self.timeout,
            ) and ok
        self._log(ok, "Discord")
        return ok

    def _send_slack(self, url, message):
        ok = _post_json(url, {"text": message}, timeout=self.timeout)
        self._log(ok, "Slack")
        return ok

    def _send_telegram(self, message):
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        ok = True
        for chunk in _chunk(message, limit=4000):
            ok = _post_json(
                url,
                {
                    "chat_id": config.TELEGRAM_CHAT_ID,
                    "text": chunk,
                    "disable_web_page_preview": True,
                },
                timeout=self.timeout,
            ) and ok
        self._log(ok, "Telegram")
        return ok

    def _send_webhook(self, url, message, subject):
        ok = _post_json(
            url,
            {
                "source": "subsentry",
                "subject": subject,
                "text": message,
            },
            timeout=self.timeout,
        )
        self._log(ok, "webhook")
        return ok

    @staticmethod
    def _log(ok, name):
        if ok:
            logger.info(f"  {Colors.GREEN}✓{Colors.RESET} Notification sent ({name})")
        else:
            logger.error(f"  {Colors.RED}✗{Colors.RESET} {name} rejected the message")

    # ── high-level helper ─────────────────────────────────────────────────

    def send_new_subdomains(self, diff_result, domain):
        """Send a formatted notification about newly discovered subdomains."""
        from subsentry.diff import format_diff_notify

        message = format_diff_notify(diff_result, domain)
        if not message:
            logger.debug("No new subdomains to notify about")
            return True
        return self.send(message, subject=f"{domain}: {diff_result.get('new_count', 0)} new subdomain(s)")
