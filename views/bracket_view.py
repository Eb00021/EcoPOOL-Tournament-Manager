"""
EcoPOOL League - Tournament Bracket View
Visual tournament bracket display with animations for end-of-semester finals.
"""

import customtkinter as ctk
from tkinter import Canvas, messagebox, filedialog
import math
from database import DatabaseManager
from profile_pictures import ProfilePicture, get_profile_picture_widget
from animations import AnimatedCard
from fonts import get_font, get_font_path

try:
    from PIL import Image, ImageDraw
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


class BracketNode:
    """Represents a single match in the bracket."""
    def __init__(self, round_num: int, position: int, player1=None, player2=None,
                 winner=None, score1: int = 0, score2: int = 0):
        self.round_num = round_num
        self.position = position
        self.player1 = player1
        self.player2 = player2
        self.winner = winner
        self.score1 = score1
        self.score2 = score2
        self.match_id = None


class TournamentBracket:
    """Manages tournament bracket logic."""
    
    def __init__(self, players: list, bracket_size: int = None):
        """
        Initialize bracket with players.
        Players should be sorted by ranking (best first).
        """
        self.players = players
        self.bracket_size = bracket_size or self._get_bracket_size(len(players))
        self.rounds = []
        self.champion = None
        
        self._create_bracket()
    
    def _get_bracket_size(self, num_players: int) -> int:
        """Get the appropriate bracket size (power of 2)."""
        if num_players <= 2:
            return 2
        elif num_players <= 4:
            return 4
        elif num_players <= 8:
            return 8
        elif num_players <= 16:
            return 16
        else:
            return 32
    
    def _create_bracket(self):
        """Create the bracket structure with seeding."""
        num_rounds = int(math.log2(self.bracket_size))
        
        # Create seeded first round
        first_round = []
        seeded_positions = self._get_seeding_order(self.bracket_size)
        
        for i in range(0, self.bracket_size, 2):
            seed1 = seeded_positions[i]
            seed2 = seeded_positions[i + 1]
            
            p1 = self.players[seed1 - 1] if seed1 <= len(self.players) else None
            p2 = self.players[seed2 - 1] if seed2 <= len(self.players) else None
            
            node = BracketNode(0, i // 2, p1, p2)
            
            # If only one player (bye), auto-advance
            if p1 and not p2:
                node.winner = p1
            elif p2 and not p1:
                node.winner = p2
            
            first_round.append(node)
        
        self.rounds.append(first_round)
        
        # Create subsequent rounds
        for round_num in range(1, num_rounds):
            round_matches = []
            prev_round = self.rounds[round_num - 1]
            
            for i in range(0, len(prev_round), 2):
                node = BracketNode(round_num, i // 2)
                
                # Link to previous round winners
                if prev_round[i].winner:
                    node.player1 = prev_round[i].winner
                if i + 1 < len(prev_round) and prev_round[i + 1].winner:
                    node.player2 = prev_round[i + 1].winner
                
                round_matches.append(node)
            
            self.rounds.append(round_matches)
    
    def _get_seeding_order(self, size: int) -> list:
        """Get the seeding order for proper bracket matchups (1v8, 4v5, etc)."""
        if size == 2:
            return [1, 2]
        elif size == 4:
            return [1, 4, 2, 3]
        elif size == 8:
            return [1, 8, 4, 5, 2, 7, 3, 6]
        elif size == 16:
            return [1, 16, 8, 9, 4, 13, 5, 12, 2, 15, 7, 10, 3, 14, 6, 11]
        else:
            # For larger brackets, use simple ordering
            return list(range(1, size + 1))
    
    def get_round_name(self, round_num: int) -> str:
        """Get the display name for a round."""
        total_rounds = len(self.rounds)
        rounds_from_end = total_rounds - round_num - 1
        
        if rounds_from_end == 0:
            return "Finals"
        elif rounds_from_end == 1:
            return "Semi-Finals"
        elif rounds_from_end == 2:
            return "Quarter-Finals"
        else:
            return f"Round {round_num + 1}"
    
    def set_winner(self, round_num: int, position: int, winner, score1: int, score2: int):
        """Set the winner of a match and propagate to next round."""
        node = self.rounds[round_num][position]
        node.winner = winner
        node.score1 = score1
        node.score2 = score2
        
        # Propagate to next round
        if round_num + 1 < len(self.rounds):
            next_position = position // 2
            next_node = self.rounds[round_num + 1][next_position]
            
            if position % 2 == 0:
                next_node.player1 = winner
            else:
                next_node.player2 = winner
        else:
            # This was the finals
            self.champion = winner


class BracketCanvas(ctk.CTkFrame):
    """Canvas for drawing the tournament bracket."""
    
    def __init__(self, parent, bracket: TournamentBracket, db: DatabaseManager,
                 on_match_click=None):
        super().__init__(parent, fg_color="transparent")
        
        self.bracket = bracket
        self.db = db
        self.on_match_click = on_match_click
        
        # Bracket styling
        self.match_width = 180
        self.match_height = 70
        self.round_spacing = 220
        self.match_spacing = 90
        self.colors = {
            'bg': '#161b22',
            'match_bg': '#252540',
            'match_hover': '#353560',
            'winner_bg': '#1e4a1e',
            'line': '#4CAF50',
            'text': '#ffffff',
            'seed': '#888888',
            'score': '#ffd700'
        }
        
        self._setup_canvas()
        self._draw_bracket()
    
    def _setup_canvas(self):
        """Setup the scrollable canvas with native scrolling to prevent tearing."""
        # Calculate required size
        num_rounds = len(self.bracket.rounds)
        first_round_matches = len(self.bracket.rounds[0])
        
        self.canvas_width = num_rounds * self.round_spacing + 150
        self.canvas_height = first_round_matches * self.match_spacing + 100
        
        # Create container frame
        container = ctk.CTkFrame(self, fg_color=self.colors['bg'])
        container.pack(fill="both", expand=True)
        
        # Create canvas with native Tkinter scrollbars (prevents tearing)
        self.canvas = Canvas(
            container,
            width=min(self.canvas_width, 1100),
            height=min(self.canvas_height, 600),
            bg=self.colors['bg'],
            highlightthickness=0,
            scrollregion=(0, 0, self.canvas_width, self.canvas_height)
        )
        
        # Horizontal scrollbar
        h_scroll = ctk.CTkScrollbar(container, orientation="horizontal", command=self.canvas.xview)
        h_scroll.pack(side="bottom", fill="x")
        
        # Vertical scrollbar
        v_scroll = ctk.CTkScrollbar(container, orientation="vertical", command=self.canvas.yview)
        v_scroll.pack(side="right", fill="y")
        
        # Configure canvas scrolling
        self.canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        
        # Bind mouse wheel for scrolling
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Shift-MouseWheel>", self._on_shift_mousewheel)
        # Linux support
        self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))
        
        self.match_widgets = {}
    
    def _on_mousewheel(self, event):
        """Handle vertical mouse wheel scrolling."""
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    
    def _on_shift_mousewheel(self, event):
        """Handle horizontal mouse wheel scrolling (Shift+scroll)."""
        self.canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
    
    def _draw_bracket(self):
        """Draw the entire bracket."""
        # Draw round labels
        for round_num, round_matches in enumerate(self.bracket.rounds):
            x = 50 + round_num * self.round_spacing
            round_name = self.bracket.get_round_name(round_num)
            
            self.canvas.create_text(
                x + self.match_width // 2, 25,
                text=round_name,
                font=("Arial", 14, "bold"),
                fill="#4CAF50"
            )
        
        # Draw matches and connecting lines
        for round_num, round_matches in enumerate(self.bracket.rounds):
            num_matches = len(round_matches)
            
            # Calculate vertical spacing for this round
            if round_num == 0:
                start_y = 60
                spacing = self.match_spacing
            else:
                # Center between previous round matches
                prev_positions = self._get_match_positions(round_num - 1)
                start_y = (prev_positions[0] + prev_positions[1]) // 2 - self.match_height // 2
                spacing = self.match_spacing * (2 ** round_num)
            
            for pos, node in enumerate(round_matches):
                x = 50 + round_num * self.round_spacing
                y = start_y + pos * spacing
                
                # Draw match box
                self._draw_match(x, y, node, round_num, pos)
                
                # Draw connecting lines to next round
                if round_num + 1 < len(self.bracket.rounds):
                    self._draw_connector(x, y, round_num, pos)
    
    def _get_match_positions(self, round_num: int) -> list:
        """Get the Y positions of matches in a round."""
        if round_num == 0:
            start_y = 60
            spacing = self.match_spacing
        else:
            prev_positions = self._get_match_positions(round_num - 1)
            start_y = (prev_positions[0] + prev_positions[1]) // 2 - self.match_height // 2
            spacing = self.match_spacing * (2 ** round_num)
        
        positions = []
        for i in range(len(self.bracket.rounds[round_num])):
            positions.append(start_y + i * spacing)
        return positions
    
    def _draw_match(self, x: int, y: int, node: BracketNode, round_num: int, pos: int):
        """Draw a single match box."""
        # Determine colors
        if node.winner:
            bg_color = self.colors['winner_bg']
        else:
            bg_color = self.colors['match_bg']
        
        # Main match rectangle
        match_id = f"match_{round_num}_{pos}"
        
        self.canvas.create_rectangle(
            x, y, x + self.match_width, y + self.match_height,
            fill=bg_color, outline=self.colors['line'], width=2,
            tags=(match_id, "match")
        )
        
        # Player 1
        p1_name = node.player1.name if node.player1 else "TBD"
        p1_seed = ""
        if round_num == 0 and node.player1:
            try:
                idx = self.bracket.players.index(node.player1) + 1
                p1_seed = f"#{idx} "
            except (ValueError, AttributeError):
                p1_seed = ""
        
        p1_color = self.colors['score'] if node.winner == node.player1 and node.winner else self.colors['text']
        self.canvas.create_text(
            x + 10, y + 18,
            text=f"{p1_seed}{p1_name[:15]}",
            font=("Arial", 11, "bold" if node.winner == node.player1 else "normal"),
            fill=p1_color, anchor="w",
            tags=(match_id,)
        )
        
        # Score 1
        if node.winner:
            self.canvas.create_text(
                x + self.match_width - 15, y + 18,
                text=str(node.score1),
                font=("Arial", 11, "bold"),
                fill=self.colors['score'], anchor="e",
                tags=(match_id,)
            )
        
        # Divider line
        self.canvas.create_line(
            x + 5, y + self.match_height // 2,
            x + self.match_width - 5, y + self.match_height // 2,
            fill=self.colors['line'], width=1,
            tags=(match_id,)
        )
        
        # Player 2
        p2_name = node.player2.name if node.player2 else "TBD"
        p2_seed = ""
        if round_num == 0 and node.player2:
            try:
                idx = self.bracket.players.index(node.player2) + 1
                p2_seed = f"#{idx} "
            except (ValueError, AttributeError):
                p2_seed = ""
        
        p2_color = self.colors['score'] if node.winner == node.player2 and node.winner else self.colors['text']
        self.canvas.create_text(
            x + 10, y + self.match_height - 18,
            text=f"{p2_seed}{p2_name[:15]}",
            font=("Arial", 11, "bold" if node.winner == node.player2 else "normal"),
            fill=p2_color, anchor="w",
            tags=(match_id,)
        )
        
        # Score 2
        if node.winner:
            self.canvas.create_text(
                x + self.match_width - 15, y + self.match_height - 18,
                text=str(node.score2),
                font=("Arial", 11, "bold"),
                fill=self.colors['score'], anchor="e",
                tags=(match_id,)
            )
        
        # Winner crown
        if node.winner and round_num == len(self.bracket.rounds) - 1:
            self.canvas.create_text(
                x + self.match_width // 2, y - 15,
                text="👑 CHAMPION 👑",
                font=("Arial", 12, "bold"),
                fill="#ffd700"
            )
        
        # Make clickable
        self.canvas.tag_bind(match_id, "<Button-1>",
                            lambda e, r=round_num, p=pos: self._on_match_click(r, p))
        self.canvas.tag_bind(match_id, "<Enter>",
                            lambda e, mid=match_id: self._on_match_enter(mid))
        self.canvas.tag_bind(match_id, "<Leave>",
                            lambda e, mid=match_id: self._on_match_leave(mid))
    
    def _draw_connector(self, x: int, y: int, round_num: int, pos: int):
        """Draw connector lines to next round."""
        next_positions = self._get_match_positions(round_num + 1)
        next_pos = pos // 2
        
        if next_pos < len(next_positions):
            next_y = next_positions[next_pos] + self.match_height // 2
            
            # Line from match to right
            line_x = x + self.match_width
            line_y = y + self.match_height // 2
            mid_x = line_x + (self.round_spacing - self.match_width) // 2
            
            # Horizontal line right
            self.canvas.create_line(
                line_x, line_y, mid_x, line_y,
                fill=self.colors['line'], width=2
            )
            
            # Vertical connector
            if pos % 2 == 0:
                # Top match - line goes down
                partner_y = self._get_match_positions(round_num)[pos + 1] + self.match_height // 2
                self.canvas.create_line(
                    mid_x, line_y, mid_x, partner_y,
                    fill=self.colors['line'], width=2
                )
            
            # Line to next match
            self.canvas.create_line(
                mid_x, next_y,
                50 + (round_num + 1) * self.round_spacing, next_y,
                fill=self.colors['line'], width=2
            )
    
    def _on_match_click(self, round_num: int, pos: int):
        """Handle match click."""
        if self.on_match_click:
            self.on_match_click(round_num, pos)
    
    def _on_match_enter(self, match_id: str):
        """Handle mouse enter on match."""
        # Only change the rectangle fill, not text elements
        # Find items with this tag and only modify rectangles
        items = self.canvas.find_withtag(match_id)
        for item in items:
            item_type = self.canvas.type(item)
            if item_type == "rectangle":
                self.canvas.itemconfig(item, fill=self.colors['match_hover'])
            elif item_type == "text":
                # Invert text to white for readability on gray background
                self.canvas.itemconfig(item, fill="#ffffff")
    
    def _on_match_leave(self, match_id: str):
        """Handle mouse leave on match."""
        # Restore original colors
        parts = match_id.split("_")
        round_num = int(parts[1])
        pos = int(parts[2])
        node = self.bracket.rounds[round_num][pos]
        
        # Restore rectangle color
        items = self.canvas.find_withtag(match_id)
        for item in items:
            item_type = self.canvas.type(item)
            if item_type == "rectangle":
                if node.winner:
                    self.canvas.itemconfig(item, fill=self.colors['winner_bg'])
                else:
                    self.canvas.itemconfig(item, fill=self.colors['match_bg'])
        
        # Redraw to restore text colors properly
        self._restore_match_text_colors(match_id, node)
    
    def _restore_match_text_colors(self, match_id: str, node: BracketNode):
        """Restore proper text colors after hover."""
        items = self.canvas.find_withtag(match_id)
        
        # Get text items and restore their colors based on context
        text_items = [item for item in items if self.canvas.type(item) == "text"]
        
        for i, item in enumerate(text_items):
            text_content = self.canvas.itemcget(item, "text")
            
            # Determine color based on whether this player is the winner
            if node.winner:
                # Check if this text represents the winner or a score
                if node.player1 and node.player1.name[:15] in text_content:
                    if node.winner == node.player1:
                        self.canvas.itemconfig(item, fill=self.colors['score'])
                    else:
                        self.canvas.itemconfig(item, fill=self.colors['text'])
                elif node.player2 and node.player2.name[:15] in text_content:
                    if node.winner == node.player2:
                        self.canvas.itemconfig(item, fill=self.colors['score'])
                    else:
                        self.canvas.itemconfig(item, fill=self.colors['text'])
                elif text_content.isdigit():
                    # Score text
                    self.canvas.itemconfig(item, fill=self.colors['score'])
                else:
                    self.canvas.itemconfig(item, fill=self.colors['text'])
            else:
                # No winner yet - all text should be white
                self.canvas.itemconfig(item, fill=self.colors['text'])
    
    def refresh(self):
        """Refresh the bracket display."""
        self.canvas.delete("all")
        self._draw_bracket()


class BracketView(ctk.CTkFrame):
    """Main tournament bracket view."""
    
    def __init__(self, parent, db: DatabaseManager):
        super().__init__(parent, fg_color="transparent")
        self.db = db
        
        self.bracket = None
        self.bracket_canvas = None
        self.selected_players = []
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the main UI."""
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(
            header,
            text="🏆 Tournament Bracket Generator",
            font=get_font(28, "bold")
        ).pack(side="left")
        
        # Export button
        self.export_btn = ctk.CTkButton(
            header,
            text="📄 Export Bracket",
            font=get_font(14),
            fg_color="#3d5a80",
            hover_color="#2d4a70",
            height=40,
            command=self.export_bracket,
            state="disabled"
        )
        self.export_btn.pack(side="right", padx=5)
        
        # Main content area
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Setup panel (shown when no bracket)
        self.setup_panel = ctk.CTkFrame(self.content, fg_color="#1a1a2e", corner_radius=15)
        self.setup_panel.pack(fill="both", expand=True)
        
        self._create_setup_panel()
    
    def _create_setup_panel(self):
        """Create the bracket setup panel."""
        # Title
        ctk.CTkLabel(
            self.setup_panel,
            text="Create Tournament Bracket",
            font=get_font(22, "bold")
        ).pack(pady=(30, 10))
        
        ctk.CTkLabel(
            self.setup_panel,
            text="Select players for the end-of-semester tournament",
            font=get_font(14),
            text_color="#888888"
        ).pack(pady=(0, 20))
        
        # Two column layout
        columns = ctk.CTkFrame(self.setup_panel, fg_color="transparent")
        columns.pack(fill="both", expand=True, padx=30, pady=10)
        
        # Left: Player selection
        left_panel = ctk.CTkFrame(columns, fg_color="#252540", corner_radius=10)
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        ctk.CTkLabel(
            left_panel,
            text="Available Players",
            font=get_font(16, "bold")
        ).pack(pady=15)
        
        # Select all / rank buttons
        btn_row = ctk.CTkFrame(left_panel, fg_color="transparent")
        btn_row.pack(fill="x", padx=15)
        
        ctk.CTkButton(
            btn_row, text="Select Top 4", height=30, width=100,
            fg_color="#3d5a80", hover_color="#2d4a70",
            command=lambda: self.select_top_n(4)
        ).pack(side="left", padx=3)
        
        ctk.CTkButton(
            btn_row, text="Select Top 8", height=30, width=100,
            fg_color="#3d5a80", hover_color="#2d4a70",
            command=lambda: self.select_top_n(8)
        ).pack(side="left", padx=3)
        
        ctk.CTkButton(
            btn_row, text="Clear", height=30, width=60,
            fg_color="#555555", hover_color="#444444",
            command=self.clear_selection
        ).pack(side="right", padx=3)
        
        # Player list
        self.players_scroll = ctk.CTkScrollableFrame(left_panel, fg_color="transparent")
        self.players_scroll.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.player_checkboxes = {}
        self._load_players()
        
        # Right: Preview & options
        right_panel = ctk.CTkFrame(columns, fg_color="#252540", corner_radius=10, width=300)
        right_panel.pack(side="right", fill="both", padx=(10, 0))
        right_panel.pack_propagate(False)
        
        ctk.CTkLabel(
            right_panel,
            text="Tournament Settings",
            font=get_font(16, "bold")
        ).pack(pady=15)
        
        # Bracket size
        size_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
        size_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(
            size_frame, text="Bracket Size:",
            font=get_font(13)
        ).pack(anchor="w")
        
        self.size_var = ctk.StringVar(value="Auto")
        ctk.CTkComboBox(
            size_frame,
            values=["Auto", "4 Players", "8 Players", "16 Players"],
            variable=self.size_var,
            height=35,
            width=150
        ).pack(pady=5)
        
        # Tournament name
        name_frame = ctk.CTkFrame(right_panel, fg_color="transparent")
        name_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(
            name_frame, text="Tournament Name:",
            font=get_font(13)
        ).pack(anchor="w")
        
        self.tourney_name = ctk.CTkEntry(
            name_frame,
            height=35,
            placeholder_text="EcoPOOL Championship"
        )
        self.tourney_name.pack(fill="x", pady=5)
        
        # Selected count
        self.selected_label = ctk.CTkLabel(
            right_panel,
            text="0 players selected",
            font=get_font(14),
            text_color="#888888"
        )
        self.selected_label.pack(pady=20)
        
        # Generate button
        ctk.CTkButton(
            right_panel,
            text="🏆 Generate Bracket",
            font=get_font(16, "bold"),
            height=50,
            fg_color="#2d7a3e",
            hover_color="#1a5f2a",
            command=self.generate_bracket
        ).pack(fill="x", padx=20, pady=10)
        
        # Back button (for when bracket is shown)
        self.back_btn = ctk.CTkButton(
            right_panel,
            text="← New Bracket",
            font=get_font(13),
            height=35,
            fg_color="#555555",
            hover_color="#444444",
            command=self.reset_to_setup
        )
    
    def _load_players(self):
        """Load players into the selection list."""
        for widget in self.players_scroll.winfo_children():
            widget.destroy()
        
        self.player_checkboxes.clear()
        players = self.db.get_leaderboard("wins")  # Get ranked players
        
        for i, player in enumerate(players, 1):
            row = ctk.CTkFrame(self.players_scroll, fg_color="#353550", corner_radius=8)
            row.pack(fill="x", pady=3)
            
            # Checkbox
            var = ctk.BooleanVar(value=False)
            cb = ctk.CTkCheckBox(
                row,
                text="",
                variable=var,
                width=24,
                fg_color="#2d7a3e",
                command=self._update_selection_count
            )
            cb.pack(side="left", padx=10, pady=8)
            
            # Rank
            ctk.CTkLabel(
                row,
                text=f"#{i}",
                font=get_font(12, "bold"),
                text_color="#4CAF50",
                width=30
            ).pack(side="left", padx=5)
            
            # Profile picture
            try:
                pic = ProfilePicture(row, size=35, 
                                    image_path=player.profile_picture,
                                    player_name=player.name)
                pic.pack(side="left", padx=5)
            except (OSError, FileNotFoundError, AttributeError):
                pass
            
            # Name
            ctk.CTkLabel(
                row,
                text=player.name,
                font=get_font(13)
            ).pack(side="left", padx=10)
            
            # Stats
            stats = f"{player.games_won}W | {player.win_rate:.0f}%"
            ctk.CTkLabel(
                row,
                text=stats,
                font=get_font(11),
                text_color="#888888"
            ).pack(side="right", padx=15)
            
            self.player_checkboxes[player.id] = (var, player)
    
    def _update_selection_count(self):
        """Update the selected player count label."""
        count = sum(1 for var, _ in self.player_checkboxes.values() if var.get())
        self.selected_label.configure(text=f"{count} players selected")
        
        # Update color based on valid count
        if count in [2, 4, 8, 16]:
            self.selected_label.configure(text_color="#4CAF50")
        elif count > 1:
            self.selected_label.configure(text_color="#ffd700")
        else:
            self.selected_label.configure(text_color="#888888")
    
    def select_top_n(self, n: int):
        """Select top N ranked players."""
        self.clear_selection()
        
        count = 0
        for pid, (var, player) in self.player_checkboxes.items():
            if count < n:
                var.set(True)
                count += 1
        
        self._update_selection_count()
    
    def clear_selection(self):
        """Clear all selections."""
        for var, _ in self.player_checkboxes.values():
            var.set(False)
        self._update_selection_count()
    
    def generate_bracket(self):
        """Generate the tournament bracket."""
        # Get selected players
        selected = [p for pid, (var, p) in self.player_checkboxes.items() if var.get()]
        
        if len(selected) < 2:
            messagebox.showwarning("Not Enough Players", 
                                  "Please select at least 2 players for the bracket.")
            return
        
        # Determine bracket size
        size_str = self.size_var.get()
        if size_str == "Auto":
            bracket_size = None
        else:
            bracket_size = int(size_str.split()[0])
        
        # Create bracket
        self.bracket = TournamentBracket(selected, bracket_size)
        self.selected_players = selected
        
        # Hide setup, show bracket
        self.setup_panel.pack_forget()
        self._show_bracket()
        
        # Enable export
        self.export_btn.configure(state="normal")
    
    def _show_bracket(self):
        """Show the bracket visualization."""
        # Bracket display frame
        self.bracket_frame = ctk.CTkFrame(self.content, fg_color="#1a1a2e", corner_radius=15)
        self.bracket_frame.pack(fill="both", expand=True)
        
        # Header with tournament name
        header = ctk.CTkFrame(self.bracket_frame, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=15)
        
        name = self.tourney_name.get() or "EcoPOOL Championship"
        ctk.CTkLabel(
            header,
            text=f"🏆 {name} 🏆",
            font=get_font(24, "bold"),
            text_color="#ffd700"
        ).pack()
        
        ctk.CTkLabel(
            header,
            text=f"{len(self.selected_players)} Players | {self.bracket.bracket_size}-Player Bracket",
            font=get_font(13),
            text_color="#888888"
        ).pack(pady=5)
        
        # Bracket canvas
        self.bracket_canvas = BracketCanvas(
            self.bracket_frame,
            self.bracket,
            self.db,
            on_match_click=self._on_match_click
        )
        self.bracket_canvas.pack(fill="both", expand=True, padx=15, pady=10)
        
        # Bottom controls
        controls = ctk.CTkFrame(self.bracket_frame, fg_color="transparent")
        controls.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkButton(
            controls,
            text="← Create New Bracket",
            font=get_font(13),
            height=35,
            fg_color="#555555",
            hover_color="#444444",
            command=self.reset_to_setup
        ).pack(side="left")
        
        ctk.CTkLabel(
            controls,
            text="Click on a match to set the winner",
            font=get_font(12),
            text_color="#666666"
        ).pack(side="right")
    
    def _on_match_click(self, round_num: int, pos: int):
        """Handle click on a bracket match."""
        node = self.bracket.rounds[round_num][pos]
        
        if not node.player1 or not node.player2:
            messagebox.showinfo("Match Not Ready", 
                              "Both players must be determined before setting a winner.")
            return
        
        # Create winner selection dialog
        self._show_winner_dialog(node, round_num, pos)
    
    def _show_winner_dialog(self, node: BracketNode, round_num: int, pos: int):
        """Show dialog to select match winner."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Set Match Winner")
        dialog.geometry("480x420")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        
        # Center
        dialog.update_idletasks()
        x = self.winfo_toplevel().winfo_x() + (self.winfo_toplevel().winfo_width() // 2) - 240
        y = self.winfo_toplevel().winfo_y() + (self.winfo_toplevel().winfo_height() // 2) - 210
        dialog.geometry(f"+{x}+{y}")
        
        round_name = self.bracket.get_round_name(round_num)
        
        ctk.CTkLabel(
            dialog,
            text=f"{round_name}",
            font=get_font(22, "bold"),
            text_color="#4CAF50"
        ).pack(pady=(25, 15))
        
        # Player buttons
        players_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        players_frame.pack(fill="x", padx=40, pady=10)
        
        winner_var = ctk.IntVar(value=0)
        
        # Player 1
        p1_frame = ctk.CTkFrame(players_frame, fg_color="#1e4a1e", corner_radius=10)
        p1_frame.pack(fill="x", pady=8)
        
        ctk.CTkRadioButton(
            p1_frame,
            text=node.player1.name,
            variable=winner_var,
            value=1,
            font=get_font(15),
            fg_color="#4CAF50"
        ).pack(side="left", padx=20, pady=18)
        
        # Player 2
        p2_frame = ctk.CTkFrame(players_frame, fg_color="#1e3a5f", corner_radius=10)
        p2_frame.pack(fill="x", pady=8)
        
        ctk.CTkRadioButton(
            p2_frame,
            text=node.player2.name,
            variable=winner_var,
            value=2,
            font=get_font(15),
            fg_color="#2196F3"
        ).pack(side="left", padx=20, pady=18)
        
        # Score inputs
        score_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        score_frame.pack(fill="x", padx=40, pady=20)
        
        ctk.CTkLabel(score_frame, text="Games Won:", font=get_font(14, "bold")).pack()
        
        scores_row = ctk.CTkFrame(score_frame, fg_color="transparent")
        scores_row.pack(pady=10)
        
        # Truncate names more reasonably for the score display
        p1_display = node.player1.name if len(node.player1.name) <= 15 else node.player1.name[:12] + "..."
        p2_display = node.player2.name if len(node.player2.name) <= 15 else node.player2.name[:12] + "..."
        
        ctk.CTkLabel(scores_row, text=p1_display, font=get_font(13), width=120, anchor="e").pack(side="left")
        score1_entry = ctk.CTkEntry(scores_row, width=50, height=35, font=get_font(14))
        score1_entry.insert(0, "2")
        score1_entry.pack(side="left", padx=8)
        
        ctk.CTkLabel(scores_row, text="-", font=get_font(16, "bold"), width=20).pack(side="left")
        
        score2_entry = ctk.CTkEntry(scores_row, width=50, height=35, font=get_font(14))
        score2_entry.insert(0, "0")
        score2_entry.pack(side="left", padx=8)
        ctk.CTkLabel(scores_row, text=p2_display, font=get_font(13), width=120, anchor="w").pack(side="left")
        
        def save_winner():
            winner_idx = winner_var.get()
            if winner_idx == 0:
                messagebox.showwarning("Select Winner", "Please select a winner.")
                return
            
            try:
                score1 = int(score1_entry.get())
                score2 = int(score2_entry.get())
            except (ValueError, TypeError):
                score1 = 2
                score2 = 0
            
            winner = node.player1 if winner_idx == 1 else node.player2
            self.bracket.set_winner(round_num, pos, winner, score1, score2)
            
            # Refresh bracket display
            self.bracket_canvas.refresh()
            
            # Check if champion
            if self.bracket.champion:
                dialog.destroy()
                self._celebrate_champion()
            else:
                dialog.destroy()
        
        # Buttons
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=20)
        
        ctk.CTkButton(
            btn_frame, text="Cancel", width=120, height=40,
            font=get_font(14),
            fg_color="#555555", hover_color="#444444",
            command=dialog.destroy
        ).pack(side="left", padx=15)
        
        ctk.CTkButton(
            btn_frame, text="Set Winner", width=120, height=40,
            font=get_font(14, "bold"),
            fg_color="#2d7a3e", hover_color="#1a5f2a",
            command=save_winner
        ).pack(side="left", padx=15)
    
    def _celebrate_champion(self):
        """Celebrate the tournament champion."""
        # Refresh bracket to show final state
        self.bracket_canvas.refresh()
        
        # Force UI update
        self.update_idletasks()
        
        # Champion announcement
        champ_name = self.bracket.champion.name
        messagebox.showinfo(
            "🏆 CHAMPION CROWNED! 🏆",
            f"Congratulations to {champ_name}!\n\n"
            f"They are the {self.tourney_name.get() or 'EcoPOOL'} Champion!"
        )
        
        # Refresh again after dialog closes to ensure bracket is visible
        self.bracket_canvas.refresh()
    
    def reset_to_setup(self):
        """Reset to the setup view."""
        if hasattr(self, 'bracket_frame'):
            self.bracket_frame.destroy()
        
        self.bracket = None
        self.bracket_canvas = None
        self.export_btn.configure(state="disabled")
        
        self.setup_panel.pack(fill="both", expand=True)
        self._load_players()
    
    def export_bracket(self):
        """Export the bracket to an image."""
        if not self.bracket:
            return
        
        filepath = filedialog.asksaveasfilename(
            defaultextension=".png",
            filetypes=[
                ("PNG Image", "*.png"),
                ("JPEG Image", "*.jpg"),
                ("All files", "*.*")
            ],
            title="Export Bracket",
            initialfile=f"{self.tourney_name.get() or 'tournament'}_bracket.png"
        )
        
        if not filepath:
            return
        
        try:
            if HAS_PIL:
                # Render bracket to image using PIL
                img = self._render_bracket_to_image()
                img.save(filepath)
                messagebox.showinfo("Export Success", f"Bracket exported to:\n{filepath}")
            else:
                messagebox.showinfo("Export",
                    "PIL/Pillow not available for image export.\n"
                    "Please install Pillow: pip install Pillow")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export: {str(e)}")
    
    def _render_bracket_to_image(self):
        """Render the bracket to a PIL Image."""
        from PIL import Image, ImageDraw, ImageFont
        
        # Canvas dimensions from bracket_canvas
        canvas = self.bracket_canvas
        width = canvas.canvas_width + 50
        height = canvas.canvas_height + 50
        
        # Colors
        colors = {
            'bg': '#161b22',
            'match_bg': '#252540',
            'winner_bg': '#1e4a1e',
            'line': '#4CAF50',
            'text': '#ffffff',
            'seed': '#888888',
            'score': '#ffd700',
            'title': '#ffd700'
        }
        
        # Create image
        img = Image.new('RGB', (width, height), colors['bg'])
        draw = ImageDraw.Draw(img)
        
        # Try to use the local font first, then system fonts, then default
        import os
        # Get the path to the fonts directory (relative to this file's parent directory)
        views_dir = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.dirname(views_dir)
        local_font = os.path.join(project_dir, "fonts", "HelveticaNeueMedium.otf")
        
        font_title = None
        font_round = None
        font_player = None
        font_score = None
        
        # Try local font first
        if os.path.exists(local_font):
            try:
                font_title = ImageFont.truetype(local_font, 24)
                font_round = ImageFont.truetype(local_font, 16)
                font_player = ImageFont.truetype(local_font, 12)
                font_score = ImageFont.truetype(local_font, 12)
            except:
                pass
        
        # Fallback to system Arial (Windows)
        if font_title is None:
            try:
                font_title = ImageFont.truetype("arial.ttf", 24)
                font_round = ImageFont.truetype("arial.ttf", 16)
                font_player = ImageFont.truetype("arial.ttf", 12)
                font_score = ImageFont.truetype("arial.ttf", 12)
            except:
                pass
        
        # Fallback to DejaVu (Linux)
        if font_title is None:
            try:
                font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 24)
                font_round = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
                font_player = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
                font_score = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
            except:
                pass
        
        # Final fallback to default
        if font_title is None:
            font_title = ImageFont.load_default()
            font_round = ImageFont.load_default()
            font_player = ImageFont.load_default()
            font_score = ImageFont.load_default()
        
        # Draw title
        title = self.tourney_name.get() or "EcoPOOL Championship"
        title_text = f"🏆 {title} 🏆"
        # Center the title
        try:
            title_bbox = draw.textbbox((0, 0), title_text, font=font_title)
            title_width = title_bbox[2] - title_bbox[0]
        except:
            title_width = len(title_text) * 12
        draw.text(((width - title_width) // 2, 10), title_text, fill=colors['title'], font=font_title)
        
        # Bracket dimensions
        match_width = canvas.match_width
        match_height = canvas.match_height
        round_spacing = canvas.round_spacing
        match_spacing = canvas.match_spacing
        
        # Draw round labels
        for round_num, round_matches in enumerate(self.bracket.rounds):
            x = 50 + round_num * round_spacing
            round_name = self.bracket.get_round_name(round_num)
            draw.text((x + match_width // 2 - 30, 50), round_name, fill=colors['line'], font=font_round)
        
        # Helper to get match Y positions
        def get_match_positions(round_num):
            if round_num == 0:
                start_y = 85
                spacing = match_spacing
            else:
                prev_positions = get_match_positions(round_num - 1)
                start_y = (prev_positions[0] + prev_positions[1]) // 2 - match_height // 2
                spacing = match_spacing * (2 ** round_num)
            
            positions = []
            for i in range(len(self.bracket.rounds[round_num])):
                positions.append(int(start_y + i * spacing))
            return positions
        
        # Draw matches and lines
        for round_num, round_matches in enumerate(self.bracket.rounds):
            positions = get_match_positions(round_num)
            
            for pos, node in enumerate(round_matches):
                x = 50 + round_num * round_spacing
                y = positions[pos]
                
                # Match background
                bg_color = colors['winner_bg'] if node.winner else colors['match_bg']
                draw.rectangle([x, y, x + match_width, y + match_height], fill=bg_color, outline=colors['line'], width=2)
                
                # Player 1
                p1_name = node.player1.name if node.player1 else "TBD"
                p1_seed = ""
                if round_num == 0 and node.player1:
                    try:
                        idx = self.bracket.players.index(node.player1) + 1
                        p1_seed = f"#{idx} "
                    except:
                        pass
                
                p1_color = colors['score'] if node.winner == node.player1 and node.winner else colors['text']
                p1_text = f"{p1_seed}{p1_name[:15]}"
                draw.text((x + 10, y + 8), p1_text, fill=p1_color, font=font_player)
                
                # Score 1
                if node.winner:
                    draw.text((x + match_width - 25, y + 8), str(node.score1), fill=colors['score'], font=font_score)
                
                # Divider
                draw.line([x + 5, y + match_height // 2, x + match_width - 5, y + match_height // 2], fill=colors['line'], width=1)
                
                # Player 2
                p2_name = node.player2.name if node.player2 else "TBD"
                p2_seed = ""
                if round_num == 0 and node.player2:
                    try:
                        idx = self.bracket.players.index(node.player2) + 1
                        p2_seed = f"#{idx} "
                    except:
                        pass
                
                p2_color = colors['score'] if node.winner == node.player2 and node.winner else colors['text']
                p2_text = f"{p2_seed}{p2_name[:15]}"
                draw.text((x + 10, y + match_height - 22), p2_text, fill=p2_color, font=font_player)
                
                # Score 2
                if node.winner:
                    draw.text((x + match_width - 25, y + match_height - 22), str(node.score2), fill=colors['score'], font=font_score)
                
                # Champion crown
                if node.winner and round_num == len(self.bracket.rounds) - 1:
                    crown_text = "CHAMPION"
                    draw.text((x + match_width // 2 - 35, y - 20), crown_text, fill=colors['title'], font=font_round)
                
                # Draw connector lines to next round
                if round_num + 1 < len(self.bracket.rounds):
                    next_positions = get_match_positions(round_num + 1)
                    next_pos = pos // 2
                    
                    if next_pos < len(next_positions):
                        next_y = next_positions[next_pos] + match_height // 2
                        
                        line_x = x + match_width
                        line_y = y + match_height // 2
                        mid_x = line_x + (round_spacing - match_width) // 2
                        
                        # Horizontal right
                        draw.line([line_x, line_y, mid_x, line_y], fill=colors['line'], width=2)
                        
                        # Vertical connector (only for even positions)
                        if pos % 2 == 0 and pos + 1 < len(positions):
                            partner_y = positions[pos + 1] + match_height // 2
                            draw.line([mid_x, line_y, mid_x, partner_y], fill=colors['line'], width=2)
                        
                        # Line to next match
                        draw.line([mid_x, next_y, 50 + (round_num + 1) * round_spacing, next_y], fill=colors['line'], width=2)
        
        return img
