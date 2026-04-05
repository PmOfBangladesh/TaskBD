#!/usr/bin/env python3
# ============================================================
#  SMLBot v2.0  —  main.py
#  Aiogram 3.x  |  Async  |  Multi-log  |  Spam Guard
# ============================================================
import asyncio
import os
import sys

from aiogram import Dispatcher
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats

from core.bot import bot, dp
from core.logger import get_logger
from config import ADMIN_IDS, DATA_DIR, USERS_DIR, LOGS_DIR, EXPORTS_DIR, BOT_NAME, BOT_VERSION

# ── Routers ─────────────────────────────────────────────────
from handlers.system    import router as system_router
from handlers.user      import router as user_router
from handlers.admin     import router as admin_router
from handlers.callbacks import router as callbacks_router
from handlers.broadcast import router as broadcast_router
from handlers.pricelist import router as pricelist_router

logger = get_logger("Main")


# ──────────────────────────────────────────────
#  Ensure all directories exist
# ──────────────────────────────────────────────
def _ensure_dirs():
    for d in [DATA_DIR, USERS_DIR, LOGS_DIR,
              os.path.join(EXPORTS_DIR, "reports"),
              os.path.join(EXPORTS_DIR, "xlsx")]:
        os.makedirs(d, exist_ok=True)

    # Ensure data JSON files exist
    import json
    for fpath, default in [
        (os.path.join(DATA_DIR, "licenses.json"),    {}),
        (os.path.join(DATA_DIR, "pending.json"),     {}),
        (os.path.join(DATA_DIR, "withdrawals.json"), []),
        (os.path.join(DATA_DIR, "spam_users.json"),  {}),
        (os.path.join(DATA_DIR, "price_list.json"),  {
            "Regular Account": "৳5.00",
            "2FA Account":     "৳8.00",
        }),
    ]:
        if not os.path.exists(fpath):
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(default, f, indent=4)


# ──────────────────────────────────────────────
#  Bot commands menu
# ──────────────────────────────────────────────
async def _set_commands():
    user_commands = [
        BotCommand(command="start",     description="Start the bot"),
        BotCommand(command="pricelist", description="View price list"),
    ]
    await bot.set_my_commands(user_commands, scope=BotCommandScopeAllPrivateChats())

    # Admin commands (send directly, no scope for bot commands API)
    admin_text = (
        "🤖 <b>Admin Commands</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "/admin      — Admin Panel\n"
        "/live       — Live user stats\n"
        "/resetstats — Reset stats\n"
        "/ping       — System status\n"
        "/speedtest  — Speed test\n"
        "/logs       — View bot logs\n"
        "/broadcast  — Send to all users\n"
        "/ban        — Ban a user\n"
        "/unban      — Unban a user\n"
        "/restart    — Restart bot\n"
        "/pricelist  — View / Edit price list"
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, admin_text)
        except Exception:
            pass


# ──────────────────────────────────────────────
#  Startup / Shutdown hooks
# ──────────────────────────────────────────────
async def on_startup():
    _ensure_dirs()
    me = await bot.get_me()
    logger.info(f"✅ {BOT_NAME} v{BOT_VERSION} started | @{me.username}")

    await _set_commands()

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🟢 <b>{BOT_NAME} v{BOT_VERSION} Online!</b>\n"
                f"🤖 @{me.username}\n"
                f"⚡ Aiogram 3.x | Async\n"
                f"📋 Type /admin for panel"
            )
        except Exception:
            pass


async def on_shutdown():
    logger.info("🛑 Bot shutting down…")
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, f"🔴 <b>{BOT_NAME} is going offline.</b>")
        except Exception:
            pass
    await bot.session.close()


# ──────────────────────────────────────────────
#  Register routers
# ──────────────────────────────────────────────
def _register_routers():
    # Order matters — more specific routers first
    dp.include_router(system_router)
    dp.include_router(callbacks_router)
    dp.include_router(admin_router)
    dp.include_router(broadcast_router)
    dp.include_router(pricelist_router)
    dp.include_router(user_router)   # user last (catches generic text)


# ──────────────────────────────────────────────
#  Main entry
# ──────────────────────────────────────────────
async def main():
    _register_routers()
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    logger.info(f"🚀 Starting {BOT_NAME} v{BOT_VERSION}…")
    await dp.start_polling(
        bot,
        allowed_updates=dp.resolve_used_update_types(),
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Stopped by user.")
    except Exception as e:
        logger.critical(f"💥 CRASH: {e}", exc_info=True)
        sys.exit(1)
