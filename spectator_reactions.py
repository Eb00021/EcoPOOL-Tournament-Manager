"""
EcoPOOL League - Spectator Reactions
Allows web viewers to send reactions that appear on the main display.
"""

import threading
import time
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import List, Dict, Callable, Optional
from collections import deque


@dataclass
class Reaction:
    """Represents a spectator reaction."""
    id: int
    emoji: str
    text: str
    sender: str
    timestamp: datetime
    expires_at: datetime


# Available reaction types
REACTIONS = {
    'ecocar': {'emoji': '🚗', 'text': 'EcoCAR!'},
    'nice_shot': {'emoji': '🎯', 'text': 'Nice shot!'},
    'great_game': {'emoji': '🔥', 'text': 'Great game!'},
    'gg': {'emoji': '👏', 'text': 'GG!'},
    'wow': {'emoji': '😮', 'text': 'WOW!'},
    'clutch': {'emoji': '💪', 'text': 'CLUTCH!'},
    'pool': {'emoji': '🎱', 'text': ''},
    'trophy': {'emoji': '🏆', 'text': ''},
    'fire': {'emoji': '🔥', 'text': ''},
    'star': {'emoji': '⭐', 'text': ''},
    'heart': {'emoji': '❤️', 'text': ''},
    'laughing': {'emoji': '😂', 'text': ''},
    'thinking': {'emoji': '🤔', 'text': ''},
}


class ReactionManager:
    """Manages spectator reactions."""

    def __init__(self, display_duration: int = 5, max_reactions: int = 20):
        """Initialize the reaction manager.

        Args:
            display_duration: How long reactions are displayed (seconds)
            max_reactions: Maximum number of reactions to keep
        """
        self.display_duration = display_duration
        self.max_reactions = max_reactions
        self._reactions: deque = deque(maxlen=max_reactions)
        self._reaction_id = 0
        self._lock = threading.Lock()
        self._callbacks: List[Callable] = []
        self._rate_limits: Dict[str, datetime] = {}
        self._rate_limit_seconds = 2  # Minimum seconds between reactions per IP

    def add_reaction(self, reaction_type: str, sender: str = "Anonymous",
                    client_ip: str = None) -> Optional[Reaction]:
        """Add a new reaction.

        Args:
            reaction_type: Key from REACTIONS dict
            sender: Name of the sender
            client_ip: IP address for rate limiting

        Returns:
            The created Reaction, or None if rate limited
        """
        if reaction_type not in REACTIONS:
            return None

        # Rate limiting
        if client_ip:
            with self._lock:
                last_reaction = self._rate_limits.get(client_ip)
                now = datetime.now()

                if last_reaction and (now - last_reaction).total_seconds() < self._rate_limit_seconds:
                    return None  # Rate limited

                self._rate_limits[client_ip] = now

                # Clean old rate limit entries
                cutoff = now - timedelta(minutes=5)
                self._rate_limits = {k: v for k, v in self._rate_limits.items() if v > cutoff}

        reaction_data = REACTIONS[reaction_type]

        with self._lock:
            self._reaction_id += 1
            now = datetime.now()

            reaction = Reaction(
                id=self._reaction_id,
                emoji=reaction_data['emoji'],
                text=reaction_data['text'],
                sender=sender[:20],  # Limit sender name length
                timestamp=now,
                expires_at=now + timedelta(seconds=self.display_duration)
            )

            self._reactions.append(reaction)

        # Notify callbacks
        self._notify_reaction(reaction)

        return reaction

    def get_active_reactions(self) -> List[Reaction]:
        """Get all currently active (non-expired) reactions."""
        now = datetime.now()

        with self._lock:
            return [r for r in self._reactions if r.expires_at > now]

    def get_reaction_json(self) -> List[Dict]:
        """Get active reactions as JSON-serializable list."""
        return [
            {
                'id': r.id,
                'emoji': r.emoji,
                'text': r.text,
                'sender': r.sender,
                'timestamp': r.timestamp.isoformat()
            }
            for r in self.get_active_reactions()
        ]

    def register_callback(self, callback: Callable):
        """Register a callback for new reactions.

        Callback receives (reaction: Reaction) as argument.
        """
        self._callbacks.append(callback)

    def unregister_callback(self, callback: Callable):
        """Unregister a reaction callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def _notify_reaction(self, reaction: Reaction):
        """Notify all callbacks of a new reaction."""
        for callback in self._callbacks:
            try:
                callback(reaction)
            except Exception:
                pass

    def clear(self):
        """Clear all reactions."""
        with self._lock:
            self._reactions.clear()


# Global reaction manager
_reaction_manager: Optional[ReactionManager] = None


def get_reaction_manager() -> ReactionManager:
    """Get the global reaction manager."""
    global _reaction_manager
    if _reaction_manager is None:
        _reaction_manager = ReactionManager()
    return _reaction_manager


# Flask routes for reactions (to be added to web_server.py)
REACTION_ROUTES_HTML = '''
<!-- Reaction bar -->
<div class="reaction-bar">
    <div class="reaction-buttons">
        <button class="reaction-btn" onclick="sendReaction('nice_shot')">🎯</button>
        <button class="reaction-btn" onclick="sendReaction('fire')">🔥</button>
        <button class="reaction-btn" onclick="sendReaction('clutch')">💪</button>
        <button class="reaction-btn" onclick="sendReaction('gg')">👏</button>
        <button class="reaction-btn" onclick="sendReaction('trophy')">🏆</button>
        <button class="reaction-btn" onclick="sendReaction('wow')">😮</button>
        <button class="reaction-btn" onclick="sendReaction('heart')">❤️</button>
        <button class="reaction-btn" onclick="sendReaction('pool')">🎱</button>
    </div>
</div>

<!-- Reaction display overlay -->
<div class="reaction-overlay" id="reactionOverlay"></div>

<style>
.reaction-bar {
    position: fixed;
    bottom: 20px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(0, 0, 0, 0.8);
    border-radius: 30px;
    padding: 10px 20px;
    z-index: 1000;
}

.reaction-buttons {
    display: flex;
    gap: 10px;
}

.reaction-btn {
    width: 45px;
    height: 45px;
    border-radius: 50%;
    border: none;
    background: rgba(255, 255, 255, 0.1);
    font-size: 24px;
    cursor: pointer;
    transition: transform 0.2s, background 0.2s;
}

.reaction-btn:hover {
    transform: scale(1.2);
    background: rgba(255, 255, 255, 0.2);
}

.reaction-btn:active {
    transform: scale(0.95);
}

.reaction-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    pointer-events: none;
    z-index: 999;
}

.floating-reaction {
    position: absolute;
    font-size: 48px;
    animation: floatUp 3s ease-out forwards;
    pointer-events: none;
}

@keyframes floatUp {
    0% {
        opacity: 1;
        transform: translateY(0) scale(1);
    }
    100% {
        opacity: 0;
        transform: translateY(-200px) scale(1.5);
    }
}
</style>

<script>
let reactionCooldown = false;

function sendReaction(type) {
    if (reactionCooldown) return;

    reactionCooldown = true;
    setTimeout(() => reactionCooldown = false, 2000);

    fetch('/api/reaction', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({type: type})
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            showLocalReaction(data.reaction.emoji);
        }
    })
    .catch(err => console.log('Reaction error:', err));
}

function showLocalReaction(emoji) {
    const overlay = document.getElementById('reactionOverlay');
    const reaction = document.createElement('div');
    reaction.className = 'floating-reaction';
    reaction.textContent = emoji;
    reaction.style.left = (Math.random() * 80 + 10) + '%';
    reaction.style.bottom = '100px';
    overlay.appendChild(reaction);

    setTimeout(() => reaction.remove(), 3000);
}

// Listen for reactions from SSE
if (typeof eventSource !== 'undefined') {
    eventSource.addEventListener('reaction', function(e) {
        const data = JSON.parse(e.data);
        showLocalReaction(data.emoji);
    });
}
</script>
'''
