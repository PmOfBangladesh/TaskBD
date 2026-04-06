# ============================================================
#  handlers/user/profile.py  —  Profile view & payment change
# ============================================================
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from core.bot import bot
from core.database import get_user_profile, get_7_days_history, update_payment_method
from core.state import PayChange
from core.logger import get_logger
from helpers.decorators import private_only
from helpers.formatter import fmt_profile
from helpers.validators import is_valid_pay_method
from handlers.user.start import main_menu, back_btn

router = Router(name="user_profile")
logger = get_logger("User.Profile")


# ──────────────────────────────────────────────
#  Profile callback
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("u_profile_"))
async def cb_profile(call: CallbackQuery):
    key     = call.data[len("u_profile_"):]
    profile = await get_user_profile(key)
    if not profile:
        await call.answer("❌ Profile not found!", show_alert=True)
        return
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Change Payment", callback_data=f"u_changepay_{key}")],
        [InlineKeyboardButton(text="⬅️ Back",           callback_data=f"u_back_{key}")],
    ])
    await call.message.edit_text(fmt_profile(profile, key), reply_markup=markup)
    await call.answer()


# ──────────────────────────────────────────────
#  History callback
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("u_history_"))
async def cb_history(call: CallbackQuery):
    key  = call.data[len("u_history_"):]
    text = await get_7_days_history(key)
    await call.message.edit_text(text, reply_markup=back_btn(key))
    await call.answer()


# ──────────────────────────────────────────────
#  Change payment method (FSM)
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("u_changepay_"))
async def cb_changepay(call: CallbackQuery, state: FSMContext):
    key = call.data[len("u_changepay_"):]
    await state.update_data(key=key)
    await state.set_state(PayChange.method)
    await call.answer()
    await bot.send_message(
        call.from_user.id,
        "💳 Enter new payment method:\n<i>bKash / Nagad / Rocket / Upay</i>"
    )


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
    await message.answer(
        f"✅ <b>Payment method updated!</b>\n"
        f"💳 {method} — {number}",
        reply_markup=main_menu(key),
    )
    logger.info(f"Payment method updated | key={key} | method={method}")
