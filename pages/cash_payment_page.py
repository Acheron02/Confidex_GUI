import time
import threading
from tkinter import messagebox
from frontend import tk_compat as ctk
from frontend import theme
from frontend.widgets import AppShell, RoundedCard, PillButton, card_body
from backend.util import api_client

try:
    from gpiozero import Button, LED
except Exception:
    class Button:
        def __init__(self, *a, **k): self.when_pressed = None
    class LED:
        def __init__(self, *a, **k): pass
        def on(self): pass
        def off(self): pass


class CashPaymentPage(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color=theme.CREAM)
        self.controller = controller
        self.selected_product = None
        self.user_data = {}
        self.discount = 0
        self.total_cash_inserted = 0
        self.transaction_in_progress = False
        self.loading_visible = False
        self.pulse_count = 0
        self.last_pulse_time = 0
        self.tolerance = 0.3

        self.bill_acceptor = Button(17)
        self.bill_acceptor.when_pressed = self._pulse_callback
        self.reject_pin = LED(27)
        threading.Thread(target=self._pulse_watcher, daemon=True).start()

        self.shell = AppShell(self, title_right='Cash Payment')
        self.shell.pack(fill='both', expand=True)

        top_bar = ctk.CTkFrame(self.shell.body, fg_color='transparent')
        top_bar.pack(fill='x', padx=28, pady=(16, 6))

        self.back_btn = PillButton(
            top_bar,
            text='Back',
            width=120,
            command=self.go_back,
            font=theme.font(18, 'bold')
        )
        self.back_btn.pack(side='left')

        self.cancel_btn = PillButton(
            top_bar,
            text='Cancel Transaction',
            width=220,
            command=self.prompt_cancel_transaction,
            font=theme.font(18, 'bold')
        )
        self.cancel_btn.pack(side='right')

        self.card = RoundedCard(self.shell.body, width=760, height=360)
        self.card.place(relx=0.5, rely=0.50, anchor='center')
        body = card_body(self.card)

        self.order_text = ctk.CTkLabel(
            body,
            text='No item selected',
            font=theme.font(26, 'bold'),
            text_color=theme.MUTED,
            justify='left',
            fg_color=theme.WHITE
        )
        self.order_text.pack(padx=30, pady=(28, 16), anchor='w')

        self.status_text = ctk.CTkLabel(
            body,
            text='Insert bills to pay',
            font=theme.font(24, 'bold'),
            text_color=theme.INFO,
            wraplength=660,
            fg_color=theme.WHITE
        )
        self.status_text.pack(padx=30, pady=14)

        self.progress = ctk.CTkLabel(
            body,
            text='Accepted denominations: 50, 100, 200, 500, 1000',
            font=theme.font(18, 'bold'),
            text_color=theme.MUTED,
            fg_color=theme.WHITE
        )
        self.progress.pack(pady=(12, 0))

        self.loading_overlay = ctk.CTkFrame(self, fg_color='#E6E1C9')
        self.loading_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.loading_overlay.lower()

        self.loading_label = ctk.CTkLabel(
            self.loading_overlay,
            text='Processing payment...',
            font=theme.heavy(30),
            text_color=theme.BLACK
        )
        self.loading_label.place(relx=0.5, rely=0.46, anchor='center')

        self.loading_dots = ctk.CTkLabel(
            self.loading_overlay,
            text='',
            font=theme.heavy(28),
            text_color=theme.BLACK
        )
        self.loading_dots.place(relx=0.5, rely=0.55, anchor='center')

        self._dot_count = 0
        self._animate_dots_running = False

    def show_loading(self):
        if self.loading_visible:
            return
        self.loading_visible = True
        self.loading_overlay.lift()
        self._animate_dots_running = True
        self._animate_dots()

    def hide_loading(self):
        self.loading_visible = False
        self.loading_overlay.lower()
        self._animate_dots_running = False
        self.loading_dots.configure(text='')

    def _animate_dots(self):
        if not self._animate_dots_running:
            return
        self._dot_count = (self._dot_count + 1) % 4
        self.loading_dots.configure(text='.' * self._dot_count)
        self.after(450, self._animate_dots)

    def reject_bill(self, duration=0.5):
        self.reject_pin.on()
        time.sleep(duration)
        self.reject_pin.off()

    def _pulse_callback(self):
        self.pulse_count += 1
        self.last_pulse_time = time.time()

    def _pulse_watcher(self):
        while True:
            if self.pulse_count > 0 and (time.time() - self.last_pulse_time) > self.tolerance:
                count = self.pulse_count
                self.pulse_count = 0
                bill_value = self.map_pulses_to_bill(count)
                if bill_value:
                    self.controller.after(0, lambda v=bill_value: self.process_bill(v))
                else:
                    self.controller.after(
                        0,
                        lambda c=count: self.status_text.configure(
                            text=f'Unknown bill ({c} pulses). Rejecting...',
                            text_color=theme.ERROR
                        )
                    )
                    threading.Thread(target=self.reject_bill, daemon=True).start()
                    self.controller.after(
                        2500,
                        lambda: self.status_text.configure(text='Insert bills to pay', text_color=theme.INFO)
                    )
            time.sleep(0.01)

    def map_pulses_to_bill(self, count):
        return {5: 50, 10: 100, 20: 200, 50: 500, 100: 1000}.get(count)

    def prompt_cancel_transaction(self):
        if messagebox.askyesno(
            'Cancel Transaction',
            'Are you sure you want to cancel this transaction?\n\nYou will need to generate a new login QR code from the website.'
        ):
            self.controller.cancel_session_and_return_home(
                'Transaction cancelled. Please generate a new login QR code from the website.'
            )

    def go_back(self):
        if messagebox.askyesno(
            'Exit Payment',
            'Are you sure you want to leave the payment page?\n\nThis will cancel the current session and you will need a new login QR code.'
        ):
            self.controller.cancel_session_and_return_home(
                'Transaction cancelled. Please generate a new login QR code from the website.'
            )

    def process_bill(self, bill_value):
        self.show_loading()

        if not self.selected_product:
            self.status_text.configure(text='No product selected - returning bill', text_color=theme.ERROR)
            threading.Thread(target=self.reject_bill, daemon=True).start()
            self.after(1000, self.hide_loading)
            return

        self.total_cash_inserted += bill_value
        total_price = self.selected_product.get('price', 0) * (1 - self.discount / 100)
        remaining = total_price - self.total_cash_inserted

        if remaining > 0:
            self.status_text.configure(
                text=f'Total inserted: ₱{self.total_cash_inserted:.2f}. Insert ₱{remaining:.2f} more',
                text_color=theme.INFO
            )
            self.after(700, self.hide_loading)
        else:
            if not self.transaction_in_progress:
                self.transaction_in_progress = True
                self.status_text.configure(
                    text=f'Total inserted: ₱{self.total_cash_inserted:.2f}. Payment complete!',
                    text_color=theme.SUCCESS
                )
                self.after(1200, self.confirm_payment)
            self.after(700, self.hide_loading)

    def update_data(self, user_data=None, selected_product=None, discount=0, **kwargs):
        self.user_data = (user_data or {}).copy()
        self.selected_product = (selected_product or {}).copy() if selected_product else None
        self.discount = discount or 0
        self.total_cash_inserted = 0
        self.transaction_in_progress = False
        self.pulse_count = 0

        if not self.user_data or not self.selected_product:
            self.order_text.configure(text='No product selected or user data missing', text_color=theme.ERROR)
            return

        total = self.selected_product.get('price', 0) * (1 - self.discount / 100)
        self.order_text.configure(
            text=(
                f"User: {self.user_data.get('username', 'User')}\n"
                f"Product: {self.selected_product.get('name', 'Unknown')}\n"
                f"Type: {self.selected_product.get('type', 'Unknown')}\n"
                f"Total: ₱{total:.2f}"
            ),
            text_color=theme.BLACK
        )
        self.status_text.configure(text='Insert bills to pay', text_color=theme.INFO)
        self.hide_loading()

    def confirm_payment(self):
        if not self.selected_product or not self.user_data:
            self.transaction_in_progress = False
            self.status_text.configure(text='No product selected or user data missing', text_color=theme.ERROR)
            self.hide_loading()
            return

        cash = self.total_cash_inserted
        total = self.selected_product.get('price', 0) * (1 - self.discount / 100)
        change = cash - total

        transaction_data = {
            'user_id': self.user_data.get('_id') or self.user_data.get('userID'),
            'status': 'completed',
            'items': [{
                'name': self.selected_product.get('name', 'Unknown'),
                'productID': self.selected_product.get('productID') or self.selected_product.get('product_id') or ''
            }],
            'purchasedDate': None,
        }

        threading.Thread(target=self.post_transaction, args=(transaction_data,), daemon=True).start()

        self.controller.show_frame(
            'ReceiptPage',
            user_data=self.user_data,
            product=self.selected_product,
            discount=self.discount,
            total_paid=cash,
            change=change,
            total=total
        )
        self.after(7000, self.reset_fields)

    def post_transaction(self, transaction_data_local):
        try:
            response = api_client.post_transaction(transaction_data_local)
            if not response.ok:
                threading.Thread(target=self.reject_bill, daemon=True).start()
                self.controller.after(
                    0,
                    lambda: self.status_text.configure(
                        text='Transaction failed. Bill returned.',
                        text_color=theme.ERROR
                    )
                )
        except Exception as e:
            print('Transaction API error:', e)
            threading.Thread(target=self.reject_bill, daemon=True).start()
            self.controller.after(
                0,
                lambda: self.status_text.configure(
                    text='Network error. Bill returned.',
                    text_color=theme.ERROR
                )
            )

    def reset_fields(self, **kwargs):
        self.selected_product = None
        self.user_data = {}
        self.discount = 0
        self.total_cash_inserted = 0
        self.transaction_in_progress = False
        self.pulse_count = 0
        self.order_text.configure(text='No item selected', text_color=theme.MUTED)
        self.status_text.configure(text='Insert bills to pay', text_color=theme.INFO)
        self.hide_loading()