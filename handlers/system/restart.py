# ============================================================
#  handlers/system/restart.py  —  /restart command
# ============================================================
import os
import sys

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from core.logger import get_logger
from helpers.decorators import admin_only

router = Router(name="system_restart")
logger = get_logger("System.Restart")


@router.message(Command("restart"))
@admin_only
async def cmd_restart(message: Message):
    await message.answer(
        "🔄 <b>Restarting bot…</b>\n"
        "<i>The bot will be back in a moment.</i>"
    )
    logger.info(f"Restart triggered | by={message.from_user.id}")
    os.execv(sys.executable, [sys.executable] + sys.argv)
