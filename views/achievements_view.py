"""
EcoPOOL League - Achievements View
Displays player achievements, badges, and progress.
"""

import customtkinter as ctk
from tkinter import Canvas
from typing import Optional, Callable
from database import DatabaseManager
from achievements import AchievementManager, Achievement, ACHIEVEMENTS, TIER_COLORS, TIER_BG_COLORS
from profile_pictures import ProfilePicture
from fonts import get_font
from animations import AnimatedCard, flash_widget


class AchievementBadge(ctk.CTkFrame):
    """Widget displaying a single achievement badge."""

    def __init__(self, parent, achievement: Achievement, unlocked: bool = False,
                 progress: int = 0, progress_percent: int = 0,
                 unlocked_at: str = None, size: str = 'medium', **kwargs):

        # Determine colors based on tier and unlock status
        if unlocked:
            bg_color = TIER_BG_COLORS.get(achievement.tier, '#252540')
            border_color = TIER_COLORS.get(achievement.tier, '#888888')
        else:
            bg_color = '#1a1a2e'
            border_color = '#333333'

        super().__init__(parent, fg_color=bg_color, corner_radius=12, **kwargs)

        self.achievement = achievement
        self.unlocked = unlocked

        # Size configurations
        sizes = {
            'small': {'width': 100, 'height': 100, 'icon_size': 24, 'name_size': 10},
            'medium': {'width': 150, 'height': 150, 'icon_size': 32, 'name_size': 12},
            'large': {'width': 200, 'height': 200, 'icon_size': 48, 'name_size': 14}
        }
        config = sizes.get(size, sizes['medium'])

        self.configure(width=config['width'], height=config['height'])
        self.pack_propagate(False)

        # Icon
        icon_text = achievement.icon if unlocked else '🔒'
        opacity = '' if unlocked else ' (locked)'

        ctk.CTkLabel(
            self,
            text=icon_text,
            font=get_font(config['icon_size'])
        ).pack(pady=(15, 5))

        # Name
        name_color = TIER_COLORS.get(achievement.tier, '#888888') if unlocked else '#666666'
        ctk.CTkLabel(
            self,
            text=achievement.name,
            font=get_font(config['name_size'], 'bold'),
            text_color=name_color,
            wraplength=config['width'] - 20
        ).pack(pady=2)

        # Description (for medium/large)
        if size in ['medium', 'large']:
            desc_color = '#cccccc' if unlocked else '#555555'
            ctk.CTkLabel(
                self,
                text=achievement.description,
                font=get_font(9),
                text_color=desc_color,
                wraplength=config['width'] - 20
            ).pack(pady=2)

        # Progress bar (if not unlocked)
        if not unlocked and size != 'small':
            progress_frame = ctk.CTkFrame(self, fg_color='#333333', height=6, corner_radius=3)
            progress_frame.pack(fill='x', padx=15, pady=5)
            progress_frame.pack_propagate(False)

            if progress_percent > 0:
                fill_width = max(1, int((config['width'] - 30) * progress_percent / 100))
                progress_fill = ctk.CTkFrame(
                    progress_frame,
                    fg_color=TIER_COLORS.get(achievement.tier, '#4CAF50'),
                    height=6,
                    width=fill_width,
                    corner_radius=3
                )
                progress_fill.place(x=0, y=0)

            ctk.CTkLabel(
                self,
                text=f"{progress}/{achievement.requirement}",
                font=get_font(9),
                text_color='#666666'
            ).pack()

        # Tier indicator
        if unlocked:
            tier_frame = ctk.CTkFrame(
                self,
                fg_color=TIER_COLORS.get(achievement.tier, '#888888'),
                corner_radius=8,
                height=16
            )
            tier_frame.pack(pady=5)

            ctk.CTkLabel(
                tier_frame,
                text=f" {achievement.tier.upper()} • {achievement.points} pts ",
                font=get_font(8, 'bold'),
                text_color='#000000' if achievement.tier != 'platinum' else '#333333'
            ).pack(padx=5)


class AchievementsView(ctk.CTkFrame):
    """View for displaying all achievements."""

    def __init__(self, parent, db: DatabaseManager, player_id: int = None):
        super().__init__(parent, fg_color='transparent')
        self.db = db
        self.achievement_mgr = AchievementManager(db)
        self.selected_player_id = player_id
        self.current_category = 'all'

        self.setup_ui()
        self.load_achievements()

    def setup_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color='transparent')
        header.pack(fill='x', padx=20, pady=(20, 10))

        ctk.CTkLabel(
            header,
            text='🏆 Achievements',
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
        player_names = ['All Players'] + [p.name for p in players]

        self.player_var = ctk.StringVar(value='All Players')
        self.player_dropdown = ctk.CTkComboBox(
            selector_frame,
            values=player_names,
            variable=self.player_var,
            width=200,
            font=get_font(12),
            command=self.on_player_select
        )
        self.player_dropdown.pack(side='left', padx=5)

        # Category filters
        filter_frame = ctk.CTkFrame(self, fg_color='#252540', corner_radius=10)
        filter_frame.pack(fill='x', padx=20, pady=10)

        filter_inner = ctk.CTkFrame(filter_frame, fg_color='transparent')
        filter_inner.pack(fill='x', padx=15, pady=10)

        categories = [
            ('all', 'All'),
            ('milestone', 'Milestones'),
            ('skill', 'Skill'),
            ('streak', 'Streaks'),
            ('special', 'Special')
        ]

        self.category_buttons = {}
        for key, text in categories:
            btn = ctk.CTkButton(
                filter_inner,
                text=text,
                font=get_font(12),
                width=100,
                height=35,
                fg_color='#2d7a3e' if key == 'all' else 'transparent',
                hover_color='#1e3a1e',
                command=lambda k=key: self.set_category(k)
            )
            btn.pack(side='left', padx=5)
            self.category_buttons[key] = btn

        # Stats summary
        self.stats_frame = ctk.CTkFrame(self, fg_color='#1a3a1a', corner_radius=10)
        self.stats_frame.pack(fill='x', padx=20, pady=10)

        stats_inner = ctk.CTkFrame(self.stats_frame, fg_color='transparent')
        stats_inner.pack(fill='x', padx=20, pady=15)

        self.unlocked_label = ctk.CTkLabel(
            stats_inner,
            text='0 / 0',
            font=get_font(24, 'bold'),
            text_color='#4CAF50'
        )
        self.unlocked_label.pack(side='left')

        ctk.CTkLabel(
            stats_inner,
            text=' Achievements Unlocked',
            font=get_font(14),
            text_color='#888888'
        ).pack(side='left')

        self.points_label = ctk.CTkLabel(
            stats_inner,
            text='0 pts',
            font=get_font(20, 'bold'),
            text_color='#FFD700'
        )
        self.points_label.pack(side='right')

        ctk.CTkLabel(
            stats_inner,
            text='Achievement Points: ',
            font=get_font(12),
            text_color='#888888'
        ).pack(side='right')

        # Achievements grid
        self.achievements_frame = ctk.CTkScrollableFrame(
            self,
            fg_color='#1a1a2e',
            corner_radius=15
        )
        self.achievements_frame.pack(fill='both', expand=True, padx=20, pady=10)

    def set_category(self, category: str):
        """Set the active category filter."""
        self.current_category = category

        for key, btn in self.category_buttons.items():
            if key == category:
                btn.configure(fg_color='#2d7a3e')
            else:
                btn.configure(fg_color='transparent')

        self.load_achievements()

    def on_player_select(self, selection):
        """Handle player selection change."""
        if selection == 'All Players':
            self.selected_player_id = None
        else:
            players = self.db.get_all_players()
            for p in players:
                if p.name == selection:
                    self.selected_player_id = p.id
                    break

        self.load_achievements()

    def load_achievements(self):
        """Load and display achievements."""
        # Clear existing
        for widget in self.achievements_frame.winfo_children():
            widget.destroy()

        if self.selected_player_id:
            # Show achievements for specific player
            achievements = self.achievement_mgr.get_player_achievements(self.selected_player_id)

            # Filter by category
            if self.current_category != 'all':
                achievements = [a for a in achievements
                               if a['achievement'].category == self.current_category]

            # Update stats
            unlocked = [a for a in achievements if a['unlocked']]
            total_points = sum(a['achievement'].points for a in unlocked)

            self.unlocked_label.configure(text=f"{len(unlocked)} / {len(achievements)}")
            self.points_label.configure(text=f"{total_points} pts")

            # Display achievements
            self._display_achievements(achievements)

        else:
            # Show achievement leaderboard
            self._display_leaderboard()

    def _display_achievements(self, achievements):
        """Display achievement badges in a grid."""
        # Separate unlocked and locked
        unlocked = [a for a in achievements if a['unlocked']]
        locked = [a for a in achievements if not a['unlocked']]

        # Show unlocked first
        if unlocked:
            ctk.CTkLabel(
                self.achievements_frame,
                text='✅ Unlocked',
                font=get_font(16, 'bold'),
                text_color='#4CAF50'
            ).pack(anchor='w', padx=10, pady=(10, 5))

            unlocked_grid = ctk.CTkFrame(self.achievements_frame, fg_color='transparent')
            unlocked_grid.pack(fill='x', padx=10, pady=5)

            for i, ach_data in enumerate(unlocked):
                row = i // 5
                col = i % 5

                badge = AchievementBadge(
                    unlocked_grid,
                    achievement=ach_data['achievement'],
                    unlocked=True,
                    unlocked_at=ach_data.get('unlocked_at'),
                    size='medium'
                )
                badge.grid(row=row, column=col, padx=5, pady=5)

        # Show locked
        if locked:
            ctk.CTkLabel(
                self.achievements_frame,
                text='🔒 Locked',
                font=get_font(16, 'bold'),
                text_color='#666666'
            ).pack(anchor='w', padx=10, pady=(20, 5))

            locked_grid = ctk.CTkFrame(self.achievements_frame, fg_color='transparent')
            locked_grid.pack(fill='x', padx=10, pady=5)

            for i, ach_data in enumerate(locked):
                row = i // 5
                col = i % 5

                badge = AchievementBadge(
                    locked_grid,
                    achievement=ach_data['achievement'],
                    unlocked=False,
                    progress=ach_data['progress'],
                    progress_percent=ach_data['progress_percent'],
                    size='medium'
                )
                badge.grid(row=row, column=col, padx=5, pady=5)

    def _display_leaderboard(self):
        """Display achievement points leaderboard."""
        leaderboard = self.achievement_mgr.get_leaderboard_by_achievements()

        # Update stats
        total_unlocked = sum(e['achievements_unlocked'] for e in leaderboard)
        total_points = sum(e['achievement_points'] for e in leaderboard)

        self.unlocked_label.configure(text=f"{total_unlocked} total")
        self.points_label.configure(text=f"{total_points} pts")

        ctk.CTkLabel(
            self.achievements_frame,
            text='🏆 Achievement Leaderboard',
            font=get_font(18, 'bold')
        ).pack(anchor='w', padx=10, pady=(10, 15))

        # Header row
        header = ctk.CTkFrame(self.achievements_frame, fg_color='#2d7a3e', corner_radius=10)
        header.pack(fill='x', padx=10, pady=5)

        headers = [('Rank', 50), ('', 50), ('Player', 150),
                   ('Achievements', 100), ('Points', 80)]

        for text, width in headers:
            ctk.CTkLabel(
                header,
                text=text,
                font=get_font(12, 'bold'),
                width=width
            ).pack(side='left', padx=5, pady=8)

        # Leaderboard rows
        for i, entry in enumerate(leaderboard[:20], 1):
            player = entry['player']

            # Row color based on rank
            if i == 1:
                bg = '#5c4d1a'
            elif i == 2:
                bg = '#4a4a4a'
            elif i == 3:
                bg = '#4a3020'
            else:
                bg = '#252540'

            row = ctk.CTkFrame(self.achievements_frame, fg_color=bg, corner_radius=8, height=50)
            row.pack(fill='x', padx=10, pady=2)
            row.pack_propagate(False)

            # Rank
            rank_text = ['🥇', '🥈', '🥉'][i - 1] if i <= 3 else str(i)
            ctk.CTkLabel(
                row,
                text=rank_text,
                font=get_font(14, 'bold'),
                width=50
            ).pack(side='left', padx=5, pady=8)

            # Profile picture
            pic_frame = ctk.CTkFrame(row, fg_color='transparent', width=50)
            pic_frame.pack(side='left', padx=5)
            pic_frame.pack_propagate(False)

            try:
                pic = ProfilePicture(
                    pic_frame, size=35,
                    image_path=player.profile_picture,
                    player_name=player.name
                )
                pic.pack(expand=True)
            except:
                pass

            # Name
            ctk.CTkLabel(
                row,
                text=player.name,
                font=get_font(13, 'bold'),
                width=150,
                anchor='w'
            ).pack(side='left', padx=5)

            # Achievements count
            ctk.CTkLabel(
                row,
                text=f"{entry['achievements_unlocked']}/{entry['achievements_total']}",
                font=get_font(12),
                width=100
            ).pack(side='left', padx=5)

            # Points
            ctk.CTkLabel(
                row,
                text=str(entry['achievement_points']),
                font=get_font(14, 'bold'),
                text_color='#FFD700',
                width=80
            ).pack(side='left', padx=5)

            # Make row clickable
            row.bind('<Button-1>', lambda e, pid=player.id: self._select_player(pid))
            for child in row.winfo_children():
                child.bind('<Button-1>', lambda e, pid=player.id: self._select_player(pid))

    def _select_player(self, player_id: int):
        """Select a player from the leaderboard."""
        player = self.db.get_player(player_id)
        if player:
            self.selected_player_id = player_id
            self.player_var.set(player.name)
            self.load_achievements()


class AchievementUnlockPopup(ctk.CTkToplevel):
    """Popup displayed when an achievement is unlocked."""

    def __init__(self, parent, achievement: Achievement, player_name: str = None):
        super().__init__(parent)

        self.title('Achievement Unlocked!')
        self.geometry('400x350')
        self.transient(parent)
        self.grab_set()

        # Center the popup
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - 200
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - 175
        self.geometry(f'+{x}+{y}')

        # Configure
        self.configure(fg_color='#1a1a2e')

        # Content
        ctk.CTkLabel(
            self,
            text='🎉 ACHIEVEMENT UNLOCKED! 🎉',
            font=get_font(18, 'bold'),
            text_color='#FFD700'
        ).pack(pady=(30, 20))

        # Badge
        badge_frame = ctk.CTkFrame(
            self,
            fg_color=TIER_BG_COLORS.get(achievement.tier, '#252540'),
            corner_radius=15
        )
        badge_frame.pack(padx=40, pady=10)

        ctk.CTkLabel(
            badge_frame,
            text=achievement.icon,
            font=get_font(48)
        ).pack(pady=(20, 5))

        ctk.CTkLabel(
            badge_frame,
            text=achievement.name,
            font=get_font(18, 'bold'),
            text_color=TIER_COLORS.get(achievement.tier, '#ffffff')
        ).pack(pady=5)

        ctk.CTkLabel(
            badge_frame,
            text=achievement.description,
            font=get_font(12),
            text_color='#cccccc'
        ).pack(pady=(0, 10))

        # Points
        ctk.CTkLabel(
            badge_frame,
            text=f'+{achievement.points} Achievement Points',
            font=get_font(14, 'bold'),
            text_color='#4CAF50'
        ).pack(pady=(5, 20))

        # Player name
        if player_name:
            ctk.CTkLabel(
                self,
                text=f'Congratulations, {player_name}!',
                font=get_font(14),
                text_color='#888888'
            ).pack(pady=10)

        # Close button
        ctk.CTkButton(
            self,
            text='Awesome!',
            font=get_font(14, 'bold'),
            fg_color='#4CAF50',
            hover_color='#388E3C',
            height=40,
            width=120,
            command=self.destroy
        ).pack(pady=20)

        # Auto close after 5 seconds
        self.after(5000, self.destroy)
