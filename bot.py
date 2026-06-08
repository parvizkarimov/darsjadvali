import json
import logging
import os
import sqlite3
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
ADMIN_ID = os.environ.get("ADMIN_ID", "882178675") # Admin telegram ID si
CHAT_ID = None
TZ = pytz.timezone("Asia/Tashkent")
DB_PATH = os.environ.get("DB_PATH", "data/bot_database.db")

# ===== BAZANI ISHGA TUSHIRISH =====
def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                username TEXT,
                joined_at TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        conn.commit()

# ===== OFLAYN DARS JADVALI (08.06.2026 - 13.06.2026) =====
SCHEDULE = [
    # 08.06.2026 - Dushanba
    ("08.06.2026", 13, 0, "INSURANCE", "ABDULLAYEV XUDOYMUROD", "A-503"),
    ("08.06.2026", 14, 0, "INSURANCE", "PRIMKULOVA ZILOLA", "A-303"),
    ("08.06.2026", 15, 0, "ISLAMIC FINANCE", "XAYDARI ZOXIR", "A-502"),
    ("08.06.2026", 16, 0, "INTERNATIONAL NEGOTIATION", "ISLOMOV SHUHRAT", "A-303"),

    # 09.06.2026 - Seshanba
    ("09.06.2026", 13, 0, "FINANCIAL TECHNOLOGIES", "KARIMOVA SHAHRIZODA", "C -102"),
    ("09.06.2026", 14, 0, "INSURANCE", "PRIMKULOVA ZILOLA", "A-303"),
    ("09.06.2026", 15, 0, "PUBLIC FINANCE", "KARIMOVA SHAHRIZODA", "C -102"),
    ("09.06.2026", 16, 0, "ECONOMIC ANALYSIS", "BERDIKULOVA IRODA", "A-303"),
    ("09.06.2026", 17, 0, "ECONOMIC ANALYSIS", "BERDIKULOVA IRODA", "A-516"),

    # 10.06.2026 - Chorshanba
    ("10.06.2026", 13, 0, "PUBLIC FINANCE", "KARIMOVA SHAHRIZODA", "C -102"),
    ("10.06.2026", 14, 0, "ISLAMIC FINANCE", "XAYDARI ZOXIR", "A-510"),
    ("10.06.2026", 15, 0, "ECONOMIC ANALYSIS", "BERDIKULOVA IRODA", "A-303"),
    ("10.06.2026", 16, 0, "ISLAMIC FINANCE", "XAYDARI ZOXIR", "A-503"),
    ("10.06.2026", 17, 0, "INTERNATIONAL NEGOTIATION", "ISLOMOV SHUHRAT", "A-502"),

    # 11.06.2026 - Payshanba
    ("11.06.2026", 13, 0, "ISLAMIC FINANCE", "XAYDARI ZOXIR", "A-503"),
    ("11.06.2026", 14, 0, "PUBLIC FINANCE", "ABDUVAXOPOV INOMJON", "A-502"),
    ("11.06.2026", 15, 0, "INSURANCE", "PRIMKULOVA ZILOLA", "A-303"),
    ("11.06.2026", 16, 0, "FINANCIAL TECHNOLOGIES", "ABDUVAXOPOV INOMJON", "A-502"),

    # 12.06.2026 - Juma
    ("12.06.2026", 13, 0, "PUBLIC FINANCE", "KARIMOVA SHAHRIZODA", "C -102"),
    ("12.06.2026", 14, 0, "FINANCIAL TECHNOLOGIES", "KARIMOVA SHAHRIZODA", "C -102"),
    ("12.06.2026", 15, 0, "ECONOMIC ANALYSIS", "BERDIKULOVA IRODA", "A-502"),
    ("12.06.2026", 16, 0, "FINANCIAL TECHNOLOGIES", "ABDUVAXOPOV INOMJON", "A-502"),

    # 13.06.2026 - Shanba
    ("13.06.2026", 13, 0, "INTERNATIONAL NEGOTIATION", "ISLOMOV SHUHRAT", "A-303"),
    ("13.06.2026", 14, 0, "ISLAMIC FINANCE", "XAYDARI ZOXIR", "A-502"),
    ("13.06.2026", 15, 0, "INTERNATIONAL NEGOTIATION", "ISLOMOV SHUHRAT", "A-510"),
    ("13.06.2026", 16, 0, "INSURANCE", "ABDULLAYEV XUDOYMUROD", "A-502"),
    ("13.06.2026", 17, 0, "PUBLIC FINANCE", "ABDUVAXOPOV INOMJON", "A-502"),
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

def save_user(user):
    if not user:
        return
    user_id_str = str(user.id)
    first_name = user.first_name or ""
    last_name = user.last_name or ""
    username = user.username or ""
    joined_at = datetime.now(TZ).strftime("%d.%m.%Y %H:%M:%S")
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id_str,))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO users (user_id, first_name, last_name, username, joined_at)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id_str, first_name, last_name, username, joined_at))
            conn.commit()

def save_chat_id(chat_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("REPLACE INTO settings (key, value) VALUES ('CHAT_ID', ?)", (str(chat_id),))
        conn.commit()

def load_chat_id():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = 'CHAT_ID'")
        row = cursor.fetchone()
        if row:
            return int(row[0])
    return None

def get_today_schedule():
    today = datetime.now(TZ).strftime("%d.%m.%Y")
    return [l for l in SCHEDULE if l[0] == today]

def get_week_schedule():
    now = datetime.now(TZ)
    # Jadvalni faqat joriy kundan kelgusi 7 kunga qaytarish
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
            _, hour, minute, subject, teacher, room = lesson
            text += f"\n🕐 *{hour:02d}:{minute:02d}* — {subject}\n"
            text += f"👩‍🏫 _{teacher}_\n"
            text += f"🚪 Xona: *{room}*\n"
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
    
    user = update.effective_user
    save_user(user)
    save_chat_id(CHAT_ID)

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
    user = update.effective_user
    save_user(user)
    
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
    now = datetime.now(TZ)
    today = now.strftime("%d.%m.%Y")
    if not lessons:
        start_date = TZ.localize(datetime(2026, 6, 8))
        if now < start_date:
            msg = "⏳ *Darslar 8-iyundan boshlanadi!*"
        else:
            msg = f"📭 *{today}* kuni dars yo'q yoki barcha darslar tugagan."
        await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_menu_keyboard())
        return
    text = f"📋 *Bugungi darslar ({today}):*\n" + format_schedule_by_date(lessons)
    await send_long_message(
        lambda t, **kw: update.message.reply_text(t, **kw),
        text, parse_mode="Markdown", disable_web_page_preview=True,
        reply_markup=main_menu_keyboard()
    )

async def cmd_hafta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("08.06 - Dushanba", callback_data="day_08.06.2026"),
         InlineKeyboardButton("09.06 - Seshanba", callback_data="day_09.06.2026")],
        [InlineKeyboardButton("10.06 - Chorshanba", callback_data="day_10.06.2026"),
         InlineKeyboardButton("11.06 - Payshanba", callback_data="day_11.06.2026")],
        [InlineKeyboardButton("12.06 - Juma", callback_data="day_12.06.2026"),
         InlineKeyboardButton("13.06 - Shanba", callback_data="day_13.06.2026")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📋 *Qaysi kunning jadvalini ko'rmoqchisiz?*", parse_mode="Markdown", reply_markup=reply_markup)

async def cmd_jadval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "📋 *To'liq dars jadvali (08.06-13.06):*\n" + format_schedule_by_date(SCHEDULE)
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

    _, hour, minute, subject, teacher, room = lesson

    text = (
        f"⏰ *Keyingi dars:*\n\n"
        f"🕐 *{hour:02d}:{minute:02d}* ({time_left})\n"
        f"📅 {lesson[0]}\n"
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
        "🎓 Bu bot *3-kurs Finance (FINP-S-1323U)* talabalari uchun mo'ljallangan (8-13 Iyun darslari).\n\n"
        "📅 *Bugungi darslar* — bugun bo'ladigan darslar\n"
        "⏰ *Keyingi dars* — keyingi dars qancha vaqtdan so'ng\n"
        "📋 *Haftalik jadval* — kelgusi 7 kun\n"
        "📚 *To'liq jadval* — barcha darslar\n\n"
        "🔔 Har bir dars boshlanishidan *15 daqiqa oldin* avtomatik eslatma keladi.\n\n"
        "❓ Bot bo'yicha savollar bo'lsa: @parvizkarimov",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

async def cmd_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    
    # Check if admin
    if not ADMIN_ID or user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Bu komanda faqat adminlar uchun.")
        return
        
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, first_name, last_name, username, joined_at FROM users")
            users = cursor.fetchall()
    except Exception as e:
        users = []
        
    if not users:
        await update.message.reply_text("📭 Hali hech qanday foydalanuvchi ulanmadi.")
        return
        
    text = f"📊 *Bot statistikasi:*\n👥 Jami foydalanuvchilar: {len(users)} ta\n\n*Ro'yxat:*\n"
    for idx, row in enumerate(users, 1):
        uid, fname, lname, uname, joined = row
        name = fname or ""
        if lname:
            name += f" {lname}"
        username = f" (@{uname})" if uname else ""
        text += f"{idx}. {name}{username} (ID: `{uid}`) - _ulandi: {joined}_\n"
        
    await send_long_message(
        lambda t, **kw: update.message.reply_text(t, **kw),
        text, parse_mode="Markdown"
    )

async def cmd_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if not ADMIN_ID or user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Bu komanda faqat adminlar uchun.")
        return
        
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users")
            users = cursor.fetchall()
    except Exception as e:
        users = []
        
    if not users:
        await update.message.reply_text("📭 Hali hech qanday foydalanuvchi ulanmadi.")
        return
        
    bot_username = context.bot.username
    text_to_send = (
        "👋 *Assalomu alaykum!*\n\n"
        "🤖 Dars jadvali botimiz eng so'nggi va ishonchli versiyaga yangilandi! "
        "Bot sizda doimiy, xatosiz ishlashi va dars eslatmalari o'z vaqtida kelishi uchun "
        "iltimos, quyidagi havolaga (ssilkaga) bosib, botni qayta ishga tushiring:\n\n"
        f"👉 https://t.me/{bot_username}?start=1 👈\n\n"
        "_(yoki bot ichida to'g'ridan-to'g'ri /start ustiga bosing)_\n\n"
        "✅ Shundan so'ng botdan bemalol foydalanishda davom etishingiz mumkin. "
        "Tushunganingiz uchun rahmat! 😊"
    )
    
    success = 0
    failed = 0
    await update.message.reply_text(f"⏳ Xabar {len(users)} ta foydalanuvchiga yuborish boshlandi...")
    
    for (uid,) in users:
        try:
            await context.bot.send_message(chat_id=uid, text=text_to_send, parse_mode="Markdown")
            success += 1
        except Exception:
            failed += 1
            
    await update.message.reply_text(
        f"✅ *Xabar yuborish yakunlandi!*\n\n"
        f"🟢 Muvaffaqiyatli bordi: {success} ta\n"
        f"🔴 Yuborilmadi (botni o'chirib yuborganlar): {failed} ta", 
        parse_mode="Markdown"
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
    elif query.data.startswith("day_"):
        date_str = query.data.split("_")[1]
        lessons = [l for l in SCHEDULE if l[0] == date_str]
        
        if not lessons:
            text = f"📭 *{date_str}* kuni dars yo'q."
        else:
            text = f"📋 *Jadval ({date_str}):*\n" + format_schedule_by_date(lessons)
            
        back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Haftalik jadvalga qaytish", callback_data="back_to_week")]])
        await query.edit_message_text(text, parse_mode="Markdown", disable_web_page_preview=True, reply_markup=back_kb)
        
    elif query.data == "back_to_week":
        keyboard = [
            [InlineKeyboardButton("08.06 - Dushanba", callback_data="day_08.06.2026"),
             InlineKeyboardButton("09.06 - Seshanba", callback_data="day_09.06.2026")],
            [InlineKeyboardButton("10.06 - Chorshanba", callback_data="day_10.06.2026"),
             InlineKeyboardButton("11.06 - Payshanba", callback_data="day_11.06.2026")],
            [InlineKeyboardButton("12.06 - Juma", callback_data="day_12.06.2026"),
             InlineKeyboardButton("13.06 - Shanba", callback_data="day_13.06.2026")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("📋 *Qaysi kunning jadvalini ko'rmoqchisiz?*", parse_mode="Markdown", reply_markup=reply_markup)

# ===== ESLATMALAR =====

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    chat_id = job_data["chat_id"]
    lesson = job_data["lesson"]
    _, hour, minute, subject, teacher, room = lesson

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
    now = datetime.now(TZ)
    count = 0
    logger.info("--- ESLATMALAR TEKSHIRUVI ---")
    logger.info(f"Hozirgi O'zbekiston vaqti (UTC+5): {now.strftime('%d.%m.%Y %H:%M:%S')}")
    
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
            logger.info(f"Tasdiqlandi: '{lesson[3]}' darsi uchun eslatma -> {reminder_dt.strftime('%d.%m.%Y %H:%M:%S')} (O'zbekiston vaqti)")
            
    logger.info(f"Jami {count} ta eslatma rejalashtirildi")
    return count

# ===== MAIN =====

def main():
    global CHAT_ID
    
    init_db()
    
    CHAT_ID = load_chat_id()
    if CHAT_ID:
        logger.info(f"Chat ID bazadan yuklandi: {CHAT_ID}")
    else:
        logger.info("Chat ID hali o'rnatilmagan. /start bosing.")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("user", cmd_users))
    app.add_handler(CommandHandler("send", cmd_send))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))

    async def post_init(application):
        if CHAT_ID:
            schedule_reminders(application, CHAT_ID)
            
        # Adminga deploy xabarini jo'natish
        try:
            if ADMIN_ID:
                await application.bot.send_message(
                    chat_id=ADMIN_ID, 
                    text="✅ *Bot muvaffaqiyatli Railway'ga deploy bo'ldi va ishga tushdi!*",
                    parse_mode="Markdown"
                )
                logger.info("Adminga deploy xabari yuborildi.")
        except Exception as e:
            logger.error(f"Adminga deploy xabarini yuborishda xatolik: {e}")

    app.post_init = post_init

    logger.info("Bot ishga tushmoqda...")
    app.run_polling(allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    main()
