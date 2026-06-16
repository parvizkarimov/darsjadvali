import os
import re
import json
import logging
from datetime import datetime
from groq import Groq

# Reportlab imports
from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor, Color
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing, Circle, Rect, Polygon, Line

logger = logging.getLogger(__name__)

def get_color(color_val):
    """Hex rangni Reportlab Color formatiga o'tkazish, shaffoflikni (alpha) to'g'ri qo'llash"""
    if not color_val:
        return None
    if not isinstance(color_val, str):
        return color_val
    cleaned = color_val.lstrip('#')
    if len(cleaned) == 8:
        return HexColor('#' + cleaned, hasAlpha=True)
    return HexColor('#' + cleaned)

# ===== DIZAYN SHABLONLARI (STYLES) =====
STYLE_TEMPLATES = {
    "corporate_blue": {
        "name": "Corporate Blue 🏢",
        "cover_bg": "#0F172A",      # Slate 900
        "slide_bg": "#F8FAFC",      # Slate 50
        "primary": "#1E3A8A",       # Blue 800
        "accent": "#2563EB",        # Blue 600
        "text_color": "#1E293B",    # Slate 800
        "text_muted": "#64748B",    # Slate 500
        "cover_text": "#FFFFFF",
        "cover_sub": "#93C5FD",     # Blue 300
    },
    "sleek_dark": {
        "name": "Sleek Dark 🌙",
        "cover_bg": "#090D16",      # Near black
        "slide_bg": "#0F172A",      # Slate 900
        "primary": "#A78BFA",       # Violet 400
        "accent": "#F472B6",        # Pink 400
        "text_color": "#F8FAFC",    # Slate 50
        "text_muted": "#94A3B8",    # Slate 400
        "cover_text": "#FFFFFF",
        "cover_sub": "#DDD6FE",     # Violet 200
    },
    "warm_minimalist": {
        "name": "Warm Minimalist 🎨",
        "cover_bg": "#FAF7F2",      # Warm Ivory
        "slide_bg": "#FAFDFB",      # Pale Cream
        "primary": "#1E293B",       # Slate 800
        "accent": "#EA580C",        # Rust Orange
        "text_color": "#334155",    # Slate 700
        "text_muted": "#64748B",    # Slate 500
        "cover_text": "#1E293B",
        "cover_sub": "#EA580C",
    },
    "eco_green": {
        "name": "Eco Green 🌿",
        "cover_bg": "#064E3B",      # Emerald 900
        "slide_bg": "#F0FDF4",      # Green 50
        "primary": "#065F46",       # Emerald 800
        "accent": "#10B981",        # Emerald 500
        "text_color": "#064E3B",    # Emerald 900
        "text_muted": "#4B6B60",    # Muted green-gray
        "cover_text": "#FFFFFF",
        "cover_sub": "#A7F3D0",     # Emerald 200
    },
    "sunset_orange": {
        "name": "Sunset Orange 🍊",
        "cover_bg": "#EA580C",      # Orange 600
        "slide_bg": "#FFF7ED",      # Orange 50
        "primary": "#7C2D12",       # Orange 800
        "accent": "#F97316",        # Orange 500
        "text_color": "#431407",    # Dark brown
        "text_muted": "#9A3412",
        "cover_text": "#FFFFFF",
        "cover_sub": "#FFEDD5",
    },
    "ocean_breeze": {
        "name": "Ocean Breeze 🌊",
        "cover_bg": "#115E59",      # Teal 800
        "slide_bg": "#F0FDFA",      # Teal 50
        "primary": "#0F766E",       # Teal 700
        "accent": "#06B6D4",        # Cyan 500
        "text_color": "#115E59",
        "text_muted": "#0D9488",
        "cover_text": "#FFFFFF",
        "cover_sub": "#CCFBF1",
    },
    "royal_purple": {
        "name": "Royal Purple 👑",
        "cover_bg": "#4C1D95",      # Violet 800
        "slide_bg": "#F5F3FF",      # Violet 50
        "primary": "#5B21B6",       # Violet 700
        "accent": "#8B5CF6",        # Violet 500
        "text_color": "#2E1065",
        "text_muted": "#7C3AED",
        "cover_text": "#FFFFFF",
        "cover_sub": "#DDD6FE",
    },
    "cherry_blossom": {
        "name": "Cherry Blossom 🌸",
        "cover_bg": "#BE185D",      # Pink 700
        "slide_bg": "#FDF2F8",      # Pink 50
        "primary": "#9D174D",       # Pink 800
        "accent": "#EC4899",        # Pink 500
        "text_color": "#500724",
        "text_muted": "#DB2777",
        "cover_text": "#FFFFFF",
        "cover_sub": "#FCE7F3",
    },
    "midnight_gold": {
        "name": "Midnight Gold ✨",
        "cover_bg": "#030712",      # Gray 950
        "slide_bg": "#0B0F19",      # Dark Blue-Gray
        "primary": "#F59E0B",       # Amber 500
        "accent": "#D97706",        # Amber 600
        "text_color": "#F9FAFB",    # Gray 50
        "text_muted": "#9CA3AF",    # Gray 400
        "cover_text": "#FFFFFF",
        "cover_sub": "#FDE68A",
    },
    "retro_neon": {
        "name": "Retro Neon ⚡",
        "cover_bg": "#09090B",      # Zinc 950
        "slide_bg": "#18181B",      # Zinc 900
        "primary": "#06B6D4",       # Cyan 500
        "accent": "#10B981",        # Emerald 500
        "text_color": "#FAFAFA",    # Zinc 50
        "text_muted": "#A1A1AA",    # Zinc 400
        "cover_text": "#FFFFFF",
        "cover_sub": "#A7F3D0",
    },
    "nordic_slate": {
        "name": "Nordic Slate 🏔️",
        "cover_bg": "#1F2937",      # Gray 800
        "slide_bg": "#F3F4F6",      # Gray 100
        "primary": "#374151",       # Gray 700
        "accent": "#4B5563",       # Gray 600
        "text_color": "#111827",    # Gray 900
        "text_muted": "#6B7280",    # Gray 500
        "cover_text": "#FFFFFF",
        "cover_sub": "#E5E7EB",
    },
    "vintage_sepia": {
        "name": "Vintage Sepia 📜",
        "cover_bg": "#451A03",      # Amber 950
        "slide_bg": "#FEF3C7",      # Amber 100
        "primary": "#78350F",       # Amber 900
        "accent": "#D97706",        # Amber 600
        "text_color": "#451A03",
        "text_muted": "#B45309",
        "cover_text": "#FFFFFF",
        "cover_sub": "#FDE68A",
    },
    "cyberpunk": {
        "name": "Cyberpunk 🚀",
        "cover_bg": "#090212",      # Deep dark violet
        "slide_bg": "#0F051D",      # Dark purple
        "primary": "#D946EF",       # Fuchsia 500
        "accent": "#06B6D4",        # Cyan 500
        "text_color": "#FDF4FF",
        "text_muted": "#A21CAF",
        "cover_text": "#FFFFFF",
        "cover_sub": "#F5D0FE",
    },
    "coffee_cream": {
        "name": "Coffee & Cream ☕",
        "cover_bg": "#3E2723",      # Brown 900
        "slide_bg": "#F5EBE6",      # Soft warm cream
        "primary": "#4E3629",       # Brown 800
        "accent": "#8C6239",        # Soft bronze
        "text_color": "#271206",
        "text_muted": "#6D4C41",
        "cover_text": "#FFFFFF",
        "cover_sub": "#EFEBE9",
    }
}

def normalize_uzbek_text(text):
    """Uzbek tilidagi maxsus belgilarni Helvetica qo'llab-quvvatlaydigan formatga o'tkazish"""
    if not text:
        return ""
    
    replacements = {
        "ʻ": "'",
        "ʼ": "'",
        "’": "'",
        "‘": "'",
        "“": '"',
        "”": '"',
    }
    for orig, rep in replacements.items():
        text = text.replace(orig, rep)
        
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    
    return text

def clean_data_recursively(data):
    """Hamma matnlarni normallashtirish"""
    if isinstance(data, dict):
        return {k: clean_data_recursively(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [clean_data_recursively(item) for item in data]
    elif isinstance(data, str):
        return normalize_uzbek_text(data)
    return data

# ===== GENERATOR LOGIKASI =====

def generate_presentation_content(topic, api_key):
    """Groq Llama modelidan foydalanib prezentatsiya kontentini JSON formatda olish"""
    if not api_key:
        raise ValueError("GROQ_API_KEY o'rnatilmagan.")

    client = Groq(api_key=api_key)
    
    prompt = (
        "Sen yuqori malakali ma'ruzachi va taqdimotchi mutaxassissan. "
        f"Mavzu: '{topic}'.\n"
        "Ushbu mavzu bo'yicha slaydlar matnini o'zbek tilida juda batafsil va chuqur tahliliy ma'lumotlar bilan tayyorlab ber. "
        "Taqdimot aniq 10 ta slayddan iborat bo'lishi shart (muqova sahifasidan tashqari 9 ta kontent slayd). "
        "Javobni faqat va vaqt JSON formatda qaytar. Boshqa hech qanday izoh yoki kirish so'zlarini yozma. "
        "JSON formati quyidagi ko'rinishda bo'lishi shart:\n"
        "{\n"
        "  \"title\": \"Taqdimotning bosh sarlavhasi (Mavzuni to'liq yorituvchi va batafsil)\",\n"
        "  \"subtitle\": \"Mavzuning mohiyatini ochib beruvchi qiziqarli tag-sarlavha\",\n"
        "  \"slides\": [\n"
        "    {\n"
        "      \"slide_number\": 1,\n"
        "      \"title\": \"Slayd sarlavhasi (masalan, Kirish yoki Reja)\",\n"
        "      \"description\": \"Slayd mavzusi bo'yicha qisqa umumiy tushuncha yoki kirish gap (1-2 gapdan iborat batafsil matn).\",\n"
        "      \"layout_type\": \"Slayd maketi turi: 'grid_cards', 'split_focus', 'horizontal_timeline' yoki 'quote_highlight'\",\n"
        "      \"points\": [\n"
        "        {\n"
        "          \"text\": \"Mavzuga oid chuqur tahliliy fakt yoki g'oya (2-3 ta gapdan iborat batafsil tushuntirish, 200-280 ta belgi)\",\n"
        "          \"icon_type\": \"Ushbu nuqtaga mos ikonka turi: 'trend', 'shield', 'database', 'user', 'globe', 'idea', 'gear', 'lock', 'chat', 'star'\"\n"
        "        },\n"
        "        ...\n"
        "      ]\n"
        "    },\n"
        "    ... (yana 8 ta slayd, jami 9 ta)\n"
        "  ]\n"
        "}\n\n"
        "Qoidalarga amal qil:\n"
        "1. Taqdimot mutlaqo yuzaki bo'lmasin, ma'lumotlar hajmi va chuqurligi professional bo'lsin.\n"
        "2. Har bir slaydning 'layout_type' maydoni bo'lsin. Mavzuga va slayd kontentiga qarab layout turlarini turlicha tanla. Masalan, reja va bosqichlar uchun 'horizontal_timeline', tahlillar va xulosalar uchun 'split_focus' yoki 'quote_highlight', umumiy ma'lumotlar uchun 'grid_cards' ishlating. Har bir taqdimotda kamida 3-4 xil layout turlari aralash bo'lsin (hammasi bir xil bo'lib qolmasin).\n"
        "3. Har bir slaydda 3 tadan 5 tagacha 'points' (nuqtalar) bo'lishi shart. Har bir nuqta uchun uning ma'nosiga mos 'icon_type' tanlansin (masalan: kiberxavfsizlikka shield/lock, o'sishga trend, ma'lumotlarga database, texnik jarayonlarga gear, muloqotga chat).\n"
        "4. Har bir nuqtaning 'text' maydonidagi matn chuqur tahliliy ma'lumotlarga boy va professional bo'lishi shart. Har bir punkt 2-3 ta batafsil gapdan iborat bo'lib, o'rtacha 200-280 ta belgi atrofida yozilsin (juda qisqa gaplar yoki iboralar bo'lmasin).\n"
        "5. Slaydlar tartibi mantiqiy bo'lsin: Kirish -> Muammo -> Tahlil -> Yechim -> Kelajak -> Xulosa va h.k."
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=3000,
            response_format={"type": "json_object"}
        )
        content_str = response.choices[0].message.content
        logger.info(f"Groq API response raw length: {len(content_str)}")
        
        # JSON parsing
        data = json.loads(content_str)
        cleaned_data = clean_data_recursively(data)
        
        return cleaned_data
    except Exception as e:
        logger.error(f"Failed to generate presentation via Groq: {e}")
        raise e

# ===== VECTOR GRAPHICS & ICONS GENERATION =====

def get_custom_vector_icon(icon_type, primary, accent, size=36):
    """Mavzuga oid yuqori texnologiyali va batafsil vektor ikonkalarini chiroyli olti burchakli (hexagon) panel ichida chizish"""
    d = Drawing(size, size)
    scale = size / 36.0
    
    def s_x(val): return val * scale
    def s_y(val): return val * scale
    
    p_color = get_color(primary)
    a_color = get_color(accent)
    w_color = get_color("#FFFFFF")
    
    # 1. Tashqi porlovchi oltiburchak ramka (Double-nested glowing hexagon boundary)
    poly_outer = Polygon([
        s_x(18), s_y(35), 
        s_x(33), s_y(26.5), 
        s_x(33), s_y(9.5), 
        s_x(18), s_y(1), 
        s_x(3), s_y(9.5), 
        s_x(3), s_y(26.5)
    ], fillColor=get_color(accent + "12"), strokeColor=a_color, strokeWidth=1.0)
    d.add(poly_outer)
    
    # Ichki nozik oltiburchak ramka
    poly_mid = Polygon([
        s_x(18), s_y(32.5), 
        s_x(30.5), s_y(25.3), 
        s_x(30.5), s_y(10.7), 
        s_x(18), s_y(3.5), 
        s_x(5.5), s_y(10.7), 
        s_x(5.5), s_y(25.3)
    ], fillColor=None, strokeColor=get_color(accent + "33"), strokeWidth=0.6)
    d.add(poly_mid)
    
    # 2. Ichki to'q rangli oltiburchak plastinka
    poly_inner = Polygon([
        s_x(18), s_y(29.5), 
        s_x(28), s_y(23.7), 
        s_x(28), s_y(12.3), 
        s_x(18), s_y(6.5), 
        s_x(8), s_y(12.3), 
        s_x(8), s_y(23.7)
    ], fillColor=p_color, strokeColor=None)
    d.add(poly_inner)
    
    # 3. Ichki ramz (Ikonka turi) chizish
    if icon_type == "trend":
        # Trend: Grid, dynamic bar lines, and a zigzag rising trend arrow
        d.add(Line(s_x(12), s_y(12), s_x(24), s_y(12), strokeColor=get_color(accent + "44"), strokeWidth=0.5))
        d.add(Line(s_x(12), s_y(18), s_x(24), s_y(18), strokeColor=get_color(accent + "44"), strokeWidth=0.5))
        d.add(Rect(s_x(12), s_y(10), s_x(2.5), s_y(6), fillColor=a_color, strokeColor=None))
        d.add(Rect(s_x(16.5), s_y(10), s_x(2.5), s_y(11), fillColor=w_color, strokeColor=None))
        d.add(Rect(s_x(21), s_y(10), s_x(2.5), s_y(15), fillColor=a_color, strokeColor=None))
        d.add(Line(s_x(10), s_y(11), s_x(24), s_y(23), strokeColor=w_color, strokeWidth=1.5))
        d.add(Line(s_x(20), s_y(23), s_x(24), s_y(23), strokeColor=w_color, strokeWidth=1.5))
        d.add(Line(s_x(24), s_y(19), s_x(24), s_y(23), strokeColor=w_color, strokeWidth=1.5))
        d.add(Circle(s_x(24), s_y(23), s_x(1.8), fillColor=a_color, strokeColor=w_color, strokeWidth=0.5))
        
    elif icon_type == "shield":
        d.add(Polygon([s_x(18), s_y(8), s_x(26), s_y(13), s_x(26), s_y(21), s_x(18), s_y(28), s_x(10), s_y(21), s_x(10), s_y(13)], fillColor=w_color, strokeColor=a_color, strokeWidth=0.5))
        d.add(Polygon([s_x(18), s_y(11), s_x(23), s_y(15), s_x(23), s_y(20), s_x(18), s_y(25), s_x(13), s_y(20), s_x(13), s_y(15)], fillColor=p_color, strokeColor=a_color, strokeWidth=0.8))
        d.add(Line(s_x(18), s_y(11), s_x(18), s_y(25), strokeColor=w_color, strokeWidth=0.6))
        d.add(Circle(s_x(18), s_y(18), s_x(2.2), fillColor=a_color, strokeColor=w_color, strokeWidth=0.6))
        
    elif icon_type == "database":
        for y_offset, fill_c in [(21, w_color), (15, a_color), (9, w_color)]:
            d.add(Rect(s_x(10), s_y(y_offset), s_x(16), s_y(4), rx=s_x(1.5), ry=s_y(1.5), fillColor=fill_c, strokeColor=None))
            d.add(Circle(s_x(18), s_y(y_offset + 4), s_x(8), fillColor=fill_c, strokeColor=None))
            d.add(Circle(s_x(13), s_y(y_offset + 2), s_x(0.8), fillColor=p_color, strokeColor=None))
        d.add(Line(s_x(8.5), s_y(11), s_x(8.5), s_y(23), strokeColor=a_color, strokeWidth=0.8))
        d.add(Line(s_x(8.5), s_y(11), s_x(10), s_y(11), strokeColor=a_color, strokeWidth=0.8))
        d.add(Line(s_x(8.5), s_y(17), s_x(10), s_y(17), strokeColor=a_color, strokeWidth=0.8))
        d.add(Line(s_x(8.5), s_y(23), s_x(10), s_y(23), strokeColor=a_color, strokeWidth=0.8))
        
    elif icon_type == "user":
        d.add(Circle(s_x(18), s_y(18), s_x(8.5), fillColor=None, strokeColor=get_color(accent + "33"), strokeWidth=0.6))
        d.add(Circle(s_x(18), s_y(22), s_x(4.0), fillColor=w_color, strokeColor=a_color, strokeWidth=0.5))
        d.add(Polygon([s_x(11), s_y(10), s_x(25), s_y(10), s_x(22.5), s_y(16.5), s_x(13.5), s_y(16.5)], fillColor=a_color, strokeColor=w_color, strokeWidth=0.5))
        d.add(Line(s_x(18), s_y(7), s_x(18), s_y(9), strokeColor=a_color, strokeWidth=0.8))
        d.add(Line(s_x(18), s_y(27), s_x(18), s_y(29), strokeColor=a_color, strokeWidth=0.8))
        
    elif icon_type == "globe":
        d.add(Circle(s_x(18), s_y(18), s_x(8.5), fillColor=None, strokeColor=w_color, strokeWidth=1.2))
        d.add(Line(s_x(9.5), s_y(18), s_x(26.5), s_y(18), strokeColor=a_color, strokeWidth=0.8))
        d.add(Line(s_x(18), s_y(9.5), s_x(18), s_y(26.5), strokeColor=a_color, strokeWidth=0.8))
        d.add(Circle(s_x(18), s_y(18), s_x(5.0), fillColor=None, strokeColor=w_color, strokeWidth=0.6))
        d.add(Circle(s_x(25), s_y(22), s_x(1.5), fillColor=a_color, strokeColor=w_color, strokeWidth=0.5))
        
    elif icon_type == "idea":
        d.add(Circle(s_x(18), s_y(21), s_x(5.0), fillColor=w_color, strokeColor=a_color, strokeWidth=0.5))
        d.add(Polygon([s_x(15), s_y(21), s_x(21), s_y(21), s_x(19.5), s_y(14), s_x(16.5), s_y(14)], fillColor=a_color, strokeColor=None))
        d.add(Rect(s_x(15), s_y(11), s_x(6), s_y(3), rx=s_x(0.6), ry=s_y(0.6), fillColor=w_color, strokeColor=None))
        d.add(Line(s_x(18), s_y(19), s_x(18), s_y(23), strokeColor=p_color, strokeWidth=0.8))
        d.add(Line(s_x(18), s_y(28), s_x(18), s_y(30), strokeColor=a_color, strokeWidth=0.8))
        d.add(Line(s_x(11), s_y(24), s_x(13), s_y(23), strokeColor=a_color, strokeWidth=0.8))
        d.add(Line(s_x(25), s_y(24), s_x(23), s_y(23), strokeColor=a_color, strokeWidth=0.8))
        
    elif icon_type == "gear":
        d.add(Circle(s_x(16), s_y(20), s_x(6.5), fillColor=a_color, strokeColor=None))
        for angle in range(0, 360, 45):
            import math
            rad = math.radians(angle)
            gx = 16 + 8 * math.cos(rad)
            gy = 20 + 8 * math.sin(rad)
            d.add(Circle(s_x(gx), s_y(gy), s_x(1.8), fillColor=a_color, strokeColor=None))
        d.add(Circle(s_x(16), s_y(20), s_x(4.5), fillColor=p_color, strokeColor=None))
        d.add(Circle(s_x(16), s_y(20), s_x(2.0), fillColor=w_color, strokeColor=None))
        d.add(Circle(s_x(24), s_y(12), s_x(4.0), fillColor=w_color, strokeColor=None))
        d.add(Circle(s_x(24), s_y(12), s_x(2.5), fillColor=p_color, strokeColor=None))
        d.add(Circle(s_x(24), s_y(12), s_x(1.0), fillColor=a_color, strokeColor=None))
        
    elif icon_type == "lock":
        d.add(Circle(s_x(18), s_y(21), s_x(4.2), fillColor=None, strokeColor=w_color, strokeWidth=1.5))
        d.add(Rect(s_x(12), s_y(10), s_x(12), s_y(8), rx=s_x(1.2), ry=s_y(1.2), fillColor=a_color, strokeColor=w_color, strokeWidth=0.5))
        d.add(Circle(s_x(18), s_y(15), s_x(1.5), fillColor=w_color, strokeColor=None))
        d.add(Polygon([s_x(17.2), s_y(11), s_x(18.8), s_y(11), s_x(18.3), s_y(14.5), s_x(17.7), s_y(14.5)], fillColor=w_color, strokeColor=None))
        
    elif icon_type == "chat":
        d.add(Rect(s_x(10), s_y(14), s_x(17), s_y(11), rx=s_x(2), ry=s_y(2), fillColor=w_color, strokeColor=None))
        d.add(Polygon([s_x(12), s_y(14), s_x(12), s_y(10), s_x(17), s_y(14)], fillColor=w_color, strokeColor=None))
        d.add(Circle(s_x(14.5), s_y(19.5), s_x(1.0), fillColor=p_color, strokeColor=None))
        d.add(Circle(s_x(18.5), s_y(19.5), s_x(1.0), fillColor=a_color, strokeColor=None))
        d.add(Circle(s_x(22.5), s_y(19.5), s_x(1.0), fillColor=p_color, strokeColor=None))
        d.add(Polygon([s_x(23), s_y(12), s_x(26), s_y(9), s_x(26), s_y(12)], fillColor=a_color, strokeColor=None))
        d.add(Rect(s_x(21), s_y(12), s_x(8), s_y(6), rx=s_x(1), ry=s_y(1), fillColor=a_color, strokeColor=None))
        
    elif icon_type == "star":
        points = [
            s_x(18), s_y(29),
            s_x(20.8), s_y(20.8),
            s_x(29), s_y(18),
            s_x(20.8), s_y(15.2),
            s_x(18), s_y(7),
            s_x(15.2), s_y(15.2),
            s_x(7), s_y(18),
            s_x(15.2), s_y(20.8)
        ]
        d.add(Polygon(points, fillColor=w_color, strokeColor=None))
        d.add(Line(s_x(18), s_y(4), s_x(18), s_y(32), strokeColor=get_color(accent + "88"), strokeWidth=0.6))
        d.add(Line(s_x(4), s_y(18), s_x(32), s_y(18), strokeColor=get_color(accent + "88"), strokeWidth=0.6))
        d.add(Circle(s_x(18), s_y(18), s_x(3.0), fillColor=a_color, strokeColor=w_color, strokeWidth=0.5))
        
    else:
        d.add(Polygon([s_x(18), s_y(9), s_x(27), s_y(18), s_x(18), s_y(27), s_x(9), s_y(18)], fillColor=w_color, strokeColor=None))
        d.add(Circle(s_x(18), s_y(18), s_x(3.8), fillColor=a_color, strokeColor=w_color, strokeWidth=0.5))
        
    return d

def get_slide_icon(primary, accent, style_name):
    return get_custom_vector_icon("default", primary, accent)

def draw_tech_illustration(canvas_obj, x, y, primary, accent, style_name):
    """Muqova varag'ida sun'iy intellekt va blockchain mavzusiga oid katta neyro-tarmoq chizmasini chizish"""
    canvas_obj.saveState()
    
    # 1. Orqa yarim-shaffof orbital aylanalar
    canvas_obj.setFillColor(get_color(accent + "1C"))
    canvas_obj.circle(x, y, 95, fill=True, stroke=False)
    
    # 2. Neyro-tarmoq mesh liniyalari (aloqalar)
    canvas_obj.setStrokeColor(get_color(accent + "44"))
    canvas_obj.setLineWidth(0.8)
    
    # Mesh tugunlari koordinatalari (markaz atrofida)
    nodes = [
        (x - 50, y + 50), (x + 50, y + 50),
        (x + 70, y - 20), (x - 70, y - 20),
        (x - 20, y - 70), (x + 20, y - 70),
        (x - 80, y + 20), (x + 80, y + 20),
        (x, y) # Center
    ]
    
    # Tugunlararo chiziqlar chizish (interconnected mesh)
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            if (i + j) % 2 == 0 or (i * j) % 3 == 0:
                canvas_obj.line(nodes[i][0], nodes[i][1], nodes[j][0], nodes[j][1])
                
    # 3. Concentric porlovchi halqalar
    canvas_obj.setStrokeColor(get_color("#FFFFFF" if style_name in ["sleek_dark", "cyberpunk", "retro_neon", "midnight_gold"] else primary))
    canvas_obj.setLineWidth(1.5)
    canvas_obj.circle(x, y, 50, fill=False, stroke=True)
    
    # Katta orbital aylana (dashed line)
    canvas_obj.setLineWidth(1.2)
    canvas_obj.setDash(4, 4)
    canvas_obj.circle(x, y, 80, fill=False, stroke=True)
    canvas_obj.setDash(1, 8)
    canvas_obj.circle(x, y, 92, fill=False, stroke=True)
    canvas_obj.setDash() # reset dash
    
    # 4. Tugun nuqtalarini (neyronlarni) chizish
    node_color = "#FFFFFF" if style_name in ["sleek_dark", "cyberpunk", "retro_neon", "midnight_gold"] else accent
    canvas_obj.setFillColor(get_color(node_color))
    for nx, ny in nodes:
        canvas_obj.circle(nx, ny, 4.5, fill=True, stroke=False)
        
    # Markaziy yadro
    canvas_obj.setFillColor(get_color(accent))
    canvas_obj.circle(x, y, 12, fill=True, stroke=False)
    canvas_obj.setFillColor(get_color("#FFFFFF"))
    canvas_obj.circle(x, y, 5, fill=True, stroke=False)
    
    canvas_obj.restoreState()

def draw_hud_decorations(canvas_obj, doc, style):
    """Barcha sahifalarga kiber-HUD to'r liniyalari va burchak krestiklarini chizish"""
    width, height = doc.pagesize
    
    # 1. HUD To'r liniyalari (subtle grid network)
    canvas_obj.setStrokeColor(get_color(style["accent"] + "05")) # 2% xiralikda juda mayin liniyalar
    canvas_obj.setLineWidth(0.6)
    
    # Vertikal grid
    for x in range(80, int(width), 80):
        canvas_obj.line(x, 0, x, height)
    # Gorizontal grid
    for y in range(80, int(height), 80):
        canvas_obj.line(0, y, width, y)
        
    # 2. Burchaklardagi HUD krestiklari (HUD corner crosshairs "+")
    canvas_obj.setStrokeColor(get_color(style["accent"] + "26")) # 15% xiralik
    canvas_obj.setLineWidth(1)
    
    corners = [
        (35, height - 35),           # Top-left
        (width - 35, height - 35),   # Top-right
        (35, 35),                    # Bottom-left
        (width - 35, 35)             # Bottom-right
    ]
    for cx, cy in corners:
        canvas_obj.line(cx, cy - 6, cx, cy + 6)
        canvas_obj.line(cx - 6, cy, cx + 6, cy)

def draw_cover_background(canvas_obj, doc):
    canvas_obj.saveState()
    style = doc.style_config
    
    # Draw background color
    canvas_obj.setFillColor(get_color(style["cover_bg"]))
    canvas_obj.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=True, stroke=False)
    
    # Draw HUD grid & crosshairs
    draw_hud_decorations(canvas_obj, doc, style)
    
    # 3. Kiber dizayndagi porlovchi sarlavha blok-trapeziyasi (Angled polygon card)
    canvas_obj.setFillColor(get_color(style["primary"] + "12")) # 7% shaffoflikda to'q yadro foni
    canvas_obj.setStrokeColor(get_color(style["accent"]))
    canvas_obj.setLineWidth(1.8)
    
    p_card = canvas_obj.beginPath()
    p_card.moveTo(60, 80)
    p_card.lineTo(490, 80)
    p_card.lineTo(550, doc.pagesize[1] - 90)
    p_card.lineTo(60, doc.pagesize[1] - 90)
    p_card.close()
    canvas_obj.drawPath(p_card, fill=True, stroke=True)
    
    # Trapeziya chetiga dekorativ kiber nuqta/chiziqchalar qo'shish
    canvas_obj.setFillColor(get_color(style["accent"]))
    canvas_obj.rect(60, doc.pagesize[1] - 88, 30, 3, fill=True, stroke=False)
    canvas_obj.rect(460, 78, 30, 3, fill=True, stroke=False)
    
    # Neyro-tarmoq chizmasi
    ill_x = doc.pagesize[0] - 170
    ill_y = doc.pagesize[1] * 0.6
    draw_tech_illustration(canvas_obj, ill_x, ill_y, style["primary"], style["accent"], doc.style_name)
        
    canvas_obj.restoreState()

def draw_bottom_tech_decoration(canvas_obj, x, y, primary, accent, style_name, page_num):
    """Slaydning pastki qismida bo'sh joyni to'ldirish va kreativlikni oshirish uchun mavzuga oid texnik chizmalar chizish"""
    canvas_obj.saveState()
    
    p_color = get_color(primary)
    a_color = get_color(accent)
    w_color = get_color("#FFFFFF")
    
    # 10% shaffoflikda bezak ranglari
    decor_color = get_color(accent + "1C")
    canvas_obj.setStrokeColor(decor_color)
    canvas_obj.setFillColor(decor_color)
    canvas_obj.setLineWidth(0.8)
    
    if page_num % 3 == 1:
        # A: Radar Scope / Compass Dial (Bottom-Right)
        canvas_obj.circle(x, y, 55, fill=False, stroke=True)
        canvas_obj.circle(x, y, 35, fill=False, stroke=True)
        canvas_obj.setDash(2, 4)
        canvas_obj.circle(x, y, 45, fill=False, stroke=True)
        canvas_obj.setDash()
        # Cross lines
        canvas_obj.line(x - 65, y, x + 65, y)
        canvas_obj.line(x, y - 65, x, y + 65)
        # Radar sweep angle
        canvas_obj.setLineWidth(1.5)
        canvas_obj.line(x, y, x + 38, y + 38)
        canvas_obj.circle(x + 38, y + 38, 3, fill=True, stroke=False)
        # Text label
        canvas_obj.setFont("Helvetica-Bold", 7)
        canvas_obj.setFillColor(get_color(accent + "44"))
        canvas_obj.drawString(x - 55, y - 50, "RADAR_SWEEP // ACTIVE")
        
    elif page_num % 3 == 2:
        # B: Signal Oscilloscope / Wave grid (Bottom-Right)
        gw, gh = 110, 45
        gx, gy = x - 55, y - 22
        canvas_obj.setStrokeColor(get_color(accent + "0C"))
        for xi in range(int(gx), int(gx + gw) + 1, 15):
            canvas_obj.line(xi, gy, xi, gy + gh)
        for yi in range(int(gy), int(gy + gh) + 1, 10):
            canvas_obj.line(gx, yi, gx + gw, yi)
        # Draw sine wave
        canvas_obj.setStrokeColor(a_color)
        canvas_obj.setLineWidth(1.2)
        points_wave = []
        for step in range(0, 111, 4):
            import math
            wx = gx + step
            wy = (gy + gh/2) + 15 * math.sin(step * 0.09)
            points_wave.append((wx, wy))
        for j in range(len(points_wave) - 1):
            canvas_obj.line(points_wave[j][0], points_wave[j][1], points_wave[j+1][0], points_wave[j+1][1])
        # Text label
        canvas_obj.setFont("Helvetica-Bold", 7)
        canvas_obj.setFillColor(get_color(accent + "44"))
        canvas_obj.drawString(gx, gy - 8, "FREQ_OSCILLOSCOPE // 44.1 KHZ")
        
    else:
        # C: Hexagonal Tech Mesh / Nodes (Bottom-Right)
        points_mesh = [
            (x - 35, y + 15), (x + 15, y + 25),
            (x + 35, y - 8), (x - 15, y - 25),
            (x, y)
        ]
        canvas_obj.setStrokeColor(get_color(accent + "33"))
        for i in range(len(points_mesh)):
            for j in range(i+1, len(points_mesh)):
                if (i+j) % 2 == 1:
                    canvas_obj.line(points_mesh[i][0], points_mesh[i][1], points_mesh[j][0], points_mesh[j][1])
        canvas_obj.setFillColor(a_color)
        for px, py in points_mesh:
            canvas_obj.circle(px, py, 2.5, fill=True, stroke=False)
        canvas_obj.circle(x, y, 4, fill=True, stroke=False)
        canvas_obj.setFillColor(w_color)
        canvas_obj.circle(x, y, 1.8, fill=True, stroke=False)
        # Text label
        canvas_obj.setFont("Helvetica-Bold", 7)
        canvas_obj.setFillColor(get_color(accent + "44"))
        canvas_obj.drawString(x - 45, y - 40, "MESH_GRID // NODE_ACTIVE")
        
    canvas_obj.restoreState()

def draw_slide_background(canvas_obj, doc):
    canvas_obj.saveState()
    style = doc.style_config
    page_num = canvas_obj.getPageNumber()
    
    # Draw slide background
    canvas_obj.setFillColor(get_color(style["slide_bg"]))
    canvas_obj.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=True, stroke=False)
    
    # Draw HUD grid & crosshairs
    draw_hud_decorations(canvas_obj, doc, style)
    
    # Slaydlar har xil va kreativ ko'rinishi uchun sahifa raqamiga qarab turli vektor bezaklar chizamiz
    canvas_obj.setFillColor(get_color(style["accent"]))
    
    if page_num % 3 == 1:
        canvas_obj.rect(54, doc.pagesize[1] - 40, doc.pagesize[0] - 108, 4, fill=True, stroke=False)
        
        p = canvas_obj.beginPath()
        p.moveTo(doc.pagesize[0], doc.pagesize[1])
        p.lineTo(doc.pagesize[0] - 80, doc.pagesize[1])
        p.lineTo(doc.pagesize[0], doc.pagesize[1] - 80)
        p.close()
        canvas_obj.drawPath(p, fill=True, stroke=False)
        
    elif page_num % 3 == 2:
        canvas_obj.rect(40, 54, 4, doc.pagesize[1] - 108, fill=True, stroke=False)
        
        canvas_obj.circle(doc.pagesize[0] - 20, 20, 40, fill=True, stroke=False)
        canvas_obj.setFillColor(get_color(style["slide_bg"]))
        canvas_obj.circle(doc.pagesize[0] - 20, 20, 34, fill=True, stroke=False)
        
    else:
        canvas_obj.setFillColor(get_color(style["primary"]))
        canvas_obj.rect(54, doc.pagesize[1] - 40, doc.pagesize[0] - 108, 3, fill=True, stroke=False)
        canvas_obj.setFillColor(get_color(style["accent"]))
        canvas_obj.rect(54, doc.pagesize[1] - 46, doc.pagesize[0] - 108, 1.5, fill=True, stroke=False)
        
        canvas_obj.circle(30, doc.pagesize[1] - 30, 8, fill=True, stroke=False)

    # Draw bottom tech decoration
    ill_x = doc.pagesize[0] - 120
    ill_y = 110
    draw_bottom_tech_decoration(canvas_obj, ill_x, ill_y, style["primary"], style["accent"], doc.style_name, page_num)

    # Draw bottom footer line
    border_color = "#cbd5e1" if doc.style_name not in ["sleek_dark", "cyberpunk", "retro_neon", "midnight_gold"] else "#334155"
    canvas_obj.setFillColor(get_color(border_color))
    canvas_obj.rect(54, 45, doc.pagesize[0] - 108, 1, fill=True, stroke=False)
    
    # Draw tech status feed line above footer
    canvas_obj.setFont("Helvetica-Bold", 6)
    canvas_obj.setFillColor(get_color(style["accent"] + "44"))
    status_text = f"[ SYS.FEED // CONNECTED // PAGE_0{page_num} ] ---------------------------------------------------- [ SECURE // SHIELD_ON ]"
    canvas_obj.drawString(54, 52, status_text)
    
    # Draw footer metadata
    canvas_obj.setFont("Helvetica", 9)
    canvas_obj.setFillColor(get_color(style["text_muted"]))
    canvas_obj.drawString(54, 28, doc.topic_title)
    
    # Draw page number
    canvas_obj.drawRightString(doc.pagesize[0] - 54, 28, f"{page_num} / 10")
    
    canvas_obj.restoreState()

# ===== HELPERS =====
def extract_point_info(pt):
    if isinstance(pt, dict):
        text = pt.get("text", "")
        icon_type = pt.get("icon_type", "default")
    else:
        text = str(pt)
        icon_type = "default"
        
    # Xatolik va cheksiz aylanib qolishni oldini olish maqsadida matnni cheklaymiz (320 belgi)
    if len(text) > 320:
        text = text[:317] + "..."
        
    return text, icon_type

# ===== PDF YARATISH LOGIKASI =====

def create_presentation_pdf(data, style_name, output_path, author_name="Taqdimotchi"):
    """Keltirilgan ma'lumotlar asosida 10 varaqalik taqdimot PDF yaratadi"""
    if style_name not in STYLE_TEMPLATES:
        style_name = "corporate_blue"
        
    style_config = STYLE_TEMPLATES[style_name]
    pagesize = landscape(A4)
    
    doc = SimpleDocTemplate(
        output_path,
        pagesize=pagesize,
        leftMargin=60,
        rightMargin=60,
        topMargin=55,
        bottomMargin=55
    )
    
    doc.style_name = style_name
    doc.style_config = style_config
    doc.topic_title = data.get("title", "Taqdimot")
    
    styles = getSampleStyleSheet()
    
    cover_title_style = ParagraphStyle(
        "CoverTitle",
        fontName="Helvetica-Bold",
        fontSize=36,
        leading=44,
        textColor=get_color(style_config["cover_text"]),
        spaceAfter=15,
        alignment=0
    )
    
    cover_sub_style = ParagraphStyle(
        "CoverSub",
        fontName="Helvetica",
        fontSize=18,
        leading=24,
        textColor=get_color(style_config["cover_sub"]),
        spaceAfter=40,
        alignment=0
    )
    
    cover_footer_style = ParagraphStyle(
        "CoverFooter",
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=get_color(style_config["cover_text"]),
        alignment=0
    )
    
    slide_title_style = ParagraphStyle(
        "SlideTitle",
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=get_color(style_config["primary"]),
        spaceAfter=10
    )
    
    slide_desc_style = ParagraphStyle(
        "SlideDesc",
        fontName="Helvetica-Oblique",
        fontSize=10,
        leading=14,
        textColor=get_color(style_config["accent"]),
        spaceAfter=10
    )
    
    slide_body_style = ParagraphStyle(
        "SlideBody",
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=get_color(style_config["text_color"]),
        spaceAfter=6
    )
    
    story = []
    
    # --- 1. MUQOVA SLAYD (Cover page) ---
    story.append(Spacer(1, 100))
    
    indent_style_title = ParagraphStyle("IndentTitle", parent=cover_title_style, leftIndent=80)
    indent_style_sub = ParagraphStyle("IndentSub", parent=cover_sub_style, leftIndent=80)
    indent_style_foot = ParagraphStyle("IndentFoot", parent=cover_footer_style, leftIndent=80)
    
    story.append(Paragraph(data.get('title', 'Taqdimot'), indent_style_title))
    story.append(Paragraph(data.get('subtitle', ''), indent_style_sub))
    story.append(Paragraph(f"Tayyorladi: {author_name}", indent_style_foot))
        
    story.append(PageBreak())
    
    # --- 2. KONTENT SLAYDLAR (Slides 2-10) ---
    slides = data.get("slides", [])
    if len(slides) > 9:
        slides = slides[:9]
        
    for idx, slide in enumerate(slides):
        story.append(Spacer(1, 5))
        story.append(Paragraph(slide.get("title", f"{idx+2}-slayd"), slide_title_style))
        
        desc_text = slide.get("description", "")
        if desc_text:
            if len(desc_text) > 250:
                desc_text = desc_text[:247] + "..."
            story.append(Paragraph(desc_text, slide_desc_style))
            
        points = slide.get("points", [])
        num_points = len(points)
        
        layout_type = slide.get("layout_type", "grid_cards")
        if layout_type not in ["grid_cards", "split_focus", "horizontal_timeline", "quote_highlight"]:
            layout_types = ["grid_cards", "split_focus", "horizontal_timeline", "quote_highlight"]
            layout_type = layout_types[idx % len(layout_types)]
            
        if num_points > 0:
            # 1. GRID CARDS LAYOUT (Neon border box wrapping)
            if layout_type == "grid_cards":
                cell_data = []
                col_widths = []
                
                if num_points <= 2:
                    col_widths = [(doc.pagesize[0] - 120) / 2] * 2
                    row = []
                    for i, pt in enumerate(points):
                        text, icon_type = extract_point_info(pt)
                        icon = get_custom_vector_icon(icon_type, style_config["primary"], style_config["accent"])
                        row.append([
                            icon,
                            Spacer(1, 6),
                            Paragraph(f"<b>0{i+1}.</b> {text}", slide_body_style)
                        ])
                    if num_points == 1:
                        row.append([Paragraph("", slide_body_style)])
                    cell_data.append(row)
                elif num_points == 3:
                    col_widths = [(doc.pagesize[0] - 120) / 3] * 3
                    row = []
                    for i, pt in enumerate(points):
                        text, icon_type = extract_point_info(pt)
                        icon = get_custom_vector_icon(icon_type, style_config["primary"], style_config["accent"])
                        row.append([
                            icon,
                            Spacer(1, 6),
                            Paragraph(f"<b>0{i+1}.</b> {text}", slide_body_style)
                        ])
                    cell_data.append(row)
                else:
                    col_widths = [(doc.pagesize[0] - 120) / 2] * 2
                    row = []
                    for i, pt in enumerate(points):
                        text, icon_type = extract_point_info(pt)
                        icon = get_custom_vector_icon(icon_type, style_config["primary"], style_config["accent"])
                        row.append([
                            icon,
                            Spacer(1, 6),
                            Paragraph(f"<b>0{i+1}.</b> {text}", slide_body_style)
                        ])
                        if len(row) == 2:
                            cell_data.append(row)
                            row = []
                    if row:
                        row.append([Paragraph("", slide_body_style)])
                        cell_data.append(row)
                        
                t_style_list = [
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 12),
                    ('TOPPADDING', (0,0), (-1,-1), 12),
                ]
                for r_idx in range(len(cell_data)):
                    for c_idx in range(len(col_widths)):
                        t_style_list.append(('LEFTPADDING', (c_idx, r_idx), (c_idx, r_idx), 12))
                        t_style_list.append(('RIGHTPADDING', (c_idx, r_idx), (c_idx, r_idx), 12))
                        flat_idx = r_idx * len(col_widths) + c_idx
                        if flat_idx < num_points:
                            # Premium neon box casing design
                            t_style_list.append(('BACKGROUND', (c_idx, r_idx), (c_idx, r_idx), get_color(style_config["accent"] + "0A")))
                            t_style_list.append(('BOX', (c_idx, r_idx), (c_idx, r_idx), 1, get_color(style_config["accent"] + "22")))
                            t_style_list.append(('LINEBEFORE', (c_idx, r_idx), (c_idx, r_idx), 3.5, get_color(style_config["accent"])))
                            
                points_table = Table(cell_data, colWidths=col_widths, style=TableStyle(t_style_list))
                story.append(points_table)

            # 2. SPLIT FOCUS LAYOUT
            elif layout_type == "split_focus":
                w_total = doc.pagesize[0] - 120
                w_left = w_total * 0.35
                w_right = w_total * 0.65
                
                left_icon_type = "star"
                if num_points > 0:
                    _, first_icon = extract_point_info(points[0])
                    if first_icon != "default":
                        left_icon_type = first_icon
                
                left_icon = get_custom_vector_icon(left_icon_type, style_config["primary"], style_config["accent"], size=50)
                
                focus_title_style = ParagraphStyle(
                    f"FocusTitle_{idx}",
                    fontName="Helvetica-Bold",
                    fontSize=15,
                    leading=18,
                    textColor=get_color("#FFFFFF" if style_name in ["sleek_dark", "cyberpunk", "retro_neon", "midnight_gold"] else style_config["cover_text"])
                )
                focus_desc_style = ParagraphStyle(
                    f"FocusDesc_{idx}",
                    fontName="Helvetica",
                    fontSize=10,
                    leading=14,
                    textColor=get_color(style_config["cover_sub"] if style_name in ["sleek_dark", "cyberpunk", "retro_neon", "midnight_gold"] else style_config["primary"])
                )
                
                focus_desc = slide.get("description", "Asosiy xulosalar.")
                if len(focus_desc) > 250:
                    focus_desc = focus_desc[:247] + "..."
                    
                focus_card_content = [
                    Spacer(1, 8),
                    left_icon,
                    Spacer(1, 8),
                    Paragraph("DIQQAT MARKAZIDA", focus_title_style),
                    Spacer(1, 6),
                    Paragraph(focus_desc, focus_desc_style),
                    Spacer(1, 8)
                ]
                
                left_table = Table([[focus_card_content]], colWidths=[w_left - 10])
                left_bg = style_config["primary"] if style_name in ["sleek_dark", "cyberpunk", "retro_neon", "midnight_gold"] else style_config["accent"]
                left_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), get_color(left_bg)),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 12),
                    ('TOPPADDING', (0,0), (-1,-1), 12),
                    ('LEFTPADDING', (0,0), (-1,-1), 12),
                    ('RIGHTPADDING', (0,0), (-1,-1), 12),
                ]))
                
                right_rows = []
                for i, pt in enumerate(points):
                    text, icon_type = extract_point_info(pt)
                    icon = get_custom_vector_icon(icon_type, style_config["primary"], style_config["accent"])
                    point_cell = [
                        icon,
                        Spacer(1, 4),
                        Paragraph(f"<b>0{i+1}.</b> {text}", slide_body_style)
                    ]
                    right_rows.append([point_cell])
                    
                right_table = Table(right_rows, colWidths=[w_right - 10])
                
                r_style_list = [
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                    ('TOPPADDING', (0,0), (-1,-1), 8),
                    ('LEFTPADDING', (0,0), (-1,-1), 12),
                ]
                for r_idx in range(len(right_rows)):
                    r_style_list.append(('BACKGROUND', (0, r_idx), (0, r_idx), get_color(style_config["accent"] + "0A")))
                    r_style_list.append(('BOX', (0, r_idx), (0, r_idx), 1, get_color(style_config["accent"] + "22")))
                    r_style_list.append(('LINEBEFORE', (0, r_idx), (0, r_idx), 3.5, get_color(style_config["accent"])))
                right_table.setStyle(TableStyle(r_style_list))
                
                split_table = Table([[left_table, right_table]], colWidths=[w_left, w_right])
                split_table.setStyle(TableStyle([
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ('LEFTPADDING', (0,0), (-1,-1), 0),
                    ('RIGHTPADDING', (0,0), (-1,-1), 0),
                ]))
                story.append(split_table)

            # 3. HORIZONTAL TIMELINE LAYOUT
            elif layout_type == "horizontal_timeline":
                w_total = doc.pagesize[0] - 120
                col_w = w_total / num_points
                
                row_content = []
                for i, pt in enumerate(points):
                    text, icon_type = extract_point_info(pt)
                    icon = get_custom_vector_icon(icon_type, style_config["primary"], style_config["accent"])
                    
                    step_title_style = ParagraphStyle(
                        f"StepTitle_{idx}_{i}",
                        fontName="Helvetica-Bold",
                        fontSize=10,
                        leading=12,
                        textColor=get_color(style_config["accent"]),
                        alignment=1
                    )
                    
                    step_body_style = ParagraphStyle(
                        f"StepBody_{idx}_{i}",
                        parent=slide_body_style,
                        fontSize=9.5,
                        leading=13.5,
                        alignment=1
                    )
                    
                    cell_flowables = [
                        Paragraph(f"BOSQICH 0{i+1}", step_title_style),
                        Spacer(1, 6),
                        Table([[icon]], colWidths=[36], style=TableStyle([
                            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                            ('LEFTPADDING', (0,0), (-1,-1), 0),
                            ('RIGHTPADDING', (0,0), (-1,-1), 0),
                        ])),
                        Spacer(1, 8),
                        Paragraph(text, step_body_style)
                    ]
                    row_content.append(cell_flowables)
                    
                timeline_table = Table([row_content], colWidths=[col_w]*num_points)
                t_style_list = [
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ('LEFTPADDING', (0,0), (-1,-1), 8),
                    ('RIGHTPADDING', (0,0), (-1,-1), 8),
                    ('TOPPADDING', (0,0), (-1,-1), 10),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 10),
                ]
                for c_idx in range(num_points):
                    t_style_list.append(('BACKGROUND', (c_idx, 0), (c_idx, 0), get_color(style_config["accent"] + "0A")))
                    t_style_list.append(('BOX', (c_idx, 0), (c_idx, 0), 1, get_color(style_config["accent"] + "22")))
                    t_style_list.append(('LINEBEFORE', (c_idx, 0), (c_idx, 0), 3.5, get_color(style_config["accent"])))
                    
                timeline_table.setStyle(TableStyle(t_style_list))
                story.append(timeline_table)

            # 4. QUOTE HIGHLIGHT LAYOUT
            elif layout_type == "quote_highlight":
                w_total = doc.pagesize[0] - 120
                
                takeaway_text = slide.get("description", "Asosiy xulosa kiritilmagan.")
                if len(takeaway_text) > 250:
                    takeaway_text = takeaway_text[:247] + "..."
                    
                quote_text_style = ParagraphStyle(
                    f"QuoteTextStyle_{idx}",
                    fontName="Helvetica-Oblique",
                    fontSize=12,
                    leading=16,
                    textColor=get_color(style_config["primary"]),
                )
                
                quote_icon_type = "idea"
                if num_points > 0:
                    _, first_icon = extract_point_info(points[0])
                    if first_icon != "default":
                        quote_icon_type = first_icon
                quote_icon = get_custom_vector_icon(quote_icon_type, style_config["primary"], style_config["accent"])
                
                quote_table = Table([[[quote_icon, Spacer(1, 4), Paragraph(f"\"{takeaway_text}\"", quote_text_style)]]], colWidths=[w_total])
                quote_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), get_color(style_config["accent"] + "12")),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('LINEBEFORE', (0,0), (0,0), 4, get_color(style_config["accent"])),
                    ('TOPPADDING', (0,0), (-1,-1), 10),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 10),
                    ('LEFTPADDING', (0,0), (-1,-1), 12),
                    ('RIGHTPADDING', (0,0), (-1,-1), 12),
                ]))
                story.append(quote_table)
                story.append(Spacer(1, 12))
                
                col_w = w_total / 2
                left_col = []
                right_col = []
                for i, pt in enumerate(points):
                    text, icon_type = extract_point_info(pt)
                    icon = get_custom_vector_icon(icon_type, style_config["primary"], style_config["accent"])
                    point_flow = [
                        icon,
                        Spacer(1, 4),
                        Paragraph(f"<b>0{i+1}.</b> {text}", slide_body_style)
                    ]
                    if i % 2 == 0:
                        left_col.append(point_flow)
                    else:
                        right_col.append(point_flow)
                        
                if not left_col:
                    left_col.append([Paragraph("", slide_body_style)])
                if not right_col:
                    right_col.append([Paragraph("", slide_body_style)])
                    
                bottom_table = Table([[left_col, right_col]], colWidths=[col_w, col_w])
                bottom_table.setStyle(TableStyle([
                    ('VALIGN', (0,0), (-1,-1), 'TOP'),
                    ('LEFTPADDING', (0,0), (-1,-1), 10),
                    ('RIGHTPADDING', (0,0), (-1,-1), 10),
                    ('TOPPADDING', (0,0), (-1,-1), 6),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                    # Left column card style
                    ('BACKGROUND', (0,0), (0,0), get_color(style_config["accent"] + "0A")),
                    ('BOX', (0,0), (0,0), 1, get_color(style_config["accent"] + "22")),
                    ('LINEBEFORE', (0,0), (0,0), 3.5, get_color(style_config["accent"])),
                    # Right column card style
                    ('BACKGROUND', (1,0), (1,0), get_color(style_config["accent"] + "0A")),
                    ('BOX', (1,0), (1,0), 1, get_color(style_config["accent"] + "22")),
                    ('LINEBEFORE', (1,0), (1,0), 3.5, get_color(style_config["accent"])),
                ]))
                story.append(bottom_table)

        # Add PageBreak unless it's the last page
        if idx < len(slides) - 1:
            story.append(PageBreak())
            
    # Build document
    doc.build(
        story,
        onFirstPage=draw_cover_background,
        onLaterPages=draw_slide_background
    )
    logger.info(f"Presentation PDF successfully built at: {output_path}")
