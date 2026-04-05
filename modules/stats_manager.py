# ============================================================
#  modules/stats_manager.py  —  Live stats pagination builder
# ============================================================
from datetime import datetime
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from core.database import load_licenses, get_today_stats, get_today_2fa_count
from config import USERS_PER_PAGE
from core.logger import get_logger

logger = get_logger("StatsManager")


async def build_live_pages() -> list[str]:
    licenses = await load_licenses()
    now      = datetime.now().strftime("%Y-%m-%d %H:%M")
    entries  = []

    for key, info in licenses.items():
        stats = await get_today_stats(info.get("username", ""))
        entries.append({
            "name": info.get("name", "N/A"),
            "key":  key,
            "aprv": stats["aprv"],
            "sub":  stats["sub"],
            "rej":  stats["rej"],
            "sus":  stats["sus"],
            "pct":  stats["pct"],
        })

    entries     = sorted(entries, key=lambda x: x["aprv"], reverse=True)
    total_pages = max(1, (len(entries) + USERS_PER_PAGE - 1) // USERS_PER_PAGE)
    pages       = []

    for pn in range(total_pages):
        chunk = entries[pn * USERS_PER_PAGE:(pn + 1) * USERS_PER_PAGE]
        text  = (
            f"📊 <b>Live Stats — All Users</b>\n"
            f"🕒 <i>{now}</i>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
        )
        for e in chunk:
            text += (
                f"👤 <b>{e['name']}</b>  <code>{e['key']}</code>\n"
                f"   ✅ <b>{e['aprv']}</b>  📥 {e['sub']}  ❌ {e['rej']}  🚫 {e['sus']}\n"
                f"   📈 <b>{e['pct']}%</b>\n"
                f"   ─────────────────\n"
            )
        text += f"📄 Page {pn + 1}/{total_pages}"
        pages.append(text)

    return pages


def live_markup(page: int, total: int) -> InlineKeyboardMarkup:
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"live_{page - 1}"))
    buttons.append(InlineKeyboardButton(text="🔄 Refresh", callback_data=f"live_{page}"))
    if page < total - 1:
        buttons.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"live_{page + 1}"))
    return InlineKeyboardMarkup(inline_keyboard=[buttons])
