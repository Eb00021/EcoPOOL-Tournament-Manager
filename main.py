"""
EcoPOOL League Manager
A comprehensive pool league management application for the WVU EcoCAR team.

Features:
- Player Management with statistics tracking and profile pictures
- Random partner and match generation with multi-round scheduling
- Tournament bracket generation for end-of-semester finals
- Interactive scorecard with pool table visualization
- Match history and leaderboard with animations
- Pool table tracking for the venue
- Live scores web server with Server-Sent Events (SSE)
- Achievements system with tier-based badges
- Advanced statistics (head-to-head, form, predictions)
- Venmo payment integration for buy-ins
- Settings and theme customization
- Export to PDF, CSV, and JSON
- Cool animations and celebration effects

Run with: python main.py
"""

import customtkinter as ctk
from tkinter import messagebox, filedialog
import sys
import os
import io
import webbrowser

try:
    import qrcode
    from PIL import Image
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

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
from views.stats_view import StatsView
from views.achievements_view import AchievementsView
from views.payments_view import PaymentsView
from views.settings_view import SettingsView
from achievements import AchievementManager
from animations import AnimatedCard, AnimatedButton, show_celebration
from web_server import LiveScoreServer


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
        
        # Initialize achievement manager
        self.achievement_mgr = AchievementManager(self.db)
        
        # Initialize web server for live scores
        self.web_server = LiveScoreServer(self.db)
        
        # Track current view
        self.current_view = None
        self.views = {}
        
        # Persist generated pairings across view changes
        self.pending_pairings = None
        self.pending_pairings_multi_round = False
        
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
        
        # Logo/Title (fixed at top)
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.pack(fill="x", padx=10, pady=(15, 10))

        # Load and display logo image
        logo_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logo.png")
        if os.path.exists(logo_path):
            try:
                logo_img = Image.open(logo_path)
                # Scale to fit sidebar width (about 200px wide)
                aspect = logo_img.width / logo_img.height
                logo_width = 200
                logo_height = int(logo_width / aspect)
                logo_ctk = ctk.CTkImage(light_image=logo_img, dark_image=logo_img, size=(logo_width, logo_height))
                ctk.CTkLabel(logo_frame, image=logo_ctk, text="").pack()
            except Exception:
                # Fallback to text if image fails
                ctk.CTkLabel(logo_frame, text="EcoPOOL", font=get_font(22, "bold"), text_color="#EAAA00").pack()
        else:
            ctk.CTkLabel(logo_frame, text="EcoPOOL", font=get_font(22, "bold"), text_color="#EAAA00").pack()

        ctk.CTkLabel(
            logo_frame,
            text="League Manager",
            font=get_font(11),
            text_color="#888888"
        ).pack()
        
        # Scrollable content area for navigation and data management
        sidebar_scroll = ctk.CTkScrollableFrame(
            self.sidebar, 
            fg_color="transparent",
            scrollbar_button_color="#333333",
            scrollbar_button_hover_color="#444444"
        )
        sidebar_scroll.pack(fill="both", expand=True, padx=0, pady=0)
        
        # Navigation buttons
        self.nav_buttons = {}
        
        nav_items = [
            ("home", "Dashboard", self.show_home),
            ("players", "Players", lambda: self.show_view("players")),
            ("generator", "Match Generator", lambda: self.show_view("generator")),
            ("scorecard", "Scorecard", lambda: self.show_view("scorecard")),
            ("bracket", "Tournament", lambda: self.show_view("bracket")),
            ("tables", "Table Tracker", lambda: self.show_view("tables")),
            ("history", "Match History", lambda: self.show_view("history")),
            ("leaderboard", "Leaderboard", lambda: self.show_view("leaderboard")),
            ("stats", "Advanced Stats", lambda: self.show_view("stats")),
            ("achievements", "Achievements", lambda: self.show_view("achievements")),
            ("payments", "Payments", lambda: self.show_view("payments")),
            ("settings", "Settings", lambda: self.show_view("settings")),
        ]
        
        nav_frame = ctk.CTkFrame(sidebar_scroll, fg_color="transparent")
        nav_frame.pack(fill="x", padx=10, pady=(5, 10))
        
        for key, text, command in nav_items:
            btn = ctk.CTkButton(
                nav_frame,
                text=text,
                font=get_font(14),
                height=40,
                anchor="w",
                fg_color="transparent",
                hover_color="#1e3a1e",
                text_color="#cccccc",
                command=command
            )
            btn.pack(fill="x", pady=2)
            self.nav_buttons[key] = btn
        
        # Separator
        ctk.CTkFrame(sidebar_scroll, height=2, fg_color="#333333").pack(fill="x", padx=15, pady=10)
        
        # Live Scores Web Server section (moved up)
        web_frame = ctk.CTkFrame(sidebar_scroll, fg_color="#161b22", corner_radius=10)
        web_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(
            web_frame,
            text="Live Scores Server",
            font=get_font(13, "bold"),
            text_color="#888888"
        ).pack(pady=(8, 5))
        
        ctk.CTkLabel(
            web_frame,
            text="Share scores to mobile devices",
            font=get_font(10),
            text_color="#666666"
        ).pack(pady=(0, 5))
        
        self.web_server_btn = ctk.CTkButton(
            web_frame,
            text="Start Server",
            font=get_font(11),
            height=30,
            fg_color="#2d7a3e",
            hover_color="#1a5f2a",
            command=self.toggle_web_server
        )
        self.web_server_btn.pack(fill="x", padx=8, pady=2)
        
        self.qr_code_btn = ctk.CTkButton(
            web_frame,
            text="Show QR Code",
            font=get_font(11),
            height=30,
            fg_color="#3d5a80",
            hover_color="#2d4a70",
            command=self.show_qr_code,
            state="disabled"
        )
        self.qr_code_btn.pack(fill="x", padx=8, pady=2)
        
        self.web_server_status = ctk.CTkLabel(
            web_frame,
            text="Server stopped",
            font=get_font(10),
            text_color="#666666"
        )
        self.web_server_status.pack(pady=(2, 8))
        
        # Separator
        ctk.CTkFrame(sidebar_scroll, height=2, fg_color="#333333").pack(fill="x", padx=15, pady=10)
        
        # Quick stats (compact)
        stats_frame = ctk.CTkFrame(sidebar_scroll, fg_color="#161b22", corner_radius=10)
        stats_frame.pack(fill="x", padx=10, pady=5)
        
        ctk.CTkLabel(
            stats_frame,
            text="Quick Stats",
            font=get_font(11, "bold"),
            text_color="#888888"
        ).pack(pady=(8, 5))
        
        stats_inner = ctk.CTkFrame(stats_frame, fg_color="transparent")
        stats_inner.pack(fill="x", padx=10, pady=(0, 8))
        
        self.stats_players_label = ctk.CTkLabel(
            stats_inner,
            text="Players: 0",
            font=get_font(11)
        )
        self.stats_players_label.pack(side="left", padx=5)
        
        self.stats_matches_label = ctk.CTkLabel(
            stats_inner,
            text="Matches: 0",
            font=get_font(11)
        )
        self.stats_matches_label.pack(side="left", padx=5)
        
        self.stats_active_label = ctk.CTkLabel(
            stats_inner,
            text="Live: 0",
            font=get_font(11),
            text_color="#4CAF50"
        )
        self.stats_active_label.pack(side="left", padx=5)
        
        # Version info at bottom (fixed)
        ctk.CTkLabel(
            self.sidebar,
            text="v3.0 - WVU EcoCAR",
            font=get_font(10),
            text_color="#555555"
        ).pack(side="bottom", pady=8)
        
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
        self.stats_active_label.configure(text=f"Live: {len(active)}")
    
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
            ("Generate Matches", "Create random team pairings\nfor league night", "generator", "#2d7a3e"),
            ("Open Scorecard", "Track scores with\ninteractive pool table", "scorecard", "#1e5a8a"),
            ("Tournament", "Create end-of-semester\nbrackets & playoffs", "bracket", "#8a3d3d"),
            ("Manage Players", "Add, edit, or view\nplayer statistics", "players", "#6b4e8a"),
            ("Leaderboard", "Check rankings and\nexport reports", "leaderboard", "#8a6b3d"),
        ]
        
        for title, desc, view_key, color in cards:
            card = AnimatedCard(cards_frame, fg_color=color, corner_radius=15, width=210, height=140)
            card.pack(side="left", padx=8, pady=10)
            card.pack_propagate(False)
            
            ctk.CTkLabel(card, text=title, font=get_font(16, "bold")).pack(pady=(25, 8))
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
            text="Recent Matches",
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
            text="Quick Rules Reference",
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
        
        # Status indicator (colored dot)
        status_color = "#4CAF50" if match['is_complete'] else "#f44336"
        status_frame = ctk.CTkFrame(row, fg_color=status_color, corner_radius=6, width=12, height=12)
        status_frame.pack(side="left", padx=15, pady=10)
        status_frame.pack_propagate(False)
        
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
            view = PlayersView(self.content, self.db, on_player_change=self.notify_scores_updated)
            view.pack(fill="both", expand=True)
        elif view_name == "generator":
            view = MatchGeneratorView(
                self.content, self.db, 
                on_match_created=self.on_matches_created,
                on_pairings_changed=self.on_pairings_changed,
                initial_pairings=self.pending_pairings,
                initial_multi_round=self.pending_pairings_multi_round
            )
            view.pack(fill="both", expand=True)
        elif view_name == "scorecard":
            view = ScorecardView(self.content, self.db, on_score_change=self.notify_scores_updated,
                                achievement_mgr=self.achievement_mgr)
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
        elif view_name == "stats":
            view = StatsView(self.content, self.db)
            view.pack(fill="both", expand=True)
        elif view_name == "achievements":
            view = AchievementsView(self.content, self.db)
            view.pack(fill="both", expand=True)
        elif view_name == "payments":
            view = PaymentsView(self.content, self.db)
            view.pack(fill="both", expand=True)
        elif view_name == "settings":
            view = SettingsView(
                self.content, self.db,
                exporter=self.exporter,
                on_new_pool_night=self.new_pool_night,
                on_data_change=self.on_settings_data_change
            )
            view.pack(fill="both", expand=True)
    
    def new_pool_night(self):
        """Start a new pool night - clears incomplete matches but keeps completed games for leaderboard."""
        if messagebox.askyesno(
            "New Pool Night",
            "This will clear the current league night setup.\n\n"
            "COMPLETED games will be KEPT for the leaderboard.\n"
            "Only incomplete matches will be removed.\n\n"
            "Do you want to save the current match history first?",
            icon="question"
        ):
            # Offer to save first
            self.save_matches()
        
        if messagebox.askyesno(
            "Confirm New Pool Night",
            "Start a new pool night?\n\n"
            "• Incomplete matches will be cleared\n"
            "• Completed games stay in leaderboard\n"
            "• Players are kept",
            icon="question"
        ):
            # Keep completed matches for leaderboard persistence
            self.db.clear_matches(keep_completed=True)
            # Clear pending pairings
            self.pending_pairings = None
            self.pending_pairings_multi_round = False
            self.update_quick_stats()
            self.show_home()
            messagebox.showinfo(
                "Success", 
                "New pool night started!\n\n"
                "Completed games remain in the leaderboard.\n"
                "Go to Match Generator to set up tonight's games."
            )
    
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
    
    def on_pairings_changed(self, pairings, is_multi_round):
        """Called when generated pairings change in MatchGeneratorView."""
        self.pending_pairings = pairings
        self.pending_pairings_multi_round = is_multi_round
    
    def on_matches_created(self):
        """Called when matches are created from the generator."""
        # Clear pending pairings since they've been saved
        self.pending_pairings = None
        self.pending_pairings_multi_round = False
        self.update_quick_stats()
        # Notify web server of new matches
        self.notify_scores_updated()
    
    def on_settings_data_change(self):
        """Called when data changes from settings (import/load)."""
        self.update_quick_stats()
        self.notify_scores_updated()
    
    def go_to_scorecard(self, match_id: int):
        """Navigate to scorecard with a specific match selected."""
        self.clear_content()
        self.set_active_nav("scorecard")
        self.update_quick_stats()
        
        view = ScorecardView(self.content, self.db, on_score_change=self.notify_scores_updated,
                            achievement_mgr=self.achievement_mgr)
        view.pack(fill="both", expand=True)
        
        # Select the match in the scorecard
        view.select_match_by_id(match_id)
    
    def toggle_web_server(self):
        """Start or stop the live scores web server."""
        if self.web_server.is_running():
            self.web_server.stop()
            self.web_server_btn.configure(
                text="Start Server",
                fg_color="#2d7a3e",
                hover_color="#1a5f2a"
            )
            self.qr_code_btn.configure(state="disabled")
            self.web_server_status.configure(
                text="Server stopped",
                text_color="#666666"
            )
            self._current_server_url = None
        else:
            success, result = self.web_server.start()
            if success:
                self._current_server_url = result
                self.web_server_btn.configure(
                    text="Stop Server",
                    fg_color="#c44536",
                    hover_color="#a43526"
                )
                self.qr_code_btn.configure(state="normal")
                self.web_server_status.configure(
                    text=result,
                    text_color="#4CAF50"
                )
                # Show QR code popup automatically
                self.show_qr_code()
            else:
                messagebox.showerror("Server Error", f"Failed to start server:\n{result}")
    
    def show_qr_code(self):
        """Show a QR code popup for the server URL."""
        if not hasattr(self, '_current_server_url') or not self._current_server_url:
            messagebox.showwarning("Server Not Running", "Start the server first to generate a QR code.")
            return
        
        url = self._current_server_url
        
        # Check if QR code library is available
        if not QR_AVAILABLE:
            messagebox.showinfo(
                "QR Code Not Available",
                f"Install qrcode library to enable QR codes:\n\n"
                f"pip install qrcode[pil]\n\n"
                f"For now, manually enter this URL:\n{url}"
            )
            return
        
        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=2,
        )
        qr.add_data(url)
        qr.make(fit=True)
        
        # Create image (CTkImage will handle resizing)
        qr_image = qr.make_image(fill_color="black", back_color="white").convert('RGB')
        
        # Create popup window
        popup = ctk.CTkToplevel(self)
        popup.title("Scan to Open Live Scores")
        popup.geometry("380x520")
        popup.resizable(False, False)
        popup.transient(self)
        popup.grab_set()
        
        # Center the popup
        popup.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - 190
        y = self.winfo_y() + (self.winfo_height() // 2) - 260
        popup.geometry(f"+{x}+{y}")
        
        # Header
        ctk.CTkLabel(
            popup,
            text="Scan QR Code",
            font=get_font(22, "bold"),
            text_color="#4CAF50"
        ).pack(pady=(20, 5))
        
        ctk.CTkLabel(
            popup,
            text="Open your phone camera and point at the code",
            font=get_font(12),
            text_color="#888888"
        ).pack(pady=(0, 15))
        
        # QR Code frame
        qr_frame = ctk.CTkFrame(popup, fg_color="white", corner_radius=10)
        qr_frame.pack(padx=30, pady=10)
        
        # Convert PIL image to CTkImage for proper HighDPI support
        ctk_image = ctk.CTkImage(light_image=qr_image, dark_image=qr_image, size=(280, 280))
        
        qr_label = ctk.CTkLabel(qr_frame, image=ctk_image, text="")
        qr_label.image = ctk_image  # Keep reference
        qr_label.pack(padx=10, pady=10)
        
        # URL display
        ctk.CTkLabel(
            popup,
            text="Or type this URL:",
            font=get_font(11),
            text_color="#888888"
        ).pack(pady=(15, 5))
        
        url_frame = ctk.CTkFrame(popup, fg_color="#252540", corner_radius=8)
        url_frame.pack(padx=20, fill="x")
        
        url_label = ctk.CTkLabel(
            url_frame,
            text=url,
            font=get_font(14, "bold"),
            text_color="#4CAF50",
            cursor="hand2"
        )
        url_label.pack(pady=10)
        url_label.bind("<Button-1>", lambda e: webbrowser.open(url))
        
        # Close button
        ctk.CTkButton(
            popup,
            text="Close",
            font=get_font(12),
            fg_color="#555555",
            hover_color="#444444",
            height=35,
            width=120,
            command=popup.destroy
        ).pack(pady=20)
    
    def notify_scores_updated(self):
        """Notify the web server that scores have been updated."""
        if self.web_server.is_running():
            self.web_server.notify_update()
    
    def on_close(self):
        """Handle application close."""
        # Stop web server if running
        if self.web_server.is_running():
            self.web_server.stop()
        self.db.close()
        self.destroy()


def main():
    """Main entry point."""
    app = EcoPoolApp()
    app.mainloop()


if __name__ == "__main__":
    main()
