# ============================================================
#  handlers/admin/maintenance.py  —  Spam, ban/unban, exports
# ============================================================
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, CallbackQuery, BufferedInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from core.bot import bot
from core.database import read_all_csv, read_2fa_csv
from core.logger import get_logger, get_admin_logger
from core.state import BanUser
from helpers.decorators import admin_only
from helpers.xlsx_builder import build_report_xlsx, build_plain_xlsx
from modules.spam_detector import SpamDetector
from config import ADMIN_IDS, SPAM_BAN_MINS

router = Router(name="admin_maintenance")
logger = get_logger("Admin.Maintenance")
alog   = get_admin_logger()


# ──────────────────────────────────────────────
#  Callback entry-points from panel
# ──────────────────────────────────────────────

@router.callback_query(F.data.in_({"adm_spamlist", "adm_unban", "adm_export",
                                    "adm_export2fa", "adm_ban"}))
async def handle_maintenance_callbacks(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Access Denied!", show_alert=True)
        return
    await call.answer()

    if call.data == "adm_spamlist":
        await _show_spam_list(call.from_user.id)

    elif call.data == "adm_ban":
        await state.set_state(BanUser.user_id)
        await call.message.answer(
            "🚫 <b>Ban User</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "Enter the <b>User ID</b> to ban:\n"
            "<i>Tip: reply /cancel to abort.</i>"
        )

    elif call.data == "adm_unban":
        await call.message.answer(
            "<i>Use: /unban &lt;user_id&gt;  — or tap the button and enter ID below.</i>"
        )

    elif call.data == "adm_export":
        await _do_export_xlsx(call.from_user.id)

    elif call.data == "adm_export2fa":
        await _do_export_2fa(call.from_user.id)


# ──────────────────────────────────────────────
#  FSM: Ban via inline panel
# ──────────────────────────────────────────────

@router.message(Command("cancel"), BanUser.user_id)
@router.message(Command("cancel"), BanUser.reason)
async def cancel_ban(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ <b>Ban cancelled.</b>")


@router.message(BanUser.user_id)
async def ban_step_uid(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
    raw = message.text.strip()
    try:
        uid = int(raw)
    except ValueError:
        await message.answer("❌ Invalid user ID. Enter a number:")
        return
    await state.clear()
    markup = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="♾️ Permanent",  callback_data=f"ban_perm_{uid}"),
        InlineKeyboardButton(text=f"⏰ {SPAM_BAN_MINS} min", callback_data=f"ban_temp_{uid}"),
        InlineKeyboardButton(text="❌ Cancel",      callback_data="ban_cancel"),
    ]])
    await message.answer(
        f"🚫 <b>Choose ban type for <code>{uid}</code>:</b>",
        reply_markup=markup,
    )


@router.callback_query(F.data.startswith("ban_perm_"))
async def ban_permanent(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Access Denied!", show_alert=True)
        return
    uid = int(call.data[len("ban_perm_"):])
    await SpamDetector.ban(uid, permanent=True, reason="manual_admin")
    await call.answer("✅ Banned permanently!")
    await call.message.edit_text(
        f"🚫 <b>User Banned</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 ID: <code>{uid}</code>\n"
        f"♾️ Type: <b>Permanent</b>\n"
        f"🛡 Reason: manual_admin",
        reply_markup=None,
    )
    alog.info(f"Permanent ban | uid={uid} | by={call.from_user.id}")


@router.callback_query(F.data.startswith("ban_temp_"))
async def ban_temporary(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Access Denied!", show_alert=True)
        return
    uid = int(call.data[len("ban_temp_"):])
    await SpamDetector.ban(uid, permanent=False, reason="manual_admin")
    await call.answer(f"✅ Banned for {SPAM_BAN_MINS} min!")
    await call.message.edit_text(
        f"🚫 <b>User Banned</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 ID: <code>{uid}</code>\n"
        f"⏰ Type: <b>Temporary ({SPAM_BAN_MINS} min)</b>\n"
        f"🛡 Reason: manual_admin",
        reply_markup=None,
    )
    alog.info(f"Temp ban | uid={uid} | mins={SPAM_BAN_MINS} | by={call.from_user.id}")


@router.callback_query(F.data == "ban_cancel")
async def ban_cancel_cb(call: CallbackQuery):
    await call.answer("❌ Cancelled.")
    await call.message.edit_text("❌ <b>Ban cancelled.</b>", reply_markup=None)


# ──────────────────────────────────────────────
#  /ban  /unban commands
# ──────────────────────────────────────────────

@router.message(Command("ban"))
@admin_only
async def cmd_ban(message: Message):
    args = message.text.strip().split()
    if len(args) < 2:
        await message.answer(
            "📖 <b>Usage:</b> <code>/ban &lt;user_id&gt; [permanent]</code>\n"
            "<i>Omit 'permanent' for a timed ban.</i>"
        )
        return
    try:
        uid  = int(args[1])
        perm = len(args) > 2 and args[2].lower() == "permanent"
    except ValueError:
        await message.answer("❌ Invalid user ID.")
        return
    await SpamDetector.ban(uid, permanent=perm, reason="manual_admin")
    label = "♾️ permanently" if perm else f"⏰ for {SPAM_BAN_MINS} min"
    await message.answer(
        f"🚫 <b>User Banned</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 ID: <code>{uid}</code>\n"
        f"🔒 Duration: <b>{label}</b>"
    )
    alog.info(f"User banned | uid={uid} | permanent={perm} | by={message.from_user.id}")


@router.message(Command("unban"))
@admin_only
async def cmd_unban(message: Message):
    args = message.text.strip().split()
    if len(args) < 2:
        await message.answer("📖 <b>Usage:</b> <code>/unban &lt;user_id&gt;</code>")
        return
    try:
        uid = int(args[1])
    except ValueError:
        await message.answer("❌ Invalid user ID.")
        return
    ok = await SpamDetector.unban(uid)
    if ok:
        await message.answer(
            f"✅ <b>User Unbanned</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 ID: <code>{uid}</code>"
        )
        alog.info(f"User unbanned | uid={uid} | by={message.from_user.id}")
    else:
        await message.answer(f"⚠️ User <code>{uid}</code> was not banned.")


# ──────────────────────────────────────────────
#  Spam list helper
# ──────────────────────────────────────────────

async def _show_spam_list(chat_id: int):
    banned = await SpamDetector.get_all_banned()
    if not banned:
        await bot.send_message(chat_id, "✅ <b>No banned users.</b>")
        return
    lines = ["🚫 <b>Banned Users</b>\n━━━━━━━━━━━━━━━━━━"]
    for b in banned:
        perm  = "♾️ PERMANENT" if b.get("permanent") else "⏰ Temp"
        lines.append(
            f"• <code>{b['user_id']}</code> — {perm} | {b.get('reason', '?')}"
        )
    await bot.send_message(chat_id, "\n".join(lines))


# ──────────────────────────────────────────────
#  XLSX export helpers
# ──────────────────────────────────────────────

async def _do_export_xlsx(chat_id: int):
    rows = await read_all_csv()
    if not rows:
        await bot.send_message(chat_id, "⚠️ All.csv is empty or not found!")
        return
    formatted = [
        {
            "Username": r.get("IG_Username", r.get("username", "")).strip(),
            "Password": r.get("IG_Password", r.get("password", "")).strip(),
        }
        for r in rows
        if (r.get("IG_Username") or r.get("username", "")).strip()
    ]
    if not formatted:
        await bot.send_message(chat_id, "⚠️ No valid data found!")
        return
    buf   = build_plain_xlsx(formatted, ["Username", "Password"])
    today = datetime.now().strftime("%Y-%m-%d")
    await bot.send_document(
        chat_id,
        BufferedInputFile(buf.read(), filename=f"Accounts_{today}.xlsx"),
        caption=f"📊 <b>Accounts Export</b>\n📅 {today}\n👥 {len(formatted)}"
    )
    logger.info(f"XLSX export sent | rows={len(formatted)} | to={chat_id}")


async def _do_export_2fa(chat_id: int):
    rows = await read_2fa_csv()
    if not rows:
        await bot.send_message(chat_id, "⚠️ 2FA CSV empty or not found!")
        return
    buf   = build_report_xlsx(rows, "2FA Accounts", ["Username", "Password", "2FA Secret"])
    today = datetime.now().strftime("%Y-%m-%d")
    await bot.send_document(
        chat_id,
        BufferedInputFile(buf.read(), filename=f"2FA_Accounts_{today}.xlsx"),
        caption=f"🔐 <b>2FA Export</b>\n📅 {today}\n👥 {len(rows)}"
    )
    logger.info(f"2FA XLSX export sent | rows={len(rows)} | to={chat_id}")
