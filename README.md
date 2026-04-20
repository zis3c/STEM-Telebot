# Eligible STEM Bot

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Telegram](https://img.shields.io/badge/Telegram-Bot-26A5E4?logo=telegram&logoColor=white)
![PTB](https://img.shields.io/badge/python--telegram--bot-v20%2B-2AABEE)
![aiohttp](https://img.shields.io/badge/aiohttp-Async%20HTTP-005571)
![gspread](https://img.shields.io/badge/gspread-Sheets%20API-4285F4?logo=google-sheets&logoColor=white)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)
![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-brightgreen.svg)

A high-performance, bilingual Telegram bot designed to automate membership verification, register new members with automated ID generation, and provide a robust administrative dashboard for student organizations.

> [!NOTE]
> **Data Integrity**: This bot uses Google Sheets as its primary database. It features an automated status-tracking system to prevent duplicate registrations and ensure real-time synchronization between the bot and your organization's records.

## Features

- **Multi-lingual Support**: Full support for both English and Bahasa Melayu (Toggle via `/settings`).
- **Instant Verification**: Real-time membership status checks via Matric Number and IC.
- **Automated Registration**:
  - Auto-generation of USAS format emails and Membership IDs (`STEM(YY/YY)XXXX`).
  - Automatic session calculation based on date of entry.
  - Automated PDF receipt delivery via email (hosted on Google Drive).
- **Comprehensive Admin Dashboard**:
  - Search members with Simple (List) or Detailed (Card UI) views.
  - Approve/Reject registrations and manage members.
  - Global broadcast system with deduplication logic.
  - Monthly growth statistics and system health monitoring.
- **Superadmin Controls**:
  - Global maintenance mode toggle.
  - Admin permission management.
  - Robust activity logging with daily automated reports.
- **Async Architecture**: Built with `asyncio` and `python-telegram-bot` v20+ for high concurrency (100+ requests).

## Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/zis3c/STEM-Telebot.git
   cd STEM-Telebot
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv .venv
   # Windows PowerShell
   .\.venv\Scripts\Activate.ps1
   # Linux/macOS
   # source .venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment**
   ```bash
   copy .env.example .env   # Windows
   # cp .env.example .env   # Linux/macOS
   ```

5. **Setup Google Cloud**
   - Place your `service_account.json` in the project root or configure the `GOOGLE_CREDENTIALS` env var.
   - Share your Google Sheet with the Service Account email.

6. **Run bot**
   ```bash
   python bot.py
   ```

## Environment Variables

**Core:**
- `TELEGRAM_TOKEN` - Bot token from [@BotFather](https://t.me/BotFather)
- `PORT` - Local health endpoint port (default `10000`)
- `WEBHOOK_URL` - Optional for webhook mode (leave empty for polling)

**Google Sheets:**
- `SHEET_ID` - The unique ID of your Google Spreadsheet
- `GOOGLE_CREDENTIALS` - Optional JSON string of your service account key

**Access Control:**
- `SUPERADMIN_IDS` - Comma-separated Telegram IDs of Superadmins
- `ADMIN_IDS` - Comma-separated Telegram IDs of regular Admins

## Deploy to DigitalOcean (Recommended)

This project is currently deployed on a DigitalOcean Droplet using polling + `systemd`.

1. Clone the repo on the droplet into `/opt/stem-telebot`.
2. Set up the virtual environment and install dependencies.
3. Configure the `.env` file and `service_account.json`.
4. Create a systemd service file:
   - `WorkingDirectory=/opt/stem-telebot`
   - `ExecStart=/opt/stem-telebot/.venv/bin/python /opt/stem-telebot/bot.py`
5. Enable service:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now stem-telebot
   ```

## Auto Deploy (GitHub Actions)

This repository includes `.github/workflows/deploy-digitalocean.yml`.
Every push to `main` triggers automatic deployment to the droplet.
For full setup and troubleshooting, see [AUTO_DEPLOY.md](AUTO_DEPLOY.md).

Required repository secrets:
- `DROPLET_HOST` (example: `203.0.113.10`)
- `DROPLET_USER` (recommended: `deploy`)
- `DROPLET_SSH_KEY` (private SSH key for the deploy user)

Server assumptions:
- App path: `/opt/stem-telebot`
- Service name: `stem-telebot`
- Deploy user can run `sudo systemctl restart stem-telebot`

## Project Structure

```text
STEM-Telebot/
├── bot.py                # Main entrypoint and scheduler bootstrap
├── handlers.py           # Core user registration and verification flows
├── admin.py              # Admin dashboard and member management
├── superadmin.py         # System settings and maintenance controls
├── database.py           # Google Sheets API wrapper and local cache
├── keyboards.py          # Dynamic UI/Keyboard layouts
├── strings.py            # Multi-language string repository (EN/MS)
├── states.py             # Conversation state constants
├── google_apps_script.js # Script for Google Sheets automated logic
├── LICENSE               # MIT License
└── requirements.txt      # Project dependencies
```

## Commands

| Command | Description |
|:--------|:------------|
| `/start` | Open main menu |
| `/help` | Show usage and guidance |
| `/settings` | Open language/settings menu |
| `/check_pending` | Manually trigger pending registration check |
| `/admin` | Open Admin Dashboard (Admins only) |
| `/superadmin` | Open Superadmin Panel (Superadmins only) |
| `/cancel` | Exit current conversation flow |

## How It Works

1. **User Interaction**: Users start the bot and select their language.
2. **Verification**: If checking membership, the bot queries the `Registrations` sheet for a Matric/IC match.
3. **Registration**: New users submit details and payment proof; data is pushed to Google Sheets with `Pending` status.
4. **Automation**: Google Apps Script automatically generates Membership IDs and formats and dates.
5. **Approval**: Admins review members via the `/admin` menu; approving a member triggers the "Success" flow.
6. **Logging**: All actions are logged to `activity.log` and reported daily to Superadmins.

## Troubleshooting

- **Bot not responding**: Verify `TELEGRAM_TOKEN` and check if the process is running via `ps aux`.
- **Sheet access denied**: Ensure the Service Account email has "Editor" permissions on the spreadsheet.
- **Maintenance Mode**: Check if a Superadmin has enabled maintenance mode via `/superadmin`.
- **Missing IDs**: Ensure the `google_apps_script.js` is correctly installed in your spreadsheet.

## Additional Docs

- [AUTO_DEPLOY.md](AUTO_DEPLOY.md)
- [INSTALLATION.md](INSTALLATION.md)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [SECURITY.md](SECURITY.md)
- [LICENSE](LICENSE)

<center>Built with 🔥 by <b>@zis3c</b></center>
