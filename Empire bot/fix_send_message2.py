with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and fix send_or_edit_message function
for i, line in enumerate(lines):
    if 'def send_or_edit_message(client, target_id, text, reply_markup=None, force_new=False):' in line:
        lines[i] = line.replace('def send_or_edit_message', 'async def send_or_edit_message')
    if 'client.edit_message_text(' in line and 'await' not in line:
        lines[i] = line.replace('client.edit_message_text(', 'await client.edit_message_text(')
    if 'client.send_message(target_id, text, reply_markup=reply_markup)' in line and 'await' not in line:
        lines[i] = line.replace('client.send_message(target_id, text, reply_markup=reply_markup)', 'await client.send_message(target_id, text, reply_markup=reply_markup)')

# Fix all calls to send_or_edit_message to use await
for i, line in enumerate(lines):
    if 'send_or_edit_message(' in line and 'await' not in line and 'def send_or_edit_message' not in line:
        lines[i] = line.replace('send_or_edit_message(', 'await send_or_edit_message(')

with open('main.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('Fixed send_or_edit_message async issues (v2)')
