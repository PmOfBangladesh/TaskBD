# ============================================================
#  core/database.py  —  All JSON + CSV I/O (async-safe)
# ============================================================
import json
import os
import csv
import aiofiles
import asyncio
from datetime import datetime
from typing import Optional

from core.logger import get_logger
from config import (
    BASE_DIR, DATA_DIR, USERS_DIR,
    LICENSES_FILE, PENDING_FILE, WITHDRAWALS_FILE, SPAM_FILE
)

logger = get_logger("Database")
_lock  = asyncio.Lock()

os.makedirs(DATA_DIR,  exist_ok=True)
os.makedirs(USERS_DIR, exist_ok=True)


# ─── Generic JSON helpers ────────────────────────────────────

async def _read_json(path: str) -> dict | list:
    if not os.path.exists(path):
        return {}
    try:
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            return json.loads(await f.read())
    except Exception as e:
        logger.error(f"JSON read error [{path}]: {e}")
        return {}


async def _write_json(path: str, data: dict | list) -> None:
    async with _lock:
        # backup
        if os.path.exists(path):
            try:
                async with aiofiles.open(path + ".bak", "w", encoding="utf-8") as f:
                    content = await _read_json(path)
                    await f.write(json.dumps(content, indent=4, ensure_ascii=False))
            except Exception:
                pass
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            await f.write(json.dumps(data, indent=4, ensure_ascii=False))


# ─── Licenses ────────────────────────────────────────────────

async def load_licenses() -> dict:
    return await _read_json(LICENSES_FILE)


async def save_licenses(data: dict) -> None:
    await _write_json(LICENSES_FILE, data)


async def get_user_by_key(key: str) -> Optional[dict]:
    return (await load_licenses()).get(key.upper())


async def get_key_by_tg_id(tg_id: int) -> Optional[str]:
    for key, info in (await load_licenses()).items():
        if str(info.get("tg_id", "")) == str(tg_id):
            return key
    return None


async def update_tg_id(key: str, tg_id: int) -> bool:
    licenses = await load_licenses()
    if key in licenses:
        licenses[key]["tg_id"] = tg_id
        await save_licenses(licenses)
        return True
    return False


async def add_balance(key: str, amount: float) -> Optional[float]:
    licenses = await load_licenses()
    if key in licenses:
        licenses[key]["balance"] = round(licenses[key].get("balance", 0.0) + amount, 2)
        await save_licenses(licenses)
        return licenses[key]["balance"]
    return None


async def deduct_balance(key: str, amount: float) -> Optional[float]:
    licenses = await load_licenses()
    if key in licenses:
        current = licenses[key].get("balance", 0.0)
        if current < amount:
            return None
        licenses[key]["balance"]         = round(current - amount, 2)
        licenses[key]["total_withdraws"] = licenses[key].get("total_withdraws", 0) + 1
        await save_licenses(licenses)
        return licenses[key]["balance"]
    return None


async def update_payment_method(key: str, method: str, number: str) -> bool:
    licenses = await load_licenses()
    if key in licenses:
        licenses[key]["payment_method"] = method
        licenses[key]["payment_number"] = number
        await save_licenses(licenses)
        return True
    return False


async def delete_user(key: str) -> bool:
    licenses = await load_licenses()
    if key in licenses:
        del licenses[key]
        await save_licenses(licenses)
        return True
    return False


async def get_user_profile(key: str) -> Optional[dict]:
    info = (await load_licenses()).get(key, {})
    if not info:
        return None
    history = info.get("history", {})
    return {
        "name":            info.get("name", "N/A"),
        "username":        info.get("username", "N/A"),
        "joined":          info.get("joined", "N/A"),
        "validity":        info.get("validity", "N/A"),
        "payment_method":  info.get("payment_method", "N/A"),
        "payment_number":  info.get("payment_number", "N/A"),
        "balance":         info.get("balance", 0.0),
        "total_earned":    info.get("total_earned", 0.0),
        "total_withdraws": info.get("total_withdraws", 0),
        "mentor":          info.get("mentor", ""),
        "history":         history,
    }


async def get_all_time_stats() -> list[dict]:
    results = []
    for key, info in (await load_licenses()).items():
        h = info.get("history", {})
        results.append({
            "key":         key,
            "name":        info.get("name", ""),
            "username":    info.get("username", ""),
            "total_aprv":  sum(d.get("aprv", 0) for d in h.values()),
            "total_sub":   sum(d.get("sub",  0) for d in h.values()),
            "total_rej":   sum(d.get("rej",  0) for d in h.values()),
            "days_active": len(h),
            "balance":     info.get("balance", 0.0),
        })
    return results


# ─── Stats ───────────────────────────────────────────────────

async def get_today_stats(username: str) -> dict:
    user_folder = os.path.join(USERS_DIR, username)
    stats = {"aprv": 0, "sub": 0, "rej": 0, "sus": 0}
    file_map = {
        "Success.csv":          "aprv",
        "sub-success.txt":      "sub",
        "no_follow_reject.txt": "rej",
        "reject.txt":           "rej",
        "suspended.txt":        "sus",
    }
    for fname, skey in file_map.items():
        fpath = os.path.join(user_folder, fname)
        if os.path.exists(fpath):
            try:
                async with aiofiles.open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    lines = await f.readlines()
                stats[skey] += sum(1 for l in lines if l.strip())
            except Exception:
                pass
    total = stats["aprv"] + stats["sub"] + stats["rej"]
    stats["pct"] = round(stats["aprv"] / total * 100, 1) if total > 0 else 0.0
    return stats


async def get_today_2fa_count(username: str) -> int:
    csv_path = os.path.join(USERS_DIR, username, "2fa_success.csv")
    if not os.path.exists(csv_path):
        return 0
    try:
        async with aiofiles.open(csv_path, "r", encoding="utf-8") as f:
            lines = await f.readlines()
        return max(0, len([l for l in lines if l.strip()]) - 1)  # skip header
    except Exception as e:
        logger.error(f"2FA read error {username}: {e}")
        return 0


async def reset_today_stats(username: str) -> list[str]:
    user_folder = os.path.join(USERS_DIR, username)
    files = ["Success.csv", "sub-success.txt", "no_follow_reject.txt",
             "reject.txt", "suspended.txt", "2fa_success.csv"]
    cleared = []
    for fname in files:
        fpath = os.path.join(user_folder, fname)
        if os.path.exists(fpath):
            try:
                async with aiofiles.open(fpath, "w") as f:
                    await f.write("")
                cleared.append(fname)
            except Exception as e:
                logger.error(f"Reset error {fname}: {e}")
    return cleared


async def reset_all_stats() -> list[str]:
    if not os.path.exists(USERS_DIR):
        return []
    results = []
    for username in os.listdir(USERS_DIR):
        if os.path.isdir(os.path.join(USERS_DIR, username)):
            if await reset_today_stats(username):
                results.append(username)
    return results


async def get_7_days_history(key: str) -> str:
    licenses = await load_licenses()
    if key not in licenses:
        return "❌ License not found."
    info    = licenses[key]
    history = dict(info.get("history", {}))
    today   = datetime.now().strftime("%Y-%m-%d")
    live    = await get_today_stats(info.get("username", ""))
    if any(v > 0 for v in [live["aprv"], live["sub"], live["rej"]]):
        history[today] = live
    if not history:
        return "<i>No history yet. Start working today!</i>"
    text = "📅 <b>Last 7 Days History</b>\n━━━━━━━━━━━━━━━━━━\n"
    for date in sorted(history.keys(), reverse=True)[:7]:
        d     = history[date]
        aprv  = d.get("aprv", 0)
        sub   = d.get("sub",  0)
        rej   = d.get("rej",  0)
        total = aprv + sub + rej
        pct   = round(aprv / total * 100, 1) if total > 0 else 0.0
        mark  = "📍" if date == today else "📆"
        text += f"{mark} <b>{date}</b>\n   ✅ {aprv} | 📥 {sub} | ❌ {rej} | 📊 {pct}%\n"
    return text


# ─── CSV export ──────────────────────────────────────────────

async def read_all_csv() -> list[dict]:
    csv_path = os.path.join(USERS_DIR, "All.csv")
    rows = []
    if not os.path.exists(csv_path):
        return rows
    try:
        async with aiofiles.open(csv_path, "r", encoding="utf-8", errors="ignore") as f:
            content = await f.read()
        reader = csv.DictReader(content.splitlines())
        rows   = list(reader)
    except Exception as e:
        logger.error(f"CSV read error: {e}")
    return rows


async def read_2fa_csv() -> list[dict]:
    from config import TWOFA_CSV
    if not os.path.exists(TWOFA_CSV):
        return []
    try:
        async with aiofiles.open(TWOFA_CSV, "r", encoding="utf-8") as f:
            content = await f.read()
        rows = []
        for row in csv.DictReader(content.splitlines()):
            username = row.get("Username", row.get("username", "")).strip()
            password = row.get("Password", row.get("pass", "")).strip()
            twofa    = row.get("2FA_Code", row.get("2fector secret", "")).strip()
            if username:
                rows.append({"Username": username, "Password": password, "2FA Secret": twofa})
        return rows
    except Exception as e:
        logger.error(f"2FA CSV read error: {e}")
        return []


# ─── Spam store ──────────────────────────────────────────────

async def load_spam() -> dict:
    return await _read_json(SPAM_FILE)


async def save_spam(data: dict) -> None:
    await _write_json(SPAM_FILE, data)


# ─── Pending / Withdrawals ───────────────────────────────────

async def load_pending() -> dict:
    return await _read_json(PENDING_FILE)


async def save_pending(data: dict) -> None:
    await _write_json(PENDING_FILE, data)


async def load_withdrawals() -> list:
    data = await _read_json(WITHDRAWALS_FILE)
    return data if isinstance(data, list) else []


async def save_withdrawal(record: dict) -> None:
    records = await load_withdrawals()
    records.append(record)
    await _write_json(WITHDRAWALS_FILE, records)
