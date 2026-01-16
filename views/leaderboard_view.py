"""
EcoPOOL League - Leaderboard View
Enhanced with point-based ranking, season filter, and expanded statistics.
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
from database import DatabaseManager
from exporter import Exporter
from profile_pictures import ProfilePicture
from fonts import get_font


class LeaderboardView(ctk.CTkFrame):
    def __init__(self, parent, db: DatabaseManager):
        super().__init__(parent, fg_color="transparent")
        self.db = db
        self.exporter = Exporter(db)
        
        # Hidden menu trigger - click counter
        self._title_click_count = 0
        self._last_click_time = 0
        
        self.setup_ui()
        self.load_leaderboard()
        
        # Bind keyboard shortcut for hidden menu (Ctrl+Shift+R)
        # Use after() to bind once the widget is fully initialized
        self.after(100, self._setup_keyboard_shortcut)
    
    def _setup_keyboard_shortcut(self):
        """Setup keyboard shortcut after widget is initialized."""
        try:
            self.winfo_toplevel().bind("<Control-Shift-R>", self._show_hidden_menu)
        except Exception:
            pass  # Ignore if binding fails
    
    def setup_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))
        
        # Title - clickable for hidden menu (click 5 times quickly)
        self.title_label = ctk.CTkLabel(
            header, 
            text="Leaderboard",
            font=get_font(28, "bold"),
            cursor="hand2"
        )
        self.title_label.pack(side="left")
        self.title_label.bind("<Button-1>", self._on_title_click)
        
        # Export buttons
        ctk.CTkButton(
            header,
            text="Export PDF",
            font=get_font(13),
            fg_color="#3d5a80",
            hover_color="#2d4a70",
            height=38,
            command=self.export_pdf
        ).pack(side="right", padx=5)
        
        ctk.CTkButton(
            header,
            text="Export CSV",
            font=get_font(13),
            fg_color="#555555",
            hover_color="#444444",
            height=38,
            command=self.export_csv
        ).pack(side="right", padx=5)
        
        # Filters row
        filters_frame = ctk.CTkFrame(self, fg_color="#252540", corner_radius=10)
        filters_frame.pack(fill="x", padx=20, pady=10)
        
        filters_inner = ctk.CTkFrame(filters_frame, fg_color="transparent")
        filters_inner.pack(fill="x", padx=15, pady=10)
        
        # Sort options
        ctk.CTkLabel(
            filters_inner, text="Sort by:",
            font=get_font(13)
        ).pack(side="left", padx=(0, 10))
        
        self.sort_var = ctk.StringVar(value="points")  # Default to points now
        
        for text, value in [("Points", "points"), ("Wins", "wins"), 
                            ("Win Rate", "win_rate"), ("Avg Pts", "avg_points")]:
            ctk.CTkRadioButton(
                filters_inner, text=text, variable=self.sort_var, value=value,
                font=get_font(12),
                fg_color="#2d7a3e", hover_color="#1a5f2a",
                command=self.load_leaderboard
            ).pack(side="left", padx=10)
        
        # Leaderboard container
        self.board_frame = ctk.CTkScrollableFrame(
            self, fg_color="#1a1a2e", corner_radius=15
        )
        self.board_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Headers
        headers_frame = ctk.CTkFrame(self.board_frame, fg_color="#2d7a3e", corner_radius=10)
        headers_frame.pack(fill="x", padx=5, pady=(5, 10))
        
        # Updated headers with emphasis on Points
        headers = [
            ("Rank", 50), ("", 50), ("Player", 140), 
            ("Points", 80), ("Games", 60), ("W", 50), ("L", 50),
            ("Win %", 70), ("Avg", 60), ("Golden", 60)
        ]
        
        for text, width in headers:
            font_weight = "bold" if text == "Points" else "bold"
            text_color = "#ffd700" if text == "Points" else "#ffffff"
            ctk.CTkLabel(
                headers_frame,
                text=text,
                font=get_font(12, font_weight),
                text_color=text_color,
                width=width,
                anchor="center"
            ).pack(side="left", padx=2, pady=8)
        
        self.rows_container = ctk.CTkFrame(self.board_frame, fg_color="transparent")
        self.rows_container.pack(fill="both", expand=True)
    
    def load_leaderboard(self):
        for widget in self.rows_container.winfo_children():
            widget.destroy()
        
        # Get leaderboard (all time)
        leaderboard = self.db.get_leaderboard_for_season(
            None,  # All time
            self.sort_var.get()
        )
        
        if not leaderboard:
            empty_frame = ctk.CTkFrame(self.rows_container, fg_color="transparent")
            empty_frame.pack(expand=True, pady=50)
            
            ctk.CTkLabel(
                empty_frame,
                text="No rankings yet",
                font=get_font(18, "bold"),
                text_color="#888888"
            ).pack(pady=10)
            
            ctk.CTkLabel(
                empty_frame,
                text="Play some games to see the leaderboard!",
                font=get_font(14),
                text_color="#666666"
            ).pack()
            return
        
        for i, entry in enumerate(leaderboard, 1):
            self.create_row(i, entry)
    
    def create_row(self, rank: int, entry: dict):
        """Create a leaderboard row."""
        player = entry['player']
        
        # Determine row color based on rank
        if rank == 1:
            bg_color = "#5c4d1a"  # Gold tint
            rank_text = "1st"
        elif rank == 2:
            bg_color = "#4a4a4a"  # Silver tint
            rank_text = "2nd"
        elif rank == 3:
            bg_color = "#4a3020"  # Bronze tint
            rank_text = "3rd"
        else:
            bg_color = "#252540"
            rank_text = str(rank)
        
        row = ctk.CTkFrame(
            self.rows_container, 
            fg_color=bg_color, 
            corner_radius=8, 
            height=55
        )
        row.pack(fill="x", padx=5, pady=2)
        row.pack_propagate(False)
        
        # Rank
        ctk.CTkLabel(
            row, text=rank_text,
            font=get_font(14 if rank <= 3 else 12, "bold"),
            width=50, anchor="center"
        ).pack(side="left", padx=2, pady=8)
        
        # Profile picture
        pic_frame = ctk.CTkFrame(row, fg_color="transparent", width=50)
        pic_frame.pack(side="left", padx=2)
        pic_frame.pack_propagate(False)
        
        try:
            pic = ProfilePicture(
                pic_frame, size=38,
                image_path=player.profile_picture,
                player_name=player.name
            )
            pic.pack(expand=True)
        except (OSError, FileNotFoundError, AttributeError):
            pass
        
        # Name
        ctk.CTkLabel(
            row, text=player.name,
            font=get_font(13, "bold"),
            width=140, anchor="w"
        ).pack(side="left", padx=2)
        
        # POINTS (primary stat - emphasized)
        points_frame = ctk.CTkFrame(row, fg_color="#2d5a2d", corner_radius=5, width=80)
        points_frame.pack(side="left", padx=2)
        points_frame.pack_propagate(False)
        
        ctk.CTkLabel(
            points_frame, text=str(entry['total_points']),
            font=get_font(14, "bold"),
            text_color="#ffd700",
            anchor="center"
        ).pack(expand=True)
        
        # Games
        ctk.CTkLabel(
            row, text=str(entry['games_played']),
            font=get_font(12),
            width=60, anchor="center"
        ).pack(side="left", padx=2)
        
        # Wins
        ctk.CTkLabel(
            row, text=str(entry['games_won']),
            font=get_font(12),
            text_color="#4CAF50",
            width=50, anchor="center"
        ).pack(side="left", padx=2)
        
        # Losses
        ctk.CTkLabel(
            row, text=str(entry['games_lost']),
            font=get_font(12),
            text_color="#ff6b6b",
            width=50, anchor="center"
        ).pack(side="left", padx=2)
        
        # Win %
        win_rate = entry['win_rate']
        win_color = "#4CAF50" if win_rate >= 50 else "#ff6b6b"
        
        win_frame = ctk.CTkFrame(row, fg_color="transparent", width=70)
        win_frame.pack(side="left", padx=2)
        
        ctk.CTkLabel(
            win_frame, text=f"{win_rate:.0f}%",
            font=get_font(12, "bold"),
            text_color=win_color
        ).pack()
        
        # Mini progress bar
        progress_bg = ctk.CTkFrame(win_frame, fg_color="#333333", height=3, corner_radius=1)
        progress_bg.pack(fill="x", pady=1)
        
        progress_fill = ctk.CTkFrame(
            progress_bg, 
            fg_color=win_color, 
            height=3, 
            corner_radius=1,
            width=int(50 * (win_rate / 100))
        )
        progress_fill.place(x=0, y=0)
        
        # Avg Points
        ctk.CTkLabel(
            row, text=f"{entry['avg_points']:.1f}",
            font=get_font(12),
            text_color="#64B5F6",
            width=60, anchor="center"
        ).pack(side="left", padx=2)
        
        # Golden Breaks
        golden = entry['golden_breaks']
        golden_text = f"{golden}" if golden > 0 else "-"
        ctk.CTkLabel(
            row, text=golden_text,
            font=get_font(12),
            text_color="#ffd700" if golden > 0 else "#666666",
            width=60, anchor="center"
        ).pack(side="left", padx=2)
    
    def export_pdf(self):
        filepath = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            title="Export Leaderboard",
            initialfile="ecopool_leaderboard.pdf"
        )
        
        if filepath:
            if self.exporter.export_leaderboard_pdf(filepath, self.sort_var.get()):
                messagebox.showinfo("Success", f"Leaderboard exported to:\n{filepath}")
            else:
                messagebox.showerror("Error", "Failed to export leaderboard.")
    
    def export_csv(self):
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            title="Export Players",
            initialfile="ecopool_players.csv"
        )
        
        if filepath:
            if self.exporter.export_players_csv(filepath):
                messagebox.showinfo("Success", f"Players exported to:\n{filepath}")
            else:
                messagebox.showerror("Error", "Failed to export players.")
    
    def _on_title_click(self, event=None):
        """Handle title click for hidden menu trigger."""
        import time
        current_time = time.time()
        
        # Reset count if more than 2 seconds since last click
        if current_time - self._last_click_time > 2.0:
            self._title_click_count = 0
        
        self._last_click_time = current_time
        self._title_click_count += 1
        
        # Show hidden menu after 5 rapid clicks
        if self._title_click_count >= 5:
            self._title_click_count = 0
            self._show_hidden_menu()
    
    def _show_hidden_menu(self, event=None):
        """Show the hidden admin menu for leaderboard reset."""
        # Create hidden menu dialog
        dialog = ctk.CTkToplevel(self)
        dialog.title("Admin Menu")
        dialog.geometry("400x300")
        dialog.transient(self)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() // 2) - 200
        y = self.winfo_rooty() + (self.winfo_height() // 2) - 150
        dialog.geometry(f"+{x}+{y}")
        
        # Warning header
        ctk.CTkLabel(
            dialog,
            text="⚠️ Admin Menu",
            font=get_font(20, "bold"),
            text_color="#ff6b6b"
        ).pack(pady=(20, 10))
        
        ctk.CTkLabel(
            dialog,
            text="These actions are destructive and cannot be undone!",
            font=get_font(12),
            text_color="#ffcc80"
        ).pack(pady=(0, 20))
        
        # Reset leaderboard button
        reset_frame = ctk.CTkFrame(dialog, fg_color="#3a2020", corner_radius=10)
        reset_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(
            reset_frame,
            text="Reset Leaderboard",
            font=get_font(14, "bold"),
            text_color="#ff6b6b"
        ).pack(pady=(15, 5))
        
        ctk.CTkLabel(
            reset_frame,
            text="Deletes ALL match history and game data.\nPlayer accounts will be kept.",
            font=get_font(11),
            text_color="#aaaaaa"
        ).pack(pady=(0, 10))
        
        ctk.CTkButton(
            reset_frame,
            text="Reset All Leaderboard Data",
            font=get_font(12, "bold"),
            fg_color="#c44536",
            hover_color="#a43526",
            height=40,
            command=lambda: self._confirm_reset_leaderboard(dialog)
        ).pack(fill="x", padx=20, pady=(0, 15))
        
        # Close button
        ctk.CTkButton(
            dialog,
            text="Close",
            font=get_font(12),
            fg_color="#555555",
            hover_color="#444444",
            height=35,
            command=dialog.destroy
        ).pack(pady=20)
    
    def _confirm_reset_leaderboard(self, parent_dialog):
        """Confirm and execute leaderboard reset."""
        # First confirmation
        result = messagebox.askyesno(
            "Confirm Reset",
            "Are you SURE you want to reset the leaderboard?\n\n"
            "This will DELETE:\n"
            "• All match history\n"
            "• All game scores\n"
            "• All player statistics\n\n"
            "This action CANNOT be undone!",
            icon="warning",
            parent=parent_dialog
        )
        
        if not result:
            return
        
        # Second confirmation with typing requirement
        confirm_dialog = ctk.CTkToplevel(parent_dialog)
        confirm_dialog.title("Final Confirmation")
        confirm_dialog.geometry("350x200")
        confirm_dialog.transient(parent_dialog)
        confirm_dialog.grab_set()
        
        confirm_dialog.update_idletasks()
        x = parent_dialog.winfo_rootx() + 25
        y = parent_dialog.winfo_rooty() + 50
        confirm_dialog.geometry(f"+{x}+{y}")
        
        ctk.CTkLabel(
            confirm_dialog,
            text="Type 'RESET' to confirm:",
            font=get_font(14, "bold"),
            text_color="#ff6b6b"
        ).pack(pady=(30, 10))
        
        entry = ctk.CTkEntry(
            confirm_dialog,
            width=200,
            height=40,
            font=get_font(16),
            placeholder_text="Type RESET here"
        )
        entry.pack(pady=10)
        
        def do_reset():
            if entry.get().strip().upper() == "RESET":
                # Actually reset the leaderboard
                self.db.reset_leaderboard()
                confirm_dialog.destroy()
                parent_dialog.destroy()
                
                messagebox.showinfo(
                    "Reset Complete",
                    "Leaderboard has been reset.\n\n"
                    "All match history and statistics have been cleared."
                )
                
                # Refresh the view
                self.load_leaderboard()
            else:
                messagebox.showerror(
                    "Invalid",
                    "You must type 'RESET' exactly to confirm.",
                    parent=confirm_dialog
                )
        
        ctk.CTkButton(
            confirm_dialog,
            text="Confirm Reset",
            font=get_font(12, "bold"),
            fg_color="#c44536",
            hover_color="#a43526",
            height=35,
            command=do_reset
        ).pack(pady=15)
