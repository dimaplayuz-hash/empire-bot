with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix all message.reply_text to await message.reply_text in async functions
for i, line in enumerate(lines):
    if 'message.reply_text' in line and 'await' not in line:
        # Skip if it's in a sync function (validate_phone_number is sync)
        if i > 0 and 'def validate_phone_number' in lines[i-1]:
            continue
        lines[i] = line.replace('message.reply_text', 'await message.reply_text')

with open('main.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('Fixed async/await issues')
