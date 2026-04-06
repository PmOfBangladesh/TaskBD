# ============================================================
#  handlers/admin/panel.py  —  Admin panel & main /admin cmd
# ============================================================
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from core.logger import get_logger, get_admin_logger
from helpers.decorators import admin_only
from config import OWNER_ID

router = Router(name="admin_panel")
logger = get_logger("Admin")
alog   = get_admin_logger()


# ──────────────────────────────────────────────
#  Keyboard builders
# ──────────────────────────────────────────────

def admin_panel_markup(user_id: int = 0) -> InlineKeyboardMarkup:
    """Full admin panel — every admin command in one keyboard."""
    rows = [
        # ── Licenses ────────────────────────────────
        [
            InlineKeyboardButton(text="🔑 Gen License",    callback_data="adm_gen"),
            InlineKeyboardButton(text="🔍 Check License",  callback_data="adm_chk"),
        ],
        # ── Reports / Exports ───────────────────────
        [
            InlineKeyboardButton(text="📊 Export XLSX",    callback_data="adm_export"),
            InlineKeyboardButton(text="🔐 Export 2FA",     callback_data="adm_export2fa"),
        ],
        [
            InlineKeyboardButton(text="💰 Final Report",   callback_data="adm_report"),
            InlineKeyboardButton(text="💰 2FA Report",     callback_data="adm_report2fa"),
        ],
        # ── Stats ────────────────────────────────────
        [
            InlineKeyboardButton(text="📈 All-Time Stats", callback_data="adm_stats"),
            InlineKeyboardButton(text="📊 Live Stats",     callback_data="live_0"),
        ],
        [
            InlineKeyboardButton(text="🔄 Reset Stats",    callback_data="adm_resetmenu"),
            InlineKeyboardButton(text="💸 Price List",     callback_data="adm_pricelist"),
        ],
        # ── User management ──────────────────────────
        [
            InlineKeyboardButton(text="➕ Add Balance",    callback_data="adm_addbal"),
            InlineKeyboardButton(text="🗑 Delete User",    callback_data="adm_deluser"),
        ],
        # ── Moderation ───────────────────────────────
        [
            InlineKeyboardButton(text="🚫 Ban User",       callback_data="adm_ban"),
            InlineKeyboardButton(text="🔓 Unban User",     callback_data="adm_unban"),
        ],
        [
            InlineKeyboardButton(text="📋 Spam List",      callback_data="adm_spamlist"),
            InlineKeyboardButton(text="📢 Broadcast",      callback_data="adm_broadcast"),
        ],
        # ── System ───────────────────────────────────
        [
            InlineKeyboardButton(text="🏓 Ping",           callback_data="adm_ping"),
            InlineKeyboardButton(text="⚡ Speedtest",      callback_data="adm_speedtest"),
        ],
        [
            InlineKeyboardButton(text="📜 Logs",           callback_data="adm_logs"),
            InlineKeyboardButton(text="🔄 Restart Bot",    callback_data="adm_restart"),
        ],
    ]

    # Owner-only row — visible only to OWNER
    if user_id and user_id == OWNER_ID:
        rows.append([
            InlineKeyboardButton(text="👑 Add Admin",      callback_data="own_addadmin"),
            InlineKeyboardButton(text="🗑 Remove Admin",   callback_data="own_removeadmin"),
        ])
        rows.append([
            InlineKeyboardButton(text="💻 Shell",          callback_data="own_shell"),
            InlineKeyboardButton(text="🖥 Reboot Server",  callback_data="own_reboot"),
        ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


# ──────────────────────────────────────────────
#  /admin
# ──────────────────────────────────────────────

@router.message(Command("admin", "abidbotol"))
@admin_only
async def cmd_admin_panel(message: Message):
    uid = message.from_user.id
    owner_tag = "\n👑 <b>Owner mode active</b>" if uid == OWNER_ID else ""
    await message.answer(
        f"╔══════════════════════╗\n"
        f"║  👑  <b>Admin Control Panel</b>  ║\n"
        f"╚══════════════════════╝\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"Welcome, Boss! 🤖\n"
        f"Choose an action from the menu below.{owner_tag}",
        reply_markup=admin_panel_markup(uid),
    )
    logger.info(f"Admin panel opened | user_id={uid}")
    alog.info(f"Admin panel | uid={uid}")


# ──────────────────────────────────────────────
#  Inline-button passthrough for system commands
#  (ping, speedtest, logs, restart handled here
#   since they live in other routers but need a
#   panel callback entry-point)
# ──────────────────────────────────────────────

from aiogram import F
from aiogram.types import CallbackQuery
from config import ADMIN_IDS


@router.callback_query(F.data.in_({"adm_ping", "adm_speedtest", "adm_logs", "adm_restart"}))
async def handle_system_panel_callbacks(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Access Denied!", show_alert=True)
        return
    await call.answer()

    # For system commands we call the underlying logic directly (bypassing @admin_only)
    # because call.message.from_user is the bot, not the admin.
    if call.data == "adm_ping":
        import time
        import platform
        import psutil
        from datetime import datetime

        start = time.monotonic()
        sent  = await call.message.answer("🏓 <b>Pinging...</b>")
        ms    = round((time.monotonic() - start) * 1000, 2)

        try:
            with open("/proc/uptime") as f:
                sec = float(f.read().split()[0])
            d, rem = divmod(int(sec), 86400)
            h, rem = divmod(rem, 3600)
            m      = rem // 60
            uptime = f"{d}d {h}h {m}m" if d else f"{h}h {m}m"
        except Exception:
            uptime = "N/A"

        try:
            import os as _os
            os_name = platform.system()
            if _os.path.exists("/etc/os-release"):
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

        def _bar(pct: float, width: int = 10) -> str:
            filled = int(pct / 100 * width)
            return "█" * filled + "░" * (width - filled)

        from config import BOT_NAME, BOT_VERSION
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

    elif call.data == "adm_speedtest":
        import asyncio as _asyncio
        import shutil
        from datetime import datetime

        if not shutil.which("speedtest") and not shutil.which("speedtest-cli"):
            await call.message.answer(
                "⚠️ <b>speedtest-cli not installed.</b>\n"
                "<code>pip install speedtest-cli</code>"
            )
            return
        sent = await call.message.answer("⚡ <b>Running speed test…</b>\n<i>This may take 30s.</i>")
        try:
            proc = await _asyncio.create_subprocess_exec(
                "speedtest", "--simple",
                stdout=_asyncio.subprocess.PIPE,
                stderr=_asyncio.subprocess.PIPE,
            )
            stdout, stderr = await _asyncio.wait_for(proc.communicate(), timeout=60)
            out = stdout.decode().strip() or stderr.decode().strip()
        except _asyncio.TimeoutError:
            await sent.edit_text("⏱ <b>Speed test timed out.</b>")
            return
        except Exception as e:
            await sent.edit_text(f"❌ Speed test error: {e}")
            return
        await sent.edit_text(
            f"⚡ <b>Speed Test Result</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<pre>{out}</pre>\n"
            f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )

    elif call.data == "adm_logs":
        import os as _os
        from modules.log_viewer import build_log_pages, log_markup, clean_old_logs, LOG_FILE
        chat_id = call.message.chat.id
        removed = clean_old_logs()
        if not _os.path.exists(LOG_FILE):
            await call.message.answer("⚠️ No log file found.")
            return
        with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        if not lines:
            await call.message.answer("⚠️ Log file is empty.")
            return
        pages = build_log_pages(lines)
        last  = len(pages) - 1
        note  = f"\n🗑 <i>Auto-cleaned {removed} old entries</i>" if removed else ""
        await call.message.answer(pages[last] + note, reply_markup=log_markup(last, len(pages)))

    elif call.data == "adm_restart":
        markup = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Yes, Restart", callback_data="adm_restart_confirm"),
            InlineKeyboardButton(text="❌ Cancel",       callback_data="adm_restart_cancel"),
        ]])
        await call.message.answer(
            "⚠️ <b>Restart Bot?</b>\n<i>The bot will restart immediately.</i>",
            reply_markup=markup,
        )


@router.callback_query(F.data.in_({"adm_restart_confirm", "adm_restart_cancel"}))
async def handle_restart_confirm(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Access Denied!", show_alert=True)
        return
    if call.data == "adm_restart_cancel":
        await call.answer("❌ Cancelled.")
        await call.message.edit_text("❌ <b>Restart cancelled.</b>", reply_markup=None)
    else:
        await call.answer("🔄 Restarting…")
        await call.message.edit_text("🔄 <b>Restarting bot…</b>", reply_markup=None)
        import os, sys
        logger.info(f"Restart via panel | uid={call.from_user.id}")
        os.execv(sys.executable, [sys.executable] + sys.argv)


@router.callback_query(F.data == "adm_pricelist")
async def handle_pricelist_panel(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Access Denied!", show_alert=True)
        return
    await call.answer()
    from handlers.admin.pricing import cmd_pricelist
    await cmd_pricelist(call.message)
