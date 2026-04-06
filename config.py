# ============================================================
#  SMLBot v2.0 — config.py
# ============================================================
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN            = os.getenv("BOT_TOKEN", "")
OWNER_ID         = int(os.getenv("OWNER_ID", "0"))
ADMIN_IDS        = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))
GROUP_ID         = int(os.getenv("GROUP_ID", "0"))
LOG_ADMIN_ID     = int(os.getenv("LOG_ADMIN_ID", "0"))
CHANNEL_ID       = os.getenv("CHANNEL_ID", "@Taskbd")
LOG_CHANNEL      = os.getenv("LOG_CHANNEL", "@Taskbd")

BASE_DIR         = os.path.dirname(os.path.abspath(__file__))
DATA_DIR         = os.path.join(BASE_DIR, "data")
USERS_DIR        = os.path.join(BASE_DIR, "users")
LOGS_DIR         = os.path.join(BASE_DIR, "logs")
EXPORTS_DIR      = os.path.join(BASE_DIR, "exports")

LICENSES_FILE    = os.path.join(DATA_DIR, "licenses.json")
PENDING_FILE     = os.path.join(DATA_DIR, "pending.json")
WITHDRAWALS_FILE = os.path.join(DATA_DIR, "withdrawals.json")
PRICELIST_FILE   = os.path.join(DATA_DIR, "price_list.json")
SPAM_FILE        = os.path.join(DATA_DIR, "spam_users.json")
TWOFA_CSV        = os.path.join(USERS_DIR, "2faall.csv")

MIN_WITHDRAW     = 10
VALID_PAY_METHODS = ["bkash", "nagad", "rocket", "upay"]

SPAM_MAX_MSGS    = 8
SPAM_WINDOW      = 10
SPAM_BAN_MINS    = 30

LINES_PER_PAGE   = 30
USERS_PER_PAGE   = 5

PARTY_STICKER    = "5298766204649872471"
MESSAGE_EFFECTS  = [
    {"name": "Fire",        "id": "5104841245755180586"},
    {"name": "Thumbs Up",   "id": "5107584321108051014"},
    {"name": "Heart",       "id": "5044134455711629726"},
    {"name": "Celebration", "id": "5046509860389126442"},
]

BOT_VERSION      = "2.0.0"
BOT_NAME         = "SMLBot"
