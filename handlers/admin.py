# ============================================================
#  handlers/admin.py  —  Full admin panel
# ============================================================
import io
import os
import random
import string
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, CallbackQuery, BufferedInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton
)

from core.bot import bot
from core.database import (
    load_licenses, save_licenses, get_user_by_key,
    get_today_stats, get_all_time_stats,
    reset_today_stats, reset_all_stats,
    add_balance, delete_user, get_user_profile,
    read_all_csv, read_2fa_csv
)
from core.state import (
    LicenseGen, Report, Report2FA,
    AddBalance, DeleteUser, LicenseCheck
)
from core.logger import get_logger, get_admin_logger
from helpers.decorators import admin_only, admin_callback
from helpers.validators import is_valid_date, is_valid_amount
from helpers.xlsx_builder import build_report_xlsx, build_plain_xlsx
from modules.stats_manager import build_live_pages, live_markup
from modules.report_builder import build_final_report, build_2fa_report, commit_report
from modules.spam_detector import SpamDetector
from config import ADMIN_IDS, LOG_ADMIN_ID, USERS_DIR

router = Router(name="admin")
logger = get_logger("Admin")
alog   = get_admin_logger()

# pending final reports: admin_id → {rows, today, prize, survived}
_pending_report: dict[int, dict] = {}
_pending_report2fa: dict[int, dict] = {}


# ──────────────────────────────────────────────
#  Admin Panel keyboard
# ──────────────────────────────────────────────

def admin_panel_markup() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔑 Gen License",       callback_data="adm_gen"),
            InlineKeyboardButton(text="📊 Export XLSX",       callback_data="adm_export"),
        ],
        [
            InlineKeyboardButton(text="🔐 Export 2FA",        callback_data="adm_export2fa"),
            InlineKeyboardButton(text="💰 Final Report",      callback_data="adm_report"),
        ],
        [
            InlineKeyboardButton(text="💰 2FA Report",        callback_data="adm_report2fa"),
            InlineKeyboardButton(text="🔍 Check License",     callback_data="adm_chk"),
        ],
        [
            InlineKeyboardButton(text="📈 All-Time Stats",    callback_data="adm_stats"),
            InlineKeyboardButton(text="📊 Live Stats",        callback_data="live_0"),
        ],
        [
            InlineKeyboardButton(text="📢 Broadcast",         callback_data="adm_broadcast"),
            InlineKeyboardButton(text="🔄 Reset Stats",       callback_data="adm_resetmenu"),
        ],
        [
            InlineKeyboardButton(text="➕ Add Balance",       callback_data="adm_addbal"),
            InlineKeyboardButton(text="🗑 Delete User",       callback_data="adm_deluser"),
        ],
        [
            InlineKeyboardButton(text="🚫 Spam List",         callback_data="adm_spamlist"),
            InlineKeyboardButton(text="🔓 Unban User",        callback_data="adm_unban"),
        ],
    ])


# ──────────────────────────────────────────────
#  /admin
# ──────────────────────────────────────────────

@router.message(Command("admin", "abidbotol"))
@admin_only
async def cmd_admin_panel(message: Message):
    await message.answer(
        "👑 <b>Admin Control Panel</b>\n"
        "Welcome Boss! Choose an action:",
        reply_markup=admin_panel_markup()
    )


# ──────────────────────────────────────────────
#  /live
# ──────────────────────────────────────────────

@router.message(Command("live"))
@admin_only
async def cmd_live(message: Message):
    pages = await build_live_pages()
    if not pages:
        await message.answer("⚠️ No users found!")
        return
    await message.answer(pages[0], reply_markup=live_markup(0, len(pages)))


@router.callback_query(F.data.startswith("live_"))
async def cb_live(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Access Denied!", show_alert=True); return
    try:
        page = int(call.data.split("_")[1])
    except (IndexError, ValueError):
        await call.answer(); return
    pages = await build_live_pages()
    page  = min(page, len(pages) - 1)
    await call.message.edit_text(pages[page], reply_markup=live_markup(page, len(pages)))
    await call.answer("🔄 Refreshed!")


# ──────────────────────────────────────────────
#  Main admin callback router
# ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("adm_"))
async def handle_admin_callbacks(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Access Denied!", show_alert=True); return

    await call.answer()
    data    = call.data
    chat_id = call.from_user.id

    if data == "adm_gen":
        await state.set_state(LicenseGen.name)
        await call.message.answer("➡️ <b>Step 1/7:</b> Enter Full Name:")

    elif data == "adm_export":
        await _do_export_xlsx(chat_id)

    elif data == "adm_export2fa":
        await _do_export_2fa(chat_id)

    elif data == "adm_chk":
        await state.set_state(LicenseCheck.key)
        await call.message.answer("🔍 Enter License Key to check:")

    elif data == "adm_report":
        await state.set_state(Report.survived)
        await call.message.answer("📊 Enter <b>Total Accounts Survived</b> from server:")

    elif data == "adm_report2fa":
        await state.set_state(Report2FA.survived)
        await call.message.answer("📊 Enter <b>Total 2FA Accounts Survived</b>:")

    elif data == "adm_stats":
        await _do_all_time_stats(chat_id)

    elif data == "adm_broadcast":
        await state.set_state(__import__("core.state", fromlist=["Broadcast"]).Broadcast.message)
        await call.message.answer(
            "📢 <b>Broadcast</b>\nEnter message to send to all users:"
        )

    elif data == "adm_resetmenu":
        await _send_reset_menu(chat_id)

    elif data == "adm_addbal":
        await state.set_state(AddBalance.key)
        await call.message.answer("➕ <b>Add Balance</b>\nEnter License Key:")

    elif data == "adm_deluser":
        await state.set_state(DeleteUser.key)
        await call.message.answer("🗑 <b>Delete User</b>\nEnter License Key:")

    elif data == "adm_spamlist":
        await _show_spam_list(chat_id)

    elif data == "adm_unban":
        await call.message.answer(
            "🔓 Enter user Telegram ID to unban:\n<i>(Send /cancel to abort)</i>"
        )
        # simple next step via state could be added; for now, use /unban command
        await call.message.answer(
            "<i>Use: /unban &lt;user_id&gt;</i>"
        )


# ──────────────────────────────────────────────
#  Reset menu
# ──────────────────────────────────────────────

async def _send_reset_menu(chat_id: int):
    licenses = await load_licenses()
    rows = [[InlineKeyboardButton(text="🔄 Reset ALL Users", callback_data="adm_resetall_ask")]]
    for key, info in licenses.items():
        name = info.get("name", "N/A")
        uname = info.get("username", "N/A")
        rows.append([InlineKeyboardButton(
            text=f"👤 {name} ({uname})",
            callback_data=f"adm_resetuser_{info.get('username', '')}"
        )])
    rows.append([InlineKeyboardButton(text="❌ Cancel", callback_data="adm_resetcancel")])
    markup = InlineKeyboardMarkup(inline_keyboard=rows)
    await bot.send_message(
        chat_id,
        "🔄 <b>Reset Stats Menu</b>\n<i>Choose who to reset:</i>",
        reply_markup=markup
    )


@router.callback_query(F.data.startswith("adm_reset"))
async def handle_reset_callbacks(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Access Denied!", show_alert=True); return

    data = call.data

    if data == "adm_resetcancel":
        await call.answer("❌ Cancelled.")
        await call.message.edit_text("❌ <b>Reset cancelled.</b>", reply_markup=None)

    elif data == "adm_resetall_ask":
        await call.answer()
        markup = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ YES Reset ALL", callback_data="adm_resetall_confirm"),
            InlineKeyboardButton(text="❌ Cancel",        callback_data="adm_resetcancel"),
        ]])
        await call.message.answer(
            "⚠️ <b>Reset ALL users' stats?</b>\n<i>This cannot be undone!</i>",
            reply_markup=markup
        )

    elif data == "adm_resetall_confirm":
        await call.answer("🔄 Resetting…")
        users = await reset_all_stats()
        await call.message.edit_text(
            f"✅ <b>All Stats Reset!</b>\n👥 {len(users)} users cleared.",
            reply_markup=None
        )
        alog.info(f"Admin {call.from_user.id} reset ALL stats")

    elif data.startswith("adm_resetuser_"):
        username = data[len("adm_resetuser_"):]
        await call.answer("🔄 Resetting…")
        cleared  = await reset_today_stats(username)
        await call.message.edit_text(
            f"✅ <b>Stats Reset!</b>\n👤 <code>{username}</code>\n🗑 {len(cleared)} files cleared.",
            reply_markup=None
        )
        alog.info(f"Admin {call.from_user.id} reset stats for {username}")


# ──────────────────────────────────────────────
#  /resetstats command shortcut
# ──────────────────────────────────────────────

@router.message(Command("resetstats"))
@admin_only
async def cmd_resetstats(message: Message):
    args = message.text.strip().split()
    if len(args) == 1:
        await _send_reset_menu(message.chat.id)
    else:
        username = args[1].strip()
        cleared  = await reset_today_stats(username)
        if cleared:
            await message.answer(
                f"✅ <b>Stats Reset!</b>\n👤 <code>{username}</code>\n🗑 {len(cleared)} files cleared."
            )
        else:
            await message.answer(f"⚠️ No stat files found for <code>{username}</code>.")


# ──────────────────────────────────────────────
#  FSM: License Generation (7 steps)
# ──────────────────────────────────────────────

@router.message(LicenseGen.name)
@admin_only
async def gen_step_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await state.set_state(LicenseGen.username)
    await message.answer("✅ Name saved.\n➡️ <b>Step 2/7:</b> Enter Username (folder name):")


@router.message(LicenseGen.username)
@admin_only
async def gen_step_username(message: Message, state: FSMContext):
    await state.update_data(username=message.text.strip())
    await state.set_state(LicenseGen.validity)
    await message.answer("✅ Username saved.\n➡️ <b>Step 3/7:</b> Enter Validity (YYYY-MM-DD):")


@router.message(LicenseGen.validity)
@admin_only
async def gen_step_validity(message: Message, state: FSMContext):
    if not is_valid_date(message.text.strip()):
        await message.answer("❌ Invalid format! Use <b>YYYY-MM-DD</b>. Try again:")
        return
    await state.update_data(validity=message.text.strip())
    await state.set_state(LicenseGen.pay_num)
    await message.answer("✅ Validity saved.\n➡️ <b>Step 4/7:</b> Enter Payment Number:")


@router.message(LicenseGen.pay_num)
@admin_only
async def gen_step_pay_num(message: Message, state: FSMContext):
    await state.update_data(pay_num=message.text.strip())
    await state.set_state(LicenseGen.pay_method)
    await message.answer("✅ Number saved.\n➡️ <b>Step 5/7:</b> Enter Payment Method (bKash/Nagad/Rocket):")


@router.message(LicenseGen.pay_method)
@admin_only
async def gen_step_pay_method(message: Message, state: FSMContext):
    await state.update_data(pay_method=message.text.strip())
    await state.set_state(LicenseGen.mentor_key)
    await message.answer(
        "✅ Method saved.\n➡️ <b>Step 6/7:</b> Enter <b>Mentor License Key</b>:\n"
        "<i>Type <b>done</b> if no mentor.</i>"
    )


@router.message(LicenseGen.mentor_key)
@admin_only
async def gen_step_mentor_key(message: Message, state: FSMContext):
    text = message.text.strip()
    if text.lower() == "done":
        await state.update_data(mentor_key="", mentor_bonus=0.0)
        await _finish_gen(message, state)
        return
    mentor_key = text.upper()
    licenses   = await load_licenses()
    if mentor_key not in licenses:
        await message.answer(
            f"❌ Mentor key <code>{mentor_key}</code> not found!\n"
            f"Try again or type <b>done</b> to skip."
        )
        return
    mentor_name = licenses[mentor_key].get("name", "N/A")
    await state.update_data(mentor_key=mentor_key)
    await state.set_state(LicenseGen.mentor_bonus)
    await message.answer(
        f"✅ Mentor: <b>{mentor_name}</b>\n"
        f"➡️ <b>Step 7/7:</b> Per-account bonus for mentor (৳):\n"
        f"<i>Type <b>0</b> for no bonus.</i>"
    )


@router.message(LicenseGen.mentor_bonus)
@admin_only
async def gen_step_mentor_bonus(message: Message, state: FSMContext):
    ok, val = is_valid_amount(message.text)
    if not ok and message.text.strip() != "0":
        await message.answer("❌ Enter a valid amount (e.g. 5.50):")
        return
    try:
        bonus = float(message.text.strip())
    except Exception:
        bonus = 0.0
    await state.update_data(mentor_bonus=bonus)
    await _finish_gen(message, state)


async def _finish_gen(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    mentor_key   = data.get("mentor_key", "")
    mentor_bonus = data.get("mentor_bonus", 0.0)
    licenses     = await load_licenses()

    # Build key prefix
    if mentor_key and mentor_key in licenses:
        prefix = "".join(c for c in licenses[mentor_key].get("name", "SML").upper() if c.isalnum())[:10]
    else:
        prefix = "SML"

    key = f"{prefix}-SML-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

    licenses[key] = {
        "name":                    data["name"],
        "username":                data["username"],
        "validity":                data["validity"],
        "payment_number":          data["pay_num"],
        "payment_method":          data["pay_method"],
        "mentor_key":              mentor_key,
        "mentor_per_account_bonus": mentor_bonus,
        "mentor_bonus":            0.0,
        "tg_id":                   "",
        "balance":                 0.0,
        "total_withdraws":         0,
        "total_earned":            0.0,
        "joined":                  "",
        "history":                 {},
    }
    await save_licenses(licenses)
    os.makedirs(os.path.join(USERS_DIR, data["username"]), exist_ok=True)

    mentor_line = ""
    if mentor_key and mentor_key in licenses:
        mname       = licenses[mentor_key].get("name", "N/A")
        mentor_line = (
            f"👨‍🏫 Mentor: <b>{mname}</b> (<code>{mentor_key}</code>)\n"
            f"🎁 Bonus: <b>{mentor_bonus} ৳</b>/account\n"
        )
    else:
        mentor_line = "👨‍🏫 Mentor: None\n"

    await message.answer(
        f"✨ <b>License Created!</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔑 Key:      <code>{key}</code>\n"
        f"👤 Name:     {data['name']}\n"
        f"📂 Username: {data['username']}\n"
        f"⏳ Valid:    {data['validity']}\n"
        f"💳 {data['pay_method']} — {data['pay_num']}\n"
        f"{mentor_line}"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<i>Share this key with the user.</i>"
    )
    alog.info(f"License created: {key} for {data['name']}")


# ──────────────────────────────────────────────
#  FSM: License Check
# ──────────────────────────────────────────────

@router.message(LicenseCheck.key)
@admin_only
async def do_license_check(message: Message, state: FSMContext):
    await state.clear()
    key      = message.text.strip().upper()
    licenses = await load_licenses()
    if key not in licenses:
        await message.answer(f"❌ License <code>{key}</code> not found!")
        return
    info       = licenses[key]
    stats      = await get_today_stats(info.get("username", ""))
    history    = info.get("history", {})
    total_aprv = sum(d.get("aprv", 0) for d in history.values())
    total_sub  = sum(d.get("sub",  0) for d in history.values())
    total_rej  = sum(d.get("rej",  0) for d in history.values())

    mentor_key  = info.get("mentor_key", "")
    mentor_line = ""
    if mentor_key and mentor_key in licenses:
        mname        = licenses[mentor_key].get("name", "N/A")
        bonus        = info.get("mentor_per_account_bonus", 0.0)
        mentor_line  = f"👨‍🏫 Mentor: <b>{mname}</b> | {bonus} ৳/acc\n"

    text = (
        f"🔍 <b>License Details</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔑 Key:      <code>{key}</code>\n"
        f"👤 Name:     {info.get('name','N/A')}\n"
        f"📂 Username: {info.get('username','N/A')}\n"
        f"⏳ Valid:    {info.get('validity','N/A')}\n"
        f"💳 {info.get('payment_method','N/A')} — {info.get('payment_number','N/A')}\n"
        f"{mentor_line}"
        f"🤖 TG ID:    {info.get('tg_id') or 'Not started'}\n"
        f"💰 Balance:  {info.get('balance', 0.0)} ৳\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📊 <b>Today:</b> ✅{stats['aprv']} 📥{stats['sub']} ❌{stats['rej']} 📈{stats['pct']}%\n"
        f"📈 <b>All-Time:</b> ✅{total_aprv} 📥{total_sub} ❌{total_rej} 📅{len(history)}d\n"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Export History TXT", callback_data=f"adm_hist_{key}")]
    ])
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith("adm_hist_"))
async def export_history_txt(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Access Denied!", show_alert=True); return
    key      = call.data[len("adm_hist_"):]
    licenses = await load_licenses()
    if key not in licenses:
        await call.answer("❌ Not found!"); return
    info    = licenses[key]
    history = info.get("history", {})
    lines   = [
        f"Payment History — {info.get('name','N/A')} ({key})",
        f"Username: {info.get('username','N/A')}",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "=" * 50,
    ]
    for date in sorted(history.keys(), reverse=True):
        d = history[date]
        lines.append(
            f"{date} | Aprv: {d.get('aprv',0)} | Sub: {d.get('sub',0)} | "
            f"Rej: {d.get('rej',0)} | Rate: {d.get('pct',0)}%"
        )
    content = "\n".join(lines).encode("utf-8")
    await bot.send_document(
        call.from_user.id,
        BufferedInputFile(content, filename=f"history_{key}.txt"),
        caption=f"📄 History: <code>{key}</code> | {len(history)} entries"
    )
    await call.answer("📄 Exported!")


# ──────────────────────────────────────────────
#  FSM: Final Report
# ──────────────────────────────────────────────

@router.message(Report.survived)
@admin_only
async def report_step_survived(message: Message, state: FSMContext):
    ok, val = is_valid_amount(message.text)
    if not ok:
        await message.answer("❌ Enter a valid positive number:"); return
    await state.update_data(survived=int(val))
    await state.set_state(Report.prize)
    await message.answer(f"✅ Survived: <b>{int(val)}</b>\n➡️ Enter <b>Prize per Account</b> (৳):")


@router.message(Report.prize)
@admin_only
async def report_step_prize(message: Message, state: FSMContext):
    ok, prize = is_valid_amount(message.text)
    if not ok:
        await message.answer("❌ Enter a valid amount:"); return
    data     = await state.get_data()
    survived = data.get("survived", 0)
    await state.clear()

    proc = await message.answer("🔄 <i>Processing…</i>")
    rows, preview = await build_final_report(survived, prize)
    if not rows:
        await proc.edit_text(preview); return

    _pending_report[message.from_user.id] = {
        "rows": rows, "today": datetime.now().strftime("%Y-%m-%d"),
        "prize": prize, "survived": survived
    }
    await proc.delete()

    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Confirm & Commit", callback_data="adm_report_confirm"),
            InlineKeyboardButton(text="❌ Cancel",           callback_data="adm_report_cancel"),
        ]
    ])
    total_pay = sum(r["payment"] for r in rows)
    await message.answer(
        f"📊 <b>Final Report Preview</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{preview}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🏆 Survived: <b>{survived}</b>\n"
        f"💲 Prize: <b>{prize} ৳</b>/acc\n"
        f"💰 Total Pay: <b>{round(total_pay, 2)} ৳</b>\n\n"
        f"<i>Confirm to add balances and save history.</i>",
        reply_markup=markup
    )


@router.callback_query(F.data == "adm_report_confirm")
async def report_confirm(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Access Denied!", show_alert=True); return
    pending = _pending_report.pop(call.from_user.id, None)
    if not pending:
        await call.answer("❌ Session expired.", show_alert=True); return
    await call.answer("✅ Committing…")
    await commit_report(pending["rows"], pending["today"])
    await call.message.edit_text(
        f"✅ <b>Final Report Committed!</b>\n"
        f"📅 {pending['today']} | 🏆 {pending['survived']} survived\n"
        f"👥 {len(pending['rows'])} users paid.",
        reply_markup=None
    )
    alog.info(f"Admin {call.from_user.id} committed final report: {pending['today']}")

    # Log to log admin
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
        await call.answer("❌ Access Denied!", show_alert=True); return
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
        await message.answer("❌ Enter a valid positive number:"); return
    await state.update_data(survived=int(val))
    await state.set_state(Report2FA.prize)
    await message.answer(f"✅ Survived: <b>{int(val)}</b>\n➡️ Enter <b>Prize per 2FA Account</b> (৳):")


@router.message(Report2FA.prize)
@admin_only
async def report2fa_prize(message: Message, state: FSMContext):
    ok, prize = is_valid_amount(message.text)
    if not ok:
        await message.answer("❌ Enter a valid amount:"); return
    data     = await state.get_data()
    survived = data.get("survived", 0)
    await state.clear()

    proc = await message.answer("🔄 <i>Processing…</i>")
    rows, preview = await build_2fa_report(survived, prize)
    if not rows:
        await proc.edit_text(preview); return

    _pending_report2fa[message.from_user.id] = {
        "rows": rows, "today": datetime.now().strftime("%Y-%m-%d"),
        "prize": prize, "survived": survived
    }
    await proc.delete()
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Confirm", callback_data="adm_report2fa_confirm"),
            InlineKeyboardButton(text="❌ Cancel",  callback_data="adm_report2fa_cancel"),
        ]
    ])
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
        await call.answer("❌ Access Denied!", show_alert=True); return
    pending = _pending_report2fa.pop(call.from_user.id, None)
    if not pending:
        await call.answer("❌ Session expired.", show_alert=True); return
    await call.answer("✅ Committing…")
    await commit_report(pending["rows"], pending["today"])
    await call.message.edit_text("✅ <b>2FA Report Committed!</b>", reply_markup=None)


@router.callback_query(F.data == "adm_report2fa_cancel")
async def report2fa_cancel(call: CallbackQuery):
    _pending_report2fa.pop(call.from_user.id, None)
    await call.answer("❌ Cancelled.")
    await call.message.edit_text("❌ <b>2FA Report cancelled.</b>", reply_markup=None)


# ──────────────────────────────────────────────
#  FSM: Add Balance
# ──────────────────────────────────────────────

@router.message(AddBalance.key)
@admin_only
async def addbal_step_key(message: Message, state: FSMContext):
    key      = message.text.strip().upper()
    licenses = await load_licenses()
    if key not in licenses:
        await message.answer(f"❌ Key <code>{key}</code> not found!"); return
    name = licenses[key].get("name", "N/A")
    await state.update_data(key=key)
    await state.set_state(AddBalance.amount)
    await message.answer(f"✅ Found: <b>{name}</b>\n➕ Enter amount to add (৳):")


@router.message(AddBalance.amount)
@admin_only
async def addbal_step_amount(message: Message, state: FSMContext):
    ok, amount = is_valid_amount(message.text)
    if not ok:
        await message.answer("❌ Enter a valid positive number:"); return
    data     = await state.get_data()
    key      = data.get("key", "")
    await state.clear()

    licenses = await load_licenses()
    if key not in licenses:
        await message.answer("❌ Session expired."); return

    info            = licenses[key]
    old_bal         = info.get("balance", 0.0)
    new_bal         = round(old_bal + amount, 2)
    info["balance"] = new_bal
    await save_licenses(licenses)

    # Auto reset stats
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
        from core.database import get_today_stats
        today_stats   = await get_today_stats(username)
        approved      = today_stats["aprv"]
        bonus_amount  = round(approved * mentor_bonus, 2)
        if bonus_amount > 0:
            mentor_info              = licenses[mentor_key]
            mentor_bal               = round(mentor_info.get("balance", 0.0) + bonus_amount, 2)
            mentor_info["balance"]   = mentor_bal
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
    alog.info(f"Admin {message.from_user.id} added {amount}৳ to {key}")


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
        await state.clear(); return
    name = licenses[key].get("name", "N/A")
    await state.clear()
    markup = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"✅ Delete {name}", callback_data=f"adm_delconfirm_{key}"),
        InlineKeyboardButton(text="❌ Cancel",          callback_data="adm_delcancel"),
    ]])
    await message.answer(
        f"⚠️ <b>Delete user?</b>\n👤 {name}\n🔑 <code>{key}</code>",
        reply_markup=markup
    )


@router.callback_query(F.data.startswith("adm_delconfirm_"))
async def delete_confirm(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Access Denied!", show_alert=True); return
    key = call.data[len("adm_delconfirm_"):]
    await delete_user(key)
    await call.answer("✅ Deleted!")
    await call.message.edit_text(f"✅ <b>User deleted:</b> <code>{key}</code>", reply_markup=None)
    alog.info(f"Admin {call.from_user.id} deleted license {key}")


@router.callback_query(F.data == "adm_delcancel")
async def delete_cancel(call: CallbackQuery):
    await call.answer("❌ Cancelled.")
    await call.message.edit_text("❌ <b>Deletion cancelled.</b>", reply_markup=None)


# ──────────────────────────────────────────────
#  All-Time Stats
# ──────────────────────────────────────────────

async def _do_all_time_stats(chat_id: int):
    stats = await get_all_time_stats()
    if not stats:
        await bot.send_message(chat_id, "⚠️ No data found."); return
    lines = []
    for s in sorted(stats, key=lambda x: x["total_aprv"], reverse=True):
        lines.append(
            f"👤 <b>{s['name']}</b>\n"
            f"   ✅{s['total_aprv']} 📥{s['total_sub']} ❌{s['total_rej']} "
            f"📅{s['days_active']}d 💰{s['balance']}৳"
        )
    text = "📈 <b>All-Time Stats</b>\n━━━━━━━━━━━━━━━━━━\n" + "\n".join(lines)
    # Export as XLSX too
    buf     = build_report_xlsx(stats, "All-Time Stats",
                                ["name", "username", "total_aprv", "total_sub",
                                 "total_rej", "days_active", "balance"])
    today   = datetime.now().strftime("%Y-%m-%d")
    await bot.send_message(chat_id, text[:4000])
    await bot.send_document(
        chat_id,
        BufferedInputFile(buf.read(), filename=f"AllTimeStats_{today}.xlsx"),
        caption="📊 All-Time Stats Export"
    )


# ──────────────────────────────────────────────
#  XLSX Exports
# ──────────────────────────────────────────────

async def _do_export_xlsx(chat_id: int):
    rows = await read_all_csv()
    if not rows:
        await bot.send_message(chat_id, "⚠️ All.csv is empty or not found!"); return
    formatted = [
        {"Username": r.get("IG_Username", r.get("username", "")).strip(),
         "Password": r.get("IG_Password", r.get("password", "")).strip()}
        for r in rows
        if (r.get("IG_Username") or r.get("username", "")).strip()
    ]
    if not formatted:
        await bot.send_message(chat_id, "⚠️ No valid data found!"); return
    buf   = build_plain_xlsx(formatted, ["Username", "Password"])
    today = datetime.now().strftime("%Y-%m-%d")
    await bot.send_document(
        chat_id,
        BufferedInputFile(buf.read(), filename=f"Accounts_{today}.xlsx"),
        caption=f"📊 <b>Accounts Export</b>\n📅 {today}\n👥 {len(formatted)}"
    )


async def _do_export_2fa(chat_id: int):
    rows = await read_2fa_csv()
    if not rows:
        await bot.send_message(chat_id, "⚠️ 2FA CSV empty or not found!"); return
    buf   = build_report_xlsx(rows, "2FA Accounts", ["Username", "Password", "2FA Secret"])
    today = datetime.now().strftime("%Y-%m-%d")
    await bot.send_document(
        chat_id,
        BufferedInputFile(buf.read(), filename=f"2FA_Accounts_{today}.xlsx"),
        caption=f"🔐 <b>2FA Export</b>\n📅 {today}\n👥 {len(rows)}"
    )


# ──────────────────────────────────────────────
#  Spam management
# ──────────────────────────────────────────────

async def _show_spam_list(chat_id: int):
    banned = await SpamDetector.get_all_banned()
    if not banned:
        await bot.send_message(chat_id, "✅ No banned users."); return
    lines = ["🚫 <b>Banned Users</b>\n━━━━━━━━━━━━━━━━━━"]
    for b in banned:
        perm  = "♾️ PERMANENT" if b.get("permanent") else "⏰ Temp"
        lines.append(f"• <code>{b['user_id']}</code> — {perm} | {b.get('reason','?')}")
    await bot.send_message(chat_id, "\n".join(lines))


@router.message(Command("unban"))
@admin_only
async def cmd_unban(message: Message):
    args = message.text.strip().split()
    if len(args) < 2:
        await message.answer("Usage: /unban <user_id>"); return
    try:
        uid = int(args[1])
    except ValueError:
        await message.answer("❌ Invalid user ID."); return
    ok = await SpamDetector.unban(uid)
    if ok:
        await message.answer(f"✅ User <code>{uid}</code> unbanned.")
        alog.info(f"Admin {message.from_user.id} unbanned {uid}")
    else:
        await message.answer(f"⚠️ User <code>{uid}</code> was not banned.")


@router.message(Command("ban"))
@admin_only
async def cmd_ban(message: Message):
    args = message.text.strip().split()
    if len(args) < 2:
        await message.answer("Usage: /ban <user_id> [permanent]"); return
    try:
        uid  = int(args[1])
        perm = len(args) > 2 and args[2].lower() == "permanent"
    except ValueError:
        await message.answer("❌ Invalid user ID."); return
    await SpamDetector.ban(uid, permanent=perm, reason="manual_admin")
    label = "permanently" if perm else f"for {__import__('config').SPAM_BAN_MINS} min"
    await message.answer(f"🚫 User <code>{uid}</code> banned {label}.")
    alog.info(f"Admin {message.from_user.id} banned {uid} permanent={perm}")
