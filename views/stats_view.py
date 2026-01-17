"""
EcoPOOL League - Advanced Statistics View
Displays head-to-head stats, rivalries, predictions, and analytics.
"""

import customtkinter as ctk
from tkinter import Canvas
from typing import Optional
from database import DatabaseManager
from advanced_stats import AdvancedStatsManager, HeadToHeadRecord, PlayerStreak, PlayerForm
from profile_pictures import ProfilePicture
from fonts import get_font


class HeadToHeadCard(ctk.CTkFrame):
    """Card displaying head-to-head record between two players."""

    def __init__(self, parent, h2h: HeadToHeadRecord, **kwargs):
        super().__init__(parent, fg_color='#252540', corner_radius=12, **kwargs)

        self.configure(height=100)
        self.pack_propagate(False)

        # Player 1
        p1_frame = ctk.CTkFrame(self, fg_color='transparent', width=150)
        p1_frame.pack(side='left', padx=15, pady=10)
        p1_frame.pack_propagate(False)

        p1_wins_color = '#4CAF50' if h2h.player1_wins > h2h.player2_wins else '#888888'
        ctk.CTkLabel(
            p1_frame,
            text=h2h.player1_name,
            font=get_font(14, 'bold'),
            text_color=p1_wins_color
        ).pack()

        ctk.CTkLabel(
            p1_frame,
            text=f"{h2h.player1_wins} wins",
            font=get_font(12),
            text_color=p1_wins_color
        ).pack()

        ctk.CTkLabel(
            p1_frame,
            text=f"{h2h.player1_points} pts",
            font=get_font(10),
            text_color='#666666'
        ).pack()

        # VS
        vs_frame = ctk.CTkFrame(self, fg_color='transparent')
        vs_frame.pack(side='left', expand=True)

        ctk.CTkLabel(
            vs_frame,
            text='VS',
            font=get_font(16, 'bold'),
            text_color='#ff6b6b'
        ).pack()

        ctk.CTkLabel(
            vs_frame,
            text=f'{h2h.total_games} games',
            font=get_font(10),
            text_color='#666666'
        ).pack()

        # Player 2
        p2_frame = ctk.CTkFrame(self, fg_color='transparent', width=150)
        p2_frame.pack(side='right', padx=15, pady=10)
        p2_frame.pack_propagate(False)

        p2_wins_color = '#4CAF50' if h2h.player2_wins > h2h.player1_wins else '#888888'
        ctk.CTkLabel(
            p2_frame,
            text=h2h.player2_name,
            font=get_font(14, 'bold'),
            text_color=p2_wins_color
        ).pack()

        ctk.CTkLabel(
            p2_frame,
            text=f"{h2h.player2_wins} wins",
            font=get_font(12),
            text_color=p2_wins_color
        ).pack()

        ctk.CTkLabel(
            p2_frame,
            text=f"{h2h.player2_points} pts",
            font=get_font(10),
            text_color='#666666'
        ).pack()


class PlayerFormCard(ctk.CTkFrame):
    """Card showing player's recent form."""

    def __init__(self, parent, db: DatabaseManager, stats_mgr: AdvancedStatsManager,
                 player_id: int, **kwargs):
        super().__init__(parent, fg_color='#252540', corner_radius=12, **kwargs)

        player = db.get_player(player_id)
        streak = stats_mgr.get_player_streak(player_id)
        form = stats_mgr.get_player_form(player_id)

        if not player:
            return

        self.configure(height=180)
        self.pack_propagate(False)

        # Header
        header = ctk.CTkFrame(self, fg_color='transparent')
        header.pack(fill='x', padx=15, pady=(10, 5))

        # Profile pic
        try:
            pic = ProfilePicture(
                header, size=50,
                image_path=player.profile_picture,
                player_name=player.name
            )
            pic.pack(side='left', padx=(0, 10))
        except:
            pass

        # Name and form
        name_frame = ctk.CTkFrame(header, fg_color='transparent')
        name_frame.pack(side='left', fill='y')

        ctk.CTkLabel(
            name_frame,
            text=player.name,
            font=get_font(16, 'bold')
        ).pack(anchor='w')

        # Form indicator
        form_colors = {'hot': '#ff6b6b', 'cold': '#6b9bff', 'neutral': '#888888'}
        form_emoji = {'hot': '🔥', 'cold': '❄️', 'neutral': '➡️'}

        ctk.CTkLabel(
            name_frame,
            text=f"{form_emoji.get(form.form_trend, '')} {form.form_trend.upper()}",
            font=get_font(12, 'bold'),
            text_color=form_colors.get(form.form_trend, '#888888')
        ).pack(anchor='w')

        # Stats
        stats_frame = ctk.CTkFrame(self, fg_color='transparent')
        stats_frame.pack(fill='x', padx=15, pady=10)

        # Last 5 results
        results_frame = ctk.CTkFrame(stats_frame, fg_color='transparent')
        results_frame.pack(side='left')

        ctk.CTkLabel(
            results_frame,
            text='Last 5:',
            font=get_font(11),
            text_color='#888888'
        ).pack(side='left', padx=(0, 5))

        for result in streak.last_5_results:
            color = '#4CAF50' if result == 'W' else '#ff6b6b'
            ctk.CTkLabel(
                results_frame,
                text=result,
                font=get_font(12, 'bold'),
                text_color=color,
                width=20
            ).pack(side='left')

        # Streak
        if streak.streak_count > 1:
            streak_color = '#4CAF50' if streak.streak_type == 'win' else '#ff6b6b'
            streak_text = f"{'🔥' if streak.streak_type == 'win' else '❄️'} {streak.streak_count} {streak.streak_type} streak"

            ctk.CTkLabel(
                stats_frame,
                text=streak_text,
                font=get_font(12, 'bold'),
                text_color=streak_color
            ).pack(side='right')

        # More stats
        more_stats = ctk.CTkFrame(self, fg_color='#1a1a2e', corner_radius=8)
        more_stats.pack(fill='x', padx=15, pady=5)

        stats_inner = ctk.CTkFrame(more_stats, fg_color='transparent')
        stats_inner.pack(fill='x', padx=10, pady=8)

        # Last 10 win rate
        rate_color = '#4CAF50' if form.last_10_win_rate >= 50 else '#ff6b6b'
        ctk.CTkLabel(
            stats_inner,
            text=f"Last 10: {form.last_10_win_rate:.0f}%",
            font=get_font(11),
            text_color=rate_color
        ).pack(side='left', padx=10)

        # Trend
        trend_text = f"({form.trend_change:+.0f}% vs overall)" if form.trend_change != 0 else "(stable)"
        ctk.CTkLabel(
            stats_inner,
            text=trend_text,
            font=get_font(10),
            text_color='#666666'
        ).pack(side='left')

        # Clutch rating
        ctk.CTkLabel(
            stats_inner,
            text=f"Clutch: {form.clutch_rating:.0f}%",
            font=get_font(11),
            text_color='#FFD700' if form.clutch_rating >= 60 else '#888888'
        ).pack(side='right', padx=10)


class MatchPredictionCard(ctk.CTkFrame):
    """Card showing match outcome prediction."""

    def __init__(self, parent, prediction: dict, **kwargs):
        super().__init__(parent, fg_color='#252540', corner_radius=12, **kwargs)

        self.configure(height=120)
        self.pack_propagate(False)

        # Header
        ctk.CTkLabel(
            self,
            text='🎱 Match Prediction',
            font=get_font(14, 'bold')
        ).pack(pady=(10, 5))

        # Probability bars
        prob_frame = ctk.CTkFrame(self, fg_color='transparent')
        prob_frame.pack(fill='x', padx=20, pady=10)

        p1_prob = prediction['team1_win_probability']
        p2_prob = prediction['team2_win_probability']

        # Team 1
        ctk.CTkLabel(
            prob_frame,
            text=f"Team 1: {p1_prob:.0f}%",
            font=get_font(12, 'bold'),
            text_color='#4CAF50' if p1_prob > 50 else '#888888'
        ).pack(anchor='w')

        bar_frame = ctk.CTkFrame(prob_frame, fg_color='#333333', height=20, corner_radius=5)
        bar_frame.pack(fill='x', pady=2)
        bar_frame.pack_propagate(False)

        p1_fill = ctk.CTkFrame(
            bar_frame,
            fg_color='#4CAF50',
            corner_radius=5,
            width=int(p1_prob * 3)  # Scale to ~300px max
        )
        p1_fill.place(x=0, y=0, relheight=1)

        # Team 2
        ctk.CTkLabel(
            prob_frame,
            text=f"Team 2: {p2_prob:.0f}%",
            font=get_font(12, 'bold'),
            text_color='#ff6b6b' if p2_prob > 50 else '#888888'
        ).pack(anchor='w', pady=(10, 0))

        bar_frame2 = ctk.CTkFrame(prob_frame, fg_color='#333333', height=20, corner_radius=5)
        bar_frame2.pack(fill='x', pady=2)
        bar_frame2.pack_propagate(False)

        p2_fill = ctk.CTkFrame(
            bar_frame2,
            fg_color='#ff6b6b',
            corner_radius=5,
            width=int(p2_prob * 3)
        )
        p2_fill.place(x=0, y=0, relheight=1)

        # Confidence
        conf = prediction['confidence']
        conf_colors = {'high': '#4CAF50', 'medium': '#ff9800', 'low': '#888888'}
        ctk.CTkLabel(
            self,
            text=f"Confidence: {conf.upper()}",
            font=get_font(10),
            text_color=conf_colors.get(conf, '#888888')
        ).pack()


class StatsView(ctk.CTkFrame):
    """Main view for advanced statistics."""

    def __init__(self, parent, db: DatabaseManager):
        super().__init__(parent, fg_color='transparent')
        self.db = db
        self.stats_mgr = AdvancedStatsManager(db)
        self.selected_player_id = None
        self.current_tab = 'form'

        self.setup_ui()
        self.load_stats()

    def setup_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color='transparent')
        header.pack(fill='x', padx=20, pady=(20, 10))

        ctk.CTkLabel(
            header,
            text='📊 Advanced Statistics',
            font=get_font(28, 'bold')
        ).pack(side='left')

        # Player selector
        selector_frame = ctk.CTkFrame(header, fg_color='transparent')
        selector_frame.pack(side='right')

        ctk.CTkLabel(
            selector_frame,
            text='Player:',
            font=get_font(13)
        ).pack(side='left', padx=5)

        players = self.db.get_all_players()
        player_names = [p.name for p in players]

        self.player_var = ctk.StringVar(value=player_names[0] if player_names else '')
        self.player_dropdown = ctk.CTkComboBox(
            selector_frame,
            values=player_names,
            variable=self.player_var,
            width=200,
            font=get_font(12),
            command=self.on_player_select
        )
        self.player_dropdown.pack(side='left', padx=5)

        if players:
            self.selected_player_id = players[0].id

        # Tabs
        tab_frame = ctk.CTkFrame(self, fg_color='#252540', corner_radius=10)
        tab_frame.pack(fill='x', padx=20, pady=10)

        tab_inner = ctk.CTkFrame(tab_frame, fg_color='transparent')
        tab_inner.pack(fill='x', padx=15, pady=10)

        tabs = [
            ('form', '🔥 Form'),
            ('rivalries', '⚔️ Rivalries'),
            ('handicap', '⚖️ Handicap'),
            ('predict', '🎯 Predictions'),
            ('partners', '🤝 Partners')
        ]

        self.tab_buttons = {}
        for key, text in tabs:
            btn = ctk.CTkButton(
                tab_inner,
                text=text,
                font=get_font(12),
                width=110,
                height=35,
                fg_color='#2d7a3e' if key == 'form' else 'transparent',
                hover_color='#1e3a1e',
                command=lambda k=key: self.set_tab(k)
            )
            btn.pack(side='left', padx=5)
            self.tab_buttons[key] = btn

        # Content area
        self.content_frame = ctk.CTkScrollableFrame(
            self,
            fg_color='#1a1a2e',
            corner_radius=15
        )
        self.content_frame.pack(fill='both', expand=True, padx=20, pady=10)

    def set_tab(self, tab: str):
        """Set the active tab."""
        self.current_tab = tab

        for key, btn in self.tab_buttons.items():
            if key == tab:
                btn.configure(fg_color='#2d7a3e')
            else:
                btn.configure(fg_color='transparent')

        self.load_stats()

    def on_player_select(self, selection):
        """Handle player selection."""
        players = self.db.get_all_players()
        for p in players:
            if p.name == selection:
                self.selected_player_id = p.id
                break
        self.load_stats()

    def load_stats(self):
        """Load statistics for current tab."""
        for widget in self.content_frame.winfo_children():
            widget.destroy()

        if not self.selected_player_id:
            ctk.CTkLabel(
                self.content_frame,
                text='Select a player to view stats',
                font=get_font(14),
                text_color='#666666'
            ).pack(pady=50)
            return

        if self.current_tab == 'form':
            self._load_form_stats()
        elif self.current_tab == 'rivalries':
            self._load_rivalries()
        elif self.current_tab == 'handicap':
            self._load_handicap()
        elif self.current_tab == 'predict':
            self._load_predictions()
        elif self.current_tab == 'partners':
            self._load_partner_stats()

    def _load_form_stats(self):
        """Load player form analysis."""
        ctk.CTkLabel(
            self.content_frame,
            text='📈 Current Form',
            font=get_font(18, 'bold')
        ).pack(anchor='w', padx=10, pady=(10, 15))

        # Form card
        card = PlayerFormCard(
            self.content_frame,
            self.db,
            self.stats_mgr,
            self.selected_player_id
        )
        card.pack(fill='x', padx=10, pady=5)

        # All players form comparison
        ctk.CTkLabel(
            self.content_frame,
            text='🔥 Hot & Cold Players',
            font=get_font(16, 'bold')
        ).pack(anchor='w', padx=10, pady=(20, 10))

        players = self.db.get_all_players()

        # Get form for all players
        hot_players = []
        cold_players = []

        for player in players:
            if player.games_played < 5:
                continue
            form = self.stats_mgr.get_player_form(player.id)
            if form.form_trend == 'hot':
                hot_players.append((player, form))
            elif form.form_trend == 'cold':
                cold_players.append((player, form))

        # Hot players
        if hot_players:
            hot_frame = ctk.CTkFrame(self.content_frame, fg_color='#3a2020', corner_radius=10)
            hot_frame.pack(fill='x', padx=10, pady=5)

            ctk.CTkLabel(
                hot_frame,
                text='🔥 HOT',
                font=get_font(14, 'bold'),
                text_color='#ff6b6b'
            ).pack(anchor='w', padx=10, pady=(10, 5))

            for player, form in hot_players:
                row = ctk.CTkFrame(hot_frame, fg_color='transparent')
                row.pack(fill='x', padx=10, pady=2)

                ctk.CTkLabel(
                    row,
                    text=player.name,
                    font=get_font(12)
                ).pack(side='left')

                ctk.CTkLabel(
                    row,
                    text=f"{form.last_10_win_rate:.0f}% ({form.trend_change:+.0f}%)",
                    font=get_font(11),
                    text_color='#4CAF50'
                ).pack(side='right', padx=10)

            ctk.CTkFrame(hot_frame, height=10, fg_color='transparent').pack()

        # Cold players
        if cold_players:
            cold_frame = ctk.CTkFrame(self.content_frame, fg_color='#202a3a', corner_radius=10)
            cold_frame.pack(fill='x', padx=10, pady=5)

            ctk.CTkLabel(
                cold_frame,
                text='❄️ COLD',
                font=get_font(14, 'bold'),
                text_color='#6b9bff'
            ).pack(anchor='w', padx=10, pady=(10, 5))

            for player, form in cold_players:
                row = ctk.CTkFrame(cold_frame, fg_color='transparent')
                row.pack(fill='x', padx=10, pady=2)

                ctk.CTkLabel(
                    row,
                    text=player.name,
                    font=get_font(12)
                ).pack(side='left')

                ctk.CTkLabel(
                    row,
                    text=f"{form.last_10_win_rate:.0f}% ({form.trend_change:+.0f}%)",
                    font=get_font(11),
                    text_color='#ff6b6b'
                ).pack(side='right', padx=10)

            ctk.CTkFrame(cold_frame, height=10, fg_color='transparent').pack()

    def _load_rivalries(self):
        """Load head-to-head rivalry stats."""
        ctk.CTkLabel(
            self.content_frame,
            text='⚔️ Head-to-Head Records',
            font=get_font(18, 'bold')
        ).pack(anchor='w', padx=10, pady=(10, 15))

        rivalries = self.stats_mgr.get_all_rivalries(self.selected_player_id)

        if not rivalries:
            ctk.CTkLabel(
                self.content_frame,
                text='No rivalry data yet. Play more games!',
                font=get_font(14),
                text_color='#666666'
            ).pack(pady=30)
            return

        for h2h in rivalries:
            card = HeadToHeadCard(self.content_frame, h2h)
            card.pack(fill='x', padx=10, pady=5)

    def _load_handicap(self):
        """Load handicap information."""
        ctk.CTkLabel(
            self.content_frame,
            text='⚖️ Handicap System',
            font=get_font(18, 'bold')
        ).pack(anchor='w', padx=10, pady=(10, 15))

        # Player's handicap
        player = self.db.get_player(self.selected_player_id)
        handicap = self.stats_mgr.calculate_handicap(self.selected_player_id)

        player_card = ctk.CTkFrame(self.content_frame, fg_color='#252540', corner_radius=12)
        player_card.pack(fill='x', padx=10, pady=10)

        ctk.CTkLabel(
            player_card,
            text=f"{player.name}'s Handicap",
            font=get_font(16, 'bold')
        ).pack(pady=(15, 5))

        handicap_color = '#4CAF50' if handicap < 0 else '#ff6b6b' if handicap > 0 else '#888888'
        handicap_text = f"{handicap:+.1f}" if handicap != 0 else "0 (Average)"

        ctk.CTkLabel(
            player_card,
            text=handicap_text,
            font=get_font(36, 'bold'),
            text_color=handicap_color
        ).pack(pady=10)

        explanation = "Gives points to opponents" if handicap < 0 else "Receives points from opponents" if handicap > 0 else "No adjustment"
        ctk.CTkLabel(
            player_card,
            text=explanation,
            font=get_font(12),
            text_color='#888888'
        ).pack(pady=(0, 15))

        # Explanation
        explain_frame = ctk.CTkFrame(self.content_frame, fg_color='#1a3a1a', corner_radius=10)
        explain_frame.pack(fill='x', padx=10, pady=10)

        ctk.CTkLabel(
            explain_frame,
            text='How Handicaps Work',
            font=get_font(14, 'bold')
        ).pack(anchor='w', padx=15, pady=(10, 5))

        explanation_text = (
            "• Handicap ranges from -5 (strong) to +5 (developing)\n"
            "• Based on win rate and average points per game\n"
            "• Players with positive handicap receive bonus points\n"
            "• Players with negative handicap give bonus points\n"
            "• Requires minimum 5 games to calculate"
        )

        ctk.CTkLabel(
            explain_frame,
            text=explanation_text,
            font=get_font(11),
            text_color='#aaaaaa',
            justify='left'
        ).pack(anchor='w', padx=15, pady=(0, 15))

        # All players handicaps
        ctk.CTkLabel(
            self.content_frame,
            text='All Player Handicaps',
            font=get_font(16, 'bold')
        ).pack(anchor='w', padx=10, pady=(20, 10))

        players = self.db.get_all_players()
        handicaps = [(p, self.stats_mgr.calculate_handicap(p.id)) for p in players]
        handicaps.sort(key=lambda x: x[1])

        for player, hc in handicaps:
            if player.games_played < 5:
                continue

            row = ctk.CTkFrame(self.content_frame, fg_color='#252540', corner_radius=8, height=40)
            row.pack(fill='x', padx=10, pady=2)
            row.pack_propagate(False)

            ctk.CTkLabel(
                row,
                text=player.name,
                font=get_font(12)
            ).pack(side='left', padx=15, pady=8)

            hc_color = '#4CAF50' if hc < 0 else '#ff6b6b' if hc > 0 else '#888888'
            ctk.CTkLabel(
                row,
                text=f"{hc:+.1f}",
                font=get_font(14, 'bold'),
                text_color=hc_color
            ).pack(side='right', padx=15)

    def _load_predictions(self):
        """Load match predictions."""
        ctk.CTkLabel(
            self.content_frame,
            text='🎯 Match Predictions',
            font=get_font(18, 'bold')
        ).pack(anchor='w', padx=10, pady=(10, 15))

        # Prediction tool
        predict_frame = ctk.CTkFrame(self.content_frame, fg_color='#252540', corner_radius=12)
        predict_frame.pack(fill='x', padx=10, pady=10)

        ctk.CTkLabel(
            predict_frame,
            text='Select teams to predict outcome',
            font=get_font(14)
        ).pack(pady=(15, 10))

        players = self.db.get_all_players()
        player_names = ['None'] + [p.name for p in players]

        # Team selectors
        teams_frame = ctk.CTkFrame(predict_frame, fg_color='transparent')
        teams_frame.pack(fill='x', padx=20, pady=10)

        # Team 1
        t1_frame = ctk.CTkFrame(teams_frame, fg_color='#1a3a1a', corner_radius=10)
        t1_frame.pack(side='left', expand=True, fill='both', padx=5)

        ctk.CTkLabel(t1_frame, text='Team 1', font=get_font(12, 'bold')).pack(pady=(10, 5))

        self.t1_p1_var = ctk.StringVar(value='None')
        ctk.CTkComboBox(
            t1_frame, values=player_names, variable=self.t1_p1_var,
            width=150, font=get_font(11)
        ).pack(pady=2)

        self.t1_p2_var = ctk.StringVar(value='None')
        ctk.CTkComboBox(
            t1_frame, values=player_names, variable=self.t1_p2_var,
            width=150, font=get_font(11)
        ).pack(pady=(2, 10))

        # VS
        ctk.CTkLabel(teams_frame, text='VS', font=get_font(16, 'bold')).pack(side='left', padx=10)

        # Team 2
        t2_frame = ctk.CTkFrame(teams_frame, fg_color='#3a1a1a', corner_radius=10)
        t2_frame.pack(side='right', expand=True, fill='both', padx=5)

        ctk.CTkLabel(t2_frame, text='Team 2', font=get_font(12, 'bold')).pack(pady=(10, 5))

        self.t2_p1_var = ctk.StringVar(value='None')
        ctk.CTkComboBox(
            t2_frame, values=player_names, variable=self.t2_p1_var,
            width=150, font=get_font(11)
        ).pack(pady=2)

        self.t2_p2_var = ctk.StringVar(value='None')
        ctk.CTkComboBox(
            t2_frame, values=player_names, variable=self.t2_p2_var,
            width=150, font=get_font(11)
        ).pack(pady=(2, 10))

        ctk.CTkButton(
            predict_frame,
            text='Predict!',
            font=get_font(14, 'bold'),
            fg_color='#4CAF50',
            hover_color='#388E3C',
            height=40,
            command=self._run_prediction
        ).pack(pady=15)

        # Results area
        self.prediction_results = ctk.CTkFrame(self.content_frame, fg_color='transparent')
        self.prediction_results.pack(fill='x', padx=10, pady=10)

    def _run_prediction(self):
        """Run match prediction."""
        players = self.db.get_all_players()
        player_map = {p.name: p.id for p in players}

        t1_p1 = player_map.get(self.t1_p1_var.get())
        t1_p2 = player_map.get(self.t1_p2_var.get())
        t2_p1 = player_map.get(self.t2_p1_var.get())
        t2_p2 = player_map.get(self.t2_p2_var.get())

        if not t1_p1 or not t2_p1:
            return

        prediction = self.stats_mgr.predict_match_outcome(t1_p1, t1_p2, t2_p1, t2_p2)

        # Clear previous results
        for widget in self.prediction_results.winfo_children():
            widget.destroy()

        # Show prediction
        card = MatchPredictionCard(self.prediction_results, prediction)
        card.pack(fill='x', pady=5)

    def _load_partner_stats(self):
        """Load partner statistics."""
        ctk.CTkLabel(
            self.content_frame,
            text='🤝 Partner Statistics',
            font=get_font(18, 'bold')
        ).pack(anchor='w', padx=10, pady=(10, 15))

        partner_stats = self.db.get_partner_stats(self.selected_player_id)

        if not partner_stats:
            ctk.CTkLabel(
                self.content_frame,
                text='No partner data yet. Play some doubles matches!',
                font=get_font(14),
                text_color='#666666'
            ).pack(pady=30)
            return

        # Best partners
        ctk.CTkLabel(
            self.content_frame,
            text='Best Partners (by win rate)',
            font=get_font(14, 'bold')
        ).pack(anchor='w', padx=10, pady=(10, 5))

        for i, stat in enumerate(partner_stats[:5]):
            partner = stat['partner']

            bg_color = '#1a3a1a' if i == 0 else '#252540'
            row = ctk.CTkFrame(self.content_frame, fg_color=bg_color, corner_radius=8, height=50)
            row.pack(fill='x', padx=10, pady=2)
            row.pack_propagate(False)

            # Rank
            rank_emoji = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣'][i] if i < 5 else ''
            ctk.CTkLabel(
                row,
                text=rank_emoji,
                font=get_font(16),
                width=40
            ).pack(side='left', padx=5, pady=8)

            # Profile pic
            try:
                pic = ProfilePicture(row, size=35, image_path=partner.profile_picture, player_name=partner.name)
                pic.pack(side='left', padx=5)
            except:
                pass

            # Name
            ctk.CTkLabel(
                row,
                text=partner.name,
                font=get_font(13, 'bold'),
                width=150,
                anchor='w'
            ).pack(side='left', padx=5)

            # Games together
            ctk.CTkLabel(
                row,
                text=f"{stat['games_together']} games",
                font=get_font(11),
                text_color='#888888',
                width=80
            ).pack(side='left', padx=5)

            # Wins together
            ctk.CTkLabel(
                row,
                text=f"{stat['wins_together']} wins",
                font=get_font(11),
                text_color='#4CAF50',
                width=70
            ).pack(side='left', padx=5)

            # Win rate
            rate_color = '#4CAF50' if stat['win_rate'] >= 50 else '#ff6b6b'
            ctk.CTkLabel(
                row,
                text=f"{stat['win_rate']:.0f}%",
                font=get_font(14, 'bold'),
                text_color=rate_color
            ).pack(side='right', padx=15)
