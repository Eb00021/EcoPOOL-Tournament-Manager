"""
EcoPOOL League - Animations Module
Provides cool animations and visual effects for the application.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import Canvas
import math
import random
from typing import Callable, Optional


class AnimationManager:
    """Manages animations for widgets."""
    
    @staticmethod
    def fade_in(widget, duration: int = 300, callback: Optional[Callable] = None):
        """Fade in a widget by animating its opacity."""
        # CustomTkinter doesn't support true opacity, so we'll use a simple delay
        # Removed update_idletasks() which was causing performance issues
        if callback:
            widget.after(duration, callback)
    
    @staticmethod
    def pulse(widget, color1: str, color2: str, duration: int = 500, cycles: int = 2):
        """Create a pulsing color effect on a widget.
        
        Optimized: Reduced steps for better performance.
        """
        steps = 8  # Reduced from 20 for better performance
        step_time = duration // (steps * cycles * 2)
        total_steps = steps * cycles * 2
        
        def animate(step=0):
            if step < total_steps:
                # Simple toggle between colors
                try:
                    widget.configure(fg_color=color2 if step % 2 == 0 else color1)
                except (tk.TclError, AttributeError):
                    pass
                
                widget.after(step_time, lambda: animate(step + 1))
            else:
                try:
                    widget.configure(fg_color=color1)
                except (tk.TclError, AttributeError):
                    pass
        
        animate()
    
    @staticmethod
    def bounce(widget, amplitude: int = 10, duration: int = 400):
        """Create a bouncing effect on a widget."""
        steps = 20
        step_time = duration // steps
        original_y = widget.winfo_y()
        
        def animate(step=0):
            if step <= steps:
                # Damped sine wave for bounce
                progress = step / steps
                damping = 1 - progress
                offset = int(amplitude * damping * abs(math.sin(progress * math.pi * 3)))
                
                try:
                    widget.place_configure(y=original_y - offset)
                except (tk.TclError, AttributeError):
                    pass
                
                widget.after(step_time, lambda: animate(step + 1))
        
        animate()
    
    @staticmethod
    def shake(widget, amplitude: int = 5, duration: int = 300):
        """Create a horizontal shake effect."""
        steps = 15
        step_time = duration // steps
        
        def animate(step=0):
            if step <= steps:
                offset = int(amplitude * math.sin(step * math.pi * 4) * (1 - step/steps))
                try:
                    widget.place_configure(x=widget.winfo_x() + offset)
                except (tk.TclError, AttributeError):
                    pass
                widget.after(step_time, lambda: animate(step + 1))
        
        animate()
    
    @staticmethod
    def glow(widget, glow_color: str = "#4CAF50", duration: int = 600):
        """Create a glowing border effect."""
        try:
            original_border = widget.cget("border_color")
        except (tk.TclError, AttributeError):
            original_border = "transparent"
        
        steps = 30
        step_time = duration // steps
        
        def animate(step=0):
            if step <= steps:
                t = step / steps
                # Fade glow in and out
                if t < 0.5:
                    try:
                        widget.configure(border_color=glow_color, border_width=3)
                    except (tk.TclError, AttributeError):
                        pass
                else:
                    try:
                        widget.configure(border_color=original_border, border_width=0)
                    except (tk.TclError, AttributeError):
                        pass
                widget.after(step_time, lambda: animate(step + 1))
        
        animate()


class Confetti(Canvas):
    """Confetti celebration effect canvas overlay."""
    
    def __init__(self, parent, width=800, height=600, duration=3000):
        # Get parent background color
        try:
            parent_bg = parent.cget("bg")
        except (tk.TclError, AttributeError):
            try:
                parent_bg = parent.cget("fg_color")
                if isinstance(parent_bg, tuple):
                    parent_bg = parent_bg[1]
            except (tk.TclError, AttributeError):
                parent_bg = "#161b22"
        
        if not parent_bg or parent_bg == "transparent":
            parent_bg = "#161b22"
            
        super().__init__(parent, width=width, height=height, 
                        bg=parent_bg, highlightthickness=0)
        
        self.width = width
        self.height = height
        self.duration = duration
        self.particles = []
        self.colors = [
            "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", 
            "#FFEAA7", "#DDA0DD", "#98D8C8", "#F7DC6F",
            "#BB8FCE", "#85C1E9", "#F8B500", "#FF69B4"
        ]
        
        self.running = False
    
    def start(self):
        """Start the confetti animation."""
        self.running = True
        self.particles = []
        
        # Reduced particle count for better performance (was 100)
        for _ in range(40):
            self.particles.append(self._create_particle())
        
        self._animate()
        self.after(self.duration, self.stop)
    
    def _create_particle(self):
        """Create a single confetti particle."""
        return {
            'x': random.randint(0, self.width),
            'y': random.randint(-self.height, 0),
            'vx': random.uniform(-2, 2),
            'vy': random.uniform(2, 6),
            'color': random.choice(self.colors),
            'size': random.randint(5, 12),
            'shape': random.choice(['rect', 'oval'])  # Reduced shapes, removed triangle for perf
        }
    
    def _animate(self):
        """Animate the confetti."""
        if not self.running:
            return
        
        self.delete("confetti")
        
        for particle in self.particles:
            # Update position
            particle['x'] += particle['vx']
            particle['y'] += particle['vy']
            
            # Add gravity and air resistance
            particle['vy'] += 0.1
            particle['vx'] *= 0.99
            
            # Draw particle
            x, y = particle['x'], particle['y']
            size = particle['size']
            color = particle['color']
            
            if particle['shape'] == 'rect':
                self.create_rectangle(
                    x, y, x + size, y + size/2,
                    fill=color, outline="", tags="confetti"
                )
            else:  # oval
                self.create_oval(
                    x, y, x + size, y + size,
                    fill=color, outline="", tags="confetti"
                )
            
            # Reset particle if it goes off screen
            if particle['y'] > self.height + 20:
                new_p = self._create_particle()
                particle.update(new_p)
        
        # Increased interval for better performance (was 30ms)
        self.after(50, self._animate)
    
    def stop(self):
        """Stop the confetti animation."""
        self.running = False
        self.delete("confetti")
        self.destroy()


class AnimatedButton(ctk.CTkButton):
    """A button with hover animations."""
    
    def __init__(self, *args, hover_scale: float = 1.02, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.hover_scale = hover_scale
        self.original_fg_color = kwargs.get('fg_color', '#2d7a3e')
        
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
    
    def _on_enter(self, event):
        """Handle mouse enter."""
        # Lighten color on hover
        try:
            if self.original_fg_color and self.original_fg_color != "transparent":
                lighter = self._lighten_color(self.original_fg_color, 20)
                self.configure(fg_color=lighter)
        except (tk.TclError, AttributeError, ValueError):
            pass
    
    def _on_leave(self, event):
        """Handle mouse leave."""
        try:
            self.configure(fg_color=self.original_fg_color)
        except (tk.TclError, AttributeError):
            pass
    
    def _lighten_color(self, color: str, amount: int) -> str:
        """Lighten a hex color."""
        if not color.startswith('#'):
            return color
        
        try:
            r = min(255, int(color[1:3], 16) + amount)
            g = min(255, int(color[3:5], 16) + amount)
            b = min(255, int(color[5:7], 16) + amount)
            return f"#{r:02x}{g:02x}{b:02x}"
        except:
            return color


class AnimatedCard(ctk.CTkFrame):
    """A card widget with hover lift effect.
    
    Optimized: Removed recursive child binding which was very slow.
    Now uses simple enter/leave on the frame itself.
    """
    
    def __init__(self, *args, lift_amount: int = 5, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.lift_amount = lift_amount
        self.original_fg_color = kwargs.get('fg_color', '#252540')
        self._hover_color = self._lighten_color(self.original_fg_color, 15)
        self.is_hovered = False
        
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
    
    def _on_enter(self, event):
        if not self.is_hovered:
            self.is_hovered = True
            self._apply_hover_style()
    
    def _on_leave(self, event):
        # Only remove hover if mouse actually left the card
        # Check bounds to handle child widget transitions
        try:
            x, y = self.winfo_pointerxy()
            card_x = self.winfo_rootx()
            card_y = self.winfo_rooty()
            card_w = self.winfo_width()
            card_h = self.winfo_height()
            
            if not (card_x <= x <= card_x + card_w and card_y <= y <= card_y + card_h):
                self.is_hovered = False
                self._remove_hover_style()
        except (tk.TclError, RuntimeError):
            self.is_hovered = False
            self._remove_hover_style()
    
    def _apply_hover_style(self):
        try:
            self.configure(fg_color=self._hover_color)
        except (tk.TclError, AttributeError):
            pass
    
    def _remove_hover_style(self):
        try:
            self.configure(fg_color=self.original_fg_color)
        except (tk.TclError, AttributeError):
            pass
    
    def _lighten_color(self, color: str, amount: int) -> str:
        if not color or not color.startswith('#'):
            return color or '#252540'
        try:
            r = min(255, int(color[1:3], 16) + amount)
            g = min(255, int(color[3:5], 16) + amount)
            b = min(255, int(color[5:7], 16) + amount)
            return f"#{r:02x}{g:02x}{b:02x}"
        except:
            return color


class ScoreAnimation:
    """Animated score counter."""
    
    @staticmethod
    def animate_score(label: ctk.CTkLabel, start: int, end: int, 
                     duration: int = 500, callback: Optional[Callable] = None):
        """Animate a score label from start to end value."""
        steps = max(abs(end - start), 10)
        step_time = max(duration // steps, 20)
        
        def animate(current_step=0):
            if current_step <= steps:
                progress = current_step / steps
                # Ease out cubic
                ease = 1 - pow(1 - progress, 3)
                current_value = int(start + (end - start) * ease)
                
                label.configure(text=str(current_value))
                label.after(step_time, lambda: animate(current_step + 1))
            else:
                label.configure(text=str(end))
                if callback:
                    callback()
        
        animate()


class StarBurst(Canvas):
    """Star burst celebration effect."""
    
    def __init__(self, parent, x: int, y: int, size: int = 100):
        # Get parent background color
        try:
            parent_bg = parent.cget("bg")
        except (tk.TclError, AttributeError):
            try:
                parent_bg = parent.cget("fg_color")
                if isinstance(parent_bg, tuple):
                    parent_bg = parent_bg[1]
            except (tk.TclError, AttributeError):
                parent_bg = "#161b22"
        
        if not parent_bg or parent_bg == "transparent":
            parent_bg = "#161b22"
            
        super().__init__(parent, width=size*2, height=size*2,
                        bg=parent_bg, highlightthickness=0)
        
        # Position at center
        self.place(x=x-size, y=y-size)
        
        self.size = size
        self.colors = ["#FFD700", "#FFA500", "#FF6347", "#FF69B4"]
        self._animate()
    
    def _animate(self):
        """Animate the starburst."""
        steps = 20
        
        def draw_frame(step):
            if step > steps:
                self.destroy()
                return
            
            self.delete("all")
            progress = step / steps
            
            # Draw expanding rays
            num_rays = 12
            for i in range(num_rays):
                angle = (i / num_rays) * 2 * math.pi
                length = self.size * progress
                
                x1 = self.size + math.cos(angle) * 10
                y1 = self.size + math.sin(angle) * 10
                x2 = self.size + math.cos(angle) * length
                y2 = self.size + math.sin(angle) * length
                
                color = self.colors[i % len(self.colors)]
                width = max(1, int(5 * (1 - progress)))
                
                self.create_line(x1, y1, x2, y2, fill=color, width=width)
            
            self.after(30, lambda: draw_frame(step + 1))
        
        draw_frame(0)


class TypewriterLabel(ctk.CTkLabel):
    """Label with typewriter text effect."""
    
    def __init__(self, *args, **kwargs):
        self._full_text = kwargs.pop('text', '')
        kwargs['text'] = ''
        super().__init__(*args, **kwargs)
    
    def typewrite(self, text: str = None, speed: int = 50, callback: Optional[Callable] = None):
        """Display text with typewriter effect."""
        if text is not None:
            self._full_text = text
        
        def animate(index=0):
            if index <= len(self._full_text):
                self.configure(text=self._full_text[:index])
                self.after(speed, lambda: animate(index + 1))
            elif callback:
                callback()
        
        animate()


class ProgressRing(ctk.CTkFrame):
    """Animated circular progress indicator."""
    
    def __init__(self, parent, size: int = 100, thickness: int = 10,
                 color: str = "#4CAF50", bg_color: str = "#333333"):
        super().__init__(parent, fg_color="transparent",
                        width=size, height=size)
        
        # Get parent background for canvas
        try:
            parent_bg = parent.cget("fg_color")
            if isinstance(parent_bg, tuple):
                parent_bg = parent_bg[1]
            if not parent_bg or parent_bg == "transparent":
                parent_bg = "#252540"
        except (tk.TclError, AttributeError):
            parent_bg = "#252540"
        
        self.canvas = Canvas(self, width=size, height=size,
                            bg=parent_bg, highlightthickness=0)
        self.canvas.pack()
        
        self.size = size
        self.thickness = thickness
        self.color = color
        self.bg_color = bg_color
        self.progress = 0
        
        self._draw()
    
    def _draw(self):
        """Draw the progress ring."""
        self.canvas.delete("all")
        
        padding = self.thickness // 2
        
        # Background ring
        self.canvas.create_arc(
            padding, padding,
            self.size - padding, self.size - padding,
            start=90, extent=-360,
            style="arc", outline=self.bg_color, width=self.thickness
        )
        
        # Progress ring
        extent = -360 * self.progress
        self.canvas.create_arc(
            padding, padding,
            self.size - padding, self.size - padding,
            start=90, extent=extent,
            style="arc", outline=self.color, width=self.thickness
        )
        
        # Center text
        percentage = int(self.progress * 100)
        self.canvas.create_text(
            self.size // 2, self.size // 2,
            text=f"{percentage}%",
            fill="white", font=("Arial", self.size // 5, "bold")
        )
    
    def set_progress(self, value: float, animate: bool = True):
        """Set progress value (0.0 to 1.0)."""
        if animate:
            self._animate_to(value)
        else:
            self.progress = value
            self._draw()
    
    def _animate_to(self, target: float, duration: int = 500):
        """Animate progress to target value."""
        start = self.progress
        steps = 30
        step_time = duration // steps
        
        def animate(step=0):
            if step <= steps:
                progress = step / steps
                ease = 1 - pow(1 - progress, 3)  # Ease out
                self.progress = start + (target - start) * ease
                self._draw()
                self.after(step_time, lambda: animate(step + 1))
        
        animate()


def show_celebration(parent, duration: int = 3000):
    """Show a celebration overlay with confetti."""
    # Get parent dimensions
    width = parent.winfo_width()
    height = parent.winfo_height()
    
    # Create confetti overlay
    confetti = Confetti(parent, width=width, height=height, duration=duration)
    confetti.place(x=0, y=0, relwidth=1, relheight=1)
    confetti.lift()
    confetti.start()
    
    return confetti


def flash_widget(widget, flash_color: str = "#4CAF50", times: int = 3):
    """Flash a widget with a color."""
    try:
        original_color = widget.cget("fg_color")
    except (tk.TclError, AttributeError):
        original_color = "#252540"
    
    def flash(count=0):
        if count < times * 2:
            color = flash_color if count % 2 == 0 else original_color
            try:
                widget.configure(fg_color=color)
            except (tk.TclError, AttributeError):
                pass
            widget.after(150, lambda: flash(count + 1))
    
    flash()
