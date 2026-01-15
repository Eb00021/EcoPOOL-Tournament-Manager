"""
EcoPOOL League - Scorecard View with Pool Table Visualization
Interactive scoring and ball tracking with celebration animations.
"""

import customtkinter as ctk
from tkinter import Canvas, messagebox, filedialog
import math
from database import DatabaseManager
from exporter import Exporter
from animations import flash_widget
from fonts import get_font


# Ball colors for 8-ball
BALL_COLORS = {
    1: ("#FFD700", "1"),    # Yellow solid
    2: ("#0066CC", "2"),    # Blue solid
    3: ("#CC0000", "3"),    # Red solid
    4: ("#6B2D8B", "4"),    # Purple solid
    5: ("#FF6600", "5"),    # Orange solid
    6: ("#006633", "6"),    # Green solid
    7: ("#8B0000", "7"),    # Maroon solid
    8: ("#000000", "8"),    # Black (8-ball)
    9: ("#FFD700", "9"),    # Yellow stripe
    10: ("#0066CC", "10"),  # Blue stripe
    11: ("#CC0000", "11"),  # Red stripe
    12: ("#6B2D8B", "12"),  # Purple stripe
    13: ("#FF6600", "13"),  # Orange stripe
    14: ("#006633", "14"),  # Green stripe
    15: ("#8B0000", "15"),  # Maroon stripe
}

SOLIDS = [1, 2, 3, 4, 5, 6, 7]
STRIPES = [9, 10, 11, 12, 13, 14, 15]


class PoolTableCanvas(ctk.CTkFrame):
    """Interactive pool table visualization."""
    
    def __init__(self, parent, on_ball_click=None, width=500, height=280):
        super().__init__(parent, fg_color="transparent")
        
        self.on_ball_click = on_ball_click
        self.canvas_width = width
        self.canvas_height = height
        self.ball_radius = 18
        
        # Ball states: 'table', 'pocketed_team1', 'pocketed_team2'
        self.ball_states = {i: 'table' for i in range(1, 16)}
        self.team1_group = None  # 'solids' or 'stripes'
        
        self.setup_canvas()
        self.draw_table()
        self.reset_balls()
    
    def setup_canvas(self):
        self.canvas = Canvas(
            self, 
            width=self.canvas_width, 
            height=self.canvas_height,
            bg="#1a1a2e",
            highlightthickness=0
        )
        self.canvas.pack(padx=10, pady=10)
        self.canvas.bind("<Button-1>", self.handle_click)
    
    def draw_table(self):
        """Draw the pool table felt and rails."""
        margin = 20
        rail_width = 15
        
        # Outer rail (wood)
        self.canvas.create_rectangle(
            margin, margin,
            self.canvas_width - margin, self.canvas_height - margin,
            fill="#5D3A1A", outline="#3D2A0A", width=3
        )
        
        # Felt
        self.canvas.create_rectangle(
            margin + rail_width, margin + rail_width,
            self.canvas_width - margin - rail_width, 
            self.canvas_height - margin - rail_width,
            fill="#0B6623", outline="#094D1B", width=2
        )
        
        # Pockets
        pocket_radius = 14
        pockets = [
            (margin + rail_width, margin + rail_width),  # Top left
            (self.canvas_width // 2, margin + 5),  # Top middle
            (self.canvas_width - margin - rail_width, margin + rail_width),  # Top right
            (margin + rail_width, self.canvas_height - margin - rail_width),  # Bottom left
            (self.canvas_width // 2, self.canvas_height - margin - 5),  # Bottom middle
            (self.canvas_width - margin - rail_width, self.canvas_height - margin - rail_width),  # Bottom right
        ]
        
        for px, py in pockets:
            self.canvas.create_oval(
                px - pocket_radius, py - pocket_radius,
                px + pocket_radius, py + pocket_radius,
                fill="#1a1a1a", outline="#0a0a0a"
            )
        
        # Head string (for kitchen area)
        kitchen_x = margin + rail_width + (self.canvas_width - 2*margin - 2*rail_width) * 0.25
        self.canvas.create_line(
            kitchen_x, margin + rail_width + 5,
            kitchen_x, self.canvas_height - margin - rail_width - 5,
            fill="#0D7A2D", dash=(5, 5)
        )
    
    def reset_balls(self):
        """Reset all balls to table and redraw."""
        self.ball_states = {i: 'table' for i in range(1, 16)}
        self.team1_group = None
        self.draw_balls()
    
    def draw_balls(self):
        """Draw balls in their current positions."""
        # Clear existing ball drawings
        self.canvas.delete("ball")
        
        # Calculate positions for balls on table
        start_x = self.canvas_width - 100
        start_y = self.canvas_height // 2
        
        # Rack formation positions
        rack_positions = []
        row_counts = [1, 2, 3, 4, 5]
        current_y_offset = 0
        
        for row_idx, count in enumerate(row_counts):
            row_x = start_x - row_idx * (self.ball_radius * 1.8)
            for ball_idx in range(count):
                y_offset = (ball_idx - (count - 1) / 2) * (self.ball_radius * 2.1)
                rack_positions.append((row_x, start_y + y_offset))
        
        # Standard rack order (matches the diagram)
        rack_order = [1, 9, 2, 3, 8, 10, 11, 7, 14, 5, 13, 15, 6, 4, 12]
        
        balls_on_table = [b for b in rack_order if self.ball_states[b] == 'table']
        
        for idx, ball_num in enumerate(balls_on_table):
            if idx < len(rack_positions):
                x, y = rack_positions[idx]
                self.draw_ball(x, y, ball_num)
    
    def draw_ball(self, x, y, ball_num):
        """Draw a single ball."""
        color, text = BALL_COLORS[ball_num]
        r = self.ball_radius
        
        is_stripe = ball_num >= 9
        
        if is_stripe:
            # Draw stripe ball (white with colored stripe)
            self.canvas.create_oval(
                x - r, y - r, x + r, y + r,
                fill="white", outline="#333333", width=1, tags="ball"
            )
            # Draw stripe
            self.canvas.create_arc(
                x - r, y - r, x + r, y + r,
                start=60, extent=60, fill=color, outline="", tags="ball"
            )
            self.canvas.create_arc(
                x - r, y - r, x + r, y + r,
                start=240, extent=60, fill=color, outline="", tags="ball"
            )
        else:
            # Solid ball
            self.canvas.create_oval(
                x - r, y - r, x + r, y + r,
                fill=color, outline="#333333", width=1, tags="ball"
            )
        
        # Number circle
        self.canvas.create_oval(
            x - 8, y - 8, x + 8, y + 8,
            fill="white", outline="", tags="ball"
        )
        
        # Number text
        self.canvas.create_text(
            x, y, text=text,
            font=("Arial", 9, "bold"), fill="black", tags="ball"
        )
        
        # Store ball position for click detection
        if not hasattr(self, 'ball_positions'):
            self.ball_positions = {}
        self.ball_positions[ball_num] = (x, y)
    
    def handle_click(self, event):
        """Handle click on canvas to pocket balls."""
        if not hasattr(self, 'ball_positions'):
            return
        
        # Find clicked ball
        for ball_num, (bx, by) in self.ball_positions.items():
            if self.ball_states[ball_num] != 'table':
                continue
            
            distance = math.sqrt((event.x - bx)**2 + (event.y - by)**2)
            if distance <= self.ball_radius:
                if self.on_ball_click:
                    self.on_ball_click(ball_num)
                return
    
    def pocket_ball(self, ball_num, team: int):
        """Mark a ball as pocketed by a team."""
        self.ball_states[ball_num] = f'pocketed_team{team}'
        self.draw_balls()
    
    def unpocket_ball(self, ball_num):
        """Return a ball to the table."""
        self.ball_states[ball_num] = 'table'
        self.draw_balls()
    
    def set_team_group(self, team1_group: str):
        """Set which group team 1 has (solids or stripes)."""
        self.team1_group = team1_group


class ScorecardView(ctk.CTkFrame):
    """Main scorecard view with match selection and game scoring."""
    
    def __init__(self, parent, db: DatabaseManager):
        super().__init__(parent, fg_color="transparent")
        self.db = db
        self.exporter = Exporter(db)
        
        self.current_match = None
        self.current_game = None
        self.current_game_id = None
        
        self.setup_ui()
        self.load_matches()
    
    def setup_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(
            header, 
            text="🎯 Scorecard",
            font=get_font(28, "bold")
        ).pack(side="left")
        
        # Match selector
        selector_frame = ctk.CTkFrame(self, fg_color="#1a1a2e", corner_radius=15)
        selector_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(
            selector_frame,
            text="Select Match:",
            font=get_font(14, "bold")
        ).pack(side="left", padx=15, pady=12)
        
        self.match_var = ctk.StringVar(value="Select a match...")
        self.match_dropdown = ctk.CTkComboBox(
            selector_frame,
            variable=self.match_var,
            values=["Loading..."],
            width=400,
            height=35,
            font=get_font(13),
            command=self.on_match_selected
        )
        self.match_dropdown.pack(side="left", padx=10, pady=12)
        
        ctk.CTkButton(
            selector_frame,
            text="🔄",
            width=40,
            height=35,
            command=self.load_matches
        ).pack(side="left", padx=5)
        
        # Export button
        self.export_btn = ctk.CTkButton(
            selector_frame,
            text="📄 Export Scorecard",
            font=get_font(13),
            fg_color="#3d5a80",
            hover_color="#2d4a70",
            height=35,
            command=self.export_scorecard,
            state="disabled"
        )
        self.export_btn.pack(side="right", padx=15, pady=12)
        
        # Main content area
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Placeholder
        self.placeholder = ctk.CTkLabel(
            self.content,
            text="Select a match to start scoring",
            font=get_font(18),
            text_color="#666666"
        )
        self.placeholder.pack(expand=True)
        
        self.match_ids = {}
    
    def load_matches(self):
        matches = self.db.get_all_matches(limit=50)
        
        match_options = []
        self.match_ids.clear()
        
        for match in matches:
            team1 = match['team1_p1_name'] or "Unknown"
            if match['team1_p2_name']:
                team1 += f" & {match['team1_p2_name']}"
            
            team2 = match['team2_p1_name'] or "Unknown"
            if match['team2_p2_name']:
                team2 += f" & {match['team2_p2_name']}"
            
            status = "✅" if match['is_complete'] else "🔴"
            match_type = "🏆" if match['is_finals'] else "🎱"
            
            label = f"{status} {match_type} {team1} vs {team2} (Table {match['table_number']})"
            match_options.append(label)
            self.match_ids[label] = match['id']
        
        if not match_options:
            match_options = ["No matches available"]
        
        self.match_dropdown.configure(values=match_options)
        self.match_var.set("Select a match...")
    
    def on_match_selected(self, selection):
        if selection not in self.match_ids:
            return
        
        match_id = self.match_ids[selection]
        self.current_match = self.db.get_match(match_id)
        
        if self.current_match:
            self.export_btn.configure(state="normal")
            self.show_scorecard()
    
    def select_match_by_id(self, match_id: int):
        """Programmatically select a match by its ID (used for navigation from other views)."""
        # Find the label for this match ID
        for label, mid in self.match_ids.items():
            if mid == match_id:
                self.match_var.set(label)
                self.on_match_selected(label)
                return True
        return False
    
    def show_scorecard(self):
        # Clear content
        for widget in self.content.winfo_children():
            widget.destroy()
        
        match = self.current_match
        
        # Two-column layout
        left_col = ctk.CTkFrame(self.content, fg_color="transparent")
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 10))
        
        right_col = ctk.CTkFrame(self.content, fg_color="#1a1a2e", corner_radius=15, width=350)
        right_col.pack(side="right", fill="y", padx=(10, 0))
        right_col.pack_propagate(False)
        
        # === LEFT COLUMN: Teams and Pool Table ===
        
        # Teams display
        teams_frame = ctk.CTkFrame(left_col, fg_color="#1a1a2e", corner_radius=15)
        teams_frame.pack(fill="x", pady=(0, 10))
        
        team1_name = match['team1_p1_name']
        if match['team1_p2_name']:
            team1_name += f" & {match['team1_p2_name']}"
        
        team2_name = match['team2_p1_name']
        if match['team2_p2_name']:
            team2_name += f" & {match['team2_p2_name']}"
        
        # Team 1
        t1_frame = ctk.CTkFrame(teams_frame, fg_color="#1e4a1e", corner_radius=10)
        t1_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(
            t1_frame, text="TEAM 1",
            font=get_font(12, "bold"),
            text_color="#90EE90"
        ).pack(pady=(10, 2))
        
        ctk.CTkLabel(
            t1_frame, text=team1_name,
            font=get_font(16, "bold")
        ).pack(pady=(0, 5))
        
        self.team1_score_label = ctk.CTkLabel(
            t1_frame, text="0",
            font=get_font(48, "bold"),
            text_color="#4CAF50"
        )
        self.team1_score_label.pack(pady=5)
        
        self.team1_group_label = ctk.CTkLabel(
            t1_frame, text="Group: -",
            font=get_font(13),
            text_color="#888888"
        )
        self.team1_group_label.pack(pady=(0, 10))
        
        # VS
        ctk.CTkLabel(
            teams_frame, text="VS",
            font=get_font(20, "bold"),
            text_color="#ff9800"
        ).pack(side="left", padx=10)
        
        # Team 2
        t2_frame = ctk.CTkFrame(teams_frame, fg_color="#1e3a5f", corner_radius=10)
        t2_frame.pack(side="left", fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(
            t2_frame, text="TEAM 2",
            font=get_font(12, "bold"),
            text_color="#90CAF9"
        ).pack(pady=(10, 2))
        
        ctk.CTkLabel(
            t2_frame, text=team2_name,
            font=get_font(16, "bold")
        ).pack(pady=(0, 5))
        
        self.team2_score_label = ctk.CTkLabel(
            t2_frame, text="0",
            font=get_font(48, "bold"),
            text_color="#2196F3"
        )
        self.team2_score_label.pack(pady=5)
        
        self.team2_group_label = ctk.CTkLabel(
            t2_frame, text="Group: -",
            font=get_font(13),
            text_color="#888888"
        )
        self.team2_group_label.pack(pady=(0, 10))
        
        # Pool Table
        table_frame = ctk.CTkFrame(left_col, fg_color="#1a1a2e", corner_radius=15)
        table_frame.pack(fill="both", expand=True)
        
        ctk.CTkLabel(
            table_frame,
            text="Click a ball to pocket it",
            font=get_font(14),
            text_color="#888888"
        ).pack(pady=(15, 5))
        
        self.pool_table = PoolTableCanvas(table_frame, on_ball_click=self.on_ball_clicked)
        self.pool_table.pack(pady=10)
        
        # Ball pocket controls
        pocket_controls = ctk.CTkFrame(table_frame, fg_color="transparent")
        pocket_controls.pack(fill="x", padx=20, pady=10)
        
        self.pocket_team_var = ctk.IntVar(value=1)
        
        ctk.CTkLabel(
            pocket_controls, text="Pocket for:",
            font=get_font(13)
        ).pack(side="left", padx=10)
        
        ctk.CTkRadioButton(
            pocket_controls, text="Team 1", variable=self.pocket_team_var, value=1,
            fg_color="#4CAF50", hover_color="#388E3C"
        ).pack(side="left", padx=15)
        
        ctk.CTkRadioButton(
            pocket_controls, text="Team 2", variable=self.pocket_team_var, value=2,
            fg_color="#2196F3", hover_color="#1976D2"
        ).pack(side="left", padx=15)
        
        ctk.CTkButton(
            pocket_controls, text="Reset Balls",
            fg_color="#c44536", hover_color="#a43526",
            width=100,
            command=self.reset_current_game
        ).pack(side="right", padx=10)
        
        # === RIGHT COLUMN: Game Controls ===
        
        ctk.CTkLabel(
            right_col,
            text="Game Controls",
            font=get_font(18, "bold")
        ).pack(pady=15)
        
        # Game selector
        game_frame = ctk.CTkFrame(right_col, fg_color="#252540", corner_radius=10)
        game_frame.pack(fill="x", padx=15, pady=5)
        
        ctk.CTkLabel(
            game_frame, text="Current Game:",
            font=get_font(13)
        ).pack(pady=(10, 5))
        
        self.game_buttons_frame = ctk.CTkFrame(game_frame, fg_color="transparent")
        self.game_buttons_frame.pack(pady=10)
        
        self.game_buttons = []
        for i in range(1, 4):  # Best of 3
            btn = ctk.CTkButton(
                self.game_buttons_frame,
                text=str(i),
                width=50, height=40,
                fg_color="#3d5a80" if i == 1 else "#444444",
                command=lambda g=i: self.select_game(g)
            )
            btn.pack(side="left", padx=5)
            self.game_buttons.append(btn)
        
        # Group assignment
        group_frame = ctk.CTkFrame(right_col, fg_color="#252540", corner_radius=10)
        group_frame.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkLabel(
            group_frame, text="Team 1 Group:",
            font=get_font(13)
        ).pack(pady=(10, 5))
        
        group_btns = ctk.CTkFrame(group_frame, fg_color="transparent")
        group_btns.pack(pady=10)
        
        self.group_var = ctk.StringVar(value="")
        
        ctk.CTkButton(
            group_btns, text="⚫ Solids (1-7)",
            fg_color="#2d7a3e", hover_color="#1a5f2a",
            width=130, height=35,
            command=lambda: self.set_group("solids")
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            group_btns, text="⬜ Stripes (9-15)",
            fg_color="#3d5a80", hover_color="#2d4a70",
            width=130, height=35,
            command=lambda: self.set_group("stripes")
        ).pack(side="left", padx=5)
        
        # Special events
        special_frame = ctk.CTkFrame(right_col, fg_color="#252540", corner_radius=10)
        special_frame.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkLabel(
            special_frame, text="Special Events:",
            font=get_font(13)
        ).pack(pady=(10, 5))
        
        ctk.CTkButton(
            special_frame, text="⭐ Golden Break (17 pts)",
            fg_color="#B8860B", hover_color="#8B6914",
            height=40,
            command=self.golden_break
        ).pack(fill="x", padx=15, pady=5)
        
        early_btns = ctk.CTkFrame(special_frame, fg_color="transparent")
        early_btns.pack(fill="x", padx=15, pady=5)
        
        ctk.CTkButton(
            early_btns, text="❌ T1 Early 8",
            fg_color="#c44536", hover_color="#a43526",
            width=130, height=35,
            command=lambda: self.early_8ball(1)
        ).pack(side="left", padx=2)
        
        ctk.CTkButton(
            early_btns, text="❌ T2 Early 8",
            fg_color="#c44536", hover_color="#a43526",
            width=130, height=35,
            command=lambda: self.early_8ball(2)
        ).pack(side="left", padx=2)
        
        # Win buttons
        win_frame = ctk.CTkFrame(right_col, fg_color="#252540", corner_radius=10)
        win_frame.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkLabel(
            win_frame, text="Declare Winner:",
            font=get_font(13)
        ).pack(pady=(10, 5))
        
        win_btns = ctk.CTkFrame(win_frame, fg_color="transparent")
        win_btns.pack(pady=10)
        
        ctk.CTkButton(
            win_btns, text="🏆 Team 1 Wins",
            fg_color="#4CAF50", hover_color="#388E3C",
            width=130, height=40,
            command=lambda: self.declare_winner(1)
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            win_btns, text="🏆 Team 2 Wins",
            fg_color="#2196F3", hover_color="#1976D2",
            width=130, height=40,
            command=lambda: self.declare_winner(2)
        ).pack(side="left", padx=5)
        
        # Match status
        self.match_status_label = ctk.CTkLabel(
            right_col,
            text="Match: 0 - 0",
            font=get_font(16, "bold"),
            text_color="#ffd700"
        )
        self.match_status_label.pack(pady=15)
        
        # Initialize game 1
        self.select_game(1)
        self.update_match_status()
    
    def select_game(self, game_num):
        """Select which game to score."""
        self.current_game_num = game_num
        
        # Update button styles
        for i, btn in enumerate(self.game_buttons, 1):
            if i == game_num:
                btn.configure(fg_color="#3d5a80")
            else:
                btn.configure(fg_color="#444444")
        
        # Load or create game
        games = self.db.get_games_for_match(self.current_match['id'])
        
        existing_game = None
        for g in games:
            if g['game_number'] == game_num:
                existing_game = g
                break
        
        if existing_game:
            self.current_game_id = existing_game['id']
            self.load_game_state(existing_game)
        else:
            self.current_game_id = self.db.create_game(
                self.current_match['id'], game_num
            )
            self.reset_current_game()
    
    def load_game_state(self, game):
        """Load saved game state."""
        self.pool_table.reset_balls()
        
        balls = game.get('balls_pocketed', {})
        for ball_str, team in balls.items():
            ball_num = int(ball_str)
            self.pool_table.pocket_ball(ball_num, team)
        
        if game['team1_group']:
            self.set_group(game['team1_group'], save=False)
        
        self.update_scores()
    
    def reset_current_game(self):
        """Reset current game to initial state."""
        self.pool_table.reset_balls()
        self.group_var.set("")
        self.team1_group_label.configure(text="Group: -")
        self.team2_group_label.configure(text="Group: -")
        self.update_scores()
    
    def set_group(self, group: str, save=True):
        """Set team 1's group (solids or stripes)."""
        self.group_var.set(group)
        self.pool_table.set_team_group(group)
        
        if group == "solids":
            self.team1_group_label.configure(text="Group: Solids (1-7)")
            self.team2_group_label.configure(text="Group: Stripes (9-15)")
        else:
            self.team1_group_label.configure(text="Group: Stripes (9-15)")
            self.team2_group_label.configure(text="Group: Solids (1-7)")
        
        if save:
            self.save_game_state()
    
    def on_ball_clicked(self, ball_num):
        """Handle ball click - pocket it for selected team."""
        team = self.pocket_team_var.get()
        
        if self.pool_table.ball_states[ball_num] == 'table':
            self.pool_table.pocket_ball(ball_num, team)
        else:
            self.pool_table.unpocket_ball(ball_num)
        
        self.update_scores()
        self.save_game_state()
    
    def update_scores(self):
        """Calculate and update displayed scores."""
        team1_score = 0
        team2_score = 0
        
        for ball_num, state in self.pool_table.ball_states.items():
            if state == 'pocketed_team1':
                if ball_num == 8:
                    team1_score += 3
                else:
                    team1_score += 1
            elif state == 'pocketed_team2':
                if ball_num == 8:
                    team2_score += 3
                else:
                    team2_score += 1
        
        self.team1_score_label.configure(text=str(team1_score))
        self.team2_score_label.configure(text=str(team2_score))
    
    def save_game_state(self):
        """Save current game state to database."""
        if not self.current_game_id:
            return
        
        balls_pocketed = {}
        for ball_num, state in self.pool_table.ball_states.items():
            if state.startswith('pocketed_team'):
                team = int(state[-1])
                balls_pocketed[str(ball_num)] = team
        
        team1_score = int(self.team1_score_label.cget("text"))
        team2_score = int(self.team2_score_label.cget("text"))
        
        game = self.db.get_game(self.current_game_id)
        winner = game.get('winner_team', 0) if game else 0
        golden = game.get('golden_break', False) if game else False
        early = game.get('early_8ball_team', 0) if game else 0
        
        self.db.update_game(
            self.current_game_id,
            team1_score, team2_score,
            self.group_var.get(),
            balls_pocketed,
            winner,
            golden,
            early
        )
    
    def golden_break(self):
        """Handle golden break - 17 points to breaking team."""
        # Ask which team broke
        dialog = ctk.CTkInputDialog(
            text="Which team got the golden break? (1 or 2)",
            title="Golden Break"
        )
        result = dialog.get_input()
        
        if result in ['1', '2']:
            team = int(result)
            
            # Reset and set score
            self.pool_table.reset_balls()
            
            # Pocket all balls for winning team
            for ball_num in range(1, 16):
                self.pool_table.pocket_ball(ball_num, team)
            
            self.update_scores()
            
            # Save with golden break flag
            if team == 1:
                self.team1_score_label.configure(text="17")
                self.team2_score_label.configure(text="0")
            else:
                self.team1_score_label.configure(text="0")
                self.team2_score_label.configure(text="17")
            
            self.declare_winner(team, is_golden=True)
    
    def early_8ball(self, offending_team: int):
        """Handle early 8-ball foul."""
        winning_team = 2 if offending_team == 1 else 1
        
        # Give 10 points to winning team
        if winning_team == 1:
            self.team1_score_label.configure(text="10")
        else:
            self.team2_score_label.configure(text="10")
        
        self.declare_winner(winning_team, early_8ball_team=offending_team)
    
    def declare_winner(self, team: int, is_golden=False, early_8ball_team=0):
        """Declare winner for current game."""
        team1_score = int(self.team1_score_label.cget("text"))
        team2_score = int(self.team2_score_label.cget("text"))
        
        balls_pocketed = {}
        for ball_num, state in self.pool_table.ball_states.items():
            if state.startswith('pocketed_team'):
                balls_pocketed[str(ball_num)] = int(state[-1])
        
        self.db.update_game(
            self.current_game_id,
            team1_score, team2_score,
            self.group_var.get(),
            balls_pocketed,
            team,
            is_golden,
            early_8ball_team
        )
        
        self.update_match_status()
        
        # Force UI to update before showing messagebox
        self.update_idletasks()
        
        # Subtle flash on winning team's score label
        winning_label = self.team1_score_label if team == 1 else self.team2_score_label
        flash_widget(winning_label, flash_color="#ffd700", times=2)
        
        # Show message
        if is_golden:
            messagebox.showinfo("⭐ GOLDEN BREAK! ⭐", 
                              f"Team {team} wins with a GOLDEN BREAK!\n17 points!")
        else:
            messagebox.showinfo("Game Over", f"Team {team} wins Game {self.current_game_num}!")
    
    def update_match_status(self):
        """Update overall match status (games won)."""
        games = self.db.get_games_for_match(self.current_match['id'])
        
        team1_wins = sum(1 for g in games if g['winner_team'] == 1)
        team2_wins = sum(1 for g in games if g['winner_team'] == 2)
        
        self.match_status_label.configure(text=f"Match: {team1_wins} - {team2_wins}")
        
        # Check if match is complete (best of 3 = first to 2)
        if team1_wins >= 2 or team2_wins >= 2:
            winner = 1 if team1_wins >= 2 else 2
            self.db.complete_match(self.current_match['id'])
            self.match_status_label.configure(
                text=f"🏆 MATCH COMPLETE: Team {winner} wins!",
                text_color="#ffd700"
            )
            
            # Subtle flash on the match status label
            flash_widget(self.match_status_label, flash_color="#ffd700", times=2)
    
    def export_scorecard(self):
        """Export current match scorecard to PDF."""
        if not self.current_match:
            return
        
        filepath = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            title="Export Scorecard",
            initialfile=f"scorecard_match_{self.current_match['id']}.pdf"
        )
        
        if filepath:
            if self.exporter.export_scorecard_pdf(self.current_match['id'], filepath):
                messagebox.showinfo("Success", f"Scorecard exported to:\n{filepath}")
            else:
                messagebox.showerror("Error", "Failed to export scorecard.")
