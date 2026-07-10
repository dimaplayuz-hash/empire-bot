import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. resolve_chat_id
content = content.replace('def resolve_chat_id(client, raw: str):', 'async def resolve_chat_id(client, raw: str):')
content = content.replace('chat = client.join_chat(target)', 'chat = await client.join_chat(target)')
content = content.replace('chat = client.get_chat(target)', 'chat = await client.get_chat(target)')

# 2. get_user_client_started
content = content.replace('def get_user_client_started(user_id):', 'async def get_user_client_started(user_id):')
content = content.replace('client.start()', 'await client.start()')

# 3. scrape_task
content = content.replace('def scrape_task(target_id, raw_group, filter_type="⚡ Avtomatik (Tez)", message_count=None):', 'async def scrape_task(target_id, raw_group, filter_type="⚡ Avtomatik (Tez)", message_count=None):')
content = content.replace('user_client = get_user_client_started(target_id)', 'user_client = await get_user_client_started(target_id)')
content = content.replace('chat_id, chat_title = resolve_chat_id(user_client, raw_group)', 'chat_id, chat_title = await resolve_chat_id(user_client, raw_group)')
content = content.replace('for message in user_client.get_chat_history', 'async for message in user_client.get_chat_history')
content = content.replace('for member in user_client.get_chat_members', 'async for member in user_client.get_chat_members')

# 4. broadcast_task
content = content.replace('def broadcast_task(target_id, recipients, body):', 'async def broadcast_task(target_id, recipients, body):')
content = content.replace('user_client.send_message(username, body)', 'await user_client.send_message(username, body)')

# 5. handle_login_upload
content = content.replace('user_client.connect()', 'await user_client.connect()')
content = content.replace('me = user_client.get_me()', 'me = await user_client.get_me()')

# 6. threading to asyncio.create_task in main menu
# scrape threading
content = re.sub(
    r'threading\.Thread\(\s*target=scrape_task,\s*args=\(user_id, selection\["group"\], filter_type\),\s*daemon=True,\s*\)\.start\(\)',
    r'asyncio.create_task(scrape_task(user_id, selection["group"], filter_type))',
    content
)
# scrape messages threading
content = re.sub(
    r'threading\.Thread\(\s*target=scrape_task,\s*args=\(user_id, selection\["group"\], "📊 Xabarlar orqali \(Sekin\)", message_count\),\s*daemon=True,\s*\)\.start\(\)',
    r'asyncio.create_task(scrape_task(user_id, selection["group"], "📊 Xabarlar orqali (Sekin)", message_count))',
    content
)
# broadcast threading
content = re.sub(
    r'threading\.Thread\(\s*target=broadcast_task,\s*args=\(user_id, usernames, msg_text\),\s*daemon=True,\s*\)\.start\(\)',
    r'asyncio.create_task(broadcast_task(user_id, usernames, msg_text))',
    content
)

# 7. asyncio import might be there, we also need to fix time.sleep to asyncio.sleep inside async functions
content = re.sub(r'time\.sleep\((\d+(\.\d+)?)\)', r'await asyncio.sleep(\1)', content)

# 8. search global chats
content = content.replace('result = user_client.invoke(functions.contacts.Search(q=keyword, limit=20))', 'result = await user_client.invoke(functions.contacts.Search(q=keyword, limit=20))')


with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed async issues!")
