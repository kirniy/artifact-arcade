#!/usr/bin/env python3
"""Test script for AIYIN IP-802 label printer on Mac via USB.

Tests label printing for all ARTIFACT arcade modes using the existing
label layout engine. Connect the printer via USB before running.

Usage:
    python scripts/test_mac_printer.py [mode]

Modes:
    all       - Print all test labels (default)
    fortune   - Fortune Teller mode
    zodiac    - Zodiac/Horoscope mode
    ai_prophet - AI Prophet mode
    roast     - Roast mode
    quiz      - Quiz mode
    roulette  - Roulette mode
    photobooth - Photobooth mode
    sorting_hat - Sorting Hat mode
    rapgod    - Rap God mode
    list      - List all available modes
"""

import sys
import os
import time
from datetime import datetime
from io import BytesIO

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

import usb.core
import usb.util

# Printer USB IDs
VENDOR_ID = 0x353D  # IPRT LABELPrinter
PRODUCT_ID = 0x1249


class MacUSBPrinter:
    """Mac USB printer driver for AIYIN IP-802 label printer."""

    def __init__(self):
        self.dev = None
        self.ep_out = None
        self.ep_in = None

    def connect(self) -> bool:
        """Connect to the printer via USB."""
        self.dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
        if self.dev is None:
            print("❌ Printer not found. Is it connected via USB?")
            return False

        print(f"✅ Found: {self.dev.manufacturer} - {self.dev.product}")
        print(f"   Serial: {self.dev.serial_number}")

        # Detach kernel driver if necessary
        try:
            if self.dev.is_kernel_driver_active(0):
                self.dev.detach_kernel_driver(0)
                print("   Detached kernel driver")
        except Exception as e:
            pass  # May not have kernel driver on Mac

        # Set configuration
        try:
            self.dev.set_configuration()
        except Exception as e:
            pass  # May already be configured

        # Claim interface
        try:
            usb.util.claim_interface(self.dev, 0)
            print("   Interface claimed")
        except Exception as e:
            print(f"   Note: {e}")

        # Find endpoints
        cfg = self.dev.get_active_configuration()
        intf = cfg[(0, 0)]  # First interface

        for ep in intf:
            if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
                self.ep_out = ep.bEndpointAddress
            else:
                self.ep_in = ep.bEndpointAddress

        print(f"   OUT endpoint: 0x{self.ep_out:02x}")
        return True

    def disconnect(self):
        """Release the USB interface."""
        if self.dev:
            try:
                usb.util.release_interface(self.dev, 0)
            except:
                pass

    def send(self, data: bytes, timeout: int = 10000) -> int:
        """Send data to printer."""
        if not self.dev or not self.ep_out:
            raise RuntimeError("Printer not connected")
        return self.dev.write(self.ep_out, data, timeout=timeout)

    def print_label(self, raw_commands: bytes) -> bool:
        """Print a label from ESC/POS commands."""
        try:
            bytes_sent = self.send(raw_commands)
            print(f"   Sent {bytes_sent} bytes")
            time.sleep(2)  # Wait for printing
            return True
        except Exception as e:
            print(f"   ❌ Print error: {e}")
            return False


def create_test_image(text: str = "TEST", size: tuple = (200, 200)) -> bytes:
    """Create a simple test image with text."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new('RGB', size, 'white')
    draw = ImageDraw.Draw(img)

    # Draw border
    draw.rectangle([0, 0, size[0]-1, size[1]-1], outline='black', width=2)

    # Draw diagonal lines for visual pattern
    for i in range(0, max(size), 20):
        draw.line([(i, 0), (0, i)], fill='gray', width=1)
        draw.line([(size[0]-i, 0), (size[0], i)], fill='gray', width=1)

    # Draw text in center
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
    except:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (size[0] - text_width) // 2
    y = (size[1] - text_height) // 2

    # White background for text
    draw.rectangle([x-5, y-5, x+text_width+5, y+text_height+5], fill='white')
    draw.text((x, y), text, fill='black', font=font)

    # Convert to bytes
    buf = BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


def get_test_data(mode: str) -> dict:
    """Get test data for a specific mode."""

    base_data = {
        "timestamp": datetime.now().isoformat(),
        "qr_url": "https://vnvnc.ru/test",
        "short_url": "vnvnc.ru/t123",
    }

    test_caricature = create_test_image("CARICATURE", (300, 300))
    test_portrait = create_test_image("PORTRAIT", (250, 250))

    mode_data = {
        "fortune": {
            **base_data,
            "fortune": "Сегодня звёзды благоволят тебе! Ожидай неожиданную встречу, которая изменит твою жизнь. Удача на твоей стороне.",
            "zodiac_sign": "Овен",
            "zodiac_ru": "Овен",
            "lucky_color": "Красный",
            "caricature": test_caricature,
        },
        "zodiac": {
            **base_data,
            "zodiac_ru": "Скорпион",
            "zodiac_symbol": "♏",
            "birthday": "15.11",
            "horoscope": "Этот месяц принесёт тебе много возможностей для роста. Будь открыт к новым идеям и не бойся рисковать. Венера входит в твой знак!",
            "caricature": test_portrait,
        },
        "ai_prophet": {
            **base_data,
            "prediction": "В ближайшие дни тебя ждёт судьбоносная встреча. Доверься интуиции и следуй за своими мечтами. Пророчество сбудется!",
            "lucky_number": 7,
            "lucky_color": "Золотой",
            "caricature": test_caricature,
        },
        "roast": {
            **base_data,
            "roast": "О, смотрите кто пришёл! Человек, который думает что умеет танцевать после двух пива. Твой стиль одежды кричит 'мама выбирала'!",
            "vibe": "Главный клоун вечеринки",
            "vibe_icon": "crown",  # AI picks icon based on the role
            "doodle": create_test_image("ROAST", (280, 280)),
        },
        "quiz": {
            **base_data,
            "score": 8,
            "total": 10,
            "percentage": 80,
            "won_cocktail": True,
            "coupon_code": "QUIZ-2024-ABCD",
            "rank": "🥇 ЭКСПЕРТ",
            "caricature": create_test_image("WINNER", (220, 220)),
        },
        "roulette": {
            **base_data,
            "result": "Выпить шот с незнакомцем!",
            "category": "🍹 Алкогольное",
        },
        "photobooth": {
            **base_data,
            "caricature": create_test_image("PHOTO", (400, 400)),
        },
        "sorting_hat": {
            **base_data,
            "house_name_ru": "Гриффиндор",
            "house_ru": "Гриффиндор",
            "animal_ru": "Лев",
            "traits": ["Храбрость", "Отвага", "Благородство"],
            "caricature": test_portrait,
        },
        "squid_game": {
            **base_data,
            "result": "VICTORY",
            "survived_time": "2:45",
            "coupon_code": "SQUID-WIN-1234",
            "caricature": create_test_image("SQUID", (220, 220)),
        },
        "rapgod": {
            **base_data,
            "song_title": "Ночной Флекс",
            "artist": "AI Рэпер",
            "genre": "trap",
            "bpm": 145,
            "hook": "Я на флексе, на волне\nДеньги текут ко мне\nВечер пятницы, огонь",
            "one_liner": "Деньги — это просто бумага",
        },
        "autopsy": {
            **base_data,
            "diagnosis": "Пациент страдает от острого дефицита танцевальных навыков. Рекомендуется срочная терапия на танцполе!",
            "id": "VNVNC-2024-0042",
            "scan_image": create_test_image("X-RAY", (240, 240)),
        },
        "guess_me": {
            **base_data,
            "title": "Загадочный Незнакомец",
            "prediction": "Ты — душа компании, которая скрывает глубокий интеллект за маской весельчака. В прошлой жизни был философом!",
            "caricature": test_portrait,
        },
        "tower_stack": {
            **base_data,
            "score": 42,
            "height": 15,
            "max_streak": 7,
            "difficulty": "HARD",
        },
        "brick_breaker": {
            **base_data,
            "score": 12500,
            "win": True,
            "level": 5,
            "max_combo": 12,
            "lives_remaining": 2,
        },
        "y2k": {
            **base_data,
            "archetype": "Гламурная Принцесса",
            "description": "Ты — воплощение стиля нулевых! Розовый телефон, блёстки везде, и Yes to Paris. Хилтон бы гордилась!",
            "score": 7,
            "total": 10,
            "caricature": test_caricature,
        },
        "bad_santa": {
            **base_data,
            "verdict": "NICE",
            "nice_score": 0.75,
            "verdict_text": "Ну что ж, ты был относительно хорошим в этом году. Санта впечатлён... почти.",
            "coupon_code": "SANTA-SHOT-2024",
            "caricature": test_portrait,
        },
    }

    return mode_data.get(mode, {**base_data, "result": f"Test for {mode}"})


def print_mode_label(printer: MacUSBPrinter, mode: str) -> bool:
    """Generate and print a label for a specific mode."""
    from artifact.printing.label_receipt import LabelReceiptGenerator

    print(f"\n{'='*50}")
    print(f"🖨️  Printing: {mode.upper()}")
    print(f"{'='*50}")

    # Get test data
    data = get_test_data(mode)

    # Generate label
    generator = LabelReceiptGenerator()
    receipt = generator.generate_receipt(mode, data)

    print(f"   Layout: {len(receipt.layout.blocks)} blocks")
    print(f"   Commands: {len(receipt.raw_commands)} bytes")

    # Save preview
    preview_path = f"/tmp/label_preview_{mode}.png"
    if receipt.preview_image:
        with open(preview_path, 'wb') as f:
            f.write(receipt.preview_image)
        print(f"   Preview saved: {preview_path}")

    # Print
    result = printer.print_label(receipt.raw_commands)

    if result:
        print(f"   ✅ Printed successfully!")
    else:
        print(f"   ❌ Print failed")

    return result


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Test AIYIN IP-802 label printer on Mac")
    parser.add_argument('mode', nargs='?', default='all',
                       help='Mode to test (default: all)')
    parser.add_argument('--delay', type=float, default=3.0,
                       help='Delay between prints in seconds (default: 3)')
    args = parser.parse_args()

    all_modes = [
        "fortune", "zodiac", "ai_prophet", "roast", "quiz",
        "roulette", "photobooth", "sorting_hat", "squid_game",
        "rapgod", "autopsy", "guess_me", "tower_stack",
        "brick_breaker", "y2k", "bad_santa"
    ]

    if args.mode == 'list':
        print("\nAvailable modes:")
        for m in all_modes:
            print(f"  - {m}")
        return

    # Connect to printer
    printer = MacUSBPrinter()
    if not printer.connect():
        sys.exit(1)

    try:
        if args.mode == 'all':
            # Print all modes
            print(f"\n🎰 ARTIFACT Label Printer Test")
            print(f"   Testing all {len(all_modes)} modes")
            print(f"   Delay between prints: {args.delay}s")

            success = 0
            for mode in all_modes:
                if print_mode_label(printer, mode):
                    success += 1
                time.sleep(args.delay)

            print(f"\n{'='*50}")
            print(f"📊 Results: {success}/{len(all_modes)} labels printed")
            print(f"{'='*50}")
        else:
            # Print single mode
            if args.mode not in all_modes:
                print(f"❌ Unknown mode: {args.mode}")
                print(f"   Use 'list' to see available modes")
                sys.exit(1)

            print_mode_label(printer, args.mode)

    finally:
        printer.disconnect()
        print("\n✅ Printer disconnected")


if __name__ == "__main__":
    main()
