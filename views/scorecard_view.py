"""
EcoPOOL League - Scorecard View with Pool Table Visualization
Interactive scoring and ball tracking with celebration animations.
"""

import customtkinter as ctk
from tkinter import Canvas, messagebox, filedialog
import math
import json
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
    
    def __init__(self, parent, db: DatabaseManager, on_score_change=None):
        super().__init__(parent, fg_color="transparent")
        self.db = db
        self.exporter = Exporter(db)
        self.on_score_change = on_score_change  # Callback for live score updates
        
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
        
        # Separate live and completed matches
        live_matches = []
        completed_matches = []
        
        for match in matches:
            team1 = match['team1_p1_name'] or "Unknown"
            if match['team1_p2_name']:
                team1 += f" & {match['team1_p2_name']}"
            
            team2 = match['team2_p1_name'] or "Unknown"
            if match['team2_p2_name']:
                team2 += f" & {match['team2_p2_name']}"
            
            match_type = "🏆" if match['is_finals'] else "🎱"
            table_num = match.get('table_number', 0) or 0
            
            if match['is_complete']:
                status = "✅"
                label = f"{status} {match_type} {team1} vs {team2} (Table {table_num})"
                completed_matches.append((label, match['id']))
            elif table_num > 0:
                # Live/in-progress matches on a real table get live indicator
                status = "🔴 LIVE"
                label = f"{status} {match_type} {team1} vs {team2} (Table {table_num})"
                live_matches.append((label, match['id']))
            # Skip queued matches (table_num == 0) - don't show them in scorecard
        
        # Add live matches first (they're more important)
        if live_matches:
            match_options.append("--- LIVE GAMES ---")
            self.match_ids["--- LIVE GAMES ---"] = None
            for label, match_id in live_matches:
                match_options.append(label)
                self.match_ids[label] = match_id
            if completed_matches:
                match_options.append("--- COMPLETED ---")
                self.match_ids["--- COMPLETED ---"] = None
        
        # Then add completed matches
        for label, match_id in completed_matches:
            match_options.append(label)
            self.match_ids[label] = match_id
        
        if not match_options:
            match_options = ["No matches available"]
        
        self.match_dropdown.configure(values=match_options)
        self.match_var.set("Select a match...")
    
    def on_match_selected(self, selection):
        if selection not in self.match_ids:
            return
        
        match_id = self.match_ids[selection]
        
        # Ignore separator labels
        if match_id is None:
            self.match_var.set("Select a match...")
            return
        
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
            text="Click ball to pocket • Balls count for their owner (not who pocketed) • 8-ball only scores if your group is cleared",
            font=get_font(12),
            text_color="#888888"
        ).pack(pady=(15, 5))
        
        self.pool_table = PoolTableCanvas(table_frame, on_ball_click=self.on_ball_clicked)
        self.pool_table.pack(pady=10)
        
        # Turn indicator and controls
        turn_controls = ctk.CTkFrame(table_frame, fg_color="transparent")
        turn_controls.pack(fill="x", padx=20, pady=10)
        
        self.pocket_team_var = ctk.IntVar(value=1)
        
        # Visual turn indicator - clickable to switch teams
        self.turn_indicator_frame = ctk.CTkFrame(turn_controls, fg_color="transparent")
        self.turn_indicator_frame.pack(side="left", expand=True)
        
        ctk.CTkLabel(
            self.turn_indicator_frame, text="SHOOTING:",
            font=get_font(11),
            text_color="#888888"
        ).pack(side="left", padx=(0, 10))
        
        # Team 1 indicator (clickable)
        self.team1_turn_btn = ctk.CTkButton(
            self.turn_indicator_frame,
            text="◀ TEAM 1",
            font=get_font(14, "bold"),
            fg_color="#4CAF50",
            hover_color="#388E3C",
            width=120, height=40,
            corner_radius=20,
            command=lambda: self.set_shooting_team(1)
        )
        self.team1_turn_btn.pack(side="left", padx=5)
        
        # Arrow indicator
        self.turn_arrow = ctk.CTkLabel(
            self.turn_indicator_frame,
            text="🎯",
            font=get_font(20)
        )
        self.turn_arrow.pack(side="left", padx=5)
        
        # Team 2 indicator (clickable)
        self.team2_turn_btn = ctk.CTkButton(
            self.turn_indicator_frame,
            text="TEAM 2 ▶",
            font=get_font(14, "bold"),
            fg_color="#444444",
            hover_color="#1976D2",
            width=120, height=40,
            corner_radius=20,
            command=lambda: self.set_shooting_team(2)
        )
        self.team2_turn_btn.pack(side="left", padx=5)
        
        # Miss/Scratch button - switches turn without pocketing a ball
        self.miss_btn = ctk.CTkButton(
            turn_controls, text="Miss / Scratch",
            fg_color="#8B4513", hover_color="#654321",
            width=110,
            command=self.handle_miss
        )
        self.miss_btn.pack(side="right", padx=5)
        
        ctk.CTkButton(
            turn_controls, text="Reset Balls",
            fg_color="#c44536", hover_color="#a43526",
            width=100,
            command=self.reset_current_game
        ).pack(side="right", padx=5)
        
        # === GAME PROGRESS VISUALIZATION ===
        progress_frame = ctk.CTkFrame(table_frame, fg_color="#252540", corner_radius=10)
        progress_frame.pack(fill="x", padx=20, pady=(5, 15))
        
        # Team 1 progress
        t1_progress = ctk.CTkFrame(progress_frame, fg_color="transparent")
        t1_progress.pack(fill="x", padx=15, pady=8)
        
        ctk.CTkLabel(
            t1_progress, text="Team 1:",
            font=get_font(11, "bold"),
            text_color="#4CAF50",
            width=60
        ).pack(side="left")
        
        self.team1_balls_frame = ctk.CTkFrame(t1_progress, fg_color="transparent")
        self.team1_balls_frame.pack(side="left", padx=10)
        
        self.team1_ball_indicators = []
        for i in range(7):
            indicator = ctk.CTkLabel(
                self.team1_balls_frame,
                text="●",
                font=get_font(16),
                text_color="#666666",
                width=20
            )
            indicator.pack(side="left")
            self.team1_ball_indicators.append(indicator)
        
        self.team1_8ball_indicator = ctk.CTkLabel(
            t1_progress,
            text="⑧",
            font=get_font(18),
            text_color="#333333"
        )
        self.team1_8ball_indicator.pack(side="left", padx=(10, 0))
        
        self.team1_progress_label = ctk.CTkLabel(
            t1_progress,
            text="0/7",
            font=get_font(11),
            text_color="#888888",
            width=40
        )
        self.team1_progress_label.pack(side="right")
        
        # Team 2 progress
        t2_progress = ctk.CTkFrame(progress_frame, fg_color="transparent")
        t2_progress.pack(fill="x", padx=15, pady=(0, 8))
        
        ctk.CTkLabel(
            t2_progress, text="Team 2:",
            font=get_font(11, "bold"),
            text_color="#2196F3",
            width=60
        ).pack(side="left")
        
        self.team2_balls_frame = ctk.CTkFrame(t2_progress, fg_color="transparent")
        self.team2_balls_frame.pack(side="left", padx=10)
        
        self.team2_ball_indicators = []
        for i in range(7):
            indicator = ctk.CTkLabel(
                self.team2_balls_frame,
                text="●",
                font=get_font(16),
                text_color="#666666",
                width=20
            )
            indicator.pack(side="left")
            self.team2_ball_indicators.append(indicator)
        
        self.team2_8ball_indicator = ctk.CTkLabel(
            t2_progress,
            text="⑧",
            font=get_font(18),
            text_color="#333333"
        )
        self.team2_8ball_indicator.pack(side="left", padx=(10, 0))
        
        self.team2_progress_label = ctk.CTkLabel(
            t2_progress,
            text="0/7",
            font=get_font(11),
            text_color="#888888",
            width=40
        )
        self.team2_progress_label.pack(side="right")
        
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
            group_frame, text="Team 1 Group (auto or manual):",
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
        
        # Set up auto-refresh timer to check for external updates (from web interface)
        self._setup_auto_refresh()
    
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
        if isinstance(balls, str):
            try:
                balls = json.loads(balls)
            except:
                balls = {}
        
        for ball_str, team in balls.items():
            ball_num = int(ball_str)
            self.pool_table.pocket_ball(ball_num, team)
        
        if game.get('team1_group'):
            self.set_group(game['team1_group'], save=False)
        
        # Check if game is already complete
        if game.get('winner_team', 0) > 0:
            self.set_game_over_state()
            self._game_was_complete = True
        else:
            self.set_game_active_state()
            self._game_was_complete = False
        
        self.update_scores()
        self.update_progress_visualization()
    
    def reset_current_game(self):
        """Reset current game to initial state."""
        self.pool_table.reset_balls()
        self.group_var.set("")
        self.pool_table.set_team_group(None)
        self.team1_group_label.configure(text="Group: -")
        self.team2_group_label.configure(text="Group: -")
        self.team1_score_label.configure(text="0")
        self.team2_score_label.configure(text="0")
        self.set_game_active_state()  # Enable turn controls
        self.update_progress_visualization()
        self.save_game_state()
    
    def set_shooting_team(self, team: int, flash=True):
        """Set which team is currently shooting and update visual indicator."""
        self.pocket_team_var.set(team)
        
        if team == 1:
            self.team1_turn_btn.configure(fg_color="#4CAF50")
            self.team2_turn_btn.configure(fg_color="#444444")
            self.turn_arrow.configure(text="🎯")
        else:
            self.team1_turn_btn.configure(fg_color="#444444")
            self.team2_turn_btn.configure(fg_color="#2196F3")
            self.turn_arrow.configure(text="🎯")
        
        # Flash the active team button (unless disabled)
        if flash:
            active_btn = self.team1_turn_btn if team == 1 else self.team2_turn_btn
            flash_widget(active_btn, flash_color="#ffd700", times=1)
    
    def switch_turn(self):
        """Switch to the other team's turn."""
        current_team = self.pocket_team_var.get()
        new_team = 2 if current_team == 1 else 1
        self.set_shooting_team(new_team)
    
    def handle_miss(self):
        """Handle a miss or scratch - switch turns without pocketing a ball."""
        self.switch_turn()
    
    def set_game_over_state(self):
        """Dim the turn indicators when the game is over."""
        self.team1_turn_btn.configure(fg_color="#333333", state="disabled")
        self.team2_turn_btn.configure(fg_color="#333333", state="disabled")
        self.turn_arrow.configure(text="🏁")
        self.miss_btn.configure(state="disabled")
    
    def set_game_active_state(self):
        """Re-enable turn indicators for active game."""
        self.team1_turn_btn.configure(state="normal")
        self.team2_turn_btn.configure(state="normal")
        self.miss_btn.configure(state="normal")
        self.set_shooting_team(1, flash=False)
    
    def update_progress_visualization(self):
        """Update the ball progress indicators for both teams."""
        group = self.group_var.get()
        
        # Check if current game is complete (has a winner)
        game_over = False
        if self.current_game_id:
            game = self.db.get_game(self.current_game_id)
            if game and game.get('winner_team', 0) > 0:
                game_over = True
        
        if not group:
            # No groups assigned - show neutral state
            dim_color = "#444444" if game_over else "#666666"
            for indicator in self.team1_ball_indicators:
                indicator.configure(text="●", text_color=dim_color)
            for indicator in self.team2_ball_indicators:
                indicator.configure(text="●", text_color=dim_color)
            self.team1_8ball_indicator.configure(text_color="#333333")
            self.team2_8ball_indicator.configure(text_color="#333333")
            self.team1_progress_label.configure(text="0/7", text_color="#666666" if game_over else "#888888")
            self.team2_progress_label.configure(text="0/7", text_color="#666666" if game_over else "#888888")
            return
        
        # Determine which balls belong to which team
        if group == "solids":
            team1_balls = SOLIDS
            team2_balls = STRIPES
            team1_color = "#FFD700"  # Gold for solids
            team2_color = "#87CEEB"  # Light blue for stripes (white with stripe)
        else:
            team1_balls = STRIPES
            team2_balls = SOLIDS
            team1_color = "#87CEEB"
            team2_color = "#FFD700"
        
        # Dim colors if game is over
        if game_over:
            team1_color = "#666666"
            team2_color = "#666666"
        
        # Count pocketed balls for each team
        team1_pocketed = 0
        team2_pocketed = 0
        eight_ball_pocketed_by = None
        
        for ball_num, state in self.pool_table.ball_states.items():
            if state.startswith('pocketed_'):
                if ball_num in team1_balls:
                    team1_pocketed += 1
                elif ball_num in team2_balls:
                    team2_pocketed += 1
                elif ball_num == 8:
                    eight_ball_pocketed_by = int(state[-1])
        
        # Update Team 1 indicators
        for i, indicator in enumerate(self.team1_ball_indicators):
            if i < team1_pocketed:
                check_color = "#666666" if game_over else "#4CAF50"
                indicator.configure(text="✓", text_color=check_color)
            else:
                indicator.configure(text="●", text_color=team1_color)
        
        # Update Team 2 indicators
        for i, indicator in enumerate(self.team2_ball_indicators):
            if i < team2_pocketed:
                check_color = "#666666" if game_over else "#2196F3"
                indicator.configure(text="✓", text_color=check_color)
            else:
                indicator.configure(text="●", text_color=team2_color)
        
        # Update 8-ball indicators
        if game_over:
            self.team1_8ball_indicator.configure(text_color="#333333")
            self.team2_8ball_indicator.configure(text_color="#333333")
        else:
            if team1_pocketed == 7:
                self.team1_8ball_indicator.configure(text_color="#4CAF50")  # Ready to shoot 8
            else:
                self.team1_8ball_indicator.configure(text_color="#333333")
            
            if team2_pocketed == 7:
                self.team2_8ball_indicator.configure(text_color="#2196F3")  # Ready to shoot 8
            else:
                self.team2_8ball_indicator.configure(text_color="#333333")
        
        # Show if 8-ball was legally pocketed
        if eight_ball_pocketed_by == 1 and team1_pocketed == 7:
            check_color = "#888888" if game_over else "#ffd700"
            self.team1_8ball_indicator.configure(text="✓", text_color=check_color)
        elif eight_ball_pocketed_by == 2 and team2_pocketed == 7:
            check_color = "#888888" if game_over else "#ffd700"
            self.team2_8ball_indicator.configure(text="✓", text_color=check_color)
        else:
            self.team1_8ball_indicator.configure(text="⑧")
            self.team2_8ball_indicator.configure(text="⑧")
        
        # Update progress labels
        label_color = "#666666" if game_over else "#888888"
        self.team1_progress_label.configure(text=f"{team1_pocketed}/7", text_color=label_color)
        self.team2_progress_label.configure(text=f"{team2_pocketed}/7", text_color=label_color)
    
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
        
        # Update progress visualization with new group colors
        self.update_progress_visualization()
        
        if save:
            self.save_game_state()
    
    def on_ball_clicked(self, ball_num):
        """Handle ball click - pocket it for selected team.
        
        Turn switching rules (standard 8-ball):
        - Pocket your own ball → keep shooting (same turn)
        - Pocket opponent's ball → turn switches to opponent
        - Pocket 8-ball legally → game over (winner)
        - Pocket 8-ball illegally → game over (loser)
        """
        team = self.pocket_team_var.get()
        
        if self.pool_table.ball_states[ball_num] == 'table':
            # Check for illegal 8-ball pocket
            if ball_num == 8:
                if self._check_early_8ball(team):
                    # Warn about early 8-ball but still allow pocketing for tracking
                    result = messagebox.askyesno(
                        "Early 8-Ball Warning",
                        f"Team {team} has NOT cleared all their balls yet!\n\n"
                        "Pocketing the 8-ball now is a foul.\n"
                        "Do you want to record this as an early 8-ball loss?\n\n"
                        "Yes = Record as early 8-ball (Team loses)\n"
                        "No = Just pocket the ball (for tracking only)"
                    )
                    if result:
                        self.early_8ball(team)
                        return
            
            self.pool_table.pocket_ball(ball_num, team)
            
            # Determine if turn should switch based on ball ownership
            should_switch = self._should_switch_turn(ball_num, team)
            
            # Auto-assign groups based on first non-8 ball pocketed
            if ball_num != 8 and not self.group_var.get():
                self._auto_assign_group(ball_num, team)
                # First ball pocketed - team keeps shooting
                should_switch = False
            
            # Show feedback if ball benefits opponent (pocketing wrong group)
            elif ball_num != 8 and self.group_var.get():
                self._check_opponent_ball_pocketed(ball_num, team)
            
            # Switch turn if needed (opponent's ball or foul)
            if should_switch:
                self.switch_turn()
        else:
            # Unpocketing a ball (undo) - don't switch turns
            self.pool_table.unpocket_ball(ball_num)
            
            # Check if we need to clear group assignment (no balls pocketed anymore)
            self._check_clear_group()
        
        self.update_scores()
        self.update_progress_visualization()
        self.save_game_state()
    
    def _should_switch_turn(self, ball_num: int, pocketing_team: int) -> bool:
        """Determine if turn should switch based on which ball was pocketed.
        
        Returns True if turn should switch to other team.
        """
        group = self.group_var.get()
        
        # 8-ball - don't switch (game ending shot)
        if ball_num == 8:
            return False
        
        # No group assigned yet - will be assigned, keep turn
        if not group:
            return False
        
        # Determine which balls belong to the pocketing team
        if group == "solids":
            team1_balls = SOLIDS
            team2_balls = STRIPES
        else:
            team1_balls = STRIPES
            team2_balls = SOLIDS
        
        # Check if ball belongs to pocketing team
        if pocketing_team == 1:
            owns_ball = ball_num in team1_balls
        else:
            owns_ball = ball_num in team2_balls
        
        # Switch turn if pocketed opponent's ball
        return not owns_ball
    
    def _check_early_8ball(self, team: int) -> bool:
        """Check if pocketing the 8-ball would be early/illegal for the given team.
        
        Returns True if it's an early 8-ball (team hasn't cleared their balls).
        """
        group = self.group_var.get()
        
        if not group:
            # No groups assigned yet - definitely early
            return True
        
        # Determine which balls belong to the pocketing team
        if group == "solids":
            team_balls = SOLIDS if team == 1 else STRIPES
        else:  # stripes
            team_balls = STRIPES if team == 1 else SOLIDS
        
        # Count how many of the team's balls are still on the table
        balls_remaining = sum(
            1 for ball in team_balls 
            if self.pool_table.ball_states[ball] == 'table'
        )
        
        # Early 8-ball if any balls remain
        return balls_remaining > 0
    
    def _check_opponent_ball_pocketed(self, ball_num: int, pocketing_team: int):
        """Check if the pocketed ball belongs to the opponent and flash their score.
        
        In 8-ball, pocketing opponent's ball benefits them (ball stays down, counts for them).
        """
        group = self.group_var.get()
        
        # Determine which balls belong to which team
        if group == "solids":
            team1_balls = SOLIDS
            team2_balls = STRIPES
        else:  # stripes
            team1_balls = STRIPES
            team2_balls = SOLIDS
        
        # Check if ball belongs to opponent
        if pocketing_team == 1 and ball_num in team2_balls:
            # Team 1 pocketed Team 2's ball - benefits Team 2
            flash_widget(self.team2_score_label, flash_color="#2196F3", times=2)
        elif pocketing_team == 2 and ball_num in team1_balls:
            # Team 2 pocketed Team 1's ball - benefits Team 1
            flash_widget(self.team1_score_label, flash_color="#4CAF50", times=2)
    
    def _auto_assign_group(self, ball_num: int, team: int):
        """Auto-assign groups based on the first ball pocketed."""
        # Determine if ball is solid or stripe
        is_solid = ball_num in SOLIDS
        is_stripe = ball_num in STRIPES
        
        if is_solid:
            # Team that pocketed gets solids
            if team == 1:
                self.set_group("solids", save=False)
            else:
                self.set_group("stripes", save=False)  # Team 2 gets solids, so Team 1 gets stripes
        elif is_stripe:
            # Team that pocketed gets stripes
            if team == 1:
                self.set_group("stripes", save=False)
            else:
                self.set_group("solids", save=False)  # Team 2 gets stripes, so Team 1 gets solids
        
        # Show notification
        group = self.group_var.get()
        if group:
            team1_group = "Solids (1-7)" if group == "solids" else "Stripes (9-15)"
            team2_group = "Stripes (9-15)" if group == "solids" else "Solids (1-7)"
            # Flash the group labels to indicate auto-assignment
            flash_widget(self.team1_group_label, flash_color="#4CAF50", times=2)
            flash_widget(self.team2_group_label, flash_color="#2196F3", times=2)
    
    def _check_clear_group(self):
        """Check if groups should be cleared (no non-8 balls pocketed)."""
        # Count pocketed non-8 balls
        pocketed_balls = [
            ball for ball, state in self.pool_table.ball_states.items()
            if state.startswith('pocketed_') and ball != 8
        ]
        
        # If no non-8 balls are pocketed, clear the group assignment
        if not pocketed_balls and self.group_var.get():
            self.group_var.set("")
            self.pool_table.set_team_group(None)
            self.team1_group_label.configure(text="Group: -")
            self.team2_group_label.configure(text="Group: -")
    
    def update_scores(self):
        """Calculate and update displayed scores based on team groups.
        
        Scoring rules (standard 8-ball):
        - Each ball in a team's group is worth 1 point when pocketed
        - Balls count for the team that OWNS them (by color), not who pocketed them
        - The 8-ball is worth 3 points ONLY when legally pocketed 
          (after team has cleared all their assigned balls)
        - Total possible points: 7 (solids) + 7 (stripes) + 3 (8-ball) = 17
        """
        team1_score = 0
        team2_score = 0
        
        group = self.group_var.get()
        
        if not group:
            # No group assigned yet - show 0 for both until groups are determined
            self.team1_score_label.configure(text="0")
            self.team2_score_label.configure(text="0")
            return
        
        # Determine which balls belong to which team
        if group == "solids":
            team1_balls = SOLIDS  # Team 1 has solids
            team2_balls = STRIPES  # Team 2 has stripes
        else:  # stripes
            team1_balls = STRIPES  # Team 1 has stripes
            team2_balls = SOLIDS  # Team 2 has solids
        
        # Count pocketed balls (regardless of who pocketed them - ball ownership matters)
        team1_balls_pocketed = 0
        team2_balls_pocketed = 0
        eight_ball_pocketed = False
        eight_ball_pocketing_team = None
        
        for ball_num, state in self.pool_table.ball_states.items():
            if state.startswith('pocketed_'):
                if ball_num in team1_balls:
                    # This ball belongs to Team 1's group - counts for Team 1
                    team1_score += 1
                    team1_balls_pocketed += 1
                elif ball_num in team2_balls:
                    # This ball belongs to Team 2's group - counts for Team 2
                    team2_score += 1
                    team2_balls_pocketed += 1
                elif ball_num == 8:
                    eight_ball_pocketed = True
                    eight_ball_pocketing_team = int(state[-1])
        
        # Handle 8-ball scoring (only legal if all your balls are cleared first)
        if eight_ball_pocketed and eight_ball_pocketing_team:
            if eight_ball_pocketing_team == 1:
                # Team 1 pocketed the 8-ball - only legal if all their balls are cleared
                if team1_balls_pocketed == 7:
                    team1_score += 3  # Legal 8-ball pocket
                # else: early/illegal 8-ball - no points (handled by early_8ball button)
            elif eight_ball_pocketing_team == 2:
                # Team 2 pocketed the 8-ball - only legal if all their balls are cleared
                if team2_balls_pocketed == 7:
                    team2_score += 3  # Legal 8-ball pocket
        
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
        
        # Notify live scores server of update
        if self.on_score_change:
            self.on_score_change()
    
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
            
            # Set groups (team gets solids for golden break convention)
            if team == 1:
                self.set_group("solids", save=False)
            else:
                self.set_group("stripes", save=False)
            
            # Pocket all balls for winning team
            for ball_num in range(1, 16):
                self.pool_table.pocket_ball(ball_num, team)
            
            self.update_scores()
            self.update_progress_visualization()
            
            # Save with golden break flag (17 points)
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
        
        # Set game over state - dim turn indicators
        self.set_game_over_state()
        
        self.update_match_status()
        
        # Notify live scores server of update
        if self.on_score_change:
            self.on_score_change()
        
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
        
        # Get best_of from match (default to 1 for new system, 3 for finals)
        best_of = self.current_match.get('best_of', 1)
        wins_needed = (best_of // 2) + 1
        
        # Check if match is complete
        if team1_wins >= wins_needed or team2_wins >= wins_needed:
            winner = 1 if team1_wins >= wins_needed else 2
            
            # Use the new method that also updates status
            self.db.complete_match_with_status(self.current_match['id'])
            
            self.match_status_label.configure(
                text=f"MATCH COMPLETE: Team {winner} wins!",
                text_color="#ffd700"
            )
            
            # Subtle flash on the match status label
            flash_widget(self.match_status_label, flash_color="#ffd700", times=2)
            
            # Check if there's a queue and offer to start next game
            self._check_queue_for_next_game()
    
    def _check_queue_for_next_game(self):
        """Check if there's a next game in the queue and offer to start it."""
        # Get the table number from current match
        table_num = self.current_match.get('table_number', 0)
        if not table_num:
            return
        
        # Get current league night
        league_night = self.db.get_current_league_night()
        if not league_night:
            return
        
        # Check for next queued match (respecting round and pair availability)
        next_match = self.db.get_next_available_match(league_night['id'])
        if next_match:
            # Get team names for display
            team1 = next_match['team1_p1_name'] or "Unknown"
            if next_match['team1_p2_name']:
                team1 += f" & {next_match['team1_p2_name']}"
            
            team2 = next_match['team2_p1_name'] or "Unknown"
            if next_match['team2_p2_name']:
                team2 += f" & {next_match['team2_p2_name']}"
            
            result = messagebox.askyesno(
                "Next Game",
                f"Match complete!\n\n"
                f"Start next game on Table {table_num}?\n\n"
                f"{team1} vs {team2}"
            )
            
            if result:
                # Start the next match on this table
                self.db.start_match(next_match['id'], table_num)
                
                # Refresh the match list
                self.load_matches()
                
                # Automatically switch to the new match
                new_match_id = next_match['id']
                self.select_match_by_id(new_match_id)
    
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
    
    def _setup_auto_refresh(self):
        """Set up automatic refresh to check for external updates."""
        def check_for_updates():
            if not self.current_match or not self.current_game_id:
                # Schedule next check
                self.after(2000, check_for_updates)
                return
            
            try:
                # Reload current game from database to check for external changes
                game = self.db.get_game(self.current_game_id)
                if game:
                    # Check if balls_pocketed or scores have changed
                    current_balls = {}
                    for ball_num, state in self.pool_table.ball_states.items():
                        if state.startswith('pocketed_team'):
                            current_balls[str(ball_num)] = int(state[-1])
                    
                    saved_balls = game.get('balls_pocketed', {})
                    if isinstance(saved_balls, str):
                        try:
                            saved_balls = json.loads(saved_balls)
                        except:
                            saved_balls = {}
                    
                    # Compare balls
                    if current_balls != saved_balls:
                        # External change detected - reload game state
                        self.load_game_state(game)
                    
                    # Check scores
                    current_team1_score = int(self.team1_score_label.cget("text"))
                    current_team2_score = int(self.team2_score_label.cget("text"))
                    if (current_team1_score != game.get('team1_score', 0) or 
                        current_team2_score != game.get('team2_score', 0)):
                        # Scores changed externally - reload
                        self.load_game_state(game)
                    
                    # Check for winner change
                    if game.get('winner_team', 0) > 0:
                        if not hasattr(self, '_game_was_complete') or not self._game_was_complete:
                            self._game_was_complete = True
                            self.load_game_state(game)
                            self.update_match_status()
                
                # Check match status
                match = self.db.get_match(self.current_match['id'])
                if match:
                    if match.get('is_complete') != self.current_match.get('is_complete'):
                        # Match completion status changed
                        self.current_match = match
                        self.update_match_status()
            except Exception as e:
                # Silently handle errors - don't spam console
                pass
            
            # Schedule next check (every 2 seconds)
            self.after(2000, check_for_updates)
        
        # Start checking after a short delay
        self.after(2000, check_for_updates)
