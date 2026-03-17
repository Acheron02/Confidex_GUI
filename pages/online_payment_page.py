from frontend import tk_compat as ctk
from frontend import theme
from frontend.widgets import AppShell, RoundedCard, PillButton, card_body
from backend.util import api_client

import threading
import qrcode

try:
    from PIL import ImageTk
except Exception:
    ImageTk = None


class OnlinePaymentPage(ctk.CTkFrame):
    POLL_INTERVAL_MS = 3000
    ERROR_REDIRECT_DELAY_MS = 1800
    CONTENT_WRAPLENGTH = 760
    DETAILS_WRAPLENGTH = 760
    STATUS_WRAPLENGTH = 760
    QR_SIZE = 300

    def __init__(self, master, controller):
        super().__init__(master, fg_color=theme.CREAM)
        self.controller = controller
        self.user_data = {}
        self.selected_product = None
        self.discount = 0

        self.payment_session_id = None
        self.payment_checkout_url = None
        self.payment_reference = None
        self.payment_amount = 0
        self.payment_status = None
        self.payment_mode = 'test'
        self.simulated = True

        self.poll_job = None
        self.redirect_job = None
        self.qr_photo = None
        self.request_in_progress = False
        self.redirecting_to_cash = False

        self.shell = AppShell(self, title_right='Welcome, User!')
        self.shell.pack(fill='both', expand=True)

        top_bar = ctk.CTkFrame(self.shell.body, fg_color='transparent')
        top_bar.pack(fill='x', padx=24, pady=(14, 8))
        top_bar.grid_columnconfigure(0, weight=0)
        top_bar.grid_columnconfigure(1, weight=1)
        top_bar.grid_columnconfigure(2, weight=0)

        self.back_btn = PillButton(
            top_bar,
            text='Back',
            width=120,
            height=52,
            command=self.go_back,
            font=theme.font(16, 'bold')
        )
        self.back_btn.grid(row=0, column=0, sticky='w')

        self.title_label = ctk.CTkLabel(
            top_bar,
            text='ONLINE PAYMENT',
            font=theme.heavy(28),
            text_color=theme.BLACK
        )
        self.title_label.grid(row=0, column=1)

        content_wrap = ctk.CTkFrame(self.shell.body, fg_color='transparent')
        content_wrap.pack(expand=True, fill='both', padx=24, pady=(6, 18))
        content_wrap.grid_columnconfigure(0, weight=1)
        content_wrap.grid_rowconfigure(0, weight=1)

        self.main_card = RoundedCard(content_wrap, auto_size=False, pad=16)
        self.main_card.grid(row=0, column=0, sticky='nsew')

        body = card_body(self.main_card)
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=0)
        body.grid_rowconfigure(1, weight=0)
        body.grid_rowconfigure(2, weight=1)
        body.grid_rowconfigure(3, weight=0)
        body.grid_rowconfigure(4, weight=0)

        self.desc_label = ctk.CTkLabel(
            body,
            text='Scan the QR code using GCash, Maya, or another supported e-wallet.',
            font=theme.font(18, 'bold'),
            text_color=theme.MUTED,
            fg_color=theme.WHITE,
            wraplength=self.CONTENT_WRAPLENGTH,
            justify='center'
        )
        self.desc_label.grid(row=0, column=0, padx=18, pady=(8, 10), sticky='ew')

        self.qr_frame = ctk.CTkFrame(body, fg_color=theme.WHITE)
        self.qr_frame.grid(row=1, column=0, pady=(0, 12), sticky='n')
        self.qr_frame.grid_columnconfigure(0, weight=1)

        self.qr_label = ctk.CTkLabel(
            self.qr_frame,
            text='Preparing payment QR...',
            font=theme.font(16, 'bold'),
            text_color=theme.MUTED,
            fg_color=theme.WHITE,
            wraplength=420,
            justify='center'
        )
        self.qr_label.pack(padx=18, pady=18)

        self.details_label = ctk.CTkLabel(
            body,
            text='',
            font=theme.font(16, 'bold'),
            text_color=theme.BLACK,
            fg_color=theme.WHITE,
            justify='center',
            wraplength=self.DETAILS_WRAPLENGTH
        )
        self.details_label.grid(row=2, column=0, padx=18, pady=(0, 10), sticky='new')

        self.status_label = ctk.CTkLabel(
            body,
            text='',
            font=theme.font(16, 'bold'),
            text_color=theme.ORANGE,
            fg_color=theme.WHITE,
            wraplength=self.STATUS_WRAPLENGTH,
            justify='center'
        )
        self.status_label.grid(row=3, column=0, padx=18, pady=(0, 10), sticky='ew')

        btn_row = ctk.CTkFrame(body, fg_color=theme.WHITE)
        btn_row.grid(row=4, column=0, pady=(4, 8), padx=8, sticky='ew')
        btn_row.grid_columnconfigure(0, weight=1)
        btn_row.grid_columnconfigure(1, weight=1)

        self.refresh_btn = PillButton(
            btn_row,
            text='Refresh Status',
            width=180,
            height=54,
            command=self.manual_check_status,
            font=theme.font(16, 'bold')
        )
        self.refresh_btn.grid(row=0, column=0, padx=10, sticky='e')

        self.cancel_btn = PillButton(
            btn_row,
            text='Cancel',
            width=180,
            height=54,
            command=self.cancel_and_go_back,
            font=theme.font(16, 'bold')
        )
        self.cancel_btn.grid(row=0, column=1, padx=10, sticky='w')

        self.bind('<Configure>', self._on_resize)

    def _on_resize(self, event=None):
        try:
            total_width = max(self.winfo_width(), 900)
            content_width = max(520, total_width - 220)

            self.desc_label.configure(wraplength=min(content_width, 820))
            self.details_label.configure(wraplength=min(content_width, 820))
            self.status_label.configure(wraplength=min(content_width, 820))
        except Exception:
            pass

    def update_data(self, user_data=None, selected_product=None, discount=0, **kwargs):
        self._stop_polling()
        self._cancel_redirect()
        self._reset_state()

        self.user_data = user_data or {}
        self.selected_product = selected_product
        self.discount = discount or 0

        self.shell.set_header_right(f"Welcome, {self.user_data.get('username', 'User')}!")
        self.qr_label.configure(image=None, text='Preparing payment QR...')
        self.details_label.configure(text='')
        self.status_label.configure(
            text='Creating PayMongo payment session...',
            text_color=theme.INFO
        )

        self.after(150, self.start_online_payment)

    def start_online_payment(self):
        if self.request_in_progress or self.redirecting_to_cash:
            return

        if not self.selected_product:
            self._redirect_to_cash_with_error('No product selected.')
            return

        self.request_in_progress = True
        threading.Thread(target=self._create_checkout_session, daemon=True).start()

    def _create_checkout_session(self):
        try:
            amount = self._compute_total_amount()
            payload = {
                'userId': self.user_data.get('_id') or self.user_data.get('userID'),
                'username': self.user_data.get('username', 'User'),
                'productId': (
                    self.selected_product.get('productID')
                    or self.selected_product.get('product_id')
                    or ''
                ),
                'productName': self.selected_product.get('name') or self.selected_product.get('type') or 'Confidex Kit',
                'productType': self.selected_product.get('type') or '',
                'originalPrice': self.selected_product.get('price') or 0,
                'discountPercent': self.discount or 0,
                'amount': amount,
                'currency': 'PHP',
            }

            response = api_client.create_paymongo_checkout(payload)
            data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}

            if not response.ok:
                raise RuntimeError(data.get('error') or 'Failed to create PayMongo checkout session.')

            session_id = data.get('sessionId')
            checkout_url = data.get('checkoutUrl')
            reference = data.get('referenceNumber') or data.get('reference') or session_id

            if not session_id or not checkout_url:
                raise RuntimeError('Missing sessionId or checkoutUrl from backend.')

            self.payment_mode = str(data.get('mode', 'test')).lower()
            self.simulated = bool(data.get('simulated', self.payment_mode == 'test'))

            print('\n' + '=' * 60, flush=True)
            print('[PAYMONGO] Checkout session created')
            print(f'[PAYMONGO] MODE: {self.payment_mode.upper()}', flush=True)
            print(f'[PAYMONGO] SIMULATED: {self.simulated}', flush=True)
            print(f'[PAYMONGO] SESSION ID: {session_id}', flush=True)
            print(f'[PAYMONGO] REFERENCE: {reference}', flush=True)
            print('=' * 60 + '\n', flush=True)

            self.after(0, lambda: self._on_checkout_created(
                session_id=session_id,
                checkout_url=checkout_url,
                reference=reference,
                amount=amount
            ))

        except Exception as e:
            self.after(0, lambda err=str(e): self._on_checkout_error(err))

    def _on_checkout_created(self, session_id, checkout_url, reference, amount):
        if self.redirecting_to_cash:
            return

        self.request_in_progress = False
        self.payment_session_id = session_id
        self.payment_checkout_url = checkout_url
        self.payment_reference = reference
        self.payment_amount = amount
        self.payment_status = 'pending'

        try:
            self._render_qr(checkout_url)
        except Exception as e:
            self._redirect_to_cash_with_error(f'Unable to render QR code. {e}')
            return

        if self.payment_mode == 'test':
            details_text = (
                'TEST MODE (Simulated Payment)\n\n'
                f'Reference: {reference}\n'
                f'Amount: ₱{amount:.2f}\n'
                f'Product: {self.selected_product.get("type", "Test Kit")}'
            )
        else:
            details_text = (
                f'Reference: {reference}\n'
                f'Amount: ₱{amount:.2f}\n'
                f'Product: {self.selected_product.get("type", "Test Kit")}'
            )

        self.details_label.configure(text=details_text)

        if self.payment_mode == 'test':
            self.status_label.configure(
                text='Waiting for simulated payment confirmation...',
                text_color=theme.ORANGE
            )
        else:
            self.status_label.configure(
                text='Waiting for payment confirmation...',
                text_color=theme.ORANGE
            )

    def _on_checkout_error(self, error_message):
        self.request_in_progress = False
        self._redirect_to_cash_with_error(error_message)

    def _compute_total_amount(self):
        price = float(self.selected_product.get('price', 0) or 0)
        discount = float(self.discount or 0)
        total = price * (1 - discount / 100.0)
        return round(max(total, 0), 2)

    def _render_qr(self, text):
        if ImageTk is None:
            raise RuntimeError('Pillow is not installed, so the QR image cannot be displayed.')

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2
        )
        qr.add_data(text)
        qr.make(fit=True)

        img = qr.make_image(fill_color='black', back_color='white').convert('RGB')
        img = img.resize((self.QR_SIZE, self.QR_SIZE))
        self.qr_photo = ImageTk.PhotoImage(img)

        self.qr_label.configure(image=self.qr_photo, text='')

        self._start_polling()

    def _start_polling(self):
        if self.redirecting_to_cash:
            return
        self._stop_polling()
        self.poll_job = self.after(self.POLL_INTERVAL_MS, self._poll_status)

    def _stop_polling(self):
        if self.poll_job is not None:
            try:
                self.after_cancel(self.poll_job)
            except Exception:
                pass
            self.poll_job = None

    def _cancel_redirect(self):
        if self.redirect_job is not None:
            try:
                self.after_cancel(self.redirect_job)
            except Exception:
                pass
            self.redirect_job = None

    def _poll_status(self):
        self.poll_job = None
        if not self.payment_session_id or self.redirecting_to_cash:
            return
        threading.Thread(target=self._fetch_status, daemon=True).start()

    def manual_check_status(self):
        if not self.payment_session_id or self.redirecting_to_cash:
            return
        self.status_label.configure(
            text='Checking payment status...',
            text_color=theme.INFO
        )
        threading.Thread(target=self._fetch_status, daemon=True).start()

    def _fetch_status(self):
        try:
            response = api_client.get_paymongo_checkout_status(self.payment_session_id)
            data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}

            if not response.ok:
                raise RuntimeError(data.get('error') or 'Failed to get payment status.')

            status = str(data.get('status', 'pending')).lower()
            paid = bool(data.get('paid', False))

            self.payment_mode = str(data.get('mode', self.payment_mode)).lower()
            self.simulated = bool(data.get('simulated', self.payment_mode == 'test'))

            print('[PAYMONGO] Status check', flush=True)
            print(f'[PAYMONGO] MODE: {self.payment_mode.upper()}', flush=True)
            print(f'[PAYMONGO] SIMULATED: {self.simulated}', flush=True)
            print(f'[PAYMONGO] STATUS: {status}', flush=True)
            print(f'[PAYMONGO] PAID: {paid}', flush=True)
            print('-' * 60, flush=True)

            self.after(0, lambda: self._handle_status(status, paid))

        except Exception as e:
            self.after(0, lambda err=str(e): self._handle_status_error(err))

    def _handle_status(self, status, paid):
        if self.redirecting_to_cash:
            return

        self.payment_status = status

        if paid or status in ('paid', 'completed', 'succeeded'):
            self.status_label.configure(
                text='Payment confirmed. Finalizing purchase...',
                text_color=theme.SUCCESS
            )
            self._stop_polling()
            self.after(800, self.finish_online_payment)
            return

        if status in ('failed', 'expired', 'cancelled'):
            self._redirect_to_cash_with_error(
                f'Online payment {status}. Redirecting to cash payment...'
            )
            return

        if self.payment_mode == 'test':
            self.status_label.configure(
                text='Waiting for simulated payment confirmation...',
                text_color=theme.ORANGE
            )
        else:
            self.status_label.configure(
                text='Waiting for payment confirmation...',
                text_color=theme.ORANGE
            )

        self._start_polling()

    def _handle_status_error(self, error_message):
        self._redirect_to_cash_with_error(
            f'Status check failed: {error_message}'
        )

    def _redirect_to_cash_with_error(self, error_message):
        if self.redirecting_to_cash:
            return

        print('[PAYMONGO] Redirecting to cash because of error:', flush=True)
        print(f'[PAYMONGO] {error_message}', flush=True)

        self.redirecting_to_cash = True
        self.request_in_progress = False
        self._stop_polling()
        self._cancel_redirect()

        self.status_label.configure(
            text=f'{error_message}\nRedirecting to cash payment...',
            text_color=theme.ERROR
        )
        self.qr_label.configure(image=None, text='Online payment unavailable.')
        self.details_label.configure(text='')

        self.refresh_btn.configure(state='disabled')
        self.cancel_btn.configure(state='disabled')
        self.back_btn.configure(state='disabled')

        self.redirect_job = self.after(
            self.ERROR_REDIRECT_DELAY_MS,
            self._go_to_cash_payment
        )

    def _go_to_cash_payment(self):
        self.redirect_job = None
        self.controller.show_loading_then(
            'Redirecting to cash payment',
            'CashPaymentPage',
            delay=3000,
            user_data=self.user_data,
            selected_product=self.selected_product,
            discount=self.discount
        )

    def finish_online_payment(self):
        print('\n' + '=' * 60)
        print('[PAYMONGO] Payment confirmed', flush=True)
        print(f'[PAYMONGO] MODE: {self.payment_mode.upper()}', flush=True)
        print(f'[PAYMONGO] SIMULATED: {self.simulated}', flush=True)
        print(f'[PAYMONGO] SESSION ID: {self.payment_session_id}', flush=True)
        print(f'[PAYMONGO] REFERENCE: {self.payment_reference}', flush=True)
        print(f'[PAYMONGO] AMOUNT: {self.payment_amount}', flush=True)
        print('=' * 60 + '\n', flush=True)

        self.controller.show_loading_then(
            'Payment confirmed. Generating receipt',
            'ReceiptPage',
            delay=800,
            user_data=self.user_data,
            product=self.selected_product,
            discount=self.discount,
            total_paid=self.payment_amount,
            change=0,
            total=self.payment_amount,
            online_payment=True,
            payment_method='paymongo',
            payment_session_id=self.payment_session_id,
            payment_reference=self.payment_reference,
            payment_amount=self.payment_amount,
            payment_mode=self.payment_mode,
            simulated=self.simulated
        )

    def cancel_and_go_back(self):
        if self.redirecting_to_cash:
            return

        self._stop_polling()
        self._cancel_redirect()
        self._reset_state()
        self.controller.show_loading_then(
            'Returning to payment methods',
            'PaymentMethodPage',
            delay=800,
            user_data=self.user_data,
            selected_product=self.selected_product,
            discount=self.discount
        )

    def go_back(self):
        self.cancel_and_go_back()

    def _reset_state(self):
        self.payment_session_id = None
        self.payment_checkout_url = None
        self.payment_reference = None
        self.payment_amount = 0
        self.payment_status = None
        self.payment_mode = 'test'
        self.simulated = True
        self.qr_photo = None
        self.request_in_progress = False
        self.redirecting_to_cash = False

        try:
            self.refresh_btn.configure(state='normal')
            self.cancel_btn.configure(state='normal')
            self.back_btn.configure(state='normal')
        except Exception:
            pass

    def destroy(self):
        self._stop_polling()
        self._cancel_redirect()
        super().destroy()