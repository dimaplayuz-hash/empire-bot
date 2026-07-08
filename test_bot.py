import os
from pyrogram import Client, filters

# Environment variables
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

print(f"🔍 Environment variables:")
print(f"API_ID: {API_ID}")
print(f"API_HASH: {API_HASH[:10]}... if API_HASH else None")
print(f"BOT_TOKEN: {BOT_TOKEN[:10]}... if BOT_TOKEN else None")

if not API_ID:
    raise ValueError("API_ID environment variable not set")
if not API_HASH:
    raise ValueError("API_HASH environment variable not set")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set")

API_ID = int(API_ID)

app = Client(
    "test_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

@app.on_message(filters.command("start") & filters.private)
def start(client, message):
    print(f"📩 /start buyrug'i olindi: {message.from_user.id}")
    message.reply_text("✅ Test bot ishlayapti!")

print("🚀 Test botni ishga tushirish...")
app.run()
