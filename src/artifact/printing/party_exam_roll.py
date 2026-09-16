"""Light, ornate VNVNC University student document for the 80mm RP80."""
from io import BytesIO
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps
from artifact.printing.photobooth_roll import PhotoboothRollReceiptGenerator, PhotoboothRollReceipt
from artifact.printing.wheel_qr import render_wheel_receipt_qr


class PartyExamRollReceiptGenerator(PhotoboothRollReceiptGenerator):
    def generate_receipt(self, mode_name, data):
        image = self.render_document(data)
        output = BytesIO(); image.save(output, 'PNG')
        return PhotoboothRollReceipt(self.image_to_escpos(image), output.getvalue(), self._parse_timestamp(data), '')

    def render_document(self, data):
        import re
        url = str(data['claim_url'])
        if not re.fullmatch(r'https://t.me/vnvncbattlebot\?start=exam_[A-Za-z0-9_-]{32}', url):
            raise ValueError('Invalid permanent Telegram claim link')
        saturday = str(data['night']) == '2026-09-19'
        image = Image.new('L', (576, 3400), 255)
        d = ImageDraw.Draw(image)
        def center(text, y, size=28, bold=False):
            font = self._fit_font(text, 472, size, 18, bold=bold)
            d.text((288, y), text, font=font, fill=0, anchor='mt')
            return y + size + 10
        def paragraph(text, y, size=25):
            font = self._font(size)
            lines, line = [], ""
            for word in text.split():
                candidate = (line + " " + word).strip()
                if d.textlength(candidate, font=font) > 466 and line:
                    lines.append(line); line = word
                else:
                    line = candidate
            if line:
                lines.append(line)
            for line in lines:
                d.text((55, y), line, font=font, fill=0)
                y += size + 8
            return y + 10
        # The same generated artwork as the gradebook, composited on white for thermal output.
        assets = Path(__file__).resolve().parents[3] / 'assets' / 'party_exam'
        def ink_asset(name, box, top):
            with Image.open(assets/name) as original:
                rgba = ImageOps.contain(original.convert('RGBA'), box)
                white = Image.new('RGBA', rgba.size, 'white')
                white.alpha_composite(rgba)
                ink = white.convert('L')
                image.paste(ink, ((576-ink.width)//2, top))
                return top + ink.height
        y = ink_asset('crest.png', (180,180), 42)
        y = center('VNVNC', y+12, 48, True)
        y = center('U N I V E R S I T Y', y - 6, 25, True)
        d.line((68, y+4, 508, y+4), fill=0, width=2)
        y = center('PARTY EXAM', y+21, 46, True)
        y = center('ЗАЧЁТНАЯ КАРТОЧКА СТУДЕНТА', y, 23, True)
        y = center(f"№ {int(data['student_number'])}", y+4, 37, True)
        photo = Image.open(BytesIO(data['caricature'])).convert('L')
        photo = ImageOps.contain(photo, (300, 360))
        photo = ImageOps.autocontrast(photo, cutoff=1)
        px, py = (576-photo.width)//2, y+12
        d.rectangle((px-9, py-9, px+photo.width+9, py+photo.height+9), outline=0, width=2)
        image.paste(photo, (px, py))
        y = py + photo.height + 27
        y = center('ЗАЧИСЛЕН В ПОТОК НОЧНОГО ОБУЧЕНИЯ', y, 20, True)
        y = center('18 / 19 СЕНТЯБРЯ' if not saturday else '19 / 20 СЕНТЯБРЯ', y, 24)
        y = paragraph('Сдай сессию. Забери приз.', y+5)
        d.line((55,y,521,y), fill=0, width=2); y += 19
        y = center('ЛИЧНОЕ ДЕЛО В TELEGRAM', y, 27, True)
        qr = render_wheel_receipt_qr(url, max_size_px=340, error_correction='H', telegram_icon=False).image
        image.paste(qr, ((576-qr.width)//2,y)); y += qr.height + 12
        y = paragraph('Сканируй QR → «Старт» → зачётка.', y)
        if saturday:
            y = center('УЧЕБНЫЙ МАРШРУТ', y, 29, True)
            for text in ('01 · Сплетни — фотозона КХ.',
                         '02 · Прокрастинация — АНГАР, стол напротив бара.',
                         '03 · Сомнительные решения — АНГАР, справа от бара.',
                         '04 · Кринжология — там же, у второго ведущего.'):
                y = paragraph(text,y,24)
            y = paragraph('Пройди 4 этапа. После каждого сканируй QR ведущего в зачётке. Все 4 отметки до 04:00 — и ты в розыгрыше.',y,24)
        else:
            y = paragraph('Всё на фотозоне КХ. Пройди интерактив. Сканируй итоговый QR ведущего в зачётке. Зачёт до 04:00 — и ты в розыгрыше.',y,25)
        y = center('ГЛАВНЫЙ РОЗЫГРЫШ · 04:00',y+5,29,True)
        y = center('20.09.2026 МСК' if saturday else '19.09.2026 МСК',y,23)
        y = paragraph('Депозит 5 000 руб. • Пати-сет «Хаски + Red Bull» • Три бесплатных коктейля. Три победителя этой ночи.',y,24)
        y = paragraph('Фишка на шот — у ведущего. Только этой ночью, до 07:00.',y,24)
        y = center('ДИРЕКТОР КОЛЛЕДЖА',y+8,23,True)
        y = ink_asset('signature.png', (420,140), y+4) + 28
        if y >= image.height - 20:
            raise ValueError('Receipt content exceeds canvas')
        for inset,width in ((17,3),(26,1),(33,2)):
            d.rectangle((inset,inset,575-inset,y-inset+16),outline=0,width=width)
        for x in (42,534):
            for yy in (42,y-27):
                d.polygon(((x,yy-11),(x+8,yy),(x,yy+11),(x-8,yy)),outline=0)
        for yy in range(74,y-45,20):
            d.ellipse((21,yy,24,yy+3),fill=0);d.ellipse((551,yy,554,yy+3),fill=0)
        return image.crop((0,0,576,y+18))
