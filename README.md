# SubSentry

> A professional-grade subdomain monitoring and alerting engine. Keep a constant watch on your attack surface and receive instant Discord notifications when new assets appear.

---

## Overview

SubSentry is a powerful utility designed for security researchers and bug bounty hunters. It streamlines the reconnaissance process by aggregating data from top-tier enumeration tools, maintaining a historical baseline in a local SQLite database, and alerting you the moment a change is detected.

## Core Features

*   **Integrated Enumeration**: Harnesses the combined power of Subfinder, Findomain, and Assetfinder.
*   **Persistent Baselines**: Automatically tracks known subdomains in a SQLite database with detailed timestamps.
*   **Delta Detection**: Intelligent scanning identifies new discoveries and tracks disappearing assets.
*   **Instant Alerting**: Delivers real-time notifications to Discord via ProjectDiscovery's `notify` tool.
*   **Audit Trail**: Maintains a complete history of every scan performed with associated statistics.

---

## Getting Started

### Prerequisites

You should have at least one of these enumeration tools installed on your system for maximum coverage:

```bash
# Install Subfinder
go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest

# Install Assetfinder
go install github.com/tomnomnom/assetfinder@latest

# Install Notify for Discord alerts
go install -v github.com/projectdiscovery/notify/cmd/notify@latest
```

*Note: Findomain can be downloaded directly from its [official releases](https://github.com/Findomain/Findomain/releases).*

### Installation

Clone the repository and install the package using pip:

```bash
git clone https://github.com/subsentry/subsentry.git
cd subsentry
pip install -e .
```

---

## Usage Guide

### Initialize Your Target

Establish your first baseline of known subdomains:

```bash
subsentry init example.com
```

### Run a Delta Scan

Scan for new subdomains and compare them against your baseline:

```bash
subsentry scan example.com --notify
```

### Automated Monitoring

Set up continuous monitoring to run at specific intervals:

```bash
# Monitor every hour (default)
subsentry monitor example.com --notify

# Monitor with a custom 5-minute interval
subsentry monitor example.com --notify --interval 300
```

### Data Management

Interact with your stored results:

```bash
# List all known subdomains for a domain
subsentry list example.com

# Export results as JSON
subsentry list example.com --json

# View full scan history and statistics
subsentry history example.com
```

---

## Discord Notifications

SubSentry leverages the `notify` utility for modular alerting.

### 1. Webhook Setup

1. Open your Discord server settings.
2. Navigate to **Integrations** and select **Webhooks**.
3. Create a **New Webhook** and copy the URL.

### 2. Configuration

Create or update your configuration file at `~/.config/notify/provider-config.yaml`:

```yaml
discord:
  - id: "subsentry"
    discord_channel: "recon-alerts"
    discord_username: "SubSentry"
    discord_format: "{{data}}"
    discord_webhook_url: "YOUR_DISCORD_WEBHOOK_URL_HERE"
```

### 3. Execution

```bash
# Start scanning with notifications enabled
subsentry scan example.com --notify
```

---

## License

This project is released under the MIT License. Please see the [LICENSE](LICENSE) file for more information.
