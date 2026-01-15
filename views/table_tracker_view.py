"""
EcoPOOL League - Pool Table Tracker View
Visual overview of all tables at the pool hall.
"""

import customtkinter as ctk
from datetime import datetime
from database import DatabaseManager
from fonts import get_font


class TableTrackerView(ctk.CTkFrame):
    def __init__(self, parent, db: DatabaseManager, on_match_click=None):
        super().__init__(parent, fg_color="transparent")
        self.db = db
        self.on_match_click = on_match_click  # Callback for navigating to scorecard
        
        # Load saved table count or default to 4
        saved_count = self.db.get_setting("num_tables", "4")
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
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(
            header, 
            text="🎱 Pool Hall Table Tracker",
            font=get_font(28, "bold")
        ).pack(side="left")
        
        # Current time display
        self.time_label = ctk.CTkLabel(
            header,
            text="",
            font=get_font(14),
            text_color="#888888"
        )
        self.time_label.pack(side="right", padx=20)
        
        ctk.CTkButton(
            header,
            text="🔄 Refresh",
            font=get_font(14),
            fg_color="#3d5a80",
            hover_color="#2d4a70",
            height=40,
            command=self.refresh_tables
        ).pack(side="right")
        
        # Table count selector and stats
        count_frame = ctk.CTkFrame(self, fg_color="transparent")
        count_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(
            count_frame, text="Tables:",
            font=get_font(14)
        ).pack(side="left", padx=(0, 10))
        
        self.table_count_var = ctk.StringVar(value=str(self.num_tables))
        table_selector = ctk.CTkComboBox(
            count_frame,
            values=["1", "2", "3", "4"],
            variable=self.table_count_var,
            width=80,
            command=self.update_table_count
        )
        table_selector.pack(side="left")
        
        # Stats summary
        self.stats_label = ctk.CTkLabel(
            count_frame,
            text="",
            font=get_font(13),
            text_color="#888888"
        )
        self.stats_label.pack(side="left", padx=30)
        
        # Legend
        legend = ctk.CTkFrame(count_frame, fg_color="transparent")
        legend.pack(side="right")
        
        for color, text in [("#4CAF50", "Active"), ("#2d2d44", "Available")]:
            dot = ctk.CTkFrame(legend, fg_color=color, width=12, height=12, corner_radius=6)
            dot.pack(side="left", padx=(15, 5))
            ctk.CTkLabel(legend, text=text, font=get_font(12)).pack(side="left")
        
        # Tables container (non-scrollable, fills space)
        self.tables_frame = ctk.CTkFrame(self, fg_color="#1a1a2e", corner_radius=15)
        self.tables_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.table_widgets = {}
        self.timer_labels = {}
        self._last_width = 0
        self._last_height = 0
    
    def _on_resize(self, event):
        """Handle window resize - debounced refresh for responsive layout."""
        # Only respond to significant size changes
        new_width = self.winfo_width()
        new_height = self.winfo_height()
        
        if abs(new_width - self._last_width) > 50 or abs(new_height - self._last_height) > 50:
            self._last_width = new_width
            self._last_height = new_height
            
            # Debounce the refresh
            if self._resize_after_id:
                self.after_cancel(self._resize_after_id)
            self._resize_after_id = self.after(150, self.refresh_tables)
    
    def format_player_name(self, name: str) -> str:
        """Format name: 'Ethan Boyd' -> 'Ethan B', but keep funny/unusual names."""
        if not name:
            return "Unknown"
        
        # List of patterns that indicate a "funny" or nickname (don't abbreviate)
        funny_indicators = [
            # All lowercase or all uppercase (likely a nickname)
            name.islower(),
            name.isupper() and len(name) > 3,
            # Contains numbers
            any(c.isdigit() for c in name),
            # Single word that's not a typical first name length
            len(name.split()) == 1,
            # Contains special characters (except hyphen/apostrophe)
            any(c in name for c in ['_', '@', '#', '!', '$', '%']),
            # All caps short nickname
            len(name) <= 4 and name.isupper(),
            # Quoted or has emoji
            '"' in name or "'" in name.replace("'", ""),
        ]
        
        if any(funny_indicators):
            return name[:20]  # Keep funny names, just truncate if too long
        
        parts = name.split()
        
        # If it's a two-word name with normal capitalization, abbreviate
        if len(parts) == 2:
            first, last = parts
            # Check if both look like normal names (capitalized)
            if first[0].isupper() and last[0].isupper() and len(last) > 1:
                return f"{first} {last[0]}"
        
        # For other cases, just return the name (truncated if needed)
        return name[:20]
    
    def update_table_count(self, value):
        self.num_tables = int(value)
        self.db.set_setting("num_tables", value)
        self.refresh_tables()
    
    def start_timer_updates(self):
        """Update timers every second."""
        self.update_timers()
    
    def update_timers(self):
        """Update match duration timers and clock."""
        # Update current time
        now = datetime.now()
        self.time_label.configure(text=now.strftime("🕐 %I:%M %p"))
        
        # Update match timers
        for table_num, timer_info in self.timer_labels.items():
            if timer_info and 'start_time' in timer_info:
                start = timer_info['start_time']
                if start:
                    try:
                        start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                        elapsed = now - start_dt.replace(tzinfo=None)
                        minutes = int(elapsed.total_seconds() // 60)
                        timer_info['label'].configure(text=f"⏱️ {minutes} min")
                    except:
                        pass
        
        # Schedule next update
        self.after_id = self.after(10000, self.update_timers)  # Update every 10 seconds
    
    def _calculate_table_size(self):
        """Calculate responsive table widget size based on available space."""
        # Get available space
        frame_width = self.tables_frame.winfo_width()
        frame_height = self.tables_frame.winfo_height()
        
        # Use reasonable defaults if not yet rendered
        if frame_width < 100:
            frame_width = 800
        if frame_height < 100:
            frame_height = 500
        
        # Calculate based on number of tables and layout
        if self.num_tables == 1:
            # Single table - use more space
            card_width = min(450, frame_width - 80)
            card_height = min(350, frame_height - 60)
        elif self.num_tables == 2:
            # 2 tables side by side
            card_width = min(350, (frame_width - 120) // 2)
            card_height = min(300, frame_height - 60)
        else:
            # 3-4 tables in 2x2 grid
            card_width = min(320, (frame_width - 120) // 2)
            card_height = min(250, (frame_height - 80) // 2)
        
        # Ensure minimum sizes
        card_width = max(250, card_width)
        card_height = max(180, card_height)
        
        return card_width, card_height
    
    def refresh_tables(self):
        # Clear existing
        for widget in self.tables_frame.winfo_children():
            widget.destroy()
        self.table_widgets.clear()
        self.timer_labels.clear()
        
        # Get active matches
        matches = self.db.get_all_matches(limit=100)
        active_tables = {}
        active_count = 0
        
        for match in matches:
            if not match['is_complete']:
                table_num = match['table_number']
                active_tables[table_num] = match
                active_count += 1
        
        # Update stats
        self.stats_label.configure(
            text=f"📊 {active_count} active match{'es' if active_count != 1 else ''} | {self.num_tables - active_count} available"
        )
        
        # Calculate responsive sizes
        card_width, card_height = self._calculate_table_size()
        
        # Configure grid for responsive layout
        self.tables_frame.grid_columnconfigure(0, weight=1)
        self.tables_frame.grid_rowconfigure(0, weight=1)
        
        # Main container centered in the frame
        main_container = ctk.CTkFrame(self.tables_frame, fg_color="transparent")
        main_container.place(relx=0.5, rely=0.5, anchor="center")
        
        # Layout based on number of tables (1-4)
        if self.num_tables == 1:
            table_widget = self.create_table_widget(main_container, 1, active_tables.get(1), card_width, card_height)
            table_widget.pack(padx=20, pady=20)
            self.table_widgets[1] = table_widget
            
        elif self.num_tables == 2:
            row_frame = ctk.CTkFrame(main_container, fg_color="transparent")
            row_frame.pack(expand=True)
            for i in range(1, 3):
                table_widget = self.create_table_widget(row_frame, i, active_tables.get(i), card_width, card_height)
                table_widget.pack(side="left", padx=25, pady=20)
                self.table_widgets[i] = table_widget
                
        elif self.num_tables == 3:
            top_row = ctk.CTkFrame(main_container, fg_color="transparent")
            top_row.pack()
            for i in range(1, 3):
                table_widget = self.create_table_widget(top_row, i, active_tables.get(i), card_width, card_height)
                table_widget.pack(side="left", padx=25, pady=15)
                self.table_widgets[i] = table_widget
            
            bottom_row = ctk.CTkFrame(main_container, fg_color="transparent")
            bottom_row.pack()
            table_widget = self.create_table_widget(bottom_row, 3, active_tables.get(3), card_width, card_height)
            table_widget.pack(padx=25, pady=15)
            self.table_widgets[3] = table_widget
            
        else:  # 4 tables - 2x2 grid
            top_row = ctk.CTkFrame(main_container, fg_color="transparent")
            top_row.pack()
            for i in range(1, 3):
                table_widget = self.create_table_widget(top_row, i, active_tables.get(i), card_width, card_height)
                table_widget.pack(side="left", padx=25, pady=15)
                self.table_widgets[i] = table_widget
            
            bottom_row = ctk.CTkFrame(main_container, fg_color="transparent")
            bottom_row.pack()
            for i in range(3, 5):
                table_widget = self.create_table_widget(bottom_row, i, active_tables.get(i), card_width, card_height)
                table_widget.pack(side="left", padx=25, pady=15)
                self.table_widgets[i] = table_widget
    
    def create_table_widget(self, parent, table_num: int, match=None, card_width=280, card_height=220):
        # Determine status and colors
        if match:
            status_color = "#2d5a2d"  # Darker green for better contrast
            border_color = "#4CAF50"
            status_text = "🔴 LIVE"
            status_text_color = "#ff6b6b"
            is_clickable = True
        else:
            status_color = "#252540"
            border_color = "#3d3d5c"
            status_text = "Available"
            status_text_color = "#666666"
            is_clickable = False
        
        # Outer frame for border effect
        outer_frame = ctk.CTkFrame(parent, fg_color=border_color, corner_radius=18)
        
        frame = ctk.CTkFrame(outer_frame, fg_color=status_color, corner_radius=15, 
                            width=card_width, height=card_height)
        frame.pack(padx=3, pady=3)
        frame.pack_propagate(False)
        
        # Make active matches clickable
        if is_clickable and match and self.on_match_click:
            outer_frame.configure(cursor="hand2")
            frame.configure(cursor="hand2")
            
            def on_click(event, match_id=match['id']):
                self.on_match_click(match_id)
            
            outer_frame.bind("<Button-1>", on_click)
            frame.bind("<Button-1>", on_click)
        
        # Table number header with pool table icon
        header = ctk.CTkFrame(frame, fg_color="#1a1a2e", corner_radius=10)
        header.pack(fill="x", padx=12, pady=(12, 8))
        
        header_content = ctk.CTkFrame(header, fg_color="transparent")
        header_content.pack(fill="x", padx=10, pady=8)
        
        ctk.CTkLabel(
            header_content,
            text=f"🎱 Table {table_num}",
            font=get_font(20, "bold")
        ).pack(side="left")
        
        # Status badge
        status_badge = ctk.CTkLabel(
            header_content,
            text=status_text,
            font=get_font(12, "bold"),
            text_color=status_text_color
        )
        status_badge.pack(side="right")
        
        if match:
            # Match info container
            info_frame = ctk.CTkFrame(frame, fg_color="#1a1a2e", corner_radius=10)
            info_frame.pack(fill="x", padx=12, pady=5)
            
            # Team 1
            p1_name = self.format_player_name(match['team1_p1_name'])
            p2_name = self.format_player_name(match['team1_p2_name']) if match['team1_p2_name'] else None
            
            if p2_name:
                team1_text = f"{p1_name} & {p2_name}"
            else:
                team1_text = p1_name
            
            ctk.CTkLabel(
                info_frame,
                text=team1_text,
                font=get_font(13, "bold"),
                text_color="#90EE90"
            ).pack(pady=(8, 2))
            
            # VS divider
            vs_frame = ctk.CTkFrame(info_frame, fg_color="transparent")
            vs_frame.pack(fill="x", pady=2)
            ctk.CTkFrame(vs_frame, fg_color="#444444", height=1, width=60).pack(side="left", expand=True, padx=10)
            ctk.CTkLabel(vs_frame, text="VS", font=get_font(10, "bold"), 
                        text_color="#888888").pack(side="left")
            ctk.CTkFrame(vs_frame, fg_color="#444444", height=1, width=60).pack(side="left", expand=True, padx=10)
            
            # Team 2
            p1_name = self.format_player_name(match['team2_p1_name'])
            p2_name = self.format_player_name(match['team2_p2_name']) if match['team2_p2_name'] else None
            
            if p2_name:
                team2_text = f"{p1_name} & {p2_name}"
            else:
                team2_text = p1_name
            
            ctk.CTkLabel(
                info_frame,
                text=team2_text,
                font=get_font(13, "bold"),
                text_color="#90CAF9"
            ).pack(pady=(2, 8))
            
            # Score and timer row
            stats_frame = ctk.CTkFrame(frame, fg_color="transparent")
            stats_frame.pack(fill="x", padx=12, pady=5)
            
            # Game score with visual
            games = self.db.get_games_for_match(match['id'])
            t1_wins = sum(1 for g in games if g['winner_team'] == 1)
            t2_wins = sum(1 for g in games if g['winner_team'] == 2)
            
            score_frame = ctk.CTkFrame(stats_frame, fg_color="#1a1a2e", corner_radius=8)
            score_frame.pack(side="left", padx=5)
            
            ctk.CTkLabel(
                score_frame,
                text=f"  🏆 {t1_wins} - {t2_wins}  ",
                font=get_font(16, "bold"),
                text_color="#ffd700"
            ).pack(pady=6, padx=8)
            
            # Match timer
            timer_frame = ctk.CTkFrame(stats_frame, fg_color="#1a1a2e", corner_radius=8)
            timer_frame.pack(side="right", padx=5)
            
            timer_label = ctk.CTkLabel(
                timer_frame,
                text="⏱️ --",
                font=get_font(12),
                text_color="#aaaaaa"
            )
            timer_label.pack(pady=6, padx=8)
            
            # Store timer info for updates
            self.timer_labels[table_num] = {
                'label': timer_label,
                'start_time': match.get('date')
            }
            
        else:
            # Empty state with cool visual
            empty_frame = ctk.CTkFrame(frame, fg_color="transparent")
            empty_frame.pack(expand=True, fill="both", padx=12, pady=10)
            
            # Mini pool table visual - responsive sizing
            table_width = max(80, int(card_width * 0.45))
            table_height = max(50, int(card_height * 0.35))
            
            table_visual = ctk.CTkFrame(empty_frame, fg_color="#0d4a1c", corner_radius=8, 
                                       width=table_width, height=table_height)
            table_visual.pack(pady=(15, 10))
            table_visual.pack_propagate(False)
            
            # Inner felt - responsive
            felt_width = max(60, int(table_width * 0.85))
            felt_height = max(35, int(table_height * 0.75))
            felt = ctk.CTkFrame(table_visual, fg_color="#1a5a2a", corner_radius=5,
                               width=felt_width, height=felt_height)
            felt.place(relx=0.5, rely=0.5, anchor="center")
            
            ctk.CTkLabel(
                empty_frame,
                text="Ready for players",
                font=get_font(13),
                text_color="#666666"
            ).pack(pady=5)
            
            ctk.CTkLabel(
                empty_frame,
                text="🎯 Start a match!",
                font=get_font(11),
                text_color="#4CAF50"
            ).pack(pady=(0, 10))
        
        # Bind click events to all children for active matches
        if is_clickable and match and self.on_match_click:
            def bind_click_recursive(widget, match_id):
                widget.bind("<Button-1>", lambda e, mid=match_id: self.on_match_click(mid))
                try:
                    widget.configure(cursor="hand2")
                except:
                    pass
                for child in widget.winfo_children():
                    bind_click_recursive(child, match_id)
            
            bind_click_recursive(frame, match['id'])
        
        return outer_frame
    
    def destroy(self):
        """Clean up timers on destroy."""
        if self.after_id:
            self.after_cancel(self.after_id)
        if self._resize_after_id:
            self.after_cancel(self._resize_after_id)
        super().destroy()
