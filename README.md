# Eligible STEM Bot

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?logo=telegram&logoColor=white)
![PTB](https://img.shields.io/badge/python--telegram--bot-v20%2B-2AABEE)
![aiohttp](https://img.shields.io/badge/aiohttp-Async%20HTTP-005571)
![gspread](https://img.shields.io/badge/gspread-Sheets%20API-4285F4?logo=google-sheets&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)
![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-brightgreen.svg)

A high-performance, bilingual automation ecosystem for student organizations. Built for speed, security, and scalability, this bot handles everything from membership verification and registration to system health monitoring and global administrative auditing.

> [!NOTE]
> **Hybrid Database Architecture**: This bot utilizes a highly optimized hybrid approach, using Google Sheets as a low-code database for organization managers while implementing a local thread-safe config cache and asynchronous logging for production-grade responsiveness.

## Features & Functionality

### 👤 User Experience
- **Bilingual Interface**: Seamlessly switch between English and Bahasa Melayu (Persistence handled via `user_data`).
- **Secure 2-Step Verification**: Real-time cross-referencing of Matric Number and the last 4 digits of IC against the organization registry.
- **Automated Metadata Engine**:
  - Instant generation of formatted IDs (e.g., `STEM(24/25)0123`).
  - Auto-calculation of academic sessions based on raw entry timestamps.
  - Success notifications with automated PDF receipt delivery via email (integrated with Google Drive).
- **Interactive Help System**: Inline callback queries for "How it Works" guides without cluttering the chat history.

### 🛡️ Administrative Dashboard (`/admin`)
- **Member Lifecycle Management**: List, Detail-Search, and Delete members directly from Telegram.
- **Advanced Search UI**: Toggle between **Simple View** (ID/Matric cards) and **Detailed View** (Full member profile including evidence links, phone numbers, and addresses).
- **Real-Time Registration Alerts**: Background jobs scan for new entries and notify admins immediately, implementing a "Seen" tag system (`✓`) to prevent multi-admin processing overlap.
- **Intelligent Broadcasting**: Global message delivery with deduplication logic, retry handling, and delivery success/failure reporting.
- **Live Metrics**: Instant statistics on total membership and registration trends.

### 👑 Superadmin Control Center (`/superadmin`)
- **System Maintenance**: Global toggle to lock the bot interface during updates, with prioritized access for admins.
- **System Health Dashboard**: Real-time monitoring of CPU usage, RAM utilization, and Service Uptime using `psutil`.
- **RBAC Management**: Dynamically add or remove secondary admins via the bot interface, synced to Google Sheets.
- **Log Management**: On-demand activity log retrieval and automated daily rotation with reporting to Superadmins at 00:00 UTC.
- **Hot-Reload Config**: Synchronize system settings and admin lists from Google Sheets without restarting the service.

### ⚙️ System Integrity
- **Async IO (AIO)**: Non-blocking handlers for all network and database operations to maintain responsiveness under high load.
- **Anomaly Detection Logging**: Logs all interactions (including non-text like stickers/media) for security auditing and usage analysis.
- **Self-Healing Cron**: Maintenance loops that automatically recover stale connections and ensure daily tasks are executed even after service downtime.

---

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/zis3c/STEM-Telebot.git
   cd STEM-Telebot
   ```

2. **Initialize Environment**
   ```bash
   python -m venv .venv
   # Windows
   .\.venv\Scripts\Activate.ps1
   # Linux/macOS
   source .venv/bin/activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Credential Setup**
   - Rename `.env.example` to `.env` and fill the variables.
   - Place your Google Cloud `service_account.json` in the root directory.

5. **Execute**
   ```bash
   python bot.py
   ```

---

## Environment Variables

| Variable | Category | Description |
| :--- | :--- | :--- |
| `TELEGRAM_TOKEN` | **Core** | Official API token from @BotFather. |
| `SHEET_ID` | **Sheets** | Unique ID found in your Google Spreadsheet URL. |
| `GOOGLE_CREDENTIALS` | **Sheets** | (Optional) Full JSON key string for cloud-native deployment. |
| `SUPERADMIN_IDS` | **Access** | CSV of Telegram User IDs for system-level controllers. |
| `ADMIN_IDS` | **Access** | CSV of Telegram User IDs for regional/club managers. |
| `PORT` | **Runtime** | Local port for health routes (Webhooks/Healthchecks). |
| `WEBHOOK_URL` | **Runtime** | Required only if running in Webhook mode. |

---

## 🛠️ Production Deployment (DigitalOcean)

### Systemd Service Configuration
We recommend running as a background service for 99.9% uptime. Create `/etc/systemd/system/stem-telebot.service`:

```ini
[Unit]
Description=Eligible STEM Bot Service
After=network.target

[Service]
User=deploy
Group=deploy
WorkingDirectory=/opt/stem-telebot
EnvironmentFile=/opt/stem-telebot/.env
ExecStart=/opt/stem-telebot/.venv/bin/python bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### GitHub Actions Auto-Deploy
Every push to `main` triggers `.github/workflows/deploy-digitalocean.yml`, which:
1. SSHs into the Droplet.
2. Pulls latest changes and updates dependencies.
3. Restarts the systemd service.
4. Verifies service health via the `/health` endpoint.

---

## 📂 Project Structure

```text
STEM-Telebot/
├── bot.py                # Application entrypoint, Webhook/Polling bootstrap & Health routes
├── handlers.py           # Core logic: User workflows, Keyword navigation & Background Jobs
├── admin.py              # Admin Dashboard implementation (Search, Manage, Broadcast)
├── superadmin.py         # System level controls (Health, Maintenance, RBAC)
├── database.py           # Gspread API wrapper, Config caching & Thread-safe Logging
├── keyboards.py          # Centralized UI Factory for multi-lingual dynamic menus
├── strings.py            # Internationalization (EN/MS) & Content Repository
├── states.py             # FSM (Finite State Machine) constants for conversation flows
├── activity.log          # Runtime interaction logs (Rotated daily)
├── .env.example          # Template for environment secrets
├── requirements.txt      # Python package dependencies
├── google_apps_script.js # Apps Script for automated Row/ID/Date logic in Sheets
├── INSTALLATION.md       # Comprehensive setup guide
└── AUTO_DEPLOY.md        # Detailed CI/CD documentation
```

---

## ⌨️ Command Reference

| Command | Scope | Description |
| :--- | :--- | :--- |
| `/start` | Public | Launch the bot and open main menu |
| `/help` | Public | Open interactive guidance system |
| `/settings` | Public | Configure language and user preferences |
| `/admin` | Admin | Open Administrative Dashboard |
| `/superadmin` | Superadmin | Open System Control Panel |
| `/check_pending` | Admin | Force scan for new registrations |
| `/cancel` | Multi-role | Reset current conversation FSM state |

---

## 🔄 How It Works: Under the Hood

### 1. The Verification Lifecycle
When a user initiates `/check`, the bot enters an FSM (Finite State Machine). It validates the **Matric Number** format via Regex, then requests the **IC last 4 digits**. `database.py` executes a threaded search in Google Sheets using a local cache to minimize API latency.

### 2. Approval & ID Generation
New registrations are picked up by the `check_registrations` job queue. This job marks the row as `✓` in Google Sheets to prevent race conditions. When an admin approves, the `google_apps_script.js` handles the complex ID generation logic within the sheet environment, which the bot then reads to notify the user.

### 3. Log Rotation & Security
The `MessageHandler(filters.ALL, ...)` in `bot.py` ensures every interaction is audited. Every 24 hours, the `maintenance_loop` performs a log rotation, packaging the day's activity into a CSV and delivering it to the Superadmins before clearing the local buffer.

---

## 🆘 Troubleshooting

- **"Sheet Access Denied"**: Verify the Service Account email has **Editor** permissions on the Spreadsheet.
- **"Bot is Unresponsive"**: Check `ps aux | grep bot.py`. If on DigitalOcean, run `journalctl -u stem-telebot -f`.
- **"ID Generation Stuck"**: Ensure the **Apps Script Trigger** (setupTrigger) is active in the Google Sheet's script editor.
- **"Admin Unauthorized"**: Ensure your Telegram ID is added to `ADMIN_IDS` in `.env` OR added via `/superadmin` menu.

---

<div align="center">

Built with 🔥 by **[@zis3c](https://github.com/zis3c)**  
*Empowering Student Communities through Intelligent Automation*

[Report Bug](https://github.com/zis3c/STEM-Telebot/issues) • [Request Feature](https://github.com/zis3c/STEM-Telebot/issues)

</div>
