"""
EcoPOOL League - Match Generator
Handles random partner assignment and match generation.
"""

import random
from typing import Optional
from itertools import permutations
from database import DatabaseManager, Player


class MatchGenerator:
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    def _normalize_team(self, team: tuple[int, Optional[int]]) -> tuple:
        """Normalize a team tuple to a sorted tuple for comparison."""
        return tuple(sorted(filter(None, team)))
    
    def _create_matchup_key(self, team1: tuple[int, Optional[int]], 
                            team2: tuple[int, Optional[int]]) -> frozenset:
        """Create a normalized matchup key for comparison."""
        return frozenset([self._normalize_team(team1), self._normalize_team(team2)])
    
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
    
    def generate_match_pairings(self, teams: list[tuple[int, Optional[int]]], 
                                 avoid_repeats: bool = True) -> list[dict]:
        """
        Generate match pairings from teams, avoiding repeated matchups when possible.
        
        Args:
            teams: List of team tuples (player1_id, player2_id)
            avoid_repeats: If True, tries to avoid matchups that have occurred before
            
        Returns:
            List of match dictionaries with is_repeat flag indicating if this matchup
            has occurred before.
        """
        if len(teams) < 2:
            return []
        
        # Get historical matchup counts
        matchup_counts = self.db.get_matchup_counts() if avoid_repeats else {}
        
        matches = []
        available_teams = teams.copy()
        
        # Try to find optimal pairings that minimize repeat matchups
        if avoid_repeats and len(available_teams) >= 2:
            best_pairings = self._find_best_pairings(available_teams, matchup_counts)
            if best_pairings:
                for team1, team2 in best_pairings:
                    matchup_key = self._create_matchup_key(team1, team2)
                    repeat_count = matchup_counts.get(matchup_key, 0)
                    matches.append({
                        'team1_p1': team1[0],
                        'team1_p2': team1[1],
                        'team2_p1': team2[0],
                        'team2_p2': team2[1],
                        'is_repeat': repeat_count > 0,
                        'repeat_count': repeat_count
                    })
                return matches
        
        # Fallback to simple random pairing
        random.shuffle(available_teams)
        for i in range(0, len(available_teams), 2):
            if i + 1 < len(available_teams):
                team1 = available_teams[i]
                team2 = available_teams[i + 1]
                matchup_key = self._create_matchup_key(team1, team2)
                repeat_count = matchup_counts.get(matchup_key, 0)
                matches.append({
                    'team1_p1': team1[0],
                    'team1_p2': team1[1],
                    'team2_p1': team2[0],
                    'team2_p2': team2[1],
                    'is_repeat': repeat_count > 0,
                    'repeat_count': repeat_count
                })
        
        return matches
    
    def _find_best_pairings(self, teams: list[tuple[int, Optional[int]]], 
                            matchup_counts: dict) -> list[tuple]:
        """
        Find the best team pairings that minimize repeat matchups.
        
        Uses a greedy algorithm for larger sets, exhaustive search for smaller ones.
        
        Returns:
            List of (team1, team2) tuples representing optimal pairings.
        """
        n_teams = len(teams)
        
        if n_teams < 2:
            return []
        
        # For small number of teams (<=8), we can try all permutations
        if n_teams <= 8:
            return self._exhaustive_best_pairings(teams, matchup_counts)
        
        # For larger sets, use greedy algorithm
        return self._greedy_best_pairings(teams, matchup_counts)
    
    def _exhaustive_best_pairings(self, teams: list[tuple[int, Optional[int]]], 
                                   matchup_counts: dict) -> list[tuple]:
        """
        Find optimal pairings by checking all possible arrangements.
        Only practical for small number of teams.
        """
        best_pairings = None
        best_score = float('inf')  # Lower is better (fewer repeats)
        
        # Try different orderings of teams
        teams_list = list(teams)
        
        # Generate all unique pairings (avoid duplicates from permutations)
        seen_configs = set()
        
        for perm in permutations(range(len(teams_list))):
            # Create pairings from this permutation
            pairings = []
            for i in range(0, len(perm) - 1, 2):
                t1_idx, t2_idx = perm[i], perm[i + 1]
                # Normalize the pairing order for deduplication
                pair = tuple(sorted([t1_idx, t2_idx]))
                pairings.append(pair)
            
            # Create a canonical representation of this configuration
            config_key = frozenset(pairings)
            if config_key in seen_configs:
                continue
            seen_configs.add(config_key)
            
            # Calculate score (total repeat count)
            score = 0
            actual_pairings = []
            for t1_idx, t2_idx in pairings:
                team1, team2 = teams_list[t1_idx], teams_list[t2_idx]
                matchup_key = self._create_matchup_key(team1, team2)
                score += matchup_counts.get(matchup_key, 0)
                actual_pairings.append((team1, team2))
            
            if score < best_score:
                best_score = score
                best_pairings = actual_pairings
                
                # If we found a perfect solution (no repeats), stop early
                if score == 0:
                    break
        
        return best_pairings or []
    
    def _greedy_best_pairings(self, teams: list[tuple[int, Optional[int]]], 
                               matchup_counts: dict) -> list[tuple]:
        """
        Find good pairings using a greedy algorithm.
        Prioritizes matchups with the lowest repeat count.
        """
        available = list(teams)
        random.shuffle(available)  # Add some randomness
        pairings = []
        
        while len(available) >= 2:
            # Pick the first available team
            team1 = available.pop(0)
            
            # Find the best opponent (lowest repeat count)
            best_opponent_idx = 0
            best_repeat_count = float('inf')
            
            for i, team2 in enumerate(available):
                matchup_key = self._create_matchup_key(team1, team2)
                repeat_count = matchup_counts.get(matchup_key, 0)
                
                if repeat_count < best_repeat_count:
                    best_repeat_count = repeat_count
                    best_opponent_idx = i
                    
                    # Perfect match found, no need to look further
                    if repeat_count == 0:
                        break
            
            team2 = available.pop(best_opponent_idx)
            pairings.append((team1, team2))
        
        return pairings
    
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
    
    def generate_full_league_night(self, player_ids: list[int], avoid_repeats: bool = True) -> dict:
        """
        Generate a complete league night with random teams and matches.
        Attempts to avoid repeating matchups that have occurred before.
        
        Args:
            player_ids: List of player IDs to include
            avoid_repeats: If True, tries to generate unique matchups
            
        Returns:
            Dict with teams, match pairings, and repeat information.
        """
        teams = self.generate_random_partners(player_ids)
        matches = self.generate_match_pairings(teams, avoid_repeats=avoid_repeats)
        
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
        total_repeats = 0
        for i, match in enumerate(matches):
            t1p1 = self.db.get_player(match['team1_p1'])
            t1p2 = self.db.get_player(match['team1_p2']) if match['team1_p2'] else None
            t2p1 = self.db.get_player(match['team2_p1'])
            t2p2 = self.db.get_player(match['team2_p2']) if match['team2_p2'] else None
            
            team1_name = f"{t1p1.name} & {t1p2.name}" if t1p2 else f"{t1p1.name}"
            team2_name = f"{t2p1.name} & {t2p2.name}" if t2p2 else f"{t2p1.name}"
            
            is_repeat = match.get('is_repeat', False)
            repeat_count = match.get('repeat_count', 0)
            if is_repeat:
                total_repeats += 1
            
            match_display.append({
                'match_num': i + 1,
                'team1': team1_name,
                'team2': team2_name,
                'is_repeat': is_repeat,
                'repeat_count': repeat_count,
                'raw': match
            })
        
        return {
            'teams': teams,
            'team_display': team_display,
            'matches': matches,
            'match_display': match_display,
            'total_repeats': total_repeats,
            'has_repeats': total_repeats > 0
        }
    
    def generate_multi_round_league_night(self, player_ids: list[int], 
                                           min_games_per_player: int = 4,
                                           avoid_repeats: bool = True) -> dict:
        """
        Generate multiple rounds of matches to ensure each player gets at least
        min_games_per_player games. Teams are re-randomized each round.
        
        Args:
            player_ids: List of player IDs to include
            min_games_per_player: Minimum number of games each player should play
            avoid_repeats: If True, tries to avoid repeating matchups
            
        Returns:
            Dict with rounds, each containing teams and matches.
        """
        if len(player_ids) < 2:
            return {'rounds': [], 'total_rounds': 0, 'games_per_player': {}}
        
        # Get historical matchup counts
        historical_counts = self.db.get_matchup_counts() if avoid_repeats else {}
        
        # Track matchups for this night (to avoid same-night repeats)
        tonight_matchups = {}  # matchup_key -> count
        
        # Calculate how many rounds we need
        # Each round, a player plays 1 game (since they're on one team per round)
        num_rounds = max(min_games_per_player, 1)
        
        rounds = []
        all_player_ids = set(player_ids)
        games_per_player = {pid: 0 for pid in player_ids}
        
        for round_num in range(1, num_rounds + 1):
            # Generate new random teams for this round
            teams = self.generate_random_partners(player_ids)
            
            # Generate match pairings, considering both historical and tonight's matchups
            combined_counts = {**historical_counts}
            for key, count in tonight_matchups.items():
                combined_counts[key] = combined_counts.get(key, 0) + count
            
            matches = self._generate_match_pairings_with_counts(teams, combined_counts)
            
            # Update tonight's matchup counts
            for match in matches:
                matchup_key = self._create_matchup_key(
                    (match['team1_p1'], match.get('team1_p2')),
                    (match['team2_p1'], match.get('team2_p2'))
                )
                tonight_matchups[matchup_key] = tonight_matchups.get(matchup_key, 0) + 1
            
            # Track games per player
            for match in matches:
                for pid in [match['team1_p1'], match.get('team1_p2'), 
                           match['team2_p1'], match.get('team2_p2')]:
                    if pid is not None:
                        games_per_player[pid] = games_per_player.get(pid, 0) + 1
            
            # Build display info
            team_display = []
            for team in teams:
                p1 = self.db.get_player(team[0])
                p2 = self.db.get_player(team[1]) if team[1] else None
                if p2:
                    team_display.append(f"{p1.name} & {p2.name}")
                else:
                    team_display.append(f"{p1.name} (Lone Wolf)")
            
            match_display = []
            round_repeats = 0
            for i, match in enumerate(matches):
                t1p1 = self.db.get_player(match['team1_p1'])
                t1p2 = self.db.get_player(match['team1_p2']) if match['team1_p2'] else None
                t2p1 = self.db.get_player(match['team2_p1'])
                t2p2 = self.db.get_player(match['team2_p2']) if match['team2_p2'] else None
                
                team1_name = f"{t1p1.name} & {t1p2.name}" if t1p2 else f"{t1p1.name}"
                team2_name = f"{t2p1.name} & {t2p2.name}" if t2p2 else f"{t2p1.name}"
                
                is_repeat = match.get('is_repeat', False)
                repeat_count = match.get('repeat_count', 0)
                if is_repeat:
                    round_repeats += 1
                
                match_display.append({
                    'match_num': i + 1,
                    'team1': team1_name,
                    'team2': team2_name,
                    'is_repeat': is_repeat,
                    'repeat_count': repeat_count,
                    'raw': match
                })
            
            rounds.append({
                'round_num': round_num,
                'teams': teams,
                'team_display': team_display,
                'matches': matches,
                'match_display': match_display,
                'round_repeats': round_repeats,
                'has_repeats': round_repeats > 0
            })
        
        # Calculate total repeats across all rounds
        total_repeats = sum(r['round_repeats'] for r in rounds)
        
        # Get player names for games_per_player display
        games_per_player_display = {}
        for pid, count in games_per_player.items():
            player = self.db.get_player(pid)
            if player:
                games_per_player_display[player.name] = count
        
        return {
            'rounds': rounds,
            'total_rounds': len(rounds),
            'total_repeats': total_repeats,
            'has_repeats': total_repeats > 0,
            'games_per_player': games_per_player,
            'games_per_player_display': games_per_player_display,
            'min_games': min(games_per_player.values()) if games_per_player else 0,
            'max_games': max(games_per_player.values()) if games_per_player else 0
        }
    
    def _generate_match_pairings_with_counts(self, teams: list[tuple[int, Optional[int]]], 
                                              matchup_counts: dict) -> list[dict]:
        """Generate match pairings using provided matchup counts."""
        if len(teams) < 2:
            return []
        
        # Use the best pairings algorithm with provided counts
        if len(teams) <= 8:
            best_pairings = self._exhaustive_best_pairings_with_counts(teams, matchup_counts)
        else:
            best_pairings = self._greedy_best_pairings_with_counts(teams, matchup_counts)
        
        matches = []
        for team1, team2 in best_pairings:
            matchup_key = self._create_matchup_key(team1, team2)
            repeat_count = matchup_counts.get(matchup_key, 0)
            matches.append({
                'team1_p1': team1[0],
                'team1_p2': team1[1],
                'team2_p1': team2[0],
                'team2_p2': team2[1],
                'is_repeat': repeat_count > 0,
                'repeat_count': repeat_count
            })
        
        return matches
    
    def _exhaustive_best_pairings_with_counts(self, teams: list[tuple[int, Optional[int]]], 
                                               matchup_counts: dict) -> list[tuple]:
        """Find optimal pairings using provided matchup counts."""
        best_pairings = None
        best_score = float('inf')
        
        teams_list = list(teams)
        seen_configs = set()
        
        for perm in permutations(range(len(teams_list))):
            pairings = []
            for i in range(0, len(perm) - 1, 2):
                t1_idx, t2_idx = perm[i], perm[i + 1]
                pair = tuple(sorted([t1_idx, t2_idx]))
                pairings.append(pair)
            
            config_key = frozenset(pairings)
            if config_key in seen_configs:
                continue
            seen_configs.add(config_key)
            
            score = 0
            actual_pairings = []
            for t1_idx, t2_idx in pairings:
                team1, team2 = teams_list[t1_idx], teams_list[t2_idx]
                matchup_key = self._create_matchup_key(team1, team2)
                score += matchup_counts.get(matchup_key, 0)
                actual_pairings.append((team1, team2))
            
            if score < best_score:
                best_score = score
                best_pairings = actual_pairings
                if score == 0:
                    break
        
        return best_pairings or []
    
    def _greedy_best_pairings_with_counts(self, teams: list[tuple[int, Optional[int]]], 
                                           matchup_counts: dict) -> list[tuple]:
        """Find good pairings using greedy algorithm with provided counts."""
        available = list(teams)
        random.shuffle(available)
        pairings = []
        
        while len(available) >= 2:
            team1 = available.pop(0)
            
            best_opponent_idx = 0
            best_repeat_count = float('inf')
            
            for i, team2 in enumerate(available):
                matchup_key = self._create_matchup_key(team1, team2)
                repeat_count = matchup_counts.get(matchup_key, 0)
                
                if repeat_count < best_repeat_count:
                    best_repeat_count = repeat_count
                    best_opponent_idx = i
                    if repeat_count == 0:
                        break
            
            team2 = available.pop(best_opponent_idx)
            pairings.append((team1, team2))
        
        return pairings
