import json
import logging
import os
import sqlite3
import csv
import io
import threading
from datetime import datetime, timedelta, time
from flask import Flask, request, session, redirect, url_for, render_template_string, Response, jsonify
import urllib.request

import pytz
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from groq import Groq
import asyncio
import tempfile
from presentation_generator import generate_presentation_content, create_presentation_pdf


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
WEBAPP_URL = os.environ.get("WEBAPP_URL", "https://darsjadvali-production.up.railway.app") # Railway app domen yoki o'zingizning domen (https bilan)

groq_client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None

# Rate limiter: {user_id: [timestamp1, timestamp2, ...]}
user_rate_limits = {}

# Suhbat xotirasi: {user_id: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}
chat_history = {}

# ===== AI XOTIRASIGA SAVOLLARNI YUKLASH =====
EXAM_QUESTIONS_TEXT = ""

def load_exam_questions_text():
    global EXAM_QUESTIONS_TEXT
    try:
        q_path = os.path.join(os.path.dirname(__file__), 'questions.json')
        if os.path.exists(q_path):
            with open(q_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if "ECONOMIC ANALYSIS" in data:
                text_lines = ["ECONOMIC ANALYSIS imtihon savollari va TO'G'RI javoblari:"]
                for idx, q in enumerate(data["ECONOMIC ANALYSIS"], 1):
                    correct_ans = q["options"][q["correct"]]
                    text_lines.append(f"{idx}. {q['text']} -> Javob: {correct_ans}")
                EXAM_QUESTIONS_TEXT = "\n".join(text_lines)
                logger.info(f"Loaded {len(data['ECONOMIC ANALYSIS'])} questions into AI prompt memory.")
    except Exception as e:
        logger.error(f"Error loading exam questions for AI: {e}")

load_exam_questions_text()

# ===== TAQDIMOT REJIMI HOLATLARI =====
STATE_NONE = 0
STATE_AWAITING_AUTHOR = 1
STATE_AWAITING_TOPIC = 2
STATE_AWAITING_STYLE = 3

user_states = {} # user_id: {"state": state, "author": author, "topic": topic}


# ===== BAZANI ISHGA TUSHIRISH =====
def init_db():
    db_dir = os.path.dirname(DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                username TEXT,
                phone_number TEXT,
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
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN phone_number TEXT")
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
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS presentations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                username TEXT,
                topic TEXT,
                style_name TEXT,
                author_name TEXT,
                file_id TEXT,
                status TEXT DEFAULT 'success',
                created_at TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS test_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                first_name TEXT,
                last_name TEXT,
                username TEXT,
                score REAL,
                correct_count INTEGER,
                wrong_count INTEGER,
                skipped_count INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
            
        conn.commit()

# ===== OFLAYN DARS JADVALI (15.06.2026 - 20.06.2026) =====
SCHEDULE = [
    # 15.06.2026 - Dushanba
    ("15.06.2026", 13, 0, "INSURANCE", "ABDULLAYEV XUDOYMUROD", "A-503"),
    ("15.06.2026", 14, 0, "INSURANCE", "PRIMKULOVA ZILOLA", "C-103"),
    ("15.06.2026", 15, 0, "ISLAMIC FINANCE", "XAYDARI ZOXIR", "A-502"),
    ("15.06.2026", 16, 0, "INTERNATIONAL NEGOTIATION", "ISLOMOV SHUHRAT", "C-101"),

    # 16.06.2026 - Seshanba
    ("16.06.2026", 13, 0, "FINANCIAL TECHNOLOGIES", "KARIMOVA SHAHRIZODA", "C-102"),
    ("16.06.2026", 14, 0, "INSURANCE", "PRIMKULOVA ZILOLA", "C-109"),
    ("16.06.2026", 15, 0, "PUBLIC FINANCE", "KARIMOVA SHAHRIZODA", "C-102"),
    ("16.06.2026", 16, 0, "ECONOMIC ANALYSIS", "BERDIKULOVA IRODA", "A-303"),
    ("16.06.2026", 17, 0, "ECONOMIC ANALYSIS", "BERDIKULOVA IRODA", "A-516"),

    # 17.06.2026 - Chorshanba
    ("17.06.2026", 13, 0, "PUBLIC FINANCE", "KARIMOVA SHAHRIZODA", "C-102"),
    ("17.06.2026", 14, 0, "ISLAMIC FINANCE", "XAYDARI ZOXIR", "A-510"),
    ("17.06.2026", 15, 0, "ECONOMIC ANALYSIS", "BERDIKULOVA IRODA", "A-303"),
    ("17.06.2026", 16, 0, "ISLAMIC FINANCE", "XAYDARI ZOXIR", "A-503"),
    ("17.06.2026", 17, 0, "INTERNATIONAL NEGOTIATION", "ISLOMOV SHUHRAT", "A-516"),

    # 18.06.2026 - Payshanba
    ("18.06.2026", 13, 0, "ISLAMIC FINANCE", "XAYDARI ZOXIR", "A-503"),
    ("18.06.2026", 14, 0, "PUBLIC FINANCE", "ABDUVAXOPOV INOMJON", "A-502"),
    ("18.06.2026", 15, 0, "INSURANCE", "PRIMKULOVA ZILOLA", "C-103"),
    ("18.06.2026", 16, 0, "FINANCIAL TECHNOLOGIES", "ABDUVAXOPOV INOMJON", "A-502"),

    # 19.06.2026 - Juma
    ("19.06.2026", 13, 0, "PUBLIC FINANCE", "KARIMOVA SHAHRIZODA", "C-102"),
    ("19.06.2026", 14, 0, "FINANCIAL TECHNOLOGIES", "KARIMOVA SHAHRIZODA", "C-102"),
    ("19.06.2026", 15, 0, "ECONOMIC ANALYSIS", "BERDIKULOVA IRODA", "A-502"),
    ("19.06.2026", 16, 0, "FINANCIAL TECHNOLOGIES", "ABDUVAXOPOV INOMJON", "A-502"),

    # 20.06.2026 - Shanba
    ("20.06.2026", 13, 0, "INTERNATIONAL NEGOTIATION", "ISLOMOV SHUHRAT", "C-103"),
    ("20.06.2026", 14, 0, "ISLAMIC FINANCE", "XAYDARI ZOXIR", "A-502"),
    ("20.06.2026", 15, 0, "INTERNATIONAL NEGOTIATION", "ISLOMOV SHUHRAT", "A-510"),
    ("20.06.2026", 16, 0, "INSURANCE", "ABDULLAYEV XUDOYMUROD", "A-502"),
    ("20.06.2026", 17, 0, "PUBLIC FINANCE", "ABDUVAXOPOV INOMJON", "A-502"),
]

# ===== IMTIHON JADVALI (FIN-S-1323U) =====
EXAMS = [
    ("22.06.2026", 9, 20, "ECONOMIC ANALYSIS", "B-202"),
    ("23.06.2026", 9, 20, "FINANCIAL TECHNOLOGIES", "B-202"),
    ("24.06.2026", 9, 20, "PUBLIC FINANCE", "B-202"),
    ("25.06.2026", 9, 20, "INTERNATIONAL NEGOTIATION", "B-202"),
    ("26.06.2026", 9, 20, "INSURANCE", "B-202"),
    ("27.06.2026", 9, 20, "ISLAMIC FINANCE", "B-202"),
]

# ===== MENYULAR =====

def main_menu_keyboard():
    """Asosiy pastki menyu (ReplyKeyboard)"""
    keyboard = [
        [KeyboardButton("📅 Bugungi Imtihon"), KeyboardButton("⏩ Ertangi Imtihon")],
        [KeyboardButton("📋 To'liq ro'yxat"), KeyboardButton("📝 Prezentatsiya")],
        [KeyboardButton("ℹ️ Yordam")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def author_keyboard():
    """Muallif nomini tanlash/kiritish uchun reply keyboard"""
    keyboard = [
        [KeyboardButton("👤 Telegram ismimdan olish")],
        [KeyboardButton("🔙 Bekor qilish")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

def cancel_keyboard():
    """Oddiy bekor qilish reply keyboard"""
    keyboard = [[KeyboardButton("🔙 Bekor qilish")]]
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
            # Mavjud foydalanuvchining ismini yangilash
            cursor.execute('''
                UPDATE users SET first_name = ?, last_name = ?, username = ? WHERE user_id = ?
            ''', (user.first_name, user.last_name, user.username, str(user.id)))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to save user: {e}")

def has_phone(user_id):
    """Foydalanuvchi telefon raqamini berganmi tekshirish"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT phone_number FROM users WHERE user_id = ?", (str(user_id),))
            row = cursor.fetchone()
            return row and row[0]
    except:
        return False

def save_phone(user_id, phone_number):
    """Telefon raqamini bazaga saqlash"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE users SET phone_number = ? WHERE user_id = ?", (phone_number, str(user_id)))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to save phone: {e}")

def phone_request_keyboard():
    """Telefon raqamni ulashish tugmasi"""
    keyboard = [[KeyboardButton("📱 Telefon raqamni ulashish", request_contact=True)]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

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
            start_time = f"{hour:02d}:{minute:02d}"
            end_dt = datetime.strptime(start_time, "%H:%M") + timedelta(minutes=50)
            end_time = end_dt.strftime("%H:%M")
            text += f"\n🕐 *{start_time} - {end_time}* — {subject}\n"
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

    if not has_phone(user.id):
        await update.message.reply_text(
            "👋 *Salom! 3-kurs Finance (FINP-S-1323U) oflayn dars jadvali boti!*\n\n"
            "🔐 Botdan foydalanish uchun avval telefon raqamingizni ulashing.\n"
            "Quyidagi tugmani bosing 👇",
            parse_mode="Markdown",
            reply_markup=phone_request_keyboard()
        )
        return

    await update.message.reply_text(
        "👋 *Salom! 3-kurs Finance (FINP-S-1323U) oflayn dars jadvali boti!*\n\n"
        "📌 Dars boshlanishidan *5 daqiqa oldin* avtomatik eslatma olasiz.\n\n"
        "Quyidagi menyudan foydalaning 👇",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Telefon raqamni qabul qilish"""
    contact = update.message.contact
    user = update.effective_user
    
    if contact.user_id != user.id:
        await update.message.reply_text("⚠️ Iltimos, faqat o'z raqamingizni yuboring.", reply_markup=phone_request_keyboard())
        return
    
    save_user(user)
    save_phone(user.id, contact.phone_number)
    log_action(user, "TELEFON", contact.phone_number)
    
    await update.message.reply_text(
        "✅ *Rahmat! Telefon raqamingiz saqlandi.*\n\n"
        "Endi botdan bemalol foydalanishingiz mumkin! 👇",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pastki menyu tugmalarini qayta ishlash"""
    user = update.effective_user
    save_user(user)
    
    # Telefon raqam tekshirish
    if not has_phone(user.id):
        await update.message.reply_text(
            "🔐 Botdan foydalanish uchun avval telefon raqamingizni ulashing.\n"
            "Quyidagi tugmani bosing 👇",
            reply_markup=phone_request_keyboard()
        )
        return
    
    text = update.message.text
    user_id = str(user.id)
    
    menu_buttons = ["📅 Bugungi Imtihon", "⏩ Ertangi Imtihon", "📋 To'liq ro'yxat", "📝 Prezentatsiya", "ℹ️ Yordam"]
    
    # Agar boshqa tugma bosilsa yoki Bekor qilish tanlansa, holatni tozalaymiz
    if (text in menu_buttons and text != "📝 Prezentatsiya") or text == "🔙 Bekor qilish":
        if user_id in user_states:
            del user_states[user_id]
        if text == "🔙 Bekor qilish":
            await update.message.reply_text("❌ Taqdimot yaratish bekor qilindi.", reply_markup=main_menu_keyboard())
            return
            
    current_state = user_states.get(user_id, {}).get("state", STATE_NONE)
    
    # 1. Muallif ismini kiritish holati
    if current_state == STATE_AWAITING_AUTHOR and text not in menu_buttons:
        author = text.strip()
        if text == "👤 Telegram ismimdan olish":
            author = user.first_name
            if user.last_name:
                author += f" {user.last_name}"
                
        if not author:
            await update.message.reply_text("⚠️ Iltimos, muallif ismini kiriting.", reply_markup=author_keyboard())
            return
            
        user_states[user_id] = {"state": STATE_AWAITING_TOPIC, "author": author}
        await update.message.reply_text(
            f"👤 Muallif: *\"{author}\"*\n\n"
            "Endi taqdimot (prezentatsiya) mavzusini yozib yuboring:\n"
            "Masalan: `Sun'iy intellektning kelajagi` yoki `O'zbekiston iqtisodiyoti`",
            parse_mode="Markdown",
            reply_markup=cancel_keyboard()
        )
        return

    # 2. Mavzuni kiritish holati
    elif current_state == STATE_AWAITING_TOPIC and text not in menu_buttons:
        topic = text.strip()
        if not topic:
            await update.message.reply_text("⚠️ Iltimos, yaroqli mavzu kiriting.", reply_markup=cancel_keyboard())
            return
            
        author = user_states[user_id]["author"]
        user_states[user_id] = {"state": STATE_AWAITING_STYLE, "author": author, "topic": topic}
        
        keyboard = [
            [InlineKeyboardButton("Corporate Blue 🏢", callback_data="style_corporate_blue"),
             InlineKeyboardButton("Sleek Dark 🌙", callback_data="style_sleek_dark")],
            [InlineKeyboardButton("Warm Minimalist 🎨", callback_data="style_warm_minimalist"),
             InlineKeyboardButton("Eco Green 🌿", callback_data="style_eco_green")],
            [InlineKeyboardButton("Sunset Orange 🍊", callback_data="style_sunset_orange"),
             InlineKeyboardButton("Ocean Breeze 🌊", callback_data="style_ocean_breeze")],
            [InlineKeyboardButton("Royal Purple 👑", callback_data="style_royal_purple"),
             InlineKeyboardButton("Cherry Blossom 🌸", callback_data="style_cherry_blossom")],
            [InlineKeyboardButton("Midnight Gold ✨", callback_data="style_midnight_gold"),
             InlineKeyboardButton("Retro Neon ⚡", callback_data="style_retro_neon")],
            [InlineKeyboardButton("Nordic Slate 🏔️", callback_data="style_nordic_slate"),
             InlineKeyboardButton("Vintage Sepia 📜", callback_data="style_vintage_sepia")],
            [InlineKeyboardButton("Cyberpunk 🚀", callback_data="style_cyberpunk"),
             InlineKeyboardButton("Coffee & Cream ☕", callback_data="style_coffee_cream")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Bosh menyuni tiklab qo'yamiz inline tugmalardan oldin
        await update.message.reply_text(
            f"📌 Taqdimot mavzusi: *\"{topic}\"*\n"
            f"👤 Muallif: *\"{author}\"*\n\n"
            "Endi quyidagi dizayn shablonlaridan birini tanlang: 👇",
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
        await update.message.reply_text(
            "Dizayn shablonini tanlang:",
            reply_markup=reply_markup
        )
        return
        
    action_type = "TUGMA" if text in menu_buttons else "MATN"
    log_id = log_action(user, action_type, text)

    if text == "📅 Bugungi Imtihon":
        await cmd_bugungi_imtihon(update, context)
    elif text == "⏩ Ertangi Imtihon":
        await cmd_ertangi_imtihon(update, context)
    elif text == "📋 To'liq ro'yxat":
        await cmd_imtihon(update, context)
    elif text == "📝 Prezentatsiya":
        user_states[user_id] = {"state": STATE_AWAITING_AUTHOR}
        await update.message.reply_text(
            "📝 *Yangi taqdimot yaratish*\n\n"
            "Taqdimot slaydlarida muallif sifatida ko'rsatiladigan Ism va Familiyangizni kiriting:\n\n"
            "_(Telegramdagi ismingizni ishlatish uchun quyidagi tugmani bosing)_ 👇",
            parse_mode="Markdown",
            reply_markup=author_keyboard()
        )
    elif text == "ℹ️ Yordam":
        await cmd_yordam(update, context)
    else:
        await handle_ai_chat(update, context, log_id)

async def handle_ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE, log_id: int = None):
    text = update.message.text
    user_id = str(update.effective_user.id)
    await process_ai_chat(update, context, user_id, text, log_id)

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if not groq_client:
        await update.message.reply_text("Kechirasiz, sun'iy intellekt hozircha ulanmagan.", reply_markup=main_menu_keyboard())
        return

    # Rate limit check for voice as well
    now = datetime.now(TZ)
    if user_id not in user_rate_limits:
        user_rate_limits[user_id] = []
    user_rate_limits[user_id] = [t for t in user_rate_limits[user_id] if (now - t).total_seconds() < 60]
    if len(user_rate_limits[user_id]) >= 5:
        await update.message.reply_text("⏳ Juda tez-tez yozyapsiz. Iltimos, 1 daqiqa kutib turing.", reply_markup=main_menu_keyboard())
        return

    msg = await update.message.reply_text("🎙 Ovozli xabar qabul qilindi, tushunishga harakat qilyapman...")
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action='typing')
    
    try:
        voice_file = await update.message.voice.get_file()
        file_bytes = await voice_file.download_as_bytearray()
        
        transcription = groq_client.audio.transcriptions.create(
            file=("voice.ogg", bytes(file_bytes)),
            model="whisper-large-v3",
            language="uz"
        )
        user_text = transcription.text
        
        if not user_text.strip():
            await msg.edit_text("Ovozli xabaringizda so'zlar aniqlanmadi. Iltimos, qaytadan yuboring.")
            return
            
        await msg.edit_text(f"🗣 Siz dedingiz: _{user_text}_\n\n🤖 O'ylayapman...", parse_mode="Markdown")
        
        # Log action manually since it's not a button or plain text
        log_id = log_action(update.effective_user, "VOICE", user_text)
        
        # Use common logic
        await process_ai_chat(update, context, user_id, user_text, log_id)
        
    except Exception as e:
        logger.error(f"Ovozli xabarni ishlashda xatolik: {e}")
        await msg.edit_text("Kechirasiz, ovozli xabarni ishlashda xatolik yuz berdi. Iltimos, matn orqali yozing.")

async def process_ai_chat(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, text: str, log_id: int = None):
    if not groq_client:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Kechirasiz, sun'iy intellekt hozircha ulanmagan.", reply_markup=main_menu_keyboard())
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
        "Sen talabalarning eng yaxshi do'sti va aqlli yordamchisisan. Sening isming 'Dars Jadvali Bot'. "
        "Sen har qanday mavzuda bemalol suhbatlashasan — darslar, hayot, hazillar, maslahatlar, fan, texnologiya, har narsa. "
        "Hech qachon 'men faqat jadval haqida javob beraman' dema. Sen HAMMA narsaga javob bera olasan. "
        "O'zbek tilida samimiy, qisqa va do'stona gapir. Javobni 2-3 jumla bilan ber, kerakdan ortiq cho'zma.\n\n"
        f"Hozirgi vaqt: {now_str}.\n"
        "Qo'shimcha bilim: Sen 3-kurs Finance (FINP-S-1323U) guruhining botisan. "
        "Agar talaba dars, jadval, o'qituvchi yoki xona haqida so'rasa, quyidagi jadvaldan to'g'ri javob ber:\n"
        f"{schedule_text}\n\n"
        "SEN QILA OLMAYDIGAN NARSALAR (bularni va'da qilma, halol ayt):\n"
        "- Sen eslatma (reminder) qo'ya OLMAYSAN. Kelajakda xabar yubora OLMAYSAN.\n"
        "- Sen fayl, rasm, audio yubora OLMAYSAN.\n"
        "- Sen internetga kira OLMAYSAN, qidiruv qila OLMAYSAN.\n"
        "- Sen boshqa odamlarga xabar yubora OLMAYSAN.\n"
        "Agar talaba shu narsalarni so'rasa, HALOL javob ber: 'Kechirasiz, men buni qila olmayman' de va sababini tushuntir.\n\n"
        "QOIDALAR: Javobda yulduzcha (*, **), tire (-), raqamlangan ro'yxat ishlatma. Faqat oddiy matn yoz."
    )
    
    if EXAM_QUESTIONS_TEXT:
        system_prompt += (
            "\n\nMUHIM: Quyida oraliq/yakuniy imtihon savollari va ularning aniq TO'G'RI javoblari keltirilgan. "
            "Agar foydalanuvchi imtihon savolidan parcha yo'llasa yoki imtihon haqida so'rasa, faqatgina quyidagi bazadan to'g'ri javobni yoz va tushuntirib ber.\n\n"
            f"{EXAM_QUESTIONS_TEXT}\n"
        )
        
    try:
        # Suhbat tarixini olish
        if user_id not in chat_history:
            chat_history[user_id] = []
        
        messages = [{"role": "system", "content": system_prompt}]
        # Oxirgi 50 ta xabarni kontekstga qo'shish (token tejash uchun)
        messages.extend(chat_history[user_id][-50:])
        messages.append({"role": "user", "content": text})
        
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=0.7,
            max_tokens=1024
        )
        ai_text = response.choices[0].message.content
        
        # Xotirada saqlash
        chat_history[user_id].append({"role": "user", "content": text})
        chat_history[user_id].append({"role": "assistant", "content": ai_text})
        
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
        await context.bot.send_message(chat_id=update.effective_chat.id, text=err_text, reply_markup=main_menu_keyboard())

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
        start_date = TZ.localize(datetime(2026, 6, 15))
        if now < start_date:
            msg = "⏳ *Darslar 15-iyundan boshlanadi!*"
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
        [InlineKeyboardButton("15.06 - Dushanba", callback_data="day_15.06.2026"),
         InlineKeyboardButton("16.06 - Seshanba", callback_data="day_16.06.2026")],
        [InlineKeyboardButton("17.06 - Chorshanba", callback_data="day_17.06.2026"),
         InlineKeyboardButton("18.06 - Payshanba", callback_data="day_18.06.2026")],
        [InlineKeyboardButton("19.06 - Juma", callback_data="day_19.06.2026"),
         InlineKeyboardButton("20.06 - Shanba", callback_data="day_20.06.2026")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("📋 *Qaysi kunning jadvalini ko'rmoqchisiz?*", parse_mode="Markdown", reply_markup=reply_markup)

async def cmd_jadval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "📋 *To'liq dars jadvali (15.06-20.06):*\n" + format_schedule_by_date(SCHEDULE)
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

async def cmd_bugungi_imtihon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(TZ)
    today_str = now.strftime("%d.%m.%Y")
    day_names = {0: "Dushanba", 1: "Seshanba", 2: "Chorshanba", 3: "Payshanba", 4: "Juma", 5: "Shanba", 6: "Yakshanba"}
    today_day_name = day_names[now.weekday()]
    
    exams_today = [e for e in EXAMS if e[0] == today_str]
    
    if not exams_today:
        upcoming = sorted(
            [(get_lesson_datetime(e[0], e[1], e[2]), e) for e in EXAMS
             if get_lesson_datetime(e[0], e[1], e[2]) > now],
            key=lambda x: x[0]
        )
        if upcoming:
            next_dt, exam = upcoming[0]
            delta = next_dt - now
            days = delta.days
            hours = int((delta.total_seconds() % 86400) // 3600)
            minutes = int((delta.total_seconds() % 3600) // 60)
            
            time_left = ""
            if days > 0:
                time_left += f"{days} kun "
            if hours > 0:
                time_left += f"{hours} soat "
            time_left += f"{minutes} daqiqa"
            
            date_str, hour, minute, subject, room = exam
            next_day_name = day_names[datetime.strptime(date_str, "%d.%m.%Y").weekday()]
            
            await update.message.reply_text(
                f"📭 *{today_str} ({today_day_name})* kuni imtihon yo'q.\n\n"
                f"⏰ *Keyingi imtihon:*\n"
                f"📅 {date_str} ({next_day_name}) | 🕐 {hour:02d}:{minute:02d} ({time_left.strip()} qoldi)\n"
                f"📚 {subject} | 🚪 Xona: {room}",
                parse_mode="Markdown", reply_markup=main_menu_keyboard()
            )
        else:
            await update.message.reply_text(f"📭 *{today_str} ({today_day_name})* kuni imtihon yo'q. Kelgusi imtihonlar topilmadi.", parse_mode="Markdown", reply_markup=main_menu_keyboard())
        return
        
    text = f"📅 *Bugungi Imtihonlar, {today_str} ({today_day_name}):*\n"
    for date, hour, minute, subject, room in exams_today:
        start_time = f"{hour:02d}:{minute:02d}"
        end_dt = datetime.strptime(start_time, "%H:%M") + timedelta(minutes=20)
        end_time = end_dt.strftime("%H:%M")
        text += f"\n🕐 {start_time} - {end_time}\n📚 {subject} | 🚪 Xona: {room}\n"
        
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())

async def cmd_ertangi_imtihon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now(TZ)
    tomorrow = now + timedelta(days=1)
    tomorrow_str = tomorrow.strftime("%d.%m.%Y")
    day_names = {0: "Dushanba", 1: "Seshanba", 2: "Chorshanba", 3: "Payshanba", 4: "Juma", 5: "Shanba", 6: "Yakshanba"}
    tomorrow_day_name = day_names[tomorrow.weekday()]
    
    exams_tomorrow = [e for e in EXAMS if e[0] == tomorrow_str]
    
    if not exams_tomorrow:
        await update.message.reply_text(f"📭 *{tomorrow_str} ({tomorrow_day_name})* kuni imtihon yo'q.", parse_mode="Markdown", reply_markup=main_menu_keyboard())
        return
        
    text = f"⏩ *Ertangi Imtihonlar, {tomorrow_str} ({tomorrow_day_name}):*\n"
    for date, hour, minute, subject, room in exams_tomorrow:
        start_time = f"{hour:02d}:{minute:02d}"
        end_dt = datetime.strptime(start_time, "%H:%M") + timedelta(minutes=20)
        end_time = end_dt.strftime("%H:%M")
        text += f"\n🕐 {start_time} - {end_time}\n📚 {subject} | 🚪 Xona: {room}\n"
        
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())

async def cmd_imtihon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🎓 *To'liq Imtihonlar jadvali (FIN-S-1323U):*\n"
    day_names = {0: "Dushanba", 1: "Seshanba", 2: "Chorshanba", 3: "Payshanba", 4: "Juma", 5: "Shanba", 6: "Yakshanba"}
    for date, hour, minute, subject, room in EXAMS:
        start_time = f"{hour:02d}:{minute:02d}"
        end_dt = datetime.strptime(start_time, "%H:%M") + timedelta(minutes=20)
        end_time = end_dt.strftime("%H:%M")
        
        day_idx = datetime.strptime(date, "%d.%m.%Y").weekday()
        day_name = day_names[day_idx]
        
        text += f"\n📅 *{date} ({day_name})* | 🕐 {start_time} - {end_time}\n"
        text += f"📚 {subject}\n"
        text += f"🚪 Xona: *{room}*\n"
        
    from telegram import WebAppInfo
    reply_markup = None
    if WEBAPP_URL:
        # Agar WEBAPP_URL kiritilgan bo'lsa, inline tugma ham qo'shamiz
        # Web app URL oxirida '/' qo'yilmasa Telegram qabul qilmadi deb xato bermasligi uchun
        ik = InlineKeyboardMarkup([[InlineKeyboardButton("📱 Imtihon Tayyorgarlik (Web App)", web_app=WebAppInfo(url=f"{WEBAPP_URL}/"))]])
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())
        await update.message.reply_text("👇 Test ishlash va savol-javoblarni ko'rish uchun quyidagi Web App ni oching:", reply_markup=ik)
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu_keyboard())

async def cmd_yordam(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "ℹ️ *Yordam*\n\n"
        "🎓 Bu bot *3-kurs Finance (FINP-S-1323U)* talabalari uchun mo'ljallangan (15-20 Iyun darslari).\n\n"
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

def get_samarkand_weather(date_str):
    from datetime import datetime
    try:
        dt = datetime.strptime(date_str, "%d.%m.%Y")
        formatted_date = dt.strftime("%Y-%m-%d")
        url = f"https://api.open-meteo.com/v1/forecast?latitude=39.6525&longitude=66.9558&daily=temperature_2m_max,temperature_2m_min&timezone=Asia/Tashkent&start_date={formatted_date}&end_date={formatted_date}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
        if "daily" in data:
            temp_max = data["daily"]["temperature_2m_max"][0]
            temp_min = data["daily"]["temperature_2m_min"][0]
            return temp_max, temp_min
    except Exception as e:
        logger.error(f"Weather API error: {e}")
    return None

async def cmd_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("15.06 - Dushanba", callback_data="weather_15.06.2026"),
         InlineKeyboardButton("16.06 - Seshanba", callback_data="weather_16.06.2026")],
        [InlineKeyboardButton("17.06 - Chorshanba", callback_data="weather_17.06.2026"),
         InlineKeyboardButton("18.06 - Payshanba", callback_data="weather_18.06.2026")],
        [InlineKeyboardButton("19.06 - Juma", callback_data="weather_19.06.2026"),
         InlineKeyboardButton("20.06 - Shanba", callback_data="weather_20.06.2026")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "🌤 *Samarqand shahri uchun ob-havo ma'lumoti:*\n\nIltimos, kerakli sanani tanlang: 👇",
        parse_mode="Markdown",
        reply_markup=reply_markup
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

# ===== PROCESS PRESENTATION (BACKGROUND TASK) =====

async def process_presentation(update, context, user_id, topic, style_name, query, author):
    # Edit the inline button message to show loading status
    status_msg = await query.edit_message_text(
        f"🤖 *\"{topic}\"* mavzusida taqdimot tayyorlash boshlandi...\n\n"
        f"👤 Muallif: *{author}*\n"
        f"🎨 Shablon: *{style_name.replace('_', ' ').title()}*\n"
        "⏳ Groq AI kontent yaratmoqda (bu 15-30 soniya vaqt olishi mumkin)...",
        parse_mode="Markdown"
    )
    
    try:
        # Run content generation in executor
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(
            None, 
            lambda: generate_presentation_content(topic, GROQ_API_KEY)
        )
        
        await status_msg.edit_text(
            f"🤖 *\"{topic}\"* mavzusida taqdimot...\n\n"
            f"👤 Muallif: *{author}*\n"
            f"🎨 Shablon: *{style_name.replace('_', ' ').title()}*\n"
            "📄 PDF slaydlar yig'ilmoqda...",
            parse_mode="Markdown"
        )
        
        # Create temp file
        temp_dir = tempfile.gettempdir()
        output_filename = f"prezentatsiya_{user_id}_{int(datetime.now().timestamp())}.pdf"
        output_path = os.path.join(temp_dir, output_filename)
        
        # Run PDF creation in executor
        await loop.run_in_executor(
            None,
            lambda: create_presentation_pdf(data, style_name, output_path, author)
        )
        
        await status_msg.edit_text("📤 Taqdimot tayyor! Fayl yuborilmoqda...")
        
        # Send PDF
        with open(output_path, 'rb') as f:
            sent_doc = await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=f,
                filename=f"{topic[:30].replace(' ', '_')}_taqdimot.pdf",
                caption=f"✅ *\"{topic}\"* mavzusidagi taqdimot tayyor bo'ldi!\n\n"
                        f"📊 Slaydlar soni: 10 ta\n"
                        f"👤 Muallif: {author}\n"
                        f"🎨 Tanlangan shablon: {style_name.replace('_', ' ').title()}",
                parse_mode="Markdown",
                reply_markup=main_menu_keyboard()
            )
        
        # Save presentation record to DB
        try:
            file_id = sent_doc.document.file_id if sent_doc and sent_doc.document else None
            pres_user = query.from_user
            pres_username = pres_user.first_name or "UNKNOWN"
            if pres_user.last_name:
                pres_username += f" {pres_user.last_name}"
            created_at = datetime.now(TZ).strftime("%d.%m.%Y %H:%M:%S")
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT INTO presentations (user_id, username, topic, style_name, author_name, file_id, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (user_id, pres_username, topic, style_name, author, file_id, 'success', created_at)
                )
                conn.commit()
        except Exception as db_err:
            logger.error(f"Presentation DB insert error: {db_err}")
            
        # Delete temp file
        if os.path.exists(output_path):
            os.remove(output_path)
            
        await status_msg.delete()
        
    except Exception as e:
        logger.error(f"Presentation generation error: {e}")
        error_text = f"❌ Kechirasiz, *\"{topic}\"* mavzusida taqdimot tayyorlashda xatolik yuz berdi."
        if "GROQ_API_KEY" in str(e) or not GROQ_API_KEY:
            error_text += "\n⚠️ Botda Groq API kaliti o'rnatilmagan yoki noto'g'ri."
        await status_msg.edit_text(error_text, parse_mode="Markdown", reply_markup=main_menu_keyboard())


# ===== CALLBACK (inline tugmalar) =====

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("style_"):
        user_id = str(update.effective_user.id)
        style_name = query.data.replace("style_", "")
        
        user_data = user_states.get(user_id)
        if not user_data or user_data.get("state") != STATE_AWAITING_STYLE:
            await query.message.reply_text("⚠️ Prezentatsiya seansi muddati tugagan. Iltimos, bosh menyudan qayta urinib ko'ring.", reply_markup=main_menu_keyboard())
            return
            
        topic = user_data["topic"]
        author = user_data["author"]
        # Clear user state immediately
        del user_states[user_id]
        
        # Process presentation in a background task
        asyncio.create_task(process_presentation(update, context, user_id, topic, style_name, query, author))
        return
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
            [InlineKeyboardButton("15.06 - Dushanba", callback_data="day_15.06.2026"),
             InlineKeyboardButton("16.06 - Seshanba", callback_data="day_16.06.2026")],
            [InlineKeyboardButton("17.06 - Chorshanba", callback_data="day_17.06.2026"),
             InlineKeyboardButton("18.06 - Payshanba", callback_data="day_18.06.2026")],
            [InlineKeyboardButton("19.06 - Juma", callback_data="day_19.06.2026"),
             InlineKeyboardButton("20.06 - Shanba", callback_data="day_20.06.2026")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("📋 *Qaysi kunning jadvalini ko'rmoqchisiz?*", parse_mode="Markdown", reply_markup=reply_markup)
    elif query.data.startswith("weather_"):
        date_str = query.data.replace("weather_", "")
        
        # Loading message representation
        await query.edit_message_text("⏳ Ob-havo ma'lumoti yuklanmoqda...")
        
        weather_data = get_samarkand_weather(date_str)
        if weather_data:
            temp_max, temp_min = weather_data
            text = (
                f"🌤 *Samarqand ob-havosi ({date_str}):*\n\n"
                f"☀️ Kunduzi: *{temp_max}°C*\n"
                f"🌙 Kechasi: *{temp_min}°C*"
            )
        else:
            text = f"❌ Kechirasiz, *{date_str}* sanasi uchun ob-havo ma'lumotlarini olib bo'lmadi."
            
        back_kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Boshqa sanani tanlash", callback_data="weather_back_to_week")]])
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=back_kb)
    elif query.data == "weather_back_to_week":
        keyboard = [
            [InlineKeyboardButton("15.06 - Dushanba", callback_data="weather_15.06.2026"),
             InlineKeyboardButton("16.06 - Seshanba", callback_data="weather_16.06.2026")],
            [InlineKeyboardButton("17.06 - Chorshanba", callback_data="weather_17.06.2026"),
             InlineKeyboardButton("18.06 - Payshanba", callback_data="weather_18.06.2026")],
            [InlineKeyboardButton("19.06 - Juma", callback_data="weather_19.06.2026"),
             InlineKeyboardButton("20.06 - Shanba", callback_data="weather_20.06.2026")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🌤 *Samarqand shahri uchun ob-havo ma'lumoti:*\n\nIltimos, kerakli sanani tanlang: 👇",
            parse_mode="Markdown",
            reply_markup=reply_markup
        )

# ===== ESLATMALAR =====

async def send_pre_reminder(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    exam = job_data["exam"]
    _, hour, minute, subject, room = exam

    text = (
        f"🔔 *Eslatma!*\n\n"
        f"⏰ *Imtihon boshlanishiga 20 daqiqa qoldi*\n\n"
        f"🕐 {hour:02d}:{minute:02d}\n"
        f"📚 *{subject}*\n"
        f"🚪 Xona: *{room}*"
    )
    await send_to_all_users(context.bot, text)

async def send_start_reminder(context: ContextTypes.DEFAULT_TYPE):
    job_data = context.job.data
    exam = job_data["exam"]
    _, hour, minute, subject, room = exam
    
    end_dt = datetime.strptime(f"{hour:02d}:{minute:02d}", "%H:%M") + timedelta(minutes=20)

    text = (
        f"🟢 *Imtihon boshlandi!*\n\n"
        f"📚 *{subject}*\n"
        f"🚪 Xona: *{room}*\n"
        f"🕐 Vaqt: {hour:02d}:{minute:02d} dan {end_dt.strftime('%H:%M')} gacha"
    )
    await send_to_all_users(context.bot, text)

async def send_daily_schedule(context: ContextTypes.DEFAULT_TYPE):
    logger.info("Yuborilmoqda: Kundalik darslar jadvali (9:00)")
    lessons = get_today_schedule()
    now = datetime.now(TZ)
    today = now.strftime("%d.%m.%Y")
    
    if not lessons:
        start_date = TZ.localize(datetime(2026, 6, 15))
        if now < start_date:
            text = "⏳ *Darslar 15-iyundan boshlanadi!*"
        else:
            text = f"📭 *{today}* kuni dars yo'q."
    else:
        text = f"📋 *Bugungi darslar ({today}):*\n" + format_schedule_by_date(lessons)
        
    await send_to_all_users(context.bot, text)

async def send_to_all_users(bot, text):
    """Barcha ro'yxatdan o'tgan foydalanuvchilarga xabar yuborish"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM users")
            users = cursor.fetchall()
        
        # Hamma user_id larni to'plamga yig'amiz
        recipient_ids = set(str(user_id) for (user_id,) in users)
        
        # Settings dagi CHAT_ID ni ham qo'shamiz (bu guruh yoki asosiy chat bo'lishi mumkin)
        group_chat_id = load_chat_id()
        if group_chat_id:
            recipient_ids.add(str(group_chat_id))
        
        for chat_id in recipient_ids:
            try:
                await bot.send_message(chat_id=chat_id, text=text, parse_mode="Markdown")
            except Exception as e:
                logger.error(f"Eslatma yuborishda xatolik (ID: {chat_id}): {e}")
    except Exception as e:
        logger.error(f"send_to_all_users xatoligi: {e}")

def schedule_reminders(app, chat_id=None):
    now = datetime.now(TZ)
    count = 0
    logger.info("--- ESLATMALAR TEKSHIRUVI ---")
    logger.info(f"Hozirgi O'zbekiston vaqti (UTC+5): {now.strftime('%d.%m.%Y %H:%M:%S')}")
    logger.info(f"Chat ID: {chat_id}")
    logger.info(f"Imtihonlar soni: {len(EXAMS)}")
    
    for exam in EXAMS:
        exam_dt = get_lesson_datetime(exam[0], exam[1], exam[2])
        
        pre_dt = exam_dt - timedelta(minutes=20)
        start_dt = exam_dt

        # 1. 20 minut oldin eslatma
        if pre_dt > now:
            job_name = f"pre_exam_{exam[0]}_{exam[1]}_{exam[2]}"
            existing = app.job_queue.get_jobs_by_name(job_name)
            if not existing:
                delay = (pre_dt - now).total_seconds()
                app.job_queue.run_once(send_pre_reminder, when=delay, data={"chat_id": chat_id, "exam": exam}, name=job_name)
                logger.info(f"  ✅ ESLATMA rejalashtirildi: {exam[3]} — {pre_dt.strftime('%d.%m.%Y %H:%M')} ({int(delay)}s keyin)")
                count += 1
            else:
                logger.info(f"  ⏩ Allaqachon mavjud: {job_name}")
        else:
            logger.info(f"  ⏩ O'tib ketgan: {exam[3]} — {pre_dt.strftime('%d.%m.%Y %H:%M')}")

        # 2. Imtihon boshlandi
        if start_dt > now:
            job_name = f"start_exam_{exam[0]}_{exam[1]}_{exam[2]}"
            if not app.job_queue.get_jobs_by_name(job_name):
                delay = (start_dt - now).total_seconds()
                app.job_queue.run_once(send_start_reminder, when=delay, data={"chat_id": chat_id, "exam": exam}, name=job_name)
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
                <a href="?tab=presentations" class="tab {% if tab == 'presentations' %}active{% endif %}">📝 Prezentatsiyalar</a>
                <a href="?tab=users" class="tab {% if tab == 'users' %}active{% endif %}">👥 Foydalanuvchilar</a>
                <a href="?tab=logs" class="tab {% if tab == 'logs' %}active{% endif %}">📊 Harakatlar Tarixi</a>
                <a href="?tab=test_results" class="tab {% if tab == 'test_results' %}active{% endif %}">🏆 Test Natijalari</a>
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

            {% elif tab == 'presentations' %}
                <h2 style="margin-bottom: 1.5rem; font-weight: 600; text-align: center;">📝 Prezentatsiyalar Tarixi (Jami: <b style="color: white;">{{ presentations|length }}</b> ta)</h2>
                <div class="glass table-wrapper" style="margin-bottom: 5rem;">
                    {% if presentations %}
                    <table>
                        <thead>
                            <tr>
                                <th>#</th>
                                <th>Foydalanuvchi</th>
                                <th>Mavzu</th>
                                <th>Shablon</th>
                                <th>Muallif</th>
                                <th>Yuklab olish</th>
                                <th>Vaqti</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for p in presentations %}
                            <tr>
                                <td style="color: var(--text-muted);">{{ p[0] }}</td>
                                <td style="font-weight: 600;">{{ p[2] }}<br><span style="color: var(--text-muted); font-size: 0.8rem;">ID: {{ p[1] }}</span></td>
                                <td style="max-width: 250px; word-wrap: break-word; font-weight: 600; color: #60a5fa;">{{ p[3] }}</td>
                                <td><span style="background: rgba(167, 139, 250, 0.2); color: #a78bfa; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.8rem; font-weight: 600;">{{ p[4]|replace('_', ' ')|title }}</span></td>
                                <td>{{ p[5] }}</td>
                                <td>
                                    {% if p[6] %}
                                    <a href="/download/{{ p[0] }}" target="_blank" style="color: #10b981; text-decoration: none; font-weight: 600;">📥 Yuklab olish</a>
                                    {% else %}
                                    <span style="color: var(--text-muted);">—</span>
                                    {% endif %}
                                </td>
                                <td style="color: var(--text-muted); font-size: 0.9rem;">{{ p[8] }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                    {% else %}
                    <div class="empty">Hozircha prezentatsiya yaratilmagan</div>
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
                                <th>Telefon</th>
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
                                <td style="color: #10b981; font-weight: 600;">{{ u[4] or '-' }}</td>
                                <td style="color: var(--text-muted); font-size: 0.9rem;">{{ u[5] }}</td>
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
            {% elif tab == 'test_results' %}
                <div style="display: flex; justify-content: space-between; margin-bottom: 1rem; align-items: center;">
                    <span style="color: var(--text-muted);">Jami test yechganlar: <b style="color: white;">{{ test_results|length }}</b> ta</span>
                </div>
                <div class="glass table-wrapper">
                    {% if test_results %}
                    <table>
                        <thead>
                            <tr>
                                <th>#</th>
                                <th>Foydalanuvchi</th>
                                <th>Ball</th>
                                <th>To'g'ri</th>
                                <th>Xato</th>
                                <th>Sariq</th>
                                <th>Vaqti</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for r in test_results %}
                            <tr>
                                <td style="color: var(--text-muted);">{{ r[0] }}</td>
                                <td style="font-weight: 600;">{{ r[2] }} {{ r[3] or '' }}<br><span style="color: #3b82f6; font-size: 0.8rem;">{% if r[4] %}@{{ r[4] }}{% else %}{{ r[1] }}{% endif %}</span></td>
                                <td><span style="color:var(--green); font-weight:bold;">{{ r[5] }}</span></td>
                                <td><span style="color:var(--green);">{{ r[6] }}</span></td>
                                <td><span style="color:var(--red);">{{ r[7] }}</span></td>
                                <td><span style="color:var(--yellow);">{{ r[8] }}</span></td>
                                <td style="color: var(--text-muted); font-size: 0.9rem;">{{ r[9] }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                    {% else %}
                    <div class="empty">Hozircha test natijalari yo'q</div>
                    {% endif %}
                </div>
            {% endif %}
        {% endif %}
    </div>
</body>
</html>
"""

@app_web.route('/admin', methods=['GET', 'POST'])
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
    presentations = []
    test_results = []
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            if tab == 'logs':
                cursor.execute("SELECT id, user_id, username, action_type, content, timestamp, ai_response FROM logs ORDER BY id DESC LIMIT 500")
                logs = cursor.fetchall()
            elif tab == 'users':
                cursor.execute("SELECT user_id, first_name, last_name, username, phone_number, joined_at FROM users ORDER BY joined_at DESC")
                users = cursor.fetchall()
            elif tab == 'broadcast':
                cursor.execute("SELECT id, message, status, success_count, failed_count, created_at FROM broadcasts ORDER BY id DESC LIMIT 50")
                broadcasts = cursor.fetchall()
            elif tab == 'presentations':
                cursor.execute("SELECT id, user_id, username, topic, style_name, author_name, file_id, status, created_at FROM presentations ORDER BY id DESC LIMIT 100")
                presentations = cursor.fetchall()
            elif tab == 'test_results':
                cursor.execute("SELECT id, user_id, first_name, last_name, username, score, correct_count, wrong_count, skipped_count, created_at FROM test_results ORDER BY id DESC LIMIT 500")
                test_results = cursor.fetchall()
    except Exception as e:
        logger.error(f"Web DB error: {e}")
        
    msg_success = session.pop('msg_success', False)
    return render_template_string(HTML_TEMPLATE, require_login=False, tab=tab, logs=logs, users=users, broadcasts=broadcasts, presentations=presentations, test_results=test_results, msg_success=msg_success)

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

@app_web.route('/download/<int:pres_id>')
def download_presentation(pres_id):
    if not session.get('logged_in'):
        return redirect(url_for('dashboard'))
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT file_id, topic FROM presentations WHERE id = ?", (pres_id,))
            row = cursor.fetchone()
        if not row or not row[0]:
            return "Fayl topilmadi", 404
        file_id = row[0]
        topic = row[1] or "prezentatsiya"
        # Get file path from Telegram
        get_file_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
        with urllib.request.urlopen(get_file_url) as resp:
            file_info = json.loads(resp.read().decode())
        if not file_info.get("ok"):
            return "Telegram API xatosi", 500
        file_path = file_info["result"]["file_path"]
        # Download file from Telegram
        download_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        with urllib.request.urlopen(download_url) as resp:
            file_data = resp.read()
        filename = f"{topic[:30].replace(' ', '_')}_taqdimot.pdf"
        return Response(
            file_data,
            mimetype='application/pdf',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
    except Exception as e:
        logger.error(f"Download error: {e}")
        return "Yuklab olishda xatolik", 500

EXAM_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Imtihonga Tayyorgarlik</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-color: #1a2232;
            --text-color: #ffffff;
            --button-color: #3b82f6;
            --button-text-color: #ffffff;
            --card-bg: #222b3c;
            --border-color: #384256;
            --green: #20c978;
            --red: #f15249;
            --yellow: #f59e0b;
            --gray: #6b7280;
        }
        * { box-sizing: border-box; font-family: 'Inter', sans-serif; margin: 0; padding: 0; }
        body { background-color: var(--bg-color) !important; color: var(--text-color) !important; padding: 16px; overflow-x: hidden; }
        .glass { background: var(--card-bg); backdrop-filter: blur(10px); border: 1px solid var(--border-color); border-radius: 16px; padding: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        
        .screen { display: none; animation: fadeIn 0.3s ease-in-out; }
        .screen.active { display: flex; flex-direction: column; gap: 16px; }
        @keyframes fadeIn { from { opacity: 0; transform: scale(0.95); } to { opacity: 1; transform: scale(1); } }
        
        h1 { font-size: 24px; text-align: center; margin-bottom: 24px; font-weight: 700; }
        h2 { font-size: 20px; font-weight: 600; margin-bottom: 16px; }
        
        /* Home Screen */
        .btn-large { background: var(--button-color); color: var(--button-text-color); border: none; padding: 20px; border-radius: 16px; font-size: 18px; font-weight: 600; display: flex; align-items: center; justify-content: center; gap: 12px; cursor: pointer; transition: transform 0.1s; width: 100%; box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3); }
        .btn-large:active { transform: scale(0.97); }
        .btn-secondary { background: var(--card-bg); color: var(--text-color); border: 1px solid var(--border-color); }
        
        /* Study Mode */
        .qa-card { margin-bottom: 16px; }
        .q-text { font-weight: 600; margin-bottom: 8px; font-size: 15px; }
        .a-text { color: var(--green); font-size: 14px; }
        
        /* Test Mode */
        .top-bar { display: flex; justify-content: space-between; align-items: center; background: var(--card-bg); padding: 12px 16px; border-radius: 12px; border: 1px solid var(--border-color); }
        .timer { font-size: 18px; font-weight: 700; color: var(--button-color); }
        .score { font-size: 16px; font-weight: 600; }
        
        .navigator { display: flex; overflow-x: auto; gap: 8px; padding-bottom: 8px; scroll-behavior: smooth; }
        .navigator::-webkit-scrollbar { height: 4px; }
        .navigator::-webkit-scrollbar-thumb { background: var(--border-color); border-radius: 4px; }
        .nav-dot { width: 32px; height: 32px; flex-shrink: 0; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 14px; font-weight: 600; background: var(--gray); color: white; transition: all 0.3s; }
        .nav-dot.green { background: var(--green); }
        .nav-dot.red { background: var(--red); }
        .nav-dot.yellow { background: var(--yellow); }
        .nav-dot.active-dot { box-shadow: 0 0 0 3px var(--bg-color), 0 0 0 5px var(--button-color); transform: scale(1.1); }
        
        .option-btn { background: var(--card-bg); border: 1px solid var(--border-color); color: var(--text-color); padding: 12px 14px; border-radius: 8px; font-size: 14px; text-align: left; transition: all 0.2s; width: 100%; cursor: pointer; margin-bottom: 8px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); line-height: 1.4; }
        .option-btn:active { transform: scale(0.98); }
        .option-btn.correct { background: var(--green); color: white; border-color: var(--green); }
        .option-btn.wrong { background: var(--red); color: white; border-color: var(--red); }
        
        .skip-btn { background: var(--yellow); color: #000; font-weight: 600; padding: 12px 20px; font-size: 14px; border-radius: 8px; width: auto; display: inline-block; }
        .next-btn { background: var(--button-color); color: var(--button-text-color); font-weight: 600; padding: 12px 20px; font-size: 14px; border-radius: 8px; width: auto; display: none; border: none; cursor: pointer; }
        
        #resultsScreen h1 { font-size: 32px; margin-bottom: 8px; }
        .stat-row { display: flex; justify-content: space-between; font-size: 18px; margin-bottom: 12px; padding-bottom: 12px; border-bottom: 1px solid var(--border-color); }
        
        .bottom-nav { position: fixed; bottom: 0; left: 0; right: 0; height: 65px; background: var(--card-bg); backdrop-filter: blur(10px); border-top: 1px solid var(--border-color); display: flex; justify-content: space-around; align-items: center; z-index: 1000; padding-bottom: env(safe-area-inset-bottom); }
        .nav-item { display: flex; flex-direction: column; align-items: center; font-size: 12px; font-weight: 600; color: var(--text-color); cursor: pointer; opacity: 0.6; transition: 0.2s; }
        .nav-item.active { opacity: 1; color: var(--button-color); }
        .nav-item i { font-size: 20px; margin-bottom: 4px; font-style: normal; }
        body { padding-bottom: 80px; }
    </style>
</head>
<body>

    <div id="subjectScreen" class="screen active">
        <h1>Fanni tanlang</h1>
        <button class="btn-large" onclick="selectSubject('ECONOMIC ANALYSIS')">📊 ECONOMIC ANALYSIS</button>
    </div>

    <div id="homeScreen" class="screen">
        <h1>Imtihonga Tayyorgarlik</h1>
        <button class="btn-large" onclick="startStudyMode()">📚 Savol-Javoblar (O'qish)</button>
        <button class="btn-large" style="background: linear-gradient(135deg, #10b981, #059669);" onclick="startTestMode()">📝 Test Topshirish</button>
    </div>

    <div id="studyScreen" class="screen">
        <button class="btn-large btn-secondary" style="padding: 12px; margin-bottom: 16px;" onclick="goHome()">🔙 Asosiy Menyu</button>
        <h2>Barcha Savollar</h2>
        <input type="text" id="studySearch" placeholder="🔍 Savollardan qidirish..." onkeyup="filterStudyQuestions()" style="width: 100%; padding: 12px; margin-bottom: 16px; border-radius: 12px; border: 1px solid var(--border-color); background: var(--bg-color); color: var(--text-color); font-size: 16px;">
        <div id="studyList"></div>
    </div>

    <div id="testScreen" class="screen">
        <div class="top-bar">
            <div class="timer" id="timerDisplay">20:00</div>
            <div class="score">Ball: <span id="scoreDisplay">0</span></div>
        </div>
        
        <div class="navigator" id="navigatorContainer"></div>
        
        <div class="glass" id="questionCard">
            <div class="q-text" id="testQuestionText">Savol matni...</div>
            <div id="optionsContainer" style="margin-top: 20px;"></div>
        </div>
        <div style="display: flex; justify-content: center; align-items: center; gap: 16px; margin-top: 16px;">
            <button class="btn-large skip-btn" id="skipBtn" onclick="skipQuestion()">⏭ O'tkazib yuborish</button>
            <button class="btn-large next-btn" id="nextBtn" onclick="goToNextAfterAnswer()">Keyingi savol ➡</button>
        </div>
    </div>

    <div id="resultsScreen" class="screen">
        <div class="glass" style="text-align: center;">
            <div style="font-size: 48px; margin-bottom: 16px;">🏆</div>
            <h2>Test Yakunlandi!</h2>
            <div class="stat-row"><span>To'plangan ball:</span> <strong id="resScore">0</strong></div>
            <div class="stat-row"><span>To'g'ri javoblar:</span> <strong id="resCorrect" style="color: var(--green);">0</strong></div>
            <div class="stat-row"><span>Xato javoblar:</span> <strong id="resWrong" style="color: var(--red);">0</strong></div>
            <div class="stat-row" style="border:none;"><span>O'tkazib yuborilgan:</span> <strong id="resSkipped" style="color: var(--yellow);">0</strong></div>
            <button class="btn-large" style="margin-top: 24px;" onclick="showAllResults()">📊 Barcha natijalarni ko'rish</button>
        </div>
    </div>

    <div id="allResultsScreen" class="screen">
        <h2 style="margin-bottom: 16px; text-align: center;">🏆 Reyting</h2>
        
        <div id="myResultContainer" style="margin-bottom: 24px;"></div>
        
        <h3 style="margin-bottom: 12px; font-size: 16px; color: var(--text-color); opacity: 0.8;">Boshqalar natijalari</h3>
        <div id="otherResultsContainer"></div>
    </div>

    <div class="bottom-nav" id="bottomNav" style="display: none;">
        <div class="nav-item active" onclick="goHome()" id="nav-home">
            <i>🏠</i><span>Asosiy sahifa</span>
        </div>
        <div class="nav-item" onclick="startStudyMode()" id="nav-study">
            <i>📚</i><span>Savol-javob</span>
        </div>
        <div class="nav-item" onclick="startTestMode()" id="nav-test">
            <i>📝</i><span>Real test</span>
        </div>
        <div class="nav-item" onclick="showAllResults()" id="nav-results">
            <i>📊</i><span>Natijalar</span>
        </div>
    </div>

    <script>
        const tg = window.Telegram.WebApp;
        tg.expand();
        
        let allQuestions = [];
        let dbQuestions = [];
        let questions = [];
        let questionState = [];
        let currentQueue = [];
        let currentIndex = 0;
        let score = 0;
        let correctCount = 0;
        let wrongCount = 0;
        let skippedCount = 0;
        let timerInterval = null;
        let timeLeft = 1200; 

        function updateBottomNav(activeId) {
            document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
            if(activeId) document.getElementById(activeId).classList.add('active');
        }

        function showScreen(id) {
            document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
            document.getElementById(id).classList.add('active');
            if (id !== 'subjectScreen') {
                document.getElementById('bottomNav').style.display = 'flex';
            }
        }

        function selectSubject(subjectName) {
            // Fetch questions from API
            fetch('/api/questions')
                .then(res => res.json())
                .then(data => {
                    if(data[subjectName]) {
                        allQuestions = data[subjectName].map((q, idx) => ({
                            id: idx + 1,
                            text: q.text,
                            options: q.options,
                            correct: q.correct
                        }));
                        dbQuestions = allQuestions;
                        showScreen('homeScreen');
                        updateBottomNav('nav-home');
                    } else {
                        alert("Bu fan bo'yicha savollar topilmadi!");
                    }
                })
                .catch(err => {
                    console.error(err);
                    alert("Savollarni yuklashda xatolik yuz berdi!");
                });
        }

        function goHome() {
            clearInterval(timerInterval);
            showScreen('homeScreen');
            updateBottomNav('nav-home');
        }

        function showAllResults() {
            clearInterval(timerInterval);
            showScreen('allResultsScreen');
            updateBottomNav('nav-results');
            
            const myContainer = document.getElementById('myResultContainer');
            const otherContainer = document.getElementById('otherResultsContainer');
            
            myContainer.innerHTML = '<div style="text-align:center;">Yuklanmoqda...</div>';
            otherContainer.innerHTML = '';
            
            fetch('/api/results')
                .then(res => res.json())
                .then(data => {
                    myContainer.innerHTML = '';
                    otherContainer.innerHTML = '';
                    
                    if(data.error) {
                        myContainer.innerHTML = `<div style="color:red; text-align:center;">Xatolik: ${data.error}</div>`;
                        return;
                    }
                    
                    const currentUser = tg.initDataUnsafe?.user;
                    const myId = currentUser ? String(currentUser.id) : null;
                    
                    let rank = 1;
                    data.forEach(item => {
                        const isMe = String(item.user_id) === myId;
                        const name = (item.first_name + " " + item.last_name).trim() || item.username || "Anonim";
                        
                        const card = document.createElement('div');
                        card.className = 'glass';
                        card.style.marginBottom = '10px';
                        card.style.padding = '12px 16px';
                        card.style.display = 'flex';
                        card.style.justifyContent = 'space-between';
                        card.style.alignItems = 'center';
                        
                        if(isMe) {
                            card.style.background = 'rgba(16, 185, 129, 0.15)'; // Yashilroq fon
                            card.style.border = '1px solid rgba(16, 185, 129, 0.3)';
                        }
                        
                        card.innerHTML = `
                            <div style="display: flex; align-items: center; gap: 12px;">
                                <div style="font-weight: bold; width: 24px; color: var(--text-muted);">${rank}.</div>
                                <div>
                                    <div style="font-weight: 600; ${isMe ? 'color: var(--green);' : ''}">${name} ${isMe ? '(Siz)' : ''}</div>
                                    <div style="font-size: 12px; color: var(--text-muted);">To'g'ri javoblar: ${item.correct} ta</div>
                                </div>
                            </div>
                            <div style="font-weight: bold; font-size: 18px;">${item.score} <span style="font-size: 12px; font-weight: normal; color: var(--text-muted);">ball</span></div>
                        `;
                        
                        if(isMe) {
                            myContainer.appendChild(card);
                        } else {
                            otherContainer.appendChild(card);
                        }
                        rank++;
                    });
                    
                    if(myContainer.innerHTML === '') {
                        myContainer.innerHTML = '<div class="glass" style="text-align:center; color: var(--text-muted);">Siz hali test ishlamagansiz.</div>';
                    }
                    if(otherContainer.innerHTML === '') {
                        otherContainer.innerHTML = '<div class="glass" style="text-align:center; color: var(--text-muted);">Boshqalar hali test ishlashmadi.</div>';
                    }
                })
                .catch(err => {
                    console.error(err);
                    myContainer.innerHTML = '<div style="color:red; text-align:center;">Natijalarni yuklashda xatolik!</div>';
                });
        }

        function startStudyMode() {
            const list = document.getElementById('studyList');
            list.innerHTML = '';
            document.getElementById('studySearch').value = ''; // Qidiruvni tozalash
            
            dbQuestions.forEach((q, idx) => {
                const card = document.createElement('div');
                card.className = 'glass qa-card';
                let optsHTML = q.options.map((opt, i) => {
                    let isCorrect = (i === q.correct);
                    let letter = String.fromCharCode(65 + i);
                    let color = isCorrect ? 'color: var(--green); font-weight: bold;' : 'color: var(--text-color);';
                    let icon = isCorrect ? '✅' : '⚪️';
                    let border = (i < q.options.length - 1) ? 'border-bottom: 1px solid var(--border-color);' : '';
                    return `<div style="padding: 10px 0; ${border} ${color}">${icon} <b>${letter})</b> ${opt}</div>`;
                }).join('');
                
                card.innerHTML = `
                    <div class="q-text">${idx + 1}. ${q.text}</div>
                    <div style="margin-top: 12px;">${optsHTML}</div>
                `;
                list.appendChild(card);
            });
            showScreen('studyScreen');
            updateBottomNav('nav-study');
        }

        function filterStudyQuestions() {
            const input = document.getElementById('studySearch').value.toLowerCase();
            const list = document.getElementById('studyList');
            const cards = list.getElementsByClassName('qa-card');
            
            for (let i = 0; i < cards.length; i++) {
                const text = cards[i].innerText.toLowerCase();
                if (text.includes(input)) {
                    cards[i].style.display = "";
                } else {
                    cards[i].style.display = "none";
                }
            }
        }

        function startTestMode() {
            let shuffled = JSON.parse(JSON.stringify(dbQuestions));
            shuffled.sort(() => Math.random() - 0.5); // Savollarni aralashtirish
            questions = shuffled.slice(0, 20); // Test uchun faqat 20 tasini tasodifiy olamiz
            questionState = new Array(questions.length).fill('gray');
            currentQueue = questions.map((_, i) => i);
            score = 0;
            correctCount = 0;
            wrongCount = 0;
            skippedCount = 0;
            timeLeft = 1200;
            document.getElementById('scoreDisplay').innerText = score;
            
            buildNavigator();
            startTimer();
            loadNextQuestion();
            showScreen('testScreen');
            updateBottomNav('nav-test');
        }

        function buildNavigator() {
            const nav = document.getElementById('navigatorContainer');
            nav.innerHTML = '';
            questions.forEach((_, i) => {
                const dot = document.createElement('div');
                dot.className = `nav-dot ${questionState[i]}`;
                dot.id = `nav-dot-${i}`;
                dot.innerText = i + 1;
                nav.appendChild(dot);
            });
        }

        function updateNavigatorDot(index) {
            const dot = document.getElementById(`nav-dot-${index}`);
            dot.className = `nav-dot ${questionState[index]}`;
        }

        function setActiveNavigatorDot(index) {
            document.querySelectorAll('.nav-dot').forEach(d => d.classList.remove('active-dot'));
            if(index !== null) {
                const dot = document.getElementById(`nav-dot-${index}`);
                if(dot) {
                    dot.classList.add('active-dot');
                    dot.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
                }
            }
        }

        function loadNextQuestion() {
            if (currentQueue.length === 0) {
                endTest();
                return;
            }
            currentIndex = currentQueue[0];
            const q = questions[currentIndex];
            
            setActiveNavigatorDot(currentIndex);
            document.getElementById('testQuestionText').innerText = `${currentIndex + 1}. ${q.text}`;
            
            const optsContainer = document.getElementById('optionsContainer');
            optsContainer.innerHTML = '';
            
            q.options.forEach((optText, optIdx) => {
                const btn = document.createElement('button');
                btn.className = 'option-btn';
                const letter = String.fromCharCode(65 + optIdx);
                btn.innerHTML = `<b>${letter})</b> ${optText}`;
                btn.onclick = () => selectOption(optIdx, btn);
                optsContainer.appendChild(btn);
            });
            
            document.getElementById('skipBtn').style.display = 'inline-block';
            document.getElementById('nextBtn').style.display = 'none';
        }

        function selectOption(selectedIdx, btnElement) {
            const btns = document.querySelectorAll('.option-btn');
            btns.forEach(b => b.onclick = null); 
            document.getElementById('skipBtn').style.display = 'none';
            document.getElementById('nextBtn').style.display = 'inline-block';

            const q = questions[currentIndex];
            if (selectedIdx === q.correct) {
                btnElement.classList.add('correct');
                score += 3.5;
                correctCount++;
                questionState[currentIndex] = 'green';
                document.getElementById('scoreDisplay').innerText = score;
            } else {
                btnElement.classList.add('wrong');
                btns[q.correct].classList.add('correct');
                wrongCount++;
                questionState[currentIndex] = 'red';
            }
            
            updateNavigatorDot(currentIndex);
            currentQueue.shift();
        }

        function goToNextAfterAnswer() {
            loadNextQuestion();
        }

        function skipQuestion() {
            questionState[currentIndex] = 'yellow';
            updateNavigatorDot(currentIndex);
            skippedCount++;
            
            const skippedIdx = currentQueue.shift();
            currentQueue.push(skippedIdx); 
            
            loadNextQuestion();
        }

        function startTimer() {
            clearInterval(timerInterval);
            updateTimerDisplay();
            timerInterval = setInterval(() => {
                timeLeft--;
                updateTimerDisplay();
                if (timeLeft <= 0) {
                    endTest();
                }
            }, 1000);
        }

        function updateTimerDisplay() {
            const m = Math.floor(timeLeft / 60).toString().padStart(2, '0');
            const s = (timeLeft % 60).toString().padStart(2, '0');
            document.getElementById('timerDisplay').innerText = `${m}:${s}`;
        }

        function endTest() {
            clearInterval(timerInterval);
            document.getElementById('resScore').innerText = score;
            document.getElementById('resCorrect').innerText = correctCount;
            document.getElementById('resWrong').innerText = wrongCount;
            document.getElementById('resSkipped').innerText = currentQueue.length;
            showScreen('resultsScreen');
            
            // Serverga natijani yuborish
            const user = tg.initDataUnsafe?.user;
            if (user) {
                fetch('/save-test-result', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user_id: user.id,
                        first_name: user.first_name,
                        last_name: user.last_name,
                        username: user.username,
                        score: score,
                        correct_count: correctCount,
                        wrong_count: wrongCount,
                        skipped_count: currentQueue.length
                    })
                }).catch(err => console.error("Xatolik:", err));
            }
        }
    </script>
</body>
</html>
"""

@app_web.route('/')
def exam_app():
    return render_template_string(EXAM_HTML_TEMPLATE)

@app_web.route('/api/questions')
def api_questions():
    try:
        q_path = os.path.join(os.path.dirname(__file__), 'questions.json')
        with open(q_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify(data)
    except Exception as e:
        logger.error(f"Error loading questions: {e}")
        return jsonify({"error": "No questions found"}), 404

@app_web.route('/save-test-result', methods=['POST'])
def save_test_result():
    data = request.json
    if not data:
        return {"status": "error", "message": "No data"}, 400
    try:
        user_id = str(data.get('user_id'))
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        username = data.get('username', '')
        score = data.get('score', 0)
        correct_count = data.get('correct_count', 0)
        wrong_count = data.get('wrong_count', 0)
        skipped_count = data.get('skipped_count', 0)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO test_results (user_id, first_name, last_name, username, score, correct_count, wrong_count, skipped_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, first_name, last_name, username, score, correct_count, wrong_count, skipped_count))
            conn.commit()

        import requests
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        
        # User message
        text_user = f"📊 *Sizning test natijangiz:*\n\n✅ To'g'ri: {correct_count}\n❌ Xato: {wrong_count}\n⏭ O'tkazib yuborilgan: {skipped_count}\n\n🏆 Umumiy ball: {score}"
        try:
            requests.post(url, json={"chat_id": user_id, "text": text_user, "parse_mode": "Markdown"}, timeout=3)
        except Exception as e:
            logger.error(f"Userga xabar yuborishda xatolik: {e}")
            
        # Admin message
        if ADMIN_ID:
            full_name = f"{first_name} {last_name}".strip()
            if username:
                full_name += f" (@{username})"
            text_admin = f"📝 *Yangi test natijasi*\n\n👤 O'quvchi: {full_name} (ID: {user_id})\n✅ To'g'ri: {correct_count}\n❌ Xato: {wrong_count}\n⏭ O'tkazib yuborilgan: {skipped_count}\n\n🏆 Ball: {score}"
            try:
                requests.post(url, json={"chat_id": ADMIN_ID, "text": text_admin, "parse_mode": "Markdown"}, timeout=3)
            except Exception as e:
                logger.error(f"Adminga xabar yuborishda xatolik: {e}")

        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Test natijasini saqlashda xatolik: {e}")
        return {"status": "error", "message": str(e)}, 500

@app_web.route('/api/results')
def api_results():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            # Group by user_id to show leaderboard
            cursor.execute('''
                SELECT user_id, first_name, last_name, username, MAX(score) as max_score, SUM(correct_count) as total_correct, MAX(created_at) as last_attempt
                FROM test_results
                GROUP BY user_id
                ORDER BY max_score DESC
            ''')
            rows = cursor.fetchall()
            
            results = []
            for r in rows:
                results.append({
                    "user_id": r[0],
                    "first_name": r[1] or "",
                    "last_name": r[2] or "",
                    "username": r[3] or "",
                    "score": r[4],
                    "correct": r[5]
                })
        return jsonify(results)
    except Exception as e:
        logger.error(f"Error loading test results API: {e}")
        return jsonify({"error": str(e)}), 500


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
                        # Convert to int if possible for maximum compatibility
                        try:
                            target_chat_id = int(u_id)
                        except ValueError:
                            target_chat_id = u_id
                            
                        try:
                            # Try sending with Markdown parse mode
                            await context.bot.send_message(chat_id=target_chat_id, text=message, parse_mode="Markdown")
                            success_count += 1
                        except Exception as e:
                            logger.warning(f"Markdown broadcast failed for {u_id}, retrying as plain text: {e}")
                            try:
                                # Fallback to plain text if Markdown format fails
                                await context.bot.send_message(chat_id=target_chat_id, text=message)
                                success_count += 1
                            except Exception as e_fallback:
                                failed_count += 1
                                logger.error(f"Broadcast yuborishda xatolik (ID: {u_id}): {e_fallback}")
                                # Log exact exception to DB logs table for easy debugging in dashboard logs tab
                                try:
                                    cursor.execute(
                                        "INSERT INTO logs (user_id, username, action_type, content, ai_response) VALUES (?, ?, ?, ?, ?)",
                                        (str(u_id), "SYSTEM", "broadcast_error", f"Msg ID: {b_id}", f"Error: {str(e_fallback)}")
                                    )
                                except Exception as log_err:
                                    logger.error(f"Error inserting broadcast error log: {log_err}")
                                    
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
    app.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu))

    async def post_init(application):
        schedule_reminders(application)
            
        application.job_queue.run_repeating(check_broadcasts, interval=10)
        
        # Kundalik dars jadvalini 9:00 da yuborish (Toshkent vaqti bilan)
        daily_time = time(hour=9, minute=0, tzinfo=TZ)
        application.job_queue.run_daily(send_daily_schedule, time=daily_time, name="daily_schedule_9am")
        logger.info("Kundalik darslar jadvali xabari (9:00) rejalashtirildi.")
            
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
