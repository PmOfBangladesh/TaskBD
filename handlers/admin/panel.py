# ============================================================
#  handlers/admin/panel.py  —  Admin panel & main /admin cmd
# ============================================================
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from core.logger import get_logger, get_admin_logger
from helpers.decorators import admin_only

router = Router(name="admin_panel")
logger = get_logger("Admin")
alog   = get_admin_logger()


# ──────────────────────────────────────────────
#  Shared keyboard builder (imported by sub-files)
# ──────────────────────────────────────────────

def admin_panel_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔑 Gen License",    callback_data="adm_gen"),
            InlineKeyboardButton(text="📊 Export XLSX",    callback_data="adm_export"),
        ],
        [
            InlineKeyboardButton(text="🔐 Export 2FA",     callback_data="adm_export2fa"),
            InlineKeyboardButton(text="💰 Final Report",   callback_data="adm_report"),
        ],
        [
            InlineKeyboardButton(text="💰 2FA Report",     callback_data="adm_report2fa"),
            InlineKeyboardButton(text="🔍 Check License",  callback_data="adm_chk"),
        ],
        [
            InlineKeyboardButton(text="📈 All-Time Stats", callback_data="adm_stats"),
            InlineKeyboardButton(text="📊 Live Stats",     callback_data="live_0"),
        ],
        [
            InlineKeyboardButton(text="📢 Broadcast",      callback_data="adm_broadcast"),
            InlineKeyboardButton(text="🔄 Reset Stats",    callback_data="adm_resetmenu"),
        ],
        [
            InlineKeyboardButton(text="➕ Add Balance",    callback_data="adm_addbal"),
            InlineKeyboardButton(text="🗑 Delete User",    callback_data="adm_deluser"),
        ],
        [
            InlineKeyboardButton(text="🚫 Spam List",      callback_data="adm_spamlist"),
            InlineKeyboardButton(text="🔓 Unban User",     callback_data="adm_unban"),
        ],
    ])


# ──────────────────────────────────────────────
#  /admin
# ──────────────────────────────────────────────

@router.message(Command("admin", "abidbotol"))
@admin_only
async def cmd_admin_panel(message: Message):
    await message.answer(
        "👑 <b>Admin Control Panel</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "Welcome Boss! Choose an action:",
        reply_markup=admin_panel_markup()
    )
    logger.info(f"Admin panel opened by {message.from_user.id}")
