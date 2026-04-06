# ============================================================
#  handlers/user/withdraw.py  —  Withdraw request flow
# ============================================================
from datetime import datetime

from aiogram import Router, F
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from core.bot import bot
from core.database import get_user_profile
from core.logger import get_logger
from config import ADMIN_IDS, MIN_WITHDRAW

router = Router(name="user_withdraw")
logger = get_logger("User.Withdraw")


# ──────────────────────────────────────────────
#  Initiate withdraw
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("u_withdraw_"))
async def cb_withdraw(call: CallbackQuery):
    key     = call.data[len("u_withdraw_"):]
    profile = await get_user_profile(key)
    if not profile:
        await call.answer("❌ Not found!", show_alert=True)
        return
    balance = profile["balance"]
    if balance < MIN_WITHDRAW:
        await call.answer(
            f"❌ Min withdraw is {MIN_WITHDRAW}৳. Your balance: {balance}৳",
            show_alert=True,
        )
        return
    text = (
        f"💸 <b>Withdraw Request</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 Balance: <b>{balance} ৳</b>\n"
        f"💳 Method:  {profile['payment_method']}\n"
        f"📱 Number:  {profile['payment_number']}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<i>Confirm to send request to admin.</i>"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Confirm", callback_data=f"u_confirmwd_{key}"),
        InlineKeyboardButton(text="❌ Cancel",  callback_data=f"u_back_{key}"),
    ]])
    await call.message.edit_text(text, reply_markup=markup)
    await call.answer()


# ──────────────────────────────────────────────
#  Confirm — forward to admins
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("u_confirmwd_"))
async def cb_confirm_withdraw(call: CallbackQuery):
    key     = call.data[len("u_confirmwd_"):]
    profile = await get_user_profile(key)
    if not profile:
        await call.answer("❌ Not found!", show_alert=True)
        return

    admin_text = (
        f"🔔 <b>WITHDRAW REQUEST</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 Name:   <b>{profile['name']}</b>\n"
        f"🔑 User:   {profile['username']}\n"
        f"💳 Method: {profile['payment_method']}\n"
        f"📱 Number: {profile['payment_number']}\n"
        f"💰 Amount: <b>{profile['balance']} ৳</b>\n"
        f"📅 Date:   {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔑 Key: <code>{key}</code>"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Confirm & Send SS", callback_data=f"admin_confirm_{key}")
    ]])
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_text, reply_markup=markup)
        except Exception:
            pass

    await call.answer("🚀 Request sent!")
    await call.message.edit_text(
        f"✅ <b>Withdraw request sent!</b>\n"
        f"💰 Amount: {profile['balance']} ৳\n\n"
        f"<i>Waiting for admin approval…</i>"
    )
    logger.info(f"Withdraw request | key={key} | amount={profile['balance']}৳")
