# ============================================================
#  modules/link_watcher.py  —  URL monitor
# ============================================================
from core.logger import get_logger

logger = get_logger("LinkWatcher")
_sessions: dict[int, dict] = {}


def add_watch(chat_id: int, url: str) -> None:
    _sessions[chat_id] = {"url": url, "active": True}
    logger.info(f"Watch added: {chat_id} → {url}")


def remove_watch(chat_id: int) -> bool:
    if chat_id in _sessions:
        _sessions.pop(chat_id)
        return True
    return False


def list_watches() -> dict:
    return dict(_sessions)
