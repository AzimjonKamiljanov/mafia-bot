from dataclasses import dataclass
from typing import Optional, List, Dict
from config import ROLES, ROLE_ORDER, REPEATABLE_ROLES, NIGHT_ACTIVE_ROLES

@dataclass
class RoleInfo:
    name: str
    team: str  # 'blue', 'red', 'solo'
    icon: str
    night_active: bool
    priority: int  # Tartib: 1: Block/Siren, 2: Protect/Doc/Tansoqchi, 3: Frame, 4: Kill/Attack, 5: Visit/Witness, 6: Investigate, 7: Steal
    description: str

ROLE_METADATA: Dict[str, RoleInfo] = {
    # 🔵 SHAHAR (BLUE)
    "Fuqaro": RoleInfo(
        name="Tinch axoli",
        team="blue",
        icon="👨🏼",
        night_active=False,
        priority=99,
        description="Oddiy tinch axoli. Maxsus tungi kuchi yo'q, lekin o'tkir mantiq va kunduzgi ovozi bilan shaharni qutqaradi."
    ),
    "Detektiv": RoleInfo(
        name="Detektiv",
        team="blue",
        icon="🕵🏻",
        night_active=True,
        priority=6,
        description="Har tun bir o'yinchining shaxsini tekshiradi yoki shubhali shaxsga qarshi qurol ishlatadi."
    ),
    "Sherif": RoleInfo(
        name="Sherif",
        team="blue",
        icon="👮🏻",
        night_active=True,
        priority=6,
        description="Detektivning sherigi. Nishonning qizil yoki ko'k ekanini tekshiradi. Detektiv o'lsa, uning vakolatlarini oladi."
    ),
    "Doktor": RoleInfo(
        name="Doktor",
        team="blue",
        icon="👨🏼‍⚕",
        night_active=True,
        priority=2,
        description="Har tun 1 o'yinchini o'limdan qutqaradi. O'zini butun o'yin davomida faqat 1 marta davolay oladi."
    ),
    "Tansoqchi": RoleInfo(
        name="Tansoqchi",
        team="blue",
        icon="🛡️",
        night_active=True,
        priority=2,
        description="Nishonni o'z joni evaziga himoya qiladi. Agar nishonga hujum bo'lsa, tajovuzkor bilan birga halok bo'ladi."
    ),
    "Koldun": RoleInfo(
        name="Koldun",
        team="blue",
        icon="⚡",
        night_active=True,
        priority=2,
        description="Nishonni o'z joni evaziga himoya qiladi va qatldan asraydi."
    ),
    "Sayyoh": RoleInfo(
        name="Daydi",
        team="blue",
        icon="🧙🏻",
        night_active=True,
        priority=5,
        description="Tunda kimningdir uyiga mehmonga boradi. Agar mezbon o'ldirilsa, qotilning shaxsiga guvoh bo'ladi."
    ),
    "Advokat": RoleInfo(
        name="Advokat",
        team="blue",
        icon="⚖️",
        night_active=True,
        priority=8,
        description="Har tunda o'z himoyasiga mijoz oladi. Agar mijoz kunduzi qatl qilinadigan bo'lsa, uni 1 marta qutqarib qoladi."
    ),
    "Ruhshunos": RoleInfo(
        name="Ruhshunos",
        team="blue",
        icon="🔮",
        night_active=True,
        priority=7,
        description="Tunda narigi dunyo (Ruhlar olami) bilan bog'lanib, o'liklarning gumonlari va vasiyatlarini o'rganadi."
    ),
    "Mer": RoleInfo(
        name="Mer",
        team="blue",
        icon="🎖️",
        night_active=False,
        priority=99,
        description="Shahar hokimi. Kunduzgi sudda o'z shaxsini oshkor qilsa, uning ovozi 3 ta ovoz kuchiga teng bo'ladi."
    ),
    "Boy": RoleInfo(
        name="Boy",
        team="blue",
        icon="💎",
        night_active=True,
        priority=7,
        description="Tunda o'z tangalari evaziga boshqa o'yinchilarning tungi qobiliyatini 1 tunga ijaraga sotib oladi."
    ),
    "Qirol": RoleInfo(
        name="Qirol",
        team="blue",
        icon="👑",
        night_active=False,
        priority=4,
        description="Oliy hukmdor. Unga tunda hujum bo'lsa, o'lmaydi va hujumchini qatl yoki avf etishni o'zi hal qiladi."
    ),
    "Begona": RoleInfo(
        name="Begona",
        team="blue",
        icon="🕴️",
        night_active=True,
        priority=1,
        description="Har tun bir o'yinchining uyiga bostirib kirib, uning tungi harakatini butunlay bloklaydi."
    ),
    "Savdogar": RoleInfo(
        name="Savdogar",
        team="blue",
        icon="🛒",
        night_active=True,
        priority=7,
        description="Tunda o'yinchilarga do'kon buyumlarini arzonlashtirilgan narxda taklif qiladi."
    ),

    # 🔴 MAFIA (RED)
    "Boshliq": RoleInfo(
        name="Don",
        team="red",
        icon="🤵🏻",
        night_active=True,
        priority=4,
        description="Mafiya lideri (Don). Tungi qotillik nishonini belgilaydi. Detektiv tekshiruvlarida oddiy fuqaro bo'lib ko'rinadi."
    ),
    "Qotil": RoleInfo(
        name="Mafia",
        team="red",
        icon="🤵🏻",
        night_active=True,
        priority=4,
        description="Boshliqning ijrochisi. Boshliq buyurgan qurbonni yo'q qiladi. Boshliq o'lsa, boshqaruvni o'z qo'liga oladi."
    ),
    "Soya": RoleInfo(
        name="Soya",
        team="red",
        icon="🥷",
        night_active=True,
        priority=3,
        description="Mafiyaning maxfiy ayg'oqchisi. Tekshiruv natijalarini teskarisiga o'zgartiradi va qadamlarni kuzatadi."
    ),
    "Soxtachi": RoleInfo(
        name="Soxtachi",
        team="red",
        icon="🎭",
        night_active=True,
        priority=3,
        description="Tinch fuqaroning uyiga soxta qora dalillar tashlab, Detektiv ko'ziga uni Mafiya qilib ko'rsatadi."
    ),
    "Maftunkor": RoleInfo(
        name="Maftunkor",
        team="red",
        icon="💃",
        night_active=True,
        priority=1,
        description="Mafiyaning jozibador a'zosi. Tunda tanlangan shaxsning e'tiborini o'g'irlab, harakatini muzlatadi (Roleblock)."
    ),
    "Kamikadze": RoleInfo(
        name="Kamikadze",
        team="red",
        icon="💣",
        night_active=False,
        priority=99,
        description="Mafiyaning fidoiysi. Kunduzi sudda osiladigan bo'lsa, o'zini portlatib, bitta ayblovchini o'zi bilan olib ketadi."
    ),
    "Bori": RoleInfo(
        name="Bo'ri",
        team="red",
        icon="🐺",
        night_active=True,
        priority=4,
        description="Yirtqich bo'ri. Tungi hujumlardan omon qoladi va hujumchini yashirincha o'z domiga tortadi."
    ),
    "Bo'ri": RoleInfo(
        name="Bo'ri",
        team="red",
        icon="🐺",
        night_active=True,
        priority=4,
        description="Yirtqich bo'ri. Tungi hujumlardan omon qoladi va hujumchini yashirincha o'z domiga tortadi."
    ),

    # 🟡 NEYTRALLAR (SOLO)
    "Joker": RoleInfo(
        name="Joker",
        team="solo",
        icon="🃏",
        night_active=True,
        priority=7,
        description="Telba qahramon. Kunduzgi sudda o'zini osishlariga erishsa, yolg'iz o'zi mutlaq g'alabaga erishadi!"
    ),
    "Maniak": RoleInfo(
        name="Maniak",
        team="solo",
        icon="🩸",
        night_active=True,
        priority=4,
        description="Shafqatsiz qotil. Har kecha bir kishini vahshiylarcha yo'q qiladi. Birinchi tungi hujumga qarshi immunitetga ega."
    ),
    "Pirotexnik": RoleInfo(
        name="Pirotexnik",
        team="solo",
        icon="🔥",
        night_active=True,
        priority=4,
        description="O't qo'yuvchi. Har tun uylarga kerosin quyadi va istagan tunda barchasini birdaniga portlatib yoqib yuboradi!"
    ),
    "Qasoskor": RoleInfo(
        name="Qasoskor",
        team="solo",
        icon="⚔️",
        night_active=True,
        priority=4,
        description="O'ldirilsa, o'z qotilini javob zarbasi bilan mahv etadi. Agar sudda osilsa, ayblovchilardan birini pichoqlaydi."
    ),
    "Pul o'g'risi": RoleInfo(
        name="Pul o'g'risi",
        team="solo",
        icon="💰",
        night_active=True,
        priority=7,
        description="Kallakesar o'g'ri. Har kecha boy fuqarolardan 50 Coingacha o'g'irlab cho'ntagiga uradi."
    ),
    "Firibgar": RoleInfo(
        name="Buqalamun",
        team="solo",
        icon="🦎",
        night_active=True,
        priority=3,
        description="O'zini istalgan boshqa rol qilib ko'rsata oladi va tekshiruvchilarning boshini qotiradi."
    ),
}

# Cross-reference aliases
_aliases = {
    "Tinch axoli": "Fuqaro",
    "Komissar katani": "Detektiv",
    "Komissar": "Detektiv",
    "Don": "Boshliq",
    "Mafia": "Qotil",
    "Buqalamun": "Firibgar",
    "Daydi": "Sayyoh",
}
for _alias, _orig in list(_aliases.items()):
    if _orig in ROLE_METADATA:
        ROLE_METADATA[_alias] = ROLE_METADATA[_orig]

def get_role_info(role_name: str) -> RoleInfo:
    return ROLE_METADATA.get(role_name, RoleInfo(
        name=role_name,
        team=ROLES.get(role_name, "blue"),
        icon="🎭",
        night_active=role_name in NIGHT_ACTIVE_ROLES,
        priority=50,
        description="Maxsus qobiliyat egasi."
    ))

def get_role_icon(role_name: str) -> str:
    info = ROLE_METADATA.get(role_name)
    return info.icon if info else "🎭"

def get_role_team(role_name: str) -> str:
    return ROLES.get(role_name, "blue")

def format_role_display(role_name: str) -> str:
    info = ROLE_METADATA.get(role_name)
    if info:
        return f"{info.icon} {info.name}"
    return f"🎭 {role_name}"

def is_valid_role_action(role: str, action: str, game: Optional[Dict[str, Any]] = None, actor: Optional[int] = None) -> bool:
    """Validate whether the specified role is permitted to perform the night action."""
    if action in ("sleep", "will_help"):
        return True

    if role == "Boy" and game and actor:
        stolen = game.get("boy_stolen_roles", {}).get(actor)
        if stolen and stolen.get("accepted") and stolen.get("night") == game.get("night", 1):
            role = stolen.get("role", role)

    if role == "Detektiv":
        return action in ("detective", "detective_shoot")

    if role == "Sherif":
        det_alive = False
        if game:
            det_alive = any(
                game.get("alive", {}).get(u, False) and game.get("roles", {}).get(u) == "Detektiv"
                for u in game.get("players", [])
            )
        is_promoted = bool(game and actor and actor in game.get("sheriff_promoted", set()))
        if is_promoted or not det_alive:
            return action in ("detective", "detective_shoot", "sheriff_check")
        return action in ("sheriff_check",)

    if role in ("Bo'ri", "Bori"):
        return action in ("kill", "killer_assist")

    if role == "Doktor":
        return action == "protect"

    if role == "Tansoqchi":
        return action == "guard"

    if role == "Advokat":
        return action == "lawyer"

    if role == "Sayyoh":
        return action == "tourist"

    if role == "Ruhshunos":
        return action == "medium"

    if role == "Boshliq":
        return action == "kill"

    if role == "Qotil":
        boss_alive = False
        if game:
            boss_alive = any(
                game.get("alive", {}).get(u, False) and game.get("roles", {}).get(u) == "Boshliq"
                for u in game.get("players", [])
            )
        if not boss_alive:
            return action in ("kill", "killer_assist")
        return action in ("killer_assist",)

    if role == "Soya":
        return action == "shadow"

    if role == "Soxtachi":
        return action == "frame"

    if role in ("Maftunkor", "Begona"):
        return action == "block"

    if role == "Maniak":
        return action == "maniac_kill"

    if role == "Pirotexnik":
        return action in ("douse", "ignite")

    if role == "Qasoskor":
        return action == "revenge"

    if role == "Pul o'g'risi":
        return action == "coin_thief"

    if role == "Boy":
        return action == "boy"

    if role == "Savdogar":
        return action == "merchant"

    if role == "Firibgar":
        return action == "firibgar"

    if role == "Joker":
        return action == "joker_laugh"

    return False

from roles.dossier import RoleDossier, ROLE_DOSSIERS, get_role_dossier, format_role_dossier
