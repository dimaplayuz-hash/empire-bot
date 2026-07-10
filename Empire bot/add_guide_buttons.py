with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add guide button handlers before the command handlers
guide_handlers = '''# ================= YORIQNOMA TUGMALARI =================
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
        "📖 **API_ID olish bo'yicha yoriqnoma:**\\n\\n"
        "1️⃣ Quyidagi saytga o'ting:\\n"
        "[my.telegram.org](https://my.telegram.org)\\n\\n"
        "2️⃣ Telegram bilan login qiling (telefon raqam + kod)\\n\\n"
        "3️⃣ 'API development tools' bo'limiga o'ting\\n\\n"
        "4️⃣ 'Create new application' tugmasini bosing\\n\\n"
        "5️⃣ Ma'lumotlarni to'ldiring:\\n"
        "   - App title: Empire Bot\\n"
        "   - Short name: empirebot\\n"
        "   - Platform: Desktop\\n\\n"
        "6️⃣ 'Create application' tugmasini bosing\\n\\n"
        "7️⃣ API_ID ni ko'ring (masalan: 12345678)\\n\\n"
        "❌ Yopish uchun: /cancel"
    )
    await callback.message.edit_text(text, disable_web_page_preview=True)

@bot_app.on_callback_query(filters.regex("^guide_api_hash$"))
async def guide_api_hash_callback(client, callback):
    """API_HASH yoriqnomasini ko'rsatish"""
    text = (
        "📖 **API_HASH olish bo'yicha yoriqnoma:**\\n\\n"
        "1️⃣ Quyidagi saytga o'ting:\\n"
        "[my.telegram.org](https://my.telegram.org)\\n\\n"
        "2️⃣ 'API development tools' bo'limiga o'ting\\n\\n"
        "3️⃣ Siz yaratgan applicationni tanlang\\n\\n"
        "4️⃣ API_HASH ni ko'ring (masalan: a1b2c3d4e5f6g7h8i9j0)\\n\\n"
        "5️⃣ API_HASH ni nusxalab botga yuboring\\n\\n"
        "❌ Yopish uchun: /cancel"
    )
    await callback.message.edit_text(text, disable_web_page_preview=True)


'''

# Find the line with "# ================= ADMINLIK TIZIMI =================" and insert before it
content = content.replace('# ================= ADMINLIK TIZIMI =================', guide_handlers + '# ================= ADMINLIK TIZIMI =================')

# Update start_command to include guide button
old_start_text = '''        text = (
            "🔐 **Botdan foydalanish uchun login qiling**\\n\\n"
            "📱 **Avval API_ID va API_HASH oling:**\\n\\n"
            "1️⃣ Quyidagi saytga o'ting:\\n"
            "[my.telegram.org](https://my.telegram.org)\\n\\n"
            "2️⃣ Login qiling\\n"
            "3️⃣ 'API development tools' bo'limiga o'ting\\n"
            "4️⃣ Yangi application yaratib API_ID va API_HASH oling\\n\\n"
            "🔑 **API_ID ni kiriting:**\\n"
            "Masalan: `12345678`\\n\\n"
            "❌ Bekor qilish uchun: /cancel"
        )
        await message.reply_text(text, disable_web_page_preview=True)'''

new_start_text = '''        text = (
            "🔐 **Botdan foydalanish uchun login qiling**\\n\\n"
            "🔑 **API_ID ni kiriting:**\\n"
            "Masalan: `12345678`\\n\\n"
            "❌ Bekor qilish uchun: /cancel"
        )
        await message.reply_text(text, reply_markup=api_id_guide_keyboard())'''

content = content.replace(old_start_text, new_start_text)

# Update handle_login_api_id to include guide button
old_api_id_text = '''        await message.reply_text(
            f"✅ API_ID qabul qilindi: `{api_id}`\\n\\n"
            f"🔑 **API_HASH ni kiriting:**\\n"
            f"my.telegram.org dan olingan API_HASH ni yuboring."
        )'''

new_api_id_text = '''        await message.reply_text(
            f"✅ API_ID qabul qilindi: `{api_id}`\\n\\n"
            f"🔑 **API_HASH ni kiriting:**\\n"
            f"my.telegram.org dan olingan API_HASH ni yuboring.",
            reply_markup=api_hash_guide_keyboard()
        )'''

content = content.replace(old_api_id_text, new_api_id_text)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Added guide buttons for API_ID and API_HASH')
