"""
EcoPOOL League - Database Manager
SQLite database for persistent storage of players, matches, and statistics.
"""

import sqlite3
from datetime import datetime
from typing import Optional
from dataclasses import dataclass
import json


@dataclass
class Player:
    id: Optional[int]
    name: str
    email: str = ""
    venmo: str = ""
    created_at: str = ""
    profile_picture: str = ""  # Path to profile picture or avatar ID
    # Stats (computed from matches)
    games_played: int = 0
    games_won: int = 0
    total_points: int = 0
    golden_breaks: int = 0
    
    @property
    def win_rate(self) -> float:
        if self.games_played == 0:
            return 0.0
        return (self.games_won / self.games_played) * 100
    
    @property
    def avg_points(self) -> float:
        if self.games_played == 0:
            return 0.0
        return self.total_points / self.games_played


@dataclass
class Match:
    id: Optional[int]
    date: str
    team1_player1_id: int
    team1_player2_id: Optional[int]  # None for lone wolf
    team2_player1_id: int
    team2_player2_id: Optional[int]  # None for lone wolf
    best_of: int = 3
    is_finals: bool = False
    is_complete: bool = False
    

@dataclass
class Game:
    id: Optional[int]
    match_id: int
    game_number: int
    team1_score: int = 0
    team2_score: int = 0
    team1_group: str = ""  # "solids" or "stripes"
    balls_pocketed: str = ""  # JSON string of ball states
    winner_team: int = 0  # 1 or 2, 0 if not complete
    golden_break: bool = False
    early_8ball_team: int = 0  # Team that committed early 8-ball foul (0 if none)
    breaking_team: int = 1  # 1 or 2


class DatabaseManager:
    def __init__(self, db_path: str = "ecopool_league.db"):
        self.db_path = db_path
        self.conn = None
        self.init_database()
    
    def get_connection(self) -> sqlite3.Connection:
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
        return self.conn
    
    def init_database(self):
        """Initialize database tables."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Players table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                email TEXT DEFAULT '',
                venmo TEXT DEFAULT '',
                profile_picture TEXT DEFAULT '',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                active INTEGER DEFAULT 1
            )
        ''')
        
        # Add profile_picture column if it doesn't exist (migration for existing DBs)
        try:
            cursor.execute("ALTER TABLE players ADD COLUMN profile_picture TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        # League nights table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS league_nights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                location TEXT DEFAULT 'The Met Pool Hall',
                buy_in REAL DEFAULT 0,
                notes TEXT DEFAULT ''
            )
        ''')
        
        # Matches table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league_night_id INTEGER,
                date TEXT DEFAULT CURRENT_TIMESTAMP,
                team1_player1_id INTEGER NOT NULL,
                team1_player2_id INTEGER,
                team2_player1_id INTEGER NOT NULL,
                team2_player2_id INTEGER,
                table_number INTEGER DEFAULT 1,
                best_of INTEGER DEFAULT 3,
                is_finals INTEGER DEFAULT 0,
                is_complete INTEGER DEFAULT 0,
                FOREIGN KEY (league_night_id) REFERENCES league_nights(id),
                FOREIGN KEY (team1_player1_id) REFERENCES players(id),
                FOREIGN KEY (team1_player2_id) REFERENCES players(id),
                FOREIGN KEY (team2_player1_id) REFERENCES players(id),
                FOREIGN KEY (team2_player2_id) REFERENCES players(id)
            )
        ''')
        
        # Games table (individual games within a match)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER NOT NULL,
                game_number INTEGER NOT NULL,
                team1_score INTEGER DEFAULT 0,
                team2_score INTEGER DEFAULT 0,
                team1_group TEXT DEFAULT '',
                balls_pocketed TEXT DEFAULT '{}',
                winner_team INTEGER DEFAULT 0,
                golden_break INTEGER DEFAULT 0,
                early_8ball_team INTEGER DEFAULT 0,
                breaking_team INTEGER DEFAULT 1,
                notes TEXT DEFAULT '',
                FOREIGN KEY (match_id) REFERENCES matches(id)
            )
        ''')
        
        # RSVP tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rsvps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league_night_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                paid INTEGER DEFAULT 0,
                FOREIGN KEY (league_night_id) REFERENCES league_nights(id),
                FOREIGN KEY (player_id) REFERENCES players(id),
                UNIQUE(league_night_id, player_id)
            )
        ''')
        
        # Settings table for app preferences
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        ''')
        
        conn.commit()
    
    # ============ Settings Operations ============
    
    def get_setting(self, key: str, default: str = "") -> str:
        """Get a setting value by key."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        if row:
            return row['value']
        return default
    
    def set_setting(self, key: str, value: str):
        """Set a setting value."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
        ''', (key, value))
        conn.commit()
    
    # ============ Player Operations ============
    
    def add_player(self, name: str, email: str = "", venmo: str = "", 
                   profile_picture: str = "") -> int:
        """Add a new player. Returns player ID."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO players (name, email, venmo, profile_picture) VALUES (?, ?, ?, ?)",
            (name, email, venmo, profile_picture)
        )
        conn.commit()
        return cursor.lastrowid
    
    def update_player(self, player_id: int, name: str, email: str = "", venmo: str = "",
                      profile_picture: str = None):
        """Update player information."""
        conn = self.get_connection()
        cursor = conn.cursor()
        if profile_picture is not None:
            cursor.execute(
                "UPDATE players SET name = ?, email = ?, venmo = ?, profile_picture = ? WHERE id = ?",
                (name, email, venmo, profile_picture, player_id)
            )
        else:
            cursor.execute(
                "UPDATE players SET name = ?, email = ?, venmo = ? WHERE id = ?",
                (name, email, venmo, player_id)
            )
        conn.commit()
    
    def update_player_picture(self, player_id: int, profile_picture: str):
        """Update just the player's profile picture."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE players SET profile_picture = ? WHERE id = ?",
            (profile_picture, player_id)
        )
        conn.commit()
    
    def delete_player(self, player_id: int):
        """Soft delete a player (set inactive)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE players SET active = 0 WHERE id = ?", (player_id,))
        conn.commit()
    
    def get_player(self, player_id: int) -> Optional[Player]:
        """Get a player by ID with computed stats."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM players WHERE id = ?", (player_id,))
        row = cursor.fetchone()
        if row:
            player = Player(
                id=row['id'],
                name=row['name'],
                email=row['email'],
                venmo=row['venmo'],
                profile_picture=row['profile_picture'] if 'profile_picture' in row.keys() else "",
                created_at=row['created_at']
            )
            # Compute stats
            self._compute_player_stats(player)
            return player
        return None
    
    def get_all_players(self, active_only: bool = True) -> list[Player]:
        """Get all players with computed stats.
        
        Optimized: Uses a single query to compute all stats instead of N+1 queries.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # First get all players
        if active_only:
            cursor.execute("SELECT * FROM players WHERE active = 1 ORDER BY name")
        else:
            cursor.execute("SELECT * FROM players ORDER BY name")
        
        player_rows = cursor.fetchall()
        
        # Batch compute all player stats in one query
        stats_cache = self._compute_all_player_stats()
        
        players = []
        for row in player_rows:
            player = Player(
                id=row['id'],
                name=row['name'],
                email=row['email'],
                venmo=row['venmo'],
                profile_picture=row['profile_picture'] if 'profile_picture' in row.keys() else "",
                created_at=row['created_at']
            )
            # Apply cached stats
            if player.id in stats_cache:
                stats = stats_cache[player.id]
                player.games_played = stats['games_played']
                player.games_won = stats['games_won']
                player.total_points = stats['total_points']
                player.golden_breaks = stats['golden_breaks']
            players.append(player)
        return players
    
    def _compute_all_player_stats(self) -> dict:
        """Compute statistics for all players in a single query.
        
        Returns a dict of player_id -> stats dict.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get all game data with player participation in one query
        cursor.execute('''
            SELECT 
                m.team1_player1_id, m.team1_player2_id, 
                m.team2_player1_id, m.team2_player2_id,
                g.team1_score, g.team2_score, g.winner_team, 
                g.golden_break, g.breaking_team
            FROM matches m
            JOIN games g ON g.match_id = m.id
            WHERE g.winner_team > 0
        ''')
        
        stats = {}  # player_id -> {games_played, games_won, total_points, golden_breaks}
        
        for row in cursor.fetchall():
            # Process each team's players
            team1_players = [row['team1_player1_id']]
            if row['team1_player2_id']:
                team1_players.append(row['team1_player2_id'])
            
            team2_players = [row['team2_player1_id']]
            if row['team2_player2_id']:
                team2_players.append(row['team2_player2_id'])
            
            # Get breaking_team safely (sqlite3.Row doesn't support .get())
            try:
                breaking_team = row['breaking_team']
            except (KeyError, IndexError):
                breaking_team = 1
            
            # Update stats for team 1 players
            for pid in team1_players:
                if pid not in stats:
                    stats[pid] = {'games_played': 0, 'games_won': 0, 'total_points': 0, 'golden_breaks': 0}
                stats[pid]['games_played'] += 1
                stats[pid]['total_points'] += row['team1_score']
                if row['winner_team'] == 1:
                    stats[pid]['games_won'] += 1
                if row['golden_break'] and breaking_team == 1:
                    stats[pid]['golden_breaks'] += 1
            
            # Update stats for team 2 players
            for pid in team2_players:
                if pid not in stats:
                    stats[pid] = {'games_played': 0, 'games_won': 0, 'total_points': 0, 'golden_breaks': 0}
                stats[pid]['games_played'] += 1
                stats[pid]['total_points'] += row['team2_score']
                if row['winner_team'] == 2:
                    stats[pid]['games_won'] += 1
                if row['golden_break'] and breaking_team == 2:
                    stats[pid]['golden_breaks'] += 1
        
        return stats
    
    def _compute_player_stats(self, player: Player):
        """Compute player statistics from games (single player version)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get all matches where player participated
        cursor.execute('''
            SELECT m.*, g.team1_score, g.team2_score, g.winner_team, g.golden_break
            FROM matches m
            JOIN games g ON g.match_id = m.id
            WHERE (m.team1_player1_id = ? OR m.team1_player2_id = ? 
                   OR m.team2_player1_id = ? OR m.team2_player2_id = ?)
            AND g.winner_team > 0
        ''', (player.id, player.id, player.id, player.id))
        
        games_played = 0
        games_won = 0
        total_points = 0
        golden_breaks = 0
        
        for row in cursor.fetchall():
            games_played += 1
            is_team1 = row['team1_player1_id'] == player.id or row['team1_player2_id'] == player.id
            
            # Get breaking_team safely (sqlite3.Row doesn't support .get())
            try:
                breaking_team = row['breaking_team']
            except (KeyError, IndexError):
                breaking_team = 1
            
            if is_team1:
                total_points += row['team1_score']
                if row['winner_team'] == 1:
                    games_won += 1
                if row['golden_break'] and breaking_team == 1:
                    golden_breaks += 1
            else:
                total_points += row['team2_score']
                if row['winner_team'] == 2:
                    games_won += 1
                if row['golden_break'] and breaking_team == 2:
                    golden_breaks += 1
        
        player.games_played = games_played
        player.games_won = games_won
        player.total_points = total_points
        player.golden_breaks = golden_breaks
    
    # ============ Match Operations ============
    
    def create_match(self, team1_p1: int, team1_p2: Optional[int],
                     team2_p1: int, team2_p2: Optional[int],
                     table_number: int = 1, best_of: int = 3,
                     is_finals: bool = False, league_night_id: Optional[int] = None) -> int:
        """Create a new match. Returns match ID."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO matches 
            (league_night_id, team1_player1_id, team1_player2_id, 
             team2_player1_id, team2_player2_id, table_number, best_of, is_finals)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (league_night_id, team1_p1, team1_p2, team2_p1, team2_p2, 
              table_number, best_of, 1 if is_finals else 0))
        conn.commit()
        return cursor.lastrowid
    
    def get_match(self, match_id: int) -> Optional[dict]:
        """Get match details with player names."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT m.*,
                   p1.name as team1_p1_name, p2.name as team1_p2_name,
                   p3.name as team2_p1_name, p4.name as team2_p2_name
            FROM matches m
            LEFT JOIN players p1 ON m.team1_player1_id = p1.id
            LEFT JOIN players p2 ON m.team1_player2_id = p2.id
            LEFT JOIN players p3 ON m.team2_player1_id = p3.id
            LEFT JOIN players p4 ON m.team2_player2_id = p4.id
            WHERE m.id = ?
        ''', (match_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    def get_all_matches(self, limit: int = 50) -> list[dict]:
        """Get recent matches with details."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT m.*,
                   p1.name as team1_p1_name, p2.name as team1_p2_name,
                   p3.name as team2_p1_name, p4.name as team2_p2_name
            FROM matches m
            LEFT JOIN players p1 ON m.team1_player1_id = p1.id
            LEFT JOIN players p2 ON m.team1_player2_id = p2.id
            LEFT JOIN players p3 ON m.team2_player1_id = p3.id
            LEFT JOIN players p4 ON m.team2_player2_id = p4.id
            ORDER BY m.date DESC
            LIMIT ?
        ''', (limit,))
        return [dict(row) for row in cursor.fetchall()]
    
    def complete_match(self, match_id: int):
        """Mark a match as complete."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE matches SET is_complete = 1 WHERE id = ?", (match_id,))
        conn.commit()
    
    # ============ Game Operations ============
    
    def create_game(self, match_id: int, game_number: int, breaking_team: int = 1) -> int:
        """Create a new game within a match."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO games (match_id, game_number, breaking_team)
            VALUES (?, ?, ?)
        ''', (match_id, game_number, breaking_team))
        conn.commit()
        return cursor.lastrowid
    
    def update_game(self, game_id: int, team1_score: int, team2_score: int,
                    team1_group: str, balls_pocketed: dict, winner_team: int,
                    golden_break: bool = False, early_8ball_team: int = 0):
        """Update game state."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE games SET
                team1_score = ?, team2_score = ?, team1_group = ?,
                balls_pocketed = ?, winner_team = ?, golden_break = ?,
                early_8ball_team = ?
            WHERE id = ?
        ''', (team1_score, team2_score, team1_group, 
              json.dumps(balls_pocketed), winner_team,
              1 if golden_break else 0, early_8ball_team, game_id))
        conn.commit()
    
    def get_games_for_match(self, match_id: int) -> list[dict]:
        """Get all games in a match."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM games WHERE match_id = ? ORDER BY game_number",
            (match_id,)
        )
        games = []
        for row in cursor.fetchall():
            game = dict(row)
            game['balls_pocketed'] = json.loads(game['balls_pocketed'] or '{}')
            games.append(game)
        return games
    
    def get_games_for_matches(self, match_ids: list[int]) -> dict[int, list[dict]]:
        """Get all games for multiple matches in one query.
        
        Returns a dict of match_id -> list of games.
        Optimized: Single query instead of N queries.
        """
        if not match_ids:
            return {}
        
        conn = self.get_connection()
        cursor = conn.cursor()
        
        placeholders = ','.join('?' * len(match_ids))
        cursor.execute(
            f"SELECT * FROM games WHERE match_id IN ({placeholders}) ORDER BY match_id, game_number",
            match_ids
        )
        
        result = {mid: [] for mid in match_ids}
        for row in cursor.fetchall():
            game = dict(row)
            game['balls_pocketed'] = json.loads(game['balls_pocketed'] or '{}')
            result[game['match_id']].append(game)
        
        return result
    
    def get_game(self, game_id: int) -> Optional[dict]:
        """Get a specific game."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM games WHERE id = ?", (game_id,))
        row = cursor.fetchone()
        if row:
            game = dict(row)
            game['balls_pocketed'] = json.loads(game['balls_pocketed'] or '{}')
            return game
        return None
    
    # ============ Leaderboard ============
    
    def get_leaderboard(self, sort_by: str = "wins") -> list[Player]:
        """Get players sorted by performance."""
        players = self.get_all_players(active_only=True)
        
        if sort_by == "wins":
            players.sort(key=lambda p: (-p.games_won, -p.win_rate))
        elif sort_by == "win_rate":
            players.sort(key=lambda p: (-p.win_rate, -p.games_won))
        elif sort_by == "points":
            players.sort(key=lambda p: (-p.total_points, -p.games_won))
        elif sort_by == "avg_points":
            players.sort(key=lambda p: (-p.avg_points, -p.games_won))
        
        return players
    
    def get_historical_team_matchups(self) -> set[frozenset]:
        """Get all historical team matchups as a set of frozensets.
        
        Each matchup is represented as a frozenset containing two team tuples.
        This allows checking if a particular team pairing has occurred before.
        
        Returns:
            Set of frozensets, where each frozenset contains two tuples 
            representing the teams that played (sorted player IDs).
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT team1_player1_id, team1_player2_id, 
                   team2_player1_id, team2_player2_id
            FROM matches
        ''')
        
        matchups = set()
        for row in cursor.fetchall():
            # Create normalized team representations (sorted tuples)
            team1 = tuple(sorted(filter(None, [row['team1_player1_id'], row['team1_player2_id']])))
            team2 = tuple(sorted(filter(None, [row['team2_player1_id'], row['team2_player2_id']])))
            
            # Use frozenset so order of teams doesn't matter (A vs B == B vs A)
            matchup = frozenset([team1, team2])
            matchups.add(matchup)
        
        return matchups
    
    def get_matchup_counts(self) -> dict:
        """Get count of how many times each team matchup has occurred.
        
        Returns:
            Dict mapping frozenset matchups to their occurrence count.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT team1_player1_id, team1_player2_id, 
                   team2_player1_id, team2_player2_id
            FROM matches
        ''')
        
        matchup_counts = {}
        for row in cursor.fetchall():
            team1 = tuple(sorted(filter(None, [row['team1_player1_id'], row['team1_player2_id']])))
            team2 = tuple(sorted(filter(None, [row['team2_player1_id'], row['team2_player2_id']])))
            matchup = frozenset([team1, team2])
            
            matchup_counts[matchup] = matchup_counts.get(matchup, 0) + 1
        
        return matchup_counts
    
    # ============ League Night Operations ============
    
    def create_league_night(self, date: str, location: str = "The Met Pool Hall",
                            buy_in: float = 0) -> int:
        """Create a new league night."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO league_nights (date, location, buy_in) VALUES (?, ?, ?)",
            (date, location, buy_in)
        )
        conn.commit()
        return cursor.lastrowid
    
    def clear_matches(self):
        """Clear all matches and games (for new pool night). Keeps players."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM games")
        cursor.execute("DELETE FROM matches")
        cursor.execute("DELETE FROM league_nights")
        conn.commit()
    
    def clear_all_players(self):
        """Clear all players from the database."""
        conn = self.get_connection()
        cursor = conn.cursor()
        # First clear matches since they reference players
        cursor.execute("DELETE FROM games")
        cursor.execute("DELETE FROM matches")
        cursor.execute("DELETE FROM rsvps")
        cursor.execute("DELETE FROM players")
        conn.commit()
    
    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
