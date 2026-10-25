from dataclasses import dataclass
from typing import Dict, Optional
from config import ROLES

@dataclass
class RoleDossier:
    role_name: str
    team_display: str  # e.g. "Shahar aholisi 🔵", "Mafiya sindikati 🔴", "Yakkaxon neytral 🟡"
    icon: str
    goal: str
    actions_night: str
    actions_day: str
    tactical_tip: str

ROLE_DOSSIERS: Dict[str, RoleDossier] = {
    # 🔵 SHAHAR AHOLISI (TOWN)
    "Fuqaro": RoleDossier(
        role_name="Fuqaro",
        team_display="Shahar aholisi 🔵",
        icon="👤",
        goal="Shahardagi barcha mafiya va shafqatsiz qotillarni fosh qilish, tinch aholining mutlaq g'alabasiga erishish.",
        actions_night="Uyquda bo'lasiz. Maxsus tungi amal yo'q, lekin tongdagi hodisalar va dalillarni diqqat bilan kuzatib boring.",
        actions_day="Shahar chatidagi suhbatlarni, kim kimga qarshi ovoz berayotganini va ashyoviy dalillarni tahlil qiling. Gumonli shaxslarni sud minbariga chiqarish uchun ovoz bering!",
        tactical_tip="Befarq bo'lmang! Sukut saqlagan fuqaro — mafiya uchun oson o'lja yoki shubha nishoniga aylanadi. O'tkir mantiqiy savollar berib, shaharga yetakchilik qiling."
    ),
    "Detektiv": RoleDossier(
        role_name="Detektiv",
        team_display="Shahar aholisi 🔵",
        icon="🕵️‍♂️",
        goal="Qora kuchlarni (Mafiya va Qotillarni) tekshiruvlar orqali fosh qilib, ularni sud minbariga olib chiqish yoki to'pponcha bilan yo'q qilish.",
        actions_night="Botda «🔎 Shaxsni tekshirish» tugmasini bosib bir shaxsning aniq rolini bilib oling. Agar aniq qotil ekaniga ishonchingiz komil bo'lsa, «🔫 Shubhali shaxsni otish» tugmasidan foydalaning!",
        actions_day="Olingan tekshiruv ma'lumotlarini shahar bilan ehtiyotkorona ulashing, shahar ovozini fosh etilgan mafiyalarga qarshi yo'naltiring.",
        tactical_tip="1-kuni o'zingizni oshkor qilmang, aks holda tunda mafiyaning 1-raqamli nishoniga aylanasiz! Dalillarni Sherif yoki Doktor bilan pinhona kelishgan holda ishlating."
    ),
    "Sherif": RoleDossier(
        role_name="Sherif",
        team_display="Shahar aholisi 🔵",
        icon="👮‍♂️",
        goal="Detektiv bilan birgalikda shahar xavfsizligini ta'minlash va mafiya a'zolarini hibsga olib, shaharni himoya qilish.",
        actions_night="«👮 Shahar/Mafiya tekshiruvi» orqali o'yinchining Tinch (🔵) yoki Mafiya (🔴) ekanini tekshiring. Detektiv halok bo'lsa, siz avtomatik uning to'pponchasi va barcha vakolatlarini meros qilib olasiz!",
        actions_day="Detektiv bilan birgalikda gumonlanuvchilarni fosh qiling va shaharga to'g'ri ovoz berishda ko'maklashing.",
        tactical_tip="Detektiv sizning sherigingiz. Agar Detektiv xavfda bo'lsa, e'tiborni o'zingizga qaratib, Detektivga erkin tergov o'tkazish imkonini yarating."
    ),
    "Doktor": RoleDossier(
        role_name="Doktor",
        team_display="Shahar aholisi 🔵",
        icon="🩺",
        goal="Shaharning muhim rahbarlari va tinch fuqarolarini tunda qotillardan asrab qolish.",
        actions_night="«🩺 Bir kishini davolash / himoya» tugmasini bosib, tunda kimga hujum qilinishi mumkin deb hisoblasangiz, o'shani davolang. O'zingizni butun o'yin davomida faqat 1 marta davolay olasiz!",
        actions_day="Kunduzgi bahslarda kimlar shubhali ekanini kuzating, o'z rolingizni oshkor qilmasdan tinch fuqarolarga qo'shiling.",
        tactical_tip="Birinchi tunda Detektiv yoki o'yindagi eng faol o'yinchilarni davolash tavsiya etiladi. O'zingizni behuda oshkor qilmang!"
    ),
    "Tansoqchi": RoleDossier(
        role_name="Tansoqchi",
        team_display="Shahar aholisi 🔵",
        icon="🛡️",
        goal="Shaharning yetakchilarini o'z joni evaziga dushmanlardan himoya qilish.",
        actions_night="«🛡️ Jon fido qilib himoyalash» tugmasi orqali muhim o'yinchini tanlang. Agar unga tunda qotil hujum qilsa, siz tajovuzkorni ham o'ldirasiz, lekin o'zingiz ham qahramonlarcha halok bo'lasiz!",
        actions_day="Jasur bo'ling, kim shaharga ko'proq foyda keltirayotgan bo'lsa (Detektiv, Mer), uni tunda himoya qilish uchun reja tuzing.",
        tactical_tip="Agar siz tunda kuchli qotilni (Don yoki Maniakni) o'zingiz bilan birga narigi dunyoga olib ketsangiz — shahar uchun ulkan g'alaba ta'minlaysiz."
    ),
    "Advokat": RoleDossier(
        role_name="Advokat",
        team_display="Shahar aholisi 🔵",
        icon="⚖️",
        goal="Tinch fuqarolarni va qimmatli yetakchilarni kunduzgi sud doridan qutqarib qolish.",
        actions_night="«⚖️ Himoyaga mijoz tanlash» orqali 1 o'yinchini qonuniy order bilan himoyaga oling.",
        actions_day="Agar siz himoyaga olgan mijoz kunduzgi sudda eng ko'p ovoz olib osiladigan bo'lsa, sizning order-hujjatingiz tufayli dor bekor qilinadi va u omon qoladi!",
        tactical_tip="Tunda nohaq gumon ostida qolishi mumkin bo'lgan o'yinchini (yoki Detektivni) mijoz sifatida tanlang."
    ),
    "Sayyoh": RoleDossier(
        role_name="Sayyoh",
        team_display="Shahar aholisi 🔵",
        icon="🚶",
        goal="Tunda o'yinchilarning uyiga mehmonga borib, jinoyatlarga bevosita guvoh bo'lish va qotillarni fosh qilish.",
        actions_night="«🚶 Mehmonga borish» tugmasi orqali bir o'yinchining uyiga boring. Agar o'sha kecha mezbonga qotil hujum qilsa, siz qotilning shaxsini ko'rasiz va tongda bot sizga qotil kimligini bildiradi!",
        actions_day="Guvoh bo'lgan ma'lumotingizni kunduzgi sudda e'lon qilib, haqiqiy qotilning dorda osilishini ta'minlang.",
        tactical_tip="O'ldirilishi eng ehtimoli baland bo'lgan nishonlarning uyiga boring. Ammo mezbon vafot etsa ham, guvohlik berish sizning qo'lingizda!"
    ),
    "Ruhshunos": RoleDossier(
        role_name="Ruhshunos",
        team_display="Shahar aholisi 🔵",
        icon="🔮",
        goal="Marhumlar olami (Graveyard) bilan muloqot qilib, ularning vasiyatlari va sirlarini ochish.",
        actions_night="«🔮 Ruhlar olami bilan bog'lanish» tugmasini bosib, o'lganlarning so'nggi sirlari, taxminlari va vasiyatlarini o'rganing.",
        actions_day="Marhumlar qoldirgan muhim dalillarni tirik aholi bilan baham ko'ring va xiyonatkorlarni toping.",
        tactical_tip="Ruhlar o'z qotilini ko'pincha to'g'ri sezishadi. Ularning ko'rsatmalaridan foydalanib shubhalilarni qistovga oling."
    ),
    "Mer": RoleDossier(
        role_name="Mer",
        team_display="Shahar aholisi 🔵",
        icon="🎖️",
        goal="Shahar qonunlari ustuvorligini saqlash va muhim sud lahzasida hal qiluvchi kuch bo'lish.",
        actions_night="Tungi maxsus harakat yo'q.",
        actions_day="Kunduzgi ovoz berishda oddiy ovoz berishingiz mumkin, ammo eng keskin vaziyatda «🎖️ Merlikni e'lon qilish (/reveal)» tugmasini bossangiz, ovozingiz 3 TA OVOZ kuchiga aylanadi!",
        tactical_tip="Merlikni 1-kuni e'lon qilmang, aks holda tunda qotillar sizni darhol nishonga oladi. Ovozlar teng kelganda yoki mafiyani osish kerak bo'lganda kuchingizni ko'rsating."
    ),
    "Boy": RoleDossier(
        role_name="Boy",
        team_display="Shahar aholisi 🔵",
        icon="💎",
        goal="O'zining behisob boyligi orqali har tunda shahar taqdirini o'zgartirish.",
        actions_night="«💎 Rolni sotib olish/ijara» tugmasi orqali istalgan o'yinchiga 50 Coin to'lab, uning tungi qobiliyatini 1 tunga ijaraga oling (masalan, Detektiv, Doktor va b.)!",
        actions_day="Pul bilan ko'p narsani hal qilish mumkin, lekin sudda o'tkir fikrlaringiz bilan ham shaharga yordam bering.",
        tactical_tip="Do'kondan yoki boshqa o'yinchilardan foydali qobiliyatlarni o'z vaqtida xarid qiling."
    ),
    "Qirol": RoleDossier(
        role_name="Qirol",
        team_display="Shahar aholisi 🔵",
        icon="👑",
        goal="Oliy adolatni saqlab qolish va unga suiqasd qilgan har qanday dushmanga joyida hukm chiqarish.",
        actions_night="Qirolga tunda hujum qilinsa, Qirol birinchi hujumda o'lmaydi! Qirolga xabar keladi va u o'ziga hujum qilganni darhol QATL qilish yoki AFV etishni shaxsan o'zi hal qiladi.",
        actions_day="Shahar xalqini birlashtiring, haqiqiy hukmdor sifatida bahslarda adolatli yo'l tuting.",
        tactical_tip="Tunda sizga suiqasd qilgan tajovuzkorni aslo afv etmang — qatl qiling!"
    ),
    "Begona": RoleDossier(
        role_name="Begona",
        team_display="Shahar aholisi 🔵",
        icon="🕴️",
        goal="Shubhali shaxslarning uyiga bostirib kirib, ularning tungi qabih rejalarini yo'qqa chiqarish.",
        actions_night="«🕴️ Harakatni bloklash» tugmasi orqali o'yinchini tanlang. U tunda hech qanday amal bajara olmaydi.",
        actions_day="O'tgan tunda kimni bloklaganingizni va oqibatda kimlar o'lmaganini tahlil qiling.",
        tactical_tip="Agar siz bloklagan tunda qotillik bo'lmasa, demak siz Don yoki Maniakni topgansiz!"
    ),
    "Savdogar": RoleDossier(
        role_name="Savdogar",
        team_display="Shahar aholisi 🔵",
        icon="🛒",
        goal="Shahar aholisini arzonlashtirilgan do'kon buyumlari va himoya vositalari bilan ta'minlash.",
        actions_night="Tanlangan o'yinchiga bepul do'kon buyumi yoki himoya qalqoni (Protection) taqdim eting.",
        actions_day="Shahar iqtisodiyoti va xavfsizligini qo'llab-quvvatlang.",
        tactical_tip="Eng ishonchli tinch o'yinchilarga qalqon bering, toki qotillar ularni o'ldira olmasin."
    ),

    # 🔴 MAFIYA SINDIKATI (MAFIA)
    "Boshliq": RoleDossier(
        role_name="Boshliq",
        team_display="Mafiya sindikati 🔴",
        icon="👑",
        goal="Shahardagi barcha aholini yo'q qilib, mafiya sonini shahar soniga tenglashtirish va shaharni egallash!",
        actions_night="«👑 Qotillik nishonini tanlash» orqali kim o'ldirilishini belgilang. Detektiv sizni tekshirganda «👤 Fuqaro (Tinch)» bo'lib ko'rinasiz!",
        actions_day="O'zingizni eng ishonchli, namunali tinch fuqaro kabi tuting. Hech kim sizdan shubhalanmasin!",
        tactical_tip="Birinchi navbatda Detektiv va Doktorni topib yo'q qiling. O'z sheriklaringizni himoya qiling, ammo vaziyat taqozo qilsa, shubhadan qochish uchun moslashing."
    ),
    "Qotil": RoleDossier(
        role_name="Qotil",
        team_display="Mafiya sindikati 🔴",
        icon="🔪",
        goal="Boshliqning buyruqlarini aniq bajarish va shaharni bitta-bitta qulatish.",
        actions_night="Boshliq tirik ekan, u ko'rsatgan nishonni yo'q qilasiz. Agar Boshliq halok bo'lsa, mafiya yetakchiligi sizga o'tadi va nishonni o'zingiz tanlaysiz!",
        actions_day="Guruhdagi bahslarda tinch fuqarolar bir-birini ayblashi uchun provokatsiya qiling.",
        tactical_tip="Boshliqning orqasida turing. Agar Boshliq xavf ostida qolsa, aybni begonalarga ag'daring."
    ),
    "Soya": RoleDossier(
        role_name="Soya",
        team_display="Mafiya sindikati 🔴",
        icon="🥷",
        goal="Tergovchilarning boshini qotirish, izlarni yashirish va mafiyani tekshiruvlardan pana qilish.",
        actions_night="«🥷 Chalg'itish / Kuzatuv» orqali o'yinchini tanlang. Uning qadamlarini kuzatasiz va tekshiruv natijalarini teskarisiga o'zgartirasiz.",
        actions_day="Shaharda yolg'on mish-mishlar va noto'g'ri tahlillarni tarqating.",
        tactical_tip="Detektiv tekshirishi mumkin bo'lgan nishonlarni kuzatib, natijani buzib bering."
    ),
    "Soxtachi": RoleDossier(
        role_name="Soxtachi",
        team_display="Mafiya sindikati 🔴",
        icon="🎭",
        goal="Tinch aholini qora dalillar bilan xalq ko'ziga jinoyatchi qilib ko'rsatish.",
        actions_night="«🎭 Soxta dalil tashlash (Frame)» orqali tinch o'yinchini tanlang. Agar Detektiv uni tekshirsa, uni «🔴 Mafiya» deb topadi!",
        actions_day="Detektiv o'sha tinch odamni mafiya deb e'lon qilganida, uni dorda osishga butun kuchingiz bilan ovoz bering!",
        tactical_tip="Eng ishonchli va obro'li tinch fuqaroni frame qiling — shunda shahar o'z qahramonini o'zi dorga tortadi!"
    ),
    "Maftunkor": RoleDossier(
        role_name="Maftunkor",
        team_display="Mafiya sindikati 🔴",
        icon="💃",
        goal="Shaharning faol rahbarlarini o'z jozibasi bilan sehrlab, tunda amallarini muzlatish.",
        actions_night="«🕴️ Harakatni bloklash» tugmasi orqali o'yinchini tanlang. U tunda hech qanday amal bajara olmaydi.",
        actions_day="Chiroyli va ishonarli so'zlar bilan shahar e'tiborini mafiyadan uzoqlashtiring.",
        tactical_tip="Detektiv yoki Doktorni bloklang, shunda mafiya qotilligi to'sqinliksiz amalga oshadi!"
    ),
    "Kamikadze": RoleDossier(
        role_name="Kamikadze",
        team_display="Mafiya sindikati 🔴",
        icon="💣",
        goal="Mafiya foydasiga o'zini qurbon qilish va shahar sudini qonli fojiaga aylantirish.",
        actions_night="Maxsus tungi harakat yo'q.",
        actions_day="Sudda o'zingizni bemalol tuting. Agar ko'pchilik sizni dorda osishga hukm qilsa, sizga qarshi ovoz berganlardan birini o'zingiz bilan birga portlatib ketasiz!",
        tactical_tip="O'zingizga aynan Detektiv yoki Mer ovoz berishiga erishing, shunda o'limingiz evaziga shahar rahbarini yo'q qilasiz!"
    ),
    "Bo'ri": RoleDossier(
        role_name="Bo'ri",
        team_display="Mafiya sindikati 🔴",
        icon="🐺",
        goal="Yirtqich kuchi bilan mafiyani himoya qilish va hujumlarga chidash.",
        actions_night="Mafiya hujumlarida qatnashadi. Birinchi tungi hujumga qarshi immunitetga ega.",
        actions_day="Jasur va qat'iy harakat qiling.",
        tactical_tip="Sizni tunda o'ldirish oson emas, shuning uchun agressiv tarzda mafiya dushmanlarini yo'q qilishga yordam bering."
    ),
    "Bori": RoleDossier(
        role_name="Bori",
        team_display="Mafiya sindikati 🔴",
        icon="🐺",
        goal="Yirtqich kuchi bilan mafiyani himoya qilish va hujumlarga chidash.",
        actions_night="Mafiya hujumlarida qatnashadi. Birinchi tungi hujumga qarshi immunitetga ega.",
        actions_day="Jasur va qat'iy harakat qiling.",
        tactical_tip="Sizni tunda o'ldirish oson emas, shuning uchun agressiv tarzda mafiya dushmanlarini yo'q qilishga yordam bering."
    ),

    # 🟡 YAKKAXON NEYTRALLAR (SOLO)
    "Joker": RoleDossier(
        role_name="Joker",
        team_display="Yakkaxon neytral 🟡",
        icon="🃏",
        goal="BUTUN SHAHARNI ALDAB, KUNDUZGI SUDDA O'ZINI DORGA OSISHLARIGA ERISHISH! Agar dorda osilsangiz — YOLG'IZ O'ZINGIZ MUTLAQ G'ALABA QOZONASIZ!",
        actions_night="Maxsus harakat talab etilmaydi.",
        actions_day="O'zingizni xuddi ayyor mafiya kabi tuting, kichik xatolarga yo'l qo'ying va xalqni sizga ovoz berishga gijgijlang!",
        tactical_tip="Haddan tashqari ochiqcha bo'lmang, aks holda shahar sizni Joker deb sezib qoladi yoki tunda mafiya sizni o'ldirib qo'yadi. Nozik psixologik o'yin olib boring!"
    ),
    "Maniak": RoleDossier(
        role_name="Maniak",
        team_display="Yakkaxon neytral 🟡",
        icon="🩸",
        goal="Shaharni ham, mafiyani ham — BARCHANI yo'q qilib, yagona tirik g'olib bo'lish!",
        actions_night="«🩸 Vahshiy qotillik» tugmasi orqali har tunda 1 kishini o'ldiring. Birinchi tungi hujumga qarshi immunitetingiz bor!",
        actions_day="Mafiya va shahar bir-birini qirishi uchun fitna uyushtiring.",
        tactical_tip="Avvalo mafiya va faol tinch rollarni o'ldiring. O'zingizni tinch fuqaro qilib ko'rsating."
    ),
    "Pirotexnik": RoleDossier(
        role_name="Pirotexnik",
        team_display="Yakkaxon neytral 🟡",
        icon="🔥",
        goal="Shahar uylariga yashirincha kerosin quyib chiqish va bir kechada barchasini o't ichida yoqib, yakka o'zi g'olib bo'lish!",
        actions_night="Har tun «Uylarga kerosin quyish» orqali o'yinchilarni belgilang. Kerakli paytda «🔥 Kerosin quyilganlarni yoqish!» tugmasini bosib barchasini birdaniga yoqing!",
        actions_day="Jimjit va muloyim bo'ling, sizdan hech kim shubhalanmasin.",
        tactical_tip="2-3 kishiga kerosin sepib, hal qiluvchi kechada ularni birdaniga yoqib yuboring!"
    ),
    "Qasoskor": RoleDossier(
        role_name="Qasoskor",
        team_display="Yakkaxon neytral 🟡",
        icon="⚔️",
        goal="O'zining o'limiga qasos zarbasi berish va o'z qotilini narigi dunyoga tortib ketish.",
        actions_night="«⚔️ Qasos nishonini belgilash» orqali dushmaningizni belgilang.",
        actions_day="Agar sizni tunda o'ldirishsa — qotilingiz ham o'ladi! Agar sudda osishsa — ayblovchilardan biri halok bo'ladi!",
        tactical_tip="Hech kimdan qo'rqmang, sizga qo'l ko'targan har qanday kimsa qonli tovon to'laydi."
    ),
    "Pul o'g'risi": RoleDossier(
        role_name="Pul o'g'risi",
        team_display="Yakkaxon neytral 🟡",
        icon="💰",
        goal="Shaharning boy fuqarolarini tunab, cho'ntagini to'ldirish va eng boy shaxsga aylanish.",
        actions_night="«💰 Cho'ntak kesish / O'g'irlik» orqali har tun bir boydan 50 Coin o'g'irlang.",
        actions_day="Shubhaga tushmaslik uchun kamtarona bo'ling.",
        tactical_tip="Qimmatbaho buyumlari yoki tangalari ko'p bo'lgan faol o'yinchilarni nishonga oling."
    ),
    "Firibgar": RoleDossier(
        role_name="Firibgar",
        team_display="Yakkaxon neytral 🟡",
        icon="🎪",
        goal="O'zini istalgan boshqa rol sifatida niqoblab, barcha tekshiruvchilarni chalg'itish va omon qolish.",
        actions_night="«🎪 Niqob tanlash» orqali bugungi rolingizni tanlang (masalan, Detektiv, Doktor yoki Fuqaro). Tergovchilar sizni tekshirganda o'sha soxta rolni ko'radi!",
        actions_day="Tanlagan niqobingizga mos tarzda rol o'ynang.",
        tactical_tip="Haqiqiy Detektiv sizni tekshirishidan oldin to'g'ri niqobni kiyib oling!"
    ),
}

def get_role_dossier(role_name: str) -> RoleDossier:
    if role_name in ROLE_DOSSIERS:
        return ROLE_DOSSIERS[role_name]
    team = ROLES.get(role_name, "blue")
    team_display = "Shahar aholisi 🔵" if team == "blue" else ("Mafiya sindikati 🔴" if team == "red" else "Yakkaxon neytral 🟡")
    return RoleDossier(
        role_name=role_name,
        team_display=team_display,
        icon="🎭",
        goal="O'z jamoangiz bilan birgalikda to'liq g'alabaga erishish.",
        actions_night="Tungi maxsus vazifalaringizni bot orqali bajaring.",
        actions_day="Guruh muhokamasida faol qatnashing va shahar taqdirini hal qiling.",
        tactical_tip="O'z rolingizni sir saqlang va strategik fikrlang."
    )

def format_role_dossier(role_name: str, partner_text: str = "") -> str:
    dossier = get_role_dossier(role_name)
    lines = [
        f"{dossier.icon} Sizning rolingiz: *{dossier.role_name}*",
        f"🏷️ Jamoa: *{dossier.team_display}*",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "🎯 *Bosh Maqsadi:*",
        f"{dossier.goal}",
        "",
        "⚡ *Nima qilishingiz kerak?*",
        f"• *Tunda:* {dossier.actions_night}",
        f"• *Kunduzi:* {dossier.actions_day}",
        "",
        "💡 *Taktik Maslahat:*",
        f"_{dossier.tactical_tip}_",
    ]
    if partner_text:
        lines.append("")
        lines.append(partner_text.strip())
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🤫 *Rolingizni sir saqlang va guruhdagi muhokamada faol bo'ling!*")
    return "\n".join(lines)
