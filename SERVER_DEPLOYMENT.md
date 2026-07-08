# Botni Serverga Joylashtirish Ko'rsatmalari

## 1. Server Tanlash

### Bepul Variantlar:
- **Railway.app** - Eng oson, 512MB RAM bepul
- **Render.com** - 512MB RAM bepul
- **Heroku** - Eskirgan, hozir kamroq bepul
- **VPS (DigitalOcean, Linode)** - Pullik, lekin to'liq nazorat

## 2. Railway.app ga Joylashtirish (Eng Oson)

### 2.1 Railway Hisob Ochish
1. https://railway.app ga boring
2. GitHub bilan login qiling
3. $5 bepul kredit olishingiz mumkin

### 2.2 Project Yaratish
1. "New Project" bosing
2. "Deploy from GitHub repo" tanlang
3. Repositoryingizni tanlang

### 2.3 Fayllar Tayyorlash

#### `railway.json` (Project root ga qo'shing)
```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "python main.py",
    "healthcheckPath": "/",
    "healthcheckTimeout": 100,
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

#### `requirements.txt` (Agar yo'q bo'lsa)
```txt
pyrogram==2.0.106
TgCrypto==1.2.5
```

#### `Procfile` (Agar yo'q bo'lsa)
```
worker: python main.py
```

### 2.4 Environment Variables

Railway dashboardda:
1. "Variables" tabiga boring
2. Quyidagilarni qo'shing:

```
API_ID=12345678
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
```

### 2.5 Deploy

1. "Deploy" bosing
2. Loglarni kuzating

## 3. Render.com ga Joylashtirish

### 3.1 Hisob Ochish
1. https://render.com ga boring
2. GitHub bilan login qiling

### 3.2 Web Service Yaratish
1. "New +" -> "Web Service"
2. GitHub repositoryingizni tanlang
3. Build Command: `pip install -r requirements.txt`
4. Start Command: `python main.py`

### 3.3 Environment Variables
Render dashboardda:
```
API_ID=12345678
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
```

## 4. VPS (DigitalOcean) ga Joylashtirish

### 4.1 VPS Yaratish
1. https://digitalocean.com ga boring
2. Droplet yarating (Ubuntu 22.04, $4-6/oy)
3. SSH bilan ulaning

### 4.2 Python O'rnatish
```bash
sudo apt update
sudo apt install python3 python3-pip -y
```

### 4.3 Projectni Clone Qilish
```bash
git clone your-repo-url
cd your-repo
```

### 4.4 Dependencies O'rnatish
```bash
pip3 install -r requirements.txt
```

### 4.5 Environment Variables
```bash
nano .env
```

Quyidagilarni qo'shing:
```
API_ID=12345678
API_HASH=your_api_hash
BOT_TOKEN=your_bot_token
```

### 4.6 Botni Ishga Tushirish
```bash
python3 main.py
```

### 4.7 Backgroundda Ishlatish (PM2)
```bash
sudo npm install -g pm2
pm2 start main.py --name empire-bot
pm2 startup
pm2 save
```

## 5. Muhim Eslatmalar

### 5.1 Session Fayli
- Serverda `user_session.session` fayli yaratilmaydi
- Botni ishga tushirgandan so'ng, serverda telefon raqam kiritish kerak
- Yoki localda session yarating va serverga yuboring

### 5.2 Database
- `database/` papkasi serverda avtomatik yaratiladi
- Agar kerak bo'lsa, backup qiling

### 5.3 Logging
- Railway va Render loglarni dashboardda ko'rsatadi
- VPS da `pm2 logs empire-bot` buyrug'i bilan ko'rish mumkin

### 5.4 Auto-restart
- Railway va Render avtomatik restart qiladi
- VPS da PM2 ishlatish tavsiya etiladi

## 6. Xavfsizlik

- API ID, API HASH, BOT TOKEN hech qachon GitHub ga yubormang
- Environment variables ishlating
- `.gitignore` ga quyidagilarni qo'shing:
```
*.session
.env
database/
__pycache__/
```

## 7. Monitoring

### Railway
- Dashboardda loglarni kuzating
- Metrics tabida resource usage ko'rish mumkin

### Render
- Logs tabida loglarni ko'ring
- Metrics tabida monitoring

### VPS
```bash
pm2 monit
pm2 logs empire-bot
```

## 8. Muammolar va Yechimlar

### 8.1 Memory Error
- Agar "Memory limit exceeded" xatosi bo'lsa:
  - Railway: Upgrade qiling (pullik)
  - Render: Upgrade qiling
  - VPS: RAM oshiring

### 8.2 Session Timeout
- Session fayli serverda yaratilmayapti:
  - Localda session yarating
  - Serverga yuboring
  - Yoki serverda interaktiv login qiling

### 8.3 Bot Javob Bermayapti
- Environment variables tekshiring
- API ID va HASH to'g'ri ekanligiga ishonch hosil qiling
- Loglarni tekshiring
