# ============================================================
#  handlers/admin/users.py  —  Add balance & delete user
# ============================================================
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from core.bot import bot
from core.database import (
    load_licenses, save_licenses,
    delete_user, get_today_stats, reset_today_stats,
)
from core.state import AddBalance, DeleteUser
from core.logger import get_logger, get_admin_logger
from helpers.decorators import admin_only
from helpers.validators import is_valid_amount
from config import ADMIN_IDS

router = Router(name="admin_users")
logger = get_logger("Admin.Users")
alog   = get_admin_logger()


# ──────────────────────────────────────────────
#  Callback entry-points from panel
# ──────────────────────────────────────────────

@router.callback_query(F.data.in_({"adm_addbal", "adm_deluser"}))
async def handle_user_mgmt_callbacks(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Access Denied!", show_alert=True)
        return
    await call.answer()

    if call.data == "adm_addbal":
        await state.set_state(AddBalance.key)
        await call.message.answer("➕ <b>Add Balance</b>\nEnter License Key:")

    elif call.data == "adm_deluser":
        await state.set_state(DeleteUser.key)
        await call.message.answer("🗑 <b>Delete User</b>\nEnter License Key:")


# ──────────────────────────────────────────────
#  FSM: Add Balance
# ──────────────────────────────────────────────

@router.message(AddBalance.key)
@admin_only
async def addbal_step_key(message: Message, state: FSMContext):
    key      = message.text.strip().upper()
    licenses = await load_licenses()
    if key not in licenses:
        await message.answer(f"❌ Key <code>{key}</code> not found!")
        return
    name = licenses[key].get("name", "N/A")
    await state.update_data(key=key)
    await state.set_state(AddBalance.amount)
    await message.answer(f"✅ Found: <b>{name}</b>\n➕ Enter amount to add (৳):")


@router.message(AddBalance.amount)
@admin_only
async def addbal_step_amount(message: Message, state: FSMContext):
    ok, amount = is_valid_amount(message.text)
    if not ok:
        await message.answer("❌ Enter a valid positive number:")
        return
    data = await state.get_data()
    key  = data.get("key", "")
    await state.clear()

    licenses = await load_licenses()
    if key not in licenses:
        await message.answer("❌ Session expired.")
        return

    info            = licenses[key]
    old_bal         = info.get("balance", 0.0)
    new_bal         = round(old_bal + amount, 2)
    info["balance"] = new_bal
    await save_licenses(licenses)

    # Auto reset today's stats for this user
    username = info.get("username", "")
    if username:
        await reset_today_stats(username)

    # Notify user
    tg_id = info.get("tg_id")
    if tg_id:
        try:
            await bot.send_message(
                tg_id,
                f"💰 <b>Balance Added!</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"➕ Added:   <b>{amount} ৳</b>\n"
                f"💵 Balance: <b>{new_bal} ৳</b>"
            )
        except Exception:
            pass

    # Mentor bonus
    mentor_key   = info.get("mentor_key", "")
    mentor_bonus = info.get("mentor_per_account_bonus", 0.0)
    if mentor_key and mentor_key in licenses and mentor_bonus > 0:
        today_stats  = await get_today_stats(username)
        approved     = today_stats["aprv"]
        bonus_amount = round(approved * mentor_bonus, 2)
        if bonus_amount > 0:
            mentor_info            = licenses[mentor_key]
            mentor_bal             = round(mentor_info.get("balance", 0.0) + bonus_amount, 2)
            mentor_info["balance"] = mentor_bal
            await save_licenses(licenses)
            mentor_tg = mentor_info.get("tg_id")
            if mentor_tg:
                try:
                    await bot.send_message(
                        mentor_tg,
                        f"🎉 <b>Mentor Bonus Received!</b>\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"👤 Student:  <b>{info['name']}</b>\n"
                        f"🎁 Bonus:    <b>{bonus_amount} ৳</b>\n"
                        f"💵 Balance:  <b>{mentor_bal} ৳</b>"
                    )
                except Exception:
                    pass

    await message.answer(
        f"✅ <b>Balance Added!</b>\n"
        f"👤 {info['name']}\n"
        f"➕ {amount} ৳ → Balance: <b>{new_bal} ৳</b>\n"
        f"🔄 Stats auto-reset done."
    )
    alog.info(f"Balance added | key={key} | amount={amount}৳ | by={message.from_user.id}")


# ──────────────────────────────────────────────
#  FSM: Delete User
# ──────────────────────────────────────────────

@router.message(DeleteUser.key)
@admin_only
async def delete_step_key(message: Message, state: FSMContext):
    key      = message.text.strip().upper()
    licenses = await load_licenses()
    if key not in licenses:
        await message.answer(f"❌ Key <code>{key}</code> not found!")
        await state.clear()
        return
    name = licenses[key].get("name", "N/A")
    await state.clear()
    markup = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"✅ Delete {name}", callback_data=f"adm_delconfirm_{key}"),
        InlineKeyboardButton(text="❌ Cancel",          callback_data="adm_delcancel"),
    ]])
    await message.answer(
        f"⚠️ <b>Delete user?</b>\n👤 {name}\n🔑 <code>{key}</code>",
        reply_markup=markup,
    )


@router.callback_query(F.data.startswith("adm_delconfirm_"))
async def delete_confirm(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Access Denied!", show_alert=True)
        return
    key = call.data[len("adm_delconfirm_"):]
    await delete_user(key)
    await call.answer("✅ Deleted!")
    await call.message.edit_text(
        f"✅ <b>User deleted:</b> <code>{key}</code>",
        reply_markup=None,
    )
    alog.info(f"License deleted | key={key} | by={call.from_user.id}")


@router.callback_query(F.data == "adm_delcancel")
async def delete_cancel(call: CallbackQuery):
    await call.answer("❌ Cancelled.")
    await call.message.edit_text("❌ <b>Deletion cancelled.</b>", reply_markup=None)
