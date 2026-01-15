"""
EcoPOOL League - Leaderboard View
Enhanced with profile pictures and animations.
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
            text="🏆 Leaderboard",
            font=get_font(28, "bold")
        ).pack(side="left")
        
        # Export buttons
        ctk.CTkButton(
            header,
            text="📄 Export PDF",
            font=get_font(14),
            fg_color="#3d5a80",
            hover_color="#2d4a70",
            height=40,
            command=self.export_pdf
        ).pack(side="right", padx=5)
        
        ctk.CTkButton(
            header,
            text="📊 Export CSV",
            font=get_font(14),
            fg_color="#555555",
            hover_color="#444444",
            height=40,
            command=self.export_csv
        ).pack(side="right", padx=5)
        
        # Sort options
        sort_frame = ctk.CTkFrame(self, fg_color="transparent")
        sort_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(
            sort_frame, text="Sort by:",
            font=get_font(14)
        ).pack(side="left", padx=(0, 10))
        
        self.sort_var = ctk.StringVar(value="wins")
        
        for text, value in [("Wins", "wins"), ("Win Rate", "win_rate"), 
                            ("Total Points", "points"), ("Avg Points", "avg_points")]:
            ctk.CTkRadioButton(
                sort_frame, text=text, variable=self.sort_var, value=value,
                font=get_font(13),
                fg_color="#2d7a3e", hover_color="#1a5f2a",
                command=self.load_leaderboard
            ).pack(side="left", padx=15)
        
        # Leaderboard container
        self.board_frame = ctk.CTkScrollableFrame(
            self, fg_color="#1a1a2e", corner_radius=15
        )
        self.board_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Headers
        headers_frame = ctk.CTkFrame(self.board_frame, fg_color="#2d7a3e", corner_radius=10)
        headers_frame.pack(fill="x", padx=5, pady=(5, 10))
        
        headers = [("Rank", 60), ("", 55), ("Player", 160), ("Games", 70), ("Wins", 70), 
                   ("Win %", 80), ("Points", 80), ("Avg Pts", 80), ("Golden", 70)]
        
        for text, width in headers:
            ctk.CTkLabel(
                headers_frame,
                text=text,
                font=get_font(13, "bold"),
                width=width,
                anchor="center"
            ).pack(side="left", padx=3, pady=10)
        
        self.rows_container = ctk.CTkFrame(self.board_frame, fg_color="transparent")
        self.rows_container.pack(fill="both", expand=True)
    
    def load_leaderboard(self):
        for widget in self.rows_container.winfo_children():
            widget.destroy()
        
        players = self.db.get_leaderboard(self.sort_var.get())
        
        if not players:
            empty_frame = ctk.CTkFrame(self.rows_container, fg_color="transparent")
            empty_frame.pack(expand=True, pady=50)
            
            ctk.CTkLabel(
                empty_frame,
                text="🏆",
                font=get_font(48)
            ).pack()
            
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
        
        # Show top 3 podium if we have enough players with games
        players_with_games = [p for p in players if p.games_played > 0]
        if len(players_with_games) >= 3:
            self._create_podium(players_with_games[:3])
        
        for i, player in enumerate(players, 1):
            self.create_row(i, player)
    
    def _create_podium(self, top_3):
        """Create an animated podium for top 3 players."""
        podium_frame = ctk.CTkFrame(self.rows_container, fg_color="#1a1a2e")
        podium_frame.pack(fill="x", padx=5, pady=(10, 20))
        
        # Inner frame to center the podium content
        inner = ctk.CTkFrame(podium_frame, fg_color="transparent")
        inner.pack(pady=15)
        
        # Container that uses grid for proper alignment at bottom
        grid_container = ctk.CTkFrame(inner, fg_color="transparent")
        grid_container.pack()
        
        # Arrange: 2nd, 1st, 3rd (columns 0, 1, 2)
        positions = [
            (top_3[1], 2, "#4a4a4a", 90, "🥈", 0),   # Silver - left
            (top_3[0], 1, "#5c4d1a", 120, "🥇", 1),  # Gold - center
            (top_3[2], 3, "#4a3020", 70, "🥉", 2),   # Bronze - right
        ]
        
        for player, rank, color, height, medal, col in positions:
            # Podium stand
            stand = ctk.CTkFrame(grid_container, fg_color=color, corner_radius=10, 
                               width=120, height=height)
            stand.grid(row=0, column=col, padx=10, sticky="s")
            stand.grid_propagate(False)
            
            # Content inside stand
            content = ctk.CTkFrame(stand, fg_color="transparent")
            content.pack(expand=True, fill="both", pady=8)
            
            # Medal
            ctk.CTkLabel(
                content,
                text=medal,
                font=get_font(24)
            ).pack()
            
            # Profile picture
            try:
                pic = ProfilePicture(
                    content, size=40,
                    image_path=player.profile_picture,
                    player_name=player.name
                )
                pic.pack(pady=3)
            except:
                pass
            
            # Name
            name = player.name
            if len(name) > 10:
                name = name[:8] + "..."
            ctk.CTkLabel(
                content,
                text=name,
                font=get_font(11, "bold")
            ).pack()
    
    def create_row(self, rank: int, player):
        # Determine row color based on rank
        if rank == 1:
            bg_color = "#5c4d1a"  # Gold tint
            rank_text = "🥇"
        elif rank == 2:
            bg_color = "#4a4a4a"  # Silver tint
            rank_text = "🥈"
        elif rank == 3:
            bg_color = "#4a3020"  # Bronze tint
            rank_text = "🥉"
        else:
            bg_color = "#252540"
            rank_text = str(rank)
        
        # Use simple CTkFrame instead of AnimatedCard for better scroll performance
        row = ctk.CTkFrame(
            self.rows_container, 
            fg_color=bg_color, 
            corner_radius=8, 
            height=60
        )
        row.pack(fill="x", padx=5, pady=3)
        row.pack_propagate(False)
        
        # Rank
        ctk.CTkLabel(
            row, text=rank_text,
            font=get_font(16 if rank <= 3 else 14, "bold"),
            width=60, anchor="center"
        ).pack(side="left", padx=3, pady=10)
        
        # Profile picture
        pic_frame = ctk.CTkFrame(row, fg_color="transparent", width=55)
        pic_frame.pack(side="left", padx=3)
        pic_frame.pack_propagate(False)
        
        try:
            pic = ProfilePicture(
                pic_frame, size=40,
                image_path=player.profile_picture,
                player_name=player.name
            )
            pic.pack(expand=True)
        except:
            pass
        
        # Name
        ctk.CTkLabel(
            row, text=player.name,
            font=get_font(15, "bold"),
            width=160, anchor="w"
        ).pack(side="left", padx=3)
        
        # Games
        ctk.CTkLabel(
            row, text=str(player.games_played),
            font=get_font(14),
            width=70, anchor="center"
        ).pack(side="left", padx=3)
        
        # Wins
        ctk.CTkLabel(
            row, text=str(player.games_won),
            font=get_font(14, "bold"),
            text_color="#4CAF50",
            width=70, anchor="center"
        ).pack(side="left", padx=3)
        
        # Win %
        win_color = "#4CAF50" if player.win_rate >= 50 else "#ff6b6b"
        
        # Win rate with progress bar style
        win_frame = ctk.CTkFrame(row, fg_color="transparent", width=80)
        win_frame.pack(side="left", padx=3)
        
        ctk.CTkLabel(
            win_frame, text=f"{player.win_rate:.1f}%",
            font=get_font(14, "bold"),
            text_color=win_color
        ).pack()
        
        # Mini progress bar
        progress_bg = ctk.CTkFrame(win_frame, fg_color="#333333", height=4, corner_radius=2)
        progress_bg.pack(fill="x", pady=2)
        
        progress_fill = ctk.CTkFrame(
            progress_bg, 
            fg_color=win_color, 
            height=4, 
            corner_radius=2,
            width=int(60 * (player.win_rate / 100))
        )
        progress_fill.place(x=0, y=0)
        
        # Total Points
        ctk.CTkLabel(
            row, text=str(player.total_points),
            font=get_font(14),
            text_color="#64B5F6",
            width=80, anchor="center"
        ).pack(side="left", padx=3)
        
        # Avg Points
        ctk.CTkLabel(
            row, text=f"{player.avg_points:.1f}",
            font=get_font(14),
            width=80, anchor="center"
        ).pack(side="left", padx=3)
        
        # Golden Breaks
        golden_text = f"⭐{player.golden_breaks}" if player.golden_breaks > 0 else "-"
        ctk.CTkLabel(
            row, text=golden_text,
            font=get_font(14),
            text_color="#ffd700" if player.golden_breaks > 0 else "#666666",
            width=70, anchor="center"
        ).pack(side="left", padx=3)
    
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
