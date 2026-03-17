import json
import threading
from datetime import datetime
from pathlib import Path

from frontend import tk_compat as ctk
from frontend import theme
from frontend.widgets import AppShell, RoundedCard, card_body

try:
    from backend.printer import generate_token, print_discount_qr
except Exception as e:
    generate_token = None
    print_discount_qr = None
    print(f'[RECEIPT] Printer import failed: {e}', flush=True)


ROOT = Path(__file__).resolve().parents[2]
CAPTURES_DIR = ROOT / 'captures'
CAPTURES_DIR.mkdir(exist_ok=True)


def create_receipt_session(user_id: str):
    safe_user = str(user_id or 'unknown')
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    session_dir = CAPTURES_DIR / safe_user / ts
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def save_receipt_json(session_dir: Path, receipt_data: dict):
    receipt_path = session_dir / 'receipt.json'
    with open(receipt_path, 'w', encoding='utf-8') as f:
        json.dump(receipt_data, f, indent=2, ensure_ascii=False)
    return str(receipt_path)


class ReceiptPage(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color=theme.CREAM)
        self.controller = controller

        self.user_data = {}
        self.product = {}
        self.discount = 0
        self.total_paid = 0
        self.change = 0
        self.total = 0

        self.online_payment = False
        self.payment_method = 'cash'
        self.payment_session_id = None
        self.payment_reference = None
        self.payment_amount = None
        self.payment_mode = None
        self.simulated = False
        self.transaction_id = None

        self.receipt_data = None
        self.receipt_session_dir = None
        self.receipt_text_content = ''
        self.discount_token = None
        self.printing_in_progress = False

        self.shell = AppShell(self, title_right='Receipt')
        self.shell.pack(fill='both', expand=True)

        self.card = RoundedCard(self.shell.body)
        self.card.pack(fill='both', expand=True, padx=28, pady=22)

        body = card_body(self.card)

        ctk.CTkLabel(
            body,
            text='Receipt',
            font=theme.heavy(34),
            text_color=theme.BLACK,
            fg_color=theme.WHITE
        ).pack(pady=(22, 12))

        self.receipt_text = ctk.CTkLabel(
            body,
            text='',
            font=theme.font(22, 'bold'),
            justify='left',
            anchor='w',
            text_color=theme.TEXT,
            fg_color=theme.WHITE,
            wraplength=900
        )
        self.receipt_text.pack(padx=30, pady=22, anchor='w')

        self.saved_path_label = ctk.CTkLabel(
            body,
            text='',
            font=theme.font(14, 'bold'),
            justify='left',
            anchor='w',
            text_color=theme.MUTED,
            fg_color=theme.WHITE,
            wraplength=900
        )
        self.saved_path_label.pack(padx=30, pady=(0, 18), anchor='w')

    def update_data(
        self,
        user_data=None,
        product=None,
        discount=0,
        total_paid=0,
        change=0,
        total=0,
        online_payment=False,
        payment_method='cash',
        payment_session_id=None,
        payment_reference=None,
        payment_amount=None,
        payment_mode=None,
        simulated=False,
        transaction_id=None,
        **kwargs
    ):
        print('[RECEIPT] update_data called', flush=True)

        self.user_data = user_data or {}
        self.product = product or {}
        self.discount = float(discount or 0)
        self.total_paid = float(total_paid or 0)
        self.change = float(change or 0)
        self.total = float(total or 0)

        self.online_payment = bool(online_payment)
        self.payment_method = payment_method or 'cash'
        self.payment_session_id = payment_session_id
        self.payment_reference = payment_reference
        self.payment_amount = payment_amount
        self.payment_mode = payment_mode
        self.simulated = bool(simulated)
        self.transaction_id = transaction_id

        username = self.user_data.get('username', 'User')
        user_id = self.user_data.get('userID') or self.user_data.get('_id') or 'Unknown'

        product_name = self.product.get('name', 'Unknown')
        product_id = (
            self.product.get('productID')
            or self.product.get('product_id')
            or self.product.get('id')
            or 'Unknown'
        )
        product_type = self.product.get('type', 'Unknown')
        price = float(self.product.get('price', 0) or 0)

        purchase_dt = datetime.now()
        date_str = purchase_dt.strftime('%Y-%m-%d')
        time_str = purchase_dt.strftime('%I:%M:%S %p')
        timestamp_str = purchase_dt.strftime('%Y%m%d_%H%M%S')

        resolved_transaction_id = (
            self.transaction_id
            or self.payment_reference
            or self.payment_session_id
            or f"TXN-{purchase_dt.strftime('%Y%m%d%H%M%S')}-{str(user_id)[:6]}"
        )

        if self.online_payment:
            mode_of_payment = f'Online ({self.payment_method})'
        else:
            mode_of_payment = 'Cash'

        self.receipt_session_dir = create_receipt_session(user_id)

        self.receipt_data = {
            'transaction_id': resolved_transaction_id,
            'user': {
                'user_id': user_id,
                'username': username,
            },
            'purchase': {
                'date': date_str,
                'time': time_str,
                'timestamp_folder': timestamp_str,
                'datetime_iso': purchase_dt.isoformat(),
            },
            'product': {
                'name': product_name,
                'product_id': product_id,
                'type': product_type,
                'price': price,
            },
            'amounts': {
                'discount_percent': self.discount,
                'total': self.total,
                'total_paid': self.total_paid,
                'change': self.change,
            },
            'payment': {
                'mode_of_payment': mode_of_payment,
                'payment_method': self.payment_method,
                'online_payment': self.online_payment,
                'payment_session_id': self.payment_session_id,
                'payment_reference': self.payment_reference,
                'payment_amount': self.payment_amount,
                'payment_mode': self.payment_mode,
                'simulated': self.simulated,
            },
            'saved_paths': {
                'session_dir': str(self.receipt_session_dir),
                'receipt_json': str(self.receipt_session_dir / 'receipt.json'),
            }
        }

        if generate_token is not None:
            self.discount_token = generate_token(user_id)
            self.receipt_data['discount_token'] = self.discount_token
            print(f'[RECEIPT] discount token generated: {self.discount_token}', flush=True)
        else:
            self.discount_token = None
            print('[RECEIPT] generate_token not available', flush=True)

        self.shell.set_header_right(f"Welcome, {username}!")

        self.receipt_text_content = (
            f"Transaction ID: {resolved_transaction_id}\n\n"
            f"Username: {username}\n\n"
            f"User ID: {user_id}\n\n"
            f"Date of Purchase: {date_str}\n\n"
            f"Time of Purchase: {time_str}\n\n"
            f"Item Name: {product_name}\n\n"
            f"Product ID: {product_id}\n\n"
            f"Product Type: {product_type}\n\n"
            f"Price: ₱{price:.2f}\n\n"
            f"Discount: {self.discount:.2f}%\n\n"
            f"Total: ₱{self.total:.2f}\n\n"
            f"Total Paid: ₱{self.total_paid:.2f}\n\n"
            f"Change: ₱{self.change:.2f}\n\n"
            f"Mode of Payment: {mode_of_payment}\n\n"
            f"Discount QR Token: {self.discount_token or 'Unavailable'}"
        )

        self.receipt_text.configure(text=self.receipt_text_content)

        try:
            saved_path = save_receipt_json(self.receipt_session_dir, self.receipt_data)
            self.saved_path_label.configure(
                text=f"Digital receipt saved to:\n{saved_path}"
            )
            print(f'[RECEIPT] Receipt JSON saved to: {saved_path}', flush=True)
        except Exception as e:
            self.saved_path_label.configure(
                text=f"Failed to save digital receipt: {e}"
            )
            print(f'[RECEIPT] Failed to save receipt JSON: {e}', flush=True)

        self.printing_in_progress = True
        threading.Thread(target=self._print_receipt, daemon=True).start()

    def _print_receipt(self):
        try:
            if print_discount_qr is not None and self.discount_token:
                print('[RECEIPT] Printing QR coupon only using backend.printer.print_discount_qr', flush=True)
                print_discount_qr(self.discount_token)
                print('[RECEIPT] QR coupon printing finished', flush=True)
            else:
                print('[RECEIPT] print_discount_qr unavailable or token missing', flush=True)
        except Exception as e:
            print(f'[RECEIPT] Failed to print QR coupon: {e}', flush=True)
        finally:
            self.printing_in_progress = False
            self.after(0, self._redirect_to_dispensing)

    def _redirect_to_dispensing(self):
        if self.printing_in_progress:
            print('[RECEIPT] Still printing, redirect postponed', flush=True)
            return

        print('[RECEIPT] Redirecting to DispensingPage', flush=True)
        self.controller.show_loading_then(
            'Dispensing item',
            'DispensingPage',
            delay=1000,
            user_data=self.user_data,
            product=self.product,
            discount=self.discount,
            total_paid=self.total_paid,
            change=self.change,
            total=self.total,
            online_payment=self.online_payment,
            payment_method=self.payment_method,
            payment_session_id=self.payment_session_id,
            payment_reference=self.payment_reference,
            payment_amount=self.payment_amount,
            payment_mode=self.payment_mode,
            simulated=self.simulated,
            transaction_id=self.transaction_id
        )