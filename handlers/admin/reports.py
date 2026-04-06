# ============================================================
#  handlers/admin/reports.py  —  Final & 2FA report FSMs
# ============================================================
from datetime import datetime

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from core.bot import bot
from core.state import Report, Report2FA
from core.logger import get_logger, get_admin_logger
from helpers.decorators import admin_only
from helpers.validators import is_valid_amount
from modules.report_builder import build_final_report, build_2fa_report, commit_report
from config import ADMIN_IDS, LOG_ADMIN_ID

router = Router(name="admin_reports")
logger = get_logger("Admin.Reports")
alog   = get_admin_logger()

# per-admin pending report buffers
_pending_report:      dict[int, dict] = {}
_pending_report2fa:   dict[int, dict] = {}


# ──────────────────────────────────────────────
#  Callback entry-points from panel
# ──────────────────────────────────────────────

@router.callback_query(F.data.in_({"adm_report", "adm_report2fa"}))
async def handle_report_callbacks(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Access Denied!", show_alert=True)
        return
    await call.answer()

    if call.data == "adm_report":
        await state.set_state(Report.survived)
        await call.message.answer("📊 Enter <b>Total Accounts Survived</b> from server:")

    elif call.data == "adm_report2fa":
        await state.set_state(Report2FA.survived)
        await call.message.answer("📊 Enter <b>Total 2FA Accounts Survived</b>:")


# ──────────────────────────────────────────────
#  FSM: Final Report
# ──────────────────────────────────────────────

@router.message(Report.survived)
@admin_only
async def report_step_survived(message: Message, state: FSMContext):
    ok, val = is_valid_amount(message.text)
    if not ok:
        await message.answer("❌ Enter a valid positive number:")
        return
    await state.update_data(survived=int(val))
    await state.set_state(Report.prize)
    await message.answer(f"✅ Survived: <b>{int(val)}</b>\n➡️ Enter <b>Prize per Account</b> (৳):")


@router.message(Report.prize)
@admin_only
async def report_step_prize(message: Message, state: FSMContext):
    ok, prize = is_valid_amount(message.text)
    if not ok:
        await message.answer("❌ Enter a valid amount:")
        return
    data     = await state.get_data()
    survived = data.get("survived", 0)
    await state.clear()

    proc = await message.answer("🔄 <i>Processing…</i>")
    rows, preview = await build_final_report(survived, prize)
    if not rows:
        await proc.edit_text(preview)
        return

    _pending_report[message.from_user.id] = {
        "rows": rows,
        "today": datetime.now().strftime("%Y-%m-%d"),
        "prize": prize,
        "survived": survived,
    }
    await proc.delete()

    markup = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Confirm & Commit", callback_data="adm_report_confirm"),
        InlineKeyboardButton(text="❌ Cancel",           callback_data="adm_report_cancel"),
    ]])
    total_pay = sum(r["payment"] for r in rows)
    await message.answer(
        f"📊 <b>Final Report Preview</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{preview}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Survived: <b>{survived}</b>\n"
        f"💲 Prize:    <b>{prize} ৳</b>/acc\n"
        f"💰 Total Pay: <b>{round(total_pay, 2)} ৳</b>\n\n"
        f"<i>Confirm to add balances and save history.</i>",
        reply_markup=markup
    )


@router.callback_query(F.data == "adm_report_confirm")
async def report_confirm(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Access Denied!", show_alert=True)
        return
    pending = _pending_report.pop(call.from_user.id, None)
    if not pending:
        await call.answer("❌ Session expired.", show_alert=True)
        return

    await call.answer("✅ Committing…")
    await commit_report(pending["rows"], pending["today"])
    await call.message.edit_text(
        f"✅ <b>Final Report Committed!</b>\n"
        f"📅 {pending['today']} | 🏆 {pending['survived']} survived\n"
        f"👥 {len(pending['rows'])} users paid.",
        reply_markup=None
    )
    alog.info(
        f"Final report committed | by={call.from_user.id} "
        f"| date={pending['today']} | users={len(pending['rows'])}"
    )
    try:
        await bot.send_message(
            LOG_ADMIN_ID,
            f"📋 <b>Final Report Committed</b>\n"
            f"By: {call.from_user.id}\n"
            f"Date: {pending['today']}\n"
            f"Users: {len(pending['rows'])}"
        )
    except Exception:
        pass


@router.callback_query(F.data == "adm_report_cancel")
async def report_cancel(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Access Denied!", show_alert=True)
        return
    _pending_report.pop(call.from_user.id, None)
    await call.answer("❌ Cancelled.")
    await call.message.edit_text("❌ <b>Report cancelled.</b>", reply_markup=None)


# ──────────────────────────────────────────────
#  FSM: 2FA Report
# ──────────────────────────────────────────────

@router.message(Report2FA.survived)
@admin_only
async def report2fa_survived(message: Message, state: FSMContext):
    ok, val = is_valid_amount(message.text)
    if not ok:
        await message.answer("❌ Enter a valid positive number:")
        return
    await state.update_data(survived=int(val))
    await state.set_state(Report2FA.prize)
    await message.answer(
        f"✅ Survived: <b>{int(val)}</b>\n"
        f"➡️ Enter <b>Prize per 2FA Account</b> (৳):"
    )


@router.message(Report2FA.prize)
@admin_only
async def report2fa_prize(message: Message, state: FSMContext):
    ok, prize = is_valid_amount(message.text)
    if not ok:
        await message.answer("❌ Enter a valid amount:")
        return
    data     = await state.get_data()
    survived = data.get("survived", 0)
    await state.clear()

    proc = await message.answer("🔄 <i>Processing…</i>")
    rows, preview = await build_2fa_report(survived, prize)
    if not rows:
        await proc.edit_text(preview)
        return

    _pending_report2fa[message.from_user.id] = {
        "rows": rows,
        "today": datetime.now().strftime("%Y-%m-%d"),
        "prize": prize,
        "survived": survived,
    }
    await proc.delete()
    markup = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Confirm", callback_data="adm_report2fa_confirm"),
        InlineKeyboardButton(text="❌ Cancel",  callback_data="adm_report2fa_cancel"),
    ]])
    total_pay = sum(r["payment"] for r in rows)
    await message.answer(
        f"🔐 <b>2FA Report Preview</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{preview}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 Total Pay: <b>{round(total_pay, 2)} ৳</b>",
        reply_markup=markup
    )


@router.callback_query(F.data == "adm_report2fa_confirm")
async def report2fa_confirm(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Access Denied!", show_alert=True)
        return
    pending = _pending_report2fa.pop(call.from_user.id, None)
    if not pending:
        await call.answer("❌ Session expired.", show_alert=True)
        return
    await call.answer("✅ Committing…")
    await commit_report(pending["rows"], pending["today"])
    await call.message.edit_text("✅ <b>2FA Report Committed!</b>", reply_markup=None)
    alog.info(
        f"2FA report committed | by={call.from_user.id} "
        f"| date={pending['today']} | users={len(pending['rows'])}"
    )


@router.callback_query(F.data == "adm_report2fa_cancel")
async def report2fa_cancel(call: CallbackQuery):
    _pending_report2fa.pop(call.from_user.id, None)
    await call.answer("❌ Cancelled.")
    await call.message.edit_text("❌ <b>2FA Report cancelled.</b>", reply_markup=None)
