with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix handle_login_upload function (lines 850, 863, 875, 877)
content = content.replace(
    'message.reply_text("❌ Bu bot session fayli. User session faylni yuboring.")',
    'await message.reply_text("❌ Bu bot session fayli. User session faylni yuboring.")'
)
content = content.replace(
    'message.reply_text(\n                f"✅ **Muvaffaqiyatli ulandi!**\n\n',
    'await message.reply_text(\n                f"✅ **Muvaffaqiyatli ulandi!**\n\n'
)
content = content.replace(
    'message.reply_text(f"❌ Xatolik: {str(e)}\\n\\nQaytadan urinib ko\'ring.")',
    'await message.reply_text(f"❌ Xatolik: {str(e)}\\n\\nQaytadan urinib ko\'ring.")'
)
content = content.replace(
    'message.reply_text("❌ Iltimos, session faylni yuboring.")',
    'await message.reply_text("❌ Iltimos, session faylni yuboring.")'
)

# Fix validate_phone_number function
content = content.replace(
    'message.reply_text(\n            "❌ **Noto\'g\'ri telefon raqam!**\n\n',
    'await message.reply_text(\n            "❌ **Noto\'g\'ri telefon raqam!**\n\n'
)

# Fix handle_login_phone function
content = content.replace(
    'message.reply_text(\n            f"✅ **Kod yuborildi!**\n\n',
    'await message.reply_text(\n            f"✅ **Kod yuborildi!**\n\n'
)
content = content.replace(
    'message.reply_text(f"⏳ Juda ko\'p urinishlar. {e.value} soniya kuting.")',
    'await message.reply_text(f"⏳ Juda ko\'p urinishlar. {e.value} soniya kuting.")'
)
content = content.replace(
    'message.reply_text(f"❌ Xatolik: {str(e)}")',
    'await message.reply_text(f"❌ Xatolik: {str(e)}")'
)

# Fix handle_login_code function
content = content.replace(
    'message.reply_text("❌ Avval telefon raqamni kiriting.")',
    'await message.reply_text("❌ Avval telefon raqamni kiriting.")'
)
content = content.replace(
    'message.reply_text("❌ Kod faqat raqamlardan iborat bo\'lishi kerak.")',
    'await message.reply_text("❌ Kod faqat raqamlardan iborat bo\'lishi kerak.")'
)
content = content.replace(
    'message.reply_text(\n                    "🔐 **2FA parol kerak**\n\n',
    'await message.reply_text(\n                    "🔐 **2FA parol kerak**\n\n'
)
content = content.replace(
    'message.reply_text(\n            f"✅ **Muvaffaqiyatli login bo\'ldi!**\n\n',
    'await message.reply_text(\n            f"✅ **Muvaffaqiyatli login bo\'ldi!**\n\n'
)

# Fix handle_login_password function
content = content.replace(
    'message.reply_text("❌ Avval telefon raqamni kiriting.")',
    'await message.reply_text("❌ Avval telefon raqamni kiriting.")'
)
content = content.replace(
    'message.reply_text(\n            f"✅ **Muvaffaqiyatli login bo\'ldi!**\n\n',
    'await message.reply_text(\n            f"✅ **Muvaffaqiyatli login bo\'ldi!**\n\n'
)
content = content.replace(
    'message.reply_text(f"❌ Noto\'g\'ri parol: {str(e)}\\n\\nQaytadan urinib ko\'ring.")',
    'await message.reply_text(f"❌ Noto\'g\'ri parol: {str(e)}\\n\\nQaytadan urinib ko\'ring.")'
)

# Fix process_messages function
content = content.replace(
    'message.reply_text("❌ Iltimos, session faylni yuboring.")',
    'await message.reply_text("❌ Iltimos, session faylni yuboring.")'
)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed all remaining async/await issues')
