# ============================================================
#  handlers/system/speedtest.py  —  /speedtest command
# ============================================================
import asyncio
import shutil
from datetime import datetime

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from core.logger import get_logger
from helpers.decorators import admin_only

router = Router(name="system_speedtest")
logger = get_logger("System.Speedtest")


@router.message(Command("speedtest"))
@admin_only
async def cmd_speedtest(message: Message):
    sent = await message.answer("🚀 <b>Running speed test…</b>\n<i>~30 seconds</i>")
    try:
        cli = shutil.which("speedtest-cli") or shutil.which("speedtest")
        if not cli:
            raise FileNotFoundError("speedtest-cli not found")

        proc = await asyncio.create_subprocess_exec(
            cli, "--simple", "--single",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=90)
        output    = stdout.decode().strip()

        ping = dl = ul = "N/A"
        for line in output.splitlines():
            if line.startswith("Ping:"):       ping = line.replace("Ping:", "").strip()
            elif line.startswith("Download:"): dl   = line.replace("Download:", "").strip()
            elif line.startswith("Upload:"):   ul   = line.replace("Upload:", "").strip()

        text = (
            f"🚀 <b>Speed Test Result</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🏓 Ping     : <b>{ping}</b>\n"
            f"⬇️ Download : <b>{dl}</b>\n"
            f"⬆️ Upload   : <b>{ul}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🕒 <i>{datetime.now().strftime('%Y-%m-%d %H:%M')}</i>"
        )
    except FileNotFoundError:
        text = (
            "⚠️ <b>speedtest-cli not installed!</b>\n"
            "<code>pip install speedtest-cli</code>"
        )
    except asyncio.TimeoutError:
        text = "⏰ <b>Speedtest timed out (&gt;90s)</b>"
    except Exception as e:
        text = f"❌ <b>Error:</b> <code>{e}</code>"

    await sent.edit_text(text)
