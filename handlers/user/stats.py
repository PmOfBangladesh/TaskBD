# ============================================================
#  handlers/user/stats.py  —  Live stats & 2FA stats callbacks
# ============================================================
import time

from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from core.database import get_user_by_key, get_today_stats, get_today_2fa_count
from core.logger import get_logger
from handlers.user.start import back_btn

router = Router(name="user_stats")
logger = get_logger("User.Stats")


# ──────────────────────────────────────────────
#  Live stats callback
# ──────────────────────────────────────────────

@router.callback_query(
    F.data.startswith("u_stats_") & ~F.data.startswith("u_stats2fa_")
)
async def cb_stats(call: CallbackQuery):
    key       = call.data[len("u_stats_"):]
    user_data = await get_user_by_key(key)
    if not user_data:
        await call.answer("❌ Not found!", show_alert=True)
        return
    stats = await get_today_stats(user_data["username"])
    text  = (
        f"📊 <b>Live Statistics</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"✅ Approved:  <b>{stats['aprv']}</b>\n"
        f"📥 Submitted: <b>{stats['sub']}</b>\n"
        f"❌ Rejected:  <b>{stats['rej']}</b>\n"
        f"🚫 Suspended: <b>{stats['sus']}</b>\n"
        f"📈 Rate:      <b>{stats['pct']}%</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🕒 <i>{time.strftime('%I:%M:%S %p')}</i>"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Refresh", callback_data=f"u_stats_{key}")],
        [InlineKeyboardButton(text="⬅️ Back",    callback_data=f"u_back_{key}")],
    ])
    await call.message.edit_text(text, reply_markup=markup)
    await call.answer("🔄 Refreshed!")


# ──────────────────────────────────────────────
#  2FA stats callback
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("u_stats2fa_"))
async def cb_stats2fa(call: CallbackQuery):
    key       = call.data[len("u_stats2fa_"):]
    user_data = await get_user_by_key(key)
    if not user_data:
        await call.answer("❌ Not found!", show_alert=True)
        return
    count = await get_today_2fa_count(user_data["username"])
    text  = (
        f"🔐 <b>2FA Live Statistics</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"✅ 2FA Success: <b>{count}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🕒 <i>{time.strftime('%I:%M:%S %p')}</i>"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Refresh", callback_data=f"u_stats2fa_{key}")],
        [InlineKeyboardButton(text="⬅️ Back",    callback_data=f"u_back_{key}")],
    ])
    await call.message.edit_text(text, reply_markup=markup)
    await call.answer("🔄 Refreshed!")
