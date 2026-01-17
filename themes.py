"""
EcoPOOL League - Theme Manager
Handles dark/light mode switching and custom color schemes.
"""

import customtkinter as ctk
from dataclasses import dataclass
from typing import Dict, Optional, Callable, List


@dataclass
class Theme:
    """Represents a color theme."""
    name: str
    mode: str  # 'dark' or 'light'

    # Main colors
    bg_primary: str
    bg_secondary: str
    bg_tertiary: str

    # Text colors
    text_primary: str
    text_secondary: str
    text_muted: str

    # Accent colors
    accent_primary: str
    accent_secondary: str
    accent_success: str
    accent_warning: str
    accent_error: str

    # Component colors
    sidebar_bg: str
    card_bg: str
    button_bg: str
    button_hover: str
    input_bg: str
    border_color: str

    # Special colors
    gold: str
    silver: str
    bronze: str


# Predefined themes
THEMES = {
    'dark': Theme(
        name='Dark',
        mode='dark',
        bg_primary='#161b22',
        bg_secondary='#1a1a2e',
        bg_tertiary='#252540',
        text_primary='#ffffff',
        text_secondary='#cccccc',
        text_muted='#888888',
        accent_primary='#4CAF50',
        accent_secondary='#2d7a3e',
        accent_success='#4CAF50',
        accent_warning='#ff9800',
        accent_error='#c44536',
        sidebar_bg='#0d1117',
        card_bg='#252540',
        button_bg='#2d7a3e',
        button_hover='#1a5f2a',
        input_bg='#252540',
        border_color='#333333',
        gold='#FFD700',
        silver='#C0C0C0',
        bronze='#CD7F32'
    ),
    'light': Theme(
        name='Light',
        mode='light',
        bg_primary='#f5f5f5',
        bg_secondary='#ffffff',
        bg_tertiary='#e8e8e8',
        text_primary='#1a1a1a',
        text_secondary='#444444',
        text_muted='#888888',
        accent_primary='#2e7d32',
        accent_secondary='#43a047',
        accent_success='#2e7d32',
        accent_warning='#f57c00',
        accent_error='#c62828',
        sidebar_bg='#e0e0e0',
        card_bg='#ffffff',
        button_bg='#2e7d32',
        button_hover='#1b5e20',
        input_bg='#ffffff',
        border_color='#cccccc',
        gold='#FFD700',
        silver='#A0A0A0',
        bronze='#CD7F32'
    ),
    'midnight': Theme(
        name='Midnight',
        mode='dark',
        bg_primary='#0a0a1a',
        bg_secondary='#12122a',
        bg_tertiary='#1a1a3a',
        text_primary='#e0e0ff',
        text_secondary='#b0b0cc',
        text_muted='#6060aa',
        accent_primary='#6366f1',
        accent_secondary='#4f46e5',
        accent_success='#22c55e',
        accent_warning='#f59e0b',
        accent_error='#ef4444',
        sidebar_bg='#080818',
        card_bg='#1a1a3a',
        button_bg='#4f46e5',
        button_hover='#4338ca',
        input_bg='#1a1a3a',
        border_color='#2a2a4a',
        gold='#FFD700',
        silver='#C0C0C0',
        bronze='#CD7F32'
    ),
    'forest': Theme(
        name='Forest',
        mode='dark',
        bg_primary='#1a2e1a',
        bg_secondary='#1e3a1e',
        bg_tertiary='#2a4a2a',
        text_primary='#e0ffe0',
        text_secondary='#b0d0b0',
        text_muted='#608060',
        accent_primary='#4ade80',
        accent_secondary='#22c55e',
        accent_success='#4ade80',
        accent_warning='#fbbf24',
        accent_error='#f87171',
        sidebar_bg='#0f1f0f',
        card_bg='#2a4a2a',
        button_bg='#22c55e',
        button_hover='#16a34a',
        input_bg='#2a4a2a',
        border_color='#3a5a3a',
        gold='#FFD700',
        silver='#C0C0C0',
        bronze='#CD7F32'
    ),
    'ocean': Theme(
        name='Ocean',
        mode='dark',
        bg_primary='#0c1929',
        bg_secondary='#0f2744',
        bg_tertiary='#1a3a5c',
        text_primary='#e0f4ff',
        text_secondary='#a0c4e8',
        text_muted='#5080b0',
        accent_primary='#38bdf8',
        accent_secondary='#0ea5e9',
        accent_success='#34d399',
        accent_warning='#fbbf24',
        accent_error='#f87171',
        sidebar_bg='#081422',
        card_bg='#1a3a5c',
        button_bg='#0ea5e9',
        button_hover='#0284c7',
        input_bg='#1a3a5c',
        border_color='#2a4a6c',
        gold='#FFD700',
        silver='#C0C0C0',
        bronze='#CD7F32'
    )
}


class ThemeManager:
    """Manages application themes and appearance."""

    def __init__(self, db_manager=None):
        self.db = db_manager
        self._current_theme: Theme = THEMES['dark']
        self._callbacks: List[Callable] = []

        # Load saved theme preference
        if db_manager:
            saved_theme = db_manager.get_setting('app_theme', 'dark')
            if saved_theme in THEMES:
                self._current_theme = THEMES[saved_theme]

    @property
    def current_theme(self) -> Theme:
        """Get the current theme."""
        return self._current_theme

    @property
    def theme_name(self) -> str:
        """Get current theme name."""
        return self._current_theme.name

    @property
    def is_dark_mode(self) -> bool:
        """Check if current theme is dark mode."""
        return self._current_theme.mode == 'dark'

    def get_available_themes(self) -> List[str]:
        """Get list of available theme names."""
        return list(THEMES.keys())

    def set_theme(self, theme_name: str):
        """Set the application theme.

        Args:
            theme_name: Name of theme from THEMES dict
        """
        if theme_name not in THEMES:
            return

        self._current_theme = THEMES[theme_name]

        # Apply to customtkinter
        ctk.set_appearance_mode(self._current_theme.mode)

        # Save preference
        if self.db:
            self.db.set_setting('app_theme', theme_name)

        # Notify callbacks
        self._notify_theme_change()

    def toggle_dark_mode(self):
        """Toggle between dark and light mode."""
        if self.is_dark_mode:
            self.set_theme('light')
        else:
            self.set_theme('dark')

    def register_callback(self, callback: Callable):
        """Register a callback for theme changes.

        Callback receives the new Theme object.
        """
        self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable):
        """Unregister a theme change callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _notify_theme_change(self):
        """Notify all callbacks of theme change."""
        for callback in self._callbacks:
            try:
                callback(self._current_theme)
            except Exception:
                pass

    # ============ Color Accessors ============

    def get_color(self, color_name: str) -> str:
        """Get a color from the current theme."""
        return getattr(self._current_theme, color_name, '#ffffff')

    @property
    def bg_primary(self) -> str:
        return self._current_theme.bg_primary

    @property
    def bg_secondary(self) -> str:
        return self._current_theme.bg_secondary

    @property
    def bg_tertiary(self) -> str:
        return self._current_theme.bg_tertiary

    @property
    def text_primary(self) -> str:
        return self._current_theme.text_primary

    @property
    def text_secondary(self) -> str:
        return self._current_theme.text_secondary

    @property
    def accent_primary(self) -> str:
        return self._current_theme.accent_primary

    @property
    def accent_success(self) -> str:
        return self._current_theme.accent_success

    @property
    def accent_error(self) -> str:
        return self._current_theme.accent_error

    @property
    def card_bg(self) -> str:
        return self._current_theme.card_bg

    @property
    def sidebar_bg(self) -> str:
        return self._current_theme.sidebar_bg

    # ============ Widget Style Helpers ============

    def get_button_style(self, variant: str = 'primary') -> Dict:
        """Get button style kwargs for a variant."""
        theme = self._current_theme

        if variant == 'primary':
            return {
                'fg_color': theme.button_bg,
                'hover_color': theme.button_hover,
                'text_color': '#ffffff'
            }
        elif variant == 'secondary':
            return {
                'fg_color': theme.bg_tertiary,
                'hover_color': theme.border_color,
                'text_color': theme.text_primary
            }
        elif variant == 'success':
            return {
                'fg_color': theme.accent_success,
                'hover_color': self._darken_color(theme.accent_success, 20),
                'text_color': '#ffffff'
            }
        elif variant == 'danger':
            return {
                'fg_color': theme.accent_error,
                'hover_color': self._darken_color(theme.accent_error, 20),
                'text_color': '#ffffff'
            }
        elif variant == 'warning':
            return {
                'fg_color': theme.accent_warning,
                'hover_color': self._darken_color(theme.accent_warning, 20),
                'text_color': '#000000'
            }
        else:
            return {
                'fg_color': theme.button_bg,
                'hover_color': theme.button_hover,
                'text_color': '#ffffff'
            }

    def get_card_style(self) -> Dict:
        """Get card frame style kwargs."""
        return {
            'fg_color': self._current_theme.card_bg,
            'corner_radius': 15
        }

    def get_input_style(self) -> Dict:
        """Get input/entry style kwargs."""
        return {
            'fg_color': self._current_theme.input_bg,
            'border_color': self._current_theme.border_color,
            'text_color': self._current_theme.text_primary
        }

    def _darken_color(self, color: str, amount: int) -> str:
        """Darken a hex color."""
        if not color.startswith('#'):
            return color
        try:
            r = max(0, int(color[1:3], 16) - amount)
            g = max(0, int(color[3:5], 16) - amount)
            b = max(0, int(color[5:7], 16) - amount)
            return f"#{r:02x}{g:02x}{b:02x}"
        except:
            return color

    def _lighten_color(self, color: str, amount: int) -> str:
        """Lighten a hex color."""
        if not color.startswith('#'):
            return color
        try:
            r = min(255, int(color[1:3], 16) + amount)
            g = min(255, int(color[3:5], 16) + amount)
            b = min(255, int(color[5:7], 16) + amount)
            return f"#{r:02x}{g:02x}{b:02x}"
        except:
            return color


# Global theme manager instance
_theme_manager: Optional[ThemeManager] = None


def get_theme_manager(db_manager=None) -> ThemeManager:
    """Get the global theme manager instance."""
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = ThemeManager(db_manager)
    return _theme_manager


def get_current_theme() -> Theme:
    """Get the current theme."""
    return get_theme_manager().current_theme
