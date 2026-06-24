import os
import re
import time
import json
import asyncio
import threading
import sys
import shutil

# Windows compatibility fix for asyncio and Pyrogram
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from pyrogram import Client, filters
from pyrogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from pyrogram.errors import (
    FloodWait,
    PeerIdInvalid,
    UserPrivacyRestricted,
    UsernameNotOccupied,
    UserNotParticipant,
    InviteHashExpired,
    ChannelPrivate,
    UserAlreadyParticipant,
    UserDeactivated,
)
from pyrogram import idle
from pyrogram.raw import functions

# ================= KONSOL VA TOKEN SOZLAMALARI =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

def load_config():
    # Environment variables (Railway.app uchun)
    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    bot_token = os.getenv("BOT_TOKEN")
    
    if api_id and api_hash and bot_token:
        return {
            "API_ID": int(api_id),
            "API_HASH": api_hash,
            "BOT_TOKEN": bot_token
        }
    
    # Local development uchun config.json
    parent_config = os.path.join(os.path.dirname(BASE_DIR), "config.json")
    if not os.path.exists(CONFIG_FILE) and os.path.exists(parent_config):
        with open(parent_config, "r", encoding="utf-8") as f:
            config = json.load(f)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
        return config
    if not os.path.exists(CONFIG_FILE):
        token = input("Bot Tokenni kiriting (@BotFather dan olingan): ")
        config = {
            "API_ID": 36427121,
            "API_HASH": "f4b857c7d7e08dce9244615ef32d7cc7",
            "BOT_TOKEN": token
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
        return config
    else:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)

config = load_config()

# 1. BOT KLIYENTI - run_bot() ichida yaratiladi (Windows asyncio fix)
bot_app = None  # Global referens, run_bot() da to'ldiriladi

# ================= YORDAMCHI FUNKSIYALAR =================
def parse_group_input(raw: str):
    """Guruh username, ID yoki invite havolasini ajratib oladi."""
    text = raw.strip()
    if not text:
        return None

    if text.lstrip("-").isdigit():
        return int(text)

    invite_match = re.search(
        r"(?:https?://)?(?:www\.)?t\.me/(?:\+|joinchat/)([A-Za-z0-9_-]+)",
        text,
    )
    if invite_match:
        return f"https://t.me/+{invite_match.group(1)}"

    link_match = re.search(r"(?:https?://)?(?:www\.)?t\.me/([A-Za-z0-9_]+)", text)
    if link_match:
        username = link_match.group(1)
        if username.lower() not in ("joinchat", "addstickers", "share", "proxy", "socks"):
            return username

    if text.startswith("@"):
        return text[1:]

    if re.fullmatch(r"[A-Za-z0-9_]{5,32}", text):
        return text

    return text


async def resolve_chat_id(client, raw: str):
    """Guruhni topadi; invite link bo'lsa avval qo'shiladi."""
    target = parse_group_input(raw)
    if not target:
        raise ValueError("Guruh manzili bo'sh")

    if isinstance(target, str) and target.startswith("https://t.me/+"):
        try:
            chat = await client.join_chat(target)
        except UserAlreadyParticipant:
            chat = await client.get_chat(target)
        return chat.id, chat.title or "Guruh"

    chat = await client.get_chat(target)
    return chat.id, chat.title or str(target)


def explain_telegram_error(error: Exception) -> str:
    err = str(error)
    if isinstance(error, UsernameNotOccupied) or "USERNAME_NOT_OCCUPIED" in err:
        return (
            "❌ **Bunday @username topilmadi!**\n\n"
            "Ehtimol:\n"
            "• Guruh **nomi** emas, **@username** yuborilishi kerak\n"
            "• Username xato yozilgan (`@empire_mafia` kabi)\n"
            "• Guruh yopiq — **invite havola** yuboring: `https://t.me/+xxxxx`\n"
            "• Guruh o'chirilgan yoki username o'zgartirilgan"
        )
    if isinstance(error, UserNotParticipant) or "USER_NOT_PARTICIPANT" in err:
        return (
            "❌ **Siz bu guruhda yo'qsiz!**\n\n"
            "Scraper ishlashi uchun user akkauntingiz avval guruhga qo'shilishi kerak."
        )
    if isinstance(error, ChannelPrivate) or "CHANNEL_PRIVATE" in err:
        return "❌ **Guruh yopiq!** Invite havola (`t.me/+...`) yuboring yoki guruhga qo'shiling."
    if isinstance(error, InviteHashExpired) or "INVITE_HASH_EXPIRED" in err:
        return "❌ **Invite havola muddati tugagan.** Yangi havola oling."
    if "PEER_ID_INVALID" in err:
        return "❌ **Guruh topilmadi.** Username yoki havolani tekshiring."
    return f"❌ Xatolik yuz berdi.\n\n`{err}`"


# ================= MA'LUMOTLAR BAZASI =================
user_states = {}
user_pagination = {}
active_tasks = {}
last_commands = {}
pagination_cooldown = {}
tasks_lock = threading.Lock()
COMMAND_COOLDOWN = 1.0  # 1 soniya cooldown (qisqartirildi)
PAGINATION_COOLDOWN = 0.8
PAGINATION_SIZE = 50
DATABASE_DIR = os.path.join(BASE_DIR, "database")
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(DATABASE_DIR, exist_ok=True)

# User sessionlarni boshqarish
user_clients = {}  # {user_id: Client}
clients_lock = threading.Lock()

# Logged in users uchun ID tracking
logged_in_users = set()  # {user_id}

# Login uchun vaqtinchalik ma'lumotlar
login_data = {}  # {user_id: {"phone": "...", "phone_code_hash": "...", "client": Client}}

def get_user_client(user_id):
    """User uchun client olish yoki yaratish"""
    with clients_lock:
        if user_id in user_clients:
            return user_clients[user_id]
        
        session_name = f"sessions/user_{user_id}"
        client = Client(
            session_name,
            api_id=config["API_ID"],
            api_hash=config["API_HASH"],
            workdir=BASE_DIR,
        )
        user_clients[user_id] = client
        return client

async def get_user_client_started(user_id):
    """User uchun client olish va start qilish"""
    client = get_user_client(user_id)
    if not client.is_connected:
        try:
            await client.start()
        except:
            pass  # Login paytida start qilinadi
    return client

def is_user_logged_in(user_id):
    """User login qilganmi tekshirish"""
    # Taqdimot uchun user ID bo'yicha tekshirish
    return user_id in logged_in_users

# ================= YORIQNOMA TUGMALARI =================
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

def api_id_guide_keyboard():
    """API_ID yoriqnoma tugmasi"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Yoriqnoma", callback_data="guide_api_id")]
    ])

def api_hash_guide_keyboard():
    """API_HASH yoriqnoma tugmasi"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📖 Yoriqnoma", callback_data="guide_api_hash")]
    ])

@bot_app.on_callback_query(filters.regex("^guide_api_id$"))
async def guide_api_id_callback(client, callback):
    """API_ID yoriqnomasini ko'rsatish"""
    text = (
        "📖 **API_ID olish bo'yicha yoriqnoma:**\n\n"
        "1️⃣ Quyidagi saytga o'ting:\n"
        "[my.telegram.org](https://my.telegram.org)\n\n"
        "2️⃣ Telegram bilan login qiling (telefon raqam + kod)\n\n"
        "3️⃣ 'API development tools' bo'limiga o'ting\n\n"
        "4️⃣ 'Create new application' tugmasini bosing\n\n"
        "5️⃣ Ma'lumotlarni to'ldiring:\n"
        "   - App title: Empire Bot\n"
        "   - Short name: empirebot\n"
        "   - Platform: Desktop\n\n"
        "6️⃣ 'Create application' tugmasini bosing\n\n"
        "7️⃣ API_ID ni ko'ring (masalan: 12345678)\n\n"
        "❌ Yopish uchun: /cancel"
    )
    await callback.message.edit_text(text, disable_web_page_preview=True)

@bot_app.on_callback_query(filters.regex("^guide_api_hash$"))
async def guide_api_hash_callback(client, callback):
    """API_HASH yoriqnomasini ko'rsatish"""
    text = (
        "📖 **API_HASH olish bo'yicha yoriqnoma:**\n\n"
        "1️⃣ Quyidagi saytga o'ting:\n"
        "[my.telegram.org](https://my.telegram.org)\n\n"
        "2️⃣ 'API development tools' bo'limiga o'ting\n\n"
        "3️⃣ Siz yaratgan applicationni tanlang\n\n"
        "4️⃣ API_HASH ni ko'ring (masalan: a1b2c3d4e5f6g7h8i9j0)\n\n"
        "5️⃣ API_HASH ni nusxalab botga yuboring\n\n"
        "❌ Yopish uchun: /cancel"
    )
    await callback.message.edit_text(text, disable_web_page_preview=True)


# ================= ADMINLIK TIZIMI =================
# Adminlar ro'yxati (ID lar)
ADMIN_IDS = {
    8513957498,  # Bosh admin (siz)
    8691898228,  # Ikkinchi admin
}

# Bosh admin ID (faqat /admins buyruqi uchun)
SUPER_ADMIN_ID = 8513957498

# Ikkinchi admin ID (faqat /shutdown va /power buyruqlari uchun)
SECOND_ADMIN_ID = 8691898228

# Bot offline holati
bot_offline = False

def is_admin(user_id):
    """Foydalanuvchi admin ekanligini tekshiradi"""
    return user_id in ADMIN_IDS

def is_super_admin(user_id):
    """Foydalanuvchi bosh admin ekanligini tekshiradi"""
    return user_id == SUPER_ADMIN_ID

def is_second_admin(user_id):
    """Foydalanuvchi ikkinchi admin ekanligini tekshiradi"""
    return user_id == SECOND_ADMIN_ID

# ================= XABARLARNI KUZATISH =================
last_bot_messages = {}  # {user_id: {"message_id": int, "is_editable": bool}}


async def send_or_edit_message(client, target_id, text, reply_markup=None, force_new=False):
    """Oxirgi xabarni edit qiladi yoki yangisini yuboradi"""
    if not force_new and target_id in last_bot_messages:
        last_msg = last_bot_messages[target_id]
        if last_msg["is_editable"]:
            try:
                await client.edit_message_text(
                    target_id,
                    last_msg["message_id"],
                    text,
                    reply_markup=reply_markup,
                )
                return
            except Exception:
                pass  # Edit qilib bo'lmadi, yangi xabar yuboramiz
    
    # Yangi xabar yuborish
    try:
        msg = await client.send_message(target_id, text, reply_markup=reply_markup)
        last_bot_messages[target_id] = {
            "message_id": msg.id,
            "is_editable": True
        }
        return msg
    except Exception as e:
        # Agar xabar yuborib bo'lmasa, oddiy reply_text ishlatamiz
        try:
            msg = await client.send_message(target_id, text, reply_markup=reply_markup)
            last_bot_messages[target_id] = {
                "message_id": msg.id,
                "is_editable": True
            }
            return msg
        except:
            return None

# ================= HIMOYA TIZIMI =================
flood_protection = {}  # {user_id: {"count": int, "start_time": float, "blocked_until": float}}
FLOOD_THRESHOLD = 10  # 10 soniyada 10 ta xabar
FLOOD_BLOCK_TIME = 60  # 60 soniya blok
FLOOD_WARNING_TIME = 30  # 30 soniya ogohlantirish

blocked_users = {}  # {user_id: {"blocked_until": float, "reason": str, "warnings": int}}
MAX_WARNINGS = 3  # 3 ta ogohlantirishdan keyin permanent blok


def check_flood(user_id):
    """Flood attack detection"""
    now = time.time()
    
    # Agar user bloklangan bo'lsa (permanent yoki temporary)
    if user_id in blocked_users:
        blocked_until = blocked_users[user_id].get("blocked_until", 0)
        if blocked_until == 0:  # Permanent block
            return f"🚫 **Siz bloklangansiz!**\n\nSabab: {blocked_users[user_id]['reason']}\n\nAdmin bilan bog'laning.", True
        elif now < blocked_until:  # Temporary block
            remaining = int(blocked_until - now)
            return f"⚠️ **Flood himoya!**\n\nSiz juda tez xabar yuboryapsiz.\n⏳ {remaining} soniya kuting.", True
        else:
            # Block muddati tugadi, qaytadan boshlash
            del blocked_users[user_id]
    
    # Flood countni yangilash
    if user_id not in flood_protection:
        flood_protection[user_id] = {"count": 0, "start_time": now, "blocked_until": 0}
    
    # 10 soniyadan o'tsa, countni qaytadan boshlash
    if now - flood_protection[user_id]["start_time"] > 10:
        flood_protection[user_id]["count"] = 0
        flood_protection[user_id]["start_time"] = now
    
    flood_protection[user_id]["count"] += 1
    
    # Flood thresholdni tekshirish
    if flood_protection[user_id]["count"] >= FLOOD_THRESHOLD:
        # Userni bloklash
        if user_id not in blocked_users:
            blocked_users[user_id] = {"blocked_until": 0, "reason": "", "warnings": 0}
        
        blocked_users[user_id]["warnings"] += 1
        warnings = blocked_users[user_id]["warnings"]
        
        if warnings >= MAX_WARNINGS:
            # Permanent block
            blocked_users[user_id]["blocked_until"] = 0
            blocked_users[user_id]["reason"] = "Ko'p marta flood qilish"
            flood_protection[user_id]["count"] = 0
            return f"🚫 **PERMANENT BLOK!**\n\nSiz {MAX_WARNINGS} marta ogohlantirildingiz.\nEndi botdan foydalanish taqiqlandi.", True
        else:
            # Temporary block
            block_time = FLOOD_BLOCK_TIME * warnings  # Har safar ko'payadi
            blocked_users[user_id]["blocked_until"] = now + block_time
            flood_protection[user_id]["count"] = 0
            return f"⚠️ **FLOOD HIMOYA FAOL!**\n\nSiz juda ko'p xabar yubordingiz.\n⏳ {block_time} soniya bloklandingiz.\n⚠️ Ogohlantirish: {warnings}/{MAX_WARNINGS}", True
    
    # Warning
    if flood_protection[user_id]["count"] >= FLOOD_THRESHOLD - 3:
        return f"⚠️ **Ogohlantirish!**\n\nTez-tez xabar yubormang.\nAks holda bloklanishingiz mumkin.", False
    
    return None, False

MENU_BUTTONS = frozenset({
    "🚀 Scraper",
    "🔍 Guruh Qidirish",
    "📨 Xabar yuborish",
    "📁 Yig'ilgan userlar",
})

DATABASE_BUTTONS = frozenset({
    "🗑️ Bazani tozalash",
    "🏠 Asosiy menyu",
})

SCRAPER_FILTERS = frozenset({
    "⚡ Avtomatik (Tez)",
    "📊 Xabarlar orqali (Sekin)",
    "🌸 Qizlar (Filtrlangan)",
    "👱‍♀️ Adminlar",
})

TASK_LABELS = {
    "scrape": "🚀 Scraper",
    "broadcast": "📨 Xabar yuborish",
    "search": "🔍 Guruh qidirish",
}

DEDUP_EXEMPT = frozenset({"❌ Bekor qilish", "/cancel"})

scraper_selections = {}


def get_active_task(user_id):
    with tasks_lock:
        return active_tasks.get(user_id)


def acquire_task(user_id, task_name):
    with tasks_lock:
        current = active_tasks.get(user_id)
        if current:
            return False, current
        active_tasks[user_id] = task_name
        return True, None


def release_task(user_id, task_name):
    with tasks_lock:
        if active_tasks.get(user_id) == task_name:
            active_tasks.pop(user_id, None)


def is_duplicate_command(user_id, text):
    now = time.time()
    with tasks_lock:
        prev = last_commands.get(user_id)
        if prev and prev["text"] == text and now - prev["time"] < COMMAND_COOLDOWN:
            return True
        last_commands[user_id] = {"text": text, "time": now}
        return False


def active_task_message(task_name):
    return f"⚠️ **{TASK_LABELS.get(task_name, task_name)}** hali ishlayapti. Tugashini kuting."

if not os.path.exists(DATABASE_DIR):
    os.makedirs(DATABASE_DIR)

def get_user_file(user_id):
    return os.path.join(DATABASE_DIR, f"users_{user_id}.txt")


def load_user_database(user_id):
    file_path = get_user_file(user_id)
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def save_user_database(user_id, usernames):
    with open(get_user_file(user_id), "w", encoding="utf-8") as f:
        for username in usernames:
            f.write(f"{username}\n")


def format_user_batch(total, batch_usernames, start_num, end_num):
    lines = [
        f"📊 Yig'ildi: {total} user",
        f"({start_num}-{end_num})",
        "",
    ]
    lines.extend(batch_usernames)
    return "\n".join(lines)


def get_total_pages(count, batch_size=PAGINATION_SIZE):
    return max(1, (count + batch_size - 1) // batch_size)


def get_page_slice(usernames, page, batch_size=PAGINATION_SIZE):
    start = page * batch_size
    chunk = usernames[start : start + batch_size]
    return chunk, start + 1, start + len(chunk)


def build_nav_keyboard(page, total_users, batch_size=PAGINATION_SIZE):
    if total_users <= batch_size:
        return None

    total_pages = get_total_pages(total_users, batch_size)
    row = []
    if page > 0:
        row.append(InlineKeyboardButton("⬅️ Oldingi", callback_data="pg:prev"))
    if page < total_pages - 1:
        row.append(InlineKeyboardButton("➡️ Orqaga", callback_data="pg:next"))
    row.append(InlineKeyboardButton("❌ Yopish", callback_data="pg:close"))
    return InlineKeyboardMarkup([row])


def show_paginated_users(client, target_id, usernames, page=0):
    total = len(usernames)
    chunk, start_num, end_num = get_page_slice(usernames, page)
    text = format_user_batch(total, chunk, start_num, end_num)
    keyboard = build_nav_keyboard(page, total)

    user_pagination[target_id] = {"usernames": usernames, "page": page}
    client.send_message(target_id, text, reply_markup=keyboard)




def interruptible_sleep(seconds, stop_event, step=0.5):
    elapsed = 0.0
    while elapsed < seconds:
        if stop_event.is_set():
            return True
        time.sleep(min(step, seconds - elapsed))
        elapsed += step
    return stop_event.is_set()


def chunk_list(items, batch_size):
    for i in range(0, len(items), batch_size):
        yield items[i : i + batch_size]


async def scrape_task(target_id, raw_group, filter_type="⚡ Avtomatik (Tez)", message_count=None):
    try:
        user_client = await get_user_client_started(target_id)
        chat_id, chat_title = await resolve_chat_id(user_client, raw_group)
        
        if filter_type == "📊 Xabarlar orqali (Sekin)":
            max_messages = message_count if message_count else 1000
            # Boshlang'ich xabar
            bot_app.send_message(
                target_id,
                f"🔍 **{chat_title}** guruhidan xabarlar o'qilmoqda...\n📌 Filtr: {filter_type}\n\n⏳ {max_messages:,} ta xabar o'qiladi.",
            )
            
            scraped = set()
            msg_count = 0
            progress_interval = max(100, max_messages // 100)  # Dynamic progress reporting
            
            async for message in user_client.get_chat_history(chat_id, limit=max_messages):
                if message.from_user and not message.from_user.is_bot and message.from_user.username:
                    scraped.add(f"@{message.from_user.username}")
                msg_count += 1
                if msg_count % progress_interval == 0:
                    # Progress update - edit qilish
                    try:
                        if target_id in last_bot_messages:
                            bot_app.edit_message_text(
                                target_id,
                                last_bot_messages[target_id]["message_id"],
                                f"🔍 **{chat_title}** guruhidan xabarlar o'qilmoqda...\n📌 Filtr: {filter_type}\n\n⏳ {msg_count:,}/{max_messages:,} ta xabar o'qildi...",
                            )
                    except:
                        pass  # Edit qilib bo'lmadi, davom etamiz
            
        else:
            # Boshlang'ich xabar
            bot_app.send_message(
                target_id,
                f"🔍 **{chat_title}** guruhidan userlar yig'ilmoqda...\n📌 Filtr: {filter_type}\n\n⏳ 0 ta user yig'ildi...",
            )

            scraped = set()
            member_count = 0
            progress_interval = 50  # Har 50 ta userdan keyin update
            
            async for member in user_client.get_chat_members(chat_id):
                if member.user.is_bot or not member.user.username:
                    continue

                username = f"@{member.user.username}"

                if filter_type == "⚡ Avtomatik (Tez)":
                    scraped.add(username)

                elif filter_type == "👱‍♀️ Adminlar":
                    if member.status in ("creator", "administrator"):
                        scraped.add(username)

                elif filter_type == "🌸 Qizlar (Filtrlangan)":
                    username_lower = member.user.username.lower()
                    
                    # 1. Username oxiri 'a' bilan tugaganlar (raqamdan oldingi harfga qarab)
                    # Oxirgi harfni topish (raqamlarni e'tiborsiz qoldirish)
                    last_char = None
                    for char in reversed(username_lower):
                        if char.isalpha():
                            last_char = char
                            break
                    
                    if last_char == 'a':
                        scraped.add(username)
                    else:
                        # 2. Tarkibida ayol ismlari bo'lganlar
                        female_keywords = ["gul", "niso", "bibi", "khan", "xon", "begim", "oy", "mariya", "nigora", "sevara", "dilnoza", "malika", "zuhra", "nargiza", "kamola", "mavjuda", "shahnoza", "aziza", "fatima", "zaynab", "aisha", "khadija", "mukarram", "makhsuma", "zahra", "ruziya", "mubina", "salima", "habiba", "jamila", "latifa", "nafisa", "safiya", "sumaya", "ummu", "aysha", "fotima", "hafsa", "sawda", "ruqayya", "kulthum", "aliya", "amina", "asfiya", "baraka", "bushra", "dalia", "eisha", "fariha", "ghada", "haniya", "imana", "jana", "kadija", "laila", "mahira", "nadia", "omar", "parveen", "qasira", "raisa", "sana", "tahira", "umara", "wafa", "yamila", "zara", "zoya", "nur", "noor", "shams", "hilal", "badr", "najma", "sitar", "anahita", "anara", "arzu", "asal", "barakat", "bina", "bonu", "dila", "dilbara", "dildora", "dilfuza", "dilrabo", "dilshoda", "elina", "eliza", "emira", "farangiz", "farida", "feruza", "gavhar", "gulandom", "gulbahor", "gulchehra", "guldasta", "gulira", "gulnara", "gulnoza", "gulruhsora", "gulshoda", "gulsanam", "gulzara", "hadicha", "hayola", "hilola", "humora", "inobat", "kamola", "kumush", "lola", "malika", "maftuna", "makhsuma", "mavjuda", "mavzuna", "mehriniso", "mohira", "mubina", "mukarrama", "muslima", "nafisa", "nargiza", "nigora", "niso", "nodira", "noila", "nurida", "nurjahan", "nurkhon", "nurliyo", "nurshoda", "nurzoda", "parvina", "rano", "rakhima", "ramina", "ravshana", "raykhona", "roya", "roziya", "ruhida", "ruhijon", "ruziya", "sabina", "sadiya", "safina", "sahar", "saliha", "salima", "samira", "sana", "sanobar", "sarvinoz", "sevinch", "shahida", "shahnoza", "sharifa", "shirin", "shodiyona", "shukrona", "sitora", "sumayya", "surayyo", "tabassum", "tahira", "tamina", "tanzila", "tarona", "umida"]
                        if any(keyword in username_lower for keyword in female_keywords):
                            scraped.add(username)
                
                member_count += 1
                if member_count % progress_interval == 0:
                    # Progress update - edit qilish
                    try:
                        if target_id in last_bot_messages:
                            bot_app.edit_message_text(
                                target_id,
                                last_bot_messages[target_id]["message_id"],
                                f"🔍 **{chat_title}** guruhidan userlar yig'ilmoqda...\n📌 Filtr: {filter_type}\n\n⏳ {len(scraped)} ta user yig'ildi...",
                            )
                    except:
                        pass  # Edit qilib bo'lmadi, davom etamiz

        if not scraped:
            bot_app.send_message(
                target_id,
                f"❌ **{chat_title}** guruhida filtr bo'yicha user topilmadi.",
            )
            return

        existing = load_user_database(target_id)
        existing_set = set(existing)
        new_count = sum(1 for u in scraped if u not in existing_set)
        all_users = existing + [u for u in sorted(scraped) if u not in existing_set]
        save_user_database(target_id, all_users)

        scraped_list = sorted(scraped, key=str.lower)
        bot_app.send_message(
            target_id,
            f"✅ **{chat_title}** guruhidan **{len(scraped_list)}** ta user yig'ildi!\n"
            f"💾 Bazaga **{new_count}** ta yangi qo'shildi (jami: **{len(all_users)}**).",
        )
        show_paginated_users(bot_app, target_id, scraped_list)

    except Exception as e:
        bot_app.send_message(target_id, explain_telegram_error(e))
    finally:
        release_task(target_id, "scrape")


async def broadcast_task(target_id, recipients, body):
    try:
        user_client = await get_user_client_started(target_id)
        success = 0
        failed = 0
        total = len(recipients)
        
        bot_app.send_message(
            target_id,
            f"📤 **Xabar yuborish boshlandi...**\n\n"
            f"📊 Jami: **{total}** ta user\n"
            f"⏳ Jarayon davom etmoqda...",
        )
        
        for idx, username in enumerate(recipients):
            try:
                await user_client.send_message(username, body)
                success += 1
                
                # Har 10 ta userdan keyin progress update
                if (idx + 1) % 10 == 0:
                    try:
                        if target_id in last_bot_messages:
                            bot_app.edit_message_text(
                                target_id,
                                last_bot_messages[target_id]["message_id"],
                                f"📤 **Xabar yuborilmoqda...**\n\n"
                                f"📊 Jami: **{total}** ta user\n"
                                f"✅ Yuborildi: **{success}** ta\n"
                                f"❌ Yuborilmadi: **{failed}** ta\n"
                                f"⏳ Qolgan: **{total - success - failed}** ta",
                            )
                    except:
                        pass  # Edit qilib bo'lmadi, davom etamiz
                
                await asyncio.sleep(3)
            except FloodWait as e:
                time.sleep(e.value + 5)
                try:
                    await user_client.send_message(username, body)
                    success += 1
                except Exception:
                    failed += 1
            except (PeerIdInvalid, UserPrivacyRestricted, Exception):
                failed += 1

        bot_app.send_message(
            target_id,
            f"✅ **Xabar yuborish tugadi!**\n\n"
            f"📤 Yuborildi: **{success}** ta\n"
            f"❌ Yuborilmadi: **{failed}** ta\n"
            f"📊 Jami: **{total}** ta",
            reply_markup=main_menu(),
        )
    except Exception as e:
        bot_app.send_message(target_id, explain_telegram_error(e), reply_markup=main_menu())
    finally:
        release_task(target_id, "broadcast")

# ================= MENYU =================
def main_menu():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("🚀 Scraper"), KeyboardButton("🔍 Guruh Qidirish")],
            [KeyboardButton("📨 Xabar yuborish"), KeyboardButton("📁 Yig'ilgan userlar")]
        ],
        resize_keyboard=True,
        placeholder="Bo'limni tanlang..."
    )

def cancel_menu():
    return ReplyKeyboardMarkup([[KeyboardButton("❌ Bekor qilish")]], resize_keyboard=True)


def database_menu():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("🗑️ Bazani tozalash"), KeyboardButton("🏠 Asosiy menyu")]
        ],
        resize_keyboard=True,
        placeholder="Baza bo'limi..."
    )




def scraper_filter_menu():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("⚡ Avtomatik (Tez)"), KeyboardButton("📊 Xabarlar orqali (Sekin)")],
            [KeyboardButton("🌸 Qizlar (Filtrlangan)"), KeyboardButton("👱‍♀️ Adminlar")],
            [KeyboardButton("❌ Bekor qilish")]
        ],
        resize_keyboard=True,
        placeholder="Filtrni tanlang..."
    )

# ================= HANDLERLAR =================
@bot_app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    user_id = message.from_user.id
    
    # Offline check
    global bot_offline
    if bot_offline:
        return  # Offline bo'lsa, hech narsa qilmaymiz
    
    # Login check
    if not is_user_logged_in(user_id):
        # Yangi login jarayoni - API_ID so'rash
        user_states[user_id] = "login_api_id"
        text = (
            "🔐 **Botdan foydalanish uchun login qiling**\n\n"
            "🔑 **API_ID ni kiriting:**\n"
            "Masalan: `12345678`\n\n"
            "❌ Bekor qilish uchun: /cancel"
        )
        await message.reply_text(text)
        return
    
    # Agar user logged in bo'lsa, menyuni ko'rsatmaslik kerak
    # Chunki login flow davom etmoqda
    if user_states.get(user_id) in ["login_api_id", "login_api_hash", "login_phone", "login_code", "login_password"]:
        return
    
    user_states[user_id] = "menu"
    first_name = message.from_user.first_name or "Mijoz"
    
    text = (
        f"👋 Assalomu alaykum, {first_name}!\n\n"
        "🎭 **Empire Mafia** boshqaruv paneliga xush kelibsiz!\n\n"
        "📌 **Mavjud xizmatlar:**\n"
        "• 🚀 Scraper — guruhlardan user yig'ish\n"
        "• 📨 Xabar yuborish — bazadagi userlarga DM\n"
        "• 🔍 Guruh qidirish — kalit so'z bo'yicha qidiruv\n\n"
        "Quyidagi tugmalardan birini tanlang:"
    )
    await message.reply_text(text, reply_markup=main_menu())


@bot_app.on_message(filters.command("cancel") & filters.private)
async def cancel_command(client, message):
    user_id = message.from_user.id
    state = user_states.get(user_id)
    
    if state in ["login_phone", "login_code", "login_password", "login_upload", "login_api_id", "login_api_hash"]:
        # Login jarayonini bekor qilish
        if user_id in login_data:
            try:
                # Clientni tozalash
                data = login_data[user_id]
                if "client" in data and data["client"].is_connected:
                    data["client"].disconnect()
            except:
                pass
            del login_data[user_id]
        
        user_states[user_id] = "menu"
        await message.reply_text("❌ Login bekor qilindi.", reply_markup=main_menu())
    else:
        await message.reply_text("Hech narsa bekor qilinmadi.")


@bot_app.on_message(filters.command("shutdown") & filters.private)
async def shutdown_command(client, message):
    """Botni offline qiladi (faqat ikkinchi admin uchun)"""
    user_id = message.from_user.id
    
    if not is_second_admin(user_id):
        await message.reply_text("❌ Sizda bu buyruqni ishlatish uchun huquq yo'q.")
        return
    
    global bot_offline
    bot_offline = True
    await message.reply_text("🔴 **Bot offline holatiga o'tdi.**\n\nEndi hech qanday buyruqga javob bermaydi.\nOnline qilish uchun: `/power`")


@bot_app.on_message(filters.command("power") & filters.private)
async def power_command(client, message):
    """Botni online qiladi (faqat ikkinchi admin uchun)"""
    user_id = message.from_user.id
    
    if not is_second_admin(user_id):
        await message.reply_text("❌ Sizda bu buyruqni ishlatish uchun huquq yo'q.")
        return
    
    global bot_offline
    bot_offline = False
    await message.reply_text("🟢 **Bot online holatiga o'tdi.**\n\nEndi barcha buyruqlarga javob berada.")


@bot_app.on_message(filters.command("admins") & filters.private)
async def admins_command(client, message):
    """Adminlar ro'yxatini ko'rsatadi (faqat bosh admin uchun)"""
    user_id = message.from_user.id
    
    # Faqat bosh admin ko'ra oladi
    if not is_super_admin(user_id):
        return  # Bosh admin bo'lmasa, hech narsa qilmaymiz (buyruq mavjud emasdek)
    
    if not ADMIN_IDS:
        await message.reply_text("❌ Hozircha adminlar yo'q.")
        return
    
    # Bosh admin uchun barcha adminlarni ko'rsatadi
    text = f"👑 **Adminlar ro'yxati:**\n\n"
    
    for admin_id in ADMIN_IDS:
        if admin_id == SUPER_ADMIN_ID:
            text += f"• {admin_id} - Bosh Admin (Siz)\n"
        else:
            text += f"• {admin_id} - Admin\n"
    
    text += f"\n• Jami: {len(ADMIN_IDS)} ta admin"
    
    await message.reply_text(text)


# Login flow handlers
async def handle_login_upload(client, message, user_id):
    """Session faylini qabul qilish"""
    if message.document:
        try:
            # Faylni yuklab olish
            file = message.document
            file_path = await client.download_media(file, file_name=f"sessions/user_{user_id}.session")
            
            # Faylni SESSIONS_DIR ga ko'chirish
            final_path = os.path.join(SESSIONS_DIR, f"user_{user_id}.session")
            shutil.move(file_path, final_path)
            
            # Client yaratish va tekshirish
            session_name = f"sessions/user_{user_id}"
            user_client = Client(
                session_name,
                api_id=config["API_ID"],
                api_hash=config["API_HASH"],
                workdir=BASE_DIR,
            )
            
            # Clientni connect qilish
            await user_client.connect()
            
            # Tekshirish - bot emasligini
            me = await user_client.get_me()
            if me.is_bot:
                await message.reply_text("❌ Bu bot session fayli. User session faylini yuboring.")
                os.remove(final_path)
                return
            
            # Muvaffaqiyatli
            with clients_lock:
                user_clients[user_id] = user_client
            
            if user_id in login_data:
                del login_data[user_id]
            user_states[user_id] = "menu"
            
            first_name = message.from_user.first_name or "Mijoz"
            await message.reply_text(
                f"✅ **Muvaffaqiyatli ulandi!**\n\n"
                f"👋 Assalomu alaykum, {first_name}!\n\n"
                "🎭 **Empire Mafia** boshqaruv paneliga xush kelibsiz!\n\n"
                "📌 **Mavjud xizmatlar:**\n"
                "• 🚀 Scraper — guruhlardan user yig'ish\n"
                "• 📨 Xabar yuborish — bazadagi userlarga DM\n"
                "• 🔍 Guruh qidirish — kalit so'z bo'yicha qidiruv\n\n"
                "Quyidagi tugmalardan birini tanlang:",
                reply_markup=main_menu()
            )
        except Exception as e:
            await message.reply_text(f"❌ Xatolik: {str(e)}\n\nQaytadan urinib ko'ring.")
    else:
        await message.reply_text("❌ Iltimos, session faylini yuboring.")


# API_ID/API_HASH handlers
async def handle_login_api_id(client, message, user_id, text):
    """API_ID ni qabul qilish"""
    try:
        api_id = int(text.strip())
        if api_id <= 0:
            await message.reply_text("❌ API_ID musbat son bo'lishi kerak.")
            return False
        
        login_data[user_id] = {"api_id": api_id}
        user_states[user_id] = "login_api_hash"
        await message.reply_text(
            f"✅ API_ID qabul qilindi: `{api_id}`\n\n"
            f"🔑 **API_HASH ni kiriting:**\n"
            f"my.telegram.org dan olingan API_HASH ni yuboring."
        )
        return True
    except ValueError:
        await message.reply_text("❌ API_ID raqam bo'lishi kerak. Masalan: `12345678`")
        return False

async def handle_login_api_hash(client, message, user_id, text):
    """API_HASH ni qabul qilish"""
    if user_id not in login_data:
        await message.reply_text("❌ Avval API_ID kiriting.")
        return False
    
    api_hash = text.strip()
    if len(api_hash) < 10:
        await message.reply_text("❌ API_HASH noto'g'ri ko'rinadi.")
        return False
    
    login_data[user_id]["api_hash"] = api_hash
    user_states[user_id] = "login_phone"
    await message.reply_text(
        f"✅ API_HASH qabul qilindi.\n\n"
        f"📱 **Telefon raqamingizni kiriting:**\n"
        f"Masalan: `+998901234567` yoki `998901234567`\n\n"
        f"📂 **Yoki session fayl yuboring:**\n"
        f"Agar oldin session yaratgan bo'lsangiz, .session faylini yuborishingiz mumkin."
    )
    return True


# Telefon raqam formatini tekshirish
def validate_phone_number(phone: str) -> str:
    """Telefon raqamni tozalash va tekshirish"""
    # Barcha bo'sh joylar, qavslar va chiziqlarni olib tashlash
    cleaned = re.sub(r'[\s\(\)\-\.]', '', phone)
    
    # + belgisini olib tashlash (agar bor bo'lsa)
    if cleaned.startswith('+'):
        cleaned = cleaned[1:]
    
    # Faqat raqamlar qolganini tekshirish
    if not cleaned.isdigit():
        return None
    
    # Uzunligini tekshirish (7-15 raqam)
    if len(cleaned) < 7 or len(cleaned) > 15:
        return None
    
    return cleaned


async def handle_login_phone(client, message, user_id, phone_text):
    """Telefon raqamni qabul qilish va kod yuborish"""
    phone = validate_phone_number(phone_text)
    
    if not phone:
        await message.reply_text(
            "❌ **Noto'g'ri telefon raqam!**\n\n"
            "Iltimos, to'g'ri formatda kiriting:\n"
            "Masalan: `+998901234567` yoki `998901234567`"
        )
        return False
    
    try:
        # User uchun client yaratish
        session_name = f"sessions/user_{user_id}"
        api_id = login_data.get(user_id, {}).get("api_id", config["API_ID"])
        api_hash = login_data.get(user_id, {}).get("api_hash", config["API_HASH"])
        
        user_client = Client(
            session_name,
            api_id=api_id,
            api_hash=api_hash,
            workdir=BASE_DIR,
        )
        
        # Clientni ulash
        await user_client.connect()
        
        # Kod yuborish
        sent_code = await user_client.send_code(phone)
        
        # Ma'lumotlarni saqlash
        login_data[user_id] = {
            "api_id": api_id,
            "api_hash": api_hash,
            "phone": phone,
            "phone_code_hash": sent_code.phone_code_hash,
            "client": user_client
        }
        
        # Keyingi holatga o'tish
        user_states[user_id] = "login_code"
        print(f"🔑 User {user_id} state changed to login_code")
        
        await message.reply_text(
            f"✅ **Kod yuborildi!**\n\n"
            f"📱 Raqam: `{phone}`\n\n"
            f"🔢 Telegramdan kelgan kodni kiriting.\n\n"
            f"💡 Masalan: `12345`"
        )
        return True
        
    except FloodWait as e:
        await message.reply_text(f"⏳ Juda ko'p urinishlar. {e.value} soniya kuting.")
        return False
    except Exception as e:
        print(f"❌ Error in handle_login_phone: {e}")
        await message.reply_text(f"❌ Xatolik: {str(e)}")
        return False


async def handle_login_code(client, message, user_id, code_text):
    """Kodni qabul qilish va login qilish"""
    if user_id not in login_data:
        await message.reply_text("❌ Avval telefon raqamni kiriting.")
        return False
    
    try:
        # Probel, chiziqcha va nuqtalarni olib tashlash
        code = re.sub(r'[\s\-\.]', '', code_text)
        if not code.isdigit():
            await message.reply_text("❌ Kod faqat raqamlardan iborat bo'lishi kerak (probellarsiz 12345 kabi).")
            return False
        
        data = login_data[user_id]
        phone = data["phone"]
        phone_code_hash = data["phone_code_hash"]
        user_client = data["client"]
        
        # Kod bilan login qilish
        try:
            await user_client.sign_in(phone, phone_code_hash, code)
        except Exception as e:
            error_str = str(e)
            if "SESSION_PASSWORD_NEEDED" in error_str or "2FA" in error_str.lower() or "two-factor" in error_str.lower():
                # 2FA parol kerak
                user_states[user_id] = "login_password"
                await message.reply_text(
                    "🔐 **2FA parol kerak**\n\n"
                    "Ikkita faktorli himoya parolini kiriting:\n\n"
                    "❌ Bekor qilish uchun: /cancel"
                )
                return True
            else:
                raise e
        
        # Muvaffaqiyatli login!
        await user_client.disconnect()
        
        session_name = f"sessions/user_{user_id}"
        api_id = data.get("api_id", config["API_ID"])
        api_hash = data.get("api_hash", config["API_HASH"])
        
        # Clientni qaytadan yaratish va saqlash
        user_client = Client(
            session_name,
            api_id=api_id,
            api_hash=api_hash,
            workdir=BASE_DIR,
        )
        
        with clients_lock:
            user_clients[user_id] = user_client
        
        # Tozalash
        if user_id in login_data:
            del login_data[user_id]
        
        user_states[user_id] = "menu"
        logged_in_users.add(user_id)  # User ni logged_in_users ga qo'shish
        
        first_name = message.from_user.first_name or "Mijoz"
        await message.reply_text(
            f"✅ **Muvaffaqiyatli login bo'ldi!**\n\n"
            f"👋 Assalomu alaykum, {first_name}!\n\n"
            f"🎭 **Empire Mafia** boshqaruv paneliga xush kelibsiz!\n\n"
            f"📌 **Mavjud xizmatlar:**\n"
            f"• 🚀 Scraper — guruhlardan user yig'ish\n"
            f"• 📨 Xabar yuborish — bazadagi userlarga DM\n"
            f"• 🔍 Guruh qidirish — kalit so'z bo'yicha qidiruv\n\n"
            f"Quyidagi tugmalardan birini tanlang:",
            reply_markup=main_menu()
        )
        return True
        
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {str(e)}\n\nQaytadan urinib ko'ring.")
        return False


async def handle_login_password(client, message, user_id, password_text):
    """2FA parolni qabul qilish"""
    if user_id not in login_data:
        await message.reply_text("❌ Avval telefon raqamni kiriting.")
        return False
    
    try:
        data = login_data[user_id]
        phone = data["phone"]
        phone_code_hash = data["phone_code_hash"]
        user_client = data["client"]
        
        # Parol bilan login qilish
        await user_client.sign_in(phone, phone_code_hash, password=password_text)
        
        # Muvaffaqiyatli login!
        await user_client.disconnect()
        
        session_name = f"sessions/user_{user_id}"
        api_id = data.get("api_id", config["API_ID"])
        api_hash = data.get("api_hash", config["API_HASH"])
        
        # Clientni qaytadan yaratish va saqlash
        user_client = Client(
            session_name,
            api_id=api_id,
            api_hash=api_hash,
            workdir=BASE_DIR,
        )
        
        with clients_lock:
            user_clients[user_id] = user_client
        
        # Tozalash
        if user_id in login_data:
            del login_data[user_id]
        
        user_states[user_id] = "menu"
        logged_in_users.add(user_id)  # User ni logged_in_users ga qo'shish
        
        first_name = message.from_user.first_name or "Mijoz"
        await message.reply_text(
            f"✅ **Muvaffaqiyatli login bo'ldi!**\n\n"
            f"👋 Assalomu alaykum, {first_name}!\n\n"
            f"🎭 **Empire Mafia** boshqaruv paneliga xush kelibsiz!\n\n"
            f"📌 **Mavjud xizmatlar:**\n"
            f"• 🚀 Scraper — guruhlardan user yig'ish\n"
            f"• 📨 Xabar yuborish — bazadagi userlarga DM\n"
            f"• 🔍 Guruh qidirish — kalit so'z bo'yicha qidiruv\n\n"
            f"Quyidagi tugmalardan birini tanlang:",
            reply_markup=main_menu()
        )
        return True
        
    except Exception as e:
        await message.reply_text(f"❌ Noto'g'ri parol: {str(e)}\n\nQaytadan urinib ko'ring.")
        return False


@bot_app.on_message(filters.private & ~filters.command(["start", "shutdown", "power", "admins", "cancel"]))
async def process_messages(client, message):
    user_id = message.from_user.id
    text = message.text

    if not text:
        return
    
    # Debug logging
    state = user_states.get(user_id)
    print(f"📨 User {user_id} sent: '{text}', current state: {state}")
    
    # Login flow - API_ID kiritilganda
    if state == "login_api_id":
        await handle_login_api_id(client, message, user_id, text)
        return
    
    # Login flow - API_HASH kiritilganda
    if state == "login_api_hash":
        await handle_login_api_hash(client, message, user_id, text)
        return
    
    # Login flow - session fayl yuborilganda
    if state == "login_upload":
        if message.document:
            await handle_login_upload(client, message, user_id)
        else:
            await message.reply_text("❌ Iltimos, session faylini yuboring.")
        return
    
    # Login flow - telefon raqam kiritilganda
    if state == "login_phone":
        # Agar session fayl yuborilgan bo'lsa
        if message.document:
            await handle_login_upload(client, message, user_id)
            return
        # Telefon raqamni qabul qilish
        await handle_login_phone(client, message, user_id, text)
        return
    
    # Login flow - kod kiritilganda
    if state == "login_code":
        print(f"🔑 Processing code for user {user_id}")
        await handle_login_code(client, message, user_id, text)
        return
    
    # Login flow - 2FA parol kiritilganda
    if state == "login_password":
        await handle_login_password(client, message, user_id, text)
        return
    
    # Offline check - admin buyruqlaridan tashqari barchasini ignore qiladi
    global bot_offline
    if bot_offline:
        # Faqat adminlar /power buyruqini ishlatishi mumkin
        if text == "/power" and is_admin(user_id):
            # Bu buyruq alohida handlerda ishlaydi
            pass
        else:
            return  # Offline bo'lsa, barcha xabarlarni ignore qiladi

    # Flood protection check
    flood_message, is_blocked = check_flood(user_id)
    if flood_message:
        await send_or_edit_message(client, user_id, flood_message)
        if is_blocked:
            return

    if text in ["❌ Bekor qilish", "/cancel"]:
        user_states[user_id] = "menu"
        await send_or_edit_message(client, user_id, "🏠 Asosiy menyuga qaytdingiz.", reply_markup=main_menu())
        return


    state = user_states.get(user_id, "menu")

    if text in MENU_BUTTONS:
        if state != "menu":
            await send_or_edit_message(client, user_id, 
                "⚠️ Avval joriy amalni tugating yoki `❌ Bekor qilish` bosing.",
                reply_markup=cancel_menu(),
            )
            return
        active = get_active_task(user_id)
        if active:
            await send_or_edit_message(client, user_id, active_task_message(active), reply_markup=main_menu())
            return

    if text in DATABASE_BUTTONS:
        if text == "🗑️ Bazani tozalash":
            file_path = get_user_file(user_id)
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    await send_or_edit_message(client, user_id, "✅ Bazani muvaffaqiyatli tozaladim.", reply_markup=main_menu())
                except Exception as e:
                    await send_or_edit_message(client, user_id, f"❌ Xatolik: {e}", reply_markup=database_menu())
            else:
                await send_or_edit_message(client, user_id, "❌ Baza allaqachon bo'sh.", reply_markup=database_menu())
            user_states[user_id] = "menu"
        elif text == "🏠 Asosiy menyu":
            user_states[user_id] = "menu"
            await send_or_edit_message(client, user_id, "🏠 Asosiy menyuga qaytdingiz.", reply_markup=main_menu())
        return

    if text not in DEDUP_EXEMPT and is_duplicate_command(user_id, text):
        await send_or_edit_message(client, user_id,
            "⚠️ Xuddi shu buyruq hozirgina yuborilgan. Biroz kuting.",
            reply_markup=main_menu() if state == "menu" else cancel_menu(),
        )
        return

    # ----- ASOSIY MENYU -----
    if state == "menu":
        if text == "🚀 Scraper":
            user_states[user_id] = "scrape_wait_group"
            await send_or_edit_message(client, user_id,
                "🚀 **SCRAPER (Full Olish)**\n\n"
                "Guruh manzilini yuboring:\n"
                "• `@guruh_username`\n"
                "• `https://t.me/guruh_username`\n"
                "• Yopiq guruh: `https://t.me/+invite_kodi`\n\n"
                "⚠️ Guruh **nomi** emas, **@username** yoki **havola** yuboring!\n"
                "User akkauntingiz guruhda bo'lishi kerak.",
                reply_markup=cancel_menu()
            )
            
        elif text == "🔍 Guruh Qidirish":
            user_states[user_id] = "search_wait_keyword"
            await send_or_edit_message(client, user_id,
                "🔍 **GURUH QIDIRISH**\n\nQaysi mavzuda guruh izlayapsiz? Kalit so'zni yozing:\n(Masalan: `biznes`, `kino`)",
                reply_markup=cancel_menu()
            )
            
            
        elif text == "📨 Xabar yuborish" or text == "Xabar yuborish":
            file_path = get_user_file(user_id)
            if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                await send_or_edit_message(client, user_id,
                    "❌ Bazangiz bo'sh. Avval `🚀 Scraper` orqali foydalanuvchi yig'ing.",
                    reply_markup=main_menu()
                )
                return
            with open(file_path, "r", encoding="utf-8") as f:
                count = sum(1 for line in f if line.strip())
            user_states[user_id] = "broadcast_wait_text"
            await send_or_edit_message(client, user_id,
                f"📨 **XABAR YUBORISH**\n\n"
                f"Bazangizda **{count}** ta foydalanuvchi bor.\n\n"
                "Endi yuboriladigan xabar matnini yozing:\n"
                "_(Spamdan himoya uchun har bir xabar orasida 3 soniya pauza qo'yiladi)_",
                reply_markup=cancel_menu()
            )

        elif text == "📁 Yig'ilgan userlar":
            usernames = load_user_database(user_id)
            if usernames:
                await send_or_edit_message(client, user_id,
                    f"📁 Bazangizda **{len(usernames)}** ta user bor.",
                    reply_markup=database_menu(),
                )
                show_paginated_users(client, user_id, usernames)
            else:
                await send_or_edit_message(client, user_id, "❌ Hozircha bazangiz bo'sh. Avval `🚀 Scraper` orqali user yig'ing.")
        else:
            await send_or_edit_message(client, user_id, "Iltimos, tugmalardan birini tanlang.", reply_markup=main_menu())

    # ----- SCRAPER (FULL OLISH) -----
    elif state == "scrape_wait_group":
        group_input = text
        try:
            user_client = get_user_client_started(user_id)
            chat_id, chat_title = resolve_chat_id(user_client, text)
            scraper_selections[user_id] = {"group": group_input, "chat_id": chat_id, "chat_title": chat_title}
            user_states[user_id] = "scrape_wait_filter"
            await send_or_edit_message(client, user_id,
                f"✅ Guruh qabul qilindi: **{chat_title}**\n\n"
                "Endi scraping usulini tanlang:",
                reply_markup=scraper_filter_menu(),
            )
        except Exception as e:
            await send_or_edit_message(client, user_id, explain_telegram_error(e), reply_markup=main_menu())
            user_states[user_id] = "menu"

    elif state == "scrape_wait_filter":
        if text not in SCRAPER_FILTERS:
            await send_or_edit_message(client, user_id, "Iltimos, filtr tugmalaridan birini tanlang.", reply_markup=scraper_filter_menu())
            return

        selection = scraper_selections.get(user_id)
        if not selection:
            await send_or_edit_message(client, user_id, "❌ Xatolik. Qayta boshlang.", reply_markup=main_menu())
            user_states[user_id] = "menu"
            return

        filter_type = text
        
        if filter_type == "📊 Xabarlar orqali (Sekin)":
            user_states[user_id] = "scrape_wait_message_count"
            await send_or_edit_message(client, user_id,
                "📊 **XABARLAR SONI**\n\n"
                "Nechta xabarni o'qishni xohlaysiz?\n"
                "• Masalan: `1000`, `10000`, `1000000`\n\n"
                "⚠️ Maksimal: **5,000,000** ta xabar",
                reply_markup=cancel_menu(),
            )
        else:
            ok, current = acquire_task(user_id, "scrape")
            if not ok:
                await send_or_edit_message(client, user_id, active_task_message(current), reply_markup=main_menu())
                user_states[user_id] = "menu"
                return

            await send_or_edit_message(client, user_id,
                "⏳ Userlar yig'ilmoqda — bu biroz vaqt olishi mumkin.",
                reply_markup=main_menu(),
            )
            user_states[user_id] = "menu"

            asyncio.create_task(scrape_task(user_id, selection["group"], filter_type))
            scraper_selections.pop(user_id, None)

    elif state == "scrape_wait_message_count":
        try:
            message_count = int(text.replace(",", "").replace(" ", ""))
        except ValueError:
            await send_or_edit_message(client, user_id, "❌ Iltimos, raqam kiriting. Masalan: `1000`", reply_markup=cancel_menu())
            return

        if message_count < 1:
            await send_or_edit_message(client, user_id, "❌ Kamida 1 ta xabar kiritishingiz kerak.", reply_markup=cancel_menu())
            return

        if message_count > 5000000:
            await send_or_edit_message(client, user_id, "❌ Maksimal 5,000,000 ta xabar kiritish mumkin.", reply_markup=cancel_menu())
            return

        selection = scraper_selections.get(user_id)
        if not selection:
            await send_or_edit_message(client, user_id, "❌ Xatolik. Qayta boshlang.", reply_markup=main_menu())
            user_states[user_id] = "menu"
            return

        ok, current = acquire_task(user_id, "scrape")
        if not ok:
            await send_or_edit_message(client, user_id, active_task_message(current), reply_markup=main_menu())
            user_states[user_id] = "menu"
            return

        await send_or_edit_message(client, user_id,
            f"⏳ {message_count:,} ta xabar o'qilmoqda — bu biroz vaqt olishi mumkin.",
            reply_markup=main_menu(),
        )
        user_states[user_id] = "menu"

        asyncio.create_task(scrape_task(user_id, selection["group"], "📊 Xabarlar orqali (Sekin)", message_count))
        scraper_selections.pop(user_id, None)

    # ----- GURUH QIDIRISH (GLOBAL SEARCH) -----
    elif state == "search_wait_keyword":
        keyword = text
        ok, current = acquire_task(user_id, "search")
        if not ok:
            await send_or_edit_message(client, user_id, active_task_message(current), reply_markup=main_menu())
            user_states[user_id] = "menu"
            return

        await send_or_edit_message(client, user_id,
            f"⏳ '{keyword}' so'zi bo'yicha Telegram global tarmog'idan guruhlar axtarilmoqda..."
        )

        try:
            user_client = await get_user_client_started(user_id)
            result = await user_client.invoke(functions.contacts.Search(q=keyword, limit=20))

            found_chats = []
            for chat in result.chats:
                if getattr(chat, "username", None):
                    found_chats.append(f"📌 @{chat.username} | {chat.title}")

            if found_chats:
                res_text = "🔎 **Topilgan guruhlar:**\n\n" + "\n".join(found_chats)
                await send_or_edit_message(client, user_id, res_text, reply_markup=main_menu())
            else:
                await send_or_edit_message(client, user_id, "❌ Hech qanday guruh topilmadi.", reply_markup=main_menu())
        except Exception as e:
            await send_or_edit_message(client, user_id, f"❌ Qidiruvda xatolik: {e}", reply_markup=main_menu())
        finally:
            release_task(user_id, "search")

        user_states[user_id] = "menu"

    # ----- XABAR YUBORISH (BROADCAST) -----
    elif state == "broadcast_wait_text":
        msg_text = text
        file_path = get_user_file(user_id)
        user_states[user_id] = "menu"

        with open(file_path, "r", encoding="utf-8") as f:
            usernames = [line.strip() for line in f if line.strip()]

        if not usernames:
            await send_or_edit_message(client, user_id, "❌ Bazada foydalanuvchi yo'q.", reply_markup=main_menu())
            return

        ok, current = acquire_task(user_id, "broadcast")
        if not ok:
            await send_or_edit_message(client, user_id, active_task_message(current), reply_markup=main_menu())
            return

        await send_or_edit_message(client, user_id,
            f"⏳ **{len(usernames)}** ta foydalanuvchiga xabar yuborish boshlandi...\n"
            "Jarayon fonda davom etadi, natija alohida xabar qilib yuboriladi.",
            reply_markup=main_menu(),
        )

        asyncio.create_task(broadcast_task(user_id, usernames, msg_text))



@bot_app.on_callback_query(filters.regex("^pg:"))
def pagination_callback(client, callback_query):
    user_id = callback_query.from_user.id
    action = callback_query.data.split(":")[1]

    now = time.time()
    with tasks_lock:
        last_click = pagination_cooldown.get(user_id, 0)
        if now - last_click < PAGINATION_COOLDOWN:
            callback_query.answer("Juda tez bosyapsiz. Biroz kuting.")
            return
        pagination_cooldown[user_id] = now

    pag = user_pagination.get(user_id)
    if not pag:
        callback_query.answer("Ro'yxat topilmadi. Qayta oching.", show_alert=True)
        return

    usernames = pag["usernames"]
    page = pag["page"]
    total = len(usernames)
    total_pages = get_total_pages(total)

    if action == "close":
        user_pagination.pop(user_id, None)
        callback_query.message.delete()
        callback_query.answer("Yopildi")
        return

    if action == "prev" and page > 0:
        page -= 1
    elif action == "next" and page < total_pages - 1:
        page += 1
    else:
        callback_query.answer()
        return

    pag["page"] = page
    chunk, start_num, end_num = get_page_slice(usernames, page)
    text = format_user_batch(total, chunk, start_num, end_num)
    keyboard = build_nav_keyboard(page, total)

    callback_query.message.edit_text(text, reply_markup=keyboard)
    callback_query.answer()


def reset_user_session():
    for name in (
        "user_session.session",
        "user_session.session-journal",
        "empire_bot_session.session",
        "empire_bot_session.session-journal",
    ):
        path = os.path.join(BASE_DIR, name)
        if os.path.exists(path):
            try:
                os.remove(path)
            except PermissionError:
                print(f"⚠️ {name} hozir band. Botni to'xtatib, qo'lda o'chiring.")


async def run_bot():
    global bot_app
    # Client shu yerda yaratiladi — asyncio.run() loop ichida, Windows uchun xavfsiz
    bot_app = Client(
        "empire_bot_session",
        api_id=config["API_ID"],
        api_hash=config["API_HASH"],
        bot_token=config["BOT_TOKEN"],
        workdir=BASE_DIR,
        in_memory=True,
    )
    print("🚀 Botni ishga tushirish...")
    try:
        await bot_app.start()
        print("✅ Bot muvaffaqiyatli ishga tushdi!")
    except FloodWait as e:
        print(f"\n⚠️ FloodWait: {e.value} sekund kutish kerak...")
        await asyncio.sleep(e.value)
        await bot_app.start()
    except UserDeactivated:
        print("\n⚠️ Bot sessiyasi yaroqsiz. Eski sessiya o'chirilmoqda...")
        try:
            await bot_app.stop()
        except Exception:
            pass
        reset_user_session()
        await bot_app.start()
    except Exception as e:
        print(f"❌ Bot ishga tushirishda xatolik: {e}")
        raise

    try:
        await idle()
    finally:
        try:
            await bot_app.stop()
        except Exception:
            pass


if __name__ == "__main__":
    print("====================================")
    print(" EMPIRE BOT SERVER ISHGA TUSHIRILDI ")
    print("====================================")
    print(f"📁 Working directory: {BASE_DIR}")
    print(f"🔑 API_ID: {config.get('API_ID', 'NOT SET')}")
    print(f"🔑 API_HASH: {config.get('API_HASH', 'NOT SET')[:10]}..." if config.get('API_HASH') else "🔑 API_HASH: NOT SET")
    print(f"🤖 BOT_TOKEN: {config.get('BOT_TOKEN', 'NOT SET')[:20]}..." if config.get('BOT_TOKEN') else "🤖 BOT_TOKEN: NOT SET")
    print(f"👥 Admin IDs: {config.get('ADMIN_IDS', 'NOT SET')}")
    print(f"👥 Second Admin IDs: {config.get('SECOND_ADMIN_IDS', 'NOT SET')}")
    print(f"📊 logged_in_users initialized: {logged_in_users}")
    try:
        asyncio.run(run_bot())
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        import traceback
        traceback.print_exc()
