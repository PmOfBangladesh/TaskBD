# ============================================================
#  handlers/callbacks.py  —  Withdraw confirm + screenshot
# ============================================================
from datetime import datetime

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery, Message,
    InlineKeyboardMarkup, InlineKeyboardButton,
    BufferedInputFile
)

from core.bot import bot
from core.database import get_user_by_key, deduct_balance, save_withdrawal
from core.state import Screenshot
from core.logger import get_logger
from helpers.decorators import admin_callback
from helpers.formatter import mask_number, generate_txn_id
from config import ADMIN_IDS, GROUP_ID, LOG_CHANNEL, PARTY_STICKER

router = Router(name="callbacks")
logger = get_logger("Callbacks")

# admin_id → {key, photo_id}
_pending_ss: dict[int, dict] = {}


# ──────────────────────────────────────────────
#  Admin clicks "Confirm & Send SS"
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin_confirm_"))
async def handle_admin_confirm(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Access Denied!", show_alert=True); return

    key       = call.data[len("admin_confirm_"):]
    user_data = await get_user_by_key(key)
    if not user_data:
        await call.answer("❌ License not found!", show_alert=True); return

    await call.answer("📸 Send the screenshot now!")
    await call.message.edit_text(
        f"🔄 <i>Processing payment for</i> <b>{user_data['name']}</b>…\n"
        f"💰 {user_data.get('balance', 0.0)} ৳ | <code>{key}</code>",
        reply_markup=None
    )

    # Notify other admins
    for admin_id in ADMIN_IDS:
        if admin_id == call.from_user.id:
            continue
        try:
            await bot.send_message(
                admin_id,
                f"🔔 <b>Withdraw being handled</b>\n"
                f"👤 {user_data['name']} | <code>{key}</code>\n"
                f"✅ <i>Handled by another admin</i>"
            )
        except Exception:
            pass

    await bot.send_message(
        call.from_user.id,
        f"📸 <b>Waiting for Screenshot</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>{user_data['name']}</b>\n"
        f"💳 {user_data.get('payment_method','N/A')} — {user_data.get('payment_number','N/A')}\n"
        f"💰 {user_data.get('balance', 0.0)} ৳\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📤 <b>Send payment screenshot now:</b>"
    )
    await state.update_data(withdraw_key=key)
    await state.set_state(Screenshot.waiting)


# ──────────────────────────────────────────────
#  Admin sends screenshot photo
# ──────────────────────────────────────────────

@router.message(Screenshot.waiting, F.photo)
async def receive_screenshot(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return

    data      = await state.get_data()
    key       = data.get("withdraw_key", "")
    user_data = await get_user_by_key(key)
    if not user_data:
        await message.answer("❌ License not found. Process aborted.")
        await state.clear()
        return

    photo_id = message.photo[-1].file_id
    _pending_ss[message.from_user.id] = {"key": key, "photo_id": photo_id}

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Done — Send Payment", callback_data=f"admin_done_{key}"),
            InlineKeyboardButton(text="❌ Cancel",              callback_data=f"admin_cancel_{key}"),
        ]
    ])
    await message.answer_photo(
        photo_id,
        caption=(
            f"📋 <b>Review Payment</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>{user_data['name']}</b>\n"
            f"💳 {user_data['payment_method']} — {user_data['payment_number']}\n"
            f"💰 <b>{user_data.get('balance', 0.0)} ৳</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<i>Confirm to send to user.</i>"
        ),
        reply_markup=markup
    )


@router.message(Screenshot.waiting)
async def receive_screenshot_wrong(message: Message, state: FSMContext):
    """Non-photo sent while waiting for screenshot."""
    if message.from_user.id not in ADMIN_IDS:
        return
    await message.answer("❌ That's not a photo! Send the <b>payment screenshot</b>:")


# ──────────────────────────────────────────────
#  Admin confirms — send to user + group
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin_done_"))
async def handle_admin_done(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Access Denied!", show_alert=True); return

    key     = call.data[len("admin_done_"):]
    pending = _pending_ss.pop(call.from_user.id, None)
    if not pending or pending.get("key") != key:
        await call.answer("❌ Session expired. Start again.", show_alert=True); return

    await call.answer("✅ Sending payment…")
    photo_id  = pending["photo_id"]
    user_data = await get_user_by_key(key)
    if not user_data:
        await call.message.answer("❌ License not found."); return

    amount         = user_data.get("balance", 0.0)
    now            = datetime.now().strftime("%Y-%m-%d %H:%M")
    txn_id         = generate_txn_id()
    masked_number  = mask_number(user_data.get("payment_number", ""))
    tg_id          = user_data.get("tg_id")

    caption_user = (
        f"💰 <b>Payment Successful!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 Name:   {user_data['name']}\n"
        f"💵 Amount: <b>{amount} ৳</b>\n"
        f"📅 Date:   {now}\n"
        f"💳 Method: {user_data['payment_method']}\n"
        f"🆔 Txn ID: <code>{txn_id}</code>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"✨ Thank you for working with SML!"
    )
    caption_group = (
        f"✅ <b>PAYMENT SUCCESSFUL</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 Name:   <b>{user_data['name']}</b>\n"
        f"🔑 User:   {user_data['username']}\n"
        f"💵 Amount: {amount} ৳\n"
        f"📅 Date:   {now}\n"
        f"💳 Method: {user_data['payment_method']}\n"
        f"📱 Number: {masked_number}\n"
        f"🆔 Txn ID: <code>{txn_id}</code>\n"
        f"━━━━━━━━━━━━━━━━━━"
    )

    # 1. Send to user
    if tg_id:
        try:
            await bot.send_photo(tg_id, photo_id, caption=caption_user)
            await bot.send_sticker(tg_id, PARTY_STICKER)
        except Exception as e:
            await call.message.answer(f"⚠️ Could not notify user: {e}")

    # 2. Send to group
    try:
        await bot.send_photo(GROUP_ID, photo_id, caption=caption_group)
    except Exception as e:
        logger.error(f"Group send failed: {e}")

    # 3. Send to log channel
    try:
        await bot.send_photo(LOG_CHANNEL, photo_id, caption=caption_group)
    except Exception:
        pass

    # 4. Deduct balance
    await deduct_balance(key, amount)

    # 5. Save withdrawal record
    await save_withdrawal({
        "key": key, "name": user_data["name"],
        "amount": amount, "txn_id": txn_id,
        "method": user_data["payment_method"],
        "date": now,
    })

    # 6. Edit preview
    try:
        await call.message.edit_caption(
            f"✅ <b>Payment Dispatched!</b>\n"
            f"👤 {user_data['name']} | 💵 {amount} ৳\n"
            f"🆔 <code>{txn_id}</code> | 📅 {now}",
            reply_markup=None
        )
    except Exception:
        pass

    # 7. Notify other admins
    for admin_id in ADMIN_IDS:
        if admin_id == call.from_user.id:
            continue
        try:
            await bot.send_message(
                admin_id,
                f"✅ <b>Payment Done</b>\n"
                f"👤 {user_data['name']} | 💵 {amount} ৳\n"
                f"🆔 <code>{txn_id}</code>"
            )
        except Exception:
            pass

    await call.message.answer("✅ <b>Payment dispatched successfully!</b>")
    await state.clear()
    logger.info(f"Payment dispatched: {key} | {amount}৳ | {txn_id}")


# ──────────────────────────────────────────────
#  Admin cancels
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("admin_cancel_"))
async def handle_admin_cancel(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Access Denied!", show_alert=True); return

    key = call.data[len("admin_cancel_"):]
    _pending_ss.pop(call.from_user.id, None)
    await state.clear()
    await call.answer("❌ Cancelled.")
    try:
        await call.message.edit_caption(
            f"❌ <b>Payment Cancelled</b>\n🔑 <code>{key}</code>",
            reply_markup=None
        )
    except Exception:
        pass
    await call.message.answer("❌ Payment process cancelled.")
    logger.info(f"Payment cancelled: {key} by {call.from_user.id}")
