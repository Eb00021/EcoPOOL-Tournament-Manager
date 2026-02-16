"""
EcoPOOL League - Google Sheets Integration
Uploads weekly schedule data (participants, pairs, matchups, scores) to Google Sheets
using a service account.
"""

import logging

_logger = logging.getLogger(__name__)

try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']


class GoogleDriveExporter:
    """Exports league data to Google Sheets via service account credentials."""

    def __init__(self, credentials_path: str):
        if not GOOGLE_API_AVAILABLE:
            raise ImportError(
                "Google API libraries not installed. "
                "Run: pip install google-api-python-client google-auth"
            )
        self.credentials_path = credentials_path
        self._creds = Credentials.from_service_account_file(
            credentials_path, scopes=SCOPES
        )
        self._service = build('sheets', 'v4', credentials=self._creds)
        self._sheets = self._service.spreadsheets()

    def test_connection(self, spreadsheet_id: str) -> tuple:
        """Verify credentials and spreadsheet access.

        Returns:
            (success: bool, message: str)
        """
        try:
            result = self._sheets.get(spreadsheetId=spreadsheet_id).execute()
            title = result.get('properties', {}).get('title', 'Unknown')
            return True, f"Connected to: {title}"
        except Exception as e:
            return False, f"Connection failed: {e}"

    def _get_or_create_sheet(self, spreadsheet_id: str, sheet_name: str) -> int:
        """Get existing sheet ID or create a new one.

        Returns the sheet ID (gid).
        """
        spreadsheet = self._sheets.get(spreadsheetId=spreadsheet_id).execute()
        for sheet in spreadsheet.get('sheets', []):
            if sheet['properties']['title'] == sheet_name:
                return sheet['properties']['sheetId']

        # Create the sheet
        body = {
            'requests': [{
                'addSheet': {
                    'properties': {'title': sheet_name}
                }
            }]
        }
        resp = self._sheets.batchUpdate(
            spreadsheetId=spreadsheet_id, body=body
        ).execute()
        return resp['replies'][0]['addSheet']['properties']['sheetId']

    def upload_week_data(self, spreadsheet_id: str, week_name: str,
                         participants: list, pairs_data: list,
                         matchups: list):
        """Create or update a week sheet matching the Excel format.

        Args:
            spreadsheet_id: Google Sheets file ID
            week_name: Sheet tab name, e.g. "Week 1 (1/29)"
            participants: List of dicts with keys: first, last, email, buyin_paid
            pairs_data: List of dicts with keys:
                team_num, player1_first, player1_last, player2_first, player2_last,
                scores (list of per-match scores), total, wins, losses
            matchups: List of dicts with keys: set_num, team1_num, team2_num
        """
        self._get_or_create_sheet(spreadsheet_id, week_name)

        rows = []

        # ---- Participants section (rows 1-18) ----
        rows.append(['Participants'])
        rows.append(['#', 'First', 'Last', 'Email', 'Buy-In Paid'])
        for i, p in enumerate(participants, 1):
            rows.append([
                i,
                p.get('first', ''),
                p.get('last', ''),
                p.get('email', ''),
                'Yes' if p.get('buyin_paid') else 'No'
            ])
        # Pad to row 19
        while len(rows) < 19:
            rows.append([])

        # ---- Partners section (rows 20-38) ----
        rows.append(['Partners'])
        rows.append(['Team #', 'First', 'Last', 'Match 1', 'Match 2',
                      'Match 3', 'Match 4', 'Total', 'Wins', 'Losses'])
        for pair in pairs_data:
            scores = pair.get('scores', [])
            # Pad scores to 4 entries
            while len(scores) < 4:
                scores.append('')
            # Player 1 row
            rows.append([
                pair.get('team_num', ''),
                pair.get('player1_first', ''),
                pair.get('player1_last', ''),
                scores[0] if scores[0] != '' else '',
                scores[1] if len(scores) > 1 and scores[1] != '' else '',
                scores[2] if len(scores) > 2 and scores[2] != '' else '',
                scores[3] if len(scores) > 3 and scores[3] != '' else '',
                pair.get('total', ''),
                pair.get('wins', ''),
                pair.get('losses', ''),
            ])
            # Player 2 row
            rows.append([
                '',
                pair.get('player2_first', ''),
                pair.get('player2_last', ''),
            ])
        # Pad to row 39
        while len(rows) < 39:
            rows.append([])

        # ---- Matchups section (rows 40-60) ----
        rows.append(['Matchups'])
        rows.append(['Set #', 'Team 1', 'Team 2'])
        for m in matchups:
            rows.append([
                m.get('set_num', ''),
                m.get('team1_num', ''),
                m.get('team2_num', ''),
            ])

        # Write all data in one batch
        range_str = f"'{week_name}'!A1"
        body = {'values': rows}
        self._sheets.values().update(
            spreadsheetId=spreadsheet_id,
            range=range_str,
            valueInputOption='RAW',
            body=body
        ).execute()

        _logger.info(f"Uploaded week data to sheet '{week_name}'")
