import random
from typing import Dict, Any, Optional

WEAPON_CLUES = {
    "Boshliq": [
        "9mm kalibrli maxsus to'pponcha gilzasi",
        "Qimmatbaho revolver patroni qoldig'i",
        "Sokin ovoz pasaytirgich (glushitel) bilan otilgan o'q izi",
    ],
    "Qotil": [
        "O'tkir ov pichog'i qoldirgan chuqur kesma",
        "Zangori po'lat tig' izi va ko'krak qafasiga berilgan aniq zarba",
        "Qora tutqichli pichoq qoldirgan qonli tamg'a",
    ],
    "Maniak": [
        "Jarrohlik skalpeli qoldirgan qonli naqsh",
        "Shafqatsizlarcha bir necha bor urilgan boltacha izi",
        "Zaharli kimyoviy eritma va bo'g'ish arqoni qoldig'i",
    ],
    "Pirotexnik": [
        "Kerosin va oltingugurtning o'tkir hidi",
        "Yarim kuygan qora gugurt cho'pi va benzin idishi qopqog'i",
        "Kuygan gazlama va portlovchi kukun qoldiqlari",
    ],
    "Detektiv": [
        "Politsiya xizmat to'pponchasining 7.62mm patroni",
        "Detektivlik nishoni zanjirining kichik halqasi",
    ],
    "Sherif": [
        "Sheriflik karabinining og'ir kalibrli o'qi",
        "Charm qin va maxsus patrullik gilzasi",
    ],
    "default": [
        "Noma'lum o'tkir jism qoldirgan jarohat",
        "Qorong'uda sodir etilgan shafqatsiz hujum izlari",
    ]
}

FABRIC_CLUES = {
    "Boshliq": [
        "Qimmatbaho italyan ipak matosining mayda tolasi",
        "Oltinrang tugma qoldig'i",
    ],
    "Qotil": [
        "Qora charm kurtka yirtig'i",
        "Tungi qora niqob ipi",
    ],
    "Maniak": [
        "Qon sachragan rezina qo'lqop parchasi",
        "Kasalxona bintining ifloslangan qoldig'i",
    ],
    "Pirotexnik": [
        "Olovga chidamli ishchi fartug'ining kuygan bo'lagi",
        "Neft dog'i tekkan dag'al jinsi matosi",
    ],
    "default": [
        "Qora jun gazlama tolasi",
        "Yirtilgan qorong'i kiyim parchasi",
    ]
}

FOOTPRINT_CLUES = [
    "44-o'lchamli og'ir etikning loyqa izlari",
    "42-o'lchamli yengil krossovkaning sirpanish izi",
    "Klassik charm tufli qoldirgan chuqur tovon izi",
    "Burchak sari shoshilinch qochib ketgan oyoq izlari",
    "Yomg'ir suvida yuvilib ulgurmagan qadam izlari",
]

TIMES_OF_DEATH = [
    "Tungi soat 01:45 da",
    "Tungi soat 02:30 atrofida",
    "Tungi soat 03:15 da",
    "Tong sahar 04:10 da",
    "Shaharga qalin tuman tushgan paytda",
]

def generate_forensic_clue(killer_role: str, victim_name: str) -> Dict[str, str]:
    """Generate a realistic forensic clue from the crime scene."""
    weapons = WEAPON_CLUES.get(killer_role, WEAPON_CLUES["default"])
    fabrics = FABRIC_CLUES.get(killer_role, FABRIC_CLUES["default"])

    weapon = random.choice(weapons)
    fabric = random.choice(fabrics)
    footprint = random.choice(FOOTPRINT_CLUES)
    tod = random.choice(TIMES_OF_DEATH)

    return {
        "weapon": weapon,
        "fabric": fabric,
        "footprint": footprint,
        "time": tod,
        "summary": f"🔍 Dalil: {weapon} | {fabric} | {footprint} ({tod})"
    }
