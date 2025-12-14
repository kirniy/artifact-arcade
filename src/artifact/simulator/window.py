"""
Main simulator window using pygame.

Provides a desktop development environment that simulates
all ARTIFACT hardware components.
"""

import pygame
import asyncio
import logging
from typing import Callable
from dataclasses import dataclass

from ..core.state import StateMachine, State
from ..core.events import EventBus, EventType, Event
from .mock_hardware.display import SimulatedHUB75, SimulatedWS2812B, SimulatedLCD
from .mock_hardware.input import SimulatedButton, SimulatedKeypad, SimulatedArcade
from .printer_preview import ThermalPrinterPreview, PrintJob

logger = logging.getLogger(__name__)


@dataclass
class WindowConfig:
    """Simulator window configuration."""
    width: int = 1280
    height: int = 720
    title: str = "VNVNC Simulator"
    fullscreen: bool = False
    fps: int = 60

    # Display scale factors
    # According to design: Ticker is WIDER than main (480mm vs 384mm)
    main_scale: int = 3     # 128x128 * 3 = 384x384
    ticker_scale: int = 10  # 48x8 * 10 = 480x80 (wider than main!)
    lcd_scale: int = 2

    # Colors
    bg_color: tuple[int, int, int] = (20, 20, 30)
    panel_color: tuple[int, int, int] = (40, 40, 50)
    text_color: tuple[int, int, int] = (200, 200, 220)
    accent_color: tuple[int, int, int] = (100, 150, 255)


class SimulatorWindow:
    """
    Main simulator window managing all virtual hardware.

    Keyboard Mapping:
        SPACE: Center button (USB Big Button)
        LEFT ARROW: Left arcade button
        RIGHT ARROW: Right arcade button
        0-9: Keypad numbers
        *: Keypad asterisk
        #: Keypad hash
        F1: Toggle debug overlay
        F2: Capture screenshot
        F3: Mock camera (file picker)
        F5: Reload theme
        ESC: Exit simulator
    """

    def __init__(
        self,
        config: WindowConfig | None = None,
        state_machine: StateMachine | None = None,
        event_bus: EventBus | None = None
    ) -> None:
        self.config = config or WindowConfig()
        self.state_machine = state_machine or StateMachine()
        self.event_bus = event_bus or EventBus()

        # Pygame setup
        self._screen: pygame.Surface | None = None
        self._clock: pygame.Clock | None = None
        self._running = False
        self._frame_count = 0
        self._show_debug = True

        # Virtual displays
        self.main_display = SimulatedHUB75(128, 128)
        self.ticker_display = SimulatedWS2812B(48, 8)
        self.lcd_display = SimulatedLCD(16, 1)

        # Virtual inputs
        self.center_button = SimulatedButton()
        self.left_button = SimulatedArcade("left")
        self.right_button = SimulatedArcade("right")
        self.keypad = SimulatedKeypad()

        # UI elements positions (calculated on init)
        self._layout: dict[str, pygame.Rect] = {}

        # Fonts
        self._font: pygame.font.Font | None = None
        self._small_font: pygame.font.Font | None = None

        # Log viewer
        self._show_log = False
        self._log_buffer: list[str] = []
        self._max_log_lines = 20

        # Thermal printer preview
        self._show_printer = False
        self._printer_preview = ThermalPrinterPreview()

        # Setup log handler to capture logs
        self._setup_log_capture()

        logger.info("SimulatorWindow created")

    def _setup_log_capture(self) -> None:
        """Setup log capturing for the log viewer."""
        class SimulatorLogHandler(logging.Handler):
            def __init__(self, window: 'SimulatorWindow'):
                super().__init__()
                self.window = window

            def emit(self, record):
                msg = self.format(record)
                self.window._log_buffer.append(msg)
                # Keep buffer size limited
                if len(self.window._log_buffer) > self.window._max_log_lines * 2:
                    self.window._log_buffer = self.window._log_buffer[-self.window._max_log_lines:]

        handler = SimulatorLogHandler(self)
        handler.setFormatter(logging.Formatter('%(levelname).1s %(name)s: %(message)s'))
        logging.getLogger().addHandler(handler)

    def _init_pygame(self) -> None:
        """Initialize pygame and create window."""
        pygame.init()
        pygame.display.set_caption(self.config.title)

        flags = pygame.DOUBLEBUF
        if self.config.fullscreen:
            flags |= pygame.FULLSCREEN

        self._screen = pygame.display.set_mode(
            (self.config.width, self.config.height),
            flags
        )
        self._clock = pygame.time.Clock()

        # Initialize fonts - use fonts that support Cyrillic
        pygame.font.init()

        # Try to load Arial Unicode directly (has full Cyrillic support)
        cyrillic_font_paths = [
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial Unicode.ttf",
        ]

        self._font = None
        self._small_font = None

        for font_path in cyrillic_font_paths:
            try:
                import os
                if os.path.exists(font_path):
                    self._font = pygame.font.Font(font_path, 16)
                    self._small_font = pygame.font.Font(font_path, 12)
                    # Test Cyrillic rendering
                    self._font.render("ТЕСТ", True, (255, 255, 255))
                    logger.info(f"Using font: {font_path}")
                    break
            except Exception as e:
                logger.debug(f"Font {font_path} failed: {e}")
                continue

        # Fallback to system fonts
        if not self._font:
            cyrillic_fonts = ["Arial Unicode MS", "DejaVu Sans", "Noto Sans", "Helvetica"]
            for font_name in cyrillic_fonts:
                try:
                    self._font = pygame.font.SysFont(font_name, 16)
                    self._small_font = pygame.font.SysFont(font_name, 12)
                    self._font.render("ТЕСТ", True, (255, 255, 255))
                    logger.info(f"Using system font: {font_name}")
                    break
                except:
                    continue

        if not self._font:
            self._font = pygame.font.SysFont(None, 16)
            self._small_font = pygame.font.SysFont(None, 12)
            logger.warning("No Cyrillic font found, using default")

        # Calculate layout
        self._calculate_layout()

        logger.info(f"Pygame initialized: {self.config.width}x{self.config.height}")

    def _calculate_layout(self) -> None:
        """Calculate positions for all UI elements."""
        w, h = self.config.width, self.config.height
        main_size = 128 * self.config.main_scale
        ticker_w = 48 * self.config.ticker_scale
        ticker_h = 8 * self.config.ticker_scale

        # Ticker at top with margin
        ticker_x = (w - ticker_w) // 2
        ticker_y = 30

        # Main display below ticker with proper gap (like physical machine)
        main_x = (w - main_size) // 2
        main_y = ticker_y + ticker_h + 25  # Gap between displays

        # LCD below main display
        lcd_w = 16 * 12  # Approximate character width
        lcd_h = 24
        lcd_x = (w - lcd_w) // 2
        lcd_y = main_y + main_size + 30

        # Debug panel on the right
        debug_x = w - 280
        debug_y = 50
        debug_w = 260
        debug_h = h - 100

        # Input panel at bottom
        input_y = h - 80
        input_h = 60

        self._layout = {
            "main": pygame.Rect(main_x, main_y, main_size, main_size),
            "ticker": pygame.Rect(ticker_x, ticker_y, ticker_w, ticker_h),
            "lcd": pygame.Rect(lcd_x, lcd_y, lcd_w, lcd_h),
            "debug": pygame.Rect(debug_x, debug_y, debug_w, debug_h),
            "input": pygame.Rect(50, input_y, w - 100, input_h),
        }

    def _handle_events(self) -> None:
        """Process pygame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self._running = False

            elif event.type == pygame.KEYDOWN:
                self._handle_keydown(event)

            elif event.type == pygame.KEYUP:
                self._handle_keyup(event)

    def _handle_keydown(self, event: pygame.event.Event) -> None:
        """Handle key press."""
        key = event.key

        # System keys (Mac-friendly - no F-keys required)
        if key == pygame.K_ESCAPE or key == pygame.K_q:
            self._running = False
        elif key == pygame.K_d:
            # D for Debug
            self._show_debug = not self._show_debug
        elif key == pygame.K_s:
            # S for Screenshot
            self._capture_screenshot()
        elif key == pygame.K_f:
            # F for Fullscreen
            self._toggle_fullscreen()
        elif key == pygame.K_l:
            # L for Log viewer
            self._show_log = not getattr(self, '_show_log', False)
        elif key == pygame.K_p:
            # P for Printer preview
            self._show_printer = not self._show_printer
        elif key == pygame.K_r:
            # R for Reboot/restart system
            self.event_bus.emit(Event(EventType.REBOOT, source="keyboard"))
        elif key == pygame.K_BACKSPACE:
            # Go back
            self.event_bus.emit(Event(EventType.BACK, source="keyboard"))

        # Center button (SPACE or RETURN)
        elif key in (pygame.K_SPACE, pygame.K_RETURN):
            self.center_button._press()
            self.event_bus.emit(Event(EventType.BUTTON_PRESS, source="center"))

        # Arcade buttons
        elif key == pygame.K_LEFT:
            self.left_button._press()
            self.event_bus.emit(Event(EventType.ARCADE_LEFT, source="arcade"))
        elif key == pygame.K_RIGHT:
            self.right_button._press()
            self.event_bus.emit(Event(EventType.ARCADE_RIGHT, source="arcade"))

        # Keypad
        elif key in range(pygame.K_0, pygame.K_9 + 1):
            char = chr(key)
            self.keypad._press(char)
            self.event_bus.emit(Event(
                EventType.KEYPAD_INPUT, data={"key": char}, source="keypad"
            ))
        elif key == pygame.K_KP0:
            self.keypad._press("0")
        elif key in range(pygame.K_KP1, pygame.K_KP9 + 1):
            char = str(key - pygame.K_KP1 + 1)
            self.keypad._press(char)
        elif key == pygame.K_ASTERISK or key == pygame.K_KP_MULTIPLY:
            self.keypad._press("*")
        elif key == pygame.K_HASH:
            self.keypad._press("#")

        # UP/DOWN for scrolling print preview
        elif key == pygame.K_UP:
            if self._show_printer and self._printer_preview:
                self._printer_preview.scroll(-1)  # Scroll up
        elif key == pygame.K_DOWN:
            if self._show_printer and self._printer_preview:
                self._printer_preview.scroll(1)  # Scroll down

    def _handle_keyup(self, event: pygame.event.Event) -> None:
        """Handle key release."""
        key = event.key

        if key in (pygame.K_SPACE, pygame.K_RETURN):
            self.center_button._release()
            self.event_bus.emit(Event(EventType.BUTTON_RELEASE, source="center"))
        elif key == pygame.K_LEFT:
            self.left_button._release()
        elif key == pygame.K_RIGHT:
            self.right_button._release()

    def _render(self) -> None:
        """Render all UI elements."""
        if not self._screen:
            return

        # Clear background
        self._screen.fill(self.config.bg_color)

        # Render displays
        self._render_main_display()
        self._render_ticker()
        self._render_lcd()

        # Render panels
        self._render_input_panel()
        if self._show_debug:
            self._render_debug_panel()
        if self._show_log:
            self._render_log_panel()
        if self._show_printer:
            self._render_printer_panel()

        # Render title bar
        self._render_title_bar()

        # Flip display
        pygame.display.flip()

    def _render_main_display(self) -> None:
        """Render the main 128x128 display."""
        rect = self._layout["main"]
        surface = self.main_display.render(self.config.main_scale)

        # Draw border
        pygame.draw.rect(self._screen, self.config.panel_color, rect.inflate(8, 8))
        self._screen.blit(surface, rect.topleft)

    def _render_ticker(self) -> None:
        """Render the WS2812B ticker display."""
        rect = self._layout["ticker"]
        surface = self.ticker_display.render(self.config.ticker_scale)

        # Draw border
        pygame.draw.rect(self._screen, self.config.panel_color, rect.inflate(8, 8))
        self._screen.blit(surface, rect.topleft)

    def _render_lcd(self) -> None:
        """Render the LCD character display."""
        rect = self._layout["lcd"]

        # Background
        pygame.draw.rect(self._screen, (30, 50, 30), rect)
        pygame.draw.rect(self._screen, (50, 100, 50), rect, 2)

        # Text
        if self._font:
            text = self.lcd_display.get_text()
            text_surface = self._font.render(text, True, (150, 255, 150))
            text_rect = text_surface.get_rect(center=rect.center)
            self._screen.blit(text_surface, text_rect)

    def _render_input_panel(self) -> None:
        """Render the input status panel with arcade-style buttons."""
        rect = self._layout["input"]

        # Background with gradient effect
        pygame.draw.rect(self._screen, self.config.panel_color, rect, border_radius=8)
        pygame.draw.rect(self._screen, (60, 60, 80), rect, 2, border_radius=8)

        if not self._font:
            return

        # Arcade button visualization using symbols
        buttons = [
            ("←", self.left_button.is_pressed(), (231, 76, 60)),    # Red
            ("●", self.center_button.is_pressed(), (46, 204, 113)), # Green
            ("→", self.right_button.is_pressed(), (52, 152, 219)),  # Blue
        ]

        spacing = rect.width // 4
        for i, (symbol, pressed, active_color) in enumerate(buttons):
            x = rect.x + spacing * (i + 1)
            y = rect.centery

            # Draw button circle
            radius = 22
            btn_color = active_color if pressed else (60, 60, 80)
            glow_color = tuple(min(255, c + 50) for c in active_color) if pressed else (40, 40, 60)

            # Glow effect when pressed
            if pressed:
                pygame.draw.circle(self._screen, glow_color, (x, y), radius + 4)

            pygame.draw.circle(self._screen, btn_color, (x, y), radius)
            pygame.draw.circle(self._screen, (100, 100, 120), (x, y), radius, 2)

            # Symbol
            color = (255, 255, 255) if pressed else (150, 150, 170)
            text_surface = self._font.render(symbol, True, color)
            text_rect = text_surface.get_rect(center=(x, y))
            self._screen.blit(text_surface, text_rect)

        # Keypad status with better formatting
        last_key = self.keypad.get_last_key()
        if last_key:
            key_text = f"⌨ {last_key}"
            key_surface = self._small_font.render(key_text, True, self.config.accent_color)
            self._screen.blit(key_surface, (rect.right - 60, rect.centery - 6))

    def _render_debug_panel(self) -> None:
        """Render the debug information panel."""
        rect = self._layout["debug"]

        # Background
        pygame.draw.rect(self._screen, self.config.panel_color, rect, border_radius=5)

        if not self._small_font:
            return

        lines = [
            f"FPS: {self._clock.get_fps():.1f}" if self._clock else "FPS: --",
            f"Frame: {self._frame_count}",
            f"State: {self.state_machine.state.name}",
            f"Mode: {self.state_machine.context.current_mode or 'None'}",
            "",
            "---- CONTROLS ----",
            "SPACE   Start/OK",
            "ARROWS  Select",
            "0-9,*,# Keypad",
            "R       Restart",
            "",
            "---- SYSTEM ----",
            "F  Fullscreen",
            "D  Debug panel",
            "L  Log viewer",
            "P  Printer preview",
            "S  Screenshot",
            "Q  Quit",
        ]

        y = rect.y + 10
        for line in lines:
            text_surface = self._small_font.render(
                line, True, self.config.text_color
            )
            self._screen.blit(text_surface, (rect.x + 10, y))
            y += 18

    def _render_log_panel(self) -> None:
        """Render the log viewer panel."""
        if not self._show_log or not self._small_font:
            return

        # Log panel on the left side
        rect = pygame.Rect(10, 50, 300, self.config.height - 150)

        # Semi-transparent background
        surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        surf.fill((20, 25, 35, 230))
        self._screen.blit(surf, rect.topleft)
        pygame.draw.rect(self._screen, (60, 80, 100), rect, 1, border_radius=5)

        # Title
        title_surf = self._font.render("═══ LOG VIEWER ═══", True, (100, 200, 255))
        self._screen.blit(title_surf, (rect.x + 10, rect.y + 5))

        # Log lines
        y = rect.y + 28
        visible_lines = self._log_buffer[-self._max_log_lines:]

        for line in visible_lines:
            # Color code by level
            if line.startswith('E'):
                color = (255, 100, 100)  # Error - red
            elif line.startswith('W'):
                color = (255, 200, 100)  # Warning - yellow
            elif line.startswith('I'):
                color = (150, 200, 150)  # Info - green
            else:
                color = (150, 150, 170)  # Debug - gray

            # Truncate long lines
            display_line = line[:45] + "..." if len(line) > 48 else line
            text_surf = self._small_font.render(display_line, True, color)
            self._screen.blit(text_surf, (rect.x + 8, y))
            y += 14

            if y > rect.bottom - 10:
                break

    def _render_printer_panel(self) -> None:
        """Render the thermal printer preview panel."""
        if not self._show_printer:
            return

        # Update printer animation
        self._printer_preview.update(16)  # ~60fps

        # Position on the right side
        panel_width = 280
        panel_height = self.config.height - 100
        panel_x = self.config.width - panel_width - 10
        panel_y = 50

        self._printer_preview.render(
            self._screen,
            panel_x, panel_y,
            panel_width, panel_height
        )

    def trigger_print(self, result_data: dict) -> None:
        """Trigger a print job from mode result data."""
        from .printer_preview import create_print_job_from_result

        job = create_print_job_from_result(result_data)
        self._printer_preview.set_print_job(job)
        self._show_printer = True

    def _render_title_bar(self) -> None:
        """Render the title bar with stylish header."""
        if not self._font:
            return

        # Main title
        title = f"◆ ARTIFACT Simulator ◆ | {self.state_machine.state.name}"
        text_surface = self._font.render(title, True, self.config.accent_color)
        self._screen.blit(text_surface, (20, 15))

        # Status indicators on the right
        indicators = []
        if self.config.fullscreen:
            indicators.append("⛶ FULL")
        if self._show_debug:
            indicators.append("◉ DBG")
        if self._show_log:
            indicators.append("◎ LOG")
        if self._show_printer:
            indicators.append("⎙ PRINT")

        if indicators:
            status = " │ ".join(indicators)
            status_surf = self._small_font.render(status, True, (100, 150, 200))
            self._screen.blit(status_surf, (self.config.width - 200, 18))

    def _capture_screenshot(self) -> None:
        """Capture and save a screenshot."""
        if self._screen:
            filename = f"screenshot_{self._frame_count}.png"
            pygame.image.save(self._screen, filename)
            logger.info(f"Screenshot saved: {filename}")

    def _toggle_fullscreen(self) -> None:
        """Toggle fullscreen mode."""
        self.config.fullscreen = not self.config.fullscreen

        if self.config.fullscreen:
            # Get display info for fullscreen resolution
            info = pygame.display.Info()
            self._screen = pygame.display.set_mode(
                (info.current_w, info.current_h),
                pygame.FULLSCREEN | pygame.DOUBLEBUF
            )
            self.config.width = info.current_w
            self.config.height = info.current_h
        else:
            # Return to windowed mode
            self.config.width = 1280
            self.config.height = 720
            self._screen = pygame.display.set_mode(
                (self.config.width, self.config.height),
                pygame.DOUBLEBUF
            )

        # Recalculate layout for new resolution
        self._calculate_layout()
        logger.info(f"Fullscreen: {self.config.fullscreen}")

    async def run(self) -> None:
        """Main simulator loop."""
        self._init_pygame()
        self._running = True

        logger.info("Simulator started")

        while self._running:
            # Handle events
            self._handle_events()

            # Emit tick event
            if self._clock:
                delta = self._clock.get_time() / 1000.0
                self.event_bus.emit(Event(
                    EventType.TICK,
                    data={"delta": delta, "frame": self._frame_count}
                ))

            # Process event queue
            await self.event_bus.process_queue()

            # Render
            self._render()

            # Frame timing
            if self._clock:
                self._clock.tick(self.config.fps)

            self._frame_count += 1

            # Yield to other tasks
            await asyncio.sleep(0)

        self._cleanup()

    def _cleanup(self) -> None:
        """Clean up pygame resources."""
        pygame.quit()
        logger.info("Simulator stopped")

    def stop(self) -> None:
        """Stop the simulator."""
        self._running = False
