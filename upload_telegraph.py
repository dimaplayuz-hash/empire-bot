import requests
import json

files = [
    r"C:\Users\user\.gemini\antigravity\brain\e4cb33ff-0a13-4f90-975b-da90b26f01e4\media__1782316982161.png",
    r"C:\Users\user\.gemini\antigravity\brain\e4cb33ff-0a13-4f90-975b-da90b26f01e4\media__1782317060600.png",
    r"C:\Users\user\.gemini\antigravity\brain\e4cb33ff-0a13-4f90-975b-da90b26f01e4\media__1782317142261.png",
    r"C:\Users\user\.gemini\antigravity\brain\e4cb33ff-0a13-4f90-975b-da90b26f01e4\media__1782317304367.png",
    r"C:\Users\user\.gemini\antigravity\brain\e4cb33ff-0a13-4f90-975b-da90b26f01e4\media__1782317576129.png"
]

urls = []
for f in files:
    with open(f, 'rb') as img:
        response = requests.post('https://telegra.ph/upload', files={'file': open(f, 'rb')})
        result = response.json()
        if isinstance(result, list):
            urls.append('https://telegra.ph' + result[0]['src'])
        else:
            print("Error uploading", f, result)

# Create an account
acc_res = requests.get('https://api.telegra.ph/createAccount?short_name=VENTO&author_name=VENTO').json()
access_token = acc_res['result']['access_token']

# Create content
content = [{"tag": "p", "children": ["Quyida API_ID va API_HASH olish bo'yicha qadam-ba-qadam rasmli qo'llanma:"]}]
for url in urls:
    content.append({"tag": "img", "attrs": {"src": url}})
    content.append({"tag": "br"})

# Create page
page_res = requests.post('https://api.telegra.ph/createPage', data={
    'access_token': access_token,
    'title': 'API_ID va API_HASH olish yoriqnomasi',
    'content': json.dumps(content),
    'return_content': 'false'
}).json()

print("Telegraph URL:", page_res['result']['url'])
