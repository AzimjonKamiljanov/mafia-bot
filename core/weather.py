import random
from typing import Dict, Any

WEATHER_EVENTS = [
    {
        "id": "clear",
        "name": "Musaffo osmon",
        "icon": "🌌",
        "desc": "Tungi osmonda yulduzlar charaqlab turibdi. Shaharda odatiy sokinlik hukmron.",
        "effect": "Oddiy tun, hech qanday qo'shimcha o'zgarishlar yo'q.",
        "chance": 45,
    },
    {
        "id": "fog",
        "name": "Qora tuman",
        "icon": "🌫️",
        "desc": "Shaharni quyuq va rutubatli tuman qopladi. Ko'rish masofasi bir necha qadamdan oshmaydi.",
        "effect": "Tuman sababli Detektiv va Sherifning tungi tekshiruvlari chalg'ishi mumkin (25% noaniqlik).",
        "chance": 20,
    },
    {
        "id": "blood_moon",
        "name": "Qonli tun",
        "icon": "🩸",
        "desc": "Osmonni xiralashgan qizil oy yoritmoqda. Qotillar va vahshiy ruhiy kuchlar uyg'ondi.",
        "effect": "Qotillar va Maniakning hujumlari yanada shafqatsizlashadi.",
        "chance": 15,
    },
    {
        "id": "curfew",
        "name": "Komendantlik soati",
        "icon": "🚨",
        "desc": "Politsiya patrullari ko'chalarda reyd o'tkazmoqda. Harakatlanish qat'iy cheklangan.",
        "effect": "Tunda ko'chaga chiqqan faol rollarning Sayyoh yoki Soya tomonidan ko'rib qolinish ehtimoli yuqori.",
        "chance": 10,
    },
    {
        "id": "amnesty",
        "name": "Sud amnistiyasi",
        "icon": "⚖️",
        "desc": "Shahar sud kollegiyasi tomonidan kutilmagan amnistiya farmoni e'lon qilindi.",
        "effect": "Ertasi kungi sudda ovozlar teng kelib qolsa, ayblanuvchi zudlik bilan avf etiladi.",
        "chance": 10,
    },
]

def roll_weather() -> Dict[str, Any]:
    """Roll a random atmospheric weather event based on configured chances."""
    total = sum(e["chance"] for e in WEATHER_EVENTS)
    r = random.randint(1, total)
    cum = 0
    for e in WEATHER_EVENTS:
        cum += e["chance"]
        if r <= cum:
            return dict(e)
    return dict(WEATHER_EVENTS[0])
