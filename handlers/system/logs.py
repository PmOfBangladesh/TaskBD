# ============================================================
#  handlers/system/logs.py  —  /logs command + pagination
# ============================================================
import os

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile

from core.bot import bot
from core.logger import get_logger
from helpers.decorators import admin_only
from modules.log_viewer import build_log_pages, log_markup, clean_old_logs, LOG_FILE
from config import ADMIN_IDS

router = Router(name="system_logs")
logger = get_logger("System.Logs")

# per-chat cached pages
_log_sessions: dict[int, list[str]] = {}


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

    pages                  = build_log_pages(lines)
    _log_sessions[chat_id] = pages
    last                   = len(pages) - 1
    note = f"\n🗑 <i>Auto-cleaned {removed} old entries</i>" if removed else ""
    await message.answer(pages[last] + note, reply_markup=log_markup(last, len(pages)))


@router.callback_query(F.data.startswith("log_"))
async def handle_log_cb(call: CallbackQuery):
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
                caption="📥 <b>Full Log File</b>",
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
                reply_markup=log_markup(last, len(pages)),
            )

    elif data.startswith("log_page_"):
        try:
            page = int(data.split("_")[-1])
        except ValueError:
            await call.answer()
            return
        if not os.path.exists(LOG_FILE):
            await call.answer("⚠️ Log file missing!")
            return
        with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        pages                  = build_log_pages(lines)
        _log_sessions[chat_id] = pages
        page                   = min(page, len(pages) - 1)
        await call.message.edit_text(pages[page], reply_markup=log_markup(page, len(pages)))
        await call.answer()
