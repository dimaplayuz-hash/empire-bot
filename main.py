import os
import re
import time
import json
import asyncio
import threading
import sys
import shutil
import requests

# Windows compatibility fix for asyncio and Pyrogram
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from pyrogram import Client, filters, idle, StopPropagation, ContinuePropagation
from pyrogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    Message,
    ReplyKeyboardRemove,
)
try:
    from pyrogram.types import LabeledPrice
except ImportError:
    LabeledPrice = None  # Eski Pyrogram versiyalarida yo'q

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
from pyrogram import raw
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
        cfg = {"API_ID": int(api_id), "API_HASH": api_hash, "BOT_TOKEN": bot_token}
        # Admin ID'larini ham o'qish
        super_admin = os.getenv("SUPER_ADMIN_ID")
        second_admin = os.getenv("SECOND_ADMIN_ID")
        admin_ids_raw = os.getenv("ADMIN_IDS")
        if super_admin:
            cfg["SUPER_ADMIN_ID"] = int(super_admin)
        if second_admin:
            cfg["SECOND_ADMIN_ID"] = int(second_admin)
        if admin_ids_raw:
            try:
                import json as _json
                cfg["ADMIN_IDS"] = _json.loads(admin_ids_raw)
            except:
                cfg["ADMIN_IDS"] = [int(x.strip()) for x in admin_ids_raw.split(",") if x.strip().isdigit()]
        return cfg

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
            "BOT_TOKEN": token,
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
        return config
    else:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)


config = load_config()

# 1. BOT KLIYENTI (Tugmalar va boshqaruv uchun)
bot_app = Client(
    "empire_bot_session",
    api_id=config["API_ID"],
    api_hash=config["API_HASH"],
    bot_token=config["BOT_TOKEN"],
    workdir=BASE_DIR,
    in_memory=True,
)


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
        if username.lower() not in (
            "joinchat",
            "addstickers",
            "share",
            "proxy",
            "socks",
        ):
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
    if err.startswith("❌"):
        return err
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
temp_add_users = {}
temp_broadcast_count = {}
active_tasks = {}
stop_flags = {}
last_commands = {}
pagination_cooldown = {}
tasks_lock = threading.Lock()
COMMAND_COOLDOWN = 2.0  # 2 soniya cooldown
PAGINATION_COOLDOWN = 0.8
PAGINATION_SIZE = 50
DATA_DIR = os.path.join(BASE_DIR, "data")
DATABASE_DIR = os.path.join(DATA_DIR, "database")
SESSIONS_DIR = os.path.join(DATA_DIR, "sessions")
os.makedirs(SESSIONS_DIR, exist_ok=True)
os.makedirs(DATABASE_DIR, exist_ok=True)

# ================= SUBSCRIPTION TIZIMI =================
SUBSCRIPTIONS_FILE = os.path.join(DATA_DIR, "subscriptions.json")
SUBSCRIPTION_PRICE_STARS = 100
SUBSCRIPTION_DAYS = 30

def load_subscriptions():
    if not os.path.exists(SUBSCRIPTIONS_FILE):
        return {}
    try:
        with open(SUBSCRIPTIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_subscriptions(subs):
    with open(SUBSCRIPTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(subs, f, indent=4)

STATS_FILE = os.path.join(DATA_DIR, "stats.json")

def load_stats():
    if not os.path.exists(STATS_FILE):
        return {"total_income": 0, "payments": [], "expired_subs": 0}
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"total_income": 0, "payments": [], "expired_subs": 0}

def save_stats(stats):
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=4)


def bot_api_request(method, **payload):
    url = f"https://api.telegram.org/bot{config['BOT_TOKEN']}/{method}"
    try:
        resp = requests.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Bot API {method} xato: {e}")
        return {"ok": False, "description": str(e)}


async def prompt_subscription_payment(user_id):
    """Pyrogram send_invoice qo'llab-quvvatlamaydi — Bot API orqali invoice yuboriladi."""
    result = bot_api_request(
        "sendInvoice",
        chat_id=user_id,
        title="Premium Obuna",
        description=(
            f"Botning barcha funksiyalaridan {SUBSCRIPTION_DAYS} kun "
            "to'liq foydalanish imkoniyati."
        ),
        payload="monthly_sub",
        provider_token="",
        currency="XTR",
        prices=[{"label": "Oylik obuna", "amount": SUBSCRIPTION_PRICE_STARS}],
    )
    if not result.get("ok"):
        error_desc = result.get("description", "Noma'lum xato")
        await bot_app.send_message(
            user_id,
            "❌ To'lov hisob-fakturasini yuborib bo'lmadi. Keyinroq /start bosing.\n\n"
            f"`{error_desc}`",
        )
        return False

    await bot_app.send_message(
        chat_id=user_id,
        text="💬 **Stars orqali to'lashda muammo bo'lsa**, admin bilan bog'lanishingiz mumkin:",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("📞 Bog'lanish", callback_data="contact_click_track")]]
        ),
    )
    return True


LOGIN_FLOW_STATES = {
    "login_phone",
    "login_code",
    "login_password",
    "login_upload",
}


async def cleanup_login_attempt(user_id):
    """Login jarayonidagi vaqtinchalik ma'lumotlarni tozalash."""
    if user_id not in login_data:
        return
    try:
        data = login_data[user_id]
        client_obj = data.get("client")
        if client_obj and client_obj.is_connected:
            await client_obj.disconnect()
    except Exception:
        pass
    login_data.pop(user_id, None)


async def require_subscription_before_login(message, user_id):
    """Obunasiz foydalanuvchini login o'rniga to'lovga yo'naltirish."""
    await cleanup_login_attempt(user_id)
    user_states[user_id] = "wait_payment"
    await prompt_subscription_payment(user_id)
    await message.reply_text(
        "💳 **Obuna to'lovi talab qilinadi.**\n\n"
        "Botdan foydalanish uchun avval to'lovni amalga oshiring. "
        "Admin tasdiqlagach /start bosing va login qiling.",
        reply_markup=ReplyKeyboardRemove(),
    )


async def show_post_auth_screen(client, message, user_id):
    """Login muvaffaqiyatidan keyin obuna yoki asosiy menyu."""
    if not is_subscribed(user_id):
        await require_subscription_before_login(message, user_id)
        return

    user_states[user_id] = "menu"
    logged_in_users.add(user_id)
    first_name = message.from_user.first_name or "Mijoz"
    await message.reply_text(
        f"✅ **Muvaffaqiyatli login bo'ldi!**\n\n"
        f"👋 Assalomu alaykum, {first_name}!\n\n"
        f"🎭 **VENTO** boshqaruv paneliga xush kelibsiz!\n\n"
        f"📌 **Mavjud xizmatlar:**\n"
        f"• 🚀 Scraper — guruhlardan user yig'ish\n"
        f"• 📨 Xabar yuborish — bazadagi userlarga DM\n"
        f"• 🔍 Guruh qidirish — kalit so'z bo'yicha qidiruv\n\n"
        f"Quyidagi tugmalardan birini tanlang:",
        reply_markup=main_menu(),
    )


async def begin_login_flow(message, user_id):
    if not is_subscribed(user_id):
        await require_subscription_before_login(message, user_id)
        return

    user_states[user_id] = "login_phone"
    markup = ReplyKeyboardMarkup(
        [
            [KeyboardButton("📞 Telefon raqamini yuborish", request_contact=True)],
            [KeyboardButton("❌ Bekor qilish")],
        ],
        resize_keyboard=True,
    )
    await message.reply_text(
        "🔌 **Sessiya ulash jarayoni boshlandi.**\n\n"
        "Iltimos, Telegram akkauntingiz telefon raqamini kiriting (masalan: `+998901234567` formatida) "
        "yoki pastdagi tugma orqali yuboring:",
        reply_markup=markup,
    )


def is_subscribed(user_id):
    if is_admin(user_id) or is_super_admin(user_id) or is_second_admin(user_id):
        return True
        
    VIP_FILE = os.path.join(DATA_DIR, "vips.json")
    if os.path.exists(VIP_FILE):
        try:
            with open(VIP_FILE, "r", encoding="utf-8") as f:
                vips = json.load(f)
                # Eski format (list)
                if isinstance(vips, list):
                    if user_id in vips:
                        return True
                # Yangi format (dict)
                elif isinstance(vips, dict):
                    str_id = str(user_id)
                    if str_id in vips:
                        vip_data = vips[str_id]
                        # Muddati bormi tekshirish
                        if isinstance(vip_data, dict) and vip_data.get("expiry"):
                            if time.time() > vip_data["expiry"]:
                                return False  # Muddati tugagan
                        return True
        except:
            pass
        
    subs = load_subscriptions()
    str_id = str(user_id)
    if str_id not in subs:
        return False
        
    expiry = subs[str_id].get("expiry", 0)
    if time.time() > expiry:
        return False
    return True

async def subscription_checker():
    while True:
        try:
            subs = load_subscriptions()
            now = time.time()
            changed = False
            
            for user_id_str, info in list(subs.items()):
                expiry = info.get("expiry", 0)
                warned = info.get("warned", False)
                
                # Check 1 day warning (86400 seconds)
                if not warned and 0 < expiry - now <= 86400:
                    try:
                        await bot_app.send_message(
                            int(user_id_str),
                            "⚠️ **Diqqat!**\n\nSizning botdan foydalanish obunangiz tugashiga 1 kun qoldi.\n"
                            "Obunangiz tugagach botdan foydalana olmaysiz."
                        )
                        subs[user_id_str]["warned"] = True
                        changed = True
                    except:
                        pass
                        
                # Check expiry
                if expiry > 0 and now >= expiry:
                    try:
                        await bot_app.send_message(
                            int(user_id_str),
                            "❌ **Obunangiz tugadi!**\n\nBotdan foydalanishni davom ettirish uchun obunani yangilashingiz kerak."
                        )
                    except:
                        pass
                    del subs[user_id_str]
                    changed = True
                    
                    stats = load_stats()
                    stats["expired_subs"] = stats.get("expired_subs", 0) + 1
                    save_stats(stats)
                    
            if changed:
                save_subscriptions(subs)
                
        except Exception as e:
            pass
            
        await asyncio.sleep(3600)  # Check every hour

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

        session_name = os.path.join("data", "sessions", f"user_{user_id}")
        client = Client(
            session_name,
            api_id=config["API_ID"],
            api_hash=config["API_HASH"],
            workdir=BASE_DIR,
        )
        user_clients[user_id] = client
        return client


async def get_user_client_started(user_id):
    """User uchun client olish va start qilish. Sessiya muddati o'tgan bo'lsa, tozalaydi."""
    client = get_user_client(user_id)
    if not client.is_connected:
        try:
            await client.connect()
            # Sessiya haqiqiy ishlayotganini tekshirish
            await client.get_me()
        except Exception as e:
            print(f"❌ Sessiya yuklashda xatolik (User: {user_id}): {e}")
            try:
                await client.disconnect()
            except:
                pass
            with clients_lock:
                user_clients.pop(user_id, None)
            
            session_path = os.path.join(SESSIONS_DIR, f"user_{user_id}.session")
            if os.path.exists(session_path):
                try:
                    os.remove(session_path)
                except:
                    pass
            
            logged_in_users.discard(user_id)
            if is_subscribed(user_id):
                user_states[user_id] = "login_phone"
                raise ValueError(
                    "❌ **Sessiyangiz muddati tugagan yoki faolsizlantirilgan!**\n\n"
                    "Sessiya o'chirildi. Iltimos, /start buyrug'ini berib qaytadan login qiling."
                )
            user_states[user_id] = "wait_payment"
            raise ValueError(
                "❌ **Sessiyangiz muddati tugagan va obunangiz yo'q!**\n\n"
                "Sessiya o'chirildi. /start bosing va obunani yangilang."
            )
    return client


def is_user_logged_in(user_id):
    """User login qilganmi tekshirish"""
    # Xotiradagi emas, session fayl borligiga qarab tekshiramiz
    session_path = os.path.join(SESSIONS_DIR, f"user_{user_id}.session")
    if os.path.exists(session_path):
        logged_in_users.add(user_id)
        return True
    return False


# ================= YORIQNOMA TUGMALARI =================
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def api_id_guide_keyboard():
    """API_ID yoriqnoma tugmasi"""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📖 Yo'riqnoma", callback_data="guide_api_id"),
                InlineKeyboardButton("🖼 Masalan", callback_data="show_screenshots"),
            ]
        ]
    )


def api_hash_guide_keyboard():
    """API_HASH yoriqnoma tugmasi"""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📖 Yo'riqnoma", callback_data="guide_api_hash"),
                InlineKeyboardButton("🖼 Masalan", callback_data="show_screenshots"),
            ]
        ]
    )


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
        "   - App title: Users (yoki ixtiyoriy 5+ harfli nom)\n"
        "   - Short name: users (faqat inglizcha kichik harf va raqamlar)\n"
        "   - Platform: Android\n"
        "   _(yoki boshqacha yozishingiz ham mumkin, muhimi talabga javob bersa bo'ldi)_\n\n"
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


@bot_app.on_callback_query(filters.regex("^show_screenshots$"))
async def show_screenshots_callback(client, callback):
    """Skrinshotlarni yuborish"""
    await callback.answer(
        "Skrinshotlar yuborilmoqda, biroz kuting...", show_alert=False
    )

    from pyrogram.types import InputMediaPhoto

    media_group = [
        InputMediaPhoto(
            os.path.join(BASE_DIR, "assets", "step1.png"),
            caption="1. my.telegram.org ga kirib telefon raqamni kiritasiz",
        ),
        InputMediaPhoto(
            os.path.join(BASE_DIR, "assets", "step2.png"),
            caption="2. Telegramdan kelgan kodni kiritasiz",
        ),
        InputMediaPhoto(
            os.path.join(BASE_DIR, "assets", "step3.png"),
            caption="3. 'API development tools' bo'limiga kirasiz",
        ),
        InputMediaPhoto(
            os.path.join(BASE_DIR, "assets", "step4.png"),
            caption="4. Application ma'lumotlarini to'ldirasiz",
        ),
        InputMediaPhoto(
            os.path.join(BASE_DIR, "assets", "step5.png"),
            caption="5. API_ID va API_HASH larni nusxalab olasiz",
        ),
    ]

    try:
        await client.send_media_group(callback.message.chat.id, media_group)
    except Exception as e:
        await callback.message.reply_text(f"❌ Rasmlarni yuborishda xatolik: {e}")


# ================= ADMINLIK TIZIMI =================
ADMINS_FILE = os.path.join(DATA_DIR, "admins.json")

def load_admins():
    if not os.path.exists(ADMINS_FILE):
        return [8513957498, 8348307850]
    try:
        with open(ADMINS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return [8513957498, 8348307850]

def save_admins(admins_list):
    with open(ADMINS_FILE, "w", encoding="utf-8") as f:
        json.dump(list(set(admins_list)), f, indent=4)

BANNED_FILE = os.path.join(DATA_DIR, "banned.json")

def load_banned():
    if not os.path.exists(BANNED_FILE):
        return []
    try:
        with open(BANNED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_banned(banned_list):
    with open(BANNED_FILE, "w", encoding="utf-8") as f:
        json.dump(list(set(banned_list)), f, indent=4)

def is_banned(user_id):
    return user_id in load_banned()


SUPER_ADMIN_ID = config.get("SUPER_ADMIN_ID", 8513957498)
SECOND_ADMIN_ID = config.get("SECOND_ADMIN_ID", 8348307850)

# Bot offline holati
bot_offline = False

def is_admin(user_id):
    """Foydalanuvchi admin ekanligini tekshiradi"""
    return user_id in load_admins() or user_id == SUPER_ADMIN_ID

def is_super_admin(user_id):
    """Foydalanuvchi bosh admin ekanligini tekshiradi"""
    return user_id == SUPER_ADMIN_ID

def is_second_admin(user_id):
    """Foydalanuvchi ikkinchi admin ekanligini tekshiradi"""
    return user_id == SECOND_ADMIN_ID


# ================= XABARLARNI KUZATISH =================
last_bot_messages = {}  # {user_id: {"message_id": int, "is_editable": bool}}


async def send_or_edit_message(
    client, target_id, text, reply_markup=None, force_new=False
):
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
        last_bot_messages[target_id] = {"message_id": msg.id, "is_editable": True}
        return msg
    except Exception as e:
        # Agar xabar yuborib bo'lmasa, oddiy reply_text ishlatamiz
        try:
            msg = await client.send_message(target_id, text, reply_markup=reply_markup)
            last_bot_messages[target_id] = {"message_id": msg.id, "is_editable": True}
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
            return (
                f"🚫 **Siz bloklangansiz!**\n\nSabab: {blocked_users[user_id]['reason']}\n\nAdmin bilan bog'laning.",
                True,
            )
        elif now < blocked_until:  # Temporary block
            remaining = int(blocked_until - now)
            return (
                f"⚠️ **Flood himoya!**\n\nSiz juda tez xabar yuboryapsiz.\n⏳ {remaining} soniya kuting.",
                True,
            )
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
            return (
                f"🚫 **PERMANENT BLOK!**\n\nSiz {MAX_WARNINGS} marta ogohlantirildingiz.\nEndi botdan foydalanish taqiqlandi.",
                True,
            )
        else:
            # Temporary block
            block_time = FLOOD_BLOCK_TIME * warnings  # Har safar ko'payadi
            blocked_users[user_id]["blocked_until"] = now + block_time
            flood_protection[user_id]["count"] = 0
            return (
                f"⚠️ **FLOOD HIMOYA FAOL!**\n\nSiz juda ko'p xabar yubordingiz.\n⏳ {block_time} soniya bloklandingiz.\n⚠️ Ogohlantirish: {warnings}/{MAX_WARNINGS}",
                True,
            )

    # Warning
    if flood_protection[user_id]["count"] >= FLOOD_THRESHOLD - 3:
        return (
            f"⚠️ **Ogohlantirish!**\n\nTez-tez xabar yubormang.\nAks holda bloklanishingiz mumkin.",
            False,
        )

    return None, False


MENU_BUTTONS = frozenset(
    {
        "⚡ Super Scraper",
        "📮 Smart Xabarnoma",
        "💾 Yig'ilgan Bazalar",
    }
)

DATABASE_BUTTONS = frozenset(
    {
        "➕ Yangi user(lar) qo'shish",
        "🗑️ Bazani tozalash",
        "🏠 Asosiy menyu",
    }
)

SCRAPER_FILTERS = frozenset(
    {
        "⚡ Avtomatik (Tez)",
        "📊 Xabarlar orqali (Sekin)",
        "🌸 Qizlar (Filtrlangan)",
        "👱‍♀️ Adminlar",
    }
)

TASK_LABELS = {
    "scrape": "⚡ Super Scraper",
    "broadcast": "📮 Smart Xabarnoma",
    "search": "🌐 Global Qidiruv",
    "utag": "🧠 Smart Yo'llanma",
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


async def cleanup_user_client(user_id):
    """Userning clientini xotiradan tozalaydi va ulanishni yopadi (Xotirani tejash uchun)"""
    with clients_lock:
        client = user_clients.pop(user_id, None)
    if client:
        try:
            if client.is_connected:
                await client.disconnect()
        except:
            pass

def release_task(user_id, task_name, cleanup=False):
    """Taskni bo'shatadi. cleanup=True bo'lsa clientni ham tozalaydi."""
    with tasks_lock:
        if active_tasks.get(user_id) == task_name:
            active_tasks.pop(user_id, None)
    stop_flags.pop(user_id, None)
    if cleanup:
        asyncio.create_task(cleanup_user_client(user_id))


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



import random
from datetime import datetime

def get_user_json_file(user_id):
    return os.path.join(DATABASE_DIR, f"users_{user_id}.json")

def migrate_database(user_id):
    txt_file = os.path.join(DATABASE_DIR, f"users_{user_id}.txt")
    json_file = get_user_json_file(user_id)
    if os.path.exists(txt_file) and not os.path.exists(json_file):
        with open(txt_file, "r", encoding="utf-8") as f:
            users = [line.strip() for line in f if line.strip()]
        if users:
            data = {
                "databases": {
                    "1000": {
                        "title": "Eski baza",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "users": users
                    }
                },
                "selected_db": "1000"
            }
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        try:
            os.remove(txt_file)
        except:
            pass

def get_all_databases(user_id):
    migrate_database(user_id)
    json_file = get_user_json_file(user_id)
    if not os.path.exists(json_file):
        return {}
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            return json.load(f).get("databases", {})
    except:
        return {}

def get_database(user_id, db_id):
    dbs = get_all_databases(user_id)
    return dbs.get(str(db_id), {})

def save_database(user_id, title, new_users, db_id=None):
    migrate_database(user_id)
    json_file = get_user_json_file(user_id)
    data = {"databases": {}, "selected_db": None}
    if os.path.exists(json_file):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            pass
    
    if not db_id:
        # Generate random 4-digit ID
        while True:
            db_id = str(random.randint(1000, 9999))
            if db_id not in data["databases"]:
                break
    else:
        db_id = str(db_id)
        
    existing_users = data["databases"].get(db_id, {}).get("users", [])
    updated_users = list(set(existing_users) | set(new_users))
    
    data["databases"][db_id] = {
        "title": title,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "users": updated_users
    }
    data["selected_db"] = db_id
    
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        
    return db_id

def clear_user_database(user_id, db_id=None):
    json_file = get_user_json_file(user_id)
    if not os.path.exists(json_file):
        return
        
    if db_id is None:
        # Clear all
        if os.path.exists(json_file):
            os.remove(json_file)
    else:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if str(db_id) in data["databases"]:
                del data["databases"][str(db_id)]
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except:
            pass

def load_user_database(user_id):
    migrate_database(user_id)
    json_file = get_user_json_file(user_id)
    if not os.path.exists(json_file):
        return []
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            selected = data.get("selected_db")
            if selected and selected in data.get("databases", {}):
                return data["databases"][selected].get("users", [])
            return []
    except:
        return []



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
    asyncio.create_task(client.send_message(target_id, text, reply_markup=keyboard))


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


async def scrape_task(
    target_id, raw_group, filter_type="⚡ Avtomatik (Tez)", message_count=None
):
    try:
        user_client = await get_user_client_started(target_id)
        chat_id, chat_title = await resolve_chat_id(user_client, raw_group)

        if filter_type == "📊 Xabarlar orqali (Sekin)":
            max_messages = message_count if message_count else 1000
            # Boshlang'ich xabar
            await bot_app.send_message(
                target_id,
                f"🔍 **{chat_title}** guruhidan xabarlar o'qilmoqda...\n📌 Filtr: {filter_type}\n\n⏳ {max_messages:,} ta xabar o'qiladi.",
            )

            scraped = set()
            msg_count = 0
            progress_interval = max(
                100, max_messages // 100
            )  # Dynamic progress reporting

            async for message in user_client.get_chat_history(
                chat_id, limit=max_messages
            ):
                if stop_flags.get(target_id):
                    break
                if (
                    message.from_user
                    and not message.from_user.is_bot
                    and message.from_user.username
                ):
                    scraped.add(f"@{message.from_user.username}")
                msg_count += 1
                if msg_count % progress_interval == 0:
                    # Progress update - edit qilish
                    try:
                        if target_id in last_bot_messages:
                            await bot_app.edit_message_text(
                                target_id,
                                last_bot_messages[target_id]["message_id"],
                                f"🔍 **{chat_title}** guruhidan xabarlar o'qilmoqda...\n📌 Filtr: {filter_type}\n\n⏳ {msg_count:,}/{max_messages:,} ta xabar o'qildi...",
                            )
                    except:
                        pass  # Edit qilib bo'lmadi, davom etamiz

        else:
            # Boshlang'ich xabar
            await bot_app.send_message(
                target_id,
                f"🔍 **{chat_title}** guruhidan userlar yig'ilmoqda...\n📌 Filtr: {filter_type}\n\n⏳ 0 ta user yig'ildi...",
            )

            scraped = set()
            member_count = 0
            progress_interval = 50  # Har 50 ta userdan keyin update

            async for member in user_client.get_chat_members(chat_id):
                if stop_flags.get(target_id):
                    break
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

                    if last_char == "a":
                        scraped.add(username)
                    else:
                        # 2. Tarkibida ayol ismlari bo'lganlar
                        female_keywords = [
                            "gul",
                            "niso",
                            "bibi",
                            "khan",
                            "xon",
                            "begim",
                            "oy",
                            "mariya",
                            "nigora",
                            "sevara",
                            "dilnoza",
                            "malika",
                            "zuhra",
                            "nargiza",
                            "kamola",
                            "mavjuda",
                            "shahnoza",
                            "aziza",
                            "fatima",
                            "zaynab",
                            "aisha",
                            "khadija",
                            "mukarram",
                            "makhsuma",
                            "zahra",
                            "ruziya",
                            "mubina",
                            "salima",
                            "habiba",
                            "jamila",
                            "latifa",
                            "nafisa",
                            "safiya",
                            "sumaya",
                            "ummu",
                            "aysha",
                            "fotima",
                            "hafsa",
                            "sawda",
                            "ruqayya",
                            "kulthum",
                            "aliya",
                            "amina",
                            "asfiya",
                            "baraka",
                            "bushra",
                            "dalia",
                            "eisha",
                            "fariha",
                            "ghada",
                            "haniya",
                            "imana",
                            "jana",
                            "kadija",
                            "laila",
                            "mahira",
                            "nadia",
                            "omar",
                            "parveen",
                            "qasira",
                            "raisa",
                            "sana",
                            "tahira",
                            "umara",
                            "wafa",
                            "yamila",
                            "zara",
                            "zoya",
                            "nur",
                            "noor",
                            "shams",
                            "hilal",
                            "badr",
                            "najma",
                            "sitar",
                            "anahita",
                            "anara",
                            "arzu",
                            "asal",
                            "barakat",
                            "bina",
                            "bonu",
                            "dila",
                            "dilbara",
                            "dildora",
                            "dilfuza",
                            "dilrabo",
                            "dilshoda",
                            "elina",
                            "eliza",
                            "emira",
                            "farangiz",
                            "farida",
                            "feruza",
                            "gavhar",
                            "gulandom",
                            "gulbahor",
                            "gulchehra",
                            "guldasta",
                            "gulira",
                            "gulnara",
                            "gulnoza",
                            "gulruhsora",
                            "gulshoda",
                            "gulsanam",
                            "gulzara",
                            "hadicha",
                            "hayola",
                            "hilola",
                            "humora",
                            "inobat",
                            "kamola",
                            "kumush",
                            "lola",
                            "malika",
                            "maftuna",
                            "makhsuma",
                            "mavjuda",
                            "mavzuna",
                            "mehriniso",
                            "mohira",
                            "mubina",
                            "mukarrama",
                            "muslima",
                            "nafisa",
                            "nargiza",
                            "nigora",
                            "niso",
                            "nodira",
                            "noila",
                            "nurida",
                            "nurjahan",
                            "nurkhon",
                            "nurliyo",
                            "nurshoda",
                            "nurzoda",
                            "parvina",
                            "rano",
                            "rakhima",
                            "ramina",
                            "ravshana",
                            "raykhona",
                            "roya",
                            "roziya",
                            "ruhida",
                            "ruhijon",
                            "ruziya",
                            "sabina",
                            "sadiya",
                            "safina",
                            "sahar",
                            "saliha",
                            "salima",
                            "samira",
                            "sana",
                            "sanobar",
                            "sarvinoz",
                            "sevinch",
                            "shahida",
                            "shahnoza",
                            "sharifa",
                            "shirin",
                            "shodiyona",
                            "shukrona",
                            "sitora",
                            "sumayya",
                            "surayyo",
                            "tabassum",
                            "tahira",
                            "tamina",
                            "tanzila",
                            "tarona",
                            "umida",
                        ]
                        if any(
                            keyword in username_lower for keyword in female_keywords
                        ):
                            scraped.add(username)

                member_count += 1
                if member_count % progress_interval == 0:
                    # Progress update - edit qilish
                    try:
                        if target_id in last_bot_messages:
                            await bot_app.edit_message_text(
                                target_id,
                                last_bot_messages[target_id]["message_id"],
                                f"🔍 **{chat_title}** guruhidan userlar yig'ilmoqda...\n📌 Filtr: {filter_type}\n\n⏳ {len(scraped)} ta user yig'ildi...",
                            )
                    except:
                        pass  # Edit qilib bo'lmadi, davom etamiz

        if not scraped:
            await bot_app.send_message(
                target_id,
                f"❌ **{chat_title}** guruhida filtr bo'yicha user topilmadi.",
            )
            return

        # We save this scrape session to a new database
        existing = []
        existing_set = set()
        new_count = len(scraped)
        all_users = [u for u in sorted(scraped)]
        db_id = save_database(target_id, chat_title, all_users)

        scraped_list = sorted(scraped, key=str.lower)
        await bot_app.send_message(
            target_id,
            f"✅ **{chat_title}** guruhidan **{len(scraped_list)}** ta user yig'ildi!\n"
            f"💾 Bazaga **{new_count}** ta yangi qo'shildi (jami: **{len(all_users)}**).",
        )
        show_paginated_users(bot_app, target_id, scraped_list)

    except Exception as e:
        await bot_app.send_message(target_id, explain_telegram_error(e))
    finally:
        release_task(target_id, "scrape", cleanup=True)


async def broadcast_task(target_id, recipients, body, auto_delete=False):
    try:
        user_client = await get_user_client_started(target_id)
        success = 0
        failed = 0
        total = len(recipients)
        
        last_edit_time = time.time()
        
        sent_messages_history = []

        await send_or_edit_message(
            bot_app,
            target_id,
            f"📤 **Xabar yuborish boshlandi...**\n\n"
            f"📊 Jami: **{total}** ta user\n"
            f"⏳ Jarayon davom etmoqda...",
        )

        for idx, username in enumerate(recipients):
            if stop_flags.get(target_id):
                break
            try:
                # Remove @ prefix if present for Pyrogram
                clean_username = username.lstrip('@')
                sent_msg = await user_client.send_message(clean_username, body)
                success += 1
                if sent_msg:
                    sent_messages_history.append({"chat_id": sent_msg.chat.id, "message_id": sent_msg.id})
            except FloodWait as e:
                await asyncio.sleep(e.value + 5)
                try:
                    sent_msg = await user_client.send_message(clean_username, body)
                    success += 1
                    if sent_msg:
                        sent_messages_history.append({"chat_id": sent_msg.chat.id, "message_id": sent_msg.id})
                except Exception:
                    failed += 1
            except (PeerIdInvalid, UserPrivacyRestricted, Exception) as e:
                failed += 1
                # Log the actual error for debugging
                print(f"❌ Failed to send to {username}: {type(e).__name__}: {e}")

            current_time = time.time()
            if current_time - last_edit_time >= 2.0 or (success + failed) == total:
                try:
                    if target_id in last_bot_messages:
                        progress = success + failed
                        percent = (progress / total) * 100
                        bar_len = 10
                        filled = int(percent / 10)
                        bar = "▓" * filled + "░" * (bar_len - filled)
                        
                        await bot_app.edit_message_text(
                            target_id,
                            last_bot_messages[target_id]["message_id"],
                            f"📤 **Xabar yuborilmoqda...**\n\n"
                            f"[{bar}] {percent:.1f}%\n"
                            f"📊 Yuborilgan userlar: **{progress}/{total}**\n\n"
                            f"✅ Muvaffaqiyatli: **{success}** ta\n"
                            f"❌ Yuborilmadi: **{failed}** ta",
                        )
                        last_edit_time = current_time
                except Exception:
                    pass

            await asyncio.sleep(3)

        # Save history to file
        history_file = os.path.join(DATA_DIR, f"broadcast_history_{target_id}.json")
        try:
            with open(history_file, "w", encoding="utf-8") as f:
                json.dump(sent_messages_history, f)
        except Exception:
            pass

        markup = None
        if sent_messages_history:
            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑️ Barcha yuborilganlarni o'chirish", callback_data="delete_broadcast")]
            ])

        await bot_app.send_message(
            target_id,
            f"✅ **Xabar yuborish tugadi!**\n\n"
            f"📤 Yuborildi: **{success}** ta\n"
            f"❌ Yuborilmadi: **{failed}** ta\n"
            f"📊 Jami: **{total}** ta\n\n"
            f"💡 *Agar xabarlarni barchadan o'chirib tashlamoqchi bo'lsangiz, pastdagi tugmani bosing.*",
            reply_markup=markup
        )
        
        # O'zgarishsiz qoldirish uchun main_menu ham yuboramiz
        await send_or_edit_message(bot_app, target_id, "🏠 Asosiy menyu", reply_markup=main_menu())
        
    except Exception as e:
        await send_or_edit_message(
            bot_app, target_id, explain_telegram_error(e), reply_markup=main_menu()
        )
    finally:
        release_task(target_id, "broadcast", cleanup=True)


# ================= MENYU =================
def main_menu():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("⚡ Super Scraper")],
            [KeyboardButton("📮 Smart Xabarnoma"), KeyboardButton("💾 Yig'ilgan Bazalar")],
        ],
        resize_keyboard=True,
        placeholder="Bo'limni tanlang...",
    )


def cancel_menu():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("❌ Bekor qilish")]], resize_keyboard=True
    )

def broadcast_count_menu():
    return ReplyKeyboardMarkup(
        [[KeyboardButton("Barchasiga yuborish")], [KeyboardButton("❌ Bekor qilish")]],
        resize_keyboard=True,
    )


def database_menu():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("➕ Yangi user(lar) qo'shish")],
            [KeyboardButton("🗑️ Bazani tozalash"), KeyboardButton("🏠 Asosiy menyu")]
        ],
        resize_keyboard=True,
        placeholder="Baza bo'limi...",
    )


def confirm_delete_menu():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("✅ Ha, tozalash"), KeyboardButton("❌ Bekor qilish")],
        ],
        resize_keyboard=True,
    )


def scraper_filter_menu():
    return ReplyKeyboardMarkup(
        [
            [
                KeyboardButton("⚡ Avtomatik (Tez)"),
                KeyboardButton("📊 Xabarlar orqali (Sekin)"),
            ],
            [KeyboardButton("🌸 Qizlar (Filtrlangan)"), KeyboardButton("👱‍♂️ Adminlar")],
            [KeyboardButton("❌ Bekor qilish")],
        ],
        resize_keyboard=True,
        placeholder="Filtrni tanlang...",
    )


# ================= U-TAG VAZIFASI =================
async def utag_task(user_id, chat_identifier, text):
    try:
        user_client = await get_user_client_started(user_id)
        
        # Odamlarni to'plash
        await bot_app.send_message(user_id, "⏳ Guruh a'zolari to'planmoqda...")
        
        # chat_identifier orqali guruhni topish (agar matn bo'lsa, API orqali topadi va cache muammosi bo'lmaydi)
        try:
            if isinstance(chat_identifier, str):
                chat_id, _ = await resolve_chat_id(user_client, chat_identifier)
            else:
                chat_id = chat_identifier
                await user_client.get_chat(chat_id)
        except (PeerIdInvalid, ValueError) as e:
            if isinstance(e, ValueError) and "Peer id invalid" not in str(e).lower():
                raise e
            async for _ in user_client.get_dialogs(limit=100):
                pass
            chat_id = chat_identifier
            await user_client.get_chat(chat_id)
            
        members = []
        async for member in user_client.get_chat_members(chat_id):
            if stop_flags.get(user_id):
                break
            if not member.user.is_bot and not member.user.is_deleted:
                members.append(member.user)
                
        # Xabar yuborish
        count = 0
        for member in members:
            if stop_flags.get(user_id):
                break
                
            mention = f"[{member.first_name}](tg://user?id={member.id})"
            msg = f"{mention}\n{text}" if text else mention
            
            try:
                await user_client.send_message(chat_id, msg)
                count += 1
                await asyncio.sleep(1.5)
            except FloodWait as e:
                await asyncio.sleep(e.value + 2)
            except Exception as e:
                pass
                
        await bot_app.send_message(user_id, f"✅ U-Tag yakunlandi! ({count} ta a'zo tag qilindi)")
    except Exception as e:
        await bot_app.send_message(user_id, f"❌ U-Tag xatosi: {e}")
    finally:
        release_task(user_id, "utag", cleanup=True)

# ================= PAYMENT HANDLERLAR =================
# Pyrogram to'lov handlerlarini to'g'ridan-to'g'ri qo'llab-quvvatlamaydi.
# Bot API va raw update orqali ishlaydi.


@bot_app.on_message(filters.all, group=-1)
async def ban_filter(client, message):
    if message.from_user and is_banned(message.from_user.id):
        raise StopPropagation
    raise ContinuePropagation

@bot_app.on_callback_query(group=-1)
async def ban_callback_filter(client, callback_query):
    if callback_query.from_user and is_banned(callback_query.from_user.id):
        await callback_query.answer("❌ Siz botdan ban qilingansiz.", show_alert=True)
        raise StopPropagation
    raise ContinuePropagation

@bot_app.on_raw_update()
async def handle_payment_updates(client, update, users, chats):
    try:
        if isinstance(update, raw.types.UpdateBotPrecheckoutQuery):
            payload = (
                update.payload.decode()
                if isinstance(update.payload, bytes)
                else str(update.payload)
            )
            ok = payload == "monthly_sub" and update.currency == "XTR"
            bot_api_request(
                "answerPreCheckoutQuery",
                pre_checkout_query_id=update.query_id,
                ok=ok,
                error_message="" if ok else "Noto'g'ri to'lov.",
            )
            return

        message = None
        if isinstance(update, raw.types.UpdateNewMessage):
            message = update.message
        elif isinstance(update, raw.types.UpdateNewChannelMessage):
            message = update.message

        if not message or getattr(message, "action", None) is None:
            return

        action = message.action
        if not isinstance(action, raw.types.MessageActionPaymentSentMe):
            return

        payload = (
            action.payload.decode()
            if isinstance(action.payload, bytes)
            else str(action.payload)
        )
        if payload != "monthly_sub":
            return

        user_id = None
        if message.peer_id and isinstance(message.peer_id, raw.types.PeerUser):
            user_id = message.peer_id.user_id
        if not user_id:
            return

        user = users.get(user_id)
        first_name = getattr(user, "first_name", None) or "Foydalanuvchi"
        charge_id = action.charge.id if action.charge else ""
        amount = action.total_amount

        pendings_file = os.path.join(DATA_DIR, "pending_payments.json")
        pendings = {}
        if os.path.exists(pendings_file):
            try:
                with open(pendings_file, "r", encoding="utf-8") as f:
                    pendings = json.load(f)
            except Exception:
                pass

        user_id_str = str(user_id)
        pendings[user_id_str] = {
            "amount": amount,
            "first_name": first_name,
            "charge_id": charge_id,
            "time": time.time(),
        }
        with open(pendings_file, "w", encoding="utf-8") as f:
            json.dump(pendings, f, indent=4)

        user_states[user_id] = "wait_payment"
        await bot_app.send_message(
            user_id,
            "✅ **To'lovingiz qabul qilindi!**\n\n"
            "Admin tasdiqlashini kuting. Tasdiqlangach /start bosing.",
        )

        admin_ids = list(set(load_admins() + [SUPER_ADMIN_ID, SECOND_ADMIN_ID]))
        markup = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"sub_approve:{user_id}"),
                    InlineKeyboardButton("❌ Rad etish", callback_data=f"sub_reject:{user_id}"),
                ]
            ]
        )
        for admin_id in admin_ids:
            try:
                await bot_app.send_message(
                    admin_id,
                    f"💰 **Yangi to'lov!**\n\n"
                    f"👤 {first_name} (ID: `{user_id}`)\n"
                    f"💎 Summa: {amount} Stars\n\n"
                    f"Tasdiqlash yoki rad etish:",
                    reply_markup=markup,
                )
            except Exception:
                pass
    except Exception as e:
        print(f"Payment handler xato: {e}")


@bot_app.on_callback_query(filters.regex("^contact_click_track$"))
async def handle_contact_click(client, callback_query):
    user_id = callback_query.from_user.id
    first_name = callback_query.from_user.first_name or "Foydalanuvchi"
    
    # Stats ga yozish
    stats = load_stats()
    stats["contact_clicks"] = stats.get("contact_clicks", 0) + 1
    save_stats(stats)
    
    # Foydalanuvchini adminga yo'naltirish
    await callback_query.message.edit_text(
        f"✅ **Admin bilan bog'lanish uchun quyidagi havolani bosing:**\n\n"
        f"👉 [Admin bilan yozishing](tg://user?id={SECOND_ADMIN_ID})\n\n"
        f"Yoki to'g'ridan-to'g'ri yozing.",
    )
    await callback_query.answer()
    
    # Ikkala adminga xabar yuborish
    admins_list = load_admins()
    for admin_id in list(set(admins_list)):
        try:
            await bot_app.send_message(
                admin_id,
                f"📞 **Bog'lanish so'rovi!**\n\n"
                f"👤 [{first_name}](tg://user?id={user_id}) (ID: `{user_id}`) "
                f"admin bilan bog'lanish tugmasini bosdi.\n\n"
                f"Ehtimol Stars orqali to'lashda muammoga duch kelgan."
            )
        except:
            pass

@bot_app.on_callback_query(filters.regex("^sub_(approve|reject):"))
async def handle_sub_approval(client, callback_query):
    data_parts = callback_query.data.split(":")
    action = data_parts[0].split("_")[1] # approve or reject
    user_id_str = data_parts[1]
    user_id = int(user_id_str)
    
    pendings_file = os.path.join(DATA_DIR, "pending_payments.json")
    try:
        with open(pendings_file, "r") as f:
            pendings = json.load(f)
    except:
        await callback_query.answer("❌ Ma'lumot topilmadi.", show_alert=True)
        return
        
    if user_id_str not in pendings:
        await callback_query.answer("❌ Bu to'lov allaqachon ko'rib chiqilgan.", show_alert=True)
        return
        
    pending_info = pendings.pop(user_id_str)
    with open(pendings_file, "w") as f:
        json.dump(pendings, f, indent=4)
        
    if action == "approve":
        # Grant sub
        subs = load_subscriptions()
        expiry = time.time() + (SUBSCRIPTION_DAYS * 86400)
        subs[user_id_str] = {
            "expiry": expiry,
            "warned": False
        }
        save_subscriptions(subs)
        
        # Stats
        stats = load_stats()
        stats["total_income"] = stats.get("total_income", 0) + pending_info["amount"]
        if "payments" not in stats:
            stats["payments"] = []
        stats["payments"].append({
            "user_id": user_id,
            "amount": pending_info["amount"],
            "time": time.time()
        })
        save_stats(stats)
        
        try:
            await bot_app.send_message(
                user_id,
                "✅ **Admin tasdiqladi, botdan bemalol foydalanishingiz mumkin!**\n\nBoshlash uchun /start bosing."
            )
        except:
            pass
            
        await callback_query.message.edit_text(f"✅ {pending_info['first_name']} (ID: `{user_id}`) tasdiqlandi va ruxsat berildi.")
        
    elif action == "reject":
        charge_id = pending_info["charge_id"]
        url = f"https://api.telegram.org/bot{config['BOT_TOKEN']}/refundStarPayment"
        try:
            requests.post(url, json={"user_id": user_id, "telegram_payment_charge_id": charge_id})
        except Exception as e:
            print("Refund req error:", e)
            
        try:
            await bot_app.send_message(
                user_id,
                "❌ Xatolik: tolov qaytarildi."
            )
        except:
            pass
            
        await callback_query.message.edit_text(f"❌ {pending_info['first_name']} (ID: `{user_id}`) rad etildi. To'lov qaytarildi.")


# ================= HANDLERLAR =================
@bot_app.on_message(filters.command(["utag", "atag", "tagall"], prefixes=["/", ".", "!"]) & filters.group)
async def group_utag_command(client, message):
    user_id = message.from_user.id
    if not is_user_logged_in(user_id):
        return

    ok, current = acquire_task(user_id, "utag")
    if not ok:
        await message.reply_text(f"⚠️ Sizda hozir **{current}** vazifasi ishlayapti. Tugashini kuting.")
        return

    text = message.text.split(maxsplit=1)[1] if len(message.command) > 1 else ""
    stop_flags[user_id] = False
    
    await message.reply_text("✅ U-Tag boshlandi! To'xtatish uchun: `.stop` yozing.")
    chat_identifier = message.chat.username if message.chat.username else message.chat.id
    asyncio.create_task(utag_task(user_id, chat_identifier, text))

@bot_app.on_message(filters.command(["stop", "stop_utag", "cancel_task"], prefixes=["/", ".", "!"]))
async def global_stop_command(client, message):
    user_id = message.from_user.id
    if get_active_task(user_id):
        stop_flags[user_id] = True
        await message.reply_text("🛑 Vazifa to'xtatilmoqda...")
    else:
        await message.reply_text("Hech qanday faol vazifa topilmadi.")

@bot_app.on_message(filters.command("help", prefixes=["/", "."]) & filters.private)
async def help_command(client, message):
    """Barcha mavjud buyruqlar ro'yxatini chiroyli ko'rsatadi"""
    user_id = message.from_user.id

    text = (
        "╔══════════════════════════════╗\n"
        "   📖  **VENTO — Yordam Menyusi**\n"
        "╚══════════════════════════════╝\n\n"
        
        "━━━━━ 🔐 **Tizim** ━━━━━\n\n"
        
        "▸ `/start`\n"
        "  Botni ishga tushiradi va login jarayonini boshlaydi\n\n"
        
        "▸ `/help` yoki `.help`\n"
        "  Barcha buyruqlar va ularning vazifalari haqida ma'lumot\n\n"
        
        "▸ `/logout`\n"
        "  Tizimdan chiqadi, sessiya va bazani o'chiradi\n\n"
        
        "▸ `/cancel`\n"
        "  Joriy amalni bekor qiladi va asosiy menyuga qaytaradi\n\n"
        
        "━━━━━ 🚀 **Asosiy Xizmatlar** ━━━━━\n\n"
        
        "▸ **🚀 Scraper**\n"
        "  Guruhdan userlarni yig'adi (username bo'yicha).\n"
        "  4 xil filtr: Avtomatik, Xabarlar orqali, Qizlar, Adminlar\n\n"
        
        "▸ **📨 Xabar yuborish**\n"
        "  Bazadagi userlarga ommaviy DM xabar yuboradi.\n"
        "  Sonini tanlash yoki barchasiga yuborish mumkin\n\n"
        
        "▸ **🔍 Guruh Qidirish**\n"
        "  Kalit so'z bo'yicha Telegram global qidiruvidan\n"
        "  ochiq guruhlarni topadi\n\n"
        
        "▸ **📁 Yig'ilgan userlar**\n"
        "  Bazangizdagi barcha userlarni ko'rsatadi.\n"
        "  Yangi user qo'shish yoki bazani tozalash mumkin\n\n"
        
        "▸ **🎯 U-Tag**\n"
        "  Guruh a'zolarini mention qilib tag qiladi.\n"
        "  Menyu orqali yoki guruhda `.utag` buyrug'i bilan ishlatiladi\n\n"
        
        "━━━━━ ⚡ **Guruh Buyruqlari** ━━━━━\n\n"
        
        "▸ `.utag [matn]` yoki `.tagall [matn]`\n"
        "  Guruhda to'g'ridan-to'g'ri barcha a'zolarni tag qiladi\n\n"
        
        "▸ `.stop`\n"
        "  Istalgan faol vazifani (scraper, broadcast, utag) to'xtatadi\n\n"
        
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 **Maslahat:** Barcha xizmatlardan foydalanish uchun\n"
        "avval `/start` orqali tizimga kiring.\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    await message.reply_text(text, reply_markup=main_menu())

@bot_app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    user_id = message.from_user.id

    # Offline check
    global bot_offline
    if bot_offline:
        return  # Offline bo'lsa, hech narsa qilmaymiz

    # Login qilmagan — avval shartlar, keyin to'lov, so'ng login
    if not is_user_logged_in(user_id):
        if not is_subscribed(user_id):
            user_states[user_id] = "wait_terms_agree"
            terms_text = (
                "📜 **Foydalanish shartlari va Maxfiylik Siyosati (Privacy Policy)**\n\n"
                "Empire Bot xizmatlaridan foydalanish orqali siz quyidagilarga rozi bo'lasiz:\n"
                "1️⃣ Bot orqali jo'natilgan xabarlar, spam yoki boshqa harakatlar uchun foydalanuvchining shaxsan o'zi javobgar.\n"
                "2️⃣ Bot faqatgina vositachi hisoblanadi. Telegram tomonidan profilingizga tushadigan har qanday cheklov (ban/spam) uchun ma'muriyat javobgar emas.\n"
                "3️⃣ Xavfsizligingizni ta'minlash maqsadida bot orqali kirgan akkauntingiz barcha ma'lumotlari shifrlangan tarzda faqat ushbu serverda saqlanadi.\n\n"
                "Iltimos, botdan foydalanishni davom ettirish uchun shartlarga rozi ekanligingizni tasdiqlang."
            )
            markup = ReplyKeyboardMarkup(
                [[KeyboardButton("✅ Shartlarni qabul qilaman")]],
                resize_keyboard=True,
            )
            await message.reply_text(terms_text, reply_markup=markup)
            return

        await begin_login_flow(message, user_id)
        return

    # Login qilgan, lekin obunasi yo'q — to'lov so'rash
    if not is_subscribed(user_id):
        await require_subscription_before_login(message, user_id)
        return

    user_states[user_id] = "menu"
    first_name = message.from_user.first_name or "Mijoz"

    text = (
        f"👋 Assalomu alaykum, {first_name}!\n\n"
        "🎭 **VENTO** boshqaruv paneliga xush kelibsiz!\n\n"
        "📌 **Mavjud xizmatlar:**\n"
        "• 🚀 Scraper — guruhlardan user yig'ish\n"
        "• 📨 Xabar yuborish — bazadagi userlarga DM\n"
        "• 🔍 Guruh qidirish — kalit so'z bo'yicha qidiruv\n\n"
        "• U-Tag - guruhdagilarni chaqirish uchun\n"
        "Quyidagi tugmalardan birini tanlang:"
    )
    await message.reply_text(text, reply_markup=main_menu())


@bot_app.on_message(filters.command("profile") & filters.private)
async def profile_command(client, message):
    """Foydalanuvchi profil ma'lumotlarini ko'rsatadi"""
    user_id = message.from_user.id
    first_name = message.from_user.first_name or "Noma'lum"
    username = message.from_user.username or "Yo'q"
    
    # Admin status
    admin_status = "❌ Foydalanuvchi"
    if is_super_admin(user_id):
        admin_status = "👑 Bosh Admin"
    elif is_second_admin(user_id):
        admin_status = "⭐ Ikkinchi Admin"
    elif is_admin(user_id):
        admin_status = "🛡️ Admin"
    
    # Subscription status
    sub_status = "❌ Obunaga ega emas"
    sub_joined_date = "—"
    if is_subscribed(user_id):
        if is_admin(user_id) or is_super_admin(user_id) or is_second_admin(user_id):
            sub_status = "✅ Cheksiz (Admin)"
        else:
            subs = load_subscriptions()
            str_id = str(user_id)
            if str_id in subs:
                expiry = subs[str_id].get("expiry", 0)
                joined = subs[str_id].get("joined", 0)
                remaining_days = int((expiry - time.time()) / 86400)
                if remaining_days > 0:
                    sub_status = f"✅ Obunaga ega ({remaining_days} kun qoldi)"
                else:
                    sub_status = "⚠️ Obuna muddati tugagan"
                if joined > 0:
                    sub_joined_date = datetime.fromtimestamp(joined).strftime("%d.%m.%Y")
    
    # VIP status
    vip_status = "❌ VIP emas"
    vip_joined_date = "—"
    VIP_FILE = os.path.join(DATA_DIR, "vips.json")
    if os.path.exists(VIP_FILE):
        try:
            with open(VIP_FILE, "r", encoding="utf-8") as f:
                vips = json.load(f)
                if isinstance(vips, dict):
                    str_id = str(user_id)
                    if str_id in vips:
                        vip_data = vips[str_id]
                        if isinstance(vip_data, dict) and vip_data.get("expiry"):
                            expiry = vip_data["expiry"]
                            joined = vip_data.get("joined", 0)
                            if time.time() > expiry:
                                vip_status = "⚠️ VIP muddati tugagan"
                            else:
                                remaining_days = int((expiry - time.time()) / 86400)
                                vip_status = f"💎 VIP ({remaining_days} kun qoldi)"
                            if joined > 0:
                                vip_joined_date = datetime.fromtimestamp(joined).strftime("%d.%m.%Y")
                        else:
                            vip_status = "💎 VIP (Cheksiz)"
                elif isinstance(vips, list):
                    if user_id in vips:
                        vip_status = "💎 VIP (Cheksiz)"
        except:
            pass
    
    # Database count
    databases = get_all_databases(user_id)
    db_count = len(databases)
    total_users = sum(len(db.get("users", [])) for db in databases.values())
    
    # Login status
    login_status = "✅ Login qilgan" if is_user_logged_in(user_id) else "❌ Login qilmagan"
    
    # User join date (first time using bot)
    USER_DATA_FILE = os.path.join(DATA_DIR, "user_data.json")
    user_joined_date = "—"
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
                user_data = json.load(f)
                str_id = str(user_id)
                if str_id in user_data:
                    joined = user_data[str_id].get("joined", 0)
                    if joined > 0:
                        user_joined_date = datetime.fromtimestamp(joined).strftime("%d.%m.%Y")
        except:
            pass
    
    text = (
        f"👤 **Profil Ma'lumotlari**\n\n"
        f"🆔 **User ID:** `{user_id}`\n"
        f"👤 **Ism:** {first_name}\n"
        f"🔖 **Username:** @{username}\n"
        f"🛡️ **Status:** {admin_status}\n"
        f"📅 **Obuna:** {sub_status}\n"
        f"📆 **Obuna qo'shilgan:** {sub_joined_date}\n"
        f"💎 **VIP:** {vip_status}\n"
        f"📆 **VIP qo'shilgan:** {vip_joined_date}\n"
        f"🔐 **Login:** {login_status}\n"
        f"📆 **Botga qo'shilgan:** {user_joined_date}\n"
        f"💾 **Bazalar:** {db_count} ta\n"
        f"👥 **Jami userlar:** {total_users} ta\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    
    # Yordam tugmasi bilan inline keyboard - admin username orqali
    try:
        admin_user = await client.get_users(SUPER_ADMIN_ID)
        admin_username = admin_user.username if admin_user.username else str(SUPER_ADMIN_ID)
        help_url = f"https://t.me/{admin_username}"
    except:
        help_url = f"https://t.me/{SUPER_ADMIN_ID}"
    
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("❓ Yordam", url=help_url)]
    ])
    
    await message.reply_text(text, reply_markup=markup)


@bot_app.on_message(filters.command("cancel") & filters.private)
async def cancel_command(client, message):
    user_id = message.from_user.id
    state = user_states.get(user_id)

    if state in [
        "wait_terms_agree",
        "wait_payment",
        "login_phone",
        "login_code",
        "login_password",
        "login_upload",
    ]:
        # Login jarayonini bekor qilish
        if user_id in login_data:
            try:
                # Clientni tozalash
                data = login_data[user_id]
                if "client" in data and data["client"].is_connected:
                    await data["client"].disconnect()
            except:
                pass
            del login_data[user_id]

        user_states.pop(user_id, None)
        from pyrogram.types import ReplyKeyboardRemove
        await message.reply_text("❌ Login bekor qilindi.\n\nQayta boshlash uchun /start ni bosing.", reply_markup=ReplyKeyboardRemove())
    elif state and state != "menu":
        user_states[user_id] = "menu"
        await message.reply_text(
            "🏠 Asosiy menyuga qaytdingiz.", reply_markup=main_menu()
        )
    else:
        await message.reply_text(
            "Hech narsa bekor qilinmadi.", reply_markup=main_menu()
        )


@bot_app.on_message(filters.command("logout") & filters.private)
async def logout_command(client, message):
    user_id = message.from_user.id
    if not is_user_logged_in(user_id):
        await message.reply_text("❌ Siz hali tizimga kirmagansiz.")
        return

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Ha, chiqish", callback_data="confirm_logout"),
                InlineKeyboardButton("❌ Yo'q, qolish", callback_data="cancel_logout"),
            ]
        ]
    )
    await message.reply_text(
        "⚠️ **Diqqat!**\n\nTizimdan chiqsangiz barcha yig'ilgan bazangiz (userlar) va sessiyangiz o'chib ketadi. "
        "Qaytadan telefon raqam orqali kirishingiz kerak bo'ladi.\n\nRostdan ham chiqmoqchimisiz?",
        reply_markup=keyboard,
    )


@bot_app.on_callback_query(filters.regex("^(confirm_logout|cancel_logout)$"))
async def logout_callback(client, callback):
    user_id = callback.from_user.id

    if callback.data == "cancel_logout":
        await callback.message.edit_text("❌ Tizimdan chiqish bekor qilindi.")
        return

    if callback.data == "confirm_logout":
        await callback.answer("Ma'lumotlar o'chirilmoqda...")

        # Sessiyani o'chirish
        session_path = os.path.join(SESSIONS_DIR, f"user_{user_id}.session")

        with clients_lock:
            user_client = user_clients.get(user_id)

        if user_client:
            try:
                if user_client.is_connected:
                    await user_client.disconnect()
            except:
                pass
            with clients_lock:
                if user_id in user_clients:
                    del user_clients[user_id]

        if os.path.exists(session_path):
            try:
                os.remove(session_path)
            except Exception as e:
                print(f"Error removing session {user_id}: {e}")

        # Bazani tozalash
        clear_user_database(user_id)

        # Holatlarni tozalash
        logged_in_users.discard(user_id)
        user_states.pop(user_id, None)

        text = (
            "✅ **Tizimdan muvaffaqiyatli chiqdingiz va barcha ma'lumotlaringiz o'chirildi.**\n\n"
            "Qayta kirish uchun /start ni bosing."
        )
        await callback.message.edit_text(text)


@bot_app.on_message(filters.command("shutdown") & filters.private)
async def shutdown_command(client, message):
    """Botni offline qiladi (faqat ikkinchi admin uchun)"""
    user_id = message.from_user.id

    if not (is_second_admin(user_id) or is_super_admin(user_id)):
        await message.reply_text("❌ Sizda bu buyruqni ishlatish uchun huquq yo'q.")
        return

    global bot_offline
    bot_offline = True
    await message.reply_text(
        "🔴 **Bot offline holatiga o'tdi.**\n\nEndi hech qanday buyruqga javob bermaydi.\nOnline qilish uchun: `/power`"
    )


@bot_app.on_message(filters.command("power") & filters.private)
async def power_command(client, message):
    """Botni online qiladi (faqat ikkinchi admin uchun)"""
    user_id = message.from_user.id

    if not (is_second_admin(user_id) or is_super_admin(user_id)):
        await message.reply_text("❌ Sizda bu buyruqni ishlatish uchun huquq yo'q.")
        return

    global bot_offline
    bot_offline = False
    await message.reply_text(
        "🟢 **Bot online holatiga o'tdi.**\n\nEndi barcha buyruqlarga javob berada."
    )


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


@bot_app.on_message(filters.command("dashboard") & filters.private)
async def dashboard_command(client, message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.reply_text("❌ Sizda bu buyruqni ishlatish uchun huquq yo'q.")
        return
        
    subs = load_subscriptions()
    stats = load_stats()
    
    try:
        total_users = len([f for f in os.listdir(SESSIONS_DIR) if f.endswith(".session")])
    except:
        total_users = 0
        
    active_subs = len(subs)
    expired_subs = stats.get("expired_subs", 0)
    total_income = stats.get("total_income", 0)
    
    today_start = time.mktime(time.strptime(time.strftime("%Y-%m-%d 00:00:00"), "%Y-%m-%d %H:%M:%S"))
    today_payments = 0
    today_income = 0
    
    for p in stats.get("payments", []):
        if p.get("time", 0) >= today_start:
            today_payments += 1
            today_income += p.get("amount", 0)
            
    contact_clicks = stats.get("contact_clicks", 0)
    
    text = (
        "📊 **BOT DASHBOARD (Statistika)**\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "👥 **Foydalanuvchilar:**\n"
        f"👤 Jami ro'yxatdan o'tganlar: **{total_users}** ta\n"
        f"🟢 Faol obunachilar: **{active_subs}** ta\n"
        f"🔴 Muddati tugagan obunalar: **{expired_subs}** ta\n\n"
        "💰 **Moliya (Telegram Stars ⭐️):**\n"
        f"💵 Barcha vaqtdagi daromad: **{total_income}** ⭐️\n"
        f"📅 Bugungi to'lovlar soni: **{today_payments}** ta\n"
        f"📈 Bugungi tushum: **{today_income}** ⭐️\n\n"
        "📞 **Bog'lanishlar:**\n"
        f"💬 Admin bilan bog'lanish tanlagan: **{contact_clicks}** ta\n\n"
        "━━━━━━━━━━━━━━━━━━━━"
    )
    
    await message.reply_text(text)


# Login flow handlers
async def handle_login_upload(client, message, user_id):
    """Session faylini qabul qilish"""
    if message.document:
        try:
            # Faylni yuklab olish
            file = message.document
            file_path = await client.download_media(
                file, file_name=f"sessions/user_{user_id}.session"
            )

            # Faylni SESSIONS_DIR ga ko'chirish
            final_path = os.path.join(SESSIONS_DIR, f"user_{user_id}.session")
            shutil.move(file_path, final_path)

            # Client yaratish va tekshirish
            session_name = os.path.join("data", "sessions", f"user_{user_id}")
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
                await message.reply_text(
                    "❌ Bu bot session fayli. User session faylini yuboring."
                )
                os.remove(final_path)
                return

            # Muvaffaqiyatli
            with clients_lock:
                user_clients[user_id] = user_client

            if user_id in login_data:
                del login_data[user_id]
            await show_post_auth_screen(client, message, user_id)
        except Exception as e:
            await message.reply_text(
                f"❌ Xatolik: {str(e)}\n\nQaytadan urinib ko'ring."
            )
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
            f"my.telegram.org dan olingan API_HASH ni yuboring.",
            reply_markup=api_hash_guide_keyboard(),
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
    cleaned = re.sub(r"[\s\(\)\-\.]", "", phone)

    # Faqat raqamlar qolganini tekshirish uchun + ni vaqtincha olib turish
    num_only = cleaned[1:] if cleaned.startswith("+") else cleaned

    # Faqat raqamlar qolganini tekshirish
    if not num_only.isdigit():
        return None

    # Uzunligini tekshirish (7-15 raqam)
    if len(num_only) < 7 or len(num_only) > 15:
        return None

    return "+" + num_only


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
        session_name = os.path.join("data", "sessions", f"user_{user_id}")

        user_client = Client(
            session_name,
            api_id=config["API_ID"],
            api_hash=config["API_HASH"],
            workdir=BASE_DIR,
        )

        # Clientni ulash
        await user_client.connect()

        # Kod yuborish
        sent_code = await user_client.send_code(phone)

        # Ma'lumotlarni saqlash
        login_data[user_id] = {
            "api_id": config["API_ID"],
            "api_hash": config["API_HASH"],
            "phone": phone,
            "phone_code_hash": sent_code.phone_code_hash,
            "client": user_client,
        }

        # Keyingi holatga o'tish
        user_states[user_id] = "login_code"
        print(f"🔑 User {user_id} state changed to login_code")

        await message.reply_text(
            f"✅ **Kod yuborildi!**\n\n"
            f"📱 Raqam: `{phone}`\n\n"
            f"🔢 Telegramdan kelgan kodni kiriting.\n\n"
            f"💡 Masalan: `1 2 3 4 5` (Orasiga 1 probel qo'yin yozing)"
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
        code = re.sub(r"[\s\-\.]", "", code_text)
        if not code.isdigit():
            await message.reply_text(
                "❌ Kod faqat raqamlardan iborat bo'lishi kerak. Masalan: `1 2 3 4 5`"
            )
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
            if (
                "SESSION_PASSWORD_NEEDED" in error_str
                or "2FA" in error_str.lower()
                or "two-factor" in error_str.lower()
            ):
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

        session_name = os.path.join("data", "sessions", f"user_{user_id}")

        # Clientni qaytadan yaratish va saqlash
        user_client = Client(
            session_name,
            api_id=config["API_ID"],
            api_hash=config["API_HASH"],
            workdir=BASE_DIR,
        )

        with clients_lock:
            user_clients[user_id] = user_client

        # Tozalash
        if user_id in login_data:
            del login_data[user_id]

        await show_post_auth_screen(client, message, user_id)
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

        # Parol bilan login qilish (Pyrogram v2: check_password())
        await user_client.check_password(password_text)

        # Muvaffaqiyatli login!
        await user_client.disconnect()

        session_name = os.path.join("data", "sessions", f"user_{user_id}")

        # Clientni qaytadan yaratish va saqlash
        user_client = Client(
            session_name,
            api_id=config["API_ID"],
            api_hash=config["API_HASH"],
            workdir=BASE_DIR,
        )

        with clients_lock:
            user_clients[user_id] = user_client

        # Tozalash
        if user_id in login_data:
            del login_data[user_id]

        await show_post_auth_screen(client, message, user_id)
        return True

    except Exception as e:
        await message.reply_text(
            f"❌ Noto'g'ri parol: {str(e)}\n\nQaytadan urinib ko'ring."
        )
        return False


@bot_app.on_message(
    filters.private
    & ~filters.command(["start", "shutdown", "power", "admins", "cancel", "logout", "help", "add_admin", "del_admin", "add_vip", "del_vip", "add_member", "del_member", "dashboard", "profile"])
)
async def process_messages(client, message):
    from pyrogram.types import ReplyKeyboardRemove

    user_id = message.from_user.id
    text = message.text
    if message.contact:
        text = message.contact.phone_number

    if not text and not message.document:
        return

    # Debug logging
    state = user_states.get(user_id)
    print(f"📨 User {user_id} sent: '{text}', current state: {state}")

    if text in ["❌ Bekor qilish", "/cancel"]:
        user_states.pop(user_id, None)
        await message.reply_text("❌ Bekor qilindi.", reply_markup=ReplyKeyboardRemove())
        return

    # Xavfsizlik: Login qilmagan bo'lsa hech narsa qila olmaydi (faqat ruxsat etilgan state'larda)
    if not is_user_logged_in(user_id) and state not in [
        "wait_terms_agree",
        "wait_payment",
        *LOGIN_FLOW_STATES,
    ]:
        await message.reply_text(
            "❌ Xatolik: Siz avval tizimga kirishingiz kerak. /start ni bosing.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    # Subscription check (login flow bundan mustasno emas)
    if state not in ["wait_terms_agree", "wait_payment"] and not is_subscribed(user_id):
        await require_subscription_before_login(message, user_id)
        return

    # Login flow - Shartlarga rozi bo'lish
    if state == "wait_terms_agree":
        if text == "✅ Shartlarni qabul qilaman":
            if not is_subscribed(user_id):
                await require_subscription_before_login(message, user_id)
            else:
                await begin_login_flow(message, user_id)
        else:
            await message.reply_text("Iltimos, pastdagi tugma orqali shartlarga rozi bo'ling.")
        return

    if state == "wait_payment":
        await message.reply_text(
            "⏳ To'lov kutilmoqda. Invoice xabarini ochib Stars bilan to'lang.\n\n"
            "To'lov qilgan bo'lsangiz, admin tasdiqlashini kuting va /start bosing.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    # Login flow — obunasiz kirish bloklangan
    if state in LOGIN_FLOW_STATES and not is_subscribed(user_id):
        await require_subscription_before_login(message, user_id)
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
        await send_or_edit_message(
            client, user_id, "🏠 Asosiy menyuga qaytdingiz.", reply_markup=main_menu()
        )
        return

    # Dublikat buyruq tekshiruvi — login va cancel bundan ozod
    if is_duplicate_command(user_id, text):
        await send_or_edit_message(
            client,
            user_id,
            "⚠️ Bir xil tugmani ketma-ket bosmang. Biroz kuting.",
            reply_markup=main_menu()
            if user_states.get(user_id, "menu") == "menu"
            else cancel_menu(),
        )
        return

    state = user_states.get(user_id, "menu")

    if text in MENU_BUTTONS:
        if state != "menu":
            await send_or_edit_message(
                client,
                user_id,
                "⚠️ Avval joriy amalni tugating yoki `❌ Bekor qilish` bosing.",
                reply_markup=cancel_menu(),
            )
            return
        active = get_active_task(user_id)
        if active:
            await send_or_edit_message(
                client, user_id, active_task_message(active), reply_markup=main_menu()
            )
            return

    if text in DATABASE_BUTTONS:
        if text == "➕ Yangi user(lar) qo'shish":
            user_states[user_id] = "add_new_users_wait"
            await send_or_edit_message(client, user_id,
                "➕ **Yangi user(lar)ni kiriting:**\n"
                "Usernamelarni probel, vergul yoki yangi qatordan ajratib yozavering.\n"
                "Masalan: `@username1, @username2, @username3`",
                reply_markup=cancel_menu(),
            )
            return
        elif text == "🗑️ Bazani tozalash":
            await send_or_edit_message(
                client,
                user_id,
                "⚠️ **Diqqat!** Barcha yig'ilgan userlar o'chirib yuboriladi.\n"
                "Rostdan ham tozalaysizmi?",
                reply_markup=confirm_delete_menu(),
            )
            user_states[user_id] = "confirm_delete"
            return
        elif text == "🔙 Orqaga":
            user_states[user_id] = "menu"
            await send_or_edit_message(
                client,
                user_id,
                "🏠 Asosiy menyuga qaytdingiz.",
                reply_markup=main_menu(),
            )
            return
        return

    if state == "add_new_users_wait":
        usernames = re.findall(r"@?([A-Za-z0-9_]{5,32})", text)
        if not usernames:
            await send_or_edit_message(
                client, user_id, "❌ Hech qanday yaroqli username topilmadi. Qaytadan kiriting:", reply_markup=cancel_menu()
            )
            return
        
        formatted_usernames = [f"@{u}" if not u.startswith("@") else u for u in usernames]
        temp_add_users[user_id] = formatted_usernames
        user_states[user_id] = "add_new_users_confirm"
        
        await send_or_edit_message(
            client, user_id,
            f"✅ **{len(formatted_usernames)}** ta username topildi.\n\n"
            f"Shularni bazaga qo'shishni tasdiqlaysizmi?",
            reply_markup=ReplyKeyboardMarkup(
                [[KeyboardButton("✅ Ha, tasdiqlash"), KeyboardButton("❌ Yo'q, bekor qilish")]],
                resize_keyboard=True
            )
        )
        return

    if state == "add_new_users_confirm":
        if text == "✅ Ha, tasdiqlash":
            users_to_add = temp_add_users.get(user_id, [])
            if users_to_add:
                # Add to a new DB called 'Qo'lda qo'shilganlar'
                save_database(user_id, "Qo'lda qo'shilganlar", users_to_add)
            
            user_states[user_id] = "menu"
            temp_add_users.pop(user_id, None)
            
            usernames = load_user_database(user_id)
            await send_or_edit_message(
                client, user_id,
                f"✅ **{len(users_to_add)}** ta user bazaga qo'shildi!\n\n"
                f"📁 Bazangizda jami **{len(usernames)}** ta user bor.",
                reply_markup=database_menu(),
            )
            show_paginated_users(client, user_id, usernames)
            
        elif text == "❌ Yo'q, bekor qilish":
            user_states[user_id] = "menu"
            temp_add_users.pop(user_id, None)
            usernames = load_user_database(user_id)
            await send_or_edit_message(
                client, user_id, "❌ Bekor qilindi.", reply_markup=database_menu()
            )
            show_paginated_users(client, user_id, usernames)
        return

    if state == "confirm_delete":
        if text == "✅ Ha, tozalash":
            clear_user_database(user_id)
            user_states[user_id] = "menu"
            await send_or_edit_message(
                client, user_id, "🗑️ Baza tozalandi.", reply_markup=main_menu()
            )
        elif text == "❌ Bekor qilish":
            user_states[user_id] = "menu"
            await send_or_edit_message(
                client, user_id, "Bekor qilindi.", reply_markup=main_menu()
            )
        return

    # ----- ASOSIY MENYU -----
    if state == "menu":
        if text == "⚡ Super Scraper":
            user_states[user_id] = "scrape_wait_group"
            await send_or_edit_message(
                client,
                user_id,
                "🚀 **SCRAPER (Full Olish)**\n\n"
                "Guruh manzilini yuboring:\n"
                "• `@guruh_username`\n"
                "• `https://t.me/guruh_username`\n"
                "• Yopiq guruh: `https://t.me/+invite_kodi`\n\n"
                "⚠️ Guruh **nomi** emas, **@username** yoki **havola** yuboring!\n"
                "User akkauntingiz guruhda bo'lishi kerak.",
                reply_markup=cancel_menu(),
            )

        elif text == "📮 Smart Xabarnoma" or text == "Xabar yuborish":
            dbs = get_all_databases(user_id)
            if not dbs:
                await send_or_edit_message(
                    client,
                    user_id,
                    "❌ Bazangizda userlar yo'q. Avval `🚀 Scraper` orqali user yig'ing yoki pastdagi menyudan o'zingiz qo'shing.",
                    reply_markup=database_menu()
                )
                return
            
            text_msg = f"📨 **XABAR YUBORISH**\n\nQaysi bazadagi userlarga xabar yubormoqchisiz?\n\n"
            for db_id, info in dbs.items():
                title = info.get("title", "Noma'lum")
                text_msg += f"🔹 **ID:** `{db_id}` | Guruh: _{title}_ | Qoldi: **{len(info.get('users', []))}**\n"
            text_msg += "\nID raqamini yozing:"
            
            user_states[user_id] = "wait_db_id_broadcast"
            await send_or_edit_message(
                client,
                user_id,
                text_msg,
                reply_markup=cancel_menu(),
            )

        elif text == "💾 Yig'ilgan Bazalar":
            dbs = get_all_databases(user_id)
            if dbs:
                text_msg = f"📁 **Saqlangan foydalanuvchilar bazasi**\n📊 Jami guruhlar: **{len(dbs)}** ta\n\n"
                for db_id, info in dbs.items():
                    title = info.get("title", "Noma'lum")
                    time_str = info.get("timestamp", "Noma'lum")
                    text_msg += f"🔹 **ID:** `{db_id}`\n📝 Guruh: _{title}_\n👥 Qoldi: **{len(info.get('users', []))}** ta\n🕒 Vaqt: {time_str}\n\n"
                
                text_msg += "Tavsilotni olish uchun bazaning ID raqamini pastga yozing:"
                user_states[user_id] = "wait_db_id_view"
                await send_or_edit_message(
                    client,
                    user_id,
                    text_msg,
                    reply_markup=database_menu(),
                )
            else:
                await send_or_edit_message(
                    client,
                    user_id,
                    "❌ Hozircha bazangiz bo'sh. Avval `🚀 Scraper` orqali user yig'ing yoki pastdagi tugma orqali o'zingiz qo'shing.",
                    reply_markup=database_menu()
                )
        else:
            await send_or_edit_message(
                client,
                user_id,
                "Iltimos, tugmalardan birini tanlang.",
                reply_markup=main_menu(),
            )

    
    # ----- DATABASE SELECTION -----
    elif state == "wait_db_id_broadcast":
        if text in ["🏠 Asosiy menyu", "🔙 Orqaga", "❌ Bekor qilish"]:
            user_states[user_id] = "menu"
            await send_or_edit_message(
                client, user_id, "🏠 Asosiy menyuga qaytdingiz.", reply_markup=main_menu()
            )
            return
            
        db_id = text.strip()
        db = get_database(user_id, db_id)
        if not db:
            await send_or_edit_message(
                client, user_id, "❌ Bunday ID topilmadi. Qaytadan kiriting:", reply_markup=cancel_menu()
            )
            return
            
        # Select this DB
        json_file = get_user_json_file(user_id)
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["selected_db"] = db_id
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except:
            pass

        users = db.get("users", [])
        title = db.get("title", "Noma'lum")
        
        user_states[user_id] = "broadcast_wait_count"
        await send_or_edit_message(
            client,
            user_id,
            f"✅ **Baza tanlandi!**\n\n📁 Guruh: _{title}_\n👥 Jami {len(users)} ta foydalanuvchi.\n\n"
            f"📤 Ulardan nechtasini yuboray? (Raqam kiriting)\n_Eslatma: To'liq ro'yxat bazada saqlanadi._\nID: {db_id}",
            reply_markup=broadcast_count_menu()
        )
        return

    # ----- BROADCAST COUNT -----
        db = get_database(user_id, db_id)
        if not db:
            await send_or_edit_message(
                client, user_id, "❌ Bunday ID topilmadi. Qaytadan kiriting:", reply_markup=database_menu()
            )
            return
            
        json_file = get_user_json_file(user_id)
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["selected_db"] = db_id
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except:
            pass

        users = db.get("users", [])
        title = db.get("title", "Noma'lum")
        
        user_states[user_id] = "menu"
        await send_or_edit_message(
            client, user_id,
            f"✅ **Baza tanlandi!**\n\n📁 Guruh: _{title}_\n👥 Jami {len(users)} ta foydalanuvchi.\n",
            reply_markup=main_menu()
        )
        show_paginated_users(client, user_id, users)
        return

    # ----- SCRAPER (FULL OLISH) -----
    elif state == "scrape_wait_group":
        group_input = text
        try:
            user_client = await get_user_client_started(user_id)
            chat_id, chat_title = await resolve_chat_id(user_client, text)
            scraper_selections[user_id] = {
                "group": group_input,
                "chat_id": chat_id,
                "chat_title": chat_title,
            }
            user_states[user_id] = "scrape_wait_filter"
            await send_or_edit_message(
                client,
                user_id,
                f"✅ Guruh qabul qilindi: **{chat_title}**\n\n"
                "Endi scraping usulini tanlang:",
                reply_markup=scraper_filter_menu(),
            )
        except Exception as e:
            await send_or_edit_message(
                client, user_id, explain_telegram_error(e), reply_markup=main_menu()
            )
            user_states[user_id] = "menu"

    elif state == "scrape_wait_filter":
        if text not in SCRAPER_FILTERS:
            await send_or_edit_message(
                client,
                user_id,
                "Iltimos, filtr tugmalaridan birini tanlang.",
                reply_markup=scraper_filter_menu(),
            )
            return

        selection = scraper_selections.get(user_id)
        if not selection:
            await send_or_edit_message(
                client, user_id, "❌ Xatolik. Qayta boshlang.", reply_markup=main_menu()
            )
            user_states[user_id] = "menu"
            return

        filter_type = text

        if filter_type == "📊 Xabarlar orqali (Sekin)":
            user_states[user_id] = "scrape_wait_message_count"
            await send_or_edit_message(
                client,
                user_id,
                "📊 **XABARLAR SONI**\n\n"
                "Nechta xabarni o'qishni xohlaysiz?\n"
                "• Masalan: `1000`, `10000`, `1000000`\n\n"
                "⚠️ Maksimal: **5,000,000** ta xabar",
                reply_markup=cancel_menu(),
            )
        else:
            ok, current = acquire_task(user_id, "scrape")
            if not ok:
                await send_or_edit_message(
                    client,
                    user_id,
                    active_task_message(current),
                    reply_markup=main_menu(),
                )
                user_states[user_id] = "menu"
                return

            await send_or_edit_message(
                client,
                user_id,
                "⏳ Userlar yig'ilmoqda — bu biroz vaqt olishi mumkin.",
                reply_markup=ReplyKeyboardRemove(),
            )
            user_states[user_id] = "menu"

            asyncio.create_task(scrape_task(user_id, selection["group"], filter_type))
            scraper_selections.pop(user_id, None)

    elif state == "scrape_wait_message_count":
        try:
            message_count = int(text.replace(",", "").replace(" ", ""))
        except ValueError:
            await send_or_edit_message(
                client,
                user_id,
                "❌ Iltimos, raqam kiriting. Masalan: `1000`",
                reply_markup=cancel_menu(),
            )
            return

        if message_count < 1:
            await send_or_edit_message(
                client,
                user_id,
                "❌ Kamida 1 ta xabar kiritishingiz kerak.",
                reply_markup=cancel_menu(),
            )
            return

        if message_count > 5000000:
            await send_or_edit_message(
                client,
                user_id,
                "❌ Maksimal 5,000,000 ta xabar kiritish mumkin.",
                reply_markup=cancel_menu(),
            )
            return

        selection = scraper_selections.get(user_id)
        if not selection:
            await send_or_edit_message(
                client, user_id, "❌ Xatolik. Qayta boshlang.", reply_markup=main_menu()
            )
            user_states[user_id] = "menu"
            return

        ok, current = acquire_task(user_id, "scrape")
        if not ok:
            await send_or_edit_message(
                client, user_id, active_task_message(current), reply_markup=main_menu()
            )
            user_states[user_id] = "menu"
            return

        await send_or_edit_message(
            client,
            user_id,
            f"⏳ {message_count:,} ta xabar o'qilmoqda — bu biroz vaqt olishi mumkin.",
            reply_markup=ReplyKeyboardRemove(),
        )
        user_states[user_id] = "menu"

        asyncio.create_task(
            scrape_task(
                user_id, selection["group"], "📊 Xabarlar orqali (Sekin)", message_count
            )
        )
        scraper_selections.pop(user_id, None)

    # ----- GURUH QIDIRISH (GLOBAL SEARCH) -----
    elif state == "search_wait_keyword":
        keyword = text
        ok, current = acquire_task(user_id, "search")
        if not ok:
            await send_or_edit_message(
                client, user_id, active_task_message(current), reply_markup=main_menu()
            )
            user_states[user_id] = "menu"
            return

        await send_or_edit_message(
            client,
            user_id,
            f"⏳ '{keyword}' so'zi bo'yicha Telegram global tarmog'idan guruhlar axtarilmoqda...",
        )

        try:
            user_client = await get_user_client_started(user_id)
            result = await user_client.invoke(
                functions.contacts.Search(q=keyword, limit=20)
            )

            found_chats = []
            for chat in result.chats:
                if getattr(chat, "username", None):
                    found_chats.append(f"📌 @{chat.username} | {chat.title}")

            if found_chats:
                res_text = "🔎 **Topilgan guruhlar:**\n\n" + "\n".join(found_chats)
                await send_or_edit_message(
                    client, user_id, res_text, reply_markup=main_menu()
                )
            else:
                await send_or_edit_message(
                    client,
                    user_id,
                    "❌ Hech qanday guruh topilmadi.",
                    reply_markup=main_menu(),
                )
        except Exception as e:
            await send_or_edit_message(
                client, user_id, f"❌ Qidiruvda xatolik: {e}", reply_markup=main_menu()
            )
        finally:
            release_task(user_id, "search", cleanup=True)

        user_states[user_id] = "menu"

    # ----- XABAR YUBORISH (BROADCAST) -----
    elif state == "broadcast_wait_count":
        usernames = load_user_database(user_id)
        if not usernames:
            await send_or_edit_message(
                client, user_id, "❌ Baza topilmadi yoki bo'sh. Qaytadan baza tanlang.", reply_markup=main_menu()
            )
            user_states[user_id] = "menu"
            return
            
        if text == "Barchasiga yuborish":
            count = len(usernames)
        else:
            try:
                count = int(text)
                if count <= 0:
                    raise ValueError
                if count > len(usernames):
                    count = len(usernames)
            except ValueError:
                await send_or_edit_message(
                    client, user_id, "❌ Noto'g'ri son kiritildi. Qaytadan kiriting:", reply_markup=broadcast_count_menu()
                )
                return
        
        temp_broadcast_count[user_id] = count
        user_states[user_id] = "broadcast_wait_text"
        await send_or_edit_message(
            client,
            user_id,
            f"✅ **{count}** ta user tanlandi.\n\n"
            "Endi yuboriladigan xabar matnini yozing:\n"
            "_(Spamdan himoya uchun har bir xabar orasida 3 soniya pauza qo'yiladi)_",
            reply_markup=cancel_menu(),
        )
        return

    elif state == "broadcast_wait_text":
        msg_text = text
        count = temp_broadcast_count.get(user_id, 0)
        user_states[user_id] = "menu"
        temp_broadcast_count.pop(user_id, None)

        usernames = load_user_database(user_id)
        if not usernames:
            await send_or_edit_message(
                client,
                user_id,
                "❌ Bazada foydalanuvchi yo'q.",
                reply_markup=main_menu(),
            )
            return

        if count > 0 and count < len(usernames):
            usernames = usernames[:count]

        ok, current = acquire_task(user_id, "broadcast")
        if not ok:
            await send_or_edit_message(
                client, user_id, active_task_message(current), reply_markup=main_menu()
            )
            return

        from pyrogram.types import ReplyKeyboardRemove as RKR

        await send_or_edit_message(
            client,
            user_id,
            f"⏳ **{len(usernames)}** ta foydalanuvchiga xabar yuborish boshlandi...\n"
            "Jarayon fonda davom etadi, natija alohida xabar qilib yuboriladi.",
            reply_markup=RKR(),
        )

        asyncio.create_task(broadcast_task(user_id, usernames, msg_text))

    # ----- U-TAG (MENYU ORQALI) -----
    elif state == "utag_wait_group":
        ok, current = acquire_task(user_id, "utag")
        if not ok:
            await send_or_edit_message(
                client, user_id, active_task_message(current), reply_markup=main_menu()
            )
            user_states[user_id] = "menu"
            return

        try:
            user_client = await get_user_client_started(user_id)
            target = parse_group_input(text)
            chat_id, chat_title = await resolve_chat_id(user_client, text)
            
            # Guruh topildi, matni so'raymiz
            release_task(user_id, "utag", cleanup=False)  # Taskni bo'shatamiz, lekin clientni O'CHIRMAYMIZ
            temp_add_users[user_id] = {"chat_id": chat_id, "chat_title": chat_title, "target": target}
            user_states[user_id] = "utag_wait_text"
            await send_or_edit_message(
                client,
                user_id,
                f"✅ Guruh topildi: **{chat_title}**\n\n"
                "📝 Qo'shimcha matn yozing (mention + matn):\n"
                "Yoki matn kerak bo'lmasa `yo'q` deb yozing.",
                reply_markup=cancel_menu(),
            )
        except Exception as e:
            release_task(user_id, "utag", cleanup=False)
            await send_or_edit_message(
                client, user_id, explain_telegram_error(e), reply_markup=main_menu()
            )
            user_states[user_id] = "menu"

    elif state == "utag_wait_text":
        info = temp_add_users.pop(user_id, None)
        if not info:
            user_states[user_id] = "menu"
            await send_or_edit_message(client, user_id, "❌ Xatolik. Qaytadan urinib ko'ring.", reply_markup=main_menu())
            return

        utag_text = "" if text.lower() in ("yo'q", "yoq", "no", "-") else text

        ok, current = acquire_task(user_id, "utag")
        if not ok:
            await send_or_edit_message(
                client, user_id, active_task_message(current), reply_markup=main_menu()
            )
            user_states[user_id] = "menu"
            return

        stop_flags[user_id] = False
        user_states[user_id] = "menu"

        await send_or_edit_message(
            client,
            user_id,
            f"🎯 **{info['chat_title']}** guruhida U-Tag boshlandi!\n\n"
            "To'xtatish uchun: `.stop` yozing.",
            reply_markup=main_menu(),
        )
        asyncio.create_task(utag_task(user_id, info.get("target", info["chat_id"]), utag_text))


@bot_app.on_callback_query(filters.regex("^delete_broadcast$"))
async def delete_broadcast_callback(client, callback_query):
    user_id = callback_query.from_user.id
    history_file = os.path.join(DATA_DIR, f"broadcast_history_{user_id}.json")
    
    if not os.path.exists(history_file):
        await callback_query.answer("❌ O'chirish uchun xabarlar topilmadi.", show_alert=True)
        return
        
    try:
        with open(history_file, "r", encoding="utf-8") as f:
            sent_messages = json.load(f)
    except Exception:
        sent_messages = []
        
    if not sent_messages:
        await callback_query.answer("❌ O'chirish uchun xabarlar topilmadi.", show_alert=True)
        return

    await callback_query.answer("🗑️ Xabarlarni o'chirish boshlandi. Iltimos kuting...", show_alert=False)
    
    # Hide the button and update message text to indicate deletion process
    try:
        await callback_query.edit_message_text(
            callback_query.message.text + "\n\n⏳ **Xabarlar o'chirilmoqda...**",
            reply_markup=None
        )
    except:
        pass
        
    deleted_count = 0
    failed_count = 0
    
    # Run the deletion in background to avoid blocking callback
    async def process_deletion():
        nonlocal deleted_count, failed_count
        user_client = await get_user_client_started(user_id)
        if not user_client:
            return
            
        for item in sent_messages:
            try:
                await user_client.delete_messages(chat_id=item["chat_id"], message_ids=item["message_id"])
                deleted_count += 1
            except FloodWait as e:
                await asyncio.sleep(e.value + 5)
                try:
                    await user_client.delete_messages(chat_id=item["chat_id"], message_ids=item["message_id"])
                    deleted_count += 1
                except:
                    failed_count += 1
            except Exception:
                failed_count += 1
            await asyncio.sleep(0.5)  # To avoid aggressive flooding while deleting
            
        # Clean up the file
        if os.path.exists(history_file):
            os.remove(history_file)
            
        try:
            await callback_query.message.edit_text(
                callback_query.message.text.replace("⏳ **Xabarlar o'chirilmoqda...**", "") + 
                f"\n\n✅ **Natija:**\n🗑️ Muvaffaqiyatli o'chirildi: **{deleted_count}** ta\n⚠️ O'chirib bo'lmadi: **{failed_count}** ta"
            )
        except:
            pass

    asyncio.create_task(process_deletion())


@bot_app.on_callback_query(filters.regex("^pg:"))
async def pagination_callback(client, callback_query):
    user_id = callback_query.from_user.id
    action = callback_query.data.split(":")[1]

    now = time.time()
    with tasks_lock:
        last_click = pagination_cooldown.get(user_id, 0)
        if now - last_click < PAGINATION_COOLDOWN:
            await callback_query.answer("Juda tez bosyapsiz. Biroz kuting.")
            return
        pagination_cooldown[user_id] = now

    pag = user_pagination.get(user_id)
    if not pag:
        await callback_query.answer("Ro'yxat topilmadi. Qayta oching.", show_alert=True)
        return

    usernames = pag["usernames"]
    page = pag["page"]
    total = len(usernames)
    total_pages = get_total_pages(total)

    if action == "close":
        user_pagination.pop(user_id, None)
        await callback_query.message.delete()
        await callback_query.answer("Yopildi")
        return

    if action == "prev" and page > 0:
        page -= 1
    elif action == "next" and page < total_pages - 1:
        page += 1
    else:
        await callback_query.answer()
        return

    pag["page"] = page
    chunk, start_num, end_num = get_page_slice(usernames, page)
    text = format_user_batch(total, chunk, start_num, end_num)
    keyboard = build_nav_keyboard(page, total)

    await callback_query.message.edit_text(text, reply_markup=keyboard)
    await callback_query.answer()


@bot_app.on_message(filters.command("add_admin") & filters.private)
async def add_admin_command(client, message):
    if not is_super_admin(message.from_user.id):
        return
        
    if len(message.command) < 2:
        await message.reply_text("❌ Foydalanish: `/add_admin <foydalanuvchi_id>`")
        return
        
    try:
        new_admin = int(message.command[1])
        admins = load_admins()
        if new_admin not in admins:
            admins.append(new_admin)
            save_admins(admins)
            await message.reply_text(f"✅ {new_admin} ID'li foydalanuvchi admin etib tayinlandi.\nEndi u ham dashboardni ko'ra oladi va foydalanuvchilarni qabul qilishi mumkin.")
        else:
            await message.reply_text("⚠️ Bu foydalanuvchi allaqachon admin.")
    except:
        await message.reply_text("❌ ID ni to'g'ri raqamda kiriting.")


@bot_app.on_message(filters.command("del_admin") & filters.private)
async def del_admin_command(client, message):
    if not is_super_admin(message.from_user.id):
        return
        
    if len(message.command) < 2:
        await message.reply_text("❌ Foydalanish: `/del_admin <foydalanuvchi_id>`")
        return
        
    try:
        del_admin = int(message.command[1])
        if del_admin == SUPER_ADMIN_ID:
            await message.reply_text("❌ O'zingizni adminlikdan ololmaysiz!")
            return
            
        admins = load_admins()
        if del_admin in admins:
            admins.remove(del_admin)
            save_admins(admins)
            await message.reply_text(f"✅ {del_admin} ID'li foydalanuvchi adminlikdan o'chirildi.")
        else:
            await message.reply_text("⚠️ Bu foydalanuvchi admin emas.")
    except:
        await message.reply_text("❌ ID ni to'g'ri raqamda kiriting.")

@bot_app.on_message(filters.command("ban") & filters.private)
async def ban_command(client, message):
    if not is_super_admin(message.from_user.id) and not is_admin(message.from_user.id):
        return
        
    if len(message.command) < 2:
        await message.reply_text("❌ Foydalanish: `/ban <foydalanuvchi_id>`")
        return
        
    try:
        target_id = int(message.command[1])
        if target_id == SUPER_ADMIN_ID:
            await message.reply_text("❌ Bosh adminni ban qilib bo'lmaydi!")
            return
            
        banned = load_banned()
        if target_id not in banned:
            banned.append(target_id)
            save_banned(banned)
            await message.reply_text(f"✅ `{target_id}` ID'li foydalanuvchi ban qilindi. Endi u botdan umuman foydalana olmaydi.")
        else:
            await message.reply_text("⚠️ Bu foydalanuvchi allaqachon ban qilingan.")
    except:
        await message.reply_text("❌ ID ni to'g'ri raqamda kiriting.")

@bot_app.on_message(filters.command("unban") & filters.private)
async def unban_command(client, message):
    if not is_super_admin(message.from_user.id) and not is_admin(message.from_user.id):
        return
        
    if len(message.command) < 2:
        await message.reply_text("❌ Foydalanish: `/unban <foydalanuvchi_id>`")
        return
        
    try:
        target_id = int(message.command[1])
        banned = load_banned()
        if target_id in banned:
            banned.remove(target_id)
            save_banned(banned)
            await message.reply_text(f"✅ `{target_id}` ID'li foydalanuvchidan ban olib tashlandi.")
        else:
            await message.reply_text("⚠️ Bu foydalanuvchi ban qilinmagan.")
    except:
        await message.reply_text("❌ ID ni to'g'ri raqamda kiriting.")

@bot_app.on_message(filters.command("userinfo") & filters.private)
async def userinfo_command(client, message):
    if not is_super_admin(message.from_user.id) and not is_admin(message.from_user.id):
        return
        
    if len(message.command) < 2:
        await message.reply_text("❌ Foydalanish: `/userinfo <foydalanuvchi_id>`")
        return
        
    try:
        target_id = int(message.command[1])
        try:
            user = await client.get_users(target_id)
            name = f"{user.first_name or ''} {user.last_name or ''}".strip()
            username = f"@{user.username}" if user.username else "Yo'q"
        except:
            name = "Noma'lum"
            username = "Noma'lum"
            
        subs = load_subscriptions()
        has_sub = is_subscribed(target_id)
        sub_info = "❌ Obuna yo'q"
        if has_sub:
            if str(target_id) in subs:
                sub_data = subs[str(target_id)]
                import datetime
                expiry = datetime.datetime.fromtimestamp(sub_data.get('expiry', 0)).strftime('%Y-%m-%d %H:%M')
                sub_info = f"✅ Obuna bor (Tugaydi: {expiry})"
            else:
                sub_info = "✅ VIP (Umrbod)"
                
        is_ban = "🔴 Ha" if is_banned(target_id) else "🟢 Yo'q"
        is_adm = "✅ Ha" if is_admin(target_id) else "❌ Yo'q"
        
        await message.reply_text(
            f"👤 **Foydalanuvchi Ma'lumotlari**\n\n"
            f"🔹 **Ism:** {name}\n"
            f"🔹 **Username:** {username}\n"
            f"🔹 **ID:** `{target_id}`\n\n"
            f"💎 **Obuna holati:** {sub_info}\n"
            f"🛡 **Adminmi?:** {is_adm}\n"
            f"🚫 **Ban qilinganmi?:** {is_ban}"
        )
    except:
        await message.reply_text("❌ ID ni to'g'ri raqamda kiriting.")

@bot_app.on_message(filters.command("users") & filters.private)
async def users_command(client, message):
    if not is_super_admin(message.from_user.id) and not is_admin(message.from_user.id):
        return
        
    await message.reply_text("⏳ Foydalanuvchilar ro'yxati tayyorlanmoqda...")
    
    subs = load_subscriptions()
    admins = load_admins()
    banned = load_banned()
    
    VIP_FILE = os.path.join(DATA_DIR, "vips.json")
    vips = {}
    if os.path.exists(VIP_FILE):
        try:
            with open(VIP_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, list):
                    vips = {str(uid): "Umrbod" for uid in loaded}
                else:
                    vips = loaded
        except:
            pass

    import datetime
    
    lines = ["📊 EMPIRE BOT FOYDALANUVCHILARI\n"]
    
    lines.append(f"👨‍💻 ADMINLAR ({len(admins)} ta):")
    for adm in admins:
        lines.append(f" - {adm}")
        
    lines.append(f"\n💎 VIP FOYDALANUVCHILAR ({len(vips)} ta):")
    for vip_id, data in vips.items():
        if isinstance(data, dict):
            days = data.get("days")
            lines.append(f" - {vip_id} ({days} kunlik)" if days else f" - {vip_id} (Umrbod)")
        else:
            lines.append(f" - {vip_id} (Umrbod)")
            
    lines.append(f"\n🟢 FAOL OBUNACHILAR ({len(subs)} ta):")
    for sub_id, data in subs.items():
        expiry = datetime.datetime.fromtimestamp(data.get('expiry', 0)).strftime('%Y-%m-%d %H:%M')
        source = data.get('source', 'Noma\'lum')
        lines.append(f" - {sub_id} | Tugaydi: {expiry} | Manba: {source}")
        
    lines.append(f"\n🚫 BAN QILINGANLAR ({len(banned)} ta):")
    for ban_id in banned:
        lines.append(f" - {ban_id}")
        
    file_path = os.path.join(DATA_DIR, "users_list.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
        
    await client.send_document(
        chat_id=message.from_user.id,
        document=file_path,
        caption="📋 Barcha foydalanuvchilar ro'yxati.\nUlarni boshqarish uchun `/userinfo`, `/ban`, `/del_member` komandalaridan foydalaning."
    )
    try:
        os.remove(file_path)
    except:
        pass


@bot_app.on_message(filters.command("add_vip") & filters.private)
async def add_vip_command(client, message):
    if not is_super_admin(message.from_user.id):
        return
    
    # Forward qilingan xabardan ID olish
    new_vip = None
    days = None
    
    if message.reply_to_message and message.reply_to_message.forward_from:
        new_vip = message.reply_to_message.forward_from.id
    
    if len(message.command) >= 2:
        try:
            new_vip = int(message.command[1])
        except:
            pass
        # Kunlik muddat: /add_vip 123456 30 (30 kun)
        if len(message.command) >= 3:
            try:
                days = int(message.command[2])
            except:
                pass
    
    if not new_vip:
        await message.reply_text(
            "❌ **Foydalanish:**\n\n"
            "1️⃣ `/add_vip <ID>` — umrbod VIP\n"
            "2️⃣ `/add_vip <ID> <kunlar>` — muddatli VIP (masalan 30 kun)\n"
            "3️⃣ Odam xabarini **forward** qiling va unga reply qilib `/add_vip` yozing\n\n"
            "💡 ID bilmaysizmi? Odam botga kirsin, /start bossin, keyin `/users` bilan ko'ring."
        )
        return
        
    try:
        VIP_FILE = os.path.join(DATA_DIR, "vips.json")
        vips = {}
        if os.path.exists(VIP_FILE):
            try:
                with open(VIP_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    # Eski formatni yangi formatga o'tkazish
                    if isinstance(loaded, list):
                        vips = {str(uid): {"added": time.time(), "days": None} for uid in loaded}
                    else:
                        vips = loaded
            except:
                pass
                
        str_vip = str(new_vip)
        expiry_text = "♾ Umrbod (cheksiz)" if not days else f"📅 {days} kun"
        
        vips[str_vip] = {
            "added": time.time(),
            "days": days,
            "expiry": time.time() + (days * 86400) if days else None
        }
        with open(VIP_FILE, "w", encoding="utf-8") as f:
            json.dump(vips, f, indent=4)
        await message.reply_text(
            f"✅ **VIP qo'shildi!**\n\n"
            f"👤 ID: `{new_vip}`\n"
            f"⏰ Muddat: {expiry_text}\n\n"
            f"Endi unga bot tekin ishlaydi. Dashboard'da ko'rinmaydi."
        )
    except:
        await message.reply_text("❌ Xatolik yuz berdi.")


@bot_app.on_message(filters.command("del_vip") & filters.private)
async def del_vip_command(client, message):
    if not is_super_admin(message.from_user.id):
        return
        
    if len(message.command) < 2:
        await message.reply_text("❌ Foydalanish: `/del_vip <foydalanuvchi_id>`")
        return
        
    try:
        del_vip = str(message.command[1])
        VIP_FILE = os.path.join(DATA_DIR, "vips.json")
        vips = {}
        if os.path.exists(VIP_FILE):
            try:
                with open(VIP_FILE, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, list):
                        vips = {str(uid): {"added": time.time(), "days": None} for uid in loaded}
                    else:
                        vips = loaded
            except:
                pass
                
        if del_vip in vips:
            del vips[del_vip]
            with open(VIP_FILE, "w", encoding="utf-8") as f:
                json.dump(vips, f, indent=4)
            await message.reply_text(f"✅ {del_vip} VIP ro'yxatdan o'chirildi.")
        else:
            await message.reply_text("⚠️ Bu foydalanuvchi VIP emas.")
    except:
        await message.reply_text("❌ ID ni to'g'ri raqamda kiriting.")


@bot_app.on_message(filters.command("add_member") & filters.private)
async def add_member_command(client, message):
    """Lichkadan kelishgan odamga qo'lda obuna berish"""
    user_id = message.from_user.id
    if not is_admin(user_id) and not is_super_admin(user_id):
        return
    
    target_id = None
    days = SUBSCRIPTION_DAYS  # Default: 30 kun
    
    # Forward qilingan xabardan ID olish
    if message.reply_to_message and message.reply_to_message.forward_from:
        target_id = message.reply_to_message.forward_from.id
    
    if len(message.command) >= 2:
        try:
            target_id = int(message.command[1])
        except:
            pass
        if len(message.command) >= 3:
            try:
                days = int(message.command[2])
            except:
                pass
    
    if not target_id:
        await message.reply_text(
            "📋 **OBUNACHI QO'SHISH**\n\n"
            "Lichkadan kelishgan odamga qo'lda obuna berish:\n\n"
            "**Foydalanish:**\n"
            f"1️⃣ `/add_member <ID>` — {SUBSCRIPTION_DAYS} kunga obuna\n"
            "2️⃣ `/add_member <ID> <kunlar>` — belgilangan kunga\n"
            "3️⃣ Odam xabarini forward qilib `/add_member` deb reply qiling\n\n"
            "**Misol:**\n"
            "`/add_member 123456789 30` — 30 kunlik obuna\n"
            "`/add_member 123456789 7` — 1 haftalik sinov\n\n"
            "💡 **ID qanday topiladi?**\n"
            "Odam botga /start bosganida logda chiqadi yoki @userinfobot ga yuboring."
        )
        return
    
    try:
        subs = load_subscriptions()
        str_target = str(target_id)
        
        expiry_time = time.time() + (days * 86400)
        subs[str_target] = {
            "expiry": expiry_time,
            "source": "admin_manual",
            "added_by": user_id,
            "added_at": time.time()
        }
        save_subscriptions(subs)
        
        # Foydalanuvchiga xabar yuborish
        try:
            expiry_date = time.strftime("%Y-%m-%d %H:%M", time.localtime(expiry_time))
            await client.send_message(
                target_id,
                f"🎉 **Tabriklaymiz!**\n\n"
                f"✅ Sizga **{days}** kunlik obuna faollashtirildi!\n"
                f"📅 Amal qilish muddati: `{expiry_date}`\n\n"
                f"Botning barcha funksiyalaridan foydalanishingiz mumkin.\n"
                f"Boshlash uchun /start tugmasini bosing."
            )
        except Exception:
            pass  # Foydalanuvchi botni start qilmagan bo'lishi mumkin
        
        expiry_date = time.strftime("%Y-%m-%d %H:%M", time.localtime(expiry_time))
        await message.reply_text(
            f"✅ **Obuna faollashtirildi!**\n\n"
            f"👤 ID: `{target_id}`\n"
            f"📅 Muddat: **{days}** kun\n"
            f"⏰ Tugash sanasi: `{expiry_date}`\n"
            f"📝 Turi: Qo'lda (admin tomonidan)"
        )
    except Exception as e:
        await message.reply_text(f"❌ Xatolik: {e}")


@bot_app.on_message(filters.command("del_member") & filters.private)
async def del_member_command(client, message):
    """Obunani bekor qilish"""
    user_id = message.from_user.id
    if not is_admin(user_id) and not is_super_admin(user_id):
        return
    
    if len(message.command) < 2:
        await message.reply_text("❌ Foydalanish: `/del_member <ID>`")
        return
    
    try:
        target_id = int(message.command[1])
        subs = load_subscriptions()
        str_target = str(target_id)
        
        if str_target in subs:
            del subs[str_target]
            save_subscriptions(subs)
            await message.reply_text(f"✅ `{target_id}` obunasi bekor qilindi.")
        else:
            await message.reply_text("⚠️ Bu foydalanuvchi obunachi emas.")
    except:
        await message.reply_text("❌ ID ni to'g'ri raqamda kiriting.")


# ================= QOROVUL VA AQLLI SOTUVCHI =================

@bot_app.on_message(filters.group & filters.service)
async def handle_service_messages(client, message):
    """Guruhdagi service xabarlarni o'chiradi va salomlashadi/xayrlashadi"""
    try:
        # Yangi a'zolar qo'shilganda
        if getattr(message, "new_chat_members", None):
            for new_member in message.new_chat_members:
                if new_member.is_bot:
                    continue
                
                name = new_member.first_name or "A'zo"
                mention = f"[{name}](tg://user?id={new_member.id})"
                welcome_text = (
                    f"Assalomu alaykum, Hurmatli {mention}!\n\n"
                    "Bizning Empire oilamizga qo'shilganingizdan xursandmiz. Iltimos, boshqalarni va o'zingizni xurmatingizni saqlang. Istasangiz qonun qoidalar bilan quyida tanishib chiqishingiz mumkin: <link>"
                )
                try:
                    await client.send_message(message.chat.id, welcome_text, disable_web_page_preview=True)
                except:
                    pass

        # A'zo guruhdan chiqqanda
        elif getattr(message, "left_chat_member", None):
            left_member = message.left_chat_member
            if not left_member.is_bot:
                try:
                    await client.send_message(
                        message.chat.id, 
                        "Oilamizni tark etayotganingizdan afsusdamiz. Yana qaytasiz deb umid qilamiz!"
                    )
                except:
                    pass

        # Service xabarning o'zini o'chirish
        await message.delete()
    except:
        pass

@bot_app.on_message(filters.group & filters.text)
async def smart_seller(client, message):
    """Guruhda narx so'raganlarga javob beradi va lichkasiga yozadi"""
    # Botning o'zi yoki boshqa botlar yozsa e'tibor bermaslik
    if not message.from_user or message.from_user.is_bot:
        return
        
    text = message.text.lower()
    
    # Kalit so'zlar
    keywords = ["narx", "qancha", "obuna", "sotib", "to'lov", "tolov", "tarif"]
    if any(word in text for word in keywords):
        try:
            # Avval lichkaga yozishga harakat qilamiz
            await client.send_message(
                message.from_user.id, 
                "💎 **Empire Bot Tariflari:**\n\n"
                "• 1 Oylik obuna - **100 Stars** (yoki **26.000 UZS**)\n\n"
                "Barcha VIP funksiyalar (Scraper, U-Tag, Mass DM) to'liq ochiladi.\n"
                "To'lov qilish yoki sinab ko'rish uchun avval botimizga o'ting va **/start** bosing.\n"
                "Savollaringiz bo'lsa adminga murojaat qiling."
            )
            # Agar lichkaga yozish muvaffaqiyatli bo'lsa, guruhda javob beramiz
            await message.reply_text("Ma'lumotlarni shaxsiy xabaringizga (lichkangizga) yubordim 📩")
        except:
            # Lichka yopiq bo'lsa (botni start qilmagan bo'lsa)
            await message.reply_text("Sizga ma'lumot yuborish uchun iltimos, avval botimizga kirib **/start** bosing!")


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


if __name__ == "__main__":
    print("====================================")
    print(" VENTO SERVER ISHGA TUSHIRILDI ")
    print("====================================")
    print(f"📁 Working directory: {BASE_DIR}")
    print(f"🔑 API_ID: {config.get('API_ID', 'NOT SET')}")
    print(
        f"🔑 API_HASH: {config.get('API_HASH', 'NOT SET')[:10]}..."
        if config.get("API_HASH")
        else "🔑 API_HASH: NOT SET"
    )
    print(
        f"🤖 BOT_TOKEN: {config.get('BOT_TOKEN', 'NOT SET')[:20]}..."
        if config.get("BOT_TOKEN")
        else "🤖 BOT_TOKEN: NOT SET"
    )
    print(f"👥 Admin IDs: {config.get('ADMIN_IDS', 'NOT SET')}")
    print(f"📊 logged_in_users initialized: {logged_in_users}")
    print("🚀 Botni ishga tushirish...")

    import asyncio
    from pyrogram.errors import FloodWait as StartupFloodWait

    async def main():
        retry = 0
        while True:
            try:
                loop = asyncio.get_event_loop()
                loop.create_task(subscription_checker())
                await bot_app.start()
                print("✅ Bot muvaffaqiyatli ishga tushdi!")
                await idle()
                await bot_app.stop()
                break
            except StartupFloodWait as e:
                wait_sec = e.value + 5
                print(f"⏳ Telegram FloodWait: {wait_sec} soniya kutilmoqda (urinish #{retry+1})...")
                await asyncio.sleep(wait_sec)
                retry += 1
            except Exception as e:
                print(f"❌ Startup xatosi: {e}")
                await asyncio.sleep(10)
                retry += 1
                if retry >= 5:
                    print("❌ 5 marta urinib ko'rildi, bot to'xtatildi.")
                    break

    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())

