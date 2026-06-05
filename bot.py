import logging
import os
from datetime import datetime, timedelta, time

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

# ===== OFLAYN DARS JADVALI =====
# 0: Dushanba, 1: Seshanba, 2: Chorshanba, 3: Payshanba, 4: Juma, 5: Shanba, 6: Yakshanba
OFFLINE_SCHEDULE = {
    0: [ # Dushanba
        (13, 0, "INSURANCE", "ABDULLAYEV XUDOYMUROD", "A-503"),
        (14, 0, "INSURANCE", "PRIMKULOVA ZILOLA", "A-303"),
        (15, 0, "ISLAMIC FINANCE", "XAYDARI ZOXIR", "A-502"),
        (16, 0, "INTERNATIONAL NEGOTIATION", "ISLOMOV SHUHRAT", "A-303"),
    ],
    1: [ # Seshanba
        (13, 0, "FINANCIAL TECHNOLOGIES", "KARIMOVA SHAHRIZODA", "C -102"),
        (14, 0, "INSURANCE", "PRIMKULOVA ZILOLA", "A-303"),
        (15, 0, "PUBLIC FINANCE", "KARIMOVA SHAHRIZODA", "C -102"),
        (16, 0, "ECONOMIC ANALYSIS", "BERDIKULOVA IRODA", "A-303"),
        (17, 0, "ECONOMIC ANALYSIS", "BERDIKULOVA IRODA", "A-516"),
    ],
    2: [ # Chorshanba
        (13, 0, "PUBLIC FINANCE", "KARIMOVA SHAHRIZODA", "C -102"),
        (14, 0, "ISLAMIC FINANCE", "XAYDARI ZOXIR", "A-510"),
        (15, 0, "ECONOMIC ANALYSIS", "BERDIKULOVA IRODA", "A-303"),
        (16, 0, "ISLAMIC FINANCE", "XAYDARI ZOXIR", "A-503"),
        (17, 0, "INTERNATIONAL NEGOTIATION", "ISLOMOV SHUHRAT", "A-502"),
    ],
    3: [ # Payshanba
        (13, 0, "ISLAMIC FINANCE", "XAYDARI ZOXIR", "A-503"),
        (14, 0, "PUBLIC FINANCE", "ABDUVAXOPOV INOMJON", "A-502"),
        (15, 0, "INSURANCE", "PRIMKULOVA ZILOLA", "A-303"),
        (16, 0, "FINANCIAL TECHNOLOGIES", "ABDUVAXOPOV INOMJON", "A-502"),
    ],
    4: [ # Juma
        (13, 0, "PUBLIC FINANCE", "KARIMOVA SHAHRIZODA", "C -102"),
        (14, 0, "FINANCIAL TECHNOLOGIES", "KARIMOVA SHAHRIZODA", "C -102"),
        (15, 0, "ECONOMIC ANALYSIS", "BERDIKULOVA IRODA", "A-502"),
        (16, 0, "FINANCIAL TECHNOLOGIES", "ABDUVAXOPOV INOMJON", "A-502"),
    ],
    5: [ # Shanba
        (13, 0, "INTERNATIONAL NEGOTIATION", "ISLOMOV SHUHRAT", "A-303"),
        (14, 0, "ISLAMIC FINANCE", "XAYDARI ZOXIR", "A-502"),
        (15, 0, "INTERNATIONAL NEGOTIATION", "ISLOMOV SHUHRAT", "A-510"),
        (16, 0, "INSURANCE", "ABDULLAYEV XUDOYMUROD", "A-502"),
        (17, 0, "PUBLIC FINANCE", "ABDUVAXOPOV INOMJON", "A-502"),
    ],
    6: [] # Yakshanba
}

DAY_NAMES = {
    0: "Dushanba", 1: "Seshanba", 2: "Chorshanba", 3: "Payshanba",
    4: "Juma", 5: "Shanba", 6: "Yakshanba"
}

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

def get_today_schedule():
    now = datetime.now(TZ)
    weekday = now.weekday()
    return OFFLINE_SCHEDULE.get(weekday, [])

def format_day_schedule(weekday, lessons, date_str=""):
    if not lessons:
        return ""
    
    day_name = DAY_NAMES[weekday]
    header = f"📅 *{date_str} — {day_name}*" if date_str else f"📅 *{day_name}*"
    
    text = f"\n━━━━━━━━━━━━━━━\n{header}\n━━━━━━━━━━━━━━━\n"
    for lesson in sorted(lessons, key=lambda x: (x[0], x[1])):
        hour, minute, subject, teacher, room = lesson
        text += f"\n🕐 *{hour:02d}:{minute:02d}* — {subject}\n"
        text += f"👩‍🏫 _{teacher}_\n"
        text += f"🚪 Xona: *{room}*\n"
    return text

def format_full_schedule():
    text = ""
    for weekday in range(7):
        lessons = OFFLINE_SCHEDULE.get(weekday, [])
        if lessons:
            text += format_day_schedule(weekday, lessons)
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
        "👋 *Salom! 3-kurs Finance (FINP-S-1323U) oflayn dars jadvali boti!*\n\n"
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
    elif text == "📋 Haftalik jadval" or text == "📚 To'liq jadval":
        await cmd_jadval(update, context)
    elif text == "ℹ️ Yordam":
        await cmd_yordam(update, context)

async def cmd_bugun(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lessons = get_today_schedule()
    now = datetime.now(TZ)
    today_str = now.strftime("%d.%m.%Y")
    weekday = now.weekday()
    
    if not lessons:
        msg = f"📭 *{today_str}* kuni dars yo'q."
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_menu_keyboard())
        return
        
    text = f"📋 *Bugungi darslar ({today_str}):*\n" + format_day_schedule(weekday, lessons, today_str)
    await send_long_message(
        lambda t, **kw: update.message.reply_text(t, **kw),
        text, parse_mode="Markdown", disable_web_page_preview=True,
        reply_markup=main_menu_keyboard()
    )

async def cmd_jadval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "📋 *To'liq dars jadvali (FINP-S-1323U):*\n" + format_full_schedule()
    await send_long_message(
        lambda t, **kw: update.message.reply_text(t, **kw),
        text, parse_mode="Markdown", disable_web_page_preview=True,
        reply_markup=main_menu_keyboard()
    )

async def cmd_keyingi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(TZ)
    
    next_dt = None
    next_lesson = None
    
    # Check today
    weekday = now.weekday()
    today_lessons = OFFLINE_SCHEDULE.get(weekday, [])
    for lesson in sorted(today_lessons, key=lambda x: (x[0], x[1])):
        dt = now.replace(hour=lesson[0], minute=lesson[1], second=0, microsecond=0)
        if dt > now:
            next_dt = dt
            next_lesson = lesson
            break
            
    # Check next 7 days if not found today
    if not next_dt:
        for i in range(1, 8):
            next_day = now + timedelta(days=i)
            next_weekday = next_day.weekday()
            next_lessons = OFFLINE_SCHEDULE.get(next_weekday, [])
            if next_lessons:
                first_lesson = sorted(next_lessons, key=lambda x: (x[0], x[1]))[0]
                next_dt = next_day.replace(hour=first_lesson[0], minute=first_lesson[1], second=0, microsecond=0)
                next_lesson = first_lesson
                break

    if not next_dt or not next_lesson:
        await update.message.reply_text("📭 Kelgusi darslar topilmadi.", reply_markup=main_menu_keyboard())
        return

    delta = next_dt - now
    hours = int(delta.total_seconds() // 3600)
    minutes = int((delta.total_seconds() % 3600) // 60)
    time_left = f"{hours} soat {minutes} daqiqadan so'ng" if hours > 0 else f"{minutes} daqiqadan so'ng"

    hour, minute, subject, teacher, room = next_lesson

    text = (
        f"⏰ *Keyingi dars:*\n\n"
        f"🕐 *{hour:02d}:{minute:02d}* ({time_left})\n"
        f"📅 {next_dt.strftime('%d.%m.%Y')} — {DAY_NAMES[next_dt.weekday()]}\n"
        f"📚 *{subject}*\n"
        f"👩‍🏫 {teacher}\n"
        f"🚪 Xona: *{room}*"
    )
    
    await update.message.reply_text(
        text, parse_mode="Markdown", disable_web_page_preview=True,
        reply_markup=main_menu_keyboard()
    )

async def cmd_yordam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ *Yordam*\n\n"
        "🎓 Bu bot *3-kurs Finance (FINP-S-1323U)* talabalari uchun mo'ljallangan (Oflayn darslar).\n\n"
        "📅 *Bugungi darslar* — bugun bo'ladigan darslar\n"
        "⏰ *Keyingi dars* — keyingi dars qancha vaqtdan so'ng\n"
        "📋 *Haftalik jadval* — barcha darslar ro'yxati\n"
        "📚 *To'liq jadval* — barcha darslar ro'yxati\n\n"
        "🔔 Har bir dars boshlanishidan *15 daqiqa oldin* avtomatik eslatma keladi.\n\n"
        "❓ Bot bo'yicha savollar bo'lsa: @parvizkarimov",
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
    hour, minute, subject, teacher, room = lesson

    text = (
        f"🔔 *Dars eslatmasi!*\n\n"
        f"⏰ *15 daqiqadan so'ng dars boshlanadi*\n\n"
        f"🕐 {hour:02d}:{minute:02d}\n"
        f"📚 *{subject}*\n"
        f"👩‍🏫 {teacher}\n"
        f"🚪 Xona: *{room}*"
    )
    
    await context.bot.send_message(
        chat_id=chat_id, text=text,
        parse_mode="Markdown",
        disable_web_page_preview=True
    )

def schedule_reminders(app, chat_id):
    # Oldingi barcha eslatmalarni o'chirish
    for job in app.job_queue.jobs():
        if job.name and job.name.startswith("reminder_"):
            job.schedule_removal()

    count = 0
    for weekday, lessons in OFFLINE_SCHEDULE.items():
        for lesson in lessons:
            hour, minute, subject, teacher, room = lesson
            
            # Eslatma vaqti (15 daqiqa oldin)
            dummy_dt = datetime(2026, 1, 1, hour, minute)
            reminder_dt = dummy_dt - timedelta(minutes=15)
            reminder_time = time(hour=reminder_dt.hour, minute=reminder_dt.minute, tzinfo=TZ)
            
            job_name = f"reminder_{weekday}_{hour}_{minute}"
            
            app.job_queue.run_daily(
                send_reminder, 
                time=reminder_time,
                days=(weekday,),
                data={"chat_id": chat_id, "lesson": lesson},
                name=job_name
            )
            count += 1
            
    logger.info(f"Yangi {count} ta haftalik eslatma rejalashtirildi")
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
