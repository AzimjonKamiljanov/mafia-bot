# 🕵️ Detektiv (Mafia) Telegram Bot

O'zbek tilidagi eng to'liq, xavfsiz va qiziqarli Telegram Mafiya/Detektiv o'yini boti. Ushbu bot zamonaviy asinxron Python arxitekturasi (`python-telegram-bot >= 21`, `aiosqlite`) asosida ishlab chiqilgan bo'lib, guruhlarda va shaxsiy xabarlarda qulay interaktiv boshqaruvni ta'minlaydi.

---

## 📋 Mundarija
1. [Loyiha Haqida](#-loyiha-haqida)
2. [Asosiy Xususiyatlar](#-asosiy-xususiyatlar)
3. [Arxitektura va Tizim Dizayni](#-arxitektura-va-tizim-dizayni)
4. [O'yin Qoidalari va Rollar](#-oyin-qoidalari-va-rollar)
5. [Tezkor Boshlash (5 Qadam)](#-tezkor-boshlash-5-qadam)
6. [Muhit O'zgaruvchilari (Environment Variables)](#-muhit-ozgaruvchilari)
7. [Buyruqlar Ma'lumotnomasi](#-buyruqlar-malumotnomasi)
8. [Docker & Docker Compose orqali O'rnatish](#-docker--docker-compose)
9. [Ma'lumotlar Bazasini Zaxiralash va Migratsiya](#-malumotlar-bazasini-zaxiralash)
10. [Testlash (Unit & Integration Tests)](#-testlash)
11. [Xavfsizlik va Maxfiylikni Saqlash](#-xavfsizlik-va-maxfiylik)

---

## 🔎 Loyiha Haqida

`mafia-bot` — bu do'stlar davrasida o'ynaladigan klassik "Mafiya" va "Detektiv" rolli stol o'yinining to'liq avtomatlashtirilgan Telegram versiyasi. Bot o'yin fazalarini (Kutish, Tun, Kun, Sud, Hukm) o'zi boshqaradi, ovozlarni hisoblaydi, rollarni taqsimlaydi va o'yinchilarning statistikasini yuritadi.

---

## ✨ Asosiy Xususiyatlar

- 🎭 **Ko'p sonli rollar:** Fuqaro, Detektiv, Shifokor, Mafiya, Don, Maniak, Pirotexnik, Kamikadze, Advokat, Joker, Firibgar va boshqalar.
- ⚡ **Asinxron va Tezkor:** `python-telegram-bot v21` va `aiosqlite` bilan to'liq asinxron arxitektura.
- 🔒 **Kriptografik va Poygaga Chidamli Baza:** Barcha balans va inventar yangilanishlari bitta atomik SQL so'rovi bilan bajariladi (race condition xavfisiz).
- ⏱️ **To'liq Nazorat Qilinadigan Taymerlar:** O'yin `/stop_game` buyrug'i bilan to'xtatilganda barcha fon vazifalari toza bekor qilinadi.
- 💰 **Oltin Tashlash (Drop) Tizimi:** Guruhlarga tushadigan oltin xaltalari `uuid4` identifikatorlari va 10 daqiqalik yashash muddati bilan himoyalangan.
- 🤖 **Admin AI:** Tabiiy tildagi buyruqlarni tekshiruvchi, chegara o'rnatilgan va 2 bosqichli tasdiqlash (`inline confirmation`) mexanizmiga ega tizim.
- 🛡️ **Rate Limiter:** Spam va DoS xurujlarining oldini oluvchi sirpanuvchi oyna (sliding-window) tizimi.
- 📦 **Konteynerizatsiya:** Xavfsiz, root bo'lmagan foydalanuvchi (`appuser`) va avtomatik healthcheck'ka ega Docker muhiti.

---

## 🏗️ Arxitektura va Tizim Dizayni

```
               [ Telegram API ]
                      │
                      ▼
            [ Sliding Rate Limiter ]
                      │
         ┌────────────┴────────────┐
         ▼                         ▼
   [ Group Handlers ]       [ PM Dispatcher O(1) ]
         │                         │
         └────────────┬────────────┘
                      ▼
            [ Game State Machine ]
    (Lobby ➔ Night ➔ Day ➔ Court ➔ Verdict)
                      │
                      ▼
         [ Atomic Database Engine ]
    (aiosqlite + PRAGMA user_version)
         │                         │
         ▼                         ▼
   [ chat_settings ]    [ VIEW group_settings ]
         │
         ▼
[ SQLite (detektiv.db) ]
```

---

## 🎭 O'yin Qoidalari va Rollar

### Shahar Fuqarolari (Tinch aholi):
- 👨‍💼 **Fuqaro:** Maxsus qobiliyatsiz oddiy aholi. Kunduzi munozaralarda qatnashadi va shubhali shaxslarni ovoz berish orqali fosh qiladi.
- 🕵️ **Detektiv:** Kechasi bir o'yinchining rolini tekshiradi yoki shubhali shaxsni otishga harakat qiladi.
- 👨‍⚕️ **Shifokor:** Kechasi bir o'yinchini tanlab, uni Mafiya yoki boshqa qotillar hujumidan davolaydi.
- 💣 **Kamikadze:** O'zini qurbon qilib, gumonlanuvchini o'zi bilan birga olib ketishi mumkin.

### Qora Kuchlar (Mafiya guruhi):
- 🤵 **Don:** Mafiya yetakchisi. Kechasi qotillik buyrug'ini beradi va Detektiv tekshiruvida "Fuqaro" bo'lib ko'rinishi mumkin.
- 🔫 **Mafiya:** Don ko'rsatmasi bilan qotilliklarni amalga oshiradi.

### Yolg'iz Qotillar va Neytrallar:
- 🔪 **Maniak:** Har kecha bitta odamni o'ldiradi. Uning maqsadi — barchani yo'q qilib, yolg'iz o'zi tirik qolish.
- 🔥 **Pirotexnik:** Kechalari uylarga benzin sepadi va xohlagan payti barchasini birdaniga portlatib yuboradi.
- 🃏 **Joker:** Maqsadi — kunduzgi sudda barchani alday olib, o'zini osishga majbur qilish. Agar uni osishsa, Joker yagona g'olib bo'ladi.

---

## 🚀 Tezkor Boshlash (5 Qadam)

### 1-qadam: Python 3.11+ o'rnatilganligini tekshiring
```bash
python3 --version
```

### 2-qadam: Repozitoriyni klonlash va virtual muhit yaratish
```bash
git clone https://github.com/your-username/mafia-bot.git
cd mafia-bot
python3 -m venv .venv
source .venv/bin/activate
```

### 3-qadam: Bog'liqliklarni o'rnatish
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 4-qadam: Muhit o'zgaruvchilarini sozlash
`.env.example` faylidan nusxa olib `.env` yarating:
```bash
cp .env.example .env
```
`.env` faylini ochib, bot tokeningizni va admin ID raqamingizni kiriting:
```ini
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789
ADMIN_IDS=123456789,987654321
DB_PATH=./data/detektiv.db
LOG_LEVEL=INFO
PORT=8000
```

### 5-qadam: Botni ishga tushirish
```bash
python bot.py
```

---

## ⚙️ Muhit O'zgaruvchilari

| O'zgaruvchi | Majburiy? | Standart qiymat | Tavsif |
|---|---|---|---|
| `BOT_TOKEN` | **Ha** | — | Telegram BotFather tomonidan berilgan API token |
| `ADMIN_IDS` | **Ha** | — | Vergul bilan ajratilgan admin Telegram user ID lari |
| `DB_PATH` | Yo'q | `./data/detektiv.db` | SQLite ma'lumotlar bazasi fayl yo'li |
| `LOG_LEVEL` | Yo'q | `INFO` | Loglash darajasi (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `PORT` | Yo'q | `8000` | 24/7 hosting (Koyeb, Docker) monitoringi uchun HTTP port |

---

## 🎮 Buyruqlar Ma'lumotnomasi

### Guruhdagi Buyruqlar:
- `/start_game` — Yangi o'yin lobbisini ochish (kamida 4 nafar o'yinchi kerak).
- `/stop_game` — O'yinni to'xtatish (faqat guruh admini yoki bot admini).
- `/join` — Ochiq lobbiga qo'shilish.
- `/leave` — Boshlanmagan lobbidan chiqish.
- `/chiqish` — Davom etayotgan o'yindan chiqish (o'yinchi avtomatik o'lik deb e'lon qilinadi).
- `/statistika` — Guruhning umumiy o'yinlar statistikasi.
- `/top` — Guruhdagi eng kuchli o'yinchilar reytingi.
- `/sozlamalar` — Guruhdagi o'yin vaqtlarini sozlash (kunduz, tun, sud davomiyligi).

### Shaxsiy Chatdagi Buyruqlar:
- `/start` — Bot haqida umumiy ma'lumot va asosiy menyu.
- `💰 Balans` — Foydalanuvchining tangalari va oltinlari miqdori.
- `🛒 Do'kon` — Himoya vositalari va qurollarni xarid qilish (Qalqon, To'pponcha va h.k.).
- `🎒 Inventar` — Sotib olingan buyumlarni ko'rish.
- `🏆 Reyting` — Butun bot bo'yicha global TOP o'yinchilar.

### Admin AI Buyruqlari (Faqat ADMIN_IDS uchun):
Botga shaxsiy xabarda yoki guruhda quyidagi formatda yozish mumkin:
- `adm grant 500 coin to 123456789`
- `adm ber 100 gold 123456789`
- `adm qo'sh 5 qalqon 123456789`
> *Eslatma: Har bir amaliyotda chegara (100,000 valyuta, 50 buyum) mavjud bo'lib, xavfsizlik uchun Inline tasdiqlash talab qilinadi.*

---

## 🐳 Docker & Docker Compose

Docker yordamida botni bir buyruq bilan xavfsiz konteynerda ishga tushirishingiz mumkin:

```bash
docker compose up -d --build
```

Konteyner quyidagi xususiyatlarga ega:
- **Xavfsiz foydalanuvchi:** Root bo'lmagan `appuser` (UID: 1000).
- **Ma'lumotlar saqlanishi:** `./data` jildi konteynerdagi `/app/data` bilan bog'langan (ma'lumotlar bazasi va loglar saqlanadi).
- **Healthcheck:** Port 8000 orqali bot holati har 30 soniyada tekshiriladi.

Loglarni kuzatish:
```bash
docker compose logs -f bot
```

---

## 💾 Ma'lumotlar Bazasini Zaxiralash

Ma'lumotlar bazasi SQLite tranzaksiyalarini to'liq qo'llab-quvvatlaydi. Zaxira nusxa olish:

```bash
# Zaxira nusxa yaratish
sqlite3 data/detektiv.db ".backup 'data/detektiv_backup_$(date +%Y%m%d).db'"

# Zaxiradan tiklash
cp data/detektiv_backup_20261104.db data/detektiv.db
```

### Migratsiyalar:
Bot ishga tushganda `init_db()` avtomatik ravishda `PRAGMA user_version`ni tekshiradi va eski sxemalarni yangi `chat_settings` va `VIEW group_settings` sxemasiga xavfsiz o'tkazadi.

---

## 🧪 Testlash

Loyiha 186 dan ortiq to'liq integratsion va birlik (unit) testlar bilan ta'minlangan. Testlarni ishga tushirish:

```bash
pytest
```

Natija:
```text
186 passed in ~2.6s
```

CI quvuri har bir push va pull request'da GitHub Actions orqali Python 3.11, 3.12 va 3.13 versiyalarida testlarni avtomatik tekshiradi.

---

## 🔒 Xavfsizlik va Maxfiylik

> [!WARNING] **Muhim Xavfsizlik Talabi**  
> Agar bot tokeni ommaviy repozitoriyga tasodifan chiqib ketgan bo'lsa:
> 1. Telegram [@BotFather](https://t.me/BotFather) orqali zudlik bilan `/revoke` buyrug'ini bering va yangi token oling.
> 2. Yangi tokenni faqat `.env` fayliga yozing.
> 3. Git tarixini tozalash uchun quyidagi buyruqdan foydalaning:
>    ```bash
>    git filter-repo --invert-paths --path .env --path detektiv.db --path mafia_bot_server.zip
>    git push origin --force --all
>    ```

---

## 📄 Litsenziya
MIT License. Erkin foydalanish va rivojlantirish mumkin.
