with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the line with "# Login flow - session fayl yuborilganda"
for i, line in enumerate(lines):
    if '# Login flow - session fayl yuborilganda' in line:
        # Insert API_ID and API_HASH handlers before this line
        insert_lines = [
            '    # Login flow - API_ID kiritilganda\n',
            '    if state == "login_api_id":\n',
            '        await handle_login_api_id(client, message, user_id, text)\n',
            '        return\n',
            '    \n',
            '    # Login flow - API_HASH kiritilganda\n',
            '    if state == "login_api_hash":\n',
            '        await handle_login_api_hash(client, message, user_id, text)\n',
            '        return\n',
            '    \n',
        ]
        lines[i:i] = insert_lines
        break

with open('main.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('Added API_ID/API_HASH handlers to process_messages')
