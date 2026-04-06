# ============================================================
#  core/logger.py  —  Multi-file async-safe logging
#  Beautiful structured console output + rotating file logs
# ============================================================
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from config import LOGS_DIR

os.makedirs(LOGS_DIR, exist_ok=True)

_FILE_FMT  = "%(asctime)s [%(name)-20s] %(levelname)-8s %(message)s"
_DATEFMT   = "%Y-%m-%d %H:%M:%S"

# ANSI colour codes — fall back gracefully on Windows / no-tty
_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_COLORS = {
    "DEBUG":    "\033[36m",   # cyan
    "INFO":     "\033[32m",   # green
    "WARNING":  "\033[33m",   # yellow
    "ERROR":    "\033[31m",   # red
    "CRITICAL": "\033[35m",   # magenta
}
_ICONS = {
    "DEBUG":    "🔵",
    "INFO":     "✅",
    "WARNING":  "⚠️ ",
    "ERROR":    "❌",
    "CRITICAL": "🔥",
}

_USE_COLOR = sys.stdout.isatty() or os.getenv("FORCE_COLOR", "").lower() in ("1", "true", "yes")


class _BotConsoleFormatter(logging.Formatter):
    """Pretty, coloured console formatter."""

    def format(self, record: logging.LogRecord) -> str:
        lvl   = record.levelname
        icon  = _ICONS.get(lvl, "  ")
        color = _COLORS.get(lvl, "") if _USE_COLOR else ""
        reset = _RESET if _USE_COLOR else ""
        bold  = _BOLD  if _USE_COLOR else ""
        dim   = _DIM   if _USE_COLOR else ""

        ts   = self.formatTime(record, _DATEFMT)
        name = f"{record.name:<20}"
        msg  = record.getMessage()

        line = (
            f"{dim}{ts}{reset} "
            f"{color}{bold}{icon} {lvl:<8}{reset} "
            f"{dim}[{name}]{reset}  "
            f"{color}{msg}{reset}"
        )

        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


def _make_handler(filename: str, level: int = logging.DEBUG) -> RotatingFileHandler:
    path = os.path.join(LOGS_DIR, filename)
    h = RotatingFileHandler(path, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
    h.setLevel(level)
    h.setFormatter(logging.Formatter(_FILE_FMT, datefmt=_DATEFMT))
    return h


def _make_console_handler(level: int = logging.INFO) -> logging.StreamHandler:
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    ch.setFormatter(_BotConsoleFormatter())
    return ch


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.DEBUG)

    logger.addHandler(_make_console_handler(logging.INFO))
    logger.addHandler(_make_handler("bot.log",   logging.INFO))
    logger.addHandler(_make_handler("error.log", logging.ERROR))
    logger.addHandler(_make_handler("debug.log", logging.DEBUG))

    return logger


def get_spam_logger() -> logging.Logger:
    logger = logging.getLogger("SpamDetector")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    logger.addHandler(_make_handler("spam.log", logging.INFO))
    logger.addHandler(_make_console_handler(logging.WARNING))
    return logger


def get_admin_logger() -> logging.Logger:
    logger = logging.getLogger("AdminActions")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    logger.addHandler(_make_handler("admin_actions.log", logging.INFO))
    logger.addHandler(_make_console_handler(logging.INFO))
    return logger
