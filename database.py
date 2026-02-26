"""
EcoPOOL League - Database Manager
SQLite database for persistent storage of players, matches, and statistics.
"""

import sqlite3
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass, field
import json
import logging

# Configure logging for database migrations
_db_logger = logging.getLogger(__name__)

# Constants for scoring rules
# Legal 8-ball win: 7 regular balls (1 pt each) + 8-ball (3 pts) = 10 points
LEGAL_8BALL_MIN_SCORE = 10


def _column_exists(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    """Check if a column exists in a table.

    Args:
        cursor: SQLite cursor
        table: Table name
        column: Column name

    Returns:
        True if column exists, False otherwise
    """
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns


def _safe_add_column(cursor: sqlite3.Cursor, table: str, column: str,
                     column_def: str) -> bool:
    """Safely add a column to a table if it doesn't exist.

    Args:
        cursor: SQLite cursor
        table: Table name
        column: Column name
        column_def: Full column definition (e.g., "INTEGER DEFAULT 0")

    Returns:
        True if column was added, False if it already existed
    """
    if _column_exists(cursor, table, column):
        return False

    try:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_def}")
        _db_logger.info(f"Added column {column} to {table}")
        return True
    except sqlite3.OperationalError as e:
        _db_logger.warning(f"Failed to add column {column} to {table}: {e}")
        return False


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
    games_lost: int = 0
    total_points: int = 0
    golden_breaks: int = 0
    eight_ball_sinks: int = 0  # Legal 8-ball wins
    
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
class Season:
    id: Optional[int]
    name: str
    start_date: str
    end_date: str = ""
    is_active: bool = True
    notes: str = ""


@dataclass
class Pair:
    id: Optional[int]
    league_night_id: int
    player1_id: int
    player2_id: Optional[int]  # None for lone wolf
    pair_name: str = ""
    

@dataclass
class BuyIn:
    id: Optional[int]
    league_night_id: int
    player_id: int
    amount: float = 0.0
    paid: bool = False
    venmo_confirmed: bool = False
    notes: str = ""


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
    # New fields for queue system
    pair1_id: Optional[int] = None
    pair2_id: Optional[int] = None
    queue_position: int = 0
    status: str = "queued"  # 'queued', 'live', 'completed'
    season_id: Optional[int] = None
    # Round system - matches in same round can be played simultaneously
    round_number: int = 1
    

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
    current_turn: int = 1  # 1 or 2 - which team is currently shooting


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
        _safe_add_column(cursor, 'players', 'profile_picture', "TEXT DEFAULT ''")
        
        # Seasons table (NEW)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS seasons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                start_date TEXT NOT NULL,
                end_date TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1,
                notes TEXT DEFAULT ''
            )
        ''')
        
        # League nights table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS league_nights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                location TEXT DEFAULT 'The Met Pool Hall',
                buy_in REAL DEFAULT 0,
                notes TEXT DEFAULT '',
                season_id INTEGER,
                table_count INTEGER DEFAULT 3,
                FOREIGN KEY (season_id) REFERENCES seasons(id)
            )
        ''')
        
        # Add new columns to league_nights if they don't exist
        _safe_add_column(cursor, 'league_nights', 'season_id', "INTEGER")
        _safe_add_column(cursor, 'league_nights', 'table_count', "INTEGER DEFAULT 3")
        
        # League night pairs table (NEW) - Fixed pairs for the night
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS league_night_pairs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league_night_id INTEGER NOT NULL,
                player1_id INTEGER NOT NULL,
                player2_id INTEGER,
                pair_name TEXT DEFAULT '',
                FOREIGN KEY (league_night_id) REFERENCES league_nights(id),
                FOREIGN KEY (player1_id) REFERENCES players(id),
                FOREIGN KEY (player2_id) REFERENCES players(id)
            )
        ''')
        
        # League night buy-ins table (NEW)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS league_night_buyins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league_night_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                amount REAL DEFAULT 0,
                paid INTEGER DEFAULT 0,
                venmo_confirmed INTEGER DEFAULT 0,
                notes TEXT DEFAULT '',
                FOREIGN KEY (league_night_id) REFERENCES league_nights(id),
                FOREIGN KEY (player_id) REFERENCES players(id),
                UNIQUE(league_night_id, player_id)
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
                pair1_id INTEGER,
                pair2_id INTEGER,
                queue_position INTEGER DEFAULT 0,
                status TEXT DEFAULT 'queued',
                season_id INTEGER,
                FOREIGN KEY (league_night_id) REFERENCES league_nights(id),
                FOREIGN KEY (team1_player1_id) REFERENCES players(id),
                FOREIGN KEY (team1_player2_id) REFERENCES players(id),
                FOREIGN KEY (team2_player1_id) REFERENCES players(id),
                FOREIGN KEY (team2_player2_id) REFERENCES players(id),
                FOREIGN KEY (pair1_id) REFERENCES league_night_pairs(id),
                FOREIGN KEY (pair2_id) REFERENCES league_night_pairs(id),
                FOREIGN KEY (season_id) REFERENCES seasons(id)
            )
        ''')
        
        # Add new columns to matches if they don't exist (migration)
        for col, default in [("pair1_id", "INTEGER"), ("pair2_id", "INTEGER"),
                             ("queue_position", "INTEGER DEFAULT 0"),
                             ("status", "TEXT DEFAULT 'queued'"),
                             ("season_id", "INTEGER"),
                             ("round_number", "INTEGER DEFAULT 1")]:
            _safe_add_column(cursor, 'matches', col, default)

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

        # Add current_turn column to games table if it doesn't exist (migration)
        _safe_add_column(cursor, 'games', 'current_turn', "INTEGER DEFAULT 1")

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

        # Teammate pairs table - tracks historical pairings per season
        # Used to prevent players from being partnered together repeatedly
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS teammate_pairs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                season_id INTEGER NOT NULL,
                player1_id INTEGER NOT NULL,
                player2_id INTEGER NOT NULL,
                pair_count INTEGER DEFAULT 1,
                last_paired_date TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (season_id) REFERENCES seasons(id),
                FOREIGN KEY (player1_id) REFERENCES players(id),
                FOREIGN KEY (player2_id) REFERENCES players(id),
                UNIQUE(season_id, player1_id, player2_id)
            )
        ''')

        # Match events table - tracks timeline events during matches
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS match_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER NOT NULL,
                game_number INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                event_data TEXT DEFAULT '{}',
                team INTEGER,
                timestamp TEXT NOT NULL,
                timestamp_ms INTEGER NOT NULL,
                FOREIGN KEY (match_id) REFERENCES matches(id)
            )
        ''')

        # Index for efficient timeline queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_match_events_match_game
            ON match_events(match_id, game_number, timestamp_ms)
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
    
    def find_player_by_name(self, name: str) -> Optional[int]:
        """Find an active player by name. Returns player ID or None."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM players WHERE name = ? AND active = 1", (name,))
        row = cursor.fetchone()
        return row['id'] if row else None

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
                player.games_lost = stats['games_played'] - stats['games_won']
                player.total_points = stats['total_points']
                player.golden_breaks = stats['golden_breaks']
                player.eight_ball_sinks = stats.get('eight_ball_sinks', 0)
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
                g.golden_break, g.breaking_team, g.balls_pocketed
            FROM matches m
            JOIN games g ON g.match_id = m.id
            WHERE g.winner_team > 0
        ''')
        
        stats = {}  # player_id -> {games_played, games_won, total_points, golden_breaks, eight_ball_sinks}
        
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
            
            # Check for legal 8-ball pocket (winner who cleared their balls)
            # Legal 8-ball: 7 regular balls + 8-ball = LEGAL_8BALL_MIN_SCORE points
            team1_legal_8ball = row['winner_team'] == 1 and row['team1_score'] >= LEGAL_8BALL_MIN_SCORE
            team2_legal_8ball = row['winner_team'] == 2 and row['team2_score'] >= LEGAL_8BALL_MIN_SCORE
            
            # Update stats for team 1 players
            for pid in team1_players:
                if pid not in stats:
                    stats[pid] = {'games_played': 0, 'games_won': 0, 'total_points': 0, 'golden_breaks': 0, 'eight_ball_sinks': 0}
                stats[pid]['games_played'] += 1
                stats[pid]['total_points'] += row['team1_score']
                if row['winner_team'] == 1:
                    stats[pid]['games_won'] += 1
                if row['golden_break'] and breaking_team == 1:
                    stats[pid]['golden_breaks'] += 1
                if team1_legal_8ball:
                    stats[pid]['eight_ball_sinks'] += 1
            
            # Update stats for team 2 players
            for pid in team2_players:
                if pid not in stats:
                    stats[pid] = {'games_played': 0, 'games_won': 0, 'total_points': 0, 'golden_breaks': 0, 'eight_ball_sinks': 0}
                stats[pid]['games_played'] += 1
                stats[pid]['total_points'] += row['team2_score']
                if row['winner_team'] == 2:
                    stats[pid]['games_won'] += 1
                if row['golden_break'] and breaking_team == 2:
                    stats[pid]['golden_breaks'] += 1
                if team2_legal_8ball:
                    stats[pid]['eight_ball_sinks'] += 1
        
        return stats
    
    def _compute_player_stats(self, player: Player):
        """Compute player statistics from games (single player version)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get all matches where player participated
        cursor.execute('''
            SELECT m.*, g.team1_score, g.team2_score, g.winner_team, g.golden_break, g.breaking_team
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
        eight_ball_sinks = 0
        
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
                    # Legal 8-ball if won with required minimum points
                    if row['team1_score'] >= LEGAL_8BALL_MIN_SCORE:
                        eight_ball_sinks += 1
                if row['golden_break'] and breaking_team == 1:
                    golden_breaks += 1
            else:
                total_points += row['team2_score']
                if row['winner_team'] == 2:
                    games_won += 1
                    if row['team2_score'] >= LEGAL_8BALL_MIN_SCORE:
                        eight_ball_sinks += 1
                if row['golden_break'] and breaking_team == 2:
                    golden_breaks += 1
        
        player.games_played = games_played
        player.games_won = games_won
        player.games_lost = games_played - games_won
        player.total_points = total_points
        player.golden_breaks = golden_breaks
        player.eight_ball_sinks = eight_ball_sinks
    
    # ============ Match Operations ============
    
    def create_match(self, team1_p1: int, team1_p2: Optional[int],
                     team2_p1: int, team2_p2: Optional[int],
                     table_number: int = 1, best_of: int = 3,
                     is_finals: bool = False, league_night_id: Optional[int] = None,
                     pair1_id: Optional[int] = None, pair2_id: Optional[int] = None,
                     queue_position: int = 0, status: str = "queued",
                     season_id: Optional[int] = None, round_number: int = 1) -> int:
        """Create a new match. Returns match ID."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO matches 
            (league_night_id, team1_player1_id, team1_player2_id, 
             team2_player1_id, team2_player2_id, table_number, best_of, is_finals,
             pair1_id, pair2_id, queue_position, status, season_id, round_number)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (league_night_id, team1_p1, team1_p2, team2_p1, team2_p2, 
              table_number, best_of, 1 if is_finals else 0,
              pair1_id, pair2_id, queue_position, status, season_id, round_number))
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
        # Initialize current_turn to breaking_team (the breaking team shoots first)
        cursor.execute('''
            INSERT INTO games (match_id, game_number, breaking_team, current_turn)
            VALUES (?, ?, ?, ?)
        ''', (match_id, game_number, breaking_team, breaking_team))
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
    
    def get_leaderboard(self, sort_by: str = "points") -> list[Player]:
        """Get players sorted by performance. Default sort is by total points."""
        players = self.get_all_players(active_only=True)
        
        if sort_by == "points":
            players.sort(key=lambda p: (-p.total_points, -p.games_won))
        elif sort_by == "wins":
            players.sort(key=lambda p: (-p.games_won, -p.win_rate))
        elif sort_by == "win_rate":
            players.sort(key=lambda p: (-p.win_rate, -p.games_won))
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

    # ============ Teammate Pair Operations ============

    def get_teammate_pair_counts(self, season_id: int) -> dict:
        """Get count of how many times each player pair has been teammates in a season.

        Args:
            season_id: The season ID to check

        Returns:
            Dict mapping frozenset of (player1_id, player2_id) to their pair count.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT player1_id, player2_id, pair_count
            FROM teammate_pairs
            WHERE season_id = ?
        ''', (season_id,))

        pair_counts = {}
        for row in cursor.fetchall():
            # Create normalized pair key (sorted tuple as frozenset)
            pair_key = frozenset([row['player1_id'], row['player2_id']])
            pair_counts[pair_key] = row['pair_count']

        return pair_counts

    def record_teammate_pair(self, season_id: int, player1_id: int, player2_id: int):
        """Record that two players were paired as teammates.

        Args:
            season_id: The season ID
            player1_id: First player ID
            player2_id: Second player ID (can be None for lone wolf)
        """
        if player2_id is None:
            return  # Don't record lone wolves

        # Normalize order (smaller ID first)
        p1, p2 = (min(player1_id, player2_id), max(player1_id, player2_id))

        conn = self.get_connection()
        cursor = conn.cursor()

        # Insert or increment pair count
        cursor.execute('''
            INSERT INTO teammate_pairs (season_id, player1_id, player2_id, pair_count, last_paired_date)
            VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP)
            ON CONFLICT(season_id, player1_id, player2_id) DO UPDATE SET
                pair_count = pair_count + 1,
                last_paired_date = CURRENT_TIMESTAMP
        ''', (season_id, p1, p2))
        conn.commit()

    def get_player_pair_history(self, season_id: int, player_id: int) -> dict:
        """Get the pairing history for a specific player in a season.

        Args:
            season_id: The season ID
            player_id: The player to check

        Returns:
            Dict mapping partner player IDs to pair count.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT player1_id, player2_id, pair_count
            FROM teammate_pairs
            WHERE season_id = ?
              AND (player1_id = ? OR player2_id = ?)
        ''', (season_id, player_id, player_id))

        partner_counts = {}
        for row in cursor.fetchall():
            # Get the other player's ID
            partner_id = row['player2_id'] if row['player1_id'] == player_id else row['player1_id']
            partner_counts[partner_id] = row['pair_count']

        return partner_counts

    def get_best_available_partner(self, season_id: int, player_id: int,
                                   available_players: list[int]) -> tuple[int, int]:
        """Find the best available partner for a player (one with lowest pair count).

        Args:
            season_id: The season ID
            player_id: The player needing a partner
            available_players: List of available player IDs to choose from

        Returns:
            Tuple of (partner_id, pair_count) for the best match.
        """
        if not available_players:
            return (None, 0)

        partner_history = self.get_player_pair_history(season_id, player_id)

        # Find player with lowest pair count
        best_partner = None
        best_count = float('inf')

        for partner_id in available_players:
            if partner_id == player_id:
                continue
            count = partner_history.get(partner_id, 0)
            if count < best_count:
                best_count = count
                best_partner = partner_id

        return (best_partner, best_count if best_count != float('inf') else 0)

    # ============ League Night Operations ============
    
    def create_league_night(self, date: str, location: str = "The Met Pool Hall",
                            buy_in: float = 0, season_id: Optional[int] = None,
                            table_count: int = 3) -> int:
        """Create a new league night."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO league_nights (date, location, buy_in, season_id, table_count) VALUES (?, ?, ?, ?, ?)",
            (date, location, buy_in, season_id, table_count)
        )
        conn.commit()
        return cursor.lastrowid
    
    def get_league_night(self, league_night_id: int) -> Optional[dict]:
        """Get a league night by ID."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM league_nights WHERE id = ?", (league_night_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_current_league_night(self) -> Optional[dict]:
        """Get the most recent league night."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM league_nights ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def update_league_night_table_count(self, league_night_id: int, table_count: int):
        """Update the table count for a league night."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE league_nights SET table_count = ? WHERE id = ?",
            (table_count, league_night_id)
        )
        conn.commit()
    
    def clear_matches(self, keep_completed: bool = True):
        """Clear matches for new pool night. 
        
        Args:
            keep_completed: If True, keeps completed matches and their games 
                           (preserves leaderboard). If False, clears everything.
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if keep_completed:
            # Only clear incomplete matches and their games - preserve leaderboard data
            cursor.execute('''
                DELETE FROM games WHERE match_id IN (
                    SELECT id FROM matches WHERE is_complete = 0
                )
            ''')
            cursor.execute("DELETE FROM matches WHERE is_complete = 0")
            # Only delete league nights that have no remaining completed matches
            cursor.execute('''
                DELETE FROM league_night_buyins WHERE league_night_id IN (
                    SELECT id FROM league_nights WHERE id NOT IN (
                        SELECT DISTINCT league_night_id FROM matches WHERE is_complete = 1
                    )
                )
            ''')
            cursor.execute('''
                DELETE FROM league_night_pairs WHERE league_night_id IN (
                    SELECT id FROM league_nights WHERE id NOT IN (
                        SELECT DISTINCT league_night_id FROM matches WHERE is_complete = 1
                    )
                )
            ''')
            cursor.execute('''
                DELETE FROM league_nights WHERE id NOT IN (
                    SELECT DISTINCT league_night_id FROM matches WHERE is_complete = 1
                )
            ''')
        else:
            # Full clear - also clears leaderboard
            cursor.execute("DELETE FROM games")
            cursor.execute("DELETE FROM matches")
            cursor.execute("DELETE FROM league_night_buyins")
            cursor.execute("DELETE FROM league_night_pairs")
            cursor.execute("DELETE FROM league_nights")
        
        conn.commit()
    
    def reset_leaderboard(self):
        """Reset all leaderboard data by clearing all matches and games.
        This is a destructive operation - use with caution."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM match_events")
        cursor.execute("DELETE FROM games")
        cursor.execute("DELETE FROM matches")
        cursor.execute("DELETE FROM league_night_buyins")
        cursor.execute("DELETE FROM league_night_pairs")
        cursor.execute("DELETE FROM league_nights")
        cursor.execute("DELETE FROM teammate_pairs")
        conn.commit()
    
    def clear_all_players(self):
        """Clear all players from the database."""
        conn = self.get_connection()
        cursor = conn.cursor()
        # First clear matches since they reference players
        cursor.execute("DELETE FROM games")
        cursor.execute("DELETE FROM matches")
        cursor.execute("DELETE FROM league_night_buyins")
        cursor.execute("DELETE FROM league_night_pairs")
        cursor.execute("DELETE FROM rsvps")
        cursor.execute("DELETE FROM players")
        conn.commit()
    
    # ============ Season Operations ============
    
    def create_season(self, name: str, start_date: str = None) -> int:
        """Create a new season. Returns season ID."""
        if start_date is None:
            start_date = datetime.now().strftime("%Y-%m-%d")
        conn = self.get_connection()
        cursor = conn.cursor()
        # Deactivate other seasons
        cursor.execute("UPDATE seasons SET is_active = 0")
        cursor.execute(
            "INSERT INTO seasons (name, start_date, is_active) VALUES (?, ?, 1)",
            (name, start_date)
        )
        conn.commit()
        return cursor.lastrowid
    
    def get_active_season(self) -> Optional[Season]:
        """Get the currently active season."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM seasons WHERE is_active = 1 LIMIT 1")
        row = cursor.fetchone()
        if row:
            return Season(
                id=row['id'],
                name=row['name'],
                start_date=row['start_date'],
                end_date=row['end_date'] or "",
                is_active=bool(row['is_active']),
                notes=row['notes'] or ""
            )
        return None
    
    def get_all_seasons(self) -> list[Season]:
        """Get all seasons."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM seasons ORDER BY start_date DESC")
        seasons = []
        for row in cursor.fetchall():
            seasons.append(Season(
                id=row['id'],
                name=row['name'],
                start_date=row['start_date'],
                end_date=row['end_date'] or "",
                is_active=bool(row['is_active']),
                notes=row['notes'] or ""
            ))
        return seasons
    
    def set_active_season(self, season_id: int):
        """Set a season as active."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE seasons SET is_active = 0")
        cursor.execute("UPDATE seasons SET is_active = 1 WHERE id = ?", (season_id,))
        conn.commit()
    
    def end_season(self, season_id: int, end_date: str = None):
        """End a season."""
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE seasons SET end_date = ?, is_active = 0 WHERE id = ?",
            (end_date, season_id)
        )
        conn.commit()
    
    # ============ Pair Operations ============
    
    def create_pair(self, league_night_id: int, player1_id: int, 
                    player2_id: Optional[int] = None, pair_name: str = "") -> int:
        """Create a pair for a league night. Returns pair ID."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO league_night_pairs (league_night_id, player1_id, player2_id, pair_name) VALUES (?, ?, ?, ?)",
            (league_night_id, player1_id, player2_id, pair_name)
        )
        conn.commit()
        return cursor.lastrowid
    
    def get_pairs_for_night(self, league_night_id: int) -> list[dict]:
        """Get all pairs for a league night with player details."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.*, 
                   p1.name as player1_name, p1.profile_picture as player1_pic,
                   p2.name as player2_name, p2.profile_picture as player2_pic
            FROM league_night_pairs p
            LEFT JOIN players p1 ON p.player1_id = p1.id
            LEFT JOIN players p2 ON p.player2_id = p2.id
            WHERE p.league_night_id = ?
        ''', (league_night_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_pair(self, pair_id: int) -> Optional[dict]:
        """Get a pair by ID with player details."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT p.*, 
                   p1.name as player1_name, p1.profile_picture as player1_pic,
                   p2.name as player2_name, p2.profile_picture as player2_pic
            FROM league_night_pairs p
            LEFT JOIN players p1 ON p.player1_id = p1.id
            LEFT JOIN players p2 ON p.player2_id = p2.id
            WHERE p.id = ?
        ''', (pair_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def delete_pairs_for_night(self, league_night_id: int):
        """Delete all pairs for a league night."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM league_night_pairs WHERE league_night_id = ?", (league_night_id,))
        conn.commit()
    
    def update_pair_name(self, pair_id: int, pair_name: str):
        """Update a pair's name."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE league_night_pairs SET pair_name = ? WHERE id = ?", (pair_name, pair_id))
        conn.commit()
    
    # ============ Buy-In Operations ============
    
    def set_buyin(self, league_night_id: int, player_id: int, amount: float,
                  paid: bool = False, venmo_confirmed: bool = False, notes: str = ""):
        """Set or update a player's buy-in for a league night."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO league_night_buyins (league_night_id, player_id, amount, paid, venmo_confirmed, notes)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(league_night_id, player_id) 
            DO UPDATE SET amount = excluded.amount, paid = excluded.paid, 
                         venmo_confirmed = excluded.venmo_confirmed, notes = excluded.notes
        ''', (league_night_id, player_id, amount, 1 if paid else 0, 
              1 if venmo_confirmed else 0, notes))
        conn.commit()
    
    def mark_buyin_paid(self, league_night_id: int, player_id: int, paid: bool = True,
                        venmo_confirmed: bool = False):
        """Mark a player's buy-in as paid."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE league_night_buyins SET paid = ?, venmo_confirmed = ?
            WHERE league_night_id = ? AND player_id = ?
        ''', (1 if paid else 0, 1 if venmo_confirmed else 0, league_night_id, player_id))
        conn.commit()
    
    def get_buyins_for_night(self, league_night_id: int) -> list[dict]:
        """Get all buy-ins for a league night with player details."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT b.*, p.name as player_name, p.venmo as player_venmo
            FROM league_night_buyins b
            JOIN players p ON b.player_id = p.id
            WHERE b.league_night_id = ?
        ''', (league_night_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_total_pot(self, league_night_id: int) -> tuple[float, float]:
        """Get total pot and paid amount for a league night.
        Returns (total_expected, total_paid)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COALESCE(SUM(amount), 0) as total,
                   COALESCE(SUM(CASE WHEN paid = 1 THEN amount ELSE 0 END), 0) as paid
            FROM league_night_buyins WHERE league_night_id = ?
        ''', (league_night_id,))
        row = cursor.fetchone()
        return (row['total'], row['paid'])
    
    # ============ Queue Operations ============
    
    def get_queued_matches(self, league_night_id: int) -> list[dict]:
        """Get all queued matches for a league night, ordered by position."""
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
            WHERE m.league_night_id = ? AND m.status = 'queued'
            ORDER BY m.queue_position
        ''', (league_night_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def trim_excess_queued_matches(self, league_night_id: int, max_games: int = 4) -> int:
        """Delete queued matches where both pairs already have >= max_games played or scheduled.

        Only counts live and completed matches as fixed; walks the queued matches in
        queue_position order, keeping each one unless both pairs already reached max_games.
        Re-sequences queue_position on survivors and returns the number of deleted matches.
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, status, queue_position,
                   pair1_id, pair2_id,
                   team1_player1_id, team1_player2_id,
                   team2_player1_id, team2_player2_id
            FROM matches
            WHERE league_night_id = ?
            ORDER BY queue_position, id
        ''', (league_night_id,))
        all_matches = [dict(row) for row in cursor.fetchall()]

        def get_pair_key(m, side):
            if side == 1:
                pid = m.get('pair1_id')
                if pid:
                    return ('id', pid)
                return ('players', frozenset(filter(None, [m.get('team1_player1_id'), m.get('team1_player2_id')])))
            else:
                pid = m.get('pair2_id')
                if pid:
                    return ('id', pid)
                return ('players', frozenset(filter(None, [m.get('team2_player1_id'), m.get('team2_player2_id')])))

        # Count games from live + completed matches
        games_per_pair = {}
        queued_matches = []
        for m in all_matches:
            if m['status'] in ('live', 'completed'):
                k1 = get_pair_key(m, 1)
                k2 = get_pair_key(m, 2)
                games_per_pair[k1] = games_per_pair.get(k1, 0) + 1
                games_per_pair[k2] = games_per_pair.get(k2, 0) + 1
            elif m['status'] == 'queued':
                queued_matches.append(m)

        # Walk queued matches; collect ids to delete
        ids_to_delete = []
        survivors = []
        for m in queued_matches:
            k1 = get_pair_key(m, 1)
            k2 = get_pair_key(m, 2)
            if games_per_pair.get(k1, 0) >= max_games and games_per_pair.get(k2, 0) >= max_games:
                ids_to_delete.append(m['id'])
            else:
                survivors.append(m)
                games_per_pair[k1] = games_per_pair.get(k1, 0) + 1
                games_per_pair[k2] = games_per_pair.get(k2, 0) + 1

        if ids_to_delete:
            cursor.execute(
                f'DELETE FROM matches WHERE id IN ({",".join("?" * len(ids_to_delete))})',
                ids_to_delete
            )

        # Re-sequence queue_position on survivors
        for new_pos, m in enumerate(survivors):
            cursor.execute(
                'UPDATE matches SET queue_position = ? WHERE id = ?',
                (new_pos, m['id'])
            )

        conn.commit()
        return len(ids_to_delete)

    def get_live_matches(self, league_night_id: int) -> list[dict]:
        """Get all live matches for a league night."""
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
            WHERE m.league_night_id = ? AND m.status = 'live'
            ORDER BY m.table_number
        ''', (league_night_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_matches_by_status(self, league_night_id: int, status: str) -> list[dict]:
        """Get matches filtered by status."""
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
            WHERE m.league_night_id = ? AND m.status = ?
            ORDER BY m.queue_position, m.table_number
        ''', (league_night_id, status))
        return [dict(row) for row in cursor.fetchall()]
    
    def start_match(self, match_id: int, table_number: int):
        """Move a match from queued to live on a table."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE matches SET status = 'live', table_number = ? WHERE id = ?",
            (table_number, match_id)
        )
        conn.commit()
    
    def complete_match_with_status(self, match_id: int):
        """Mark a match as completed and update status."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE matches SET status = 'completed', is_complete = 1 WHERE id = ?",
            (match_id,)
        )
        conn.commit()
    
    def get_next_queued_match(self, league_night_id: int) -> Optional[dict]:
        """Get the next match in the queue."""
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
            WHERE m.league_night_id = ? AND m.status = 'queued'
            ORDER BY m.queue_position
            LIMIT 1
        ''', (league_night_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def advance_queue(self, league_night_id: int, table_number: int) -> Optional[dict]:
        """Move the next queued match to a specific table.
        Returns the match that was moved, or None if queue is empty."""
        next_match = self.get_next_queued_match(league_night_id)
        if next_match:
            self.start_match(next_match['id'], table_number)
            return next_match
        return None
    
    def update_match_status(self, match_id: int, status: str):
        """Update the status of a match."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE matches SET status = ? WHERE id = ?", (status, match_id))
        if status == 'completed':
            cursor.execute("UPDATE matches SET is_complete = 1 WHERE id = ?", (match_id,))
        conn.commit()
    
    # ============ Round System Operations ============
    
    def get_current_round(self, league_night_id: int) -> int:
        """Get the current active round number for a league night.
        Returns the lowest round number with incomplete matches, or 0 if no matches."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT MIN(round_number) as current_round
            FROM matches 
            WHERE league_night_id = ? AND status != 'completed'
        ''', (league_night_id,))
        row = cursor.fetchone()
        return row['current_round'] if row and row['current_round'] else 0
    
    def is_round_complete(self, league_night_id: int, round_number: int) -> bool:
        """Check if all matches in a round are completed."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) as incomplete
            FROM matches 
            WHERE league_night_id = ? AND round_number = ? AND status != 'completed'
        ''', (league_night_id, round_number))
        row = cursor.fetchone()
        return row['incomplete'] == 0
    
    def get_matches_for_round(self, league_night_id: int, round_number: int) -> list[dict]:
        """Get all matches for a specific round."""
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
            WHERE m.league_night_id = ? AND m.round_number = ?
            ORDER BY m.queue_position
        ''', (league_night_id, round_number))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_total_rounds(self, league_night_id: int) -> int:
        """Get the total number of rounds for a league night."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT MAX(round_number) as total_rounds
            FROM matches WHERE league_night_id = ?
        ''', (league_night_id,))
        row = cursor.fetchone()
        return row['total_rounds'] if row and row['total_rounds'] else 0
    
    def get_pairs_playing_in_round(self, league_night_id: int, round_number: int) -> set[int]:
        """Get all pair IDs that are currently playing (live) in a round.
        Used to prevent same pair from being at multiple tables."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT pair1_id, pair2_id
            FROM matches 
            WHERE league_night_id = ? AND round_number = ? AND status = 'live'
        ''', (league_night_id, round_number))
        
        playing_pairs = set()
        for row in cursor.fetchall():
            if row['pair1_id']:
                playing_pairs.add(row['pair1_id'])
            if row['pair2_id']:
                playing_pairs.add(row['pair2_id'])
        return playing_pairs
    
    def can_start_match(self, match_id: int) -> tuple[bool, str]:
        """Check if a match can be started.
        Checks: 1) Match is in current round, 2) Pairs not already playing anywhere.
        Returns (can_start, reason)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Get match details
        cursor.execute('''
            SELECT league_night_id, round_number, pair1_id, pair2_id
            FROM matches WHERE id = ?
        ''', (match_id,))
        match = cursor.fetchone()
        
        if not match:
            return False, "Match not found"
        
        if not match['league_night_id']:
            return True, ""  # Legacy match without league night
        
        # Check if this match is in the current round
        current_round = self.get_current_round(match['league_night_id'])
        match_round = match['round_number'] or 1
        
        if match_round > current_round:
            return False, f"This match is in Round {match_round}, but Round {current_round} is not complete yet"
        
        # Get ALL pairs currently playing (anywhere, not just this round)
        playing_pairs = self.get_all_pairs_currently_playing(match['league_night_id'])
        
        # Check if either pair is already playing
        if match['pair1_id'] and match['pair1_id'] in playing_pairs:
            return False, "Pair 1 is already playing at another table"
        if match['pair2_id'] and match['pair2_id'] in playing_pairs:
            return False, "Pair 2 is already playing at another table"
        
        return True, ""
    
    def get_queued_matches_for_current_round(self, league_night_id: int) -> list[dict]:
        """Get queued matches only from the current active round."""
        current_round = self.get_current_round(league_night_id)
        if current_round == 0:
            return []
        
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
            WHERE m.league_night_id = ? AND m.round_number = ? AND m.status = 'queued'
            ORDER BY m.queue_position
        ''', (league_night_id, current_round))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_next_available_match(self, league_night_id: int) -> Optional[dict]:
        """Get the next queued match where neither pair is currently playing.
        Only returns matches from the current round - never jumps to future rounds.
        Prefers matches whose teams have been idle longest."""
        queued_matches = self.get_queued_matches_for_current_round(league_night_id)
        current_round = self.get_current_round(league_night_id)

        if not queued_matches or current_round == 0:
            return None

        # Get ALL pairs currently playing live (not just in this round, but anywhere)
        playing_pairs = self.get_all_pairs_currently_playing(league_night_id)

        # Get last completed time for each pair to prefer idle teams
        pair_last_active = self._get_pair_last_active_times(league_night_id)

        available = []
        for match in queued_matches:
            # Only allow matches from the current round
            if match.get('round_number', 1) != current_round:
                continue

            pair1_available = match['pair1_id'] not in playing_pairs if match['pair1_id'] else True
            pair2_available = match['pair2_id'] not in playing_pairs if match['pair2_id'] else True

            if pair1_available and pair2_available:
                # Score by idle time: prefer pairs that finished longest ago
                p1_last = pair_last_active.get(match.get('pair1_id'), '')
                p2_last = pair_last_active.get(match.get('pair2_id'), '')
                # Earlier last-active = more idle = should go first
                idle_key = max(p1_last, p2_last) if p1_last and p2_last else ''
                available.append((idle_key, match))

        if not available:
            return None

        # Sort so the match with the earliest last-active time comes first
        available.sort(key=lambda x: x[0])
        return available[0][1]

    def _get_pair_last_active_times(self, league_night_id: int) -> dict:
        """Get the last time each pair was in a completed or live match."""
        conn = self.get_connection()
        cursor = conn.cursor()
        # Use the match date as a proxy for when the pair was last active
        cursor.execute('''
            SELECT pair1_id, pair2_id, date
            FROM matches
            WHERE league_night_id = ? AND status IN ('completed', 'live')
        ''', (league_night_id,))

        result = {}
        for row in cursor.fetchall():
            ts = row['date'] or ''
            if row['pair1_id']:
                if ts > result.get(row['pair1_id'], ''):
                    result[row['pair1_id']] = ts
            if row['pair2_id']:
                if ts > result.get(row['pair2_id'], ''):
                    result[row['pair2_id']] = ts
        return result
    
    def get_all_pairs_currently_playing(self, league_night_id: int) -> set[int]:
        """Get all pair IDs that are currently playing (live) in ANY match.
        This prevents a pair from being at multiple tables simultaneously."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT pair1_id, pair2_id
            FROM matches 
            WHERE league_night_id = ? AND status = 'live'
        ''', (league_night_id,))
        
        playing_pairs = set()
        for row in cursor.fetchall():
            if row['pair1_id']:
                playing_pairs.add(row['pair1_id'])
            if row['pair2_id']:
                playing_pairs.add(row['pair2_id'])
        return playing_pairs
    
    def is_round_in_progress(self, league_night_id: int, round_number: int) -> bool:
        """Check if any matches in a round are currently live (in progress)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) as live_count
            FROM matches
            WHERE league_night_id = ? AND round_number = ? AND status = 'live'
        ''', (league_night_id, round_number))
        row = cursor.fetchone()
        return row['live_count'] > 0

    # ============ Match Event/Timeline Operations ============

    def log_match_event(self, match_id: int, game_number: int, event_type: str,
                        event_data: dict = None, team: int = None) -> int:
        """Log an event to the match timeline.

        Args:
            match_id: The match ID
            game_number: The game number within the match
            event_type: Type of event (ball_pocketed, game_win, golden_break, etc.)
            event_data: Additional event details as a dict
            team: Team number (1, 2, or None)

        Returns:
            The event ID
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        timestamp_ms = int(datetime.now().timestamp() * 1000)
        event_data_json = json.dumps(event_data or {})

        cursor.execute('''
            INSERT INTO match_events (match_id, game_number, event_type, event_data, team, timestamp, timestamp_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (match_id, game_number, event_type, event_data_json, team, timestamp, timestamp_ms))
        conn.commit()
        return cursor.lastrowid

    def get_match_timeline(self, match_id: int, game_number: int = None) -> list[dict]:
        """Get timeline events for a match.

        Args:
            match_id: The match ID
            game_number: Optional - filter to specific game number

        Returns:
            List of event dicts sorted by timestamp
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        if game_number is not None:
            cursor.execute('''
                SELECT * FROM match_events
                WHERE match_id = ? AND game_number = ?
                ORDER BY timestamp_ms ASC
            ''', (match_id, game_number))
        else:
            cursor.execute('''
                SELECT * FROM match_events
                WHERE match_id = ?
                ORDER BY game_number ASC, timestamp_ms ASC
            ''', (match_id,))

        events = []
        for row in cursor.fetchall():
            event = dict(row)
            # Parse event_data JSON
            try:
                event['event_data'] = json.loads(event['event_data'] or '{}')
            except (json.JSONDecodeError, TypeError):
                event['event_data'] = {}
            events.append(event)

        return events

    def clear_match_events(self, match_id: int, game_number: int = None):
        """Clear timeline events for a match or specific game.

        Args:
            match_id: The match ID
            game_number: Optional - only clear events for this game
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        if game_number is not None:
            cursor.execute('''
                DELETE FROM match_events
                WHERE match_id = ? AND game_number = ?
            ''', (match_id, game_number))
        else:
            cursor.execute('''
                DELETE FROM match_events
                WHERE match_id = ?
            ''', (match_id,))

        conn.commit()
    
    def get_queued_matches_in_current_round_only(self, league_night_id: int) -> list[dict]:
        """Get queued matches ONLY from the current round, not future rounds."""
        current_round = self.get_current_round(league_night_id)
        if current_round == 0:
            return []
        
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
            WHERE m.league_night_id = ? AND m.round_number = ? AND m.status = 'queued'
            ORDER BY m.queue_position
        ''', (league_night_id, current_round))
        return [dict(row) for row in cursor.fetchall()]
    
    # ============ Season-Aware Stats ============
    
    def get_player_stats_for_season(self, player_id: int, season_id: Optional[int] = None) -> dict:
        """Get player statistics for a specific season (or all time if season_id is None)."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        season_filter = "AND m.season_id = ?" if season_id else ""
        # Build params list - player_id repeated for each placeholder
        pid = player_id
        base_params = [pid, pid, pid, pid,  # games_won check
                       pid, pid,              # total_points check  
                       pid, pid, pid, pid,    # golden_breaks check
                       pid, pid, pid, pid]    # WHERE clause
        if season_id:
            base_params.append(season_id)
        
        cursor.execute(f'''
            SELECT 
                COUNT(*) as games_played,
                SUM(CASE 
                    WHEN (m.team1_player1_id = ? OR m.team1_player2_id = ?) AND g.winner_team = 1 THEN 1
                    WHEN (m.team2_player1_id = ? OR m.team2_player2_id = ?) AND g.winner_team = 2 THEN 1
                    ELSE 0 
                END) as games_won,
                SUM(CASE 
                    WHEN m.team1_player1_id = ? OR m.team1_player2_id = ? THEN g.team1_score
                    ELSE g.team2_score 
                END) as total_points,
                SUM(CASE WHEN g.golden_break = 1 AND (
                    (g.breaking_team = 1 AND (m.team1_player1_id = ? OR m.team1_player2_id = ?)) OR
                    (g.breaking_team = 2 AND (m.team2_player1_id = ? OR m.team2_player2_id = ?))
                ) THEN 1 ELSE 0 END) as golden_breaks
            FROM matches m
            JOIN games g ON g.match_id = m.id
            WHERE (m.team1_player1_id = ? OR m.team1_player2_id = ? 
                   OR m.team2_player1_id = ? OR m.team2_player2_id = ?)
            AND g.winner_team > 0
            {season_filter}
        ''', base_params)
        
        row = cursor.fetchone()
        games_played = row['games_played'] or 0
        games_won = row['games_won'] or 0
        
        return {
            'games_played': games_played,
            'games_won': games_won,
            'games_lost': games_played - games_won,
            'total_points': row['total_points'] or 0,
            'golden_breaks': row['golden_breaks'] or 0,
            'win_rate': (games_won / games_played * 100) if games_played > 0 else 0,
            'avg_points': (row['total_points'] or 0) / games_played if games_played > 0 else 0
        }
    
    def get_leaderboard_for_season(self, season_id: Optional[int] = None, 
                                   sort_by: str = "points") -> list[dict]:
        """Get leaderboard for a specific season, sorted by the specified field.
        Default sort is by total points (not wins)."""
        players = self.get_all_players(active_only=True)
        
        leaderboard = []
        for player in players:
            stats = self.get_player_stats_for_season(player.id, season_id)
            leaderboard.append({
                'player': player,
                'games_played': stats['games_played'],
                'games_won': stats['games_won'],
                'games_lost': stats['games_lost'],
                'total_points': stats['total_points'],
                'golden_breaks': stats['golden_breaks'],
                'win_rate': stats['win_rate'],
                'avg_points': stats['avg_points']
            })
        
        # Sort by specified field (default: points)
        if sort_by == "points":
            leaderboard.sort(key=lambda x: (-x['total_points'], -x['games_won']))
        elif sort_by == "wins":
            leaderboard.sort(key=lambda x: (-x['games_won'], -x['win_rate']))
        elif sort_by == "win_rate":
            leaderboard.sort(key=lambda x: (-x['win_rate'], -x['games_won']))
        elif sort_by == "avg_points":
            leaderboard.sort(key=lambda x: (-x['avg_points'], -x['games_won']))
        
        return leaderboard
    
    def get_partner_stats(self, player_id: int, season_id: Optional[int] = None) -> list[dict]:
        """Get stats for all partners a player has played with."""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        season_filter = "AND m.season_id = ?" if season_id else ""
        pid = player_id
        # 4 for CASE, 4 for wins SUM, 4 for WHERE = 12 total
        params = [pid, pid, pid, pid,  # CASE for partner_id
                  pid, pid, pid, pid,  # wins_together SUM
                  pid, pid, pid, pid]  # WHERE clause
        if season_id:
            params.append(season_id)
        
        cursor.execute(f'''
            SELECT 
                CASE 
                    WHEN m.team1_player1_id = ? THEN m.team1_player2_id
                    WHEN m.team1_player2_id = ? THEN m.team1_player1_id
                    WHEN m.team2_player1_id = ? THEN m.team2_player2_id
                    WHEN m.team2_player2_id = ? THEN m.team2_player1_id
                END as partner_id,
                COUNT(DISTINCT g.id) as games_together,
                SUM(CASE 
                    WHEN (m.team1_player1_id = ? OR m.team1_player2_id = ?) AND g.winner_team = 1 THEN 1
                    WHEN (m.team2_player1_id = ? OR m.team2_player2_id = ?) AND g.winner_team = 2 THEN 1
                    ELSE 0 
                END) as wins_together
            FROM matches m
            JOIN games g ON g.match_id = m.id
            WHERE (m.team1_player1_id = ? OR m.team1_player2_id = ? 
                   OR m.team2_player1_id = ? OR m.team2_player2_id = ?)
            AND g.winner_team > 0
            {season_filter}
            GROUP BY partner_id
            HAVING partner_id IS NOT NULL
        ''', params)
        
        partner_stats = []
        for row in cursor.fetchall():
            partner = self.get_player(row['partner_id'])
            if partner:
                games = row['games_together']
                wins = row['wins_together']
                partner_stats.append({
                    'partner': partner,
                    'games_together': games,
                    'wins_together': wins,
                    'win_rate': (wins / games * 100) if games > 0 else 0
                })
        
        # Sort by win rate
        partner_stats.sort(key=lambda x: (-x['win_rate'], -x['games_together']))
        return partner_stats
    
    def get_schedule_data_for_league_night(self, league_night_id: int) -> dict:
        """Reconstruct schedule data from database for PDF export.

        Returns a dict compatible with export_match_diagram_pdf() containing:
        - rounds: List of round data with matches
        - total_rounds: Total number of rounds
        - has_repeats: Whether there are repeat matchups
        - total_repeats: Count of repeat matchups
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # Get all pairs for this league night
        pairs = self.get_pairs_for_night(league_night_id)
        pair_lookup = {p['id']: p for p in pairs}

        # Build team display names
        def get_pair_display(pair_id: int) -> str:
            if pair_id not in pair_lookup:
                return "Unknown"
            pair = pair_lookup[pair_id]
            name1 = pair.get('player1_name', 'Unknown')
            name2 = pair.get('player2_name')
            if name2:
                return f"{name1} & {name2}"
            return name1

        # Get total rounds
        total_rounds = self.get_total_rounds(league_night_id)

        if total_rounds == 0:
            return {
                'rounds': [],
                'total_rounds': 0,
                'has_repeats': False,
                'total_repeats': 0
            }

        rounds_data = []
        total_repeats = 0

        for round_num in range(1, total_rounds + 1):
            # Get matches for this round
            matches = self.get_matches_for_round(league_night_id, round_num)

            # Build team display list for this round
            team_ids = set()
            for match in matches:
                if match.get('pair1_id'):
                    team_ids.add(match['pair1_id'])
                if match.get('pair2_id'):
                    team_ids.add(match['pair2_id'])

            team_display = [get_pair_display(pid) for pid in sorted(team_ids)]

            # Build match display data
            match_display = []
            round_repeats = 0

            for i, match in enumerate(matches, 1):
                team1 = get_pair_display(match.get('pair1_id'))
                team2 = get_pair_display(match.get('pair2_id'))

                # Check for repeat (simplified - would need matchup history for accurate count)
                is_repeat = False
                repeat_count = 0

                match_display.append({
                    'match_num': i,
                    'team1': team1,
                    'team2': team2,
                    'is_repeat': is_repeat,
                    'repeat_count': repeat_count,
                    'table_number': match.get('table_number'),
                    'status': match.get('status', 'queued')
                })

            rounds_data.append({
                'round_num': round_num,
                'team_display': team_display,
                'match_display': match_display,
                'round_repeats': round_repeats
            })

            total_repeats += round_repeats

        return {
            'rounds': rounds_data,
            'total_rounds': total_rounds,
            'has_repeats': total_repeats > 0,
            'total_repeats': total_repeats
        }

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
