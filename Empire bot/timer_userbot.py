import os
import asyncio
from pyrogram import Client

# Bot token
API_ID = 36427121
API_HASH = "f4b857c7d7e08dce9244615ef32d7cc7"
BOT_TOKEN = "8599432298:AAG2ge9-eCDZWwM7ZQmZAFfVKqRykSCL-iA"  # @vento_assist_bot token

app = Client(
    "timer_userbot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

# Timer sozlamalari
CHANNEL_ID = "@vento_news"  # Kanal username
TOTAL_SECONDS = 18 * 60 * 60  # 18 soat (sekundda)

async def countdown_timer():
    """18 soatlik teskari sanoq taymer"""
    remaining = TOTAL_SECONDS
    
    print(f"🚀 Taymer boshlandi: {remaining} sekund qoldi")
    
    # Boshlang'ich xabarni yuborish
    hours = remaining // 3600
    minutes = (remaining % 3600) // 60
    seconds = remaining % 60
    
    message_text = (
        f"⏰ **Taymer**\n\n"
        f"⏳ Qolgan vaqt: {hours:02d}:{minutes:02d}:{seconds:02d}\n"
        f"📊 Jami: {remaining} sekund"
    )
    
    try:
        # Boshlang'ich xabarni yuborish
        sent_message = await app.send_message(CHANNEL_ID, message_text)
        print(f"✅ Boshlang'ich xabar yuborildi: {hours:02d}:{minutes:02d}:{seconds:02d}")
    except Exception as e:
        print(f"❌ Xatolik: {e}")
        return
    
    # Taymer boshlash
    while remaining > 0:
        # 1 sekund kutish
        await asyncio.sleep(1)
        remaining -= 1
        
        # Soat, daqiqa, sekundni hisoblash
        hours = remaining // 3600
        minutes = (remaining % 3600) // 60
        seconds = remaining % 60
        
        # Xabar matnini yangilash
        message_text = (
            f"⏰ **Taymer**\n\n"
            f"⏳ Qolgan vaqt: {hours:02d}:{minutes:02d}:{seconds:02d}\n"
            f"📊 Jami: {remaining} sekund"
        )
        
        try:
            # Xabarni edit qilish
            await sent_message.edit_text(message_text)
            print(f"✅ Xabar edit qilindi: {hours:02d}:{minutes:02d}:{seconds:02d}")
        except Exception as e:
            print(f"❌ Xatolik: {e}")
    
    # Taymer tugadi - hech qanday xabar yubormaydi
    print("🎉 Taymer tugadi! 00:00:00")

async def main():
    """Asosiy funksiya"""
    print("🚀 Timer Userbotni ishga tushirish...")
    print(f"📊 Kanal ID: {CHANNEL_ID}")
    print(f"⏰ Taymer: {TOTAL_SECONDS} sekund")
    
    try:
        await app.start()
        print("✅ Userbot muvaffaqiyatli ishga tushdi!")
        
        # Taymerni boshlash
        await countdown_timer()
        
    except KeyboardInterrupt:
        print("\n⚠️ Userbot to'xtatildi")
    except Exception as e:
        print(f"❌ Xatolik: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await app.stop()
        print("👋 Userbot to'xtatildi")

if __name__ == "__main__":
    app.run(main())
