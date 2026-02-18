"""
EcoPOOL League - Settings View
Application settings including themes and preferences.
"""

import customtkinter as ctk
from tkinter import messagebox, filedialog
import os
import shutil
import hashlib
from datetime import datetime
from database import DatabaseManager
from excel_importer import ExcelImporter
from fonts import get_font


def _hash_credential(credential: str) -> str:
    """Hash a password or PIN using PBKDF2-HMAC-SHA256.

    Args:
        credential: The plaintext password/PIN to hash

    Returns:
        A string in format "salt_hex:hash_hex" for storage
    """
    salt = os.urandom(32)

    # Use PBKDF2 with 100,000 iterations (OWASP recommended minimum)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        credential.encode('utf-8'),
        salt,
        iterations=100000
    )

    return f"{salt.hex()}:{key.hex()}"


class SettingsView(ctk.CTkFrame):
    """View for application settings."""

    def __init__(self, parent, db: DatabaseManager, exporter=None, 
                 on_new_pool_night=None, on_data_change=None):
        super().__init__(parent, fg_color='transparent')
        self.db = db
        self.exporter = exporter
        self.on_new_pool_night = on_new_pool_night
        self.on_data_change = on_data_change

        self.setup_ui()

    def setup_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color='transparent')
        header.pack(fill='x', padx=20, pady=(20, 10))

        ctk.CTkLabel(
            header,
            text='Settings',
            font=get_font(28, 'bold')
        ).pack(side='left')

        # Scrollable content
        content = ctk.CTkScrollableFrame(self, fg_color='transparent')
        content.pack(fill='both', expand=True, padx=20, pady=10)

        # ========== Venmo Section ==========
        self._create_section(content, 'Venmo Settings')

        venmo_card = ctk.CTkFrame(content, fg_color='#252540', corner_radius=15)
        venmo_card.pack(fill='x', pady=10)

        venmo_inner = ctk.CTkFrame(venmo_card, fg_color='transparent')
        venmo_inner.pack(fill='x', padx=20, pady=15)

        ctk.CTkLabel(
            venmo_inner,
            text='Organizer Venmo',
            font=get_font(14, 'bold')
        ).pack(anchor='w')

        ctk.CTkLabel(
            venmo_inner,
            text='Your Venmo username for receiving buy-ins',
            font=get_font(11),
            text_color='#888888'
        ).pack(anchor='w')

        saved_venmo = self.db.get_setting('organizer_venmo', '')
        self.venmo_var = ctk.StringVar(value=saved_venmo)

        venmo_entry_row = ctk.CTkFrame(venmo_inner, fg_color='transparent')
        venmo_entry_row.pack(fill='x', pady=10)

        ctk.CTkLabel(
            venmo_entry_row,
            text='@',
            font=get_font(14)
        ).pack(side='left')

        venmo_entry = ctk.CTkEntry(
            venmo_entry_row,
            textvariable=self.venmo_var,
            height=40,
            width=200,
            font=get_font(14),
            placeholder_text='username'
        )
        venmo_entry.pack(side='left', padx=5)

        ctk.CTkButton(
            venmo_entry_row,
            text='Save',
            font=get_font(12),
            fg_color='#4CAF50',
            hover_color='#388E3C',
            height=40,
            width=80,
            command=self._save_venmo
        ).pack(side='left', padx=10)

        # Default buy-in
        buyin_row = ctk.CTkFrame(venmo_inner, fg_color='transparent')
        buyin_row.pack(fill='x', pady=10)

        ctk.CTkLabel(
            buyin_row,
            text='Default Buy-in: $',
            font=get_font(12)
        ).pack(side='left')

        saved_buyin = self.db.get_setting('default_buyin', '5')
        self.buyin_var = ctk.StringVar(value=saved_buyin)

        ctk.CTkEntry(
            buyin_row,
            textvariable=self.buyin_var,
            width=60,
            height=35,
            font=get_font(14)
        ).pack(side='left', padx=5)

        ctk.CTkButton(
            buyin_row,
            text='Save',
            font=get_font(11),
            fg_color='#4CAF50',
            hover_color='#388E3C',
            height=35,
            width=60,
            command=self._save_buyin
        ).pack(side='left', padx=5)

        # ========== Manager Password Section ==========
        self._create_section(content, 'Manager Password')

        manager_card = ctk.CTkFrame(content, fg_color='#252540', corner_radius=15)
        manager_card.pack(fill='x', pady=10)

        manager_inner = ctk.CTkFrame(manager_card, fg_color='transparent')
        manager_inner.pack(fill='x', padx=20, pady=15)

        ctk.CTkLabel(
            manager_inner,
            text='Web Manager Password',
            font=get_font(14, 'bold')
        ).pack(anchor='w')

        ctk.CTkLabel(
            manager_inner,
            text='Password for accessing manager mode on the web interface',
            font=get_font(11),
            text_color='#888888'
        ).pack(anchor='w')

        password_row = ctk.CTkFrame(manager_inner, fg_color='transparent')
        password_row.pack(fill='x', pady=10)

        self.manager_password_var = ctk.StringVar(value='')
        manager_password_entry = ctk.CTkEntry(
            password_row,
            textvariable=self.manager_password_var,
            height=40,
            width=200,
            font=get_font(14),
            placeholder_text='Enter new password',
            show='*'
        )
        manager_password_entry.pack(side='left', padx=5)

        ctk.CTkButton(
            password_row,
            text='Change Password',
            font=get_font(12),
            fg_color='#4CAF50',
            hover_color='#388E3C',
            height=40,
            width=140,
            command=self._change_manager_password
        ).pack(side='left', padx=10)

        # Show current password status
        current_password = self.db.get_setting('manager_password', '')
        password_status = 'Set' if current_password else 'Not set'
        self.password_status_label = ctk.CTkLabel(
            manager_inner,
            text=f'Current status: {password_status}',
            font=get_font(11),
            text_color='#888888'
        )
        self.password_status_label.pack(anchor='w', pady=(5, 0))

        # ========== Payment Portal PIN Section ==========
        self._create_section(content, 'Payment Portal PIN')

        payment_pin_card = ctk.CTkFrame(content, fg_color='#252540', corner_radius=15)
        payment_pin_card.pack(fill='x', pady=10)

        payment_pin_inner = ctk.CTkFrame(payment_pin_card, fg_color='transparent')
        payment_pin_inner.pack(fill='x', padx=20, pady=15)

        ctk.CTkLabel(
            payment_pin_inner,
            text='Payment Portal PIN',
            font=get_font(14, 'bold')
        ).pack(anchor='w')

        ctk.CTkLabel(
            payment_pin_inner,
            text='PIN/passcode for accessing the payment admin portal on the web interface',
            font=get_font(11),
            text_color='#888888'
        ).pack(anchor='w')

        pin_row = ctk.CTkFrame(payment_pin_inner, fg_color='transparent')
        pin_row.pack(fill='x', pady=10)

        self.payment_pin_var = ctk.StringVar(value='')
        payment_pin_entry = ctk.CTkEntry(
            pin_row,
            textvariable=self.payment_pin_var,
            height=40,
            width=200,
            font=get_font(14),
            placeholder_text='Enter new PIN',
            show='*'
        )
        payment_pin_entry.pack(side='left', padx=5)

        ctk.CTkButton(
            pin_row,
            text='Change PIN',
            font=get_font(12),
            fg_color='#4CAF50',
            hover_color='#388E3C',
            height=40,
            width=140,
            command=self._change_payment_pin
        ).pack(side='left', padx=10)

        # Show current PIN status
        current_pin = self.db.get_setting('payment_portal_pin', '')
        pin_status = 'Set' if current_pin else 'Not set'
        self.pin_status_label = ctk.CTkLabel(
            payment_pin_inner,
            text=f'Current status: {pin_status}',
            font=get_font(11),
            text_color='#888888'
        )
        self.pin_status_label.pack(anchor='w', pady=(5, 0))

        # ========== Public Server (ngrok) Section ==========
        self._create_section(content, 'Public Server (ngrok)')

        ngrok_card = ctk.CTkFrame(content, fg_color='#252540', corner_radius=15)
        ngrok_card.pack(fill='x', pady=10)

        ngrok_inner = ctk.CTkFrame(ngrok_card, fg_color='transparent')
        ngrok_inner.pack(fill='x', padx=20, pady=15)

        ctk.CTkLabel(
            ngrok_inner,
            text='Enable Public Access',
            font=get_font(14, 'bold')
        ).pack(anchor='w')

        ctk.CTkLabel(
            ngrok_inner,
            text='Make the live scores server accessible from anywhere via ngrok',
            font=get_font(11),
            text_color='#888888'
        ).pack(anchor='w')

        ngrok_toggle_row = ctk.CTkFrame(ngrok_inner, fg_color='transparent')
        ngrok_toggle_row.pack(fill='x', pady=10)

        ngrok_enabled = self.db.get_setting('ngrok_enabled', 'false') == 'true'
        self.ngrok_enabled_var = ctk.BooleanVar(value=ngrok_enabled)

        ctk.CTkLabel(
            ngrok_toggle_row,
            text='Enable public access via ngrok',
            font=get_font(12)
        ).pack(side='left')

        ctk.CTkSwitch(
            ngrok_toggle_row,
            text='',
            variable=self.ngrok_enabled_var,
            command=self._save_ngrok_enabled,
            fg_color='#333333',
            progress_color='#4CAF50'
        ).pack(side='right')

        # Auth token field
        ctk.CTkLabel(
            ngrok_inner,
            text='Auth Token (required for static domain)',
            font=get_font(13, 'bold')
        ).pack(anchor='w', pady=(15, 5))

        ctk.CTkLabel(
            ngrok_inner,
            text='Get your free auth token at dashboard.ngrok.com',
            font=get_font(11),
            text_color='#888888'
        ).pack(anchor='w')

        token_row = ctk.CTkFrame(ngrok_inner, fg_color='transparent')
        token_row.pack(fill='x', pady=10)

        saved_token = self.db.get_setting('ngrok_auth_token', '')
        self.ngrok_token_var = ctk.StringVar(value=saved_token)

        ctk.CTkEntry(
            token_row,
            textvariable=self.ngrok_token_var,
            height=40,
            width=280,
            font=get_font(14),
            placeholder_text='Enter ngrok auth token',
            show='*'
        ).pack(side='left', padx=(0, 10))

        ctk.CTkButton(
            token_row,
            text='Save Token',
            font=get_font(12),
            fg_color='#4CAF50',
            hover_color='#388E3C',
            height=40,
            width=100,
            command=self._save_ngrok_token
        ).pack(side='left')

        # Static domain field (eliminates browser warning)
        ctk.CTkLabel(
            ngrok_inner,
            text='Static Domain (eliminates browser warning)',
            font=get_font(13, 'bold')
        ).pack(anchor='w', pady=(15, 5))

        ctk.CTkLabel(
            ngrok_inner,
            text='Get one free static domain at dashboard.ngrok.com/domains',
            font=get_font(11),
            text_color='#888888'
        ).pack(anchor='w')

        domain_row = ctk.CTkFrame(ngrok_inner, fg_color='transparent')
        domain_row.pack(fill='x', pady=10)

        saved_domain = self.db.get_setting('ngrok_static_domain', '')
        self.ngrok_domain_var = ctk.StringVar(value=saved_domain)

        ctk.CTkEntry(
            domain_row,
            textvariable=self.ngrok_domain_var,
            height=40,
            width=280,
            font=get_font(14),
            placeholder_text='yourname.ngrok-free.app'
        ).pack(side='left', padx=(0, 10))

        ctk.CTkButton(
            domain_row,
            text='Save Domain',
            font=get_font(12),
            fg_color='#4CAF50',
            hover_color='#388E3C',
            height=40,
            width=100,
            command=self._save_ngrok_domain
        ).pack(side='left')

        # Info label
        ctk.CTkLabel(
            ngrok_inner,
            text='Note: Using a static domain completely removes the ngrok\n'
                 'browser warning. Auth token is required for static domains.',
            font=get_font(10),
            text_color='#666666'
        ).pack(anchor='w', pady=(5, 0))

        # ========== AI Team Names Section ==========
        self._create_section(content, 'AI Team Names')

        ai_card = ctk.CTkFrame(content, fg_color='#252540', corner_radius=15)
        ai_card.pack(fill='x', pady=10)

        ai_inner = ctk.CTkFrame(ai_card, fg_color='transparent')
        ai_inner.pack(fill='x', padx=20, pady=15)

        ctk.CTkLabel(
            ai_inner,
            text='Claude AI Team Names',
            font=get_font(14, 'bold')
        ).pack(anchor='w')

        ctk.CTkLabel(
            ai_inner,
            text='Generate creative pool-themed team names for each pair using Claude AI',
            font=get_font(11),
            text_color='#888888'
        ).pack(anchor='w')

        # Enable toggle
        ai_toggle_row = ctk.CTkFrame(ai_inner, fg_color='transparent')
        ai_toggle_row.pack(fill='x', pady=10)

        ctk.CTkLabel(
            ai_toggle_row,
            text='Enable AI team names',
            font=get_font(12)
        ).pack(side='left')

        ai_enabled = self.db.get_setting('ai_names_enabled', 'false') == 'true'
        self.ai_names_enabled_var = ctk.BooleanVar(value=ai_enabled)

        ctk.CTkSwitch(
            ai_toggle_row,
            text='',
            variable=self.ai_names_enabled_var,
            command=self._save_ai_names_enabled,
            fg_color='#333333',
            progress_color='#4CAF50'
        ).pack(side='right')

        # API key field
        ctk.CTkLabel(
            ai_inner,
            text='Anthropic API Key',
            font=get_font(13, 'bold')
        ).pack(anchor='w', pady=(10, 5))

        ctk.CTkLabel(
            ai_inner,
            text='Get your API key at console.anthropic.com',
            font=get_font(11),
            text_color='#888888'
        ).pack(anchor='w')

        ai_key_row = ctk.CTkFrame(ai_inner, fg_color='transparent')
        ai_key_row.pack(fill='x', pady=10)

        saved_key = self.db.get_setting('anthropic_api_key', '')
        self.ai_api_key_var = ctk.StringVar(value=saved_key)

        ctk.CTkEntry(
            ai_key_row,
            textvariable=self.ai_api_key_var,
            height=40,
            width=280,
            font=get_font(14),
            placeholder_text='sk-ant-...',
            show='*'
        ).pack(side='left', padx=(0, 10))

        ctk.CTkButton(
            ai_key_row,
            text='Save Key',
            font=get_font(12),
            fg_color='#4CAF50',
            hover_color='#388E3C',
            height=40,
            width=100,
            command=self._save_ai_api_key
        ).pack(side='left')

        # ========== Season Management Section ==========
        self._create_section(content, 'Season Management')

        season_card = ctk.CTkFrame(content, fg_color='#252540', corner_radius=15)
        season_card.pack(fill='x', pady=10)

        season_inner = ctk.CTkFrame(season_card, fg_color='transparent')
        season_inner.pack(fill='x', padx=20, pady=15)

        # Current season display
        active_season = self.db.get_active_season()
        season_text = active_season.name if active_season else 'No active season'
        
        ctk.CTkLabel(
            season_inner,
            text='Current Season',
            font=get_font(14, 'bold')
        ).pack(anchor='w')

        self.current_season_label = ctk.CTkLabel(
            season_inner,
            text=season_text,
            font=get_font(12),
            text_color='#4CAF50' if active_season else '#ff6b6b'
        )
        self.current_season_label.pack(anchor='w', pady=(2, 10))

        # Create new season
        ctk.CTkLabel(
            season_inner,
            text='Create New Season',
            font=get_font(13, 'bold')
        ).pack(anchor='w', pady=(10, 5))

        new_season_row = ctk.CTkFrame(season_inner, fg_color='transparent')
        new_season_row.pack(fill='x', pady=5)

        self.new_season_var = ctk.StringVar(value='')
        ctk.CTkEntry(
            new_season_row,
            textvariable=self.new_season_var,
            height=40,
            width=200,
            font=get_font(14),
            placeholder_text='Season name (e.g., Spring 2026)'
        ).pack(side='left', padx=(0, 10))

        ctk.CTkButton(
            new_season_row,
            text='Create Season',
            font=get_font(12),
            fg_color='#4CAF50',
            hover_color='#388E3C',
            height=40,
            width=140,
            command=self._create_season
        ).pack(side='left')

        # Season actions
        season_actions = ctk.CTkFrame(season_inner, fg_color='transparent')
        season_actions.pack(fill='x', pady=10)

        ctk.CTkButton(
            season_actions,
            text='Switch Season',
            font=get_font(11),
            fg_color='#3d5a80',
            hover_color='#2d4a70',
            height=35,
            width=120,
            command=self._switch_season
        ).pack(side='left', padx=(0, 5))

        ctk.CTkButton(
            season_actions,
            text='End Current Season',
            font=get_font(11),
            fg_color='#c44536',
            hover_color='#a43526',
            height=35,
            width=150,
            command=self._end_season
        ).pack(side='left', padx=5)

        # ========== Data Management Section ==========
        self._create_section(content, 'Data Management')

        data_card = ctk.CTkFrame(content, fg_color='#252540', corner_radius=15)
        data_card.pack(fill='x', pady=10)

        data_inner = ctk.CTkFrame(data_card, fg_color='transparent')
        data_inner.pack(fill='x', padx=20, pady=15)

        # New Pool Night button
        ctk.CTkLabel(
            data_inner,
            text='Pool Night',
            font=get_font(13, 'bold')
        ).pack(anchor='w')

        ctk.CTkButton(
            data_inner,
            text='New Pool Night',
            font=get_font(12),
            fg_color='#c44536',
            hover_color='#a43526',
            height=40,
            command=self._new_pool_night
        ).pack(anchor='w', pady=(5, 15))

        # Matches section
        ctk.CTkLabel(
            data_inner,
            text='Match History',
            font=get_font(13, 'bold')
        ).pack(anchor='w')

        matches_btns = ctk.CTkFrame(data_inner, fg_color='transparent')
        matches_btns.pack(fill='x', pady=5)

        ctk.CTkButton(
            matches_btns,
            text='Save Matches',
            font=get_font(11),
            fg_color='#3d5a80',
            hover_color='#2d4a70',
            height=35,
            width=130,
            command=self._save_matches
        ).pack(side='left', padx=(0, 5))

        ctk.CTkButton(
            matches_btns,
            text='Load Matches',
            font=get_font(11),
            fg_color='#3d5a80',
            hover_color='#2d4a70',
            height=35,
            width=130,
            command=self._load_matches
        ).pack(side='left', padx=5)

        # Players section
        ctk.CTkLabel(
            data_inner,
            text='Player Data',
            font=get_font(13, 'bold')
        ).pack(anchor='w', pady=(15, 0))

        players_btns = ctk.CTkFrame(data_inner, fg_color='transparent')
        players_btns.pack(fill='x', pady=5)

        ctk.CTkButton(
            players_btns,
            text='Export Players',
            font=get_font(11),
            fg_color='#6b4e8a',
            hover_color='#5b3e7a',
            height=35,
            width=130,
            command=self._export_players
        ).pack(side='left', padx=(0, 5))

        ctk.CTkButton(
            players_btns,
            text='Import Players',
            font=get_font(11),
            fg_color='#6b4e8a',
            hover_color='#5b3e7a',
            height=35,
            width=130,
            command=self._import_players
        ).pack(side='left', padx=5)

        # Excel Import section
        ctk.CTkFrame(data_inner, height=1, fg_color='#444444').pack(fill='x', pady=15)

        ctk.CTkLabel(
            data_inner,
            text='Excel Import',
            font=get_font(13, 'bold')
        ).pack(anchor='w')

        ctk.CTkLabel(
            data_inner,
            text='Import players, pairs, matchups, and scores from the master Excel scoresheet.',
            font=get_font(11),
            text_color='#aaaaaa'
        ).pack(anchor='w', pady=(2, 8))

        ctk.CTkButton(
            data_inner,
            text='Import Excel Workbook',
            font=get_font(11),
            fg_color='#2d7a3e',
            hover_color='#1a5f2a',
            height=35,
            width=200,
            command=self._import_excel_workbook
        ).pack(anchor='w')

        # Separator
        ctk.CTkFrame(data_inner, height=1, fg_color='#444444').pack(fill='x', pady=15)

        # Auto backup toggle
        ctk.CTkLabel(
            data_inner,
            text='Database Backup',
            font=get_font(13, 'bold')
        ).pack(anchor='w')

        backup_toggle = ctk.CTkFrame(data_inner, fg_color='transparent')
        backup_toggle.pack(fill='x', pady=5)

        auto_backup = self.db.get_setting('auto_backup', 'true') == 'true'
        self.auto_backup_var = ctk.BooleanVar(value=auto_backup)

        ctk.CTkLabel(
            backup_toggle,
            text='Auto-backup on exit',
            font=get_font(12)
        ).pack(side='left')

        ctk.CTkSwitch(
            backup_toggle,
            text='',
            variable=self.auto_backup_var,
            command=lambda: self.db.set_setting('auto_backup', str(self.auto_backup_var.get()).lower()),
            fg_color='#333333',
            progress_color='#4CAF50'
        ).pack(side='right')

        # Backup buttons
        backup_btns = ctk.CTkFrame(data_inner, fg_color='transparent')
        backup_btns.pack(fill='x', pady=10)

        ctk.CTkButton(
            backup_btns,
            text='Create Backup',
            font=get_font(11),
            fg_color='#3d5a80',
            hover_color='#2d4a70',
            height=35,
            command=self._create_backup
        ).pack(side='left', padx=(0, 5))

        ctk.CTkButton(
            backup_btns,
            text='Restore Backup',
            font=get_font(11),
            fg_color='#6b4e8a',
            hover_color='#5b3e7a',
            height=35,
            command=self._restore_backup
        ).pack(side='left', padx=5)

        ctk.CTkButton(
            backup_btns,
            text='Open Folder',
            font=get_font(11),
            fg_color='#555555',
            hover_color='#444444',
            height=35,
            command=self._open_data_folder
        ).pack(side='left', padx=5)

        # Last backup info
        last_backup = self.db.get_setting('last_backup', 'Never')
        self.backup_label = ctk.CTkLabel(
            data_inner,
            text=f'Last backup: {last_backup}',
            font=get_font(11),
            text_color='#888888'
        )
        self.backup_label.pack(anchor='w')

        # ========== About Section ==========
        self._create_section(content, 'About')

        about_card = ctk.CTkFrame(content, fg_color='#252540', corner_radius=15)
        about_card.pack(fill='x', pady=10)

        about_inner = ctk.CTkFrame(about_card, fg_color='transparent')
        about_inner.pack(fill='x', padx=20, pady=15)

        ctk.CTkLabel(
            about_inner,
            text='EcoPOOL League Manager',
            font=get_font(18, 'bold')
        ).pack(anchor='w')

        ctk.CTkLabel(
            about_inner,
            text='Version 3.0',
            font=get_font(12),
            text_color='#888888'
        ).pack(anchor='w')

        ctk.CTkLabel(
            about_inner,
            text='Built for the WVU EcoCAR Team',
            font=get_font(12),
            text_color='#888888'
        ).pack(anchor='w', pady=(10, 0))

        ctk.CTkLabel(
            about_inner,
            text='Features: Achievements, Statistics, Venmo Integration & more!',
            font=get_font(11),
            text_color='#666666'
        ).pack(anchor='w', pady=(5, 0))

    def _create_section(self, parent, title: str):
        """Create a section header."""
        ctk.CTkLabel(
            parent,
            text=title,
            font=get_font(16, 'bold')
        ).pack(anchor='w', pady=(20, 5))

    def _new_pool_night(self):
        """Start a new pool night."""
        if self.on_new_pool_night:
            self.on_new_pool_night()
        else:
            # Fallback if no callback provided
            if messagebox.askyesno(
                "New Pool Night",
                "This will clear the current league night setup.\n\n"
                "COMPLETED games will be KEPT for the leaderboard.\n"
                "Only incomplete matches will be removed.\n\n"
                "Continue?"
            ):
                self.db.clear_matches(keep_completed=True)
                messagebox.showinfo("Success", "New pool night started!")
                if self.on_data_change:
                    self.on_data_change()

    def _save_matches(self):
        """Save match history to JSON file."""
        if not self.exporter:
            messagebox.showerror("Error", "Exporter not available")
            return
            
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

    def _load_matches(self):
        """Load match history from JSON file."""
        if not self.exporter:
            messagebox.showerror("Error", "Exporter not available")
            return
            
        filepath = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json")],
            title="Load Match History"
        )
        
        if filepath:
            success, message = self.exporter.import_matches_json(filepath)
            if success:
                messagebox.showinfo("Success", message)
                if self.on_data_change:
                    self.on_data_change()
            else:
                messagebox.showerror("Error", message)

    def _export_players(self):
        """Export player database to JSON file."""
        if not self.exporter:
            messagebox.showerror("Error", "Exporter not available")
            return
            
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

    def _import_players(self):
        """Import players from JSON file."""
        if not self.exporter:
            messagebox.showerror("Error", "Exporter not available")
            return
            
        filepath = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json")],
            title="Import Players"
        )
        
        if filepath:
            success, message = self.exporter.import_players_json(filepath)
            if success:
                messagebox.showinfo("Success", message)
                if self.on_data_change:
                    self.on_data_change()
            else:
                messagebox.showerror("Error", message)

    def _import_excel_workbook(self):
        """Import data from an Excel workbook."""
        filepath = filedialog.askopenfilename(
            filetypes=[("Excel files", "*.xlsx *.xls")],
            title="Import Excel Workbook"
        )
        if filepath:
            importer = ExcelImporter(self.db)
            success, message = importer.import_workbook(filepath)
            if success:
                messagebox.showinfo("Success", message)
                if self.on_data_change:
                    self.on_data_change()
            else:
                messagebox.showerror("Error", message)

    def _save_venmo(self):
        """Save organizer Venmo username."""
        username = self.venmo_var.get().strip().lstrip('@')
        self.db.set_setting('organizer_venmo', username)
        messagebox.showinfo("Saved", f"Organizer Venmo saved: @{username}")

    def _save_buyin(self):
        """Save default buy-in amount."""
        try:
            amount = float(self.buyin_var.get())
            self.db.set_setting('default_buyin', str(amount))
            messagebox.showinfo("Saved", f"Default buy-in saved: ${amount:.2f}")
        except ValueError:
            messagebox.showerror("Error", "Invalid amount")

    def _change_manager_password(self):
        """Change manager password for web interface."""
        new_password = self.manager_password_var.get().strip()
        
        if not new_password:
            messagebox.showerror("Error", "Password cannot be empty")
            return
        
        if len(new_password) < 4:
            messagebox.showerror("Error", "Password must be at least 4 characters")
            return
        
        # Confirm password change
        if messagebox.askyesno(
            "Confirm Password Change",
            "Are you sure you want to change the manager password?\n\n"
            "This will affect access to manager mode on the web interface."
        ):
            # Hash the password before storing
            hashed_password = _hash_credential(new_password)
            self.db.set_setting('manager_password', hashed_password)
            self.manager_password_var.set('')
            self.password_status_label.configure(text='Current status: Set')
            messagebox.showinfo("Success", "Manager password has been changed successfully")

    def _change_payment_pin(self):
        """Change payment portal PIN for web interface."""
        new_pin = self.payment_pin_var.get().strip()
        
        if not new_pin:
            messagebox.showerror("Error", "PIN cannot be empty")
            return
        
        if len(new_pin) < 4:
            messagebox.showerror("Error", "PIN must be at least 4 characters")
            return
        
        # Confirm PIN change
        if messagebox.askyesno(
            "Confirm PIN Change",
            "Are you sure you want to change the payment portal PIN?\n\n"
            "This will affect access to the payment admin portal on the web interface."
        ):
            # Hash the PIN before storing
            hashed_pin = _hash_credential(new_pin)
            self.db.set_setting('payment_portal_pin', hashed_pin)
            self.payment_pin_var.set('')
            self.pin_status_label.configure(text='Current status: Set')
            messagebox.showinfo("Success", "Payment portal PIN has been changed successfully")

    def _save_ngrok_enabled(self):
        """Save ngrok enabled setting."""
        enabled = self.ngrok_enabled_var.get()
        self.db.set_setting('ngrok_enabled', str(enabled).lower())

    def _save_ngrok_token(self):
        """Save ngrok auth token."""
        token = self.ngrok_token_var.get().strip()
        self.db.set_setting('ngrok_auth_token', token)
        if token:
            messagebox.showinfo("Saved", "Ngrok auth token saved")
        else:
            messagebox.showinfo("Cleared", "Ngrok auth token cleared")

    def _save_ngrok_domain(self):
        """Save ngrok static domain."""
        domain = self.ngrok_domain_var.get().strip()
        # Clean up domain format
        if domain.startswith('https://'):
            domain = domain[8:]
        elif domain.startswith('http://'):
            domain = domain[7:]
        # Remove trailing slashes
        domain = domain.rstrip('/')

        self.db.set_setting('ngrok_static_domain', domain)
        self.ngrok_domain_var.set(domain)

        if domain:
            if '.' not in domain:
                messagebox.showwarning(
                    "Warning",
                    "Domain format looks invalid.\n"
                    "Expected format: yourname.ngrok-free.app"
                )
            else:
                messagebox.showinfo(
                    "Saved",
                    f"Static domain saved: {domain}\n\n"
                    "Make sure you have also set your auth token.\n"
                    "Restart the server for changes to take effect."
                )
        else:
            messagebox.showinfo("Cleared", "Static domain cleared")

    def _save_ai_names_enabled(self):
        """Save AI names enabled setting."""
        enabled = self.ai_names_enabled_var.get()
        self.db.set_setting('ai_names_enabled', str(enabled).lower())

    def _save_ai_api_key(self):
        """Save Anthropic API key."""
        key = self.ai_api_key_var.get().strip()
        self.db.set_setting('anthropic_api_key', key)
        if key:
            messagebox.showinfo("Saved", "Anthropic API key saved")
        else:
            messagebox.showinfo("Cleared", "Anthropic API key cleared")

    def _create_backup(self):
        """Create a database backup."""
        filepath = filedialog.asksaveasfilename(
            defaultextension='.db',
            filetypes=[('Database files', '*.db'), ('All files', '*.*')],
            title='Save Backup',
            initialfile=f'ecopool_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
        )

        if filepath:
            try:
                shutil.copy2(self.db.db_path, filepath)
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M')
                self.db.set_setting('last_backup', timestamp)
                self.backup_label.configure(text=f'Last backup: {timestamp}')
                messagebox.showinfo("Success", f"Backup saved to:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create backup:\n{str(e)}")

    def _restore_backup(self):
        """Restore from a backup file."""
        filepath = filedialog.askopenfilename(
            filetypes=[('Database files', '*.db'), ('All files', '*.*')],
            title='Select Backup File'
        )

        if filepath:
            if messagebox.askyesno(
                "Confirm Restore",
                "This will replace all current data with the backup.\n\n"
                "Are you sure you want to continue?"
            ):
                try:
                    # Create backup of current first
                    backup_path = self.db.db_path + '.before_restore'
                    shutil.copy2(self.db.db_path, backup_path)

                    # Restore
                    shutil.copy2(filepath, self.db.db_path)
                    messagebox.showinfo(
                        "Success",
                        "Backup restored successfully!\n\n"
                        "Please restart the application for changes to take effect."
                    )
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to restore backup:\n{str(e)}")

    def _open_data_folder(self):
        """Open the folder containing the database."""
        folder = os.path.dirname(self.db.db_path)
        try:
            os.startfile(folder)
        except:
            messagebox.showinfo("Data Location", f"Database location:\n{self.db.db_path}")

    def _create_season(self):
        """Create a new season."""
        name = self.new_season_var.get().strip()
        
        if not name:
            messagebox.showerror("Error", "Please enter a season name")
            return
        
        # Confirm creation
        if messagebox.askyesno(
            "Create Season",
            f"Create new season '{name}'?\n\n"
            "This will become the active season."
        ):
            try:
                start_date = datetime.now().strftime('%Y-%m-%d')
                season_id = self.db.create_season(name, start_date)
                self.db.set_active_season(season_id)
                
                # Update display
                self.current_season_label.configure(text=name, text_color='#4CAF50')
                self.new_season_var.set('')
                
                messagebox.showinfo("Success", f"Season '{name}' created and set as active!")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to create season:\n{str(e)}")

    def _switch_season(self):
        """Switch to a different season."""
        seasons = self.db.get_all_seasons()
        
        if not seasons:
            messagebox.showinfo("No Seasons", "No seasons found. Create a season first.")
            return
        
        # Create a dialog to select season
        dialog = ctk.CTkToplevel(self)
        dialog.title('Switch Season')
        dialog.geometry('400x450')
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        
        # Center
        dialog.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() // 2) - 200
        y = self.winfo_rooty() + (self.winfo_height() // 2) - 225
        dialog.geometry(f'+{x}+{y}')
        
        ctk.CTkLabel(
            dialog,
            text='Select Season',
            font=get_font(18, 'bold')
        ).pack(pady=(20, 10))
        
        # Scrollable list of seasons
        seasons_frame = ctk.CTkScrollableFrame(dialog, height=300)
        seasons_frame.pack(fill='x', padx=20, pady=10)
        
        active_season = self.db.get_active_season()
        selected_var = ctk.IntVar(value=active_season.id if active_season else 0)
        
        for season in seasons:
            is_active = active_season and season.id == active_season.id
            status = " (Active)" if is_active else ""
            end_status = " [Ended]" if season.end_date else ""
            
            row = ctk.CTkFrame(seasons_frame, fg_color='transparent')
            row.pack(fill='x', pady=2)
            
            ctk.CTkRadioButton(
                row,
                text=f"{season.name}{status}{end_status}",
                variable=selected_var,
                value=season.id,
                font=get_font(13),
                fg_color='#4CAF50'
            ).pack(side='left', padx=5)
            
            ctk.CTkLabel(
                row,
                text=season.start_date or '',
                font=get_font(10),
                text_color='#888888'
            ).pack(side='right', padx=10)
        
        def do_switch():
            season_id = selected_var.get()
            if season_id:
                self.db.set_active_season(season_id)
                # Find the season name
                for s in seasons:
                    if s.id == season_id:
                        self.current_season_label.configure(text=s.name, text_color='#4CAF50')
                        break
                dialog.destroy()
                messagebox.showinfo("Success", "Active season changed!")
        
        btn_frame = ctk.CTkFrame(dialog, fg_color='transparent')
        btn_frame.pack(pady=15)
        
        ctk.CTkButton(
            btn_frame,
            text='Cancel',
            font=get_font(12),
            fg_color='#555555',
            hover_color='#444444',
            width=100,
            height=35,
            command=dialog.destroy
        ).pack(side='left', padx=10)
        
        ctk.CTkButton(
            btn_frame,
            text='Switch',
            font=get_font(12, 'bold'),
            fg_color='#4CAF50',
            hover_color='#388E3C',
            width=100,
            height=35,
            command=do_switch
        ).pack(side='left', padx=10)

    def _end_season(self):
        """End the current season."""
        active_season = self.db.get_active_season()
        
        if not active_season:
            messagebox.showinfo("No Active Season", "No active season to end.")
            return
        
        if active_season.end_date:
            messagebox.showinfo("Already Ended", f"Season '{active_season.name}' has already ended.")
            return
        
        if messagebox.askyesno(
            "End Season",
            f"End season '{active_season.name}'?\n\n"
            "This will mark the season as complete.\n"
            "All stats and leaderboard data will be preserved.\n\n"
            "You can still create a new season afterwards."
        ):
            try:
                end_date = datetime.now().strftime('%Y-%m-%d')
                self.db.end_season(active_season.id, end_date)
                self.current_season_label.configure(
                    text=f"{active_season.name} (Ended)",
                    text_color='#888888'
                )
                messagebox.showinfo("Success", f"Season '{active_season.name}' has been ended.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to end season:\n{str(e)}")
