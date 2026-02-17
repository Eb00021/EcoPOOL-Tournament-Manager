"""
EcoPOOL League - AI Pair Name Generator
Generates creative pool-themed team names for player pairs using the Anthropic Claude API.
Falls back to a curated list of names when the API is unavailable.
"""

import os
import threading

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

FALLBACK_NAMES = [
    "The Scratch Artists",
    "Eight Ball Outlaws",
    "Rack 'Em Rangers",
    "The Golden Breakers",
    "Felt Fury",
    "Corner Pocket Crew",
    "The Hustlers",
    "Chalk Dust Posse",
    "The Bridge Bandits",
    "Cue-pid's Arrows",
    "The Dead Stripes",
    "No Mercy Nine-Balls",
    "The Miscue Maestros",
    "Rail Birds",
    "The Long Shots",
]


class PairNameGenerator:
    """Generates AI-powered team names for player pairs."""

    def __init__(self, db):
        self.db = db
        self._client = None
        self._client_initialized = False

    def _get_client(self):
        """Lazily initialize the Anthropic client."""
        if self._client_initialized:
            return self._client

        self._client_initialized = True

        if not ANTHROPIC_AVAILABLE:
            return None

        api_key = self.db.get_setting("anthropic_api_key", "") or os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            return None

        try:
            self._client = anthropic.Anthropic(api_key=api_key)
        except Exception:
            self._client = None

        return self._client

    def _build_prompt(self, p1_stats: dict, p2_stats: dict) -> str:
        """Build the Claude prompt from player stats."""
        def describe_player(stats: dict) -> str:
            parts = []
            form = stats.get("form_trend", "neutral")
            if form != "neutral":
                parts.append(f"form: {form}")
            streak_count = stats.get("streak_count", 0)
            streak_type = stats.get("streak_type", "none")
            if streak_count >= 2 and streak_type != "none":
                parts.append(f"{streak_count}-game {streak_type} streak")
            golden = stats.get("golden_breaks", 0)
            if golden > 0:
                parts.append(f"{golden} golden break{'s' if golden > 1 else ''}")
            win_rate = stats.get("win_rate", 0.0)
            parts.append(f"{win_rate:.0f}% win rate")
            clutch = stats.get("clutch_rating", 0.0)
            if clutch > 60:
                parts.append("clutch player")
            elif clutch < 40:
                parts.append("struggles under pressure")
            eight_ball = stats.get("eight_ball_sinks", 0)
            if eight_ball > 0:
                parts.append(f"{eight_ball} legal 8-ball win{'s' if eight_ball > 1 else ''}")
            avg_pts = stats.get("avg_points", 0.0)
            parts.append(f"{avg_pts:.1f} avg pts/game")
            return ", ".join(parts) if parts else "new player"

        p1_desc = describe_player(p1_stats)
        p2_desc = describe_player(p2_stats)

        return (
            f"You are naming a pool/billiards duo. Create ONE creative, funny, or intimidating "
            f"pool-themed team name for this pair. Maximum 4 words. Reply with the name only, "
            f"no explanation.\n\n"
            f"Player 1: {p1_desc}\n"
            f"Player 2: {p2_desc}"
        )

    def _get_player_stats(self, player_id: int) -> dict:
        """Fetch combined stats for a player."""
        stats = {
            "form_trend": "neutral",
            "streak_count": 0,
            "streak_type": "none",
            "golden_breaks": 0,
            "win_rate": 0.0,
            "clutch_rating": 50.0,
            "eight_ball_sinks": 0,
            "avg_points": 0.0,
        }
        try:
            player = self.db.get_player(player_id)
            if player:
                stats["golden_breaks"] = player.golden_breaks
                stats["win_rate"] = player.win_rate
                stats["eight_ball_sinks"] = player.eight_ball_sinks
                stats["avg_points"] = player.avg_points

            from advanced_stats import AdvancedStatsManager
            mgr = AdvancedStatsManager(self.db)

            streak = mgr.get_player_streak(player_id)
            if streak:
                stats["streak_count"] = streak.streak_count
                stats["streak_type"] = streak.streak_type

            form = mgr.get_player_form(player_id)
            if form:
                stats["form_trend"] = form.form_trend
                stats["clutch_rating"] = form.clutch_rating
        except Exception:
            pass
        return stats

    def generate_name_for_pair(self, player1_id: int, player2_id: int, pair_idx: int) -> str:
        """Generate a name for a single pair. Returns fallback on any error."""
        try:
            client = self._get_client()
            if client is None:
                return FALLBACK_NAMES[pair_idx % len(FALLBACK_NAMES)]

            p1_stats = self._get_player_stats(player1_id)
            p2_stats = self._get_player_stats(player2_id) if player2_id else {}

            prompt = self._build_prompt(p1_stats, p2_stats)

            message = client.messages.create(
                model="claude-haiku-4-5",
                max_tokens=30,
                messages=[{"role": "user", "content": prompt}]
            )

            raw = message.content[0].text.strip()
            # Sanitize: strip quotes, limit length, reject if too long or empty
            raw = raw.strip('"\'')
            words = raw.split()
            if not words or len(words) > 6 or len(raw) > 50:
                return FALLBACK_NAMES[pair_idx % len(FALLBACK_NAMES)]
            return raw

        except Exception:
            return FALLBACK_NAMES[pair_idx % len(FALLBACK_NAMES)]

    def generate_names_for_all_pairs(self, pairs: list, on_name_ready=None,
                                     on_complete=None, use_threading=True):
        """Generate names for all pairs. Fires callbacks as names arrive."""
        def _run():
            for i, (p1_id, p2_id) in enumerate(pairs):
                if p2_id is None:
                    name = FALLBACK_NAMES[i % len(FALLBACK_NAMES)]
                else:
                    name = self.generate_name_for_pair(p1_id, p2_id, i)
                if on_name_ready:
                    on_name_ready(i, name)
            if on_complete:
                on_complete()

        if use_threading:
            t = threading.Thread(target=_run, daemon=True)
            t.start()
        else:
            _run()
