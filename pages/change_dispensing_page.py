from frontend import tk_compat as ctk
from frontend import theme
from frontend.widgets import AppShell, RoundedCard, PillButton, card_body

import threading

from backend.util.dispenser_serial import send_change_command


class ChangeDispensingPage(ctk.CTkFrame):
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
        self.payment_method = "cash"
        self.payment_session_id = None
        self.payment_reference = None
        self.payment_amount = None
        self.payment_mode = None
        self.simulated = False
        self.transaction_id = None

        self.dispense_started = False
        self.dispense_finished = False
        self.redirect_scheduled = False
        self.result = None

        self._dot_job = None
        self._dot_count = 0
        self._animating = False

        self.shell = AppShell(self, title_right="Dispensing Change")
        self.shell.pack(fill="both", expand=True)

        top_bar = ctk.CTkFrame(self.shell.body, fg_color="transparent")
        top_bar.pack(fill="x", padx=28, pady=(16, 8))
        top_bar.grid_columnconfigure(0, weight=0)
        top_bar.grid_columnconfigure(1, weight=1)
        top_bar.grid_columnconfigure(2, weight=0)

        self.back_btn = PillButton(
            top_bar,
            text="Back",
            width=130,
            height=58,
            command=self.go_back,
            font=theme.font(18, "bold")
        )
        self.back_btn.grid(row=0, column=0, sticky="w")

        self.page_title = ctk.CTkLabel(
            top_bar,
            text="DISPENSING CHANGE",
            font=theme.heavy(32),
            text_color=theme.BLACK
        )
        self.page_title.grid(row=0, column=1)

        content_wrap = ctk.CTkFrame(self.shell.body, fg_color="transparent")
        content_wrap.pack(expand=True, fill="both", padx=28, pady=(6, 18))
        content_wrap.grid_columnconfigure(0, weight=1)
        content_wrap.grid_rowconfigure(0, weight=1)
        content_wrap.grid_rowconfigure(1, weight=0)
        content_wrap.grid_rowconfigure(2, weight=1)

        self.card = RoundedCard(content_wrap, auto_size=True, pad=18)
        self.card.grid(row=1, column=0)

        body = card_body(self.card)
        body.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            body,
            text="PLEASE COLLECT YOUR CHANGE",
            font=theme.heavy(30),
            text_color=theme.BLACK,
            fg_color=theme.WHITE
        )
        self.title_label.grid(row=0, column=0, padx=20, pady=(14, 12))

        self.amount_label = ctk.CTkLabel(
            body,
            text="",
            font=theme.heavy(42),
            text_color=theme.ORANGE,
            fg_color=theme.WHITE,
            justify="center"
        )
        self.amount_label.grid(row=1, column=0, padx=20, pady=(4, 12), sticky="ew")

        self.info_label = ctk.CTkLabel(
            body,
            text="The machine is preparing your coins.",
            font=theme.font(20, "bold"),
            text_color=theme.MUTED,
            fg_color=theme.WHITE,
            wraplength=760,
            justify="center"
        )
        self.info_label.grid(row=2, column=0, padx=24, pady=(4, 10), sticky="ew")

        self.status_label = ctk.CTkLabel(
            body,
            text="Starting coin dispensing...",
            font=theme.font(20, "bold"),
            text_color=theme.INFO,
            fg_color=theme.WHITE,
            wraplength=760,
            justify="center"
        )
        self.status_label.grid(row=3, column=0, padx=24, pady=(0, 10), sticky="ew")

        self.breakdown_label = ctk.CTkLabel(
            body,
            text="",
            font=theme.font(18, "bold"),
            text_color=theme.MUTED,
            fg_color=theme.WHITE,
            wraplength=760,
            justify="center"
        )
        self.breakdown_label.grid(row=4, column=0, padx=24, pady=(0, 10), sticky="ew")

        self.stock_label = ctk.CTkLabel(
            body,
            text="",
            font=theme.font(15, "bold"),
            text_color=theme.MUTED,
            fg_color=theme.WHITE,
            wraplength=760,
            justify="center"
        )
        self.stock_label.grid(row=5, column=0, padx=24, pady=(0, 14), sticky="ew")

        self.continue_btn = PillButton(
            body,
            text="Continue to Receipt",
            width=240,
            height=56,
            command=self._redirect_to_receipt,
            font=theme.font(16, "bold"),
        )
        self.continue_btn.grid(row=6, column=0, pady=(6, 24))
        self.continue_btn.configure(state="disabled")

    def update_data(
        self,
        user_data=None,
        product=None,
        discount=0,
        total_paid=0,
        change=0,
        total=0,
        online_payment=False,
        payment_method="cash",
        payment_session_id=None,
        payment_reference=None,
        payment_amount=None,
        payment_mode=None,
        simulated=False,
        transaction_id=None,
        **kwargs
    ):
        print("[CHANGE] update_data called", flush=True)

        self.user_data = user_data or {}
        self.product = product or kwargs.get("selected_product") or {}
        self.discount = float(discount or 0)
        self.total_paid = float(total_paid or 0)
        self.change = float(change or 0)
        self.total = float(total or 0)

        self.online_payment = bool(online_payment)
        self.payment_method = payment_method or "cash"
        self.payment_session_id = payment_session_id
        self.payment_reference = payment_reference
        self.payment_amount = payment_amount
        self.payment_mode = payment_mode
        self.simulated = bool(simulated)
        self.transaction_id = transaction_id

        self.dispense_started = False
        self.dispense_finished = False
        self.redirect_scheduled = False
        self.result = None

        username = self.user_data.get("username", "User")
        self.shell.set_header_right(f"Welcome, {username}!")

        self.amount_label.configure(text=f"₱{self.change:.2f}")
        self.info_label.configure(
            text=(
                "Please wait while the machine dispenses your change.\n"
                "Collect all coins from the tray before proceeding."
            )
        )
        self.breakdown_label.configure(text="")
        self.stock_label.configure(text="")
        self.continue_btn.configure(state="disabled")

        if self.change <= 0:
            self.status_label.configure(
                text="No change to dispense. Redirecting to receipt...",
                text_color=theme.SUCCESS
            )
            self.after(700, self._redirect_to_receipt)
            return

        self._start_status_animation("Dispensing coins", theme.INFO)
        self.after(150, self._start_dispensing_once)

    def _start_dispensing_once(self):
        if self.dispense_started:
            return
        self.dispense_started = True
        threading.Thread(target=self._dispense_change_thread, daemon=True).start()

    def _dispense_change_thread(self):
        try:
            amount = int(round(self.change))
            print(f"[CHANGE] Sending change command for amount={amount}", flush=True)

            result = send_change_command(amount)
            print(f"[CHANGE] send_change_command result={result}", flush=True)

            self.after(0, lambda r=result: self._on_dispense_finished(r))

        except Exception as e:
            print(f"[CHANGE] dispense thread exception: {e}", flush=True)
            self.after(0, lambda err=str(e): self._on_dispense_failed(err))

    def _on_dispense_finished(self, result):
        self.dispense_finished = True
        self.result = result or {}
        self._stop_status_animation()

        success = bool(self.result.get("success"))
        message = str(self.result.get("message") or "")
        stock = self.result.get("stock") or {}

        if success:
            self.status_label.configure(
                text="Change dispensed successfully.",
                text_color=theme.SUCCESS
            )

            breakdown = self._extract_breakdown(message)
            if breakdown:
                self.breakdown_label.configure(
                    text=f"Dispensed coins: {breakdown}",
                    text_color=theme.BLACK
                )
            else:
                self.breakdown_label.configure(
                    text=message or "Coin dispensing completed.",
                    text_color=theme.BLACK
                )

            stock_text = self._format_stock(stock)
            self.stock_label.configure(
                text=stock_text if stock_text else "",
                text_color=theme.MUTED
            )

            self.continue_btn.configure(state="normal")

            if not self.redirect_scheduled:
                self.redirect_scheduled = True
                self.after(1200, self._redirect_to_receipt)
        else:
            self.status_label.configure(
                text="Coin dispensing failed.",
                text_color=theme.ERROR
            )
            self.breakdown_label.configure(
                text=message or "The machine did not confirm change dispensing.",
                text_color=theme.ERROR
            )

            stock_text = self._format_stock(stock)
            self.stock_label.configure(
                text=stock_text if stock_text else "",
                text_color=theme.MUTED
            )

            self.continue_btn.configure(state="normal")

    def _on_dispense_failed(self, error_text):
        self.dispense_finished = True
        self._stop_status_animation()

        self.status_label.configure(
            text="Coin dispensing failed.",
            text_color=theme.ERROR
        )
        self.breakdown_label.configure(
            text=error_text or "Unknown dispensing error.",
            text_color=theme.ERROR
        )
        self.stock_label.configure(text="")
        self.continue_btn.configure(state="normal")

    def _extract_breakdown(self, message: str) -> str:
        upper = str(message or "").strip()
        if upper.upper().startswith("CHANGE_DISPENSED:"):
            return upper.split(":", 1)[1].strip()
        return ""

    def _format_stock(self, stock: dict) -> str:
        if not isinstance(stock, dict) or not stock:
            return ""

        count1 = stock.get(1, stock.get("1"))
        count5 = stock.get(5, stock.get("5"))
        count20 = stock.get(20, stock.get("20"))

        parts = []
        if count1 is not None:
            parts.append(f"₱1: {count1}")
        if count5 is not None:
            parts.append(f"₱5: {count5}")
        if count20 is not None:
            parts.append(f"₱20: {count20}")

        if not parts:
            return ""

        return "Remaining coin stock: " + " | ".join(parts)

    def _start_status_animation(self, base_text="Dispensing coins", color=None):
        self._stop_status_animation()
        self._animating = True
        self._base_status_text = base_text
        self._status_color = color or theme.INFO
        self._dot_count = 0
        self._animate_status_text()

    def _stop_status_animation(self):
        self._animating = False
        if self._dot_job is not None:
            try:
                self.after_cancel(self._dot_job)
            except Exception:
                pass
            self._dot_job = None

    def _animate_status_text(self):
        if not self._animating:
            return

        self._dot_count = (self._dot_count + 1) % 4
        dots = "." * self._dot_count

        self.status_label.configure(
            text=f"{self._base_status_text}{dots}",
            text_color=self._status_color
        )

        self._dot_job = self.after(450, self._animate_status_text)

    def go_back(self):
        if not self.dispense_finished:
            print("[CHANGE] Back blocked while dispensing is in progress", flush=True)
            return
        self._redirect_to_receipt()

    def _redirect_to_receipt(self):
        print(f"[CHANGE] Redirecting to ReceiptPage | transaction_id={self.transaction_id}", flush=True)

        self.controller.show_loading_then(
            "Preparing receipt",
            "ReceiptPage",
            delay=800,
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

    def destroy(self):
        self._stop_status_animation()
        super().destroy()