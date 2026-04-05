# ============================================================
#  handlers/system.py  —  /ping /speedtest /restart /logs
# ============================================================
import os
import sys
import time
import shutil
import platform
import asyncio
import subprocess
from datetime import datetime

import psutil
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile

from core.bot import bot
from core.logger import get_logger
from helpers.decorators import admin_only
from modules.log_viewer import (
    build_log_pages, log_markup, clean_old_logs, LOG_FILE
)
from config import BOT_VERSION, BOT_NAME, LOGS_DIR

router = get_logger  # just to import cleanly
logger = get_logger("System")
router = Router(name="system")

# per-chat log session cache
_log_sessions: dict[int, list[str]] = {}


# ──────────────────────────────────────────────
#  /ping  —  Pro template style
# ──────────────────────────────────────────────

@router.message(Command("ping"))
@admin_only
async def cmd_ping(message: Message):
    start = time.monotonic()
    sent  = await message.answer("🏓 <b>Pinging...</b>")
    ms    = round((time.monotonic() - start) * 1000, 2)

    # Uptime
    try:
        with open("/proc/uptime") as f:
            sec  = float(f.read().split()[0])
        d, rem   = divmod(int(sec), 86400)
        h, rem   = divmod(rem, 3600)
        m        = rem // 60
        uptime   = f"{d}d {h}h {m}m" if d else f"{h}h {m}m"
    except Exception:
        uptime = "N/A"

    # OS
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

    # CPU / RAM / Disk
    cpu        = psutil.cpu_percent(interval=0.3)
    ram        = psutil.virtual_memory()
    disk       = psutil.disk_usage("/")
    ram_used   = round(ram.used  / 1024**3, 2)
    ram_total  = round(ram.total / 1024**3, 2)
    disk_used  = round(disk.used  / 1024**3, 1)
    disk_total = round(disk.total / 1024**3, 1)

    # CPU bar
    def _bar(pct: float, width: int = 10) -> str:
        filled = int(pct / 100 * width)
        return "█" * filled + "░" * (width - filled)

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
        f"💿 Disk : <b>{disk_used}/{disk_total} GB</b>  "
        f"<code>[{_bar(disk.percent)}]</code>  ({disk.percent}%)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🕒 <i>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
    )
    await sent.edit_text(text)


# ──────────────────────────────────────────────
#  /speedtest
# ──────────────────────────────────────────────

@router.message(Command("speedtest"))
@admin_only
async def cmd_speedtest(message: Message):
    sent = await message.answer("🚀 <b>Running speed test…</b>\n<i>~30 seconds</i>")
    try:
        cli = shutil.which("speedtest-cli") or shutil.which("speedtest")
        if not cli:
            raise FileNotFoundError("speedtest-cli not found")

        proc = await asyncio.create_subprocess_exec(
            cli, "--simple", "--single",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=90)
        output    = stdout.decode().strip()

        ping = dl = ul = "N/A"
        for line in output.splitlines():
            if line.startswith("Ping:"):     ping = line.replace("Ping:", "").strip()
            elif line.startswith("Download:"): dl   = line.replace("Download:", "").strip()
            elif line.startswith("Upload:"):   ul   = line.replace("Upload:", "").strip()

        text = (
            f"🚀 <b>Speed Test Result</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🏓 Ping     : <b>{ping}</b>\n"
            f"⬇️ Download : <b>{dl}</b>\n"
            f"⬆️ Upload   : <b>{ul}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🕒 <i>{datetime.now().strftime('%Y-%m-%d %H:%M')}</i>"
        )
    except FileNotFoundError:
        text = (
            "⚠️ <b>speedtest-cli not installed!</b>\n"
            "<code>pip install speedtest-cli</code>"
        )
    except asyncio.TimeoutError:
        text = "⏰ <b>Speedtest timed out (&gt;90s)</b>"
    except Exception as e:
        text = f"❌ <b>Error:</b> <code>{e}</code>"

    await sent.edit_text(text)


# ──────────────────────────────────────────────
#  /restart
# ──────────────────────────────────────────────

@router.message(Command("restart"))
@admin_only
async def cmd_restart(message: Message):
    await message.answer("🔄 <b>Restarting bot…</b>")
    logger.info(f"Restart triggered by admin {message.from_user.id}")
    os.execv(sys.executable, [sys.executable] + sys.argv)


# ──────────────────────────────────────────────
#  /logs
# ──────────────────────────────────────────────

@router.message(Command("logs"))
@admin_only
async def cmd_logs(message: Message):
    chat_id = message.chat.id
    removed = clean_old_logs()

    if not os.path.exists(LOG_FILE):
        await message.answer("⚠️ No log file found.")
        return

    with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    if not lines:
        await message.answer("⚠️ Log file is empty.")
        return

    pages                    = build_log_pages(lines)
    _log_sessions[chat_id]   = pages
    last                     = len(pages) - 1
    note = f"\n🗑 <i>Auto-cleaned {removed} old entries</i>" if removed else ""
    await message.answer(pages[last] + note, reply_markup=log_markup(last, len(pages)))


# ──────────────────────────────────────────────
#  Log callbacks
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("log_"))
async def handle_log_cb(call: CallbackQuery):
    from config import ADMIN_IDS
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Access Denied!", show_alert=True)
        return

    chat_id = call.message.chat.id
    data    = call.data

    if data == "log_noop":
        await call.answer()

    elif data == "log_close":
        await call.answer()
        await call.message.delete()
        _log_sessions.pop(chat_id, None)

    elif data == "log_download":
        await call.answer("📥 Sending file…")
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "rb") as f:
                content = f.read()
            await bot.send_document(
                chat_id,
                BufferedInputFile(content, filename="bot_logs.txt"),
                caption="📥 <b>Full Log File</b>"
            )

    elif data == "log_clean":
        removed = clean_old_logs()
        await call.answer(f"🗑 Cleaned {removed} entries!")
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
            pages                  = build_log_pages(lines)
            _log_sessions[chat_id] = pages
            last = len(pages) - 1
            await call.message.edit_text(
                pages[last] + f"\n🗑 <i>Cleaned {removed} entries</i>",
                reply_markup=log_markup(last, len(pages))
            )

    elif data.startswith("log_page_"):
        try:
            page = int(data.split("_")[-1])
        except ValueError:
            await call.answer(); return
        if not os.path.exists(LOG_FILE):
            await call.answer("⚠️ Log file missing!"); return
        with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        pages                  = build_log_pages(lines)
        _log_sessions[chat_id] = pages
        page = min(page, len(pages) - 1)
        await call.message.edit_text(pages[page], reply_markup=log_markup(page, len(pages)))
        await call.answer()
