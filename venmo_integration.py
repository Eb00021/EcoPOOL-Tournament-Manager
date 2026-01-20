"""
EcoPOOL League - Venmo Integration Module
Handles Venmo deep links for payment requests and tracking.

Note: Venmo does not have a public API for sending payment requests.
This module uses deep links which open the Venmo app with pre-filled info.
"""

import webbrowser
import urllib.parse
import platform
import sys
from dataclasses import dataclass
from typing import Optional, List, Dict
from datetime import datetime


@dataclass
class PaymentRequest:
    """Represents a payment request."""
    id: Optional[int]
    league_night_id: int
    player_id: int
    amount: float
    note: str
    status: str  # 'pending', 'requested', 'paid', 'cancelled'
    requested_at: Optional[str]
    paid_at: Optional[str]
    venmo_txn_id: Optional[str]


class VenmoIntegration:
    """Handles Venmo integration for buy-ins and payments."""

    def __init__(self, db_manager):
        self.db = db_manager
        self._init_tables()
        self.default_note = "EcoPOOL League Buy-In"

    def _init_tables(self):
        """Initialize payment tracking tables."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payment_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                league_night_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                note TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                requested_at TEXT,
                paid_at TEXT,
                venmo_txn_id TEXT,
                FOREIGN KEY (league_night_id) REFERENCES league_nights(id),
                FOREIGN KEY (player_id) REFERENCES players(id)
            )
        ''')

        # Payment audit log table for tracking all changes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS payment_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                payment_request_id INTEGER,
                league_night_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                old_status TEXT,
                new_status TEXT,
                amount REAL,
                note TEXT,
                performed_by TEXT DEFAULT 'system',
                performed_at TEXT NOT NULL,
                details TEXT,
                FOREIGN KEY (league_night_id) REFERENCES league_nights(id),
                FOREIGN KEY (player_id) REFERENCES players(id)
            )
        ''')

        conn.commit()

    # ============ Deep Link Generation ============

    @staticmethod
    def generate_payment_link(venmo_username: str, amount: float, note: str = "") -> str:
        """Generate a Venmo payment deep link.

        This link opens the Venmo app with pre-filled payment info.
        Works on mobile devices with Venmo installed.

        Args:
            venmo_username: Recipient's Venmo username (without @)
            amount: Payment amount in dollars
            note: Payment note/description

        Returns:
            Venmo deep link URL
        """
        # Clean up username (remove @ if present)
        username = venmo_username.lstrip('@')

        # URL encode the note
        encoded_note = urllib.parse.quote(note)

        # Venmo deep link format
        # venmo://paycharge?txn=pay&recipients={username}&amount={amount}&note={note}
        deep_link = f"venmo://paycharge?txn=pay&recipients={username}&amount={amount}&note={encoded_note}"

        return deep_link

    @staticmethod
    def generate_request_link(venmo_username: str, amount: float, note: str = "") -> str:
        """Generate a Venmo payment request deep link.

        This link opens the Venmo app to request money.
        Note: This opens YOUR Venmo to create a request to send to them.

        Args:
            venmo_username: Person to request money from (without @)
            amount: Request amount in dollars
            note: Request note/description

        Returns:
            Venmo deep link URL
        """
        username = venmo_username.lstrip('@')
        encoded_note = urllib.parse.quote(note)

        # Request link uses txn=charge
        deep_link = f"venmo://paycharge?txn=charge&recipients={username}&amount={amount}&note={encoded_note}"

        return deep_link

    @staticmethod
    def generate_web_link(venmo_username: str) -> str:
        """Generate a Venmo web profile link.

        Fallback for when app isn't installed.

        Args:
            venmo_username: Venmo username (without @)

        Returns:
            Venmo web URL
        """
        username = venmo_username.lstrip('@')
        return f"https://venmo.com/u/{username}"

    @staticmethod
    def generate_qr_payment_data(venmo_username: str, amount: float, note: str = "") -> str:
        """Generate data for a Venmo QR code.

        Players can scan this to pay quickly.

        Returns:
            URL to encode in QR code
        """
        username = venmo_username.lstrip('@')
        encoded_note = urllib.parse.quote(note)
        return f"https://venmo.com/{username}?txn=pay&amount={amount}&note={encoded_note}"

    # ============ Payment Request Management ============

    def create_payment_request(self, league_night_id: int, player_id: int,
                               amount: float, note: str = None,
                               performed_by: str = 'system') -> int:
        """Create a new payment request record.

        Returns:
            Request ID
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        if note is None:
            note = self.default_note

        cursor.execute('''
            INSERT INTO payment_requests (league_night_id, player_id, amount, note, status)
            VALUES (?, ?, ?, ?, 'pending')
        ''', (league_night_id, player_id, amount, note))

        conn.commit()
        request_id = cursor.lastrowid

        # Log to audit trail
        self._log_audit(
            payment_request_id=request_id,
            league_night_id=league_night_id,
            player_id=player_id,
            action='created',
            new_status='pending',
            amount=amount,
            note=note,
            performed_by=performed_by
        )

        return request_id

    def send_payment_request(self, request_id: int) -> bool:
        """Mark a payment request as sent and open Venmo.

        On desktop (Windows/Mac/Linux), falls back to web version if deep link fails.
        On mobile, uses deep link to open Venmo app.

        Returns:
            True if Venmo link was opened successfully
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Get request details
        cursor.execute('''
            SELECT pr.*, p.venmo, p.name
            FROM payment_requests pr
            JOIN players p ON pr.player_id = p.id
            WHERE pr.id = ?
        ''', (request_id,))

        row = cursor.fetchone()
        if not row or not row['venmo']:
            return False

        username = row['venmo'].lstrip('@')
        amount = row['amount']
        note = row['note'] or f"EcoPOOL Buy-In - {row['name']}"

        # On desktop platforms, deep links often don't work
        # Use web link as fallback or primary method
        is_desktop = platform.system() in ('Windows', 'Darwin', 'Linux')
        
        if is_desktop:
            # On desktop, open web version with payment link
            # Venmo web doesn't support deep links, so we'll open their profile
            # and show a message with instructions
            web_link = self.generate_web_link(username)
            try:
                webbrowser.open(web_link)
                
                # Update status
                cursor.execute('''
                    UPDATE payment_requests
                    SET status = 'requested', requested_at = ?
                    WHERE id = ?
                ''', (datetime.now().isoformat(), request_id))
                
                conn.commit()
                return True
            except Exception:
                return False
        else:
            # On mobile, try deep link first
            deep_link = self.generate_request_link(username, amount, note)
            try:
                webbrowser.open(deep_link)
                
                # Update status
                cursor.execute('''
                    UPDATE payment_requests
                    SET status = 'requested', requested_at = ?
                    WHERE id = ?
                ''', (datetime.now().isoformat(), request_id))
                
                conn.commit()
                return True
            except Exception:
                # Fallback to web if deep link fails
                web_link = self.generate_web_link(username)
                try:
                    webbrowser.open(web_link)
                    cursor.execute('''
                        UPDATE payment_requests
                        SET status = 'requested', requested_at = ?
                        WHERE id = ?
                    ''', (datetime.now().isoformat(), request_id))
                    conn.commit()
                    return True
                except Exception:
                    return False

    def mark_as_paid(self, request_id: int, txn_id: str = None, performed_by: str = 'system'):
        """Mark a payment request as paid."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Get current info for audit log
        cursor.execute('''
            SELECT pr.*, p.name as player_name
            FROM payment_requests pr
            JOIN players p ON pr.player_id = p.id
            WHERE pr.id = ?
        ''', (request_id,))
        request = cursor.fetchone()

        if not request:
            return

        old_status = request['status']

        cursor.execute('''
            UPDATE payment_requests
            SET status = 'paid', paid_at = ?, venmo_txn_id = ?
            WHERE id = ?
        ''', (datetime.now().isoformat(), txn_id, request_id))

        conn.commit()

        # Log to audit trail
        self._log_audit(
            payment_request_id=request_id,
            league_night_id=request['league_night_id'],
            player_id=request['player_id'],
            action='marked_paid',
            old_status=old_status,
            new_status='paid',
            amount=request['amount'],
            performed_by=performed_by,
            details=f"Transaction ID: {txn_id}" if txn_id else None
        )

        # Also update the buy-in record if it exists
        self.db.mark_buyin_paid(request['league_night_id'], request['player_id'], True, True)

    def get_pending_requests(self, league_night_id: int) -> List[Dict]:
        """Get all pending payment requests for a league night."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT pr.*, p.name, p.venmo, p.email
            FROM payment_requests pr
            JOIN players p ON pr.player_id = p.id
            WHERE pr.league_night_id = ? AND pr.status IN ('pending', 'requested')
            ORDER BY p.name
        ''', (league_night_id,))

        return [dict(row) for row in cursor.fetchall()]

    def get_all_requests(self, league_night_id: int) -> List[Dict]:
        """Get all payment requests for a league night."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT pr.*, p.name, p.venmo, p.email
            FROM payment_requests pr
            JOIN players p ON pr.player_id = p.id
            WHERE pr.league_night_id = ?
            ORDER BY
                CASE pr.status
                    WHEN 'pending' THEN 1
                    WHEN 'requested' THEN 2
                    WHEN 'paid' THEN 3
                    ELSE 4
                END,
                p.name
        ''', (league_night_id,))

        return [dict(row) for row in cursor.fetchall()]

    def get_league_night_payments(self, league_night_id: int) -> List[Dict]:
        """Get all payments/buy-ins for a league night with player details.

        Returns data from league_night_buyins table for API compatibility.
        """
        return self.db.get_buyins_for_night(league_night_id)

    # ============ Bulk Operations ============

    def create_bulk_requests(self, league_night_id: int, player_ids: List[int],
                            amount: float, note: str = None) -> List[int]:
        """Create payment requests for multiple players.

        Returns:
            List of created request IDs
        """
        request_ids = []
        for player_id in player_ids:
            req_id = self.create_payment_request(league_night_id, player_id, amount, note)
            request_ids.append(req_id)
        return request_ids

    def open_bulk_requests(self, request_ids: List[int], delay_ms: int = 500):
        """Open Venmo for multiple requests with delay between each.

        Note: This opens multiple Venmo windows/tabs. Use sparingly.
        """
        import time

        for i, req_id in enumerate(request_ids):
            if i > 0:
                time.sleep(delay_ms / 1000)
            self.send_payment_request(req_id)

    def generate_payment_summary(self, league_night_id: int) -> Dict:
        """Generate payment summary for a league night."""
        requests = self.get_all_requests(league_night_id)

        total_expected = sum(r['amount'] for r in requests)
        total_paid = sum(r['amount'] for r in requests if r['status'] == 'paid')
        total_pending = sum(r['amount'] for r in requests if r['status'] in ('pending', 'requested'))

        return {
            'total_requests': len(requests),
            'paid_count': len([r for r in requests if r['status'] == 'paid']),
            'pending_count': len([r for r in requests if r['status'] in ('pending', 'requested')]),
            'total_expected': total_expected,
            'total_paid': total_paid,
            'total_pending': total_pending,
            'collection_rate': (total_paid / total_expected * 100) if total_expected > 0 else 0,
            'requests': requests
        }

    # ============ QR Code Generation ============

    def generate_collection_qr(self, organizer_venmo: str, amount: float,
                               league_night_id: int = None) -> Optional[str]:
        """Generate a QR code for players to scan and pay.

        Returns:
            Base64 encoded QR code image data, or None if qrcode not installed
        """
        try:
            import qrcode
            from io import BytesIO
            import base64

            # Get league night date for the note
            note = "EcoPOOL Buy-In"
            if league_night_id:
                night = self.db.get_league_night(league_night_id)
                if night:
                    note = f"EcoPOOL Buy-In - {night.get('date', '')}"

            url = self.generate_qr_payment_data(organizer_venmo, amount, note)

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=2
            )
            qr.add_data(url)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")

            buffer = BytesIO()
            img.save(buffer, format='PNG')
            qr_data = base64.b64encode(buffer.getvalue()).decode()

            return qr_data

        except ImportError:
            return None

    # ============ Utility Methods ============

    @staticmethod
    def validate_venmo_username(username: str) -> bool:
        """Validate a Venmo username format.

        Venmo usernames:
        - 5-30 characters
        - Can contain letters, numbers, underscores, hyphens
        - Cannot start with number
        """
        if not username:
            return False

        username = username.lstrip('@')

        if len(username) < 5 or len(username) > 30:
            return False

        if username[0].isdigit():
            return False

        allowed_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-')
        return all(c in allowed_chars for c in username)

    @staticmethod
    def format_venmo_username(username: str) -> str:
        """Format a Venmo username for display (with @)."""
        if not username:
            return ""
        return f"@{username.lstrip('@')}"

    def open_player_venmo(self, player_id: int):
        """Open a player's Venmo profile in browser/app."""
        player = self.db.get_player(player_id)
        if player and player.venmo:
            link = self.generate_web_link(player.venmo)
            webbrowser.open(link)
            return True
        return False

    # ============ Audit Trail ============

    def _log_audit(self, payment_request_id: Optional[int], league_night_id: int,
                   player_id: int, action: str, old_status: str = None,
                   new_status: str = None, amount: float = None,
                   note: str = None, performed_by: str = 'system', details: str = None):
        """Log a payment action to the audit trail."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO payment_audit_log
            (payment_request_id, league_night_id, player_id, action, old_status,
             new_status, amount, note, performed_by, performed_at, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (payment_request_id, league_night_id, player_id, action, old_status,
              new_status, amount, note, performed_by, datetime.now().isoformat(), details))

        conn.commit()

    def get_audit_log(self, league_night_id: int = None, player_id: int = None,
                      limit: int = 100) -> List[Dict]:
        """Get audit log entries with optional filters."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        query = '''
            SELECT al.*, p.name as player_name, ln.date as league_night_date
            FROM payment_audit_log al
            LEFT JOIN players p ON al.player_id = p.id
            LEFT JOIN league_nights ln ON al.league_night_id = ln.id
            WHERE 1=1
        '''
        params = []

        if league_night_id:
            query += ' AND al.league_night_id = ?'
            params.append(league_night_id)

        if player_id:
            query += ' AND al.player_id = ?'
            params.append(player_id)

        query += ' ORDER BY al.performed_at DESC LIMIT ?'
        params.append(limit)

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    # ============ Payment Analytics ============

    def get_payment_analytics(self, season_id: int = None) -> Dict:
        """Get comprehensive payment analytics."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Get all league nights for the season
        if season_id:
            cursor.execute('''
                SELECT id, date FROM league_nights
                WHERE season_id = ?
                ORDER BY date
            ''', (season_id,))
        else:
            cursor.execute('''
                SELECT id, date FROM league_nights
                ORDER BY date DESC
                LIMIT 20
            ''')

        nights = cursor.fetchall()
        night_ids = [n['id'] for n in nights]

        if not night_ids:
            return {
                'total_expected': 0,
                'total_collected': 0,
                'collection_rate': 0,
                'by_night': [],
                'by_player': [],
                'trends': []
            }

        # Calculate totals
        placeholders = ','.join('?' * len(night_ids))
        cursor.execute(f'''
            SELECT
                COALESCE(SUM(amount), 0) as total_expected,
                COALESCE(SUM(CASE WHEN paid = 1 THEN amount ELSE 0 END), 0) as total_collected
            FROM league_night_buyins
            WHERE league_night_id IN ({placeholders})
        ''', night_ids)

        totals = cursor.fetchone()
        total_expected = totals['total_expected']
        total_collected = totals['total_collected']
        collection_rate = (total_collected / total_expected * 100) if total_expected > 0 else 0

        # Per-night breakdown
        cursor.execute(f'''
            SELECT
                b.league_night_id,
                ln.date,
                COUNT(*) as player_count,
                SUM(b.amount) as expected,
                SUM(CASE WHEN b.paid = 1 THEN b.amount ELSE 0 END) as collected,
                SUM(CASE WHEN b.paid = 1 THEN 1 ELSE 0 END) as paid_count
            FROM league_night_buyins b
            JOIN league_nights ln ON b.league_night_id = ln.id
            WHERE b.league_night_id IN ({placeholders})
            GROUP BY b.league_night_id
            ORDER BY ln.date
        ''', night_ids)

        by_night = []
        for row in cursor.fetchall():
            by_night.append({
                'league_night_id': row['league_night_id'],
                'date': row['date'],
                'player_count': row['player_count'],
                'expected': row['expected'],
                'collected': row['collected'],
                'paid_count': row['paid_count'],
                'collection_rate': (row['collected'] / row['expected'] * 100) if row['expected'] > 0 else 0
            })

        # Per-player breakdown
        cursor.execute(f'''
            SELECT
                b.player_id,
                p.name as player_name,
                COUNT(*) as nights_attended,
                SUM(b.amount) as total_owed,
                SUM(CASE WHEN b.paid = 1 THEN b.amount ELSE 0 END) as total_paid,
                SUM(CASE WHEN b.paid = 0 THEN b.amount ELSE 0 END) as outstanding
            FROM league_night_buyins b
            JOIN players p ON b.player_id = p.id
            WHERE b.league_night_id IN ({placeholders})
            GROUP BY b.player_id
            ORDER BY outstanding DESC, p.name
        ''', night_ids)

        by_player = []
        for row in cursor.fetchall():
            by_player.append({
                'player_id': row['player_id'],
                'player_name': row['player_name'],
                'nights_attended': row['nights_attended'],
                'total_owed': row['total_owed'],
                'total_paid': row['total_paid'],
                'outstanding': row['outstanding'],
                'payment_rate': (row['total_paid'] / row['total_owed'] * 100) if row['total_owed'] > 0 else 0
            })

        # Trends (collection rate over time)
        trends = [{'date': n['date'], 'rate': n['collection_rate']} for n in by_night]

        return {
            'total_expected': total_expected,
            'total_collected': total_collected,
            'collection_rate': round(collection_rate, 1),
            'outstanding': total_expected - total_collected,
            'by_night': by_night,
            'by_player': by_player,
            'trends': trends
        }

    def get_season_summary(self, season_id: int = None) -> Dict:
        """Get a comprehensive season payment summary.

        Args:
            season_id: Season ID to filter by. If 0, returns all league nights
                      regardless of season. If None, uses most recent season.
        """
        conn = self.db.get_connection()
        cursor = conn.cursor()

        # Handle "all seasons" case (season_id = 0)
        if season_id == 0:
            # Get all league nights regardless of season
            cursor.execute('''
                SELECT id, date FROM league_nights
                ORDER BY date
            ''')
            nights = [dict(row) for row in cursor.fetchall()]
            night_ids = [n['id'] for n in nights]

            # Create a synthetic "all seasons" record
            season = {'id': 0, 'name': 'All Seasons', 'is_active': 0, 'start_date': None, 'end_date': None}
        else:
            # Get season info
            if season_id:
                cursor.execute('SELECT * FROM seasons WHERE id = ?', (season_id,))
            else:
                cursor.execute('SELECT * FROM seasons ORDER BY start_date DESC LIMIT 1')

            season = cursor.fetchone()
            if not season:
                return {'error': 'No season found'}

            season_id = season['id']

            # Get all league nights for this season
            cursor.execute('''
                SELECT id, date FROM league_nights
                WHERE season_id = ?
                ORDER BY date
            ''', (season_id,))

            nights = [dict(row) for row in cursor.fetchall()]
            night_ids = [n['id'] for n in nights]

        if not night_ids:
            return {
                'season': dict(season),
                'total_nights': 0,
                'total_players': 0,
                'total_expected': 0,
                'total_collected': 0,
                'collection_rate': 0,
                'outstanding': 0,
                'nights': [],
                'player_standings': []
            }

        placeholders = ','.join('?' * len(night_ids))

        # Get unique players from buyins
        cursor.execute(f'''
            SELECT COUNT(DISTINCT player_id) as count
            FROM league_night_buyins
            WHERE league_night_id IN ({placeholders})
        ''', night_ids)
        total_players_buyins = cursor.fetchone()['count']

        # Get totals from buyins
        cursor.execute(f'''
            SELECT
                COALESCE(SUM(amount), 0) as total_expected,
                COALESCE(SUM(CASE WHEN paid = 1 THEN amount ELSE 0 END), 0) as total_collected
            FROM league_night_buyins
            WHERE league_night_id IN ({placeholders})
        ''', night_ids)

        totals = cursor.fetchone()

        # Get per-night details
        cursor.execute(f'''
            SELECT
                ln.id,
                ln.date,
                COUNT(b.id) as player_count,
                COALESCE(SUM(b.amount), 0) as expected,
                COALESCE(SUM(CASE WHEN b.paid = 1 THEN b.amount ELSE 0 END), 0) as collected
            FROM league_nights ln
            LEFT JOIN league_night_buyins b ON ln.id = b.league_night_id
            WHERE ln.id IN ({placeholders})
            GROUP BY ln.id
            ORDER BY ln.date
        ''', night_ids)

        night_details = []
        for row in cursor.fetchall():
            rate = (row['collected'] / row['expected'] * 100) if row['expected'] > 0 else 0
            night_details.append({
                'id': row['id'],
                'date': row['date'],
                'player_count': row['player_count'],
                'expected': row['expected'],
                'collected': row['collected'],
                'collection_rate': round(rate, 1)
            })

        # Get player payment standings from buyins
        cursor.execute(f'''
            SELECT
                p.id,
                p.name,
                p.venmo,
                COUNT(b.id) as nights_played,
                COALESCE(SUM(b.amount), 0) as total_owed,
                COALESCE(SUM(CASE WHEN b.paid = 1 THEN b.amount ELSE 0 END), 0) as total_paid
            FROM players p
            JOIN league_night_buyins b ON p.id = b.player_id
            WHERE b.league_night_id IN ({placeholders})
            GROUP BY p.id
            ORDER BY (COALESCE(SUM(b.amount), 0) - COALESCE(SUM(CASE WHEN b.paid = 1 THEN b.amount ELSE 0 END), 0)) DESC
        ''', night_ids)

        player_standings = []
        for row in cursor.fetchall():
            outstanding = row['total_owed'] - row['total_paid']
            rate = (row['total_paid'] / row['total_owed'] * 100) if row['total_owed'] > 0 else 0
            player_standings.append({
                'id': row['id'],
                'name': row['name'],
                'venmo': row['venmo'],
                'nights_played': row['nights_played'],
                'total_owed': row['total_owed'],
                'total_paid': row['total_paid'],
                'outstanding': outstanding,
                'payment_rate': round(rate, 1)
            })

        # If no buyins exist yet, get players from matches instead
        # This allows the admin page to show players who have played even before buy-ins are created
        if not player_standings:
            # Get the default buy-in amount from settings
            default_buyin = float(self.db.get_setting('default_buyin', '5'))
            
            # Count how many nights each player participated in
            cursor.execute(f'''
                SELECT player_id, COUNT(DISTINCT league_night_id) as nights_count
                FROM (
                    SELECT team1_player1_id as player_id, league_night_id FROM matches WHERE league_night_id IN ({placeholders}) AND team1_player1_id IS NOT NULL
                    UNION ALL SELECT team1_player2_id, league_night_id FROM matches WHERE league_night_id IN ({placeholders}) AND team1_player2_id IS NOT NULL
                    UNION ALL SELECT team2_player1_id, league_night_id FROM matches WHERE league_night_id IN ({placeholders}) AND team2_player1_id IS NOT NULL
                    UNION ALL SELECT team2_player2_id, league_night_id FROM matches WHERE league_night_id IN ({placeholders}) AND team2_player2_id IS NOT NULL
                )
                GROUP BY player_id
            ''', night_ids * 4)
            
            player_nights = {row['player_id']: row['nights_count'] for row in cursor.fetchall()}
            
            cursor.execute(f'''
                SELECT DISTINCT p.id, p.name, p.venmo
                FROM players p
                WHERE p.id IN (
                    SELECT team1_player1_id FROM matches WHERE league_night_id IN ({placeholders}) AND team1_player1_id IS NOT NULL
                    UNION SELECT team1_player2_id FROM matches WHERE league_night_id IN ({placeholders}) AND team1_player2_id IS NOT NULL
                    UNION SELECT team2_player1_id FROM matches WHERE league_night_id IN ({placeholders}) AND team2_player1_id IS NOT NULL
                    UNION SELECT team2_player2_id FROM matches WHERE league_night_id IN ({placeholders}) AND team2_player2_id IS NOT NULL
                )
                ORDER BY p.name
            ''', night_ids * 4)

            for row in cursor.fetchall():
                nights_played = player_nights.get(row['id'], 1)
                total_owed = default_buyin * nights_played
                player_standings.append({
                    'id': row['id'],
                    'name': row['name'],
                    'venmo': row['venmo'],
                    'nights_played': nights_played,
                    'total_owed': total_owed,
                    'total_paid': 0,
                    'outstanding': total_owed,  # Default to unpaid
                    'payment_rate': 0
                })

        # If still no players from matches, get all active players
        if not player_standings:
            default_buyin = float(self.db.get_setting('default_buyin', '5'))
            cursor.execute('''
                SELECT id, name, venmo FROM players
                WHERE active = 1
                ORDER BY name
            ''')
            for row in cursor.fetchall():
                player_standings.append({
                    'id': row['id'],
                    'name': row['name'],
                    'venmo': row['venmo'],
                    'nights_played': 1,
                    'total_owed': default_buyin,
                    'total_paid': 0,
                    'outstanding': default_buyin,  # Default to unpaid
                    'payment_rate': 0
                })

        total_players = total_players_buyins if total_players_buyins > 0 else len(player_standings)
        
        # If we have buyins, use those totals; otherwise calculate from player_standings
        if totals['total_expected'] > 0:
            total_expected = totals['total_expected']
            total_collected = totals['total_collected']
        else:
            # Calculate from player standings (fallback data)
            total_expected = sum(p['total_owed'] for p in player_standings)
            total_collected = sum(p['total_paid'] for p in player_standings)
        
        outstanding = total_expected - total_collected
        collection_rate = (total_collected / total_expected * 100) if total_expected > 0 else 0

        return {
            'season': dict(season),
            'total_nights': len(nights),
            'total_players': total_players,
            'total_expected': total_expected,
            'total_collected': total_collected,
            'outstanding': outstanding,
            'collection_rate': round(collection_rate, 1),
            'nights': night_details,
            'player_standings': player_standings
        }
