with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add API_ID/API_HASH to login_data structure
# Modify start_command to ask for API_ID first
old_start = '''    # Login check
    if not is_user_logged_in(user_id):
        # Yangi login jarayoni - telefon raqam so'rash
        user_states[user_id] = "login_phone"
        text = (
            "🔐 **Botdan foydalanish uchun login qiling**\\n\\n"
            "📱 **Telefon raqamingizni kiriting:**\\n"
            "Masalan: `+998901234567` yoki `998901234567`\\n\\n"
            "📂 **Yoki session fayl yuboring:**\\n"
            "Agar oldin session yaratgan bo'lsangiz, .session faylini yuborishingiz mumkin.\\n\\n"
            "❌ Bekor qilish uchun: /cancel"
        )
        await message.reply_text(text)
        return'''

new_start = '''    # Login check
    if not is_user_logged_in(user_id):
        # Yangi login jarayoni - API_ID so'rash
        user_states[user_id] = "login_api_id"
        text = (
            "🔐 **Botdan foydalanish uchun login qiling**\\n\\n"
            "📱 **my.telegram.org dan API_ID ni kiriting:**\\n"
            "Masalan: `12345678`\\n\\n"
            "❌ Bekor qilish uchun: /cancel"
        )
        await message.reply_text(text)
        return'''

content = content.replace(old_start, new_start)

# Add new handler for API_ID input
new_handler = '''# API_ID/API_HASH handlers
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
            f"✅ API_ID qabul qilindi: `{api_id}`\\n\\n"
            f"🔑 **API_HASH ni kiriting:**\\n"
            f"my.telegram.org dan olingan API_HASH ni yuboring."
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
        f"✅ API_HASH qabul qilindi.\\n\\n"
        f"📱 **Telefon raqamingizni kiriting:**\\n"
        f"Masalan: `+998901234567` yoki `998901234567`\\n\\n"
        f"📂 **Yoki session fayl yuboring:**\\n"
        f"Agar oldin session yaratgan bo'lsangiz, .session faylini yuborishingiz mumkin."
    )
    return True


# Telefon raqam formatini tekshirish'''

content = content.replace('# Telefon raqam formatini tekshirish', new_handler)

# Update process_messages to handle login_api_id and login_api_hash states
old_process = '''    # Login flow - session fayl yuborilganda
    if state == "login_upload":
        if message.document:
            await handle_login_upload(client, message, user_id)
        else:
            await message.reply_text("❌ Iltimos, session faylni yuboring.")
        return
    
    # Login flow - telefon raqam kiritilganda
    if state == "login_phone":'''

new_process = '''    # Login flow - API_ID kiritilganda
    if state == "login_api_id":
        await handle_login_api_id(client, message, user_id, text)
        return
    
    # Login flow - API_HASH kiritilganda
    if state == "login_api_hash":
        await handle_login_api_hash(client, message, user_id, text)
        return
    
    # Login flow - session fayl yuborilganda
    if state == "login_upload":
        if message.document:
            await handle_login_upload(client, message, user_id)
        else:
            await message.reply_text("❌ Iltimos, session faylni yuboring.")
        return
    
    # Login flow - telefon raqam kiritilganda
    if state == "login_phone":'''

content = content.replace(old_process, new_process)

# Update handle_login_phone to use dynamic API_ID/API_HASH
old_phone = '''    phone = validate_phone_number(phone_text)
    
    if not phone:
        await message.reply_text(
            "❌ **Noto'g'ri telefon raqam!**\\n\\n"
            "Iltimos, to'g'ri formatda kiriting:\\n"
            "Masalan: `+998901234567` yoki `998901234567`"
        )
        return False
    
    # User client yaratish
    user_client = Client(
        f"temp_login_{user_id}",
        api_id=config["API_ID"],
        api_hash=config["API_HASH"],
        workdir=BASE_DIR,
    )'''

new_phone = '''    phone = validate_phone_number(phone_text)
    
    if not phone:
        await message.reply_text(
            "❌ **Noto'g'ri telefon raqam!**\\n\\n"
            "Iltimos, to'g'ri formatda kiriting:\\n"
            "Masalan: `+998901234567` yoki `998901234567`"
        )
        return False
    
    # API_ID/API_HASH olish
    if user_id not in login_data or "api_id" not in login_data[user_id]:
        await message.reply_text("❌ API_ID/API_HASH topilmadi. Qaytadan boshlang.")
        return False
    
    api_id = login_data[user_id]["api_id"]
    api_hash = login_data[user_id]["api_hash"]
    
    # User client yaratish
    user_client = Client(
        f"temp_login_{user_id}",
        api_id=api_id,
        api_hash=api_hash,
        workdir=BASE_DIR,
    )'''

content = content.replace(old_phone, new_phone)

# Update handle_login_code to use dynamic API_ID/API_HASH
old_code = '''    # Clientni qaytadan yaratish va saqlash
    user_client = Client(
        session_name,
        api_id=config["API_ID"],
        api_hash=config["API_HASH"],
        workdir=BASE_DIR,
    )'''

new_code = '''    # API_ID/API_HASH olish
    if user_id not in login_data or "api_id" not in login_data[user_id]:
        await message.reply_text("❌ API_ID/API_HASH topilmadi. Qaytadan boshlang.")
        return False
    
    api_id = login_data[user_id]["api_id"]
    api_hash = login_data[user_id]["api_hash"]
    
    # Clientni qaytadan yaratish va saqlash
    user_client = Client(
        session_name,
        api_id=api_id,
        api_hash=api_hash,
        workdir=BASE_DIR,
    )'''

content = content.replace(old_code, new_code)

# Update handle_login_password to use dynamic API_ID/API_HASH
old_password = '''    # Clientni qaytadan yaratish va saqlash
    user_client = Client(
        session_name,
        api_id=config["API_ID"],
        api_hash=config["API_HASH"],
        workdir=BASE_DIR,
    )'''

new_password = '''    # API_ID/API_HASH olish
    if user_id not in login_data or "api_id" not in login_data[user_id]:
        await message.reply_text("❌ API_ID/API_HASH topilmadi. Qaytadan boshlang.")
        return False
    
    api_id = login_data[user_id]["api_id"]
    api_hash = login_data[user_id]["api_hash"]
    
    # Clientni qaytadan yaratish va saqlash
    user_client = Client(
        session_name,
        api_id=api_id,
        api_hash=api_hash,
        workdir=BASE_DIR,
    )'''

content = content.replace(old_password, new_password)

# Update handle_login_upload to use dynamic API_ID/API_HASH
old_upload = '''            # Client yaratish va tekshirish
            session_name = f"sessions/user_{user_id}"
            user_client = Client(
                session_name,
                api_id=config["API_ID"],
                api_hash=config["API_HASH"],
                workdir=BASE_DIR,
            )'''

new_upload = '''            # API_ID/API_HASH olish (agar session fayl yuborilsa, config dan olinadi)
            api_id = config["API_ID"]
            api_hash = config["API_HASH"]
            
            # Client yaratish va tekshirish
            session_name = f"sessions/user_{user_id}"
            user_client = Client(
                session_name,
                api_id=api_id,
                api_hash=api_hash,
                workdir=BASE_DIR,
            )'''

content = content.replace(old_upload, new_upload)

# Update cancel_command to include new states
old_cancel = '''    if state in ["login_phone", "login_code", "login_password", "login_upload"]:'''

new_cancel = '''    if state in ["login_api_id", "login_api_hash", "login_phone", "login_code", "login_password", "login_upload"]:'''

content = content.replace(old_cancel, new_cancel)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Made API_ID/API_HASH dynamic')
