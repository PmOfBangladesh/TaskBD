# 🤖 TaskBD Bot v2.0

> **Async Telegram Bot** — Account management system for workers  
> Built with **Aiogram 3.x** | Python 3.11+ | Fully async

---

## 📁 Project Structure

```
TaskBD/
├── main.py              # Entry point
├── config.py            # All settings (.env reader)
├── .env                 # Secrets (never commit)
│
├── core/
│   ├── bot.py
│   ├── database.py
│   ├── logger.py
│   ├── state.py
│   └── constants.py
│
├── handlers/
│   ├── user.py
│   ├── admin.py
│   ├── callbacks.py
│   ├── broadcast.py
│   ├── system.py
│   └── pricelist.py
│
├── modules/
│   ├── stats_manager.py
│   ├── report_builder.py
│   ├── log_viewer.py
│   ├── link_watcher.py
│   └── spam_detector.py
│
├── helpers/
│   ├── utils.py
│   ├── decorators.py
│   ├── formatter.py
│   ├── xlsx_builder.py
│   └── validators.py
│
├── data/
├── users/
├── logs/
└── exports/
```

---

## ⚡ Setup

```bash
# Clone repo
git clone https://github.com/PmOfBangladesh/TaskBD
cd TaskBD

# Create virtualenv
python3.11 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
nano .env

# Run bot
python main.py
```

---

## ⚙️ Systemd Service (Root User)

```ini
[Unit]
Description=TaskBD Bot
After=network.target

[Service]
WorkingDirectory=/root/TaskBD
ExecStart=/root/TaskBD/venv/bin/python main.py
Restart=always
RestartSec=5
User=root

[Install]
WantedBy=multi-user.target
```

---

## 🛡️ Admin Commands

| Command | Description |
|--------|------------|
| `/admin` | Open admin panel |
| `/live` | Live user stats |
| `/resetstats` | Reset stats |
| `/ping` | Server status |
| `/speedtest` | Network speed |
| `/logs` | View logs |
| `/broadcast` | Send message |
| `/ban <id>` | Ban user |
| `/unban <id>` | Unban user |
| `/restart` | Restart bot |
| `/pricelist` | Edit/view prices |

---

## 👤 User Commands

| Command | Description |
|--------|------------|
| `/start` | Start bot |
| `/pricelist` | View prices |

---

## 🚫 Spam Protection

- 8 messages / 10 sec → auto ban (30 min)
- Persistent ban system
- Admin bypass enabled

---

## 📊 License Format

```
SML-XXXXXX
MENTOR-SML-XXXXXX
```

---

## 📌 Notes

- Use `.env` for all secrets
- Never upload `data/` or `.env` to GitHub
- Logs auto-rotate

---

## 👑 Credits

**Developer:** @codeninjaxd  
**Project:** TaskBD Bot
