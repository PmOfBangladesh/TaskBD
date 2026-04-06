# ============================================================
#  handlers/admin/broadcast.py  —  Broadcast to all users
# ============================================================
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from core.bot import bot
from core.database import load_licenses
from core.state import Broadcast
from core.logger import get_logger
from helpers.decorators import admin_only
from config import ADMIN_IDS

router = Router(name="admin_broadcast")
logger = get_logger("Admin.Broadcast")


# ──────────────────────────────────────────────
#  Callback entry-point from panel
# ──────────────────────────────────────────────

@router.callback_query(F.data == "adm_broadcast")
async def cb_broadcast(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Access Denied!", show_alert=True)
        return
    await call.answer()
    await state.set_state(Broadcast.message)
    await call.message.answer(
        "📢 <b>Broadcast</b>\n"
        "Enter the message to send to all users:\n"
        "<i>Supports HTML formatting. Send /cancel to abort.</i>"
    )


# ──────────────────────────────────────────────
#  /broadcast command
# ──────────────────────────────────────────────

@router.message(Command("broadcast"))
@admin_only
async def cmd_broadcast(message: Message, state: FSMContext):
    await state.set_state(Broadcast.message)
    await message.answer(
        "📢 <b>Broadcast</b>\n"
        "Enter the message to send to all users:\n"
        "<i>Supports HTML formatting. Send /cancel to abort.</i>"
    )


@router.message(Command("cancel"), Broadcast.message)
async def cancel_broadcast(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Broadcast cancelled.")


@router.message(Broadcast.message)
async def do_broadcast(message: Message, state: FSMContext):
    await state.clear()
    licenses = await load_licenses()
    sent = failed = 0

    status_msg = await message.answer(f"📢 Broadcasting to {len(licenses)} users…")

    for key, info in licenses.items():
        tg_id = info.get("tg_id")
        if not tg_id:
            continue
        try:
            await bot.send_message(
                tg_id,
                f"📢 <b>Announcement</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"{message.text or message.caption or ''}",
            )
            sent += 1
        except Exception:
            failed += 1

    await status_msg.edit_text(
        f"✅ <b>Broadcast Complete!</b>\n"
        f"📤 Sent:   <b>{sent}</b>\n"
        f"❌ Failed: <b>{failed}</b>"
    )
    logger.info(
        f"Broadcast complete | sent={sent} | failed={failed} | by={message.from_user.id}"
    )
