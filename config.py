import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
if not BOT_TOKEN:
    raise ValueError(
        "BOT_TOKEN is missing or empty. Please set BOT_TOKEN in your environment or .env file."
    )

BOT_USERNAME = os.getenv("BOT_USERNAME", "Detektivmj_bot")

raw_admin_ids = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = set()
for part in raw_admin_ids.split(","):
    part = part.strip()
    if part.isdigit():
        ADMIN_IDS.add(int(part))

raw_admin_id = os.getenv("ADMIN_ID", "0").strip()
ADMIN_ID = int(raw_admin_id) if raw_admin_id.isdigit() else 0
if ADMIN_ID != 0:
    ADMIN_IDS.add(ADMIN_ID)
ADMIN_USERNAMES = set()

db_env = os.getenv("DB_PATH", "").strip()
if db_env:
    if db_env == ":memory:":
        DB_PATH = ":memory:"
    elif os.path.isabs(db_env):
        DB_PATH = db_env
    else:
        DB_PATH = str((BASE_DIR / db_env).resolve())
else:
    DB_PATH = str(BASE_DIR / "data" / "detektiv.db")
DAY_PHOTO_PATH = str(BASE_DIR / "hayrli_kun.jpg")
NIGHT_PHOTO_PATH = str(BASE_DIR / "osuda_tun.jpg")

MIN_PLAYERS = 4
MAX_PLAYERS = 35

DEFAULT_LOBBY_SECONDS = 300
DEFAULT_NIGHT_SECONDS = 60
DEFAULT_DAY_SECONDS = 15
DEFAULT_VOTE_SECONDS = 45
DEFAULT_VERDICT_SECONDS = 25
DEFAULT_KING_TIMEOUT_SECONDS = 30

# 🎭 ROLLAR RO'YXATI VA JAMOA TAALLUQLILIGI
# blue: Shahar / Tinchlar
# red: Mafia / Qizillar
# solo: Mustaqillar / Neytrallar
ROLES = {
    # 🔵 Shahar (Town / Blue)
    "Detektiv": "blue",
    "Sherif": "blue",
    "Doktor": "blue",
    "Tansoqchi": "blue",
    "Advokat": "blue",
    "Sayyoh": "blue",
    "Ruhshunos": "blue",
    "Mer": "blue",
    "Boy": "blue",
    "Qirol": "blue",
    "Begona": "blue",
    "Savdogar": "blue",
    "Fuqaro": "blue",

    # 🔴 Mafia (Red)
    "Boshliq": "red",
    "Qotil": "red",
    "Soya": "red",
    "Soxtachi": "red",
    "Maftunkor": "red",
    "Kamikadze": "red",
    "Bo'ri": "red",

    # 🟡 Neytrallar (Solo)
    "Joker": "solo",
    "Maniak": "solo",
    "Pirotexnik": "solo",
    "Qasoskor": "solo",
    "Pul o'g'risi": "solo",
    "Firibgar": "solo",
}

ROLE_ORDER = list(ROLES.keys())

# 🔁 12+ o'yinchilarda ko'p marta chiqishi mumkin bo'lgan rollar
REPEATABLE_ROLES = {
    "Fuqaro",
    "Qotil",
    "Soya",
    "Bo'ri",
    "Qasoskor",
    "Tansoqchi",
}

# 🌙 Tunda faol harakat qiluvchi rollar
NIGHT_ACTIVE_ROLES = {
    "Detektiv",
    "Sherif",
    "Doktor",
    "Tansoqchi",
    "Advokat",
    "Sayyoh",
    "Ruhshunos",
    "Boy",
    "Savdogar",
    "Begona",
    "Boshliq",
    "Qotil",
    "Soya",
    "Soxtachi",
    "Maftunkor",
    "Joker",
    "Maniak",
    "Pirotexnik",
    "Qasoskor",
    "Pul o'g'risi",
    "Firibgar",
    "Bo'ri",
}

# 🛒 DO'KON KONSTANTALARI
COIN_SHOP = {
    "fake_document": ("📄 Soxta hujjat", 200),
    "ruler_protection": ("👑 Hukmdan himoya", 200),
    "coin_protect": ("🛡️ Himoya", 100),
    "rose": ("🌹 Gul", 200),
    "extra_vote": ("🗳️ Qo'shimcha ovoz", 150),
}

GOLD_SHOP = {
    "badge_special": ("✦ Maxsus belgi", 300),
    "badge_crown": ("👑 Qirol Toji", 300),
    "badge_lightning": ("⚡ Yashin belgisi", 300),
    "badge_mystery": ("🕶️ Sirli Detektiv", 300),
    "badge_sharpshooter": ("🎯 Aniqchi", 300),
    "revenge_knife": ("🔪 Qasos pichog'i", 5),
}

BADGE_DAYS = 30
