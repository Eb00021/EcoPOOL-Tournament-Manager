"""
EcoPOOL League - Live Scores Web Server
A mobile-friendly web server that displays real-time league night scores.
Uses Server-Sent Events (SSE) for live updates without page refresh.
"""

import threading
import time
import json
import socket
import os
import atexit
import signal
import sys
from datetime import datetime
from flask import Flask, Response, render_template_string, jsonify, send_file, abort
import logging

# Suppress Flask's default logging to keep console clean
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# Global reference for cleanup
_active_servers = []


class LiveScoreServer:
    """Web server for displaying live league night scores."""
    
    def __init__(self, db_manager, port=5000):
        self.db = db_manager
        self.db_path = db_manager.db_path  # Store path for creating thread-local connections
        self.port = port
        self.app = Flask(__name__)
        self.server_thread = None
        self.running = False
        self._last_data_hash = None
        self._update_event = threading.Event()
        self._shutdown_event = threading.Event()
        
        # Thread-local storage for database connections
        self._local = threading.local()
        
        # Register for global cleanup
        _active_servers.append(self)
        
        # Setup routes
        self._setup_routes()
    
    def _get_thread_db(self):
        """Get a thread-local database connection."""
        if not hasattr(self._local, 'db'):
            from database import DatabaseManager
            self._local.db = DatabaseManager(self.db_path)
        return self._local.db
    
    def _setup_routes(self):
        """Setup Flask routes."""
        
        @self.app.route('/')
        def index():
            return render_template_string(self._get_html_template())
        
        @self.app.route('/api/scores')
        def get_scores():
            """API endpoint for current scores."""
            return jsonify(self._get_scores_data())
        
        @self.app.route('/api/match/<int:match_id>')
        def get_match_details(match_id):
            """API endpoint for detailed match/scorecard data."""
            return jsonify(self._get_match_details(match_id))
        
        @self.app.route('/api/pfp/<path:filename>')
        def get_profile_picture(filename):
            """Serve profile picture images."""
            try:
                # Look for the file in the profile_pictures directory
                pictures_dir = os.path.join(os.path.dirname(__file__), "profile_pictures")
                filepath = os.path.join(pictures_dir, filename)
                
                # Security check - ensure the file is within the pictures directory
                filepath = os.path.abspath(filepath)
                pictures_dir = os.path.abspath(pictures_dir)
                
                if not filepath.startswith(pictures_dir):
                    abort(403)
                
                if os.path.exists(filepath) and os.path.isfile(filepath):
                    return send_file(filepath)
                else:
                    abort(404)
            except Exception:
                abort(404)
        
        @self.app.route('/api/stream')
        def stream():
            """Server-Sent Events endpoint for live updates."""
            def generate():
                while self.running and not self._shutdown_event.is_set():
                    # Send current data
                    data = self._get_scores_data()
                    yield f"data: {json.dumps(data)}\n\n"
                    
                    # Wait for update signal or timeout (poll every 2 seconds)
                    self._update_event.wait(timeout=2.0)
                    self._update_event.clear()
            
            return Response(
                generate(),
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive',
                    'Access-Control-Allow-Origin': '*'
                }
            )
    
    def _get_scores_data(self) -> dict:
        """Get current scores data from database."""
        try:
            # Use thread-local database connection
            db = self._get_thread_db()
            
            # Get current league night for queue info
            league_night = db.get_current_league_night()
            
            # Get all active (incomplete) matches
            matches = db.get_all_matches(limit=50)
            
            live_matches = []
            completed_matches = []
            
            # Get all game data in one batch query
            match_ids = [m['id'] for m in matches]
            all_games = db.get_games_for_matches(match_ids) if match_ids else {}
            
            for match in matches:
                match_data = self._format_match(match, all_games.get(match['id'], []))
                
                if match['is_complete']:
                    completed_matches.append(match_data)
                else:
                    live_matches.append(match_data)
            
            # Get queue data
            queue_data = []
            current_round = 0
            total_rounds = 0
            round_progress = None
            
            if league_night:
                queued_matches = db.get_queued_matches(league_night['id'])
                for i, match in enumerate(queued_matches):
                    queue_data.append(self._format_queue_item(match, i + 1))
                
                # Get round info
                current_round = db.get_current_round(league_night['id'])
                total_rounds = db.get_total_rounds(league_night['id'])
                
                if current_round > 0:
                    round_matches = db.get_matches_for_round(league_night['id'], current_round)
                    completed_in_round = sum(1 for m in round_matches if m['status'] == 'completed')
                    live_in_round = sum(1 for m in round_matches if m['status'] == 'live')
                    total_in_round = len(round_matches)
                    
                    round_progress = {
                        'current_round': current_round,
                        'total_rounds': total_rounds,
                        'completed': completed_in_round,
                        'live': live_in_round,
                        'total': total_in_round
                    }
            
            # Get tables data
            tables_data = self._get_tables_data(db, league_night, all_games)
            
            # Get leaderboard (top 10)
            leaderboard = db.get_leaderboard_for_season(None, "points")[:10]
            leaderboard_data = [
                {
                    'rank': i + 1,
                    'name': entry['player'].name,
                    'profile_picture': entry['player'].profile_picture if hasattr(entry['player'], 'profile_picture') else '',
                    'points': entry['total_points'],
                    'wins': entry['games_won'],
                    'losses': entry['games_lost'],
                    'games': entry['games_played'],
                    'win_rate': round(entry['win_rate'], 1),
                    'avg_points': round(entry['avg_points'], 1),
                    'golden_breaks': entry['golden_breaks']
                }
                for i, entry in enumerate(leaderboard)
            ]
            
            # Calculate overall league stats
            total_games = sum(p['games'] for p in leaderboard_data)
            total_points = sum(p['points'] for p in leaderboard_data)
            total_golden = sum(p['golden_breaks'] for p in leaderboard_data)
            
            # Find leaders
            top_scorer = leaderboard_data[0] if leaderboard_data else None
            top_win_rate = max(leaderboard_data, key=lambda x: (x['win_rate'], x['games'])) if leaderboard_data else None
            top_golden = max(leaderboard_data, key=lambda x: x['golden_breaks']) if leaderboard_data else None
            
            league_stats = {
                'total_games': total_games // 2,  # Divide by 2 since each game has 2 players
                'total_points': total_points,
                'total_golden': total_golden,
                'top_scorer': top_scorer['name'] if top_scorer else None,
                'top_scorer_pts': top_scorer['points'] if top_scorer else 0,
                'top_scorer_pfp': top_scorer.get('profile_picture', '') if top_scorer else '',
                'best_win_rate': top_win_rate['name'] if top_win_rate and top_win_rate['games'] >= 3 else None,
                'best_win_rate_pct': top_win_rate['win_rate'] if top_win_rate and top_win_rate['games'] >= 3 else 0,
                'best_win_rate_pfp': top_win_rate.get('profile_picture', '') if top_win_rate and top_win_rate['games'] >= 3 else '',
                'most_golden': top_golden['name'] if top_golden and top_golden['golden_breaks'] > 0 else None,
                'most_golden_count': top_golden['golden_breaks'] if top_golden else 0,
                'most_golden_pfp': top_golden.get('profile_picture', '') if top_golden and top_golden['golden_breaks'] > 0 else ''
            }
            
            return {
                'timestamp': datetime.now().strftime('%I:%M:%S %p'),
                'live_matches': live_matches,
                'completed_matches': completed_matches[:5],  # Last 5 completed
                'queue': queue_data,
                'tables': tables_data,
                'leaderboard': leaderboard_data,
                'league_stats': league_stats,
                'round_progress': round_progress,
                'total_live': len(live_matches),
                'total_completed': len([m for m in matches if m['is_complete']]),
                'total_queued': len(queue_data)
            }
        except Exception as e:
            return {
                'timestamp': datetime.now().strftime('%I:%M:%S %p'),
                'error': str(e),
                'live_matches': [],
                'completed_matches': [],
                'queue': [],
                'tables': [],
                'leaderboard': [],
                'league_stats': {},
                'round_progress': None,
                'total_live': 0,
                'total_completed': 0,
                'total_queued': 0
            }
    
    def _format_match(self, match: dict, games: list) -> dict:
        """Format a match for the web display."""
        # Team names
        team1 = match['team1_p1_name'] or "TBD"
        if match['team1_p2_name']:
            team1 += f" & {match['team1_p2_name']}"
        
        team2 = match['team2_p1_name'] or "TBD"
        if match['team2_p2_name']:
            team2 += f" & {match['team2_p2_name']}"
        
        # Calculate match score (games won)
        team1_games_won = sum(1 for g in games if g.get('winner_team') == 1)
        team2_games_won = sum(1 for g in games if g.get('winner_team') == 2)
        
        # Get current game scores
        current_game = None
        for g in games:
            if g.get('winner_team', 0) == 0:  # Incomplete game
                current_game = g
                break
        
        team1_points = current_game.get('team1_score', 0) if current_game else 0
        team2_points = current_game.get('team2_score', 0) if current_game else 0
        
        # If all games complete, show final game scores
        if not current_game and games:
            last_game = games[-1]
            team1_points = last_game.get('team1_score', 0)
            team2_points = last_game.get('team2_score', 0)
        
        return {
            'id': match['id'],
            'team1': team1,
            'team2': team2,
            'team1_games': team1_games_won,
            'team2_games': team2_games_won,
            'team1_points': team1_points,
            'team2_points': team2_points,
            'table': match.get('table_number', 0),
            'is_finals': match.get('is_finals', False),
            'best_of': match.get('best_of', 1)
        }
    
    def _format_queue_item(self, match: dict, position: int) -> dict:
        """Format a queued match for the web display."""
        team1 = match['team1_p1_name'] or "TBD"
        if match['team1_p2_name']:
            team1 += f" & {match['team1_p2_name']}"
        
        team2 = match['team2_p1_name'] or "TBD"
        if match['team2_p2_name']:
            team2 += f" & {match['team2_p2_name']}"
        
        return {
            'id': match['id'],
            'position': position,
            'team1': team1,
            'team2': team2,
            'round': match.get('round_number', 1),
            'is_finals': match.get('is_finals', False)
        }
    
    def _get_tables_data(self, db, league_night, all_games: dict) -> list:
        """Get visual table data showing which tables are active."""
        tables = []
        
        # Get table count from league night or default
        if league_night:
            num_tables = league_night.get('table_count', 3)
        else:
            num_tables = int(db.get_setting("num_tables", "3"))
        
        # Get active matches by table
        active_tables = {}
        if league_night:
            live_matches = db.get_live_matches(league_night['id'])
            for match in live_matches:
                table_num = match['table_number']
                active_tables[table_num] = match
        else:
            # Fallback to old method
            matches = db.get_all_matches(limit=100)
            for match in matches:
                if not match['is_complete']:
                    table_num = match['table_number']
                    if table_num not in active_tables:
                        active_tables[table_num] = match
        
        # Build table data
        for i in range(1, num_tables + 1):
            match = active_tables.get(i)
            if match:
                # Get game data for this match
                games = all_games.get(match['id'], [])
                t1_wins = sum(1 for g in games if g.get('winner_team') == 1)
                t2_wins = sum(1 for g in games if g.get('winner_team') == 2)
                
                # Get current game info
                current_game = None
                for g in games:
                    if g.get('winner_team', 0) == 0:
                        current_game = g
                        break
                
                # Extract first names for cleaner display
                team1_p1_first = (match['team1_p1_name'] or "TBD").split()[0] if match['team1_p1_name'] else "TBD"
                team1_p2_first = match['team1_p2_name'].split()[0] if match['team1_p2_name'] else None
                team2_p1_first = (match['team2_p1_name'] or "TBD").split()[0] if match['team2_p1_name'] else "TBD"
                team2_p2_first = match['team2_p2_name'].split()[0] if match['team2_p2_name'] else None
                
                team1 = team1_p1_first
                if team1_p2_first:
                    team1 += f" & {team1_p2_first}"
                
                team2 = team2_p1_first
                if team2_p2_first:
                    team2 += f" & {team2_p2_first}"
                
                # Get group assignment (solids/stripes) from current game
                team1_group = current_game.get('team1_group', '') if current_game else ''
                
                tables.append({
                    'table_number': i,
                    'status': 'live',
                    'match_id': match['id'],
                    'team1': team1,
                    'team2': team2,
                    'team1_games': t1_wins,
                    'team2_games': t2_wins,
                    'team1_points': current_game.get('team1_score', 0) if current_game else 0,
                    'team2_points': current_game.get('team2_score', 0) if current_game else 0,
                    'is_finals': match.get('is_finals', False),
                    'team1_group': team1_group  # 'solids', 'stripes', or ''
                })
            else:
                tables.append({
                    'table_number': i,
                    'status': 'available',
                    'match_id': None,
                    'team1': None,
                    'team2': None,
                    'team1_games': 0,
                    'team2_games': 0,
                    'team1_points': 0,
                    'team2_points': 0,
                    'is_finals': False,
                    'team1_group': ''
                })
        
        return tables
    
    def _get_match_details(self, match_id: int) -> dict:
        """Get detailed match info including balls pocketed for scorecard view."""
        try:
            db = self._get_thread_db()
            match = db.get_match(match_id)
            
            if not match:
                return {'error': 'Match not found'}
            
            games = db.get_games_for_match(match_id)
            
            # Extract first names for cleaner display
            team1_p1_first = (match['team1_p1_name'] or "TBD").split()[0] if match['team1_p1_name'] else "TBD"
            team1_p2_first = match['team1_p2_name'].split()[0] if match['team1_p2_name'] else None
            team2_p1_first = (match['team2_p1_name'] or "TBD").split()[0] if match['team2_p1_name'] else "TBD"
            team2_p2_first = match['team2_p2_name'].split()[0] if match['team2_p2_name'] else None
            
            team1 = team1_p1_first
            if team1_p2_first:
                team1 += f" & {team1_p2_first}"
            
            team2 = team2_p1_first
            if team2_p2_first:
                team2 += f" & {team2_p2_first}"
            
            # Calculate match score
            t1_wins = sum(1 for g in games if g.get('winner_team') == 1)
            t2_wins = sum(1 for g in games if g.get('winner_team') == 2)
            
            # Get current game's group assignment for display
            current_game_group = ''
            for g in games:
                if g.get('winner_team', 0) == 0:  # Current incomplete game
                    current_game_group = g.get('team1_group', '')
                    break
            # If all games complete, use last game's group
            if not current_game_group and games:
                current_game_group = games[-1].get('team1_group', '')
            
            # Format games with ball data
            games_data = []
            for g in games:
                balls = g.get('balls_pocketed', {})
                # balls_pocketed is a dict of ball_num -> team that pocketed it
                team1_balls = [int(b) for b, t in balls.items() if t == 1]
                team2_balls = [int(b) for b, t in balls.items() if t == 2]
                
                games_data.append({
                    'game_number': g['game_number'],
                    'team1_score': g['team1_score'],
                    'team2_score': g['team2_score'],
                    'team1_group': g.get('team1_group', ''),
                    'winner_team': g.get('winner_team', 0),
                    'golden_break': g.get('golden_break', False),
                    'team1_balls': sorted(team1_balls),
                    'team2_balls': sorted(team2_balls),
                    'balls_pocketed': balls
                })
            
            return {
                'id': match_id,
                'team1': team1,
                'team2': team2,
                'team1_games': t1_wins,
                'team2_games': t2_wins,
                'best_of': match.get('best_of', 1),
                'is_finals': match.get('is_finals', False),
                'is_complete': match.get('is_complete', False),
                'table': match.get('table_number', 0),
                'games': games_data,
                'team1_group': current_game_group  # Current/last game's group assignment
            }
        except Exception as e:
            return {'error': str(e)}
    
    def _get_html_template(self) -> str:
        """Get the HTML template for the live scores page."""
        return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="mobile-web-app-capable" content="yes">
    <title>EcoPOOL Live Scores</title>
    <style>
        :root {
            --bg-primary: #0d1117;
            --bg-secondary: #161b22;
            --bg-card: #1a1a2e;
            --bg-accent: #252540;
            --text-primary: #ffffff;
            --text-secondary: #888888;
            --green: #4CAF50;
            --green-dark: #2d7a3e;
            --blue: #2196F3;
            --gold: #ffd700;
            --red: #ff6b6b;
            --orange: #ff9800;
            --felt-green: #0B6623;
        }
        
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            padding: 10px;
            padding-bottom: 80px;
        }
        
        .header {
            text-align: center;
            padding: 15px 10px;
            background: linear-gradient(135deg, var(--green-dark), #1a5f2a);
            border-radius: 15px;
            margin-bottom: 15px;
        }
        
        .header h1 {
            font-size: 1.5em;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }
        
        .header .subtitle {
            font-size: 0.85em;
            color: var(--text-secondary);
            margin-top: 5px;
        }
        
        .live-indicator {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: rgba(255,0,0,0.2);
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 0.8em;
            margin-top: 8px;
        }
        
        .live-dot {
            width: 8px;
            height: 8px;
            background: #ff4444;
            border-radius: 50%;
            animation: pulse 1.5s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(1.2); }
        }
        
        .section {
            margin-bottom: 20px;
        }
        
        .section-title {
            font-size: 1.1em;
            color: var(--text-secondary);
            padding: 8px 12px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .match-card {
            background: var(--bg-card);
            border-radius: 12px;
            padding: 15px;
            margin-bottom: 10px;
            border-left: 4px solid var(--green);
        }
        
        .match-card.completed {
            border-left-color: var(--text-secondary);
            opacity: 0.8;
        }
        
        .match-card.finals {
            border-left-color: var(--gold);
            background: linear-gradient(135deg, var(--bg-card), #2a2a3a);
        }
        
        .match-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.75em;
            color: var(--text-secondary);
            margin-bottom: 10px;
        }
        
        .table-badge {
            background: var(--bg-accent);
            padding: 3px 10px;
            border-radius: 10px;
        }
        
        .teams-container {
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        
        .team {
            flex: 1;
            text-align: center;
        }
        
        .team-name {
            font-size: 0.9em;
            font-weight: 600;
            margin-bottom: 8px;
            line-height: 1.3;
        }
        
        .score-box {
            display: flex;
            flex-direction: column;
            align-items: center;
        }
        
        .game-score {
            font-size: 2em;
            font-weight: bold;
            color: var(--green);
        }
        
        .team:last-child .game-score {
            color: var(--blue);
        }
        
        .points-score {
            font-size: 0.85em;
            color: var(--text-secondary);
            margin-top: 2px;
        }
        
        .vs-divider {
            padding: 0 10px;
            color: var(--orange);
            font-weight: bold;
            font-size: 0.9em;
        }
        
        /* Tables Grid */
        .tables-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 12px;
            margin-bottom: 15px;
        }
        
        .table-card {
            background: var(--bg-card);
            border-radius: 12px;
            padding: 12px;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
            border: 2px solid transparent;
        }
        
        .table-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }
        
        .table-card.live {
            border-color: var(--green);
            background: linear-gradient(135deg, #1e4a1e, var(--bg-card));
        }
        
        .table-card.available {
            border-color: var(--bg-accent);
            opacity: 0.6;
        }
        
        .table-card .table-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        
        .table-card .table-number {
            font-weight: bold;
            font-size: 1.1em;
        }
        
        .table-card .table-status {
            font-size: 0.7em;
            padding: 2px 6px;
            border-radius: 8px;
            background: var(--green);
            color: white;
        }
        
        .table-card.available .table-status {
            background: var(--bg-accent);
            color: var(--text-secondary);
        }
        
        .table-visual {
            background: var(--felt-green);
            border-radius: 8px;
            padding: 10px;
            margin: 8px 0;
            min-height: 60px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            border: 3px solid #5D3A1A;
        }
        
        .table-visual .match-score {
            font-size: 1.5em;
            font-weight: bold;
            color: white;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.5);
        }
        
        .table-visual .match-teams {
            font-size: 0.7em;
            color: rgba(255,255,255,0.9);
            text-align: center;
            margin-top: 4px;
        }
        
        .table-visual .match-points {
            font-size: 0.75em;
            color: rgba(255,255,255,0.7);
            margin-top: 2px;
        }
        
        .table-visual.empty {
            color: rgba(255,255,255,0.4);
            font-size: 0.8em;
        }
        
        .table-teams {
            display: flex;
            flex-direction: column;
            align-items: center;
            margin: 8px 0;
            gap: 2px;
        }
        
        .table-team {
            font-size: 0.8em;
            font-weight: 500;
            line-height: 1.2;
        }
        
        .table-team.team1 {
            color: var(--green);
        }
        
        .table-team.team2 {
            color: var(--blue);
        }
        
        .table-vs {
            font-size: 0.65em;
            color: var(--text-secondary);
        }
        
        .table-waiting {
            text-align: center;
            font-size: 0.75em;
            color: var(--text-secondary);
            margin: 8px 0;
        }
        
        .table-tap-hint {
            text-align: center;
            font-size: 0.7em;
            color: var(--text-secondary);
            opacity: 0.7;
        }
        
        .group-badge {
            display: inline-block;
            font-size: 0.65em;
            padding: 2px 5px;
            border-radius: 4px;
            margin-left: 4px;
            vertical-align: middle;
        }
        
        .group-badge.solids {
            background: rgba(0, 0, 0, 0.4);
            color: #FFD700;
        }
        
        .group-badge.stripes {
            background: rgba(255, 255, 255, 0.15);
            color: #87CEEB;
        }
        
        /* Queue Section */
        .queue-list {
            background: var(--bg-card);
            border-radius: 12px;
            overflow: hidden;
        }
        
        .queue-header {
            background: #3d3a1e;
            padding: 10px 15px;
            font-weight: bold;
            color: var(--gold);
            display: flex;
            justify-content: space-between;
        }
        
        .queue-item {
            display: flex;
            align-items: center;
            padding: 10px 15px;
            border-bottom: 1px solid var(--bg-accent);
        }
        
        .queue-item:last-child {
            border-bottom: none;
        }
        
        .queue-position {
            width: 30px;
            font-weight: bold;
            color: var(--gold);
        }
        
        .queue-teams {
            flex: 1;
            font-size: 0.9em;
        }
        
        .queue-round {
            font-size: 0.75em;
            color: var(--text-secondary);
            background: var(--bg-accent);
            padding: 2px 8px;
            border-radius: 8px;
        }
        
        .leaderboard {
            background: var(--bg-card);
            border-radius: 12px;
            overflow: hidden;
        }
        
        .leaderboard-header {
            background: var(--green-dark);
            padding: 10px 15px;
            font-weight: bold;
            display: flex;
            justify-content: space-between;
        }
        
        .leaderboard-row {
            display: flex;
            flex-direction: column;
            padding: 12px 15px;
            border-bottom: 1px solid var(--bg-accent);
        }
        
        .leaderboard-row:last-child {
            border-bottom: none;
        }
        
        .leaderboard-row.top-3 {
            background: linear-gradient(90deg, rgba(255,215,0,0.1), transparent);
        }
        
        .player-main {
            display: flex;
            align-items: center;
            margin-bottom: 8px;
        }
        
        .rank {
            width: 35px;
            font-weight: bold;
            color: var(--gold);
        }
        
        .player-avatar {
            width: 36px;
            height: 36px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 0.85em;
            color: white;
            margin-right: 10px;
            flex-shrink: 0;
            text-shadow: 1px 1px 1px rgba(0,0,0,0.3);
            object-fit: cover;
        }
        
        img.player-avatar {
            display: inline-block;
            border: 2px solid var(--bg-accent);
        }
        
        .player-avatar.emoji {
            font-size: 1.2em;
            background: linear-gradient(135deg, #3d5a80, #2d4a70);
        }
        
        .player-name {
            flex: 1;
            font-weight: 500;
        }
        
        .points-badge {
            background: var(--green-dark);
            color: var(--gold);
            padding: 4px 10px;
            border-radius: 12px;
            font-weight: bold;
            font-size: 0.9em;
        }
        
        .player-stats {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            padding-left: 81px; /* rank (35px) + avatar (36px) + margin (10px) */
            font-size: 0.8em;
        }
        
        .stat {
            display: flex;
            align-items: center;
            gap: 4px;
            background: var(--bg-accent);
            padding: 3px 8px;
            border-radius: 8px;
        }
        
        .stat-value {
            font-weight: bold;
        }
        
        .stat-value.wins {
            color: var(--green);
        }
        
        .stat-value.losses {
            color: var(--red);
        }
        
        .stat-value.golden {
            color: var(--gold);
        }
        
        .stat-label {
            color: var(--text-secondary);
        }
        
        .win-rate-bar {
            width: 50px;
            height: 4px;
            background: var(--bg-primary);
            border-radius: 2px;
            overflow: hidden;
            margin-left: 4px;
        }
        
        .win-rate-fill {
            height: 100%;
            border-radius: 2px;
            transition: width 0.3s ease;
        }
        
        .empty-state {
            text-align: center;
            padding: 30px;
            color: var(--text-secondary);
        }
        
        .empty-state .emoji {
            font-size: 2em;
            margin-bottom: 10px;
        }
        
        /* Round Progress */
        .round-progress-card {
            background: linear-gradient(135deg, #2d4a70, #1a3050);
            border-radius: 12px;
            padding: 15px 20px;
            margin-bottom: 10px;
        }
        
        .round-info {
            display: flex;
            align-items: baseline;
            gap: 8px;
            margin-bottom: 8px;
        }
        
        .round-number {
            font-size: 1.4em;
            font-weight: bold;
            color: var(--gold);
        }
        
        .round-of {
            font-size: 0.9em;
            color: var(--text-secondary);
        }
        
        .round-stats {
            display: flex;
            gap: 10px;
            font-size: 0.85em;
            margin-bottom: 10px;
        }
        
        .round-live {
            color: var(--green);
            font-weight: 500;
        }
        
        .round-sep {
            color: var(--text-secondary);
        }
        
        .round-done {
            color: var(--text-secondary);
        }
        
        .round-progress-bar {
            height: 6px;
            background: rgba(255,255,255,0.1);
            border-radius: 3px;
            overflow: hidden;
        }
        
        .round-progress-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--green), var(--gold));
            border-radius: 3px;
            transition: width 0.5s ease;
        }
        
        .league-stats {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 10px;
            margin-bottom: 15px;
        }
        
        .stat-card {
            background: var(--bg-card);
            border-radius: 10px;
            padding: 12px;
            text-align: center;
        }
        
        .stat-card.highlight {
            background: linear-gradient(135deg, var(--green-dark), #1a5f2a);
        }
        
        .stat-card .stat-icon {
            font-size: 1.2em;
            margin-bottom: 4px;
        }
        
        .stat-card .stat-number {
            font-size: 1.4em;
            font-weight: bold;
            color: var(--gold);
        }
        
        .stat-card .stat-desc {
            font-size: 0.75em;
            color: var(--text-secondary);
            margin-top: 2px;
        }
        
        .stat-card .stat-player {
            font-size: 0.85em;
            color: var(--text-primary);
            margin-top: 4px;
            font-weight: 500;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 6px;
        }
        
        .stat-card .mini-avatar {
            width: 24px;
            height: 24px;
            border-radius: 50%;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 0.7em;
            font-weight: bold;
            color: white;
            flex-shrink: 0;
            object-fit: cover;
        }
        
        .stat-card img.mini-avatar {
            display: inline-block;
            border: 1px solid var(--bg-accent);
        }
        
        .stat-card .mini-avatar.emoji {
            font-size: 0.9em;
            background: linear-gradient(135deg, #3d5a80, #2d4a70);
        }
        
        .update-time {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: var(--bg-secondary);
            padding: 12px;
            text-align: center;
            font-size: 0.8em;
            color: var(--text-secondary);
            border-top: 1px solid var(--bg-accent);
            z-index: 100;
        }
        
        .connection-status {
            display: inline-flex;
            align-items: center;
            gap: 5px;
            margin-left: 10px;
        }
        
        .status-dot {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            background: var(--green);
        }
        
        .status-dot.disconnected {
            background: var(--red);
        }
        
        /* Modal Styles */
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.85);
            z-index: 1000;
            overflow-y: auto;
            padding: 20px;
        }
        
        .modal-overlay.active {
            display: block;
        }
        
        .modal-content {
            background: var(--bg-secondary);
            border-radius: 15px;
            max-width: 500px;
            margin: 0 auto;
            padding: 20px;
            position: relative;
        }
        
        .modal-close {
            position: absolute;
            top: 10px;
            right: 15px;
            font-size: 1.5em;
            cursor: pointer;
            color: var(--text-secondary);
        }
        
        .modal-header {
            text-align: center;
            margin-bottom: 15px;
            padding-bottom: 15px;
            border-bottom: 1px solid var(--bg-accent);
        }
        
        .modal-header h2 {
            font-size: 1.3em;
            margin-bottom: 5px;
        }
        
        .modal-header .table-info {
            color: var(--text-secondary);
            font-size: 0.9em;
        }
        
        .scorecard-teams {
            display: flex;
            justify-content: space-around;
            margin-bottom: 20px;
        }
        
        .scorecard-team {
            text-align: center;
        }
        
        .scorecard-team-name {
            font-weight: 600;
            margin-bottom: 5px;
            color: var(--green);
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 4px;
        }
        
        .scorecard-team:last-child .scorecard-team-name {
            color: var(--blue);
        }
        
        .scorecard-team-name .group-badge {
            font-size: 0.7em;
            margin-left: 0;
        }
        
        .scorecard-team-score {
            font-size: 2.5em;
            font-weight: bold;
        }
        
        .scorecard-team:first-child .scorecard-team-score {
            color: var(--green);
        }
        
        .scorecard-team:last-child .scorecard-team-score {
            color: var(--blue);
        }
        
        .scorecard-game {
            background: var(--bg-card);
            border-radius: 10px;
            padding: 12px;
            margin-bottom: 10px;
        }
        
        .scorecard-game-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 10px;
            font-size: 0.85em;
            color: var(--text-secondary);
        }
        
        .scorecard-game-scores {
            display: flex;
            justify-content: space-around;
            margin-bottom: 10px;
        }
        
        .scorecard-game-score {
            font-size: 1.5em;
            font-weight: bold;
        }
        
        .balls-display {
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px solid var(--bg-accent);
        }
        
        .balls-row {
            display: flex;
            align-items: center;
            margin-bottom: 8px;
            gap: 8px;
        }
        
        .balls-label {
            font-size: 0.75em;
            color: var(--text-secondary);
            width: 60px;
        }
        
        .balls-container {
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
        }
        
        .ball {
            width: 24px;
            height: 24px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.65em;
            font-weight: bold;
            color: white;
            text-shadow: 1px 1px 1px rgba(0,0,0,0.5);
        }
        
        .ball.solid-1 { background: #FFD700; color: black; }
        .ball.solid-2 { background: #0066CC; }
        .ball.solid-3 { background: #CC0000; }
        .ball.solid-4 { background: #6B2D8B; }
        .ball.solid-5 { background: #FF6600; }
        .ball.solid-6 { background: #006633; }
        .ball.solid-7 { background: #8B0000; }
        .ball.solid-8 { background: #000000; }
        .ball.stripe-9 { background: linear-gradient(90deg, white 30%, #FFD700 30%, #FFD700 70%, white 70%); color: black; }
        .ball.stripe-10 { background: linear-gradient(90deg, white 30%, #0066CC 30%, #0066CC 70%, white 70%); color: black; }
        .ball.stripe-11 { background: linear-gradient(90deg, white 30%, #CC0000 30%, #CC0000 70%, white 70%); color: black; }
        .ball.stripe-12 { background: linear-gradient(90deg, white 30%, #6B2D8B 30%, #6B2D8B 70%, white 70%); color: black; }
        .ball.stripe-13 { background: linear-gradient(90deg, white 30%, #FF6600 30%, #FF6600 70%, white 70%); color: black; }
        .ball.stripe-14 { background: linear-gradient(90deg, white 30%, #006633 30%, #006633 70%, white 70%); color: black; }
        .ball.stripe-15 { background: linear-gradient(90deg, white 30%, #8B0000 30%, #8B0000 70%, white 70%); color: black; }
        
        .golden-badge {
            background: var(--gold);
            color: black;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 0.75em;
            font-weight: bold;
        }
        
        .winner-badge {
            color: var(--gold);
        }
        
        @media (min-width: 768px) {
            body {
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
            }
            
            .header h1 {
                font-size: 2em;
            }
            
            .match-card {
                padding: 20px;
            }
            
            .team-name {
                font-size: 1.1em;
            }
            
            .game-score {
                font-size: 2.5em;
            }
            
            .tables-grid {
                grid-template-columns: repeat(3, 1fr);
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎱 EcoPOOL Live Scores</h1>
        <div class="subtitle">WVU EcoCAR Pool League</div>
        <div class="live-indicator">
            <span class="live-dot"></span>
            <span>LIVE</span>
        </div>
    </div>
    
    <div id="content">
        <div class="empty-state">
            <div class="emoji">⏳</div>
            <div>Loading scores...</div>
        </div>
    </div>
    
    <div class="update-time">
        Last updated: <span id="update-time">--:--:-- --</span>
        <span class="connection-status">
            <span class="status-dot" id="status-dot"></span>
            <span id="status-text">Connecting...</span>
        </span>
    </div>
    
    <!-- Scorecard Modal -->
    <div class="modal-overlay" id="scorecard-modal">
        <div class="modal-content">
            <span class="modal-close" onclick="closeModal()">&times;</span>
            <div id="scorecard-content">
                <div class="empty-state">Loading...</div>
            </div>
        </div>
    </div>
    
    <script>
        let eventSource = null;
        let reconnectAttempts = 0;
        const maxReconnectAttempts = 10;
        
        const BALL_COLORS = {
            1: 'solid-1', 2: 'solid-2', 3: 'solid-3', 4: 'solid-4',
            5: 'solid-5', 6: 'solid-6', 7: 'solid-7', 8: 'solid-8',
            9: 'stripe-9', 10: 'stripe-10', 11: 'stripe-11', 12: 'stripe-12',
            13: 'stripe-13', 14: 'stripe-14', 15: 'stripe-15'
        };
        
        // Avatar colors matching the desktop app
        const AVATAR_COLORS = [
            ["#FF6B6B", "#C62828"], ["#4ECDC4", "#00897B"], ["#45B7D1", "#0277BD"],
            ["#96CEB4", "#388E3C"], ["#FFEAA7", "#F9A825"], ["#DDA0DD", "#7B1FA2"],
            ["#F8B500", "#E65100"], ["#85C1E9", "#1565C0"], ["#BB8FCE", "#6A1B9A"],
            ["#98D8C8", "#00695C"], ["#F7DC6F", "#FBC02D"], ["#FF69B4", "#C2185B"]
        ];
        
        function getAvatarColorForName(name) {
            // Simple hash to get consistent color for a name
            let hash = 0;
            for (let i = 0; i < name.length; i++) {
                hash = name.charCodeAt(i) + ((hash << 5) - hash);
            }
            return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
        }
        
        function getInitials(name) {
            if (!name) return '?';
            const parts = name.trim().split(' ');
            if (parts.length >= 2) {
                return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
            } else if (parts[0].length >= 2) {
                return parts[0].substring(0, 2).toUpperCase();
            }
            return parts[0][0].toUpperCase();
        }
        
        function getProfilePictureUrl(profilePicture) {
            // Extract filename from a file path and return the API URL
            if (!profilePicture) return null;
            // Handle Windows and Unix paths
            const parts = profilePicture.replace(/\\\\/g, '/').split('/');
            const filename = parts[parts.length - 1];
            return `/api/pfp/${encodeURIComponent(filename)}`;
        }
        
        function isFilePath(profilePicture) {
            // Check if this is an actual file path (not emoji: or color: prefix)
            if (!profilePicture) return false;
            if (profilePicture.startsWith('emoji:')) return false;
            if (profilePicture.startsWith('color:')) return false;
            // If it contains path separators or file extensions, it's likely a file
            return profilePicture.includes('/') || profilePicture.includes('\\\\') || 
                   profilePicture.match(/\\.(jpg|jpeg|png|gif)$/i);
        }
        
        function createAvatar(name, profilePicture) {
            // Check if it's an actual image file
            if (isFilePath(profilePicture)) {
                const url = getProfilePictureUrl(profilePicture);
                return `<img class="player-avatar" src="${url}" alt="${escapeHtml(name)}" onerror="this.outerHTML=createAvatarFallback('${escapeHtml(name)}', false)">`;
            }
            
            // Check if it's an emoji avatar
            if (profilePicture && profilePicture.startsWith('emoji:')) {
                const emoji = profilePicture.substring(6);
                return `<div class="player-avatar emoji">${emoji}</div>`;
            }
            
            // Generate initials-based avatar
            return createAvatarFallback(name, false);
        }
        
        function createAvatarFallback(name, isMini) {
            const colors = getAvatarColorForName(name);
            const initials = getInitials(name);
            const className = isMini ? 'mini-avatar' : 'player-avatar';
            return `<div class="${className}" style="background: linear-gradient(135deg, ${colors[0]}, ${colors[1]})">${initials}</div>`;
        }
        
        function createMiniAvatar(name, profilePicture) {
            // Check if it's an actual image file
            if (isFilePath(profilePicture)) {
                const url = getProfilePictureUrl(profilePicture);
                return `<img class="mini-avatar" src="${url}" alt="${escapeHtml(name)}" onerror="this.outerHTML=createAvatarFallback('${escapeHtml(name)}', true)">`;
            }
            
            // Smaller version for stat cards
            if (profilePicture && profilePicture.startsWith('emoji:')) {
                const emoji = profilePicture.substring(6);
                return `<div class="mini-avatar emoji">${emoji}</div>`;
            }
            
            return createAvatarFallback(name, true);
        }
        
        function connectSSE() {
            if (eventSource) {
                eventSource.close();
            }
            
            eventSource = new EventSource('/api/stream');
            
            eventSource.onopen = function() {
                console.log('Connected to live updates');
                reconnectAttempts = 0;
                updateConnectionStatus(true);
            };
            
            eventSource.onmessage = function(event) {
                const data = JSON.parse(event.data);
                updateUI(data);
            };
            
            eventSource.onerror = function() {
                console.log('SSE connection error');
                updateConnectionStatus(false);
                
                eventSource.close();
                
                if (reconnectAttempts < maxReconnectAttempts) {
                    reconnectAttempts++;
                    setTimeout(connectSSE, 3000);
                }
            };
        }
        
        function updateConnectionStatus(connected) {
            const dot = document.getElementById('status-dot');
            const text = document.getElementById('status-text');
            
            if (connected) {
                dot.classList.remove('disconnected');
                text.textContent = 'Connected';
            } else {
                dot.classList.add('disconnected');
                text.textContent = 'Reconnecting...';
            }
        }
        
        function updateUI(data) {
            document.getElementById('update-time').textContent = data.timestamp;
            
            let html = '';
            
            // Round Progress Section (if rounds exist)
            if (data.round_progress && data.round_progress.total_rounds > 0) {
                const rp = data.round_progress;
                const progressPercent = rp.total > 0 ? Math.round((rp.completed / rp.total) * 100) : 0;
                html += `
                    <div class="section">
                        <div class="round-progress-card">
                            <div class="round-info">
                                <span class="round-number">Round ${rp.current_round}</span>
                                <span class="round-of">of ${rp.total_rounds}</span>
                            </div>
                            <div class="round-stats">
                                <span class="round-live">${rp.live} live</span>
                                <span class="round-sep">•</span>
                                <span class="round-done">${rp.completed}/${rp.total} done</span>
                            </div>
                            <div class="round-progress-bar">
                                <div class="round-progress-fill" style="width: ${progressPercent}%"></div>
                            </div>
                        </div>
                    </div>
                `;
            }
            
            // Tables Section (Visual Overview) - Main focus
            if (data.tables && data.tables.length > 0) {
                const liveTables = data.tables.filter(t => t.status === 'live').length;
                const availableTables = data.tables.length - liveTables;
                html += `
                    <div class="section">
                        <div class="section-title">🎱 Pool Hall <span style="font-weight:normal;font-size:0.85em;color:var(--text-secondary)">(${liveTables} active, ${availableTables} open)</span></div>
                        <div class="tables-grid">
                            ${data.tables.map(t => createTableCard(t)).join('')}
                        </div>
                    </div>
                `;
            }
            
            // Queue Section - Up Next
            if (data.queue && data.queue.length > 0) {
                html += `
                    <div class="section">
                        <div class="section-title">⏳ Up Next</div>
                        <div class="queue-list">
                            <div class="queue-header">
                                <span>Queue</span>
                                <span>${data.queue.length} waiting</span>
                            </div>
                            ${data.queue.slice(0, 5).map(q => createQueueItem(q)).join('')}
                            ${data.queue.length > 5 ? `<div class="queue-item" style="justify-content:center;color:var(--text-secondary);">+ ${data.queue.length - 5} more</div>` : ''}
                        </div>
                    </div>
                `;
            }
            
            // Completed matches section
            if (data.completed_matches && data.completed_matches.length > 0) {
                html += `
                    <div class="section">
                        <div class="section-title">✅ Recent Results</div>
                        ${data.completed_matches.map(m => createMatchCard(m, true)).join('')}
                    </div>
                `;
            }
            
            // League Stats section
            if (data.league_stats && data.league_stats.total_games > 0) {
                const ls = data.league_stats;
                html += `
                    <div class="section">
                        <div class="section-title">📈 League Stats</div>
                        <div class="league-stats">
                            <div class="stat-card highlight">
                                <div class="stat-icon">🎱</div>
                                <div class="stat-number">${ls.total_games}</div>
                                <div class="stat-desc">Games Played</div>
                            </div>
                            <div class="stat-card">
                                <div class="stat-icon">⭐</div>
                                <div class="stat-number">${ls.total_golden}</div>
                                <div class="stat-desc">Golden Breaks</div>
                            </div>
                            ${ls.top_scorer ? `
                            <div class="stat-card">
                                <div class="stat-icon">👑</div>
                                <div class="stat-number">${ls.top_scorer_pts}</div>
                                <div class="stat-desc">Top Scorer</div>
                                <div class="stat-player">${createMiniAvatar(ls.top_scorer, ls.top_scorer_pfp)} ${escapeHtml(ls.top_scorer)}</div>
                            </div>
                            ` : ''}
                            ${ls.best_win_rate ? `
                            <div class="stat-card">
                                <div class="stat-icon">🎯</div>
                                <div class="stat-number">${ls.best_win_rate_pct}%</div>
                                <div class="stat-desc">Best Win Rate</div>
                                <div class="stat-player">${createMiniAvatar(ls.best_win_rate, ls.best_win_rate_pfp)} ${escapeHtml(ls.best_win_rate)}</div>
                            </div>
                            ` : ''}
                        </div>
                    </div>
                `;
            }
            
            // Leaderboard section
            if (data.leaderboard && data.leaderboard.length > 0) {
                html += `
                    <div class="section">
                        <div class="section-title">🏆 Leaderboard</div>
                        <div class="leaderboard">
                            ${data.leaderboard.map((p, i) => createLeaderboardRow(p, i)).join('')}
                        </div>
                    </div>
                `;
            }
            
            // Empty state
            if (!data.tables?.some(t => t.status === 'live') && !data.queue?.length && !data.completed_matches?.length) {
                html = `
                    <div class="empty-state">
                        <div class="emoji">🎱</div>
                        <div>No matches yet tonight</div>
                        <div style="margin-top: 10px; font-size: 0.9em;">
                            Matches will appear here when they start
                        </div>
                    </div>
                `;
            }
            
            document.getElementById('content').innerHTML = html;
        }
        
        function createTableCard(table) {
            const statusClass = table.status === 'live' ? 'live' : 'available';
            const statusText = table.status === 'live' ? 'LIVE' : 'Open';
            const clickHandler = table.match_id ? `onclick="openScorecard(${table.match_id})"` : '';
            
            let visualContent = '';
            let teamsContent = '';
            
            if (table.status === 'live') {
                // Show large score on the table visual
                visualContent = `
                    <div class="match-score">${table.team1_games} - ${table.team2_games}</div>
                    <div class="match-points">${table.team1_points} - ${table.team2_points} pts</div>
                `;
                
                // Team names are already first names from server
                const team1Display = escapeHtml(table.team1);
                const team2Display = escapeHtml(table.team2);
                
                // Determine group labels (solids/stripes)
                let team1GroupLabel = '';
                let team2GroupLabel = '';
                if (table.team1_group === 'solids') {
                    team1GroupLabel = '<span class="group-badge solids">⚫ Solids</span>';
                    team2GroupLabel = '<span class="group-badge stripes">⬜ Stripes</span>';
                } else if (table.team1_group === 'stripes') {
                    team1GroupLabel = '<span class="group-badge stripes">⬜ Stripes</span>';
                    team2GroupLabel = '<span class="group-badge solids">⚫ Solids</span>';
                }
                
                teamsContent = `
                    <div class="table-teams">
                        <div class="table-team team1">${team1Display} ${team1GroupLabel}</div>
                        <div class="table-vs">vs</div>
                        <div class="table-team team2">${team2Display} ${team2GroupLabel}</div>
                    </div>
                `;
            } else {
                visualContent = `<div class="empty">Ready</div>`;
                teamsContent = `<div class="table-waiting">Waiting for game</div>`;
            }
            
            return `
                <div class="table-card ${statusClass}" ${clickHandler}>
                    <div class="table-header">
                        <span class="table-number">Table ${table.table_number}</span>
                        <span class="table-status">${statusText}</span>
                    </div>
                    <div class="table-visual ${table.status === 'available' ? 'empty' : ''}">
                        ${visualContent}
                    </div>
                    ${teamsContent}
                    ${table.status === 'live' ? `<div class="table-tap-hint">Tap for scorecard</div>` : ''}
                </div>
            `;
        }
        
        function createQueueItem(item) {
            return `
                <div class="queue-item">
                    <span class="queue-position">#${item.position}</span>
                    <span class="queue-teams">${escapeHtml(item.team1)} vs ${escapeHtml(item.team2)}</span>
                    ${item.round > 1 ? `<span class="queue-round">R${item.round}</span>` : ''}
                </div>
            `;
        }
        
        function createMatchCard(match, completed) {
            const finals = match.is_finals ? 'finals' : '';
            const completedClass = completed ? 'completed' : '';
            const clickHandler = `onclick="openScorecard(${match.id})"`;
            
            return `
                <div class="match-card ${finals} ${completedClass}" ${clickHandler} style="cursor:pointer">
                    <div class="match-header">
                        <span>${match.is_finals ? '🏆 Finals' : 'Best of ' + match.best_of}</span>
                        <span class="table-badge">Table ${match.table}</span>
                    </div>
                    <div class="teams-container">
                        <div class="team">
                            <div class="team-name">${escapeHtml(match.team1)}</div>
                            <div class="score-box">
                                <div class="game-score">${match.team1_games}</div>
                                <div class="points-score">${match.team1_points} pts</div>
                            </div>
                        </div>
                        <div class="vs-divider">VS</div>
                        <div class="team">
                            <div class="team-name">${escapeHtml(match.team2)}</div>
                            <div class="score-box">
                                <div class="game-score">${match.team2_games}</div>
                                <div class="points-score">${match.team2_points} pts</div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }
        
        function createLeaderboardRow(player, index) {
            const isTop3 = index < 3 ? 'top-3' : '';
            const rankDisplay = index === 0 ? '🥇' : index === 1 ? '🥈' : index === 2 ? '🥉' : (index + 1);
            const winRateColor = player.win_rate >= 50 ? 'var(--green)' : 'var(--red)';
            const goldenBreaks = player.golden_breaks || 0;
            const avatar = createAvatar(player.name, player.profile_picture);
            
            return `
                <div class="leaderboard-row ${isTop3}">
                    <div class="player-main">
                        <div class="rank">${rankDisplay}</div>
                        ${avatar}
                        <div class="player-name">${escapeHtml(player.name)}</div>
                        <div class="points-badge">${player.points} pts</div>
                    </div>
                    <div class="player-stats">
                        <div class="stat">
                            <span class="stat-value wins">${player.wins}W</span>
                            <span class="stat-label">-</span>
                            <span class="stat-value losses">${player.losses || 0}L</span>
                        </div>
                        <div class="stat">
                            <span class="stat-label">Games:</span>
                            <span class="stat-value">${player.games}</span>
                        </div>
                        <div class="stat">
                            <span class="stat-label">Win%:</span>
                            <span class="stat-value" style="color: ${winRateColor}">${player.win_rate}%</span>
                            <div class="win-rate-bar">
                                <div class="win-rate-fill" style="width: ${player.win_rate}%; background: ${winRateColor}"></div>
                            </div>
                        </div>
                        <div class="stat">
                            <span class="stat-label">Avg:</span>
                            <span class="stat-value" style="color: var(--blue)">${player.avg_points || 0}</span>
                        </div>
                        ${goldenBreaks > 0 ? `
                        <div class="stat">
                            <span class="stat-value golden">⭐ ${goldenBreaks}</span>
                            <span class="stat-label">golden</span>
                        </div>
                        ` : ''}
                    </div>
                </div>
            `;
        }
        
        function openScorecard(matchId) {
            const modal = document.getElementById('scorecard-modal');
            const content = document.getElementById('scorecard-content');
            
            content.innerHTML = '<div class="empty-state">Loading...</div>';
            modal.classList.add('active');
            
            fetch(`/api/match/${matchId}`)
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        content.innerHTML = `<div class="empty-state">${data.error}</div>`;
                        return;
                    }
                    content.innerHTML = renderScorecard(data);
                })
                .catch(err => {
                    content.innerHTML = `<div class="empty-state">Failed to load</div>`;
                });
        }
        
        function renderScorecard(match) {
            const statusText = match.is_complete ? 'Complete' : 'In Progress';
            
            // Determine group labels for team headers
            let team1GroupBadge = '';
            let team2GroupBadge = '';
            if (match.team1_group === 'solids') {
                team1GroupBadge = '<span class="group-badge solids">⚫ Solids</span>';
                team2GroupBadge = '<span class="group-badge stripes">⬜ Stripes</span>';
            } else if (match.team1_group === 'stripes') {
                team1GroupBadge = '<span class="group-badge stripes">⬜ Stripes</span>';
                team2GroupBadge = '<span class="group-badge solids">⚫ Solids</span>';
            }
            
            let gamesHtml = '';
            if (match.games && match.games.length > 0) {
                gamesHtml = match.games.map(g => {
                    const winnerIcon = g.winner_team === 1 ? '<span class="winner-badge">🏆</span>' : '';
                    const winnerIcon2 = g.winner_team === 2 ? '<span class="winner-badge">🏆</span>' : '';
                    const goldenBadge = g.golden_break ? '<span class="golden-badge">⭐ Golden Break</span>' : '';
                    
                    // Render balls pocketed
                    let ballsHtml = '';
                    if (g.balls_pocketed && Object.keys(g.balls_pocketed).length > 0) {
                        const allBalls = Object.keys(g.balls_pocketed).map(Number).sort((a,b) => a-b);
                        
                        ballsHtml = `
                            <div class="balls-display">
                                <div class="balls-row">
                                    <span class="balls-label">Balls Out:</span>
                                    <div class="balls-container">
                                        ${allBalls.map(b => `<div class="ball ${BALL_COLORS[b]}">${b}</div>`).join('')}
                                    </div>
                                </div>
                            </div>
                        `;
                    }
                    
                    return `
                        <div class="scorecard-game">
                            <div class="scorecard-game-header">
                                <span>Game ${g.game_number}</span>
                                <span>${g.team1_group ? (g.team1_group === 'solids' ? 'T1: Solids' : 'T1: Stripes') : ''}</span>
                                ${goldenBadge}
                            </div>
                            <div class="scorecard-game-scores">
                                <span class="scorecard-game-score" style="color:var(--green)">${g.team1_score} ${winnerIcon}</span>
                                <span style="color:var(--text-secondary)">-</span>
                                <span class="scorecard-game-score" style="color:var(--blue)">${winnerIcon2} ${g.team2_score}</span>
                            </div>
                            ${ballsHtml}
                        </div>
                    `;
                }).join('');
            } else {
                gamesHtml = '<div class="empty-state" style="padding:15px">No games recorded yet</div>';
            }
            
            return `
                <div class="modal-header">
                    <h2>${match.is_finals ? '🏆 Finals' : 'Match'}</h2>
                    <div class="table-info">Table ${match.table} • ${statusText}</div>
                </div>
                
                <div class="scorecard-teams">
                    <div class="scorecard-team">
                        <div class="scorecard-team-name">${escapeHtml(match.team1)} ${team1GroupBadge}</div>
                        <div class="scorecard-team-score">${match.team1_games}</div>
                    </div>
                    <div style="color:var(--text-secondary);padding:20px">vs</div>
                    <div class="scorecard-team">
                        <div class="scorecard-team-name">${escapeHtml(match.team2)} ${team2GroupBadge}</div>
                        <div class="scorecard-team-score">${match.team2_games}</div>
                    </div>
                </div>
                
                <div style="margin-bottom:10px;color:var(--text-secondary);font-size:0.85em;text-align:center">
                    Best of ${match.best_of}
                </div>
                
                ${gamesHtml}
            `;
        }
        
        function closeModal() {
            document.getElementById('scorecard-modal').classList.remove('active');
        }
        
        // Close modal on background click
        document.getElementById('scorecard-modal').addEventListener('click', function(e) {
            if (e.target === this) {
                closeModal();
            }
        });
        
        function escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        // Start connection when page loads
        connectSSE();
        
        // Reconnect on visibility change (when user returns to tab)
        document.addEventListener('visibilitychange', function() {
            if (document.visibilityState === 'visible') {
                connectSSE();
            }
        });
        
        // Fallback: fetch data periodically if SSE fails
        setInterval(function() {
            if (!eventSource || eventSource.readyState === EventSource.CLOSED) {
                fetch('/api/scores')
                    .then(r => r.json())
                    .then(updateUI)
                    .catch(console.error);
            }
        }, 5000);
    </script>
</body>
</html>
'''
    
    def get_local_ip(self) -> str:
        """Get the local IP address for the machine."""
        try:
            # Create a socket to determine the local IP
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
    
    def notify_update(self):
        """Notify connected clients of a data update."""
        self._update_event.set()
    
    def start(self) -> tuple[bool, str]:
        """Start the web server in a background thread.
        
        Returns:
            Tuple of (success, message/URL)
        """
        if self.running:
            return False, "Server is already running"
        
        try:
            # Find an available port
            self.port = self._find_available_port(self.port)
            
            self.running = True
            self.server_thread = threading.Thread(
                target=self._run_server,
                daemon=True
            )
            self.server_thread.start()
            
            # Wait a moment for server to start
            time.sleep(0.5)
            
            local_ip = self.get_local_ip()
            url = f"http://{local_ip}:{self.port}"
            
            return True, url
            
        except Exception as e:
            self.running = False
            return False, str(e)
    
    def _find_available_port(self, start_port: int) -> int:
        """Find an available port starting from start_port."""
        port = start_port
        max_attempts = 10
        
        for _ in range(max_attempts):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('', port))
                    return port
            except OSError:
                port += 1
        
        return start_port  # Fall back to original
    
    def _run_server(self):
        """Run the Flask server (called in background thread)."""
        try:
            self.app.run(
                host='0.0.0.0',
                port=self.port,
                threaded=True,
                use_reloader=False
            )
        except Exception as e:
            print(f"Web server error: {e}")
            self.running = False
    
    def stop(self):
        """Stop the web server."""
        self.running = False
        self._shutdown_event.set()  # Signal shutdown to SSE streams
        self._update_event.set()  # Wake up any waiting threads
        
        # Remove from active servers list
        if self in _active_servers:
            _active_servers.remove(self)
        
        # Close thread-local database connection if it exists
        if hasattr(self._local, 'db'):
            try:
                self._local.db.close()
            except Exception:
                pass
    
    def is_running(self) -> bool:
        """Check if the server is running."""
        return self.running


def _cleanup_all_servers():
    """Cleanup function called on exit to stop all active servers."""
    for server in _active_servers[:]:  # Copy list to avoid modification during iteration
        try:
            server.stop()
        except Exception:
            pass


# Register cleanup for normal exit
atexit.register(_cleanup_all_servers)


# Handle signals for abnormal termination (Ctrl+C, etc.)
def _signal_handler(signum, frame):
    """Handle termination signals."""
    _cleanup_all_servers()
    sys.exit(0)


# Register signal handlers (only on main thread)
try:
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
except (ValueError, OSError):
    # Signal handling not available in this context (e.g., not main thread)
    pass
