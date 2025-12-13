"""
Application settings using Pydantic.

Settings are loaded from environment variables with .env file support.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DisplaySettings(BaseSettings):
    """Display-related settings."""

    # Main display (P3 LED Matrix)
    main_width: int = 128
    main_height: int = 128

    # Ticker display (WS2812B)
    ticker_width: int = 48  # 32 center + 8 left + 8 right
    ticker_height: int = 8

    # LCD display
    lcd_width: int = 16
    lcd_rows: int = 1

    # Rendering
    fps: int = 60
    brightness: float = Field(default=1.0, ge=0.0, le=1.0)


class HardwareSettings(BaseSettings):
    """Hardware pin assignments."""

    # WS2812B ticker (PWM)
    ticker_gpio: int = 18
    ticker_led_count: int = 384  # 48x8

    # LCD I2C
    lcd_i2c_address: int = 0x27

    # Keypad GPIO matrix
    keypad_rows: list[int] = Field(default=[5, 6, 13, 19])
    keypad_cols: list[int] = Field(default=[12, 16, 20])

    # Arcade buttons
    arcade_left_gpio: int = 23
    arcade_right_gpio: int = 24

    # Thermal printer UART
    printer_port: str = "/dev/serial0"
    printer_baudrate: int = 9600


class AISettings(BaseSettings):
    """AI service settings."""

    gemini_api_key: str = Field(default="", env="GEMINI_API_KEY")

    # Model names
    prediction_model: str = "gemini-2.5-flash"
    caricature_model: str = "gemini-3-pro-image-preview"

    # Timeouts
    prediction_timeout: float = 300.0  # 5 minutes
    caricature_timeout: float = 480.0  # 8 minutes

    # Retry settings
    max_retries: int = 3
    retry_delay: float = 1.0


class Settings(BaseSettings):
    """Main application settings."""

    model_config = SettingsConfigDict(
        env_prefix="ARTIFACT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environment
    env: Literal["simulator", "hardware"] = "simulator"
    debug: bool = False

    # Theme and language
    theme: str = "mystical"
    language: Literal["ru", "en"] = "ru"

    # Paths
    base_path: Path = Field(default_factory=lambda: Path(__file__).parent.parent)
    assets_path: Path = Field(default_factory=lambda: Path(__file__).parent.parent / "assets")
    config_path: Path = Field(default_factory=lambda: Path(__file__).parent)

    # Simulator settings
    simulator_window_width: int = 1280
    simulator_window_height: int = 720
    simulator_fullscreen: bool = False

    # Nested settings
    display: DisplaySettings = Field(default_factory=DisplaySettings)
    hardware: HardwareSettings = Field(default_factory=HardwareSettings)
    ai: AISettings = Field(default_factory=AISettings)

    @property
    def is_simulator(self) -> bool:
        """Check if running in simulator mode."""
        return self.env == "simulator"

    @property
    def is_hardware(self) -> bool:
        """Check if running on real hardware."""
        return self.env == "hardware"

    @property
    def themes_path(self) -> Path:
        """Path to themes configuration."""
        return self.config_path / "themes"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
