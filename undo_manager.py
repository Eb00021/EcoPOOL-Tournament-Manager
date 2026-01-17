"""
EcoPOOL League - Undo/Redo Manager
Provides undo/redo functionality for game actions.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from copy import deepcopy


@dataclass
class GameAction:
    """Represents a single game action that can be undone."""
    action_type: str  # 'pocket_ball', 'set_group', 'golden_break', 'declare_winner', 'early_8ball'
    timestamp: datetime
    data: Dict[str, Any]
    description: str


class UndoManager:
    """Manages undo/redo stacks for game actions."""

    def __init__(self, max_history: int = 50):
        """Initialize the undo manager.

        Args:
            max_history: Maximum number of actions to keep in history
        """
        self.max_history = max_history
        self._undo_stack: List[GameAction] = []
        self._redo_stack: List[GameAction] = []
        self._callbacks: Dict[str, List[Callable]] = {
            'on_action': [],
            'on_undo': [],
            'on_redo': [],
            'on_stack_change': []
        }

    def clear(self):
        """Clear all undo/redo history."""
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._notify_stack_change()

    def record_action(self, action_type: str, data: Dict[str, Any], description: str):
        """Record an action that can be undone.

        Args:
            action_type: Type of action (e.g., 'pocket_ball')
            data: Data needed to undo/redo the action
            description: Human-readable description
        """
        action = GameAction(
            action_type=action_type,
            timestamp=datetime.now(),
            data=deepcopy(data),
            description=description
        )

        self._undo_stack.append(action)

        # Clear redo stack when new action is performed
        self._redo_stack.clear()

        # Limit history size
        if len(self._undo_stack) > self.max_history:
            self._undo_stack.pop(0)

        self._notify('on_action', action)
        self._notify_stack_change()

    def can_undo(self) -> bool:
        """Check if there are actions to undo."""
        return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        """Check if there are actions to redo."""
        return len(self._redo_stack) > 0

    def undo(self) -> Optional[GameAction]:
        """Pop and return the most recent action for undoing.

        Returns:
            The action to undo, or None if stack is empty
        """
        if not self._undo_stack:
            return None

        action = self._undo_stack.pop()
        self._redo_stack.append(action)

        self._notify('on_undo', action)
        self._notify_stack_change()

        return action

    def redo(self) -> Optional[GameAction]:
        """Pop and return the most recent undone action for redoing.

        Returns:
            The action to redo, or None if stack is empty
        """
        if not self._redo_stack:
            return None

        action = self._redo_stack.pop()
        self._undo_stack.append(action)

        self._notify('on_redo', action)
        self._notify_stack_change()

        return action

    def peek_undo(self) -> Optional[GameAction]:
        """Peek at the next action to undo without removing it."""
        return self._undo_stack[-1] if self._undo_stack else None

    def peek_redo(self) -> Optional[GameAction]:
        """Peek at the next action to redo without removing it."""
        return self._redo_stack[-1] if self._redo_stack else None

    def get_undo_description(self) -> str:
        """Get description of the next undo action."""
        action = self.peek_undo()
        return action.description if action else ""

    def get_redo_description(self) -> str:
        """Get description of the next redo action."""
        action = self.peek_redo()
        return action.description if action else ""

    def get_undo_count(self) -> int:
        """Get number of actions that can be undone."""
        return len(self._undo_stack)

    def get_redo_count(self) -> int:
        """Get number of actions that can be redone."""
        return len(self._redo_stack)

    def register_callback(self, event: str, callback: Callable):
        """Register a callback for undo/redo events.

        Events:
            - 'on_action': Called when a new action is recorded
            - 'on_undo': Called when an action is undone
            - 'on_redo': Called when an action is redone
            - 'on_stack_change': Called when undo/redo availability changes
        """
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def unregister_callback(self, event: str, callback: Callable):
        """Unregister a callback."""
        if event in self._callbacks and callback in self._callbacks[event]:
            self._callbacks[event].remove(callback)

    def _notify(self, event: str, action: GameAction):
        """Notify callbacks of an event."""
        for callback in self._callbacks.get(event, []):
            try:
                callback(action)
            except Exception:
                pass

    def _notify_stack_change(self):
        """Notify callbacks that stack availability has changed."""
        for callback in self._callbacks.get('on_stack_change', []):
            try:
                callback(self.can_undo(), self.can_redo())
            except Exception:
                pass


class GameStateSnapshot:
    """Captures the complete state of a game for restoration."""

    def __init__(self):
        self.ball_states: Dict[int, str] = {}
        self.team1_score: int = 0
        self.team2_score: int = 0
        self.team1_group: Optional[str] = None
        self.pocketed_balls: Dict[int, List[int]] = {1: [], 2: []}
        self.current_shooting_team: int = 1
        self.game_complete: bool = False
        self.winner_team: int = 0
        self.golden_break: bool = False

    def capture(self, scorecard_view) -> 'GameStateSnapshot':
        """Capture current game state from a scorecard view.

        Args:
            scorecard_view: The ScorecardView instance

        Returns:
            self for chaining
        """
        if hasattr(scorecard_view, 'pool_table'):
            self.ball_states = deepcopy(scorecard_view.pool_table.ball_states)
            self.team1_group = scorecard_view.pool_table.team1_group

        if hasattr(scorecard_view, 'current_game'):
            game = scorecard_view.current_game
            if game:
                self.team1_score = game.get('team1_score', 0)
                self.team2_score = game.get('team2_score', 0)
                self.winner_team = game.get('winner_team', 0)
                self.golden_break = game.get('golden_break', False)
                self.game_complete = game.get('winner_team', 0) > 0

        if hasattr(scorecard_view, 'pocket_team_var'):
            self.current_shooting_team = scorecard_view.pocket_team_var.get()

        return self

    def restore(self, scorecard_view):
        """Restore game state to a scorecard view.

        Args:
            scorecard_view: The ScorecardView instance
        """
        if hasattr(scorecard_view, 'pool_table'):
            scorecard_view.pool_table.ball_states = deepcopy(self.ball_states)
            scorecard_view.pool_table.team1_group = self.team1_group
            scorecard_view.pool_table.draw_balls()

        if hasattr(scorecard_view, 'pocket_team_var'):
            scorecard_view.pocket_team_var.set(self.current_shooting_team)
            scorecard_view.update_turn_indicator()

        # Update score display
        if hasattr(scorecard_view, 'update_score_display'):
            scorecard_view.update_score_display()


class ScorecardUndoManager(UndoManager):
    """Specialized undo manager for scorecard operations."""

    def __init__(self, scorecard_view=None):
        super().__init__(max_history=100)
        self.scorecard = scorecard_view

    def set_scorecard(self, scorecard_view):
        """Set the scorecard view reference."""
        self.scorecard = scorecard_view

    def record_ball_pocket(self, ball_num: int, team: int, previous_state: Dict):
        """Record a ball pocket action."""
        self.record_action(
            action_type='pocket_ball',
            data={
                'ball_num': ball_num,
                'team': team,
                'previous_ball_state': previous_state.get('ball_state', 'table'),
                'previous_team1_score': previous_state.get('team1_score', 0),
                'previous_team2_score': previous_state.get('team2_score', 0),
            },
            description=f"Pocket ball {ball_num} for Team {team}"
        )

    def record_group_set(self, group: str, previous_group: Optional[str]):
        """Record a group assignment."""
        self.record_action(
            action_type='set_group',
            data={
                'new_group': group,
                'previous_group': previous_group
            },
            description=f"Set Team 1 to {group}"
        )

    def record_golden_break(self, team: int, previous_state: Dict):
        """Record a golden break."""
        self.record_action(
            action_type='golden_break',
            data={
                'team': team,
                'previous_team1_score': previous_state.get('team1_score', 0),
                'previous_team2_score': previous_state.get('team2_score', 0),
            },
            description=f"Golden break for Team {team}"
        )

    def record_early_8ball(self, team: int, previous_state: Dict):
        """Record an early 8-ball foul."""
        self.record_action(
            action_type='early_8ball',
            data={
                'team': team,
                'previous_state': previous_state
            },
            description=f"Team {team} early 8-ball (Team {3 - team} wins)"
        )

    def record_declare_winner(self, team: int, previous_state: Dict):
        """Record declaring a winner."""
        self.record_action(
            action_type='declare_winner',
            data={
                'team': team,
                'previous_state': previous_state
            },
            description=f"Declare Team {team} winner"
        )
