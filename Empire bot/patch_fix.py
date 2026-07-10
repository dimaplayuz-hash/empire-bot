with open("main.py", "r", encoding="utf-8") as f:
    code = f.read()

code = code.replace(
    '''text_msg += f"🔹 **ID:** `{db_id}`\\n📝 Guruh: _{info.get('title', 'Noma\\'lum')}_\\n👥 Qoldi: **{len(info.get('users', []))}** ta\\n🕒 Vaqt: {info.get('timestamp', 'Noma\\'lum')}\\n\\n"''',
    '''title = info.get("title", "Noma'lum")\n                    time_str = info.get("timestamp", "Noma'lum")\n                    text_msg += f"🔹 **ID:** `{db_id}`\\n📝 Guruh: _{title}_\\n👥 Qoldi: **{len(info.get('users', []))}** ta\\n🕒 Vaqt: {time_str}\\n\\n"'''
)

code = code.replace(
    '''text_msg += f"🔹 **ID:** `{db_id}` | Guruh: _{info.get('title', 'Noma\\'lum')}_ | Qoldi: **{len(info.get('users', []))}**\\n"''',
    '''title = info.get("title", "Noma'lum")\n                text_msg += f"🔹 **ID:** `{db_id}` | Guruh: _{title}_ | Qoldi: **{len(info.get('users', []))}**\\n"'''
)

with open("main.py", "w", encoding="utf-8") as f:
    f.write(code)
