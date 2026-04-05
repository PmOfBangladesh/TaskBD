# ============================================================
#  modules/spam_detector.py  —  Rate-limit + ban tracker
# ============================================================
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Optional

from core.logger import get_spam_logger
from core.database import load_spam, save_spam
from config import SPAM_MAX_MSGS, SPAM_WINDOW, SPAM_BAN_MINS, ADMIN_IDS

logger = get_spam_logger()

# In-memory: user_id → deque of timestamps
_buckets: dict[int, deque] = defaultdict(deque)
# In-memory ban cache: user_id → unban_timestamp
_bans: dict[int, float] = {}


class SpamDetector:

    @staticmethod
    async def check(user_id: int) -> tuple[bool, str]:
        """Return (is_banned, reason). Call before processing any message."""
        if user_id in ADMIN_IDS:
            return False, ""

        # Check active ban
        if user_id in _bans:
            if time.time() < _bans[user_id]:
                remaining = int((_bans[user_id] - time.time()) / 60) + 1
                return True, f"You are rate-limited. Try again in <b>{remaining} min</b>."
            else:
                del _bans[user_id]

        # Check persistent ban
        spam_data = await load_spam()
        if str(user_id) in spam_data:
            record = spam_data[str(user_id)]
            if record.get("permanent"):
                return True, "🚫 You are permanently banned."
            unban_ts = record.get("unban_ts", 0)
            if time.time() < unban_ts:
                remaining = int((unban_ts - time.time()) / 60) + 1
                return True, f"🚫 Rate-limited. Try again in <b>{remaining} min</b>."
            else:
                # Clean expired ban
                del spam_data[str(user_id)]
                await save_spam(spam_data)

        # Rate-limit window check
        now    = time.time()
        bucket = _buckets[user_id]

        # Remove old timestamps
        while bucket and now - bucket[0] > SPAM_WINDOW:
            bucket.popleft()

        bucket.append(now)

        if len(bucket) > SPAM_MAX_MSGS:
            # Issue soft ban
            unban_ts = now + SPAM_BAN_MINS * 60
            _bans[user_id] = unban_ts
            spam_data = await load_spam()
            spam_data[str(user_id)] = {
                "user_id":   user_id,
                "banned_at": datetime.now().isoformat(),
                "unban_ts":  unban_ts,
                "permanent": False,
                "reason":    "rate_limit",
            }
            await save_spam(spam_data)
            logger.warning(f"SPAM BAN: user {user_id} — {len(bucket)} msgs in {SPAM_WINDOW}s")
            return True, f"🚫 Too many messages. Banned for <b>{SPAM_BAN_MINS} min</b>."

        return False, ""

    @staticmethod
    async def ban(user_id: int, permanent: bool = False, reason: str = "manual") -> None:
        spam_data = await load_spam()
        unban_ts  = 0 if permanent else time.time() + SPAM_BAN_MINS * 60
        spam_data[str(user_id)] = {
            "user_id":   user_id,
            "banned_at": datetime.now().isoformat(),
            "unban_ts":  unban_ts,
            "permanent": permanent,
            "reason":    reason,
        }
        if permanent:
            _bans[user_id] = float("inf")
        else:
            _bans[user_id] = unban_ts
        await save_spam(spam_data)
        logger.info(f"MANUAL BAN: user {user_id} | permanent={permanent} | reason={reason}")

    @staticmethod
    async def unban(user_id: int) -> bool:
        spam_data = await load_spam()
        if str(user_id) in spam_data:
            del spam_data[str(user_id)]
            await save_spam(spam_data)
            _bans.pop(user_id, None)
            _buckets.pop(user_id, None)
            logger.info(f"UNBAN: user {user_id}")
            return True
        return False

    @staticmethod
    async def get_all_banned() -> list[dict]:
        spam_data = await load_spam()
        now = time.time()
        active = []
        for uid, record in spam_data.items():
            if record.get("permanent") or record.get("unban_ts", 0) > now:
                active.append(record)
        return active

    @staticmethod
    async def is_banned(user_id: int) -> bool:
        banned, _ = await SpamDetector.check(user_id)
        return banned
