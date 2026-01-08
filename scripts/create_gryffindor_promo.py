#!/usr/bin/env python3
"""Create special Gryffindor promo PDF with VNVNC branding - fixed layout."""

import json
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Register fonts
pdfmetrics.registerFont(TTFont('ArialUnicode', '/System/Library/Fonts/Supplemental/Arial Unicode.ttf'))
pdfmetrics.registerFont(TTFont('ArialBold', '/System/Library/Fonts/Supplemental/Arial Bold.ttf'))
pdfmetrics.registerFont(TTFont('ArialItalic', '/System/Library/Fonts/Supplemental/Arial Italic.ttf'))

# Colors
BURGUNDY = HexColor("#740001")
GOLD = HexColor("#D4AF37")
LIGHT_GOLD = HexColor("#F4E4BA")
CREAM = HexColor("#FDF8F0")
DARK_BROWN = HexColor("#2C1810")
SLYTHERIN_GREEN = HexColor("#1A472A")
RAVENCLAW_BLUE = HexColor("#0E1A40")

IMAGES_DIR = Path("/Users/kirniy/Downloads/sorting_hat")
OUTPUT_PATH = IMAGES_DIR / "ГРИФФИНДОР_АКЦИЯ.pdf"

def load_gryffindor_images():
    with open(IMAGES_DIR / "sorting_hat_final_results.json") as f:
        results = json.load(f)
    return sorted([r["file"] for r in results["all_results"] if r["house"] == "Gryffindor"])

def create_promo_pdf():
    image_files = load_gryffindor_images()

    # Custom 4:5 aspect ratio (like Instagram) - 200mm x 250mm
    page_width = 200*mm
    page_height = 250*mm
    
    c = canvas.Canvas(str(OUTPUT_PATH), pagesize=(page_width, page_height))
    width, height = page_width, page_height

    # Layout settings for image pages
    margin = 15*mm
    img_size = 55*mm
    cols = 3
    rows = 4
    images_per_page = cols * rows
    h_spacing = (width - 2*margin - cols*img_size) / (cols - 1)
    v_spacing = 8*mm

    total_pages = (len(image_files) + images_per_page - 1) // images_per_page + 1

    def draw_header_bar():
        c.setFillColor(BURGUNDY)
        c.rect(0, height - 35*mm, width, 35*mm, fill=True, stroke=False)
        c.setFillColor(GOLD)
        c.rect(0, height - 37*mm, width, 2*mm, fill=True, stroke=False)
        c.setFillColor(HexColor("#FFFFFF"))
        c.setFont("ArialBold", 24)
        c.drawCentredString(width/2, height - 20*mm, "ГРИФФИНДОР")
        c.setFont("ArialUnicode", 10)
        c.drawCentredString(width/2, height - 30*mm, "Platform 9¾ • VNVNC • 6-7 января 2026")

    def draw_footer_bar(page_num):
        c.setFillColor(BURGUNDY)
        c.rect(0, 0, width, 18*mm, fill=True, stroke=False)
        c.setFillColor(GOLD)
        c.rect(0, 18*mm, width, 2*mm, fill=True, stroke=False)
        c.setFillColor(HexColor("#FFFFFF"))
        c.setFont("ArialUnicode", 9)
        c.drawCentredString(width/2, 8*mm, f"VNVNC.RU • Конюшенная площадь 2В • Страница {page_num} из {total_pages}")

    # === COVER PAGE ===
    c.setFillColor(CREAM)
    c.rect(0, 0, width, height, fill=True, stroke=False)

    # Decorative border
    c.setStrokeColor(GOLD)
    c.setLineWidth(3)
    c.roundRect(8*mm, 8*mm, width - 16*mm, height - 16*mm, 3, fill=False, stroke=True)
    c.setLineWidth(1)
    c.roundRect(11*mm, 11*mm, width - 22*mm, height - 22*mm, 2, fill=False, stroke=True)

    # ===== FIXED LAYOUT - Using absolute Y positions from top =====
    
    # Stars at top
    c.setFillColor(GOLD)
    c.setFont("ArialUnicode", 12)
    for i in range(7):
        c.drawCentredString(width/2 - 45*mm + i*15*mm, height - 20*mm, "✦")

    # Main header banner (Y: 28mm to 68mm from top)
    banner_top = height - 28*mm
    banner_height = 40*mm
    c.setFillColor(BURGUNDY)
    c.roundRect(20*mm, banner_top - banner_height, width - 40*mm, banner_height, 5, fill=True, stroke=False)

    c.setStrokeColor(GOLD)
    c.setLineWidth(2)
    c.roundRect(22*mm, banner_top - banner_height + 2*mm, width - 44*mm, banner_height - 4*mm, 3, fill=False, stroke=True)

    c.setFillColor(GOLD)
    c.setFont("ArialBold", 28)
    c.drawCentredString(width/2, banner_top - 14*mm, "ГРИФФИНДОР")

    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("ArialBold", 13)
    c.drawCentredString(width/2, banner_top - 26*mm, "ПОБЕЖДАЕТ В КУБКЕ ДОМОВ!")

    c.setFont("ArialUnicode", 9)
    c.drawCentredString(width/2, banner_top - 36*mm, "Platform 9¾ • 6-7 января 2026")

    # Dumbledore quote box (Y: 74mm to 96mm from top)
    quote_top = height - 74*mm
    quote_height = 22*mm
    c.setFillColor(LIGHT_GOLD)
    c.roundRect(22*mm, quote_top - quote_height, width - 44*mm, quote_height, 4, fill=True, stroke=False)

    c.setFillColor(DARK_BROWN)
    c.setFont("ArialItalic", 8)
    c.drawCentredString(width/2, quote_top - 7*mm, "«Ещё один год позади! Кубок школы необходимо вручить.")
    c.drawCentredString(width/2, quote_top - 13*mm, "По результатам Распределяющей Шляпы победитель — Гриффиндор!»")
    c.setFont("ArialUnicode", 7)
    c.drawCentredString(width/2, quote_top - 19*mm, "— Профессор Дамблдор")

    # Big stats section (Y: 115mm to 155mm from top) - MOVED DOWN
    stats_top = height - 115*mm
    
    c.setFillColor(BURGUNDY)
    c.setFont("ArialBold", 52)
    c.drawCentredString(width/2, stats_top, "72")

    c.setFont("ArialUnicode", 12)
    c.drawCentredString(width/2, stats_top - 14*mm, "студента в Гриффиндоре")

    c.setFillColor(GOLD)
    c.setFont("ArialBold", 15)
    c.drawCentredString(width/2, stats_top - 28*mm, "32.4% — ЛУЧШИЙ РЕЗУЛЬТАТ!")

    # Other houses header (Y: 158mm from top)
    houses_label_y = height - 158*mm
    c.setFillColor(DARK_BROWN)
    c.setFont("ArialBold", 9)
    c.drawCentredString(width/2, houses_label_y, "РЕЗУЛЬТАТЫ ВСЕХ ФАКУЛЬТЕТОВ:")

    # House stats boxes (Y: 166mm to 188mm from top)
    boxes_top = height - 166*mm
    box_width = 38*mm
    box_height = 22*mm
    gap = 4*mm
    total_box_width = 4 * box_width + 3 * gap
    start_x = (width - total_box_width) / 2

    houses = [
        ("ГРИФФИНДОР", "72", "32.4%", BURGUNDY, True),
        ("СЛИЗЕРИН", "56", "25.2%", SLYTHERIN_GREEN, False),
        ("ПУФФЕНДУЙ", "48", "21.6%", HexColor("#372E29"), False),
        ("КОГТЕВРАН", "46", "20.7%", RAVENCLAW_BLUE, False),
    ]

    for i, (name, count, pct, color, highlight) in enumerate(houses):
        x = start_x + i * (box_width + gap)
        c.setFillColor(color)
        c.roundRect(x, boxes_top - box_height, box_width, box_height, 3, fill=True, stroke=False)

        if highlight:
            c.setStrokeColor(GOLD)
            c.setLineWidth(2)
            c.roundRect(x, boxes_top - box_height, box_width, box_height, 3, fill=False, stroke=True)
            c.setFillColor(GOLD)
        else:
            c.setFillColor(HexColor("#FFFFFF"))

        c.setFont("ArialBold", 6)
        c.drawCentredString(x + box_width/2, boxes_top - 5*mm, name)

        c.setFillColor(HexColor("#FFFFFF"))
        c.setFont("ArialBold", 14)
        c.drawCentredString(x + box_width/2, boxes_top - 13*mm, count)
        c.setFont("ArialUnicode", 6)
        c.drawCentredString(x + box_width/2, boxes_top - 19*mm, pct)

    # Total participants (Y: 194mm from top)
    total_y = height - 194*mm
    c.setFillColor(DARK_BROWN)
    c.setFont("ArialUnicode", 9)
    c.drawCentredString(width/2, total_y, "Всего участников: 222")

    # Promo box (Y: 204mm to 250mm from top)
    promo_top = height - 204*mm
    promo_height = 46*mm
    c.setFillColor(BURGUNDY)
    c.roundRect(18*mm, promo_top - promo_height, width - 36*mm, promo_height, 5, fill=True, stroke=False)

    c.setStrokeColor(GOLD)
    c.setLineWidth(2)
    c.roundRect(20*mm, promo_top - promo_height + 2*mm, width - 40*mm, promo_height - 4*mm, 4, fill=False, stroke=True)

    c.setFillColor(GOLD)
    c.setFont("ArialBold", 14)
    c.drawCentredString(width/2, promo_top - 10*mm, "БЕСПЛАТНЫЙ ШОТ ДЛЯ ГРИФФИНДОРЦЕВ!")

    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("ArialUnicode", 9)
    c.drawCentredString(width/2, promo_top - 20*mm, "Найди себя в этих картинках,")
    c.drawCentredString(width/2, promo_top - 28*mm, "покажи своё фото бармену и получи бесплатный шот!")

    c.setFillColor(GOLD)
    c.setFont("ArialBold", 11)
    c.drawCentredString(width/2, promo_top - 40*mm, "⚡ ТОЛЬКО СЕГОДНЯ — 8 ЯНВАРЯ! ⚡")

    # VNVNC branding box (Y: 258mm to 282mm from top)
    brand_top = height - 258*mm
    brand_height = 24*mm
    c.setFillColor(DARK_BROWN)
    c.roundRect(35*mm, brand_top - brand_height, width - 70*mm, brand_height, 4, fill=True, stroke=False)

    c.setFillColor(GOLD)
    c.setFont("ArialBold", 18)
    c.drawCentredString(width/2, brand_top - 8*mm, "VNVNC")

    c.setFillColor(HexColor("#FFFFFF"))
    c.setFont("ArialUnicode", 8)
    c.drawCentredString(width/2, brand_top - 16*mm, "Конюшенная площадь 2В • VNVNC.RU")

    c.setFont("ArialUnicode", 7)
    c.drawCentredString(width/2, brand_top - 22*mm, "18+ • 23:00 — 07:00 • FC/DC")

    c.showPage()

    # === IMAGE PAGES ===
    for page_idx in range((len(image_files) + images_per_page - 1) // images_per_page):
        c.setFillColor(CREAM)
        c.rect(0, 0, width, height, fill=True, stroke=False)

        draw_header_bar()
        draw_footer_bar(page_idx + 2)

        start_idx = page_idx * images_per_page
        page_images = image_files[start_idx:start_idx + images_per_page]
        start_y = height - 45*mm

        for i, img_file in enumerate(page_images):
            row = i // cols
            col = i % cols
            x = margin + col * (img_size + h_spacing)
            img_y = start_y - row * (img_size + v_spacing) - img_size

            img_path = IMAGES_DIR / img_file
            if img_path.exists():
                try:
                    c.setStrokeColor(GOLD)
                    c.setLineWidth(2)
                    c.rect(x - 2, img_y - 2, img_size + 4, img_size + 4, fill=False, stroke=True)
                    c.drawImage(str(img_path), x, img_y, img_size, img_size, preserveAspectRatio=True)
                except Exception as e:
                    print(f"  Error: {img_file}: {e}")

        c.showPage()

    c.save()
    print(f"✅ Created: {OUTPUT_PATH}")

if __name__ == "__main__":
    print("🦁 Creating Gryffindor promo PDF...\n")
    create_promo_pdf()
    print("\n✨ Done!")
