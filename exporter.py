"""
EcoPOOL League - Export Module
Export scorecards, stats, and reports to PDF and CSV/Excel.
"""

import os
from datetime import datetime
from typing import Optional
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import csv
import json

from database import DatabaseManager


class Exporter:
    def __init__(self, db: DatabaseManager):
        self.db = db
        self.styles = getSampleStyleSheet()
        
        # Custom styles
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor=colors.HexColor('#1a5f2a')
        )
        
        self.subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=self.styles['Heading2'],
            fontSize=16,
            spaceAfter=12,
            textColor=colors.HexColor('#2d7a3e')
        )
        
        self.header_style = ParagraphStyle(
            'TableHeader',
            parent=self.styles['Normal'],
            fontSize=11,
            textColor=colors.white,
            alignment=TA_CENTER
        )
    
    def export_scorecard_pdf(self, match_id: int, filepath: str) -> bool:
        """Export a match scorecard to PDF."""
        try:
            match = self.db.get_match(match_id)
            if not match:
                return False
            
            games = self.db.get_games_for_match(match_id)
            
            doc = SimpleDocTemplate(filepath, pagesize=letter)
            elements = []
            
            # Title
            elements.append(Paragraph("WVU EcoPOOL League", self.title_style))
            elements.append(Paragraph("Match Scorecard", self.subtitle_style))
            elements.append(Spacer(1, 20))
            
            # Match info
            team1_name = match['team1_p1_name']
            if match['team1_p2_name']:
                team1_name += f" & {match['team1_p2_name']}"
            
            team2_name = match['team2_p1_name']
            if match['team2_p2_name']:
                team2_name += f" & {match['team2_p2_name']}"
            
            match_info = [
                ['Date:', match['date'][:10] if match['date'] else 'N/A'],
                ['Table:', f"Table {match['table_number']}"],
                ['Format:', f"Best of {match['best_of']}"],
                ['Type:', 'Finals' if match['is_finals'] else 'Regular'],
            ]
            
            info_table = Table(match_info, colWidths=[1.5*inch, 3*inch])
            info_table.setStyle(TableStyle([
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 11),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ]))
            elements.append(info_table)
            elements.append(Spacer(1, 20))
            
            # Teams header
            teams_header = [[
                Paragraph(f"<b>Team 1</b><br/>{team1_name}", self.styles['Normal']),
                'VS',
                Paragraph(f"<b>Team 2</b><br/>{team2_name}", self.styles['Normal']),
            ]]
            
            teams_table = Table(teams_header, colWidths=[2.5*inch, 1*inch, 2.5*inch])
            teams_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTSIZE', (1, 0), (1, 0), 16),
                ('FONTNAME', (1, 0), (1, 0), 'Helvetica-Bold'),
                ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#e8f5e9')),
                ('BACKGROUND', (2, 0), (2, 0), colors.HexColor('#e3f2fd')),
                ('BOX', (0, 0), (-1, -1), 1, colors.grey),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ('TOPPADDING', (0, 0), (-1, -1), 15),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
            ]))
            elements.append(teams_table)
            elements.append(Spacer(1, 20))
            
            # Games results
            if games:
                elements.append(Paragraph("Game Results", self.subtitle_style))
                
                game_data = [['Game', 'Team 1 Score', 'Team 2 Score', 'Winner', 'Notes']]
                
                team1_wins = 0
                team2_wins = 0
                
                for game in games:
                    winner = '-'
                    notes = []
                    
                    if game['winner_team'] == 1:
                        winner = 'Team 1'
                        team1_wins += 1
                    elif game['winner_team'] == 2:
                        winner = 'Team 2'
                        team2_wins += 1
                    
                    if game['golden_break']:
                        notes.append('Golden Break!')
                    if game['early_8ball_team']:
                        notes.append(f'Early 8-ball (Team {game["early_8ball_team"]})')
                    
                    game_data.append([
                        f"Game {game['game_number']}",
                        str(game['team1_score']),
                        str(game['team2_score']),
                        winner,
                        ', '.join(notes) if notes else '-'
                    ])
                
                # Add totals row
                game_data.append([
                    'TOTAL',
                    f"{team1_wins} wins",
                    f"{team2_wins} wins",
                    'Team 1' if team1_wins > team2_wins else ('Team 2' if team2_wins > team1_wins else 'Tie'),
                    ''
                ])
                
                game_table = Table(game_data, colWidths=[1*inch, 1.2*inch, 1.2*inch, 1*inch, 2*inch])
                game_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5f2a')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
                    ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f5f5f5')),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('BOX', (0, 0), (-1, -1), 1, colors.black),
                    ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ]))
                elements.append(game_table)
            
            elements.append(Spacer(1, 30))
            
            # Footer
            footer = Paragraph(
                f"<i>Generated by EcoPOOL League Manager - {datetime.now().strftime('%Y-%m-%d %H:%M')}</i>",
                ParagraphStyle('Footer', parent=self.styles['Normal'], fontSize=9, 
                              textColor=colors.grey, alignment=TA_CENTER)
            )
            elements.append(footer)
            
            doc.build(elements)
            return True
            
        except Exception as e:
            print(f"Error exporting scorecard: {e}")
            return False
    
    def export_leaderboard_pdf(self, filepath: str, sort_by: str = "wins") -> bool:
        """Export leaderboard to PDF."""
        try:
            players = self.db.get_leaderboard(sort_by)
            
            doc = SimpleDocTemplate(filepath, pagesize=letter)
            elements = []
            
            # Title
            elements.append(Paragraph("WVU EcoPOOL League", self.title_style))
            elements.append(Paragraph("Player Leaderboard", self.subtitle_style))
            elements.append(Paragraph(
                f"<i>As of {datetime.now().strftime('%B %d, %Y')}</i>",
                ParagraphStyle('Date', parent=self.styles['Normal'], 
                              alignment=TA_CENTER, textColor=colors.grey)
            ))
            elements.append(Spacer(1, 20))
            
            # Leaderboard table
            data = [['Rank', 'Player', 'Games', 'Wins', 'Win %', 'Total Pts', 'Avg Pts', 'Golden']]
            
            for i, player in enumerate(players, 1):
                data.append([
                    str(i),
                    player.name,
                    str(player.games_played),
                    str(player.games_won),
                    f"{player.win_rate:.1f}%",
                    str(player.total_points),
                    f"{player.avg_points:.1f}",
                    str(player.golden_breaks)
                ])
            
            if not players:
                data.append(['', 'No players found', '', '', '', '', '', ''])
            
            table = Table(data, colWidths=[0.5*inch, 1.8*inch, 0.7*inch, 0.6*inch, 
                                           0.7*inch, 0.8*inch, 0.7*inch, 0.7*inch])
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5f2a')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('BOX', (0, 0), (-1, -1), 1, colors.black),
                ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                # Highlight top 3
                ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#ffd700')) if len(players) >= 1 else (),
                ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#c0c0c0')) if len(players) >= 2 else (),
                ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#cd7f32')) if len(players) >= 3 else (),
            ]))
            elements.append(table)
            
            elements.append(Spacer(1, 30))
            footer = Paragraph(
                f"<i>Generated by EcoPOOL League Manager</i>",
                ParagraphStyle('Footer', parent=self.styles['Normal'], fontSize=9, 
                              textColor=colors.grey, alignment=TA_CENTER)
            )
            elements.append(footer)
            
            doc.build(elements)
            return True
            
        except Exception as e:
            print(f"Error exporting leaderboard: {e}")
            return False
    
    def export_players_csv(self, filepath: str) -> bool:
        """Export all players to CSV."""
        try:
            players = self.db.get_all_players()
            
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Name', 'Email', 'Venmo', 'Games Played', 'Games Won',
                    'Win Rate %', 'Total Points', 'Avg Points', 'Golden Breaks'
                ])
                
                for player in players:
                    writer.writerow([
                        player.name,
                        player.email,
                        player.venmo,
                        player.games_played,
                        player.games_won,
                        f"{player.win_rate:.1f}",
                        player.total_points,
                        f"{player.avg_points:.1f}",
                        player.golden_breaks
                    ])
            
            return True
        except Exception as e:
            print(f"Error exporting players CSV: {e}")
            return False
    
    def export_matches_csv(self, filepath: str) -> bool:
        """Export all matches to CSV."""
        try:
            matches = self.db.get_all_matches(limit=1000)
            
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    'Date', 'Team 1', 'Team 2', 'Table', 'Best Of',
                    'Finals', 'Complete'
                ])
                
                for match in matches:
                    team1 = match['team1_p1_name']
                    if match['team1_p2_name']:
                        team1 += f" & {match['team1_p2_name']}"
                    
                    team2 = match['team2_p1_name']
                    if match['team2_p2_name']:
                        team2 += f" & {match['team2_p2_name']}"
                    
                    writer.writerow([
                        match['date'][:10] if match['date'] else '',
                        team1,
                        team2,
                        match['table_number'],
                        match['best_of'],
                        'Yes' if match['is_finals'] else 'No',
                        'Yes' if match['is_complete'] else 'No'
                    ])
            
            return True
        except Exception as e:
            print(f"Error exporting matches CSV: {e}")
            return False
    
    def export_match_history_pdf(self, filepath: str) -> bool:
        """Export all match history to PDF."""
        try:
            matches = self.db.get_all_matches(limit=1000)
            
            doc = SimpleDocTemplate(filepath, pagesize=letter)
            elements = []
            
            # Title
            elements.append(Paragraph("WVU EcoPOOL League", self.title_style))
            elements.append(Paragraph("Match History", self.subtitle_style))
            elements.append(Paragraph(
                f"<i>Generated on {datetime.now().strftime('%B %d, %Y')}</i>",
                ParagraphStyle('Date', parent=self.styles['Normal'], 
                              alignment=TA_CENTER, textColor=colors.grey)
            ))
            elements.append(Spacer(1, 20))
            
            if not matches:
                elements.append(Paragraph("No matches found.", self.styles['Normal']))
            else:
                # Summary stats
                total_matches = len(matches)
                completed = sum(1 for m in matches if m['is_complete'])
                finals = sum(1 for m in matches if m['is_finals'])
                
                summary = f"<b>Total Matches:</b> {total_matches} | <b>Completed:</b> {completed} | <b>Finals:</b> {finals}"
                elements.append(Paragraph(summary, self.styles['Normal']))
                elements.append(Spacer(1, 15))
                
                # Match table
                data = [['Date', 'Team 1', 'Team 2', 'Score', 'Status']]
                
                for match in matches:
                    team1 = match['team1_p1_name'] or "Unknown"
                    if match['team1_p2_name']:
                        team1 += f" & {match['team1_p2_name']}"
                    
                    team2 = match['team2_p1_name'] or "Unknown"
                    if match['team2_p2_name']:
                        team2 += f" & {match['team2_p2_name']}"
                    
                    # Get game scores
                    games = self.db.get_games_for_match(match['id'])
                    t1_wins = sum(1 for g in games if g['winner_team'] == 1)
                    t2_wins = sum(1 for g in games if g['winner_team'] == 2)
                    
                    status = "Complete" if match['is_complete'] else "In Progress"
                    if match['is_finals']:
                        status = "Finals - " + status
                    
                    data.append([
                        match['date'][:10] if match['date'] else 'N/A',
                        team1[:25] + "..." if len(team1) > 25 else team1,
                        team2[:25] + "..." if len(team2) > 25 else team2,
                        f"{t1_wins} - {t2_wins}",
                        status
                    ])
                
                table = Table(data, colWidths=[0.9*inch, 1.8*inch, 1.8*inch, 0.7*inch, 1.2*inch])
                table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5f2a')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('BOX', (0, 0), (-1, -1), 1, colors.black),
                    ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('TOPPADDING', (0, 0), (-1, -1), 5),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
                ]))
                elements.append(table)
            
            elements.append(Spacer(1, 30))
            footer = Paragraph(
                f"<i>Generated by EcoPOOL League Manager</i>",
                ParagraphStyle('Footer', parent=self.styles['Normal'], fontSize=9, 
                              textColor=colors.grey, alignment=TA_CENTER)
            )
            elements.append(footer)
            
            doc.build(elements)
            return True
            
        except Exception as e:
            print(f"Error exporting match history PDF: {e}")
            return False
    
    def export_players_json(self, filepath: str) -> bool:
        """Export all players to JSON for portability."""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM players WHERE active = 1")
            
            players = []
            for row in cursor.fetchall():
                players.append({
                    'name': row['name'],
                    'email': row['email'],
                    'venmo': row['venmo'],
                    'created_at': row['created_at']
                })
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    'version': '1.0',
                    'type': 'players',
                    'exported_at': datetime.now().isoformat(),
                    'players': players
                }, f, indent=2)
            
            return True
        except Exception as e:
            print(f"Error exporting players JSON: {e}")
            return False
    
    def import_players_json(self, filepath: str) -> tuple[bool, str]:
        """Import players from JSON. Returns (success, message)."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if data.get('type') != 'players':
                return False, "Invalid file: not a players export file."
            
            players = data.get('players', [])
            imported = 0
            skipped = 0
            
            for player in players:
                try:
                    self.db.add_player(
                        name=player['name'],
                        email=player.get('email', ''),
                        venmo=player.get('venmo', '')
                    )
                    imported += 1
                except Exception:
                    # Player already exists (unique constraint)
                    skipped += 1
            
            return True, f"Imported {imported} players, skipped {skipped} duplicates."
        except Exception as e:
            return False, f"Error importing players: {e}"
    
    def export_matches_json(self, filepath: str) -> bool:
        """Export all matches and games to JSON for backup/portability."""
        try:
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            # Get all matches with raw IDs
            cursor.execute("SELECT * FROM matches ORDER BY date DESC")
            matches = [dict(row) for row in cursor.fetchall()]
            
            # Get all games
            cursor.execute("SELECT * FROM games ORDER BY match_id, game_number")
            games = [dict(row) for row in cursor.fetchall()]
            
            # Get player name mapping for reconstruction
            cursor.execute("SELECT id, name FROM players")
            players = {row['id']: row['name'] for row in cursor.fetchall()}
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump({
                    'version': '1.0',
                    'type': 'match_history',
                    'exported_at': datetime.now().isoformat(),
                    'player_names': players,
                    'matches': matches,
                    'games': games
                }, f, indent=2)
            
            return True
        except Exception as e:
            print(f"Error exporting matches JSON: {e}")
            return False
    
    def import_matches_json(self, filepath: str) -> tuple[bool, str]:
        """Import matches from JSON. Returns (success, message)."""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if data.get('type') != 'match_history':
                return False, "Invalid file: not a match history export file."
            
            conn = self.db.get_connection()
            cursor = conn.cursor()
            
            # Get current player name to ID mapping
            cursor.execute("SELECT id, name FROM players")
            name_to_id = {row['name']: row['id'] for row in cursor.fetchall()}
            
            old_player_names = data.get('player_names', {})
            matches = data.get('matches', [])
            games = data.get('games', [])
            
            imported_matches = 0
            skipped_matches = 0
            
            # Map old match IDs to new match IDs
            old_to_new_match = {}
            
            for match in matches:
                # Map player IDs using names
                def get_player_id(old_id):
                    if old_id is None:
                        return None
                    old_name = old_player_names.get(str(old_id))
                    if old_name and old_name in name_to_id:
                        return name_to_id[old_name]
                    return None
                
                t1p1 = get_player_id(match['team1_player1_id'])
                t1p2 = get_player_id(match['team1_player2_id'])
                t2p1 = get_player_id(match['team2_player1_id'])
                t2p2 = get_player_id(match['team2_player2_id'])
                
                if t1p1 is None or t2p1 is None:
                    skipped_matches += 1
                    continue
                
                # Create match
                new_match_id = self.db.create_match(
                    team1_p1=t1p1, team1_p2=t1p2,
                    team2_p1=t2p1, team2_p2=t2p2,
                    table_number=match.get('table_number', 1),
                    best_of=match.get('best_of', 3),
                    is_finals=bool(match.get('is_finals', 0))
                )
                
                if match.get('is_complete'):
                    self.db.complete_match(new_match_id)
                
                old_to_new_match[match['id']] = new_match_id
                imported_matches += 1
            
            # Import games
            imported_games = 0
            for game in games:
                old_match_id = game['match_id']
                if old_match_id not in old_to_new_match:
                    continue
                
                new_match_id = old_to_new_match[old_match_id]
                
                game_id = self.db.create_game(
                    match_id=new_match_id,
                    game_number=game['game_number'],
                    breaking_team=game.get('breaking_team', 1)
                )
                
                # Update game with scores
                balls_pocketed = game.get('balls_pocketed', '{}')
                if isinstance(balls_pocketed, str):
                    balls_pocketed = json.loads(balls_pocketed)
                
                self.db.update_game(
                    game_id=game_id,
                    team1_score=game.get('team1_score', 0),
                    team2_score=game.get('team2_score', 0),
                    team1_group=game.get('team1_group', ''),
                    balls_pocketed=balls_pocketed,
                    winner_team=game.get('winner_team', 0),
                    golden_break=bool(game.get('golden_break', 0)),
                    early_8ball_team=game.get('early_8ball_team', 0)
                )
                imported_games += 1
            
            return True, f"Imported {imported_matches} matches ({imported_games} games), skipped {skipped_matches}."
        except Exception as e:
            return False, f"Error importing matches: {e}"
