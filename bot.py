import asyncio
import logging
from datetime import datetime, timedelta
import pytz
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, JobQueue

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== SOZLAMALAR =====
BOT_TOKEN = "8546375317:AAHFOa94cHuXgjS_VMR7GR8kIsctEXahd5I"
CHAT_ID = None  # /start bosganda avtomatik o'rnatiladi, yoki qo'lda kiriting
TZ = pytz.timezone("Asia/Tashkent")

# Zoom havolalari
ZOOM_LINKS = {
    "3613211050": "https://us04web.zoom.us/j/3613211050",
    "3837074495": "https://us04web.zoom.us/j/3837074495",
}

# ===== DARS JADVALI =====
# Format: (sana "DD.MM.YYYY", soat, daqiqa, fan, o'qituvchi, zoom_id)
SCHEDULE = [
    # 15.05.2026 - Juma
    ("15.05.2026",  9,  0, "Insurance",                "Primkulova Zilola Abrorovna",           "3613211050"),
    ("15.05.2026", 10,  0, "Economic Analysis",        "Berdikulova Iroda Rayimkulovna",         "3613211050"),
    ("15.05.2026", 11,  0, "Islamic Finance",          "Ishbekova Lobar Yunusxonovna",           "3613211050"),
    ("15.05.2026", 12,  0, "Public Finance",           "Ergasheva Zarifa Baxtiyarovna",          "3613211050"),
    ("15.05.2026", 13,  0, "International Negotiation","Islomov Shuhrat Marufjonovich",          "3837074495"),

    # 16.05.2026 - Shanba
    ("16.05.2026",  9,  0, "Insurance",                "Primkulova Zilola Abrorovna",           "3613211050"),
    ("16.05.2026", 10,  0, "Financial Technologies",   "Abdullayev Xudoymurod Anvar o'g'li",    "3613211050"),
    ("16.05.2026", 11,  0, "Islamic Finance",          "Ishbekova Lobar Yunusxonovna",           "3613211050"),
    ("16.05.2026", 12,  0, "Public Finance",           "Ergasheva Zarifa Baxtiyarovna",          "3613211050"),
    ("16.05.2026", 13,  0, "International Negotiation","Islomov Shuhrat Marufjonovich",          "3837074495"),

    # 22.05.2026 - Juma
    ("22.05.2026",  9,  0, "Insurance",                "Primkulova Zilola Abrorovna",           "3613211050"),
    ("22.05.2026", 10,  0, "Financial Technologies",   "Abdullayev Xudoymurod Anvar o'g'li",    "3613211050"),
    ("22.05.2026", 11,  0, "Economic Analysis",        "Berdikulova Iroda Rayimkulovna",         "3613211050"),
    ("22.05.2026", 12,  0, "Islamic Finance",          "Ishbekova Lobar Yunusxonovna",           "3613211050"),
    ("22.05.2026", 13,  0, "Public Finance",           "Ergasheva Zarifa Baxtiyarovna",          "3613211050"),
    ("22.05.2026", 14,  0, "International Negotiation","Islomov Shuhrat Marufjonovich",          "3837074495"),

    # 23.05.2026 - Shanba
    ("23.05.2026",  9,  0, "Insurance",                "Primkulova Zilola Abrorovna",           "3613211050"),
    ("23.05.2026", 10,  0, "Economic Analysis",        "Berdikulova Iroda Rayimkulovna",         "3613211050"),
    ("23.05.2026", 11,  0, "Islamic Finance",          "Ishbekova Lobar Yunusxonovna",           "3613211050"),
    ("23.05.2026", 12,  0, "Islamic Finance",          "Ishbekova Lobar Yunusxonovna",           "3613211050"),
    ("23.05.2026", 13,  0, "Public Finance",           "Ergasheva Zarifa Baxtiyarovna",          "3613211050"),

    # 29.05.2026 - Juma
    ("29.05.2026",  9,  0, "Insurance",                "Primkulova Zilola Abrorovna",           "3613211050"),
    ("29.05.2026", 10,  0, "Financial Technologies",   "Abdullayev Xudoymurod Anvar o'g'li",    "3613211050"),
    ("29.05.2026", 11,  0, "Islamic Finance",          "Ishbekova Lobar Yunusxonovna",           "3613211050"),
    ("29.05.2026", 12,  0, "Public Finance",           "Ergasheva Zarifa Baxtiyarovna",          "3613211050"),
    ("29.05.2026", 13,  0, "International Negotiation","Islomov Shuhrat Marufjonovich",          "3837074495"),

    # 30.05.2026 - Shanba
    ("30.05.2026",  9,  0, "Insurance",                "Primkulova Zilola Abrorovna",           "3613211050"),
    ("30.05.2026", 10,  0, "Financial Technologies",   "Abdullayev Xudoymurod Anvar o'g'li",    "3613211050"),
    ("30.05.2026", 11,  0, "Economic Analysis",        "Berdikulova Iroda Rayimkulovna",         "3613211050"),
    ("30.05.2026", 12,  0, "Islamic Finance",          "Ishbekova Lobar Yunusxonovna",           "3613211050"),
    ("30.05.2026", 13,  0, "Public Finance",           "Ergasheva Zarifa Baxtiyarovna",          "3613211050"),
    ("30.05.2026", 14,  0, "International Negotiation","Islomov Shuhrat Marufjonovich",          "3837074495"),

    # 05.06.2026 - Juma
    ("05.06.2026",  9,  0, "Insurance",                "Primkulova Zilola Abrorovna",           "3613211050"),
    ("05.06.2026", 10,  0, "Financial Technologies",   "Abdullayev Xudoymurod Anvar o'g'li",    "3613211050"),
    ("05.06.2026", 11,  0, "Economic Analysis",        "Berdikulova Iroda Rayimkulovna",         "3613211050"),
    ("05.06.2026", 12,  0, "Islamic Finance",          "Ishbekova Lobar Yunusxonovna",           "3613211050"),
    ("05.06.2026", 13,  0, "Public Finance",           "Ergasheva Zarifa Baxtiyarovna",          "3613211050"),
    ("05.06.2026", 14,  0, "International Negotiation","Islomov Shuhrat Marufjonovich",          "3837074495"),

    # 06.06.2026 - Shanba
    ("06.06.2026",  9,  0, "Insurance",                "Primkulova Zilola Abrorovna",           "3613211050"),
    ("06.06.2026", 10,  0, "Financial Technologies",   "Abdullayev Xudoymurod Anvar o'g'li",    "3613211050"),
    ("06.06.2026", 11,  0, "Economic Analysis",        "Berdikulova Iroda Rayimkulovna",         "3613211050"),
    ("06.06.2026", 12,  0, "Public Finance",           "Ergasheva Zarifa Baxtiyarovna",          "3613211050"),
    ("06.06.2026", 13,  0, "International Negotiation","Islomov Shuhrat Marufjonovich",          "3837074495"),
]

# ===== YORDAMCHI FUNKSIYALAR =====

def get_lesson_datetime(date_str, hour, minute):
    """Dars vaqtini datetime obyektiga aylantirish"""
    dt = datetime.strptime(date_str, "%d.%m.%Y")
    dt = dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return TZ.localize(dt)


def get_today_schedule():
    """Bugungi darslarni qaytarish"""
    today = datetime.now(TZ).strftime("%d.%m.%Y")
    lessons = [l for l in SCHEDULE if l[0] == today]
    return lessons


def get_week_schedule():
    """Kelayotgan 7 kun ichidagi darslarni qaytarish"""
    now = datetime.now(TZ)
    week_later = now + timedelta(days=7)
    lessons = []
    for l in SCHEDULE:
        dt = get_lesson_datetime(l[0], l[2], l[3])  # sana, soat, daqiqa — indekslar to'g'ri
        if now <= dt <= week_later:
            lessons.append(l)
    return lessons


def format_lesson(lesson, show_date=True):
    """Darsni chiroyli formatda ko'rsatish"""
    date_str, hour, minute, subject, teacher, zoom_id = lesson
    zoom_link = ZOOM_LINKS.get(zoom_id, f"https://zoom.us/j/{zoom_id}")
    time_str = f"{hour:02d}:{minute:02d}"
    date_part = f"📅 {date_str}\n" if show_date else ""
    return (
        f"{date_part}"
        f"🕐 *{time_str} - {int(time_str.split(':')[0])+0:02d}:50*\n"
        f"📚 *{subject}*\n"
        f"👩‍🏫 {teacher}\n"
        f"🔗 [Zoom ga kirish]({zoom_link})\n"
    )


def format_schedule_by_date(lessons):
    """Darslarni sanaga guruhlash"""
    if not lessons:
        return "📭 Dars topilmadi."

    grouped = {}
    for lesson in lessons:
        date = lesson[0]
        if date not in grouped:
            grouped[date] = []
        grouped[date].append(lesson)

    text = ""
    day_names = {0: "Dushanba", 1: "Seshanba", 2: "Chorshanba", 3: "Payshanba",
                 4: "Juma", 5: "Shanba", 6: "Yakshanba"}

    for date, day_lessons in sorted(grouped.items(), key=lambda x: datetime.strptime(x[0], "%d.%m.%Y")):
        dt = datetime.strptime(date, "%d.%m.%Y")
        day_name = day_names[dt.weekday()]
        text += f"\n━━━━━━━━━━━━━━━\n"
        text += f"📅 *{date} — {day_name}*\n"
        text += f"━━━━━━━━━━━━━━━\n"
        for lesson in sorted(day_lessons, key=lambda x: (x[1], x[2])):
            _, hour, minute, subject, teacher, zoom_id = lesson
            zoom_link = ZOOM_LINKS.get(zoom_id, f"https://zoom.us/j/{zoom_id}")
            text += f"\n🕐 *{hour:02d}:{minute:02d}* — {subject}\n"
            text += f"👩‍🏫 _{teacher}_\n"
            text += f"🔗 [Zoom ga kirish]({zoom_link})\n"

    return text


# ===== KOMANDALAR =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot ishga tushganda"""
    global CHAT_ID
    CHAT_ID = update.effective_chat.id
    
    # Chat ID ni faylga saqlash
    with open("chat_id.txt", "w") as f:
        f.write(str(CHAT_ID))

    await update.message.reply_text(
        "👋 *Salom! Dars jadvali boti ishga tushdi!*\n\n"
        "Dars boshlanishidan *15 daqiqa oldin* avtomatik xabar olasiz.\n\n"
        "📌 *Komandalar:*\n"
        "/bugun — Bugungi darslar\n"
        "/jadval — Barcha darslar\n"
        "/hafta — Kelgusi 7 kunlik jadval\n"
        "/keyingidars — Keyingi dars haqida\n"
        "/yordam — Yordam",
        parse_mode="Markdown"
    )


async def bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bugungi darslar"""
    lessons = get_today_schedule()
    today = datetime.now(TZ).strftime("%d.%m.%Y")

    if not lessons:
        await update.message.reply_text(
            f"📭 *{today}* kuni dars yo'q.",
            parse_mode="Markdown"
        )
        return

    text = f"📋 *Bugungi darslar ({today}):*\n"
    text += format_schedule_by_date(lessons)
    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)


async def jadval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Barcha darslar jadvali"""
    text = "📋 *To'liq dars jadvali (FINP-S-1323U):*\n"
    text += format_schedule_by_date(SCHEDULE)
    
    # Telegram 4096 belgidan uzun xabarni qabul qilmaydi, bo'lib yuborish
    if len(text) > 4000:
        chunks = []
        current = ""
        for line in text.split("\n"):
            if len(current) + len(line) > 3800:
                chunks.append(current)
                current = line + "\n"
            else:
                current += line + "\n"
        if current:
            chunks.append(current)
        for chunk in chunks:
            await update.message.reply_text(chunk, parse_mode="Markdown", disable_web_page_preview=True)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)


async def hafta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Kelgusi 7 kunlik jadval"""
    lessons = get_week_schedule()
    text = "📋 *Kelgusi 7 kunlik jadval:*\n"
    text += format_schedule_by_date(lessons)
    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)


async def keyingi_dars(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Keyingi dars haqida ma'lumot"""
    now = datetime.now(TZ)
    
    upcoming = []
    for lesson in SCHEDULE:
        dt = get_lesson_datetime(lesson[0], lesson[1], lesson[2])
        if dt > now:
            upcoming.append((dt, lesson))
    
    if not upcoming:
        await update.message.reply_text("📭 Kelgusi darslar topilmadi.")
        return
    
    upcoming.sort(key=lambda x: x[0])
    next_dt, next_lesson = upcoming[0]
    
    delta = next_dt - now
    hours = int(delta.total_seconds() // 3600)
    minutes = int((delta.total_seconds() % 3600) // 60)
    
    time_left = ""
    if hours > 0:
        time_left = f"{hours} soat {minutes} daqiqadan so'ng"
    else:
        time_left = f"{minutes} daqiqadan so'ng"
    
    _, hour, minute, subject, teacher, zoom_id = next_lesson
    zoom_link = ZOOM_LINKS.get(zoom_id, f"https://zoom.us/j/{zoom_id}")
    
    text = (
        f"⏰ *Keyingi dars:*\n\n"
        f"🕐 *{hour:02d}:{minute:02d}* ({time_left})\n"
        f"📅 {next_lesson[0]}\n"
        f"📚 *{subject}*\n"
        f"👩‍🏫 {teacher}\n"
        f"🔗 [Zoom ga kirish]({zoom_link})"
    )
    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)


async def yordam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 *Komandalar:*\n\n"
        "/bugun — Bugungi darslar\n"
        "/jadval — Barcha darslar ro'yxati\n"
        "/hafta — Kelgusi 7 kunlik jadval\n"
        "/keyingidars — Keyingi dars\n"
        "/yordam — Ushbu yordam xabari",
        parse_mode="Markdown"
    )


# ===== AVTOMATIK ESLATMA =====

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    """Dars boshlanishidan 15 daqiqa oldin xabar yuborish"""
    job_data = context.job.data
    chat_id = job_data["chat_id"]
    lesson = job_data["lesson"]
    
    _, hour, minute, subject, teacher, zoom_id = lesson
    zoom_link = ZOOM_LINKS.get(zoom_id, f"https://zoom.us/j/{zoom_id}")
    
    text = (
        f"🔔 *Dars eslatmasi!*\n\n"
        f"⏰ *15 daqiqadan so'ng dars boshlanadi*\n\n"
        f"🕐 {hour:02d}:{minute:02d}\n"
        f"📚 *{subject}*\n"
        f"👩‍🏫 {teacher}\n"
        f"🔗 [Zoom ga kirish]({zoom_link})\n\n"
        f"Zoom ID: `{zoom_id}`"
    )
    
    keyboard = [[InlineKeyboardButton("🔗 Zoom ga kirish", url=zoom_link)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="Markdown",
        reply_markup=reply_markup,
        disable_web_page_preview=True
    )


def schedule_reminders(app, chat_id):
    """Barcha darslar uchun eslatmalarni rejalashtirish"""
    now = datetime.now(TZ)
    count = 0
    
    for lesson in SCHEDULE:
        lesson_dt = get_lesson_datetime(lesson[0], lesson[1], lesson[2])
        reminder_dt = lesson_dt - timedelta(minutes=15)
        
        # O'tib ketgan vaqtlarni o'tkazib yuborish
        if reminder_dt <= now:
            continue
        
        app.job_queue.run_once(
            send_reminder,
            when=reminder_dt,
            data={"chat_id": chat_id, "lesson": lesson},
            name=f"reminder_{lesson[0]}_{lesson[1]}_{lesson[2]}"
        )
        count += 1
    
    logger.info(f"{count} ta eslatma rejalashtirildi")
    return count


# ===== ASOSIY FUNKSIYA =====

def main():
    """Botni ishga tushirish"""
    # Chat ID ni fayldan o'qish (agar mavjud bo'lsa)
    global CHAT_ID
    try:
        with open("chat_id.txt", "r") as f:
            CHAT_ID = int(f.read().strip())
            logger.info(f"Chat ID yuklandi: {CHAT_ID}")
    except FileNotFoundError:
        logger.info("chat_id.txt topilmadi. /start bosing.")

    app = Application.builder().token(BOT_TOKEN).build()

    # Komandalar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("bugun", bugun))
    app.add_handler(CommandHandler("jadval", jadval))
    app.add_handler(CommandHandler("hafta", hafta))
    app.add_handler(CommandHandler("keyingidars", keyingi_dars))
    app.add_handler(CommandHandler("yordam", yordam))

    # Eslatmalarni rejalashtirish (agar chat_id mavjud bo'lsa)
    async def post_init(application):
        if CHAT_ID:
            count = schedule_reminders(application, CHAT_ID)
            logger.info(f"Bot tayyor. {count} ta eslatma rejalashtirildi.")
        else:
            logger.info("Chat ID yo'q — /start bosing.")

    app.post_init = post_init

    logger.info("Bot ishga tushmoqda...")
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
