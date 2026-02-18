"""
EcoPOOL League - Excel Export
Exports weekly schedule data (participants, pairs, matchups, scores) to an .xlsx file.
"""

import io
import re
import logging

import openpyxl

_logger = logging.getLogger(__name__)


class ExcelExporter:
    """Exports league data to an in-memory .xlsx file."""

    def export_week_data(self, week_name: str, participants: list,
                         pairs_data: list, matchups: list) -> bytes:
        """Build a workbook matching the Google Sheets layout and return raw bytes.

        Args:
            week_name: Sheet tab name, e.g. "Week 1 (1/29)"
            participants: List of dicts with keys: first, last, email, buyin_paid
            pairs_data: List of dicts with keys:
                team_num, player1_first, player1_last, player2_first, player2_last,
                scores (list of per-match scores), total, wins, losses
            matchups: List of dicts with keys: set_num, team1_num, team2_num

        Returns:
            Raw bytes of the .xlsx file.
        """
        wb = openpyxl.Workbook()
        sheet_title = week_name[:31]  # Excel tab name limit
        ws = wb.active
        ws.title = sheet_title

        rows = []

        # ---- Participants section (rows 1-19) ----
        rows.append(['Participants'])
        rows.append(['#', 'First', 'Last', 'Email', 'Buy-In Paid'])
        for i, p in enumerate(participants, 1):
            rows.append([
                i,
                p.get('first', ''),
                p.get('last', ''),
                p.get('email', ''),
                'Yes' if p.get('buyin_paid') else 'No',
            ])
        # Pad to row 19
        while len(rows) < 19:
            rows.append([])

        # ---- Partners section (rows 20-39) ----
        rows.append(['Partners'])
        rows.append(['Team #', 'First', 'Last', 'Match 1', 'Match 2',
                      'Match 3', 'Match 4', 'Total', 'Wins', 'Losses'])
        for pair in pairs_data:
            scores = list(pair.get('scores', []))
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

        # ---- Matchups section (rows 40+) ----
        rows.append(['Matchups'])
        rows.append(['Set #', 'Team 1', 'Team 2'])
        for m in matchups:
            rows.append([
                m.get('set_num', ''),
                m.get('team1_num', ''),
                m.get('team2_num', ''),
            ])

        for row in rows:
            ws.append(row)

        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        _logger.info(f"Exported week data to Excel for '{week_name}'")
        return buf.read()

    @staticmethod
    def safe_filename(week_name: str) -> str:
        """Convert week_name to a safe filename (no spaces or parens)."""
        name = re.sub(r'[\s()]+', '_', week_name).strip('_')
        return f"{name}.xlsx"
