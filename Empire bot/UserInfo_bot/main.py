import os, json, time, sys, asyncio, re
from dotenv import load_dotenv

load_dotenv()
from datetime import datetime

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from pyrogram import Client, filters
from pyrogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, Message,
    ChatMember, ChatPrivileges
)
from pyrogram.errors import (
    PeerIdInvalid, UsernameNotOccupied, FloodWait,
    UserNotParticipant, ChannelPrivate
)
from pyrogram.enums import ChatMemberStatus, ChatType, UserStatus

# ═══════════════ CONFIG ═══════════════
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

# Squad adminlar — faqat shu odamlar botdan foydalana oladi
SQUAD_ADMINS = [int(x.strip()) for x in os.getenv("SQUAD_ADMINS", "").split(",") if x.strip()]

HISTORY_FILE = os.path.join(DATA_DIR, "user_history.json")
SEARCH_LOG_FILE = os.path.join(DATA_DIR, "search_log.json")
STATS_FILE = os.path.join(DATA_DIR, "user_stats.json")

bot = Client(
    "userinfo_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir=BASE_DIR,
    in_memory=True,
)

# ═══════════════ DATABASE ═══════════════
def load_history():
    if not os.path.exists(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_history(data):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_search_log():
    if not os.path.exists(SEARCH_LOG_FILE):
        return {}
    try:
        with open(SEARCH_LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_search_log(data):
    with open(SEARCH_LOG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_stats():
    if not os.path.exists(STATS_FILE):
        return {}
    try:
        with open(STATS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_stats(data):
    with open(STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def track_user_activity(user_id, chat_id, chat_name, message_type="text", is_reply=False, is_forward=False):
    """Comprehensive user activity tracking"""
    stats = load_stats()
    uid = str(user_id)
    cid = str(chat_id)
    
    if uid not in stats:
        stats[uid] = {
            "total_messages": 0,
            "chats": {},
            "text_messages": 0,
            "media_messages": 0,
            "voice_messages": 0,
            "video_messages": 0,
            "reply_messages": 0,
            "forward_messages": 0,
            "admin_in_chats": [],
            "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
    
    user_stats = stats[uid]
    user_stats["total_messages"] += 1
    user_stats["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    
    # Chat tracking
    if cid not in user_stats["chats"]:
        user_stats["chats"][cid] = {"message_count": 0, "chat_name": chat_name}
    user_stats["chats"][cid]["message_count"] += 1
    user_stats["chats"][cid]["chat_name"] = chat_name  # Update chat name
    
    # Message type tracking
    if message_type == "text":
        user_stats["text_messages"] += 1
    elif message_type == "media":
        user_stats["media_messages"] += 1
    elif message_type == "voice":
        user_stats["voice_messages"] += 1
    elif message_type == "video":
        user_stats["video_messages"] += 1
    
    # Reply and forward tracking
    if is_reply:
        user_stats["reply_messages"] += 1
    if is_forward:
        user_stats["forward_messages"] += 1
    
    stats[uid] = user_stats
    save_stats(stats)

def track_admin_rights(user_id, chat_id, chat_name):
    """Track admin rights in chats"""
    stats = load_stats()
    uid = str(user_id)
    cid = str(chat_id)
    
    if uid not in stats:
        stats[uid] = {
            "total_messages": 0,
            "chats": {},
            "text_messages": 0,
            "media_messages": 0,
            "voice_messages": 0,
            "video_messages": 0,
            "reply_messages": 0,
            "forward_messages": 0,
            "admin_in_chats": [],
            "first_seen": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
    
    if cid not in stats[uid]["admin_in_chats"]:
        stats[uid]["admin_in_chats"].append({
            "chat_id": cid,
            "chat_name": chat_name
        })
    
    save_stats(stats)

def record_user_snapshot(user):
    """Userni databasega yozib qo'yish — ism/username o'zgarishlarni track qilish"""
    history = load_history()
    uid = str(user.id)
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    today = datetime.now().strftime("%Y-%m-%d")

    if uid not in history:
        history[uid] = {"usernames": [], "names": [], "first_seen": now}

    record = history[uid]

    # Username track
    current_username = user.username or ""
    if current_username:
        existing_usernames = [u["value"] for u in record["usernames"]]
        if current_username not in existing_usernames:
            record["usernames"].append({"value": current_username, "date": today})

    # Name track
    full_name = user.first_name or ""
    if user.last_name:
        full_name += " " + user.last_name
    full_name = full_name.strip()

    if full_name:
        existing_names = [n["value"] for n in record["names"]]
        if full_name not in existing_names:
            record["names"].append({"value": full_name, "date": today})

    record["last_seen"] = now
    history[uid] = record
    save_history(history)

def record_search(searcher_id, target_id):
    """Kim kimni qidirgani log"""
    log = load_search_log()
    tid = str(target_id)
    if tid not in log:
        log[tid] = {"count": 0, "searchers": []}
    log[tid]["count"] += 1
    if searcher_id not in log[tid]["searchers"]:
        log[tid]["searchers"].append(searcher_id)
    save_search_log(log)

# ═══════════════ YORDAMCHI ═══════════════
def is_squad(user_id):
    return user_id in SQUAD_ADMINS

def get_status_emoji(status):
    if status == UserStatus.ONLINE:
        return "🟢 Online"
    elif status == UserStatus.RECENTLY:
        return "🔵 Yaqinda"
    elif status == UserStatus.LAST_WEEK:
        return "🟡 Shu hafta"
    elif status == UserStatus.LAST_MONTH:
        return "🟠 Shu oy"
    elif status == UserStatus.LONG_TIME_AGO:
        return "🔴 Uzoq vaqt oldin"
    return "⚪ Noma'lum"

def format_user_info(user, history_data=None, search_count=0):
    """Chiroyli formatda user info - enhanced version with comprehensive statistics"""
    uid = user.id
    full_name = user.first_name or ""
    if user.last_name:
        full_name += " " + user.last_name

    username_link = f"@{user.username}" if user.username else "❌ Yo'q"
    tg_link = f"[{full_name}](tg://user?id={uid})"

    # Status
    status_text = get_status_emoji(user.status) if user.status else "⚪ Noma'lum"

    # Flags
    flags = []
    if user.is_premium:
        flags.append("⭐ Premium")
    if user.is_bot:
        flags.append("🤖 Bot")
    if user.is_verified:
        flags.append("✅ Verified")
    if user.is_scam:
        flags.append("🚫 SCAM")
    if user.is_fake:
        flags.append("⚠️ FAKE")
    if user.is_deleted:
        flags.append("🗑 O'chirilgan")
    if user.is_restricted:
        flags.append("🔒 Cheklangan")

    flags_text = " | ".join(flags) if flags else "Oddiy user"

    # DC ID
    dc_text = f"DC-{user.dc_id}" if user.dc_id else "Noma'lum"

    # Enhanced format - matching the requested style
    text = f"ㅤ{full_name} ({tg_link})\n"
    
    # Status va flags
    text += f"📡 {status_text}"
    if flags:
        text += f" | {flags_text}"
    text += "\n"

    # Statistics from stats file
    stats = load_stats()
    uid_str = str(uid)
    if uid_str in stats:
        user_stats = stats[uid_str]
        total_messages = user_stats.get("total_messages", 0)
        text_messages = user_stats.get("text_messages", 0)
        media_messages = user_stats.get("media_messages", 0)
        reply_messages = user_stats.get("reply_messages", 0)
        voice_messages = user_stats.get("voice_messages", 0)
        video_messages = user_stats.get("video_messages", 0)
        chats = user_stats.get("chats", {})
        num_chats = len(chats)
        admin_chats = user_stats.get("admin_in_chats", [])
        num_admin_chats = len(admin_chats)
        
        # Message diversity calculation
        if total_messages > 0:
            diversity = min(100, round((text_messages + media_messages + reply_messages) / total_messages * 100, 2))
        else:
            diversity = 0
        
        # Reply percentage
        if total_messages > 0:
            reply_percent = round(reply_messages / total_messages * 100, 2)
        else:
            reply_percent = 0
        
        # Media percentage
        if total_messages > 0:
            media_percent = round(media_messages / total_messages * 100, 2)
        else:
            media_percent = 0
        
        text += f"Разнообразие сообщ. {diversity}%\n"
        
        # Date range
        first_seen = user_stats.get("first_seen", "")
        last_seen = user_stats.get("last_seen", "")
        if first_seen and last_seen:
            try:
                first_date = datetime.strptime(first_seen, "%Y-%m-%d %H:%M")
                last_date = datetime.strptime(last_seen, "%Y-%m-%d %H:%M")
                text += f"С {first_date.strftime('%d.%m.%Y')} по {last_date.strftime('%H:%M')}\n"
            except:
                text += f"С {first_seen} по {last_seen}\n"
        
        text += f"{total_messages} сообщений в {num_chats} чатах\n"
        text += f"{reply_percent}% реплай {media_percent}% медиа\n"
        text += f"Кружки: {voice_messages}, голос: {voice_messages}\n"
        
        # Favorite chat (most messages)
        if chats:
            favorite_chat_id = max(chats.keys(), key=lambda k: chats[k]["message_count"])
            favorite_chat_name = chats[favorite_chat_id].get("chat_name", "Noma'lum")
            text += f"Любимый чат: {favorite_chat_name}\n"
        
        # Admin in chats
        if num_admin_chats > 0:
            text += f"Админ в чатах: {num_admin_chats}\n"
    else:
        # History ma'lumotlari (stats bo'lmasa)
        if history_data:
            first_seen = history_data.get("first_seen", "")
            last_seen = history_data.get("last_seen", "")
            if first_seen and last_seen:
                try:
                    first_date = datetime.strptime(first_seen, "%Y-%m-%d %H:%M")
                    last_date = datetime.strptime(last_seen, "%Y-%m-%d %H:%M")
                    text += f"С {first_date.strftime('%d.%m.%Y')} по {last_date.strftime('%H:%M')}\n"
                except:
                    text += f"С {first_seen} по {last_seen}\n"

    # Qidirilganlar soni
    if search_count > 0:
        text += f"Искали: {search_count}\n"

    # DC ID
    text += f"DC: {dc_text}\n"

    # Usernames tarixi
    if history_data:
        usernames = history_data.get("usernames", [])
        if usernames:
            total = len(usernames)
            show = usernames[-3:]  # Oxirgi 3 tasini ko'rsatish
            text += f"\nUsernames: ({len(show)} of {total})\n"
            for u in reversed(show):
                text += f"| @{u['value']}\n"

        # Ism tarixi
        names = history_data.get("names", [])
        if names:
            total = len(names)
            show = names[-3:]
            text += f"\nИмена: ({len(show)} из {total})\n"
            for i, n in enumerate(reversed(show)):
                prefix = "├" if i < len(show) - 1 else "└"
                text += f"{prefix} {n['date']}  ➜  {n['value']}\n"

    # ID va boshqa ma'lumotlar
    text += f"\nID: {uid}\n"
    
    if user.phone_number:
        text += f"📱 Телефон: +{user.phone_number}\n"

    text += f"\n⏰ {datetime.now().strftime('%H:%M')}"

    return text

async def resolve_user_input(client, text):
    """User ID, username yoki forward dan userni topish"""
    text = text.strip()

    # ID bo'lsa
    if text.lstrip("-").isdigit():
        return await client.get_users(int(text))

    # @username
    if text.startswith("@"):
        text = text[1:]

    # t.me/username link
    match = re.search(r"t\.me/([A-Za-z0-9_]+)", text)
    if match:
        text = match.group(1)

    if re.fullmatch(r"[A-Za-z0-9_]{5,32}", text):
        return await client.get_users(text)

    return None

# ═══════════════ HANDLERS ═══════════════
user_states = {}

# Message tracking handlers - track all messages in all chats
@bot.on_message(filters.text & ~filters.private)
async def track_text_message(client, message: Message):
    """Track text messages in groups/channels"""
    if not message.from_user:
        return
    
    chat_name = message.chat.title or message.chat.username or "Unknown"
    is_reply = bool(message.reply_to_message)
    is_forward = bool(message.forward_from or message.forward_from_chat)
    
    track_user_activity(
        message.from_user.id,
        message.chat.id,
        chat_name,
        message_type="text",
        is_reply=is_reply,
        is_forward=is_forward
    )

@bot.on_message(filters.photo & ~filters.private)
async def track_photo_message(client, message: Message):
    """Track photo messages"""
    if not message.from_user:
        return
    
    chat_name = message.chat.title or message.chat.username or "Unknown"
    is_reply = bool(message.reply_to_message)
    is_forward = bool(message.forward_from or message.forward_from_chat)
    
    track_user_activity(
        message.from_user.id,
        message.chat.id,
        chat_name,
        message_type="media",
        is_reply=is_reply,
        is_forward=is_forward
    )

@bot.on_message(filters.video & ~filters.private)
async def track_video_message(client, message: Message):
    """Track video messages"""
    if not message.from_user:
        return
    
    chat_name = message.chat.title or message.chat.username or "Unknown"
    is_reply = bool(message.reply_to_message)
    is_forward = bool(message.forward_from or message.forward_from_chat)
    
    track_user_activity(
        message.from_user.id,
        message.chat.id,
        chat_name,
        message_type="video",
        is_reply=is_reply,
        is_forward=is_forward
    )

@bot.on_message(filters.voice & ~filters.private)
async def track_voice_message(client, message: Message):
    """Track voice messages"""
    if not message.from_user:
        return
    
    chat_name = message.chat.title or message.chat.username or "Unknown"
    is_reply = bool(message.reply_to_message)
    is_forward = bool(message.forward_from or message.forward_from_chat)
    
    track_user_activity(
        message.from_user.id,
        message.chat.id,
        chat_name,
        message_type="voice",
        is_reply=is_reply,
        is_forward=is_forward
    )

@bot.on_message(filters.document & ~filters.private)
async def track_document_message(client, message: Message):
    """Track document messages"""
    if not message.from_user:
        return
    
    chat_name = message.chat.title or message.chat.username or "Unknown"
    is_reply = bool(message.reply_to_message)
    is_forward = bool(message.forward_from or message.forward_from_chat)
    
    track_user_activity(
        message.from_user.id,
        message.chat.id,
        chat_name,
        message_type="media",
        is_reply=is_reply,
        is_forward=is_forward
    )

@bot.on_message(filters.audio & ~filters.private)
async def track_audio_message(client, message: Message):
    """Track audio messages"""
    if not message.from_user:
        return
    
    chat_name = message.chat.title or message.chat.username or "Unknown"
    is_reply = bool(message.reply_to_message)
    is_forward = bool(message.forward_from or message.forward_from_chat)
    
    track_user_activity(
        message.from_user.id,
        message.chat.id,
        chat_name,
        message_type="media",
        is_reply=is_reply,
        is_forward=is_forward
    )

@bot.on_message(filters.sticker & ~filters.private)
async def track_sticker_message(client, message: Message):
    """Track sticker messages"""
    if not message.from_user:
        return
    
    chat_name = message.chat.title or message.chat.username or "Unknown"
    is_reply = bool(message.reply_to_message)
    is_forward = bool(message.forward_from or message.forward_from_chat)
    
    track_user_activity(
        message.from_user.id,
        message.chat.id,
        chat_name,
        message_type="media",
        is_reply=is_reply,
        is_forward=is_forward
    )

@bot.on_message(filters.animation & ~filters.private)
async def track_animation_message(client, message: Message):
    """Track animation (GIF) messages"""
    if not message.from_user:
        return
    
    chat_name = message.chat.title or message.chat.username or "Unknown"
    is_reply = bool(message.reply_to_message)
    is_forward = bool(message.forward_from or message.forward_from_chat)
    
    track_user_activity(
        message.from_user.id,
        message.chat.id,
        chat_name,
        message_type="media",
        is_reply=is_reply,
        is_forward=is_forward
    )

# Admin rights tracking
@bot.on_message(filters.new_chat_members & ~filters.private)
async def track_new_members(client, message: Message):
    """Track when bot is added to a chat and check admin rights"""
    if not message.from_user:
        return
    
    # Check if bot was added
    for member in message.new_chat_members:
        if member.id == bot.me.id:
            # Bot was added, try to get admin status for all members
            try:
                chat_name = message.chat.title or message.chat.username or "Unknown"
                # Track all members' admin rights
                async for member in client.get_chat_members(message.chat.id, limit=100):
                    if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                        if member.user and member.user.id != bot.me.id:
                            track_admin_rights(member.user.id, message.chat.id, chat_name)
            except:
                pass

@bot.on_message(filters.command("start") & filters.private)
async def start_handler(client, message: Message):
    uid = message.from_user.id

    if not is_squad(uid):
        await message.reply_text(
            "🔒 **Yopiq bot**\n\nBu bot faqat Squad a'zolari uchun.",
            quote=True
        )
        return

    record_user_snapshot(message.from_user)

    text = (
        "╔══════════════════════╗\n"
        "   🛡 **SQUAD INTEL BOT**\n"
        "╚══════════════════════╝\n\n"
        "🔍 User haqida to'liq ma'lumot olish uchun:\n\n"
        "**Usullar:**\n"
        "├ 📨 Xabarni **forward** qiling\n"
        "├ 🆔 User **ID** yuboring\n"
        "├ 📛 **@username** yuboring\n"
        "└ 🔗 **t.me/username** link yuboring\n\n"
        "**Buyruqlar:**\n"
        "├ /check `<id yoki @username>` — Tekshirish\n"
        "├ /history `<id>` — Tarix ko'rish\n"
        "├ /stats — Bot statistikasi\n"
        "└ /addadmin `<id>` — Admin qo'shish\n\n"
        "📌 Har safar tekshirilganda username va ism\n"
        "tarixi avtomatik saqlanadi."
    )

    await message.reply_text(text, quote=True)

@bot.on_message(filters.command("check") & filters.private)
async def check_handler(client, message: Message):
    uid = message.from_user.id
    if not is_squad(uid):
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text("❌ Foydalanish: `/check <ID yoki @username>`", quote=True)
        return

    query = parts[1].strip()
    status_msg = await message.reply_text("🔄 **Tekshirilmoqda...**", quote=True)

    try:
        user = await resolve_user_input(client, query)
        if not user:
            await status_msg.edit_text("❌ User topilmadi. ID yoki @username tekshiring.")
            return

        # Snapshotni saqlash
        record_user_snapshot(user)
        record_search(uid, user.id)

        # Historyni olish
        history = load_history()
        history_data = history.get(str(user.id))
        search_log = load_search_log()
        search_count = search_log.get(str(user.id), {}).get("count", 0)

        info_text = format_user_info(user, history_data, search_count)

        # Profil rasm bormi?
        buttons = []
        try:
            photos = []
            async for photo in client.get_chat_photos(user.id, limit=1):
                photos.append(photo)
            if photos:
                buttons.append([InlineKeyboardButton("🖼 Profil rasm", callback_data=f"photo_{user.id}")])
        except:
            pass

        buttons.append([InlineKeyboardButton("🔄 Yangilash", callback_data=f"refresh_{user.id}")])

        markup = InlineKeyboardMarkup(buttons) if buttons else None
        await status_msg.edit_text(info_text, reply_markup=markup, disable_web_page_preview=True)

    except UsernameNotOccupied:
        await status_msg.edit_text("❌ Bunday @username mavjud emas!")
    except PeerIdInvalid:
        await status_msg.edit_text("❌ User topilmadi. Bu ID bilan hech qachon aloqa bo'lmagan.")
    except FloodWait as e:
        await status_msg.edit_text(f"⏳ Telegram limit: {e.value} soniya kuting.")
    except Exception as e:
        await status_msg.edit_text(f"❌ Xatolik: `{e}`")

@bot.on_message(filters.command("history") & filters.private)
async def history_handler(client, message: Message):
    uid = message.from_user.id
    if not is_squad(uid):
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.reply_text("❌ Foydalanish: `/history <ID>`", quote=True)
        return

    target_id = parts[1].strip()
    history = load_history()

    if target_id not in history:
        await message.reply_text(
            f"📭 **ID {target_id}** uchun tarix topilmadi.\n\n"
            "Avval `/check` bilan tekshiring — shunda tarix yozila boshlaydi.",
            quote=True
        )
        return

    data = history[target_id]
    text = f"📜 **TARIX — ID: `{target_id}`**\n\n"

    usernames = data.get("usernames", [])
    if usernames:
        text += f"**📝 Usernames ({len(usernames)}):**\n"
        for u in reversed(usernames):
            text += f"│ @{u['value']}  ·  {u['date']}\n"
        text += "\n"

    names = data.get("names", [])
    if names:
        text += f"**✏️ Ismlar ({len(names)}):**\n"
        for i, n in enumerate(reversed(names)):
            prefix = "├" if i < len(names) - 1 else "└"
            text += f"{prefix} {n['date']}  ➜  {n['value']}\n"
        text += "\n"

    first_seen = data.get("first_seen", "Noma'lum")
    last_seen = data.get("last_seen", "Noma'lum")
    text += f"📅 Birinchi: {first_seen}\n📅 Oxirgi: {last_seen}"

    await message.reply_text(text, quote=True)

@bot.on_message(filters.command("stats") & filters.private)
async def stats_handler(client, message: Message):
    uid = message.from_user.id
    if not is_squad(uid):
        return

    history = load_history()
    search_log = load_search_log()

    total_users = len(history)
    total_searches = sum(v.get("count", 0) for v in search_log.values())
    total_usernames = sum(len(v.get("usernames", [])) for v in history.values())
    total_names = sum(len(v.get("names", [])) for v in history.values())

    # Eng ko'p qidirilgan
    top_searched = sorted(search_log.items(), key=lambda x: x[1].get("count", 0), reverse=True)[:5]

    text = (
        "╔══════════════════════╗\n"
        "   📊 **BOT STATISTIKASI**\n"
        "╚══════════════════════╝\n\n"
        f"👥 Bazadagi userlar: **{total_users}**\n"
        f"🔍 Jami qidiruvlar: **{total_searches}**\n"
        f"📝 Saqlangan usernames: **{total_usernames}**\n"
        f"✏️ Saqlangan ismlar: **{total_names}**\n"
    )

    if top_searched:
        text += "\n**🏆 Eng ko'p qidirilganlar:**\n"
        for i, (tid, info) in enumerate(top_searched, 1):
            text += f"{i}. ID `{tid}` — {info['count']} marta\n"

    text += f"\n⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    await message.reply_text(text, quote=True)

@bot.on_message(filters.command("addadmin") & filters.private)
async def add_admin_handler(client, message: Message):
    uid = message.from_user.id
    if uid != SQUAD_ADMINS[0]:  # Faqat bosh admin
        await message.reply_text("🔒 Faqat bosh admin uchun.", quote=True)
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        await message.reply_text("❌ Foydalanish: `/addadmin <user_id>`", quote=True)
        return

    new_id = int(parts[1].strip())
    if new_id in SQUAD_ADMINS:
        await message.reply_text("✅ Bu user allaqachon squad a'zosi.", quote=True)
        return

    SQUAD_ADMINS.append(new_id)
    await message.reply_text(f"✅ **ID `{new_id}`** squad a'zosi qilib qo'shildi!", quote=True)

@bot.on_message(filters.command("removeadmin") & filters.private)
async def remove_admin_handler(client, message: Message):
    uid = message.from_user.id
    if uid != SQUAD_ADMINS[0]:
        await message.reply_text("🔒 Faqat bosh admin uchun.", quote=True)
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip().isdigit():
        await message.reply_text("❌ Foydalanish: `/removeadmin <user_id>`", quote=True)
        return

    target = int(parts[1].strip())
    if target == SQUAD_ADMINS[0]:
        await message.reply_text("❌ O'zingizni o'chira olmaysiz!", quote=True)
        return

    if target in SQUAD_ADMINS:
        SQUAD_ADMINS.remove(target)
        await message.reply_text(f"✅ **ID `{target}`** squad dan olib tashlandi.", quote=True)
    else:
        await message.reply_text("❌ Bu user squad a'zosi emas.", quote=True)

# Forward qilingan xabarlarni handle qilish
@bot.on_message(filters.forwarded & filters.private)
async def forwarded_handler(client, message: Message):
    uid = message.from_user.id
    if not is_squad(uid):
        return

    if not message.forward_from:
        await message.reply_text(
            "❌ Bu user **Privacy** yoqib qo'ygan.\n"
            "Username yoki ID orqali tekshiring:\n"
            "`/check @username`",
            quote=True
        )
        return

    user = message.forward_from
    status_msg = await message.reply_text("🔄 **Tekshirilmoqda...**", quote=True)

    try:
        # To'liq ma'lumot olish
        full_user = await client.get_users(user.id)
        record_user_snapshot(full_user)
        record_search(uid, full_user.id)

        history = load_history()
        history_data = history.get(str(full_user.id))
        search_log = load_search_log()
        search_count = search_log.get(str(full_user.id), {}).get("count", 0)

        info_text = format_user_info(full_user, history_data, search_count)

        buttons = [[InlineKeyboardButton("🔄 Yangilash", callback_data=f"refresh_{full_user.id}")]]
        await status_msg.edit_text(info_text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)

    except Exception as e:
        # Forward dan olingan ma'lumotlar bilan
        record_user_snapshot(user)
        record_search(uid, user.id)

        history = load_history()
        history_data = history.get(str(user.id))
        search_log = load_search_log()
        search_count = search_log.get(str(user.id), {}).get("count", 0)

        info_text = format_user_info(user, history_data, search_count)
        await status_msg.edit_text(info_text, disable_web_page_preview=True)

# Oddiy text — username yoki ID sifatida tekshirish
@bot.on_message(filters.text & filters.private & ~filters.command(["start", "check", "history", "stats", "addadmin", "removeadmin"]))
async def text_handler(client, message: Message):
    uid = message.from_user.id
    if not is_squad(uid):
        return

    text = message.text.strip()

    # ID yoki username ekanligini aniqlash
    is_id = text.lstrip("-").isdigit()
    is_username = text.startswith("@") or re.fullmatch(r"[A-Za-z0-9_]{5,32}", text)
    is_link = "t.me/" in text

    if not (is_id or is_username or is_link):
        await message.reply_text(
            "🔍 Tekshirish uchun quyidagilardan birini yuboring:\n"
            "├ 📨 Forward xabar\n"
            "├ 🆔 User ID (raqam)\n"
            "├ 📛 @username\n"
            "└ 🔗 t.me/username",
            quote=True
        )
        return

    status_msg = await message.reply_text("🔄 **Tekshirilmoqda...**", quote=True)

    try:
        user = await resolve_user_input(client, text)
        if not user:
            await status_msg.edit_text("❌ User topilmadi.")
            return

        record_user_snapshot(user)
        record_search(uid, user.id)

        history = load_history()
        history_data = history.get(str(user.id))
        search_log = load_search_log()
        search_count = search_log.get(str(user.id), {}).get("count", 0)

        info_text = format_user_info(user, history_data, search_count)

        buttons = [[InlineKeyboardButton("🔄 Yangilash", callback_data=f"refresh_{user.id}")]]
        await status_msg.edit_text(info_text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)

    except UsernameNotOccupied:
        await status_msg.edit_text("❌ Bunday @username mavjud emas!")
    except PeerIdInvalid:
        await status_msg.edit_text("❌ User topilmadi. Bot bu user bilan hech qachon muloqot qilmagan.")
    except FloodWait as e:
        await status_msg.edit_text(f"⏳ Telegram limit: {e.value} soniya kuting.")
    except Exception as e:
        await status_msg.edit_text(f"❌ Xatolik: `{e}`")

# Callback: Yangilash va Profil rasm
@bot.on_callback_query(filters.regex(r"^refresh_(\d+)$"))
async def refresh_callback(client, callback):
    uid = callback.from_user.id
    if not is_squad(uid):
        await callback.answer("🔒 Ruxsat yo'q!", show_alert=True)
        return

    target_id = int(callback.matches[0].group(1))

    try:
        user = await client.get_users(target_id)
        record_user_snapshot(user)

        history = load_history()
        history_data = history.get(str(user.id))
        search_log = load_search_log()
        search_count = search_log.get(str(user.id), {}).get("count", 0)

        info_text = format_user_info(user, history_data, search_count)

        buttons = [[InlineKeyboardButton("🔄 Yangilash", callback_data=f"refresh_{user.id}")]]
        await callback.message.edit_text(info_text, reply_markup=InlineKeyboardMarkup(buttons), disable_web_page_preview=True)
        await callback.answer("✅ Yangilandi!")
    except Exception as e:
        await callback.answer(f"❌ Xatolik: {e}", show_alert=True)

@bot.on_callback_query(filters.regex(r"^photo_(\d+)$"))
async def photo_callback(client, callback):
    uid = callback.from_user.id
    if not is_squad(uid):
        await callback.answer("🔒 Ruxsat yo'q!", show_alert=True)
        return

    target_id = int(callback.matches[0].group(1))
    await callback.answer("📸 Yuborilmoqda...")

    try:
        photos = []
        async for photo in client.get_chat_photos(target_id, limit=5):
            photos.append(photo)

        if photos:
            from pyrogram.types import InputMediaPhoto
            if len(photos) == 1:
                await client.send_photo(callback.message.chat.id, photos[0].file_id, caption=f"👤 ID: `{target_id}` profil rasmi")
            else:
                media = [InputMediaPhoto(p.file_id) for p in photos]
                media[0] = InputMediaPhoto(photos[0].file_id, caption=f"👤 ID: `{target_id}` — {len(photos)} ta rasm")
                await client.send_media_group(callback.message.chat.id, media)
        else:
            await callback.answer("❌ Profil rasm yo'q", show_alert=True)
    except Exception as e:
        await callback.answer(f"❌ {e}", show_alert=True)

# ═══════════════ RUN ═══════════════
print("🛡 Squad Intel Bot ishga tushmoqda...")
bot.run()
