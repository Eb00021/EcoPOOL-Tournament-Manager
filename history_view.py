"""
EcoPOOL League - Match History View
"""

import customtkinter as ctk
from tkinter import messagebox, filedialog
from database import DatabaseManager
from exporter import Exporter
from fonts import get_font


class HistoryView(ctk.CTkFrame):
    def __init__(self, parent, db: DatabaseManager, on_view_match=None):
        super().__init__(parent, fg_color="transparent")
        self.db = db
        self.exporter = Exporter(db)
        self.on_view_match = on_view_match
        self._games_cache = {}  # Cache for batch-loaded games
        
        self.setup_ui()
        self.load_history()
    
    def setup_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))
        
        ctk.CTkLabel(
            header, 
            text="📜 Match History",
            font=get_font(28, "bold")
        ).pack(side="left")
        
        # Export buttons
        ctk.CTkButton(
            header,
            text="📄 Export PDF",
            font=get_font(14),
            fg_color="#8a4a6b",
            hover_color="#6a3a5b",
            height=40,
            command=self.export_pdf
        ).pack(side="right", padx=5)
        
        ctk.CTkButton(
            header,
            text="📊 Export CSV",
            font=get_font(14),
            fg_color="#3d5a80",
            hover_color="#2d4a70",
            height=40,
            command=self.export_csv
        ).pack(side="right", padx=5)
        
        # Filter options
        filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        filter_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(
            filter_frame, text="Show:",
            font=get_font(14)
        ).pack(side="left", padx=(0, 10))
        
        self.filter_var = ctk.StringVar(value="all")
        
        for text, value in [("All", "all"), ("Complete", "complete"), 
                            ("In Progress", "active"), ("Finals", "finals")]:
            ctk.CTkRadioButton(
                filter_frame, text=text, variable=self.filter_var, value=value,
                font=get_font(13),
                fg_color="#2d7a3e", hover_color="#1a5f2a",
                command=self.load_history
            ).pack(side="left", padx=15)
        
        # History container
        self.history_frame = ctk.CTkScrollableFrame(
            self, fg_color="#1a1a2e", corner_radius=15
        )
        self.history_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Headers
        headers_frame = ctk.CTkFrame(self.history_frame, fg_color="#2d2d44", corner_radius=10)
        headers_frame.pack(fill="x", padx=5, pady=(5, 10))
        
        headers = [("Status", 80), ("Type", 60), ("Date", 100), ("Team 1", 180), 
                   ("Team 2", 180), ("Score", 80), ("Actions", 120)]
        
        for text, width in headers:
            ctk.CTkLabel(
                headers_frame,
                text=text,
                font=get_font(12, "bold"),
                width=width,
                anchor="center"
            ).pack(side="left", padx=3, pady=10)
        
        self.rows_container = ctk.CTkFrame(self.history_frame, fg_color="transparent")
        self.rows_container.pack(fill="both", expand=True)
    
    def load_history(self):
        for widget in self.rows_container.winfo_children():
            widget.destroy()
        
        matches = self.db.get_all_matches(limit=100)
        filter_val = self.filter_var.get()
        
        filtered = []
        for match in matches:
            if filter_val == "all":
                filtered.append(match)
            elif filter_val == "complete" and match['is_complete']:
                filtered.append(match)
            elif filter_val == "active" and not match['is_complete']:
                filtered.append(match)
            elif filter_val == "finals" and match['is_finals']:
                filtered.append(match)
        
        if not filtered:
            ctk.CTkLabel(
                self.rows_container,
                text="No matches found.",
                font=get_font(16),
                text_color="#888888"
            ).pack(pady=50)
            return
        
        # Batch load all games for filtered matches (optimization)
        match_ids = [m['id'] for m in filtered]
        self._games_cache = self.db.get_games_for_matches(match_ids)
        
        for match in filtered:
            self.create_row(match)
    
    def create_row(self, match):
        bg_color = "#1e4a1e" if match['is_complete'] else "#252540"
        if match['is_finals']:
            bg_color = "#4a3020"
        
        row = ctk.CTkFrame(self.rows_container, fg_color=bg_color, corner_radius=8, height=55)
        row.pack(fill="x", padx=5, pady=3)
        row.pack_propagate(False)
        
        # Status
        status = "✅" if match['is_complete'] else "🔴"
        ctk.CTkLabel(
            row, text=status,
            font=get_font(16),
            width=80, anchor="center"
        ).pack(side="left", padx=3, pady=10)
        
        # Type
        match_type = "🏆" if match['is_finals'] else "🎱"
        ctk.CTkLabel(
            row, text=match_type,
            font=get_font(16),
            width=60, anchor="center"
        ).pack(side="left", padx=3)
        
        # Date
        date_str = match['date'][:10] if match['date'] else "N/A"
        ctk.CTkLabel(
            row, text=date_str,
            font=get_font(13),
            width=100, anchor="center"
        ).pack(side="left", padx=3)
        
        # Team 1
        team1 = match['team1_p1_name'] or "Unknown"
        if match['team1_p2_name']:
            team1 += f" & {match['team1_p2_name']}"
        ctk.CTkLabel(
            row, text=team1,
            font=get_font(13),
            text_color="#90EE90",
            width=180, anchor="w"
        ).pack(side="left", padx=3)
        
        # Team 2
        team2 = match['team2_p1_name'] or "Unknown"
        if match['team2_p2_name']:
            team2 += f" & {match['team2_p2_name']}"
        ctk.CTkLabel(
            row, text=team2,
            font=get_font(13),
            text_color="#90CAF9",
            width=180, anchor="w"
        ).pack(side="left", padx=3)
        
        # Score (games won) - use cached games for performance
        games = self._games_cache.get(match['id'], [])
        t1_wins = sum(1 for g in games if g['winner_team'] == 1)
        t2_wins = sum(1 for g in games if g['winner_team'] == 2)
        
        ctk.CTkLabel(
            row, text=f"{t1_wins} - {t2_wins}",
            font=get_font(14, "bold"),
            width=80, anchor="center"
        ).pack(side="left", padx=3)
        
        # Actions
        actions = ctk.CTkFrame(row, fg_color="transparent", width=120)
        actions.pack(side="left", padx=3)
        
        ctk.CTkButton(
            actions, text="📄",
            width=40, height=30,
            fg_color="#3d5a80", hover_color="#2d4a70",
            command=lambda m=match: self.export_match(m)
        ).pack(side="left", padx=2)
        
        ctk.CTkButton(
            actions, text="🗑️",
            width=40, height=30,
            fg_color="#c44536", hover_color="#a43526",
            command=lambda m=match: self.delete_match(m)
        ).pack(side="left", padx=2)
    
    def export_match(self, match):
        filepath = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            title="Export Scorecard",
            initialfile=f"scorecard_match_{match['id']}.pdf"
        )
        
        if filepath:
            if self.exporter.export_scorecard_pdf(match['id'], filepath):
                messagebox.showinfo("Success", f"Scorecard exported to:\n{filepath}")
            else:
                messagebox.showerror("Error", "Failed to export scorecard.")
    
    def delete_match(self, match):
        if messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this match?"):
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM games WHERE match_id = ?", (match['id'],))
            cursor.execute("DELETE FROM matches WHERE id = ?", (match['id'],))
            conn.commit()
            self.load_history()
    
    def export_csv(self):
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            title="Export Matches",
            initialfile="ecopool_matches.csv"
        )
        
        if filepath:
            if self.exporter.export_matches_csv(filepath):
                messagebox.showinfo("Success", f"Matches exported to:\n{filepath}")
            else:
                messagebox.showerror("Error", "Failed to export matches.")
    
    def export_pdf(self):
        filepath = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            title="Export Match History",
            initialfile="ecopool_match_history.pdf"
        )
        
        if filepath:
            if self.exporter.export_match_history_pdf(filepath):
                messagebox.showinfo("Success", f"Match history exported to:\n{filepath}")
            else:
                messagebox.showerror("Error", "Failed to export match history.")
