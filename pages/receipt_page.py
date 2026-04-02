import json
import threading
from datetime import datetime
from pathlib import Path

from frontend import tk_compat as ctk
from frontend import theme
from frontend.widgets import AppShell, RoundedCard, PillButton, card_body
from backend.util import api_client

try:
    from backend.printer import (
        generate_token,
        print_discount_qr,
    )
except Exception as e:
    generate_token = None
    print_discount_qr = None
    print(f'[RECEIPT] Printer import failed: {e}', flush=True)

try:
    from backend.sync_uploader import sync_receipt_and_images
except Exception as e:
    sync_receipt_and_images = None
    print(f'[RECEIPT] Sync uploader import failed: {e}', flush=True)

try:
    from backend.util.capture_manager import (
        get_or_create_capture_session,
        remember_capture_session,
        save_receipt_json,
        get_session_timestamp,
    )
except Exception as e:
    get_or_create_capture_session = None
    remember_capture_session = None
    save_receipt_json = None
    get_session_timestamp = None
    print(f'[RECEIPT] Capture manager import failed: {e}', flush=True)


def _find_project_root(start_path: Path) -> Path:
    current = start_path.resolve()

    for parent in [current] + list(current.parents):
        if (
            (parent / '.env.local').exists()
            or (parent / 'package.json').exists()
            or (parent / '.git').exists()
        ):
            return parent

    return current.parents[2]


ROOT = _find_project_root(Path(__file__))
CAPTURES_DIR = ROOT / 'captures'
CAPTURES_DIR.mkdir(parents=True, exist_ok=True)

print('[RECEIPT] System initialized', flush=True)


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
        self.print_error = None
        self.print_success = False
        self.redirect_scheduled = False
        self.sync_in_progress = False
        self.sync_result = None

        self.shell = AppShell(self, title_right='Receipt')
        self.shell.pack(fill='both', expand=True)

        self.card = RoundedCard(self.shell.body)
        self.card.pack(fill='both', expand=True, padx=28, pady=22)

        body = card_body(self.card)
        body.grid_columnconfigure(0, weight=1)

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
        self.saved_path_label.pack(padx=30, pady=(0, 10), anchor='w')

        self.print_status_label = ctk.CTkLabel(
            body,
            text='',
            font=theme.font(16, 'bold'),
            justify='left',
            anchor='w',
            text_color=theme.INFO,
            fg_color=theme.WHITE,
            wraplength=900
        )
        self.print_status_label.pack(padx=30, pady=(0, 18), anchor='w')

        self.continue_btn = PillButton(
            body,
            text='Continue to Dispensing',
            width=240,
            height=56,
            command=self._redirect_to_dispensing,
            font=theme.font(16, 'bold')
        )
        self.continue_btn.pack(pady=(4, 24))

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

        self.printing_in_progress = False
        self.print_error = None
        self.print_success = False
        self.redirect_scheduled = False
        self.sync_in_progress = False
        self.sync_result = None

        username = self.user_data.get('username', 'User')
        user_id = self.user_data.get('userID') or self.user_data.get('_id') or 'Unknown'

        product_name = (
            self.product.get('name')
            or self.product.get('type')
            or 'Unknown'
        )
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

        resolved_transaction_id = (
            str(self.transaction_id) if self.transaction_id else
            str(self.payment_reference) if self.payment_reference else
            str(self.payment_session_id) if self.payment_session_id else
            f"TXN-{purchase_dt.strftime('%Y%m%d%H%M%S')}-{str(user_id)[:6]}"
        )

        # IMPORTANT: persist resolved value
        self.transaction_id = str(resolved_transaction_id)
        self.user_data["transaction_id"] = self.transaction_id
        self.user_data["latest_transaction_id"] = self.transaction_id

        print(f'[RECEIPT] incoming transaction_id={transaction_id}', flush=True)
        print(f'[RECEIPT] resolved_transaction_id={resolved_transaction_id}', flush=True)
        print(f'[RECEIPT] persisted transaction_id={self.transaction_id}', flush=True)
        print(f'[RECEIPT] payment_reference={self.payment_reference}', flush=True)
        print(f'[RECEIPT] payment_session_id={self.payment_session_id}', flush=True)

        if self.online_payment:
            mode_of_payment = f'Online ({self.payment_method})'
        else:
            mode_of_payment = 'Cash'

        if get_or_create_capture_session is None or remember_capture_session is None:
            self.saved_path_label.configure(
                text='Capture session manager unavailable.'
            )
            print('[RECEIPT] capture manager unavailable', flush=True)
            return

        self.receipt_session_dir = get_or_create_capture_session(str(user_id))
        remember_capture_session(str(user_id), self.receipt_session_dir)

        actual_timestamp = get_session_timestamp(self.receipt_session_dir)
        print(f'[RECEIPT] shared session_dir={self.receipt_session_dir}', flush=True)
        print(f'[RECEIPT] shared timestamp={actual_timestamp}', flush=True)

        self.receipt_data = {
            'transaction_id': str(resolved_transaction_id),
            'user': {
                'user_id': str(user_id),
                'username': username,
            },
            'purchase': {
                'date': date_str,
                'time': time_str,
                'timestamp_folder': actual_timestamp,
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
                'receipt_json': str((self.receipt_session_dir / 'receipt.json').resolve()),
            }
        }

        if generate_token is not None:
            try:
                self.discount_token = generate_token(user_id)
                print(f'[RECEIPT] Generated discount token: {self.discount_token}', flush=True)

                store_res = api_client.store_qr_token(user_id, self.discount_token)
                print(f'[RECEIPT] store_qr_token status={store_res.status_code}', flush=True)
                print(f'[RECEIPT] store_qr_token body={store_res.text}', flush=True)

                if not store_res.ok:
                    print('[RECEIPT] Failed to store discount token in website DB', flush=True)
                    self.discount_token = None

            except Exception as e:
                self.discount_token = None
                print(f'[RECEIPT] Failed to generate token: {e}', flush=True)
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
        )

        self.receipt_text.configure(text=self.receipt_text_content)

        try:
            if save_receipt_json is None:
                raise RuntimeError('save_receipt_json is unavailable')

            receipt_path = save_receipt_json(self.receipt_session_dir, self.receipt_data)
            self.saved_path_label.configure(
                text=(
                    "Digital receipt saved locally.\n"
                    f"Folder: {self.receipt_session_dir}\n"
                    f"Receipt: {receipt_path}\n"
                    "Syncing to website..."
                )
            )

            if sync_receipt_and_images is not None:
                self.sync_in_progress = True
                threading.Thread(
                    target=self._sync_to_website,
                    args=(
                        str(user_id),
                        actual_timestamp,
                        self.receipt_data,
                        str(self.receipt_session_dir),
                        str(product_id),
                        str(resolved_transaction_id),
                    ),
                    daemon=True
                ).start()
            else:
                self.saved_path_label.configure(
                    text=(
                        "Digital receipt saved locally.\n"
                        f"Folder: {self.receipt_session_dir}\n"
                        "Website sync unavailable."
                    )
                )

        except Exception as e:
            self.saved_path_label.configure(
                text="Failed to save digital receipt."
            )
            print(f'[RECEIPT] Failed to save receipt JSON: {e}', flush=True)

        self.print_status_label.configure(
            text='Printing receipt...',
            text_color=theme.INFO
        )

        self.continue_btn.configure(state='disabled')
        self.printing_in_progress = True
        threading.Thread(target=self._print_receipt, daemon=True).start()

    def _sync_to_website(
        self,
        user_id: str,
        timestamp: str,
        receipt_data: dict,
        session_dir: str,
        product_id: str | None = None,
        transaction_id: str | None = None,
    ):
        try:
            result = sync_receipt_and_images(
                user_id=user_id,
                timestamp=timestamp,
                receipt_data=receipt_data,
                session_dir=session_dir,
                product_id=product_id,
                transaction_id=transaction_id,
            )
            print(f'[SYNC] Receipt upload attempted', flush=True)
            self.after(0, lambda: self._on_sync_finished(result))
        except Exception as e:
            print(f"[RECEIPT] Sync thread failed: {e}", flush=True)
            self.after(0, lambda: self._on_sync_failed(str(e)))

    def _on_sync_finished(self, result: dict):
        self.sync_in_progress = False
        self.sync_result = result or {}

        receipt_ok = bool(self.sync_result.get("receipt", {}).get("ok"))
        images_info = self.sync_result.get("images") or {}

        lines = ["Digital receipt saved locally."]

        if receipt_ok:
            lines.append("Receipt synced to website.")
        else:
            lines.append("Receipt sync failed.")

        if isinstance(images_info, dict) and images_info.get("skipped"):
            lines.append("Result images will sync after kit capture.")
        elif isinstance(images_info, dict):
            uploaded_images = []
            failed_images = []

            for image_name, info in images_info.items():
                if isinstance(info, dict) and info.get("ok"):
                    uploaded_images.append(image_name)
                elif isinstance(info, dict):
                    failed_images.append(image_name)

            if uploaded_images:
                lines.append(f"Uploaded images: {', '.join(uploaded_images)}")
            if failed_images:
                lines.append(f"Failed image uploads: {', '.join(failed_images)}")
            if not uploaded_images and not failed_images:
                lines.append("No session images found yet to upload.")

        self.saved_path_label.configure(text="\n".join(lines))

    def _on_sync_failed(self, error_text: str):
        self.sync_in_progress = False
        current = self.saved_path_label.cget("text") or ""
        self.saved_path_label.configure(
            text=f"{current}\nWebsite sync failed."
        )

    def _print_receipt(self):
        try:
            if print_discount_qr is None:
                self.print_success = False
                self.print_error = 'Printer function unavailable.'
                print('[RECEIPT] print_discount_qr unavailable', flush=True)
                return

            if not self.discount_token:
                self.print_success = False
                self.print_error = 'Discount token missing.'
                print('[RECEIPT] discount token missing', flush=True)
                return

            print(f'[RECEIPT] Printing discount QR: {self.discount_token}', flush=True)

            result = print_discount_qr(self.discount_token)

            if result is True:
                print('[RECEIPT] QR coupon printed successfully', flush=True)
                self.print_success = True
                self.print_error = None
            else:
                self.print_success = False
                self.print_error = 'Printer did not complete the print job.'
                print('[RECEIPT] QR coupon printing reported failure', flush=True)

        except Exception as e:
            self.print_success = False
            self.print_error = str(e)
            print(f'[RECEIPT] Failed to print QR coupon: {e}', flush=True)

        finally:
            self.printing_in_progress = False
            self.after(0, self._on_print_finished)

    def _on_print_finished(self):
        if self.print_success:
            self.print_status_label.configure(
                text='Receipt printed successfully.\nRedirecting to dispensing...',
                text_color=theme.SUCCESS
            )
        else:
            self.print_status_label.configure(
                text=(
                    f'Receipt printing failed.\n'
                    f'{self.print_error or "Unknown printer error"}\n'
                    f'Redirecting to dispensing anyway...'
                ),
                text_color=theme.ERROR
            )

        self.continue_btn.configure(state='normal')

        if not self.redirect_scheduled:
            self.redirect_scheduled = True
            print('[RECEIPT] Auto-redirect to DispensingPage scheduled', flush=True)
            self.after(1500, self._redirect_to_dispensing)

    def _redirect_to_dispensing(self):
        if self.printing_in_progress:
            print('[RECEIPT] Still printing, redirect blocked', flush=True)
            return

        print(f'[RECEIPT] Redirecting to DispensingPage with transaction_id={self.transaction_id}', flush=True)
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