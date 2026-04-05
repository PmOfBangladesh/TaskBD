# ============================================================
#  core/state.py  —  All FSM state groups (aiogram 3.x)
# ============================================================
from aiogram.fsm.state import State, StatesGroup


class LicenseGen(StatesGroup):
    name         = State()
    username     = State()
    validity     = State()
    pay_num      = State()
    pay_method   = State()
    mentor_key   = State()
    mentor_bonus = State()


class Report(StatesGroup):
    survived = State()
    prize    = State()


class Report2FA(StatesGroup):
    survived = State()
    prize    = State()


class AddBalance(StatesGroup):
    key    = State()
    amount = State()


class DeleteUser(StatesGroup):
    key = State()


class LicenseCheck(StatesGroup):
    key = State()


class Broadcast(StatesGroup):
    message = State()


class Withdraw(StatesGroup):
    confirm = State()


class PayChange(StatesGroup):
    method = State()
    number = State()


class Screenshot(StatesGroup):
    waiting = State()


class PriceList(StatesGroup):
    editing = State()


class UpdateAnnounce(StatesGroup):
    message = State()
