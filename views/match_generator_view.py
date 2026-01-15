"""
EcoPOOL League - Match Generator View
Random partner assignment and match generation.
"""

import customtkinter as ctk
from tkinter import messagebox, filedialog
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
        self.generated_pairings = initial_pairings
        self.is_multi_round = initial_multi_round
        
        self.setup_ui()
        self.load_players()
        
        # Restore pairings display if we have them
        if self.generated_pairings:
            self.restore_pairings_display()
    
    def setup_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(
            header, 
            text="🎱 Match Generator",
            font=get_font(28, "bold")
        ).pack(side="left")
        
        # Mode selector
        mode_frame = ctk.CTkFrame(header, fg_color="transparent")
        mode_frame.pack(side="right")
        
        self.mode_var = ctk.StringVar(value="random")
        
        ctk.CTkRadioButton(
            mode_frame, text="Random Teams", variable=self.mode_var, value="random",
            font=get_font(14), fg_color="#2d7a3e", hover_color="#1a5f2a",
            command=self.on_mode_changed
        ).pack(side="left", padx=10)
        
        ctk.CTkRadioButton(
            mode_frame, text="Ranked Finals (Bo3)", variable=self.mode_var, value="ranked",
            font=get_font(14), fg_color="#c44536", hover_color="#a43526",
            command=self.on_mode_changed
        ).pack(side="left", padx=10)
        
        # Main content
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Left panel - Player selection
        left_panel = ctk.CTkFrame(content, fg_color="#1a1a2e", corner_radius=15)
        left_panel.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        ctk.CTkLabel(
            left_panel,
            text="Select Players for League Night",
            font=get_font(18, "bold")
        ).pack(pady=15)
        
        # Select all / Deselect all buttons
        btn_row = ctk.CTkFrame(left_panel, fg_color="transparent")
        btn_row.pack(fill="x", padx=15)
        
        ctk.CTkButton(
            btn_row, text="Select All", height=32, width=100,
            fg_color="#3d5a80", hover_color="#2d4a70",
            command=self.select_all
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            btn_row, text="Deselect All", height=32, width=100,
            fg_color="#555555", hover_color="#444444",
            command=self.deselect_all
        ).pack(side="left", padx=5)
        
        self.selected_count_label = ctk.CTkLabel(
            btn_row, text="0 selected",
            font=get_font(13),
            text_color="#888888"
        )
        self.selected_count_label.pack(side="right", padx=10)
        
        # Player checkboxes
        self.players_scroll = ctk.CTkScrollableFrame(
            left_panel, fg_color="transparent"
        )
        self.players_scroll.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.player_checkboxes = {}
        
        # Rounds selector (for random teams mode)
        self.rounds_frame = ctk.CTkFrame(left_panel, fg_color="#252540", corner_radius=8)
        self.rounds_frame.pack(fill="x", padx=15, pady=(0, 10))
        
        ctk.CTkLabel(
            self.rounds_frame,
            text="Rounds (games per player):",
            font=get_font(13),
        ).pack(side="left", padx=10, pady=8)
        
        self.rounds_var = ctk.IntVar(value=4)
        self.rounds_slider = ctk.CTkSlider(
            self.rounds_frame,
            from_=1,
            to=8,
            number_of_steps=7,
            variable=self.rounds_var,
            width=120,
            fg_color="#3d5a80",
            progress_color="#2d7a3e",
            command=self.on_rounds_changed
        )
        self.rounds_slider.pack(side="left", padx=5, pady=8)
        
        self.rounds_label = ctk.CTkLabel(
            self.rounds_frame,
            text="4",
            font=get_font(14, "bold"),
            text_color="#4CAF50",
            width=30
        )
        self.rounds_label.pack(side="left", padx=5, pady=8)
        
        # Generate button
        self.generate_btn = ctk.CTkButton(
            left_panel,
            text="🎲 Generate Pairings",
            font=get_font(16, "bold"),
            height=50,
            fg_color="#2d7a3e",
            hover_color="#1a5f2a",
            command=self.generate_pairings
        )
        self.generate_btn.pack(fill="x", padx=15, pady=15)
        
        # Right panel - Generated pairings
        self.right_panel = ctk.CTkFrame(content, fg_color="#1a1a2e", corner_radius=15, width=400)
        self.right_panel.pack(side="right", fill="both", expand=True, padx=(10, 0))
        self.right_panel.pack_propagate(False)
        
        ctk.CTkLabel(
            self.right_panel,
            text="Generated Pairings",
            font=get_font(18, "bold")
        ).pack(pady=15)
        
        self.pairings_container = ctk.CTkScrollableFrame(
            self.right_panel, fg_color="transparent"
        )
        self.pairings_container.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Placeholder text
        self.placeholder_label = ctk.CTkLabel(
            self.pairings_container,
            text="Select players and click\n'Generate Pairings' to create matches",
            font=get_font(14),
            text_color="#666666",
            justify="center"
        )
        self.placeholder_label.pack(pady=50)
        
        # Button frame for export, clear, and create buttons
        self.button_frame = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        
        # Top row - Export and Clear buttons
        self.top_btn_row = ctk.CTkFrame(self.button_frame, fg_color="transparent")
        
        # Export button (hidden initially)
        self.export_btn = ctk.CTkButton(
            self.top_btn_row,
            text="📄 Export PDF",
            font=get_font(13, "bold"),
            height=36,
            fg_color="#3d5a80",
            hover_color="#2d4a70",
            command=self.export_matches_pdf
        )
        
        # Clear pairings button (hidden initially)
        self.clear_btn = ctk.CTkButton(
            self.top_btn_row,
            text="🗑️ Clear",
            font=get_font(13, "bold"),
            height=36,
            fg_color="#c44536",
            hover_color="#a43526",
            command=self.clear_pairings
        )
        
        # Create matches button (hidden initially)
        self.create_matches_btn = ctk.CTkButton(
            self.button_frame,
            text="✓ Create All Matches",
            font=get_font(14, "bold"),
            height=45,
            fg_color="#4CAF50",
            hover_color="#388E3C",
            command=self.create_all_matches
        )
    
    def load_players(self):
        for widget in self.players_scroll.winfo_children():
            widget.destroy()
        
        self.player_checkboxes.clear()
        players = self.db.get_all_players()
        
        for player in players:
            var = ctk.BooleanVar(value=False)
            
            cb_frame = ctk.CTkFrame(self.players_scroll, fg_color="#252540", corner_radius=8)
            cb_frame.pack(fill="x", pady=3)
            
            cb = ctk.CTkCheckBox(
                cb_frame,
                text=player.name,
                variable=var,
                font=get_font(14),
                fg_color="#2d7a3e",
                hover_color="#1a5f2a",
                command=self.update_selection_count
            )
            cb.pack(side="left", padx=15, pady=10)
            
            # Stats badge
            if player.games_played > 0:
                stats_text = f"{player.games_won}W/{player.games_played}G ({player.win_rate:.0f}%)"
                ctk.CTkLabel(
                    cb_frame,
                    text=stats_text,
                    font=get_font(11),
                    text_color="#888888"
                ).pack(side="right", padx=15)
            
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
    
    def on_mode_changed(self):
        """Handle mode change between random teams and ranked finals."""
        mode = self.mode_var.get()
        if mode == "random":
            self.rounds_frame.pack(fill="x", padx=15, pady=(0, 10))
        else:
            self.rounds_frame.pack_forget()
    
    def on_rounds_changed(self, value):
        """Update rounds label when slider changes."""
        rounds = int(value)
        self.rounds_label.configure(text=str(rounds))
    
    def export_matches_pdf(self):
        """Export the generated match pairings to PDF."""
        if not self.generated_pairings:
            messagebox.showwarning("No Pairings", "Please generate pairings first.")
            return
        
        filepath = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            title="Export Match Schedule",
            initialfile="league_night_matches.pdf"
        )
        
        if filepath:
            success = self.exporter.export_match_diagram_pdf(
                self.generated_pairings, 
                filepath, 
                is_multi_round=self.is_multi_round
            )
            if success:
                messagebox.showinfo("Success", f"Match schedule exported to:\n{filepath}")
            else:
                messagebox.showerror("Error", "Failed to export match schedule.")
    
    def clear_pairings(self):
        """Clear the current generated pairings."""
        if not self.generated_pairings:
            return
        
        # Confirm clear
        if not messagebox.askyesno("Clear Pairings", 
                                   "Are you sure you want to clear the current pairings?\n\n"
                                   "This will discard all generated matches."):
            return
        
        # Clear pairings
        self.generated_pairings = None
        self.is_multi_round = False
        
        # Notify parent that pairings changed
        if self.on_pairings_changed:
            self.on_pairings_changed(None, False)
        
        # Clear display
        for widget in self.pairings_container.winfo_children():
            widget.destroy()
        
        self.placeholder_label = ctk.CTkLabel(
            self.pairings_container,
            text="Select players and click\n'Generate Pairings' to create matches",
            font=get_font(14),
            text_color="#666666",
            justify="center"
        )
        self.placeholder_label.pack(pady=50)
        
        # Hide buttons
        self.export_btn.pack_forget()
        self.clear_btn.pack_forget()
        self.top_btn_row.pack_forget()
        self.create_matches_btn.pack_forget()
        self.button_frame.pack_forget()
        
        # Re-enable generate button
        self.generate_btn.configure(state="normal", fg_color="#2d7a3e")
    
    def restore_pairings_display(self):
        """Restore the pairings display from saved state."""
        # Clear placeholder
        for widget in self.pairings_container.winfo_children():
            widget.destroy()
        
        # Display the pairings
        if self.is_multi_round:
            self.display_multi_round_pairings()
        elif self.generated_pairings.get('is_finals', False):
            self.display_finals_pairings(self.generated_pairings.get('matches', []))
        else:
            self.display_random_pairings()
        
        # Disable generate button while pairings exist
        self.generate_btn.configure(state="disabled", fg_color="#555555")
        
        # Show buttons
        self.button_frame.pack(fill="x", padx=15, pady=15)
        self.top_btn_row.pack(fill="x", pady=(0, 8))
        self.export_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.clear_btn.pack(side="right", fill="x", expand=True, padx=(5, 0))
        self.create_matches_btn.pack(fill="x")
    
    def generate_pairings(self):
        # Check if pairings already exist
        if self.generated_pairings:
            messagebox.showwarning(
                "Pairings Already Generated", 
                "Pairings have already been generated.\n\n"
                "Click 'Clear' to discard current pairings before generating new ones, "
                "or 'Create All Matches' to save them."
            )
            return
        
        # Get selected players
        selected_ids = [pid for pid, (var, _) in self.player_checkboxes.items() if var.get()]
        
        if len(selected_ids) < 2:
            messagebox.showwarning("Not Enough Players", "Please select at least 2 players.")
            return
        
        # Clear previous display
        for widget in self.pairings_container.winfo_children():
            widget.destroy()
        
        mode = self.mode_var.get()
        
        if mode == "random":
            # Use multi-round generation to ensure min games per player
            num_rounds = self.rounds_var.get()
            self.generated_pairings = self.generator.generate_multi_round_league_night(
                selected_ids, 
                min_games_per_player=num_rounds,
                avoid_repeats=True
            )
            self.is_multi_round = True
            self.display_multi_round_pairings()
        else:
            finals_matches = self.generator.generate_ranked_finals(selected_ids, top_n=len(selected_ids))
            self.generated_pairings = {'matches': finals_matches, 'is_finals': True}
            self.is_multi_round = False
            self.display_finals_pairings(finals_matches)
        
        # Notify parent that pairings were generated (for persistence)
        if self.on_pairings_changed:
            self.on_pairings_changed(self.generated_pairings, self.is_multi_round)
        
        # Disable generate button while pairings exist
        self.generate_btn.configure(state="disabled", fg_color="#555555")
        
        # Show buttons
        self.button_frame.pack(fill="x", padx=15, pady=15)
        self.top_btn_row.pack(fill="x", pady=(0, 8))
        self.export_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.clear_btn.pack(side="right", fill="x", expand=True, padx=(5, 0))
        self.create_matches_btn.pack(fill="x")
    
    def display_multi_round_pairings(self):
        """Display multiple rounds of match pairings."""
        pairings = self.generated_pairings
        rounds = pairings.get('rounds', [])
        
        # Summary header
        summary_frame = ctk.CTkFrame(self.pairings_container, fg_color="#252540", corner_radius=10)
        summary_frame.pack(fill="x", pady=(10, 15))
        
        total_rounds = pairings.get('total_rounds', 0)
        total_repeats = pairings.get('total_repeats', 0)
        min_games = pairings.get('min_games', 0)
        max_games = pairings.get('max_games', 0)
        
        ctk.CTkLabel(
            summary_frame,
            text=f"📊 {total_rounds} Rounds | {min_games}-{max_games} games/player",
            font=get_font(14, "bold"),
            text_color="#4CAF50"
        ).pack(side="left", padx=15, pady=10)
        
        if total_repeats > 0:
            ctk.CTkLabel(
                summary_frame,
                text=f"⚠️ {total_repeats} repeat(s)",
                font=get_font(12),
                text_color="#ff9800"
            ).pack(side="right", padx=15, pady=10)
        else:
            ctk.CTkLabel(
                summary_frame,
                text="✓ All unique",
                font=get_font(12),
                text_color="#4CAF50"
            ).pack(side="right", padx=15, pady=10)
        
        # Display each round
        for round_data in rounds:
            round_num = round_data.get('round_num', 1)
            round_repeats = round_data.get('round_repeats', 0)
            
            # Round header
            round_header = ctk.CTkFrame(self.pairings_container, fg_color="#1a1a2e", corner_radius=8)
            round_header.pack(fill="x", pady=(10, 5))
            
            header_text = f"🎱 Round {round_num} (Best of 1)"
            ctk.CTkLabel(
                round_header,
                text=header_text,
                font=get_font(15, "bold"),
                text_color="#90CAF9"
            ).pack(side="left", padx=15, pady=8)
            
            if round_repeats > 0:
                ctk.CTkLabel(
                    round_header,
                    text=f"🔄 {round_repeats}",
                    font=get_font(11),
                    text_color="#ffcc80"
                ).pack(side="right", padx=15, pady=8)
            
            # Teams for this round (compact view)
            teams_text = " | ".join(round_data.get('team_display', []))
            if teams_text:
                ctk.CTkLabel(
                    self.pairings_container,
                    text=f"Teams: {teams_text}",
                    font=get_font(11),
                    text_color="#888888",
                    wraplength=350,
                    justify="left"
                ).pack(fill="x", padx=5, pady=(0, 5))
            
            # Matches for this round
            for match in round_data.get('match_display', []):
                is_repeat = match.get('is_repeat', False)
                repeat_count = match.get('repeat_count', 0)
                
                bg_color = "#5f3a1e" if is_repeat else "#1e3a5f"
                
                match_frame = ctk.CTkFrame(self.pairings_container, fg_color=bg_color, corner_radius=8)
                match_frame.pack(fill="x", pady=2, padx=5)
                
                # Compact match display
                match_inner = ctk.CTkFrame(match_frame, fg_color="transparent")
                match_inner.pack(fill="x", padx=10, pady=6)
                
                ctk.CTkLabel(
                    match_inner,
                    text=f"M{match['match_num']}",
                    font=get_font(11, "bold"),
                    text_color="#ff9800" if is_repeat else "#90CAF9",
                    width=30
                ).pack(side="left")
                
                ctk.CTkLabel(
                    match_inner,
                    text=match['team1'],
                    font=get_font(12),
                    text_color="#e8f5e9"
                ).pack(side="left", padx=(5, 0))
                
                ctk.CTkLabel(
                    match_inner,
                    text="vs",
                    font=get_font(10),
                    text_color="#888888"
                ).pack(side="left", padx=8)
                
                ctk.CTkLabel(
                    match_inner,
                    text=match['team2'],
                    font=get_font(12),
                    text_color="#e3f2fd"
                ).pack(side="left")
                
                if is_repeat:
                    ctk.CTkLabel(
                        match_inner,
                        text=f"(x{repeat_count})",
                        font=get_font(10),
                        text_color="#ffcc80"
                    ).pack(side="right")
    
    def display_random_pairings(self):
        """Display single round pairings (legacy method, kept for compatibility)."""
        pairings = self.generated_pairings
        
        # Teams section
        ctk.CTkLabel(
            self.pairings_container,
            text="📋 Teams",
            font=get_font(16, "bold"),
            anchor="w"
        ).pack(fill="x", pady=(10, 5))
        
        for i, team_name in enumerate(pairings['team_display'], 1):
            team_frame = ctk.CTkFrame(self.pairings_container, fg_color="#2d2d44", corner_radius=8)
            team_frame.pack(fill="x", pady=3)
            
            ctk.CTkLabel(
                team_frame,
                text=f"Team {i}",
                font=get_font(12, "bold"),
                text_color="#4CAF50",
                width=60
            ).pack(side="left", padx=10, pady=8)
            
            ctk.CTkLabel(
                team_frame,
                text=team_name,
                font=get_font(14)
            ).pack(side="left", padx=5, pady=8)
        
        # Matches section with repeat info
        matches_header_frame = ctk.CTkFrame(self.pairings_container, fg_color="transparent")
        matches_header_frame.pack(fill="x", pady=(20, 5))
        
        ctk.CTkLabel(
            matches_header_frame,
            text="⚔️ Matches (Best of 1)",
            font=get_font(16, "bold"),
            anchor="w"
        ).pack(side="left")
        
        # Show repeat status
        if pairings.get('has_repeats', False):
            repeat_count = pairings.get('total_repeats', 0)
            ctk.CTkLabel(
                matches_header_frame,
                text=f"⚠️ {repeat_count} repeat(s)",
                font=get_font(12),
                text_color="#ff9800"
            ).pack(side="right")
        else:
            ctk.CTkLabel(
                matches_header_frame,
                text="✓ All unique matchups",
                font=get_font(12),
                text_color="#4CAF50"
            ).pack(side="right")
        
        for match in pairings['match_display']:
            is_repeat = match.get('is_repeat', False)
            repeat_count = match.get('repeat_count', 0)
            
            # Use different color for repeat matches
            bg_color = "#5f3a1e" if is_repeat else "#1e3a5f"
            
            match_frame = ctk.CTkFrame(self.pairings_container, fg_color=bg_color, corner_radius=10)
            match_frame.pack(fill="x", pady=5)
            
            # Header with match number and repeat indicator
            header_frame = ctk.CTkFrame(match_frame, fg_color="transparent")
            header_frame.pack(fill="x", padx=15, pady=(10, 5))
            
            ctk.CTkLabel(
                header_frame,
                text=f"Match {match['match_num']}",
                font=get_font(13, "bold"),
                text_color="#ff9800" if is_repeat else "#90CAF9"
            ).pack(side="left")
            
            if is_repeat:
                repeat_text = f"🔄 Played {repeat_count}x before"
                ctk.CTkLabel(
                    header_frame,
                    text=repeat_text,
                    font=get_font(11),
                    text_color="#ffcc80"
                ).pack(side="right")
            
            vs_frame = ctk.CTkFrame(match_frame, fg_color="transparent")
            vs_frame.pack(fill="x", padx=15, pady=(0, 10))
            
            ctk.CTkLabel(
                vs_frame,
                text=match['team1'],
                font=get_font(13),
                text_color="#e8f5e9"
            ).pack(side="left")
            
            ctk.CTkLabel(
                vs_frame,
                text="VS",
                font=get_font(12, "bold"),
                text_color="#ff9800"
            ).pack(side="left", expand=True)
            
            ctk.CTkLabel(
                vs_frame,
                text=match['team2'],
                font=get_font(13),
                text_color="#e3f2fd"
            ).pack(side="right")
    
    def display_finals_pairings(self, matches):
        ctk.CTkLabel(
            self.pairings_container,
            text="🏆 Ranked Finals Bracket",
            font=get_font(16, "bold"),
            anchor="w"
        ).pack(fill="x", pady=(10, 10))
        
        for match in matches:
            p1 = self.db.get_player(match['team1_p1'])
            p2 = self.db.get_player(match['team2_p1'])
            
            match_frame = ctk.CTkFrame(self.pairings_container, fg_color="#4a1a1a", corner_radius=10)
            match_frame.pack(fill="x", pady=5)
            
            header = ctk.CTkFrame(match_frame, fg_color="transparent")
            header.pack(fill="x", padx=15, pady=(10, 5))
            
            ctk.CTkLabel(
                header,
                text=match.get('round', 'Match'),
                font=get_font(13, "bold"),
                text_color="#ff6b6b"
            ).pack(side="left")
            
            ctk.CTkLabel(
                header,
                text=match.get('seed_info', ''),
                font=get_font(11),
                text_color="#888888"
            ).pack(side="right")
            
            vs_frame = ctk.CTkFrame(match_frame, fg_color="transparent")
            vs_frame.pack(fill="x", padx=15, pady=(0, 10))
            
            ctk.CTkLabel(
                vs_frame,
                text=p1.name if p1 else "TBD",
                font=get_font(14, "bold"),
                text_color="#ffd700"
            ).pack(side="left")
            
            ctk.CTkLabel(
                vs_frame,
                text="VS",
                font=get_font(12, "bold"),
                text_color="#ff6b6b"
            ).pack(side="left", expand=True)
            
            ctk.CTkLabel(
                vs_frame,
                text=p2.name if p2 else "TBD",
                font=get_font(14, "bold"),
                text_color="#ffd700"
            ).pack(side="right")
    
    def create_all_matches(self):
        if not self.generated_pairings:
            return
        
        is_finals = self.generated_pairings.get('is_finals', False)
        
        # Regular season = best of 1, Tournament/Finals = best of 3
        best_of = 3 if is_finals else 1
        
        created = 0
        
        if self.is_multi_round:
            # Multi-round: create matches from all rounds
            rounds = self.generated_pairings.get('rounds', [])
            match_counter = 0
            for round_data in rounds:
                round_num = round_data.get('round_num', 1)
                for match in round_data.get('match_display', []):
                    match_counter += 1
                    raw = match.get('raw', match)
                    try:
                        match_id = self.db.create_match(
                            team1_p1=raw['team1_p1'],
                            team1_p2=raw.get('team1_p2'),
                            team2_p1=raw['team2_p1'],
                            team2_p2=raw.get('team2_p2'),
                            table_number=match_counter,
                            best_of=best_of,
                            is_finals=is_finals
                        )
                        created += 1
                    except Exception as e:
                        print(f"Error creating match: {e}")
        else:
            # Single round or finals
            matches_data = self.generated_pairings.get('matches', [])
            
            if not is_finals and 'match_display' in self.generated_pairings:
                matches_data = [m['raw'] for m in self.generated_pairings.get('match_display', [])]
            
            for i, match in enumerate(matches_data, 1):
                try:
                    match_id = self.db.create_match(
                        team1_p1=match['team1_p1'],
                        team1_p2=match.get('team1_p2'),
                        team2_p1=match['team2_p1'],
                        team2_p2=match.get('team2_p2'),
                        table_number=i,
                        best_of=best_of,
                        is_finals=is_finals
                    )
                    created += 1
                except Exception as e:
                    print(f"Error creating match: {e}")
        
        match_type = "finals" if is_finals else "regular season"
        messagebox.showinfo("Success", f"Created {created} {match_type} match(es)!\n(Best of {best_of})")
        
        # Clear pairings
        self.generated_pairings = None
        self.is_multi_round = False
        for widget in self.pairings_container.winfo_children():
            widget.destroy()
        
        self.placeholder_label = ctk.CTkLabel(
            self.pairings_container,
            text="Matches created!\nSelect players to generate more.",
            font=get_font(14),
            text_color="#4CAF50",
            justify="center"
        )
        self.placeholder_label.pack(pady=50)
        
        # Hide buttons
        self.export_btn.pack_forget()
        self.clear_btn.pack_forget()
        self.top_btn_row.pack_forget()
        self.create_matches_btn.pack_forget()
        self.button_frame.pack_forget()
        
        # Re-enable generate button
        self.generate_btn.configure(state="normal", fg_color="#2d7a3e")
        
        # Notify parent that pairings were cleared
        if self.on_pairings_changed:
            self.on_pairings_changed(None, False)
        
        # Callback to refresh other views
        if self.on_match_created:
            self.on_match_created()
