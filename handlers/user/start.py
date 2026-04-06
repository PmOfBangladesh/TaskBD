# ============================================================
#  handlers/user/start.py  —  /start, license key, main menu
# ============================================================
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from core.bot import bot
from core.database import (
    get_user_by_key, get_key_by_tg_id,
    load_licenses, save_licenses,
)
from core.logger import get_logger
from helpers.decorators import private_only, spam_guard
from helpers.formatter import fmt_validity
from helpers.validators import is_valid_key
from helpers.utils import check_channel_membership, random_effect_id
from config import CHANNEL_ID, BOT_NAME

router = Router(name="user_start")
logger = get_logger("User.Start")


# ──────────────────────────────────────────────
#  Shared keyboard builders
# ──────────────────────────────────────────────

def main_menu(key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👤 My Profile", callback_data=f"u_profile_{key}"),
            InlineKeyboardButton(text="📜 History",    callback_data=f"u_history_{key}"),
        ],
        [
            InlineKeyboardButton(text="📊 Live Stats", callback_data=f"u_stats_{key}"),
            InlineKeyboardButton(text="🔐 2FA Stats",  callback_data=f"u_stats2fa_{key}"),
        ],
        [
            InlineKeyboardButton(text="💸 Withdraw",   callback_data=f"u_withdraw_{key}"),
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

    if not await check_channel_membership(bot, tg_id):
        await message.answer(
            f"⚠️ <b>Join our channel first!</b>\n\n"
            f"👉 {CHANNEL_ID}\n\n"
            f"Then press /start again."
        )
        return

    existing_key = await get_key_by_tg_id(tg_id)
    if existing_key:
        user    = await get_user_by_key(existing_key)
        balance = user.get("balance", 0.0) if user else 0.0
        await bot.send_message(
            tg_id,
            f"🎉 <b>Welcome back, {firstname}!</b>\n\n"
            f"💰 Balance: <b>{balance} ৳</b>\n"
            f"<i>Choose an option below:</i>",
            message_effect_id=random_effect_id(),
            reply_markup=main_menu(existing_key),
        )
        return

    # New user — prompt for key
    await bot.send_message(
        tg_id,
        f"🌟 <b>Hey {firstname}!</b>\n\n"
        f"✨ Welcome to <b>{BOT_NAME}</b>\n"
        f"<i>Your account management partner.</i>\n\n"
        f"🔑 Enter your <b>License Key</b> to get started.\n"
        f"<i>Format: SML-XXXXXX  or  MENTOR-SML-XXXXXX</i>",
        message_effect_id=random_effect_id(),
    )


# ──────────────────────────────────────────────
#  License key handler  (catches matching text)
# ──────────────────────────────────────────────

@router.message(F.text.func(lambda t: bool(t and is_valid_key(t))))
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

    # Bind tg_id
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
        reply_markup=main_menu(key),
    )
    logger.info(f"License registered | key={key} | tg_id={tg_id}")


# ──────────────────────────────────────────────
#  u_back_ callback  (navigation back to menu)
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("u_back_"))
async def cb_back(call):
    key       = call.data[len("u_back_"):]
    user_data = await get_user_by_key(key)
    name      = user_data.get("name", "User")    if user_data else "User"
    balance   = user_data.get("balance", 0.0)    if user_data else 0.0
    await call.message.edit_text(
        f"👋 <b>Welcome back, {name}!</b>\n"
        f"💰 Balance: <b>{balance} ৳</b>\n\n"
        f"Choose an option:",
        reply_markup=main_menu(key),
    )
    await call.answer()
