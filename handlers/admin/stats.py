# ============================================================
#  handlers/admin/stats.py  —  Live stats, all-time, reset
# ============================================================
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, BufferedInputFile,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from core.bot import bot
from core.database import get_all_time_stats, reset_today_stats, reset_all_stats
from core.logger import get_logger, get_admin_logger
from helpers.decorators import admin_only
from helpers.xlsx_builder import build_report_xlsx
from modules.stats_manager import build_live_pages, live_markup
from config import ADMIN_IDS

router = Router(name="admin_stats")
logger = get_logger("Admin.Stats")
alog   = get_admin_logger()


# ──────────────────────────────────────────────
#  Callback entry-points from panel
# ──────────────────────────────────────────────

@router.callback_query(F.data.in_({"adm_stats", "adm_resetmenu"}))
async def handle_stats_callbacks(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Access Denied!", show_alert=True)
        return
    await call.answer()

    if call.data == "adm_stats":
        await _do_all_time_stats(call.from_user.id)

    elif call.data == "adm_resetmenu":
        await _send_reset_menu(call.from_user.id)


# ──────────────────────────────────────────────
#  /live  — live stats
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
        await call.answer("❌ Access Denied!", show_alert=True)
        return
    try:
        page = int(call.data.split("_")[1])
    except (IndexError, ValueError):
        await call.answer()
        return
    pages = await build_live_pages()
    page  = min(page, len(pages) - 1)
    await call.message.edit_text(pages[page], reply_markup=live_markup(page, len(pages)))
    await call.answer("🔄 Refreshed!")


# ──────────────────────────────────────────────
#  /resetstats  — command shortcut
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
                f"✅ <b>Stats Reset!</b>\n"
                f"👤 <code>{username}</code>\n"
                f"🗑 {len(cleared)} files cleared."
            )
        else:
            await message.answer(f"⚠️ No stat files found for <code>{username}</code>.")


# ──────────────────────────────────────────────
#  Reset menu helpers
# ──────────────────────────────────────────────

async def _send_reset_menu(chat_id: int):
    from core.database import load_licenses
    licenses = await load_licenses()
    rows     = [[InlineKeyboardButton(
        text="🔄 Reset ALL Users", callback_data="adm_resetall_ask"
    )]]
    for key, info in licenses.items():
        name  = info.get("name", "N/A")
        uname = info.get("username", "N/A")
        rows.append([InlineKeyboardButton(
            text=f"👤 {name} ({uname})",
            callback_data=f"adm_resetuser_{info.get('username', '')}",
        )])
    rows.append([InlineKeyboardButton(text="❌ Cancel", callback_data="adm_resetcancel")])
    markup = InlineKeyboardMarkup(inline_keyboard=rows)
    await bot.send_message(
        chat_id,
        "🔄 <b>Reset Stats Menu</b>\n<i>Choose who to reset:</i>",
        reply_markup=markup,
    )


@router.callback_query(F.data.startswith("adm_reset"))
async def handle_reset_callbacks(call: CallbackQuery):
    if call.from_user.id not in ADMIN_IDS:
        await call.answer("❌ Access Denied!", show_alert=True)
        return

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
            reply_markup=markup,
        )

    elif data == "adm_resetall_confirm":
        await call.answer("🔄 Resetting…")
        users = await reset_all_stats()
        await call.message.edit_text(
            f"✅ <b>All Stats Reset!</b>\n👥 {len(users)} users cleared.",
            reply_markup=None,
        )
        alog.info(f"ALL stats reset | by={call.from_user.id} | users={len(users)}")

    elif data.startswith("adm_resetuser_"):
        username = data[len("adm_resetuser_"):]
        await call.answer("🔄 Resetting…")
        cleared  = await reset_today_stats(username)
        await call.message.edit_text(
            f"✅ <b>Stats Reset!</b>\n"
            f"👤 <code>{username}</code>\n"
            f"🗑 {len(cleared)} files cleared.",
            reply_markup=None,
        )
        alog.info(f"Stats reset | user={username} | by={call.from_user.id}")


# ──────────────────────────────────────────────
#  All-Time stats helper
# ──────────────────────────────────────────────

async def _do_all_time_stats(chat_id: int):
    stats = await get_all_time_stats()
    if not stats:
        await bot.send_message(chat_id, "⚠️ No data found.")
        return
    lines = []
    for s in sorted(stats, key=lambda x: x["total_aprv"], reverse=True):
        lines.append(
            f"👤 <b>{s['name']}</b>\n"
            f"   ✅{s['total_aprv']} 📥{s['total_sub']} ❌{s['total_rej']} "
            f"📅{s['days_active']}d 💰{s['balance']}৳"
        )
    text  = "📈 <b>All-Time Stats</b>\n━━━━━━━━━━━━━━━━━━\n" + "\n".join(lines)
    today = datetime.now().strftime("%Y-%m-%d")
    buf   = build_report_xlsx(
        stats, "All-Time Stats",
        ["name", "username", "total_aprv", "total_sub", "total_rej", "days_active", "balance"],
    )
    await bot.send_message(chat_id, text[:4000])
    await bot.send_document(
        chat_id,
        BufferedInputFile(buf.read(), filename=f"AllTimeStats_{today}.xlsx"),
        caption="📊 All-Time Stats Export",
    )
