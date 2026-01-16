"""Print test panel for simulator.

Provides a GUI for testing the TSPL label printer directly from the simulator.
Supports loading images, printing text, and running test patterns.
"""

import pygame
import os
import sys
import logging
import threading
from typing import Optional, Callable
from dataclasses import dataclass
from io import BytesIO
from datetime import datetime

logger = logging.getLogger(__name__)

# Check for pyusb
try:
    import usb.core
    import usb.util
    PYUSB_AVAILABLE = True
except ImportError:
    PYUSB_AVAILABLE = False

# Printer constants
VENDOR_ID = 0x353D
PRODUCT_ID = 0x1249
LABEL_WIDTH_MM = 58
LABEL_HEIGHT_MM = 100
DPI = 203
LABEL_WIDTH_PX = int(LABEL_WIDTH_MM * DPI / 25.4)  # 464
LABEL_HEIGHT_PX = int(LABEL_HEIGHT_MM * DPI / 25.4)  # 800


@dataclass
class PrintTestState:
    """State for the print test panel."""
    printer_connected: bool = False
    selected_image_path: Optional[str] = None
    selected_image_preview: Optional[pygame.Surface] = None
    status_message: str = "Press T to open file picker"
    is_printing: bool = False
    menu_index: int = 0


class PrintTestPanel:
    """GUI panel for testing label printing."""

    MENU_ITEMS = [
        ("Load Image", "load"),
        ("Print Image", "print_image"),
        ("Print Test Pattern", "print_test"),
        ("Print Text", "print_text"),
        ("Check Status", "status"),
    ]

    def __init__(self):
        self._state = PrintTestState()
        self._font: Optional[pygame.font.Font] = None
        self._small_font: Optional[pygame.font.Font] = None
        self._title_font: Optional[pygame.font.Font] = None
        self._printer_dev = None
        self._printer_ep = None

    def _init_fonts(self) -> None:
        """Initialize fonts."""
        if self._font:
            return

        font_paths = [
            "/System/Library/Fonts/Helvetica.ttc",
            "/System/Library/Fonts/SFNSMono.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]

        font_path = None
        for path in font_paths:
            if os.path.exists(path):
                font_path = path
                break

        if font_path:
            try:
                self._font = pygame.font.Font(font_path, 16)
                self._small_font = pygame.font.Font(font_path, 12)
                self._title_font = pygame.font.Font(font_path, 20)
            except:
                pass

        if not self._font:
            self._font = pygame.font.SysFont("arial", 16)
            self._small_font = pygame.font.SysFont("arial", 12)
            self._title_font = pygame.font.SysFont("arial", 20, bold=True)

    def handle_key(self, key: int) -> bool:
        """Handle keyboard input. Returns True if key was consumed."""
        if key == pygame.K_UP:
            self._state.menu_index = (self._state.menu_index - 1) % len(self.MENU_ITEMS)
            return True
        elif key == pygame.K_DOWN:
            self._state.menu_index = (self._state.menu_index + 1) % len(self.MENU_ITEMS)
            return True
        elif key in (pygame.K_RETURN, pygame.K_SPACE):
            self._execute_menu_action()
            return True
        elif key == pygame.K_t:
            # Quick shortcut: T to load image
            self._open_file_picker()
            return True
        return False

    def _execute_menu_action(self) -> None:
        """Execute the currently selected menu action."""
        _, action = self.MENU_ITEMS[self._state.menu_index]

        if action == "load":
            self._open_file_picker()
        elif action == "print_image":
            self._print_current_image()
        elif action == "print_test":
            self._print_test_pattern()
        elif action == "print_text":
            self._print_text_label()
        elif action == "status":
            self._check_printer_status()

    def _open_file_picker(self) -> None:
        """Open a file picker dialog."""
        self._state.status_message = "Opening file picker..."

        # Use tkinter for file dialog (works on Mac)
        def pick_file():
            try:
                import tkinter as tk
                from tkinter import filedialog

                root = tk.Tk()
                root.withdraw()  # Hide the main window
                root.attributes('-topmost', True)  # Bring to front

                file_path = filedialog.askopenfilename(
                    title="Select Image to Print",
                    filetypes=[
                        ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp"),
                        ("PNG files", "*.png"),
                        ("JPEG files", "*.jpg *.jpeg"),
                        ("All files", "*.*"),
                    ],
                    initialdir=os.path.expanduser("~/Downloads")
                )

                root.destroy()

                if file_path:
                    self._load_image(file_path)
                else:
                    self._state.status_message = "No file selected"

            except Exception as e:
                self._state.status_message = f"Error: {e}"
                logger.error(f"File picker error: {e}")

        # Run in thread to not block pygame
        threading.Thread(target=pick_file, daemon=True).start()

    def _load_image(self, path: str) -> None:
        """Load an image for preview and printing."""
        try:
            from PIL import Image

            self._state.selected_image_path = path
            img = Image.open(path)

            # Create preview (scaled to fit panel)
            preview_size = (200, 300)
            img.thumbnail(preview_size, Image.Resampling.LANCZOS)

            # Convert to pygame surface
            if img.mode == 'RGBA':
                mode = 'RGBA'
            else:
                img = img.convert('RGB')
                mode = 'RGB'

            data = img.tobytes()
            self._state.selected_image_preview = pygame.image.fromstring(
                data, img.size, mode
            )

            self._state.status_message = f"Loaded: {os.path.basename(path)}"
            logger.info(f"Loaded image: {path}")

        except Exception as e:
            self._state.status_message = f"Load error: {e}"
            logger.error(f"Image load error: {e}")

    def _connect_printer(self) -> bool:
        """Connect to the printer."""
        if not PYUSB_AVAILABLE:
            self._state.status_message = "pyusb not installed"
            return False

        try:
            self._printer_dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
            if not self._printer_dev:
                self._state.status_message = "Printer not found"
                return False

            try:
                self._printer_dev.set_configuration()
            except:
                pass

            try:
                usb.util.claim_interface(self._printer_dev, 0)
            except:
                pass

            cfg = self._printer_dev.get_active_configuration()
            for ep in cfg[(0, 0)]:
                if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
                    self._printer_ep = ep.bEndpointAddress
                    break

            self._state.printer_connected = True
            return True

        except Exception as e:
            self._state.status_message = f"Connect error: {e}"
            return False

    def _disconnect_printer(self) -> None:
        """Disconnect from printer."""
        if self._printer_dev:
            try:
                usb.util.release_interface(self._printer_dev, 0)
            except:
                pass
            self._printer_dev = None
            self._printer_ep = None
        self._state.printer_connected = False

    def _image_to_tspl(self, img) -> bytes:
        """Convert PIL Image to TSPL commands."""
        from PIL import Image

        # Scale to fill label
        scale_w = LABEL_WIDTH_PX / img.width
        scale_h = LABEL_HEIGHT_PX / img.height
        scale = min(scale_w, scale_h)

        new_width = int(img.width * scale)
        new_height = int(img.height * scale)
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Create canvas and center
        canvas = Image.new('L', (LABEL_WIDTH_PX, LABEL_HEIGHT_PX), 255)
        x = (LABEL_WIDTH_PX - new_width) // 2
        y = (LABEL_HEIGHT_PX - new_height) // 2

        if img.mode != 'L':
            img = img.convert('L')
        canvas.paste(img, (x, y))

        # Dither to 1-bit
        canvas = canvas.convert('1', dither=Image.Dither.FLOYDSTEINBERG)

        # Ensure width multiple of 8
        width, height = canvas.size
        if width % 8 != 0:
            new_w = (width // 8 + 1) * 8
            new_canvas = Image.new('1', (new_w, height), 1)
            new_canvas.paste(canvas, (0, 0))
            canvas = new_canvas
            width = new_w

        width_bytes = width // 8

        # Build bitmap
        bitmap = []
        for row in range(height):
            for xb in range(width_bytes):
                byte_val = 0
                for bit in range(8):
                    px = xb * 8 + bit
                    if px < canvas.width and canvas.getpixel((px, row)) == 0:
                        byte_val |= (0x80 >> bit)
                bitmap.append(byte_val ^ 0xFF)

        # TSPL commands
        commands = [
            f"SIZE {LABEL_WIDTH_MM} mm, {LABEL_HEIGHT_MM} mm\r\n".encode(),
            b"GAP 3 mm, 0 mm\r\n",
            b"DIRECTION 1,0\r\n",
            b"SET TEAR ON\r\n",
            b"CLS\r\n",
            f"BITMAP 0,0,{width_bytes},{height},0,".encode(),
            bytes(bitmap),
            b"\r\n",
            b"PRINT 1,1\r\n"
        ]

        return b''.join(commands)

    def _print_current_image(self) -> None:
        """Print the currently loaded image."""
        if not self._state.selected_image_path:
            self._state.status_message = "No image loaded"
            return

        if self._state.is_printing:
            self._state.status_message = "Already printing..."
            return

        def do_print():
            self._state.is_printing = True
            self._state.status_message = "Connecting..."

            try:
                if not self._connect_printer():
                    return

                from PIL import Image
                img = Image.open(self._state.selected_image_path)

                self._state.status_message = "Converting..."
                tspl = self._image_to_tspl(img)

                self._state.status_message = f"Sending {len(tspl)} bytes..."
                self._printer_dev.write(self._printer_ep, tspl, timeout=30000)

                self._state.status_message = "Printed!"
                logger.info(f"Printed image: {self._state.selected_image_path}")

            except Exception as e:
                self._state.status_message = f"Print error: {e}"
                logger.error(f"Print error: {e}")
            finally:
                self._disconnect_printer()
                self._state.is_printing = False

        threading.Thread(target=do_print, daemon=True).start()

    def _print_test_pattern(self) -> None:
        """Print a test pattern."""
        if self._state.is_printing:
            return

        def do_print():
            self._state.is_printing = True
            self._state.status_message = "Printing test..."

            try:
                if not self._connect_printer():
                    return

                from PIL import Image, ImageDraw, ImageFont

                img = Image.new('L', (LABEL_WIDTH_PX, LABEL_HEIGHT_PX), 255)
                draw = ImageDraw.Draw(img)

                # Border
                draw.rectangle([5, 5, LABEL_WIDTH_PX - 6, LABEL_HEIGHT_PX - 6], outline=0, width=3)

                # Title
                try:
                    font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)
                    small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
                except:
                    font = ImageFont.load_default()
                    small = font

                draw.text((120, 30), "TSPL TEST", font=font, fill=0)

                # Info
                y = 100
                info = [
                    f"Label: {LABEL_WIDTH_MM}x{LABEL_HEIGHT_MM}mm",
                    f"Pixels: {LABEL_WIDTH_PX}x{LABEL_HEIGHT_PX}",
                    f"DPI: {DPI}",
                    f"Date: {datetime.now().strftime('%d.%m.%Y %H:%M')}",
                ]
                for line in info:
                    draw.text((30, y), line, font=small, fill=0)
                    y += 30

                # Gradient
                y += 20
                for i in range(10):
                    px = 30 + i * 40
                    gray = int(255 * i / 9)
                    draw.rectangle([px, y, px + 35, y + 40], fill=gray, outline=0)
                y += 60

                # Lines
                for i in range(1, 6):
                    draw.line([(30, y), (LABEL_WIDTH_PX - 30, y)], fill=0, width=i)
                    y += i + 10

                # Checkerboard
                y += 20
                box = 20
                for row in range(4):
                    for col in range(18):
                        if (row + col) % 2 == 0:
                            px = 30 + col * box
                            draw.rectangle([px, y, px + box - 1, y + box - 1], fill=0)
                    y += box

                tspl = self._image_to_tspl(img)
                self._printer_dev.write(self._printer_ep, tspl, timeout=30000)

                self._state.status_message = "Test printed!"

            except Exception as e:
                self._state.status_message = f"Error: {e}"
            finally:
                self._disconnect_printer()
                self._state.is_printing = False

        threading.Thread(target=do_print, daemon=True).start()

    def _print_text_label(self) -> None:
        """Print a simple text label."""
        if self._state.is_printing:
            return

        def do_print():
            self._state.is_printing = True
            self._state.status_message = "Printing text..."

            try:
                if not self._connect_printer():
                    return

                from PIL import Image, ImageDraw, ImageFont

                img = Image.new('L', (LABEL_WIDTH_PX, LABEL_HEIGHT_PX), 255)
                draw = ImageDraw.Draw(img)

                try:
                    font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 48)
                    small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
                except:
                    font = ImageFont.load_default()
                    small = font

                # Title
                draw.text((100, 50), "ARTIFACT", font=font, fill=0)

                # Line
                draw.line([(30, 120), (LABEL_WIDTH_PX - 30, 120)], fill=0, width=2)

                # Message
                y = 150
                messages = [
                    "Print Test",
                    "",
                    datetime.now().strftime("%d.%m.%Y"),
                    datetime.now().strftime("%H:%M:%S"),
                    "",
                    "TSPL Protocol",
                    f"{LABEL_WIDTH_PX}x{LABEL_HEIGHT_PX}px",
                ]
                for msg in messages:
                    if msg:
                        bbox = draw.textbbox((0, 0), msg, font=small)
                        w = bbox[2] - bbox[0]
                        draw.text(((LABEL_WIDTH_PX - w) // 2, y), msg, font=small, fill=0)
                    y += 35

                tspl = self._image_to_tspl(img)
                self._printer_dev.write(self._printer_ep, tspl, timeout=30000)

                self._state.status_message = "Text printed!"

            except Exception as e:
                self._state.status_message = f"Error: {e}"
            finally:
                self._disconnect_printer()
                self._state.is_printing = False

        threading.Thread(target=do_print, daemon=True).start()

    def _check_printer_status(self) -> None:
        """Check printer connection status."""
        if not PYUSB_AVAILABLE:
            self._state.status_message = "pyusb not installed"
            self._state.printer_connected = False
            return

        try:
            dev = usb.core.find(idVendor=VENDOR_ID, idProduct=PRODUCT_ID)
            if dev:
                self._state.status_message = f"Found: {dev.product}"
                self._state.printer_connected = True
            else:
                self._state.status_message = "Printer not found"
                self._state.printer_connected = False
        except Exception as e:
            self._state.status_message = f"Error: {e}"
            self._state.printer_connected = False

    def render(self, screen: pygame.Surface, rect: pygame.Rect) -> None:
        """Render the print test panel."""
        self._init_fonts()

        # Background
        pygame.draw.rect(screen, (30, 30, 40), rect, border_radius=8)
        pygame.draw.rect(screen, (60, 60, 80), rect, 2, border_radius=8)

        # Title
        title = self._title_font.render("Print Test", True, (255, 255, 255))
        screen.blit(title, (rect.x + 15, rect.y + 10))

        # Printer status indicator
        status_color = (0, 200, 0) if self._state.printer_connected else (200, 60, 60)
        pygame.draw.circle(screen, status_color, (rect.right - 20, rect.y + 20), 8)

        # Menu items
        y = rect.y + 50
        for i, (label, _) in enumerate(self.MENU_ITEMS):
            is_selected = i == self._state.menu_index

            if is_selected:
                pygame.draw.rect(screen, (60, 80, 120), (rect.x + 10, y - 2, rect.width - 20, 24), border_radius=4)
                color = (255, 255, 255)
                prefix = "> "
            else:
                color = (180, 180, 200)
                prefix = "  "

            text = self._font.render(f"{prefix}{label}", True, color)
            screen.blit(text, (rect.x + 15, y))
            y += 28

        # Divider
        y += 10
        pygame.draw.line(screen, (60, 60, 80), (rect.x + 15, y), (rect.right - 15, y))
        y += 15

        # Image preview
        if self._state.selected_image_preview:
            preview = self._state.selected_image_preview
            preview_rect = preview.get_rect(centerx=rect.centerx, top=y)
            screen.blit(preview, preview_rect)
            y = preview_rect.bottom + 10

            # Filename
            if self._state.selected_image_path:
                name = os.path.basename(self._state.selected_image_path)
                if len(name) > 25:
                    name = name[:22] + "..."
                name_text = self._small_font.render(name, True, (150, 150, 170))
                name_rect = name_text.get_rect(centerx=rect.centerx, top=y)
                screen.blit(name_text, name_rect)
                y += 20

        # Status message
        status = self._small_font.render(self._state.status_message, True, (100, 200, 100))
        status_rect = status.get_rect(centerx=rect.centerx, bottom=rect.bottom - 40)
        screen.blit(status, status_rect)

        # Help text
        help_text = self._small_font.render("T: Pick file | Enter: Action | Arrows: Navigate", True, (100, 100, 120))
        help_rect = help_text.get_rect(centerx=rect.centerx, bottom=rect.bottom - 15)
        screen.blit(help_text, help_rect)
