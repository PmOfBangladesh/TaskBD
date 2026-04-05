# ============================================================
#  helpers/utils.py  —  Shared utilities
# ============================================================
import random
from aiogram import Bot
from config import ADMIN_IDS, CHANNEL_ID, MESSAGE_EFFECTS
from core.logger import get_logger

logger = get_logger("Utils")


def random_effect_id() -> str:
    return random.choice(MESSAGE_EFFECTS)["id"]


async def check_channel_membership(bot: Bot, user_id: int) -> bool:
    try:
        m = await bot.get_chat_member(CHANNEL_ID, user_id)
        return m.status in ("member", "administrator", "creator")
    except Exception as e:
        logger.warning(f"Channel check failed for {user_id}: {e}")
        return False


async def notify_admins(bot: Bot, text: str, exclude: int = None) -> None:
    for admin_id in ADMIN_IDS:
        if admin_id == exclude:
            continue
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            pass


async def log_admin_action(bot: Bot, action: str, by: int, detail: str = "") -> None:
    from core.logger import get_admin_logger
    alog = get_admin_logger()
    alog.info(f"[{by}] {action} {detail}")
