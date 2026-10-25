# 🚀 Koyeb Bulut Platformasida Telegram Botni 24/7 To'xtovsiz Ishga Tushirish Qo'llanmasi

Ushbu loyiha Koyeb'da **24/7 to'xtovsiz, uxlab qolmaydigan (no-sleep) va o'ta tez** ishlash uchun to'liq moslashtirildi. 

Biz loyihaga quyidagilarni qo'shdik:
- ✅ `Dockerfile` — Koyeb tezkor konteyner yaratishi uchun.
- ✅ `Procfile` — Avto-start konfiguratsiyasi.
- ✅ O'rnatilgan Health Check HTTP Serveri (Port 8000) — Koyeb konteynerni doim tirik va sog'lom deb bilishi uchun.
- ✅ Git repozitoriyasi (`main` tarmog'i) yaratildi va barcha kodlar commit qilindi.

---

## 📋 3 Daqiqada Koyeb'ga Qo'yish Bo'yicha Qadamlar:

### 1-qadam: GitHub'da Yangi Repozitoriy Yarating
1. [github.com/new](https://github.com/new) manziliga kiring.
2. Repository name maydoniga masalan: `mafia-bot` deb yozing.
3. **Public** yoki **Private** qilib **"Create repository"** tugmasini bosing.

---

### 2-qadam: Kodni GitHub'ga Yuklang (Push)
Terminalda quyidagi 2 ta buyruqni bajaring (o'zingizning GitHub username'ingiz bilan):

```bash
cd "/home/cyber/Telegram in Antigravity"
git remote add origin https://github.com/SIZNING_USERNAME/mafia-bot.git
git push -u origin main
```
*(GitHub token yoki parolingizni so'rasa, GitHub Personal Access Token'ingizni kiriting).*

---

### 3-qadam: Koyeb'da 1 Bosishda Deploy Qiling
1. **[koyeb.com](https://www.koyeb.com)** saytiga kiring va kiring (yoki bepul ro'yxatdan o'ting).
2. Asosiy sahifada **"Create Service"** (yoki **"Deploy Service"**) tugmasini bosing.
3. Manba sifatida **"GitHub"** ni tanlang va yuqorida ochgan `mafia-bot` repozitoriyangizni tanlang.
4. Sozlamalarda:
   - **Service type:** Web Service (tanlangan bo'ladi).
   - **Instance type:** **Free (Eco)** (tanlang).
   - **Port:** `8000` (Path: `/`).
5. **Environment variables (Atrof-muhit o'zgaruvchilari):**
   - `BOT_TOKEN`: `8821673168:AAEz7S9Y19Gy_amoReQVQFxkoDAo9ilsnG0`
   - `ADMIN_ID`: `7651553630`
6. Pastdagi yashil **"Deploy"** tugmasini bosing!

---

## ⚡ Nega Koyeb Bepul Serverlar Ichida Eng Zo'ri?
1. **Uxlab qolmaydi (No Sleep Mode):** Render yoki Heroku kabi 15 daqiqadan keyin o'chib qolmaydi.
2. **Konteyner tezligi:** Global Anycast tarmog'i orqali Telegram API bilan o'ta tez ishlaydi.
3. **Avtomatik yangilanish:** Keyinchalik bot kodiga biror yangilik qo'shib GitHub'ga `git push` qilsangiz, Koyeb avtomatik ravishda botni serverda yangilab qo'yadi.
4. **Jonli monitoring:** Koyeb sizga bepul monitoring va havola beradi (masalan, `https://mafia-bot-xxx.koyeb.app/` orqali botingiz doim tirik ekanini brauzerda ham ko'ra olasiz).
