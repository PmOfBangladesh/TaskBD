# ============================================================
#  helpers/validators.py
# ============================================================
from datetime import datetime


def is_valid_key(text: str) -> bool:
    return "-SML-" in text.strip().upper()


def is_valid_date(text: str) -> bool:
    try:
        datetime.strptime(text.strip().replace("/", "-"), "%Y-%m-%d")
        return True
    except ValueError:
        return False


def is_valid_amount(text: str) -> tuple[bool, float]:
    try:
        v = float(text.strip())
        return (v > 0, v)
    except ValueError:
        return (False, 0.0)


def is_valid_pay_method(text: str) -> bool:
    from config import VALID_PAY_METHODS
    return text.strip().lower() in VALID_PAY_METHODS
