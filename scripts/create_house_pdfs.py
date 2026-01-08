#!/usr/bin/env python3
"""Create Harry Potter themed PDFs for each Hogwarts house with Cyrillic support."""

import json
from pathlib import Path
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, Color
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Register fonts with Cyrillic support
FONT_PATH = "/System/Library/Fonts/Supplemental/Arial Unicode.ttf"
FONT_BOLD_PATH = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"

pdfmetrics.registerFont(TTFont('ArialUnicode', FONT_PATH))
pdfmetrics.registerFont(TTFont('ArialBold', FONT_BOLD_PATH))

# House configurations with colors and Russian names
HOUSES = {
    "Gryffindor": {
        "name_ru": "ГРИФФИНДОР",
        "animal_ru": "ЛЕВ",
        "animal_emoji": "🦁",
        "promo_ru": "БЕСПЛАТНЫЙ ШОТ ДЛЯ ГРИФФИНДОРЦЕВ!",
        "primary": "#740001",
        "secondary": "#D3A625",
        "traits_ru": "Храбрость • Отвага • Благородство • Решительность"
    },
    "Slytherin": {
        "name_ru": "СЛИЗЕРИН",
        "animal_ru": "ЗМЕЯ",
        "animal_emoji": "🐍",
        "promo_ru": "БЕСПЛАТНЫЙ ШОТ ДЛЯ СЛИЗЕРИНЦЕВ!",
        "primary": "#1A472A",
        "secondary": "#5D5D5D",
        "traits_ru": "Амбиции • Хитрость • Находчивость • Лидерство"
    },
    "Ravenclaw": {
        "name_ru": "КОГТЕВРАН",
        "animal_ru": "ОРЁЛ",
        "animal_emoji": "🦅",
        "promo_ru": "БЕСПЛАТНЫЙ ШОТ ДЛЯ КОГТЕВРАНЦЕВ!",
        "primary": "#0E1A40",
        "secondary": "#946B2D",
        "traits_ru": "Мудрость • Остроумие • Творчество • Оригинальность"
    },
    "Hufflepuff": {
        "name_ru": "ПУФФЕНДУЙ",
        "animal_ru": "БАРСУК",
        "animal_emoji": "🦡",
        "promo_ru": "БЕСПЛАТНЫЙ ШОТ ДЛЯ ПУФФЕНДУЙЦЕВ!",
        "primary": "#372E29",
        "secondary": "#FFDB00",
        "traits_ru": "Верность • Трудолюбие • Терпение • Справедливость"
    }
}

IMAGES_DIR = Path("/Users/kirniy/Downloads/sorting_hat")
OUTPUT_DIR = Path("/Users/kirniy/Downloads/sorting_hat")

def load_results():
    with open(IMAGES_DIR / "sorting_hat_final_results.json") as f:
        return json.load(f)

def get_images_by_house(results):
    by_house = {house: [] for house in HOUSES}
    for r in results["all_results"]:
        house = r["house"]
        if house in by_house:
            by_house[house].append(r["file"])
    return by_house

def get_all_house_counts(results):
    """Get counts for all houses for comparison display."""
    counts = {house: 0 for house in HOUSES}
    for r in results["all_results"]:
        house = r["house"]
        if house in counts:
            counts[house] += 1
    return counts

def create_house_pdf(house_name, image_files, total_all, all_counts):
    config = HOUSES[house_name]
    output_path = OUTPUT_DIR / f"{config['name_ru']}.pdf"

    c = canvas.Canvas(str(output_path), pagesize=A4)
    width, height = A4

    primary = HexColor(config["primary"])
    secondary = HexColor(config["secondary"])

    def draw_header(page_num, total_pages):
        # Top border
        c.setFillColor(primary)
        c.rect(0, height - 35*mm, width, 35*mm, fill=True, stroke=False)

        # Accent line
        c.setFillColor(secondary)
        c.rect(0, height - 37*mm, width, 2*mm, fill=True, stroke=False)

        # House name
        c.setFillColor(HexColor("#FFFFFF"))
        c.setFont("ArialBold", 28)
        c.drawCentredString(width/2, height - 22*mm, config["name_ru"])

        # Page number
        c.setFillColor(primary)
        c.setFont("ArialUnicode", 10)
        c.drawCentredString(width/2, 10*mm, f"Страница {page_num} из {total_pages}")

    def draw_footer():
        c.setFillColor(primary)
        c.rect(0, 0, width, 20*mm, fill=True, stroke=False)
        c.setFillColor(secondary)
        c.rect(0, 20*mm, width, 2*mm, fill=True, stroke=False)

    def draw_promo_footer():
        """Draw promotional footer with free shot offer."""
        footer_height = 70*mm
        
        # Dark background
        c.setFillColor(primary)
        c.rect(0, 0, width, footer_height, fill=True, stroke=False)
        
        # Accent line at top
        c.setFillColor(secondary)
        c.rect(0, footer_height, width, 2*mm, fill=True, stroke=False)
        
        # Promo text (main)
        c.setFillColor(secondary)
        c.setFont("ArialBold", 18)
        c.drawCentredString(width/2, footer_height - 18*mm, config["promo_ru"])
        
        # Instructions
        c.setFillColor(HexColor("#FFFFFF"))
        c.setFont("ArialUnicode", 11)
        c.drawCentredString(width/2, footer_height - 32*mm, "Найди себя на фотографиях в этом PDF,")
        c.drawCentredString(width/2, footer_height - 40*mm, "покажи своё фото бармену и получи бесплатный шот!")
        
        # VNVNC branding
        c.setFont("ArialBold", 24)
        c.drawCentredString(width/2, footer_height - 55*mm, "VNVNC")
        
        # Address and info
        c.setFont("ArialUnicode", 9)
        c.drawCentredString(width/2, footer_height - 63*mm, "Конюшенная площадь 2В • VNVNC.RU")
        c.setFont("ArialUnicode", 8)
        c.setFillColor(HexColor("#AAAAAA"))
        c.drawCentredString(width/2, 5*mm, "18+ • 23:00 — 07:00 • FC/DC")

    # Layout
    margin = 15*mm
    img_size = 55*mm
    cols = 3
    rows = 4
    images_per_page = cols * rows

    h_spacing = (width - 2*margin - cols*img_size) / (cols - 1) if cols > 1 else 0
    v_spacing = 8*mm

    total_pages = (len(image_files) + images_per_page - 1) // images_per_page + 1

    # === COVER PAGE ===
    # Decorative stars at top
    c.setFillColor(secondary)
    c.setFont("ArialUnicode", 14)
    stars = "✦   ✦   ✦   ✦   ✦   ✦   ✦   ✦   ✦"
    c.drawCentredString(width/2, height - 15*mm, stars)
    
    # Main house name box
    box_y = height - 80*mm
    box_height = 50*mm
    c.setStrokeColor(secondary)
    c.setLineWidth(2)
    c.rect(margin + 10*mm, box_y, width - 2*margin - 20*mm, box_height, fill=False, stroke=True)
    
    c.setFillColor(primary)
    c.setFont("ArialBold", 42)
    c.drawCentredString(width/2, box_y + 28*mm, config["name_ru"])
    
    c.setFont("ArialBold", 16)
    c.drawCentredString(width/2, box_y + 10*mm, "ПОБЕЖДАЕТ В КУБКЕ ДОМОВ!")
    
    # Event info
    c.setFillColor(primary)
    c.setFont("ArialUnicode", 12)
    c.drawCentredString(width/2, box_y - 10*mm, "Platform 9¾ • 6-7 января 2026")
    
    # Quote box
    quote_y = height - 160*mm
    quote_height = 65*mm
    c.setFillColor(HexColor("#F8F4E8"))
    c.rect(margin, quote_y, width - 2*margin, quote_height, fill=True, stroke=False)
    
    c.setFillColor(primary)
    c.setFont("ArialUnicode", 11)
    c.drawCentredString(width/2, quote_y + quote_height - 15*mm, "«Ещё один год позади! И кубок школы необходимо вручить.")
    c.drawCentredString(width/2, quote_y + quote_height - 28*mm, f"Итак, по результатам Распределяющей Шляпы победитель — {config['name_ru'].title()}!»")
    c.setFont("ArialUnicode", 10)
    c.drawCentredString(width/2, quote_y + quote_height - 42*mm, "— Профессор Дамблдор")
    
    # Big number - MOVED DOWN to avoid overlap
    c.setFillColor(primary)
    c.setFont("ArialBold", 72)
    c.drawCentredString(width/2, quote_y + 8*mm, str(len(image_files)))
    
    # Stats section - also moved down
    stats_y = height - 240*mm
    c.setFillColor(primary)
    c.setFont("ArialUnicode", 16)
    c.drawCentredString(width/2, stats_y + 15*mm, f"студента в {config['name_ru'].title()}е")
    
    pct = len(image_files) / total_all * 100
    c.setFillColor(secondary)
    c.setFont("ArialBold", 20)
    c.drawCentredString(width/2, stats_y - 5*mm, f"{pct:.1f}% — ЛУЧШИЙ РЕЗУЛЬТАТ!")
    
    # Other houses comparison
    compare_y = stats_y - 50*mm
    c.setFillColor(primary)
    c.setFont("ArialBold", 11)
    c.drawCentredString(width/2, compare_y + 20*mm, "РЕЗУЛЬТАТЫ ДРУГИХ ФАКУЛЬТЕТОВ:")
    
    box_width = 38*mm
    box_height_small = 35*mm
    spacing = 5*mm
    total_width = 4 * box_width + 3 * spacing
    start_x = (width - total_width) / 2
    
    house_order = ["Gryffindor", "Slytherin", "Hufflepuff", "Ravenclaw"]
    for i, h in enumerate(house_order):
        h_config = HOUSES[h]
        h_color = HexColor(h_config["primary"])
        count = all_counts[h]
        h_pct = count / total_all * 100
        
        x = start_x + i * (box_width + spacing)
        
        c.setFillColor(h_color)
        c.roundRect(x, compare_y - box_height_small, box_width, box_height_small, 3, fill=True, stroke=False)
        
        c.setFillColor(HexColor("#FFFFFF"))
        c.setFont("ArialBold", 8)
        c.drawCentredString(x + box_width/2, compare_y - 10*mm, h_config["name_ru"])
        
        c.setFont("ArialBold", 20)
        c.drawCentredString(x + box_width/2, compare_y - 22*mm, str(count))
        
        c.setFont("ArialUnicode", 8)
        c.drawCentredString(x + box_width/2, compare_y - 30*mm, f"{h_pct:.1f}%")
    
    # Total participants
    c.setFillColor(primary)
    c.setFont("ArialUnicode", 10)
    c.drawCentredString(width/2, compare_y - 50*mm, f"Всего участников: {total_all}")
    
    # Promo footer
    draw_promo_footer()
    
    c.showPage()

    # === IMAGE PAGES ===
    for page_idx in range((len(image_files) + images_per_page - 1) // images_per_page):
        draw_header(page_idx + 2, total_pages)
        draw_footer()

        start_idx = page_idx * images_per_page
        page_images = image_files[start_idx:start_idx + images_per_page]

        start_y = height - 45*mm

        for i, img_file in enumerate(page_images):
            row = i // cols
            col = i % cols

            x = margin + col * (img_size + h_spacing)
            y = start_y - row * (img_size + v_spacing) - img_size

            img_path = IMAGES_DIR / img_file
            if img_path.exists():
                try:
                    c.setStrokeColor(secondary)
                    c.setLineWidth(2)
                    c.rect(x - 2, y - 2, img_size + 4, img_size + 4, fill=False, stroke=True)
                    c.drawImage(str(img_path), x, y, img_size, img_size, preserveAspectRatio=True)
                except Exception as e:
                    print(f"  Error with {img_file}: {e}")

        c.showPage()

    c.save()
    print(f"✅ {config['name_ru']}.pdf - {len(image_files)} images, {total_pages} pages")

def main():
    print("🎩 Creating PDFs with Cyrillic support...\n")

    results = load_results()
    by_house = get_images_by_house(results)
    all_counts = get_all_house_counts(results)
    total = results["total_participants"]

    for house_name, image_files in by_house.items():
        config = HOUSES[house_name]
        print(f"Creating {config['name_ru']}: {len(image_files)} images...")
        create_house_pdf(house_name, sorted(image_files), total, all_counts)

    print(f"\n✨ Done! PDFs saved to: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
