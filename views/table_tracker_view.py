"""
EcoPOOL League - Pool Table Tracker View
Visual overview of all tables with queue management system.
"""

import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime
from database import DatabaseManager
from fonts import get_font


class TableTrackerView(ctk.CTkFrame):
    def __init__(self, parent, db: DatabaseManager, on_match_click=None):
        super().__init__(parent, fg_color="transparent")
        self.db = db
        self.on_match_click = on_match_click  # Callback for navigating to scorecard
        
        # Get current league night for queue management
        self.current_league_night = self.db.get_current_league_night()
        
        # Load saved table count or get from league night
        if self.current_league_night:
            self.num_tables = self.current_league_night.get('table_count', 3)
        else:
            saved_count = self.db.get_setting("num_tables", "3")
            self.num_tables = int(saved_count)
        
        # For timer updates
        self.after_id = None
        self._resize_after_id = None
        
        self.setup_ui()
        self.refresh_tables()
        self.start_timer_updates()
        
        # Bind resize event for responsive layout
        self.bind("<Configure>", self._on_resize)
    
    def setup_ui(self):
        # Main container with two sections
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Left side - Tables
        self.left_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.left_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        # Right side - Queue
        self.right_frame = ctk.CTkFrame(self.main_container, fg_color="#1a1a2e", corner_radius=15, width=350)
        self.right_frame.pack(side="right", fill="y", padx=(5, 0))
        self.right_frame.pack_propagate(False)
        
        self._setup_tables_section()
        self._setup_queue_section()
    
    def _setup_tables_section(self):
        """Setup the tables display section."""
        # Header
        header = ctk.CTkFrame(self.left_frame, fg_color="transparent")
        header.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(
            header, 
            text="Pool Hall Tables",
            font=get_font(24, "bold")
        ).pack(side="left")
        
        # Current time display
        self.time_label = ctk.CTkLabel(
            header,
            text="",
            font=get_font(13),
            text_color="#888888"
        )
        self.time_label.pack(side="right", padx=10)
        
        ctk.CTkButton(
            header,
            text="Refresh",
            font=get_font(12),
            fg_color="#3d5a80",
            hover_color="#2d4a70",
            height=35,
            width=80,
            command=self.refresh_tables
        ).pack(side="right", padx=5)
        
        # Table count selector and stats
        count_frame = ctk.CTkFrame(self.left_frame, fg_color="#252540", corner_radius=10)
        count_frame.pack(fill="x", pady=(0, 10))
        
        count_inner = ctk.CTkFrame(count_frame, fg_color="transparent")
        count_inner.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkLabel(
            count_inner, text="Tables:",
            font=get_font(13)
        ).pack(side="left")
        
        self.table_count_var = ctk.StringVar(value=str(self.num_tables))
        table_selector = ctk.CTkComboBox(
            count_inner,
            values=["1", "2", "3", "4", "5", "6"],
            variable=self.table_count_var,
            width=70,
            command=self.update_table_count
        )
        table_selector.pack(side="left", padx=10)
        
        # Stats summary
        self.stats_label = ctk.CTkLabel(
            count_inner,
            text="",
            font=get_font(12),
            text_color="#888888"
        )
        self.stats_label.pack(side="left", padx=20)
        
        # Legend
        legend = ctk.CTkFrame(count_inner, fg_color="transparent")
        legend.pack(side="right")
        
        for color, text in [("#4CAF50", "Live"), ("#ffd700", "Queued"), ("#2d2d44", "Available")]:
            dot = ctk.CTkFrame(legend, fg_color=color, width=10, height=10, corner_radius=5)
            dot.pack(side="left", padx=(10, 3))
            ctk.CTkLabel(legend, text=text, font=get_font(11)).pack(side="left")
        
        # Tables container
        self.tables_frame = ctk.CTkFrame(self.left_frame, fg_color="#1a1a2e", corner_radius=15)
        self.tables_frame.pack(fill="both", expand=True)
        
        self.table_widgets = {}
        self.timer_labels = {}
        self._last_width = 0
        self._last_height = 0
    
    def _setup_queue_section(self):
        """Setup the queue display section."""
        # Header
        header = ctk.CTkFrame(self.right_frame, fg_color="#3d3a1e", corner_radius=10)
        header.pack(fill="x", padx=15, pady=15)
        
        ctk.CTkLabel(
            header,
            text="Game Queue",
            font=get_font(18, "bold"),
            text_color="#ffd700"
        ).pack(side="left", padx=15, pady=10)
        
        self.queue_count_label = ctk.CTkLabel(
            header,
            text="0 waiting",
            font=get_font(12),
            text_color="#888888"
        )
        self.queue_count_label.pack(side="right", padx=15, pady=10)
        
        # Queue list
        self.queue_scroll = ctk.CTkScrollableFrame(
            self.right_frame, fg_color="transparent"
        )
        self.queue_scroll.pack(fill="both", expand=True, padx=15, pady=(0, 10))
        
        # Completed games section
        completed_header = ctk.CTkFrame(self.right_frame, fg_color="#252540", corner_radius=10)
        completed_header.pack(fill="x", padx=15, pady=(10, 5))
        
        ctk.CTkLabel(
            completed_header,
            text="Completed Tonight",
            font=get_font(14, "bold"),
            text_color="#4CAF50"
        ).pack(side="left", padx=15, pady=8)
        
        self.completed_count_label = ctk.CTkLabel(
            completed_header,
            text="0 games",
            font=get_font(11),
            text_color="#888888"
        )
        self.completed_count_label.pack(side="right", padx=15, pady=8)
        
        self.completed_scroll = ctk.CTkScrollableFrame(
            self.right_frame, fg_color="transparent", height=150
        )
        self.completed_scroll.pack(fill="x", padx=15, pady=(0, 15))
    
    def _on_resize(self, event):
        """Handle window resize - debounced refresh for responsive layout."""
        new_width = self.winfo_width()
        new_height = self.winfo_height()
        
        if abs(new_width - self._last_width) > 50 or abs(new_height - self._last_height) > 50:
            self._last_width = new_width
            self._last_height = new_height
            
            if self._resize_after_id:
                self.after_cancel(self._resize_after_id)
            self._resize_after_id = self.after(150, self.refresh_tables)
    
    def format_player_name(self, name: str) -> str:
        """Format name: 'Ethan Boyd' -> 'Ethan B', but keep funny/unusual names."""
        if not name:
            return "Unknown"
        
        funny_indicators = [
            name.islower(),
            name.isupper() and len(name) > 3,
            any(c.isdigit() for c in name),
            len(name.split()) == 1,
            any(c in name for c in ['_', '@', '#', '!', '$', '%']),
            len(name) <= 4 and name.isupper(),
            '"' in name or "'" in name.replace("'", ""),
        ]
        
        if any(funny_indicators):
            return name[:15]
        
        parts = name.split()
        
        if len(parts) == 2:
            first, last = parts
            if first[0].isupper() and last[0].isupper() and len(last) > 1:
                return f"{first} {last[0]}"
        
        return name[:15]
    
    def update_table_count(self, value):
        self.num_tables = int(value)
        self.db.set_setting("num_tables", value)
        self.refresh_tables()
    
    def start_timer_updates(self):
        """Update timers every second."""
        self.update_timers()
    
    def update_timers(self):
        """Update match duration timers and clock."""
        now = datetime.now()
        time_str = now.strftime("%I:%M %p")
        self.time_label.configure(text=f"{time_str}")
        
        for table_num, timer_info in self.timer_labels.items():
            if timer_info and 'start_time' in timer_info:
                start = timer_info['start_time']
                if start:
                    try:
                        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                        elapsed = now - start_dt.replace(tzinfo=None)
                        minutes = int(elapsed.total_seconds() // 60)
                        timer_info['label'].configure(text=f"{minutes} min")
                    except (ValueError, AttributeError, TypeError):
                        pass
        
        self.after_id = self.after(10000, self.update_timers)
    
    def _calculate_table_size(self):
        """Calculate responsive table widget size based on available space."""
        frame_width = self.tables_frame.winfo_width()
        frame_height = self.tables_frame.winfo_height()
        
        if frame_width < 100:
            frame_width = 600
        if frame_height < 100:
            frame_height = 400
        
        if self.num_tables == 1:
            card_width = min(400, frame_width - 60)
            card_height = min(300, frame_height - 40)
        elif self.num_tables == 2:
            card_width = min(300, (frame_width - 80) // 2)
            card_height = min(280, frame_height - 40)
        elif self.num_tables <= 4:
            card_width = min(280, (frame_width - 80) // 2)
            card_height = min(220, (frame_height - 60) // 2)
        else:
            card_width = min(250, (frame_width - 100) // 3)
            card_height = min(200, (frame_height - 60) // 2)
        
        card_width = max(220, card_width)
        card_height = max(180, card_height)
        
        return card_width, card_height
    
    def refresh_tables(self):
        """Refresh the entire view including tables and queue."""
        self._refresh_tables_display()
        self._refresh_queue_display()
    
    def _refresh_tables_display(self):
        """Refresh just the tables display."""
        for widget in self.tables_frame.winfo_children():
            widget.destroy()
        self.table_widgets.clear()
        self.timer_labels.clear()
        
        # Get league night for status-based queries
        league_night = self.db.get_current_league_night()
        
        active_tables = {}
        active_count = 0
        
        if league_night:
            # Use new status-based query
            live_matches = self.db.get_live_matches(league_night['id'])
            for match in live_matches:
                table_num = match['table_number']
                active_tables[table_num] = match
                active_count += 1
        else:
            # Fallback to old method
            matches = self.db.get_all_matches(limit=100)
            for match in matches:
                if not match['is_complete']:
                    table_num = match['table_number']
                    active_tables[table_num] = match
                    active_count += 1
        
        available = self.num_tables - active_count
        self.stats_label.configure(
            text=f"{active_count} live | {available} available"
        )
        
        card_width, card_height = self._calculate_table_size()
        
        self.tables_frame.grid_columnconfigure(0, weight=1)
        self.tables_frame.grid_rowconfigure(0, weight=1)
        
        main_container = ctk.CTkFrame(self.tables_frame, fg_color="transparent")
        main_container.place(relx=0.5, rely=0.5, anchor="center")
        
        # Layout based on table count
        if self.num_tables <= 2:
            row_frame = ctk.CTkFrame(main_container, fg_color="transparent")
            row_frame.pack(expand=True)
            for i in range(1, self.num_tables + 1):
                table_widget = self.create_table_widget(row_frame, i, active_tables.get(i), card_width, card_height)
                table_widget.pack(side="left", padx=15, pady=15)
                self.table_widgets[i] = table_widget
        elif self.num_tables <= 4:
            # 2x2 grid
            top_row = ctk.CTkFrame(main_container, fg_color="transparent")
            top_row.pack()
            for i in range(1, 3):
                table_widget = self.create_table_widget(top_row, i, active_tables.get(i), card_width, card_height)
                table_widget.pack(side="left", padx=15, pady=10)
                self.table_widgets[i] = table_widget
            
            if self.num_tables > 2:
                bottom_row = ctk.CTkFrame(main_container, fg_color="transparent")
                bottom_row.pack()
                for i in range(3, self.num_tables + 1):
                    table_widget = self.create_table_widget(bottom_row, i, active_tables.get(i), card_width, card_height)
                    table_widget.pack(side="left", padx=15, pady=10)
                    self.table_widgets[i] = table_widget
        else:
            # 3xN grid for 5-6 tables
            top_row = ctk.CTkFrame(main_container, fg_color="transparent")
            top_row.pack()
            for i in range(1, 4):
                table_widget = self.create_table_widget(top_row, i, active_tables.get(i), card_width, card_height)
                table_widget.pack(side="left", padx=10, pady=10)
                self.table_widgets[i] = table_widget
            
            bottom_row = ctk.CTkFrame(main_container, fg_color="transparent")
            bottom_row.pack()
            for i in range(4, self.num_tables + 1):
                table_widget = self.create_table_widget(bottom_row, i, active_tables.get(i), card_width, card_height)
                table_widget.pack(side="left", padx=10, pady=10)
                self.table_widgets[i] = table_widget
    
    def _refresh_queue_display(self):
        """Refresh the queue and completed games display."""
        for widget in self.queue_scroll.winfo_children():
            widget.destroy()
        for widget in self.completed_scroll.winfo_children():
            widget.destroy()
        
        league_night = self.db.get_current_league_night()
        
        if not league_night:
            ctk.CTkLabel(
                self.queue_scroll,
                text="No active league night",
                font=get_font(12),
                text_color="#666666"
            ).pack(pady=20)
            self.queue_count_label.configure(text="0 waiting")
            self.completed_count_label.configure(text="0 games")
            return
        
        # Get queued matches
        queued_matches = self.db.get_queued_matches(league_night['id'])
        self.queue_count_label.configure(text=f"{len(queued_matches)} waiting")
        
        if queued_matches:
            for i, match in enumerate(queued_matches):
                self._create_queue_item(match, i + 1)
        else:
            ctk.CTkLabel(
                self.queue_scroll,
                text="Queue is empty",
                font=get_font(12),
                text_color="#666666"
            ).pack(pady=20)
        
        # Get completed matches
        completed_matches = self.db.get_matches_by_status(league_night['id'], 'completed')
        self.completed_count_label.configure(text=f"{len(completed_matches)} games")
        
        if completed_matches:
            for match in completed_matches[-5:]:  # Show last 5
                self._create_completed_item(match)
        else:
            ctk.CTkLabel(
                self.completed_scroll,
                text="No completed games yet",
                font=get_font(11),
                text_color="#666666"
            ).pack(pady=10)
    
    def _create_queue_item(self, match: dict, position: int):
        """Create a queue item display."""
        frame = ctk.CTkFrame(self.queue_scroll, fg_color="#3d3a1e", corner_radius=8)
        frame.pack(fill="x", pady=2)
        
        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.pack(fill="x", padx=10, pady=8)
        
        # Position
        ctk.CTkLabel(
            inner,
            text=f"#{position}",
            font=get_font(12, "bold"),
            text_color="#ffd700",
            width=30
        ).pack(side="left")
        
        # Teams
        team1 = self.format_player_name(match['team1_p1_name'])
        if match['team1_p2_name']:
            team1 += f" & {self.format_player_name(match['team1_p2_name'])}"
        
        team2 = self.format_player_name(match['team2_p1_name'])
        if match['team2_p2_name']:
            team2 += f" & {self.format_player_name(match['team2_p2_name'])}"
        
        ctk.CTkLabel(
            inner,
            text=f"{team1} vs {team2}",
            font=get_font(11),
            text_color="#dddddd"
        ).pack(side="left", padx=(5, 0))
    
    def _create_completed_item(self, match: dict):
        """Create a completed game item display."""
        frame = ctk.CTkFrame(self.completed_scroll, fg_color="#1e4a1e", corner_radius=6)
        frame.pack(fill="x", pady=1)
        
        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.pack(fill="x", padx=8, pady=5)
        
        # Get winner info
        games = self.db.get_games_for_match(match['id'])
        t1_wins = sum(1 for g in games if g['winner_team'] == 1)
        t2_wins = sum(1 for g in games if g['winner_team'] == 2)
        
        team1 = self.format_player_name(match['team1_p1_name'])
        team2 = self.format_player_name(match['team2_p1_name'])
        
        winner_team = 1 if t1_wins > t2_wins else 2
        winner_name = team1 if winner_team == 1 else team2
        
        ctk.CTkLabel(
            inner,
            text=f"{winner_name} won ({t1_wins}-{t2_wins})",
            font=get_font(10),
            text_color="#90EE90"
        ).pack(side="left")
    
    def create_table_widget(self, parent, table_num: int, match=None, card_width=250, card_height=200):
        """Create a table widget display."""
        if match:
            status_color = "#1e4a1e"
            border_color = "#4CAF50"
            status_text = "LIVE"
            status_text_color = "#ff6b6b"
            is_clickable = True
        else:
            status_color = "#252540"
            border_color = "#3d3d5c"
            status_text = "Available"
            status_text_color = "#666666"
            is_clickable = False
        
        outer_frame = ctk.CTkFrame(parent, fg_color=border_color, corner_radius=18)
        
        frame = ctk.CTkFrame(outer_frame, fg_color=status_color, corner_radius=15, 
                            width=card_width, height=card_height)
        frame.pack(padx=3, pady=3)
        frame.pack_propagate(False)
        
        if is_clickable and match and self.on_match_click:
            outer_frame.configure(cursor="hand2")
            frame.configure(cursor="hand2")
            
            def on_click(event, match_id=match['id']):
                self.on_match_click(match_id)
            
            outer_frame.bind("<Button-1>", on_click)
            frame.bind("<Button-1>", on_click)
        
        # Table number header
        header = ctk.CTkFrame(frame, fg_color="#1a1a2e", corner_radius=10)
        header.pack(fill="x", padx=10, pady=(10, 5))
        
        header_content = ctk.CTkFrame(header, fg_color="transparent")
        header_content.pack(fill="x", padx=10, pady=8)
        
        ctk.CTkLabel(
            header_content,
            text=f"Table {table_num}",
            font=get_font(18, "bold")
        ).pack(side="left")
        
        status_badge = ctk.CTkLabel(
            header_content,
            text=status_text,
            font=get_font(11, "bold"),
            text_color=status_text_color
        )
        status_badge.pack(side="right")
        
        if match:
            # Match info
            info_frame = ctk.CTkFrame(frame, fg_color="#1a1a2e", corner_radius=10)
            info_frame.pack(fill="x", padx=10, pady=5)
            
            p1_name = self.format_player_name(match['team1_p1_name'])
            p2_name = self.format_player_name(match['team1_p2_name']) if match['team1_p2_name'] else None
            team1_text = f"{p1_name} & {p2_name}" if p2_name else p1_name
            
            ctk.CTkLabel(
                info_frame,
                text=team1_text,
                font=get_font(12, "bold"),
                text_color="#90EE90"
            ).pack(pady=(8, 2))
            
            ctk.CTkLabel(info_frame, text="vs", font=get_font(10), 
                        text_color="#888888").pack()
            
            p1_name = self.format_player_name(match['team2_p1_name'])
            p2_name = self.format_player_name(match['team2_p2_name']) if match['team2_p2_name'] else None
            team2_text = f"{p1_name} & {p2_name}" if p2_name else p1_name
            
            ctk.CTkLabel(
                info_frame,
                text=team2_text,
                font=get_font(12, "bold"),
                text_color="#90CAF9"
            ).pack(pady=(2, 8))
            
            # Score and controls
            controls_frame = ctk.CTkFrame(frame, fg_color="transparent")
            controls_frame.pack(fill="x", padx=10, pady=5)
            
            games = self.db.get_games_for_match(match['id'])
            t1_wins = sum(1 for g in games if g['winner_team'] == 1)
            t2_wins = sum(1 for g in games if g['winner_team'] == 2)
            
            score_frame = ctk.CTkFrame(controls_frame, fg_color="#1a1a2e", corner_radius=8)
            score_frame.pack(side="left", padx=2)
            
            ctk.CTkLabel(
                score_frame,
                text=f" {t1_wins} - {t2_wins} ",
                font=get_font(14, "bold"),
                text_color="#ffd700"
            ).pack(pady=5, padx=8)
            
        else:
            # Empty state
            empty_frame = ctk.CTkFrame(frame, fg_color="transparent")
            empty_frame.pack(expand=True, fill="both", padx=10, pady=5)
            
            table_width = max(60, int(card_width * 0.35))
            table_height = max(35, int(card_height * 0.25))
            
            table_visual = ctk.CTkFrame(empty_frame, fg_color="#0d4a1c", corner_radius=8, 
                                       width=table_width, height=table_height)
            table_visual.pack(pady=(10, 8))
            table_visual.pack_propagate(False)
            
            felt = ctk.CTkFrame(table_visual, fg_color="#1a5a2a", corner_radius=5,
                               width=int(table_width * 0.85), height=int(table_height * 0.75))
            felt.place(relx=0.5, rely=0.5, anchor="center")
            
            ctk.CTkLabel(
                empty_frame,
                text="Ready for players",
                font=get_font(12),
                text_color="#666666"
            ).pack(pady=(5, 2))
            
            # Start from queue button if queue has items
            league_night = self.db.get_current_league_night()
            if league_night:
                next_match = self.db.get_next_queued_match(league_night['id'])
                if next_match:
                    ctk.CTkButton(
                        empty_frame,
                        text="Start Next Game",
                        font=get_font(11),
                        height=30,
                        fg_color="#ffd700",
                        hover_color="#ccaa00",
                        text_color="#000000",
                        command=lambda t=table_num: self.start_next_on_table(t)
                    ).pack(pady=5)
        
        # Bind click events to all children for active matches
        if is_clickable and match and self.on_match_click:
            def bind_click_recursive(widget, match_id):
                widget.bind("<Button-1>", lambda e, mid=match_id: self.on_match_click(mid))
                try:
                    widget.configure(cursor="hand2")
                except (AttributeError, KeyError):
                    pass
                for child in widget.winfo_children():
                    bind_click_recursive(child, match_id)
            
            bind_click_recursive(frame, match['id'])
        
        return outer_frame
    
    def complete_match_on_table(self, match: dict, table_num: int):
        """Complete a match and optionally start the next queued game."""
        # Mark match as completed
        self.db.complete_match_with_status(match['id'])
        
        # Check if there's a next game in queue
        league_night = self.db.get_current_league_night()
        if league_night:
            next_match = self.db.get_next_queued_match(league_night['id'])
            if next_match:
                # Ask if they want to start the next game
                result = messagebox.askyesno(
                    "Game Completed",
                    f"Match completed on Table {table_num}!\n\n"
                    f"Start next game from queue on this table?"
                )
                if result:
                    self.db.start_match(next_match['id'], table_num)
        
        self.refresh_tables()
    
    def start_next_on_table(self, table_num: int):
        """Start the next queued game on a specific table."""
        league_night = self.db.get_current_league_night()
        if league_night:
            next_match = self.db.advance_queue(league_night['id'], table_num)
            if next_match:
                self.refresh_tables()
            else:
                messagebox.showinfo("Queue Empty", "No more games in the queue.")
    
    def destroy(self):
        """Clean up timers on destroy."""
        if self.after_id:
            self.after_cancel(self.after_id)
        if self._resize_after_id:
            self.after_cancel(self._resize_after_id)
        super().destroy()
