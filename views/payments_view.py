"""
EcoPOOL League - Payments View
Venmo integration for buy-in collection and payment tracking.
"""

import customtkinter as ctk
from tkinter import messagebox
import webbrowser
from typing import Optional, List
from database import DatabaseManager
from venmo_integration import VenmoIntegration
from profile_pictures import ProfilePicture
from fonts import get_font
from animations import flash_widget

try:
    from PIL import Image, ImageTk
    import io
    import base64
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


class PaymentRow(ctk.CTkFrame):
    """Row displaying a single payment request."""

    def __init__(self, parent, payment: dict, venmo_mgr: VenmoIntegration,
                 on_update: callable = None, **kwargs):
        super().__init__(parent, fg_color='#252540', corner_radius=8, height=60, **kwargs)
        self.pack_propagate(False)

        self.payment = payment
        self.venmo_mgr = venmo_mgr
        self.on_update = on_update

        status = payment['status']

        # Status indicator
        status_colors = {
            'pending': '#ff9800',
            'requested': '#2196F3',
            'paid': '#4CAF50',
            'cancelled': '#888888'
        }
        status_emoji = {
            'pending': '⏳',
            'requested': '📤',
            'paid': '✅',
            'cancelled': '❌'
        }

        status_frame = ctk.CTkFrame(self, fg_color='transparent', width=30)
        status_frame.pack(side='left', padx=5, pady=10)
        status_frame.pack_propagate(False)

        ctk.CTkLabel(
            status_frame,
            text=status_emoji.get(status, '?'),
            font=get_font(16)
        ).pack(expand=True)

        # Player info
        info_frame = ctk.CTkFrame(self, fg_color='transparent', width=200)
        info_frame.pack(side='left', padx=10, pady=5)
        info_frame.pack_propagate(False)

        ctk.CTkLabel(
            info_frame,
            text=payment['name'],
            font=get_font(14, 'bold'),
            anchor='w'
        ).pack(anchor='w')

        venmo_text = f"@{payment['venmo']}" if payment['venmo'] else "No Venmo"
        venmo_color = '#888888' if payment['venmo'] else '#ff6b6b'
        ctk.CTkLabel(
            info_frame,
            text=venmo_text,
            font=get_font(11),
            text_color=venmo_color,
            anchor='w'
        ).pack(anchor='w')

        # Amount
        ctk.CTkLabel(
            self,
            text=f"${payment['amount']:.2f}",
            font=get_font(16, 'bold'),
            text_color='#4CAF50',
            width=80
        ).pack(side='left', padx=10)

        # Status text
        status_text = status.upper()
        ctk.CTkLabel(
            self,
            text=status_text,
            font=get_font(11, 'bold'),
            text_color=status_colors.get(status, '#888888'),
            width=80
        ).pack(side='left', padx=5)

        # Actions
        actions = ctk.CTkFrame(self, fg_color='transparent')
        actions.pack(side='right', padx=10)

        if status == 'pending':
            if payment['venmo']:
                ctk.CTkButton(
                    actions,
                    text='📲 Request',
                    font=get_font(11),
                    fg_color='#2196F3',
                    hover_color='#1976D2',
                    width=90,
                    height=30,
                    command=self._send_request
                ).pack(side='left', padx=2)

            ctk.CTkButton(
                actions,
                text='✅ Paid',
                font=get_font(11),
                fg_color='#4CAF50',
                hover_color='#388E3C',
                width=70,
                height=30,
                command=self._mark_paid
            ).pack(side='left', padx=2)

        elif status == 'requested':
            ctk.CTkButton(
                actions,
                text='✅ Paid',
                font=get_font(11),
                fg_color='#4CAF50',
                hover_color='#388E3C',
                width=70,
                height=30,
                command=self._mark_paid
            ).pack(side='left', padx=2)

            ctk.CTkButton(
                actions,
                text='🔄',
                font=get_font(11),
                fg_color='#555555',
                hover_color='#444444',
                width=35,
                height=30,
                command=self._send_request
            ).pack(side='left', padx=2)

    def _send_request(self):
        """Send Venmo request."""
        if self.venmo_mgr.send_payment_request(self.payment['id']):
            flash_widget(self, '#2196F3', times=2)
            if self.on_update:
                self.on_update()
        else:
            messagebox.showerror("Error", "Could not open Venmo. Make sure the player has a Venmo username set.")

    def _mark_paid(self):
        """Mark as paid."""
        self.venmo_mgr.mark_as_paid(self.payment['id'])
        flash_widget(self, '#4CAF50', times=2)
        if self.on_update:
            self.on_update()


class PaymentsView(ctk.CTkFrame):
    """View for managing Venmo payments and buy-ins."""

    def __init__(self, parent, db: DatabaseManager):
        super().__init__(parent, fg_color='transparent')
        self.db = db
        self.venmo_mgr = VenmoIntegration(db)
        self.current_night_id = None

        # Get current league night
        night = db.get_current_league_night()
        if night:
            self.current_night_id = night['id']

        self.setup_ui()
        self.load_payments()

    def setup_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color='transparent')
        header.pack(fill='x', padx=20, pady=(20, 10))

        ctk.CTkLabel(
            header,
            text='💳 Payment Manager',
            font=get_font(28, 'bold')
        ).pack(side='left')

        # Buy-in amount setting
        buyin_frame = ctk.CTkFrame(header, fg_color='transparent')
        buyin_frame.pack(side='right')

        ctk.CTkLabel(
            buyin_frame,
            text='Buy-in: $',
            font=get_font(14)
        ).pack(side='left', padx=5)

        self.buyin_var = ctk.StringVar(value='5')
        ctk.CTkEntry(
            buyin_frame,
            textvariable=self.buyin_var,
            width=60,
            height=35,
            font=get_font(14)
        ).pack(side='left')

        # Summary card
        self.summary_frame = ctk.CTkFrame(self, fg_color='#252540', corner_radius=15)
        self.summary_frame.pack(fill='x', padx=20, pady=10)

        summary_inner = ctk.CTkFrame(self.summary_frame, fg_color='transparent')
        summary_inner.pack(fill='x', padx=20, pady=15)

        # Summary stats
        stats = ctk.CTkFrame(summary_inner, fg_color='transparent')
        stats.pack(side='left')

        self.collected_label = ctk.CTkLabel(
            stats,
            text='$0.00',
            font=get_font(28, 'bold'),
            text_color='#4CAF50'
        )
        self.collected_label.pack(anchor='w')

        self.progress_label = ctk.CTkLabel(
            stats,
            text='0 of 0 payments collected (0%)',
            font=get_font(12),
            text_color='#888888'
        )
        self.progress_label.pack(anchor='w')

        # Action buttons
        actions = ctk.CTkFrame(summary_inner, fg_color='transparent')
        actions.pack(side='right')

        ctk.CTkButton(
            actions,
            text='📲 Request All Pending',
            font=get_font(12),
            fg_color='#2196F3',
            hover_color='#1976D2',
            height=40,
            command=self.request_all_pending
        ).pack(side='left', padx=5)

        ctk.CTkButton(
            actions,
            text='➕ Create Requests',
            font=get_font(12),
            fg_color='#4CAF50',
            hover_color='#388E3C',
            height=40,
            command=self.show_create_requests_dialog
        ).pack(side='left', padx=5)

        # QR Code button
        ctk.CTkButton(
            actions,
            text='📱 QR Code',
            font=get_font(12),
            fg_color='#6b4e8a',
            hover_color='#5b3e7a',
            height=40,
            command=self.show_qr_code
        ).pack(side='left', padx=5)

        # Filter tabs
        filter_frame = ctk.CTkFrame(self, fg_color='#1a1a2e', corner_radius=10)
        filter_frame.pack(fill='x', padx=20, pady=10)

        filter_inner = ctk.CTkFrame(filter_frame, fg_color='transparent')
        filter_inner.pack(fill='x', padx=10, pady=8)

        self.filter_var = ctk.StringVar(value='all')

        for value, text in [('all', 'All'), ('pending', '⏳ Pending'),
                            ('requested', '📤 Requested'), ('paid', '✅ Paid')]:
            ctk.CTkRadioButton(
                filter_inner,
                text=text,
                variable=self.filter_var,
                value=value,
                font=get_font(12),
                fg_color='#4CAF50',
                command=self.load_payments
            ).pack(side='left', padx=15)

        # Payments list
        self.payments_frame = ctk.CTkScrollableFrame(
            self,
            fg_color='#1a1a2e',
            corner_radius=15
        )
        self.payments_frame.pack(fill='both', expand=True, padx=20, pady=10)

    def load_payments(self):
        """Load and display payment requests."""
        for widget in self.payments_frame.winfo_children():
            widget.destroy()

        if not self.current_night_id:
            ctk.CTkLabel(
                self.payments_frame,
                text='No active league night.\nStart a new pool night to track payments.',
                font=get_font(14),
                text_color='#888888'
            ).pack(pady=50)
            return

        summary = self.venmo_mgr.generate_payment_summary(self.current_night_id)
        requests = summary.get('requests', [])

        # Update summary
        self.collected_label.configure(text=f"${summary.get('total_paid', 0):.2f}")
        self.progress_label.configure(
            text=f"{summary.get('paid_count', 0)} of {summary.get('total_requests', 0)} payments collected "
                 f"({summary.get('collection_rate', 0):.0f}%)"
        )

        # Filter
        filter_val = self.filter_var.get()
        if filter_val == 'pending':
            requests = [r for r in requests if r['status'] == 'pending']
        elif filter_val == 'requested':
            requests = [r for r in requests if r['status'] == 'requested']
        elif filter_val == 'paid':
            requests = [r for r in requests if r['status'] == 'paid']

        if not requests:
            status_text = {
                'all': 'No payment requests yet.',
                'pending': 'No pending payments.',
                'requested': 'No outstanding requests.',
                'paid': 'No payments collected yet.'
            }
            ctk.CTkLabel(
                self.payments_frame,
                text=status_text.get(filter_val, 'No payments.'),
                font=get_font(14),
                text_color='#888888'
            ).pack(pady=30)
            return

        # Display payments
        for payment in requests:
            row = PaymentRow(
                self.payments_frame,
                payment,
                self.venmo_mgr,
                on_update=self.load_payments
            )
            row.pack(fill='x', padx=5, pady=2)

    def show_create_requests_dialog(self):
        """Show dialog to create new payment requests."""
        dialog = ctk.CTkToplevel(self)
        dialog.title('Create Payment Requests')
        dialog.geometry('500x750')
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        # Center
        dialog.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() // 2) - 250
        y = self.winfo_rooty() + (self.winfo_height() // 2) - 375
        dialog.geometry(f'+{x}+{y}')

        ctk.CTkLabel(
            dialog,
            text='Create Payment Requests',
            font=get_font(20, 'bold')
        ).pack(pady=(20, 10))

        # Amount
        amount_frame = ctk.CTkFrame(dialog, fg_color='transparent')
        amount_frame.pack(fill='x', padx=30, pady=10)

        ctk.CTkLabel(
            amount_frame,
            text='Amount per player: $',
            font=get_font(14)
        ).pack(side='left')

        amount_var = ctk.StringVar(value=self.buyin_var.get())
        ctk.CTkEntry(
            amount_frame,
            textvariable=amount_var,
            width=80,
            height=35,
            font=get_font(14)
        ).pack(side='left')

        # Note
        ctk.CTkLabel(
            dialog,
            text='Note:',
            font=get_font(14)
        ).pack(anchor='w', padx=30, pady=(10, 2))

        note_var = ctk.StringVar(value='EcoPOOL League Buy-In')
        ctk.CTkEntry(
            dialog,
            textvariable=note_var,
            height=35,
            font=get_font(12)
        ).pack(fill='x', padx=30)

        # Player selection
        ctk.CTkLabel(
            dialog,
            text='Select players:',
            font=get_font(14)
        ).pack(anchor='w', padx=30, pady=(15, 5))

        players_frame = ctk.CTkScrollableFrame(dialog, height=380)
        players_frame.pack(fill='x', padx=30, pady=5)

        players = self.db.get_all_players()
        player_vars = {}

        for player in players:
            var = ctk.BooleanVar(value=True)
            player_vars[player.id] = var

            row = ctk.CTkFrame(players_frame, fg_color='transparent')
            row.pack(fill='x', pady=2)

            ctk.CTkCheckBox(
                row,
                text='',
                variable=var,
                width=20
            ).pack(side='left')

            ctk.CTkLabel(
                row,
                text=player.name,
                font=get_font(13)
            ).pack(side='left', padx=10)

            venmo_text = f"@{player.venmo}" if player.venmo else "No Venmo"
            venmo_color = '#888888' if player.venmo else '#ff6b6b'
            ctk.CTkLabel(
                row,
                text=venmo_text,
                font=get_font(11),
                text_color=venmo_color
            ).pack(side='right', padx=10)

        # Select all / none buttons
        sel_frame = ctk.CTkFrame(dialog, fg_color='transparent')
        sel_frame.pack(fill='x', padx=30, pady=5)

        def select_all():
            for var in player_vars.values():
                var.set(True)

        def select_none():
            for var in player_vars.values():
                var.set(False)

        ctk.CTkButton(
            sel_frame,
            text='Select All',
            font=get_font(11),
            fg_color='#555555',
            hover_color='#444444',
            width=80,
            height=30,
            command=select_all
        ).pack(side='left', padx=5)

        ctk.CTkButton(
            sel_frame,
            text='Select None',
            font=get_font(11),
            fg_color='#555555',
            hover_color='#444444',
            width=80,
            height=30,
            command=select_none
        ).pack(side='left', padx=5)

        # Create button
        def create_requests():
            try:
                amount = float(amount_var.get())
            except ValueError:
                messagebox.showerror("Error", "Invalid amount")
                return

            selected_ids = [pid for pid, var in player_vars.items() if var.get()]

            if not selected_ids:
                messagebox.showerror("Error", "Select at least one player")
                return

            self.venmo_mgr.create_bulk_requests(
                self.current_night_id,
                selected_ids,
                amount,
                note_var.get()
            )

            dialog.destroy()
            self.load_payments()
            messagebox.showinfo("Success", f"Created {len(selected_ids)} payment requests")

        btn_frame = ctk.CTkFrame(dialog, fg_color='transparent')
        btn_frame.pack(pady=20)

        ctk.CTkButton(
            btn_frame,
            text='Cancel',
            font=get_font(12),
            fg_color='#555555',
            hover_color='#444444',
            width=100,
            height=40,
            command=dialog.destroy
        ).pack(side='left', padx=10)

        ctk.CTkButton(
            btn_frame,
            text='Create Requests',
            font=get_font(12, 'bold'),
            fg_color='#4CAF50',
            hover_color='#388E3C',
            width=140,
            height=40,
            command=create_requests
        ).pack(side='left', padx=10)

    def request_all_pending(self):
        """Send Venmo requests for all pending payments."""
        pending = self.venmo_mgr.get_pending_requests(self.current_night_id)
        pending_with_venmo = [p for p in pending if p['venmo']]

        if not pending_with_venmo:
            messagebox.showinfo("No Pending", "No pending payments with Venmo accounts.")
            return

        if messagebox.askyesno(
            "Confirm",
            f"This will open Venmo to request payment from {len(pending_with_venmo)} players.\n\n"
            "Continue?"
        ):
            for payment in pending_with_venmo:
                self.venmo_mgr.send_payment_request(payment['id'])

            self.load_payments()
            messagebox.showinfo("Done", f"Opened {len(pending_with_venmo)} Venmo requests")

    def show_qr_code(self):
        """Show QR code for players to scan and pay."""
        # Get organizer venmo from settings
        organizer_venmo = self.db.get_setting('organizer_venmo', '')
        
        # Get buy-in amount
        try:
            buyin_amount = float(self.buyin_var.get())
        except ValueError:
            buyin_amount = 5.0

        dialog = ctk.CTkToplevel(self)
        dialog.title('Payment QR Code')
        dialog.geometry('400x550')
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        # Center
        dialog.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() // 2) - 200
        y = self.winfo_rooty() + (self.winfo_height() // 2) - 275
        dialog.geometry(f'+{x}+{y}')

        ctk.CTkLabel(
            dialog,
            text='📱 Payment QR Code',
            font=get_font(20, 'bold')
        ).pack(pady=(20, 10))

        ctk.CTkLabel(
            dialog,
            text='Players can scan this to pay instantly!',
            font=get_font(12),
            text_color='#888888'
        ).pack(pady=(0, 15))

        # Organizer venmo input
        venmo_frame = ctk.CTkFrame(dialog, fg_color='transparent')
        venmo_frame.pack(fill='x', padx=30, pady=10)

        ctk.CTkLabel(
            venmo_frame,
            text='Your Venmo:',
            font=get_font(12)
        ).pack(side='left')

        venmo_var = ctk.StringVar(value=organizer_venmo)
        venmo_entry = ctk.CTkEntry(
            venmo_frame,
            textvariable=venmo_var,
            width=150,
            height=35,
            placeholder_text='@username'
        )
        venmo_entry.pack(side='left', padx=10)

        # Amount
        amount_frame = ctk.CTkFrame(dialog, fg_color='transparent')
        amount_frame.pack(fill='x', padx=30, pady=5)

        ctk.CTkLabel(
            amount_frame,
            text='Amount: $',
            font=get_font(12)
        ).pack(side='left')

        amount_var = ctk.StringVar(value=str(buyin_amount))
        ctk.CTkEntry(
            amount_frame,
            textvariable=amount_var,
            width=80,
            height=35
        ).pack(side='left')

        # QR display area
        qr_frame = ctk.CTkFrame(dialog, fg_color='#ffffff', corner_radius=10, width=250, height=250)
        qr_frame.pack(pady=20)
        qr_frame.pack_propagate(False)

        qr_label = ctk.CTkLabel(qr_frame, text='', fg_color='#ffffff')
        qr_label.pack(expand=True)

        status_label = ctk.CTkLabel(
            dialog,
            text='',
            font=get_font(11),
            text_color='#888888'
        )
        status_label.pack()

        def generate_qr():
            username = venmo_var.get().strip()
            if not username:
                status_label.configure(text='Please enter your Venmo username', text_color='#ff6b6b')
                qr_label.configure(text='', image='')
                return

            try:
                amount = float(amount_var.get())
            except ValueError:
                status_label.configure(text='Invalid amount', text_color='#ff6b6b')
                qr_label.configure(text='', image='')
                return

            # Save organizer venmo
            self.db.set_setting('organizer_venmo', username)

            # Generate QR
            qr_data = self.venmo_mgr.generate_collection_qr(username, amount, self.current_night_id)

            if qr_data and HAS_PIL:
                # Decode and display QR
                try:
                    img_data = base64.b64decode(qr_data)
                    img = Image.open(io.BytesIO(img_data))
                    img = img.resize((220, 220), Image.Resampling.LANCZOS)
                    photo = ImageTk.PhotoImage(img)

                    qr_label.configure(image=photo, text='')
                    qr_label.image = photo  # Keep reference

                    status_label.configure(text='Scan with phone camera or Venmo app!', text_color='#4CAF50')
                except Exception as e:
                    status_label.configure(text='Error generating QR code', text_color='#ff6b6b')
                    qr_label.configure(text='', image='')
            else:
                # Show link instead
                link = VenmoIntegration.generate_qr_payment_data(username, amount, 'EcoPOOL Buy-In')
                qr_label.configure(text='QR library not available.\nShare this link instead:\n\n' + link[:50] + '...')
                status_label.configure(text='Install qrcode and Pillow for QR codes', text_color='#ff9800')

        # Auto-generate QR code if organizer Venmo is already set
        if organizer_venmo:
            status_label.configure(text='Generating QR code...', text_color='#888888')
            dialog.update()  # Update UI before generating
            generate_qr()
        else:
            status_label.configure(text='Enter your Venmo username and click Generate', text_color='#888888')

        ctk.CTkButton(
            dialog,
            text='🔄 Regenerate QR Code',
            font=get_font(14, 'bold'),
            fg_color='#4CAF50',
            hover_color='#388E3C',
            height=40,
            command=generate_qr
        ).pack(pady=15)

        ctk.CTkButton(
            dialog,
            text='Close',
            font=get_font(12),
            fg_color='#555555',
            hover_color='#444444',
            height=35,
            command=dialog.destroy
        ).pack()
