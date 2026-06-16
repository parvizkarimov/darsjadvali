import os
import re
import json
import logging
from datetime import datetime
from groq import Groq

# Reportlab imports
from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas

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
    }
}

def normalize_uzbek_text(text):
    """Uzbek tilidagi maxsus belgilarni Helvetica qo'llab-quvvatlaydigan formatga o'tkazish"""
    if not text:
        return ""
    
    # 1. Uzbek harflari o'zgarishi (ʻ va ʼ harflarini oddiy apostrofga almashtiramiz)
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
        
    # 2. Markdown qalin va og'ma matnlarini Reportlab HTML-ga o'tkazish
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
        "Sen malakali taqdimotchi va mutaxassissan. "
        f"Mavzu: '{topic}'.\n"
        "Ushbu mavzu bo'yicha slaydlar matnini o'zbek tilida tayyorlab ber. "
        "Taqdimot aniq 10 ta slayddan iborat bo'lishi shart. "
        "Javobni faqat va faqat JSON formatda qaytar. Boshqa hech qanday izoh yoki kirish so'zlarini yozma. "
        "JSON formati quyidagi ko'rinishda bo'lishi shart:\n"
        "{\n"
        "  \"title\": \"Taqdimotning bosh sarlavhasi (Mavzuni to'liq yorituvchi)\",\n"
        "  \"subtitle\": \"Qisqa va qiziqarli tag-sarlavha\",\n"
        "  \"slides\": [\n"
        "    {\n"
        "      \"slide_number\": 1,\n"
        "      \"title\": \"Slayd sarlavhasi (masalan, Kirish yoki Reja)\",\n"
        "      \"points\": [\n"
        "        \"Mavzuga oid muhim fakt yoki g'oya\",\n"
        "        \"Yana bir muhim tushuncha yoki ma'lumot\",\n"
        "        \"Mavzuning dastlabki tahlili (dars uchun foydali)\"\n"
        "      ]\n"
        "    },\n"
        "    ... (yana 9 ta slayd)\n"
        "  ]\n"
        "}\n\n"
        "Qoidalarga amal qil:\n"
        "1. Har bir slayd sarlavhasi va nuqtalari qisqa, tushunarli va 2-3 qatorlik gaplardan iborat bo'lsin.\n"
        "2. Har bir slaydda 3 tadan 5 tagacha nuqtalar (points) bo'lishi shart.\n"
        "3. Slaydlar tartibi mantiqiy bo'lsin: Kirish -> Muammo -> Tahlil -> Yechim -> Kelajak -> Xulosa va h.k."
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
            max_tokens=2048,
            response_format={"type": "json_object"}
        )
        content_str = response.choices[0].message.content
        logger.info(f"Groq API response raw length: {len(content_str)}")
        
        # JSON parsing
        data = json.loads(content_str)
        # Matnlarni tozalash (apostroflarni to'g'rilash)
        cleaned_data = clean_data_recursively(data)
        
        return cleaned_data
    except Exception as e:
        logger.error(f"Failed to generate presentation via Groq: {e}")
        raise e

# ===== DRAWING HANDLERS FOR REPORTLAB =====

def draw_cover_background(canvas_obj, doc):
    canvas_obj.saveState()
    style = doc.style_config
    
    # Draw background color
    canvas_obj.setFillColor(HexColor(style["cover_bg"]))
    canvas_obj.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=True, stroke=False)
    
    # Draw modern style-specific decorative elements
    canvas_obj.setFillColor(HexColor(style["accent"]))
    if doc.style_name == "corporate_blue":
        # Draw a beautiful polygon/stripe on the left
        p = canvas_obj.beginPath()
        p.moveTo(0, 0)
        p.lineTo(doc.pagesize[0] * 0.28, 0)
        p.lineTo(doc.pagesize[0] * 0.18, doc.pagesize[1])
        p.lineTo(0, doc.pagesize[1])
        p.close()
        canvas_obj.drawPath(p, fill=True, stroke=False)
        
        # Floating background circles
        canvas_obj.setFillColor(HexColor("#3b82f6")) # soft accent
        canvas_obj.circle(doc.pagesize[0] * 0.9, doc.pagesize[1] * 0.85, 130, fill=True, stroke=False)
        canvas_obj.setFillColor(HexColor(style["cover_bg"]))
        canvas_obj.circle(doc.pagesize[0] * 0.9, doc.pagesize[1] * 0.85, 115, fill=True, stroke=False)
        
    elif doc.style_name == "sleek_dark":
        # Elegant geometric lines and triangles
        p = canvas_obj.beginPath()
        p.moveTo(doc.pagesize[0], 0)
        p.lineTo(doc.pagesize[0] * 0.65, 0)
        p.lineTo(doc.pagesize[0], doc.pagesize[1] * 0.5)
        p.close()
        canvas_obj.drawPath(p, fill=True, stroke=False)
        
        canvas_obj.setFillColor(HexColor("#4c1d95")) # dark purple accent
        p2 = canvas_obj.beginPath()
        p2.moveTo(0, doc.pagesize[1])
        p2.lineTo(doc.pagesize[0] * 0.15, doc.pagesize[1])
        p2.lineTo(0, doc.pagesize[1] * 0.7)
        p2.close()
        canvas_obj.drawPath(p2, fill=True, stroke=False)
        
    elif doc.style_name == "warm_minimalist":
        # Double border line for minimalist look
        canvas_obj.setStrokeColor(HexColor(style["accent"]))
        canvas_obj.setLineWidth(3)
        canvas_obj.line(40, 40, 40, doc.pagesize[1] - 40)
        canvas_obj.line(40, doc.pagesize[1] - 40, doc.pagesize[0] - 40, doc.pagesize[1] - 40)
        canvas_obj.setLineWidth(1)
        canvas_obj.line(48, 48, 48, doc.pagesize[1] - 48)
        canvas_obj.line(48, doc.pagesize[1] - 48, doc.pagesize[0] - 48, doc.pagesize[1] - 48)
        
    elif doc.style_name == "eco_green":
        # Forest organic green vibes
        p = canvas_obj.beginPath()
        p.moveTo(0, 0)
        p.lineTo(doc.pagesize[0] * 0.35, 0)
        p.lineTo(0, doc.pagesize[1] * 0.5)
        p.close()
        canvas_obj.drawPath(p, fill=True, stroke=False)
        
        canvas_obj.setFillColor(HexColor("#34d399")) # Mint accent
        canvas_obj.circle(doc.pagesize[0] * 0.92, doc.pagesize[1] * 0.88, 100, fill=True, stroke=False)
        canvas_obj.setFillColor(HexColor(style["cover_bg"]))
        canvas_obj.circle(doc.pagesize[0] * 0.92, doc.pagesize[1] * 0.88, 90, fill=True, stroke=False)
        
    canvas_obj.restoreState()

def draw_slide_background(canvas_obj, doc):
    canvas_obj.saveState()
    style = doc.style_config
    
    # Draw slide background
    canvas_obj.setFillColor(HexColor(style["slide_bg"]))
    canvas_obj.rect(0, 0, doc.pagesize[0], doc.pagesize[1], fill=True, stroke=False)
    
    # Draw top header accent border line
    canvas_obj.setFillColor(HexColor(style["primary"]))
    canvas_obj.rect(54, doc.pagesize[1] - 40, doc.pagesize[0] - 108, 4, fill=True, stroke=False)
    
    # Draw bottom footer line
    border_color = "#cbd5e1" if doc.style_name != "sleek_dark" else "#334155"
    canvas_obj.setFillColor(HexColor(border_color))
    canvas_obj.rect(54, 45, doc.pagesize[0] - 108, 1, fill=True, stroke=False)
    
    # Draw footer metadata
    canvas_obj.setFont("Helvetica", 9)
    canvas_obj.setFillColor(HexColor(style["text_muted"]))
    canvas_obj.drawString(54, 28, doc.topic_title)
    
    # Draw page number (current page of total 10)
    canvas_obj.drawRightString(doc.pagesize[0] - 54, 28, f"{doc.page} / 10")
    
    canvas_obj.restoreState()

# ===== PDF YARATISH LOGIKASI =====

def create_presentation_pdf(data, style_name, output_path):
    """Keltirilgan ma'lumotlar asosida 10 varaqalik taqdimot PDF yaratadi"""
    if style_name not in STYLE_TEMPLATES:
        style_name = "corporate_blue"
        
    style_config = STYLE_TEMPLATES[style_name]
    
    # Landscape A4 format: 841.89 x 595.27 points
    pagesize = landscape(A4)
    width, height = pagesize
    
    # Doc template creation with custom margins
    # margins leave enough space for custom header and footer lines
    doc = SimpleDocTemplate(
        output_path,
        pagesize=pagesize,
        leftMargin=60,
        rightMargin=60,
        topMargin=80,
        bottomMargin=80
    )
    
    # Attach data to doc so the canvas callbacks can access them
    doc.style_name = style_name
    doc.style_config = style_config
    doc.topic_title = data.get("title", "Taqdimot")
    
    # Styles definition
    styles = getSampleStyleSheet()
    
    # Cover page styles
    cover_title_style = ParagraphStyle(
        "CoverTitle",
        fontName="Helvetica-Bold",
        fontSize=36,
        leading=44,
        textColor=HexColor(style_config["cover_text"]),
        spaceAfter=15,
        alignment=0 if style_name == "corporate_blue" else 1 # corporate is left-aligned due to left stripe, others centered
    )
    
    cover_sub_style = ParagraphStyle(
        "CoverSub",
        fontName="Helvetica",
        fontSize=18,
        leading=24,
        textColor=HexColor(style_config["cover_sub"]),
        spaceAfter=40,
        alignment=0 if style_name == "corporate_blue" else 1
    )
    
    cover_footer_style = ParagraphStyle(
        "CoverFooter",
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=HexColor(style_config["cover_text"]),
        alignment=0 if style_name == "corporate_blue" else 1
    )
    
    # Slide pages styles
    slide_title_style = ParagraphStyle(
        "SlideTitle",
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=30,
        textColor=HexColor(style_config["primary"]),
        spaceAfter=25
    )
    
    slide_body_style = ParagraphStyle(
        "SlideBody",
        fontName="Helvetica",
        fontSize=14,
        leading=22,
        textColor=HexColor(style_config["text_color"]),
        spaceAfter=15
    )
    
    story = []
    
    # --- 1. MUQOVA SLAYD (Cover page) ---
    # Left indent for Corporate Blue style to avoid overlapping with the left decoration stripe
    if style_name == "corporate_blue":
        story.append(Spacer(1, 100))
        # Wrap in a flowable list to add indentation
        title_para = Paragraph(f"<font color='white'>{data.get('title', 'Taqdimot')}</font>", cover_title_style)
        sub_para = Paragraph(data.get('subtitle', ''), cover_sub_style)
        footer_para = Paragraph("3-kurs Finance (FINP-S-1323U) | AI Yordamchi", cover_footer_style)
        
        # We can add left indent to corporate blue layout elements
        indent_style_title = ParagraphStyle("IndentTitle", parent=cover_title_style, leftIndent=80)
        indent_style_sub = ParagraphStyle("IndentSub", parent=cover_sub_style, leftIndent=80)
        indent_style_foot = ParagraphStyle("IndentFoot", parent=cover_footer_style, leftIndent=80)
        
        story.append(Paragraph(data.get('title', 'Taqdimot'), indent_style_title))
        story.append(Paragraph(data.get('subtitle', ''), indent_style_sub))
        story.append(Paragraph("Dars Jadvali Bot orqali tayyorlandi", indent_style_foot))
    else:
        story.append(Spacer(1, 120))
        story.append(Paragraph(data.get('title', 'Taqdimot'), cover_title_style))
        story.append(Paragraph(data.get('subtitle', ''), cover_sub_style))
        story.append(Paragraph("Dars Jadvali Bot orqali tayyorlandi", cover_footer_style))
        
    story.append(PageBreak())
    
    # --- 2. KONTENT SLAYDLAR (Slides 2-10) ---
    # Ensure there are exactly 9 content slides to reach total 10 slides
    slides = data.get("slides", [])
    if len(slides) > 9:
        slides = slides[:9]
        
    for idx, slide in enumerate(slides):
        story.append(Spacer(1, 10)) # Small gap from top line
        story.append(Paragraph(slide.get("title", f"{idx+2}-slayd"), slide_title_style))
        
        # Bullet points rendering
        for pt in slide.get("points", []):
            bullet_html = f"• {pt}"
            story.append(Paragraph(bullet_html, slide_body_style))
            
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
