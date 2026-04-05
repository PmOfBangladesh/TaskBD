# ============================================================
#  modules/report_builder.py  —  Final report calculation
# ============================================================
from datetime import datetime
from core.database import load_licenses, get_today_stats, get_today_2fa_count
from core.logger import get_logger

logger = get_logger("ReportBuilder")


async def build_final_report(survived: int, prize: float) -> tuple[list[dict], str]:
    """
    Calculate per-user payment based on survival ratio.
    Returns (report_rows, preview_text).
    """
    licenses      = await load_licenses()
    total_sub_all = 0
    user_subs     = {}

    for key, info in licenses.items():
        s              = await get_today_stats(info.get("username", ""))
        user_subs[key] = s["sub"]
        total_sub_all += s["sub"]

    if total_sub_all == 0:
        return [], "❌ No submission data found for today!"

    ratio       = survived / total_sub_all
    report_rows = []
    lines       = []

    for key, info in licenses.items():
        user_sub = user_subs.get(key, 0)
        if user_sub == 0:
            continue
        user_final  = max(1, int(user_sub * ratio))
        user_rej    = user_sub - user_final
        payment     = round(user_final * prize, 2)
        new_balance = round(info.get("balance", 0.0) + payment, 2)

        report_rows.append({
            "key":         key,
            "info":        info,
            "user_sub":    user_sub,
            "user_final":  user_final,
            "user_rej":    user_rej,
            "payment":     payment,
            "new_balance": new_balance,
        })
        lines.append(
            f"👤 <b>{info['name']}</b> — ✅{user_final} 📥{user_sub} ❌{user_rej} 💰{payment}৳"
        )

    preview = "\n".join(lines) if lines else "No data"
    return report_rows, preview


async def build_2fa_report(survived: int, prize: float) -> tuple[list[dict], str]:
    """Same logic but based on 2FA success counts."""
    licenses      = await load_licenses()
    total_2fa_all = 0
    user_2fa      = {}

    for key, info in licenses.items():
        count          = await get_today_2fa_count(info.get("username", ""))
        user_2fa[key]  = count
        total_2fa_all += count

    if total_2fa_all == 0:
        return [], "❌ No 2FA data found for today!"

    ratio       = survived / total_2fa_all
    report_rows = []
    lines       = []

    for key, info in licenses.items():
        count = user_2fa.get(key, 0)
        if count == 0:
            continue
        user_final  = max(1, int(count * ratio))
        payment     = round(user_final * prize, 2)
        new_balance = round(info.get("balance", 0.0) + payment, 2)

        report_rows.append({
            "key":         key,
            "info":        info,
            "user_2fa":    count,
            "user_final":  user_final,
            "payment":     payment,
            "new_balance": new_balance,
        })
        lines.append(
            f"👤 <b>{info['name']}</b> — 🔐{user_final}/{count} 💰{payment}৳"
        )

    preview = "\n".join(lines) if lines else "No data"
    return report_rows, preview


async def commit_report(report_rows: list[dict], today: str) -> None:
    """Write payments + history to licenses.json."""
    from core.database import load_licenses, save_licenses
    licenses = await load_licenses()

    for row in report_rows:
        key  = row["key"]
        info = licenses.get(key)
        if not info:
            continue
        info["balance"] = row["new_balance"]
        history = info.setdefault("history", {})
        history[today] = {
            "aprv":    row.get("user_final", 0),
            "sub":     row.get("user_sub", row.get("user_2fa", 0)),
            "rej":     row.get("user_rej", 0),
            "payment": row["payment"],
        }
        # Notify user
        try:
            from core.bot import bot
            tg_id = info.get("tg_id")
            if tg_id:
                await bot.send_message(
                    tg_id,
                    f"💰 <b>Balance Added!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"➕ Added: <b>{row['payment']} ৳</b>\n"
                    f"💵 New Balance: <b>{row['new_balance']} ৳</b>"
                )
        except Exception:
            pass

    await save_licenses(licenses)
    logger.info(f"Final report committed for {today}: {len(report_rows)} users")
