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
import io
import atexit
import signal
import sys
import secrets
import hmac
import hashlib
from datetime import datetime
from flask import Flask, Response, render_template, jsonify, send_file, abort, request
from werkzeug.serving import make_server
import socket as _socket
import logging

# Suppress Flask's default logging to keep console clean
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# Try to import ngrok helper for public tunneling
try:
    import ngrok_helper
    NGROK_AVAILABLE = True
except ImportError:
    NGROK_AVAILABLE = False


# ============ Security Helper Functions ============

def _hash_credential(credential: str, salt: bytes = None) -> str:
    """Hash a password or PIN using PBKDF2-HMAC-SHA256.

    Args:
        credential: The plaintext password/PIN to hash
        salt: Optional salt bytes. If None, generates a new random salt.

    Returns:
        A string in format "salt_hex:hash_hex" for storage
    """
    if salt is None:
        salt = os.urandom(32)

    # Use PBKDF2 with 100,000 iterations (OWASP recommended minimum)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        credential.encode('utf-8'),
        salt,
        iterations=100000
    )

    return f"{salt.hex()}:{key.hex()}"


def _verify_credential(credential: str, stored_hash: str) -> bool:
    """Verify a password/PIN against its stored hash using constant-time comparison.

    Args:
        credential: The plaintext credential to verify
        stored_hash: The stored hash in "salt_hex:hash_hex" format

    Returns:
        True if the credential matches, False otherwise
    """
    if not stored_hash or ':' not in stored_hash:
        # Legacy plaintext password - migrate on next set
        # Use constant-time comparison even for plaintext
        return hmac.compare_digest(credential, stored_hash) if stored_hash else False

    try:
        salt_hex, hash_hex = stored_hash.split(':', 1)
        salt = bytes.fromhex(salt_hex)
        expected_hash = bytes.fromhex(hash_hex)

        # Recompute the hash with the same salt
        actual_hash = hashlib.pbkdf2_hmac(
            'sha256',
            credential.encode('utf-8'),
            salt,
            iterations=100000
        )

        # Constant-time comparison to prevent timing attacks
        return hmac.compare_digest(actual_hash, expected_hash)
    except (ValueError, TypeError):
        # Invalid hash format - treat as legacy plaintext
        return hmac.compare_digest(credential, stored_hash)


# Global reference for cleanup
_active_servers = []


class LiveScoreServer:
    """Web server for displaying live league night scores."""
    
    def __init__(self, db_manager, port=5000):
        self.db = db_manager
        self.db_path = db_manager.db_path  # Store path for creating thread-local connections
        self.port = port
        # Set template and static folders relative to this file
        template_dir = os.path.join(os.path.dirname(__file__), 'templates')
        static_dir = os.path.join(os.path.dirname(__file__), 'static')
        self.app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
        
        # Disable caching for development - ensures fresh CSS/JS on each request
        @self.app.after_request
        def add_no_cache_headers(response):
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response
        
        self.server_thread = None
        self.running = False
        self._werkzeug_server = None
        self._last_data_hash = None
        self._update_event = threading.Event()
        self._shutdown_event = threading.Event()

        # Version counter for SSE updates - incremented when data changes
        # Each SSE client tracks the last version they saw
        self._data_version = 0
        self._data_version_lock = threading.Lock()
        
        # Thread-local storage for database connections
        self._local = threading.local()

        # Manager session tracking - stores session tokens with timestamps
        # Session tokens are generated on successful password verification
        # Format: {token: creation_timestamp}
        self._manager_sessions = {}
        self._session_lock = threading.Lock()
        self._session_max_age = 24 * 60 * 60  # 24 hours in seconds
        self._session_cleanup_interval = 60 * 60  # Cleanup every hour
        self._last_session_cleanup = time.time()

        # Initialize reaction manager with import guard
        try:
            from spectator_reactions import get_reaction_manager
            self.reaction_manager = get_reaction_manager()
            # Register callback to notify clients of new reactions
            self.reaction_manager.register_callback(self._on_reaction)
        except ImportError:
            # Fallback if spectator_reactions module is not available
            self.reaction_manager = None
            print("Warning: spectator_reactions module not found. Reactions disabled.")

        # Register for global cleanup
        _active_servers.append(self)
        
        # Setup routes
        self._setup_routes()
    
    def _on_reaction(self, reaction):
        """Callback when a new reaction is added - triggers update event."""
        self.notify_update()

    def _get_team_name(self, match: dict, team_num: int) -> str:
        """Get a display name for a team in a match.

        Args:
            match: Match dict with player IDs
            team_num: 1 or 2

        Returns:
            Team display name (e.g., "Player1 & Player2" or "Player1")
        """
        try:
            db = self._get_thread_db()
            if team_num == 1:
                p1_id = match.get('team1_player1_id')
                p2_id = match.get('team1_player2_id')
            else:
                p1_id = match.get('team2_player1_id')
                p2_id = match.get('team2_player2_id')

            p1 = db.get_player(p1_id) if p1_id else None
            p2 = db.get_player(p2_id) if p2_id else None

            if p1 and p2:
                return f"{p1.name} & {p2.name}"
            elif p1:
                return p1.name
            return f"Team {team_num}"
        except Exception:
            return f"Team {team_num}"

    def _get_thread_db(self):
        """Get a thread-local database connection for manager mode operations.
        
        Ensures the database is properly initialized and accessible.
        """
        # Ensure db_path is valid
        if not hasattr(self, 'db_path') or not self.db_path:
            raise ValueError("Database path not set. Cannot access database.")
        
        if not hasattr(self._local, 'db') or self._local.db is None:
            from database import DatabaseManager
            try:
                # Create a new database manager instance for this thread
                self._local.db = DatabaseManager(self.db_path)
                # Ensure database is initialized by attempting a simple operation
                # This will create tables if they don't exist
                _ = self._local.db.get_setting('test', '')
            except Exception as e:
                # Log the error but don't fail silently
                import traceback
                print(f"Error initializing database for manager mode: {e}")
                print(f"Database path: {self.db_path}")
                traceback.print_exc()
                # Try to reinitialize
                try:
                    self._local.db = DatabaseManager(self.db_path)
                except Exception as e2:
                    print(f"Failed to reinitialize database: {e2}")
                    raise
        return self._local.db

    def _validate_manager_session(self, session_token: str) -> bool:
        """Validate a manager session token.

        Args:
            session_token: The session token to validate

        Returns:
            True if the session is valid, False otherwise
        """
        if not session_token:
            return False

        current_time = time.time()

        with self._session_lock:
            # Periodic cleanup of expired sessions
            if current_time - self._last_session_cleanup > self._session_cleanup_interval:
                self._cleanup_expired_sessions_locked(current_time)

            # Check if session exists and is not expired
            if session_token not in self._manager_sessions:
                return False

            session_created = self._manager_sessions[session_token]
            if current_time - session_created > self._session_max_age:
                # Session expired - remove it
                del self._manager_sessions[session_token]
                return False

            return True

    def _cleanup_expired_sessions_locked(self, current_time: float):
        """Remove expired sessions. Must be called with _session_lock held."""
        expired_tokens = [
            token for token, created in self._manager_sessions.items()
            if current_time - created > self._session_max_age
        ]
        for token in expired_tokens:
            del self._manager_sessions[token]
        self._last_session_cleanup = current_time
        if expired_tokens:
            print(f"Cleaned up {len(expired_tokens)} expired manager sessions")

    def _require_payment_auth(self) -> tuple:
        """Check if request has valid payment portal authentication.

        Returns:
            Tuple of (is_authenticated, error_response).
            If authenticated, error_response is None.
            If not authenticated, error_response is a tuple of (response_dict, status_code).
        """
        # Check for PIN in request headers or query params
        pin = request.headers.get('X-Payment-PIN') or request.args.get('pin')

        if not pin:
            return False, ({'error': 'Authentication required', 'auth_required': True}, 401)

        db = self._get_thread_db()
        stored_pin = db.get_setting('payment_portal_pin', '')

        if not stored_pin:
            return False, ({'error': 'Payment portal not configured'}, 403)

        if not _verify_credential(pin, stored_pin):
            return False, ({'error': 'Invalid PIN', 'auth_required': True}, 401)

        return True, None

    def _setup_routes(self):
        """Setup Flask routes."""
        
        @self.app.route('/')
        def index():
            return render_template('index.html')

        @self.app.route('/favicon.ico')
        def favicon():
            """Serve the favicon."""
            icon_path = os.path.join(os.path.dirname(__file__), "icon.ico")
            if os.path.exists(icon_path):
                return send_file(icon_path, mimetype='image/x-icon')
            # Fallback to logo.png if no .ico file
            logo_path = os.path.join(os.path.dirname(__file__), "static", "images", "logo.png")
            if os.path.exists(logo_path):
                return send_file(logo_path, mimetype='image/png')
            abort(404)

        @self.app.route('/sw.js')
        def service_worker():
            """Serve service worker from static folder (required at root for scope)."""
            sw_path = os.path.join(os.path.dirname(__file__), "static", "sw.js")
            if os.path.exists(sw_path):
                response = send_file(sw_path, mimetype='application/javascript')
                # Service workers need to be served fresh
                response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                response.headers['Service-Worker-Allowed'] = '/'
                return response
            abort(404)

        @self.app.route('/manifest.json')
        def manifest():
            """Serve PWA manifest from static folder."""
            manifest_path = os.path.join(os.path.dirname(__file__), "static", "manifest.json")
            if os.path.exists(manifest_path):
                return send_file(manifest_path, mimetype='application/manifest+json')
            abort(404)

        @self.app.route('/api/match/<int:match_id>/timeline')
        def get_match_timeline(match_id):
            """Get timeline events for a match."""
            try:
                db = self._get_thread_db()
                if db is None:
                    return jsonify({'error': 'Database connection failed'}), 500

                game_number = request.args.get('game', type=int)
                events = db.get_match_timeline(match_id, game_number)

                return jsonify({
                    'match_id': match_id,
                    'events': events
                })
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/stream')
        def stream_overlay():
            """Streaming overlay view for OBS/Streamlabs.

            Query parameters:
                mode: 'all', 'tables', 'leaderboard', 'queue' (default: 'all')
                transparent: 'true' for transparent background (default: false)
                header: 'true'/'false' to show/hide header (default: true)
                players: max leaderboard entries (default: 10)
                tables: max tables to show (default: 8)
                refresh: refresh rate in ms (default: 3000)
                compact: 'true' for compact layout (default: false)
                bg: background color hex without # (default: none)
                fontsize: base font size in px (default: 16)
            """
            # Parse query parameters
            mode = request.args.get('mode', 'all')
            if mode not in ('all', 'tables', 'leaderboard', 'queue'):
                mode = 'all'

            transparent = request.args.get('transparent', 'false').lower() == 'true'
            show_header = request.args.get('header', 'true').lower() != 'false'
            compact = request.args.get('compact', 'false').lower() == 'true'

            try:
                max_players = int(request.args.get('players', '10'))
                max_players = max(1, min(50, max_players))
            except ValueError:
                max_players = 10

            try:
                max_tables = int(request.args.get('tables', '8'))
                max_tables = max(1, min(20, max_tables))
            except ValueError:
                max_tables = 8

            try:
                refresh_rate = int(request.args.get('refresh', '3000'))
                refresh_rate = max(1000, min(30000, refresh_rate))
            except ValueError:
                refresh_rate = 3000

            # Background color (hex without #)
            bg_color = request.args.get('bg', '')
            if bg_color:
                # Validate it's a valid hex color
                if len(bg_color) in (3, 6) and all(c in '0123456789abcdefABCDEF' for c in bg_color):
                    bg_color = f'#{bg_color}'
                else:
                    bg_color = ''

            # Font size
            try:
                font_size = int(request.args.get('fontsize', '16'))
                font_size = max(8, min(32, font_size))
            except ValueError:
                font_size = 16

            return render_template(
                'stream.html',
                mode=mode,
                transparent=transparent,
                show_header=show_header,
                compact=compact,
                max_players=max_players,
                max_tables=max_tables,
                refresh_rate=refresh_rate,
                bg_color=bg_color,
                font_size=font_size
            )

        # Alias for stream overlay
        @self.app.route('/broadcast')
        def broadcast_overlay():
            """Alias for /stream - streaming overlay view."""
            return stream_overlay()

        @self.app.route('/api/scores')
        def get_scores():
            """API endpoint for current scores."""
            return jsonify(self._get_scores_data())

        @self.app.route('/api/pairs')
        def get_pairs():
            """API endpoint for tonight's pairs with AI names."""
            try:
                db = self._get_thread_db()
                league_night = db.get_current_league_night()
                if not league_night:
                    return jsonify({'pairs': []})
                pairs = db.get_pairs_for_night(league_night['id'])
                result = [
                    {
                        'id': p['id'],
                        'player1_name': p.get('player1_name', ''),
                        'player2_name': p.get('player2_name', ''),
                        'pair_name': p.get('pair_name', ''),
                    }
                    for p in pairs
                ]
                return jsonify({'pairs': result})
            except Exception as e:
                return jsonify({'pairs': [], 'error': str(e)})

        @self.app.route('/api/match/<int:match_id>')
        def get_match_details(match_id):
            """API endpoint for detailed match/scorecard data."""
            return jsonify(self._get_match_details(match_id))
        
        @self.app.route('/api/pfp/<path:filename>')
        def get_profile_picture(filename):
            """Serve profile picture images."""
            # Allowed image extensions for security
            ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}

            try:
                # Validate filename has allowed extension
                _, ext = os.path.splitext(filename.lower())
                if ext not in ALLOWED_EXTENSIONS:
                    abort(403)  # Forbidden - invalid file type

                # Look for the file in the profile_pictures directory
                pictures_dir = os.path.join(os.path.dirname(__file__), "profile_pictures")

                # Security check - use realpath to resolve symlinks and prevent traversal
                filepath = os.path.realpath(os.path.join(pictures_dir, filename))
                pictures_dir = os.path.realpath(pictures_dir)

                # Ensure file is within pictures directory (handles symlinks and ../)
                if not filepath.startswith(pictures_dir + os.sep):
                    abort(403)

                if os.path.exists(filepath) and os.path.isfile(filepath):
                    return send_file(filepath)
                else:
                    abort(404)
            except (OSError, IOError):
                abort(404)

        @self.app.route('/api/stream')
        def stream():
            """Server-Sent Events endpoint for live updates.

            Uses a version counter to track updates. Each client maintains
            its own last-seen version to avoid race conditions when multiple
            clients are connected simultaneously.
            """
            def generate():
                last_seen_version = -1  # Track this client's last seen version

                while self.running and not self._shutdown_event.is_set():
                    try:
                        # Check if there's new data (version changed)
                        with self._data_version_lock:
                            current_version = self._data_version

                        # Always send on first iteration or when version changes
                        if current_version != last_seen_version:
                            data = self._get_scores_data()
                            yield f"data: {json.dumps(data)}\n\n"
                            last_seen_version = current_version
                    except Exception as e:
                        # Send error state but keep connection alive
                        error_data = {
                            'timestamp': datetime.now().strftime('%I:%M:%S %p'),
                            'error': str(e),
                            'live_matches': [],
                            'completed_matches': [],
                            'queue': [],
                            'tables': [],
                            'leaderboard': [],
                            'league_stats': {},
                            'round_progress': None,
                            'reactions': [],
                            'total_live': 0,
                            'total_completed': 0,
                            'total_queued': 0
                        }
                        yield f"data: {json.dumps(error_data)}\n\n"

                    # Wait for update signal or timeout (poll every 2 seconds)
                    # Don't clear the event - let other clients also wake up
                    self._update_event.wait(timeout=2.0)
            
            return Response(
                generate(),
                mimetype='text/event-stream',
                headers={
                    'Cache-Control': 'no-cache',
                    'Connection': 'keep-alive',
                    'Access-Control-Allow-Origin': '*'
                }
            )
        
        # Manager Mode API endpoints
        @self.app.route('/api/manager/verify-password', methods=['POST'])
        def verify_manager_password():
            """Verify manager password and create session."""
            try:
                data = request.get_json()
                password = data.get('password', '')
                db = self._get_thread_db()
                if db is None:
                    return jsonify({'success': False, 'error': 'Database connection failed'}), 500

                stored_password = db.get_setting('manager_password', '')

                if stored_password and _verify_credential(password, stored_password):
                    # Generate a session token and store it server-side with timestamp
                    session_token = secrets.token_urlsafe(32)
                    with self._session_lock:
                        self._manager_sessions[session_token] = time.time()
                    return jsonify({'success': True, 'session_token': session_token})
                return jsonify({'success': False, 'error': 'Incorrect password'})
            except Exception as e:
                import traceback
                error_msg = str(e)
                traceback.print_exc()
                return jsonify({'success': False, 'error': f'Database error: {error_msg}'}), 500

        @self.app.route('/api/manager/check-session', methods=['POST'])
        def check_manager_session():
            """Check if a manager session is still valid."""
            try:
                data = request.get_json()
                session_token = data.get('session_token', '')

                # Use the validation method which handles expiration
                is_valid = self._validate_manager_session(session_token)

                return jsonify({'valid': is_valid})
            except Exception as e:
                return jsonify({'valid': False, 'error': str(e)})
        
        @self.app.route('/api/manager/match/<int:match_id>', methods=['GET'])
        def get_manager_match(match_id):
            """Get match data for manager mode."""
            try:
                session_token = request.args.get('session_token')
                if not self._validate_manager_session(session_token):
                    return jsonify({'error': 'Unauthorized'}), 401

                db = self._get_thread_db()
                if db is None:
                    return jsonify({'error': 'Database connection failed'}), 500
                
                match = db.get_match(match_id)
                if not match:
                    return jsonify({'error': 'Match not found'}), 404
                
                games = db.get_games_for_match(match_id)
                if games is None:
                    games = []
                
                # If no games exist for this match, create game 1 automatically
                # This ensures manager mode can always work with a live match
                if len(games) == 0 and not match.get('is_complete', False):
                    try:
                        db.create_game(match_id, game_number=1, breaking_team=1)
                        games = db.get_games_for_match(match_id)
                        if games is None:
                            games = []
                    except Exception as e:
                        print(f"Error creating game 1: {e}")
                
                # If all games are complete but match isn't complete, create next game
                if games and all(g.get('winner_team', 0) != 0 for g in games) and not match.get('is_complete', False):
                    next_game_number = len(games) + 1
                    best_of = match.get('best_of', 3)
                    # Only create if we haven't reached the max games
                    if next_game_number <= best_of:
                        try:
                            db.create_game(match_id, game_number=next_game_number, breaking_team=1)
                            games = db.get_games_for_match(match_id)
                            if games is None:
                                games = []
                        except Exception as e:
                            print(f"Error creating game {next_game_number}: {e}")
                
                # Normalize winner_team values to ensure consistency (0 for active games)
                for game in games:
                    if game.get('winner_team') is None or game.get('winner_team') == '':
                        game['winner_team'] = 0
                    else:
                        # Ensure it's an integer
                        try:
                            game['winner_team'] = int(game['winner_team'])
                        except (ValueError, TypeError):
                            game['winner_team'] = 0
                
                # Format team names for display (same as regular match endpoint)
                team1_p1_first = (match.get('team1_p1_name') or "TBD").split()[0] if match.get('team1_p1_name') else "TBD"
                team1_p2_first = match.get('team1_p2_name', '').split()[0] if match.get('team1_p2_name') else None
                team2_p1_first = (match.get('team2_p1_name') or "TBD").split()[0] if match.get('team2_p1_name') else "TBD"
                team2_p2_first = match.get('team2_p2_name', '').split()[0] if match.get('team2_p2_name') else None
                
                team1 = team1_p1_first
                if team1_p2_first:
                    team1 += f" & {team1_p2_first}"
                
                team2 = team2_p1_first
                if team2_p2_first:
                    team2 += f" & {team2_p2_first}"
                
                # Calculate match scores
                t1_wins = sum(1 for g in games if g.get('winner_team') == 1)
                t2_wins = sum(1 for g in games if g.get('winner_team') == 2)
                
                # Get current game's group assignment
                current_game_group = ''
                for g in games:
                    if g.get('winner_team', 0) == 0:
                        current_game_group = g.get('team1_group', '')
                        break
                if not current_game_group and games:
                    current_game_group = games[-1].get('team1_group', '')
                
                # Format match for frontend (consistent with regular match endpoint)
                formatted_match = {
                    'id': match_id,
                    'team1': team1,
                    'team2': team2,
                    'team1_games': t1_wins,
                    'team2_games': t2_wins,
                    'best_of': match.get('best_of') or 1,
                    'is_finals': match.get('is_finals', False),
                    'is_complete': match.get('is_complete', False),
                    'table': match.get('table_number') or 0,
                    'team1_group': current_game_group,
                    # Also include raw names for manager panel
                    'team1_p1_name': match.get('team1_p1_name'),
                    'team1_p2_name': match.get('team1_p2_name'),
                    'team2_p1_name': match.get('team2_p1_name'),
                    'team2_p2_name': match.get('team2_p2_name'),
                }
                
                return jsonify({
                    'match': formatted_match,
                    'games': games
                })
            except Exception as e:
                import traceback
                error_msg = str(e)
                traceback.print_exc()
                return jsonify({'error': f'Database error: {error_msg}'}), 500
        
        @self.app.route('/api/manager/pocket-ball', methods=['POST'])
        def pocket_ball():
            """Pocket a ball (manager mode)."""
            try:
                data = request.get_json()
                match_id = data.get('match_id')
                game_number = data.get('game_number')
                ball_number = data.get('ball_number')
                team = data.get('team')  # 1 or 2
                session_token = data.get('session_token')

                # Verify session token
                if not self._validate_manager_session(session_token):
                    return jsonify({'success': False, 'error': 'Unauthorized'}), 401

                db = self._get_thread_db()
                if db is None:
                    return jsonify({'success': False, 'error': 'Database connection failed'}), 500
                
                # Get current game
                games = db.get_games_for_match(match_id)
                current_game = None
                for g in games:
                    if g['game_number'] == game_number and g.get('winner_team', 0) == 0:
                        current_game = g
                        break
                
                if not current_game:
                    return jsonify({'success': False, 'error': 'Game not found or completed'})
                
                # Update ball state - balls_pocketed may already be parsed as dict by database layer
                balls_data = current_game.get('balls_pocketed', {})
                if isinstance(balls_data, str):
                    balls = json.loads(balls_data) if balls_data else {}
                else:
                    balls = balls_data if balls_data else {}
                ball_str = str(ball_number)
                
                # Define ball groups
                SOLIDS = ['1', '2', '3', '4', '5', '6', '7']
                STRIPES = ['9', '10', '11', '12', '13', '14', '15']
                
                # Get current group assignment, breaking team, and current turn
                team1_group = current_game.get('team1_group', '')  # 'solids' or 'stripes'
                breaking_team = current_game.get('breaking_team', 1)  # Which team is breaking
                current_turn = current_game.get('current_turn', breaking_team)  # Which team is currently shooting
                group_changed = False
                turn_changed = False
                
                # Handle ball state changes
                # Use direct assignment for cycling (not toggle logic)
                # Track if we're adding/changing a ball (vs removing) for turn tracking
                is_adding_or_changing = False
                old_team = balls.get(ball_str)
                
                if team == 0:
                    # Remove ball (part of cycle: team2 → 0)
                    if ball_str in balls:
                        del balls[ball_str]
                        # Removing a ball - don't change turn
                else:
                    # Always set to requested team (cycling: 0 → team1, team1 → team2, team2 → 0)
                    # This ensures cycling works correctly regardless of current state
                    balls[ball_str] = team
                    is_adding_or_changing = True  # Adding or changing ball assignment
                
                # AUTO-ASSIGN GROUP: If no group assigned yet and a non-8 ball is pocketed
                # The POCKETING TEAM claims the group of the first ball type pocketed
                if not team1_group and ball_str != '8' and team in [1, 2]:
                    if ball_str in SOLIDS:
                        # A solid was pocketed - pocketing team gets solids
                        if team == 1:
                            team1_group = 'solids'
                        else:
                            team1_group = 'stripes'  # Team 2 gets solids, so Team 1 gets stripes
                        group_changed = True
                    elif ball_str in STRIPES:
                        # A stripe was pocketed - pocketing team gets stripes
                        if team == 1:
                            team1_group = 'stripes'
                        else:
                            team1_group = 'solids'  # Team 2 gets stripes, so Team 1 gets solids
                        group_changed = True
                
                # Calculate scores based on group assignment
                team1_score = 0
                team2_score = 0
                
                for ball, pocketing_team in balls.items():
                    if ball == '8':
                        # 8-ball is worth 3 points to whoever pockets it legally
                        if pocketing_team == 1:
                            team1_score += 3
                        elif pocketing_team == 2:
                            team2_score += 3
                    elif team1_group:
                        # With group assignment: points go to the team whose group the ball belongs to
                        if team1_group == 'solids':
                            if ball in SOLIDS:
                                team1_score += 1
                            elif ball in STRIPES:
                                team2_score += 1
                        else:  # team1 has stripes
                            if ball in STRIPES:
                                team1_score += 1
                            elif ball in SOLIDS:
                                team2_score += 1
                    else:
                        # No group assignment yet: points go to pocketing team
                        if pocketing_team == 1:
                            team1_score += 1
                        elif pocketing_team == 2:
                            team2_score += 1
                
                # Cap at 10 points per team
                team1_score = min(team1_score, 10)
                team2_score = min(team2_score, 10)
                
                # Update current_turn based on turn switching rules
                # Only update if we're adding or changing a ball (not removing) and it's not the 8-ball
                if is_adding_or_changing:
                    if ball_str == '8':
                        # 8-ball ends the game - no turn switch needed
                        pass
                    elif team1_group and team in [1, 2]:
                        # Determine which balls belong to which team
                        if team1_group == 'solids':
                            team1_balls = SOLIDS
                            team2_balls = STRIPES
                        else:
                            team1_balls = STRIPES
                            team2_balls = SOLIDS
                        
                        # Check if the pocketed ball belongs to the pocketing team
                        if team == 1:
                            owns_ball = ball_str in team1_balls
                        else:
                            owns_ball = ball_str in team2_balls
                        
                        # Switch turn if pocketed opponent's ball, keep turn if own ball
                        if not owns_ball:
                            # Switched to opponent's ball - switch turn
                            current_turn = 2 if current_turn == 1 else 1
                            turn_changed = True
                        # If owns_ball, keep the turn (no change needed)
                    # If no group assigned yet, we can't determine turn switching, so keep current turn
                
                # Check for illegal 8-ball pocket
                # Case 1: 8-ball pocketed on the break (before groups assigned) - loss for pocketing team
                # Case 2: 8-ball pocketed before clearing all assigned balls - loss for pocketing team
                illegal_8ball = False
                illegal_8ball_losing_team = None
                early_8ball_on_break = False
                
                if ball_str == '8' and team in [1, 2]:
                    if not team1_group:
                        # 8-ball pocketed on the break (no groups assigned yet)
                        # This is a loss for the pocketing team (standard bar rules)
                        illegal_8ball = True
                        illegal_8ball_losing_team = team
                        early_8ball_on_break = True
                    else:
                        # Groups are assigned - check if pocketing team cleared all their balls
                        team1_balls = SOLIDS if team1_group == 'solids' else STRIPES
                        team2_balls = STRIPES if team1_group == 'solids' else SOLIDS
                        
                        # Count how many of the pocketing team's balls have been pocketed
                        if team == 1:
                            # Team 1 pocketed the 8-ball
                            team1_cleared = sum(1 for b in team1_balls if str(b) in balls)
                            if team1_cleared < 7:
                                # Illegal! Team 1 hasn't cleared all their balls
                                illegal_8ball = True
                                illegal_8ball_losing_team = 1
                        else:
                            # Team 2 pocketed the 8-ball
                            team2_cleared = sum(1 for b in team2_balls if str(b) in balls)
                            if team2_cleared < 7:
                                # Illegal! Team 2 hasn't cleared all their balls
                                illegal_8ball = True
                                illegal_8ball_losing_team = 2
                
                # Update game in database (include group and turn if they changed)
                conn = db.get_connection()
                cursor = conn.cursor()
                if group_changed or turn_changed:
                    cursor.execute('''
                        UPDATE games 
                        SET team1_score = ?, team2_score = ?, balls_pocketed = ?, team1_group = ?, current_turn = ?
                        WHERE id = ?
                    ''', (team1_score, team2_score, json.dumps(balls), team1_group, current_turn, current_game['id']))
                else:
                    cursor.execute('''
                        UPDATE games 
                        SET team1_score = ?, team2_score = ?, balls_pocketed = ?
                        WHERE id = ?
                    ''', (team1_score, team2_score, json.dumps(balls), current_game['id']))
                conn.commit()
                
                # Log timeline events for ball pocketed
                if team in [1, 2]:
                    db.log_match_event(
                        match_id, game_number, 'ball_pocketed',
                        {'ball': ball_number, 'score': team1_score if team == 1 else team2_score},
                        team
                    )

                # Log group assignment event
                if group_changed:
                    db.log_match_event(
                        match_id, game_number, 'group_assigned',
                        {'team1_group': team1_group, 'trigger_ball': ball_number},
                        breaking_team
                    )

                # Handle illegal 8-ball - end the game with the other team winning
                if illegal_8ball:
                    winning_team = 2 if illegal_8ball_losing_team == 1 else 1
                    cursor.execute('''
                        UPDATE games
                        SET early_8ball_team = ?, winner_team = ?,
                            team1_score = CASE WHEN ? = 1 THEN 10 ELSE team1_score END,
                            team2_score = CASE WHEN ? = 2 THEN 10 ELSE team2_score END
                        WHERE id = ?
                    ''', (illegal_8ball_losing_team, winning_team, winning_team, winning_team, current_game['id']))
                    conn.commit()

                    # Log early 8-ball event
                    db.log_match_event(
                        match_id, game_number, 'early_8ball',
                        {'losing_team': illegal_8ball_losing_team, 'on_break': early_8ball_on_break},
                        winning_team
                    )

                    # Check if match is complete
                    games = db.get_games_for_match(match_id)
                    match = db.get_match(match_id)
                    best_of = match.get('best_of', 3)
                    team1_wins = sum(1 for g in games if g.get('winner_team') == 1)
                    team2_wins = sum(1 for g in games if g.get('winner_team') == 2)

                    if team1_wins >= (best_of // 2 + 1) or team2_wins >= (best_of // 2 + 1):
                        cursor.execute("UPDATE matches SET is_complete = 1, status = 'completed' WHERE id = ?", (match_id,))
                        conn.commit()

                    # Notify update
                    self.notify_update()

                    return jsonify({
                        'success': True,
                        'team1_score': team1_score,
                        'team2_score': team2_score,
                        'team1_group': team1_group,
                        'group_changed': group_changed,
                        'illegal_8ball': True,
                        'early_8ball_on_break': early_8ball_on_break,
                        'losing_team': illegal_8ball_losing_team,
                        'winning_team': winning_team
                    })

                # Notify update
                self.notify_update()

                return jsonify({
                    'success': True,
                    'team1_score': team1_score,
                    'team2_score': team2_score,
                    'team1_group': team1_group,
                    'group_changed': group_changed
                })
            except Exception as e:
                import traceback
                error_msg = str(e)
                traceback.print_exc()
                return jsonify({'success': False, 'error': f'Database error: {error_msg}'}), 500
        
        @self.app.route('/api/manager/win-game', methods=['POST'])
        def win_game():
            """Mark a game as won (manager mode)."""
            try:
                data = request.get_json()
                match_id = data.get('match_id')
                game_number = data.get('game_number')
                winning_team = data.get('winning_team')  # 1 or 2
                session_token = data.get('session_token')

                # Verify session token
                if not self._validate_manager_session(session_token):
                    return jsonify({'success': False, 'error': 'Unauthorized'}), 401

                db = self._get_thread_db()
                if db is None:
                    return jsonify({'success': False, 'error': 'Database connection failed'}), 500

                # Update game
                games = db.get_games_for_match(match_id)
                current_game = None
                for g in games:
                    if g['game_number'] == game_number:
                        current_game = g
                        break
                
                if not current_game:
                    return jsonify({'success': False, 'error': 'Game not found'})
                
                # Get current game state
                balls_data = current_game.get('balls_pocketed', {})
                if isinstance(balls_data, str):
                    balls = json.loads(balls_data) if balls_data else {}
                else:
                    balls = balls_data if balls_data else {}
                
                team1_group = current_game.get('team1_group', '')
                current_turn = current_game.get('current_turn', current_game.get('breaking_team', 1))
                team1_score = current_game.get('team1_score', 0)
                team2_score = current_game.get('team2_score', 0)
                scores_updated = False
                
                # Determine which team shot the 8-ball
                eight_ball_team = None
                if '8' in balls:
                    # 8-ball is already tracked in balls_pocketed
                    eight_ball_team = balls['8']
                else:
                    # 8-ball not tracked - use current_turn to determine which team shot it
                    eight_ball_team = current_turn
                    # Add 8-ball to balls_pocketed with the team that shot it
                    balls['8'] = eight_ball_team
                    
                    # Recalculate scores if 8-ball wasn't previously tracked
                    # Define ball groups
                    SOLIDS = ['1', '2', '3', '4', '5', '6', '7']
                    STRIPES = ['9', '10', '11', '12', '13', '14', '15']
                    
                    # Recalculate scores from scratch
                    team1_score = 0
                    team2_score = 0
                    
                    for ball, pocketing_team in balls.items():
                        if ball == '8':
                            # 8-ball is worth 3 points to whoever pockets it legally
                            if pocketing_team == 1:
                                team1_score += 3
                            elif pocketing_team == 2:
                                team2_score += 3
                        elif team1_group:
                            # With group assignment: points go to the team whose group the ball belongs to
                            if team1_group == 'solids':
                                if ball in SOLIDS:
                                    team1_score += 1
                                elif ball in STRIPES:
                                    team2_score += 1
                            else:  # team1 has stripes
                                if ball in STRIPES:
                                    team1_score += 1
                                elif ball in SOLIDS:
                                    team2_score += 1
                        else:
                            # No group assignment yet: points go to pocketing team
                            if pocketing_team == 1:
                                team1_score += 1
                            elif pocketing_team == 2:
                                team2_score += 1
                    
                    # Cap at 10 points per team
                    team1_score = min(team1_score, 10)
                    team2_score = min(team2_score, 10)
                    scores_updated = True
                
                conn = db.get_connection()
                cursor = conn.cursor()
                
                # Update game with winner, balls_pocketed (if updated), and scores (if recalculated)
                if scores_updated:
                    cursor.execute('''
                        UPDATE games 
                        SET winner_team = ?, balls_pocketed = ?, team1_score = ?, team2_score = ?
                        WHERE id = ?
                    ''', (winning_team, json.dumps(balls), team1_score, team2_score, current_game['id']))
                else:
                    # Only update winner_team and balls_pocketed (if 8-ball was added)
                    if '8' not in balls_data:
                        cursor.execute('''
                            UPDATE games 
                            SET winner_team = ?, balls_pocketed = ?
                            WHERE id = ?
                        ''', (winning_team, json.dumps(balls), current_game['id']))
                    else:
                        cursor.execute('''
                            UPDATE games 
                            SET winner_team = ?
                            WHERE id = ?
                        ''', (winning_team, current_game['id']))
                conn.commit()
                
                # Check if match is complete
                games = db.get_games_for_match(match_id)
                match = db.get_match(match_id)
                best_of = match.get('best_of', 3)
                team1_wins = sum(1 for g in games if g.get('winner_team') == 1)
                team2_wins = sum(1 for g in games if g.get('winner_team') == 2)
                
                match_complete = False
                if team1_wins >= (best_of // 2 + 1) or team2_wins >= (best_of // 2 + 1):
                    cursor.execute("UPDATE matches SET is_complete = 1, status = 'completed' WHERE id = ?", (match_id,))
                    conn.commit()
                    match_complete = True

                # Log game win event
                db.log_match_event(
                    match_id, game_number, 'game_win',
                    {
                        'team1_score': team1_score,
                        'team2_score': team2_score,
                        'match_complete': match_complete,
                        'team1_wins': team1_wins,
                        'team2_wins': team2_wins
                    },
                    winning_team
                )

                # Notify update
                self.notify_update()

                return jsonify({'success': True})
            except Exception as e:
                import traceback
                error_msg = str(e)
                traceback.print_exc()
                return jsonify({'success': False, 'error': f'Database error: {error_msg}'}), 500

        @self.app.route('/api/manager/edit-game-scores', methods=['POST'])
        def edit_game_scores():
            """Edit game scores manually (manager mode)."""
            try:
                data = request.get_json()
                match_id = data.get('match_id')
                game_number = data.get('game_number')
                team1_score = data.get('team1_score')
                team2_score = data.get('team2_score')
                session_token = data.get('session_token')

                # Verify session token
                if not self._validate_manager_session(session_token):
                    return jsonify({'success': False, 'error': 'Unauthorized'}), 401

                # Validate inputs
                if team1_score is None or team2_score is None:
                    return jsonify({'success': False, 'error': 'team1_score and team2_score are required'}), 400
                
                try:
                    team1_score = int(team1_score)
                    team2_score = int(team2_score)
                except (ValueError, TypeError):
                    return jsonify({'success': False, 'error': 'Scores must be integers'}), 400

                # Cap scores at 17 per team (17 possible with golden break)
                team1_score = min(max(team1_score, 0), 17)
                team2_score = min(max(team2_score, 0), 17)

                db = self._get_thread_db()
                if db is None:
                    return jsonify({'success': False, 'error': 'Database connection failed'}), 500

                # Find the game
                games = db.get_games_for_match(match_id)
                current_game = None
                for g in games:
                    if g['game_number'] == game_number:
                        current_game = g
                        break
                
                if not current_game:
                    return jsonify({'success': False, 'error': 'Game not found'})
                
                # Update game scores
                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE games 
                    SET team1_score = ?, team2_score = ?
                    WHERE id = ?
                ''', (team1_score, team2_score, current_game['id']))
                conn.commit()
                
                # Notify update
                self.notify_update()
                
                return jsonify({
                    'success': True,
                    'team1_score': team1_score,
                    'team2_score': team2_score
                })
            except Exception as e:
                import traceback
                error_msg = str(e)
                traceback.print_exc()
                return jsonify({'success': False, 'error': f'Database error: {error_msg}'}), 500

        @self.app.route('/api/manager/set-group', methods=['POST'])
        def set_group():
            """Set the group assignment (solids/stripes) for a game."""
            try:
                data = request.get_json()
                match_id = data.get('match_id')
                game_number = data.get('game_number')
                team1_group = data.get('team1_group')  # 'solids' or 'stripes'
                session_token = data.get('session_token')

                # Verify session token
                if not self._validate_manager_session(session_token):
                    return jsonify({'success': False, 'error': 'Unauthorized'}), 401

                db = self._get_thread_db()
                if db is None:
                    return jsonify({'success': False, 'error': 'Database connection failed'}), 500

                # Find the game
                games = db.get_games_for_match(match_id)
                current_game = None
                for g in games:
                    if g['game_number'] == game_number:
                        current_game = g
                        break
                
                if not current_game:
                    return jsonify({'success': False, 'error': 'Game not found'})
                
                # Update game in database
                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE games 
                    SET team1_group = ?
                    WHERE id = ?
                ''', (team1_group, current_game['id']))
                conn.commit()
                
                # Recalculate scores based on new group assignment
                balls_data = current_game.get('balls_pocketed', {})
                if isinstance(balls_data, str):
                    balls = json.loads(balls_data) if balls_data else {}
                else:
                    balls = balls_data if balls_data else {}
                
                SOLIDS = ['1', '2', '3', '4', '5', '6', '7']
                STRIPES = ['9', '10', '11', '12', '13', '14', '15']
                
                team1_score = 0
                team2_score = 0
                
                for ball, pocketing_team in balls.items():
                    if ball == '8':
                        if pocketing_team == 1:
                            team1_score += 3
                        elif pocketing_team == 2:
                            team2_score += 3
                    elif team1_group == 'solids':
                        if ball in SOLIDS:
                            team1_score += 1
                        elif ball in STRIPES:
                            team2_score += 1
                    else:  # team1 has stripes
                        if ball in STRIPES:
                            team1_score += 1
                        elif ball in SOLIDS:
                            team2_score += 1
                
                team1_score = min(team1_score, 10)
                team2_score = min(team2_score, 10)
                
                cursor.execute('''
                    UPDATE games 
                    SET team1_score = ?, team2_score = ?
                    WHERE id = ?
                ''', (team1_score, team2_score, current_game['id']))
                conn.commit()
                
                # Notify update
                self.notify_update()
                
                return jsonify({'success': True, 'team1_group': team1_group})
            except Exception as e:
                import traceback
                traceback.print_exc()
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/manager/set-breaking-team', methods=['POST'])
        def set_breaking_team():
            """Set which team is breaking/shooting first."""
            try:
                data = request.get_json()
                match_id = data.get('match_id')
                game_number = data.get('game_number')
                breaking_team = data.get('breaking_team')  # 1 or 2
                session_token = data.get('session_token')

                # Verify session token
                if not self._validate_manager_session(session_token):
                    return jsonify({'success': False, 'error': 'Unauthorized'}), 401

                db = self._get_thread_db()
                if db is None:
                    return jsonify({'success': False, 'error': 'Database connection failed'}), 500

                # Find the game
                games = db.get_games_for_match(match_id)
                current_game = None
                for g in games:
                    if g['game_number'] == game_number:
                        current_game = g
                        break
                
                if not current_game:
                    return jsonify({'success': False, 'error': 'Game not found'})
                
                # Update game in database
                # Also update current_turn to match breaking_team (breaking team shoots first)
                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE games 
                    SET breaking_team = ?, current_turn = ?
                    WHERE id = ?
                ''', (breaking_team, breaking_team, current_game['id']))
                conn.commit()
                
                # Notify update
                self.notify_update()
                
                return jsonify({'success': True, 'breaking_team': breaking_team})
            except Exception as e:
                import traceback
                traceback.print_exc()
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/manager/set-golden-break', methods=['POST'])
        def set_golden_break():
            """Set golden break status for a game."""
            try:
                data = request.get_json()
                match_id = data.get('match_id')
                game_number = data.get('game_number')
                golden_break = data.get('golden_break', False)
                winning_team = data.get('winning_team', 1)  # Team that got the golden break
                session_token = data.get('session_token')

                # Verify session token
                if not self._validate_manager_session(session_token):
                    return jsonify({'success': False, 'error': 'Unauthorized'}), 401

                db = self._get_thread_db()
                if db is None:
                    return jsonify({'success': False, 'error': 'Database connection failed'}), 500

                # Find the game
                games = db.get_games_for_match(match_id)
                current_game = None
                for g in games:
                    if g['game_number'] == game_number:
                        current_game = g
                        break
                
                if not current_game:
                    return jsonify({'success': False, 'error': 'Game not found'})
                
                # Update game with golden break - this also marks the game as won
                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE games 
                    SET golden_break = 1, winner_team = ?, team1_score = ?, team2_score = ?
                    WHERE id = ?
                ''', (winning_team, 17 if winning_team == 1 else 0, 17 if winning_team == 2 else 0, current_game['id']))
                conn.commit()
                
                # Check if match is complete
                games = db.get_games_for_match(match_id)
                match = db.get_match(match_id)
                best_of = match.get('best_of', 3)
                team1_wins = sum(1 for g in games if g.get('winner_team') == 1)
                team2_wins = sum(1 for g in games if g.get('winner_team') == 2)
                
                match_complete = False
                if team1_wins >= (best_of // 2 + 1) or team2_wins >= (best_of // 2 + 1):
                    cursor.execute("UPDATE matches SET is_complete = 1, status = 'completed' WHERE id = ?", (match_id,))
                    conn.commit()
                    match_complete = True

                # Log golden break event
                db.log_match_event(
                    match_id, game_number, 'golden_break',
                    {'match_complete': match_complete, 'team1_wins': team1_wins, 'team2_wins': team2_wins},
                    winning_team
                )

                # Notify update
                self.notify_update()

                return jsonify({'success': True, 'golden_break': True, 'winning_team': winning_team})
            except Exception as e:
                import traceback
                traceback.print_exc()
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/manager/set-early-8ball', methods=['POST'])
        def set_early_8ball():
            """Set early 8-ball (scratch/foul on 8) for a game."""
            try:
                data = request.get_json()
                match_id = data.get('match_id')
                game_number = data.get('game_number')
                losing_team = data.get('losing_team')  # Team that scratched on 8
                session_token = data.get('session_token')

                # Verify session token
                if not self._validate_manager_session(session_token):
                    return jsonify({'success': False, 'error': 'Unauthorized'}), 401

                db = self._get_thread_db()
                if db is None:
                    return jsonify({'success': False, 'error': 'Database connection failed'}), 500

                # Find the game
                games = db.get_games_for_match(match_id)
                current_game = None
                for g in games:
                    if g['game_number'] == game_number:
                        current_game = g
                        break
                
                if not current_game:
                    return jsonify({'success': False, 'error': 'Game not found'})
                
                # Determine winning team (opposite of losing team)
                winning_team = 2 if losing_team == 1 else 1
                
                # Update game - early 8ball gives the win to the other team
                # Winner gets 10 points per ruleset
                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE games
                    SET early_8ball_team = ?, winner_team = ?,
                        team1_score = CASE WHEN ? = 1 THEN 10 ELSE team1_score END,
                        team2_score = CASE WHEN ? = 2 THEN 10 ELSE team2_score END
                    WHERE id = ?
                ''', (losing_team, winning_team, winning_team, winning_team, current_game['id']))
                conn.commit()
                
                # Check if match is complete
                games = db.get_games_for_match(match_id)
                match = db.get_match(match_id)
                best_of = match.get('best_of', 3)
                team1_wins = sum(1 for g in games if g.get('winner_team') == 1)
                team2_wins = sum(1 for g in games if g.get('winner_team') == 2)
                
                match_complete = False
                if team1_wins >= (best_of // 2 + 1) or team2_wins >= (best_of // 2 + 1):
                    cursor.execute("UPDATE matches SET is_complete = 1, status = 'completed' WHERE id = ?", (match_id,))
                    conn.commit()
                    match_complete = True

                # Log early 8-ball event
                db.log_match_event(
                    match_id, game_number, 'early_8ball',
                    {'losing_team': losing_team, 'match_complete': match_complete},
                    winning_team
                )

                # Notify update
                self.notify_update()

                return jsonify({'success': True, 'winning_team': winning_team})
            except Exception as e:
                import traceback
                traceback.print_exc()
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/manager/reset-table', methods=['POST'])
        def reset_table():
            """Reset the table (clear all balls and scores) for a game."""
            try:
                data = request.get_json()
                match_id = data.get('match_id')
                game_number = data.get('game_number')
                session_token = data.get('session_token')

                # Verify session token
                if not self._validate_manager_session(session_token):
                    return jsonify({'success': False, 'error': 'Unauthorized'}), 401

                db = self._get_thread_db()
                if db is None:
                    return jsonify({'success': False, 'error': 'Database connection failed'}), 500

                # Find the game
                games = db.get_games_for_match(match_id)
                current_game = None
                for g in games:
                    if g['game_number'] == game_number:
                        current_game = g
                        break
                
                if not current_game:
                    return jsonify({'success': False, 'error': 'Game not found'})
                
                # Reset the game - clear balls, scores, and group assignment
                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE games 
                    SET team1_score = 0, team2_score = 0, balls_pocketed = '{}', 
                        team1_group = '', winner_team = 0, golden_break = 0, early_8ball_team = NULL
                    WHERE id = ?
                ''', (current_game['id'],))
                conn.commit()
                
                # Notify update
                self.notify_update()
                
                return jsonify({'success': True})
            except Exception as e:
                import traceback
                traceback.print_exc()
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/manager/revert-game', methods=['POST'])
        def revert_game():
            """Revert a completed game so it can be replayed."""
            try:
                data = request.get_json()
                match_id = data.get('match_id')
                game_number = data.get('game_number')
                session_token = data.get('session_token')

                if not self._validate_manager_session(session_token):
                    return jsonify({'success': False, 'error': 'Unauthorized'}), 401

                db = self._get_thread_db()
                if db is None:
                    return jsonify({'success': False, 'error': 'Database connection failed'}), 500

                games = db.get_games_for_match(match_id)
                current_game = None
                for g in games:
                    if g['game_number'] == game_number:
                        current_game = g
                        break

                if not current_game:
                    return jsonify({'success': False, 'error': 'Game not found'})

                conn = db.get_connection()
                cursor = conn.cursor()

                # Reset the game to active state
                cursor.execute('''
                    UPDATE games
                    SET team1_score = 0, team2_score = 0, balls_pocketed = '{}',
                        team1_group = '', winner_team = 0, golden_break = 0,
                        early_8ball_team = NULL
                    WHERE id = ?
                ''', (current_game['id'],))

                # Delete any games after this one (auto-created next games)
                cursor.execute('''
                    DELETE FROM games
                    WHERE match_id = ? AND game_number > ?
                ''', (match_id, game_number))

                # Revert match completion if it was complete
                cursor.execute('''
                    UPDATE matches SET is_complete = 0, status = 'live'
                    WHERE id = ?
                ''', (match_id,))

                # Clear match events for this game
                cursor.execute('''
                    DELETE FROM match_events
                    WHERE match_id = ? AND game_number = ?
                ''', (match_id, game_number))

                conn.commit()

                self.notify_update()
                return jsonify({'success': True})
            except Exception as e:
                import traceback
                traceback.print_exc()
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/manager/revert-match-completion', methods=['POST'])
        def revert_match_completion():
            """Reopen a completed match back to live status."""
            try:
                data = request.get_json()
                match_id = data.get('match_id')
                session_token = data.get('session_token')

                if not self._validate_manager_session(session_token):
                    return jsonify({'success': False, 'error': 'Unauthorized'}), 401

                db = self._get_thread_db()
                if db is None:
                    return jsonify({'success': False, 'error': 'Database connection failed'}), 500

                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE matches SET is_complete = 0, status = 'live'
                    WHERE id = ?
                ''', (match_id,))
                conn.commit()

                self.notify_update()
                return jsonify({'success': True})
            except Exception as e:
                import traceback
                traceback.print_exc()
                return jsonify({'success': False, 'error': str(e)}), 500

        @self.app.route('/api/manager/available-tables', methods=['GET'])
        def get_available_tables():
            """Get list of available tables (not currently running a live match)."""
            try:
                session_token = request.args.get('session_token')
                if not self._validate_manager_session(session_token):
                    return jsonify({'error': 'Unauthorized'}), 401

                db = self._get_thread_db()
                if db is None:
                    return jsonify({'error': 'Database connection failed'}), 500
                
                league_night = db.get_current_league_night()
                if not league_night:
                    return jsonify({'available_tables': [], 'queue': [], 'live_matches': [], 'total_tables': 0})
                
                # Get table count
                num_tables = league_night.get('table_count', 3)
                
                # Get tables with live matches
                try:
                    live_matches = db.get_live_matches(league_night['id']) or []
                except Exception as e:
                    print(f"Error getting live matches: {e}")
                    live_matches = []
                    
                occupied_tables = set(m['table_number'] for m in live_matches if m.get('table_number'))
                
                # Find available tables
                available_tables = [i for i in range(1, num_tables + 1) if i not in occupied_tables]
                
                # Get queued matches
                try:
                    queued_matches = db.get_queued_matches(league_night['id']) or []
                except Exception as e:
                    print(f"Error getting queued matches: {e}")
                    queued_matches = []
                queue_data = []
                for match in queued_matches:
                    team1 = match.get('team1_p1_name', 'TBD')
                    if match.get('team1_p2_name'):
                        team1 += f" & {match['team1_p2_name']}"
                    team2 = match.get('team2_p1_name', 'TBD')
                    if match.get('team2_p2_name'):
                        team2 += f" & {match['team2_p2_name']}"
                    
                    queue_data.append({
                        'id': match['id'],
                        'team1': team1,
                        'team2': team2,
                        'round': match.get('round_number', 1),
                        'best_of': match.get('best_of', 3),
                        'is_finals': match.get('is_finals', False)
                    })
                
                # Get live matches for the "Complete Match" feature
                live_matches_data = []
                for match in live_matches:
                    try:
                        team1 = match.get('team1_p1_name') or 'TBD'
                        if match.get('team1_p2_name'):
                            team1 += f" & {match['team1_p2_name']}"
                        team2 = match.get('team2_p1_name') or 'TBD'
                        if match.get('team2_p2_name'):
                            team2 += f" & {match['team2_p2_name']}"
                        
                        # Get game scores
                        try:
                            games = db.get_games_for_match(match['id']) or []
                        except Exception:
                            games = []
                        team1_games = sum(1 for g in games if g.get('winner_team') == 1)
                        team2_games = sum(1 for g in games if g.get('winner_team') == 2)
                        
                        live_matches_data.append({
                            'id': match['id'],
                            'team1': team1,
                            'team2': team2,
                            'table': match.get('table_number') or 0,
                            'team1_games': team1_games,
                            'team2_games': team2_games,
                            'is_complete': match.get('is_complete', False)
                        })
                    except Exception as e:
                        print(f"Error processing live match {match.get('id')}: {e}")
                
                return jsonify({
                    'available_tables': available_tables,
                    'queue': queue_data,
                    'live_matches': live_matches_data,
                    'total_tables': num_tables
                })
            except Exception as e:
                import traceback
                traceback.print_exc()
                return jsonify({'error': str(e)}), 500
        
        @self.app.route('/api/manager/start-match', methods=['POST'])
        def start_match_on_table():
            """Start a match from the queue on a specific table."""
            try:
                data = request.get_json()
                match_id = data.get('match_id')
                table_number = data.get('table_number')
                session_token = data.get('session_token')

                # Verify session token
                if not self._validate_manager_session(session_token):
                    return jsonify({'success': False, 'error': 'Unauthorized'}), 401

                db = self._get_thread_db()
                if db is None:
                    return jsonify({'success': False, 'error': 'Database connection failed'}), 500

                # Get the match
                match = db.get_match(match_id)
                if not match:
                    return jsonify({'success': False, 'error': 'Match not found'})
                
                # Check if table is available and players aren't already playing
                league_night = db.get_current_league_night()
                if league_night:
                    live_matches = db.get_live_matches(league_night['id'])
                    
                    # Check if the table is already in use
                    for m in live_matches:
                        if m.get('table_number') == table_number:
                            return jsonify({'success': False, 'error': f'Table {table_number} is already in use'})
                    
                    # Get all players from the match we want to start
                    match_players = set()
                    for player_name in [match.get('team1_p1_name'), match.get('team1_p2_name'),
                                        match.get('team2_p1_name'), match.get('team2_p2_name')]:
                        if player_name:
                            match_players.add(player_name.strip().lower())
                    
                    # Check if any of these players are already in an active match
                    for m in live_matches:
                        for player_name in [m.get('team1_p1_name'), m.get('team1_p2_name'),
                                            m.get('team2_p1_name'), m.get('team2_p2_name')]:
                            if player_name and player_name.strip().lower() in match_players:
                                # Find the table they're playing on
                                busy_table = m.get('table_number', 'unknown')
                                return jsonify({
                                    'success': False, 
                                    'error': f'{player_name} is already playing on Table {busy_table}'
                                })
                
                # Start the match on the table
                db.start_match(match_id, table_number)
                
                # Create game 1 for this match
                try:
                    db.create_game(match_id, game_number=1, breaking_team=1)
                except Exception as e:
                    print(f"Note: Game 1 may already exist: {e}")
                
                # Notify update
                self.notify_update()
                
                return jsonify({'success': True, 'match_id': match_id, 'table_number': table_number})
            except Exception as e:
                import traceback
                traceback.print_exc()
                return jsonify({'success': False, 'error': str(e)}), 500
        
        @self.app.route('/api/manager/complete-match', methods=['POST'])
        def complete_match():
            """Mark a match as complete and free the table."""
            try:
                data = request.get_json()
                match_id = data.get('match_id')
                session_token = data.get('session_token')

                # Verify session token
                if not self._validate_manager_session(session_token):
                    return jsonify({'success': False, 'error': 'Unauthorized'}), 401

                db = self._get_thread_db()
                if db is None:
                    return jsonify({'success': False, 'error': 'Database connection failed'}), 500

                # Get the match
                match = db.get_match(match_id)
                if not match:
                    return jsonify({'success': False, 'error': 'Match not found'})
                
                table_number = match.get('table_number')
                
                # Mark match as complete
                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE matches 
                    SET is_complete = 1, status = 'completed'
                    WHERE id = ?
                ''', (match_id,))
                conn.commit()
                
                # Notify update
                self.notify_update()
                
                return jsonify({'success': True, 'match_id': match_id, 'table_freed': table_number})
            except Exception as e:
                import traceback
                traceback.print_exc()
                return jsonify({'success': False, 'error': str(e)}), 500
        
        # New Features API endpoints
        @self.app.route('/api/achievements/<int:player_id>')
        def get_player_achievements(player_id):
            """Get achievements for a player."""
            try:
                from achievements import AchievementManager
                db = self._get_thread_db()
                mgr = AchievementManager(db)
                achievements = mgr.get_player_achievements(player_id)
                return jsonify({
                    'player_id': player_id,
                    'achievements': [
                        {
                            'id': a['achievement'].id,
                            'name': a['achievement'].name,
                            'description': a['achievement'].description,
                            'icon': a['achievement'].icon,
                            'tier': a['achievement'].tier,
                            'unlocked': a['unlocked'],
                            'progress': a['progress'],
                            'progress_percent': a['progress_percent']
                        }
                        for a in achievements
                    ]
                })
            except Exception as e:
                return jsonify({'error': str(e)})
        
        @self.app.route('/api/stats/player/<int:player_id>')
        def get_player_stats(player_id):
            """Get advanced stats for a player."""
            try:
                from advanced_stats import AdvancedStatsManager
                db = self._get_thread_db()
                mgr = AdvancedStatsManager(db)
                
                # Get player
                player = db.get_player(player_id)
                if not player:
                    return jsonify({'error': 'Player not found'})
                
                # Get form
                form = mgr.get_player_form(player_id)
                
                # Get streaks
                streaks = mgr.get_player_streaks(player_id)
                
                return jsonify({
                    'player_id': player_id,
                    'player_name': player.name,
                    'form': {
                        'recent_games': form.recent_games,
                        'recent_win_rate': form.recent_win_rate,
                        'trend': form.trend,
                        'clutch_rating': form.clutch_rating
                    } if form else None,
                    'streaks': [
                        {
                            'type': s.type,
                            'length': s.length,
                            'started_at': s.started_at
                        }
                        for s in streaks
                    ]
                })
            except Exception as e:
                return jsonify({'error': str(e)})
        
        @self.app.route('/api/stats/h2h/<int:player1_id>/<int:player2_id>')
        def get_head_to_head(player1_id, player2_id):
            """Get head-to-head stats between two players."""
            try:
                from advanced_stats import AdvancedStatsManager
                db = self._get_thread_db()
                mgr = AdvancedStatsManager(db)
                h2h = mgr.get_head_to_head(player1_id, player2_id)
                
                if not h2h:
                    return jsonify({'error': 'No head-to-head data found'})
                
                return jsonify({
                    'player1_id': player1_id,
                    'player2_id': player2_id,
                    'player1_name': h2h.player1_name,
                    'player2_name': h2h.player2_name,
                    'player1_wins': h2h.player1_wins,
                    'player2_wins': h2h.player2_wins,
                    'player1_points': h2h.player1_points,
                    'player2_points': h2h.player2_points
                })
            except Exception as e:
                return jsonify({'error': str(e)})
        
        @self.app.route('/api/payments/league-night/<int:league_night_id>')
        def get_league_night_payments(league_night_id):
            """Get payment information for a league night."""
            try:
                from venmo_integration import VenmoIntegration
                db = self._get_thread_db()
                venmo_mgr = VenmoIntegration(db)
                
                payments = venmo_mgr.get_league_night_payments(league_night_id)
                return jsonify({
                    'league_night_id': league_night_id,
                    'payments': [
                        {
                            'player_id': p['player_id'],
                            'player_name': p['player_name'],
                            'amount': p['amount'],
                            'paid': p['paid'],
                            'venmo_confirmed': p['venmo_confirmed']
                        }
                        for p in payments
                    ]
                })
            except Exception as e:
                return jsonify({'error': str(e)})

        # ============ Payment Admin Panel Routes ============

        @self.app.route('/admin/payments')
        def payments_admin():
            """Render the payments admin panel (protected by PIN)."""
            # Authentication is handled client-side via sessionStorage
            # The payments_admin.html template will redirect to login if not authenticated
            return render_template('payments_admin.html')
        
        @self.app.route('/admin/payments/login')
        def payments_login():
            """Render the payment portal login page."""
            return render_template('payments_login.html')
        
        @self.app.route('/api/payments/verify-pin', methods=['POST'])
        def verify_payment_pin():
            """Verify payment portal PIN/passcode."""
            try:
                data = request.get_json()
                pin = data.get('pin', '')
                db = self._get_thread_db()

                # Get stored payment portal PIN
                stored_pin = db.get_setting('payment_portal_pin', '')

                # If no PIN is set, require manager password to set initial PIN
                if not stored_pin:
                    return jsonify({
                        'success': False,
                        'error': 'No PIN configured. Please use the desktop app to set a payment PIN.',
                        'needs_setup': True
                    })

                # Verify PIN using constant-time comparison
                if _verify_credential(pin, stored_pin):
                    return jsonify({'success': True})
                else:
                    return jsonify({'success': False, 'error': 'Incorrect PIN'})
            except Exception as e:
                import traceback
                traceback.print_exc()
                return jsonify({'success': False, 'error': str(e)})
        
        @self.app.route('/api/payments/set-pin', methods=['POST'])
        def set_payment_pin():
            """Set or change payment portal PIN (requires manager password)."""
            try:
                data = request.get_json()
                new_pin = data.get('pin', '')
                manager_password = data.get('manager_password', '')

                if not new_pin:
                    return jsonify({'success': False, 'error': 'PIN required'})

                if len(new_pin) < 4:
                    return jsonify({'success': False, 'error': 'PIN must be at least 4 characters'})

                # Verify manager password using secure comparison
                db = self._get_thread_db()
                stored_manager_password = db.get_setting('manager_password', '')

                if not stored_manager_password or not _verify_credential(manager_password, stored_manager_password):
                    return jsonify({'success': False, 'error': 'Manager password required'})

                # Hash and store the new PIN
                hashed_pin = _hash_credential(new_pin)
                db.set_setting('payment_portal_pin', hashed_pin)

                return jsonify({'success': True, 'message': 'Payment portal PIN updated'})
            except Exception as e:
                import traceback
                traceback.print_exc()
                return jsonify({'success': False, 'error': str(e)})

        @self.app.route('/api/seasons')
        def get_seasons():
            """Get all seasons for selection dropdown."""
            try:
                db = self._get_thread_db()
                seasons = db.get_all_seasons()
                return jsonify([{
                    'id': s.id,
                    'name': s.name,
                    'is_active': s.is_active,
                    'start_date': s.start_date,
                    'end_date': s.end_date
                } for s in seasons])
            except Exception as e:
                return jsonify({'error': str(e)})

        @self.app.route('/api/payments/analytics')
        def get_payment_analytics():
            """Get payment analytics data."""
            try:
                from venmo_integration import VenmoIntegration
                db = self._get_thread_db()
                venmo_mgr = VenmoIntegration(db)
                season_id = request.args.get('season_id', type=int)
                analytics = venmo_mgr.get_payment_analytics(season_id)
                return jsonify(analytics)
            except Exception as e:
                return jsonify({'error': str(e)})

        @self.app.route('/api/payments/season-summary')
        def get_season_summary():
            """Get season payment summary."""
            try:
                from venmo_integration import VenmoIntegration
                db = self._get_thread_db()
                venmo_mgr = VenmoIntegration(db)
                season_id = request.args.get('season_id', type=int)
                summary = venmo_mgr.get_season_summary(season_id)
                return jsonify(summary)
            except Exception as e:
                return jsonify({'error': str(e)})

        @self.app.route('/api/payments/audit-log')
        def get_audit_log():
            """Get payment audit log (requires payment portal authentication)."""
            # Require authentication for sensitive payment data
            is_auth, error = self._require_payment_auth()
            if not is_auth:
                return jsonify(error[0]), error[1]

            try:
                from venmo_integration import VenmoIntegration
                db = self._get_thread_db()
                venmo_mgr = VenmoIntegration(db)
                league_night_id = request.args.get('league_night_id', type=int)
                player_id = request.args.get('player_id', type=int)
                limit = request.args.get('limit', default=100, type=int)
                log = venmo_mgr.get_audit_log(league_night_id, player_id, limit)
                return jsonify({'entries': log})
            except Exception as e:
                return jsonify({'error': str(e)})

        @self.app.route('/api/payments/mark-paid', methods=['POST'])
        def mark_payment_paid():
            """Mark a payment as paid from web admin (requires payment portal authentication)."""
            # Require authentication for payment modifications
            is_auth, error = self._require_payment_auth()
            if not is_auth:
                return jsonify(error[0]), error[1]

            try:
                from venmo_integration import VenmoIntegration
                db = self._get_thread_db()
                venmo_mgr = VenmoIntegration(db)
                data = request.get_json()
                request_id = data.get('request_id')
                txn_id = data.get('txn_id')
                if not request_id:
                    return jsonify({'success': False, 'error': 'request_id required'})
                venmo_mgr.mark_as_paid(request_id, txn_id, performed_by='web_admin')
                return jsonify({'success': True})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})

        @self.app.route('/api/payments/all-requests')
        def get_all_payment_requests():
            """Get all payment requests for a league night (requires payment portal authentication)."""
            # Require authentication for sensitive payment data
            is_auth, error = self._require_payment_auth()
            if not is_auth:
                return jsonify(error[0]), error[1]

            try:
                from venmo_integration import VenmoIntegration
                db = self._get_thread_db()
                venmo_mgr = VenmoIntegration(db)
                league_night_id = request.args.get('league_night_id', type=int)
                if not league_night_id:
                    # Get current league night
                    night = db.get_current_league_night()
                    if night:
                        league_night_id = night['id']
                    else:
                        return jsonify({'requests': [], 'error': 'No active league night'})
                requests_list = venmo_mgr.get_all_requests(league_night_id)
                return jsonify({'requests': requests_list, 'league_night_id': league_night_id})
            except Exception as e:
                return jsonify({'error': str(e)})

        @self.app.route('/api/payments/create-request', methods=['POST'])
        def create_payment_request():
            """Create a new payment request from web interface (requires payment portal authentication)."""
            # Require authentication for payment modifications
            is_auth, error = self._require_payment_auth()
            if not is_auth:
                return jsonify(error[0]), error[1]

            try:
                from venmo_integration import VenmoIntegration
                db = self._get_thread_db()
                venmo_mgr = VenmoIntegration(db)

                data = request.get_json()
                player_id = data.get('player_id')
                amount = data.get('amount')
                note = data.get('note', 'EcoPOOL League Buy-In')

                if not player_id or not amount:
                    return jsonify({'success': False, 'error': 'player_id and amount required'})

                # Get current league night
                night = db.get_current_league_night()
                if not night:
                    return jsonify({'success': False, 'error': 'No active league night'})

                request_id = venmo_mgr.create_payment_request(
                    night['id'],
                    player_id,
                    float(amount),
                    note,
                    performed_by='web_admin'
                )

                return jsonify({'success': True, 'request_id': request_id})
            except Exception as e:
                import traceback
                traceback.print_exc()
                return jsonify({'success': False, 'error': str(e)})

        @self.app.route('/api/payments/send-request', methods=['POST'])
        def send_payment_request():
            """Send a payment request - returns link to open on client device (requires payment portal authentication)."""
            # Require authentication for payment modifications
            is_auth, error = self._require_payment_auth()
            if not is_auth:
                return jsonify(error[0]), error[1]

            try:
                from venmo_integration import VenmoIntegration
                db = self._get_thread_db()
                venmo_mgr = VenmoIntegration(db)
                
                data = request.get_json()
                request_id = data.get('request_id')
                
                if not request_id:
                    return jsonify({'success': False, 'error': 'request_id required'})
                
                # Get request details to return Venmo link
                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT pr.*, p.venmo, p.name
                    FROM payment_requests pr
                    JOIN players p ON pr.player_id = p.id
                    WHERE pr.id = ?
                ''', (request_id,))
                row = cursor.fetchone()
                
                if not row or not row['venmo']:
                    return jsonify({'success': False, 'error': 'Request not found or player has no Venmo'})
                
                username = row['venmo'].lstrip('@')
                amount = row['amount']
                note = row['note'] or f"EcoPOOL Buy-In - {row['name']}"
                
                # Generate deep link for mobile app (this will open on the CLIENT device)
                venmo_deep_link = venmo_mgr.generate_request_link(username, amount, note)
                venmo_web_link = venmo_mgr.generate_web_link(username)
                
                # Update status in database (mark as requested)
                from datetime import datetime
                cursor.execute('''
                    UPDATE payment_requests
                    SET status = 'requested', requested_at = ?
                    WHERE id = ?
                ''', (datetime.now().isoformat(), request_id))
                conn.commit()
                
                # Return the links - client JavaScript will open them on the user's device
                return jsonify({
                    'success': True,
                    'venmo_deep_link': venmo_deep_link,
                    'venmo_link': venmo_web_link,
                    'message': 'Venmo link generated - will open on your device'
                })
            except Exception as e:
                import traceback
                traceback.print_exc()
                return jsonify({'success': False, 'error': str(e)})

        # Excel Export endpoint
        @self.app.route('/api/manager/export-excel', methods=['POST'])
        def export_excel():
            """Export current league night scores to a downloadable .xlsx file."""
            try:
                data = request.get_json()
                session_token = data.get('session_token', '')

                if not self._validate_manager_session(session_token):
                    return jsonify({'success': False, 'error': 'Unauthorized'}), 401

                db = self._get_thread_db()
                if db is None:
                    return jsonify({'success': False, 'error': 'Database connection failed'}), 500

                league_night = db.get_current_league_night()
                if not league_night:
                    return jsonify({'success': False, 'error': 'No active league night'})

                ln_id = league_night['id']
                pairs = db.get_pairs_for_night(ln_id)
                if not pairs:
                    return jsonify({'success': False, 'error': 'No pairs found for current league night'})

                # Build participants list from pairs
                participants = []
                seen_player_ids = set()
                for pair in pairs:
                    for key_prefix in ('player1', 'player2'):
                        pid = pair.get(f'{key_prefix}_id')
                        if pid and pid not in seen_player_ids:
                            seen_player_ids.add(pid)
                            name = pair.get(f'{key_prefix}_name', '')
                            parts = name.split(' ', 1) if name else ['', '']
                            first = parts[0]
                            last = parts[1] if len(parts) > 1 else ''
                            player = db.get_player(pid)
                            participants.append({
                                'first': first,
                                'last': last,
                                'email': player.email if player else '',
                                'buyin_paid': False
                            })

                # Build pairs_data with per-match scores
                # Get all matches for this league night
                conn = db.get_connection()
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM matches WHERE league_night_id = ? ORDER BY round_number, id",
                    (ln_id,)
                )
                matches = [dict(row) for row in cursor.fetchall()]

                match_ids = [m['id'] for m in matches]
                all_games = db.get_games_for_matches(match_ids) if match_ids else {}

                # Map pair_id -> list of per-match scores
                pair_scores = {}  # pair_id -> [score1, score2, ...]
                pair_wins = {}
                pair_losses = {}
                for m in matches:
                    games = all_games.get(m['id'], [])
                    t1_total = sum(g.get('team1_score', 0) or 0 for g in games)
                    t2_total = sum(g.get('team2_score', 0) or 0 for g in games)

                    p1_id = m.get('pair1_id')
                    p2_id = m.get('pair2_id')

                    if p1_id:
                        pair_scores.setdefault(p1_id, []).append(t1_total)
                        pair_wins.setdefault(p1_id, 0)
                        pair_losses.setdefault(p1_id, 0)
                        if m.get('is_complete'):
                            if t1_total > t2_total:
                                pair_wins[p1_id] = pair_wins.get(p1_id, 0) + 1
                            elif t2_total > t1_total:
                                pair_losses[p1_id] = pair_losses.get(p1_id, 0) + 1

                    if p2_id:
                        pair_scores.setdefault(p2_id, []).append(t2_total)
                        pair_wins.setdefault(p2_id, 0)
                        pair_losses.setdefault(p2_id, 0)
                        if m.get('is_complete'):
                            if t2_total > t1_total:
                                pair_wins[p2_id] = pair_wins.get(p2_id, 0) + 1
                            elif t1_total > t2_total:
                                pair_losses[p2_id] = pair_losses.get(p2_id, 0) + 1

                pairs_export = []
                for i, pair in enumerate(pairs, 1):
                    p1_name = pair.get('player1_name', '')
                    p2_name = pair.get('player2_name', '')
                    p1_parts = p1_name.split(' ', 1) if p1_name else ['', '']
                    p2_parts = p2_name.split(' ', 1) if p2_name else ['', '']

                    pid = pair['id']
                    scores = pair_scores.get(pid, [])
                    total = sum(s for s in scores if s)
                    wins = pair_wins.get(pid, 0)
                    losses = pair_losses.get(pid, 0)

                    pairs_export.append({
                        'team_num': i,
                        'player1_first': p1_parts[0],
                        'player1_last': p1_parts[1] if len(p1_parts) > 1 else '',
                        'player2_first': p2_parts[0],
                        'player2_last': p2_parts[1] if len(p2_parts) > 1 else '',
                        'scores': scores,
                        'total': total,
                        'wins': wins,
                        'losses': losses,
                    })

                # Build matchups grouped by round
                pair_id_to_team = {pair['id']: i for i, pair in enumerate(pairs, 1)}
                matchups_export = []
                for m in matches:
                    p1_id = m.get('pair1_id')
                    p2_id = m.get('pair2_id')
                    matchups_export.append({
                        'set_num': m.get('round_number', 1),
                        'team1_num': pair_id_to_team.get(p1_id, ''),
                        'team2_num': pair_id_to_team.get(p2_id, ''),
                    })

                # Determine week name
                notes = league_night.get('notes', '')
                if notes:
                    week_name = notes
                else:
                    cursor.execute(
                        "SELECT COUNT(*) FROM league_nights WHERE id <= ?",
                        (ln_id,)
                    )
                    week_num = cursor.fetchone()[0]
                    date_str = league_night.get('date', '')
                    week_name = f"Week {week_num}" + (f" ({date_str})" if date_str else '')

                from excel_exporter import ExcelExporter
                exporter = ExcelExporter()
                xlsx_bytes = exporter.export_week_data(
                    week_name, participants, pairs_export, matchups_export
                )
                filename = ExcelExporter.safe_filename(week_name)

                return send_file(
                    io.BytesIO(xlsx_bytes),
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    as_attachment=True,
                    download_name=filename
                )
            except Exception as e:
                import traceback
                traceback.print_exc()
                return jsonify({'success': False, 'error': str(e)})

        @self.app.route('/api/manager/trim-queue', methods=['POST'])
        def trim_queue():
            """Remove queued matches where both pairs already have enough games."""
            try:
                data = request.get_json()
                session_token = data.get('session_token', '')
                max_games = int(data.get('max_games', 4))

                if not self._validate_manager_session(session_token):
                    return jsonify({'success': False, 'error': 'Unauthorized'}), 401

                db = self._get_thread_db()
                if db is None:
                    return jsonify({'success': False, 'error': 'Database connection failed'}), 500

                league_night = db.get_current_league_night()
                if not league_night:
                    return jsonify({'success': False, 'error': 'No active league night'})

                deleted = db.trim_excess_queued_matches(league_night['id'], max_games=max_games)
                self.notify_update()

                queue = db.get_queued_matches(league_night['id'])
                return jsonify({'success': True, 'deleted': deleted, 'queue_length': len(queue)})
            except Exception as e:
                import traceback
                traceback.print_exc()
                return jsonify({'success': False, 'error': str(e)}), 500

        # Spectator Reactions API endpoints
        @self.app.route('/api/reaction', methods=['POST'])
        def add_reaction():
            """Add a spectator reaction."""
            # Handle case where reaction manager is not available
            if self.reaction_manager is None:
                return jsonify({'success': False, 'error': 'Reactions not available'})

            try:
                data = request.get_json()
                reaction_type = data.get('type')
                sender = data.get('sender', 'Anonymous')
                client_ip = request.remote_addr

                reaction = self.reaction_manager.add_reaction(reaction_type, sender, client_ip)

                if reaction:
                    return jsonify({
                        'success': True,
                        'reaction': {
                            'id': reaction.id,
                            'emoji': reaction.emoji,
                            'text': reaction.text,
                            'sender': reaction.sender
                        }
                    })
                else:
                    return jsonify({'success': False, 'error': 'Rate limited or invalid reaction type'})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})

        @self.app.route('/api/reactions')
        def get_reactions():
            """Get active reactions."""
            # Handle case where reaction manager is not available
            if self.reaction_manager is None:
                return jsonify({'reactions': []})

            try:
                reactions = self.reaction_manager.get_reaction_json()
                return jsonify({'reactions': reactions})
            except Exception as e:
                return jsonify({'error': str(e)})
    
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

            # Build pair name lookup for tonight's pairs
            pair_name_lookup = {}
            if league_night:
                try:
                    night_pairs = db.get_pairs_for_night(league_night['id'])
                    pair_name_lookup = {p['id']: p.get('pair_name', '') for p in night_pairs}
                except Exception:
                    pass

            for match in matches:
                match_data = self._format_match(match, all_games.get(match['id'], []), pair_name_lookup)

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
                    queue_data.append(self._format_queue_item(match, i + 1, pair_name_lookup))
                
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
            
            # Get full leaderboard (all players)
            leaderboard = db.get_leaderboard_for_season(None, "points")
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
            
            # Get active reactions (if available)
            reactions = self.reaction_manager.get_reaction_json() if self.reaction_manager else []
            
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
                'reactions': reactions,
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
                'reactions': [],
                'total_live': 0,
                'total_completed': 0,
                'total_queued': 0
            }
    
    def _format_match(self, match: dict, games: list, pair_name_lookup: dict = None) -> dict:
        """Format a match for the web display."""
        if pair_name_lookup is None:
            pair_name_lookup = {}

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

        # AI team names from pair lookup
        team1_ai_name = pair_name_lookup.get(match.get('pair1_id'), '')
        team2_ai_name = pair_name_lookup.get(match.get('pair2_id'), '')

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
            'best_of': match.get('best_of', 1),
            'team1_ai_name': team1_ai_name,
            'team2_ai_name': team2_ai_name,
        }
    
    def _format_queue_item(self, match: dict, position: int, pair_name_lookup: dict = None) -> dict:
        """Format a queued match for the web display."""
        if pair_name_lookup is None:
            pair_name_lookup = {}

        team1 = match['team1_p1_name'] or "TBD"
        if match['team1_p2_name']:
            team1 += f" & {match['team1_p2_name']}"

        team2 = match['team2_p1_name'] or "TBD"
        if match['team2_p2_name']:
            team2 += f" & {match['team2_p2_name']}"

        team1_ai_name = pair_name_lookup.get(match.get('pair1_id'), '')
        team2_ai_name = pair_name_lookup.get(match.get('pair2_id'), '')

        return {
            'id': match['id'],
            'position': position,
            'team1': team1,
            'team2': team2,
            'round': match.get('round_number', 1),
            'is_finals': match.get('is_finals', False),
            'team1_ai_name': team1_ai_name,
            'team2_ai_name': team2_ai_name,
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
            
            # Get timeline events for live/recent matches
            timeline = []
            if not match.get('is_complete', False):
                # For live matches, include timeline
                timeline = db.get_match_timeline(match_id)

            return {
                'id': match_id,
                'team1': team1 or 'TBD',
                'team2': team2 or 'TBD',
                'team1_games': t1_wins,
                'team2_games': t2_wins,
                'best_of': match.get('best_of') or 1,
                'is_finals': match.get('is_finals', False),
                'is_complete': match.get('is_complete', False),
                'table': match.get('table_number') or 0,
                'games': games_data,
                'team1_group': current_game_group,  # Current/last game's group assignment
                'timeline': timeline
            }
        except Exception as e:
            return {'error': str(e)}

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
        """Notify connected clients of a data update.

        Increments the version counter and signals waiting SSE clients.
        Thread-safe for concurrent access.
        """
        with self._data_version_lock:
            self._data_version += 1
        # Set and immediately clear the event to wake up all waiting clients
        self._update_event.set()
        self._update_event.clear()
    
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

            # Reset shutdown/update events for a fresh start
            self._shutdown_event.clear()
            self._update_event.clear()

            # Re-register in active servers if a previous stop() removed it
            if self not in _active_servers:
                _active_servers.append(self)

            self.running = True
            self.server_thread = threading.Thread(
                target=self._run_server,
                daemon=True
            )
            self.server_thread.start()

            # Wait for server to be ready (poll instead of blind sleep)
            deadline = time.time() + 5.0
            ready = False
            while time.time() < deadline:
                try:
                    with _socket.create_connection(('127.0.0.1', self.port), timeout=0.2):
                        ready = True
                        break
                except (ConnectionRefusedError, OSError):
                    time.sleep(0.1)

            if not ready:
                self.running = False
                return False, "Server failed to start (port not responding)"

            # Check if ngrok is enabled
            ngrok_enabled = self.db.get_setting('ngrok_enabled', 'false') == 'true'

            if ngrok_enabled and NGROK_AVAILABLE:
                # Try to start ngrok tunnel
                auth_token = self.db.get_setting('ngrok_auth_token', '')
                static_domain = self.db.get_setting('ngrok_static_domain', '')
                success, result = ngrok_helper.start_tunnel(
                    self.port,
                    auth_token if auth_token else None,
                    static_domain if static_domain else None
                )
                if success:
                    return True, result  # Return public ngrok URL
                else:
                    # Ngrok failed, fall back to local
                    print(f"Ngrok tunnel failed: {result}")

            # Return local URL (default or ngrok fallback)
            local_ip = self.get_local_ip()
            url = f"http://{local_ip}:{self.port}"

            return True, url

        except Exception as e:
            self.running = False
            return False, f"Failed to start server: {str(e)}"
    
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
            self._werkzeug_server = make_server('0.0.0.0', self.port, self.app, threaded=True)
            self._werkzeug_server.serve_forever()
        except Exception as e:
            print(f"Web server error: {e}")
            self.running = False
    
    def stop(self):
        """Stop the web server."""
        self.running = False
        self._shutdown_event.set()  # Signal shutdown to SSE streams
        self._update_event.set()  # Wake up any waiting threads

        if self._werkzeug_server:
            self._werkzeug_server.shutdown()
            self._werkzeug_server = None

        # Stop ngrok tunnel if active
        if NGROK_AVAILABLE:
            ngrok_helper.stop_tunnel()

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
