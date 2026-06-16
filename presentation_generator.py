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
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.graphics.shapes import Drawing, Circle, Rect, Polygon, Line

logger = logging.getLogger(__name__)

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
        "Javobni faqat va faqat JSON formatda qaytar. Boshqa hech qanday izoh yoki kirish so'zlarini yozma. "
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
        "          \"text\": \"Mavzuga oid muhim fakt, tahlil yoki g'oya (1-2 ta tushunarli, aniq gapdan iborat lo'nda tushuntirish, maksimal 150 ta belgi)\",\n"
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
        "4. Har bir nuqtaning 'text' maydonidagi matn 1 ta (maksimal 2 ta) lo'nda, tushunarli va mazmunli gapdan iborat bo'lishi shart (juda uzun bo'lib ketmasin, slaydda chiroyli turishi uchun).\n"
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

def get_custom_vector_icon(icon_type, primary, accent, size=30):
    """Mavzuga oid moslashtirilgan vektor ikonkalarini chizish"""
    d = Drawing(size, size)
    scale = size / 30.0
    
    def s_x(val): return val * scale
    def s_y(val): return val * scale
    
    p_color = HexColor(primary)
    a_color = HexColor(accent)
    w_color = HexColor("#FFFFFF")
    
    d.add(Circle(s_x(15), s_y(15), s_x(14), fillColor=HexColor(accent + "1A"), strokeColor=a_color, strokeWidth=1))
    
    if icon_type == "trend":
        d.add(Rect(s_x(6), s_y(6), s_x(4), s_y(8), fillColor=p_color, strokeColor=None))
        d.add(Rect(s_x(13), s_y(6), s_x(4), s_y(14), fillColor=a_color, strokeColor=None))
        d.add(Rect(s_x(20), s_y(6), s_x(4), s_y(18), fillColor=p_color, strokeColor=None))
        d.add(Line(s_x(5), s_y(8), s_x(25), s_y(24), strokeColor=w_color, strokeWidth=1.5))
        d.add(Line(s_x(20), s_y(24), s_x(25), s_y(24), strokeColor=w_color, strokeWidth=1.5))
        d.add(Line(s_x(25), s_y(19), s_x(25), s_y(24), strokeColor=w_color, strokeWidth=1.5))
        
    elif icon_type == "shield":
        poly = Polygon([s_x(15), s_y(4), s_x(25), s_y(9), s_x(25), s_y(19), s_x(15), s_y(26), s_x(5), s_y(19), s_x(5), s_y(9)], fillColor=a_color, strokeColor=None)
        d.add(poly)
        inner = Polygon([s_x(15), s_y(7), s_x(22), s_y(11), s_x(22), s_y(18), s_x(15), s_y(23), s_x(8), s_y(18), s_x(8), s_y(11)], fillColor=p_color, strokeColor=None)
        d.add(inner)
        d.add(Circle(s_x(15), s_y(15), s_x(3), fillColor=w_color, strokeColor=None))
        
    elif icon_type == "database":
        d.add(Rect(s_x(7), s_y(18), s_x(16), s_y(6), rx=s_x(2), ry=s_y(2), fillColor=a_color, strokeColor=None))
        d.add(Rect(s_x(7), s_y(11), s_x(16), s_y(6), rx=s_x(2), ry=s_y(2), fillColor=p_color, strokeColor=None))
        d.add(Rect(s_x(7), s_y(4), s_x(16), s_y(6), rx=s_x(2), ry=s_y(2), fillColor=a_color, strokeColor=None))
        d.add(Line(s_x(10), s_y(21), s_x(20), s_y(21), strokeColor=w_color, strokeWidth=1))
        d.add(Line(s_x(10), s_y(14), s_x(20), s_y(14), strokeColor=w_color, strokeWidth=1))
        d.add(Line(s_x(10), s_y(7), s_x(20), s_y(7), strokeColor=w_color, strokeWidth=1))
        
    elif icon_type == "user":
        d.add(Circle(s_x(15), s_y(21), s_x(5), fillColor=p_color, strokeColor=None))
        d.add(Polygon([s_x(6), s_y(6), s_x(24), s_y(6), s_x(21), s_y(14), s_x(9), s_y(14)], fillColor=a_color, strokeColor=None))
        d.add(Circle(s_x(15), s_y(10), s_x(2), fillColor=w_color, strokeColor=None))
        
    elif icon_type == "globe":
        d.add(Circle(s_x(15), s_y(15), s_x(10), fillColor=p_color, strokeColor=a_color, strokeWidth=1))
        d.add(Line(s_x(5), s_y(15), s_x(25), s_y(15), strokeColor=w_color, strokeWidth=1))
        d.add(Line(s_x(15), s_y(5), s_x(15), s_y(25), strokeColor=w_color, strokeWidth=1))
        d.add(Circle(s_x(15), s_y(15), s_x(6), fillColor=None, strokeColor=w_color, strokeWidth=0.8))
        
    elif icon_type == "idea":
        d.add(Circle(s_x(15), s_y(18), s_x(7), fillColor=a_color, strokeColor=None))
        d.add(Rect(s_x(12), s_y(7), s_x(6), s_y(6), fillColor=p_color, strokeColor=None))
        d.add(Line(s_x(10), s_y(5), s_x(20), s_y(5), strokeColor=w_color, strokeWidth=1.5))
        d.add(Line(s_x(12), s_y(9), s_x(18), s_y(9), strokeColor=w_color, strokeWidth=1))
        
    elif icon_type == "gear":
        d.add(Circle(s_x(15), s_y(15), s_x(8), fillColor=p_color, strokeColor=None))
        d.add(Circle(s_x(15), s_y(15), s_x(4), fillColor=w_color, strokeColor=None))
        d.add(Line(s_x(15), s_y(4), s_x(15), s_y(26), strokeColor=a_color, strokeWidth=2))
        d.add(Line(s_x(4), s_y(15), s_x(26), s_y(15), strokeColor=a_color, strokeWidth=2))
        d.add(Line(s_x(7), s_y(7), s_x(23), s_y(23), strokeColor=a_color, strokeWidth=2))
        d.add(Line(s_x(7), s_y(23), s_x(23), s_y(7), strokeColor=a_color, strokeWidth=2))
        d.add(Circle(s_x(15), s_y(15), s_x(4), fillColor=w_color, strokeColor=None))
        
    elif icon_type == "lock":
        d.add(Circle(s_x(15), s_y(18), s_x(5), fillColor=None, strokeColor=p_color, strokeWidth=2))
        d.add(Rect(s_x(8), s_y(6), s_x(14), s_y(10), rx=s_x(1.5), ry=s_y(1.5), fillColor=a_color, strokeColor=None))
        d.add(Circle(s_x(15), s_y(11), s_x(1.8), fillColor=w_color, strokeColor=None))
        d.add(Line(s_x(15), s_y(11), s_x(15), s_y(8), strokeColor=w_color, strokeWidth=1.2))
        
    elif icon_type == "chat":
        d.add(Rect(s_x(5), s_y(10), s_x(20), s_y(14), rx=s_x(2.5), ry=s_y(2.5), fillColor=p_color, strokeColor=None))
        d.add(Polygon([s_x(8), s_y(10), s_x(8), s_y(5), s_x(14), s_y(10)], fillColor=p_color, strokeColor=None))
        d.add(Circle(s_x(10), s_y(17), s_x(1.5), fillColor=w_color, strokeColor=None))
        d.add(Circle(s_x(15), s_y(17), s_x(1.5), fillColor=w_color, strokeColor=None))
        d.add(Circle(s_x(20), s_y(17), s_x(1.5), fillColor=w_color, strokeColor=None))
        
    elif icon_type == "star":
        points = [
            s_x(15), s_y(27),
            s_x(18.5), s_y(18),
            s_x(27), s_y(18),
            s_x(20.5), s_y(13),
            s_x(23), s_y(4),
            s_x(15), s_y(10),
            s_x(7), s_y(4),
            s_x(9.5), s_y(13),
            s_x(3), s_y(18),
            s_x(11.5), s_y(18)
        ]
        d.add(Polygon(points, fillColor=a_color, strokeColor=None))
        
    else:
        poly = Polygon([s_x(15), s_y(3), s_x(27), s_y(15), s_x(15), s_y(27), s_x(3), s_y(15)], fillColor=a_color, strokeColor=None)
        d.add(poly)
        d.add(Circle(s_x(15), s_y(15), s_x(5), fillColor=p_color, strokeColor=None))
        d.add(Circle(s_x(15), s_y(15), s_x(2), fillColor=w_color, strokeColor=None))
        
    return d

def get_slide_icon(primary, accent, style_name):
    return get_custom_vector_icon("default", primary, accent)

def draw_tech_illustration(canvas_obj, x, y, primary, accent, style_name):
    """Muqova varag'ida sun'iy intellekt va blockchain mavzusiga oid katta neyro-tarmoq chizmasini chizish"""
    canvas_obj.setFillColor(HexColor(accent))
    canvas_obj.circle(x, y, 90, fill=True, stroke=False)
    
    canvas_obj.setFillColor(HexColor(primary))
    canvas_obj.circle(x, y, 75, fill=True, stroke=False)
    
    line_color = "#FFFFFF" if style_name in ["sleek_dark", "cyberpunk", "retro_neon", "midnight_gold", "corporate_blue", "eco_green", "ocean_breeze", "coffee_cream"] else primary
    canvas_obj.setStrokeColor(HexColor(line_color))
    canvas_obj.setLineWidth(1.2)
    
    canvas_obj.circle(x, y, 45, fill=False, stroke=True)
    canvas_obj.circle(x, y, 20, fill=False, stroke=True)
    
    canvas_obj.line(x - 65, y, x + 65, y)
    canvas_obj.line(x, y - 65, x, y + 65)
    canvas_obj.line(x - 45, y - 45, x + 45, y + 45)
    canvas_obj.line(x - 45, y + 45, x + 45, y - 45)
    
    node_color = "#FFFFFF" if style_name in ["sleek_dark", "cyberpunk", "retro_neon", "midnight_gold"] else accent
    canvas_obj.setFillColor(HexColor(node_color))
    canvas_obj.circle(x - 45, y, 5, fill=True, stroke=False)
    canvas_obj.circle(x + 45, y, 5, fill=True, stroke=False)
    canvas_obj.circle(x, y - 45, 5, fill=True, stroke=False)
    canvas_obj.circle(x, y + 45, 5, fill=True, stroke=False)
    canvas_obj.circle(x - 32, y + 32, 5, fill=True, stroke=False)
    canvas_obj.circle(x + 32, y - 32, 5, fill=True, stroke=False)
    canvas_obj.circle(x - 32, y - 32, 5, fill=True, stroke=False)
    canvas_obj.circle(x + 32, y + 32, 5, fill=True, stroke=False)
    
    canvas_obj.setFillColor(HexColor(accent))
    canvas_obj.circle(x, y, 12, fill=True, stroke=False)
    canvas_obj.setFillColor(HexColor("#FFFFFF"))
    canvas_obj.circle(x, y, 5, fill=True, stroke=False)

# ===== DRAWING HANDLERS FOR REPORTLAB =====

def draw_cover_background(canvas_obj, doc):
    canvas_obj.saveState()
    style = doc.style_config
    
    # Draw background color
    canvas_obj.setFillColor(HexColor(style["cover_bg"]))
    canvas_obj.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=True, stroke=False)
    
    # Draw modern style-specific decorative elements
    canvas_obj.setFillColor(HexColor(style["accent"]))
    
    if doc.style_name in ["corporate_blue", "eco_green", "ocean_breeze", "coffee_cream"]:
        p = canvas_obj.beginPath()
        p.moveTo(0, 0)
        p.lineTo(doc.pagesize[0] * 0.28, 0)
        p.lineTo(doc.pagesize[0] * 0.18, doc.pagesize[1])
        p.lineTo(0, doc.pagesize[1])
        p.close()
        canvas_obj.drawPath(p, fill=True, stroke=False)
        
        canvas_obj.setFillColor(HexColor(style["accent"]))
        canvas_obj.circle(doc.pagesize[0] * 0.9, doc.pagesize[1] * 0.85, 130, fill=True, stroke=False)
        canvas_obj.setFillColor(HexColor(style["cover_bg"]))
        canvas_obj.circle(doc.pagesize[0] * 0.9, doc.pagesize[1] * 0.85, 115, fill=True, stroke=False)

    elif doc.style_name in ["sleek_dark", "midnight_gold", "retro_neon", "cyberpunk"]:
        p = canvas_obj.beginPath()
        p.moveTo(doc.pagesize[0], 0)
        p.lineTo(doc.pagesize[0] * 0.65, 0)
        p.lineTo(doc.pagesize[0], doc.pagesize[1] * 0.5)
        p.close()
        canvas_obj.drawPath(p, fill=True, stroke=False)
        
        canvas_obj.setFillColor(HexColor(style["primary"]))
        p2 = canvas_obj.beginPath()
        p2.moveTo(0, doc.pagesize[1])
        p2.lineTo(doc.pagesize[0] * 0.15, doc.pagesize[1])
        p2.lineTo(0, doc.pagesize[1] * 0.7)
        p2.close()
        canvas_obj.drawPath(p2, fill=True, stroke=False)

    else:
        canvas_obj.setStrokeColor(HexColor(style["accent"]))
        canvas_obj.setLineWidth(3)
        canvas_obj.line(40, 40, 40, doc.pagesize[1] - 40)
        canvas_obj.line(40, doc.pagesize[1] - 40, doc.pagesize[0] - 40, doc.pagesize[1] - 40)
        canvas_obj.setLineWidth(1)
        canvas_obj.line(48, 48, 48, doc.pagesize[1] - 48)
        canvas_obj.line(48, doc.pagesize[1] - 48, doc.pagesize[0] - 48, doc.pagesize[1] - 48)
        
        canvas_obj.setFillColor(HexColor(style["accent"]))
        canvas_obj.circle(doc.pagesize[0] - 80, doc.pagesize[1] - 80, 20, fill=True, stroke=False)
        
    w = doc.pagesize[0] - 120
    panel_w = (w - 20) / 3
    y_pos = 110
    panel_h = 110
    
    canvas_obj.setFillColor(HexColor(style["accent"]))
    canvas_obj.rect(60, y_pos, panel_w, panel_h, fill=True, stroke=False)
    
    canvas_obj.setFillColor(HexColor(style["primary"]))
    canvas_obj.rect(60 + panel_w + 10, y_pos, panel_w, panel_h, fill=True, stroke=False)
    
    panel3_color = style["cover_sub"] if style["cover_sub"] != style["accent"] else style["text_muted"]
    canvas_obj.setFillColor(HexColor(panel3_color))
    canvas_obj.rect(60 + 2 * panel_w + 20, y_pos, panel_w, panel_h, fill=True, stroke=False)
    
    ill_x = doc.pagesize[0] - 170
    ill_y = doc.pagesize[1] * 0.6
    draw_tech_illustration(canvas_obj, ill_x, ill_y, style["primary"], style["accent"], doc.style_name)
        
    canvas_obj.restoreState()

def draw_slide_background(canvas_obj, doc):
    canvas_obj.saveState()
    style = doc.style_config
    page_num = canvas_obj.getPageNumber()
    
    canvas_obj.setFillColor(HexColor(style["slide_bg"]))
    canvas_obj.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=True, stroke=False)
    
    canvas_obj.setFillColor(HexColor(style["accent"]))
    
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
        canvas_obj.setFillColor(HexColor(style["slide_bg"]))
        canvas_obj.circle(doc.pagesize[0] - 20, 20, 34, fill=True, stroke=False)
        
    else:
        canvas_obj.setFillColor(HexColor(style["primary"]))
        canvas_obj.rect(54, doc.pagesize[1] - 40, doc.pagesize[0] - 108, 3, fill=True, stroke=False)
        canvas_obj.setFillColor(HexColor(style["accent"]))
        canvas_obj.rect(54, doc.pagesize[1] - 46, doc.pagesize[0] - 108, 1.5, fill=True, stroke=False)
        
        canvas_obj.circle(30, doc.pagesize[1] - 30, 8, fill=True, stroke=False)

    border_color = "#cbd5e1" if doc.style_name != "sleek_dark" else "#334155"
    canvas_obj.setFillColor(HexColor(border_color))
    canvas_obj.rect(54, 45, doc.pagesize[0] - 108, 1, fill=True, stroke=False)
    
    canvas_obj.setFont("Helvetica", 9)
    canvas_obj.setFillColor(HexColor(style["text_muted"]))
    canvas_obj.drawString(54, 28, doc.topic_title)
    
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
        
    # Xatolik va cheksiz aylanib qolishni oldini olish maqsadida matnni cheklaymiz (180 belgi)
    if len(text) > 180:
        text = text[:177] + "..."
        
    return text, icon_type

# ===== PDF YARATISH LOGIKASI =====

def create_presentation_pdf(data, style_name, output_path, author_name="Taqdimotchi"):
    """Keltirilgan ma'lumotlar asosida 10 varaqalik taqdimot PDF yaratadi"""
    if style_name not in STYLE_TEMPLATES:
        style_name = "corporate_blue"
        
    style_config = STYLE_TEMPLATES[style_name]
    pagesize = landscape(A4)
    
    # Vertikal bo'shliqni ko'proq saqlash uchun top va bottom marginni 55 ga kamaytirdik
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
        textColor=HexColor(style_config["cover_text"]),
        spaceAfter=15,
        alignment=0
    )
    
    cover_sub_style = ParagraphStyle(
        "CoverSub",
        fontName="Helvetica",
        fontSize=18,
        leading=24,
        textColor=HexColor(style_config["cover_sub"]),
        spaceAfter=40,
        alignment=0
    )
    
    cover_footer_style = ParagraphStyle(
        "CoverFooter",
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=HexColor(style_config["cover_text"]),
        alignment=0
    )
    
    # Kichikroq shriftlar yordamida overflow xavfini bartaraf qilamiz
    slide_title_style = ParagraphStyle(
        "SlideTitle",
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=HexColor(style_config["primary"]),
        spaceAfter=10
    )
    
    slide_desc_style = ParagraphStyle(
        "SlideDesc",
        fontName="Helvetica-Oblique",
        fontSize=10,
        leading=14,
        textColor=HexColor(style_config["accent"]),
        spaceAfter=10
    )
    
    slide_body_style = ParagraphStyle(
        "SlideBody",
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        textColor=HexColor(style_config["text_color"]),
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
        
        # Slayd tavsifini cheklash
        desc_text = slide.get("description", "")
        if desc_text:
            if len(desc_text) > 150:
                desc_text = desc_text[:147] + "..."
            story.append(Paragraph(desc_text, slide_desc_style))
            
        points = slide.get("points", [])
        num_points = len(points)
        
        layout_type = slide.get("layout_type", "grid_cards")
        if layout_type not in ["grid_cards", "split_focus", "horizontal_timeline", "quote_highlight"]:
            layout_types = ["grid_cards", "split_focus", "horizontal_timeline", "quote_highlight"]
            layout_type = layout_types[idx % len(layout_types)]
            
        if num_points > 0:
            # 1. GRID CARDS LAYOUT
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
                    ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                    ('TOPPADDING', (0,0), (-1,-1), 4),
                ]
                for r_idx in range(len(cell_data)):
                    for c_idx in range(len(col_widths)):
                        t_style_list.append(('LEFTPADDING', (c_idx, r_idx), (c_idx, r_idx), 10))
                        t_style_list.append(('RIGHTPADDING', (c_idx, r_idx), (c_idx, r_idx), 12))
                        flat_idx = r_idx * len(col_widths) + c_idx
                        if flat_idx < num_points:
                            t_style_list.append(('LINEBEFORE', (c_idx, r_idx), (c_idx, r_idx), 3.5, HexColor(style_config["accent"])))
                            
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
                    textColor=HexColor("#FFFFFF" if style_name in ["sleek_dark", "cyberpunk", "retro_neon", "midnight_gold"] else style_config["cover_text"])
                )
                focus_desc_style = ParagraphStyle(
                    f"FocusDesc_{idx}",
                    fontName="Helvetica",
                    fontSize=10,
                    leading=14,
                    textColor=HexColor(style_config["cover_sub"] if style_name in ["sleek_dark", "cyberpunk", "retro_neon", "midnight_gold"] else style_config["primary"])
                )
                
                focus_desc = slide.get("description", "Asosiy xulosalar.")
                if len(focus_desc) > 150:
                    focus_desc = focus_desc[:147] + "..."
                    
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
                    ('BACKGROUND', (0,0), (-1,-1), HexColor(left_bg)),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 10),
                    ('TOPPADDING', (0,0), (-1,-1), 10),
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
                    ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                    ('TOPPADDING', (0,0), (-1,-1), 6),
                    ('LEFTPADDING', (0,0), (-1,-1), 12),
                ]
                for r_idx in range(len(right_rows)):
                    r_style_list.append(('LINEBEFORE', (0, r_idx), (0, r_idx), 3.5, HexColor(style_config["accent"])))
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
                        textColor=HexColor(style_config["accent"]),
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
                        Table([[icon]], colWidths=[30], style=TableStyle([
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
                    ('LEFTPADDING', (0,0), (-1,-1), 6),
                    ('RIGHTPADDING', (0,0), (-1,-1), 6),
                    ('TOPPADDING', (0,0), (-1,-1), 6),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                ]
                for c_idx in range(1, num_points):
                    t_style_list.append(('LINEBEFORE', (c_idx, 0), (c_idx, 0), 1.5, HexColor(style_config["text_muted"] + "33")))
                timeline_table.setStyle(TableStyle(t_style_list))
                story.append(timeline_table)

            # 4. QUOTE HIGHLIGHT LAYOUT
            elif layout_type == "quote_highlight":
                w_total = doc.pagesize[0] - 120
                
                takeaway_text = slide.get("description", "Asosiy xulosa kiritilmagan.")
                if len(takeaway_text) > 150:
                    takeaway_text = takeaway_text[:147] + "..."
                    
                quote_text_style = ParagraphStyle(
                    f"QuoteTextStyle_{idx}",
                    fontName="Helvetica-Oblique",
                    fontSize=12,
                    leading=16,
                    textColor=HexColor(style_config["primary"]),
                )
                
                quote_icon_type = "idea"
                if num_points > 0:
                    _, first_icon = extract_point_info(points[0])
                    if first_icon != "default":
                        quote_icon_type = first_icon
                quote_icon = get_custom_vector_icon(quote_icon_type, style_config["primary"], style_config["accent"])
                
                quote_table = Table([[[quote_icon, Spacer(1, 4), Paragraph(f"\"{takeaway_text}\"", quote_text_style)]]], colWidths=[w_total])
                quote_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), HexColor(style_config["accent"] + "12")),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                    ('LINEBEFORE', (0,0), (0,0), 4, HexColor(style_config["accent"])),
                    ('TOPPADDING', (0,0), (-1,-1), 8),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 8),
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
                    ('LEFTPADDING', (0,0), (-1,-1), 8),
                    ('RIGHTPADDING', (0,0), (-1,-1), 8),
                    ('TOPPADDING', (0,0), (-1,-1), 4),
                    ('BOTTOMPADDING', (0,0), (-1,-1), 4),
                    ('LINEBEFORE', (0,0), (0,0), 3.5, HexColor(style_config["accent"])),
                    ('LINEBEFORE', (1,0), (1,0), 3.5, HexColor(style_config["accent"])),
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
