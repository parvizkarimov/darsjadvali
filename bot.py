import logging
import os
from datetime import datetime, timedelta

import pytz
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===== SOZLAMALAR =====
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = None
TZ = pytz.timezone("Asia/Tashkent")

ZOOM_LINKS = {
    "3613211050": "https://us04web.zoom.us/j/3613211050",
    "3837074495": "https://us04web.zoom.us/j/3837074495",
}

# ===== DARS JADVALI =====
SCHEDULE = [
    # 15.05.2026 - Juma
    ("15.05.2026",  9,  0, "Insurance",                 "Primkulova Zilola Abrorovna",           "3613211050"),
    ("15.05.2026", 10,  0, "Economic Analysis",         "Berdikulova Iroda Rayimkulovna",         "3613211050"),
    ("15.05.2026", 11,  0, "Islamic Finance",           "Ishbekova Lobar Yunusxonovna",           "3613211050"),
    ("15.05.2026", 12,  0, "Public Finance",            "Ergasheva Zarifa Baxtiyarovna",          "3613211050"),
    ("15.05.2026", 13,  0, "International Negotiation", "Islomov Shuhrat Marufjonovich",          "3837074495"),
    # 16.05.2026 - Shanba
    ("16.05.2026",  9,  0, "Insurance",                 "Primkulova Zilola Abrorovna",            "3613211050"),
    ("16.05.2026", 10,  0, "Financial Technologies",    "Abdullayev Xudoymurod Anvar o'g'li",     "3613211050"),
    ("16.05.2026", 11,  0, "Islamic Finance",           "Ishbekova Lobar Yunusxonovna",           "3613211050"),
    ("16.05.2026", 12,  0, "Public Finance",            "Ergasheva Zarifa Baxtiyarovna",          "3613211050"),
    ("16.05.2026", 13,  0, "International Negotiation", "Islomov Shuhrat Marufjonovich",          "3837074495"),
    # 22.05.2026 - Juma
    ("22.05.2026",  9,  0, "Insurance",                 "Primkulova Zilola Abrorovna",            "3613211050"),
    ("22.05.2026", 10,  0, "Financial Technologies",    "Abdullayev Xudoymurod Anvar o'g'li",     "3613211050"),
    ("22.05.2026", 11,  0, "Economic Analysis",         "Berdikulova Iroda Rayimkulovna",         "3613211050"),
    ("22.05.2026", 12,  0, "Islamic Finance",           "Ishbekova Lobar Yunusxonovna",           "3613211050"),
    ("22.05.2026", 13,  0, "Public Finance",            "Ergasheva Zarifa Baxtiyarovna",          "3613211050"),
    ("22.05.2026", 14,  0, "International Negotiation", "Islomov Shuhrat Marufjonovich",          "3837074495"),
    # 23.05.2026 - Shanba
    ("23.05.2026",  9,  0, "Insurance",                 "Primkulova Zilola Abrorovna",            "3613211050"),
    ("23.05.2026", 10,  0, "Economic Analysis",         "Berdikulova Iroda Rayimkulovna",         "3613211050"),
    ("23.05.2026", 11,  0, "Islamic Finance",           "Ishbekova Lobar Yunusxonovna",           "3613211050"),
    ("23.05.2026", 12,  0, "Islamic Finance",           "Ishbekova Lobar Yunusxonovna",           "3613211050"),
    ("23.05.2026", 13,  0, "Public Finance",            "Ergasheva Zarifa Baxtiyarovna",          "3613211050"),
    # 29.05.2026 - Juma
    ("29.05.2026",  9,  0, "Insurance",                 "Primkulova Zilola Abrorovna",            "3613211050"),
    ("29.05.2026", 10,  0, "Financial Technologies",    "Abdullayev Xudoymurod Anvar o'g'li",     "3613211050"),
    ("29.05.2026", 11,  0, "Islamic Finance",           "Ishbekova Lobar Yunusxonovna",           "3613211050"),
    ("29.05.2026", 12,  0, "Public Finance",            "Ergasheva Zarifa Baxtiyarovna",          "3613211050"),
    ("29.05.2026", 13,  0, "International Negotiation", "Islomov Shuhrat Marufjonovich",          "3837074495"),
    # 30.05.2026 - Shanba
    ("30.05.2026",  9,  0, "Insurance",                 "Primkulova Zilola Abrorovna",            "3613211050"),
    ("30.05.2026", 10,  0, "Financial Technologies",    "Abdullayev Xudoymurod Anvar o'g'li",     "3613211050"),
    ("30.05.2026", 11,  0, "Economic Analysis",         "Berdikulova Iroda Rayimkulovna",         "3613211050"),
    ("30.05.2026", 12,  0, "Islamic Finance",           "Ishbekova Lobar Yunusxonovna",           "3613211050"),
    ("30.05.2026", 13,  0, "Public Finance",            "Ergasheva Zarifa Baxtiyarovna",          "3613211050"),
    ("30.05.2026", 14,  0, "International Negotiation", "Islomov Shuhrat Marufjonovich",          "3837074495"),
    # 05.06.2026 - Juma
    ("05.06.2026",  9,  0, "Insurance",                 "Primkulova Zilola Abrorovna",            "3613211050"),
    ("05.06.2026", 10,  0, "Financial Technologies",    "Abdullayev Xudoymurod Anvar o'g'li",     "3613211050"),
    ("05.06.2026", 11,  0, "Economic Analysis",         "Berdikulova Iroda Rayimkulovna",         "3613211050"),
    ("05.06.2026", 12,  0, "Islamic Finance",           "Ishbekova Lobar Yunusxonovna",           "3613211050"),
    ("05.06.2026", 13,  0, "Public Finance",            "Ergasheva Zarifa Baxtiyarovna",          "3613211050"),
    ("05.06.2026", 14,  0, "International Negotiation", "Islomov Shuhrat Marufjonovich",          "3837074495"),
    # 06.06.2026 - Shanba
    ("06.06.2026",  9,  0, "Insurance",                 "Primkulova Zilola Abrorovna",            "3613211050"),
    ("06.06.2026", 10,  0, "Financial Technologies",    "Abdullayev Xudoymurod Anvar o'g'li",     "3613211050"),
    ("06.06.2026", 11,  0, "Economic Analysis",         "Berdikulova Iroda Rayimkulovna",         "3613211050"),
    ("06.06.2026", 12,  0, "Public Finance",            "Ergasheva Zarifa Baxtiyarovna",          "3613211050"),
    ("06.06.2026", 13,  0, "International Negotiation", "Islomov Shuhrat Marufjonovich",          "3837074495"),
]

# ===== MENYULAR =====

def main_menu_keyboard():
    """Asosiy pastki menyu (ReplyKeyboard)"""
    keyboard = [
        [KeyboardButton("📅 Bugungi darslar"), KeyboardButton("⏰ Keyingi dars")],
        [KeyboardButton("📋 Haftalik jadval"),  KeyboardButton("📚 To'liq jadval")],
        [KeyboardButton("ℹ️ Yordam")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)


def back_keyboard():
    """Inline — ortga qaytish"""
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Bosh menyu", callback_data="main_menu")]])


# ===== YORDAMCHI FUNKSIYALAR =====

def get_lesson_datetime(date_str, hour, minute):
    dt = datetime.strptime(date_str, "%d.%m.%Y").replace(hour=hour, minute=minute, second=0, microsecond=0)
    return TZ.localize(dt)


def get_today_schedule():
    today = datetime.now(TZ).strftime("%d.%m.%Y")
    return [l for l in SCHEDULE if l[0] == today]


def get_week_schedule():
    now = datetime.now(TZ)
    week_later = now + timedelta(days=7)
    return [l for l in SCHEDULE if now <= get_lesson_datetime(l[0], l[1], l[2]) <= week_later]


def format_schedule_by_date(lessons):
    if not lessons:
        return "📭 Dars topilmadi."

    grouped = {}
    for lesson in lessons:
        grouped.setdefault(lesson[0], []).append(lesson)

    day_names = {0: "Dushanba", 1: "Seshanba", 2: "Chorshanba", 3: "Payshanba",
                 4: "Juma", 5: "Shanba", 6: "Yakshanba"}
    text = ""
    for date, day_lessons in sorted(grouped.items(), key=lambda x: datetime.strptime(x[0], "%d.%m.%Y")):
        day_name = day_names[datetime.strptime(date, "%d.%m.%Y").weekday()]
        text += f"\n━━━━━━━━━━━━━━━\n📅 *{date} — {day_name}*\n━━━━━━━━━━━━━━━\n"
        for lesson in sorted(day_lessons, key=lambda x: x[1]):
            _, hour, minute, subject, teacher, zoom_id = lesson
            zoom_link = ZOOM_LINKS.get(zoom_id, f"https://zoom.us/j/{zoom_id}")
            text += f"\n🕐 *{hour:02d}:{minute:02d}* — {subject}\n"
            text += f"👩‍🏫 _{teacher}_\n"
            text += f"🔗 [Zoom ga kirish]({zoom_link})\n"
    return text


async def send_long_message(send_func, text, **kwargs):
    """Uzun xabarlarni bo'lib yuborish"""
    if len(text) <= 4000:
        await send_func(text, **kwargs)
        return
    chunks, current = [], ""
    for line in text.split("\n"):
        if len(current) + len(line) > 3800:
            chunks.append(current)
            current = line + "\n"
        else:
            current += line + "\n"
    if current:
        chunks.append(current)
    for chunk in chunks:
        await send_func(chunk, **kwargs)


# ===== HANDLERLAR =====

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global CHAT_ID
    CHAT_ID = update.effective_chat.id
    with open("chat_id.txt", "w") as f:
        f.write(str(CHAT_ID))

    schedule_reminders(context.application, CHAT_ID)

    await update.message.reply_text(
        "👋 *Salom! Dars jadvali boti ishga tushdi!*\n\n"
        "📌 Dars boshlanishidan *15 daqiqa oldin* avtomatik eslatma olasiz.\n\n"
        "Quyidagi menyudan foydalaning 👇",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )


async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pastki menyu tugmalarini qayta ishlash"""
    text = update.message.text

    if text == "📅 Bugungi darslar":
        await cmd_bugun(update, context)
    elif text == "⏰ Keyingi dars":
        await cmd_keyingi(update, context)
    elif text == "📋 Haftalik jadval":
        await cmd_hafta(update, context)
    elif text == "📚 To'liq jadval":
        await cmd_jadval(update, context)
    elif text == "ℹ️ Yordam":
        await cmd_yordam(update, context)


async def cmd_bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lessons = get_today_schedule()
    today = datetime.now(TZ).strftime("%d.%m.%Y")
    if not lessons:
        msg = f"📭 *{today}* kuni dars yo'q."
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_menu_keyboard())
        return
    text = f"📋 *Bugungi darslar ({today}):*\n" + format_schedule_by_date(lessons)
    await send_long_message(
        lambda t, **kw: update.message.reply_text(t, **kw),
        text, parse_mode="Markdown", disable_web_page_preview=True,
        reply_markup=main_menu_keyboard()
    )


async def cmd_hafta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lessons = get_week_schedule()
    text = "📋 *Kelgusi 7 kunlik jadval:*\n" + format_schedule_by_date(lessons)
    await send_long_message(
        lambda t, **kw: update.message.reply_text(t, **kw),
        text, parse_mode="Markdown", disable_web_page_preview=True,
        reply_markup=main_menu_keyboard()
    )


async def cmd_jadval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "📋 *To'liq dars jadvali (FINP-S-1323U):*\n" + format_schedule_by_date(SCHEDULE)
    await send_long_message(
        lambda t, **kw: update.message.reply_text(t, **kw),
        text, parse_mode="Markdown", disable_web_page_preview=True,
        reply_markup=main_menu_keyboard()
    )


async def cmd_keyingi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(TZ)
    upcoming = sorted(
        [(get_lesson_datetime(l[0], l[1], l[2]), l) for l in SCHEDULE
         if get_lesson_datetime(l[0], l[1], l[2]) > now],
        key=lambda x: x[0]
    )
    if not upcoming:
        await update.message.reply_text("📭 Kelgusi darslar topilmadi.", reply_markup=main_menu_keyboard())
        return

    next_dt, lesson = upcoming[0]
    delta = next_dt - now
    hours = int(delta.total_seconds() // 3600)
    minutes = int((delta.total_seconds() % 3600) // 60)
    time_left = f"{hours} soat {minutes} daqiqadan so'ng" if hours > 0 else f"{minutes} daqiqadan so'ng"

    _, hour, minute, subject, teacher, zoom_id = lesson
    zoom_link = ZOOM_LINKS.get(zoom_id, f"https://zoom.us/j/{zoom_id}")

    text = (
        f"⏰ *Keyingi dars:*\n\n"
        f"🕐 *{hour:02d}:{minute:02d}* ({time_left})\n"
        f"📅 {lesson[0]}\n"
        f"📚 *{subject}*\n"
        f"👩‍🏫 {teacher}\n"
        f"🔗 [Zoom ga kirish]({zoom_link})"
    )
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Zoom ga kirish", url=zoom_link)]])
    await update.message.reply_text(
        text, parse_mode="Markdown", disable_web_page_preview=True,
        reply_markup=keyboard
    )


async def cmd_yordam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ *Yordam*\n\n"
        "📅 *Bugungi darslar* — bugun bo'ladigan darslar\n"
        "⏰ *Keyingi dars* — keyingi dars qancha vaqtdan so'ng\n"
        "📋 *Haftalik jadval* — kelgusi 7 kun\n"
        "📚 *To'liq jadval* — barcha darslar\n\n"
        "🔔 Har bir dars boshlanishidan *15 daqiqa oldin* avtomatik eslatma keladi.",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )


# ===== CALLBACK (inline tugmalar) =====

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "main_menu":
        await query.message.reply_text(
            "Bosh menyu 👇",
            reply_markup=main_menu_keyboard()
        )


# ===== ESLATMALAR =====

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
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
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Zoom ga kirish", url=zoom_link)]])
    await context.bot.send_message(
        chat_id=chat_id, text=text,
        parse_mode="Markdown", reply_markup=keyboard,
        disable_web_page_preview=True
    )


def schedule_reminders(app, chat_id):
    now = datetime.now(TZ)
    count = 0
    for lesson in SCHEDULE:
        lesson_dt = get_lesson_datetime(lesson[0], lesson[1], lesson[2])
        reminder_dt = lesson_dt - timedelta(minutes=15)
        if reminder_dt <= now:
            continue
        job_name = f"reminder_{lesson[0]}_{lesson[1]}_{lesson[2]}"
        # Takroriy qo'shmaslik
        existing = app.job_queue.get_jobs_by_name(job_name)
        if not existing:
            app.job_queue.run_once(
                send_reminder, when=reminder_dt,
                data={"chat_id": chat_id, "lesson": lesson},
                name=job_name
            )
            count += 1
    logger.info(f"{count} ta eslatma rejalashtirildi")
    return count


# ===== MAIN =====

def main():
    global CHAT_ID
    try:
        with open("chat_id.txt", "r") as f:
            CHAT_ID = int(f.read().strip())
            logger.info(f"Chat ID yuklandi: {CHAT_ID}")
    except FileNotFoundError:
        logger.info("chat_id.txt topilmadi. /start bosing.")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))

    async def post_init(application):
        if CHAT_ID:
            schedule_reminders(application, CHAT_ID)

    app.post_init = post_init

    logger.info("Bot ishga tushmoqda...")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
