# ============================================================
#  handlers/admin/owner.py  —  Owner-exclusive commands
#  Commands: /addadmin, /removeadmin, /shell, /reboot
#  All require OWNER_ID — not available to regular admins
# ============================================================
import asyncio
import os
import sys

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from core.logger import get_logger, get_admin_logger
from core.state import AddAdmin, RemoveAdmin, ShellCmd
from helpers.decorators import owner_only
from config import ADMIN_IDS, OWNER_ID

router = Router(name="admin_owner")
logger = get_logger("Owner")
alog   = get_admin_logger()

_SEP = "━━━━━━━━━━━━━━━━━━"


# ──────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────

def _is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID


# ──────────────────────────────────────────────
#  Callback entry-points from admin panel
# ──────────────────────────────────────────────

@router.callback_query(F.data.in_({"own_addadmin", "own_removeadmin",
                                    "own_shell", "own_reboot"}))
async def handle_owner_callbacks(call: CallbackQuery, state: FSMContext):
    if not _is_owner(call.from_user.id):
        await call.answer("👑 Owner only!", show_alert=True)
        return
    await call.answer()

    if call.data == "own_addadmin":
        await state.set_state(AddAdmin.user_id)
        await call.message.answer(
            f"👑 <b>Add Admin</b>\n{_SEP}\n"
            "Enter the <b>User ID</b> to promote to admin:\n"
            "<i>/cancel to abort</i>"
        )

    elif call.data == "own_removeadmin":
        await _send_admin_list_for_removal(call.from_user.id)

    elif call.data == "own_shell":
        await state.set_state(ShellCmd.command)
        await call.message.answer(
            f"💻 <b>Shell Command</b>\n{_SEP}\n"
            "Enter the shell command to execute:\n"
            "<i>⚠️ Be careful — runs on the server!</i>\n"
            "<i>/cancel to abort</i>"
        )

    elif call.data == "own_reboot":
        markup = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="✅ Yes, Reboot", callback_data="own_reboot_confirm"),
            InlineKeyboardButton(text="❌ Cancel",      callback_data="own_reboot_cancel"),
        ]])
        await call.message.answer(
            f"🖥 <b>Reboot Server</b>\n{_SEP}\n"
            "⚠️ <b>This will reboot the entire server!</b>\n"
            "<i>Are you sure?</i>",
            reply_markup=markup,
        )


@router.callback_query(F.data.in_({"own_reboot_confirm", "own_reboot_cancel"}))
async def handle_reboot_confirm(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        await call.answer("👑 Owner only!", show_alert=True)
        return
    if call.data == "own_reboot_cancel":
        await call.answer("❌ Cancelled.")
        await call.message.edit_text("❌ <b>Reboot cancelled.</b>", reply_markup=None)
    else:
        await call.answer("🖥 Rebooting…")
        await call.message.edit_text(
            f"🖥 <b>Server rebooting…</b>\n{_SEP}\n"
            "The bot will be back shortly.",
            reply_markup=None,
        )
        alog.info(f"Server reboot triggered | uid={call.from_user.id}")
        logger.warning(f"SERVER REBOOT via panel | uid={call.from_user.id}")
        os.system("sudo reboot")


@router.callback_query(F.data.startswith("own_removeconfirm_"))
async def handle_remove_admin_confirm(call: CallbackQuery):
    if not _is_owner(call.from_user.id):
        await call.answer("👑 Owner only!", show_alert=True)
        return
    uid = int(call.data[len("own_removeconfirm_"):])
    if uid in ADMIN_IDS:
        ADMIN_IDS.remove(uid)
        await call.answer("✅ Admin removed!")
        await call.message.edit_text(
            f"✅ <b>Admin Removed</b>\n{_SEP}\n"
            f"👤 ID: <code>{uid}</code>\n"
            f"<i>Change is active for this session.\n"
            f"Update ADMIN_IDS env var to make it permanent.</i>",
            reply_markup=None,
        )
        alog.info(f"Admin removed | uid={uid} | by={call.from_user.id}")
    else:
        await call.answer("⚠️ Not in admin list!")
        await call.message.edit_text("⚠️ That user is not an admin.", reply_markup=None)


# ──────────────────────────────────────────────
#  /addadmin
# ──────────────────────────────────────────────

@router.message(Command("addadmin"))
@owner_only
async def cmd_addadmin(message: Message, state: FSMContext):
    args = message.text.strip().split()
    if len(args) >= 2:
        await _do_add_admin(message, args[1])
        return
    await state.set_state(AddAdmin.user_id)
    await message.answer(
        f"👑 <b>Add Admin</b>\n{_SEP}\n"
        "Enter the <b>User ID</b> to promote:\n"
        "<i>/cancel to abort</i>"
    )


@router.message(Command("cancel"), AddAdmin.user_id)
async def cancel_addadmin(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    await state.clear()
    await message.answer("❌ <b>Add Admin cancelled.</b>")


@router.message(AddAdmin.user_id)
async def addadmin_step(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    await state.clear()
    await _do_add_admin(message, message.text.strip())


async def _do_add_admin(message: Message, raw: str):
    try:
        uid = int(raw)
    except ValueError:
        await message.answer("❌ Invalid user ID — must be a number.")
        return
    if uid in ADMIN_IDS:
        await message.answer(f"⚠️ User <code>{uid}</code> is already an admin.")
        return
    ADMIN_IDS.append(uid)
    await message.answer(
        f"✅ <b>Admin Added</b>\n{_SEP}\n"
        f"👤 ID: <code>{uid}</code>\n"
        f"<i>Active for this session.\n"
        f"Add to ADMIN_IDS env var for permanent effect.</i>"
    )
    alog.info(f"Admin added | uid={uid} | by={message.from_user.id}")


# ──────────────────────────────────────────────
#  /removeadmin
# ──────────────────────────────────────────────

@router.message(Command("removeadmin"))
@owner_only
async def cmd_removeadmin(message: Message):
    args = message.text.strip().split()
    if len(args) >= 2:
        try:
            uid = int(args[1])
        except ValueError:
            await message.answer("❌ Invalid user ID.")
            return
        await _do_remove_admin(message, uid)
        return
    await _send_admin_list_for_removal(message.chat.id)


async def _send_admin_list_for_removal(chat_id: int):
    from core.bot import bot
    if not ADMIN_IDS:
        await bot.send_message(chat_id, "⚠️ No admins configured.")
        return
    rows = []
    for uid in ADMIN_IDS:
        rows.append([InlineKeyboardButton(
            text=f"🗑 Remove {uid}",
            callback_data=f"own_removeconfirm_{uid}",
        )])
    rows.append([InlineKeyboardButton(text="❌ Cancel", callback_data="own_removecancel")])
    markup = InlineKeyboardMarkup(inline_keyboard=rows)
    await bot.send_message(
        chat_id,
        f"🗑 <b>Remove Admin</b>\n{_SEP}\n"
        f"Select admin to remove:\n"
        f"<i>Current admins: {len(ADMIN_IDS)}</i>",
        reply_markup=markup,
    )


async def _do_remove_admin(message: Message, uid: int):
    if uid not in ADMIN_IDS:
        await message.answer(f"⚠️ User <code>{uid}</code> is not an admin.")
        return
    if uid == OWNER_ID:
        await message.answer("❌ Cannot remove the owner from admins.")
        return
    ADMIN_IDS.remove(uid)
    await message.answer(
        f"✅ <b>Admin Removed</b>\n{_SEP}\n"
        f"👤 ID: <code>{uid}</code>\n"
        f"<i>Active for this session.\n"
        f"Update ADMIN_IDS env var for permanent effect.</i>"
    )
    alog.info(f"Admin removed | uid={uid} | by={message.from_user.id}")


@router.callback_query(F.data == "own_removecancel")
async def remove_admin_cancel(call: CallbackQuery):
    await call.answer("❌ Cancelled.")
    await call.message.edit_text("❌ <b>Remove Admin cancelled.</b>", reply_markup=None)


# ──────────────────────────────────────────────
#  /shell  — run shell commands (owner only)
# ──────────────────────────────────────────────

@router.message(Command("shell"))
@owner_only
async def cmd_shell(message: Message, state: FSMContext):
    # Allow inline: /shell <command>
    parts = message.text.strip().split(None, 1)
    if len(parts) >= 2:
        await _run_shell(message, parts[1])
        return
    await state.set_state(ShellCmd.command)
    await message.answer(
        f"💻 <b>Shell</b>\n{_SEP}\n"
        "Enter the command to run:\n"
        "<i>/cancel to abort</i>"
    )


@router.message(Command("cancel"), ShellCmd.command)
async def cancel_shell(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    await state.clear()
    await message.answer("❌ <b>Shell cancelled.</b>")


@router.message(ShellCmd.command)
async def shell_step(message: Message, state: FSMContext):
    if not _is_owner(message.from_user.id):
        return
    await state.clear()
    await _run_shell(message, message.text.strip())


async def _run_shell(message: Message, cmd: str):
    status = await message.answer(f"💻 <b>Running:</b> <code>{cmd}</code>\n⏳ Please wait…")
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
    except asyncio.TimeoutError:
        await status.edit_text(
            f"💻 <b>Shell</b>\n{_SEP}\n"
            f"⏱ <b>Command timed out after 30s</b>\n"
            f"<code>{cmd}</code>"
        )
        return
    except Exception as e:
        await status.edit_text(
            f"💻 <b>Shell Error</b>\n{_SEP}\n"
            f"❌ {e}"
        )
        logger.error(f"Shell command error | cmd={cmd!r} | err={e}")
        return

    out = stdout.decode("utf-8", errors="replace").strip()
    err = stderr.decode("utf-8", errors="replace").strip()

    result = out or err or "<i>(no output)</i>"
    # Telegram message limit 4096; truncate
    if len(result) > 3500:
        result = result[:3500] + "\n… <i>(truncated)</i>"

    exit_icon = "✅" if proc.returncode == 0 else "❌"
    await status.edit_text(
        f"💻 <b>Shell Result</b>\n{_SEP}\n"
        f"<code>{cmd}</code>\n"
        f"{exit_icon} Exit: <code>{proc.returncode}</code>\n"
        f"{_SEP}\n"
        f"<pre>{result}</pre>"
    )
    alog.info(f"Shell | cmd={cmd!r} | exit={proc.returncode} | by={message.from_user.id}")


# ──────────────────────────────────────────────
#  /reboot  — reboot server (owner only)
# ──────────────────────────────────────────────

@router.message(Command("reboot"))
@owner_only
async def cmd_reboot(message: Message):
    markup = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Yes, Reboot", callback_data="own_reboot_confirm"),
        InlineKeyboardButton(text="❌ Cancel",      callback_data="own_reboot_cancel"),
    ]])
    await message.answer(
        f"🖥 <b>Reboot Server</b>\n{_SEP}\n"
        "⚠️ <b>This will reboot the entire server!</b>\n"
        "<i>Are you sure?</i>",
        reply_markup=markup,
    )
