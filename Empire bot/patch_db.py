import json
import os
import re

with open("main.py", "r", encoding="utf-8") as f:
    code = f.read()

# 1. Modify database helper functions
db_funcs = """
import random
from datetime import datetime

def get_user_json_file(user_id):
    return os.path.join(DATABASE_DIR, f"users_{user_id}.json")

def migrate_database(user_id):
    txt_file = os.path.join(DATABASE_DIR, f"users_{user_id}.txt")
    json_file = get_user_json_file(user_id)
    if os.path.exists(txt_file) and not os.path.exists(json_file):
        with open(txt_file, "r", encoding="utf-8") as f:
            users = [line.strip() for line in f if line.strip()]
        if users:
            data = {
                "databases": {
                    "1000": {
                        "title": "Eski baza",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                        "users": users
                    }
                },
                "selected_db": "1000"
            }
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        try:
            os.remove(txt_file)
        except:
            pass

def get_all_databases(user_id):
    migrate_database(user_id)
    json_file = get_user_json_file(user_id)
    if not os.path.exists(json_file):
        return {}
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            return json.load(f).get("databases", {})
    except:
        return {}

def get_database(user_id, db_id):
    dbs = get_all_databases(user_id)
    return dbs.get(str(db_id), {})

def save_database(user_id, title, new_users, db_id=None):
    migrate_database(user_id)
    json_file = get_user_json_file(user_id)
    data = {"databases": {}, "selected_db": None}
    if os.path.exists(json_file):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            pass
    
    if not db_id:
        # Generate random 4-digit ID
        while True:
            db_id = str(random.randint(1000, 9999))
            if db_id not in data["databases"]:
                break
    else:
        db_id = str(db_id)
        
    existing_users = data["databases"].get(db_id, {}).get("users", [])
    updated_users = list(set(existing_users) | set(new_users))
    
    data["databases"][db_id] = {
        "title": title,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "users": updated_users
    }
    data["selected_db"] = db_id
    
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)
        
    return db_id

def clear_user_database(user_id, db_id=None):
    json_file = get_user_json_file(user_id)
    if not os.path.exists(json_file):
        return
        
    if db_id is None:
        # Clear all
        if os.path.exists(json_file):
            os.remove(json_file)
    else:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if str(db_id) in data["databases"]:
                del data["databases"][str(db_id)]
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except:
            pass

def load_user_database(user_id):
    migrate_database(user_id)
    json_file = get_user_json_file(user_id)
    if not os.path.exists(json_file):
        return []
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            selected = data.get("selected_db")
            if selected and selected in data.get("databases", {}):
                return data["databases"][selected].get("users", [])
            return []
    except:
        return []
"""

old_db_funcs = """def get_user_file(user_id):
    return os.path.join(DATABASE_DIR, f"users_{user_id}.txt")


def load_user_database(user_id):
    file_path = get_user_file(user_id)
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def save_user_database(user_id, usernames):
    with open(get_user_file(user_id), "w", encoding="utf-8") as f:
        for username in usernames:
            f.write(f"{username}\\n")


def clear_user_database(user_id):
    file_path = get_user_file(user_id)
    if os.path.exists(file_path):
        os.remove(file_path)"""

if old_db_funcs in code:
    code = code.replace(old_db_funcs, db_funcs)
else:
    print("WARNING: old_db_funcs not found!")

# 1. Scrape task saving
scrape_old = """        existing = load_user_database(target_id)
        existing_set = set(existing)
        new_count = sum(1 for u in scraped if u not in existing_set)
        all_users = existing + [u for u in sorted(scraped) if u not in existing_set]
        save_user_database(target_id, all_users)"""
scrape_new = """        # We save this scrape session to a new database
        existing = []
        existing_set = set()
        new_count = len(scraped)
        all_users = [u for u in sorted(scraped)]
        db_id = save_database(target_id, chat_title, all_users)"""
if scrape_old in code:
    code = code.replace(scrape_old, scrape_new)

# 2. Add user manual input saving
add_user_old = """            if users_to_add:
                existing_users = load_user_database(user_id)
                updated_users = set(existing_users) | set(users_to_add)
                save_user_database(user_id, updated_users)"""
add_user_new = """            if users_to_add:
                # Add to a new DB called 'Qo'lda qo'shilganlar'
                save_database(user_id, "Qo'lda qo'shilganlar", users_to_add)"""
if add_user_old in code:
    code = code.replace(add_user_old, add_user_new)

# 3. Handle '📁 Yig'ilgan userlar' menu button
yigil_old = """        elif text == "📁 Yig'ilgan userlar":
            usernames = load_user_database(user_id)
            if usernames:
                await send_or_edit_message(
                    client,
                    user_id,
                    f"📁 Bazangizda **{len(usernames)}** ta user bor.",
                    reply_markup=database_menu(),
                )
                show_paginated_users(client, user_id, usernames)
            else:
                await send_or_edit_message(
                    client,
                    user_id,
                    "❌ Hozircha bazangiz bo'sh. Avval `🚀 Scraper` orqali user yig'ing.",
                )"""
yigil_new = """        elif text == "📁 Yig'ilgan userlar":
            dbs = get_all_databases(user_id)
            if dbs:
                text_msg = f"📁 **Saqlangan foydalanuvchilar bazasi**\\n📊 Jami guruhlar: **{len(dbs)}** ta\\n\\n"
                for db_id, info in dbs.items():
                    text_msg += f"🔹 **ID:** `{db_id}`\\n📝 Guruh: _{info.get('title', 'Noma\\'lum')}_\\n👥 Qoldi: **{len(info.get('users', []))}** ta\\n🕒 Vaqt: {info.get('timestamp', 'Noma\\'lum')}\\n\\n"
                
                text_msg += "Tavsilotni olish uchun bazaning ID raqamini pastga yozing:"
                user_states[user_id] = "wait_db_id"
                await send_or_edit_message(
                    client,
                    user_id,
                    text_msg,
                    reply_markup=database_menu(),
                )
            else:
                await send_or_edit_message(
                    client,
                    user_id,
                    "❌ Hozircha bazangiz bo'sh. Avval `🚀 Scraper` orqali user yig'ing.",
                )"""
if yigil_old in code:
    code = code.replace(yigil_old, yigil_new)

# 4. Handle "wait_db_id" state
db_id_state = """
    # ----- DATABASE SELECTION -----
    elif state == "wait_db_id":
        if text in ["🏠 Asosiy menyu", "🔙 Orqaga", "❌ Bekor qilish"]:
            user_states[user_id] = "menu"
            await send_or_edit_message(
                client, user_id, "🏠 Asosiy menyuga qaytdingiz.", reply_markup=main_menu()
            )
            return
            
        db_id = text.strip()
        db = get_database(user_id, db_id)
        if not db:
            await send_or_edit_message(
                client, user_id, "❌ Bunday ID topilmadi. Qaytadan kiriting:", reply_markup=database_menu()
            )
            return
            
        # Select this DB
        json_file = get_user_json_file(user_id)
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["selected_db"] = db_id
            with open(json_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except:
            pass

        users = db.get("users", [])
        title = db.get("title", "Noma'lum")
        
        user_states[user_id] = "broadcast_wait_count"
        await send_or_edit_message(
            client,
            user_id,
            f"✅ **Baza tanlandi!**\\n\\n📁 Guruh: _{title}_\\n👥 Jami {len(users)} ta foydalanuvchi.\\n\\n"
            f"📤 Ulardan nechtasini yuboray? (Raqam kiriting)\\n_Eslatma: To'liq ro'yxat bazada saqlanadi._\\nID: {db_id}",
            reply_markup=broadcast_count_menu()
        )
        return
"""

if '# ----- SCRAPER (FULL OLISH) -----' in code:
    code = code.replace('# ----- SCRAPER (FULL OLISH) -----', db_id_state + '\n    # ----- SCRAPER (FULL OLISH) -----')

# 5. Handle broadcast wait count logic change
broad_old = """    # ----- XABAR YUBORISH (BROADCAST) -----
    elif state == "broadcast_wait_count":
        usernames = load_user_database(user_id)
        if text == "Barchasiga yuborish":
            count = len(usernames)
        else:
            try:
                count = int(text)
                if count <= 0:
                    raise ValueError
                if count > len(usernames):
                    count = len(usernames)
            except ValueError:
                await send_or_edit_message(
                    client, user_id, "❌ Noto'g'ri son kiritildi. Qaytadan kiriting:", reply_markup=broadcast_count_menu()
                )
                return
        
        temp_broadcast_count[user_id] = count"""
broad_new = """    # ----- XABAR YUBORISH (BROADCAST) -----
    elif state == "broadcast_wait_count":
        usernames = load_user_database(user_id)
        if not usernames:
            await send_or_edit_message(
                client, user_id, "❌ Baza topilmadi yoki bo'sh. Qaytadan baza tanlang.", reply_markup=main_menu()
            )
            user_states[user_id] = "menu"
            return
            
        if text == "Barchasiga yuborish":
            count = len(usernames)
        else:
            try:
                count = int(text)
                if count <= 0:
                    raise ValueError
                if count > len(usernames):
                    count = len(usernames)
            except ValueError:
                await send_or_edit_message(
                    client, user_id, "❌ Noto'g'ri son kiritildi. Qaytadan kiriting:", reply_markup=broadcast_count_menu()
                )
                return
        
        temp_broadcast_count[user_id] = count"""
if broad_old in code:
    code = code.replace(broad_old, broad_new)

# 6. Change "Xabar yuborish" button to ask for DB first
xabar_old = """        elif text == "📨 Xabar yuborish" or text == "Xabar yuborish":
            usernames = load_user_database(user_id)
            if not usernames:
                await send_or_edit_message(
                    client,
                    user_id,
                    "❌ Bazangizda userlar yo'q. Avval `🚀 Scraper` orqali user yig'ing.",
                )
                return

            user_states[user_id] = "broadcast_wait_count"
            await send_or_edit_message(
                client,
                user_id,
                f"📨 **XABAR YUBORISH**\\n\\n"
                f"Qanchasiga yuboray? (Bazangizda **{len(usernames)}** ta user bor)\\n\\n"
                "Nechta foydalanuvchiga xabar yuborishni xohlaysiz? Raqam kiriting yeki pastdagi tugmani bosing:",
                reply_markup=broadcast_count_menu(),
            )"""
xabar_new = """        elif text == "📨 Xabar yuborish" or text == "Xabar yuborish":
            dbs = get_all_databases(user_id)
            if not dbs:
                await send_or_edit_message(
                    client,
                    user_id,
                    "❌ Bazangizda userlar yo'q. Avval `🚀 Scraper` orqali user yig'ing.",
                )
                return
            
            text_msg = f"📨 **XABAR YUBORISH**\\n\\nQaysi bazadagi userlarga xabar yubormoqchisiz?\\n\\n"
            for db_id, info in dbs.items():
                text_msg += f"🔹 **ID:** `{db_id}` | Guruh: _{info.get('title', 'Noma\\'lum')}_ | Qoldi: **{len(info.get('users', []))}**\\n"
            text_msg += "\\nID raqamini yozing:"
            
            user_states[user_id] = "wait_db_id"
            await send_or_edit_message(
                client,
                user_id,
                text_msg,
                reply_markup=cancel_menu(),
            )"""
if xabar_old in code:
    code = code.replace(xabar_old, xabar_new)

with open("main.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Patch applied successfully.")
