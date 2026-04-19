# Eligible STEM Bot 🚀

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Status: Active](https://img.shields.io/badge/Status-Active-success.svg)]()
![Platform: Telegram](https://img.shields.io/badge/Platform-Telegram-blue)

A high-performance, bilingual **Telegram Bot** designed to streamline membership verification and management for student organizations. Built for speed, security, and scalability.

## ✨ Features

- **Instant Verification**: Checks student membership status via Matric Number & IC.
- **Automated Registration**:
  - Auto-generates **USAS Email**.
  - Auto-generates **Membership ID** (`STEM(YY/YY)XXXX`).
  - Auto-calculates **Session** based on Date of Entry.
  - **Payment Receipts**: Auto-sends PDF receipts via Email (Hosted on Drive).
- **Admin Dashboard**:
  - Manage Admins & Members.
  - **Detailed View**: View Status, Proof, Invoice ID, and Receipt Link.
  - Approve/Reject new registrations.
  - Broadcast messages to all users.
  - View Monthly Statistics.
*   **🛡️ Robust Admin System**:
    *   **Dashboard**: Search (Simple/Detail Views), Add/Delete Members, and Broadcast.
    *   **Advanced Search**: Toggle between **Simple View** (List) and **Detailed View** (Card UI) with full column data.
    *   **Superadmin Control**: Manage other admins, toggle Maintenance Mode, and monitor system health.
*   **📊 Google Sheets Backend**: Uses Google Sheets as a database types.
    *   **Auto-Status**: Bot marks new registrations as '✓' (Seen) to prevent duplicates.
*   **🚀 High Concurrency**: Optimized with `asyncio` and threaded logging to handle 100+ concurrent requests.

---

## 🛠️ Tech Stack

*   **Framework**: [python-telegram-bot (v20+)](https://github.com/python-telegram-bot/python-telegram-bot)
*   **Database**: Google Sheets API via [gspread](https://github.com/burnash/gspread)
*   **Automation**: [Google Apps Script](https://developers.google.com/apps-script) (for server-side sheet logic)
*   **Concurrency**: Python `asyncio` & `threading`
*   **Deployment**: Optimized for DigitalOcean Droplet (polling + systemd)

---

## 🚀 Getting Started

### Prerequisites

1.  Python 3.9+
2.  A Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
3.  Google Cloud Service Account (for Sheets API)

### 📥 Installation

> **[📖 Click here for the DETAILED INSTALLATION GUIDE (Step-by-Step)](INSTALLATION.md)**

For a quick setup:

1.  **Clone the repository**
    ```bash
    git clone https://github.com/zis3c/STEM-Telebot.git
    cd STEM-Telebot
    ```

2.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Setup Environment Variables**
    Create a `.env` file in the root directory:
    ```ini
    TELEGRAM_TOKEN=your_bot_token_here
    SHEET_ID=your_google_sheet_id
    GOOGLE_CREDENTIALS={"type": "service_account", ...} # JSON string
    SUPERADMIN_IDS=123456789,987654321
    ADMIN_IDS=123456789
    ```

4.  **Setup Google Sheets**
    *   Share your Google Sheet with the Service Account Email.
    *   Ensure tabs named: `Registrations`, `system_admins`, `system_config`.
    *   **Structure for `Registrations` Sheet** (Important!):
      
        | Col | Field | Col | Field |
        | :--- | :--- | :--- | :--- |
        | **A** | Timestamp | **L** | Birth Place |
        | **B** | Email | **M** | Address |
        | **C** | Name | **N** | Date of Entry |
        | **D** | Matric | **O** | Minute No |
        | **E** | Courses | **P** | Membership ID |
        | **F** | Semester | **Q** | Receipt Proof |
        | **G** | Phone | **R** | Status |
        | **H** | Personal Email | **S** | Payment Receipt |
        | **I** | USAS Email | **T** | Invoice No |
        | **J** | IC No | **U** | Statistic |
        | **K** | Birthday | | |

### ▶️ Running Locally (Polling Mode)

```bash
python bot.py
```

---

## Deployment (DigitalOcean Droplet)

This bot is deployed on a DigitalOcean Droplet using polling mode with `systemd`.

1.  **Prepare server packages**
    ```bash
    sudo apt update
    sudo apt install -y git python3 python3-venv python3-pip
    ```
2.  **Clone and install**
    ```bash
    git clone https://github.com/zis3c/STEM-Telebot.git
    cd STEM-Telebot
    python3 -m venv .venv
    . .venv/bin/activate
    pip install -r requirements.txt
    ```
3.  **Configure secrets**
    * Create `.env` in project root with:
      `TELEGRAM_TOKEN`, `SHEET_ID`, `SUPERADMIN_IDS`, `ADMIN_IDS`.
    * Place `service_account.json` in project root.
4.  **Run as system service**
    * Create `/etc/systemd/system/stem-telebot.service`
      with `ExecStart=/path/to/STEM-Telebot/.venv/bin/python /path/to/STEM-Telebot/bot.py`.
    * Enable and start:
      ```bash
      sudo systemctl daemon-reload
      sudo systemctl enable --now stem-telebot
      ```

Deployment target: DigitalOcean Droplet (`systemd` + polling) is the maintained production setup.

---

## Auto Deploy (GitHub Actions)

This repository includes `.github/workflows/deploy-digitalocean.yml`.
Every push to `main` triggers automatic deployment to the droplet.

Required repository secrets:
- `DROPLET_HOST` (example: `203.0.113.10`)
- `DROPLET_USER` (recommended: `deploy`)
- `DROPLET_SSH_KEY` (private SSH key for the deploy user)

Server assumptions:
- App path: `/opt/stem-telebot`
- Service name: `stem-telebot`
- Deploy user can run `sudo systemctl restart stem-telebot`

---
## 📜 System Activity Logging

1.  **Global User Tracking**: Logs **every** interaction (text, buttons, stickers, media) for all users.
2.  **Keyboard Logic**: Detects and labels specific button clicks (e.g., "Check Membership") for easier auditing.
3.  **Detailed Auditing**: Explicitly logs results of sensitive actions (Membership checks, Language changes, Registrations).
4.  **Admin Audit**: Logs administrative actions (Add/Delete Member, Broadcast).
5.  **Deduplicated User List**: Ensures broadcasts are sent only to unique users, preventing spam.
6.  **Auto-Cleanup & Reporting**:
    *   Logs are stored locally in `activity.log`.
    *   Every day at **00:00 UTC**, the bot sends the log file to Superadmins and **clears it** to maintain performance.

## 🔒 Security

*   **Role-Based Access**: Strict separation between Users, Admins, and Superadmins.
*   **Secure Logging**: Audit logs for all users actions.
*   **Credential Protection**: `.gitignore` configured to prevent leaking secrets.

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1.  Fork the project
2.  Create your feature branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<center>Built with ❤️ by <b>@zis3c</b></center>
