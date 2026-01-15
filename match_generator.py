"""
EcoPOOL League - Match Generator
Handles pair assignment and full evening schedule generation with queue system.
"""

import random
from typing import Optional, List, Tuple
from itertools import combinations, permutations
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
    
    # ============ Pair Generation Methods ============
    
    def generate_random_pairs(self, player_ids: list[int]) -> list[tuple[int, Optional[int]]]:
        """
        Generate random 2-player pairs from a list of player IDs.
        Returns list of (player1_id, player2_id) tuples.
        If odd number, last pair has only one player (lone wolf).
        """
        shuffled = player_ids.copy()
        random.shuffle(shuffled)
        
        pairs = []
        for i in range(0, len(shuffled), 2):
            if i + 1 < len(shuffled):
                pairs.append((shuffled[i], shuffled[i + 1]))
            else:
                pairs.append((shuffled[i], None))  # Lone wolf
        
        return pairs
    
    def generate_skill_based_pairs(self, player_ids: list[int]) -> list[tuple[int, Optional[int]]]:
        """
        Generate pairs that balance skill levels.
        Pairs highest-ranked with lowest-ranked players.
        """
        # Get players with stats and sort by total points
        players_with_stats = []
        for pid in player_ids:
            player = self.db.get_player(pid)
            if player:
                players_with_stats.append((pid, player.total_points))
        
        # Sort by points descending
        players_with_stats.sort(key=lambda x: -x[1])
        
        # Pair highest with lowest
        pairs = []
        sorted_ids = [p[0] for p in players_with_stats]
        
        while len(sorted_ids) >= 2:
            # Take best and worst remaining
            best = sorted_ids.pop(0)
            worst = sorted_ids.pop(-1) if sorted_ids else None
            pairs.append((best, worst))
        
        # Handle odd player (lone wolf)
        if sorted_ids:
            pairs.append((sorted_ids[0], None))
        
        return pairs
    
    def create_manual_pair(self, player1_id: int, player2_id: Optional[int]) -> tuple[int, Optional[int]]:
        """Create a manual pair from two player IDs."""
        return (player1_id, player2_id)
    
    # ============ Full Schedule Generation ============
    
    def generate_full_schedule(self, pairs: list[tuple[int, Optional[int]]], 
                               min_games_per_pair: int = 4,
                               table_count: int = 3,
                               avoid_repeats: bool = True) -> dict:
        """
        Generate a full evening schedule ensuring each pair plays at least min_games_per_pair games.
        
        Args:
            pairs: List of (player1_id, player2_id) tuples representing fixed pairs
            min_games_per_pair: Minimum games each pair should play
            table_count: Number of tables available
            avoid_repeats: Whether to avoid repeat matchups
            
        Returns:
            Dict with schedule info including live games, queued games, etc.
        """
        if len(pairs) < 2:
            return {
                'pairs': pairs,
                'matches': [],
                'live_matches': [],
                'queued_matches': [],
                'games_per_pair': {},
                'total_matches': 0
            }
        
        # Get historical matchup counts if avoiding repeats
        matchup_counts = self.db.get_matchup_counts() if avoid_repeats else {}
        
        # Generate all possible pair vs pair matchups
        all_matchups = list(combinations(range(len(pairs)), 2))
        
        # Count how many games each pair has been assigned
        games_per_pair = {i: 0 for i in range(len(pairs))}
        selected_matchups = []
        tonight_matchups = {}  # Track tonight's matchups to avoid too many repeats
        
        # First pass: Ensure minimum games per pair
        # Keep selecting matchups until all pairs have at least min_games
        while min(games_per_pair.values()) < min_games_per_pair:
            # Find pairs that need more games
            pairs_needing_games = [i for i, count in games_per_pair.items() 
                                   if count < min_games_per_pair]
            
            # Find best matchup involving a pair that needs games
            best_matchup = None
            best_score = float('inf')
            
            for p1_idx, p2_idx in all_matchups:
                # At least one pair should need more games
                if p1_idx not in pairs_needing_games and p2_idx not in pairs_needing_games:
                    continue
                
                # Calculate repeat score
                pair1 = pairs[p1_idx]
                pair2 = pairs[p2_idx]
                matchup_key = self._create_matchup_key(pair1, pair2)
                
                historical_count = matchup_counts.get(matchup_key, 0)
                tonight_count = tonight_matchups.get(matchup_key, 0)
                
                # Score: prefer matchups with fewer repeats
                # Weight tonight's repeats more heavily
                score = historical_count + (tonight_count * 10)
                
                if score < best_score:
                    best_score = score
                    best_matchup = (p1_idx, p2_idx)
            
            if best_matchup is None:
                # No valid matchup found, break
                break
            
            p1_idx, p2_idx = best_matchup
            selected_matchups.append(best_matchup)
            games_per_pair[p1_idx] += 1
            games_per_pair[p2_idx] += 1
            
            # Track tonight's matchups
            pair1 = pairs[p1_idx]
            pair2 = pairs[p2_idx]
            matchup_key = self._create_matchup_key(pair1, pair2)
            tonight_matchups[matchup_key] = tonight_matchups.get(matchup_key, 0) + 1
        
        # Shuffle matchups to randomize order
        random.shuffle(selected_matchups)
        
        # Create match data with queue positions
        matches = []
        for i, (p1_idx, p2_idx) in enumerate(selected_matchups):
            pair1 = pairs[p1_idx]
            pair2 = pairs[p2_idx]
            
            matchup_key = self._create_matchup_key(pair1, pair2)
            historical_count = matchup_counts.get(matchup_key, 0)
            
            matches.append({
                'pair1_idx': p1_idx,
                'pair2_idx': p2_idx,
                'pair1': pair1,
                'pair2': pair2,
                'queue_position': i,
                'is_repeat': historical_count > 0,
                'repeat_count': historical_count
            })
        
        # Split into live and queued matches
        live_matches = matches[:table_count]
        queued_matches = matches[table_count:]
        
        # Assign table numbers to live matches
        for i, match in enumerate(live_matches):
            match['table_number'] = i + 1
            match['status'] = 'live'
        
        for match in queued_matches:
            match['status'] = 'queued'
            match['table_number'] = None
        
        return {
            'pairs': pairs,
            'matches': matches,
            'live_matches': live_matches,
            'queued_matches': queued_matches,
            'games_per_pair': {i: games_per_pair[i] for i in range(len(pairs))},
            'total_matches': len(matches),
            'table_count': table_count
        }
    
    def get_pair_display_names(self, pairs: list[tuple[int, Optional[int]]]) -> list[str]:
        """Get display names for pairs."""
        pair_names = []
        for p1_id, p2_id in pairs:
            p1 = self.db.get_player(p1_id)
            p2 = self.db.get_player(p2_id) if p2_id else None
            
            if p2:
                pair_names.append(f"{p1.name} & {p2.name}")
            else:
                pair_names.append(f"{p1.name} (Solo)")
        
        return pair_names
    
    def get_match_display(self, match: dict, pairs: list[tuple[int, Optional[int]]]) -> dict:
        """Get display info for a match."""
        pair1 = pairs[match['pair1_idx']]
        pair2 = pairs[match['pair2_idx']]
        
        p1_1 = self.db.get_player(pair1[0])
        p1_2 = self.db.get_player(pair1[1]) if pair1[1] else None
        p2_1 = self.db.get_player(pair2[0])
        p2_2 = self.db.get_player(pair2[1]) if pair2[1] else None
        
        team1_name = f"{p1_1.name} & {p1_2.name}" if p1_2 else f"{p1_1.name}"
        team2_name = f"{p2_1.name} & {p2_2.name}" if p2_2 else f"{p2_1.name}"
        
        return {
            'team1': team1_name,
            'team2': team2_name,
            'table_number': match.get('table_number'),
            'status': match.get('status', 'queued'),
            'queue_position': match.get('queue_position', 0),
            'is_repeat': match.get('is_repeat', False),
            'repeat_count': match.get('repeat_count', 0)
        }
    
    # ============ Legacy Methods (kept for compatibility) ============
    
    def generate_random_partners(self, player_ids: list[int]) -> list[tuple[int, Optional[int]]]:
        """Legacy alias for generate_random_pairs."""
        return self.generate_random_pairs(player_ids)
    
    def generate_match_pairings(self, teams: list[tuple[int, Optional[int]]], 
                                 avoid_repeats: bool = True) -> list[dict]:
        """
        Generate match pairings from teams, avoiding repeated matchups when possible.
        Legacy method - use generate_full_schedule for new features.
        """
        if len(teams) < 2:
            return []
        
        matchup_counts = self.db.get_matchup_counts() if avoid_repeats else {}
        
        matches = []
        available_teams = teams.copy()
        
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
        """Find the best team pairings that minimize repeat matchups."""
        n_teams = len(teams)
        
        if n_teams < 2:
            return []
        
        if n_teams <= 8:
            return self._exhaustive_best_pairings(teams, matchup_counts)
        
        return self._greedy_best_pairings(teams, matchup_counts)
    
    def _exhaustive_best_pairings(self, teams: list[tuple[int, Optional[int]]], 
                                   matchup_counts: dict) -> list[tuple]:
        """Find optimal pairings by checking all possible arrangements."""
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
    
    def _greedy_best_pairings(self, teams: list[tuple[int, Optional[int]]], 
                               matchup_counts: dict) -> list[tuple]:
        """Find good pairings using a greedy algorithm."""
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
    
    def generate_ranked_finals(self, player_ids: list[int], top_n: int = 4) -> list[dict]:
        """Generate finals bracket based on player rankings."""
        players = [self.db.get_player(pid) for pid in player_ids]
        players = [p for p in players if p is not None]
        
        # Sort by points (primary), then wins, then win rate
        players.sort(key=lambda p: (-p.total_points, -p.games_won, -p.win_rate))
        
        top_players = players[:top_n]
        
        if len(top_players) < 2:
            return []
        
        matches = []
        
        if len(top_players) == 4:
            matches.append({
                'team1_p1': top_players[0].id,
                'team1_p2': None,
                'team2_p1': top_players[3].id,
                'team2_p2': None,
                'round': 'Semi-Final 1',
                'seed_info': f"#1 vs #4"
            })
            matches.append({
                'team1_p1': top_players[1].id,
                'team1_p2': None,
                'team2_p1': top_players[2].id,
                'team2_p2': None,
                'round': 'Semi-Final 2',
                'seed_info': f"#2 vs #3"
            })
        elif len(top_players) == 2:
            matches.append({
                'team1_p1': top_players[0].id,
                'team1_p2': None,
                'team2_p1': top_players[1].id,
                'team2_p2': None,
                'round': 'Final',
                'seed_info': f"#1 vs #2"
            })
        else:
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
        """Legacy method - generates single round of matches."""
        teams = self.generate_random_partners(player_ids)
        matches = self.generate_match_pairings(teams, avoid_repeats=avoid_repeats)
        
        team_display = self.get_pair_display_names(teams)
        
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
        Legacy method - kept for compatibility.
        For new features, use generate_full_schedule with fixed pairs.
        """
        if len(player_ids) < 2:
            return {'rounds': [], 'total_rounds': 0, 'games_per_player': {}}
        
        historical_counts = self.db.get_matchup_counts() if avoid_repeats else {}
        tonight_matchups = {}
        num_rounds = max(min_games_per_player, 1)
        
        rounds = []
        games_per_player = {pid: 0 for pid in player_ids}
        
        for round_num in range(1, num_rounds + 1):
            teams = self.generate_random_partners(player_ids)
            
            combined_counts = {**historical_counts}
            for key, count in tonight_matchups.items():
                combined_counts[key] = combined_counts.get(key, 0) + count
            
            matches = self._generate_match_pairings_with_counts(teams, combined_counts)
            
            for match in matches:
                matchup_key = self._create_matchup_key(
                    (match['team1_p1'], match.get('team1_p2')),
                    (match['team2_p1'], match.get('team2_p2'))
                )
                tonight_matchups[matchup_key] = tonight_matchups.get(matchup_key, 0) + 1
            
            for match in matches:
                for pid in [match['team1_p1'], match.get('team1_p2'), 
                           match['team2_p1'], match.get('team2_p2')]:
                    if pid is not None:
                        games_per_player[pid] = games_per_player.get(pid, 0) + 1
            
            team_display = self.get_pair_display_names(teams)
            
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
        
        total_repeats = sum(r['round_repeats'] for r in rounds)
        
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
