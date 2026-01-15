"""
EcoPOOL League - Match Generator View
Random partner assignment and match generation.
"""

import customtkinter as ctk
from tkinter import messagebox
from database import DatabaseManager
from match_generator import MatchGenerator
from fonts import get_font


class MatchGeneratorView(ctk.CTkFrame):
    def __init__(self, parent, db: DatabaseManager, on_match_created=None):
        super().__init__(parent, fg_color="transparent")
        self.db = db
        self.generator = MatchGenerator(db)
        self.on_match_created = on_match_created
        
        self.selected_players = set()
        self.generated_pairings = None
        
        self.setup_ui()
        self.load_players()
    
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
            font=get_font(14), fg_color="#2d7a3e", hover_color="#1a5f2a"
        ).pack(side="left", padx=10)
        
        ctk.CTkRadioButton(
            mode_frame, text="Ranked Finals", variable=self.mode_var, value="ranked",
            font=get_font(14), fg_color="#c44536", hover_color="#a43526"
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
        
        # Generate button
        ctk.CTkButton(
            left_panel,
            text="🎲 Generate Pairings",
            font=get_font(16, "bold"),
            height=50,
            fg_color="#2d7a3e",
            hover_color="#1a5f2a",
            command=self.generate_pairings
        ).pack(fill="x", padx=15, pady=15)
        
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
        
        # Create matches button (hidden initially)
        self.create_matches_btn = ctk.CTkButton(
            self.right_panel,
            text="✓ Create All Matches",
            font=get_font(16, "bold"),
            height=50,
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
    
    def generate_pairings(self):
        # Get selected players
        selected_ids = [pid for pid, (var, _) in self.player_checkboxes.items() if var.get()]
        
        if len(selected_ids) < 2:
            messagebox.showwarning("Not Enough Players", "Please select at least 2 players.")
            return
        
        # Clear previous pairings
        for widget in self.pairings_container.winfo_children():
            widget.destroy()
        
        mode = self.mode_var.get()
        
        if mode == "random":
            self.generated_pairings = self.generator.generate_full_league_night(selected_ids)
            self.display_random_pairings()
        else:
            finals_matches = self.generator.generate_ranked_finals(selected_ids, top_n=len(selected_ids))
            self.generated_pairings = {'matches': finals_matches, 'is_finals': True}
            self.display_finals_pairings(finals_matches)
        
        # Show create button
        self.create_matches_btn.pack(fill="x", padx=15, pady=15)
    
    def display_random_pairings(self):
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
        
        # Matches section
        ctk.CTkLabel(
            self.pairings_container,
            text="⚔️ Matches",
            font=get_font(16, "bold"),
            anchor="w"
        ).pack(fill="x", pady=(20, 5))
        
        for match in pairings['match_display']:
            match_frame = ctk.CTkFrame(self.pairings_container, fg_color="#1e3a5f", corner_radius=10)
            match_frame.pack(fill="x", pady=5)
            
            ctk.CTkLabel(
                match_frame,
                text=f"Match {match['match_num']}",
                font=get_font(13, "bold"),
                text_color="#90CAF9"
            ).pack(pady=(10, 5))
            
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
        matches_data = self.generated_pairings.get('matches', [])
        
        if not is_finals:
            matches_data = [m['raw'] for m in self.generated_pairings.get('match_display', [])]
        
        created = 0
        for i, match in enumerate(matches_data, 1):
            try:
                match_id = self.db.create_match(
                    team1_p1=match['team1_p1'],
                    team1_p2=match.get('team1_p2'),
                    team2_p1=match['team2_p1'],
                    team2_p2=match.get('team2_p2'),
                    table_number=i,
                    best_of=3,
                    is_finals=is_finals
                )
                created += 1
            except Exception as e:
                print(f"Error creating match: {e}")
        
        messagebox.showinfo("Success", f"Created {created} match(es)!")
        
        # Clear pairings
        self.generated_pairings = None
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
        
        self.create_matches_btn.pack_forget()
        
        # Callback to refresh other views
        if self.on_match_created:
            self.on_match_created()
