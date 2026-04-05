# ============================================================
#  helpers/formatter.py  —  Message formatters
# ============================================================
import random
import string
from datetime import datetime
from core.constants import SEP


def fmt_validity(validity: str) -> str:
    try:
        exp       = datetime.strptime(validity.replace("/", "-"), "%Y-%m-%d")
        days_left = (exp - datetime.now()).days
        label     = "⚠️ EXPIRED" if days_left < 0 else f"{days_left}d left"
        return f"{validity} ({label})"
    except Exception:
        return validity


def mask_number(number: str) -> str:
    if not number or len(number) < 6:
        return "****"
    return number[:3] + "****" + number[-3:]


def generate_txn_id() -> str:
    chars = string.ascii_letters + string.digits
    return "SML" + "".join(random.choice(chars) for _ in range(24))


def fmt_stats_block(stats: dict) -> str:
    return (
        f"✅ Approved:  <b>{stats['aprv']}</b>\n"
        f"📥 Submitted: <b>{stats['sub']}</b>\n"
        f"❌ Rejected:  <b>{stats['rej']}</b>\n"
        f"🚫 Suspended: <b>{stats['sus']}</b>\n"
        f"📈 Rate:      <b>{stats['pct']}%</b>"
    )


def fmt_profile(profile: dict, key: str) -> str:
    validity      = fmt_validity(profile["validity"])
    total_created = sum(d.get("aprv", 0) for d in profile.get("history", {}).values())
    days_active   = len(profile.get("history", {}))
    mentor_line   = f"👨‍🏫 Mentor: <b>{profile['mentor']}</b>\n" if profile.get("mentor") else ""
    return (
        f"👤 <b>My Profile</b>\n{SEP}\n"
        f"📛 Name: <b>{profile['name']}</b>\n"
        f"🔑 Username: {profile['username']}\n"
        f"📅 Joined: {profile['joined']}\n"
        f"⏳ Valid Till: {validity}\n"
        f"{mentor_line}"
        f"{SEP}\n"
        f"💰 Balance: <b>{profile['balance']} ৳</b>\n"
        f"💵 Total Earned: <b>{profile['total_earned']} ৳</b>\n"
        f"📊 Total Created: <b>{total_created}</b> accounts\n"
        f"📆 Days Active: <b>{days_active}</b> days\n"
        f"💸 Withdrawals: <b>{profile['total_withdraws']}</b>\n"
        f"{SEP}\n"
        f"💳 {profile['payment_method']} — {profile['payment_number']}\n"
    )
