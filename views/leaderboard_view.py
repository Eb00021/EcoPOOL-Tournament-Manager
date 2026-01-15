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
        
        self.setup_ui()
        self.load_leaderboard()
    
    def setup_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(
            header, 
            text="Leaderboard",
            font=get_font(28, "bold")
        ).pack(side="left")
        
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
