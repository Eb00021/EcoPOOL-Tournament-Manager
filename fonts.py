"""
EcoPOOL League - Font Configuration
Centralized font loading and management for the application.
"""

import os
import sys
import customtkinter as ctk

# Font configuration
_FONT_LOADED = False
_FONT_FAMILY = "Segoe UI" if sys.platform == "win32" else "Helvetica"

# Path to custom font
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
FONT_PATH = os.path.join(FONT_DIR, "HelveticaNeueMedium.otf")


def load_custom_font():
    """Load the custom font for the application. Call once at startup."""
    global _FONT_LOADED, _FONT_FAMILY
    
    if _FONT_LOADED:
        return _FONT_FAMILY
    
    if os.path.exists(FONT_PATH):
        try:
            # Windows: Use ctypes to add the font to the system temporarily
            if sys.platform == "win32":
                import ctypes
                # FR_PRIVATE = 0x10 - font is only available to this process
                result = ctypes.windll.gdi32.AddFontResourceExW(FONT_PATH, 0x10, 0)
                if result > 0:
                    _FONT_FAMILY = "Helvetica Neue Medium"
                    _FONT_LOADED = True
            else:
                # On macOS/Linux, the font might need different handling
                # Try to use pyglet or other library if available
                try:
                    import pyglet
                    pyglet.font.add_file(FONT_PATH)
                    _FONT_FAMILY = "Helvetica Neue Medium"
                    _FONT_LOADED = True
                except ImportError:
                    pass
        except Exception as e:
            print(f"Could not load custom font: {e}")
    
    return _FONT_FAMILY


def get_font_family() -> str:
    """Get the current font family name."""
    return _FONT_FAMILY


def get_font(size: int = 14, weight: str = "normal") -> ctk.CTkFont:
    """Get a CTkFont with the application font family."""
    return ctk.CTkFont(family=_FONT_FAMILY, size=size, weight=weight)


def get_font_path() -> str:
    """Get the path to the custom font file."""
    return FONT_PATH if os.path.exists(FONT_PATH) else None
