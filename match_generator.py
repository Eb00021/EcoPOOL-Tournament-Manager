"""
EcoPOOL League - Match Generator
Handles random partner assignment and match generation.
"""

import random
from typing import Optional
from database import DatabaseManager, Player


class MatchGenerator:
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    def generate_random_partners(self, player_ids: list[int]) -> list[tuple[int, Optional[int]]]:
        """
        Generate random 2-player teams from a list of player IDs.
        Returns list of (player1_id, player2_id) tuples.
        If odd number, last team has only one player (lone wolf).
        """
        shuffled = player_ids.copy()
        random.shuffle(shuffled)
        
        teams = []
        for i in range(0, len(shuffled), 2):
            if i + 1 < len(shuffled):
                teams.append((shuffled[i], shuffled[i + 1]))
            else:
                teams.append((shuffled[i], None))  # Lone wolf
        
        return teams
    
    def generate_match_pairings(self, teams: list[tuple[int, Optional[int]]]) -> list[dict]:
        """
        Generate match pairings from teams.
        Returns list of match dictionaries.
        """
        if len(teams) < 2:
            return []
        
        matches = []
        available_teams = teams.copy()
        random.shuffle(available_teams)
        
        for i in range(0, len(available_teams), 2):
            if i + 1 < len(available_teams):
                team1 = available_teams[i]
                team2 = available_teams[i + 1]
                matches.append({
                    'team1_p1': team1[0],
                    'team1_p2': team1[1],
                    'team2_p1': team2[0],
                    'team2_p2': team2[1],
                })
        
        return matches
    
    def generate_ranked_finals(self, player_ids: list[int], top_n: int = 4) -> list[dict]:
        """
        Generate finals bracket based on player rankings.
        Takes top N players and creates seeded matchups.
        """
        # Get players with stats
        players = [self.db.get_player(pid) for pid in player_ids]
        players = [p for p in players if p is not None]
        
        # Sort by wins, then win rate, then points
        players.sort(key=lambda p: (-p.games_won, -p.win_rate, -p.total_points))
        
        # Take top players
        top_players = players[:top_n]
        
        if len(top_players) < 2:
            return []
        
        # Create seeded bracket (1 vs 4, 2 vs 3 for 4 players)
        matches = []
        
        if len(top_players) == 4:
            # Semi-finals: 1st vs 4th, 2nd vs 3rd
            matches.append({
                'team1_p1': top_players[0].id,
                'team1_p2': None,
                'team2_p1': top_players[3].id,
                'team2_p2': None,
                'round': 'Semi-Final 1',
                'seed_info': f"#{1} vs #{4}"
            })
            matches.append({
                'team1_p1': top_players[1].id,
                'team1_p2': None,
                'team2_p1': top_players[2].id,
                'team2_p2': None,
                'round': 'Semi-Final 2',
                'seed_info': f"#{2} vs #{3}"
            })
        elif len(top_players) == 2:
            matches.append({
                'team1_p1': top_players[0].id,
                'team1_p2': None,
                'team2_p1': top_players[1].id,
                'team2_p2': None,
                'round': 'Final',
                'seed_info': f"#{1} vs #{2}"
            })
        else:
            # For other numbers, just pair up sequentially
            for i in range(0, len(top_players) - 1, 2):
                matches.append({
                    'team1_p1': top_players[i].id,
                    'team1_p2': None,
                    'team2_p1': top_players[i + 1].id,
                    'team2_p2': None,
                    'round': f'Match {i // 2 + 1}',
                    'seed_info': f"#{i + 1} vs #{i + 2}"
                })
        
        return matches
    
    def generate_full_league_night(self, player_ids: list[int]) -> dict:
        """
        Generate a complete league night with random teams and matches.
        Returns dict with teams and match pairings.
        """
        teams = self.generate_random_partners(player_ids)
        matches = self.generate_match_pairings(teams)
        
        # Get player names for display
        team_display = []
        for team in teams:
            p1 = self.db.get_player(team[0])
            p2 = self.db.get_player(team[1]) if team[1] else None
            
            if p2:
                team_display.append(f"{p1.name} & {p2.name}")
            else:
                team_display.append(f"{p1.name} (Lone Wolf)")
        
        match_display = []
        for i, match in enumerate(matches):
            t1p1 = self.db.get_player(match['team1_p1'])
            t1p2 = self.db.get_player(match['team1_p2']) if match['team1_p2'] else None
            t2p1 = self.db.get_player(match['team2_p1'])
            t2p2 = self.db.get_player(match['team2_p2']) if match['team2_p2'] else None
            
            team1_name = f"{t1p1.name} & {t1p2.name}" if t1p2 else f"{t1p1.name}"
            team2_name = f"{t2p1.name} & {t2p2.name}" if t2p2 else f"{t2p1.name}"
            
            match_display.append({
                'match_num': i + 1,
                'team1': team1_name,
                'team2': team2_name,
                'raw': match
            })
        
        return {
            'teams': teams,
            'team_display': team_display,
            'matches': matches,
            'match_display': match_display
        }
