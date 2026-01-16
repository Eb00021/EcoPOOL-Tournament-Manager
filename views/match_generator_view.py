"""
EcoPOOL League - Match Generator View
Fixed pair assignment, full evening schedule generation with queue system, and buy-in tracking.
"""

import customtkinter as ctk
from tkinter import messagebox, filedialog
from datetime import datetime
from database import DatabaseManager
from match_generator import MatchGenerator
from exporter import Exporter
from fonts import get_font


class MatchGeneratorView(ctk.CTkFrame):
    def __init__(self, parent, db: DatabaseManager, on_match_created=None, 
                 on_pairings_changed=None, initial_pairings=None, initial_multi_round=False):
        super().__init__(parent, fg_color="transparent")
        self.db = db
        self.generator = MatchGenerator(db)
        self.exporter = Exporter(db)
        self.on_match_created = on_match_created
        self.on_pairings_changed = on_pairings_changed
        
        self.selected_players = set()
        self.current_pairs = []  # List of (player1_id, player2_id) tuples
        self.generated_schedule = None
        self.current_league_night_id = None
        self.buyin_amount = 3.0
        self.buyins_paid = {}  # player_id -> bool
        
        # Manual pairing state
        self.manual_pair_selection = []  # For manual pairing mode
        
        # Store initial state to restore after UI setup
        self._initial_state = initial_pairings
        
        self.setup_ui()
        
        # Load persistent settings from database
        self._load_persistent_settings()
        
        self.load_players()
        
        # Restore state if provided (after UI is set up)
        if self._initial_state:
            self._restore_state(self._initial_state)
    
    def setup_ui(self):
        # Main container with two columns
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Left column - Setup
        self.left_col = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.left_col.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        # Right column - Schedule Preview
        self.right_col = ctk.CTkFrame(self.main_container, fg_color="#1a1a2e", corner_radius=15, width=450)
        self.right_col.pack(side="right", fill="both", padx=(5, 0))
        self.right_col.pack_propagate(False)
        
        self._setup_left_column()
        self._setup_right_column()
    
    def _setup_left_column(self):
        """Setup the left column with player selection, pair formation, and config."""
        # Header
        header = ctk.CTkFrame(self.left_col, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(
            header, 
            text="League Night Setup",
            font=get_font(24, "bold")
        ).pack(side="left")
        
        # Configuration row
        config_frame = ctk.CTkFrame(self.left_col, fg_color="#252540", corner_radius=10)
        config_frame.pack(fill="x", pady=(0, 10))
        
        config_inner = ctk.CTkFrame(config_frame, fg_color="transparent")
        config_inner.pack(fill="x", padx=15, pady=12)
        
        # Table count
        ctk.CTkLabel(config_inner, text="Tables:", font=get_font(13)).pack(side="left")
        
        self.table_count_var = ctk.IntVar(value=3)
        table_frame = ctk.CTkFrame(config_inner, fg_color="transparent")
        table_frame.pack(side="left", padx=10)
        
        ctk.CTkButton(
            table_frame, text="-", width=30, height=30,
            fg_color="#c44536", hover_color="#a43526",
            command=lambda: self._adjust_table_count(-1)
        ).pack(side="left", padx=2)
        
        self.table_count_label = ctk.CTkLabel(
            table_frame, text="3", font=get_font(16, "bold"),
            width=40, text_color="#4CAF50"
        )
        self.table_count_label.pack(side="left", padx=5)
        
        ctk.CTkButton(
            table_frame, text="+", width=30, height=30,
            fg_color="#2d7a3e", hover_color="#1a5f2a",
            command=lambda: self._adjust_table_count(1)
        ).pack(side="left", padx=2)
        
        # Separator
        ctk.CTkFrame(config_inner, width=2, height=30, fg_color="#444444").pack(side="left", padx=15)
        
        # Min games per pair
        ctk.CTkLabel(config_inner, text="Min Games/Pair:", font=get_font(13)).pack(side="left")
        
        self.min_games_var = ctk.IntVar(value=4)
        games_frame = ctk.CTkFrame(config_inner, fg_color="transparent")
        games_frame.pack(side="left", padx=10)
        
        ctk.CTkButton(
            games_frame, text="-", width=30, height=30,
            fg_color="#c44536", hover_color="#a43526",
            command=lambda: self._adjust_min_games(-1)
        ).pack(side="left", padx=2)
        
        self.min_games_label = ctk.CTkLabel(
            games_frame, text="4", font=get_font(16, "bold"),
            width=40, text_color="#4CAF50"
        )
        self.min_games_label.pack(side="left", padx=5)
        
        ctk.CTkButton(
            games_frame, text="+", width=30, height=30,
            fg_color="#2d7a3e", hover_color="#1a5f2a",
            command=lambda: self._adjust_min_games(1)
        ).pack(side="left", padx=2)
        
        # Separator
        ctk.CTkFrame(config_inner, width=2, height=30, fg_color="#444444").pack(side="left", padx=15)
        
        # Buy-in amount
        ctk.CTkLabel(config_inner, text="Buy-in: $", font=get_font(13)).pack(side="left")
        
        self.buyin_entry = ctk.CTkEntry(
            config_inner, width=60, height=30, font=get_font(13),
            placeholder_text="3"
        )
        self.buyin_entry.insert(0, "3")
        self.buyin_entry.pack(side="left", padx=5)
        
        # Two panels side by side: Players and Pairs/Buyins
        panels = ctk.CTkFrame(self.left_col, fg_color="transparent")
        panels.pack(fill="both", expand=True)
        
        # Player selection panel
        player_panel = ctk.CTkFrame(panels, fg_color="#1a1a2e", corner_radius=15)
        player_panel.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        ctk.CTkLabel(
            player_panel,
            text="Select Players",
            font=get_font(16, "bold")
        ).pack(pady=(15, 5))
        
        # Select all / Deselect all
        btn_row = ctk.CTkFrame(player_panel, fg_color="transparent")
        btn_row.pack(fill="x", padx=15)
        
        ctk.CTkButton(
            btn_row, text="All", height=28, width=60,
            fg_color="#3d5a80", hover_color="#2d4a70",
            command=self.select_all
        ).pack(side="left", padx=2)
        
        ctk.CTkButton(
            btn_row, text="None", height=28, width=60,
            fg_color="#555555", hover_color="#444444",
            command=self.deselect_all
        ).pack(side="left", padx=2)
        
        self.selected_count_label = ctk.CTkLabel(
            btn_row, text="0 selected",
            font=get_font(12),
            text_color="#888888"
        )
        self.selected_count_label.pack(side="right", padx=5)
        
        self.players_scroll = ctk.CTkScrollableFrame(
            player_panel, fg_color="transparent", height=200
        )
        self.players_scroll.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.player_checkboxes = {}
        
        # Pairs and Buy-ins panel
        pairs_panel = ctk.CTkFrame(panels, fg_color="#1a1a2e", corner_radius=15)
        pairs_panel.pack(side="right", fill="both", expand=True, padx=(5, 0))
        
        # Pair formation mode selector
        mode_frame = ctk.CTkFrame(pairs_panel, fg_color="transparent")
        mode_frame.pack(fill="x", padx=15, pady=(15, 5))
        
        ctk.CTkLabel(
            mode_frame,
            text="Pair Formation",
            font=get_font(16, "bold")
        ).pack(side="left")
        
        self.pair_mode_var = ctk.StringVar(value="random")
        
        mode_buttons = ctk.CTkFrame(pairs_panel, fg_color="transparent")
        mode_buttons.pack(fill="x", padx=15, pady=5)
        
        ctk.CTkRadioButton(
            mode_buttons, text="Random", variable=self.pair_mode_var, value="random",
            font=get_font(12), fg_color="#2d7a3e", hover_color="#1a5f2a"
        ).pack(side="left", padx=5)
        
        ctk.CTkRadioButton(
            mode_buttons, text="Skill-Based", variable=self.pair_mode_var, value="skill",
            font=get_font(12), fg_color="#3d5a80", hover_color="#2d4a70"
        ).pack(side="left", padx=5)
        
        ctk.CTkRadioButton(
            mode_buttons, text="Manual", variable=self.pair_mode_var, value="manual",
            font=get_font(12), fg_color="#6b4e8a", hover_color="#5b3e7a"
        ).pack(side="left", padx=5)
        
        # Create Pairs button
        self.create_pairs_btn = ctk.CTkButton(
            pairs_panel,
            text="Create Pairs",
            font=get_font(14, "bold"),
            height=40,
            fg_color="#2d7a3e",
            hover_color="#1a5f2a",
            command=self.create_pairs
        )
        self.create_pairs_btn.pack(fill="x", padx=15, pady=10)
        
        # Pairs display (scrollable)
        self.pairs_scroll = ctk.CTkScrollableFrame(
            pairs_panel, fg_color="transparent", height=150
        )
        self.pairs_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 5))
        
        # Buy-in tracking section
        buyin_header = ctk.CTkFrame(pairs_panel, fg_color="#252540", corner_radius=8)
        buyin_header.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(
            buyin_header,
            text="Buy-in Tracking",
            font=get_font(13, "bold")
        ).pack(side="left", padx=10, pady=8)
        
        self.pot_label = ctk.CTkLabel(
            buyin_header,
            text="Pot: $0 / $0",
            font=get_font(12),
            text_color="#4CAF50"
        )
        self.pot_label.pack(side="right", padx=10, pady=8)
        
        self.buyins_scroll = ctk.CTkScrollableFrame(
            pairs_panel, fg_color="transparent", height=100
        )
        self.buyins_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        # Generate Schedule button
        self.generate_btn = ctk.CTkButton(
            self.left_col,
            text="Generate Full Schedule",
            font=get_font(16, "bold"),
            height=50,
            fg_color="#2d7a3e",
            hover_color="#1a5f2a",
            command=self.generate_schedule,
            state="disabled"
        )
        self.generate_btn.pack(fill="x", pady=(10, 0))
    
    def _setup_right_column(self):
        """Setup the right column with schedule preview."""
        ctk.CTkLabel(
            self.right_col,
            text="Schedule Preview",
            font=get_font(18, "bold")
        ).pack(pady=15)
        
        # Stats summary
        self.stats_frame = ctk.CTkFrame(self.right_col, fg_color="#252540", corner_radius=10)
        self.stats_frame.pack(fill="x", padx=15, pady=(0, 10))
        
        self.stats_label = ctk.CTkLabel(
            self.stats_frame,
            text="Create pairs and generate schedule",
            font=get_font(12),
            text_color="#888888"
        )
        self.stats_label.pack(pady=10)
        
        # Live games section
        live_header = ctk.CTkFrame(self.right_col, fg_color="#1e4a1e", corner_radius=8)
        live_header.pack(fill="x", padx=15, pady=(5, 5))
        
        ctk.CTkLabel(
            live_header,
            text="LIVE - On Tables",
            font=get_font(14, "bold"),
            text_color="#4CAF50"
        ).pack(pady=8)
        
        self.live_scroll = ctk.CTkScrollableFrame(
            self.right_col, fg_color="transparent", height=150
        )
        self.live_scroll.pack(fill="x", padx=15, pady=(0, 10))
        
        self.live_placeholder = ctk.CTkLabel(
            self.live_scroll,
            text="No live games yet",
            font=get_font(12),
            text_color="#666666"
        )
        self.live_placeholder.pack(pady=20)
        
        # Queue section
        queue_header = ctk.CTkFrame(self.right_col, fg_color="#3d3a1e", corner_radius=8)
        queue_header.pack(fill="x", padx=15, pady=(5, 5))
        
        ctk.CTkLabel(
            queue_header,
            text="QUEUE - Waiting",
            font=get_font(14, "bold"),
            text_color="#ffd700"
        ).pack(pady=8)
        
        self.queue_scroll = ctk.CTkScrollableFrame(
            self.right_col, fg_color="transparent", height=200
        )
        self.queue_scroll.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        
        self.queue_placeholder = ctk.CTkLabel(
            self.queue_scroll,
            text="No queued games",
            font=get_font(12),
            text_color="#666666"
        )
        self.queue_placeholder.pack(pady=20)
        
        # Action buttons
        btn_frame = ctk.CTkFrame(self.right_col, fg_color="transparent")
        btn_frame.pack(fill="x", padx=15, pady=10)
        
        self.export_btn = ctk.CTkButton(
            btn_frame,
            text="Export PDF",
            font=get_font(12),
            height=35,
            fg_color="#3d5a80",
            hover_color="#2d4a70",
            command=self.export_schedule,
            state="disabled"
        )
        self.export_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        self.clear_btn = ctk.CTkButton(
            btn_frame,
            text="Clear",
            font=get_font(12),
            height=35,
            fg_color="#c44536",
            hover_color="#a43526",
            command=self.clear_schedule,
            state="disabled"
        )
        self.clear_btn.pack(side="left", fill="x", expand=True, padx=(5, 0))
        
        # Create matches button
        self.create_matches_btn = ctk.CTkButton(
            self.right_col,
            text="Create All Matches",
            font=get_font(14, "bold"),
            height=45,
            fg_color="#4CAF50",
            hover_color="#388E3C",
            command=self.create_all_matches,
            state="disabled"
        )
        self.create_matches_btn.pack(fill="x", padx=15, pady=(0, 15))
    
    def _adjust_table_count(self, delta: int):
        """Adjust the table count."""
        new_val = max(1, min(10, self.table_count_var.get() + delta))
        self.table_count_var.set(new_val)
        self.table_count_label.configure(text=str(new_val))
        # Save to database for persistence
        self.db.set_setting("match_gen_table_count", str(new_val))
    
    def _adjust_min_games(self, delta: int):
        """Adjust the minimum games per pair."""
        new_val = max(1, min(10, self.min_games_var.get() + delta))
        self.min_games_var.set(new_val)
        self.min_games_label.configure(text=str(new_val))
        # Save to database for persistence
        self.db.set_setting("match_gen_min_games", str(new_val))
    
    def _load_persistent_settings(self):
        """Load persistent settings from database."""
        # Table count
        saved_table_count = self.db.get_setting("match_gen_table_count", "3")
        try:
            table_count = int(saved_table_count)
            self.table_count_var.set(table_count)
            self.table_count_label.configure(text=str(table_count))
        except ValueError:
            pass
        
        # Min games per pair
        saved_min_games = self.db.get_setting("match_gen_min_games", "4")
        try:
            min_games = int(saved_min_games)
            self.min_games_var.set(min_games)
            self.min_games_label.configure(text=str(min_games))
        except ValueError:
            pass
        
        # Buy-in amount
        saved_buyin = self.db.get_setting("match_gen_buyin", "3")
        try:
            buyin = float(saved_buyin)
            self.buyin_amount = buyin
            self.buyin_entry.delete(0, 'end')
            self.buyin_entry.insert(0, str(int(buyin) if buyin == int(buyin) else buyin))
        except ValueError:
            pass
        
        # Pair mode
        saved_mode = self.db.get_setting("match_gen_pair_mode", "random")
        if saved_mode in ("random", "skill", "manual"):
            self.pair_mode_var.set(saved_mode)
    
    def _save_persistent_settings(self):
        """Save current settings to database for persistence."""
        self.db.set_setting("match_gen_table_count", str(self.table_count_var.get()))
        self.db.set_setting("match_gen_min_games", str(self.min_games_var.get()))
        
        # Save buy-in amount
        try:
            buyin = float(self.buyin_entry.get())
            self.db.set_setting("match_gen_buyin", str(buyin))
        except ValueError:
            pass
        
        # Save pair mode
        self.db.set_setting("match_gen_pair_mode", self.pair_mode_var.get())
    
    def load_players(self):
        """Load players into the selection list."""
        for widget in self.players_scroll.winfo_children():
            widget.destroy()
        
        self.player_checkboxes.clear()
        players = self.db.get_all_players()
        
        for player in players:
            var = ctk.BooleanVar(value=False)
            
            cb_frame = ctk.CTkFrame(self.players_scroll, fg_color="#252540", corner_radius=8)
            cb_frame.pack(fill="x", pady=2)
            
            cb = ctk.CTkCheckBox(
                cb_frame,
                text=player.name,
                variable=var,
                font=get_font(13),
                fg_color="#2d7a3e",
                hover_color="#1a5f2a",
                command=self.update_selection_count
            )
            cb.pack(side="left", padx=10, pady=8)
            
            # Show points instead of wins for ranking
            if player.games_played > 0:
                stats_text = f"{player.total_points} pts"
                ctk.CTkLabel(
                    cb_frame,
                    text=stats_text,
                    font=get_font(10),
                    text_color="#888888"
                ).pack(side="right", padx=10)
            
            self.player_checkboxes[player.id] = (var, player)
    
    def select_all(self):
        for var, _ in self.player_checkboxes.values():
            var.set(True)
        self.update_selection_count()
    
    def deselect_all(self):
        for var, _ in self.player_checkboxes.values():
            var.set(False)
        self.update_selection_count()
    
    def update_selection_count(self):
        count = sum(1 for var, _ in self.player_checkboxes.values() if var.get())
        self.selected_count_label.configure(text=f"{count} selected")
        
        # Reset pairs if selection changes
        if self.current_pairs:
            self.current_pairs = []
            self._update_pairs_display()
            self.generate_btn.configure(state="disabled")
    
    def get_selected_player_ids(self) -> list[int]:
        """Get list of selected player IDs."""
        return [pid for pid, (var, _) in self.player_checkboxes.items() if var.get()]
    
    def create_pairs(self):
        """Create pairs based on selected mode."""
        selected_ids = self.get_selected_player_ids()
        
        if len(selected_ids) < 2:
            messagebox.showwarning("Not Enough Players", "Please select at least 2 players.")
            return
        
        mode = self.pair_mode_var.get()
        
        # Save pair mode setting
        self.db.set_setting("match_gen_pair_mode", mode)
        
        if mode == "random":
            self.current_pairs = self.generator.generate_random_pairs(selected_ids)
        elif mode == "skill":
            self.current_pairs = self.generator.generate_skill_based_pairs(selected_ids)
        elif mode == "manual":
            self._start_manual_pairing(selected_ids)
            return
        
        self._update_pairs_display()
        self._update_buyins_display()
        self.generate_btn.configure(state="normal")
    
    def _start_manual_pairing(self, player_ids: list[int]):
        """Start manual pairing mode."""
        self.manual_pair_selection = []
        self.current_pairs = []
        
        # Clear pairs display and show manual pairing UI
        for widget in self.pairs_scroll.winfo_children():
            widget.destroy()
        
        ctk.CTkLabel(
            self.pairs_scroll,
            text="Click players in pairs to create teams",
            font=get_font(12),
            text_color="#888888"
        ).pack(pady=5)
        
        self.manual_players_frame = ctk.CTkFrame(self.pairs_scroll, fg_color="transparent")
        self.manual_players_frame.pack(fill="both", expand=True)
        
        self.manual_buttons = {}
        for pid in player_ids:
            player = self.db.get_player(pid)
            if player:
                btn = ctk.CTkButton(
                    self.manual_players_frame,
                    text=player.name,
                    font=get_font(12),
                    height=35,
                    fg_color="#3d5a80",
                    hover_color="#2d4a70",
                    command=lambda p=pid: self._manual_select_player(p)
                )
                btn.pack(fill="x", pady=2)
                self.manual_buttons[pid] = btn
        
        # Done button
        ctk.CTkButton(
            self.pairs_scroll,
            text="Done Creating Pairs",
            font=get_font(12, "bold"),
            height=35,
            fg_color="#4CAF50",
            hover_color="#388E3C",
            command=self._finish_manual_pairing
        ).pack(fill="x", pady=10)
    
    def _manual_select_player(self, player_id: int):
        """Handle player selection in manual mode."""
        if player_id in self.manual_pair_selection:
            # Deselect
            self.manual_pair_selection.remove(player_id)
            self.manual_buttons[player_id].configure(fg_color="#3d5a80")
        else:
            self.manual_pair_selection.append(player_id)
            self.manual_buttons[player_id].configure(fg_color="#4CAF50")
            
            # If we have 2 selected, create a pair
            if len(self.manual_pair_selection) == 2:
                p1, p2 = self.manual_pair_selection
                self.current_pairs.append((p1, p2))
                
                # Remove from available
                self.manual_buttons[p1].destroy()
                self.manual_buttons[p2].destroy()
                del self.manual_buttons[p1]
                del self.manual_buttons[p2]
                
                self.manual_pair_selection = []
                
                # Show created pair
                pair_names = self.generator.get_pair_display_names([(p1, p2)])[0]
                messagebox.showinfo("Pair Created", f"Created: {pair_names}")
    
    def _finish_manual_pairing(self):
        """Finish manual pairing mode."""
        # Handle remaining players as lone wolves
        for pid in list(self.manual_buttons.keys()):
            self.current_pairs.append((pid, None))
        
        self._update_pairs_display()
        self._update_buyins_display()
        self.generate_btn.configure(state="normal")
    
    def _update_pairs_display(self):
        """Update the pairs display."""
        for widget in self.pairs_scroll.winfo_children():
            widget.destroy()
        
        if not self.current_pairs:
            ctk.CTkLabel(
                self.pairs_scroll,
                text="No pairs created yet",
                font=get_font(12),
                text_color="#666666"
            ).pack(pady=20)
            return
        
        pair_names = self.generator.get_pair_display_names(self.current_pairs)
        
        for i, (pair, name) in enumerate(zip(self.current_pairs, pair_names)):
            pair_frame = ctk.CTkFrame(self.pairs_scroll, fg_color="#252540", corner_radius=8)
            pair_frame.pack(fill="x", pady=2)
            
            # Pair letter (A, B, C, etc.)
            letter = chr(65 + i)  # A, B, C...
            ctk.CTkLabel(
                pair_frame,
                text=f"Pair {letter}",
                font=get_font(11, "bold"),
                text_color="#4CAF50",
                width=50
            ).pack(side="left", padx=10, pady=8)
            
            ctk.CTkLabel(
                pair_frame,
                text=name,
                font=get_font(12)
            ).pack(side="left", padx=5, pady=8)
    
    def _update_buyins_display(self):
        """Update the buy-ins tracking display."""
        for widget in self.buyins_scroll.winfo_children():
            widget.destroy()
        
        if not self.current_pairs:
            return
        
        # Get buy-in amount
        try:
            self.buyin_amount = float(self.buyin_entry.get())
        except ValueError:
            self.buyin_amount = 3.0
        
        # Get all unique players from pairs
        player_ids = set()
        for p1, p2 in self.current_pairs:
            player_ids.add(p1)
            if p2:
                player_ids.add(p2)
        
        self.buyin_vars = {}
        total_expected = len(player_ids) * self.buyin_amount
        total_paid = 0
        
        for pid in sorted(player_ids):
            player = self.db.get_player(pid)
            if not player:
                continue
            
            row = ctk.CTkFrame(self.buyins_scroll, fg_color="transparent")
            row.pack(fill="x", pady=1)
            
            var = ctk.BooleanVar(value=self.buyins_paid.get(pid, False))
            self.buyin_vars[pid] = var
            
            if var.get():
                total_paid += self.buyin_amount
            
            cb = ctk.CTkCheckBox(
                row,
                text="",
                variable=var,
                width=20,
                fg_color="#4CAF50",
                hover_color="#388E3C",
                command=lambda p=pid: self._on_buyin_changed(p)
            )
            cb.pack(side="left", padx=5)
            
            ctk.CTkLabel(
                row,
                text=player.name,
                font=get_font(11),
                width=100,
                anchor="w"
            ).pack(side="left", padx=5)
            
            # Venmo info if available
            if player.venmo:
                ctk.CTkLabel(
                    row,
                    text=player.venmo,
                    font=get_font(10),
                    text_color="#888888"
                ).pack(side="right", padx=5)
        
        self.pot_label.configure(text=f"Pot: ${total_paid:.0f} / ${total_expected:.0f}")
    
    def _on_buyin_changed(self, player_id: int):
        """Handle buy-in checkbox change."""
        self.buyins_paid[player_id] = self.buyin_vars[player_id].get()
        self._update_pot_total()
    
    def _update_pot_total(self):
        """Update the pot total display."""
        total_paid = sum(self.buyin_amount for pid, var in self.buyin_vars.items() if var.get())
        total_expected = len(self.buyin_vars) * self.buyin_amount
        self.pot_label.configure(text=f"Pot: ${total_paid:.0f} / ${total_expected:.0f}")
    
    def generate_schedule(self):
        """Generate the full evening schedule."""
        if not self.current_pairs:
            messagebox.showwarning("No Pairs", "Please create pairs first.")
            return
        
        table_count = self.table_count_var.get()
        min_games = self.min_games_var.get()
        
        # Save all settings to database for persistence across app restarts
        self._save_persistent_settings()
        
        self.generated_schedule = self.generator.generate_full_schedule(
            self.current_pairs,
            min_games_per_pair=min_games,
            table_count=table_count,
            avoid_repeats=True
        )
        
        self._display_schedule()
        
        # Enable action buttons
        self.export_btn.configure(state="normal")
        self.clear_btn.configure(state="normal")
        self.create_matches_btn.configure(state="normal")
        
        # Persist state so it survives view changes
        self._persist_state()
    
    def _get_current_state(self) -> dict:
        """Get the current state as a dictionary for persistence."""
        # Get selected player IDs
        selected_ids = self.get_selected_player_ids()
        
        return {
            'selected_player_ids': selected_ids,
            'current_pairs': self.current_pairs,
            'generated_schedule': self.generated_schedule,
            'buyins_paid': self.buyins_paid.copy(),
            'table_count': self.table_count_var.get(),
            'min_games': self.min_games_var.get(),
            'buyin_amount': self.buyin_amount,
            'pair_mode': self.pair_mode_var.get()
        }
    
    def _persist_state(self):
        """Persist the current state via callback."""
        if self.on_pairings_changed:
            state = self._get_current_state()
            self.on_pairings_changed(state, False)
    
    def _restore_state(self, state: dict):
        """Restore the view state from a saved state dictionary."""
        if not state:
            return
        
        try:
            # Restore configuration values
            if 'table_count' in state:
                self.table_count_var.set(state['table_count'])
                self.table_count_label.configure(text=str(state['table_count']))
            
            if 'min_games' in state:
                self.min_games_var.set(state['min_games'])
                self.min_games_label.configure(text=str(state['min_games']))
            
            if 'buyin_amount' in state:
                self.buyin_amount = state['buyin_amount']
                self.buyin_entry.delete(0, 'end')
                self.buyin_entry.insert(0, str(state['buyin_amount']))
            
            if 'pair_mode' in state:
                self.pair_mode_var.set(state['pair_mode'])
            
            # Restore player selections
            if 'selected_player_ids' in state:
                for pid in state['selected_player_ids']:
                    if pid in self.player_checkboxes:
                        var, _ = self.player_checkboxes[pid]
                        var.set(True)
                self.update_selection_count()
            
            # Restore buyins paid
            if 'buyins_paid' in state:
                self.buyins_paid = state['buyins_paid'].copy()
            
            # Restore pairs
            if 'current_pairs' in state and state['current_pairs']:
                self.current_pairs = state['current_pairs']
                self._update_pairs_display()
                self._update_buyins_display()
                self.generate_btn.configure(state="normal")
            
            # Restore generated schedule
            if 'generated_schedule' in state and state['generated_schedule']:
                self.generated_schedule = state['generated_schedule']
                self._display_schedule()
                
                # Enable action buttons
                self.export_btn.configure(state="normal")
                self.clear_btn.configure(state="normal")
                self.create_matches_btn.configure(state="normal")
        except Exception as e:
            print(f"Error restoring match generator state: {e}")
    
    def _display_schedule(self):
        """Display the generated schedule organized by rounds."""
        if not self.generated_schedule:
            return
        
        schedule = self.generated_schedule
        
        # Update stats with round info
        total_matches = schedule['total_matches']
        total_rounds = schedule.get('total_rounds', 1)
        live_count = len(schedule['live_matches'])
        
        stats_text = f"{total_matches} games | {total_rounds} rounds | {live_count} starting"
        self.stats_label.configure(text=stats_text, text_color="#4CAF50")
        
        # Clear and populate live games (Round 1 starting games)
        for widget in self.live_scroll.winfo_children():
            widget.destroy()
        
        if schedule['live_matches']:
            ctk.CTkLabel(
                self.live_scroll,
                text="Round 1 - Starting Games",
                font=get_font(12, "bold"),
                text_color="#4CAF50"
            ).pack(pady=(5, 5))
            for match in schedule['live_matches']:
                self._create_match_card(self.live_scroll, match, is_live=True)
        else:
            ctk.CTkLabel(
                self.live_scroll,
                text="No live games",
                font=get_font(12),
                text_color="#666666"
            ).pack(pady=10)
        
        # Clear and populate queue - organized by rounds
        for widget in self.queue_scroll.winfo_children():
            widget.destroy()
        
        if schedule['queued_matches']:
            current_round = 0
            queue_num = 0
            for match in schedule['queued_matches']:
                round_num = match.get('round_number', 1)
                
                # Add round header when round changes
                if round_num != current_round:
                    current_round = round_num
                    round_header = ctk.CTkFrame(self.queue_scroll, fg_color="#2d4a70", corner_radius=6)
                    round_header.pack(fill="x", pady=(10, 5))
                    ctk.CTkLabel(
                        round_header,
                        text=f"Round {round_num}",
                        font=get_font(12, "bold"),
                        text_color="#64B5F6"
                    ).pack(pady=5)
                
                queue_num += 1
                self._create_match_card(self.queue_scroll, match, is_live=False, queue_num=queue_num)
        else:
            ctk.CTkLabel(
                self.queue_scroll,
                text="No queued games",
                font=get_font(12),
                text_color="#666666"
            ).pack(pady=10)
    
    def _create_match_card(self, parent, match: dict, is_live: bool, queue_num: int = None):
        """Create a match card for display."""
        display = self.generator.get_match_display(match, self.current_pairs)
        
        bg_color = "#1e4a1e" if is_live else "#3d3a1e"
        if match.get('is_repeat', False):
            bg_color = "#4a3020"
        
        card = ctk.CTkFrame(parent, fg_color=bg_color, corner_radius=8)
        card.pack(fill="x", pady=2)
        
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=10, pady=8)
        
        # Table number or queue position
        if is_live:
            label_text = f"T{match.get('table_number', '?')}"
            label_color = "#4CAF50"
        else:
            label_text = f"#{queue_num}"
            label_color = "#ffd700"
        
        ctk.CTkLabel(
            inner,
            text=label_text,
            font=get_font(12, "bold"),
            text_color=label_color,
            width=30
        ).pack(side="left")
        
        # Teams
        ctk.CTkLabel(
            inner,
            text=display['team1'],
            font=get_font(11),
            text_color="#e8f5e9"
        ).pack(side="left", padx=(5, 0))
        
        ctk.CTkLabel(
            inner,
            text="vs",
            font=get_font(10),
            text_color="#888888"
        ).pack(side="left", padx=8)
        
        ctk.CTkLabel(
            inner,
            text=display['team2'],
            font=get_font(11),
            text_color="#e3f2fd"
        ).pack(side="left")
        
        # Repeat indicator
        if match.get('is_repeat', False):
            ctk.CTkLabel(
                inner,
                text=f"(x{match.get('repeat_count', 1)})",
                font=get_font(9),
                text_color="#ffcc80"
            ).pack(side="right")
    
    def clear_schedule(self):
        """Clear the generated schedule."""
        if messagebox.askyesno("Clear Schedule", "Clear the current schedule?"):
            self.generated_schedule = None
            self._display_empty_schedule()
            self.export_btn.configure(state="disabled")
            self.clear_btn.configure(state="disabled")
            self.create_matches_btn.configure(state="disabled")
            
            # Clear persisted state
            if self.on_pairings_changed:
                self.on_pairings_changed(None, False)
    
    def _display_empty_schedule(self):
        """Display empty schedule state."""
        self.stats_label.configure(text="Create pairs and generate schedule", text_color="#888888")
        
        for widget in self.live_scroll.winfo_children():
            widget.destroy()
        ctk.CTkLabel(
            self.live_scroll,
            text="No live games yet",
            font=get_font(12),
            text_color="#666666"
        ).pack(pady=20)
        
        for widget in self.queue_scroll.winfo_children():
            widget.destroy()
        ctk.CTkLabel(
            self.queue_scroll,
            text="No queued games",
            font=get_font(12),
            text_color="#666666"
        ).pack(pady=20)
    
    def export_schedule(self):
        """Export the schedule to PDF."""
        if not self.generated_schedule:
            return
        
        filepath = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            title="Export Schedule",
            initialfile="league_night_schedule.pdf"
        )
        
        if filepath:
            # Build the pairings data structure for the exporter
            pair_names = self.generator.get_pair_display_names(self.current_pairs)
            
            # Build match display list
            match_display = []
            for i, match in enumerate(self.generated_schedule.get('matches', []), 1):
                pair1_idx = match['pair1_idx']
                pair2_idx = match['pair2_idx']
                
                match_display.append({
                    'match_num': i,
                    'team1': pair_names[pair1_idx] if pair1_idx < len(pair_names) else "Unknown",
                    'team2': pair_names[pair2_idx] if pair2_idx < len(pair_names) else "Unknown",
                    'is_repeat': match.get('is_repeat', False),
                    'repeat_count': match.get('repeat_count', 0)
                })
            
            pairings_data = {
                'team_display': pair_names,
                'match_display': match_display,
                'has_repeats': any(m.get('is_repeat', False) for m in self.generated_schedule.get('matches', [])),
                'total_repeats': sum(1 for m in self.generated_schedule.get('matches', []) if m.get('is_repeat', False))
            }
            
            if self.exporter.export_match_diagram_pdf(pairings_data, filepath, is_multi_round=False):
                messagebox.showinfo("Success", f"Schedule exported to:\n{filepath}")
            else:
                messagebox.showerror("Error", "Failed to export schedule.")
    
    def create_all_matches(self):
        """Create all matches in the database."""
        if not self.generated_schedule:
            return
        
        schedule = self.generated_schedule
        
        # Get or create active season
        season = self.db.get_active_season()
        season_id = season.id if season else None
        
        # Create league night
        today = datetime.now().strftime("%Y-%m-%d")
        try:
            buyin = float(self.buyin_entry.get())
        except ValueError:
            buyin = 3.0
        
        league_night_id = self.db.create_league_night(
            date=today,
            buy_in=buyin,
            season_id=season_id,
            table_count=self.table_count_var.get()
        )
        self.current_league_night_id = league_night_id
        
        # Create pairs in database
        pair_id_map = {}  # pair_idx -> database pair_id
        for i, (p1, p2) in enumerate(self.current_pairs):
            pair_name = chr(65 + i)  # A, B, C...
            pair_id = self.db.create_pair(league_night_id, p1, p2, f"Pair {pair_name}")
            pair_id_map[i] = pair_id
        
        # Save buy-ins
        for pid, paid in self.buyins_paid.items():
            self.db.set_buyin(league_night_id, pid, buyin, paid=paid)
        
        # Create matches
        created = 0
        for match in schedule['matches']:
            pair1 = self.current_pairs[match['pair1_idx']]
            pair2 = self.current_pairs[match['pair2_idx']]
            
            status = 'live' if match.get('status') == 'live' else 'queued'
            table_num = match.get('table_number', 0) or 0
            round_num = match.get('round_number', 1)
            
            try:
                self.db.create_match(
                    team1_p1=pair1[0],
                    team1_p2=pair1[1],
                    team2_p1=pair2[0],
                    team2_p2=pair2[1],
                    table_number=table_num,
                    best_of=1,  # Single game per match
                    is_finals=False,
                    league_night_id=league_night_id,
                    pair1_id=pair_id_map.get(match['pair1_idx']),
                    pair2_id=pair_id_map.get(match['pair2_idx']),
                    queue_position=match.get('queue_position', 0),
                    status=status,
                    season_id=season_id,
                    round_number=round_num
                )
                created += 1
            except Exception as e:
                print(f"Error creating match: {e}")
        
        total_rounds = schedule.get('total_rounds', 1)
        messagebox.showinfo(
            "Success",
            f"Created {created} matches in {total_rounds} rounds!\n\n"
            f"League Night ID: {league_night_id}\n"
            f"Tables: {self.table_count_var.get()}\n\n"
            f"Rounds ensure no pair plays at multiple tables simultaneously.\n"
            f"Go to Table Tracker to manage live games."
        )
        
        # Clear state
        self.generated_schedule = None
        self.current_pairs = []
        self._display_empty_schedule()
        self._update_pairs_display()
        
        # Disable buttons
        self.export_btn.configure(state="disabled")
        self.clear_btn.configure(state="disabled")
        self.create_matches_btn.configure(state="disabled")
        self.generate_btn.configure(state="disabled")
        
        # Callback
        if self.on_match_created:
            self.on_match_created()
