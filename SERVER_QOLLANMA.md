# 🕵️‍♂️ Telegram Mafia / Detektiv Bot (Ultimate Edition) — Serverga O'rnatish Qo'llanmasi

Ushbu arxivda barcha rollar (24+), AI noir storyteller, dalillar, vasiyatnoma, reyting, do'kon, Gold Drop va cheksiz admin huquqlariga ega bo'lgan to'liq tayyor bot jamlangan.

---

## 🚀 1. Serv00.com Serverida Ishga Tushirish (5 daqiqada)

### 1-qadam: SSH orqali serverga ulaning
```bash
ssh login@sXX.serv00.com
```

### 2-qadam: Fon jarayonlariga ruxsat bering (Muhim!)
```bash
devil binexec on
```

### 3-qadam: Loyihani ochish
Fayllarni serveringizdagi `~/mafia_bot` papkasiga yuklang yoki arxivni oching:
```bash
unzip mafia_bot_server.zip -d ~/mafia_bot
cd ~/mafia_bot
```

### 4-qadam: Botni birinchi marta ishga tushirish
```bash
chmod +x run_bot.sh serv00_watchdog.sh
./run_bot.sh
```
*(Bu skript avtomatik ravishda `venv` yaratadi, kutubxonalarni o'rnatadi va botni yoqadi).*

---

## ⏱️ 2. 24/7 To'xtovsiz Ishlashini Ta'minlash (Serv00 Cron Watchdog)

Serv00 haftada bir marta serverni profilaktika qilsa ham, bot o'z-o'zidan qayta yonishi uchun:

1. Terminalda `crontab -e` buyrug'ini tering.
2. Quyidagi qatorni qo'shib saqlang (har 5 daqiqada tekshirib turadi):
```bash
*/5 * * * * /home/SIZNING_LOGINGIZ/mafia_bot/serv00_watchdog.sh
```

Yoki botni **`screen`** / **`tmux`** ichida ishga tushirib chiqib ketishingiz mumkin:
```bash
screen -S mafia
./run_bot.sh
```
*(Chiqqanda: `Ctrl + A` va keyin `D` tugmasini bosing. Qaytadan kirish uchun: `screen -r mafia`).*

---

## 📁 Fayllar Tarkibi:
- `bot.py` — Asosiy bot va barcha handlerlar
- `config.py` — Konfiguratsiya, rollar ro'yxati, adminlar
- `core/` — Hikoyalar, ovoz effektlari, ob-havo, vasiyatnoma, dalillar
- `database/` — SQLite asinxron modeli (`detektiv.db`)
- `phases/` — Lobby (bitta Qo'shilish tugmasi bilan), Tun, Tong, Ovoz berish, Hukm
- `roles/` — 24+ rollar logikasi va balans taqsimoti
- `handlers/` — Buyruqlar, Gold drop (`/send`), Coin/Gold o'tkazish, admin huquqlari
- `core/last_words.py` — O'limidan oldingi so'nggi gapi (Dying Words) tizimi
- `core/atmospheric_feed.py` — Har bir rol amal qilganda guruhga keluvchi jonli xabarlar
- `core/afk_penalty.py` — Uxlab qolganlarni jarimaga tortish va "MEN QAYTIB O'YIN PAYTIDA UHLAMAYMAN!" faryodi
- `hayrli_kun.jpg` va `osuda_tun.jpg` — Tong va tun rasmlari
- `run_bot.sh` — Tezkor avto-start skripti
- `serv00_watchdog.sh` — 24/7 avto-tiklovchi cron skripti
