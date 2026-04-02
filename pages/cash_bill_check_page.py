import tkinter as tk

from frontend import tk_compat as ctk
from frontend import theme
from frontend.widgets import AppShell, RoundedCard, PillButton, card_body
from frontend.components.keyboard import CashNumericKeyboard


class CashBillCheckPage(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color=theme.CREAM)
        self.controller = controller

        self.user_data = {}
        self.selected_product = None
        self.discount = 0

        self.stock1 = 100
        self.stock5 = 100
        self.stock20 = 100

        self.amount_var = tk.StringVar(value="")
        self._message_hide_job = None

        self.shell = AppShell(self, title_right="Cash Bill Check")
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
            text="ENTER CASH AMOUNT",
            font=theme.heavy(30),
            text_color=theme.BLACK
        )
        self.page_title.grid(row=0, column=1)

        self.content_wrap = ctk.CTkFrame(self.shell.body, fg_color="transparent")
        self.content_wrap.pack(fill="both", expand=True, padx=28, pady=(10, 18))

        self.content_wrap.grid_columnconfigure(0, weight=1, uniform="cashcols")
        self.content_wrap.grid_columnconfigure(1, weight=1, uniform="cashcols")
        self.content_wrap.grid_rowconfigure(0, weight=1)

        self.left_col = ctk.CTkFrame(self.content_wrap, fg_color="transparent")
        self.left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.left_col.grid_columnconfigure(0, weight=1)
        self.left_col.grid_rowconfigure(0, weight=1)

        self.right_col = ctk.CTkFrame(self.content_wrap, fg_color="transparent")
        self.right_col.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        self.right_col.grid_columnconfigure(0, weight=1)
        self.right_col.grid_rowconfigure(0, weight=1)

        self.left_card = RoundedCard(
            self.left_col,
            auto_size=False,
            pad=18
        )
        self.left_card.grid(row=0, column=0, sticky="nsew")
        self.left_card.grid_propagate(False)

        left_body = card_body(self.left_card)
        left_body.grid_columnconfigure(0, weight=1)

        left_body.grid_rowconfigure(0, weight=1)
        left_body.grid_rowconfigure(1, weight=0)
        left_body.grid_rowconfigure(2, weight=0)
        left_body.grid_rowconfigure(3, weight=0)
        left_body.grid_rowconfigure(4, weight=0)
        left_body.grid_rowconfigure(5, weight=1)

        self.title_label = ctk.CTkLabel(
            left_body,
            text="Enter the Amount of Bill",
            font=theme.heavy(24),
            text_color=theme.BLACK,
            fg_color=theme.WHITE,
            wraplength=470,
            justify="center"
        )
        self.title_label.grid(row=1, column=0, padx=24, pady=(18, 10), sticky="ew")

        self.summary_label = ctk.CTkLabel(
            left_body,
            text="",
            font=theme.font(16, "bold"),
            text_color=theme.MUTED,
            fg_color=theme.WHITE,
            wraplength=470,
            justify="center"
        )
        self.summary_label.grid(row=2, column=0, padx=24, pady=(0, 16), sticky="ew")

        self.input_card = RoundedCard(
            left_body,
            auto_size=False,
            height=120,
            pad=8
        )
        self.input_card.grid(row=3, column=0, padx=18, pady=(0, 14), sticky="ew")
        self.input_card.grid_propagate(False)

        input_body = card_body(self.input_card)
        input_body.pack_propagate(False)

        self.currency_label = ctk.CTkLabel(
            input_body,
            text="₱",
            font=theme.heavy(38),
            text_color=theme.BLACK,
            fg_color=theme.WHITE
        )
        self.currency_label.pack(side="left", padx=(24, 12), pady=20)

        self.amount_entry = tk.Entry(
            input_body,
            textvariable=self.amount_var,
            font=("Arial", 34, "bold"),
            bd=0,
            relief="flat",
            justify="left",
            bg=theme.WHITE,
            fg=theme.BLACK,
            insertbackground=theme.BLACK,
        )
        self.amount_entry.pack(side="left", fill="both", expand=True, padx=(0, 24), pady=24)
        self.amount_entry.bind("<KeyRelease>", self._on_entry_change)
        self.amount_entry.bind("<Return>", lambda e: self.submit_amount())

        # Message card below input
        self.message_card = ctk.CTkFrame(
            left_body,
            fg_color=theme.WHITE
        )
        self.message_card.grid(row=4, column=0, padx=18, pady=(0, 10), sticky="ew")
        self.message_card.grid_propagate(False)

        self.message_card.configure(height=120)

        message_body = self.message_card
        message_body.grid_columnconfigure(0, weight=1)
        message_body.grid_rowconfigure(0, weight=1)

        self.message_label = ctk.CTkLabel(
            message_body,
            text="Enter an amount, then press Continue.",
            font=theme.font(16, "bold"),
            text_color=theme.MUTED,
            fg_color=theme.WHITE,
            wraplength=470,
            justify="center"
        )
        self.message_label.grid(row=0, column=0, padx=20, pady=18, sticky="nsew")

        self.left_spacer = ctk.CTkFrame(left_body, fg_color=theme.WHITE)
        self.left_spacer.grid(row=5, column=0, sticky="nsew")

        self.right_card = RoundedCard(
            self.right_col,
            auto_size=False,
            pad=18
        )
        self.right_card.grid(row=0, column=0, sticky="nsew")
        self.right_card.grid_propagate(False)

        right_body = card_body(self.right_card)
        right_body.grid_columnconfigure(0, weight=1)
        right_body.grid_rowconfigure(0, weight=1)

        self.keyboard = CashNumericKeyboard(
            right_body,
            on_key=self.append_digit,
            on_clear=self.clear_amount,
            on_submit=self.submit_amount,
        )
        self.keyboard.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)

        self.bind("<Configure>", self._sync_column_sizes, add="+")
        self.content_wrap.bind("<Configure>", self._sync_column_sizes, add="+")

    def _sync_column_sizes(self, event=None):
        try:
            self.update_idletasks()

            total_w = max(200, self.content_wrap.winfo_width())
            total_h = max(200, self.content_wrap.winfo_height())

            col_gap = 24
            card_w = max(320, (total_w - col_gap) // 2)
            card_h = max(420, total_h)

            self.left_card.configure(width=card_w, height=card_h)
            self.right_card.configure(width=card_w, height=card_h)

            inner_w = max(260, card_w - 54)
            self.input_card.configure(width=inner_w, height=120)
            self.message_card.configure(width=inner_w, height=120)
        except Exception:
            pass

    def update_data(self, user_data=None, selected_product=None, discount=0, **kwargs):
        self.user_data = (user_data or {}).copy()
        self.selected_product = (selected_product or {}).copy() if selected_product else None
        self.discount = discount or 0
        self.amount_var.set("")
        self._clear_message_timer()

        self.shell.set_header_right(f"Welcome, {self.user_data.get('username', 'User')}!")
        self.after(10, self._sync_column_sizes)

        if not self.selected_product:
            self.summary_label.configure(
                text="No product selected.",
                text_color=theme.ERROR
            )
            self._set_message(
                "Please go back and choose a product first.",
                theme.ERROR,
                auto_hide_ms=None
            )
            self.after(50, self._focus_entry)
            return

        total = self._compute_total()

        self.summary_label.configure(
            text=(
                f"Product: {self.selected_product.get('name', 'Unknown')}\n"
                f"Total to pay: ₱{total:.2f}\n"
            ),
            text_color=theme.MUTED
        )

        self._set_message(
            "Enter an amount, then press Continue.",
            theme.MUTED,
            auto_hide_ms=None
        )

        self.after(50, self._focus_entry)

    def _focus_entry(self):
        try:
            self.amount_entry.focus_set()
            self.amount_entry.icursor(tk.END)
        except Exception:
            pass

    def _clear_message_timer(self):
        if self._message_hide_job is not None:
            try:
                self.after_cancel(self._message_hide_job)
            except Exception:
                pass
            self._message_hide_job = None

    def _set_message(self, text, color, auto_hide_ms=None):
        self._clear_message_timer()
        self.message_label.configure(text=text, text_color=color)
        if auto_hide_ms:
            self._message_hide_job = self.after(
                auto_hide_ms,
                lambda: self._set_message(
                    "Enter an amount, then press Continue.",
                    theme.MUTED,
                    auto_hide_ms=None
                )
            )

    def _compute_total(self):
        if not self.selected_product:
            return 0.0
        price = float(self.selected_product.get("price", 0) or 0)
        return price * (1 - float(self.discount or 0) / 100.0)

    def _total_change_stock_value(self):
        return (self.stock1 * 1) + (self.stock5 * 5) + (self.stock20 * 20)

    def _current_amount(self):
        raw = self.amount_var.get().strip()
        if not raw:
            return 0

        digits = "".join(ch for ch in raw if ch.isdigit())
        if digits != raw:
            self.amount_var.set(digits)

        try:
            return int(digits) if digits else 0
        except Exception:
            return 0

    def _on_entry_change(self, event=None):
        raw = self.amount_var.get()
        digits = "".join(ch for ch in raw if ch.isdigit())[:4]

        if raw != digits:
            self.amount_var.set(digits)

        self._set_message(
            "Press Continue to validate this amount.",
            theme.MUTED,
            auto_hide_ms=None
        )

    def append_digit(self, digit):
        current = "".join(ch for ch in self.amount_var.get() if ch.isdigit())[:4]
        if len(current) >= 4:
            self._focus_entry()
            return

        self.amount_var.set((current + digit)[:4])

        self._set_message(
            "Press Continue to validate this amount.",
            theme.MUTED,
            auto_hide_ms=None
        )
        self._focus_entry()

    def clear_amount(self):
        self.amount_var.set("")
        self._set_message(
            "Enter an amount, then press Continue.",
            theme.MUTED,
            auto_hide_ms=None
        )
        self._focus_entry()

    def _validate_amount(self, amount):
        total = self._compute_total()

        if amount <= 0:
            return False, "Please enter a valid cash amount."

        if amount < total:
            return False, (
                f"₱{amount:.2f} is not enough for this purchase.\n"
                f"Please enter an amount equal to or greater than ₱{total:.2f}."
            )

        change_needed = float(amount) - float(total)
        stock_limit = self._total_change_stock_value() * 0.30
        cost_limit = total * 0.30

        if change_needed > stock_limit:
            return False, "Bill is too large. Insert a smaller Bill."

        if change_needed > cost_limit:
            return False, "Bill is too large. Insert a smaller Bill."

        return True, (
            f"Entered amount: ₱{amount:.2f}\n"
            f"Expected change: ₱{change_needed:.2f}\n\n"
            f"Amount accepted. Proceeding to cash payment..."
        )

    def submit_amount(self):
        if not self.selected_product:
            self._set_message(
                "No product selected.",
                theme.ERROR,
                auto_hide_ms=3000
            )
            return

        amount = self._current_amount()
        is_valid, message = self._validate_amount(amount)

        if not is_valid:
            if message == "Bill is too large. Insert a smaller Bill.":
                self._set_message(
                    "Bill is too large. Insert a smaller Bill.",
                    theme.ERROR,
                    auto_hide_ms=3000
                )
            else:
                self._set_message(
                    message,
                    theme.ERROR,
                    auto_hide_ms=3000
                )
            self._focus_entry()
            return

        self._set_message(
            message,
            theme.SUCCESS,
            auto_hide_ms=None
        )

        self.controller.show_loading_then(
            "Preparing cash payment",
            "CashPaymentPage",
            delay=1000,
            user_data=self.user_data,
            selected_product=self.selected_product,
            discount=self.discount,
            planned_cash_bill=amount
        )

    def go_back(self):
        self._clear_message_timer()
        self.controller.show_loading_then(
            "Returning to payment options",
            "PaymentMethodPage",
            delay=1000,
            user_data=self.user_data,
            selected_product=self.selected_product,
            discount=self.discount
        )