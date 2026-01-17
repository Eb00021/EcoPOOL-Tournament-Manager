"""
EcoPOOL League - Advanced Statistics Module
Provides head-to-head stats, handicaps, predictive analytics, and player insights.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Tuple
from datetime import datetime, timedelta
import math


@dataclass
class HeadToHeadRecord:
    """Head-to-head record between two players."""
    player1_id: int
    player2_id: int
    player1_name: str
    player2_name: str
    player1_wins: int
    player2_wins: int
    total_games: int
    player1_points: int
    player2_points: int
    last_played: str


@dataclass
class PlayerStreak:
    """Current streak information for a player."""
    player_id: int
    streak_type: str  # 'win', 'loss', 'none'
    streak_count: int
    last_5_results: List[str]  # List of 'W' or 'L'


@dataclass
class PlayerForm:
    """Recent form analysis for a player."""
    player_id: int
    last_10_win_rate: float
    form_trend: str  # 'hot', 'cold', 'neutral'
    trend_change: float  # Percentage change from overall
    clutch_rating: float  # Performance in close games


class AdvancedStatsManager:
    """Manages advanced statistics and analytics."""

    def __init__(self, db_manager):
        self.db = db_manager
        self._init_tables()

    def _init_tables(self):
        """Initialize additional stats tables."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Match duration tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS match_timings (
                match_id INTEGER PRIMARY KEY,
                started_at TEXT,
                completed_at TEXT,
                duration_seconds INTEGER,
                FOREIGN KEY (match_id) REFERENCES matches(id)
            )
        ''')

        # Game duration tracking
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS game_timings (
                game_id INTEGER PRIMARY KEY,
                started_at TEXT,
                completed_at TEXT,
                duration_seconds INTEGER,
                FOREIGN KEY (game_id) REFERENCES games(id)
            )
        ''')

        # Player handicaps
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS player_handicaps (
                player_id INTEGER PRIMARY KEY,
                handicap_rating REAL DEFAULT 0,
                games_for_handicap INTEGER DEFAULT 0,
                last_updated TEXT,
                FOREIGN KEY (player_id) REFERENCES players(id)
            )
        ''')

        conn.commit()

    # ============ Head-to-Head Statistics ============

    def get_head_to_head(self, player1_id: int, player2_id: int) -> Optional[HeadToHeadRecord]:
        """Get head-to-head record between two players."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Get all games where these two players faced each other
        cursor.execute('''
            SELECT m.*, g.team1_score, g.team2_score, g.winner_team
            FROM matches m
            JOIN games g ON g.match_id = m.id
            WHERE g.winner_team > 0
            AND (
                (m.team1_player1_id = ? OR m.team1_player2_id = ?) AND
                (m.team2_player1_id = ? OR m.team2_player2_id = ?)
            ) OR (
                (m.team1_player1_id = ? OR m.team1_player2_id = ?) AND
                (m.team2_player1_id = ? OR m.team2_player2_id = ?)
            )
            ORDER BY m.date DESC
        ''', (player1_id, player1_id, player2_id, player2_id,
              player2_id, player2_id, player1_id, player1_id))

        rows = cursor.fetchall()
        if not rows:
            return None

        p1_wins = 0
        p2_wins = 0
        p1_points = 0
        p2_points = 0
        last_played = None

        for row in rows:
            # Determine which team each player was on
            p1_on_team1 = row['team1_player1_id'] == player1_id or row['team1_player2_id'] == player1_id
            p2_on_team1 = row['team1_player1_id'] == player2_id or row['team1_player2_id'] == player2_id

            if p1_on_team1 and not p2_on_team1:
                # p1 on team 1, p2 on team 2
                p1_points += row['team1_score']
                p2_points += row['team2_score']
                if row['winner_team'] == 1:
                    p1_wins += 1
                else:
                    p2_wins += 1
            elif p2_on_team1 and not p1_on_team1:
                # p2 on team 1, p1 on team 2
                p2_points += row['team1_score']
                p1_points += row['team2_score']
                if row['winner_team'] == 1:
                    p2_wins += 1
                else:
                    p1_wins += 1

            if not last_played:
                last_played = row['date']

        # Get player names
        p1 = self.db.get_player(player1_id)
        p2 = self.db.get_player(player2_id)

        return HeadToHeadRecord(
            player1_id=player1_id,
            player2_id=player2_id,
            player1_name=p1.name if p1 else "Unknown",
            player2_name=p2.name if p2 else "Unknown",
            player1_wins=p1_wins,
            player2_wins=p2_wins,
            total_games=p1_wins + p2_wins,
            player1_points=p1_points,
            player2_points=p2_points,
            last_played=last_played or ""
        )

    def get_all_rivalries(self, player_id: int) -> List[HeadToHeadRecord]:
        """Get head-to-head records against all opponents."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Find all players this player has faced
        cursor.execute('''
            SELECT DISTINCT
                CASE
                    WHEN team1_player1_id = ? THEN team2_player1_id
                    WHEN team1_player2_id = ? THEN team2_player1_id
                    WHEN team2_player1_id = ? THEN team1_player1_id
                    WHEN team2_player2_id = ? THEN team1_player1_id
                END as opponent_id
            FROM matches
            WHERE team1_player1_id = ? OR team1_player2_id = ?
               OR team2_player1_id = ? OR team2_player2_id = ?
        ''', (player_id,) * 8)

        opponent_ids = [row['opponent_id'] for row in cursor.fetchall() if row['opponent_id']]

        rivalries = []
        for opp_id in set(opponent_ids):
            if opp_id and opp_id != player_id:
                h2h = self.get_head_to_head(player_id, opp_id)
                if h2h and h2h.total_games > 0:
                    rivalries.append(h2h)

        # Sort by most games played
        rivalries.sort(key=lambda x: -x.total_games)
        return rivalries

    # ============ Win Streaks and Form ============

    def get_player_streak(self, player_id: int) -> PlayerStreak:
        """Get current win/loss streak for a player."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Get recent games ordered by date
        cursor.execute('''
            SELECT g.winner_team, m.team1_player1_id, m.team1_player2_id,
                   m.team2_player1_id, m.team2_player2_id
            FROM games g
            JOIN matches m ON g.match_id = m.id
            WHERE g.winner_team > 0
            AND (m.team1_player1_id = ? OR m.team1_player2_id = ?
                 OR m.team2_player1_id = ? OR m.team2_player2_id = ?)
            ORDER BY m.date DESC, g.game_number DESC
            LIMIT 20
        ''', (player_id,) * 4)

        results = []
        for row in cursor.fetchall():
            is_team1 = row['team1_player1_id'] == player_id or row['team1_player2_id'] == player_id
            won = (is_team1 and row['winner_team'] == 1) or (not is_team1 and row['winner_team'] == 2)
            results.append('W' if won else 'L')

        if not results:
            return PlayerStreak(player_id, 'none', 0, [])

        # Calculate current streak
        streak_type = results[0]
        streak_count = 0
        for r in results:
            if r == streak_type:
                streak_count += 1
            else:
                break

        return PlayerStreak(
            player_id=player_id,
            streak_type='win' if streak_type == 'W' else 'loss',
            streak_count=streak_count,
            last_5_results=results[:5]
        )

    def get_player_form(self, player_id: int) -> PlayerForm:
        """Analyze recent form for a player."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Get last 10 games
        cursor.execute('''
            SELECT g.winner_team, g.team1_score, g.team2_score,
                   m.team1_player1_id, m.team1_player2_id,
                   m.team2_player1_id, m.team2_player2_id
            FROM games g
            JOIN matches m ON g.match_id = m.id
            WHERE g.winner_team > 0
            AND (m.team1_player1_id = ? OR m.team1_player2_id = ?
                 OR m.team2_player1_id = ? OR m.team2_player2_id = ?)
            ORDER BY m.date DESC, g.game_number DESC
            LIMIT 10
        ''', (player_id,) * 4)

        rows = cursor.fetchall()
        if len(rows) < 5:
            return PlayerForm(player_id, 0, 'neutral', 0, 0)

        # Calculate recent stats
        recent_wins = 0
        close_games = 0
        close_wins = 0

        for row in rows:
            is_team1 = row['team1_player1_id'] == player_id or row['team1_player2_id'] == player_id
            won = (is_team1 and row['winner_team'] == 1) or (not is_team1 and row['winner_team'] == 2)

            if won:
                recent_wins += 1

            # Close game = within 3 points
            score_diff = abs(row['team1_score'] - row['team2_score'])
            if score_diff <= 3:
                close_games += 1
                if won:
                    close_wins += 1

        last_10_rate = (recent_wins / len(rows)) * 100

        # Compare to overall
        player = self.db.get_player(player_id)
        overall_rate = player.win_rate if player else 50

        trend_change = last_10_rate - overall_rate

        if trend_change > 10:
            form_trend = 'hot'
        elif trend_change < -10:
            form_trend = 'cold'
        else:
            form_trend = 'neutral'

        # Clutch rating (performance in close games)
        clutch_rating = (close_wins / close_games * 100) if close_games > 0 else 50

        return PlayerForm(
            player_id=player_id,
            last_10_win_rate=last_10_rate,
            form_trend=form_trend,
            trend_change=trend_change,
            clutch_rating=clutch_rating
        )

    # ============ Handicap System ============

    def calculate_handicap(self, player_id: int) -> float:
        """Calculate handicap rating for a player.
        Higher handicap = weaker player (gets points).
        Scale: -5 to +5 where 0 is average."""
        player = self.db.get_player(player_id)
        if not player or player.games_played < 5:
            return 0.0  # Not enough games

        # Base handicap on win rate deviation from 50%
        # A 50% player has 0 handicap
        # A 70% player has negative handicap (gives points)
        # A 30% player has positive handicap (gets points)

        win_rate = player.win_rate
        avg_points = player.avg_points

        # Win rate component (±3 points max)
        win_handicap = ((50 - win_rate) / 50) * 3

        # Points component (based on deviation from league average of ~5)
        points_handicap = ((5 - avg_points) / 5) * 2

        total_handicap = win_handicap + points_handicap

        # Clamp to ±5
        return max(-5, min(5, round(total_handicap, 1)))

    def get_handicap_adjusted_odds(self, player1_id: int, player2_id: int) -> Tuple[float, float]:
        """Get handicap-adjusted win probability for two players."""
        h1 = self.calculate_handicap(player1_id)
        h2 = self.calculate_handicap(player2_id)

        # Difference in handicaps affects odds
        diff = h2 - h1  # Positive = player1 has advantage

        # Convert to probability (sigmoid-like)
        p1_odds = 50 + (diff * 8)  # Each handicap point = ~8% swing
        p1_odds = max(10, min(90, p1_odds))

        return (p1_odds, 100 - p1_odds)

    def update_player_handicap(self, player_id: int):
        """Update stored handicap for a player."""
        handicap = self.calculate_handicap(player_id)
        player = self.db.get_player(player_id)

        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO player_handicaps (player_id, handicap_rating, games_for_handicap, last_updated)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(player_id) DO UPDATE SET
                handicap_rating = excluded.handicap_rating,
                games_for_handicap = excluded.games_for_handicap,
                last_updated = excluded.last_updated
        ''', (player_id, handicap, player.games_played if player else 0, datetime.now().isoformat()))

        conn.commit()

    # ============ Predictive Analytics ============

    def predict_match_outcome(self, team1_p1: int, team1_p2: Optional[int],
                             team2_p1: int, team2_p2: Optional[int]) -> Dict:
        """Predict match outcome based on historical data."""
        # Get player stats
        p1_stats = self._get_team_combined_stats(team1_p1, team1_p2)
        p2_stats = self._get_team_combined_stats(team2_p1, team2_p2)

        # Base prediction on multiple factors
        factors = {}

        # 1. Win rate factor (40% weight)
        wr1 = p1_stats['combined_win_rate']
        wr2 = p2_stats['combined_win_rate']
        wr_factor = wr1 / (wr1 + wr2) if (wr1 + wr2) > 0 else 0.5
        factors['win_rate'] = wr_factor

        # 2. Recent form factor (30% weight)
        form1 = self._get_team_form_score(team1_p1, team1_p2)
        form2 = self._get_team_form_score(team2_p1, team2_p2)
        form_factor = form1 / (form1 + form2) if (form1 + form2) > 0 else 0.5
        factors['form'] = form_factor

        # 3. Head-to-head factor (20% weight)
        h2h_factor = self._get_team_h2h_factor(team1_p1, team1_p2, team2_p1, team2_p2)
        factors['head_to_head'] = h2h_factor

        # 4. Experience factor (10% weight)
        exp1 = p1_stats['total_games']
        exp2 = p2_stats['total_games']
        exp_factor = exp1 / (exp1 + exp2) if (exp1 + exp2) > 0 else 0.5
        factors['experience'] = exp_factor

        # Weighted combination
        team1_prob = (
            factors['win_rate'] * 0.4 +
            factors['form'] * 0.3 +
            factors['head_to_head'] * 0.2 +
            factors['experience'] * 0.1
        ) * 100

        team1_prob = max(15, min(85, team1_prob))  # Cap at 15-85%

        return {
            'team1_win_probability': round(team1_prob, 1),
            'team2_win_probability': round(100 - team1_prob, 1),
            'confidence': self._calculate_prediction_confidence(p1_stats, p2_stats),
            'factors': factors,
            'team1_stats': p1_stats,
            'team2_stats': p2_stats
        }

    def _get_team_combined_stats(self, p1_id: int, p2_id: Optional[int]) -> Dict:
        """Get combined statistics for a team."""
        p1 = self.db.get_player(p1_id)
        p2 = self.db.get_player(p2_id) if p2_id else None

        if p2:
            return {
                'combined_win_rate': (p1.win_rate + p2.win_rate) / 2 if p1 else 0,
                'combined_avg_points': (p1.avg_points + p2.avg_points) / 2 if p1 else 0,
                'total_games': (p1.games_played if p1 else 0) + (p2.games_played if p2 else 0),
                'total_golden_breaks': (p1.golden_breaks if p1 else 0) + (p2.golden_breaks if p2 else 0)
            }
        else:
            return {
                'combined_win_rate': p1.win_rate if p1 else 0,
                'combined_avg_points': p1.avg_points if p1 else 0,
                'total_games': p1.games_played if p1 else 0,
                'total_golden_breaks': p1.golden_breaks if p1 else 0
            }

    def _get_team_form_score(self, p1_id: int, p2_id: Optional[int]) -> float:
        """Get combined form score for a team (0-100)."""
        form1 = self.get_player_form(p1_id)
        form2 = self.get_player_form(p2_id) if p2_id else None

        score1 = form1.last_10_win_rate if form1 else 50
        score2 = form2.last_10_win_rate if form2 else 50

        if form2:
            return (score1 + score2) / 2
        return score1

    def _get_team_h2h_factor(self, t1_p1: int, t1_p2: Optional[int],
                            t2_p1: int, t2_p2: Optional[int]) -> float:
        """Get head-to-head factor for teams (0-1)."""
        # Check if these exact teams have played before
        # This is simplified - in reality we'd check historical matchups
        h2h = self.get_head_to_head(t1_p1, t2_p1)
        if h2h and h2h.total_games > 0:
            return h2h.player1_wins / h2h.total_games
        return 0.5

    def _calculate_prediction_confidence(self, stats1: Dict, stats2: Dict) -> str:
        """Calculate confidence level in prediction."""
        total_games = stats1['total_games'] + stats2['total_games']

        if total_games >= 100:
            return 'high'
        elif total_games >= 40:
            return 'medium'
        else:
            return 'low'

    # ============ Match Timing ============

    def start_match_timer(self, match_id: int):
        """Record match start time."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO match_timings (match_id, started_at)
            VALUES (?, ?)
        ''', (match_id, datetime.now().isoformat()))

        conn.commit()

    def complete_match_timer(self, match_id: int):
        """Record match completion time and calculate duration."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT started_at FROM match_timings WHERE match_id = ?', (match_id,))
        row = cursor.fetchone()

        if row and row['started_at']:
            started = datetime.fromisoformat(row['started_at'])
            completed = datetime.now()
            duration = int((completed - started).total_seconds())

            cursor.execute('''
                UPDATE match_timings
                SET completed_at = ?, duration_seconds = ?
                WHERE match_id = ?
            ''', (completed.isoformat(), duration, match_id))

            conn.commit()
            return duration

        return None

    def get_average_match_duration(self) -> Optional[int]:
        """Get average match duration in seconds."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT AVG(duration_seconds) as avg_duration
            FROM match_timings
            WHERE duration_seconds > 0
        ''')

        row = cursor.fetchone()
        return int(row['avg_duration']) if row and row['avg_duration'] else None

    def get_player_avg_game_duration(self, player_id: int) -> Optional[int]:
        """Get average game duration for a player."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT AVG(mt.duration_seconds) as avg_duration
            FROM match_timings mt
            JOIN matches m ON mt.match_id = m.id
            WHERE mt.duration_seconds > 0
            AND (m.team1_player1_id = ? OR m.team1_player2_id = ?
                 OR m.team2_player1_id = ? OR m.team2_player2_id = ?)
        ''', (player_id,) * 4)

        row = cursor.fetchone()
        return int(row['avg_duration']) if row and row['avg_duration'] else None

    # ============ Player of the Night ============

    def calculate_player_of_night(self, league_night_id: int) -> Optional[Dict]:
        """Calculate Player of the Night based on performance."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Get all games from tonight
        cursor.execute('''
            SELECT m.team1_player1_id, m.team1_player2_id,
                   m.team2_player1_id, m.team2_player2_id,
                   g.team1_score, g.team2_score, g.winner_team,
                   g.golden_break, g.breaking_team
            FROM matches m
            JOIN games g ON g.match_id = m.id
            WHERE m.league_night_id = ? AND g.winner_team > 0
        ''', (league_night_id,))

        rows = cursor.fetchall()
        if not rows:
            return None

        # Calculate scores for each player
        player_scores = {}

        for row in rows:
            # Process each player in the game
            for team, players in [(1, [row['team1_player1_id'], row['team1_player2_id']]),
                                  (2, [row['team2_player1_id'], row['team2_player2_id']])]:
                for pid in players:
                    if not pid:
                        continue

                    if pid not in player_scores:
                        player_scores[pid] = {
                            'games': 0, 'wins': 0, 'points': 0,
                            'golden_breaks': 0, 'score': 0
                        }

                    player_scores[pid]['games'] += 1

                    if team == 1:
                        player_scores[pid]['points'] += row['team1_score']
                        if row['winner_team'] == 1:
                            player_scores[pid]['wins'] += 1
                    else:
                        player_scores[pid]['points'] += row['team2_score']
                        if row['winner_team'] == 2:
                            player_scores[pid]['wins'] += 1

                    if row['golden_break'] and row['breaking_team'] == team:
                        player_scores[pid]['golden_breaks'] += 1

        # Calculate composite score
        for pid, stats in player_scores.items():
            if stats['games'] < 2:
                stats['score'] = 0
                continue

            win_rate = stats['wins'] / stats['games']
            points_per_game = stats['points'] / stats['games']

            # Score formula: wins * 10 + points + golden_breaks * 15 + (win_rate * 20)
            stats['score'] = (
                stats['wins'] * 10 +
                stats['points'] +
                stats['golden_breaks'] * 15 +
                win_rate * 20
            )

        if not player_scores:
            return None

        # Find winner
        winner_id = max(player_scores, key=lambda x: player_scores[x]['score'])
        winner = self.db.get_player(winner_id)

        return {
            'player': winner,
            'stats': player_scores[winner_id],
            'all_scores': [(self.db.get_player(pid), stats)
                          for pid, stats in sorted(player_scores.items(),
                                                   key=lambda x: -x[1]['score'])[:5]]
        }

    # ============ League Night Summary ============

    def generate_night_summary(self, league_night_id: int) -> Dict:
        """Generate comprehensive summary for a league night."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Get league night info
        night = self.db.get_league_night(league_night_id)
        if not night:
            return {}

        # Get all matches
        cursor.execute('''
            SELECT m.*, g.team1_score, g.team2_score, g.winner_team,
                   g.golden_break, g.breaking_team,
                   p1.name as t1p1_name, p2.name as t1p2_name,
                   p3.name as t2p1_name, p4.name as t2p2_name
            FROM matches m
            JOIN games g ON g.match_id = m.id
            LEFT JOIN players p1 ON m.team1_player1_id = p1.id
            LEFT JOIN players p2 ON m.team1_player2_id = p2.id
            LEFT JOIN players p3 ON m.team2_player1_id = p3.id
            LEFT JOIN players p4 ON m.team2_player2_id = p4.id
            WHERE m.league_night_id = ? AND g.winner_team > 0
        ''', (league_night_id,))

        rows = cursor.fetchall()

        total_games = len(rows)
        total_points = sum(r['team1_score'] + r['team2_score'] for r in rows)
        golden_breaks = sum(1 for r in rows if r['golden_break'])

        # Find highest scoring game
        highest_game = max(rows, key=lambda r: r['team1_score'] + r['team2_score']) if rows else None

        # Find closest game
        closest_game = min(rows, key=lambda r: abs(r['team1_score'] - r['team2_score'])) if rows else None

        # Player of the night
        potn = self.calculate_player_of_night(league_night_id)

        return {
            'league_night': night,
            'total_games': total_games,
            'total_points': total_points,
            'golden_breaks': golden_breaks,
            'avg_points_per_game': total_points / total_games if total_games > 0 else 0,
            'highest_scoring_game': highest_game,
            'closest_game': closest_game,
            'player_of_night': potn,
            'games': rows
        }
