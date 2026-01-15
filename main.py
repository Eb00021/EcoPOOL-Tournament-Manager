"""
EcoPOOL League Manager
A comprehensive pool league management application for the WVU EcoCAR team.

Features:
- Player Management with statistics tracking and profile pictures
- Random partner and match generation
- Tournament bracket generation for end-of-semester finals
- Interactive scorecard with pool table visualization
- Match history and leaderboard with animations
- Pool table tracking for the venue
- Export to PDF and CSV
- Cool animations and celebration effects

Run with: python main.py
"""

import customtkinter as ctk
from tkinter import messagebox, filedialog
import sys
import os

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fonts import load_custom_font, get_font, get_font_family

from database import DatabaseManager
from exporter import Exporter
from views.players_view import PlayersView
from views.match_generator_view import MatchGeneratorView
from views.scorecard_view import ScorecardView
from views.leaderboard_view import LeaderboardView
from views.history_view import HistoryView
from views.table_tracker_view import TableTrackerView
from views.bracket_view import BracketView
from animations import AnimatedCard, AnimatedButton, show_celebration


class EcoPoolApp(ctk.CTk):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        
        # Load custom font (must be done early)
        load_custom_font()
        
        # Configure appearance
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")
        
        # Window setup
        self.title("EcoPOOL League Manager")
        self.geometry("1400x900")
        self.minsize(1200, 700)
        
        # Initialize database
        self.db = DatabaseManager()
        self.exporter = Exporter(self.db)
        
        # Track current view
        self.current_view = None
        self.views = {}
        
        # Setup UI
        self.setup_ui()
        
        # Show home by default
        self.show_view("home")
        
        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self.on_close)
    
    def setup_ui(self):
        """Setup the main UI layout."""
        
        # Configure grid
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # === SIDEBAR ===
        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0, fg_color="#0d1117")
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        
        # Logo/Title
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.pack(fill="x", padx=20, pady=25)
        
        ctk.CTkLabel(
            logo_frame,
            text="🎱",
            font=get_font(42)
        ).pack()
        
        ctk.CTkLabel(
            logo_frame,
            text="EcoPOOL",
            font=get_font(28, "bold"),
            text_color="#4CAF50"
        ).pack()
        
        ctk.CTkLabel(
            logo_frame,
            text="League Manager",
            font=get_font(14),
            text_color="#888888"
        ).pack()
        
        # Navigation buttons
        self.nav_buttons = {}
        
        nav_items = [
            ("home", "🏠 Dashboard", self.show_home),
            ("players", "👥 Players", lambda: self.show_view("players")),
            ("generator", "🎲 Match Generator", lambda: self.show_view("generator")),
            ("scorecard", "🎯 Scorecard", lambda: self.show_view("scorecard")),
            ("bracket", "🏆 Tournament", lambda: self.show_view("bracket")),
            ("tables", "🎱 Table Tracker", lambda: self.show_view("tables")),
            ("history", "📜 Match History", lambda: self.show_view("history")),
            ("leaderboard", "📊 Leaderboard", lambda: self.show_view("leaderboard")),
        ]
        
        nav_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        nav_frame.pack(fill="x", padx=15, pady=10)
        
        for key, text, command in nav_items:
            btn = ctk.CTkButton(
                nav_frame,
                text=text,
                font=get_font(15),
                height=45,
                anchor="w",
                fg_color="transparent",
                hover_color="#1e3a1e",
                text_color="#cccccc",
                command=command
            )
            btn.pack(fill="x", pady=3)
            self.nav_buttons[key] = btn
        
        # Separator
        ctk.CTkFrame(self.sidebar, height=2, fg_color="#333333").pack(fill="x", padx=20, pady=20)
        
        # Quick stats
        stats_frame = ctk.CTkFrame(self.sidebar, fg_color="#161b22", corner_radius=10)
        stats_frame.pack(fill="x", padx=15, pady=10)
        
        ctk.CTkLabel(
            stats_frame,
            text="Quick Stats",
            font=get_font(14, "bold"),
            text_color="#888888"
        ).pack(pady=(10, 5))
        
        self.stats_players_label = ctk.CTkLabel(
            stats_frame,
            text="Players: 0",
            font=get_font(13)
        )
        self.stats_players_label.pack(pady=2)
        
        self.stats_matches_label = ctk.CTkLabel(
            stats_frame,
            text="Matches: 0",
            font=get_font(13)
        )
        self.stats_matches_label.pack(pady=2)
        
        self.stats_active_label = ctk.CTkLabel(
            stats_frame,
            text="Active: 0",
            font=get_font(13),
            text_color="#4CAF50"
        )
        self.stats_active_label.pack(pady=(2, 10))
        
        # Separator
        ctk.CTkFrame(self.sidebar, height=2, fg_color="#333333").pack(fill="x", padx=20, pady=10)
        
        # Data Management section
        data_frame = ctk.CTkFrame(self.sidebar, fg_color="#161b22", corner_radius=10)
        data_frame.pack(fill="x", padx=15, pady=5)
        
        ctk.CTkLabel(
            data_frame,
            text="Data Management",
            font=get_font(14, "bold"),
            text_color="#888888"
        ).pack(pady=(10, 5))
        
        ctk.CTkButton(
            data_frame,
            text="🆕 New Pool Night",
            font=get_font(12),
            height=32,
            fg_color="#c44536",
            hover_color="#a43526",
            command=self.new_pool_night
        ).pack(fill="x", padx=10, pady=3)
        
        ctk.CTkButton(
            data_frame,
            text="💾 Save Matches",
            font=get_font(12),
            height=32,
            fg_color="#3d5a80",
            hover_color="#2d4a70",
            command=self.save_matches
        ).pack(fill="x", padx=10, pady=3)
        
        ctk.CTkButton(
            data_frame,
            text="📂 Load Matches",
            font=get_font(12),
            height=32,
            fg_color="#3d5a80",
            hover_color="#2d4a70",
            command=self.load_matches
        ).pack(fill="x", padx=10, pady=3)
        
        ctk.CTkButton(
            data_frame,
            text="👥 Export Players",
            font=get_font(12),
            height=32,
            fg_color="#6b4e8a",
            hover_color="#5b3e7a",
            command=self.export_players
        ).pack(fill="x", padx=10, pady=3)
        
        ctk.CTkButton(
            data_frame,
            text="👥 Import Players",
            font=get_font(12),
            height=32,
            fg_color="#6b4e8a",
            hover_color="#5b3e7a",
            command=self.import_players
        ).pack(fill="x", padx=10, pady=(3, 10))
        
        # Version info at bottom
        ctk.CTkLabel(
            self.sidebar,
            text="v2.0 - WVU EcoCAR",
            font=get_font(11),
            text_color="#555555"
        ).pack(side="bottom", pady=15)
        
        # === MAIN CONTENT AREA ===
        self.main_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="#161b22")
        self.main_frame.grid(row=0, column=1, sticky="nsew")
        
        # Content container
        self.content = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.content.pack(fill="both", expand=True)
    
    def update_quick_stats(self):
        """Update the quick stats in sidebar."""
        players = self.db.get_all_players()
        matches = self.db.get_all_matches(limit=1000)
        active = [m for m in matches if not m['is_complete']]
        
        self.stats_players_label.configure(text=f"Players: {len(players)}")
        self.stats_matches_label.configure(text=f"Matches: {len(matches)}")
        self.stats_active_label.configure(text=f"Active: {len(active)}")
    
    def set_active_nav(self, key: str):
        """Highlight the active navigation button."""
        for nav_key, btn in self.nav_buttons.items():
            if nav_key == key:
                btn.configure(fg_color="#1e3a1e", text_color="#4CAF50")
            else:
                btn.configure(fg_color="transparent", text_color="#cccccc")
    
    def clear_content(self):
        """Clear the content area."""
        for widget in self.content.winfo_children():
            widget.destroy()
        self.current_view = None
    
    def show_home(self):
        """Show the home dashboard."""
        self.clear_content()
        self.set_active_nav("home")
        self.update_quick_stats()
        
        # Dashboard content
        dashboard = ctk.CTkFrame(self.content, fg_color="transparent")
        dashboard.pack(fill="both", expand=True, padx=30, pady=30)
        
        # Welcome header
        ctk.CTkLabel(
            dashboard,
            text="Welcome to EcoPOOL League Manager",
            font=get_font(32, "bold")
        ).pack(anchor="w", pady=(0, 5))
        
        ctk.CTkLabel(
            dashboard,
            text="WVU EcoCAR Pool League - Thursday Nights at The Met Pool Hall",
            font=get_font(16),
            text_color="#888888"
        ).pack(anchor="w", pady=(0, 30))
        
        # Quick action cards with hover animations
        cards_frame = ctk.CTkFrame(dashboard, fg_color="transparent")
        cards_frame.pack(fill="x", pady=10)
        
        cards = [
            ("🎲", "Generate Matches", "Create random team pairings\nfor league night", "generator", "#2d7a3e"),
            ("🎯", "Open Scorecard", "Track scores with\ninteractive pool table", "scorecard", "#1e5a8a"),
            ("🏆", "Tournament", "Create end-of-semester\nbrackets & playoffs", "bracket", "#8a3d3d"),
            ("👥", "Manage Players", "Add, edit, or view\nplayer statistics", "players", "#6b4e8a"),
            ("📊", "Leaderboard", "Check rankings and\nexport reports", "leaderboard", "#8a6b3d"),
        ]
        
        for emoji, title, desc, view_key, color in cards:
            card = AnimatedCard(cards_frame, fg_color=color, corner_radius=15, width=210, height=170)
            card.pack(side="left", padx=8, pady=10)
            card.pack_propagate(False)
            
            ctk.CTkLabel(card, text=emoji, font=get_font(36)).pack(pady=(20, 8))
            ctk.CTkLabel(card, text=title, font=get_font(16, "bold")).pack()
            ctk.CTkLabel(card, text=desc, font=get_font(11), 
                        text_color="#dddddd", justify="center").pack(pady=5)
            
            # Make card clickable with cursor change
            card.configure(cursor="hand2")
            card.bind("<Button-1>", lambda e, v=view_key: self.show_view(v))
            for child in card.winfo_children():
                child.configure(cursor="hand2")
                child.bind("<Button-1>", lambda e, v=view_key: self.show_view(v))
        
        # Recent activity
        activity_frame = ctk.CTkFrame(dashboard, fg_color="#1a1a2e", corner_radius=15)
        activity_frame.pack(fill="both", expand=True, pady=20)
        
        ctk.CTkLabel(
            activity_frame,
            text="📜 Recent Matches",
            font=get_font(20, "bold")
        ).pack(anchor="w", padx=20, pady=15)
        
        matches = self.db.get_all_matches(limit=5)
        
        if matches:
            for match in matches:
                self.create_match_preview(activity_frame, match)
        else:
            ctk.CTkLabel(
                activity_frame,
                text="No matches yet. Use Match Generator to create your first match!",
                font=get_font(14),
                text_color="#666666"
            ).pack(pady=30)
        
        # Rules quick reference
        rules_frame = ctk.CTkFrame(dashboard, fg_color="#252540", corner_radius=15)
        rules_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(
            rules_frame,
            text="📋 Quick Rules Reference",
            font=get_font(16, "bold")
        ).pack(anchor="w", padx=20, pady=(15, 10))
        
        rules_text = (
            "• 2v2 8-ball matches, Best of 3 games\n"
            "• Regular balls: 1 point each | 8-ball: 3 points | Max: 10 points per team\n"
            "• Golden Break (8 on break): 17 points to breaking team\n"
            "• Early 8-ball foul: Opposing team gets 10 points"
        )
        
        ctk.CTkLabel(
            rules_frame,
            text=rules_text,
            font=get_font(13),
            text_color="#aaaaaa",
            justify="left"
        ).pack(anchor="w", padx=20, pady=(0, 15))
    
    def create_match_preview(self, parent, match):
        """Create a match preview row."""
        row = ctk.CTkFrame(parent, fg_color="#252540", corner_radius=8, height=50)
        row.pack(fill="x", padx=15, pady=3)
        row.pack_propagate(False)
        
        # Status
        status = "✅" if match['is_complete'] else "🔴"
        ctk.CTkLabel(row, text=status, font=get_font(14)).pack(side="left", padx=15, pady=10)
        
        # Teams
        team1 = match['team1_p1_name'] or "Unknown"
        if match['team1_p2_name']:
            team1 += f" & {match['team1_p2_name']}"
        
        team2 = match['team2_p1_name'] or "Unknown"
        if match['team2_p2_name']:
            team2 += f" & {match['team2_p2_name']}"
        
        ctk.CTkLabel(
            row, text=f"{team1}  vs  {team2}",
            font=get_font(14)
        ).pack(side="left", padx=10)
        
        # Table
        ctk.CTkLabel(
            row, text=f"Table {match['table_number']}",
            font=get_font(12),
            text_color="#888888"
        ).pack(side="right", padx=15)
    
    def show_view(self, view_name: str):
        """Show a specific view with smooth transition."""
        self.clear_content()
        self.set_active_nav(view_name)
        self.update_quick_stats()
        
        if view_name == "home":
            self.show_home()
        elif view_name == "players":
            view = PlayersView(self.content, self.db)
            view.pack(fill="both", expand=True)
        elif view_name == "generator":
            view = MatchGeneratorView(self.content, self.db, 
                                     on_match_created=self.update_quick_stats)
            view.pack(fill="both", expand=True)
        elif view_name == "scorecard":
            view = ScorecardView(self.content, self.db)
            view.pack(fill="both", expand=True)
        elif view_name == "bracket":
            view = BracketView(self.content, self.db)
            view.pack(fill="both", expand=True)
        elif view_name == "tables":
            view = TableTrackerView(self.content, self.db, 
                                   on_match_click=self.go_to_scorecard)
            view.pack(fill="both", expand=True)
        elif view_name == "history":
            view = HistoryView(self.content, self.db)
            view.pack(fill="both", expand=True)
        elif view_name == "leaderboard":
            view = LeaderboardView(self.content, self.db)
            view.pack(fill="both", expand=True)
    
    def new_pool_night(self):
        """Start a new pool night - clears all matches but keeps players."""
        if messagebox.askyesno(
            "New Pool Night",
            "This will DELETE all current matches and games.\n\n"
            "Players will be kept.\n\n"
            "Do you want to save the current match history first?",
            icon="warning"
        ):
            # Offer to save first
            self.save_matches()
        
        if messagebox.askyesno(
            "Confirm New Pool Night",
            "Are you sure you want to clear all matches?\n\nThis cannot be undone.",
            icon="warning"
        ):
            self.db.clear_matches()
            self.update_quick_stats()
            self.show_home()
            messagebox.showinfo("Success", "New pool night started!\nAll matches have been cleared.")
    
    def save_matches(self):
        """Save match history to JSON file."""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            title="Save Match History",
            initialfile="ecopool_matches_backup.json"
        )
        
        if filepath:
            if self.exporter.export_matches_json(filepath):
                messagebox.showinfo("Success", f"Match history saved to:\n{filepath}")
            else:
                messagebox.showerror("Error", "Failed to save match history.")
    
    def load_matches(self):
        """Load match history from JSON file."""
        filepath = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json")],
            title="Load Match History"
        )
        
        if filepath:
            success, message = self.exporter.import_matches_json(filepath)
            if success:
                self.update_quick_stats()
                self.show_home()
                messagebox.showinfo("Success", message)
            else:
                messagebox.showerror("Error", message)
    
    def export_players(self):
        """Export player database to JSON file."""
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            title="Export Players",
            initialfile="ecopool_players.json"
        )
        
        if filepath:
            if self.exporter.export_players_json(filepath):
                messagebox.showinfo("Success", f"Players exported to:\n{filepath}")
            else:
                messagebox.showerror("Error", "Failed to export players.")
    
    def import_players(self):
        """Import players from JSON file."""
        filepath = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json")],
            title="Import Players"
        )
        
        if filepath:
            success, message = self.exporter.import_players_json(filepath)
            if success:
                self.update_quick_stats()
                self.show_home()
                messagebox.showinfo("Success", message)
            else:
                messagebox.showerror("Error", message)
    
    def go_to_scorecard(self, match_id: int):
        """Navigate to scorecard with a specific match selected."""
        self.clear_content()
        self.set_active_nav("scorecard")
        self.update_quick_stats()
        
        view = ScorecardView(self.content, self.db)
        view.pack(fill="both", expand=True)
        
        # Select the match in the scorecard
        view.select_match_by_id(match_id)
    
    def on_close(self):
        """Handle application close."""
        self.db.close()
        self.destroy()


def main():
    """Main entry point."""
    app = EcoPoolApp()
    app.mainloop()


if __name__ == "__main__":
    main()
