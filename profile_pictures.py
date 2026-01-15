"""
EcoPOOL League - Profile Pictures Module
Handles profile picture selection, avatars, and image management.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import Canvas, filedialog
from PIL import Image, ImageTk, ImageDraw
import os
import shutil
from typing import Optional, Callable
import hashlib
from fonts import get_font


# Default avatar colors for generating unique avatars
AVATAR_COLORS = [
    ("#FF6B6B", "#C62828"),  # Red
    ("#4ECDC4", "#00897B"),  # Teal
    ("#45B7D1", "#0277BD"),  # Blue
    ("#96CEB4", "#388E3C"),  # Green
    ("#FFEAA7", "#F9A825"),  # Yellow
    ("#DDA0DD", "#7B1FA2"),  # Purple
    ("#F8B500", "#E65100"),  # Orange
    ("#85C1E9", "#1565C0"),  # Light Blue
    ("#BB8FCE", "#6A1B9A"),  # Violet
    ("#98D8C8", "#00695C"),  # Mint
    ("#F7DC6F", "#FBC02D"),  # Gold
    ("#FF69B4", "#C2185B"),  # Pink
]

# Pool-themed avatar icons (emoji-style)
POOL_AVATARS = [
    "8️⃣",   # 8-ball
    "🎱",   # Pool balls
    "🏆",   # Trophy
    "⭐",   # Star
    "🔥",   # Fire
    "💎",   # Diamond
    "🎯",   # Target
    "👑",   # Crown
    "🦅",   # Eagle
    "🐺",   # Wolf
    "🦁",   # Lion
    "🐉",   # Dragon
]


class AvatarGenerator:
    """Generates unique avatars based on player name."""
    
    @staticmethod
    def get_color_for_name(name: str) -> tuple:
        """Get a consistent color pair for a name."""
        hash_val = int(hashlib.md5(name.encode()).hexdigest(), 16)
        return AVATAR_COLORS[hash_val % len(AVATAR_COLORS)]
    
    @staticmethod
    def get_initials(name: str) -> str:
        """Get initials from a name (up to 2 characters)."""
        parts = name.strip().split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[-1][0]).upper()
        elif len(parts) == 1 and len(parts[0]) >= 2:
            return parts[0][:2].upper()
        elif len(parts) == 1:
            return parts[0][0].upper()
        return "?"
    
    @staticmethod
    def create_avatar_canvas(parent, name: str, size: int = 50) -> Canvas:
        """Create a canvas with an avatar based on name."""
        colors = AvatarGenerator.get_color_for_name(name)
        initials = AvatarGenerator.get_initials(name)
        
        # Get parent background color or use default
        try:
            parent_bg = parent.cget("fg_color")
            if isinstance(parent_bg, tuple):
                parent_bg = parent_bg[1]  # Dark mode color
            if not parent_bg or parent_bg == "transparent":
                parent_bg = "#252540"
        except (tk.TclError, AttributeError):
            parent_bg = "#252540"
        
        canvas = Canvas(parent, width=size, height=size, 
                       bg=parent_bg, highlightthickness=0)
        
        # Draw circular background with gradient effect
        padding = 2
        
        # Outer circle (darker)
        canvas.create_oval(
            padding, padding,
            size - padding, size - padding,
            fill=colors[1], outline=""
        )
        
        # Inner circle (lighter)
        inner_padding = size * 0.1
        canvas.create_oval(
            inner_padding, inner_padding,
            size - inner_padding, size - inner_padding,
            fill=colors[0], outline=""
        )
        
        # Initials text
        font_size = int(size * 0.35)
        canvas.create_text(
            size // 2, size // 2,
            text=initials,
            font=("Arial", font_size, "bold"),
            fill="white"
        )
        
        return canvas


class ProfilePicture(ctk.CTkFrame):
    """A profile picture widget that can display images or generated avatars."""
    
    def __init__(self, parent, size: int = 50, image_path: str = "",
                 player_name: str = "", clickable: bool = False,
                 on_click: Optional[Callable] = None):
        super().__init__(parent, fg_color="transparent", 
                        width=size, height=size)
        self.pack_propagate(False)
        
        self.size = size
        self.image_path = image_path
        self.player_name = player_name
        self.on_click = on_click
        self.clickable = clickable
        
        self._image = None  # Keep reference to prevent garbage collection
        self._create_display()
        
        if clickable:
            self.bind("<Button-1>", self._handle_click)
            self.bind("<Enter>", self._on_enter)
            self.bind("<Leave>", self._on_leave)
    
    def _create_display(self):
        """Create the appropriate display (image or avatar)."""
        # Clear existing
        for widget in self.winfo_children():
            widget.destroy()
        
        if self.image_path and os.path.exists(self.image_path):
            self._display_image()
        elif self.image_path and self.image_path.startswith("emoji:"):
            self._display_emoji(self.image_path[6:])
        else:
            self._display_avatar()
    
    def _get_bg_color(self):
        """Get an appropriate background color."""
        try:
            parent_bg = self.cget("fg_color")
            if isinstance(parent_bg, tuple):
                parent_bg = parent_bg[1]
            if not parent_bg or parent_bg == "transparent":
                return "#252540"
            return parent_bg
        except (tk.TclError, AttributeError):
            return "#252540"
    
    def _display_image(self):
        """Display a custom image."""
        try:
            img = Image.open(self.image_path)
            img = img.resize((self.size, self.size), Image.Resampling.LANCZOS)
            
            # Create circular mask
            mask = Image.new('L', (self.size, self.size), 0)
            draw = ImageDraw.Draw(mask)
            draw.ellipse((0, 0, self.size, self.size), fill=255)
            
            # Apply mask
            output = Image.new('RGBA', (self.size, self.size), (0, 0, 0, 0))
            output.paste(img, (0, 0))
            output.putalpha(mask)
            
            self._image = ImageTk.PhotoImage(output)
            
            canvas = Canvas(self, width=self.size, height=self.size,
                          bg=self._get_bg_color(), highlightthickness=0)
            canvas.pack()
            canvas.create_image(self.size//2, self.size//2, image=self._image)
            
            if self.clickable:
                canvas.bind("<Button-1>", self._handle_click)
                
        except Exception as e:
            print(f"Error loading image: {e}")
            self._display_avatar()
    
    def _display_emoji(self, emoji: str):
        """Display an emoji avatar."""
        canvas = Canvas(self, width=self.size, height=self.size,
                       bg=self._get_bg_color(), highlightthickness=0)
        canvas.pack()
        
        # Background circle
        colors = AvatarGenerator.get_color_for_name(self.player_name or "default")
        canvas.create_oval(
            2, 2, self.size-2, self.size-2,
            fill=colors[0], outline=colors[1], width=2
        )
        
        # Emoji
        font_size = int(self.size * 0.5)
        canvas.create_text(
            self.size // 2, self.size // 2,
            text=emoji,
            font=("Segoe UI Emoji", font_size)
        )
        
        if self.clickable:
            canvas.bind("<Button-1>", self._handle_click)
    
    def _display_avatar(self):
        """Display a generated avatar."""
        canvas = AvatarGenerator.create_avatar_canvas(
            self, self.player_name or "?", self.size
        )
        canvas.pack()
        
        if self.clickable:
            canvas.bind("<Button-1>", self._handle_click)
    
    def _handle_click(self, event=None):
        """Handle click on the profile picture."""
        if self.on_click:
            self.on_click()
    
    def _on_enter(self, event):
        """Handle mouse enter."""
        if self.clickable:
            self.configure(cursor="hand2")
    
    def _on_leave(self, event):
        """Handle mouse leave."""
        self.configure(cursor="")
    
    def update_picture(self, image_path: str):
        """Update the displayed picture."""
        self.image_path = image_path
        self._create_display()


class ProfilePictureBrowser(ctk.CTkToplevel):
    """Dialog for browsing and selecting profile pictures."""
    
    def __init__(self, parent, player_name: str = "", current_picture: str = "",
                 on_select: Optional[Callable] = None):
        super().__init__(parent)
        
        self.title("Choose Profile Picture")
        self.geometry("550x600")
        self.transient(parent.winfo_toplevel())
        self.grab_set()
        
        self.player_name = player_name
        self.current_picture = current_picture
        self.on_select = on_select
        self.selected_picture = current_picture
        
        # Center dialog
        self.update_idletasks()
        x = parent.winfo_toplevel().winfo_x() + (parent.winfo_toplevel().winfo_width() // 2) - 275
        y = parent.winfo_toplevel().winfo_y() + (parent.winfo_toplevel().winfo_height() // 2) - 300
        self.geometry(f"+{x}+{y}")
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the dialog UI."""
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=15)
        
        ctk.CTkLabel(
            header,
            text="Choose Profile Picture",
            font=get_font(22, "bold")
        ).pack()
        
        ctk.CTkLabel(
            header,
            text=f"Select an avatar for {self.player_name}",
            font=get_font(14),
            text_color="#888888"
        ).pack(pady=5)
        
        # Current selection preview
        preview_frame = ctk.CTkFrame(self, fg_color="#252540", corner_radius=15)
        preview_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(
            preview_frame,
            text="Current Selection:",
            font=get_font(13)
        ).pack(pady=(15, 5))
        
        self.preview = ProfilePicture(
            preview_frame, size=80,
            image_path=self.current_picture,
            player_name=self.player_name
        )
        self.preview.pack(pady=(5, 15))
        
        # Tabs for different avatar types
        tabs = ctk.CTkTabview(self, height=300)
        tabs.pack(fill="both", expand=True, padx=20, pady=10)
        
        tabs.add("Pool Avatars")
        tabs.add("Color Avatars")
        tabs.add("Custom Image")
        
        # Pool-themed avatars tab
        self._create_pool_avatars(tabs.tab("Pool Avatars"))
        
        # Color avatars tab
        self._create_color_avatars(tabs.tab("Color Avatars"))
        
        # Custom image tab
        self._create_custom_image_tab(tabs.tab("Custom Image"))
        
        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=15)
        
        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            width=100,
            height=40,
            fg_color="#555555",
            hover_color="#444444",
            command=self.destroy
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            btn_frame,
            text="Remove Picture",
            width=120,
            height=40,
            fg_color="#c44536",
            hover_color="#a43526",
            command=self._remove_picture
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            btn_frame,
            text="Save Selection",
            width=120,
            height=40,
            fg_color="#2d7a3e",
            hover_color="#1a5f2a",
            command=self._save_selection
        ).pack(side="right", padx=5)
    
    def _create_pool_avatars(self, parent):
        """Create the pool-themed avatars grid."""
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        
        grid_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        grid_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Create grid of emoji avatars
        for i, emoji in enumerate(POOL_AVATARS):
            row = i // 4
            col = i % 4
            
            avatar_frame = ctk.CTkFrame(grid_frame, fg_color="#353550", 
                                       corner_radius=10, width=100, height=100)
            avatar_frame.grid(row=row, column=col, padx=8, pady=8)
            avatar_frame.pack_propagate(False)
            
            # Emoji display
            ctk.CTkLabel(
                avatar_frame,
                text=emoji,
                font=get_font(40)
            ).pack(expand=True)
            
            # Make clickable
            avatar_frame.bind("<Button-1>", 
                             lambda e, em=emoji: self._select_emoji(em))
            for child in avatar_frame.winfo_children():
                child.bind("<Button-1>", 
                          lambda e, em=emoji: self._select_emoji(em))
            
            # Hover effect
            avatar_frame.bind("<Enter>", 
                             lambda e, f=avatar_frame: f.configure(fg_color="#454570"))
            avatar_frame.bind("<Leave>", 
                             lambda e, f=avatar_frame: f.configure(fg_color="#353550"))
    
    def _create_color_avatars(self, parent):
        """Create the color-based avatars grid."""
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.pack(fill="both", expand=True)
        
        grid_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        grid_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        initials = AvatarGenerator.get_initials(self.player_name)
        
        for i, (light, dark) in enumerate(AVATAR_COLORS):
            row = i // 4
            col = i % 4
            
            avatar_frame = ctk.CTkFrame(grid_frame, fg_color="#353550",
                                       corner_radius=10, width=100, height=100)
            avatar_frame.grid(row=row, column=col, padx=8, pady=8)
            avatar_frame.pack_propagate(False)
            
            # Create mini avatar canvas
            canvas = Canvas(avatar_frame, width=60, height=60,
                           bg="#353550", highlightthickness=0)
            canvas.pack(expand=True)
            
            canvas.create_oval(2, 2, 58, 58, fill=light, outline=dark, width=2)
            canvas.create_text(30, 30, text=initials,
                              font=("Arial", 18, "bold"), fill="white")
            
            # Make clickable
            color_id = f"color:{i}"
            avatar_frame.bind("<Button-1>",
                             lambda e, c=color_id: self._select_color(c))
            canvas.bind("<Button-1>",
                       lambda e, c=color_id: self._select_color(c))
            
            avatar_frame.bind("<Enter>",
                             lambda e, f=avatar_frame: f.configure(fg_color="#454570"))
            avatar_frame.bind("<Leave>",
                             lambda e, f=avatar_frame: f.configure(fg_color="#353550"))
    
    def _create_custom_image_tab(self, parent):
        """Create the custom image upload section."""
        content = ctk.CTkFrame(parent, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(
            content,
            text="Upload a custom profile picture",
            font=get_font(16, "bold")
        ).pack(pady=10)
        
        ctk.CTkLabel(
            content,
            text="Supported formats: JPG, PNG, GIF",
            font=get_font(13),
            text_color="#888888"
        ).pack(pady=5)
        
        ctk.CTkButton(
            content,
            text="📁 Browse for Image",
            font=get_font(14),
            height=50,
            width=200,
            fg_color="#3d5a80",
            hover_color="#2d4a70",
            command=self._browse_image
        ).pack(pady=20)
        
        self.image_path_label = ctk.CTkLabel(
            content,
            text="No image selected",
            font=get_font(12),
            text_color="#666666"
        )
        self.image_path_label.pack(pady=10)
    
    def _select_emoji(self, emoji: str):
        """Select an emoji avatar and auto-save."""
        self.selected_picture = f"emoji:{emoji}"
        self._update_preview()
        # Auto-save the selection
        self._save_selection()
    
    def _select_color(self, color_id: str):
        """Select a color avatar and auto-save."""
        self.selected_picture = color_id
        self._update_preview()
        # Auto-save the selection
        self._save_selection()
    
    def _browse_image(self):
        """Browse for a custom image."""
        filepath = filedialog.askopenfilename(
            title="Select Profile Picture",
            filetypes=[
                ("Image files", "*.jpg *.jpeg *.png *.gif"),
                ("All files", "*.*")
            ]
        )
        
        if filepath:
            # Copy to app's profile pictures directory
            pictures_dir = os.path.join(os.path.dirname(__file__), "profile_pictures")
            os.makedirs(pictures_dir, exist_ok=True)
            
            # Create unique filename
            ext = os.path.splitext(filepath)[1]
            new_filename = f"{hashlib.md5(filepath.encode()).hexdigest()[:12]}{ext}"
            new_path = os.path.join(pictures_dir, new_filename)
            
            try:
                shutil.copy2(filepath, new_path)
                self.selected_picture = new_path
                self.image_path_label.configure(
                    text=f"Selected: {os.path.basename(filepath)}",
                    text_color="#4CAF50"
                )
                self._update_preview()
                # Auto-save the selection
                self._save_selection()
            except Exception as e:
                self.image_path_label.configure(
                    text=f"Error: {str(e)}",
                    text_color="#ff6b6b"
                )
    
    def _update_preview(self):
        """Update the preview display."""
        self.preview.update_picture(self.selected_picture)
    
    def _remove_picture(self):
        """Remove the profile picture."""
        self.selected_picture = ""
        self._update_preview()
    
    def _save_selection(self):
        """Save the selected picture."""
        if self.on_select:
            self.on_select(self.selected_picture)
        self.destroy()


def get_profile_picture_widget(parent, player, size: int = 50,
                               clickable: bool = False,
                               on_click: Optional[Callable] = None) -> ProfilePicture:
    """Helper function to create a profile picture widget for a player."""
    return ProfilePicture(
        parent,
        size=size,
        image_path=player.profile_picture if hasattr(player, 'profile_picture') else "",
        player_name=player.name if hasattr(player, 'name') else str(player),
        clickable=clickable,
        on_click=on_click
    )
