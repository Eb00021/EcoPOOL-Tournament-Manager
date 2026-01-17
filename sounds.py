"""
EcoPOOL League - Sound Effects Module
Provides audio feedback for game events.
"""

import os
import threading
from typing import Optional, Dict
from dataclasses import dataclass

# Try to import audio libraries
try:
    import winsound
    HAS_WINSOUND = True
except ImportError:
    HAS_WINSOUND = False

try:
    from playsound import playsound
    HAS_PLAYSOUND = True
except ImportError:
    HAS_PLAYSOUND = False


@dataclass
class SoundEffect:
    """Represents a sound effect."""
    name: str
    filename: str
    fallback_frequency: int  # Hz for winsound beep fallback
    fallback_duration: int   # ms for winsound beep fallback


# Define sound effects with fallback beep tones
SOUNDS = {
    'ball_pocket': SoundEffect('Ball Pocketed', 'ball_pocket.wav', 800, 100),
    'ball_pocket_stripe': SoundEffect('Stripe Pocketed', 'ball_pocket_stripe.wav', 600, 100),
    '8ball_pocket': SoundEffect('8-Ball Pocketed', '8ball_pocket.wav', 400, 300),
    'golden_break': SoundEffect('Golden Break!', 'golden_break.wav', 1200, 500),
    'game_win': SoundEffect('Game Won', 'game_win.wav', 1000, 200),
    'match_win': SoundEffect('Match Won!', 'match_win.wav', 1500, 400),
    'foul': SoundEffect('Foul', 'foul.wav', 300, 200),
    'early_8ball': SoundEffect('Early 8-Ball Foul', 'early_8ball.wav', 200, 400),
    'button_click': SoundEffect('Button Click', 'click.wav', 1000, 50),
    'notification': SoundEffect('Notification', 'notification.wav', 880, 150),
    'achievement': SoundEffect('Achievement Unlocked!', 'achievement.wav', 1318, 300),
    'countdown': SoundEffect('Countdown Tick', 'tick.wav', 440, 100),
    'start': SoundEffect('Match Start', 'start.wav', 660, 200),
}


class SoundManager:
    """Manages sound effects for the application."""

    def __init__(self, sounds_dir: str = None):
        """Initialize the sound manager.

        Args:
            sounds_dir: Directory containing sound files. If None, uses ./sounds/
        """
        self.sounds_dir = sounds_dir or os.path.join(os.path.dirname(__file__), 'sounds')
        self.enabled = True
        self.volume = 1.0  # 0.0 to 1.0
        self._playing = False
        self._play_lock = threading.Lock()

        # Cache for sound file paths
        self._sound_paths: Dict[str, str] = {}
        self._init_sound_paths()

    def _init_sound_paths(self):
        """Initialize paths to sound files."""
        if not os.path.exists(self.sounds_dir):
            try:
                os.makedirs(self.sounds_dir)
            except OSError:
                pass

        for key, sound in SOUNDS.items():
            path = os.path.join(self.sounds_dir, sound.filename)
            if os.path.exists(path):
                self._sound_paths[key] = path

    def set_enabled(self, enabled: bool):
        """Enable or disable sounds."""
        self.enabled = enabled

    def set_volume(self, volume: float):
        """Set volume level (0.0 to 1.0)."""
        self.volume = max(0.0, min(1.0, volume))

    def play(self, sound_key: str, blocking: bool = False):
        """Play a sound effect.

        Args:
            sound_key: Key from SOUNDS dictionary
            blocking: If True, wait for sound to finish
        """
        if not self.enabled:
            return

        if sound_key not in SOUNDS:
            return

        if blocking:
            self._play_sound(sound_key)
        else:
            # Play in background thread
            thread = threading.Thread(target=self._play_sound, args=(sound_key,), daemon=True)
            thread.start()

    def _play_sound(self, sound_key: str):
        """Internal method to play a sound."""
        with self._play_lock:
            if self._playing:
                return  # Don't overlap sounds
            self._playing = True

        try:
            sound = SOUNDS[sound_key]

            # Try to play actual sound file
            if sound_key in self._sound_paths:
                self._play_file(self._sound_paths[sound_key])
            else:
                # Fallback to system beep
                self._play_beep(sound.fallback_frequency, sound.fallback_duration)

        finally:
            self._playing = False

    def _play_file(self, filepath: str):
        """Play a sound file."""
        try:
            if HAS_PLAYSOUND:
                playsound(filepath, block=True)
            elif HAS_WINSOUND:
                winsound.PlaySound(filepath, winsound.SND_FILENAME)
        except Exception:
            pass  # Silently fail

    def _play_beep(self, frequency: int, duration: int):
        """Play a system beep as fallback."""
        if not HAS_WINSOUND:
            return

        try:
            # Adjust duration based on volume
            adjusted_duration = int(duration * self.volume)
            if adjusted_duration > 0:
                winsound.Beep(frequency, adjusted_duration)
        except Exception:
            pass

    # Convenience methods for common sounds
    def play_ball_pocket(self, is_stripe: bool = False):
        """Play ball pocketed sound."""
        self.play('ball_pocket_stripe' if is_stripe else 'ball_pocket')

    def play_8ball_pocket(self):
        """Play 8-ball pocketed sound."""
        self.play('8ball_pocket')

    def play_golden_break(self):
        """Play golden break sound."""
        self.play('golden_break')

    def play_game_win(self):
        """Play game won sound."""
        self.play('game_win')

    def play_match_win(self):
        """Play match won sound."""
        self.play('match_win')

    def play_foul(self):
        """Play foul sound."""
        self.play('foul')

    def play_early_8ball(self):
        """Play early 8-ball foul sound."""
        self.play('early_8ball')

    def play_click(self):
        """Play button click sound."""
        self.play('button_click')

    def play_notification(self):
        """Play notification sound."""
        self.play('notification')

    def play_achievement(self):
        """Play achievement unlocked sound."""
        self.play('achievement')

    def play_start(self):
        """Play match start sound."""
        self.play('start')


# Global sound manager instance
_sound_manager: Optional[SoundManager] = None


def get_sound_manager() -> SoundManager:
    """Get the global sound manager instance."""
    global _sound_manager
    if _sound_manager is None:
        _sound_manager = SoundManager()
    return _sound_manager


def play_sound(sound_key: str, blocking: bool = False):
    """Convenience function to play a sound."""
    get_sound_manager().play(sound_key, blocking)
