# ============================================================
#  handlers/admin/pricing.py  —  Price list view & edit
# ============================================================
import json
import os

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from core.state import PriceList
from core.logger import get_logger
from helpers.decorators import admin_only
from config import PRICELIST_FILE, ADMIN_IDS

router = Router(name="admin_pricing")
logger = get_logger("Admin.Pricing")

_DEFAULT: dict = {
    "Regular Account": "৳5.00",
    "2FA Account":     "৳8.00",
    "Premium Account": "৳10.00",
}


# ──────────────────────────────────────────────
#  I/O helpers
# ──────────────────────────────────────────────

async def _load() -> dict:
    if os.path.exists(PRICELIST_FILE):
        try:
            with open(PRICELIST_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return _DEFAULT.copy()


async def _save(data: dict) -> None:
    with open(PRICELIST_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def _fmt(prices: dict) -> str:
    lines = ["💲 <b>Price List</b>\n━━━━━━━━━━━━━━━━━━"]
    for name, price in prices.items():
        lines.append(f"• <b>{name}</b> — {price}")
    return "\n".join(lines)


# ──────────────────────────────────────────────
#  /pricelist  command
# ──────────────────────────────────────────────

@router.message(Command("pricelist"))
async def cmd_pricelist(message: Message):
    prices = await _load()
    markup = None
    if message.from_user.id in ADMIN_IDS:
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Edit Price List", callback_data="pl_edit")]
        ])
    await message.answer(_fmt(prices), reply_markup=markup)


# ──────────────────────────────────────────────
#  Edit price list (admin only)
# ──────────────────────────────────────────────

@router.callback_query(F.data == "pl_edit")
@admin_only
async def cb_pl_edit(call: CallbackQuery, state: FSMContext):
    await call.answer()
    prices = await _load()
    sample = json.dumps(prices, ensure_ascii=False, indent=2)
    await state.set_state(PriceList.editing)
    await call.message.answer(
        f"✏️ <b>Edit Price List</b>\n"
        f"Send new JSON. Current:\n<pre>{sample}</pre>"
    )


@router.message(PriceList.editing)
@admin_only
async def pl_save(message: Message, state: FSMContext):
    try:
        new_prices = json.loads(message.text)
        if not isinstance(new_prices, dict):
            raise ValueError("Must be a JSON object")
        await _save(new_prices)
        await state.clear()
        await message.answer(f"✅ Price list updated!\n\n{_fmt(new_prices)}")
        logger.info(f"Price list updated by {message.from_user.id}")
    except Exception as exc:
        await message.answer(f"❌ Invalid JSON: <code>{exc}</code>\nTry again or /cancel.")
