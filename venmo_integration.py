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
                               amount: float, note: str = None) -> int:
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
        return cursor.lastrowid

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

    def mark_as_paid(self, request_id: int, txn_id: str = None):
        """Mark a payment request as paid."""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE payment_requests
            SET status = 'paid', paid_at = ?, venmo_txn_id = ?
            WHERE id = ?
        ''', (datetime.now().isoformat(), txn_id, request_id))

        conn.commit()

        # Also update the buy-in record if it exists
        cursor.execute('''
            SELECT league_night_id, player_id FROM payment_requests WHERE id = ?
        ''', (request_id,))
        row = cursor.fetchone()
        if row:
            self.db.mark_buyin_paid(row['league_night_id'], row['player_id'], True, True)

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
