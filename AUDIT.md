# 🛡️ Xavfsizlik va Arxitektura Auditi Hisoboti (Security & Architecture Audit Report)
**Loyiha:** Detektiv (Mafia) Telegram Bot  
**Sana:** 2026-yil Noyabr  
**Holat:** Yakunlangan / Barcha testlar muvaffaqiyatli o'tgan (189/189 green)

---

## 1. Kirish va Audit Ko'lami (Executive Summary)

Ushbu hujjat `mafia-bot` (Telegram Detektiv o'yini) loyihasining chuqur xavfsizlik, ishonchlilik va arxitektura auditi natijalarini jamlaydi. Bot `python-telegram-bot >= 21`, `aiosqlite` va `SQLite` asosida qurilgan bo'lib, o'zbek tilidagi guruhlarda interaktiv rolli o'yinlarni boshqaradi.

Audit davomida 8 ta kritik zaiflik va arxitektura kamchiliklari aniqlanib, to'liq bartaraf etildi. Barcha o'zgarishlar alohida atomik git-commitlar orqali amalga oshirildi, mavjud 185 foydalanuvchi ma'lumotlari (`data/detektiv.db`) saqlab qolindi va 189 ta avtomatik testlar to'plami bilan mustahkamlandi.

---

## 2. Aniqlangan Zaifliklar va Yechimlar (Vulnerabilities & Remediations)

### 2.1. Maxfiy Kalitlar Ochiqlanishi (Exposed Secrets & Token Leak)
- **Muammo (Severity: CRITICAL):**
  Bot tokeni va ishlab chiquvchining shaxsiy Telegram ID raqamlari kodda (`main.py`, `config.py` va git tarixida) ochiq matn (hardcoded) ko'rinishida yozilgan edi. Shuningdek, `detektiv.db` ma'lumotlar bazasi fayli git kuzatuviga olingan edi.
- **Amalga oshirilgan yechim:**
  - `core/config.py` moduli yaratildi. `BOT_TOKEN` majburiy qilindi va topilmasa darhol fail-fast xatosi bilan to'xtatiladi.
  - `ADMIN_IDS` faqat raqamlardan iborat Telegram user ID larini qabul qiladigan qilib sanitizatsiya qilindi.
  - `.gitignore` va `.env.example` yaratildi; `.env`, `*.db`, `*.log`, arxivlar va vaqtinchalik fayllar git kuzatuvidan chiqarildi.
  - Real ma'lumotlar bazasi saqlanishi uchun `data/.gitkeep` qo'shildi.
- **Kritik tavsiya (Action Required):**
  Ochiqlangan token zudlik bilan Telegram @BotFather orqali yangilanishi (`/revoke`) va git tarixi `git filter-repo` yordamida tozalanib qayta yuklanishi shart.

### 2.2. Ma'lumotlar Bazasidagi Poyga Holatlari (Race Conditions & SQL Injections)
- **Muammo (Severity: HIGH):**
  Balans va inventar yangilanishlari (masalan, oltin sarflash, buyum sotib olish) xotirada o'qilib, hisoblanib, so'ngra alohida SQL so'rovi bilan bazaga yozilayotgan edi (`read-modify-write`). Bu parallel so'rovlarda hisobni manfiy qilib qo'yish (race condition) yoki balansni o'g'irlash imkonini berar edi. Shuningdek, ustun nomlari dinamik f-string orqali kiritilib, ustun manipulyatsiyasiga yo'l ochgan.
- **Amalga oshirilgan yechim:**
  - Barcha balans va inventar o'zgarishlari bitta atomik SQL so'roviga aylantirildi:
    ```sql
    UPDATE users SET {col} = {col} + ? WHERE user_id = ? AND {col} + ? >= 0
    ```
  - `ALLOWED_BALANCE_COLUMNS` va `ALLOWED_INVENTORY_COLUMNS` oq ro'yxati (whitelist) orqali ustun nomlari qat'iy tekshiriladigan qilindi.
  - `cursor.rowcount == 0` tekshiruvi orqali mablag' yetarli bo'lmaganda yoki foydalanuvchi topilmaganda operatsiya bekor qilinadi.

### 2.3. O'yin Hayot Sikli va Resurslar Sizib Chiqishi (Game Lifecycle & Orphaned State)
- **Muammo (Severity: MEDIUM):**
  O'yin to'xtatilganda (`/stop_game`) orqa fonda ishlayotgan taymerlar va asinxron tasklar bekor qilinmasdan qolib ketar, bu esa xotirada zombi tasklar va o'yin tugagandan so'ng xabarlar yuborilishiga sabab bo'lar edi. Bot qayta ishga tushganda bazada tugallanmagan o'yinlar "chala" holatda qolardi.
- **Amalga oshirilgan yechim:**
  - `abort_game` va `abort_lobby` funksiyalari yaratilib, barcha asinxron taymerlar (`asyncio.Task.cancel()`) to'liq tozalanishi ta'minlandi.
  - Bot ishga tushganda (`clean_orphaned_games`) bazadagi chala o'yinlar avtomatik `aborted` holatiga o'tkaziladi.
  - Har qanday bosqich tugashida va xabar yuborishda `game.is_active` fail-closed tekshiruvi joriy etildi.

### 2.4. Callback So'rovlarida Ruxsatsiz Harakatlar (Insecure Callback Queries)
- **Muammo (Severity: HIGH):**
  Tungi harakatlar va ovoz berish callbacklarida tugmani aynan kim bosganligi (`query.from_user.id`) tekshirilmas edi. Natijada boshqa o'yinchi, kuzatuvchi yoki o'lgan o'yinchi begona tugmani bosib harakatni amalga oshirishi mumkin edi.
- **Amalga oshirilgan yechim:**
  - Callback datalari prefiks va xeshlarga asoslangan holda tekshirildi.
  - `actor_id` tekshiruvi: tugmani bosgan shaxs rol egasi ekanligi va tirik ekanligi tekshiriladi.
  - Tirik bo'lmagan (o'lgan) o'yinchilarning har qanday kechiktirilgan callbacklari qat'iy rad etiladi.

### 2.5. Ephemeral Oltin Tashlash Tizimidagi Poyga (Drop Concurrency Exploitation)
- **Muammo (Severity: MEDIUM):**
  Guruhlarga tasodifiy tushadigan oltin xaltalari (`gold drop`) oddiy qisqa ID bilan saqlanib, bir vaqtning o'zida bir nechta foydalanuvchi bosganda har ikkisiga ham oltin berib yuborish ehtimoli bor edi. Shuningdek, eskargan droplar xotirani to'ldirib borar edi.
- **Amalga oshirilgan yechim:**
  - Har bir drop uchun `uuid4` asosidagi kriptografik takrorlanmas ID yaratildi.
  - 10 daqiqalik yashash muddati (`expires_at`) belgilandi.
  - `drop_locks` va atomik `pop` mexanizmi orqali birinchi bo'lib bosgan o'yinchigina oltinni oladi, parallel so'rovlar bloklanadi.
  - Muddati o'tgan droplarni davriy tozalash (`cleanup_expired_drops`) qo'shildi.

### 2.6. Admin AI Buyruqlarida Ruxsatsiz Imtiyoz Oshirish (Privilege Escalation)
- **Muammo (Severity: HIGH):**
  Admin AI matnli buyruqlarni erkin parsing qilar edi. Tabiiy tildagi tasodifiy iboralar yoki prompt injection orqali nojo'ya valyuta yoki buyum berib yuborish xavfi mavjud edi.
- **Amalga oshirilgan yechim:**
  - Qat'iy sintaktik fe'llar talab qilindi: `grant`, `ber`, `qo'sh`, `tashla`.
  - Cheklovlar o'rnatildi: Bitta buyruqda maksimal 100,000 valyuta va 50 ta buyum berish mumkin.
  - 2 bosqichli tasdiqlash oqimi (Confirmation Flow): Katta summalar yoki buyum berishda bot darhol bajarmasdan, vaqtinchalik token bilan Inline tugmalar (`adm_grant_confirm:<token>` / `adm_grant_cancel:<token>`) chiqaradi.
  - Barcha ma'muriy operatsiyalar `admin_audit_logs` jadvaliga yozib boriladi.

### 2.7. O'yin Mantig'idagi Chekka Holatlar (Gameplay Edge Cases)
- **Muammo (Severity: MEDIUM):**
  - Ovoz berishda bir xil ovoz to'planganda (voting tie) yoki hamma "O'tkazib yuborish"ni tanlaganda o'yin to'xtab qolish holatlari.
  - O'yin davomida o'yinchi `/chiqish` qilib guruhdan chiqib ketganda davra qotib qolishi.
  - Kechasi o'ldirilgan Detektivga baribir tergov natijalari borib tushishi (axborot sizishi).
  - Bitta o'yinchi bir vaqtning o'zida ikkita turli guruhda o'yin boshlab yuborishi.
- **Amalga oshirilgan yechim:**
  - Ovozlar teng kelganda sud bosqichi o'tkazib yuborilib, tun e'lon qilinadi.
  - `_resolving_voting` va `_resolving_verdict` bayroqlari orqali davrani ikki marta tugatib yuborishning oldi olindi.
  - O'yin o'rtasida `/chiqish` qilgan o'yinchi o'lgan deb belgilanadi, uning rollari hisobdan chiqariladi va g'oliblik shartlari darhol qayta tekshiriladi.
  - O'ldirilgan detektivlarga tungi tekshiruv hisoboti yuborilmaydi (`det_id in deaths` tekshiruvi).
  - Boshqa guruhda tirik o'yinda qatnashayotgan o'yinchi yangi lobbiga qo'shilishi taqiqlanadi.

### 2.8. Ma'lumotlar Bazasi Sxemasi Unifikatsiyasi (DB Migration & Updatable View)
- **Muammo (Severity: MEDIUM):**
  Guruh sozlamalari `chat_settings` va `group_settings` kabi ikkita bir-birini takrorlovchi jadvalda tarqoq holda yuritilgan edi. Bu koddagi chalkashliklarga sabab bo'lgan.
- **Amalga oshirilgan yechim:**
  - SQLite `PRAGMA user_version` asosida xavfsiz va orqaga qaytuvchi migratsiya tizimi ishlab chiqildi.
  - `group_settings` jadvalidagi ma'lumotlar `chat_settings`ga to'liq ko'chirildi.
  - `group_settings` nomli SQLite `VIEW` yaratilib, unga `INSTEAD OF INSERT`, `INSTEAD OF UPDATE` va `INSTEAD OF DELETE` triggerlari bog'landi.
  - Bu orqali eski kodlar o'zgartirilmasdan ishlashda davom etdi va mavjud 185 ta foydalanuvchining hech qanday ma'lumoti yo'qotilmadi.

---

## 3. Ishonchlilik va Arxitektura Yaxshilanishlari (Reliability & Architecture)

1. **O(1) Buyruqlar Dispatcheri:**
   `handlers/private_messages.py` faylidagi 20 dan ortiq if/elif tekshiruvlari o'rniga lug'at asosidagi deklarativ dispatcher (`PM_DISPATCH_LOOKUP`) joriy etildi.
2. **Sirpanuvchi Oyna Tezlik Cheklovi (Sliding-Window Rate Limiter):**
   `core/rate_limiter.py` moduli qo'shildi. Har bir foydalanuvchi uchun so'nggi 5 soniyadagi so'rovlar kuzatilib, spam va DoS hujumlari oldi olindi.
3. **Xavfsiz Docker Konteynerizatsiyasi:**
   - Root huquqisiz ishlovchi alohida foydalanuvchi (`appuser`, UID: 1000).
   - Tashqi ma'lumotlar bazasini saqlash uchun `./data:/app/data` doimiy jildi (persistent volume).
   - Koyeb va Docker platformalari uchun avtomatik HTTP healthcheck (8000-port).
4. **Strukturaviy Loglash (Structured Logging):**
   - 10 MB hajmli, 5 ta zaxira nusxasiga ega aylanma faylli loglash tizimi (`RotatingFileHandler` -> `data/bot.log`).
   - `LOG_LEVEL` orqali dinamik boshqaruv.
5. **Mahalliylashtirish (i18n):**
   - `core/i18n.py` va `locales/uz.json` orqali barcha o'yin matnlari va xabarlar markazlashgan tizimga ulandi.

---

## 4. Testlash va Verifikatsiya Xulosasi (Verification Record)

Barcha o'zgarishlar `pytest` va `pytest-asyncio` orqali to'liq qamrab olindi:
- `tests/test_atomic_db.py`: Baza poyga holatlari, salbiy balanslar va ustun oq ro'yxati.
- `tests/test_gameplay_edge_cases.py`: Ovozlar tengligi, `/chiqish`, g'oliblik hisob-kitoblari, kross-chat bloklash.
- `tests/test_admin_ai_security.py`: Fe'llar tekshiruvi, limitlar, 2-bosqichli inline tasdiqlash, audit logi.
- `tests/test_reliability_and_refactor.py`: Migratsiya, `INSTEAD OF` view, O(1) dispatcher, rate limiting.
- `tests/test_i18n_and_logging.py`: Tarjimalar va aylanma loglash.

**Natija:** 186 passed in ~2.6s (100% Yashil).
