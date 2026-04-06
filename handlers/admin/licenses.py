# ============================================================
#  handlers/admin/licenses.py  —  License generation & check
# ============================================================
import os
import random
import string
from datetime import datetime

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, CallbackQuery, BufferedInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from core.bot import bot
from core.database import load_licenses, save_licenses, get_today_stats
from core.state import LicenseGen, LicenseCheck
from core.logger import get_logger, get_admin_logger
from helpers.decorators import admin_only
from helpers.validators import is_valid_date, is_valid_amount
from config import ADMIN_IDS, USERS_DIR

router = Router(name="admin_licenses")
logger = get_logger("Admin.Licenses")
alog   = get_admin_logger()


# ──────────────────────────────────────────────
#  Callback entry-points from panel
# ──────────────────────────────────────────────

@router.callback_query(F.data.in_({"adm_gen", "adm_chk"}))
async def handle_license_callbacks(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Access Denied!", show_alert=True)
        return
    await call.answer()

    if call.data == "adm_gen":
        await state.set_state(LicenseGen.name)
        await call.message.answer("➡️ <b>Step 1/7:</b> Enter Full Name:")

    elif call.data == "adm_chk":
        await state.set_state(LicenseCheck.key)
        await call.message.answer("🔍 Enter License Key to check:")


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


# ──────────────────────────────────────────────
#  Helper: build license key prefix from mentor name
# ──────────────────────────────────────────────

def _make_prefix(mentor_key: str, licenses: dict) -> str:
    """Return alphanumeric prefix from mentor's name, fallback to 'SML'."""
    if mentor_key and mentor_key in licenses:
        raw    = licenses[mentor_key].get("name", "").upper()
        prefix = "".join(c for c in raw if c.isalnum())[:10]
        if prefix:
            return prefix
    return "SML"


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
            "Try again or type <b>done</b> to skip."
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

    prefix = _make_prefix(mentor_key, licenses)

    prefix = _make_prefix(mentor_key, licenses)
    key = f"{prefix}-SML-" + "".join(
        random.choices(string.ascii_uppercase + string.digits, k=6)
    )

    licenses[key] = {
        "name":                     data["name"],
        "username":                 data["username"],
        "validity":                 data["validity"],
        "payment_number":           data["pay_num"],
        "payment_method":           data["pay_method"],
        "mentor_key":               mentor_key,
        "mentor_per_account_bonus": mentor_bonus,
        "mentor_bonus":             0.0,
        "tg_id":                    "",
        "balance":                  0.0,
        "total_withdraws":          0,
        "total_earned":             0.0,
        "joined":                   "",
        "history":                  {},
    }
    await save_licenses(licenses)
    os.makedirs(os.path.join(USERS_DIR, data["username"]), exist_ok=True)

    if mentor_key and mentor_key in licenses:
        mname       = licenses[mentor_key].get("name", "N/A")
        mentor_line = (
            f"👨‍🏫 Mentor: <b>{mname}</b> (<code>{mentor_key}</code>)\n"
            f"🎁 Bonus:  <b>{mentor_bonus} ৳</b>/account\n"
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
    alog.info(f"License created: {key} | name={data['name']} | by={message.from_user.id}")


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
        mname       = licenses[mentor_key].get("name", "N/A")
        bonus       = info.get("mentor_per_account_bonus", 0.0)
        mentor_line = f"👨‍🏫 Mentor: <b>{mname}</b> | {bonus} ৳/acc\n"

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
        f"📊 <b>Today:</b>    ✅{stats['aprv']} 📥{stats['sub']} ❌{stats['rej']} 📈{stats['pct']}%\n"
        f"📈 <b>All-Time:</b> ✅{total_aprv} 📥{total_sub} ❌{total_rej} 📅{len(history)}d\n"
    )
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📄 Export History TXT", callback_data=f"adm_hist_{key}")]
    ])
    await message.answer(text, reply_markup=markup)


@router.callback_query(F.data.startswith("adm_hist_"))
async def export_history_txt(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Access Denied!", show_alert=True)
        return
    key      = call.data[len("adm_hist_"):]
    licenses = await load_licenses()
    if key not in licenses:
        await call.answer("❌ Not found!")
        return

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
    logger.info(f"History exported for key={key} by admin={call.from_user.id}")
