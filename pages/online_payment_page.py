from frontend import tk_compat as ctk
from frontend import theme
from frontend.widgets import AppShell, RoundedCard, PillButton, card_body
from backend.util import api_client
from config_manager import config

import threading
import qrcode

try:
    from PIL import ImageTk
except Exception:
    ImageTk = None


class OnlinePaymentPage(ctk.CTkFrame):
    CONTENT_WRAPLENGTH = 760
    DETAILS_WRAPLENGTH = 760
    STATUS_WRAPLENGTH = 760
    REFRESH_MS = 1500

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
        self.payment_mode = "test"
        self.simulated = True
        self.website_transaction_id = None

        self.poll_job = None
        self.redirect_job = None
        self.qr_photo = None

        self.request_in_progress = False
        self.status_request_in_progress = False
        self.redirecting_to_cash = False
        self.finalizing_purchase = False

        self.status_error_count = 0
        self.checkout_request_token = 0
        self.active_request_token = 0
        self._config_refresh_job = None

        self.shell = AppShell(self, title_right="Welcome, User!")
        self.shell.pack(fill="both", expand=True)

        top_bar = ctk.CTkFrame(self.shell.body, fg_color="transparent")
        top_bar.pack(fill="x", padx=24, pady=(14, 8))
        top_bar.grid_columnconfigure(0, weight=0)
        top_bar.grid_columnconfigure(1, weight=1)
        top_bar.grid_columnconfigure(2, weight=0)

        self.back_btn = PillButton(
            top_bar,
            text=config.get("online_payment_page", "back_button_text", default="Back"),
            width=120,
            height=52,
            command=self.go_back,
            font=theme.font(16, "bold")
        )
        self.back_btn.grid(row=0, column=0, sticky="w")

        self.title_label = ctk.CTkLabel(
            top_bar,
            text=config.get("online_payment_page", "title", default="ONLINE PAYMENT"),
            font=theme.heavy(28),
            text_color=theme.BLACK
        )
        self.title_label.grid(row=0, column=1)

        content_wrap = ctk.CTkFrame(self.shell.body, fg_color="transparent")
        content_wrap.pack(expand=True, fill="both", padx=24, pady=(6, 18))
        content_wrap.grid_columnconfigure(0, weight=1)
        content_wrap.grid_rowconfigure(0, weight=1)

        self.main_card = RoundedCard(content_wrap, auto_size=False, pad=16)
        self.main_card.grid(row=0, column=0, sticky="nsew")

        body = card_body(self.main_card)
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=0)
        body.grid_rowconfigure(1, weight=0)
        body.grid_rowconfigure(2, weight=1)
        body.grid_rowconfigure(3, weight=0)
        body.grid_rowconfigure(4, weight=0)

        self.desc_label = ctk.CTkLabel(
            body,
            text=config.get(
                "online_payment_page",
                "description",
                default="Scan the QR code using GCash, Maya, or another supported e-wallet."
            ),
            font=theme.font(18, "bold"),
            text_color=theme.MUTED,
            fg_color=theme.WHITE,
            wraplength=self.CONTENT_WRAPLENGTH,
            justify="center"
        )
        self.desc_label.grid(row=0, column=0, padx=18, pady=(8, 10), sticky="ew")

        self.qr_frame = ctk.CTkFrame(body, fg_color=theme.WHITE)
        self.qr_frame.grid(row=1, column=0, pady=(0, 12), sticky="n")
        self.qr_frame.grid_columnconfigure(0, weight=1)

        self.qr_label = ctk.CTkLabel(
            self.qr_frame,
            text=config.get("online_payment_page", "preparing_qr_text", default="Preparing payment QR..."),
            font=theme.font(16, "bold"),
            text_color=theme.MUTED,
            fg_color=theme.WHITE,
            wraplength=420,
            justify="center"
        )
        self.qr_label.pack(padx=18, pady=18)

        self.details_label = ctk.CTkLabel(
            body,
            text="",
            font=theme.font(16, "bold"),
            text_color=theme.BLACK,
            fg_color=theme.WHITE,
            justify="center",
            wraplength=self.DETAILS_WRAPLENGTH
        )
        self.details_label.grid(row=2, column=0, padx=18, pady=(0, 10), sticky="new")

        self.status_label = ctk.CTkLabel(
            body,
            text="",
            font=theme.font(16, "bold"),
            text_color=theme.ORANGE,
            fg_color=theme.WHITE,
            wraplength=self.STATUS_WRAPLENGTH,
            justify="center"
        )
        self.status_label.grid(row=3, column=0, padx=18, pady=(0, 10), sticky="ew")

        btn_row = ctk.CTkFrame(body, fg_color=theme.WHITE)
        btn_row.grid(row=4, column=0, pady=(4, 8), padx=8, sticky="ew")
        btn_row.grid_columnconfigure(0, weight=1)
        btn_row.grid_columnconfigure(1, weight=1)

        self.refresh_btn = PillButton(
            btn_row,
            text=config.get("online_payment_page", "refresh_button_text", default="Refresh Status"),
            width=180,
            height=54,
            command=self.manual_check_status,
            font=theme.font(16, "bold")
        )
        self.refresh_btn.grid(row=0, column=0, padx=10, sticky="e")

        self.cancel_btn = PillButton(
            btn_row,
            text=config.get("online_payment_page", "cancel_button_text", default="Cancel"),
            width=180,
            height=54,
            command=self.cancel_and_go_back,
            font=theme.font(16, "bold")
        )
        self.cancel_btn.grid(row=0, column=1, padx=10, sticky="w")

        self.bind("<Configure>", self._on_resize)
        self._start_config_refresh()

    def _poll_interval_ms(self):
        return int(config.get("online_payment_page", "poll_interval_ms", default=3000))

    def _error_redirect_delay_ms(self):
        return int(config.get("online_payment_page", "error_redirect_delay_ms", default=1800))

    def _qr_size(self):
        return int(config.get("online_payment_page", "qr_size", default=300))

    def _max_status_errors(self):
        return int(config.get("online_payment_page", "max_status_errors", default=3))

    def _refresh_from_config(self):
        try:
            self.back_btn.configure(text=config.get("online_payment_page", "back_button_text", default="Back"))
            self.title_label.configure(text=config.get("online_payment_page", "title", default="ONLINE PAYMENT"))
            self.desc_label.configure(
                text=config.get(
                    "online_payment_page",
                    "description",
                    default="Scan the QR code using GCash, Maya, or another supported e-wallet."
                )
            )
            self.refresh_btn.configure(
                text=config.get("online_payment_page", "refresh_button_text", default="Refresh Status")
            )
            self.cancel_btn.configure(
                text=config.get("online_payment_page", "cancel_button_text", default="Cancel")
            )
        except Exception as e:
            print(f"[ONLINE PAYMENT] Config refresh failed: {e}", flush=True)

    def _start_config_refresh(self):
        self._refresh_from_config()
        self._config_refresh_job = self.after(self.REFRESH_MS, self._start_config_refresh)

    def _on_resize(self, event=None):
        try:
            total_width = max(self.winfo_width(), 900)
            content_width = max(520, total_width - 220)
            wrapped = min(content_width, 820)

            self.desc_label.configure(wraplength=wrapped)
            self.details_label.configure(wraplength=wrapped)
            self.status_label.configure(wraplength=wrapped)
        except Exception:
            pass

    def _reset_state(self):
        self.payment_session_id = None
        self.payment_checkout_url = None
        self.payment_reference = None
        self.payment_amount = 0
        self.payment_status = None
        self.payment_mode = "test"
        self.simulated = True
        self.website_transaction_id = None
        self.request_in_progress = False
        self.status_request_in_progress = False
        self.redirecting_to_cash = False
        self.finalizing_purchase = False
        self.status_error_count = 0
        self.refresh_btn.configure(state="normal")
        self.cancel_btn.configure(state="normal")
        self.back_btn.configure(state="normal")

    def update_data(self, user_data=None, selected_product=None, discount=0, **kwargs):
        self._stop_polling()
        self._cancel_redirect()

        self.checkout_request_token += 1
        self.active_request_token = self.checkout_request_token

        self._reset_state()

        self.user_data = user_data or {}
        self.selected_product = selected_product or kwargs.get("product")
        self.discount = float(discount or 0)

        self.shell.set_header_right(f"Welcome, {self.user_data.get('username', 'User')}!")
        self._clear_qr_display()
        self.details_label.configure(text="")
        self.status_label.configure(
            text=config.get(
                "online_payment_page",
                "creating_session_text",
                default="Creating PayMongo payment session..."
            ),
            text_color=theme.INFO
        )

        self.after(150, lambda token=self.active_request_token: self.start_online_payment(token))

    def _clear_qr_display(self, placeholder=None):
        self.qr_photo = None
        placeholder = placeholder or config.get(
            "online_payment_page",
            "preparing_qr_text",
            default="Preparing payment QR..."
        )

        try:
            self.qr_label.image = None
        except Exception:
            pass

        try:
            self.qr_label.configure(image="")
        except Exception:
            pass

        try:
            self.qr_label.configure(text=placeholder)
        except Exception:
            pass

    def _is_stale(self, token):
        return token != self.active_request_token

    def _compute_total_amount(self):
        if not self.selected_product:
            return 0.0

        price = float(self.selected_product.get("price", 0) or 0)
        discount = float(self.discount or 0)
        total = price * (1 - discount / 100.0)
        return round(max(total, 0), 2)

    def _build_transaction_payload(self):
        product_id = (
            self.selected_product.get("productID")
            or self.selected_product.get("product_id")
            or self.selected_product.get("id")
            or ""
        )

        product_name = (
            self.selected_product.get("name")
            or self.selected_product.get("type")
            or "Confidex Kit"
        )

        product_type = self.selected_product.get("type") or ""

        total_amount = self._compute_total_amount()
        user_id = self.user_data.get("_id") or self.user_data.get("userID")

        return {
            "user_id": user_id,
            "status": "completed",
            "purchasedDate": None,
            "items": [
                {
                    "name": product_name,
                    "productID": product_id,
                    "type": product_type,
                    "price": float(self.selected_product.get("price", 0) or 0),
                    "discount": float(self.discount or 0),
                    "finalPrice": total_amount,
                    "result": "Pending",
                }
            ],
        }

    def start_online_payment(self, token):
        if self._is_stale(token):
            return

        if self.request_in_progress or self.redirecting_to_cash or self.finalizing_purchase:
            return

        if not self.selected_product:
            self._redirect_to_cash_with_error(
                config.get("online_payment_page", "no_product_text", default="No product selected.")
            )
            return

        self.request_in_progress = True
        threading.Thread(target=self._create_checkout_session, args=(token,), daemon=True).start()

    def _create_checkout_session(self, token):
        try:
            amount = self._compute_total_amount()
            payload = {
                "userId": self.user_data.get("_id") or self.user_data.get("userID"),
                "username": self.user_data.get("username", "User"),
                "productId": (
                    self.selected_product.get("productID")
                    or self.selected_product.get("product_id")
                    or ""
                ),
                "productName": self.selected_product.get("name") or self.selected_product.get("type") or "Confidex Kit",
                "productType": self.selected_product.get("type") or "",
                "originalPrice": self.selected_product.get("price") or 0,
                "discountPercent": self.discount or 0,
                "amount": amount,
                "currency": "PHP",
            }

            response = api_client.create_paymongo_checkout(payload)
            data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}

            if not response.ok:
                raise RuntimeError(data.get("error") or "Failed to create PayMongo checkout session.")

            session_id = data.get("sessionId")
            checkout_url = data.get("checkoutUrl")
            reference = data.get("referenceNumber") or data.get("reference") or session_id

            if not session_id or not checkout_url:
                raise RuntimeError("Missing sessionId or checkoutUrl from backend.")

            payment_mode = str(data.get("mode", "test")).lower()
            simulated = bool(data.get("simulated", payment_mode == "test"))

            self.after(0, lambda: self._on_checkout_created(
                token=token,
                session_id=session_id,
                checkout_url=checkout_url,
                reference=reference,
                amount=amount,
                payment_mode=payment_mode,
                simulated=simulated
            ))

        except Exception as e:
            self.after(0, lambda err=str(e): self._on_checkout_error(token, err))

    def _on_checkout_created(self, token, session_id, checkout_url, reference, amount, payment_mode, simulated):
        if self._is_stale(token) or self.redirecting_to_cash:
            return

        self.request_in_progress = False
        self.status_error_count = 0

        self.payment_session_id = session_id
        self.payment_checkout_url = checkout_url
        self.payment_reference = reference
        self.payment_amount = amount
        self.payment_status = "pending"
        self.payment_mode = payment_mode
        self.simulated = simulated

        try:
            self._render_qr(checkout_url)
        except Exception as e:
            self._redirect_to_cash_with_error(
                f"{config.get('online_payment_page', 'render_qr_error_prefix', default='Unable to render QR code.')} {e}"
            )
            return

        if self.payment_mode == "test":
            details_text = (
                f"{config.get('online_payment_page', 'test_mode_header', default='TEST MODE (Simulated Payment)')}\n\n"
                f"{config.get('online_payment_page', 'reference_label', default='Reference')}: {reference}\n"
                f"{config.get('online_payment_page', 'amount_label', default='Amount')}: ₱{amount:.2f}\n"
                f"{config.get('online_payment_page', 'product_label', default='Product')}: {self.selected_product.get('type', 'Test Kit')}"
            )
        else:
            details_text = (
                f"{config.get('online_payment_page', 'reference_label', default='Reference')}: {reference}\n"
                f"{config.get('online_payment_page', 'amount_label', default='Amount')}: ₱{amount:.2f}\n"
                f"{config.get('online_payment_page', 'product_label', default='Product')}: {self.selected_product.get('type', 'Test Kit')}"
            )

        self.details_label.configure(text=details_text)

        if self.payment_mode == "test":
            self.status_label.configure(
                text=config.get(
                    "online_payment_page",
                    "waiting_simulated_text",
                    default="Waiting for simulated payment confirmation."
                ),
                text_color=theme.ORANGE
            )
        else:
            self.status_label.configure(
                text=config.get(
                    "online_payment_page",
                    "waiting_payment_text",
                    default="Waiting for payment confirmation."
                ),
                text_color=theme.ORANGE
            )

    def _on_checkout_error(self, token, error_message):
        if self._is_stale(token):
            return

        self.request_in_progress = False
        print(f"[PAYMONGO] Checkout creation failed: {error_message}", flush=True)
        self._redirect_to_cash_with_error(error_message)

    def _render_qr(self, text):
        if ImageTk is None:
            raise RuntimeError("Pillow is not installed, so the QR image cannot be displayed.")

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=2
        )
        qr.add_data(text)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        size = self._qr_size()
        img = img.resize((size, size))
        self.qr_photo = ImageTk.PhotoImage(img)

        self.qr_label.configure(text="")
        self.qr_label.configure(image=self.qr_photo)
        self.qr_label.image = self.qr_photo

        self._start_polling()

    def _start_polling(self):
        if self.redirecting_to_cash or self.finalizing_purchase:
            return

        self._stop_polling()
        self.poll_job = self.after(self._poll_interval_ms(), self._poll_status)

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

        if (
            not self.payment_session_id
            or self.redirecting_to_cash
            or self.finalizing_purchase
            or self.status_request_in_progress
        ):
            return

        token = self.active_request_token
        self.status_request_in_progress = True
        threading.Thread(target=self._fetch_status, args=(token, False), daemon=True).start()

    def manual_check_status(self):
        if (
            not self.payment_session_id
            or self.redirecting_to_cash
            or self.finalizing_purchase
            or self.status_request_in_progress
        ):
            return

        self.status_label.configure(
            text=config.get("online_payment_page", "checking_status_text", default="Checking payment status..."),
            text_color=theme.INFO
        )
        token = self.active_request_token
        self.status_request_in_progress = True
        threading.Thread(target=self._fetch_status, args=(token, True), daemon=True).start()

    def _fetch_status(self, token, manual):
        try:
            response = api_client.get_paymongo_checkout_status(self.payment_session_id)
            data = response.json() if response.headers.get("content-type", "").startswith("application/json") else {}

            if not response.ok:
                raise RuntimeError(data.get("error") or "Failed to get payment status.")

            status = str(data.get("status", "pending")).lower()
            paid = bool(data.get("paid", False))
            payment_mode = str(data.get("mode", self.payment_mode)).lower()
            simulated = bool(data.get("simulated", payment_mode == "test"))

            self.after(0, lambda: self._handle_status(token, status, paid, payment_mode, simulated))

        except Exception as e:
            print(f"[PAYMONGO] Status check error: {e}", flush=True)
            self.after(0, lambda err=str(e): self._handle_status_error(token, err, manual))

    def _handle_status(self, token, status, paid, payment_mode, simulated):
        self.status_request_in_progress = False

        if self._is_stale(token) or self.redirecting_to_cash:
            return

        self.payment_mode = payment_mode
        self.simulated = simulated
        self.payment_status = status
        self.status_error_count = 0

        if paid or status in ("paid", "completed", "succeeded"):
            print("[PAYMONGO] Payment confirmed", flush=True)
            self.status_label.configure(
                text=config.get(
                    "online_payment_page",
                    "payment_confirmed_saving_text",
                    default="Payment confirmed. Saving transaction..."
                ),
                text_color=theme.SUCCESS
            )
            self._stop_polling()
            self.after(300, self.finish_online_payment)
            return

        if status in ("failed", "expired", "cancelled"):
            print(f"[PAYMONGO] Payment ended with status: {status}", flush=True)
            self._redirect_to_cash_with_error(
                f"{config.get('online_payment_page', 'payment_failed_prefix', default='Payment failed with status:')} {status}"
            )
            return

        if self.payment_mode == "test":
            self.status_label.configure(
                text=config.get(
                    "online_payment_page",
                    "waiting_simulated_text",
                    default="Waiting for simulated payment confirmation."
                ),
                text_color=theme.ORANGE
            )
        else:
            self.status_label.configure(
                text=config.get(
                    "online_payment_page",
                    "waiting_payment_text",
                    default="Waiting for payment confirmation."
                ),
                text_color=theme.ORANGE
            )

        self._start_polling()

    def _handle_status_error(self, token, error_message, manual):
        self.status_request_in_progress = False

        if self._is_stale(token) or self.redirecting_to_cash:
            return

        self.status_error_count += 1

        if self.status_error_count < self._max_status_errors():
            if manual:
                self.status_label.configure(
                    text=(
                        f"{config.get('online_payment_page', 'status_check_failed_text', default='Status check failed.')}\n"
                        f"{error_message}\n"
                        f"{config.get('online_payment_page', 'try_again_text', default='You may try again.')}"
                    ),
                    text_color=theme.ERROR
                )
            else:
                self.status_label.configure(
                    text=config.get(
                        "online_payment_page",
                        "status_timeout_retrying_text",
                        default="Status check timed out. Retrying."
                    ),
                    text_color=theme.ERROR
                )
                self._start_polling()
            return

        self._redirect_to_cash_with_error(
            f"{config.get('online_payment_page', 'status_failed_repeatedly_prefix', default='Status check failed repeatedly:')} {error_message}"
        )

    def _redirect_to_cash_with_error(self, error_message):
        if self.redirecting_to_cash:
            return

        self.redirecting_to_cash = True
        self.request_in_progress = False
        self.status_request_in_progress = False
        self.finalizing_purchase = False

        self._stop_polling()
        self._cancel_redirect()

        self.status_label.configure(
            text=(
                f"{error_message}\n"
                f"{config.get('online_payment_page', 'redirecting_cash_suffix', default='Redirecting to cash payment.')}"
            ),
            text_color=theme.ERROR
        )
        self._clear_qr_display(config.get("online_payment_page", "unavailable_qr_text", default="Online payment unavailable."))
        self.details_label.configure(text="")

        self.refresh_btn.configure(state="disabled")
        self.cancel_btn.configure(state="disabled")
        self.back_btn.configure(state="disabled")

        if hasattr(self.controller, "show_error"):
            self.controller.show_error(
                f"Online payment failed.\n{error_message}",
                title="Online Payment Error"
            )

        self.redirect_job = self.after(self._error_redirect_delay_ms(), self._go_to_cash_payment)

    def _go_to_cash_payment(self):
        self.redirect_job = None
        self.controller.show_loading_then(
            config.get(
                "online_payment_page",
                "cash_redirect_loading_text",
                default="Redirecting to cash payment"
            ),
            "CashPaymentPage",
            delay=1000,
            user_data=self.user_data,
            selected_product=self.selected_product,
            discount=self.discount
        )

    def finish_online_payment(self):
        if self.finalizing_purchase:
            return

        self.finalizing_purchase = True
        self.refresh_btn.configure(state="disabled")
        self.cancel_btn.configure(state="disabled")
        self.back_btn.configure(state="disabled")

        self.status_label.configure(
            text=config.get(
                "online_payment_page",
                "payment_confirmed_saving_text",
                default="Payment confirmed. Saving transaction..."
            ),
            text_color=theme.SUCCESS
        )

        token = self.active_request_token
        threading.Thread(target=self._post_transaction_and_continue, args=(token,), daemon=True).start()

    def _post_transaction_and_continue(self, token):
        try:
            payload = self._build_transaction_payload()
            response = api_client.post_transaction(payload)

            if not response.ok:
                error_text = "Failed to save transaction."
                try:
                    data = response.json()
                    error_text = data.get("error") or error_text
                except Exception:
                    pass
                raise RuntimeError(error_text)

            website_transaction_id = None
            try:
                data = response.json()
                transaction_obj = data.get("transaction") or {}
                website_transaction_id = (
                    transaction_obj.get("_id")
                    or data.get("_id")
                    or data.get("transaction_id")
                    or data.get("id")
                )
            except Exception:
                pass

            self.after(0, lambda: self._on_transaction_saved(token, website_transaction_id))

        except Exception as e:
            self.after(0, lambda err=str(e): self._on_transaction_save_failed(token, err))

    def _on_transaction_saved(self, token, website_transaction_id=None):
        if self._is_stale(token) or self.redirecting_to_cash:
            return

        self.website_transaction_id = website_transaction_id

        print("[PAYMONGO] Transaction saved", flush=True)
        self.status_label.configure(
            text=config.get(
                "online_payment_page",
                "transaction_saved_text",
                default="Transaction saved. Generating receipt..."
            ),
            text_color=theme.SUCCESS
        )

        self.controller.show_loading_then(
            config.get(
                "online_payment_page",
                "receipt_loading_text",
                default="Payment confirmed. Generating receipt"
            ),
            "ReceiptPage",
            delay=800,
            user_data=self.user_data,
            product=self.selected_product,
            discount=self.discount,
            total_paid=self.payment_amount,
            change=0,
            total=self.payment_amount,
            online_payment=True,
            payment_method="paymongo",
            payment_session_id=self.payment_session_id,
            payment_reference=self.payment_reference,
            payment_amount=self.payment_amount,
            payment_mode=self.payment_mode,
            simulated=self.simulated,
            transaction_id=website_transaction_id
        )

    def _on_transaction_save_failed(self, token, error_message):
        if self._is_stale(token) or self.redirecting_to_cash:
            return

        self.finalizing_purchase = False
        self.refresh_btn.configure(state="normal")
        self.cancel_btn.configure(state="normal")
        self.back_btn.configure(state="normal")
        self.status_label.configure(
            text=f"{config.get('online_payment_page', 'save_failed_prefix', default='Failed to save transaction:')} {error_message}",
            text_color=theme.ERROR
        )

        if hasattr(self.controller, "show_error"):
            self.controller.show_error(
                f"Payment was confirmed, but saving the transaction failed.\n{error_message}",
                title="Transaction Save Error"
            )

    def go_back(self):
        if self.request_in_progress or self.status_request_in_progress or self.finalizing_purchase:
            return

        self._stop_polling()
        self._cancel_redirect()
        self._reset_state()

        self.controller.show_loading_then(
            config.get(
                "online_payment_page",
                "back_loading_text",
                default="Returning to payment options"
            ),
            "PaymentMethodPage",
            delay=1000,
            user_data=self.user_data,
            selected_product=self.selected_product,
            discount=self.discount
        )

    def cancel_and_go_back(self):
        self.go_back()

    def destroy(self):
        self._stop_polling()
        self._cancel_redirect()
        super().destroy()