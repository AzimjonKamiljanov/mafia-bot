import random
from typing import Dict, Any, List, Optional

SETTINGS = [
    "Yomg'irli va rutubatli tor ko'cha",
    "Shahar chetidagi tashlandiq kema doklari",
    "Hashamatli Grand Hotel 404-xonasi",
    "Qadimiy shahar kutubxonasining arxivi",
    "Qora daryo ustiga qurilgan qadimiy ko'prik",
    "Xira neon chiroqlari miltillovchi jazz-bar orqa hovlisi",
    "Shahar markazidagi soat minorasi osti",
    "Tumanga burkangan xiyobondagi xiyobon o'rindiqlari",
    "Tashlandiq teatrning yarim qorong'i sahnasi",
    "Shahar bankining yer osti omborxona yo'lagi",
]

# ============================================================
# 60+ NOIR DETEKTIV HIKOYALARI TO'PLAMI (UZBEK)
# ============================================================

TEMPLATES: Dict[str, List[str]] = {
    # 1. 🔴 MAFIA BOSHLIQ BUYRUG'I (8 shablon)
    "mafia_boss": [
        "Tun sukunatini uzoqdan yangragan bitta o'q ovozi buzdi. {setting}da {victim} sovuq tosh ustida jonsiz yotardi. Mafiya sindikati o'z hukmini ijro etgan. {clue}.",
        "Qora plash kiygan soyalar {setting}ga kirib keldi. {victim} qochishga uringan, ammo Boshliqning nishonidan hech kim qutula olmaydi. {clue}.",
        "Tungi soat 02:00. Shahar uyquda bo'lgan paytda {victim} o'z uyining ostonasida kutib olindi. Boshliq buyrug'i qat'iy edi: shahar uning xiyonatini kechirmadi. {clue}.",
        "Sokin shahar osmonini qora bulutlar qopladi. {victim} {setting}da o'ldirildi. Tergovchilar voqea joyini o'rganar ekan, mafiyaning sovuqqonlik bilan ishlaganiga guvoh bo'lishdi. {clue}.",
        "Qimmatbaho sigaret tutuni va sovuq nafas... Boshliq {victim} ustidan chiqarilgan hukmni tasdiqladi. Tongda shahar ahli uning jonsiz vujudini topdi. {clue}.",
        "Shaharning eng nufuzli ko'chalarida qon to'kildi. {victim} o'z kabinetida o'ldirib ketildi. Boshliqning qo'li qanchalik uzun ekani yana bir bor isbotlandi. {clue}.",
        "Shovqinsiz qadamlar va sovuq metall tegishi... {victim} nima sodir bo'lganini anglab ulgurmadi. Boshliqning g'azabi yana bir qurbonni olib ketdi. {clue}.",
        "Yomg'ir izlarni yuvib ketishga urindi, ammo {victim}ning jasadi yonidagi izlar yashirib bo'lmas haqiqatni aytardi. Mafiya oliy rahbariyati bu kecha o'z so'zini aytdi. {clue}."
    ],

    # 2. 🔪 QOTIL HUJUMI (8 shablon)
    "killer": [
        "Qorong'i burchakdan yaltiragan po'lat tig' sukunatni tilka-pora qildi. {victim} {setting}da qotilning changaliga tushdi. {clue}.",
        "Qotil soyadek yashirinib keldi. {victim} faqat sovuq tig'ning ko'kragiga sanchilganini his qildi, xolos. Baqirishga ham ulgurmadi. {clue}.",
        "Qon sachragan devor va to'kilgan qadamlar... {victim} shafqatsiz qotil bilan yuzma-yuz keldi. Qisqa kurashdan so'ng hamma narsa jimib qoldi. {clue}.",
        "Tungi sharpadek ko'rinmas qotil {victim}ning ortidan kuzatib bordi va {setting}da unga so'nggi zarbani berdi. {clue}.",
        "Qotil o'z ishini o'ta professional bajardi. {victim}ning yuragiga berilgan bitta aniq zarba uning hayotiga chek qo'ydi. {clue}.",
        "Tong yorishmasdan oldin {victim}ning uyi oldida dahshatli fojia yuz berdi. Qotil orqada hech qanday shafqat qoldirmadi. {clue}.",
        "Sovuq shamol esib turgan tunda {victim}ning faryodi uzoqqa yetmadi. Qotil o'z qurbonini sovuqqonlik bilan yerga qulatdi. {clue}.",
        "{victim} so'nggi daqiqalarda qotilning ko'zlariga qaradi, ammo u yerda faqat qorong'ulik bor edi. Shahar yana bir fuqarosidan ayrildi. {clue}."
    ],

    # 3. 🩸 MANIAK QIRG'INI (7 shablon)
    "serial_killer": [
        "Shahar dahshatga tushdi! Maniak {setting}da {victim}ni vahshiylarcha yo'q qildi. Qotillik joyi haqiqiy qonli sahna asariga aylangandi. {clue}.",
        "Bu oddiy qotillik emas, bu aqldan ozgan vahshiyning qonli dastxati edi. {victim} maniakning qurboniga aylandi. {clue}.",
        "Maniakning qo'lidan hech qanday himoya qutqarib qololmasdi. {victim} ko'chalarda uzoq vaqt qiynoqqa solingan holda topildi. {clue}.",
        "Qora tunda qotillik ro'yxatiga yangi nom qo'shildi: {victim}. Maniak o'z nishonini qiymalab ketdi. {clue}.",
        "{setting} devorlarida maniakning telbalarcha yozgan qonli naqshlari qoldi. {victim} bu aqldan ozishning qurboni bo'ldi. {clue}.",
        "Shafqatsiz yirtqichdek pistirmada yotgan Maniak {victim}ni bir zumda halok qildi. Jinoyat joyidagi manzara hatto tajribali detektivlarni ham titratdi. {clue}.",
        "Shahar qon hidiga to'ldi. Maniak {victim}ni topdi va uning so'nggi iltijolariga quloq solmadi. {clue}."
    ],

    # 4. 🔥 PIROTEXNIK ALANGASI (6 shablon)
    "arsonist": [
        "Tunda kerosin hidi butun mavzeni tutib ketdi. Bir zumda alangaga aylangan portlash {victim}ning boshpanasini kulga aylantirdi. {clue}.",
        "Pirotexnik o'z gugurtini chaqdi! Alanga bir lahzada ko'kka o'rladi va {victim} olov domida qolib ketdi. {clue}.",
        "{setting}dan qora quyuq tutun ko'tarildi. Pirotexnik tomonidan quyilgan yoqilg'i {victim}ga najot qoldirmadi. {clue}.",
        "Olovli do'zax! {victim} kerosin olovida yonib ketdi. Shahar o't o'chiruvchilari yetib kelganda faqat kular qolgan edi. {clue}.",
        "Pirotexnikning xushchaqchaq kulgisi va ortda qolgan qora alangalar... {victim} o'z uyida yonib halok bo'ldi. {clue}.",
        "Qora tunda yongan ulkan gulxan butun shaharga ko'rindi. Bu olov qurboni bechora {victim} bo'ldi. {clue}."
    ],

    # 5. 🔫 DETEKTIV VA SHERIF OTISHMASI (6 shablon)
    "detective_shot": [
        "Qonun himoyachisi ikkilanib o'tirmadi. Detektiv {setting}da qora niyatli {victim}ga qarata to'pponchadan o't ochdi. {clue}.",
        "Tungi ko'chalarda qonuniy otishma yuz berdi. Detektiv {victim}ning qilmishlariga chek qo'yib, uni zararsizlantirdi. {clue}.",
        "Detektiv o'z intuitsiyasiga ishondi va shubhali shaxs bo'lgan {victim}ni yerga qulatdi. Qonun o'z so'zini aytdi. {clue}.",
        "Sherif ko'chada shubhali harakat qilgan {victim}ni to'xtatmoqchi bo'ldi, biroq qurolli to'qnashuvda {victim} halok bo'ldi. {clue}.",
        "Shaharning adolat posboni bu tunda qat'iyat ko'rsatdi. {victim} politsiya o'qidan jonsiz yiqildi. {clue}.",
        "Adolat qo'li bu kecha qurollandi: Detektiv {setting}da {victim}ni nishonga oldi va shahar bir xavfdan qutuldi. {clue}."
    ],

    # 6. 🛡️ TANSOQCHI MUDOFAASI VA QAHRAMONLIGI (6 shablon)
    "bodyguard_duel": [
        "Tansoqchi o'z qasamyodiga sodiq qoldi! {victim}ga hujum bo'lgan paytda Tansoqchi ko'kragini qalqon qildi va tajovuzkor bilan birga halok bo'ldi.",
        "Qonli to'qnashuv! Tansoqchi nishonni qutqarib qoldi, biroq o'zi va hujumchi o'rtasidagi shiddatli jangda ikkisi ham yer tishladi.",
        "Tansoqchining jasorati sababli xo'jayini tirik qoldi, ammo mard posbon va unga qarshi borgan hujumchi bu tundan tirik chiqmadi.",
        "Shovqinli to'qnashuv va pichoqlar jaranggi! Tansoqchi hujumchini o'zi bilan birga go'rga olib ketdi.",
        "Tansoqchi oxirgi nafasigacha kurashdi. U o'z jonini fido qilib, himoya ostidagi odamning hayotini saqlab qoldi.",
        "Qahramonlik va fojia birlashdi: Tansoqchi hujumchining zarbasini qaytardi va javob zarbasi bilan uni ham mahv etdi."
    ],

    # 7. 🩺 DOKTOR MO''JIZASI (6 shablon)
    "doctor_saved": [
        "Shahar mo''jizaga guvoh bo'ldi! Doktor o'z vaqtida yetib kelib, {saved}ning tanasidan o'qni chiqarib oldi va uning hayotini asrab qoldi.",
        "O'lim eshik qoqayotgan edi, biroq Doktor {saved}ni narigi dunyo ostonasidan qaytarib oldi. Tongda u tirik uyg'ondi!",
        "Doktorning mohir qo'llari bu kecha bir begunoh qonning to'kilishiga yo'l qo'ymadi. {saved} o'limdan omon qoldi.",
        "Tungi reanimatsiya! Qotilning zarbasi bekorga ketdi, chunki shifokor tuni bilan {saved}ning boshida turdi.",
        "Shifokorning tezkorligi tufayli bu kecha motam tutilmadi. {saved} sog'-omon tongni qarshi oldi.",
        "Doktor o'z kasbiga sodiqligini yana bir bor isbotladi: {saved} qotillik nishoni bo'lgan bo'lsa-da, tirik qoldi!"
    ],

    # 8. 🕊️ SOKIN VA TINCH TUN (8 shablon)
    "peaceful_night": [
        "Tong musaffo osmon bilan otmoqda. Bu tunda hech qanday qon to'kilmadi, shahar xotirjam nafas oldi.",
        "Shahar ko'chalarida sukunat hukm surdi. Qotillar soyada qolishni afzal ko'rishdi, barcha tirik!",
        "Qorong'i kecha tinch o'tdi. Tong quyoshi shahar tomlarini yoritganda, hech kim yo'qotilmagani ma'lum bo'ldi.",
        "Politsiya patrullari bu tunda hech qanday jinoiy hodisani qayd etmadi. Shahar bir kunlik xotirjamlikka erishdi.",
        "Ushbu kechada faqat sovuq shamol uvilladi, qotillar o'z rejalarini amalga oshirolmadilar. Barcha omon qoldi.",
        "Tonggi qushlar sayrashi va qahva hidi... Shahar bugun motamsiz uyg'ondi. Hech kim halok bo'lmadi.",
        "Yomg'ir faqat ko'chalarni tozaladi, qon to'kilmadi. Shahar ahli bir-biriga salom berib yangi kunni boshlamoqda.",
        "Qonunsizlik bir kechaga chekindi. Bugungi tong barcha uchun quvonchli xabar bilan boshlandi: yo'qotishlar yo'q!"
    ],

    # 9. ⚡ KO'PCHILIK HALOK BO'LGAN QONLI TUN (6 shablon)
    "multi_kill": [
        "Qonli qirg'in kechasi! Shahar bir vaqtning o'zida bir nechta fuqarosidan ayrildi. Har xil burchaklarda jasadlar topildi.",
        "Shahar tarixidagi eng qora tunlardan biri. Sindikatlar va yovuz kuchlar baravar zarba berdi, ko'plab qurbonlar bor.",
        "Tongda shahar motamga cho'mdi: shahar bo'ylab bir nechta otishma va qotilliklar sodir etilgani ma'lum bo'ldi.",
        "Shaharda haqiqiy urush boshlangandek: bu tunda bir nechta o'yinchi o'z hayoti bilan vidolashdi.",
        "Qonli tun o'z nomini oqladi. Bir nechta fuqaro turli joylarda qotillik qurboniga aylandi.",
        "Tergovchilar qaysi bir jinoyat joyiga borishni bilmay qolishdi: bu kecha bir nechta inson hayotiga nuqta qo'yildi."
    ],

    # 10. ⚖️ KUNDUZGI SUD VA QATL MINBARI (8 shablon)
    "verdict_lynch": [
        "Shahar maydonidagi dor ostiga olomon yig'ildi. Ko'pchilikning qat'iy qarori bilan {accused} dorga osildi. Uning roli: {role}.",
        "Sud minbarida adolat tarozisi tortildi. Fuqarolarning g'azabi {accused}ning ustiga yog'ildi va u qatl etildi. Asl roli: {role}.",
        "Hakamlar hay'atining so'nggi bolg'asi urildi! {accused} o'zining begunohligiga ishontirolmadi va jazo ijro etildi. Roli: {role}.",
        "Qatl maydonida sukunat cho'kdi. {accused} o'z so'nggi so'zini aytib, dorga ko'tarildi. Uning asl kimligi: {role}.",
        "Olomonning g'azabli hayqiriqlari ostida {accused} shahar doriga olib chiqildi va qatl qilindi. Roli: {role}.",
        "Shahar parlamenti o'z hukmini e'lon qildi: {accused} jinoyatchi deb topildi va osildi. Haqiqiy roli: {role}.",
        "G'azablangan omma adolat talab qildi va bu kecha {accused} osilgan holda maydonda qoldirildi. Roli: {role}.",
        "Qatl minbaridagi arqon taranglashdi. {accused} bu dunyodan ketdi. Shahar esa uning {role} bo'lganini bildi."
    ]
}

def generate_morning_story(
    victim_name: Optional[str],
    killer_role: Optional[str],
    clue: Optional[Dict[str, str]] = None,
    weather_info: Optional[Dict[str, Any]] = None,
    doctor_saved_name: Optional[str] = None,
    multi_victims: Optional[List[str]] = None
) -> str:
    """Generate a rich, immersive noir detective story for morning announcements."""
    setting = random.choice(SETTINGS)
    clue_text = clue.get("summary", "") if clue else "🔍 Hech qanday ashyoviy dalil topilmadi."

    # 1. Doktor qutqargan bo'lsa
    if doctor_saved_name:
        tmpl = random.choice(TEMPLATES["doctor_saved"])
        return tmpl.format(saved=doctor_saved_name)

    # 2. Hech kim o'lmagan sokin tun bo'lsa
    if not victim_name and not multi_victims:
        return random.choice(TEMPLATES["peaceful_night"])

    # 3. Bir necha kishi o'lgan bo'lsa
    if multi_victims and len(multi_victims) > 1:
        base = random.choice(TEMPLATES["multi_kill"])
        names = ", ".join(multi_victims)
        return f"{base}\n\n💀 Qurbonlar: *{names}*"

    # 4. Yagona qotillik bo'lsa (killer_role bo'yicha mos noir ssenariy)
    category = "killer"
    if killer_role == "Boshliq":
        category = "mafia_boss"
    elif killer_role == "Maniak":
        category = "serial_killer"
    elif killer_role == "Pirotexnik":
        category = "arsonist"
    elif killer_role in ("Detektiv", "Sherif"):
        category = "detective_shot"

    tmpl = random.choice(TEMPLATES[category])
    return tmpl.format(
        victim=victim_name or "Noma'lum fuqaro",
        setting=setting,
        clue=clue_text
    )

def generate_verdict_story(accused_name: str, role_name: str) -> str:
    """Generate a gallows verdict execution story."""
    tmpl = random.choice(TEMPLATES["verdict_lynch"])
    return tmpl.format(accused=accused_name, role=role_name)
