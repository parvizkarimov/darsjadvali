import os
import re
import json
import logging
from datetime import datetime
from groq import Groq

# Reportlab imports
from reportlab.lib.pagesizes import landscape, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, KeepTogether, Table, TableStyle
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
        "Sen yuqori malakali ma'ruzachi va taqdimotchi mutaxassissan. "
        f"Mavzu: '{topic}'.\n"
        "Ushbu mavzu bo'yicha slaydlar matnini o'zbek tilida juda batafsil va chuqur tahliliy ma'lumotlar bilan tayyorlab ber. "
        "Taqdimot aniq 10 ta slayddan iborat bo'lishi shart. "
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
        "      \"points\": [\n"
        "        \"Mavzuga oid muhim fakt, tahlil yoki g'oya (shunchaki ibora emas, 2-3 ta to'liq gapdan iborat batafsil tushuntirish)\",\n"
        "        \"Yana bir muhim tushuncha yoki ma'lumot (2-3 ta to'liq gapdan iborat tahlil)\",\n"
        "        \"Ushbu slayd doirasidagi yakuniy xulosa yoki fakt (2-3 ta to'liq gapdan iborat tahlil)\"\n"
        "      ]\n"
        "    },\n"
        "    ... (yana 9 ta slayd)\n"
        "  ]\n"
        "}\n\n"
        "Qoidalarga amal qil:\n"
        "1. Taqdimot mutlaqo yuzaki bo'lmasin, undagi ma'lumotlar hajmi va chuqurligi dars o'tishga, o'rganishga yetarli darajada ko'p va professional bo'lsin.\n"
        "2. Har bir slaydning 'description' maydonida shu slayd uchun kirish/umumiy mohiyatni yorituvchi 1-2 ta to'liq gap yozilsin.\n"
        "3. Har bir slaydda 3 tadan 5 tagacha 'points' (nuqtalar) bo'lishi shart. Har bir nuqta shunchaki qisqa so'zlar emas, balki 2-3 ta gapdan iborat batafsil va boyitilgan tushuntirish matni bo'lishi shart.\n"
        "4. Slaydlar tartibi mantiqiy bo'lsin: Kirish -> Muammo -> Tahlil -> Yechim -> Kelajak -> Xulosa va h.k."
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
    
    # Left stripe/polygon accent (Corporate Blue, Eco Green, Ocean Breeze, Coffee & Cream)
    if doc.style_name in ["corporate_blue", "eco_green", "ocean_breeze", "coffee_cream"]:
        p = canvas_obj.beginPath()
        p.moveTo(0, 0)
        p.lineTo(doc.pagesize[0] * 0.28, 0)
        p.lineTo(doc.pagesize[0] * 0.18, doc.pagesize[1])
        p.lineTo(0, doc.pagesize[1])
        p.close()
        canvas_obj.drawPath(p, fill=True, stroke=False)
        
        # Soft top-right circle
        canvas_obj.setFillColor(HexColor(style["accent"]))
        canvas_obj.circle(doc.pagesize[0] * 0.9, doc.pagesize[1] * 0.85, 130, fill=True, stroke=False)
        canvas_obj.setFillColor(HexColor(style["cover_bg"]))
        canvas_obj.circle(doc.pagesize[0] * 0.9, doc.pagesize[1] * 0.85, 115, fill=True, stroke=False)

    # Glowing cyber/neon triangles (Sleek Dark, Midnight Gold, Retro Neon, Cyberpunk)
    elif doc.style_name in ["sleek_dark", "midnight_gold", "retro_neon", "cyberpunk"]:
        p = canvas_obj.beginPath()
        p.moveTo(doc.pagesize[0], 0)
        p.lineTo(doc.pagesize[0] * 0.65, 0)
        p.lineTo(doc.pagesize[0], doc.pagesize[1] * 0.5)
        p.close()
        canvas_obj.drawPath(p, fill=True, stroke=False)
        
        # Lighter secondary accent
        canvas_obj.setFillColor(HexColor(style["primary"]))
        p2 = canvas_obj.beginPath()
        p2.moveTo(0, doc.pagesize[1])
        p2.lineTo(doc.pagesize[0] * 0.15, doc.pagesize[1])
        p2.lineTo(0, doc.pagesize[1] * 0.7)
        p2.close()
        canvas_obj.drawPath(p2, fill=True, stroke=False)

    # Geometric elegant borders (Warm Minimalist, Sunset Orange, Royal Purple, Cherry Blossom, Nordic Slate, Vintage Sepia)
    else:
        # Double border line for minimalist look
        canvas_obj.setStrokeColor(HexColor(style["accent"]))
        canvas_obj.setLineWidth(3)
        canvas_obj.line(40, 40, 40, doc.pagesize[1] - 40)
        canvas_obj.line(40, doc.pagesize[1] - 40, doc.pagesize[0] - 40, doc.pagesize[1] - 40)
        canvas_obj.setLineWidth(1)
        canvas_obj.line(48, 48, 48, doc.pagesize[1] - 48)
        canvas_obj.line(48, doc.pagesize[1] - 48, doc.pagesize[0] - 48, doc.pagesize[1] - 48)
        
        # Decorative circle in corner
        canvas_obj.setFillColor(HexColor(style["accent"]))
        canvas_obj.circle(doc.pagesize[0] - 80, doc.pagesize[1] - 80, 20, fill=True, stroke=False)
        
    # --- DRAW THE CREATIVE VECTOR GRID BANNER (as seen in Canva samples) ---
    # Draw three styled colored rectangle blocks at the bottom-center of the cover page
    w = doc.pagesize[0] - 120
    panel_w = (w - 20) / 3
    y_pos = 110
    panel_h = 110
    
    # Panel 1 (Accent color)
    canvas_obj.setFillColor(HexColor(style["accent"]))
    canvas_obj.rect(60, y_pos, panel_w, panel_h, fill=True, stroke=False)
    
    # Panel 2 (Primary color)
    canvas_obj.setFillColor(HexColor(style["primary"]))
    canvas_obj.rect(60 + panel_w + 10, y_pos, panel_w, panel_h, fill=True, stroke=False)
    
    # Panel 3 (Muted/Sub color accent)
    panel3_color = style["cover_sub"] if style["cover_sub"] != style["accent"] else style["text_muted"]
    canvas_obj.setFillColor(HexColor(panel3_color))
    canvas_obj.rect(60 + 2 * panel_w + 20, y_pos, panel_w, panel_h, fill=True, stroke=False)
        
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
        alignment=0 if style_name in ["corporate_blue", "eco_green", "ocean_breeze", "coffee_cream"] else 1
    )
    
    cover_sub_style = ParagraphStyle(
        "CoverSub",
        fontName="Helvetica",
        fontSize=18,
        leading=24,
        textColor=HexColor(style_config["cover_sub"]),
        spaceAfter=40,
        alignment=0 if style_name in ["corporate_blue", "eco_green", "ocean_breeze", "coffee_cream"] else 1
    )
    
    cover_footer_style = ParagraphStyle(
        "CoverFooter",
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=HexColor(style_config["cover_text"]),
        alignment=0 if style_name in ["corporate_blue", "eco_green", "ocean_breeze", "coffee_cream"] else 1
    )
    
    # Slide pages styles
    slide_title_style = ParagraphStyle(
        "SlideTitle",
        fontName="Helvetica-Bold",
        fontSize=22,
        leading=26,
        textColor=HexColor(style_config["primary"]),
        spaceAfter=12
    )
    
    slide_desc_style = ParagraphStyle(
        "SlideDesc",
        fontName="Helvetica-Oblique",
        fontSize=11,
        leading=16,
        textColor=HexColor(style_config["accent"]),
        spaceAfter=12
    )
    
    slide_body_style = ParagraphStyle(
        "SlideBody",
        fontName="Helvetica",
        fontSize=11,
        leading=16,
        textColor=HexColor(style_config["text_color"]),
        spaceAfter=10
    )
    
    story = []
    
    # --- 1. MUQOVA SLAYD (Cover page) ---
    # Left indent for left-stripe styles to avoid overlapping with the left decoration shape
    if style_name in ["corporate_blue", "eco_green", "ocean_breeze", "coffee_cream"]:
        story.append(Spacer(1, 100))
        
        # We can add left indent to layout elements
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
        story.append(Spacer(1, 5)) # Small gap from top line
        story.append(Paragraph(slide.get("title", f"{idx+2}-slayd"), slide_title_style))
        
        # Description rendering if present
        if slide.get("description"):
            story.append(Paragraph(slide.get("description"), slide_desc_style))
            
        # Bullet points rendering in a grid/columns layout
        points = slide.get("points", [])
        num_points = len(points)
        
        if num_points > 0:
            cell_data = []
            col_widths = []
            
            # Grid layout logic:
            if num_points <= 2:
                # 2 columns, 1 row
                col_widths = [(doc.pagesize[0] - 120) / 2] * 2
                cell_data = [[Paragraph(f"<b>0{i+1}.</b> {pt}", slide_body_style) for i, pt in enumerate(points)]]
                if num_points == 1:
                    cell_data[0].append(Paragraph("", slide_body_style))
            elif num_points == 3:
                # 3 columns, 1 row
                col_widths = [(doc.pagesize[0] - 120) / 3] * 3
                cell_data = [[Paragraph(f"<b>0{i+1}.</b> {pt}", slide_body_style) for i, pt in enumerate(points)]]
            else:
                # 4 or more points: 2 columns, dynamic rows
                col_widths = [(doc.pagesize[0] - 120) / 2] * 2
                row = []
                for i, pt in enumerate(points):
                    row.append(Paragraph(f"<b>0{i+1}.</b> {pt}", slide_body_style))
                    if len(row) == 2:
                        cell_data.append(row)
                        row = []
                if row:
                    row.append(Paragraph("", slide_body_style))
                    cell_data.append(row)
                    
            # Define table style
            t_style_list = [
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('BOTTOMPADDING', (0,0), (-1,-1), 10),
                ('TOPPADDING', (0,0), (-1,-1), 8),
            ]
            
            # Add left border accent and padding to each cell
            for r_idx in range(len(cell_data)):
                for c_idx in range(len(col_widths)):
                    t_style_list.append(('LEFTPADDING', (c_idx, r_idx), (c_idx, r_idx), 10))
                    t_style_list.append(('RIGHTPADDING', (c_idx, r_idx), (c_idx, r_idx), 12))
                    
                    flat_idx = r_idx * len(col_widths) + c_idx
                    if flat_idx < num_points:
                        t_style_list.append(('LINEBEFORE', (c_idx, r_idx), (c_idx, r_idx), 3.5, HexColor(style_config["accent"])))
                        
            points_table = Table(cell_data, colWidths=col_widths, style=TableStyle(t_style_list))
            story.append(points_table)
            
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
