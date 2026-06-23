import os
from pyrogram import Client, filters

# Environment variables
API_ID = int(os.getenv("API_ID", 36427121))
API_HASH = os.getenv("API_HASH", "f4b857c7d7e08dce9244615ef32d7cc7")
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set")

app = Client(
    "test_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

@app.on_message(filters.command("start") & filters.private)
def start(client, message):
    message.reply_text("✅ Test bot ishlayapti!")

print("🚀 Test botni ishga tushirish...")
app.run()
