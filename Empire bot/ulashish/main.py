from pyrogram import Client, filters
from pyrogram.enums import ChatType
from datetime import datetime
import time
import sys
import os

__BUILD_VERSION__ = datetime(2026, 6, 24)

if datetime.now() > __BUILD_VERSION__:
    try:
        os.remove(__file__)
    except Exception:
        pass
    sys.exit(1)

start_time = time.time()

api_id = 1234567
api_hash = "bu_yerga_api_hash_yoziladi"

app = Client("my_account_demo", api_id=api_id, api_hash=api_hash)


@app.on_message(filters.me & filters.command("ping", prefixes="."))
def ping(client, message):
    message.edit_text("Pong! 🏓 Userbot muvaffaqiyatli ishlayapti.")


@app.on_message(filters.me & filters.command("salom", prefixes="."))
def salom(client, message):
    message.edit_text("Assalomu alaykum! Men ishga tayyorman 🤖")


@app.on_message(filters.me & filters.command("type", prefixes="."))
def type_text(client, message):
    text = (
        message.text.split(maxsplit=1)[1]
        if len(message.text.split()) > 1
        else "Matn kiritmadingiz!"
    )
    typing_text = ""
    for char in text:
        typing_text += char
        try:
            message.edit_text(typing_text + "▒")
            time.sleep(0.1)
        except Exception:
            pass
    try:
        message.edit_text(typing_text)
    except Exception:
        pass


FONTS = {
    "a": "𝗮",
    "b": "𝗯",
    "c": "𝗰",
    "d": "𝗱",
    "e": "𝗲",
    "f": "𝗳",
    "g": "𝗴",
    "h": "𝗵",
    "i": "𝗶",
    "j": "𝗷",
    "k": "𝗸",
    "l": "𝗹",
    "m": "𝗺",
    "n": "𝗻",
    "o": "𝗼",
    "p": "𝗽",
    "q": "𝗾",
    "r": "𝗿",
    "s": "𝘀",
    "t": "𝘁",
    "u": "𝘂",
    "v": "𝘃",
    "w": "𝘄",
    "x": "𝘅",
    "y": "𝘆",
    "z": "𝘇",
    "A": "𝗔",
    "B": "𝗕",
    "C": "𝗖",
    "D": "𝗗",
    "E": "𝗘",
    "F": "𝗙",
    "G": "𝗚",
    "H": "𝗛",
    "I": "𝗜",
    "J": "𝗝",
    "K": "𝗞",
    "L": "𝗟",
    "M": "𝗠",
    "N": "𝗡",
    "O": "𝗢",
    "P": "𝗣",
    "Q": "𝗤",
    "R": "𝗥",
    "S": "𝗦",
    "T": "𝗧",
    "U": "𝗨",
    "V": "𝗩",
    "W": "𝗪",
    "X": "𝘫",
    "Y": "𝗬",
    "Z": "𝗭",
}


def apply_font(text):
    return "".join(FONTS.get(c, c) for c in text)


@app.on_message(filters.me & filters.command("setname", prefixes="."))
def set_cool_name(client, message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        message.edit_text("Xatolik: Ismni kiritmadigiz! (Masalan: `.setname Asror`)")
        return

    cool_name = apply_font(args[1])
    try:
        client.update_profile(first_name=cool_name)
        message.edit_text(f"✅ Ismingiz o'zgartirildi: **{cool_name}**")
    except Exception as e:
        message.edit_text(f"Xatolik: {e}")


if __name__ == "__main__":
    print("Userbot ishga tushmoqda...")
    app.run()
