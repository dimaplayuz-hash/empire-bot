import os
from pyrogram import Client

# API credentials
API_ID = 36427121
API_HASH = "f4b857c7d7e08dce9244615ef32d7cc7"

print("🚀 Session fayl yaratish...")
print(f"📊 API_ID: {API_ID}")
print(f"🔑 API_HASH: {API_HASH[:10]}...")

app = Client(
    "my_account",
    api_id=API_ID,
    api_hash=API_HASH,
)

print("\n📱 Telefon raqamingizni kiriting (masalan: +998901234567):")
phone = input("Telefon raqam: ")

print("\n🔔 Kod yuborilmoqda...")
app.connect()

try:
    sent_code = app.send_code(phone)
    print(f"✅ Kod yuborildi: {sent_code.phone}")
    
    print("\n🔢 Telegramdan kelgan kodni kiriting:")
    code = input("Kod: ")
    
    try:
        app.sign_in(phone, code)
        print("✅ Muvaffaqiyatli login bo'ldi!")
    except Exception as e:
        if "Two-factor authentication" in str(e) or "2FA" in str(e):
            print("\n🔐 2FA parol kerak:")
            password = input("Parol: ")
            app.sign_in(phone, code, password=password)
            print("✅ Muvaffaqiyatli login bo'ldi!")
        else:
            raise e
    
    print("\n🎉 Session fayl yaratildi: my_account.session")
    print("📁 Bu faylni botga yuboring!")
    
except Exception as e:
    print(f"❌ Xatolik: {e}")
finally:
    app.stop()
