with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix send_or_edit_message to be async
content = content.replace(
    'def send_or_edit_message(client, target_id, text, reply_markup=None, force_new=False):',
    'async def send_or_edit_message(client, target_id, text, reply_markup=None, force_new=False):'
)

# Fix client.edit_message_text to await
content = content.replace(
    'client.edit_message_text(',
    'await client.edit_message_text('
)

# Fix client.send_message to await
content = content.replace(
    'client.send_message(target_id, text, reply_markup=reply_markup)',
    'await client.send_message(target_id, text, reply_markup=reply_markup)'
)

# Fix all calls to send_or_edit_message to use await
content = content.replace(
    'send_or_edit_message(',
    'await send_or_edit_message('
)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed send_or_edit_message async issues')
