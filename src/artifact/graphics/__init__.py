"""Graphics module for ARTIFACT rendering pipeline.

Exports stay backward-compatible, but are loaded lazily so font and ticker
modules can be tested without importing the full renderer stack.
"""

from importlib import import_module

_EXPORTS = {
    "Renderer": ("artifact.graphics.renderer", "Renderer"),
    "DisplayCompositor": ("artifact.graphics.compositor", "DisplayCompositor"),
    "draw_rect": ("artifact.graphics.primitives", "draw_rect"),
    "draw_circle": ("artifact.graphics.primitives", "draw_circle"),
    "draw_line": ("artifact.graphics.primitives", "draw_line"),
    "draw_text": ("artifact.graphics.primitives", "draw_text"),
    "draw_image": ("artifact.graphics.primitives", "draw_image"),
    "fill": ("artifact.graphics.primitives", "fill"),
    "clear": ("artifact.graphics.primitives", "clear"),
    "PixelFont": ("artifact.graphics.fonts", "PixelFont"),
    "load_font": ("artifact.graphics.fonts", "load_font"),
    "get_default_font": ("artifact.graphics.fonts", "get_default_font"),
    "get_cyrillic_font": ("artifact.graphics.fonts", "get_cyrillic_font"),
    "get_ticker_font": ("artifact.graphics.fonts", "get_ticker_font"),
    "draw_text_bitmap": ("artifact.graphics.fonts", "draw_text_bitmap"),
    "center_text_x": ("artifact.graphics.fonts", "center_text_x"),
    "wrap_text": ("artifact.graphics.fonts", "wrap_text"),
    "draw_text_centered": ("artifact.graphics.fonts", "draw_text_centered"),
    "TextAlign": ("artifact.graphics.text_utils", "TextAlign"),
    "TextEffect": ("artifact.graphics.text_utils", "TextEffect"),
    "TextStyle": ("artifact.graphics.text_utils", "TextStyle"),
    "TextBlock": ("artifact.graphics.text_utils", "TextBlock"),
    "measure_text": ("artifact.graphics.text_utils", "measure_text"),
    "measure_text_exact": ("artifact.graphics.text_utils", "measure_text_exact"),
    "calc_centered_x": ("artifact.graphics.text_utils", "calc_centered_x"),
    "calc_text_x": ("artifact.graphics.text_utils", "calc_text_x"),
    "smart_wrap_text": ("artifact.graphics.text_utils", "smart_wrap_text"),
    "calc_max_chars_per_line": ("artifact.graphics.text_utils", "calc_max_chars_per_line"),
    "calc_scale_to_fit": ("artifact.graphics.text_utils", "calc_scale_to_fit"),
    "render_text_block": ("artifact.graphics.text_utils", "render_text_block"),
    "draw_centered_text": ("artifact.graphics.text_utils", "draw_centered_text"),
    "draw_wrapped_text": ("artifact.graphics.text_utils", "draw_wrapped_text"),
    "fit_text_in_rect": ("artifact.graphics.text_utils", "fit_text_in_rect"),
    "draw_title": ("artifact.graphics.text_utils", "draw_title"),
    "draw_subtitle": ("artifact.graphics.text_utils", "draw_subtitle"),
    "draw_prompt": ("artifact.graphics.text_utils", "draw_prompt"),
    "draw_main_text": ("artifact.graphics.text_utils", "draw_main_text"),
    "format_lcd_text": ("artifact.graphics.text_utils", "format_lcd_text"),
    "truncate_lcd_text": ("artifact.graphics.text_utils", "truncate_lcd_text"),
    "calc_ticker_scroll": ("artifact.graphics.text_utils", "calc_ticker_scroll"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    try:
        module_name, attr_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    module = import_module(module_name)
    return getattr(module, attr_name)
