# ============================================================
#  core/logger.py  —  Multi-file async-safe logging
# ============================================================
import logging
import os
from logging.handlers import RotatingFileHandler
from config import LOGS_DIR

os.makedirs(LOGS_DIR, exist_ok=True)

_FMT = "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def _make_handler(filename: str, level=logging.DEBUG) -> RotatingFileHandler:
    path = os.path.join(LOGS_DIR, filename)
    h = RotatingFileHandler(path, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    h.setLevel(level)
    h.setFormatter(logging.Formatter(_FMT, datefmt=_DATEFMT))
    return h


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)

    # Console
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter(_FMT, datefmt=_DATEFMT))
    logger.addHandler(ch)

    # bot.log — INFO+
    logger.addHandler(_make_handler("bot.log", logging.INFO))
    # error.log — ERROR+
    logger.addHandler(_make_handler("error.log", logging.ERROR))
    # debug.log — everything
    logger.addHandler(_make_handler("debug.log", logging.DEBUG))

    return logger


def get_spam_logger() -> logging.Logger:
    logger = logging.getLogger("SpamDetector")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    logger.addHandler(_make_handler("spam.log", logging.INFO))
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(logging.Formatter(_FMT, datefmt=_DATEFMT))
    logger.addHandler(ch)
    return logger


def get_admin_logger() -> logging.Logger:
    logger = logging.getLogger("AdminActions")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    logger.addHandler(_make_handler("admin_actions.log", logging.INFO))
    return logger
