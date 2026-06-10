import json
import logging
import os
import sqlite3
import csv
import io
import threading
from datetime import datetime, timedelta
from flask import Flask, request, session, redirect, url_for, render_template_string

import pytz
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from groq import Groq

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
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Rate limiter: {user_id: [timestamp1, timestamp2, ...]}
user_rate_limits = {}

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
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                username TEXT,
                action_type TEXT,
                content TEXT,
                ai_response TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        try:
            cursor.execute("ALTER TABLE logs ADD COLUMN ai_response TEXT")
        except:
            pass
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS broadcasts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT,
                status TEXT DEFAULT 'pending',
                success_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        try:
            cursor.execute("ALTER TABLE broadcasts ADD COLUMN success_count INTEGER DEFAULT 0")
            cursor.execute("ALTER TABLE broadcasts ADD COLUMN failed_count INTEGER DEFAULT 0")
        except:
            pass
            
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
        [KeyboardButton("🟢 Hozirgi dars"), KeyboardButton("📅 Bugungi darslar")],
        [KeyboardButton("⏩ Ertangi darslar"), KeyboardButton("⏰ Keyingi dars")],
        [KeyboardButton("📋 Haftalik jadval"), KeyboardButton("📚 To'liq jadval")],
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
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            joined_at = datetime.now(TZ).strftime("%d.%m.%Y %H:%M:%S")
            cursor.execute('''
                INSERT OR IGNORE INTO users (user_id, first_name, last_name, username, joined_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (str(user.id), user.first_name, user.last_name, user.username, joined_at))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to save user: {e}")

def log_action(user, action_type, content):
    if not user:
        return
    try:
        user_id = str(user.id)
        username = user.first_name or "UNKNOWN"
        if user.last_name:
            username += f" {user.last_name}"
        timestamp = datetime.now(TZ).strftime("%d.%m.%Y %H:%M:%S")
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO logs (user_id, username, action_type, content, timestamp) VALUES (?, ?, ?, ?, ?)",
                           (user_id, username, action_type, content, timestamp))
            conn.commit()
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Failed to log action: {e}")
        return None

def update_log_ai(log_id, ai_response):
    if not log_id: return
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE logs SET ai_response = ? WHERE id = ?", (ai_response, log_id))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to update log AI: {e}")

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
    
    menu_buttons = ["🟢 Hozirgi dars", "📅 Bugungi darslar", "⏩ Ertangi darslar", "⏰ Keyingi dars", "📋 Haftalik jadval", "📚 To'liq jadval", "ℹ️ Yordam"]
    action_type = "TUGMA" if text in menu_buttons else "MATN"
    log_id = log_action(user, action_type, text)

    if text == "🟢 Hozirgi dars":
        await cmd_hozirgi(update, context)
    elif text == "📅 Bugungi darslar":
        await cmd_bugun(update, context)
    elif text == "⏩ Ertangi darslar":
        await cmd_ertaga(update, context)
    elif text == "⏰ Keyingi dars":
        await cmd_keyingi(update, context)
    elif text == "📋 Haftalik jadval":
        await cmd_hafta(update, context)
    elif text == "📚 To'liq jadval":
        await cmd_jadval(update, context)
    elif text == "ℹ️ Yordam":
        await cmd_yordam(update, context)
    else:
        await handle_ai_chat(update, context, log_id)

async def handle_ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE, log_id: int = None):
    text = update.message.text
    user_id = str(update.effective_user.id)
    
    if not groq_client:
        await update.message.reply_text("Kechirasiz, sun'iy intellekt hozircha ulanmagan.", reply_markup=main_menu_keyboard())
        return

    # Rate limit: har foydalanuvchiga daqiqada 5 ta so'rov
    now = datetime.now(TZ)
    if user_id not in user_rate_limits:
        user_rate_limits[user_id] = []
    user_rate_limits[user_id] = [t for t in user_rate_limits[user_id] if (now - t).total_seconds() < 60]
    if len(user_rate_limits[user_id]) >= 5:
        await update.message.reply_text("⏳ Juda tez-tez yozyapsiz. Iltimos, 1 daqiqa kutib turing.", reply_markup=main_menu_keyboard())
        return
    user_rate_limits[user_id].append(now)

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    now_str = now.strftime("%d.%m.%Y %H:%M")
    schedule_text = format_schedule_by_date(SCHEDULE)
    
    system_prompt = (
        "Siz 3-kurs Finance (FINP-S-1323U) talabalari uchun yaratilgan aqlli dars jadvali va yordamchi botsiz. "
        "Talabalar savollariga do'stona, qisqa va aniq o'zbek tilida javob berasiz. "
        f"Hozirgi vaqt: {now_str}. "
        "Guruhning to'liq dars jadvali quyidagicha:\n"
        f"{schedule_text}\n"
        "AGAR talaba jadval haqida so'rasa, FAQAT yuqoridagi jadvaldan qarab to'g'ri javob bering, umuman to'qib chiqarmang! "
        "MUHIM: Javobingizni oddiy matnda yozing. Matnda hech qanday yulduzchalar (** yoki *) va qalin qilib yozish kabi formatlardan foydalanmang."
    )
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            temperature=0.7,
            max_tokens=1024
        )
        ai_text = response.choices[0].message.content
        update_log_ai(log_id, ai_text)
        await send_long_message(
            lambda t, **kw: update.message.reply_text(t, **kw),
            ai_text
        )
    except Exception as e:
        logger.error(f"Groq API xatoligi: {e}")
        error_msg = str(e)
        if "rate_limit" in error_msg.lower() or "429" in error_msg:
            err_text = "⏳ AI hozir juda band. Iltimos, bir oz kutib qayta urinib ko'ring."
        elif "api_key" in error_msg.lower() or "auth" in error_msg.lower():
            err_text = "API kalit noto'g'ri yoki yaroqsiz bo'lishi mumkin."
        else:
            err_text = "Kechirasiz, xatolik yuz berdi. Keyinroq urinib ko'ring."
        await update.message.reply_text(err_text, reply_markup=main_menu_keyboard())

async def cmd_ertaga(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(TZ)
    tomorrow = now + timedelta(days=1)
    tomorrow_str = tomorrow.strftime("%d.%m.%Y")
    
    lessons = [l for l in SCHEDULE if l[0] == tomorrow_str]
    
    if not lessons:
        await update.message.reply_text(f"📭 *{tomorrow_str}* kuni dars yo'q.", parse_mode="Markdown", reply_markup=main_menu_keyboard())
        return
        
    text = f"📋 *Ertangi darslar ({tomorrow_str}):*\n" + format_schedule_by_date(lessons)
    await send_long_message(
        lambda t, **kw: update.message.reply_text(t, **kw),
        text, parse_mode="Markdown", disable_web_page_preview=True,
        reply_markup=main_menu_keyboard()
    )

async def cmd_hozirgi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(TZ)
    lessons = get_today_schedule()
    
    if not lessons:
        await update.message.reply_text("📭 Bugun dars yo'q.", reply_markup=main_menu_keyboard())
        return

    current_lesson = None
    for lesson in lessons:
        lesson_dt = get_lesson_datetime(lesson[0], lesson[1], lesson[2])
        end_dt = lesson_dt + timedelta(minutes=50)
        if lesson_dt <= now <= end_dt:
            current_lesson = lesson
            break

    if current_lesson:
        _, hour, minute, subject, teacher, room = current_lesson
        end_dt = get_lesson_datetime(current_lesson[0], current_lesson[1], current_lesson[2]) + timedelta(minutes=50)
        text = (
            f"🟢 *Hozirgi dars:*\n\n"
            f"📚 *{subject}*\n"
            f"👩‍🏫 O'qituvchi: {teacher}\n"
            f"🚪 Xona: *{room}*\n"
            f"🕐 Vaqt: {hour:02d}:{minute:02d} dan {end_dt.strftime('%H:%M')} gacha"
        )
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())
    else:
        first_lesson_dt = get_lesson_datetime(lessons[0][0], lessons[0][1], lessons[0][2])
        last_lesson_end = get_lesson_datetime(lessons[-1][0], lessons[-1][1], lessons[-1][2]) + timedelta(minutes=50)
        
        if now < first_lesson_dt:
            await update.message.reply_text("⏳ Hali dars boshlanmadi.", reply_markup=main_menu_keyboard())
        elif now > last_lesson_end:
            await update.message.reply_text("🏁 Bugun uchun barcha darslar tugadi.", reply_markup=main_menu_keyboard())
        else:
            await update.message.reply_text("☕ Hozir tanaffus. Hali dars boshlanmadi.", reply_markup=main_menu_keyboard())

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
        "🔔 *Eslatmalar tizimi:*\n"
        "1️⃣ Dars boshlanishiga 5 daqiqa qolganda\n"
        "2️⃣ Dars boshlanganda\n"
        "3️⃣ Dars tugaganda avtomatik xabar keladi.\n\n"
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
        
    text = f"📊 <b>Bot statistikasi:</b>\n👥 Jami foydalanuvchilar: {len(users)} ta\n\n<b>Ro'yxat:</b>\n"
    for idx, row in enumerate(users, 1):
        uid, fname, lname, uname, joined = row
        name = fname or ""
        if lname:
            name += f" {lname}"
        
        name = name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        
        username = f" (@{uname})" if uname else ""
        text += f"{idx}. {name}{username} (ID: <code>{uid}</code>) - <i>ulandi: {joined}</i>\n"
        
    await send_long_message(
        lambda t, **kw: update.message.reply_text(t, **kw),
        text, parse_mode="HTML"
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
        
    custom_message = update.message.text.replace("/send", "", 1).strip()
    
    if not custom_message:
        await update.message.reply_text(
            "Iltimos, yubormoqchi bo'lgan xabaringizni yozing.\n\nMasalan: `/send Ertaga 1-para dars bo'lmaydi`", 
            parse_mode="Markdown"
        )
        return
    
    success = 0
    failed = 0
    await update.message.reply_text(f"⏳ Xabar {len(users)} ta foydalanuvchiga yuborish boshlandi...")
    
    for (uid,) in users:
        try:
            # parse_mode yozilmaganligi sababli barcha maxsus belgilar xatosiz oddiy matndek ketadi
            await context.bot.send_message(chat_id=uid, text=custom_message)
            success += 1
        except Exception as e:
            logger.error(f"Xabar yuborishda xatolik (ID: {uid}): {e}")
            failed += 1
            
    await update.message.reply_text(
        f"✅ <b>Xabar yuborish yakunlandi!</b>\n\n"
        f"🟢 Muvaffaqiyatli bordi: {success} ta\n"
        f"🔴 Yuborilmadi (botni o'chirib yuborganlar): {failed} ta", 
        parse_mode="HTML"
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

async def send_pre_reminder(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    chat_id = job_data["chat_id"]
    lesson = job_data["lesson"]
    _, hour, minute, subject, teacher, room = lesson

    text = (
        f"🔔 *Eslatma!*\n\n"
        f"⏰ *Dars boshlanishiga 5 daqiqa qoldi*\n\n"
        f"🕐 {hour:02d}:{minute:02d}\n"
        f"📚 *{subject}*\n"
        f"👩‍🏫 {teacher}\n"
        f"🚪 Xona: *{room}*"
    )
    await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown", disable_web_page_preview=True)

async def send_start_reminder(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    chat_id = job_data["chat_id"]
    lesson = job_data["lesson"]
    _, hour, minute, subject, teacher, room = lesson
    
    # Tugash vaqtini hisoblaymiz (50 daqiqa davom etadi)
    end_dt = datetime.strptime(f"{hour:02d}:{minute:02d}", "%H:%M") + timedelta(minutes=50)

    text = (
        f"🟢 *Dars boshlandi!*\n\n"
        f"📚 *{subject}*\n"
        f"👩‍🏫 O'qituvchi: {teacher}\n"
        f"🚪 Xona: *{room}*\n"
        f"🕐 Vaqt: {hour:02d}:{minute:02d} dan {end_dt.strftime('%H:%M')} gacha"
    )
    await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown", disable_web_page_preview=True)

async def send_end_reminder(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    chat_id = job_data["chat_id"]
    lesson = job_data["lesson"]
    _, hour, minute, subject, teacher, room = lesson
    
    # 50 daqiqa qo'shib tugash vaqtini hisoblaymiz
    end_dt = datetime.strptime(f"{hour:02d}:{minute:02d}", "%H:%M") + timedelta(minutes=50)

    text = (
        f"🔴 *Dars tugadi!*\n\n"
        f"📚 *{subject}*\n"
        f"👩‍🏫 O'qituvchi: {teacher}\n"
        f"🚪 Xona: *{room}*\n"
        f"🕐 Vaqt: {hour:02d}:{minute:02d} dan {end_dt.strftime('%H:%M')} gacha"
    )
    await context.bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown", disable_web_page_preview=True)

def schedule_reminders(app, chat_id):
    now = datetime.now(TZ)
    count = 0
    logger.info("--- ESLATMALAR TEKSHIRUVI ---")
    logger.info(f"Hozirgi O'zbekiston vaqti (UTC+5): {now.strftime('%d.%m.%Y %H:%M:%S')}")
    
    for lesson in SCHEDULE:
        lesson_dt = get_lesson_datetime(lesson[0], lesson[1], lesson[2])
        
        pre_dt = lesson_dt - timedelta(minutes=5)
        start_dt = lesson_dt
        end_dt = lesson_dt + timedelta(minutes=50)

        # 1. 5 minut oldin eslatma
        if pre_dt > now:
            job_name = f"pre_{lesson[0]}_{lesson[1]}_{lesson[2]}"
            if not app.job_queue.get_jobs_by_name(job_name):
                app.job_queue.run_once(send_pre_reminder, when=pre_dt, data={"chat_id": chat_id, "lesson": lesson}, name=job_name)
                count += 1

        # 2. Dars boshlandi
        if start_dt > now:
            job_name = f"start_{lesson[0]}_{lesson[1]}_{lesson[2]}"
            if not app.job_queue.get_jobs_by_name(job_name):
                app.job_queue.run_once(send_start_reminder, when=start_dt, data={"chat_id": chat_id, "lesson": lesson}, name=job_name)
                count += 1
                
        # 3. Dars tugadi
        if end_dt > now:
            job_name = f"end_{lesson[0]}_{lesson[1]}_{lesson[2]}"
            if not app.job_queue.get_jobs_by_name(job_name):
                app.job_queue.run_once(send_end_reminder, when=end_dt, data={"chat_id": chat_id, "lesson": lesson}, name=job_name)
                count += 1
            
    logger.info(f"Jami {count} ta eslatma hodisalari rejalashtirildi")
    return count


# ===== WEB DASHBOARD (FLASK) =====

app_web = Flask(__name__)
app_web.secret_key = os.environ.get("BOT_TOKEN", "super_secret_key_123")

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dars Jadvali Dashboard</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;800&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #0f172a;
            --surface: rgba(255, 255, 255, 0.05);
            --border: rgba(255, 255, 255, 0.1);
            --primary: #3b82f6;
            --primary-hover: #2563eb;
            --text: #f8fafc;
            --text-muted: #94a3b8;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; font-family: 'Inter', sans-serif; }
        body { background: var(--bg); color: var(--text); min-height: 100vh; display: flex; flex-direction: column; align-items: center; padding: 2rem; }
        .glass { background: var(--surface); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); border: 1px solid var(--border); border-radius: 16px; box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1); }
        .container { max-width: 1000px; width: 100%; margin-top: 2rem; }
        h1 { font-weight: 800; font-size: 2.5rem; margin-bottom: 0.5rem; text-align: center; background: -webkit-linear-gradient(45deg, #60a5fa, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        p.subtitle { text-align: center; color: var(--text-muted); margin-bottom: 2rem; }
        
        .login-card { max-width: 400px; margin: 5rem auto; padding: 3rem 2rem; text-align: center; }
        input[type="password"] { width: 100%; padding: 1rem; border-radius: 8px; border: 1px solid var(--border); background: rgba(0,0,0,0.2); color: white; margin-bottom: 1rem; font-size: 1.1rem; text-align: center; outline: none; transition: border-color 0.3s; }
        input[type="password"]:focus { border-color: var(--primary); }
        button { width: 100%; padding: 1rem; background: var(--primary); color: white; border: none; border-radius: 8px; font-weight: 600; font-size: 1.1rem; cursor: pointer; transition: background 0.3s, transform 0.1s; }
        button:hover { background: var(--primary-hover); transform: translateY(-2px); }
        button:active { transform: translateY(0); }
        .error { color: #ef4444; margin-bottom: 1rem; font-size: 0.9rem; }
        
        .table-wrapper { width: 100%; overflow-x: auto; padding: 1rem; border-radius: 16px; }
        table { width: 100%; border-collapse: collapse; min-width: 800px; }
        th, td { padding: 1rem; text-align: left; border-bottom: 1px solid var(--border); }
        th { font-weight: 600; color: var(--text-muted); text-transform: uppercase; font-size: 0.85rem; letter-spacing: 0.05em; }
        tr:hover { background: rgba(255, 255, 255, 0.02); }
        td.action-matn { color: #a78bfa; font-weight: 600; }
        td.action-tugma { color: #34d399; font-weight: 600; }
        .empty { text-align: center; padding: 3rem; color: var(--text-muted); }
        
        .success-alert { background: rgba(16, 185, 129, 0.2); color: #10b981; border: 1px solid #10b981; padding: 1rem; border-radius: 8px; margin-bottom: 2rem; font-weight: 600; text-align: center; }
        textarea { width: 100%; height: 150px; padding: 1rem; border-radius: 8px; border: 1px solid var(--border); background: rgba(0,0,0,0.2); color: white; margin-bottom: 1rem; font-size: 1.1rem; outline: none; transition: border-color 0.3s; font-family: inherit; resize: vertical; }
        textarea:focus { border-color: var(--primary); }
        
        .tabs { display: flex; gap: 1rem; margin-bottom: 2rem; border-bottom: 1px solid var(--border); padding-bottom: 1rem; flex-wrap: wrap; justify-content: center; }
        .tab { color: var(--text-muted); text-decoration: none; padding: 0.5rem 1rem; border-radius: 8px; font-weight: 600; transition: all 0.3s; }
        .tab:hover { background: rgba(255,255,255,0.05); color: white; }
        .tab.active { background: var(--primary); color: white; }
        .badge-success { background: rgba(16, 185, 129, 0.2); color: #10b981; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.8rem; font-weight: 600; }
        .badge-danger { background: rgba(239, 68, 68, 0.2); color: #ef4444; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.8rem; font-weight: 600; }
        .badge-pending { background: rgba(245, 158, 11, 0.2); color: #f59e0b; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.8rem; font-weight: 600; }
        
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .animate { animation: fadeIn 0.5s ease-out forwards; }
    </style>
</head>
<body>
    <div class="container animate">
        <h1>Bot Dashboard</h1>
        <p class="subtitle">Foydalanuvchilar harakatlari tarixi</p>
        
        {% if require_login %}
            <div class="glass login-card">
                <h2 style="margin-bottom: 1.5rem; font-weight: 600;">Tizimga kiring</h2>
                {% if error %}<div class="error">{{ error }}</div>{% endif %}
                <form method="POST">
                    <input type="password" name="pin" placeholder="PIN kodni kiriting" required autofocus>
                    <button type="submit">Kirish</button>
                </form>
            </div>
        {% else %}
            <div style="display: flex; justify-content: space-between; margin-bottom: 1rem; align-items: center;">
                <form method="POST" action="/logout"><button type="submit" style="width: auto; padding: 0.5rem 1rem; background: rgba(255,255,255,0.1);">Chiqish</button></form>
            </div>
            
            <div class="tabs">
                <a href="?tab=broadcast" class="tab {% if tab == 'broadcast' %}active{% endif %}">📣 Xabarnoma</a>
                <a href="?tab=users" class="tab {% if tab == 'users' %}active{% endif %}">👥 Foydalanuvchilar</a>
                <a href="?tab=logs" class="tab {% if tab == 'logs' %}active{% endif %}">📊 Harakatlar Tarixi</a>
            </div>

            {% if tab == 'broadcast' %}
                {% if msg_success %}
                <div class="success-alert">✅ Xabar barcha foydalanuvchilarga jo'natilish uchun navbatga qo'yildi! U bir necha soniya ichida yetkazib beriladi.</div>
                {% endif %}
                
                <div class="glass" style="padding: 2rem; margin-bottom: 3rem;">
                    <h2 style="margin-bottom: 1rem; font-weight: 600;">📣 Barchaga xabar yuborish</h2>
                    <p style="color: var(--text-muted); margin-bottom: 1rem; font-size: 0.9rem;">Matnni istalgancha yozishingiz mumkin. Qator tashlasangiz xuddi shunday boradi. Qalin qilish uchun <code>*matn*</code>, og'ish uchun <code>_matn_</code> dan foydalaning.</p>
                    <form method="POST" action="/broadcast">
                        <textarea name="message" placeholder="Xabaringizni shu yerga yozing..." required></textarea>
                        <button type="submit" style="background: #10b981;">🚀 Hammaga Jo'natish</button>
                    </form>
                </div>
                
                <h2 style="margin-bottom: 1.5rem; font-weight: 600; text-align: center;">Oldingi xabarlar statistikasi</h2>
                <div class="glass table-wrapper" style="margin-bottom: 5rem;">
                    {% if broadcasts %}
                    <table>
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Xabar Matni</th>
                                <th>Holati</th>
                                <th>Yetib bordi</th>
                                <th>Bloklaganlar</th>
                                <th>Vaqti</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for b in broadcasts %}
                            <tr>
                                <td style="color: var(--text-muted);">{{ b[0] }}</td>
                                <td style="max-width: 300px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{{ b[1] }}</td>
                                <td>
                                    {% if b[2] == 'completed' %}<span class="badge-success">Yakunlangan</span>
                                    {% else %}<span class="badge-pending">Kutilmoqda...</span>{% endif %}
                                </td>
                                <td><span class="badge-success">🟢 {{ b[3] }} ta</span></td>
                                <td><span class="badge-danger">🔴 {{ b[4] }} ta</span></td>
                                <td style="color: var(--text-muted); font-size: 0.9rem;">{{ b[5] }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                    {% else %}
                    <div class="empty">Hozircha xabar yuborilmagan</div>
                    {% endif %}
                </div>

            {% elif tab == 'users' %}
                <h2 style="margin-bottom: 1.5rem; font-weight: 600; text-align: center;">👥 Bot Foydalanuvchilari (Jami: <b style="color: white;">{{ users|length }}</b> ta)</h2>
                <div class="glass table-wrapper" style="margin-bottom: 5rem;">
                    {% if users %}
                    <table>
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Ism</th>
                                <th>Familiya</th>
                                <th>Username</th>
                                <th>Qo'shilgan vaqti</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for u in users %}
                            <tr>
                                <td style="color: var(--text-muted);">{{ u[0] }}</td>
                                <td style="font-weight: 600;">{{ u[1] }}</td>
                                <td>{{ u[2] or '-' }}</td>
                                <td style="color: #3b82f6;">{% if u[3] %}@{{ u[3] }}{% else %}-{% endif %}</td>
                                <td style="color: var(--text-muted); font-size: 0.9rem;">{{ u[4] }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                    {% else %}
                    <div class="empty">Hozircha foydalanuvchilar yo'q</div>
                    {% endif %}
                </div>

            {% elif tab == 'logs' %}
                <div style="display: flex; justify-content: space-between; margin-bottom: 1rem; align-items: center;">
                    <span style="color: var(--text-muted);">Jami yozuvlar: <b style="color: white;">{{ logs|length }}</b> ta (So'nggi 500 ta)</span>
                </div>
                <div class="glass table-wrapper">
                    {% if logs %}
                    <table>
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Foydalanuvchi</th>
                                <th>Harakat</th>
                                <th>Xabar / Tugma</th>
                                <th>Vaqti</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for log in logs %}
                            <tr>
                                <td style="color: var(--text-muted);">{{ log[1] }}</td>
                                <td style="font-weight: 600;">{{ log[2] }}</td>
                                <td class="{% if log[3] == 'MATN' %}action-matn{% else %}action-tugma{% endif %}">{{ log[3] }}</td>
                                <td style="max-width: 400px; line-height: 1.5;">
                                    <div style="font-weight:600; margin-bottom:0.5rem; word-wrap: break-word;">{{ log[4] }}</div>
                                    {% if log[6] %}
                                    <div style="color: #10b981; font-size: 0.9rem; border-left: 2px solid #10b981; padding-left: 0.5rem; word-wrap: break-word;"><b>AI:</b> {{ log[6][:150] }}{% if log[6]|length > 150 %}...{% endif %}</div>
                                    {% endif %}
                                </td>
                                <td style="color: var(--text-muted); font-size: 0.9rem;">{{ log[5] }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                    {% else %}
                    <div class="empty">Hozircha ma'lumot yo'q</div>
                    {% endif %}
                </div>
            {% endif %}
        {% endif %}
    </div>
</body>
</html>
"""

@app_web.route('/', methods=['GET', 'POST'])
@app_web.route('/logs', methods=['GET', 'POST'])
def dashboard():
    error = None
    if request.method == 'POST':
        pin = request.form.get('pin')
        if pin == '701':
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            error = "Xato PIN kod kiritildi!"

    if not session.get('logged_in'):
        return render_template_string(HTML_TEMPLATE, require_login=True, error=error)
        
    tab = request.args.get('tab', 'broadcast')
    logs = []
    users = []
    broadcasts = []
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            if tab == 'logs':
                cursor.execute("SELECT id, user_id, username, action_type, content, timestamp, ai_response FROM logs ORDER BY id DESC LIMIT 500")
                logs = cursor.fetchall()
            elif tab == 'users':
                cursor.execute("SELECT user_id, first_name, last_name, username, joined_at FROM users ORDER BY joined_at DESC")
                users = cursor.fetchall()
            elif tab == 'broadcast':
                cursor.execute("SELECT id, message, status, success_count, failed_count, created_at FROM broadcasts ORDER BY id DESC LIMIT 50")
                broadcasts = cursor.fetchall()
    except Exception as e:
        logger.error(f"Web DB error: {e}")
        
    msg_success = session.pop('msg_success', False)
    return render_template_string(HTML_TEMPLATE, require_login=False, tab=tab, logs=logs, users=users, broadcasts=broadcasts, msg_success=msg_success)

@app_web.route('/broadcast', methods=['POST'])
def broadcast():
    if not session.get('logged_in'):
        return redirect(url_for('dashboard'))
    message = request.form.get('message')
    if message:
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                created_at = datetime.now(TZ).strftime("%d.%m.%Y %H:%M:%S")
                cursor.execute("INSERT INTO broadcasts (message, created_at) VALUES (?, ?)", (message, created_at))
                conn.commit()
        except Exception as e:
            logger.error(f"Broadcast DB error: {e}")
    session['msg_success'] = True
    return redirect(url_for('dashboard'))

@app_web.route('/logout', methods=['POST'])
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('dashboard'))

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app_web.run(host="0.0.0.0", port=port, use_reloader=False)

async def check_broadcasts(context: ContextTypes.DEFAULT_TYPE):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, message FROM broadcasts WHERE status = 'pending'")
            pending = cursor.fetchall()
            
            if pending:
                cursor.execute("SELECT user_id FROM users")
                users = cursor.fetchall()
                
                for b_id, message in pending:
                    success_count = 0
                    failed_count = 0
                    for (u_id,) in users:
                        try:
                            await context.bot.send_message(chat_id=u_id, text=message, parse_mode="Markdown")
                            success_count += 1
                        except Exception as e:
                            failed_count += 1
                            logger.error(f"Broadcast yuborishda xatolik (ID: {u_id}): {e}")
                            
                    cursor.execute("UPDATE broadcasts SET status = 'completed', success_count = ?, failed_count = ? WHERE id = ?", (success_count, failed_count, b_id))
                    conn.commit()
                    logger.info(f"Broadcast #{b_id} {success_count} kishiga yuborildi.")
    except Exception as e:
        logger.error(f"Broadcast check xatoligi: {e}")

# ===== MAIN =====

def main():
    global CHAT_ID
    
    init_db()
    
    threading.Thread(target=run_flask, daemon=True).start()
    logger.info("Web Dashboard serveri ishga tushirildi.")
    
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
            
        application.job_queue.run_repeating(check_broadcasts, interval=10)
            
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
