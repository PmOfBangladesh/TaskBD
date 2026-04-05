# ============================================================
#  modules/log_viewer.py  —  Paginated log viewer
# ============================================================
import os
import re
from datetime import datetime, timedelta
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import LOGS_DIR, LINES_PER_PAGE
from core.constants import LEVEL_ICONS
from core.logger import get_logger

logger   = get_logger("LogViewer")
LOG_FILE = os.path.join(LOGS_DIR, "bot.log")


def clean_old_logs(days: int = 2) -> int:
    if not os.path.exists(LOG_FILE):
        return 0
    cutoff  = datetime.now() - timedelta(days=days)
    kept    = []
    removed = 0
    with open(LOG_FILE, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    for line in lines:
        m = re.match(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
        if m:
            try:
                if datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S") < cutoff:
                    removed += 1
                    continue
            except Exception:
                pass
        kept.append(line)
    with open(LOG_FILE, "w", encoding="utf-8") as f:
        f.writelines(kept)
    return removed


def _beautify(line: str) -> str | None:
    line = line.strip()
    if not line:
        return None
    m = re.match(
        r"^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}),?\d* "
        r"\[?([^\]]+)\]? (\w+): (.+)$", line
    )
    if m:
        icon = LEVEL_ICONS.get(m.group(4).upper(), "📝")
        return f"{icon} <b>{m.group(2)}</b> [{m.group(3)}] — {m.group(5)[:180]}"
    return f"📝 {line[:200]}"


def build_log_pages(lines: list[str]) -> list[str]:
    beautiful = [b for line in lines if (b := _beautify(line))]
    total     = max(1, (len(beautiful) + LINES_PER_PAGE - 1) // LINES_PER_PAGE)
    pages     = []
    for i in range(total):
        chunk   = beautiful[i * LINES_PER_PAGE:(i + 1) * LINES_PER_PAGE]
        content = "\n".join(chunk) if chunk else "<i>No entries</i>"
        pages.append(
            f"📋 <b>Bot Logs</b> — Page {i+1}/{total}\n"
            f"━━━━━━━━━━━━━━━━━━\n{content}"
        )
    return pages


def log_markup(page: int, total: int) -> InlineKeyboardMarkup:
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Prev", callback_data=f"log_page_{page-1}"))
    nav.append(InlineKeyboardButton(text=f"{page+1}/{total}", callback_data="log_noop"))
    if page < total - 1:
        nav.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"log_page_{page+1}"))
    return InlineKeyboardMarkup(inline_keyboard=[
        nav,
        [
            InlineKeyboardButton(text="🗑 Clean (2d)", callback_data="log_clean"),
            InlineKeyboardButton(text="📥 Download",   callback_data="log_download"),
        ],
        [InlineKeyboardButton(text="❌ Close", callback_data="log_close")],
    ])
