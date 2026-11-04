# Detektiv Mafia Bot — To'liq Buyruqlar Matritsasi (COMMANDS.md)

Ushbu hujjat Detektiv Mafia Telegram botidagi barcha **34 ta buyruq**, ularning slash (`/`) va slash-free (slashsiz) muqobillari, chat qamrovlari (chat scopes), ruxsat talablari (permissions), qabul qiluvchi argumentlar va kutilayotgan javob xabarlarini to'liq tavsiflaydi.

---

## 1. Tizim Arxitekturasi va Buyruqlar Qamrovi

Bot buyruqlari Telegram Bot API tomonidan qo'llab-quvvatlanuvchi 5 ta darajadagi `BotCommandScope` doirasida ro'yxatga olinadi va qayta ishlanadi:

1. **`BotCommandScopeDefault()`**: Standart umumiy menyu (Guruh a'zolari uchun xavfsiz o'yin buyruqlari).
2. **`BotCommandScopeAllGroupChats()`**: Guruh va superguruhlardagi barcha o'yinchilar menyusi (`game`, `startgame`, `call`, `salom`, `chiqish`, `para`, `bro`, `send`).
3. **`BotCommandScopeAllChatAdministrators()`**: Guruh ma'murlari uchun guruh menyusi (`game`, `startgame`, `stop`, `settings`, `call`, `salom`, `chiqish`, `para`, `bro`, `send`).
4. **`BotCommandScopeAllPrivateChats()`**: Bot bilan shaxsiy chatdagi shaxsiy buyruqlar menyusi (`start`, `profile`, `balance`, `will`, `shop`, `rating`, `guide`, `clan`, `salom`, `mypara`, `mybro`, `use`, `newclan`, `boost`, `stats`, `goal`, `teamwork`).
5. **`BotCommandScopeChat(chat_id=ADMIN_ID)`**: Bot superadminlari uchun maxsus boshqaruv menyusi (`admin`, `settings`, `stats`, `plan`, `start`, `profile`, `balance`, `shop`, `guide`, `rating`, `boost`).

### Ikki Bosqichli Buyruq Dispetcheri (Two-Tier PM Dispatcher)
Shaxsiy chatda xabarlar quyidagi tartibda tahlil qilinadi:
1. **So'nggi Vasiyat (Dying/Last Words)**: O'yinchi sud yoki qatl paytida `waiting_last_words` holatida bo'lsa, xabar guruhga so'nggi so'z sifatida yuboriladi va buyruq dispetcheri to'xtatiladi.
2. **Slash Buyruqlar (`/cmd`)**: Agar xabar `/` bilan boshlansa, birinchi so'z slashsizlantirilib `SLASH_COMMANDS` orqali tezkor $O(1)$ chaqiriladi.
3. **Slashsiz Aniq Buyruqlar (Exact Slash-Free)**: Agar xabar `/` bilan boshlanmasa, butun matn kichik harflarda `EXACT_SLASH_FREE_COMMANDS` jadvali bilan solishtiriladi (masalan, `balans`, `profil`, `do'kon`).
4. **Argumentli Slashsiz Buyruqlar**: Faqat argument kutuvchi muayyan buyruqlar uchun boshlang'ich so'z tekshiriladi (`vasiyat <matn>`, `coin <target> <soni>`, `gold <target> <soni>`, `newclan <nom> <tag>`).
5. **Admin AI Xabarlari**: Superadmin uchun tabiiy tildagi buyruqlar (`process_admin_ai_message`).
6. **Bosh Menyu**: Noma'lum matnlar uchun yo'naltiruvchi bosh menyu ko'rsatiladi.

---

## 2. To'liq Buyruqlar Matritsasi Jadvali (34 ta Buyruq)

| # | Asosiy Buyruq | Slash Muqobillari | Slashsiz Muqobillari | Handler Fayli & Funksiyasi | Chat Qamrovi | Ruxsat / Shart | Argumentlar | Qisqacha Tavsif |
|---|---|---|---|---|---|---|---|---|
| 1 | `/start` | `start`, `menu`, `menyu` | `start`, `menu`, `menyu`, `bosh menyu` | `handlers/commands_user.py:start_cmd` | Shaxsiy (Guruhda /game ga yo'naltiradi) | Hamma | `[join_<id> \| act_<id> \| cmd]` | Botni ishga tushirish, bosh menyu va deep linklar |
| 2 | `/salom` | `salom`, `assalom`, `assalomualaykum`, `salomlar`, `hello`, `hi` | `salom`, `assalom`, `assalomu alaykum`, `assalomualaykum`, `salomlar`, `hello`, `hi` | `handlers/commands_user.py:salom_cmd` | Barcha chatlar | Hamma | Yo'q | Salomlashish va profil havolasi |
| 3 | `/game` | `game`, `oyun`, `oyin` | `oyin`, `o'yin`, `game`, `play`, `boshlash`, `oyun` | `phases/lobby.py:create_lobby` | Guruh, Superguruh | Guruh a'zosi | Yo'q | Guruhda yangi Mafia lobbisini ochish |
| 4 | `/startgame` | `startgame`, `boshlash`, `start_game`, `play`, `go` | `startgame`, `start_game`, `go` | `handlers/commands_lobby.py:startgame_cmd` | Guruh, Superguruh | Lobbi a'zosi yoki Superadmin; `players >= MIN` | Yo'q | Lobbini yopib, o'yinni boshlash |
| 5 | `/stop` | `stop`, `toxtat` | `stop`, `toxtat` | `handlers/commands_lobby.py:stop_cmd` | Guruh, Superguruh | Guruh Admini yoki Superadmin | Yo'q | O'yin yoki lobbini majburiy to'xtatish |
| 6 | `/chiqish` | `chiqish`, `leave`, `tark` | `chiqish`, `leave`, `tark` | `handlers/commands_lobby.py:chiqish_cmd` | Guruh, Superguruh | Lobbida yoki faol o'yinda tirik bo'lgan o'yinchi | Yo'q | Lobbini yoki o'yinni tark etish |
| 7 | `/call` | `call`, `chaqir`, `tagall`, `chorlov` | `call`, `chaqir`, `tagall`, `chorlov` | `handlers/commands_lobby.py:call_players_cmd` | Guruh, Superguruh | Guruh a'zosi | Yo'q | Guruh a'zolarini o'yinga chorlash |
| 8 | `/settings` | `settings`, `sozlama`, `sozlamalar` | `settings`, `sozlama`, `sozlamalar` | `handlers/settings.py:settings_cmd` | Guruh (Admin), Shaxsiy (Superadmin) | Guruh Admini yoki Superadmin | `[chat_id]` (faqat PMda) | O'yin vaqtlari va rollarini sozlash |
| 9 | `/admin` | `admin`, `panel`, `boshqaruv` | `admin`, `panel`, `boshqaruv` | `handlers/admin_panel.py:admin_cmd` | Faqat Shaxsiy | Bot Super Admini (`is_admin`) | Yo'q | Master Admin boshqaruv paneli |
| 10 | `/stats` | `stats`, `statistika`, `holat` | `stats`, `statistika`, `holat` | `handlers/admin_panel.py:stats_cmd` | Shaxsiy (Guruhda adminga yo'l ko'rsatadi) | Hamma (Adminga to'liq diagnostika) | Yo'q | Bot statistikasi va metrikalari |
| 11 | `/plan` | `plan`, `reja`, `mexanika` | `reja`, `plan`, `mexanika` | `handlers/commands_meta.py:plan_cmd` | Shaxsiy | Hamma (PMda) | Yo'q | O'yin rejasi, fazalar va qoidalar bayoni |
| 12 | `/boost` | `boost`, `premium`, `vip` | `boost`, `premium`, `vip` | `handlers/commands_meta.py:boost_cmd` | Barcha chatlar | Hamma | Yo'q | Telegram Premium va guruhni boost qilish qo'llanmasi |
| 13 | `/goal` | `goal`, `maqsad` | `goal`, `maqsad` | `handlers/commands_meta.py:goal_cmd` | Barcha chatlar | Hamma | Yo'q | O'yindagi shaxsiy yoki jamoaviy maqsadlarni ko'rish |
| 14 | `/teamwork` | `teamwork`, `teamwork_preview`, `hamkorlik` | `teamwork`, `teamwork-preview`, `teamwork_preview`, `hamkorlik` | `handlers/commands_meta.py:teamwork_cmd` | Barcha chatlar | Hamma | Yo'q | Jamoaviy sinergiya va ijtimoiy bog'lanishlar yo'riqnomasi |
| 15 | `/will` | `will`, `vasiyat`, `vasiyatnoma` | `vasiyat`, `vasiyatnoma`, `will` | `handlers/commands_user.py:will_cmd` | Faqat Shaxsiy | Hamma | `[vasiyat matni]` | So'nggi vasiyatnomani yozish yoki ko'rish |
| 16 | `/reveal` | `reveal`, `mer` | `reveal`, `mer` | `handlers/commands_user.py:reveal_cmd` | Guruh yoki Shaxsiy | Faol o'yinda tirik Mer (Hokim) roli | Yo'q | Mer o'zini oshkor qilishi (ovoz vaznini 3x qiladi) |
| 17 | `/profile` | `profile`, `profil`, `me`, `shaxsiy` | `profil`, `profile`, `profilim`, `mening profilim`, `shaxsiy`, `me` | `handlers/commands_user.py:profile_cmd` | Faqat Shaxsiy | Hamma | Yo'q | Shaxsiy profil kartasi, yutuqlar va nishonlar |
| 18 | `/balance` | `balance`, `balans`, `hisob`, `pul`, `wallet` | `balans`, `balance`, `hisob`, `pul`, `pulim`, `tangalar`, `wallet` | `handlers/commands_user.py:balance_cmd` | Faqat Shaxsiy | Hamma | Yo'q | Coin va Gold balansi |
| 19 | `/rating` | `rating`, `reyting`, `top`, `top10`, `leaderboard` | `reyting`, `rating`, `top`, `top10`, `top 10`, `top 15`, `leaderboard` | `handlers/commands_user.py:rating_cmd` | Faqat Shaxsiy | Hamma | Yo'q | Top 15 detektivlar reyting jadvali |
| 20 | `/guide` | `guide`, `qollanma`, `yordam`, `help`, `rules`, `rollar`, `qoidalar` | `rollar`, `guide`, `qo'llanma`, `qollanma`, `yordam`, `help`, `qoidalar`, `rules` | `handlers/commands_user.py:guide_cmd` | Faqat Shaxsiy | Hamma | `[rol nomi]` | 24+ rollar ensiklopediyasi va taktikasi |
| 21 | `/shop` | `shop`, `dokon`, `magazin`, `bozor` | `dokon`, `do'kon`, `shop`, `magazin`, `bozor` | `handlers/shop.py:shop_cmd` | Faqat Shaxsiy | Hamma | Yo'q | Buyumlar, himoyalar va unvonlar do'koni |
| 22 | `/clan` | `clan`, `klan`, `sindikat`, `oila` | `klan`, `clan`, `sindikat`, `oila` | `handlers/clans.py:clan_cmd` | Faqat Shaxsiy | Hamma | Yo'q | Mafiya oilasi/klani holati va a'zolari |
| 23 | `/newclan` | `newclan`, `yangi_klan`, `yangiklan` | `newclan`, `yangi_klan`, `yangiklan` | `handlers/clans.py:newclan_cmd` | Faqat Shaxsiy | Balansda >= 500 Coin; klan a'zosi bo'lmagan | `<Nomi> <TAG>` | Yangi mafiya sindikati tuzish (500 Coin) |
| 24 | `/para` | `para` | `para` | `handlers/social.py:para_cmd` | Guruh, Superguruh | Faol juftligi bo'lmagan foydalanuvchi | Reply xabar | Ikkinchi insonga juftlik taklifini yuborish |
| 25 | `/dpara` | `dpara` | `dpara` | `handlers/social.py:dpara_cmd` | Barcha chatlar | Faol juftligi mavjud foydalanuvchi | Yo'q | Mavjud juftlik rishtasini bekor qilish |
| 26 | `/mypara` | `mypara`, `juftlik`, `juftim` | `mypara`, `juftlik`, `juftim` | `handlers/social.py:mypara_cmd` | Faqat Shaxsiy | Hamma | Yo'q | O'z juftligi haqida ma'lumotni ko'rish |
| 27 | `/bro` | `bro` | `bro` | `handlers/social.py:bro_cmd` | Guruh, Superguruh | Faol birodari bo'lmagan foydalanuvchi | Reply xabar | Ikkinchi insonga birodarlik taklifini yuborish |
| 28 | `/dbro` | `dbro` | `dbro` | `handlers/social.py:dbro_cmd` | Barcha chatlar | Faol birodari mavjud foydalanuvchi | Yo'q | Mavjud birodarlik rishtasini uzish |
| 29 | `/mybro` | `mybro`, `birodar`, `broim` | `mybro`, `birodar`, `broim` | `handlers/social.py:mybro_cmd` | Faqat Shaxsiy | Hamma | Yo'q | O'z birodari haqida ma'lumotni ko'rish |
| 30 | `/givegul` | `givegul` | `givegul` | `handlers/social.py:givegul_cmd` | Guruh, Superguruh | Inventarda >= 1 Rose (Gul) mavjud bo'lgan | Reply xabar | Boshqa foydalanuvchiga atirgul sovg'a qilish |
| 31 | `/send` | `send`, `drop`, `golddrop` | `send`, `drop`, `golddrop` | `handlers/social.py:send_cmd` | Guruh, Superguruh | Gold balansi yetarli bo'lgan (yoki Admin) | `<miqdor>` (1..500) | Guruhga Gold Drop tashlash |
| 32 | `/coin` | `coin`, `givecoin`, `sendcoin` | `coin`, `givecoin`, `sendcoin` | `handlers/social.py:coin_cmd` | Guruh (Reply) yoki Shaxsiy | Coin balansi yetarli bo'lgan (yoki Admin) | `[user_id \| @user] <miqdor>` | Boshqa foydalanuvchiga Coin o'tkazish |
| 33 | `/gold` | `gold`, `givegold`, `sendgold` | `gold`, `givegold`, `sendgold` | `handlers/social.py:gold_cmd` | Guruh (Reply) yoki Shaxsiy | Gold balansi yetarli bo'lgan (yoki Admin) | `[user_id \| @user] <miqdor>` | Boshqa foydalanuvchiga Gold o'tkazish |
| 34 | `/use` | `use`, `ishlat` | `use`, `ishlat` | `handlers/commands_user.py:use_item_cmd` | Shaxsiy yoki Guruh | Faol o'yinda tirik; buyum egasi | `<item_id>` | Faol o'yin davomida sotib olingan buyumni ishlatish |

---

## 3. Har Bir Buyruq Bo'yicha Batafsil Xatti-Harakatlar va Javoblar

### 1. `/start`
- **Fayl & Funksiya**: `handlers/commands_user.py:start_cmd`
- **Qamrov**: Shaxsiy chat (Guruhda yuborilsa, faol lobbi bo'lsa `/startgame`, bo'lmasa `/game` ga yo'naltiradi).
- **Argumentlar**:
  - `join_<chat_id>`: Guruhdagi ochiq lobbiga shaxsiy chat orqali bir bosishda qo'shilish.
  - `act_<chat_id>`: O'yinchining hozirgi guruhdagi rol harakatlarini ko'rish (Tun, Ovoz berish, Sud).
  - Buyruq nomi (masalan, `profile`, `shop`, `balance`, `clan`, `guide`): tegishli sahifani darhol ochish.
- **Kutilayotgan Javob**:
  - Shaxsiy chatda: Xush kelibsiz xabari va asosiy inline menyu tugmalari (O'yin, Profil, Do'kon, Rollar, Klan, Agar admin bo'lsa Master Admin).
  - Guruhda: `🎮 Guruhda yangi Mafia o'yini ochish uchun <b>/game</b> buyrug'ini yuboring.`

### 2. `/salom`
- **Fayl & Funksiya**: `handlers/commands_user.py:salom_cmd`
- **Qamrov**: Barcha chatlar.
- **Xatti-harakat**: Guruhda a'zoni DBga qayd etadi, foydalanuvchiga `tg://user?id=...` orqali chiroyli HTML formatida salom yo'llaydi va asosiy o'yin buyruqlarini eslatadi.

### 3. `/game`
- **Fayl & Funksiya**: `phases/lobby.py:create_lobby`
- **Qamrov**: Guruh, Superguruh. Shaxsiy chatda kelsa, botni guruhga qo'shish tugmasi chiqadi.
- **Xatti-harakat**: Guruhda yangi lobbi yaratadi, xabarni pin qiladi, 120 soniyalik avtomatik boshlash taymerini ishga tushiradi. Agar guruhda o'yin davom etayotgan bo'lsa, ogohlantirish beradi.

### 4. `/startgame`
- **Fayl & Funksiya**: `handlers/commands_lobby.py:startgame_cmd`
- **Qamrov**: Guruh, Superguruh.
- **Ruxsat**: Faqat lobbiga qo'shilgan o'yinchi yoki bot superadmini. Ishtirokchilar soni kamida `MIN_PLAYERS` (5 ta) bo'lishi shart.
- **Xatti-harakat**: Lobbini yopadi, rollarni taqsimlaydi, har bir o'yinchiga shaxsiy chatda rol kartasini (dossier) yuboradi va 1-Tunni boshlaydi.

### 5. `/stop`
- **Fayl & Funksiya**: `handlers/commands_lobby.py:stop_cmd`
- **Qamrov**: Guruh, Superguruh.
- **Ruxsat**: Guruh ma'muri (`administrator` yoki `creator`) yoki Bot Superadmini (`is_admin`). Guruh a'zolariga ruxsat berilmaydi (Fail-closed).
- **Xatti-harakat**: O'yin yoki lobbining barcha taymerlarini bekor qiladi, pin qilingan xabarni yechadi, o'yin xotirasini tozalaydi va to'xtatilganlik haqida e'lon beradi.

### 6. `/chiqish`
- **Fayl & Funksiya**: `handlers/commands_lobby.py:chiqish_cmd`
- **Qamrov**: Guruh, Superguruh.
- **Xatti-harakat**: Agar lobbi ochiq bo'lsa, o'yinchini ro'yxatdan chiqaradi va doskani yangilaydi. Agar o'yin ketayotgan bo'lsa, o'yinchini o'lgan deb hisoblaydi (`alive[uid] = False`), g'oliblik shartlarini tekshiradi va agar sudlanuvchi bo'lsa, sudni to'xtatib tunni boshlaydi.

### 7. `/call`
- **Fayl & Funksiya**: `handlers/commands_lobby.py:call_players_cmd`
- **Qamrov**: Guruh, Superguruh.
- **Xatti-harakat**: Guruhda avval faol bo'lgan o'yinchilar ro'yxatini oladi va ularni 5 tadan bo'lib o'yinga chaqiruvchi xabar bilan eslatadi.

### 8. `/settings`
- **Fayl & Funksiya**: `handlers/settings.py:settings_cmd`
- **Qamrov**: Guruh (faqat guruh adminlari uchun), Shaxsiy chat (faqat Bot Super Admini uchun).
- **Xatti-harakat**: O'yin sozlamalari (Tun: 30-90s, Kun: 30-120s, Ovoz: 30-90s, Sud: 30-60s) va faol rollarni yoqish/o'chirish tugmalarini taqdim etadi.

### 9. `/admin`
- **Fayl & Funksiya**: `handlers/admin_panel.py:admin_cmd`
- **Qamrov**: Faqat Shaxsiy chat. Guruhda yozilsa, adminni shaxsiy chatga yo'naltiradi, oddiy a'zolarga hech narsa ko'rsatilmaydi.
- **Ruxsat**: Faqat `config.ADMIN_IDS` ro'yxatidagi bot egalari.
- **Xatti-harakat**: Statistikalar, faol o'yinlar ro'yxati, balans berish/ayirish, global broadcast va tabiiy tildagi AI buyruqlari interfeysini ochadi.

### 10. `/stats`
- **Fayl & Funksiya**: `handlers/admin_panel.py:stats_cmd`
- **Qamrov**: Shaxsiy chat.
- **Xatti-harakat**: Oddiy foydalanuvchiga jami o'yinchilar, o'ynalgan o'yinlar va faol o'yinlar sonini ko'rsatadi. Adminga esa xotira sarfi, uptime va tizim parametrlarini taqdim etadi.

### 11. `/plan`
- **Fayl & Funksiya**: `handlers/commands_meta.py:plan_cmd`
- **Qamrov**: Shaxsiy chat.
- **Xatti-harakat**: O'yin mexanikasi, fazalar zanjiri, rollar balansi, 3-tun AFK qoidasi haqida batafsil ma'lumot beradi.

### 12. `/boost`
- **Fayl & Funksiya**: `handlers/commands_meta.py:boost_cmd`
- **Qamrov**: Barcha chatlar.
- **Xatti-harakat**: Telegram Premium orqali guruhga boost berish va VIP nishonlar, 2x tanga yutuqlari hamda klan chegirmalari haqida ma'lumot beradi.

### 13. `/goal`
- **Fayl & Funksiya**: `handlers/commands_meta.py:goal_cmd`
- **Qamrov**: Barcha chatlar.
- **Xatti-harakat**: Agar o'yinchi faol o'yinda tirik bo'lsa, uning rolining joriy maqsadi va taktik maslahatini ko'rsatadi. O'yindan tashqarida esa Shahar, Mafiya va Yakkaxonlarning umumiy maqsadlarini ko'rsatadi.

### 14. `/teamwork`
- **Fayl & Funksiya**: `handlers/commands_meta.py:teamwork_cmd`
- **Qamrov**: Barcha chatlar.
- **Xatti-harakat**: Detektiv & Sherif hamkorligi, Mafiya sindikati sinergiyasi, Shifokor & Tansoqchi himoyalari hamda Juftlik/Birodarlik haqida yo'riqnoma beradi.

### 15. `/will`
- **Fayl & Funksiya**: `handlers/commands_user.py:will_cmd`
- **Qamrov**: Faqat Shaxsiy chat. Guruhda yuborilsa, shaxsiy chatga tugma ko'rinishida yo'naltiradi.
- **Argumentlar**: `[matn]` — Vasiyat matni.
- **Xatti-harakat**: Agar matn berilmasa, amaldagi vasiyatni ko'rsatadi. Agar matn kiritilsa, DBda saqlaydi. O'yinchi tunda yoki kunduzi o'ldirilganda, ushbu matn butun shaharga fosh etiladi.

### 16. `/reveal`
- **Fayl & Funksiya**: `handlers/commands_user.py:reveal_cmd`
- **Qamrov**: Guruh yoki Shaxsiy chat.
- **Ruxsat**: Faqat faol o'yinda tirik va roli **Mer (Hokim)** bo'lgan, hali oshkor bo'lmagan o'yinchi.
- **Xatti-harakat**: Mer o'zini butun shaharga oshkor qiladi. Ovoz berish fazasida uning ovoz og'irligi avtomatik ravishda **3 ta ovoz** kuchiga ega bo'ladi.

### 17. `/profile`
- **Fayl & Funksiya**: `handlers/commands_user.py:profile_cmd`
- **Qamrov**: Faqat Shaxsiy chat.
- **Xatti-harakat**: Foydalanuvchining ismi, unvoni (badge), Coin, Gold, jami o'yinlar, g'alabalar va mag'lubiyatlar statistikasini ko'rsatadi.

### 18. `/balance`
- **Fayl & Funksiya**: `handlers/commands_user.py:balance_cmd`
- **Qamrov**: Faqat Shaxsiy chat.
- **Xatti-harakat**: Tangalar (Coin) va Oltinlar (Gold) miqdorini ko'rsatadi, do'konga va profilga o'tish tugmalarini chiqaradi.

### 19. `/rating`
- **Fayl & Funksiya**: `handlers/commands_user.py:rating_cmd`
- **Qamrov**: Faqat Shaxsiy chat.
- **Xatti-harakat**: Eng ko'p g'alabaga erishgan TOP 15 o'yinchilar ro'yxatini chiqaradi.

### 20. `/guide`
- **Fayl & Funksiya**: `handlers/commands_user.py:guide_cmd`
- **Qamrov**: Faqat Shaxsiy chat.
- **Argumentlar**: `[rol]` — Masalan: `/guide Detektiv` yoki `/guide Joker`.
- **Xatti-harakat**: Argument berilsa, ushbu rolining to'liq kartasi, qobiliyatlari va taktik yo'riqnomasini chiqaradi. Argument berilmasa, barcha 24+ rollar ro'yxatini guruhlangan holda taqdim etadi.

### 21. `/shop`
- **Fayl & Funksiya**: `handlers/shop.py:shop_cmd`
- **Qamrov**: Faqat Shaxsiy chat.
- **Xatti-harakat**: Coin do'kon (Qo'shimcha ovoz, Qalqon, Tungi niqob, Atirgul), Gold VIP do'kon (VIP nishonlar) va Shaxsiy inventar bo'limlarini ochadi.

### 22. `/clan`
- **Fayl & Funksiya**: `handlers/clans.py:clan_cmd`
- **Qamrov**: Faqat Shaxsiy chat.
- **Xatti-harakat**: Foydalanuvchi a'zo bo'lgan mafiya oilasi (Klan) nomi, tegi, yetakchisi, xazinasi va ochkolarini ko'rsatadi. Agar a'zo bo'lmasa, `/newclan` bo'yicha yo'riqnoma beradi.

### 23. `/newclan`
- **Fayl & Funksiya**: `handlers/clans.py:newclan_cmd`
- **Qamrov**: Faqat Shaxsiy chat.
- **Argumentlar**: `<Klan Nomi> <TAG>` (Masalan: `/newclan CosaNostra CN`).
- **Talab**: Foydalanuvchi balansida kamida 500 Coin bo'lishi va boshqa klan a'zosi bo'lmasligi shart.
- **Xatti-harakat**: 500 Coin yechib olinadi, yangi klan bazada yaratiladi va foydalanuvchi klan yetakchisi etib belgilanadi.

### 24. `/para`
- **Fayl & Funksiya**: `handlers/social.py:para_cmd`
- **Qamrov**: Guruh, Superguruh.
- **Talab**: Boshqa insonning xabariga 'Reply' qilib yozish kerak. Foydalanuvchida avvaldan juftlik bo'lmasligi lozim.
- **Xatti-harakat**: Nishon inson nomiga qabul qilish/rad etish tugmalari bilan sevgi/juftlik taklifini chiqaradi.

### 25. `/dpara`
- **Fayl & Funksiya**: `handlers/social.py:dpara_cmd`
- **Qamrov**: Barcha chatlar.
- **Xatti-harakat**: Mavjud juftlik rishtasini bazadan o'chiradi va "💔 Juftlik bekor qilindi" deb e'lon qiladi.

### 26. `/mypara`
- **Fayl & Funksiya**: `handlers/social.py:mypara_cmd`
- **Qamrov**: Faqat Shaxsiy chat.
- **Xatti-harakat**: O'z juftining ismi, profili va tuzilgan vaqtini ko'rsatadi.

### 27. `/bro`
- **Fayl & Funksiya**: `handlers/social.py:bro_cmd`
- **Qamrov**: Guruh, Superguruh.
- **Talab**: Boshqa insonning xabariga 'Reply' qilib yozish kerak.
- **Xatti-harakat**: Nishon inson nomiga birodarlik taklifini yuboradi.

### 28. `/dbro`
- **Fayl & Funksiya**: `handlers/social.py:dbro_cmd`
- **Qamrov**: Barcha chatlar.
- **Xatti-harakat**: Mavjud birodarlik rishtasini bekor qiladi va "🤝 Birodarlik rishtasi uzildi" deb e'lon qiladi.

### 29. `/mybro`
- **Fayl & Funksiya**: `handlers/social.py:mybro_cmd`
- **Qamrov**: Faqat Shaxsiy chat.
- **Xatti-harakat**: O'z birodarining ismi va ma'lumotlarini ko'rsatadi.

### 30. `/givegul`
- **Fayl & Funksiya**: `handlers/social.py:givegul_cmd`
- **Qamrov**: Guruh, Superguruh.
- **Talab**: Boshqa insonning xabariga 'Reply' qilib yozish va inventarda kamida 1 dona Rose (Atirgul) bo'lishi kerak.
- **Xatti-harakat**: Yuboruvchidan 1 atirgul ayirib, qabul qiluvchiga beradi va guruhda chiroyli e'lon qiladi.

### 31. `/send`
- **Fayl & Funksiya**: `handlers/social.py:send_cmd`
- **Qamrov**: Guruh, Superguruh.
- **Argumentlar**: `<miqdor>` (1 dan 500 gacha butun son).
- **Talab**: Yuboruvchining Gold balansi yetarli bo'lishi (yoki Admin) shart.
- **Xatti-harakat**: Guruhga Oltin Sovrin (Gold Drop) tashlaydi. Guruh a'zolari inline tugmani bosib har biri 1 donadan Gold olishlari mumkin.

### 32. `/coin`
- **Fayl & Funksiya**: `handlers/social.py:coin_cmd`
- **Qamrov**: Guruh (Reply orqali: `/coin <miqdor>`) yoki Shaxsiy chat (`/coin <user_id|@username> <miqdor>`).
- **Talab**: Yuboruvchining Coin balansi yetarli bo'lishi kerak.
- **Xatti-harakat**: Tangalarni yuboruvchidan qabul qiluvchiga o'tkazadi va tasdiqlash xabarini chiqaradi.

### 33. `/gold`
- **Fayl & Funksiya**: `handlers/social.py:gold_cmd`
- **Qamrov**: Guruh (Reply orqali: `/gold <miqdor>`) yoki Shaxsiy chat (`/gold <user_id|@username> <miqdor>`).
- **Talab**: Yuboruvchining Gold balansi yetarli bo'lishi kerak.
- **Xatti-harakat**: Oltinlarni yuboruvchidan qabul qiluvchiga o'tkazadi va tasdiqlash xabarini chiqaradi.

### 34. `/use`
- **Fayl & Funksiya**: `handlers/commands_user.py:use_item_cmd`
- **Qamrov**: Shaxsiy chat yoki Guruh.
- **Argumentlar**: `<item_id>` (Masalan: `/use extra_vote` yoki `/use shield`).
- **Talab**: O'yinchi faol o'yinda tirik bo'lishi va inventarida ushbu buyum mavjud bo'lishi kerak. Bitta o'yinda bitta buyumdan faqat bir marta foydalanish mumkin.
- **Xatti-harakat**: Buyumni o'yinda qo'llaydi (masalan, ovoz berishda qo'shimcha ovoz qo'shadi yoki tungi hujumga qalqon qo'yadi).
