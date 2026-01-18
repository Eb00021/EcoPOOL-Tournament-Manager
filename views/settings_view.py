"""
EcoPOOL League - Settings View
Application settings including themes and preferences.
"""

import customtkinter as ctk
from tkinter import messagebox, filedialog
import os
import shutil
from datetime import datetime
from database import DatabaseManager
from fonts import get_font


class SettingsView(ctk.CTkFrame):
    """View for application settings."""

    def __init__(self, parent, db: DatabaseManager):
        super().__init__(parent, fg_color='transparent')
        self.db = db

        self.setup_ui()

    def setup_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color='transparent')
        header.pack(fill='x', padx=20, pady=(20, 10))

        ctk.CTkLabel(
            header,
            text='⚙️ Settings',
            font=get_font(28, 'bold')
        ).pack(side='left')

        # Scrollable content
        content = ctk.CTkScrollableFrame(self, fg_color='transparent')
        content.pack(fill='both', expand=True, padx=20, pady=10)

        # ========== Venmo Section ==========
        self._create_section(content, '💳 Venmo Settings')

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
        self._create_section(content, '🔐 Manager Password')

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

        # ========== Data Management Section ==========
        self._create_section(content, '💾 Data Management')

        data_card = ctk.CTkFrame(content, fg_color='#252540', corner_radius=15)
        data_card.pack(fill='x', pady=10)

        data_inner = ctk.CTkFrame(data_card, fg_color='transparent')
        data_inner.pack(fill='x', padx=20, pady=15)

        # Auto backup
        backup_toggle = ctk.CTkFrame(data_inner, fg_color='transparent')
        backup_toggle.pack(fill='x', pady=5)

        auto_backup = self.db.get_setting('auto_backup', 'true') == 'true'
        self.auto_backup_var = ctk.BooleanVar(value=auto_backup)

        ctk.CTkLabel(
            backup_toggle,
            text='Auto-backup on exit',
            font=get_font(13)
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
        backup_btns.pack(fill='x', pady=15)

        ctk.CTkButton(
            backup_btns,
            text='📥 Create Backup',
            font=get_font(12),
            fg_color='#3d5a80',
            hover_color='#2d4a70',
            height=40,
            command=self._create_backup
        ).pack(side='left', padx=5)

        ctk.CTkButton(
            backup_btns,
            text='📤 Restore Backup',
            font=get_font(12),
            fg_color='#6b4e8a',
            hover_color='#5b3e7a',
            height=40,
            command=self._restore_backup
        ).pack(side='left', padx=5)

        ctk.CTkButton(
            backup_btns,
            text='📁 Open Data Folder',
            font=get_font(12),
            fg_color='#555555',
            hover_color='#444444',
            height=40,
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
        self._create_section(content, 'ℹ️ About')

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
            text='Version 2.0',
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
            self.db.set_setting('manager_password', new_password)
            self.manager_password_var.set('')
            self.password_status_label.configure(text='Current status: Set')
            messagebox.showinfo("Success", "Manager password has been changed successfully")

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
