"""
EcoPOOL League - Players Management View
Enhanced with profile pictures and animations.
"""

import customtkinter as ctk
from tkinter import messagebox, filedialog
from database import DatabaseManager
from profile_pictures import ProfilePicture, ProfilePictureBrowser
from animations import flash_widget, AnimationManager
from exporter import Exporter
from fonts import get_font


class PlayersView(ctk.CTkFrame):
    def __init__(self, parent, db: DatabaseManager):
        super().__init__(parent, fg_color="transparent")
        self.db = db
        self.exporter = Exporter(db)
        
        self.setup_ui()
        self.load_players()
    
    def setup_ui(self):
        # Header with animation
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=20, pady=(20, 10))
        
        title_label = ctk.CTkLabel(
            header_frame, 
            text="👥 Player Management",
            font=get_font(28, "bold")
        )
        title_label.pack(side="left")
        
        # Button container
        btn_container = ctk.CTkFrame(header_frame, fg_color="transparent")
        btn_container.pack(side="right")
        
        # Import players button
        import_btn = ctk.CTkButton(
            btn_container,
            text="Import",
            font=get_font(13),
            fg_color="#6b4e8a",
            hover_color="#5b3e7a",
            height=40,
            width=80,
            command=self.import_players
        )
        import_btn.pack(side="left", padx=5)
        
        # Clear all players button
        clear_btn = ctk.CTkButton(
            btn_container,
            text="Clear All",
            font=get_font(13),
            fg_color="#c44536",
            hover_color="#a43526",
            height=40,
            width=80,
            command=self.clear_all_players
        )
        clear_btn.pack(side="left", padx=5)
        
        # Bulk add players button
        bulk_btn = ctk.CTkButton(
            btn_container,
            text="+ Bulk Add",
            font=get_font(13),
            fg_color="#3d5a80",
            hover_color="#2d4a70",
            height=40,
            width=100,
            command=self.show_bulk_add_dialog
        )
        bulk_btn.pack(side="left", padx=5)
        
        # Add player button with hover effect
        add_btn = ctk.CTkButton(
            btn_container,
            text="+ Add Player",
            font=get_font(14, "bold"),
            fg_color="#2d7a3e",
            hover_color="#1a5f2a",
            height=40,
            command=self.show_add_dialog
        )
        add_btn.pack(side="left", padx=5)
        
        # Search bar with animation
        search_frame = ctk.CTkFrame(self, fg_color="transparent")
        search_frame.pack(fill="x", padx=20, pady=10)
        
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *args: self.filter_players())
        
        search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="🔍 Search players...",
            textvariable=self.search_var,
            height=40,
            width=300,
            font=get_font(14)
        )
        search_entry.pack(side="left")
        
        # View mode toggle
        view_frame = ctk.CTkFrame(search_frame, fg_color="transparent")
        view_frame.pack(side="right")
        
        self.view_mode = ctk.StringVar(value="list")
        
        ctk.CTkButton(
            view_frame, text="📋", width=40, height=35,
            fg_color="#3d5a80" if self.view_mode.get() == "list" else "#444444",
            command=lambda: self.set_view_mode("list")
        ).pack(side="left", padx=2)
        
        ctk.CTkButton(
            view_frame, text="🃏", width=40, height=35,
            fg_color="#3d5a80" if self.view_mode.get() == "cards" else "#444444",
            command=lambda: self.set_view_mode("cards")
        ).pack(side="left", padx=2)
        
        # Players list container
        self.list_frame = ctk.CTkScrollableFrame(
            self, 
            fg_color="#1a1a2e",
            corner_radius=15
        )
        self.list_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Column headers
        self.headers_frame = ctk.CTkFrame(self.list_frame, fg_color="#2d2d44", corner_radius=10)
        self.headers_frame.pack(fill="x", padx=5, pady=(5, 10))
        
        headers = [("", 60), ("Name", 180), ("Email", 180), ("Venmo", 130), 
                   ("Games", 70), ("Wins", 70), ("Win %", 70), ("Actions", 150)]
        
        for text, width in headers:
            ctk.CTkLabel(
                self.headers_frame,
                text=text,
                font=get_font(12, "bold"),
                width=width,
                anchor="w" if text == "Name" else "center"
            ).pack(side="left", padx=5, pady=8)
        
        self.players_container = ctk.CTkFrame(self.list_frame, fg_color="transparent")
        self.players_container.pack(fill="both", expand=True)
    
    def set_view_mode(self, mode: str):
        """Switch between list and card view."""
        self.view_mode.set(mode)
        self.load_players()
    
    def load_players(self):
        # Clear existing with fade effect
        for widget in self.players_container.winfo_children():
            widget.destroy()
        
        players = self.db.get_all_players()
        
        if not players:
            empty_frame = ctk.CTkFrame(self.players_container, fg_color="transparent")
            empty_frame.pack(expand=True, pady=50)
            
            ctk.CTkLabel(
                empty_frame,
                text="🎱",
                font=get_font(48)
            ).pack()
            
            ctk.CTkLabel(
                empty_frame,
                text="No players yet",
                font=get_font(18, "bold"),
                text_color="#888888"
            ).pack(pady=10)
            
            ctk.CTkLabel(
                empty_frame,
                text="Add your first player to get started!",
                font=get_font(14),
                text_color="#666666"
            ).pack()
            return
        
        if self.view_mode.get() == "cards":
            self._load_card_view(players)
        else:
            self._load_list_view(players)
    
    def _load_list_view(self, players):
        """Load players in list view."""
        for i, player in enumerate(players):
            self.create_player_row(player, i)
    
    def _load_card_view(self, players):
        """Load players in card view."""
        # Create grid of cards
        self.headers_frame.pack_forget()
        
        cards_frame = ctk.CTkFrame(self.players_container, fg_color="transparent")
        cards_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        for i, player in enumerate(players):
            row = i // 4
            col = i % 4
            
            self.create_player_card(cards_frame, player, row, col, i)
    
    def create_player_row(self, player, index: int = 0):
        """Create a player row (optimized - using simple frame for scroll performance)."""
        row = ctk.CTkFrame(
            self.players_container, 
            fg_color="#252540", 
            corner_radius=8, 
            height=60
        )
        row.pack(fill="x", padx=5, pady=3)
        row.pack_propagate(False)
        
        # Profile picture
        pic_frame = ctk.CTkFrame(row, fg_color="transparent", width=60)
        pic_frame.pack(side="left", padx=10, pady=5)
        pic_frame.pack_propagate(False)
        
        profile_pic = ProfilePicture(
            pic_frame, 
            size=45,
            image_path=player.profile_picture,
            player_name=player.name,
            clickable=True,
            on_click=lambda p=player: self.show_picture_browser(p)
        )
        profile_pic.pack(expand=True)
        
        # Name
        ctk.CTkLabel(
            row, text=player.name,
            font=get_font(14, "bold"),
            width=180, anchor="w"
        ).pack(side="left", padx=5, pady=10)
        
        # Email
        email_text = player.email if player.email else "-"
        if len(email_text) > 20:
            email_text = email_text[:18] + "..."
        ctk.CTkLabel(
            row, text=email_text,
            font=get_font(13),
            width=180, anchor="center",
            text_color="#aaaaaa"
        ).pack(side="left", padx=5)
        
        # Venmo
        ctk.CTkLabel(
            row, text=player.venmo or "-",
            font=get_font(13),
            width=130, anchor="center",
            text_color="#aaaaaa"
        ).pack(side="left", padx=5)
        
        # Games
        ctk.CTkLabel(
            row, text=str(player.games_played),
            font=get_font(13),
            width=70, anchor="center"
        ).pack(side="left", padx=5)
        
        # Wins
        ctk.CTkLabel(
            row, text=str(player.games_won),
            font=get_font(13),
            width=70, anchor="center",
            text_color="#4CAF50"
        ).pack(side="left", padx=5)
        
        # Win %
        win_color = "#4CAF50" if player.win_rate >= 50 else "#ff6b6b"
        ctk.CTkLabel(
            row, text=f"{player.win_rate:.0f}%",
            font=get_font(13, "bold"),
            width=70, anchor="center",
            text_color=win_color
        ).pack(side="left", padx=5)
        
        # Action buttons
        actions = ctk.CTkFrame(row, fg_color="transparent", width=150)
        actions.pack(side="left", padx=5)
        
        ctk.CTkButton(
            actions, text="📷", width=35, height=30,
            fg_color="#6b4e8a", hover_color="#5b3e7a",
            command=lambda p=player: self.show_picture_browser(p)
        ).pack(side="left", padx=2)
        
        ctk.CTkButton(
            actions, text="✏️", width=35, height=30,
            fg_color="#3d5a80", hover_color="#2d4a70",
            command=lambda p=player: self.show_edit_dialog(p)
        ).pack(side="left", padx=2)
        
        ctk.CTkButton(
            actions, text="🗑️", width=35, height=30,
            fg_color="#c44536", hover_color="#a43526",
            command=lambda p=player: self.delete_player(p)
        ).pack(side="left", padx=2)
    
    def create_player_card(self, parent, player, row: int, col: int, index: int):
        """Create a player card for grid view (optimized - simple frame for scroll performance)."""
        card = ctk.CTkFrame(
            parent,
            fg_color="#252540",
            corner_radius=15,
            width=220,
            height=200
        )
        card.grid(row=row, column=col, padx=10, pady=10)
        card.pack_propagate(False)
        
        # Profile picture (larger for card view)
        pic_frame = ctk.CTkFrame(card, fg_color="transparent")
        pic_frame.pack(pady=(20, 10))
        
        profile_pic = ProfilePicture(
            pic_frame,
            size=70,
            image_path=player.profile_picture,
            player_name=player.name,
            clickable=True,
            on_click=lambda p=player: self.show_picture_browser(p)
        )
        profile_pic.pack()
        
        # Name
        ctk.CTkLabel(
            card,
            text=player.name,
            font=get_font(16, "bold")
        ).pack(pady=5)
        
        # Stats row
        stats_frame = ctk.CTkFrame(card, fg_color="transparent")
        stats_frame.pack(pady=5)
        
        win_color = "#4CAF50" if player.win_rate >= 50 else "#ff6b6b"
        
        ctk.CTkLabel(
            stats_frame,
            text=f"🎱 {player.games_played}",
            font=get_font(12),
            text_color="#888888"
        ).pack(side="left", padx=8)
        
        ctk.CTkLabel(
            stats_frame,
            text=f"🏆 {player.games_won}",
            font=get_font(12),
            text_color="#4CAF50"
        ).pack(side="left", padx=8)
        
        ctk.CTkLabel(
            stats_frame,
            text=f"{player.win_rate:.0f}%",
            font=get_font(12, "bold"),
            text_color=win_color
        ).pack(side="left", padx=8)
        
        # Action buttons
        actions = ctk.CTkFrame(card, fg_color="transparent")
        actions.pack(pady=10)
        
        ctk.CTkButton(
            actions, text="✏️", width=50, height=30,
            fg_color="#3d5a80", hover_color="#2d4a70",
            command=lambda p=player: self.show_edit_dialog(p)
        ).pack(side="left", padx=3)
        
        ctk.CTkButton(
            actions, text="🗑️", width=50, height=30,
            fg_color="#c44536", hover_color="#a43526",
            command=lambda p=player: self.delete_player(p)
        ).pack(side="left", padx=3)
    
    def filter_players(self):
        search_text = self.search_var.get().lower()
        
        for widget in self.players_container.winfo_children():
            widget.destroy()
        
        players = self.db.get_all_players()
        
        for player in players:
            if search_text in player.name.lower() or search_text in (player.email or "").lower():
                self.create_player_row(player)
    
    def show_picture_browser(self, player):
        """Show the profile picture browser for a player."""
        def on_select(picture_path):
            self.db.update_player_picture(player.id, picture_path)
            self.load_players()
            flash_widget(self.players_container, "#4CAF50", times=2)
        
        ProfilePictureBrowser(
            self,
            player_name=player.name,
            current_picture=player.profile_picture,
            on_select=on_select
        )
    
    def show_add_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Add New Player")
        dialog.geometry("500x580")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        
        # Center dialog
        dialog.update_idletasks()
        x = self.winfo_toplevel().winfo_x() + (self.winfo_toplevel().winfo_width() // 2) - 250
        y = self.winfo_toplevel().winfo_y() + (self.winfo_toplevel().winfo_height() // 2) - 290
        dialog.geometry(f"+{x}+{y}")
        
        ctk.CTkLabel(
            dialog, text="Add New Player",
            font=get_font(22, "bold")
        ).pack(pady=20)
        
        # Profile picture preview
        pic_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        pic_frame.pack(pady=10)
        
        selected_picture = {"path": ""}
        
        preview_pic = ProfilePicture(
            pic_frame, size=80,
            player_name="New Player"
        )
        preview_pic.pack()
        
        def choose_picture():
            def on_select(path):
                selected_picture["path"] = path
                preview_pic.update_picture(path)
            
            ProfilePictureBrowser(
                dialog,
                player_name=name_entry.get() or "New Player",
                on_select=on_select
            )
        
        ctk.CTkButton(
            pic_frame, text="Choose Avatar",
            font=get_font(12),
            height=30, width=120,
            fg_color="#6b4e8a", hover_color="#5b3e7a",
            command=choose_picture
        ).pack(pady=10)
        
        form = ctk.CTkFrame(dialog, fg_color="transparent")
        form.pack(fill="x", padx=40)
        
        ctk.CTkLabel(form, text="Name *", font=get_font(14)).pack(anchor="w", pady=(10, 2))
        name_entry = ctk.CTkEntry(form, height=40, font=get_font(14))
        name_entry.pack(fill="x")
        
        ctk.CTkLabel(form, text="Email", font=get_font(14)).pack(anchor="w", pady=(15, 2))
        email_entry = ctk.CTkEntry(form, height=40, font=get_font(14))
        email_entry.pack(fill="x")
        
        ctk.CTkLabel(form, text="Venmo", font=get_font(14)).pack(anchor="w", pady=(15, 2))
        venmo_entry = ctk.CTkEntry(form, height=40, font=get_font(14), 
                                   placeholder_text="@username")
        venmo_entry.pack(fill="x")
        
        def save():
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror("Error", "Name is required")
                return
            try:
                self.db.add_player(
                    name, 
                    email_entry.get().strip(), 
                    venmo_entry.get().strip(),
                    selected_picture["path"]
                )
                dialog.destroy()
                self.load_players()
                # Flash animation
                flash_widget(self.players_container, "#4CAF50", times=2)
            except Exception as e:
                if "UNIQUE" in str(e):
                    messagebox.showerror("Error", "A player with this name already exists")
                else:
                    messagebox.showerror("Error", str(e))
        
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=25)
        
        ctk.CTkButton(
            btn_frame, text="Cancel", width=100, height=40,
            fg_color="#555555", hover_color="#444444",
            command=dialog.destroy
        ).pack(side="left", padx=10)
        
        ctk.CTkButton(
            btn_frame, text="Save Player", width=120, height=40,
            fg_color="#2d7a3e", hover_color="#1a5f2a",
            command=save
        ).pack(side="left", padx=10)
    
    def show_bulk_add_dialog(self):
        """Show dialog for adding multiple players at once."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Bulk Add Players")
        dialog.geometry("550x550")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        
        # Center dialog
        dialog.update_idletasks()
        x = self.winfo_toplevel().winfo_x() + (self.winfo_toplevel().winfo_width() // 2) - 275
        y = self.winfo_toplevel().winfo_y() + (self.winfo_toplevel().winfo_height() // 2) - 275
        dialog.geometry(f"+{x}+{y}")
        
        ctk.CTkLabel(
            dialog, text="Bulk Add Players",
            font=get_font(22, "bold")
        ).pack(pady=(20, 5))
        
        ctk.CTkLabel(
            dialog, text="Enter one name per line",
            font=get_font(14),
            text_color="#888888"
        ).pack(pady=(0, 15))
        
        # Text area for names
        text_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        text_frame.pack(fill="both", expand=True, padx=30, pady=10)
        
        names_textbox = ctk.CTkTextbox(
            text_frame,
            font=get_font(14),
            fg_color="#252540",
            corner_radius=10,
            height=280
        )
        names_textbox.pack(fill="both", expand=True)
        names_textbox.insert("1.0", "# Example:\n# John Smith\n# Jane Doe\n# Mike Johnson\n")
        
        # Info label
        self.bulk_info_label = ctk.CTkLabel(
            dialog,
            text="",
            font=get_font(12),
            text_color="#888888"
        )
        self.bulk_info_label.pack(pady=5)
        
        def update_count(*args):
            text = names_textbox.get("1.0", "end-1c")
            lines = [line.strip() for line in text.split('\n') 
                    if line.strip() and not line.strip().startswith('#')]
            count = len(lines)
            self.bulk_info_label.configure(text=f"{count} player{'s' if count != 1 else ''} to add")
        
        # Bind text change to update count
        names_textbox.bind("<KeyRelease>", update_count)
        update_count()
        
        def save_bulk():
            text = names_textbox.get("1.0", "end-1c")
            names = [line.strip() for line in text.split('\n') 
                    if line.strip() and not line.strip().startswith('#')]
            
            if not names:
                messagebox.showerror("Error", "No names entered.\n\nEnter at least one name (lines starting with # are ignored).")
                return
            
            added = 0
            skipped = []
            
            for name in names:
                try:
                    self.db.add_player(name, "", "", "")
                    added += 1
                except Exception as e:
                    if "UNIQUE" in str(e):
                        skipped.append(f"{name} (already exists)")
                    else:
                        skipped.append(f"{name} ({str(e)})")
            
            dialog.destroy()
            self.load_players()
            
            # Show results
            if added > 0:
                flash_widget(self.players_container, "#4CAF50", times=2)
            
            result_msg = f"Successfully added {added} player{'s' if added != 1 else ''}!"
            if skipped:
                result_msg += f"\n\nSkipped {len(skipped)}:\n" + "\n".join(skipped[:10])
                if len(skipped) > 10:
                    result_msg += f"\n... and {len(skipped) - 10} more"
            
            if added > 0:
                messagebox.showinfo("Bulk Add Complete", result_msg)
            else:
                messagebox.showwarning("No Players Added", result_msg)
        
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=20)
        
        ctk.CTkButton(
            btn_frame, text="Cancel", width=100, height=40,
            fg_color="#555555", hover_color="#444444",
            command=dialog.destroy
        ).pack(side="left", padx=10)
        
        ctk.CTkButton(
            btn_frame, text="Add All Players", width=140, height=40,
            fg_color="#2d7a3e", hover_color="#1a5f2a",
            command=save_bulk
        ).pack(side="left", padx=10)
    
    def show_edit_dialog(self, player):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Edit Player")
        dialog.geometry("500x580")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        
        dialog.update_idletasks()
        x = self.winfo_toplevel().winfo_x() + (self.winfo_toplevel().winfo_width() // 2) - 250
        y = self.winfo_toplevel().winfo_y() + (self.winfo_toplevel().winfo_height() // 2) - 290
        dialog.geometry(f"+{x}+{y}")
        
        ctk.CTkLabel(
            dialog, text="Edit Player",
            font=get_font(22, "bold")
        ).pack(pady=20)
        
        # Profile picture preview
        pic_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        pic_frame.pack(pady=10)
        
        selected_picture = {"path": player.profile_picture}
        
        preview_pic = ProfilePicture(
            pic_frame, size=80,
            image_path=player.profile_picture,
            player_name=player.name
        )
        preview_pic.pack()
        
        def choose_picture():
            def on_select(path):
                selected_picture["path"] = path
                preview_pic.update_picture(path)
            
            ProfilePictureBrowser(
                dialog,
                player_name=player.name,
                current_picture=selected_picture["path"],
                on_select=on_select
            )
        
        ctk.CTkButton(
            pic_frame, text="Change Avatar",
            font=get_font(12),
            height=30, width=120,
            fg_color="#6b4e8a", hover_color="#5b3e7a",
            command=choose_picture
        ).pack(pady=10)
        
        form = ctk.CTkFrame(dialog, fg_color="transparent")
        form.pack(fill="x", padx=40)
        
        ctk.CTkLabel(form, text="Name *", font=get_font(14)).pack(anchor="w", pady=(10, 2))
        name_entry = ctk.CTkEntry(form, height=40, font=get_font(14))
        name_entry.insert(0, player.name)
        name_entry.pack(fill="x")
        
        ctk.CTkLabel(form, text="Email", font=get_font(14)).pack(anchor="w", pady=(15, 2))
        email_entry = ctk.CTkEntry(form, height=40, font=get_font(14))
        email_entry.insert(0, player.email or "")
        email_entry.pack(fill="x")
        
        ctk.CTkLabel(form, text="Venmo", font=get_font(14)).pack(anchor="w", pady=(15, 2))
        venmo_entry = ctk.CTkEntry(form, height=40, font=get_font(14))
        venmo_entry.insert(0, player.venmo or "")
        venmo_entry.pack(fill="x")
        
        def save():
            name = name_entry.get().strip()
            if not name:
                messagebox.showerror("Error", "Name is required")
                return
            try:
                self.db.update_player(
                    player.id, 
                    name, 
                    email_entry.get().strip(), 
                    venmo_entry.get().strip(),
                    selected_picture["path"]
                )
                dialog.destroy()
                self.load_players()
            except Exception as e:
                messagebox.showerror("Error", str(e))
        
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=25)
        
        ctk.CTkButton(
            btn_frame, text="Cancel", width=100, height=40,
            fg_color="#555555", hover_color="#444444",
            command=dialog.destroy
        ).pack(side="left", padx=10)
        
        ctk.CTkButton(
            btn_frame, text="Save Changes", width=120, height=40,
            fg_color="#2d7a3e", hover_color="#1a5f2a",
            command=save
        ).pack(side="left", padx=10)
    
    def delete_player(self, player):
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to remove {player.name}?"):
            self.db.delete_player(player.id)
            self.load_players()
    
    def clear_all_players(self):
        """Clear all players from the database."""
        players = self.db.get_all_players()
        if not players:
            messagebox.showinfo("No Players", "There are no players to remove.")
            return
        
        if messagebox.askyesno(
            "Clear All Players",
            f"Are you sure you want to remove ALL {len(players)} players?\n\n"
            "This will also delete all match history!\n\n"
            "This action cannot be undone!",
            icon="warning"
        ):
            # Second confirmation for safety
            if messagebox.askyesno(
                "Final Confirmation",
                "This will permanently delete all player data and match history.\n\n"
                "Are you absolutely sure?",
                icon="warning"
            ):
                self.db.clear_all_players()
                self.load_players()
                messagebox.showinfo("Success", "All players and match data have been removed.")
    
    def import_players(self):
        """Import players from a JSON file."""
        filepath = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json")],
            title="Import Players"
        )
        
        if filepath:
            success, message = self.exporter.import_players_json(filepath)
            if success:
                self.load_players()
                flash_widget(self.players_container, "#4CAF50", times=2)
                messagebox.showinfo("Success", message)
            else:
                messagebox.showerror("Error", message)
