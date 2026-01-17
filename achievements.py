"""
EcoPOOL League - Achievement/Badge System
Tracks player achievements and milestones with animated unlock effects.
"""

import json
from dataclasses import dataclass
from typing import Optional, List, Dict, Callable
from datetime import datetime


@dataclass
class Achievement:
    """Represents an achievement/badge."""
    id: str
    name: str
    description: str
    icon: str
    category: str  # 'milestone', 'skill', 'streak', 'special'
    tier: str  # 'bronze', 'silver', 'gold', 'platinum'
    requirement: int  # Numeric requirement (games, wins, etc.)
    requirement_type: str  # 'games_played', 'games_won', 'win_streak', 'golden_breaks', etc.
    points: int  # Achievement points


# Define all achievements
ACHIEVEMENTS = [
    # Milestone achievements - Games Played
    Achievement("first_game", "First Steps", "Play your first game", "🎱", "milestone", "bronze", 1, "games_played", 10),
    Achievement("games_10", "Getting Started", "Play 10 games", "🎯", "milestone", "bronze", 10, "games_played", 25),
    Achievement("games_25", "Regular", "Play 25 games", "⭐", "milestone", "silver", 25, "games_played", 50),
    Achievement("games_50", "Dedicated", "Play 50 games", "🌟", "milestone", "silver", 50, "games_played", 100),
    Achievement("games_100", "Century Club", "Play 100 games", "💯", "milestone", "gold", 100, "games_played", 200),
    Achievement("games_250", "League Veteran", "Play 250 games", "🏅", "milestone", "gold", 250, "games_played", 500),
    Achievement("games_500", "Pool Legend", "Play 500 games", "👑", "milestone", "platinum", 500, "games_played", 1000),

    # Milestone achievements - Wins
    Achievement("first_win", "Winner!", "Win your first game", "🏆", "milestone", "bronze", 1, "games_won", 15),
    Achievement("wins_10", "On a Roll", "Win 10 games", "🔥", "milestone", "bronze", 10, "games_won", 30),
    Achievement("wins_25", "Competitor", "Win 25 games", "💪", "milestone", "silver", 25, "games_won", 75),
    Achievement("wins_50", "Champion", "Win 50 games", "🏆", "milestone", "silver", 50, "games_won", 150),
    Achievement("wins_100", "Master", "Win 100 games", "🎖️", "milestone", "gold", 100, "games_won", 300),
    Achievement("wins_200", "Grandmaster", "Win 200 games", "👑", "milestone", "platinum", 200, "games_won", 600),

    # Win streak achievements
    Achievement("streak_3", "Hat Trick", "Win 3 games in a row", "🎩", "streak", "bronze", 3, "win_streak", 30),
    Achievement("streak_5", "Hot Hand", "Win 5 games in a row", "🔥", "streak", "silver", 5, "win_streak", 75),
    Achievement("streak_7", "Unstoppable", "Win 7 games in a row", "💥", "streak", "gold", 7, "win_streak", 150),
    Achievement("streak_10", "Legendary Streak", "Win 10 games in a row", "⚡", "streak", "platinum", 10, "win_streak", 300),

    # Skill achievements - Golden Breaks
    Achievement("first_golden", "Golden!", "Get your first Golden Break", "✨", "skill", "silver", 1, "golden_breaks", 50),
    Achievement("golden_3", "Golden Touch", "Get 3 Golden Breaks", "🌟", "skill", "gold", 3, "golden_breaks", 100),
    Achievement("golden_5", "Midas", "Get 5 Golden Breaks", "👑", "skill", "platinum", 5, "golden_breaks", 200),
    Achievement("golden_10", "Golden God", "Get 10 Golden Breaks", "🏆", "skill", "platinum", 10, "golden_breaks", 500),

    # Skill achievements - 8-Ball sinks
    Achievement("eight_ball_10", "8-Ball Expert", "Legally sink the 8-ball 10 times", "🎱", "skill", "bronze", 10, "eight_ball_sinks", 25),
    Achievement("eight_ball_25", "8-Ball Master", "Legally sink the 8-ball 25 times", "🎱", "skill", "silver", 25, "eight_ball_sinks", 75),
    Achievement("eight_ball_50", "8-Ball Legend", "Legally sink the 8-ball 50 times", "🎱", "skill", "gold", 50, "eight_ball_sinks", 150),

    # Points achievements
    Achievement("points_100", "Point Scorer", "Accumulate 100 total points", "💎", "milestone", "bronze", 100, "total_points", 20),
    Achievement("points_500", "Point Collector", "Accumulate 500 total points", "💎", "milestone", "silver", 500, "total_points", 75),
    Achievement("points_1000", "Point Master", "Accumulate 1000 total points", "💎", "milestone", "gold", 1000, "total_points", 200),
    Achievement("points_2500", "Point Legend", "Accumulate 2500 total points", "💎", "milestone", "platinum", 2500, "total_points", 500),

    # Win rate achievements (require minimum games)
    Achievement("winrate_60", "Above Average", "Maintain 60%+ win rate (min 20 games)", "📈", "skill", "bronze", 60, "win_rate_20", 50),
    Achievement("winrate_70", "Skilled Player", "Maintain 70%+ win rate (min 30 games)", "📈", "skill", "silver", 70, "win_rate_30", 100),
    Achievement("winrate_80", "Elite Player", "Maintain 80%+ win rate (min 50 games)", "📈", "skill", "gold", 80, "win_rate_50", 250),

    # Special achievements
    Achievement("perfect_night", "Perfect Night", "Win all games in a single league night (min 3)", "🌙", "special", "gold", 1, "perfect_night", 200),
    Achievement("comeback_king", "Comeback King", "Win a match after losing the first game", "👑", "special", "silver", 1, "comeback_win", 75),
    Achievement("underdog", "Giant Slayer", "Beat a player ranked 5+ spots above you", "🗡️", "special", "silver", 1, "underdog_win", 50),
    Achievement("rivalry_winner", "Rivalry Master", "Beat the same opponent 5 times", "⚔️", "special", "gold", 5, "rivalry_wins", 100),

    # Partner achievements
    Achievement("dynamic_duo", "Dynamic Duo", "Win 10 games with the same partner", "🤝", "special", "silver", 10, "partner_wins", 75),
    Achievement("perfect_partners", "Perfect Partners", "Win 25 games with the same partner", "💫", "special", "gold", 25, "partner_wins", 200),
]

# Create lookup dictionary
ACHIEVEMENTS_BY_ID = {a.id: a for a in ACHIEVEMENTS}

# Tier colors for display
TIER_COLORS = {
    'bronze': '#CD7F32',
    'silver': '#C0C0C0',
    'gold': '#FFD700',
    'platinum': '#E5E4E2'
}

TIER_BG_COLORS = {
    'bronze': '#3D2A1A',
    'silver': '#2A2A2A',
    'gold': '#3D3A1A',
    'platinum': '#2A2D3A'
}


class AchievementManager:
    """Manages player achievements and checks for unlocks."""

    def __init__(self, db_manager):
        self.db = db_manager
        self._init_achievements_table()
        self._callbacks: List[Callable] = []  # Achievement unlock callbacks

    def _init_achievements_table(self):
        """Initialize the achievements table in the database."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS player_achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER NOT NULL,
                achievement_id TEXT NOT NULL,
                unlocked_at TEXT DEFAULT CURRENT_TIMESTAMP,
                progress INTEGER DEFAULT 0,
                FOREIGN KEY (player_id) REFERENCES players(id),
                UNIQUE(player_id, achievement_id)
            )
        ''')

        # Track win streaks
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS player_streaks (
                player_id INTEGER PRIMARY KEY,
                current_win_streak INTEGER DEFAULT 0,
                max_win_streak INTEGER DEFAULT 0,
                last_game_result TEXT DEFAULT '',
                FOREIGN KEY (player_id) REFERENCES players(id)
            )
        ''')

        conn.commit()

    def register_unlock_callback(self, callback: Callable):
        """Register a callback to be called when an achievement is unlocked.
        Callback receives (player_id, achievement) as arguments."""
        self._callbacks.append(callback)

    def _notify_unlock(self, player_id: int, achievement: Achievement):
        """Notify all registered callbacks of an achievement unlock."""
        for callback in self._callbacks:
            try:
                callback(player_id, achievement)
            except Exception:
                pass  # Don't let callback errors affect the app

    def get_player_achievements(self, player_id: int) -> List[Dict]:
        """Get all achievements for a player (unlocked and locked)."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT achievement_id, unlocked_at, progress
            FROM player_achievements
            WHERE player_id = ?
        ''', (player_id,))

        unlocked = {row['achievement_id']: {
            'unlocked_at': row['unlocked_at'],
            'progress': row['progress']
        } for row in cursor.fetchall()}

        # Get player stats for progress calculation
        player = self.db.get_player(player_id)
        if not player:
            return []

        result = []
        for achievement in ACHIEVEMENTS:
            is_unlocked = achievement.id in unlocked
            progress = self._calculate_progress(player, achievement)

            result.append({
                'achievement': achievement,
                'unlocked': is_unlocked,
                'unlocked_at': unlocked.get(achievement.id, {}).get('unlocked_at'),
                'progress': progress,
                'progress_percent': min(100, int((progress / achievement.requirement) * 100))
            })

        return result

    def get_unlocked_achievements(self, player_id: int) -> List[Achievement]:
        """Get only unlocked achievements for a player."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT achievement_id FROM player_achievements
            WHERE player_id = ?
        ''', (player_id,))

        unlocked_ids = [row['achievement_id'] for row in cursor.fetchall()]
        return [ACHIEVEMENTS_BY_ID[aid] for aid in unlocked_ids if aid in ACHIEVEMENTS_BY_ID]

    def _calculate_progress(self, player, achievement: Achievement) -> int:
        """Calculate current progress toward an achievement."""
        req_type = achievement.requirement_type

        if req_type == 'games_played':
            return player.games_played
        elif req_type == 'games_won':
            return player.games_won
        elif req_type == 'golden_breaks':
            return player.golden_breaks
        elif req_type == 'eight_ball_sinks':
            return player.eight_ball_sinks
        elif req_type == 'total_points':
            return player.total_points
        elif req_type == 'win_streak':
            return self._get_max_win_streak(player.id)
        elif req_type.startswith('win_rate_'):
            min_games = int(req_type.split('_')[-1])
            if player.games_played >= min_games:
                return int(player.win_rate)
            return 0

        return 0

    def _get_max_win_streak(self, player_id: int) -> int:
        """Get the maximum win streak for a player."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT max_win_streak FROM player_streaks WHERE player_id = ?
        ''', (player_id,))

        row = cursor.fetchone()
        return row['max_win_streak'] if row else 0

    def check_and_unlock_achievements(self, player_id: int) -> List[Achievement]:
        """Check all achievements and unlock any that are earned.
        Returns list of newly unlocked achievements."""
        player = self.db.get_player(player_id)
        if not player:
            return []

        newly_unlocked = []

        for achievement in ACHIEVEMENTS:
            if self._check_achievement(player, achievement):
                if self._unlock_achievement(player_id, achievement.id):
                    newly_unlocked.append(achievement)
                    self._notify_unlock(player_id, achievement)

        return newly_unlocked

    def _check_achievement(self, player, achievement: Achievement) -> bool:
        """Check if a player has earned an achievement."""
        progress = self._calculate_progress(player, achievement)
        return progress >= achievement.requirement

    def _unlock_achievement(self, player_id: int, achievement_id: str) -> bool:
        """Unlock an achievement for a player. Returns True if newly unlocked."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute('''
                INSERT INTO player_achievements (player_id, achievement_id, progress)
                VALUES (?, ?, ?)
            ''', (player_id, achievement_id, ACHIEVEMENTS_BY_ID[achievement_id].requirement))
            conn.commit()
            return True
        except Exception:
            return False  # Already unlocked

    def update_win_streak(self, player_id: int, won: bool):
        """Update a player's win streak after a game."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Get or create streak record
        cursor.execute('SELECT * FROM player_streaks WHERE player_id = ?', (player_id,))
        row = cursor.fetchone()

        if row:
            current_streak = row['current_win_streak']
            max_streak = row['max_win_streak']
        else:
            current_streak = 0
            max_streak = 0

        if won:
            current_streak += 1
            if current_streak > max_streak:
                max_streak = current_streak
        else:
            current_streak = 0

        cursor.execute('''
            INSERT INTO player_streaks (player_id, current_win_streak, max_win_streak, last_game_result)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(player_id) DO UPDATE SET
                current_win_streak = excluded.current_win_streak,
                max_win_streak = excluded.max_win_streak,
                last_game_result = excluded.last_game_result
        ''', (player_id, current_streak, max_streak, 'win' if won else 'loss'))

        conn.commit()

    def get_total_achievement_points(self, player_id: int) -> int:
        """Get total achievement points for a player."""
        unlocked = self.get_unlocked_achievements(player_id)
        return sum(a.points for a in unlocked)

    def get_leaderboard_by_achievements(self) -> List[Dict]:
        """Get players ranked by achievement points."""
        players = self.db.get_all_players()

        leaderboard = []
        for player in players:
            points = self.get_total_achievement_points(player.id)
            unlocked = self.get_unlocked_achievements(player.id)

            leaderboard.append({
                'player': player,
                'achievement_points': points,
                'achievements_unlocked': len(unlocked),
                'achievements_total': len(ACHIEVEMENTS)
            })

        leaderboard.sort(key=lambda x: (-x['achievement_points'], -x['achievements_unlocked']))
        return leaderboard
