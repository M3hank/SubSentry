<h1 align="center">
  🛡️ SubSentry
</h1>

<p align="center">
  <b>Subdomain Monitoring & Alerting Tool</b><br>
  <i>Continuously watch your targets for new subdomains and get notified on Discord.</i>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="MIT License">
  <img src="https://img.shields.io/badge/platform-linux%20%7C%20macos%20%7C%20windows-lightgrey" alt="Platform">
</p>

---

## 🔍 What is SubSentry?

SubSentry aggregates subdomains from **multiple enumeration tools**, stores a baseline in a local SQLite database, and alerts you on **Discord** (via [ProjectDiscovery's notify](https://github.com/projectdiscovery/notify)) whenever **new subdomains** are discovered.

Perfect for bug bounty hunters and red teamers who need to stay on top of target surface changes.

### Key Features

- 🔄 **Multi-Source Enumeration** — Combines [Subfinder](https://github.com/projectdiscovery/subfinder), [Findomain](https://github.com/Findomain/Findomain), and [Assetfinder](https://github.com/tomnomnom/assetfinder) in parallel
- 📊 **Baseline Tracking** — SQLite database stores known subdomains with timestamps and source attribution
- 🆕 **Diff Detection** — Compares each scan against the baseline to find new subdomains
- 🔔 **Discord Notifications** — Pipes alerts through `notify` for instant Discord messages
- 📈 **Scan History** — Full audit trail of every scan with stats
---

## 📦 Installation

### Prerequisites

Install the enumeration tools (need at least one, but more = better coverage):

```bash
# Subfinder (ProjectDiscovery)
go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest

# Findomain
Download from: https://github.com/Findomain/Findomain/releases

# Assetfinder (tomnomnom)
go install github.com/tomnomnom/assetfinder@latest

# Notify (ProjectDiscovery) — for Discord alerts
go install -v github.com/projectdiscovery/notify/cmd/notify@latest
```

### Install SubSentry

```bash
git clone https://github.com/subsentry/subsentry.git
cd subsentry
pip install -e .
```

---

## 🚀 Usage

### 1. Initialize Baseline

```bash
subsentry init example.com
```

This runs all available tools, collects subdomains, deduplicates them, and stores the result as your baseline.

### 2. Scan for New Subdomains

```bash
subsentry scan example.com --notify
```

```
  → Scanning example.com (baseline: 142 subdomains)

  Running 3 sources: subfinder, findomain, assetfinder
  ✓ subfinder: 98 subdomains
  ✓ findomain: 112 subdomains
  ✓ assetfinder: 87 subdomains
  Total unique: 145 subdomains

  ── Scan Results for example.com ──

  Baseline: 142  |  Current: 145  |  New: 3  |  Gone: 0

  ▶ New Subdomains (3)
    + staging-api.example.com
    + internal-dashboard.example.com
    + dev-payments.example.com

  ✓ Notification sent successfully
```

### 3. Continuous Monitoring

```bash
# Monitor every hour (default)
subsentry monitor example.com --notify

# Monitor every 5 minutes
subsentry monitor example.com --notify --interval 300
```

### 4. View Known Subdomains

```bash
# Table format
subsentry list example.com

# JSON output (for piping to other tools)
subsentry list example.com --json
```

### 5. View Scan History

```bash
subsentry history example.com
```

---

## 🔔 Discord Notification Setup

### 1. Create a Discord Webhook

1. Go to your Discord server → **Channel Settings** → **Integrations** → **Webhooks**
2. Click **New Webhook** → Copy the webhook URL

### 2. Configure Notify

Create `~/.config/notify/provider-config.yaml`:

```yaml
discord:
  - id: "subsentry"
    discord_channel: "recon-alerts"
    discord_username: "SubSentry"
    discord_format: "{{data}}"
    discord_webhook_url: "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN"
```

### 3. Use with SubSentry

```bash
# Uses default notify config
subsentry scan example.com --notify

# Use specific provider ID
subsentry scan example.com --notify --notify-id subsentry

# Use custom config path
subsentry scan example.com --notify --provider-config /path/to/config.yaml
```



## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

