#!/usr/bin/env bash
# Serv00 / Linux 24/7 Avto-Qayta Yoqish (Watchdog Cron) Skripti
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# Bot jarayoni tirikligini tekshirish
if ! pgrep -f "python3 -u bot.py" > /dev/null && ! pgrep -f "python3 bot.py" > /dev/null; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') — Bot to'xtagan, avtomatik qayta yoqilmoqda..." >> "$DIR/watchdog.log"
    if [ -d "venv" ]; then
        source venv/bin/activate
    fi
    nohup python3 -u bot.py >> "$DIR/bot_output.log" 2>&1 &
fi
