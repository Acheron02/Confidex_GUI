import random
import string
import threading
from frontend import tk_compat as ctk
from frontend import theme
from frontend.widgets import AppShell, RoundedCard, card_body
from backend.printer import print_discount_qr
from backend.util import api_client


def generate_qr_token(user_id, length=12):
    chars = string.ascii_uppercase + string.digits
    return f"{str(user_id)[:6]}-" + ''.join(random.choices(chars, k=length))


class ReceiptPage(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color=theme.CREAM)
        self.controller = controller
        self.shell = AppShell(self, title_right='Receipt')
        self.shell.pack(fill='both', expand=True)

        self.card = RoundedCard(self.shell.body)
        self.card.pack(fill='both', expand=True, padx=28, pady=22)
        body = card_body(self.card)

        ctk.CTkLabel(body, text='Receipt', font=theme.heavy(34), text_color=theme.BLACK, fg_color=theme.WHITE).pack(pady=(22, 12))
        self.receipt_text = ctk.CTkLabel(body, text='', font=theme.font(22, 'bold'), justify='left', text_color=theme.TEXT, fg_color=theme.WHITE)
        self.receipt_text.pack(padx=30, pady=22, anchor='w')

    def update_data(self, user_data=None, product=None, discount=0, total_paid=0, change=0, total=0, **kwargs):
        self.user_data = user_data or {}
        self.product = product or {}
        self.discount = discount
        self.total_paid = total_paid
        self.change = change
        self.total = total
        self.shell.set_header_right(f"Welcome, {self.user_data.get('username', 'User')}!")

        user_id = self.user_data.get('userID', 'Unknown')
        qr_token = generate_qr_token(user_id)
        self.user_data['qr_token'] = qr_token

        self.receipt_text.configure(text=(
            f"User ID: {user_id}\n\n"
            f"Username: {self.user_data.get('username', 'User')}\n\n"
            f"Product Name: {self.product.get('name', 'Unknown')}\n\n"
            f"Product ID: {self.product.get('product_id', 'Unknown')}\n\n"
            f"Product Type: {self.product.get('type', 'Unknown')}\n\n"
            f"Price: ₱{self.product.get('price', 0)}\n\n"
            f"Discount: {discount}%\n\n"
            f"Total: ₱{total:.2f}\n\n"
            f"Total Paid: ₱{total_paid:.2f}\n\n"
            f"Change: ₱{change:.2f}\n\n"
            f"QR Token: {qr_token}"
        ))

        self.after(2200, lambda: threading.Thread(target=self._store_and_print, args=(user_id, qr_token), daemon=True).start())
        self.after(2600, self._redirect_to_how_to_use)

    def _store_and_print(self, user_id, qr_token):
        try:
            api_client.store_qr_token(user_id, qr_token)
        except Exception as e:
            print('Failed to store QR token:', e)
        try:
            print_discount_qr(qr_token)
        except Exception as e:
            print('Failed to print QR code:', e)

    def _redirect_to_how_to_use(self):
        self.controller.show_frame('HowToUsePage', user_data=self.user_data, selected_product=self.product)
