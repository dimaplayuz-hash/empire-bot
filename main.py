"""
Vento Userbot — toza qayta yozilgan versiya.
Barcha buyruqlar saqlangan (AI funksiyalar olib tashlangan).
"""
import asyncio
import gc
import io
import json
import os
import random
import string
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta

import psutil
import pyshorteners
import qrcode
import requests
import wikipedia
from deep_translator import GoogleTranslator
from gtts import gTTS
from pyrogram import Client, filters, utils as pyrogram_utils
from pyrogram.enums import ChatAction, ChatType, ParseMode
from pyrogram.errors import AuthKeyUnregistered, FloodWait, MessageNotModified, PeerIdInvalid
from pyrogram.raw import functions, types
from pyrogram.raw.functions.contacts import Search
from pyrogram.types import ChatPermissions, InlineKeyboardButton, InlineKeyboardMarkup

# Pyrogram 2.0.x eski ID chegaralari yangi kanal/guruhlarda ValueError beradi
pyrogram_utils.MIN_CHANNEL_ID = -1007852516352
pyrogram_utils.MIN_CHAT_ID = -999999999999


def _get_peer_type(peer_id: int) -> str:
    peer_id_str = str(peer_id)
    if not peer_id_str.startswith("-"):
        return "user"
    if peer_id_str.startswith("-100"):
        return "channel"
    return "chat"


pyrogram_utils.get_peer_type = _get_peer_type

# Noma'lum/eskirgan peer yangilanishlarida bot yiqilmasligi uchun
from pyrogram import Client as _PyrogramClient

_orig_handle_updates = _PyrogramClient.handle_updates


async def _safe_handle_updates(self, updates):
    try:
        await _orig_handle_updates(self, updates)
    except ValueError as e:
        if "Peer id invalid" not in str(e):
            raise
    except PeerIdInvalid:
        pass


_PyrogramClient.handle_updates = _safe_handle_updates

from bot_data import (
    STARTUP_BANNER,
    apply_font,
    confetti,
    get_hack_frames,
    get_unhack_frames,
    hearts,
    moons,
    quiz_data,
    zalgo_chars,
)

# ── Sozlama ──────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERBOT_SESSION_DIR = os.path.join(BASE_DIR, "sessions")
os.makedirs(USERBOT_SESSION_DIR, exist_ok=True)

api_id = 36427121
api_hash = "f4b857c7d7e08dce9244615ef32d7cc7"

app = Client(
    "vento_userbot_v2",
    api_id=api_id,
    api_hash=api_hash,
    workdir=USERBOT_SESSION_DIR,
)

from pytgcalls import GroupCallFactory
from pytgcalls.implementation.group_call_base import GroupCallBase

# Avtomatik reconnect'ni o'chiramiz — aks holda FloodWait cheksiz loop hosil qiladi
async def _no_reconnect(self):
    pass

GroupCallBase.reconnect = _no_reconnect

group_call = None

import imageio_ffmpeg as _iio_ff
FFMPEG_PATH = _iio_ff.get_ffmpeg_exe()


def cmd(names):
    if isinstance(names, str):
        names = [names]

    def func(flt, _client, message):
        text = message.text or message.caption
        if not text:
            return False
        for name in flt.names:
            prefix = "." + name
            if text.startswith(prefix):
                if len(text) == len(prefix) or text[len(prefix)].isspace():
                    message.command = [name] + text[len(prefix):].split()
                    return True
        return False

    return filters.create(func, names=names)


async def edit_msg(message, text, **kwargs):
    try:
        if message.from_user and message.from_user.is_self and not message.media:
            return await message.edit_text(text, **kwargs)
        return await message.reply_text(text, **kwargs)
    except Exception:
        try:
            return await message.reply_text(text, **kwargs)
        except Exception:
            return None


def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def parse_delay(time_str):
    time_str = time_str.lower()
    if time_str.endswith("s"):
        return int(time_str[:-1])
    if time_str.endswith("m"):
        return int(time_str[:-1]) * 60
    if time_str.endswith("h"):
        return int(time_str[:-1]) * 3600
    raise ValueError("noto'g'ri vaqt")


def is_complex_name(name):
    score = len(name)
    for char in name:
        if not char.isalnum() and char not in (" ", "-", "_"):
            score += 2
    return score


def estimate_year(uid):
    ranges = [
        (1000000, "2013 yil, Avgust"),
        (10000000, "2013 yil, Oktyabr"),
        (30000000, "2014 yil, Yanvar"),
        (50000000, "2014 yil, Iyul"),
        (100000000, "2015 yil, Mart"),
        (200000000, "2016 yil, Aprel"),
        (300000000, "2017 yil, Mart"),
        (500000000, "2018 yil, Fevral"),
        (800000000, "2019 yil, Yanvar"),
        (1200000000, "2020 yil, Yanvar"),
        (2000000000, "2021 yil, Yanvar"),
        (3500000000, "2022 yil, Yanvar"),
        (5500000000, "2023 yil, Fevral"),
        (6500000000, "2024 yil, Fevral"),
        (7500000000, "2025 yil, Yanvar"),
        (9000000000, "2026 yil, Yanvar"),
    ]
    for max_id, period in ranges:
        if uid < max_id:
            return period
    return "2026 yil (Juda yangi profil)"


# ── Global holat ─────────────────────────────────────────────────────────
start_time = time.time()
wikipedia.set_lang("uz")

is_afk = False
afk_reason = ""
tagging_active = False
autobio_running = False
anti_raid_chats = {}
raid_spammers = {}
message_cache = {}
cleaner_pending = {}
original_profile = {}
hacked_users = set()
anti_flood_active = False
flood_warnings = defaultdict(int)
last_message_time = defaultdict(list)
active_quiz = {}
active_guess = {}
active_rps = {}
ghost_users = set()
double_users = set()
double_msg_map = {}
autotr_data = {"active": False, "lang": "en"}
is_typing = {}
gap_tasks = {}

FLOOD_LIMIT = 5
FLOOD_TIME = 3
STICKERS_FILE = os.path.join(BASE_DIR, "stickers.json")
NOTES_FILE = os.path.join(BASE_DIR, "notes.json")
EDIT_SLOTS_FILE = os.path.join(BASE_DIR, "edit_slots.json")

my_stickers = load_json(STICKERS_FILE)
my_notes = load_json(NOTES_FILE)
edit_slots = load_json(EDIT_SLOTS_FILE)

TAGFUN_PHRASES = [
    "kelarsiz endi kutyabmiz 🤝",
    "kibr bolmasez kelasz 🗿",
    "bildik kotarilibsiz 👍",
    "o'qib otirgandan foyda yo 🫡",
    "koringlar kim keldi 🤩",
    "jimsiz tinchlikmi? 🤔",
    "bizni ham eslab turing 🫂",
    "kelaqoling endi sog'indik 🥺",
    "qachongacha kutamiz ⏳",
    "yana uxlayabsizmi 😴",
    "bir choylashaylik ☕️",
    "profilingizga qarab o'tiribman, kirsangiz o'lamizmi? 💀",
    "guruhda boru, hayotda yo'q odamlar toifasidanmisiz? 👻",
    "sizni ko'rish qiyin bo'lib ketdi, nima, qidiruvdamisiz? 🕵️‍♂️",
    "online bo'la turib yozmaganingiz uchun 5 minut guruhni yuvib bering 🧹",
    "shunchalik band ekansiz, keyingi safar guruhga kirishingizga qizil yo'lakcha to'shaylikmi? 🎪",
    "siz yozguncha sochim oqardi, tezroq kiring ",
    "guruhga bir kiring, sizsiz g'iybatlar qizimayapti 🤫",
    "boyib ketib bizni unutganlar ro'yxatida birinchi o'rindasiz 🪙",
    "tirikligingiz haqida bitta stiker tashlab qo'ying hech bo'lmasa 🧟‍♂️",
    "yozmasangiz ham o'qib o'tirganingizni bilaman, sekin ekranni silliqlayvering 📱",
    "kelajakdan kelgan xabarchi, nega jimsiz? 🚀",
    "biz sizni kutyapmiz, siz esa kimdir bilan lichkada kulishyapsiz, shumi qadrimiz? 🚬",
    "kirsangiz pul beraman (hazil, shunchaki kiring) 💸",
    "xuddi 100 ta proekti bor odamdek bandsiz-a? 👀",
    "guruhga kirishingiz uchun ruxsatnoma kerakmi deyman? 🎫",
    "notiqlik san'ati kurslarida dars beryapsizmi, buncha jimlik? 🎤",
    "siz yozguncha Telegram yangi yangilanish chiqarib yuboradi 🛠️",
    "lichkada dars qilyapsizmi deyman, guruhga ham qarab qo'ying 📚",
    "shuncha odam kutyapti, siz esa kinodagi bosh qahramondek kechikasiz 🎬",
    "guruh faoli degan statusni sotib olgandirsiz balki? 🎖️",
    "bitta 'salom' deb yozish pullik bo'lib qoldimi sizga? 💶",
    "profilingiz boru, lekin o'zingiz arxivda qolib ketgandeksiz📦",
    "sizni chaqiraverib botning ham matoriga kuch keldi 🏍️",
    "guruhga kirib bir 'skrinshot' tushib keting, esdalikka qoladi 📸",
    "chatni faqat o'qish rejimida yoqib qo'yganmisiz? 📖",
    "sizni guruhga olib kirish uchun maxsus taklifnoma jo'nataylikmi? ✉️",
    "siz yozmasangiz guruh quruq cho'lga aylanib ketyapti 🏜️",
    "yozing, internetingiz megabaytini bot to'lab beradi (yolg'on) 🌐",
    "VIP personamiz qayerlarda yuribdilar ekan? 👑",
    "bitta harf yozsangiz ham mayli, tirik ekanligingizni bilaylik 🦕",
    "shuncha odam ichida faqat siz yo'qsiz, svet o'chib qoldimi? 💡",
    "sizni kutib guruhdagilar qarib ketishdi, nabirali bo'ldik mana 🧑‍🦳",
    "lichkangizda navbat ko'pmi deyman, bizga qachon navbat keladi? 🚶‍♂️",
    "guruhga bitta kirib o'ting, baraka kirsin guruhga ✨"
]


# ── Fon handlerlari ──────────────────────────────────────────────────────
@app.on_message(filters.group, group=1)
async def cache_messages(_client, message):
    chat_id = message.chat.id
    if chat_id not in message_cache:
        message_cache[chat_id] = {}
    text = message.text or message.caption or "[Media/Stiker]"
    user_id = message.from_user.id if message.from_user else None
    username = (
        f"@{message.from_user.username}"
        if message.from_user and message.from_user.username
        else "Username yo'q"
    )
    first_name = message.from_user.first_name if message.from_user else "Noma'lum"
    timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    message_cache[chat_id][message.id] = (text, user_id, username, first_name, timestamp)
    if len(message_cache[chat_id]) > 1000:
        for old_id in sorted(message_cache[chat_id].keys())[:100]:
            del message_cache[chat_id][old_id]


@app.on_message(~filters.me & (filters.private | filters.mentioned), group=2)
async def afk_reply(_client, message):
    if is_afk:
        await message.reply_text(
            f"**Avto-javob:**\nHozir bandman 💤\nSabab: {afk_reason}"
        )


@app.on_message(~filters.me & filters.group & ~filters.bot, group=3)
async def check_flood(client, message):
    if not anti_flood_active or not message.from_user:
        return
    user_id = message.from_user.id
    chat_id = message.chat.id
    now = time.time()
    last_message_time[user_id] = [t for t in last_message_time[user_id] if now - t < FLOOD_TIME]
    last_message_time[user_id].append(now)
    if len(last_message_time[user_id]) < FLOOD_LIMIT:
        return
    flood_warnings[(chat_id, user_id)] += 1
    warnings = flood_warnings[(chat_id, user_id)]
    try:
        if warnings == 1:
            await client.send_message(
                chat_id,
                f"⚠️ **Ogohlantirish!** [{message.from_user.first_name}](tg://user?id={user_id}), spam qilmang!",
            )
            await client.delete_messages(chat_id, message.id)
        else:
            await client.restrict_chat_member(
                chat_id,
                user_id,
                ChatPermissions(can_send_messages=False),
                until_date=datetime.now() + timedelta(hours=1),
            )
            await client.send_message(
                chat_id,
                f"🚫 [{message.from_user.first_name}](tg://user?id={user_id}) 1 soatga cheklandi.",
            )
            flood_warnings[(chat_id, user_id)] = 0
    except Exception:
        pass


@app.on_message(filters.new_chat_members, group=4)
async def anti_raid_handler(client, message):
    chat_id = message.chat.id
    if chat_id not in anti_raid_chats or not anti_raid_chats[chat_id]:
        return
    if chat_id not in raid_spammers:
        raid_spammers[chat_id] = []
    for member in message.new_chat_members:
        username = f"@{member.username}" if member.username else "Username yo'q"
        first_name = member.first_name or "Ism yo'q"
        timestamp = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        raid_spammers[chat_id].append((member.id, username, first_name, timestamp))
        try:
            await client.restrict_chat_member(
                chat_id,
                member.id,
                ChatPermissions(
                    can_send_messages=False,
                    can_send_media_messages=False,
                    can_send_other_messages=False,
                    can_add_web_page_previews=False,
                    can_send_polls=False,
                    can_change_info=False,
                    can_invite_users=False,
                    can_pin_messages=False,
                ),
            )
        except Exception:
            try:
                await client.ban_chat_member(chat_id, member.id)
            except Exception:
                pass


@app.on_message(filters.text, group=6)
async def check_quiz_answer(client, message):
    chat_id = message.chat.id
    if chat_id not in active_quiz or not message.text:
        return
    q = active_quiz[chat_id]
    if message.text.strip().lower() in [a.lower() for a in q["alt"]]:
        winner = message.from_user.first_name if message.from_user else "Kimdir"
        await client.send_message(
            chat_id,
            f"🎉 **To'g'ri javob!** {winner} yutdi!\n✅ Javob: **{q['a']}**",
        )
        del active_quiz[chat_id]


@app.on_message(filters.text, group=7)
async def check_guess(client, message):
    chat_id = message.chat.id
    if chat_id not in active_guess:
        return
    game = active_guess[chat_id]
    if not message.reply_to_message or message.reply_to_message.id != game["msg_id"]:
        return
    if not message.text.isdigit():
        return
    user_guess = int(message.text)
    game["attempts"] += 1
    num = game["number"]
    if user_guess == num:
        winner = message.from_user.first_name if message.from_user else "Kimdir"
        await client.send_message(
            chat_id,
            f"🎉 **Tabriklaymiz!** {winner} topdi!\nSon: **{num}**, urinishlar: {game['attempts']}",
        )
        del active_guess[chat_id]
    elif user_guess < num:
        await client.edit_message_text(
            chat_id,
            game["msg_id"],
            f"🔢 Sonni top!\n❌ {user_guess} — **kattaroq** son o'ylaganman!",
        )
    else:
        await client.edit_message_text(
            chat_id,
            game["msg_id"],
            f"🔢 Sonni top!\n❌ {user_guess} — **kichikroq** son o'ylaganman!",
        )
    try:
        await message.delete()
    except Exception:
        pass


@app.on_message(filters.text, group=8)
async def check_rps(client, message):
    chat_id = message.chat.id
    if chat_id not in active_rps:
        return
    game = active_rps[chat_id]
    if not message.reply_to_message or message.reply_to_message.id != game["msg_id"]:
        return
    text = message.text.lower().replace("'", "").replace("'", "").replace("o`", "o").replace("g`", "g")
    if text not in ("tosh", "qaychi", "qogoz", "qog'oz"):
        return
    if text == "qog'oz":
        text = "qogoz"
    user_id = message.from_user.id
    updated = False
    if user_id == game["u1_id"] and not game["u1_choice"]:
        game["u1_choice"] = text
        updated = True
    elif user_id == game["u2_id"] and not game["u2_choice"]:
        game["u2_choice"] = text
        updated = True
    if not updated:
        return
    try:
        await message.delete()
    except Exception:
        pass
    if game["u1_choice"] and game["u2_choice"]:
        c1, c2 = game["u1_choice"], game["u2_choice"]
        u1, u2 = game["u1_name"], game["u2_name"]
        if c1 == c2:
            winner = "🤝 **Durang!**"
        elif (c1, c2) in (("tosh", "qaychi"), ("qaychi", "qogoz"), ("qogoz", "tosh")):
            winner = f"🎉 **G'olib:** {u1}"
        else:
            winner = f"🎉 **G'olib:** {u2}"
        emojis = {"tosh": "🪨 Tosh", "qaychi": "✂️ Qaychi", "qogoz": "📄 Qog'oz"}
        result = (
            f"🎮 **Tosh-Qaychi-Qog'oz tugadi!**\n\n{winner}\n\n"
            f"👤 {u1}: {emojis[c1]}\n👤 {u2}: {emojis[c2]}"
        )
        await client.edit_message_text(chat_id, game["msg_id"], result)
        del active_rps[chat_id]
    else:
        who = game["u1_name"] if game["u1_choice"] else game["u2_name"]
        wait = game["u2_name"] if game["u1_choice"] else game["u1_name"]
        await client.edit_message_text(
            chat_id,
            game["msg_id"],
            f"🎮 **O'yin!**\n✅ {who} tanladi.\n⏳ Navbat: **{wait}**",
        )


@app.on_message(filters.me & filters.text & ~filters.command(["autotr", "help"], prefixes="."), group=9)
async def autotr_interceptor(client, message):
    if not autotr_data["active"] or not message.text or message.text.startswith("."):
        return
    try:
        translated = GoogleTranslator(source="auto", target=autotr_data["lang"]).translate(message.text)
        await message.edit_text(translated)
    except Exception:
        pass


@app.on_message(filters.private & ~filters.me, group=10)
async def ghost_interceptor(client, message):
    if message.from_user and message.from_user.id in ghost_users:
        try:
            await client.forward_messages("me", message.chat.id, message.id)
        except Exception:
            pass


@app.on_message(~filters.me, group=11)
async def double_interceptor(client, message):
    if not message.from_user or message.from_user.id not in double_users:
        return
    try:
        sent = None
        if message.text:
            sent = await client.send_message(message.chat.id, message.text)
        elif message.sticker:
            sent = await client.send_sticker(message.chat.id, message.sticker.file_id)
        if sent:
            double_msg_map[message.id] = (message.chat.id, sent.id)
    except Exception:
        pass


@app.on_deleted_messages(group=12)
async def double_deleted_interceptor(client, messages):
    for msg in messages:
        if msg.id in double_msg_map:
            chat_id, our_id = double_msg_map.pop(msg.id)
            try:
                await client.delete_messages(chat_id, our_id)
            except Exception:
                pass


@app.on_message(filters.me & filters.text & filters.reply, group=13)
async def cleaner_confirm(client, message):
    chat_id = message.chat.id
    if chat_id not in cleaner_pending:
        return
    pending = cleaner_pending[chat_id]
    if not message.reply_to_message or message.reply_to_message.id != pending["message_id"]:
        return
    if message.text.lower() != "y":
        return
    await message.delete()
    deleted_count = inactive_count = failed_count = 0
    for acc in pending["deleted"]:
        try:
            await client.ban_chat_member(chat_id, acc["id"])
            deleted_count += 1
            await asyncio.sleep(0.3)
        except Exception:
            failed_count += 1
    for acc in pending["inactive"]:
        try:
            await client.ban_chat_member(chat_id, acc["id"])
            inactive_count += 1
            await asyncio.sleep(0.3)
        except Exception:
            failed_count += 1
    result = (
        f"✅ **TOZALASH TUGADI!**\n\n"
        f"🗑 O'lik: {deleted_count}\n💀 Faol emas: {inactive_count}\n"
    )
    if failed_count:
        result += f"❌ Xatoliklar: {failed_count}\n"
    await client.send_message(chat_id, result, reply_to_message_id=pending["message_id"])
    del cleaner_pending[chat_id]


# ═══════════════════════ ASOSIY BUYRUQLAR ═══════════════════════
@app.on_message(filters.me & cmd("ping"))
async def ping_cmd(_c, m):
    await edit_msg(m, "Pong! 🏓 Userbot ishlayapti.")


@app.on_message(filters.me & cmd("salom"))
async def salom_cmd(_c, m):
    await edit_msg(m, "Assalomu alaykum! Men o'z ishimni bajarishga tayyorman 🤖")


@app.on_message(filters.me & cmd("yoz"))
async def yoz_cmd(client, m):
    try:
        count = int(m.command[1])
        text = m.text.split(maxsplit=2)[2]
        await m.delete()
        for _ in range(count):
            await client.send_message(m.chat.id, text)
            await asyncio.sleep(0.1)
    except Exception:
        await edit_msg(m, "Xatolik: `.yoz 5 xabar`")


async def _remote_edit_message(client, m, chat_id, msg_id, text):
    try:
        await client.edit_message_text(chat_id, msg_id, text)
        await edit_msg(m, f"✅ Tahrir qilindi!\n`{chat_id}` / `{msg_id}`")
    except Exception as e:
        await edit_msg(m, f"❌ Tahrir bo'lmadi: {e}")


@app.on_message(filters.me & cmd("tahrir"))
async def tahrir_cmd(client, m):
    args = m.command[1:]
    if not args:
        return await edit_msg(
            m,
            "**Mute paytida guruhda yozish:**\n\n"
            "1️⃣ Oldin guruhda `.` yuboring, reply + `.tahrir save`\n"
            "2️⃣ Mute bo'lgach **Saved Messages** ga:\n"
            "   `.tahrir 1 yangi matn`\n\n"
            "Yoki forward qilingan xabarga reply:\n"
            "`.tahrir yangi matn`\n\n"
            "Yoki to'g'ridan-to'g'ri:\n"
            "`.tahrir chat_id msg_id matn`\n\n"
            "`.tahrir list` — saqlangan slotlar",
        )

    if args[0] == "list":
        if not edit_slots:
            return await edit_msg(m, "Slotlar bo'sh. Guruhda `.tahrir save` ishlating.")
        lines = [
            f"**{slot}** → `{data['chat_id']}` / `{data['msg_id']}`"
            for slot, data in sorted(edit_slots.items(), key=lambda x: int(x[0]) if x[0].isdigit() else x[0])
        ]
        return await edit_msg(m, "📌 **Saqlangan slotlar:**\n" + "\n".join(lines))

    if args[0] == "save":
        if not m.reply_to_message:
            return await edit_msg(m, "O'z xabaringizga reply qiling!")
        if not m.reply_to_message.from_user or not m.reply_to_message.from_user.is_self:
            return await edit_msg(m, "Faqat o'z xabaringizni saqlash mumkin!")
        slot = args[1] if len(args) > 1 and args[1].isdigit() else "1"
        edit_slots[slot] = {"chat_id": m.chat.id, "msg_id": m.reply_to_message.id}
        save_json(EDIT_SLOTS_FILE, edit_slots)
        return await edit_msg(
            m,
            f"✅ Slot **{slot}** saqlandi.\n"
            f"Mute bo'lsa Saved Messages ga:\n`.tahrir {slot} matn`",
        )

    if args[0] in edit_slots and len(args) >= 2:
        slot = args[0]
        text = m.text.split(maxsplit=2)[2]
        data = edit_slots[slot]
        return await _remote_edit_message(client, m, data["chat_id"], data["msg_id"], text)

    if m.reply_to_message:
        reply = m.reply_to_message
        text = m.text.split(maxsplit=1)[1]
        if reply.forward_from_chat and reply.forward_from_message_id:
            return await _remote_edit_message(
                client,
                m,
                reply.forward_from_chat.id,
                reply.forward_from_message_id,
                text,
            )
        if reply.from_user and reply.from_user.is_self:
            return await _remote_edit_message(client, m, m.chat.id, reply.id, text)

    if len(args) >= 3 and args[0].lstrip("-").isdigit() and args[1].isdigit():
        chat_id = int(args[0])
        msg_id = int(args[1])
        text = m.text.split(maxsplit=3)[3]
        return await _remote_edit_message(client, m, chat_id, msg_id, text)

    await edit_msg(m, "❌ Noto'g'ri format. `.tahrir` — yordam uchun.")


@app.on_message(filters.me & cmd("ochir"))
async def ochir_cmd(client, m):
    try:
        count = int(m.command[1]) if len(m.command) > 1 else 0
        await m.delete()
        ids, deleted = [], 0
        async for msg in client.get_chat_history(m.chat.id, limit=500):
            if msg.from_user and msg.from_user.is_self:
                ids.append(msg.id)
                deleted += 1
                if len(ids) == 100:
                    await client.delete_messages(m.chat.id, ids)
                    ids = []
                    await asyncio.sleep(1)
                if count > 0 and deleted >= count:
                    break
        if ids:
            await client.delete_messages(m.chat.id, ids)
    except Exception as e:
        await client.send_message("me", f"O'chirishda xatolik: {e}")


@app.on_message(filters.me & cmd("echo"))
async def echo_cmd(client, m):
    if len(m.command) < 2:
        return await edit_msg(m, "❌ `.echo Salom`")
    text = m.text.split(maxsplit=1)[1]
    await m.delete()
    await client.send_message(m.chat.id, text)


@app.on_message(filters.me & cmd("type"))
async def type_cmd(_c, m):
    text = m.text.split(maxsplit=1)[1] if len(m.command) > 1 else "Matn kiritmadingiz!"
    typing_text = ""
    for char in text:
        typing_text += char
        try:
            await m.edit_text(typing_text + "▒")
            await asyncio.sleep(0.1)
        except Exception:
            pass
    await edit_msg(m, typing_text)


@app.on_message(filters.me & cmd("dance"))
async def dance_cmd(_c, m):
    text = m.text.split(maxsplit=1)[1].lower() if len(m.command) > 1 else "matn"
    try:
        for _ in range(5):
            for i, ch in enumerate(text):
                if ch.isalpha():
                    try:
                        await m.edit_text(text[:i] + ch.upper() + text[i + 1 :])
                        await asyncio.sleep(0.3)
                    except FloodWait as e:
                        await asyncio.sleep(e.value)
                    except Exception:
                        pass
        await edit_msg(m, text.capitalize())
    except Exception as e:
        await edit_msg(m, f"Xatolik: {e}")


GAP_SPACER_TIGHT = "⠀"
GAP_SPACER_WIDE = "⠀ ⠀ ⠀ ⠀ ⠀"


def _part_from_message(message):
    if message.sticker:
        return {"type": "sticker", "file_id": message.sticker.file_id}
    if message.text:
        return {"type": "text", "value": message.text}
    if message.caption:
        return {"type": "text", "value": message.caption}
    return None


async def _collect_gap_parts(client, message):
    parts = []

    if message.reply_to_message:
        reply = message.reply_to_message
        if reply.media_group_id:
            group_msgs = [reply]
            async for msg in client.get_chat_history(message.chat.id, limit=50):
                if msg.media_group_id == reply.media_group_id and msg.id != reply.id:
                    group_msgs.append(msg)
            group_msgs.sort(key=lambda x: x.id)
            for msg in group_msgs:
                part = _part_from_message(msg)
                if part:
                    parts.append(part)
        else:
            part = _part_from_message(reply)
            if part:
                parts.append(part)

    if len(message.command) > 1:
        for token in message.text.split(maxsplit=1)[1].split():
            if token.lower() == "stop":
                continue
            if token in my_stickers:
                parts.append({"type": "sticker", "file_id": my_stickers[token]})
            else:
                parts.append({"type": "text", "value": token})

    return parts


async def _gap_text_loop(client, chat_id, parts):
    texts = [p["value"] for p in parts]
    msg = await client.send_message(chat_id, " ".join(texts))
    wide = False
    while True:
        try:
            body = "  ".join(texts) if wide else " ".join(texts)
            await msg.edit_text(body)
            wide = not wide
            await asyncio.sleep(0.45)
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except asyncio.CancelledError:
            raise
        except Exception:
            await asyncio.sleep(0.8)


async def _gap_mixed_loop(client, chat_id, parts):
    spacers = []
    for i, part in enumerate(parts):
        if i > 0:
            spacer = await client.send_message(chat_id, GAP_SPACER_WIDE)
            spacers.append(spacer.id)
        if part["type"] == "text":
            await client.send_message(chat_id, part["value"])
        else:
            await client.send_sticker(chat_id, part["file_id"])

    wide = True
    while True:
        spacer_text = GAP_SPACER_WIDE if wide else GAP_SPACER_TIGHT
        for spacer_id in spacers:
            try:
                await client.edit_message_text(chat_id, spacer_id, spacer_text)
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except asyncio.CancelledError:
                raise
            except Exception:
                pass
        wide = not wide
        await asyncio.sleep(0.45)


async def _run_gap_animation(client, chat_id, parts):
    try:
        if all(p["type"] == "text" for p in parts):
            await _gap_text_loop(client, chat_id, parts)
        else:
            await _gap_mixed_loop(client, chat_id, parts)
    except asyncio.CancelledError:
        pass
    finally:
        if gap_tasks.get(chat_id) is asyncio.current_task():
            gap_tasks.pop(chat_id, None)


@app.on_message(filters.me & cmd("gap"))
async def gap_cmd(client, m):
    chat_id = m.chat.id

    if len(m.command) > 1 and m.command[1].lower() == "stop":
        task = gap_tasks.pop(chat_id, None)
        if task:
            task.cancel()
        return await edit_msg(m, "🛑 Gap animatsiya to'xtatildi.")

    parts = await _collect_gap_parts(client, m)
    if len(parts) < 2:
        return await edit_msg(
            m,
            "Kamida **2 ta** qism kerak!\n\n"
            "`.gap salom dunyo`\n"
            "`.gap stiker1 stiker2` — saqlangan stiker nomlari\n"
            "Stiker(lar)ga reply + `.gap`\n"
            "To'xtatish: `.gap stop`",
        )

    if chat_id in gap_tasks:
        gap_tasks[chat_id].cancel()

    try:
        await m.delete()
    except Exception:
        pass

    task = asyncio.create_task(_run_gap_animation(client, chat_id, parts))
    gap_tasks[chat_id] = task


@app.on_message(filters.me & cmd("tr"))
async def tr_cmd(_c, m):
    try:
        if len(m.command) < 2:
            return await edit_msg(m, "`.tr uz` — reply bilan")
        lang = m.command[1]
        if not m.reply_to_message or not m.reply_to_message.text:
            return await edit_msg(m, "Tarjima uchun xabarga reply qiling.")
        translated = GoogleTranslator(source="auto", target=lang).translate(m.reply_to_message.text)
        await edit_msg(m, f"**Tarjima ({lang}):**\n{translated}")
    except Exception as e:
        await edit_msg(m, f"Tarjima xatoligi: {e}")


@app.on_message(filters.me & cmd("wiki"))
async def wiki_cmd(client, m):
    if len(m.command) < 2:
        return await edit_msg(m, "Nimani qidirishni yozing: `.wiki Toshkent` yoki `.wiki en Python`")
    
    args = m.text.split(maxsplit=2)
    if len(args) > 2 and args[1] in ["uz", "ru", "en"]:
        lang = args[1]
        query = args[2]
    else:
        lang = "uz"
        query = m.text.split(maxsplit=1)[1]
        
    await m.edit_text(f"🔍 {lang.upper()} Vikipediyadan qidirilmoqda...")
    wikipedia.set_lang(lang)
    
    try:
        result = wikipedia.summary(query, sentences=4)
        text = f"**📚 Vikipediya ({lang.upper()}):** {query}\n\n{result}"
        if len(text) > 4000:
            text = text[:4000] + "..."
        await edit_msg(m, text)
    except wikipedia.exceptions.DisambiguationError as e:
        options = ", ".join(e.options[:5]) if e.options else ""
        await edit_msg(m, f"Ko'p ma'noli so'z. Aniqroq yozing. Masalan:\n{options}")
    except wikipedia.exceptions.PageError:
        if lang != "en":
            try:
                wikipedia.set_lang("en")
                result = wikipedia.summary(query, sentences=4)
                text = f"**📚 Vikipediya (EN - {lang} da topilmagani uchun):** {query}\n\n{result}"
                if len(text) > 4000:
                    text = text[:4000] + "..."
                await edit_msg(m, text)
            except Exception:
                await edit_msg(m, "Hech narsa topilmadi 😔")
        else:
            await edit_msg(m, "Hech narsa topilmadi 😔")
    except Exception as e:
        await edit_msg(m, f"Xatolik yuz berdi: {e}")


@app.on_message(filters.me & cmd("afk"))
async def afk_cmd(_c, m):
    global is_afk, afk_reason
    is_afk = True
    afk_reason = m.text.split(maxsplit=1)[1] if len(m.command) > 1 else "Sabab ko'rsatilmagan"
    await edit_msg(m, f"💤 AFK. Sabab: {afk_reason}")


@app.on_message(filters.me & cmd("unafk"))
async def unafk_cmd(_c, m):
    global is_afk, afk_reason
    is_afk = False
    afk_reason = ""
    await edit_msg(m, "✅ AFK dan chiqdingiz!")


@app.on_message(filters.me & cmd("stoptag"))
async def stoptag_cmd(_c, m):
    global tagging_active
    tagging_active = False
    await edit_msg(m, "🛑 Belgilash to'xtatildi!")


@app.on_message(filters.me & cmd(["tagall", "all"]))
async def tagall_cmd(client, m):
    global tagging_active
    if m.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return await edit_msg(m, "Faqat guruhlarda!")
    if tagging_active:
        return await edit_msg(m, "Allaqachon ketyapti! `.stoptag`")
    tagging_active = True
    tag_text = m.text.split(maxsplit=1)[1] if len(m.command) > 1 else ""
    await edit_msg(m, "📢 Belgilash boshlanmoqda... `.stoptag`")
    try:
        members = []
        async for member in client.get_chat_members(m.chat.id, limit=5000):
            if member.user.is_bot or member.user.is_deleted:
                continue
            u = member.user
            # Real @username bor bo'lsa uni ishlatamiz, yo'q bo'lsa invisible mention
            if u.username:
                members.append(f"@{u.username}")
            else:
                name = (u.first_name or "User")[:20].replace("[", "(").replace("]", ")")
                members.append(f"[{name}](tg://user?id={u.id})")

        # Har birini ALOHIDA xabar qilib yuboramiz — xuddi inson qo'lda tag qilgandek
        for mention in members:
            if not tagging_active:
                break
            body = f"{tag_text}\n{mention}" if tag_text else mention
            await client.send_message(m.chat.id, body)
            await asyncio.sleep(1.2)
        tagging_active = False
        await m.delete()
    except FloodWait as e:
        await asyncio.sleep(e.value + 10)
        tagging_active = False
    except Exception as e:
        tagging_active = False
        await client.send_message("me", f"Tagall xato: {e}")


@app.on_message(filters.me & cmd("tagfun"))
async def tagfun_cmd(client, m):
    global tagging_active
    if m.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return await edit_msg(m, "Faqat guruhlarda!")
    if tagging_active:
        return await edit_msg(m, "Allaqachon ketyapti!")
    tagging_active = True
    await edit_msg(m, "🤪 Qiziqarli belgilash...")
    try:
        seen = set()
        async for member in client.get_chat_members(m.chat.id, limit=5000):
            if not tagging_active:
                break
            u = member.user
            if u.is_bot or u.is_deleted or u.id in seen:
                continue
            seen.add(u.id)
            name = (u.first_name or "User").replace("<", "").replace(">", "")
            mention = f"<a href='tg://user?id={u.id}'>{name[:30]}</a>"
            phrase = random.choice(TAGFUN_PHRASES)
            await client.send_message(m.chat.id, f"{mention} {phrase}", parse_mode=ParseMode.HTML)
            await asyncio.sleep(3)
        tagging_active = False
        await m.delete()
    except Exception as e:
        tagging_active = False
        await client.send_message("me", f"Tagfun xato: {e}")


@app.on_message(filters.me & cmd("gtag"))
async def gtag_cmd(client, m):
    global tagging_active
    if m.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return await edit_msg(m, "Faqat guruhlarda!")
    if tagging_active:
        return await edit_msg(m, "Allaqachon ketyapti! `.stoptag`")
    tagging_active = True
    
    text = m.text.split(maxsplit=1)[1] if len(m.command) > 1 else "Diqqat!"
    await edit_msg(m, "👻 Yashirin belgilash boshlandi... `.stoptag`")
    
    try:
        members = []
        async for member in client.get_chat_members(m.chat.id, limit=5000):
            if member.user.is_bot or member.user.is_deleted:
                continue
            members.append(member.user.id)
            
        for i in range(0, len(members), 50):
            if not tagging_active:
                break
            chunk = members[i : i + 50]
            mentions = "".join([f"[\u200b](tg://user?id={uid})" for uid in chunk])
            await client.send_message(m.chat.id, f"{text}{mentions}")
            await asyncio.sleep(2)
            
        tagging_active = False
        await m.delete()
    except FloodWait as e:
        await asyncio.sleep(e.value + 10)
    except Exception as e:
        tagging_active = False
        await client.send_message("me", f"Gtag xato: {e}")


@app.on_message(filters.me & cmd("bombtag"))
async def bombtag_cmd(client, m):
    global tagging_active
    if m.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return await edit_msg(m, "Faqat guruhlarda!")
    if tagging_active:
        return await edit_msg(m, "Allaqachon ketyapti! `.stoptag`")
    tagging_active = True
    await edit_msg(m, "💣 Bomba-belgilash boshlandi... (har biriga bildirishnoma boradi)")
    try:
        async for member in client.get_chat_members(m.chat.id, limit=5000):
            if not tagging_active:
                break
            if member.user.is_bot or member.user.is_deleted:
                continue
            mention = f"[\u200b](tg://user?id={member.user.id})"
            msg = await client.send_message(m.chat.id, f"{mention}🚨")
            await asyncio.sleep(0.3)
            await msg.delete()
            await asyncio.sleep(0.2)
        tagging_active = False
        await edit_msg(m, "✅ Bomba-belgilash tugadi.")
    except Exception as e:
        tagging_active = False
        await client.send_message("me", f"Bombtag xato: {e}")


# ─── SCRAPER: username yig'ib, DM yuborish ───
scraper_collected = []  # global yig'ilgan username list

@app.on_message(filters.me & cmd("scraper"))
async def scraper_cmd(client, m):
    global scraper_collected
    if m.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return await edit_msg(m, "Faqat guruhlarda!")
    
    sub = m.command[1].lower() if len(m.command) > 1 else "scan"
    
    # ─── .scraper scan: guruhdan username yig'ish ───
    if sub == "scan":
        await m.edit_text("🔍 Guruh skanlanmoqda...")
        usernames = []
        no_username = 0
        async for member in client.get_chat_members(m.chat.id, limit=5000):
            u = member.user
            if u.is_bot or u.is_deleted:
                continue
            if u.username:
                usernames.append(f"@{u.username}")
            else:
                no_username += 1
        
        scraper_collected = usernames
        report = (
            f"📊 **Skaner natijasi:**\n"
            f"✅ Username bor: {len(usernames)} ta\n"
            f"❌ Username yo'q: {no_username} ta\n\n"
            + "\n".join(usernames[:50])
            + (f"\n... va yana {len(usernames)-50} ta" if len(usernames) > 50 else "")
        )
        await client.send_message("me", report)
        await edit_msg(m, f"✅ {len(usernames)} ta username topildi va 'Saved Messages' ga yuborildi!\nDM yuborish uchun: `.scraper dm [xabar matni]`")
    
    # ─── .scraper dm [matn]: yig'ilganlarga DM yuborish ───
    elif sub == "dm":
        if not scraper_collected:
            return await edit_msg(m, "⚠️ Avval `.scraper scan` qiling!")
        if len(m.command) < 3:
            return await edit_msg(m, "`.scraper dm [yubormoqchi xabar]`")
        
        msg_text = m.text.split(maxsplit=2)[2]
        total = len(scraper_collected)
        sent = 0
        failed = 0
        
        await m.edit_text(f"🚀 {total} ta odamga DM yuborilmoqda...")
        
        for username in scraper_collected:
            try:
                await client.send_message(username, msg_text)
                sent += 1
                await asyncio.sleep(1.5)  # flood protection
            except FloodWait as e:
                await asyncio.sleep(e.value + 5)
            except Exception:
                failed += 1
        
        stats = (
            f"📨 **DM yuborish natijasi:**\n"
            f"✅ Yuborildi: {sent} ta\n"
            f"❌ Yuborilmadi: {failed} ta\n"
            f"📊 Jami: {total} ta"
        )
        await client.send_message("me", stats)
        await edit_msg(m, f"✅ Yuborildi: **{sent}** | Muvaffaqiyatsiz: **{failed}**")
    
    # ─── .scraper list: yig'ilganlarni ko'rish ───
    elif sub == "list":
        if not scraper_collected:
            return await edit_msg(m, "Hali hech narsa skanlanmagan. `.scraper scan` qiling.")
        text = f"📝 **Yig'ilgan usernames ({len(scraper_collected)} ta):**\n" + "\n".join(scraper_collected[:100])
        if len(scraper_collected) > 100:
            text += f"\n... va yana {len(scraper_collected)-100} ta"
        await edit_msg(m, text)
    
    else:
        await edit_msg(m, "🛠 **Scraper buyruqlari:**\n`.scraper scan` — username yig'ish\n`.scraper list` — ro'yxatni ko'rish\n`.scraper dm [matn]` — hammaga DM yuborish")


@app.on_message(filters.me & cmd("ring"))
async def ring_cmd(client, m):
    global tagging_active
    if m.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return await edit_msg(m, "Faqat guruhlarda!")
    if tagging_active:
        return await edit_msg(m, "Allaqachon ketyapti! `.stoptag`")
    tagging_active = True
    
    count = int(m.command[1]) if len(m.command) > 1 and m.command[1].isdigit() else 5
    count = min(count, 15)  # Limit to 15 rings to avoid flood waits
    
    await edit_msg(m, f"🔔 Zang chalish boshlandi ({count} marta)... `.stoptag`")
    
    try:
        members = []
        async for member in client.get_chat_members(m.chat.id, limit=5000):
            if not member.user.is_bot and not member.user.is_deleted:
                members.append(member.user.id)
                
        # Send rapid tags to create a "ringing/buzzing" effect
        for c in range(count):
            if not tagging_active:
                break
            
            for i in range(0, len(members), 40):
                if not tagging_active:
                    break
                chunk = members[i : i + 40]
                mentions = "".join([f"[\u200b](tg://user?id={uid})" for uid in chunk])
                msg = await client.send_message(m.chat.id, f"☎️{mentions}")
                await msg.delete()
                await asyncio.sleep(0.3)
            await asyncio.sleep(1) # small pause between rings
            
        tagging_active = False
        await edit_msg(m, "✅ Zang chalish tugadi.")
    except FloodWait as e:
        await asyncio.sleep(e.value + 2)
        tagging_active = False
    except Exception as e:
        tagging_active = False
        await client.send_message("me", f"Ring xato: {e}")





@app.on_message(filters.me & cmd("st"))
async def st_cmd(client, m):
    if not m.reply_to_message or not m.reply_to_message.photo:
        return await edit_msg(m, "Rasmga reply qiling!")
    await m.edit_text("⏳ Stiker yasalmoqda...")
    try:
        path = await client.download_media(m.reply_to_message.photo, file_name="temp_sticker.jpg")
        await client.send_document(m.chat.id, path, file_name="sticker.webp", reply_to_message_id=m.reply_to_message.id)
        await m.delete()
        os.remove(path)
    except Exception as e:
        await edit_msg(m, f"Xatolik: {e}")


@app.on_message(filters.me & cmd("time"))
async def time_cmd(_c, m):
    now = datetime.now()
    await edit_msg(m, f"⏱ **Vaqt:** {now.strftime('%H:%M:%S')}\n📅 **Sana:** {now.strftime('%d.%m.%Y')}")


@app.on_message(filters.me & cmd(["weather", "obhavo"]))
async def weather_cmd(client, m):
    if len(m.command) > 1:
        city = m.text.split(maxsplit=1)[1]
    else:
        try:
            ip_info = requests.get("http://ip-api.com/json/", timeout=5).json()
            city = ip_info.get("city", "Tashkent") if ip_info.get("status") == "success" else None
        except Exception:
            city = None
        if not city:
            return await edit_msg(m, "Shahar kiriting: `.weather Toshkent`")
    await m.edit_text("⛅️ Tekshirilmoqda...")
    try:
        req = requests.get(f"https://wttr.in/{city.replace(' ', '+')}?format=%l:+%c+%t,+%w,+Namlik:+%h")
        if req.status_code == 200:
            await client.send_message("me", f"🌍 **Ob-havo ({city}):**\n\n{req.text.strip()}")
            await edit_msg(m, "✅ Saqlangan xabarlarga yuborildi!")
        else:
            await edit_msg(m, "Shahar topilmadi.")
    except Exception:
        await edit_msg(m, "Internet xatosi!")


@app.on_message(filters.me & cmd("count"))
async def count_cmd(client, m):
    if not m.reply_to_message or not m.reply_to_message.from_user:
        return await edit_msg(m, "Foydalanuvchi xabariga reply qiling!")
    target = m.reply_to_message.from_user
    await m.edit_text(f"⏳ **{target.first_name}** hisoblanmoqda...")
    count = 0
    try:
        async for msg in client.search_messages(m.chat.id, query="", from_user=target.id):
            count += 1
    except Exception:
        async for msg in client.get_chat_history(m.chat.id, limit=2000):
            if msg.from_user and msg.from_user.id == target.id:
                count += 1
    await client.send_message("me", f"📊 **{target.first_name}** — {count} ta xabar")
    await edit_msg(m, "✅ Statistika yuborildi!")


@app.on_message(filters.me & cmd("history"))
async def history_cmd(client, m):
    if not m.reply_to_message or not m.reply_to_message.from_user:
        return await edit_msg(m, "Reply qiling!")
    target = m.reply_to_message.from_user
    oldest = None
    try:
        async for msg in client.search_messages(m.chat.id, query="", from_user=target.id):
            oldest = msg
    except Exception:
        async for msg in client.get_chat_history(m.chat.id, limit=2000):
            if msg.from_user and msg.from_user.id == target.id:
                oldest = msg
    if not oldest:
        return await edit_msg(m, "Xabar topilmadi.")
    preview = (oldest.text[:100] + "...") if oldest.text and len(oldest.text) > 100 else (oldest.text or "Media")
    text = (
        f"📜 **Tarix — {target.first_name}**\n📅 {oldest.date.strftime('%d.%m.%Y %H:%M')}\n"
        f"💬 {preview}\n🔗 {oldest.link or 'Havola yoq'}"
    )
    await client.send_message("me", text, disable_web_page_preview=True)
    await edit_msg(m, "✅ Yuborildi!")


@app.on_message(filters.me & cmd("setname"))
async def setname_cmd(client, m):
    if len(m.command) < 2:
        return await edit_msg(m, "`.setname Ism`")
    cool = apply_font(m.text.split(maxsplit=1)[1])
    try:
        await client.update_profile(first_name=cool)
        await edit_msg(m, f"✅ Ism: **{cool}**")
    except Exception as e:
        await edit_msg(m, f"Xatolik: {e}")


def autobio_loop():
    global autobio_running
    while autobio_running:
        try:
            now = datetime.now().strftime("%H:%M")
            try:
                ip = requests.get("http://ip-api.com/json/", timeout=5).json()
                city = ip.get("city", "Tashkent")
            except Exception:
                city = "Tashkent"
            cpu = psutil.cpu_percent()
            bio = f"🕒 {now} | 📍 {city} | 💻 CPU: {cpu}%"
            asyncio.run_coroutine_threadsafe(app.update_profile(bio=bio[:70]), app.loop).result()
            time.sleep(120)
        except FloodWait as e:
            time.sleep(e.value + 10)
        except Exception:
            time.sleep(120)


@app.on_message(filters.me & cmd("autobio"))
async def autobio_cmd(_c, m):
    global autobio_running
    if len(m.command) > 1 and m.command[1] == "on":
        if not autobio_running:
            autobio_running = True
            threading.Thread(target=autobio_loop, daemon=True).start()
        await edit_msg(m, "✅ Auto-Bio yoqildi!")
    elif len(m.command) > 1 and m.command[1] == "off":
        autobio_running = False
        await edit_msg(m, "❌ Auto-Bio o'chirildi.")
    else:
        await edit_msg(m, "`.autobio on` / `.autobio off`")


@app.on_message(filters.me & cmd("save"))
async def save_cmd(_c, m):
    if len(m.command) < 2 or not m.reply_to_message or not m.reply_to_message.sticker:
        return await edit_msg(m, "Stikerga reply: `.save nom`")
    name = m.command[1].lower()
    my_stickers[name] = m.reply_to_message.sticker.file_id
    save_json(STICKERS_FILE, my_stickers)
    await edit_msg(m, f"✅ **{name}** saqlandi! `.s {name}`")


@app.on_message(filters.me & cmd("s"))
async def s_cmd(client, m):
    if len(m.command) < 2:
        return await edit_msg(m, "`.s nom`")
    name = m.command[1].lower()
    if name not in my_stickers:
        return await edit_msg(m, f"❌ **{name}** topilmadi.")
    try:
        await m.delete()
        rid = m.reply_to_message.id if m.reply_to_message else None
        await client.send_sticker(m.chat.id, my_stickers[name], reply_to_message_id=rid)
    except Exception as e:
        await edit_msg(m, f"❌ Xatolik: {e}")


@app.on_message(filters.me & cmd("list"))
async def list_cmd(_c, m):
    if not my_stickers:
        return await edit_msg(m, "Baza bo'sh.")
    text = "📦 **Stikerlar:**\n" + "\n".join(f"• **{k}** (`.s {k}`)" for k in my_stickers)
    await edit_msg(m, text)


@app.on_message(filters.me & cmd("sclear"))
async def sclear_cmd(_c, m):
    my_stickers.clear()
    save_json(STICKERS_FILE, my_stickers)
    await edit_msg(m, "✅ Baza tozalandi!")


@app.on_message(filters.me & cmd("observe"))
async def observe_cmd(client, m):
    if not m.reply_to_message or not m.reply_to_message.from_user:
        return await edit_msg(m, "Reply qiling!")
    u = m.reply_to_message.from_user
    uid = u.id
    
    await m.edit_text("🔍 Chuqur tahlil qilinmoqda...")
    try:
        # Full user data extraction using raw API for deep secrets
        full_user = await client.invoke(functions.users.GetFullUser(id=await client.resolve_peer(uid)))
        raw_u = full_user.users[0]
        f_u = full_user.full_user
        
        try:
            photos = await client.get_chat_photos_count(uid)
        except Exception:
            photos = "?"
            
        common = f_u.common_chats_count
        bio = f_u.about or "Yozilmagan"
        
        dc = raw_u.photo.dc_id if hasattr(raw_u, 'photo') and raw_u.photo else "?"
        dc_map = {1: "Miami 🇺🇸", 2: "Amsterdam 🇳🇱", 4: "Amsterdam 🇳🇱", 5: "Singapur 🇸🇬"}
        dc_name = dc_map.get(dc, "?") if dc != "?" else "?"
        
        mutual = "✅ HA (Sizni kontaktga qo'shgan!)" if getattr(raw_u, 'mutual_contact', getattr(raw_u, 'contact', False)) else "❌ Yo'q"
        scam = "⚠️ HA (Firibgar)" if getattr(raw_u, 'scam', False) else "Yo'q"
        fake = "⚠️ HA (Soxta)" if getattr(raw_u, 'fake', False) else "Yo'q"
        restricted = "⚠️ HA" if getattr(raw_u, 'restricted', False) else "Yo'q"
        reasons = "Yo'q"
        if getattr(raw_u, 'restriction_reason', None):
            reasons = ", ".join([f"{r.reason} ({getattr(r, 'platform', 'all')})" for r in raw_u.restriction_reason])
        
        # Exact online time parsing if available
        status_info = "Yashirilgan / Eski"
        if hasattr(raw_u, 'status') and hasattr(raw_u.status, 'was_online'):
            exact_time = datetime.fromtimestamp(raw_u.status.was_online).strftime('%Y-%m-%d %H:%M:%S')
            status_info = exact_time
        
        uname = f"@{u.username}" if u.username else "Yo'q"
        prem = "Ha" if getattr(raw_u, 'premium', False) else "Yo'q"
        
        info = (
            f"🕵️‍♂️ **CHUQUR TAHLIL (DEEP OBSERVE)**\n\n"
            f"👤 **Ism:** {u.first_name or ''} {u.last_name or ''}\n"
            f"🔗 **Username:** {uname}\n"
            f"🆔 **ID:** `{uid}`\n"
            f"📅 **Taxminiy ro'yxatdan o'tgan:** {estimate_year(uid)}\n\n"
            f"⭐️ **Premium:** {prem}\n"
            f"🏢 **Server (DC):** DC{dc} — {dc_name}\n"
            f"📸 **Rasmlar tarixi:** {photos} ta\n"
            f"👥 **Umumiy chatlar:** {common} ta\n"
            f"📝 **Bio:** `{bio}`\n"
            f"⏱ **Aniq oxirgi faollik:** `{status_info}`\n\n"
            f"📞 **Kontaktda saqlaganmi?:** {mutual}\n"
            f"🚩 **Scam (Firibgar) belgi:** {scam}\n"
            f"👻 **Fake (Soxta) belgi:** {fake}\n"
            f"🚫 **Cheklovlar:** {restricted}\n"
            f"ℹ️ **Cheklov sababi:** `{reasons}`"
        )
        await client.send_message("me", info)
        await edit_msg(m, "✅ Chuqur tahlil 'Saqlangan xabarlar' ga yuborildi!")
    except Exception as e:
        await edit_msg(m, f"❌ Xatolik: {e}")


@app.on_message(filters.me & cmd(["sys", "alive"]))
async def sys_cmd(_c, m):
    up = int(time.time() - start_time)
    h, r = divmod(up, 3600)
    mi, s = divmod(r, 60)
    await edit_msg(
        m,
        f"🤖 **Userbot Faol!**\n⏳ `{h}s {mi}m {s}s`\n"
        f"🧠 CPU: `{psutil.cpu_percent()}%`\n💾 RAM: `{psutil.virtual_memory().percent}%`",
    )


@app.on_message(filters.me & cmd(["tts", "voice"]))
async def voice_cmd(client, m):
    args = m.text.split(maxsplit=2)
    if len(args) < 2:
        return await edit_msg(m, "`.voice matn` yoki `.voice en Hello`")
        
    lang = "ru"
    text = ""
    
    if len(args) > 2 and len(args[1]) <= 3 and args[1].isalpha():
        lang = args[1].lower()
        text = args[2]
    else:
        text = m.text.split(maxsplit=1)[1]
        
    await m.edit_text(f"🎤 Ovoz ({lang})...")
    path = os.path.join(BASE_DIR, "voice.mp3")
    try:
        gTTS(text, lang=lang).save(path)
        rid = m.reply_to_message.id if m.reply_to_message else None
        await client.send_voice(m.chat.id, path, reply_to_message_id=rid)
        await m.delete()
    except Exception as e:
        await edit_msg(m, f"❌ Xatolik: {e}")
    finally:
        if os.path.exists(path):
            os.remove(path)


# ═══════════════════════ ADMIN / XAVFSIZLIK ═══════════════════════
@app.on_message(filters.me & cmd("ban"))
async def ban_cmd(client, m):
    if m.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP) or not m.reply_to_message:
        return await edit_msg(m, "Guruhda reply bilan!")
    try:
        uid = m.reply_to_message.from_user.id
        await client.ban_chat_member(m.chat.id, uid)
        await edit_msg(m, f"🔨 **{m.reply_to_message.from_user.first_name}** ban!")
    except Exception as e:
        await edit_msg(m, f"❌ {e}")


@app.on_message(filters.me & cmd("mute"))
async def mute_cmd(client, m):
    try:
        if m.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
            if not m.reply_to_message:
                return await edit_msg(m, "Reply qiling!")
            uid = m.reply_to_message.from_user.id
            await client.restrict_chat_member(
                m.chat.id, uid, ChatPermissions(can_send_messages=False),
                until_date=datetime.now() + timedelta(hours=1),
            )
            await edit_msg(m, f"🔇 1 soat mute!")
        elif m.chat.type == ChatType.PRIVATE:
            await client.invoke(
                functions.account.UpdateNotifySettings(
                    peer=await client.resolve_peer(m.chat.id),
                    settings=types.InputPeerNotifySettings(mute_until=2147483647),
                )
            )
            await edit_msg(m, "🔇 Bildirishnomalar o'chirildi.")
    except Exception as e:
        await edit_msg(m, f"❌ {e}")


@app.on_message(filters.me & cmd("unmute"))
async def unmute_cmd(client, m):
    try:
        if m.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
            if not m.reply_to_message:
                return await edit_msg(m, "Reply qiling!")
            uid = m.reply_to_message.from_user.id
            await client.restrict_chat_member(m.chat.id, uid, ChatPermissions(can_send_messages=True))
            await edit_msg(m, "🔊 Unmute!")
        elif m.chat.type == ChatType.PRIVATE:
            await client.invoke(
                functions.account.UpdateNotifySettings(
                    peer=await client.resolve_peer(m.chat.id),
                    settings=types.InputPeerNotifySettings(mute_until=0),
                )
            )
            await edit_msg(m, "🔊 Bildirishnomalar yoqildi.")
    except Exception as e:
        await edit_msg(m, f"❌ {e}")


@app.on_message(filters.me & cmd("block"))
async def block_cmd(client, m):
    try:
        uid = m.chat.id if m.chat.type == ChatType.PRIVATE else (
            m.reply_to_message.from_user.id if m.reply_to_message else None
        )
        if uid:
            await client.block_user(uid)
            await edit_msg(m, "🚫 Block qilindi!")
        else:
            await edit_msg(m, "Shaxsiy chat yoki reply kerak.")
    except Exception as e:
        await edit_msg(m, f"❌ {e}")


@app.on_message(filters.me & cmd("unblock"))
async def unblock_cmd(client, m):
    try:
        uid = m.chat.id if m.chat.type == ChatType.PRIVATE else (
            m.reply_to_message.from_user.id if m.reply_to_message else None
        )
        if uid:
            await client.unblock_user(uid)
            await edit_msg(m, "✅ Unblock!")
        else:
            await edit_msg(m, "Shaxsiy chat yoki reply kerak.")
    except Exception as e:
        await edit_msg(m, f"❌ {e}")


@app.on_message(filters.me & cmd("clone"))
async def clone_cmd(client, m):
    global original_profile
    if not m.reply_to_message or not m.reply_to_message.from_user:
        return await edit_msg(m, "Reply qiling!")
    target = m.reply_to_message.from_user
    await m.edit_text("⏳ Klonlanmoqda...")
    try:
        me = await client.get_me()
        if not original_profile:
            original_profile = {
                "first_name": me.first_name or "",
                "last_name": me.last_name or "",
                "bio": (await client.get_chat(me.id)).bio or "",
            }
        info = await client.get_chat(target.id)
        await client.update_profile(
            first_name=target.first_name or "", last_name=target.last_name or "", bio=info.bio or "",
        )
        if target.photo:
            photo = await client.download_media(target.photo.big_file_id)
            await client.set_profile_photo(photo=photo)
            os.remove(photo)
        await edit_msg(m, f"🎭 **{target.first_name}** klonlandi! `.revert` bilan qaytish")
    except Exception as e:
        await edit_msg(m, f"❌ {e}")


@app.on_message(filters.me & cmd("revert"))
async def revert_cmd(client, m):
    if not original_profile:
        return await edit_msg(m, "❌ Eski profil saqlanmagan.")
    try:
        await client.update_profile(**original_profile)
        await edit_msg(m, "✅ Asl profilga qaytdingiz!")
    except Exception as e:
        await edit_msg(m, f"❌ {e}")


@app.on_message(filters.me & cmd("getid"))
async def getid_cmd(_c, m):
    if not m.reply_to_message:
        return await edit_msg(m, "Reply qiling!")
    msg = m.reply_to_message
    fid = msg.photo or msg.sticker or msg.animation or msg.video or msg.document or msg.voice or msg.audio
    if fid:
        await edit_msg(m, f"📁 **ID:** `{fid.file_id}`")
    else:
        await edit_msg(m, "Media topilmadi.")


@app.on_message(filters.me & cmd("password"))
async def password_cmd(_c, m):
    length = int(m.command[1]) if len(m.command) > 1 and m.command[1].isdigit() else 12
    length = max(4, min(100, length))
    chars = string.ascii_letters + string.digits + "!@#$%^&*()"
    pwd = "".join(random.choice(chars) for _ in range(length))
    await edit_msg(m, f"🔐 **Parol ({length}):**\n`{pwd}`")


@app.on_message(filters.me & cmd("reverse"))
async def reverse_cmd(_c, m):
    text = m.text.split(maxsplit=1)[1] if len(m.command) > 1 else None
    if not text and m.reply_to_message:
        text = m.reply_to_message.text or m.reply_to_message.caption
    if not text:
        return await edit_msg(m, "Matn yoki reply kerak.")
    await edit_msg(m, f"🔄 **Teskari:**\n{str(text)[::-1]}")


@app.on_message(filters.me & cmd("bio"))
async def bio_cmd(client, m):
    if len(m.command) < 2:
        return await edit_msg(m, "`.bio matn`")
    bio = m.text.split(maxsplit=1)[1]
    try:
        await client.update_profile(bio=bio)
        await edit_msg(m, f"✅ Bio: `{bio}`")
    except Exception as e:
        await edit_msg(m, f"❌ {e}")


@app.on_message(filters.me & cmd("cinfo"))
async def cinfo_cmd(client, m):
    chat = m.chat
    if chat.type == ChatType.PRIVATE:
        return await edit_msg(m, "Guruh/kanalda ishlaydi.")
    desc = (chat.description or "Yoq")[:100]
    uname = f"@{chat.username}" if chat.username else "Yoq"
    info = (
        f"ℹ️ **{chat.title}**\n🔗 {uname}\n🆔 `{chat.id}`\n"
        f"👥 {chat.members_count or '?'} azo\n📝 {desc}"
    )
    await client.send_message("me", info)
    await edit_msg(m, "✅ Yuborildi!")


@app.on_message(filters.me & cmd("calc"))
async def calc_cmd(_c, m):
    if len(m.command) < 2:
        return await edit_msg(m, "`.calc 5*10`")
    exp = m.text.split(maxsplit=1)[1]
    try:
        result = eval(exp, {"__builtins__": None}, {})
        await edit_msg(m, f"🔢 `{exp}` = `{result}`")
    except Exception:
        await edit_msg(m, "❌ Noto'g'ri ifoda!")


@app.on_message(filters.me & cmd("id"))
async def id_cmd(_c, m):
    text = f"📌 Chat: `{m.chat.id}`\n👤 Siz: `{m.from_user.id}`"
    if m.reply_to_message and m.reply_to_message.from_user:
        text += f"\n🎯 User: `{m.reply_to_message.from_user.id}`\n💬 Msg: `{m.reply_to_message.id}`"
    await edit_msg(m, text)


@app.on_message(filters.me & cmd("antiflood"))
async def antiflood_cmd(_c, m):
    global anti_flood_active
    if len(m.command) > 1 and m.command[1] == "on":
        anti_flood_active = True
        await edit_msg(m, "🛡 Anti-Flood yoqildi!")
    elif len(m.command) > 1 and m.command[1] == "off":
        anti_flood_active = False
        await edit_msg(m, "❌ Anti-Flood o'chirildi.")
    else:
        st = "Yoniq ✅" if anti_flood_active else "O'chiq ❌"
        await edit_msg(m, f"Holat: **{st}**\n`.antiflood on/off`")


@app.on_message(filters.me & cmd("anti-raid"))
async def antiraid_cmd(_c, m):
    if m.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return await edit_msg(m, "Faqat guruhda!")
    chat_id = m.chat.id
    if len(m.command) > 1 and m.command[1] == "on":
        anti_raid_chats[chat_id] = True
        await edit_msg(m, "🛡 Anti-Raid yoqildi!")
    elif len(m.command) > 1 and m.command[1] == "off":
        anti_raid_chats.pop(chat_id, None)
        await edit_msg(m, "✅ Anti-Raid o'chirildi.")
    else:
        await edit_msg(m, "`.anti-raid on/off`")


@app.on_message(filters.me & cmd("raidlist"))
async def raidlist_cmd(client, m):
    chat_id = m.chat.id
    if chat_id not in raid_spammers or not raid_spammers[chat_id]:
        return await edit_msg(m, "📋 Ro'yxat bo'sh.")
    text = f"📋 **Spammerlar** ({len(raid_spammers[chat_id])})\n\n"
    for i, (uid, uname, fname, ts) in enumerate(raid_spammers[chat_id], 1):
        text += f"{i}. **{fname}** `{uid}` {uname} — {ts}\n"
    if len(text) > 4000:
        await client.send_message("me", text)
        await edit_msg(m, "✅ Uzun ro'yxat yuborildi.")
    else:
        await edit_msg(m, text)


@app.on_message(filters.me & cmd("reportraid"))
async def reportraid_cmd(client, m):
    chat_id = m.chat.id
    if chat_id not in raid_spammers or not raid_spammers[chat_id]:
        return await edit_msg(m, "Ro'yxat bo'sh.")
    try:
        chat = await client.get_chat(chat_id)
        title = chat.title or "Guruh"
    except Exception:
        title = "Guruh"
    report = f"🚨 **RAID SHIKOYAT** — {title}\n📊 {len(raid_spammers[chat_id])} spammer\n\n"
    for i, (uid, uname, fname, ts) in enumerate(raid_spammers[chat_id], 1):
        report += f"{i}. {fname} `{uid}` {uname} — {ts}\n"
    await client.send_message("me", report)
    await edit_msg(m, "✅ @spam ga forward qiling.")


@app.on_message(filters.me & cmd("deleted"))
async def deleted_cmd(_c, m):
    chat_id = m.chat.id
    if chat_id not in message_cache or not message_cache[chat_id]:
        return await edit_msg(m, "❌ Kesh bo'sh.")
    target_id = m.reply_to_message.id if m.reply_to_message else None
    if not target_id or target_id not in message_cache[chat_id]:
        return await edit_msg(m, "❌ Keshda topilmadi. Reply bilan urinib ko'ring.")
    text, uid, uname, fname, ts = message_cache[chat_id][target_id]
    await edit_msg(
        m,
        f"🗑 **O'CHIRILGAN XABAR**\n👤 {fname} ({uname})\n🆔 `{uid}`\n⏰ {ts}\n\n💬 {text}",
    )


@app.on_message(filters.me & cmd("scam"))
async def scam_cmd(_c, m):
    if len(m.command) < 2:
        return await edit_msg(m, "`.scam premium` / `.scam delete`")
    kind = m.command[1].lower()
    if kind == "premium":
        target = m.reply_to_message.from_user if m.reply_to_message else m.from_user
        name = target.first_name if target else "User"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("🎁 Faollashtirish", url="https://t.me/spambot")]])
        await edit_msg(
            m,
            f"🎁 **Premium Sovg'a!**\n👤 {name} sizga 1 yillik Premium sovg'a qildi!\n🎉 Oling!",
            reply_markup=kb,
        )
    elif kind == "delete":
        await edit_msg(m, "⚠️ Bu guruh 5 daqiqada o'chiriladi...\nSabab: Spam")
    else:
        await edit_msg(m, "`.scam premium` / `.scam delete`")


@app.on_message(filters.me & cmd("cleaner"))
async def cleaner_cmd(client, m):
    global cleaner_pending
    if m.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return await edit_msg(m, "Faqat guruhda!")
    await m.edit_text("🧹 Skanerlanmoqda...")
    deleted_accs, inactive_accs, total = [], [], 0
    try:
        async for member in client.get_chat_members(m.chat.id, limit=5000):
            total += 1
            if total % 50 == 0:
                try:
                    await m.edit_text(f"🧹 {total} tekshirildi...")
                except Exception:
                    pass
            if member.user.is_deleted:
                deleted_accs.append({"id": member.user.id})
            elif hasattr(member.user, "status"):
                sc = member.user.status.__class__.__name__
                if sc in ("UserStatusOffline", "UserStatusLastMonth", "UserStatusLastWeek"):
                    inactive_accs.append({"id": member.user.id, "name": member.user.first_name or "?"})
            if total % 20 == 0:
                await asyncio.sleep(0.5)
    except FloodWait as e:
        await asyncio.sleep(e.value + 5)
    if not deleted_accs and not inactive_accs:
        return await edit_msg(m, f"✅ {total} tekshirildi — muammo yo'q.")
    cleaner_pending[m.chat.id] = {"message_id": m.id, "deleted": deleted_accs, "inactive": inactive_accs}
    await edit_msg(
        m,
        f"🧹 **Natija** ({total} tekshirildi)\n🗑 O'lik: {len(deleted_accs)}\n"
        f"💀 Faol emas: {len(inactive_accs)}\n\nReply qilib **y** yozing.",
    )


@app.on_message(filters.me & cmd("purge"))
async def purge_cmd(client, m):
    if not m.reply_to_message:
        return await edit_msg(m, "Boshlang'ich xabarga reply qiling!")
    ids = list(range(m.reply_to_message.id, m.id + 1))
    try:
        for i in range(0, len(ids), 100):
            await client.delete_messages(m.chat.id, ids[i : i + 100])
            await asyncio.sleep(0.5)
        info = await client.send_message(m.chat.id, f"🗑 {len(ids)} ta o'chirildi!")
        await asyncio.sleep(2)
        await info.delete()
    except Exception as e:
        await client.send_message("me", f"Purge xato: {e}")


@app.on_message(filters.me & cmd("promote"))
async def promote_cmd(client, m):
    if not m.reply_to_message or not m.reply_to_message.from_user:
        return await edit_msg(m, "Reply qiling!")
    try:
        await client.promote_chat_member(
            m.chat.id, m.reply_to_message.from_user.id,
            privileges=types.ChatAdminRights(
                delete_messages=True, ban_users=True, invite_users=True,
                pin_messages=True, manage_call=True,
            ),
        )
        await edit_msg(m, f"👑 **{m.reply_to_message.from_user.first_name}** admin!")
    except Exception as e:
        await edit_msg(m, f"❌ {e}")


@app.on_message(filters.me & cmd("demote"))
async def demote_cmd(client, m):
    if not m.reply_to_message or not m.reply_to_message.from_user:
        return await edit_msg(m, "Reply qiling!")
    try:
        await client.promote_chat_member(
            m.chat.id, m.reply_to_message.from_user.id, privileges=types.ChatAdminRights(),
        )
        await edit_msg(m, "📉 Adminlik olindi!")
    except Exception as e:
        await edit_msg(m, f"❌ {e}")


@app.on_message(filters.me & cmd("kick"))
async def kick_cmd(client, m):
    if not m.reply_to_message or not m.reply_to_message.from_user:
        return await edit_msg(m, "Reply qiling!")
    uid = m.reply_to_message.from_user.id
    try:
        await client.ban_chat_member(m.chat.id, uid)
        await client.unban_chat_member(m.chat.id, uid)
        await edit_msg(m, "👢 Chiqarildi!")
    except Exception as e:
        await edit_msg(m, f"❌ {e}")


@app.on_message(filters.me & cmd("pin"))
async def pin_cmd(client, m):
    if not m.reply_to_message:
        return await edit_msg(m, "Pin qilinadigan xabarga reply!")
    try:
        await client.pin_chat_message(m.chat.id, m.reply_to_message.id)
        await edit_msg(m, "📌 Pin qilindi!")
    except Exception as e:
        await edit_msg(m, f"❌ {e}")


@app.on_message(filters.me & cmd("loudpin"))
async def loudpin_cmd(client, m):
    if not m.reply_to_message:
        return await edit_msg(m, "Pin qilinadigan xabarga reply qiling!")
    try:
        await client.pin_chat_message(m.chat.id, m.reply_to_message.id, disable_notification=False)
        await edit_msg(m, "📌 Barchaga bildirishnoma bilan pin qilindi!")
    except Exception as e:
        await edit_msg(m, f"❌ {e}")


@app.on_message(filters.me & cmd("unpin"))
async def unpin_cmd(client, m):
    try:
        if m.reply_to_message:
            await client.unpin_chat_message(m.chat.id, m.reply_to_message.id)
        else:
            await client.unpin_all_chat_messages(m.chat.id)
        await edit_msg(m, "📌 Unpin qilindi!")
    except Exception as e:
        await edit_msg(m, f"❌ {e}")


@app.on_message(filters.me & cmd("hack"))
async def hack_cmd(_c, m):
    if not m.reply_to_message or not m.reply_to_message.from_user:
        return await edit_msg(m, "Reply qiling!")
    uid = m.reply_to_message.from_user.id
    name = m.reply_to_message.from_user.first_name or "User"
    if uid in hacked_users:
        return await edit_msg(m, "⚠️ Allaqachon hack! `.unhack`")
    for frame in get_hack_frames(name):
        await edit_msg(m, frame)
        await asyncio.sleep(1.2)
    hacked_users.add(uid)


@app.on_message(filters.me & cmd("unhack"))
async def unhack_cmd(_c, m):
    if not m.reply_to_message or not m.reply_to_message.from_user:
        return await edit_msg(m, "Reply qiling!")
    uid = m.reply_to_message.from_user.id
    name = m.reply_to_message.from_user.first_name or "User"
    if uid not in hacked_users:
        return await edit_msg(m, "Hack qilinmagan.")
    for frame in get_unhack_frames(name):
        await edit_msg(m, frame)
        await asyncio.sleep(1.2)
    hacked_users.discard(uid)


# ═══════════════════════ SCRAPE / O'YINLAR / UTILITA ═══════════════════════
@app.on_message(filters.me & cmd("scrape"))
async def scrape_cmd(client, m):
    limit = int(m.command[1]) if len(m.command) > 1 and m.command[1].isdigit() else 1000
    await m.edit_text(f"⏳ {limit} xabar skanerlanmoqda...")
    users = []
    seen = set()
    async for msg in client.get_chat_history(m.chat.id, limit=limit):
        if msg.from_user and msg.from_user.username and msg.from_user.id not in seen:
            seen.add(msg.from_user.id)
            users.append(f"@{msg.from_user.username}\n")
    if not users:
        return await edit_msg(m, "Username topilmadi.")
    fn = os.path.join(BASE_DIR, "scraped_users.txt")
    with open(fn, "w", encoding="utf-8") as f:
        f.writelines(users)
    await client.send_document(m.chat.id, fn, caption=f"✅ {len(users)} ta user")
    os.remove(fn)


@app.on_message(filters.me & cmd("sendall"))
async def sendall_cmd(client, m):
    if not m.reply_to_message or not m.reply_to_message.document or len(m.command) < 2:
        return await edit_msg(m, "`.txt` faylga reply + `.sendall matn`")
    text = m.text.split(maxsplit=1)[1]
    path = await client.download_media(m.reply_to_message)
    with open(path, "r", encoding="utf-8") as f:
        users = [l.strip() for l in f if l.strip()]
    os.remove(path)
    ok = 0
    for u in users:
        try:
            await client.send_message(u, text)
            ok += 1
            await asyncio.sleep(3)
        except FloodWait as e:
            await asyncio.sleep(e.value + 5)
        except Exception:
            continue
    await edit_msg(m, f"✅ {ok}/{len(users)} ga yuborildi.")


@app.on_message(filters.me & cmd("search"))
async def search_cmd(client, m):
    if len(m.command) < 2:
        return await edit_msg(m, "`.search kalit`")
    kw = m.text.split(maxsplit=1)[1]
    await m.edit_text(f"🔍 '{kw}' qidirilmoqda...")
    try:
        res = await client.invoke(Search(q=kw, limit=20))
        lines = []
        for chat in res.chats:
            if hasattr(chat, "username") and chat.username:
                title = getattr(chat, "title", "Nomsiz")
                lines.append(f"▪️ {title} — @{chat.username}")
        text = f"**🔍 '{kw}':**\n\n" + ("\n".join(lines) if lines else "Topilmadi.")
        await edit_msg(m, text)
    except Exception as e:
        await edit_msg(m, f"❌ {e}")


@app.on_message(filters.me & cmd("quiz"))
async def quiz_cmd(_c, m):
    q = random.choice(quiz_data)
    active_quiz[m.chat.id] = q
    await edit_msg(m, f"❓ **Viktorina!**\n\n{q['q']}\n\n_Javob yozing..._")


@app.on_message(filters.me & cmd("duel"))
async def duel_cmd(client, m):
    if m.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return await edit_msg(m, "Faqat guruhda!")
    timer = 1
    users = []
    for arg in m.command[1:]:
        if arg.startswith("@"):
            users.append(arg)
        elif arg.isdigit():
            timer = int(arg)
    if len(users) >= 2:
        u1, u2 = users[0], users[1]
    elif m.reply_to_message and m.reply_to_message.from_user:
        u1, u2 = m.from_user.first_name, m.reply_to_message.from_user.first_name
    else:
        return await edit_msg(m, "Reply yoki 2 ta @user!")
    await m.delete()
    poll = await client.send_poll(
        m.chat.id,
        f"⚔️ DUEL: {u1} 🆚 {u2} ({timer} daq)",
        [f"🗡 {u1}", f"🛡 {u2}", "🤝 Durang"],
        is_anonymous=False,
    )

    async def announce():
        await asyncio.sleep(timer * 60)
        try:
            msg = await client.get_messages(m.chat.id, poll.id)
            if not msg.poll:
                return
            best = max(msg.poll.options, key=lambda o: o.voter_count)
            await client.send_message(m.chat.id, f"🏆 G'olib: **{best.text}** ({best.voter_count} ovoz)")
            await client.stop_poll(m.chat.id, poll.id)
        except Exception:
            pass

    asyncio.create_task(announce())


@app.on_message(filters.me & cmd("slot"))
async def slot_cmd(_c, m):
    sym = ["🍒", "🍋", "🔔", "💎", "7️⃣", "🍉", "⭐"]
    await m.edit_text("🎰 Aylanmoqda...")
    for _ in range(3):
        s = random.choices(sym, k=3)
        try:
            await m.edit_text(f"🎰 | {s[0]} | {s[1]} | {s[2]} |")
            await asyncio.sleep(0.4)
        except Exception:
            pass
    s = random.choices(sym, k=3)
    if s[0] == s[1] == s[2]:
        res = f"🎰 | {s[0]} | {s[1]} | {s[2]} |\n\n🎉 **YUTUQ!**"
    elif s[0] == s[1] or s[1] == s[2] or s[0] == s[2]:
        res = f"🎰 | {s[0]} | {s[1]} | {s[2]} |\n\n😏 Deyarli!"
    else:
        res = f"🎰 | {s[0]} | {s[1]} | {s[2]} |\n\n😔 Omad yo'q."
    await edit_msg(m, res)


@app.on_message(filters.me & cmd("guess"))
async def guess_cmd(_c, m):
    msg = await m.edit_text("🔢 1-100 son o'yladim! Reply bilan toping.")
    active_guess[m.chat.id] = {"number": random.randint(1, 100), "attempts": 0, "msg_id": msg.id}


@app.on_message(filters.me & cmd("game"))
async def game_cmd(_c, m):
    if not m.reply_to_message or not m.reply_to_message.from_user:
        return await edit_msg(m, "Reply qiling!")
    u1, u2 = m.from_user, m.reply_to_message.from_user
    if u1.id == u2.id:
        return await edit_msg(m, "O'zingiz bilan emas!")
    msg = await m.edit_text(
        f"🎮 **Tosh-Qaychi-Qog'oz**\n{u1.first_name} 🆚 {u2.first_name}\n\n"
        f"Reply: `tosh`, `qaychi`, `qog'oz`"
    )
    active_rps[m.chat.id] = {
        "msg_id": msg.id, "u1_id": u1.id, "u1_name": u1.first_name,
        "u2_id": u2.id, "u2_name": u2.first_name,
        "u1_choice": None, "u2_choice": None,
    }


@app.on_message(filters.me & cmd("mind"))
async def mind_cmd(client, m):
    if not m.reply_to_message or not m.reply_to_message.from_user:
        return await edit_msg(m, "Reply qiling!")
    user = m.reply_to_message.from_user
    count = min(int(m.command[1]), 20) if len(m.command) > 1 and m.command[1].isdigit() else 5
    mention = f"[{user.first_name}](tg://user?id={user.id})"
    await m.edit_text(f"🔔 **{user.first_name}** chaqirilmoqda...")
    for _ in range(count):
        try:
            msg = await client.send_message(m.chat.id, f"🔔 {mention}, muhim!", disable_web_page_preview=True)
            await asyncio.sleep(1)
            await msg.delete()
            await asyncio.sleep(0.5)
        except Exception as e:
            await client.send_message("me", f"mind xato: {e}")
            break
    await client.send_message(m.chat.id, f"✅ {count} marta chaqirildi.")


@app.on_message(filters.me & cmd("qr"))
async def qr_cmd(client, m):
    data = None
    if len(m.command) > 1:
        data = m.text.split(maxsplit=1)[1]
    elif m.reply_to_message:
        data = m.reply_to_message.link or f"https://t.me/c/{str(m.chat.id).replace('-100', '')}/{m.reply_to_message.id}"
    if not data:
        return await edit_msg(m, "`.qr havola` yoki reply")
    await m.edit_text("📱 QR yaratilmoqda...")
    try:
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        buf.name = "qr.png"
        await client.send_photo(m.chat.id, buf, caption=f"📱 `{data[:50]}`")
        await m.delete()
    except Exception as e:
        await edit_msg(m, f"❌ {e}")


@app.on_message(filters.me & cmd("shorten"))
async def shorten_cmd(_c, m):
    if len(m.command) < 2:
        return await edit_msg(m, "`.shorten url`")
    url = m.command[1]
    s = pyshorteners.Shortener()
    try:
        short = s.tinyurl.short(url)
    except Exception:
        try:
            short = s.isgd.short(url)
        except Exception as e:
            return await edit_msg(m, f"❌ {e}")
    await edit_msg(m, f"🔗 `{short}`")


@app.on_message(filters.me & cmd("remind"))
async def remind_cmd(client, m):
    if len(m.command) < 3:
        return await edit_msg(m, "`.remind 10m matn` (s/m/h)`")
    try:
        delay = parse_delay(m.command[1])
        text = m.text.split(maxsplit=2)[2]
    except Exception:
        return await edit_msg(m, "Vaqt: `10s`, `5m`, `2h`")
    chat_id = m.chat.id

    async def task():
        await asyncio.sleep(delay)
        try:
            await client.send_message(chat_id, f"⏰ **Eslatma!**\n\n{text}")
        except Exception:
            pass

    asyncio.create_task(task())
    disp = f"{delay}s" if delay < 60 else f"{delay // 60}m" if delay < 3600 else f"{delay // 3600}h"
    await edit_msg(m, f"✅ {disp} dan keyin eslataman:\n_{text}_")


@app.on_message(filters.me & cmd("note"))
async def note_cmd(_c, m):
    if len(m.command) == 1:
        if not my_notes:
            return await edit_msg(m, "Qayd yo'q. `.note nom matn`")
        text = "📝 **Qaydlar:**\n" + "\n".join(f"• **{k}**" for k in my_notes)
        return await edit_msg(m, text)
    if len(m.command) == 2:
        val = my_notes.get(m.command[1].lower())
        return await edit_msg(m, val or "❌ Topilmadi.")
    name = m.command[1].lower()
    content = m.text.split(maxsplit=2)[2]
    my_notes[name] = content
    save_json(NOTES_FILE, my_notes)
    await edit_msg(m, f"✅ **{name}** saqlandi!")


@app.on_message(filters.me & cmd("currency"))
async def currency_cmd(_c, m):
    if len(m.command) < 4:
        return await edit_msg(m, "`.currency 100 USD UZS`")
    try:
        amt = float(m.command[1])
        c1, c2 = m.command[2].upper(), m.command[3].upper()
        rates = requests.get(f"https://api.exchangerate-api.com/v4/latest/{c1}", timeout=10).json()
        result = amt * rates["rates"][c2]
        await edit_msg(m, f"💱 {amt} {c1} = **{result:.2f}** {c2}")
    except Exception as e:
        await edit_msg(m, f"❌ {e}")


# ═══════════════════════ VIZUAL EFFEKTLAR ═══════════════════════
MATRIX_CHARS = 'ﾊﾐﾋｰｳｼﾅﾓﾆｻﾜﾂｵﾘｱﾎﾃﾏｹﾒｴｶｷﾑﾕﾗｾﾈｽﾀﾇﾍ012345789Z:."=*+-<>¦|_'


@app.on_message(filters.me & cmd("matrix"))
async def matrix_cmd(_c, m):
    try:
        for _ in range(8):
            lines = ["".join(random.choices(MATRIX_CHARS, k=20)) for _ in range(6)]
            await m.edit_text("🟢 **MATRIX**\n\n" + "\n".join(f"`{l}`" for l in lines))
            await asyncio.sleep(0.5)
        await edit_msg(m, "🟢 **MATRIX** — _Wake up, Neo..._")
    except Exception as e:
        await edit_msg(m, f"Xatolik: {e}")


@app.on_message(filters.me & cmd("fire"))
async def fire_cmd(_c, m):
    text = m.text.split(maxsplit=1)[1] if len(m.command) > 1 else "FIRE"
    frames = [
        f"🔥🔥🔥\n🔥 {text} 🔥\n🔥🔥🔥",
        f"💥💥💥\n💥 {text} 💥\n💥💥💥",
        f"🌋🌋🌋\n🌋 {text} 🌋\n🌋🌋🌋",
        f"🔥 **{text}** 🔥",
    ]
    for f in frames:
        try:
            await m.edit_text(f)
            await asyncio.sleep(0.6)
        except Exception:
            pass


@app.on_message(filters.me & cmd("glitch"))
async def glitch_cmd(_c, m):
    text = m.text.split(maxsplit=1)[1] if len(m.command) > 1 else "GLITCH"
    try:
        for intensity in range(1, 6):
            glitched = "".join(c + "".join(random.choice(zalgo_chars) for _ in range(intensity)) for c in text)
            await m.edit_text(glitched)
            await asyncio.sleep(0.5)
        final = "".join(c + "".join(random.choice(zalgo_chars) for _ in range(8)) for c in text)
        await edit_msg(m, f"**{final}**")
    except Exception:
        pass


@app.on_message(filters.me & cmd("happy"))
async def happy_cmd(_c, m):
    text = m.text.split(maxsplit=1)[1] if len(m.command) > 1 else "Tabriklaymiz"
    padded = " " * 15 + text + " " * 15
    try:
        for i in range(len(padded) - 15):
            window = padded[i : i + 15]
            try:
                await m.edit_text(f"{random.choice(confetti)} `{window}` {random.choice(confetti)}")
            except (FloodWait, MessageNotModified):
                pass
            await asyncio.sleep(0.3)
        await edit_msg(m, f"🎉🎊 **{text}!!!** 🎊🎉")
    except Exception as e:
        await edit_msg(m, f"❌ {e}")


@app.on_message(filters.me & cmd("heart"))
async def heart_cmd(_c, m):
    try:
        for _ in range(15):
            try:
                await m.edit_text(random.choice(hearts))
            except (FloodWait, MessageNotModified):
                pass
            await asyncio.sleep(0.3)
        await edit_msg(m, "❤️")
    except Exception as e:
        await edit_msg(m, f"❌ {e}")


@app.on_message(filters.me & cmd("moon"))
async def moon_cmd(_c, m):
    try:
        for _ in range(3):
            for moon in moons:
                await m.edit_text(moon)
                await asyncio.sleep(0.2)
        await edit_msg(m, "🌝")
    except Exception:
        pass


@app.on_message(filters.me & cmd("magic"))
async def magic_cmd(_c, m):
    text = m.text.split(maxsplit=1)[1] if len(m.command) > 1 else "MAGIC"
    try:
        for i in range(len(text)):
            await m.edit_text(text[:i] + "✨" + text[i + 1 :])
            await asyncio.sleep(0.3)
        await edit_msg(m, f"✨ {text} ✨")
    except Exception:
        pass


# ═══════════════════════ SUPER WOW ═══════════════════════
@app.on_message(filters.me & cmd("burn"))
async def burn_cmd(client, m):
    if len(m.command) < 3 or not m.command[1].isdigit():
        return await edit_msg(m, "`.burn 5 sirli xabar`")
    sec = int(m.command[1])
    text = m.text.split(maxsplit=2)[2]
    try:
        msg = await m.edit_text(f"🤫 **Maxfiy:**\n{text}\n⏳ {sec}s...")
        for i in range(sec - 1, 0, -1):
            await client.edit_message_text(m.chat.id, msg.id, f"🤫 {text}\n⏳ {i}s...")
            await asyncio.sleep(1)
        await client.edit_message_text(m.chat.id, msg.id, "💥 Portladi!")
        await asyncio.sleep(0.5)
        await msg.delete()
    except Exception:
        pass


@app.on_message(filters.me & cmd("dox"))
async def dox_cmd(client, m):
    if not m.reply_to_message or not m.reply_to_message.from_user:
        return await edit_msg(m, "Reply qiling!")
    u = m.reply_to_message.from_user
    msg = await m.edit_text(f"🔍 **{u.first_name}** skanerlanmoqda...")
    await asyncio.sleep(1.5)
    ip = f"{random.randint(11,255)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"
    device = random.choice(["iPhone 15", "Samsung S24", "MacBook Pro", "Windows 11"])
    text = (
        f"🎯 **TARGET: {u.first_name}**\n\n🌐 IP: `{ip}`\n📱 Device: `{device}`\n"
        f"📍 GPS: `{random.uniform(41,42):.4f}, {random.uniform(69,70):.4f}`\n\n"
        f"⚠️ _Fake intel — ko'ngilochar_"
    )
    await client.edit_message_text(m.chat.id, msg.id, text)


@app.on_message(filters.me & cmd("typing"))
async def typing_cmd(client, m):
    cid = m.chat.id
    if is_typing.get(cid):
        is_typing[cid] = False
        await edit_msg(m, "🛑 Typing to'xtatildi!")
        return
    is_typing[cid] = True
    await edit_msg(m, "⏳ Typing yoqildi. Yana `.typing` bilan o'chiring.")

    async def loop():
        while is_typing.get(cid):
            try:
                await client.send_chat_action(cid, ChatAction.TYPING)
                await asyncio.sleep(4)
            except Exception:
                break

    asyncio.create_task(loop())


@app.on_message(filters.me & cmd("autotr"))
async def autotr_cmd(_c, m):
    if len(m.command) > 1:
        if m.command[1].lower() == "off":
            autotr_data["active"] = False
            await edit_msg(m, "✅ AutoTR o'chirildi.")
        else:
            autotr_data["active"] = True
            autotr_data["lang"] = m.command[1]
            await edit_msg(m, f"✅ AutoTR: {m.command[1]}")
    else:
        await edit_msg(m, "`.autotr en` / `.autotr off`")


@app.on_message(filters.me & cmd("ghost"))
async def ghost_cmd(_c, m):
    if len(m.command) > 1 and m.command[1] == "clear":
        ghost_users.clear()
        return await edit_msg(m, "✅ Ghost tozalandi.")
    if not m.reply_to_message or not m.reply_to_message.from_user:
        return await edit_msg(m, "Reply qiling!")
    uid = m.reply_to_message.from_user.id
    if uid in ghost_users:
        ghost_users.remove(uid)
        await edit_msg(m, "👻 Ghost o'chirildi.")
    else:
        ghost_users.add(uid)
        await edit_msg(m, "👻 Ghost yoqildi (o'qish bildirmasdan).")


@app.on_message(filters.me & cmd("double"))
async def double_cmd(_c, m):
    if len(m.command) > 1 and m.command[1] == "clear":
        double_users.clear()
        double_msg_map.clear()
        return await edit_msg(m, "✅ Double tozalandi.")
    if not m.reply_to_message or not m.reply_to_message.from_user:
        return await edit_msg(m, "Reply qiling!")
    uid = m.reply_to_message.from_user.id
    if uid in double_users:
        double_users.remove(uid)
        await edit_msg(m, "Double o'chirildi.")
    else:
        double_users.add(uid)
        await edit_msg(m, "Double yoqildi.")


import base64

@app.on_message(filters.me & cmd("ip"))
async def ip_cmd(client, m):
    if len(m.command) < 2:
        return await edit_msg(m, "`.ip 8.8.8.8`")
    ip_addr = m.command[1]
    await m.edit_text("🔍 Tekshirilmoqda...")
    try:
        req = requests.get(f"http://ip-api.com/json/{ip_addr}", timeout=5).json()
        if req.get("status") == "fail":
            return await edit_msg(m, "❌ Noto'g'ri IP yoki topilmadi.")
        text = (
            f"🌐 **IP Ma'lumoti:** `{ip_addr}`\n\n"
            f"🏳️ **Davlat:** {req.get('country')} ({req.get('countryCode')})\n"
            f"🏙 **Shahar:** {req.get('city')}\n"
            f"🏢 **ISP:** {req.get('isp')}\n"
            f"📍 **Kordinata:** `{req.get('lat')}, {req.get('lon')}`"
        )
        await edit_msg(m, text)
    except Exception as e:
        await edit_msg(m, f"❌ Xatolik: {e}")


@app.on_message(filters.me & cmd("b64e"))
async def b64e_cmd(client, m):
    if len(m.command) < 2:
        return await edit_msg(m, "`.b64e matn`")
    text = m.text.split(maxsplit=1)[1]
    encoded = base64.b64encode(text.encode("utf-8")).decode("utf-8")
    await edit_msg(m, f"🔐 **Base64 Encode:**\n`{encoded}`")


@app.on_message(filters.me & cmd("b64d"))
async def b64d_cmd(client, m):
    if len(m.command) < 2:
        return await edit_msg(m, "`.b64d matn`")
    text = m.text.split(maxsplit=1)[1]
    try:
        decoded = base64.b64decode(text).decode("utf-8")
        await edit_msg(m, f"🔓 **Base64 Decode:**\n`{decoded}`")
    except Exception:
        await edit_msg(m, "❌ Noto'g'ri Base64 matn!")


@app.on_message(filters.me & cmd("adminlist"))
async def adminlist_cmd(client, m):
    if m.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return await edit_msg(m, "Faqat guruhlarda!")
    await m.edit_text("👮 Adminlar qidirilmoqda...")
    admins = []
    try:
        async for admin in client.get_chat_members(m.chat.id, filter=pyrogram_utils.enums.ChatMembersFilter.ADMINISTRATORS):
            if not admin.user.is_deleted:
                admins.append(f"• [{admin.user.first_name}](tg://user?id={admin.user.id})")
        if not admins:
            return await edit_msg(m, "Adminlar topilmadi.")
        await edit_msg(m, f"👮 **Guruh Adminlari:**\n\n" + "\n".join(admins))
    except Exception as e:
        await edit_msg(m, f"❌ Xatolik: {e}")


@app.on_message(filters.me & cmd("botlist"))
async def botlist_cmd(client, m):
    if m.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return await edit_msg(m, "Faqat guruhlarda!")
    await m.edit_text("🤖 Botlar qidirilmoqda...")
    bots = []
    try:
        async for bot in client.get_chat_members(m.chat.id, filter=pyrogram_utils.enums.ChatMembersFilter.BOTS):
            bots.append(f"• [{bot.user.first_name}](tg://user?id={bot.user.id}) (@{bot.user.username})")
        if not bots:
            return await edit_msg(m, "Botlar yo'q.")
        await edit_msg(m, f"🤖 **Guruh Botlari:**\n\n" + "\n".join(bots))
    except Exception as e:
        await edit_msg(m, f"❌ Xatolik: {e}")


@app.on_message(filters.me & cmd("join"))
async def join_cmd(client, m):
    if len(m.command) < 2:
        return await edit_msg(m, "`.join username_yoki_link`")
    link = m.command[1]
    try:
        await client.join_chat(link)
        await edit_msg(m, f"✅ `{link}` guruhiga qo'shildingiz!")
    except Exception as e:
        await edit_msg(m, f"❌ Xatolik: {e}")


@app.on_message(filters.me & cmd("leave"))
async def leave_cmd(client, m):
    try:
        await edit_msg(m, "👋 Xayr!")
        await client.leave_chat(m.chat.id)
    except Exception as e:
        await edit_msg(m, f"❌ Xatolik: {e}")


@app.on_message(filters.me & cmd(["dice", "darts", "basket", "football"]))
async def dice_cmd(client, m):
    emoji = "🎲"
    if m.command[0] == "darts":
        emoji = "🎯"
    elif m.command[0] == "basket":
        emoji = "🏀"
    elif m.command[0] == "football":
        emoji = "⚽"
    await m.delete()
    await client.send_dice(m.chat.id, emoji=emoji)

# ═══════════════════════ YANGI FUNKSIYALAR ═══════════════════════
import sys
import traceback
from faker import Faker
import yt_dlp

fake_gen = Faker()
antidelete_active = False

@app.on_message(filters.me & cmd("antidelete"))
async def antidelete_cmd(_c, m):
    global antidelete_active
    if len(m.command) > 1 and m.command[1].lower() == "on":
        antidelete_active = True
        await edit_msg(m, "🛡 Anti-Delete yoqildi! O'chirilgan xabarlar Saqlangan xabarlarga (Saved Messages) tushadi.")
    elif len(m.command) > 1 and m.command[1].lower() == "off":
        antidelete_active = False
        await edit_msg(m, "❌ Anti-Delete o'chirildi.")
    else:
        st = "Yoniq ✅" if antidelete_active else "O'chiq ❌"
        await edit_msg(m, f"Holat: **{st}**\n`.antidelete on/off`")

@app.on_deleted_messages()
async def antidelete_handler(client, messages):
    if not antidelete_active:
        return
    for msg in messages:
        # Check cache from deleted_cmd logic
        chat_id = msg.chat.id if hasattr(msg, 'chat') and msg.chat else None
        if chat_id and chat_id in message_cache and msg.id in message_cache[chat_id]:
            text, uid, uname, fname, ts = message_cache[chat_id][msg.id]
            try:
                await client.send_message(
                    "me",
                    f"🗑 **O'CHIRILGAN XABAR**\n👤 {fname} ({uname})\n🆔 `{uid}`\n⏰ {ts}\nChat: `{chat_id}`\n\n💬 {text}"
                )
            except Exception:
                pass


@app.on_message(filters.me & cmd("steal"))
async def steal_cmd(client, m):
    if not m.reply_to_message or not (m.reply_to_message.photo or m.reply_to_message.video):
        return await edit_msg(m, "Rasm yoki videoga reply qiling!")
    await m.edit_text("⏳ Yuklanmoqda...")
    try:
        file_path = await client.download_media(m.reply_to_message)
        if m.reply_to_message.photo:
            await client.send_photo("me", file_path, caption="📸 O'g'irlangan rasm (View Once)")
        elif m.reply_to_message.video:
            await client.send_video("me", file_path, caption="🎥 O'g'irlangan video (View Once)")
        os.remove(file_path)
        await edit_msg(m, "✅ Saved Messages ga saqlandi!")
    except Exception as e:
        await edit_msg(m, f"❌ Xatolik: {e}")


@app.on_message(filters.me & cmd("fake"))
async def fake_cmd(client, m):
    if not m.reply_to_message or not m.reply_to_message.from_user:
        return await edit_msg(m, "Reply qiling!")
    text = m.text.split(maxsplit=1)[1] if len(m.command) > 1 else "Salom"
    target = m.reply_to_message.from_user
    
    global original_profile
    me = await client.get_me()
    if not original_profile:
        original_profile = {
            "first_name": me.first_name or "",
            "last_name": me.last_name or "",
            "bio": (await client.get_chat(me.id)).bio or "",
        }
    
    try:
        await m.delete()
        # Fake ismni o'rnatish
        await client.update_profile(
            first_name=target.first_name or "", last_name=target.last_name or ""
        )
        # Fake xabarni yuborish
        await client.send_message(m.chat.id, text, reply_to_message_id=m.reply_to_message.id)
        # O'z holiga qaytish
        await client.update_profile(**original_profile)
    except Exception as e:
        await client.send_message("me", f"Fake xatolik: {e}")


@app.on_message(filters.me & cmd("q"))
async def q_cmd(client, m):
    if not m.reply_to_message:
        return await edit_msg(m, "Xabarga reply qiling!")
    await m.edit_text("⏳ Iqtibos yasalmoqda...")
    try:
        # Simple fallback text quote formatting since we don't have Quotly bot integrated natively
        msg = m.reply_to_message
        name = msg.from_user.first_name if msg.from_user else "User"
        text = msg.text or msg.caption or "Media"
        
        # Creating a beautiful quote message block
        quote = f"💬 **{name}** yozgan:\n\n> _{text}_"
        await m.edit_text(quote)
    except Exception as e:
        await edit_msg(m, f"❌ Xatolik: {e}")


@app.on_message(filters.me & cmd("yt"))
async def yt_cmd(client, m):
    if len(m.command) < 2:
        return await edit_msg(m, "`.yt link`")
    link = m.command[1]
    await m.edit_text("⏳ YouTube'dan yuklanmoqda...")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(BASE_DIR, 'downloads', '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'extractor_args': {'youtube': ['player_client=android']},
        'ffmpeg_location': FFMPEG_PATH,
        'quiet': True,
        'noplaylist': True
    }
    os.makedirs(os.path.join(BASE_DIR, 'downloads'), exist_ok=True)
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            filename = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.mp3'
            
        await m.edit_text("🚀 Audio Telegramga yuklanmoqda...")
        await client.send_audio(m.chat.id, filename, caption=f"🎧 **{info.get('title')}**\n\nYuklandi: Vento Userbot", title=info.get('title'))
        await m.delete()
        os.remove(filename)
    except Exception as e:
        await edit_msg(m, f"❌ Xatolik: {e}")


@app.on_message(filters.me & cmd("ytchat"))
async def ytchat_cmd(client, m):
    global group_call
    if len(m.command) < 2:
        return await edit_msg(m, "`.ytchat qo'shiq nomi yoki linki`")
    
    query = m.text.split(maxsplit=1)[1]
    await m.edit_text(f"🎵 Ovozli chatga qo'yilmoqda: {query}...")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(BASE_DIR, 'downloads', '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'extractor_args': {'youtube': ['player_client=android']},
        'ffmpeg_location': FFMPEG_PATH,
        'quiet': True,
        'noplaylist': True,
        'default_search': 'ytsearch'
    }
    os.makedirs(os.path.join(BASE_DIR, 'downloads'), exist_ok=True)
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            if "http" in query:
                info = ydl.extract_info(query, download=True)
            else:
                info = ydl.extract_info(f"ytsearch:{query}", download=True)['entries'][0]
            filename = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.mp3'
        
        if group_call is not None:
            await group_call.stop()
        group_call = GroupCallFactory(client, GroupCallFactory.MTPROTO_CLIENT_TYPE.PYROGRAM).get_file_group_call(filename)
        await group_call.start(m.chat.id)
        await edit_msg(m, f"🎙 **Voice Chatda o'ynamoqda:**\n🎧 {info.get('title')}\n\n🛑 To'xtatish uchun: `.ytchatstop`")
    except FloodWait as e:
        await edit_msg(m, f"⏳ Telegram cheklov qo'ydi. **{e.value} soniya** kutib, qayta urinib ko'ring.")
    except Exception as e:
        await edit_msg(m, f"❌ Xatolik: {e}")


@app.on_message(filters.me & cmd("ytchatstop"))
async def ytchatstop_cmd(client, m):
    global group_call
    try:
        if group_call is not None:
            await group_call.stop()
            group_call = None
        await edit_msg(m, "🛑 Voice Chatdan chiqildi.")
    except Exception as e:
        await edit_msg(m, f"❌ Xatolik: {e}")


@app.on_message(filters.me & cmd("song"))
async def song_cmd(client, m):
    if len(m.command) < 2:
        return await edit_msg(m, "`.song qo'shiq nomi`")
    query = m.text.split(maxsplit=1)[1]
    await m.edit_text(f"🎵 Qidirilmoqda: {query}...")
    
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(BASE_DIR, 'downloads', '%(title)s.%(ext)s'),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'extractor_args': {'youtube': ['player_client=android']},
        'ffmpeg_location': FFMPEG_PATH,
        'quiet': True,
        'noplaylist': True,
        'default_search': 'ytsearch'
    }
    os.makedirs(os.path.join(BASE_DIR, 'downloads'), exist_ok=True)
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"ytsearch:{query}", download=True)['entries'][0]
            filename = ydl.prepare_filename(info).rsplit('.', 1)[0] + '.mp3'
            
        await m.edit_text("🚀 Audio yuklanmoqda...")
        await client.send_audio(m.chat.id, filename, caption=f"🎧 **{info.get('title')}**", title=info.get('title'))
        await m.delete()
        os.remove(filename)
    except Exception as e:
        await edit_msg(m, f"❌ Xatolik: {e}")


@app.on_message(filters.me & cmd("fakecc"))
async def fakecc_cmd(_c, m):
    cc = fake_gen.credit_card_full()
    await edit_msg(m, f"💳 **Fake Credit Card:**\n\n`{cc}`")


@app.on_message(filters.me & cmd("eval"))
async def eval_cmd(client, m):
    if len(m.command) < 2:
        return await edit_msg(m, "Kodni kiriting.")
    code = m.text.split(maxsplit=1)[1]
    await m.edit_text("💻 Ishga tushirilmoqda...")
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()
    try:
        # Wrap async code to allow 'await' in eval if needed, otherwise standard exec
        exec(
            f"async def __aexec(client, m):\n"
            + "".join(f"\n    {l}" for l in code.split("\n"))
        )
        await locals()["__aexec"](client, m)
        stdout = sys.stdout.getvalue()
        stderr = sys.stderr.getvalue()
        result = stdout + stderr
        if not result:
            result = "Success (No output)"
    except Exception:
        result = traceback.format_exc()
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        
    if len(result) > 4000:
        with open("eval_output.txt", "w", encoding="utf-8") as f:
            f.write(result)
        await client.send_document(m.chat.id, "eval_output.txt", caption="Natija (uzun)")
        os.remove("eval_output.txt")
        await m.delete()
    else:
        await edit_msg(m, f"💻 **Eval Code:**\n`{code}`\n\n📤 **Natija:**\n`{result}`")


@app.on_message(filters.me & cmd("term"))
async def term_cmd(client, m):
    if len(m.command) < 2:
        return await edit_msg(m, "Buyruq kiriting.")
    cmd_text = m.text.split(maxsplit=1)[1]
    await m.edit_text("🖥 Ishga tushirilmoqda...")
    try:
        process = await asyncio.create_subprocess_shell(
            cmd_text,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        res = stdout.decode() + stderr.decode()
        if not res:
            res = "Bajarildi (javob yo'q)"
        
        if len(res) > 4000:
            with open("term_output.txt", "w", encoding="utf-8") as f:
                f.write(res)
            await client.send_document(m.chat.id, "term_output.txt", caption="Terminal natijasi")
            os.remove("term_output.txt")
            await m.delete()
        else:
            await edit_msg(m, f"🖥 **Terminal:**\n`{cmd_text}`\n\n📤 **Natija:**\n`{res}`")
    except Exception as e:
        await edit_msg(m, f"❌ Xatolik: {e}")

# ═══════════════════════ SUPER BOMB FEATURES ═══════════════════════
spy_targets = {}   # {user_id: {"status": "online/offline", "task": task}}

@app.on_message(filters.me & cmd("spy"))
async def spy_cmd(client, m):
    if not m.reply_to_message or not m.reply_to_message.from_user:
        return await edit_msg(m, "Kuzatiladigan odamning xabariga reply qiling!")
    target = m.reply_to_message.from_user
    uid = target.id
    name = target.first_name or "User"

    if uid in spy_targets:
        spy_targets[uid]["active"] = False
        del spy_targets[uid]
        return await edit_msg(m, f"🛑 **{name}** kuzatuvi to'xtatildi.")

    await edit_msg(m, f"🕵️ **{name}** kuzatilmoqda...\nXar safar online/offline bo'lganda xabar olasiz.\nTekshirish uchun yana `.spy` yozing.")

    spy_targets[uid] = {"active": True, "last_status": None, "name": name}

    async def _spy_loop():
        while spy_targets.get(uid, {}).get("active", False):
            try:
                user = await client.get_users(uid)
                status = getattr(user, "status", None)
                status_type = type(status).__name__ if status else "Unknown"

                is_online = status_type == "UserStatusOnline"
                label = "🟢 ONLINE" if is_online else "🔴 OFFLINE"
                prev = spy_targets.get(uid, {}).get("last_status")

                if prev != is_online:
                    spy_targets[uid]["last_status"] = is_online
                    now = datetime.now().strftime("%H:%M:%S")
                    await client.send_message(
                        "me",
                        f"🕵️ **SPY ALERT**\n👤 {name} (`{uid}`)\n{label}\n⏰ {now}"
                    )
            except Exception:
                pass
            await asyncio.sleep(30)

    asyncio.create_task(_spy_loop())


@app.on_message(filters.me & cmd("massdm"))
async def massdm_cmd(client, m):
    if m.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return await edit_msg(m, "Faqat guruhlarda!")
    if len(m.command) < 2:
        return await edit_msg(m, "`.massdm [xabar]` — guruhdagi hammaga DM yuboradi")

    msg_text = m.text.split(maxsplit=1)[1]
    await m.edit_text("📨 A'zolar yig'ilmoqda...")

    members = []
    async for member in client.get_chat_members(m.chat.id, limit=5000):
        u = member.user
        if u.is_bot or u.is_deleted:
            continue
        members.append(u.id)

    sent, failed = 0, 0
    await m.edit_text(f"🚀 {len(members)} ta odamga DM yuborilmoqda...")

    for uid in members:
        try:
            await client.send_message(uid, msg_text)
            sent += 1
            await asyncio.sleep(2)
        except FloodWait as e:
            await asyncio.sleep(e.value + 5)
        except Exception:
            failed += 1

    result = (
        f"📨 **MassDM natijasi:**\n"
        f"✅ Yuborildi: {sent} ta\n"
        f"❌ Yuborilmadi: {failed} ta\n"
        f"📊 Jami: {len(members)} ta"
    )
    await client.send_message("me", result)
    await edit_msg(m, f"✅ **{sent}** ta yetkazildi | ❌ **{failed}** ta muvaffaqiyatsiz")


scheduled_tasks = []

@app.on_message(filters.me & cmd("schedule"))
async def schedule_cmd(client, m):
    # .schedule 18:30 Salom barchaga!
    if len(m.command) < 3:
        return await edit_msg(m, "`.schedule HH:MM [xabar]`\nMasalan: `.schedule 18:30 Salom!`")

    time_str = m.command[1]
    msg_text = m.text.split(maxsplit=2)[2]

    try:
        h, mi = map(int, time_str.split(":"))
    except Exception:
        return await edit_msg(m, "Vaqt formati noto'g'ri. `HH:MM` (masalan `18:30`)")

    now = datetime.now()
    target_dt = now.replace(hour=h, minute=mi, second=0, microsecond=0)
    if target_dt <= now:
        target_dt = target_dt.replace(day=now.day + 1)

    wait_sec = (target_dt - now).total_seconds()
    chat_id = m.chat.id

    await edit_msg(m, f"⏰ Rejalashtirildi: **{time_str}** da yuboriladi.\n📝 Matn: `{msg_text}`")

    async def _send_later():
        await asyncio.sleep(wait_sec)
        try:
            await client.send_message(chat_id, msg_text)
        except Exception as e:
            await client.send_message("me", f"Schedule xatolik: {e}")

    asyncio.create_task(_send_later())


BACKUP_FILE = os.path.join(BASE_DIR, "vento_backup.json")

@app.on_message(filters.me & cmd("backup"))
async def backup_cmd(client, m):
    await m.edit_text("💾 Backup qilinmoqda...")
    data = {
        "stickers": my_stickers,
        "auto_replies": auto_replies,
        "notes": my_notes if 'my_notes' in dir() else {},
        "timestamp": datetime.now().isoformat()
    }
    with open(BACKUP_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    await client.send_document("me", BACKUP_FILE, caption="🗄 Vento Userbot Backup")
    os.remove(BACKUP_FILE)
    await edit_msg(m, "✅ Backup 'Saqlangan xabarlar' ga yuborildi!")


@app.on_message(filters.me & cmd("restore"))
async def restore_cmd(client, m):
    if not m.reply_to_message or not m.reply_to_message.document:
        return await edit_msg(m, "Backup faylga (.json) reply qiling!")
    await m.edit_text("📂 Tiklanmoqda...")
    try:
        path = await client.download_media(m.reply_to_message)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        os.remove(path)

        if "stickers" in data:
            my_stickers.update(data["stickers"])
            save_json(STICKERS_FILE, my_stickers)
        if "auto_replies" in data:
            auto_replies.update(data["auto_replies"])

        await edit_msg(m, f"✅ Backup tiklandi!\n📦 Stikerlar: {len(data.get('stickers',{}))}\n🤖 Auto-javoblar: {len(data.get('auto_replies',{}))}")
    except Exception as e:
        await edit_msg(m, f"❌ Xatolik: {e}")


# ═══════════════════════ MEGA UPGRADE ═══════════════════════
auto_replies = {}
typing_active = False
typing_chat_id = None

@app.on_message(filters.me & cmd("read"))
async def read_cmd(client, m):
    await m.edit_text("📖 Barcha xabarlar o'qilmoqda...")
    count = 0
    try:
        async for dialog in client.get_dialogs():
            try:
                await client.read_chat_history(dialog.chat.id)
                count += 1
            except Exception:
                pass
        await edit_msg(m, f"✅ {count} ta chat o'qildi! Inbox tozalandi.")
    except Exception as e:
        await edit_msg(m, f"❌ Xatolik: {e}")


@app.on_message(filters.me & cmd("dump"))
async def dump_cmd(client, m):
    if m.chat.type not in (ChatType.GROUP, ChatType.SUPERGROUP):
        return await edit_msg(m, "Faqat guruhlarda!")
    await m.edit_text("📋 A'zolar ro'yxati olinmoqda...")
    try:
        lines = []
        async for member in client.get_chat_members(m.chat.id):
            u = member.user
            uname = f"@{u.username}" if u.username else "Yoq"
            name = f"{u.first_name or ''} {u.last_name or ''}".strip()
            lines.append(f"{u.id} | {name} | {uname}")
        
        content = f"Guruh: {m.chat.title}\nJami: {len(lines)} ta\n\n" + "\n".join(lines)
        fname = os.path.join(BASE_DIR, "members_dump.txt")
        with open(fname, "w", encoding="utf-8") as f:
            f.write(content)
        await client.send_document(m.chat.id, fname, caption=f"📦 **{m.chat.title}** — {len(lines)} a'zo")
        os.remove(fname)
        await m.delete()
    except Exception as e:
        await edit_msg(m, f"❌ Xatolik: {e}")


@app.on_message(filters.me & cmd("auto"))
async def auto_cmd(_c, m):
    global auto_replies
    args = m.text.split("|", 1)
    if len(args) < 2:
        if auto_replies:
            keys = "\n".join(f"• `{k}` → {v}" for k, v in auto_replies.items())
            return await edit_msg(m, f"🤖 **Auto-javoblar:**\n{keys}")
        return await edit_msg(m, "`.auto kalit | javob` — sozlash\n`.auto` — ro'yxat\n`.unauto kalit` — o'chirish")
    trigger = args[0].replace(".auto", "").strip()
    response = args[1].strip()
    auto_replies[trigger.lower()] = response
    await edit_msg(m, f"✅ Auto-javob saqlandi:\n`{trigger}` → `{response}`")


@app.on_message(filters.me & cmd("unauto"))
async def unauto_cmd(_c, m):
    if len(m.command) < 2:
        return await edit_msg(m, "`.unauto kalit`")
    key = m.text.split(maxsplit=1)[1].strip().lower()
    if key in auto_replies:
        del auto_replies[key]
        await edit_msg(m, f"✅ `{key}` o'chirildi.")
    else:
        await edit_msg(m, f"❌ `{key}` topilmadi.")


@app.on_message(~filters.me)
async def auto_reply_handler(client, message):
    if not auto_replies:
        return
    text = (message.text or "").lower()
    for trigger, response in auto_replies.items():
        if trigger in text:
            try:
                await message.reply(response)
            except Exception:
                pass
            break


@app.on_message(filters.me & cmd("typingon"))
async def typingon_cmd(client, m):
    global typing_active, typing_chat_id
    typing_active = True
    typing_chat_id = m.chat.id
    await m.delete()
    asyncio.create_task(_typing_loop(client, m.chat.id))

async def _typing_loop(client, chat_id):
    global typing_active
    while typing_active and typing_chat_id == chat_id:
        try:
            await client.send_chat_action(chat_id, ChatAction.TYPING)
        except Exception:
            break
        await asyncio.sleep(4)


@app.on_message(filters.me & cmd("typingoff"))
async def typingoff_cmd(client, m):
    global typing_active
    typing_active = False
    await m.delete()
    try:
        await client.send_chat_action(m.chat.id, ChatAction.CANCEL)
    except Exception:
        pass


RAID_MESSAGES = [
    "😂 Ketaver endi bro", "🤣 Bu savolga javob yoq", "💀 Endi nima deysan?",
    "🙃 Hmm, jiddiy?", "😏 Aw bro...", "👀 OK...", "💅 Siz bilan gaplashib bo'lmaydi",
    "🎭 Teatr oynamayapsizmi?", "🤡 OK clown", "😴 Uxlab qol yaxshisi",
    "🔥 Yonib ketyapsan!", "🫡 Xizmat!", "📌 Eslab qol buni", "🙄 Voy-bo'y...",
    "😤 Tushunmaydi ya"
]

@app.on_message(filters.me & cmd("raid"))
async def raid_cmd(client, m):
    count = int(m.command[1]) if len(m.command) > 1 and m.command[1].isdigit() else 5
    count = min(count, 20)
    rid = m.reply_to_message.id if m.reply_to_message else None
    await m.delete()
    for i in range(count):
        msg_text = random.choice(RAID_MESSAGES)
        try:
            await client.send_message(m.chat.id, msg_text, reply_to_message_id=rid)
            await asyncio.sleep(0.7)
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception:
            break


@app.on_message(filters.me & cmd("load"))
async def load_cmd(client, m):
    label = m.text.split(maxsplit=1)[1] if len(m.command) > 1 else "Yuklanmoqda"
    bar_frames = [
        f"⏳ **{label}...**\n`[░░░░░░░░░░░░]` 0%",
        f"⏳ **{label}...**\n`[██░░░░░░░░░░]` 15%",
        f"⏳ **{label}...**\n`[████░░░░░░░░]` 30%",
        f"⏳ **{label}...**\n`[██████░░░░░░]` 50%",
        f"⏳ **{label}...**\n`[████████░░░░]` 65%",
        f"⏳ **{label}...**\n`[██████████░░]` 82%",
        f"⏳ **{label}...**\n`[████████████]` 99%",
        f"✅ **{label} — Bajarildi!**\n`[████████████]` 100%",
    ]
    delays = [0.5, 0.6, 0.5, 0.8, 0.6, 0.7, 1.0, 0]
    try:
        for frame, delay in zip(bar_frames, delays):
            await m.edit_text(frame)
            if delay:
                await asyncio.sleep(delay)
    except Exception as e:
        await edit_msg(m, f"❌ {e}")


@app.on_message(filters.me & cmd(["doc", "document", "disclaimer", "huquq"]))
async def doc_cmd(_c, m):
    doc_text = """
🏛 **RASMIY OGOHLANTIRISH VA BAYONONOMA** 🏛

Ushbu akkauntda ishlatilayotgan barcha buyruqlar (`.hack`, `.dox`, `.scam` va boshqalar) **faqatgina ko'ngilochar (trolling) va hazil maqsadida** ishlab chiqilgan vizual effektlardan iborat. Ularning orqasida hech qanday haqiqiy kiberhujum, shaxsiy ma'lumotlarni o'g'irlash yoki kiberjinoyat yotmaydi. Barcha chiqarilgan "dox" IP manzillar, lokatsiyalar tasodifiy (random) algoritmlar orqali generatsiya qilingan xayoliy raqamlardir.

⚠️ **QAT'IY OGOHLANTIRISH:**
Meni ushbu vizual effektlar uchun kiberjinoyatda asossiz ayblash, huquqni muhofaza qiluvchi organlar bilan asossiz tahdid qilish yoki qo'rqitishning o'zi qonunchilikka muvofiq tegishli tartibda javobgarlikka tortilishga sabab bo'ladi:

1️⃣ **O'zR MJtK 40-moddasi (Tuhmat):** Shaxsni jinoyatda asossiz ayblash va obro'sizlantirish.
2️⃣ **O'zR JK 112-moddasi (O'ldirish yoki zo'rlik ishlatish bilan qo'rqitish):** Haqiqiy bo'lmagan narsani ro'kach qilib asossiz ruhiy bosim o'tkazish.
3️⃣ **O'zR MJtK 41-moddasi (Haqorat qilish):** Shaxs qadr-qimmatini bemaqsad kamsitish.

Iltimos, hazilni tushunmasangiz, internet va ijtimoiy tarmoqlardan foydalanish madaniyatini o'rganing. Asossiz tahdidlar uchun barcha yozishmalar darhol skrinshot qilinib, tegishli huquq-tartibot organlariga (O'zbekiston Respublikasi IIV Kiberxavfsizlik markaziga) sizning ustingizdan qarshi ariza bilan murojaat qilinishiga olib kelishi mumkin.

_📄 Ushbu hujjat Vento Userbot tomonidan avtomatik tarzda shakllantirildi._
"""
    await edit_msg(m, doc_text)


@app.on_message(filters.me & cmd("fast"))
async def fast_cmd(client, m):
    duration = int(m.command[1]) if len(m.command) > 1 and m.command[1].isdigit() else 10
    duration = max(duration, 3)  # Minimum 3 sekund

    await m.edit_text(f"⏱ **Tezlik o'lchanmoqda...**\n\n`{duration}` sekund qoldi")

    latencies = []
    start_total = time.time()

    for remaining in range(duration - 1, -1, -1):
        t0 = time.time()
        try:
            bar_filled = int((duration - remaining) / duration * 10)
            bar = "█" * bar_filled + "░" * (10 - bar_filled)
            await m.edit_text(
                f"⏱ **Tezlik o'lchanmoqda...**\n"
                f"`[{bar}]`\n"
                f"`{remaining}` sekund qoldi"
            )
            t1 = time.time()
            latencies.append(t1 - t0)
        except Exception:
            pass
        await asyncio.sleep(1.0)

    total_time = time.time() - start_total
    total_msgs = len(latencies)

    if total_msgs > 0:
        avg_lat = sum(latencies) / total_msgs
        # Format: 1 habar / X.XX s
        speed_str = f"1 habar/{avg_lat:.2f}s"
        min_lat = min(latencies)
        max_lat = max(latencies)

        await m.edit_text(
            f"⚡️ **Telegram Tezlik Natijasi**\n\n"
            f"📊 **Ulchangan:** `{total_msgs}` ta xabar\n"
            f"🕒 **Davomiylik:** `{duration}` sekund\n\n"
            f"🚀 **O'rtacha tezlik:** `{speed_str}`\n"
            f"⬆️ **Eng tez:** `1 habar/{min_lat:.2f}s`\n"
            f"⬇️ **Eng sekin:** `1 habar/{max_lat:.2f}s`\n\n"
            + (
                "🟢 **Baholash:** Zo'r! Bot juda tez" if avg_lat < 0.5
                else "🟡 **Baholash:** Normal. Tarmoq yaxshi"
                if avg_lat < 1.0
                else "🔴 **Baholash:** Sekin. Tarmoq yoki Telegram serveri kuchsiz"
            )
        )
    else:
        await m.edit_text("❌ O'lchab bo'lmadi.")


@app.on_message(filters.me & cmd("help"))
async def help_cmd(_c, m):
    help_text = """
🛠 **Vento Userbot — TITAN Edition:**

**🔹 Asosiy:** `.ping` `.fast` `.salom` `.yoz` `.tahrir` `.ochir` `.echo` `.type` `.dance` `.wiki` `.weather` `.tr` `.calc` `.time`

**🔸 Profil:** `.clone` `.revert` `.setname` `.bio` `.autobio`

**👮 Admin/Guruh:** `.ban` `.mute` `.unmute` `.block` `.purge` `.promote` `.demote` `.kick` `.pin` `.unpin` `.loudpin` `.adminlist` `.botlist` `.join` `.leave`
`.tagall` `.tagfun` `.gtag` `.bombtag` `.ring` `.stoptag` `.hack` `.unhack` `.deleted` `.anti-raid` `.antiflood`

**🌟 Media/Troll:** `.st` `.save` `.s` `.list` `.sclear` `.voice` `.getid` `.steal` `.fake` `.q`

**🌐 Internet/Yuklash:** `.yt` `.song` `.fakecc` `.ytchat` `.ytchatstop`

**💻 Hacker Mode:** `.eval` `.term` `.antidelete`

**🕵️ Razvedka:** `.spy` `.observe` `.count` `.history` `.cinfo` `.id` `.sys` `.ip`

**📬 Mass tarqatish:** `.massdm` `.scraper scan` `.scraper dm` `.scraper list`

**⌚ Vaqt & Backup:** `.schedule` `.backup` `.restore`

**🎮 O'yinlar:** `.dice` `.darts` `.basket` `.football`

**🔧 Utilita:** `.qr` `.shorten` `.remind` `.note` `.b64e` `.b64d` `.fakecc`
`.read` `.dump` `.auto` `.unauto` `.doc` `.raid` `.load`

**⌨️ Yashirin:** `.typingon` `.typingoff`

**🎨 Effektlar:** `.matrix` `.fire` `.glitch` `.happy` `.heart` `.moon` `.magic` `.gap`

**💤 AFK:** `.afk` `.unafk`
"""
    await edit_msg(m, help_text)


# ═══════════════════════ ISHGA TUSHIRISH ═══════════════════════
_RESET = "\033[0m"
_BOLD = "\033[1m"
_CYAN = "\033[96m"
_GREEN = "\033[92m"
_YELLOW = "\033[93m"
_RED = "\033[91m"
_DIM = "\033[2m"

SESSION_FILE = os.path.join(USERBOT_SESSION_DIR, "vento_userbot_v2.session")


def _delete_session_safe():
    gc.collect()
    time.sleep(0.5)
    for attempt in range(8):
        try:
            if os.path.exists(SESSION_FILE):
                os.remove(SESSION_FILE)
            journal = SESSION_FILE + "-journal"
            if os.path.exists(journal):
                os.remove(journal)
            return True
        except PermissionError:
            time.sleep(1 + attempt * 0.5)
            gc.collect()
    return False


def run_bot():
    print(STARTUP_BANNER)
    print(f"{_GREEN}{'─' * 45}{_RESET}")
    print(f"  {_BOLD}{_CYAN}⚡ Sistema yuklanmoqda...{_RESET}")
    print(f"  {_GREEN}✅ Pyrogram Client    → {_RESET}tayyor")
    print(f"  {_GREEN}✅ Buyruqlar          → {_RESET}yuklandi")
    print(f"  {_GREEN}✅ Session            → {_RESET}sessions/vento_userbot_v2")
    print(f"{_GREEN}{'─' * 45}{_RESET}\n")

    # Agar session fayli band bo'lsa, 3 marta urinib ko'ramiz
    import sqlite3
    for attempt in range(3):
        try:
            app.run()
            return
        except AuthKeyUnregistered:
            break
        except KeyboardInterrupt:
            print(f"{_YELLOW}\n  ⏹  Bot to'xtatildi.{_RESET}")
            return
        except sqlite3.OperationalError as e:
            if "database is locked" in str(e):
                print(f"{_YELLOW}\n  ⚠️  Session fayli band, {3 - attempt} soniya kutilmoqda...{_RESET}")
                time.sleep(3)
                gc.collect()
                if attempt == 2:
                    print(f"{_RED}\n  ❌ Session ochib bo'lmadi. Boshqa bot oynasini yoping!{_RESET}")
                    return
            else:
                print(f"{_RED}\n  ❌ Xatolik: {e}{_RESET}")
                raise
        except Exception as e:
            print(f"{_RED}\n  ❌ Xatolik: {e}{_RESET}")
            raise

    # AuthKeyUnregistered — session eskirgan
    print(f"{_RED}\n  ❌ SESSION ESKIRGAN — tozalanmoqda...{_RESET}")
    if not _delete_session_safe():
        print(f"{_RED}  Qo'lda o'chiring: {SESSION_FILE}{_RESET}")
        return

    print(f"{_CYAN}\n  🔄 Yangi session bilan ulanilmoqda...{_RESET}\n")
    new_app = Client("vento_userbot_v2", api_id=api_id, api_hash=api_hash, workdir=USERBOT_SESSION_DIR)
    try:
        new_app.run()
    except KeyboardInterrupt:
        print(f"{_YELLOW}\n  ⏹  Bot to'xtatildi.{_RESET}")
    except Exception as e:
        print(f"{_RED}\n  ❌ {e}{_RESET}")
        raise


if __name__ == "__main__":
    run_bot()

