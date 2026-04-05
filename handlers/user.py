# ============================================================
#  handlers/user.py  —  User-facing commands & menus
# ============================================================
import random
import time
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)

from core.bot import bot
from core.database import (
    get_user_by_key, get_key_by_tg_id, load_licenses, save_licenses,
    get_today_stats, get_today_2fa_count, get_user_profile, get_7_days_history,
    update_payment_method
)
from core.state import PayChange, Withdraw
from core.logger import get_logger
from helpers.decorators import private_only, spam_guard
from helpers.formatter import fmt_profile, fmt_validity
from helpers.validators import is_valid_key, is_valid_pay_method
from helpers.utils import check_channel_membership, random_effect_id
from config import ADMIN_IDS, CHANNEL_ID, MIN_WITHDRAW, BOT_NAME

router = Router(name="user")
logger = get_logger("User")


# ──────────────────────────────────────────────
#  Keyboards
# ──────────────────────────────────────────────

def main_menu(key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👤 My Profile",  callback_data=f"u_profile_{key}"),
            InlineKeyboardButton(text="📜 History",     callback_data=f"u_history_{key}"),
        ],
        [
            InlineKeyboardButton(text="📊 Live Stats",  callback_data=f"u_stats_{key}"),
            InlineKeyboardButton(text="🔐 2FA Stats",   callback_data=f"u_stats2fa_{key}"),
        ],
        [
            InlineKeyboardButton(text="💸 Withdraw",    callback_data=f"u_withdraw_{key}"),
        ],
    ])


def back_btn(key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Back", callback_data=f"u_back_{key}")]
    ])


# ──────────────────────────────────────────────
#  /start
# ──────────────────────────────────────────────

@router.message(Command("start"))
@private_only
@spam_guard
async def cmd_start(message: Message):
    tg_id     = message.from_user.id
    firstname = message.from_user.first_name or "User"

    # Channel check
    if not await check_channel_membership(bot, tg_id):
        await message.answer(
            f"⚠️ <b>Join our channel first!</b>\n\n"
            f"👉 {CHANNEL_ID}\n\n"
            f"Then press /start again."
        )
        return

    # Returning user
    existing_key = await get_key_by_tg_id(tg_id)
    if existing_key:
        user = await get_user_by_key(existing_key)
        name    = user.get("name", firstname)
        balance = user.get("balance", 0.0)
        await bot.send_message(
            tg_id,
            f"🎉 <b>Welcome back, {firstname}!</b>\n\n"
            f"💰 Balance: <b>{balance} ৳</b>\n"
            f"<i>Choose an option below:</i>",
            message_effect_id=random_effect_id(),
            reply_markup=main_menu(existing_key)
        )
        return

    # New user
    await bot.send_message(
        tg_id,
        f"🌟 <b>Hey {firstname}!</b>\n\n"
        f"✨ Welcome to <b>{BOT_NAME}</b>\n"
        f"<i>Your account management partner.</i>\n\n"
        f"🔑 Enter your <b>License Key</b> to get started.\n"
        f"<i>Format: SML-XXXXXX  or  MENTOR-SML-XXXXXX</i>",
        message_effect_id=random_effect_id()
    )


# ──────────────────────────────────────────────
#  License key handler
# ──────────────────────────────────────────────

@router.message(F.text.func(lambda t: t and is_valid_key(t)))
@private_only
@spam_guard
async def handle_license_key(message: Message):
    tg_id = message.from_user.id

    if not await check_channel_membership(bot, tg_id):
        await message.answer(f"⚠️ Join {CHANNEL_ID} first!")
        return

    existing = await get_key_by_tg_id(tg_id)
    if existing:
        await message.answer("✅ Already registered!", reply_markup=main_menu(existing))
        return

    key       = message.text.strip().upper()
    user_data = await get_user_by_key(key)

    if not user_data:
        await message.answer(
            "❌ <b>Invalid License Key!</b>\n"
            "<i>Format: SML-XXXXXX  or  MENTOR-SML-XXXXXX</i>"
        )
        return

    existing_tg = user_data.get("tg_id", "")
    if existing_tg and str(existing_tg) != str(tg_id):
        await message.answer("❌ This key is already used by another account!")
        return

    # Bind
    licenses = await load_licenses()
    lic      = licenses[key]
    if not lic.get("joined"):
        lic["joined"] = datetime.now().strftime("%Y-%m-%d")
    lic.setdefault("balance", 0.0)
    lic.setdefault("total_withdraws", 0)
    lic.setdefault("total_earned", 0.0)
    lic["tg_id"] = tg_id
    await save_licenses(licenses)

    user_data = await get_user_by_key(key)
    validity  = fmt_validity(user_data.get("validity", "N/A"))
    mentor    = user_data.get("mentor", "")
    mentor_ln = f"👨‍🏫 Mentor: <b>{mentor}</b>\n" if mentor else ""

    await message.answer(
        f"✅ <b>Key Verified! Welcome, {user_data.get('name', 'User')}!</b>\n"
        f"⏳ Valid Till: {validity}\n"
        f"{mentor_ln}"
        f"\n<i>You won't need to enter this key again.</i>\n"
        f"Choose an option below:",
        reply_markup=main_menu(key)
    )


# ──────────────────────────────────────────────
#  User callbacks
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("u_"))
async def handle_user_callbacks(call: CallbackQuery, state: FSMContext):
    tg_id  = call.from_user.id
    msg_id = call.message.message_id
    data   = call.data

    # ── Profile ──────────────────────────────
    if data.startswith("u_profile_"):
        key     = data[len("u_profile_"):]
        profile = await get_user_profile(key)
        if not profile:
            await call.answer("❌ Profile not found!", show_alert=True); return
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Change Payment", callback_data=f"u_changepay_{key}")],
            [InlineKeyboardButton(text="⬅️ Back",           callback_data=f"u_back_{key}")],
        ])
        await call.message.edit_text(fmt_profile(profile, key), reply_markup=markup)
        await call.answer()

    # ── History ──────────────────────────────
    elif data.startswith("u_history_"):
        key  = data[len("u_history_"):]
        text = await get_7_days_history(key)
        await call.message.edit_text(text, reply_markup=back_btn(key))
        await call.answer()

    # ── Live Stats ───────────────────────────
    elif data.startswith("u_stats_") and not data.startswith("u_stats2fa_"):
        key       = data[len("u_stats_"):]
        user_data = await get_user_by_key(key)
        if not user_data:
            await call.answer("❌ Not found!", show_alert=True); return
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

    # ── 2FA Stats ────────────────────────────
    elif data.startswith("u_stats2fa_"):
        key       = data[len("u_stats2fa_"):]
        user_data = await get_user_by_key(key)
        if not user_data:
            await call.answer("❌ Not found!", show_alert=True); return
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

    # ── Withdraw ─────────────────────────────
    elif data.startswith("u_withdraw_"):
        key     = data[len("u_withdraw_"):]
        profile = await get_user_profile(key)
        if not profile:
            await call.answer("❌ Not found!", show_alert=True); return
        balance = profile["balance"]
        if balance < MIN_WITHDRAW:
            await call.answer(
                f"❌ Min withdraw is {MIN_WITHDRAW}৳. Your balance: {balance}৳",
                show_alert=True
            ); return
        text = (
            f"💸 <b>Withdraw Request</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 Balance: <b>{balance} ৳</b>\n"
            f"💳 Method:  {profile['payment_method']}\n"
            f"📱 Number:  {profile['payment_number']}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<i>Confirm to send request to admin.</i>"
        )
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Confirm", callback_data=f"u_confirmwd_{key}"),
                InlineKeyboardButton(text="❌ Cancel",  callback_data=f"u_back_{key}"),
            ]
        ])
        await call.message.edit_text(text, reply_markup=markup)
        await call.answer()

    # ── Confirm Withdraw ─────────────────────
    elif data.startswith("u_confirmwd_"):
        key     = data[len("u_confirmwd_"):]
        profile = await get_user_profile(key)
        if not profile:
            await call.answer("❌ Not found!", show_alert=True); return

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
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Confirm & Send SS", callback_data=f"admin_confirm_{key}")]
        ])
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

    # ── Change Payment ────────────────────────
    elif data.startswith("u_changepay_"):
        key = data[len("u_changepay_"):]
        await state.update_data(key=key)
        await state.set_state(PayChange.method)
        await call.answer()
        await bot.send_message(
            tg_id,
            "💳 Enter new payment method:\n<i>bKash / Nagad / Rocket / Upay</i>"
        )

    # ── Back ──────────────────────────────────
    elif data.startswith("u_back_"):
        key       = data[len("u_back_"):]
        user_data = await get_user_by_key(key)
        name      = user_data.get("name", "User") if user_data else "User"
        balance   = user_data.get("balance", 0.0) if user_data else 0.0
        await call.message.edit_text(
            f"👋 <b>Welcome back, {name}!</b>\n"
            f"💰 Balance: <b>{balance} ৳</b>\n\n"
            f"Choose an option:",
            reply_markup=main_menu(key)
        )
        await call.answer()


# ──────────────────────────────────────────────
#  FSM: Change payment method
# ──────────────────────────────────────────────

@router.message(PayChange.method)
@private_only
async def pay_change_method(message: Message, state: FSMContext):
    method = message.text.strip()
    if not is_valid_pay_method(method):
        await message.answer("❌ Valid options: <b>bKash / Nagad / Rocket / Upay</b>")
        return
    await state.update_data(method=method)
    await state.set_state(PayChange.number)
    await message.answer(f"✅ Method: <b>{method}</b>\n➡️ Enter your <b>payment number</b>:")


@router.message(PayChange.number)
@private_only
async def pay_change_number(message: Message, state: FSMContext):
    number = message.text.strip()
    data   = await state.get_data()
    key    = data.get("key", "")
    method = data.get("method", "")
    await update_payment_method(key, method, number)
    await state.clear()

    from handlers.user import main_menu
    await message.answer(
        f"✅ <b>Payment method updated!</b>\n"
        f"💳 {method} — {number}",
        reply_markup=main_menu(key)
    )
