# ============================================================
#  helpers/decorators.py  —  Route guards
# ============================================================
import functools
from aiogram.types import Message, CallbackQuery
from config import ADMIN_IDS
from core.logger import get_logger

logger = get_logger("Decorators")


def admin_only(func):
    """Block non-admins from message handlers."""
    @functools.wraps(func)
    async def wrapper(message: Message, *args, **kwargs):
        if message.from_user.id not in ADMIN_IDS:
            await message.answer("❌ <b>Access Denied!</b>")
            return
        return await func(message, *args, **kwargs)
    return wrapper


def admin_callback(func):
    """Block non-admins from callback handlers."""
    @functools.wraps(func)
    async def wrapper(call: CallbackQuery, *args, **kwargs):
        if call.from_user.id not in ADMIN_IDS:
            await call.answer("❌ Access Denied!", show_alert=True)
            return
        return await func(call, *args, **kwargs)
    return wrapper


def private_only(func):
    """Allow only private/DM chats."""
    @functools.wraps(func)
    async def wrapper(message: Message, *args, **kwargs):
        if message.chat.type != "private":
            await message.answer("🤖 This bot works in DM only.")
            return
        return await func(message, *args, **kwargs)
    return wrapper


def spam_guard(func):
    """Run spam check before handler executes."""
    @functools.wraps(func)
    async def wrapper(message: Message, *args, **kwargs):
        from modules.spam_detector import SpamDetector
        banned, reason = await SpamDetector.check(message.from_user.id)
        if banned:
            await message.answer(f"🚫 <b>Slow down!</b>\n{reason}")
            return
        return await func(message, *args, **kwargs)
    return wrapper
