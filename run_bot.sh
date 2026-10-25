#!/usr/bin/env bash
# Telegram Mafia / Detektiv Bot — Ishga tushirish skripti
set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

# 1. Virtual muhitni tekshirish yoki yaratish
if [ -d ".venv" ]; then
    source .venv/bin/activate
elif [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "📦 Virtual muhit (venv) yaratilmoqda..."
    python3 -m venv venv
    source venv/bin/activate
    echo "📥 Kutubxonalar o'rnatilmoqda..."
    pip install --upgrade pip
    pip install -r requirements.txt
fi

# 2. Botni ishga tushirish
echo "🚀 Mafia Bot ishga tushmoqda..."
exec python3 -u bot.py
