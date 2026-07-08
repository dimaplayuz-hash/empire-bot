with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix handle_login_upload function
for i, line in enumerate(lines):
    if 'message.reply_text("❌ Bu bot session fayli' in line:
        lines[i] = line.replace('message.reply_text', 'await message.reply_text')
    if 'message.reply_text(' in line and 'Muvaffaqiyatli ulandi' in line:
        lines[i] = line.replace('message.reply_text', 'await message.reply_text')
    if 'message.reply_text' in line and 'Xatolik' in line and 'Qaytadan urinib' in line:
        lines[i] = line.replace('message.reply_text', 'await message.reply_text')
    if 'message.reply_text("❌ Iltimos, session faylni yuboring.")' in line:
        lines[i] = line.replace('message.reply_text', 'await message.reply_text')

# Fix validate_phone_number function
for i, line in enumerate(lines):
    if 'message.reply_text(' in line and 'Noto\'g\'ri telefon raqam' in line:
        lines[i] = line.replace('message.reply_text', 'await message.reply_text')

# Fix handle_login_phone function
for i, line in enumerate(lines):
    if 'message.reply_text(' in line and 'Kod yuborildi' in line:
        lines[i] = line.replace('message.reply_text', 'await message.reply_text')
    if 'message.reply_text(f"⏳ Juda ko\'p urinishlar' in line:
        lines[i] = line.replace('message.reply_text', 'await message.reply_text')
    if 'message.reply_text(f"❌ Xatolik: {str(e)}")' in line and i > 0 and 'Error in handle_login_phone' not in lines[i-1]:
        lines[i] = line.replace('message.reply_text', 'await message.reply_text')

# Fix handle_login_code function
for i, line in enumerate(lines):
    if 'message.reply_text("❌ Avval telefon raqamni kiriting.")' in line:
        lines[i] = line.replace('message.reply_text', 'await message.reply_text')
    if 'message.reply_text("❌ Kod faqat raqamlardan iborat bo\'lishi kerak.")' in line:
        lines[i] = line.replace('message.reply_text', 'await message.reply_text')
    if 'message.reply_text(' in line and '2FA parol kerak' in line:
        lines[i] = line.replace('message.reply_text', 'await message.reply_text')
    if 'message.reply_text(' in line and 'Muvaffaqiyatli login bo\'ldi' in line:
        lines[i] = line.replace('message.reply_text', 'await message.reply_text')

# Fix handle_login_password function
for i, line in enumerate(lines):
    if 'message.reply_text("❌ Avval telefon raqamni kiriting.")' in line:
        lines[i] = line.replace('message.reply_text', 'await message.reply_text')
    if 'message.reply_text(' in line and 'Muvaffaqiyatli login bo\'ldi' in line:
        lines[i] = line.replace('message.reply_text', 'await message.reply_text')
    if 'message.reply_text(f"❌ Noto\'g\'ri parol' in line:
        lines[i] = line.replace('message.reply_text', 'await message.reply_text')

# Fix process_messages function
for i, line in enumerate(lines):
    if 'message.reply_text("❌ Iltimos, session faylni yuboring.")' in line:
        lines[i] = line.replace('message.reply_text', 'await message.reply_text')

with open('main.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('Fixed remaining async/await issues')
