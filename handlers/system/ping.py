# ============================================================
#  handlers/system/ping.py  —  /ping system status
# ============================================================
import os
import platform
import time
from datetime import datetime

import psutil
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from core.logger import get_logger
from helpers.decorators import admin_only
from config import BOT_NAME, BOT_VERSION

router = Router(name="system_ping")
logger = get_logger("System.Ping")


def _bar(pct: float, width: int = 10) -> str:
    filled = int(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)


@router.message(Command("ping"))
@admin_only
async def cmd_ping(message: Message):
    start = time.monotonic()
    sent  = await message.answer("🏓 <b>Pinging...</b>")
    ms    = round((time.monotonic() - start) * 1000, 2)

    # System uptime
    try:
        with open("/proc/uptime") as f:
            sec = float(f.read().split()[0])
        d, rem = divmod(int(sec), 86400)
        h, rem = divmod(rem, 3600)
        m      = rem // 60
        uptime = f"{d}d {h}h {m}m" if d else f"{h}h {m}m"
    except Exception:
        uptime = "N/A"

    # OS name
    try:
        os_name = platform.system()
        if os.path.exists("/etc/os-release"):
            with open("/etc/os-release") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        os_name = line.split("=", 1)[1].strip().strip('"')
                        break
    except Exception:
        os_name = platform.system()

    cpu       = psutil.cpu_percent(interval=0.3)
    ram       = psutil.virtual_memory()
    disk      = psutil.disk_usage("/")
    ram_used  = round(ram.used  / 1024**3, 2)
    ram_total = round(ram.total / 1024**3, 2)
    disk_used = round(disk.used  / 1024**3, 1)
    disk_tot  = round(disk.total / 1024**3, 1)

    text = (
        f"🏓 <b>Pong!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⚡ Response : <b>{ms} ms</b>\n"
        f"🤖 Bot      : <b>{BOT_NAME} v{BOT_VERSION}</b>\n"
        f"🖥 OS       : <b>{os_name}</b>\n"
        f"⏱ Uptime   : <b>{uptime}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔲 CPU  : <b>{cpu}%</b>  <code>[{_bar(cpu)}]</code>\n"
        f"💾 RAM  : <b>{ram_used}/{ram_total} GB</b>  "
        f"<code>[{_bar(ram.percent)}]</code>  ({ram.percent}%)\n"
        f"💿 Disk : <b>{disk_used}/{disk_tot} GB</b>  "
        f"<code>[{_bar(disk.percent)}]</code>  ({disk.percent}%)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🕒 <i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
    )
    await sent.edit_text(text)
