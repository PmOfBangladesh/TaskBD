# 🤖 TaskBD Bot v2.0

> **Async Telegram Bot** — Account management system for workers  
> Built with **Aiogram 3.x** | Python 3.11+ | Fully async

---

## 📁 Project Structure

```
TaskBD/
├── main.py              # Entry point — registers all 4 top-level routers
├── config.py            # All settings (.env reader)
├── .env                 # Secrets (never commit)
│
├── core/
│   ├── bot.py           # Bot + Dispatcher singletons
│   ├── database.py      # All JSON/CSV I/O (async-safe)
│   ├── logger.py        # Multi-file structured logging
│   ├── state.py         # All FSM state groups
│   └── constants.py     # Static strings & emoji maps
│
├── handlers/
│   ├── admin/           # Admin panel (split by responsibility)
│   │   ├── panel.py         # /admin command & keyboard
│   │   ├── licenses.py      # License gen & check FSM
│   │   ├── reports.py       # Final report & 2FA report FSM
│   │   ├── stats.py         # Live stats, all-time stats, reset
│   │   ├── users.py         # Add balance & delete user FSM
│   │   ├── maintenance.py   # Spam list, ban/unban, XLSX exports
│   │   ├── broadcast.py     # Broadcast to all users
│   │   └── pricing.py       # Price list view & edit
│   │
│   ├── user/            # User-facing handlers
│   │   ├── start.py         # /start, license key, main menu
│   │   ├── profile.py       # Profile view & payment change
│   │   ├── stats.py         # Live stats & 2FA stats
│   │   └── withdraw.py      # Withdraw request flow
│   │
│   ├── callbacks/       # Payment screenshot & dispatch flow
│   │   └── payment.py
│   │
│   └── system/          # System diagnostics
│       ├── ping.py          # /ping — server status
│       ├── speedtest.py     # /speedtest
│       ├── restart.py       # /restart
│       └── logs.py          # /logs — paginated log viewer
│
├── modules/
│   ├── stats_manager.py    # Live stats page builder
│   ├── report_builder.py   # Final report calculation
│   ├── log_viewer.py       # Log pagination & formatting
│   ├── link_watcher.py     # URL monitor (extensible)
│   └── spam_detector.py    # Rate-limit & ban tracker
│
├── helpers/
│   ├── utils.py            # Channel check, admin notify
│   ├── decorators.py       # admin_only, spam_guard, private_only
│   ├── formatter.py        # Message formatters
│   ├── xlsx_builder.py     # XLSX generation
│   └── validators.py       # Input validators
│
├── data/                # JSON storage (auto-created)
├── users/               # Per-user stat files
├── logs/                # Rotating log files
└── exports/             # Report exports
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
