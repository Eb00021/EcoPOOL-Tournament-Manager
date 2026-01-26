# EcoPOOL League Manager
# WVU EcoCAR Pool League Management Application

__version__ = "3.0.0"
__author__ = "WVU EcoCAR"

from views.players_view import PlayersView
from views.match_generator_view import MatchGeneratorView
from views.scorecard_view import ScorecardView
from views.leaderboard_view import LeaderboardView
from views.history_view import HistoryView
from views.table_tracker_view import TableTrackerView
from views.bracket_view import BracketView

__all__ = [
    '__version__',
    '__author__',
    'PlayersView',
    'MatchGeneratorView',
    'ScorecardView',
    'LeaderboardView',
    'HistoryView',
    'TableTrackerView',
    'BracketView',
]
