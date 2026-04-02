from frontend import tk_compat as ctk
from frontend import theme
from frontend.widgets import AppShell, RoundedCard, OutlineTile, PillButton, card_body
from config_manager import config


class PaymentMethodPage(ctk.CTkFrame):
    REFRESH_MS = 1500

    def __init__(self, master, controller):
        super().__init__(master, fg_color=theme.CREAM)
        self.controller = controller
        self.user_data = {}
        self.selected_product = None
        self.discount = 0
        self.logo_refs = []
        self._config_refresh_job = None

        self.shell = AppShell(self, title_right="Welcome, User!")
        self.shell.pack(fill="both", expand=True)

        top_bar = ctk.CTkFrame(self.shell.body, fg_color="transparent")
        top_bar.pack(fill="x", padx=28, pady=(16, 8))

        self.back_btn = PillButton(
            top_bar,
            text=config.get("payment_method_page", "back_button_text", default="Back"),
            width=130,
            height=58,
            command=self.go_back,
            font=theme.font(18, "bold")
        )
        self.back_btn.pack(side="left")

        self.title_label = ctk.CTkLabel(
            top_bar,
            text=config.get("payment_method_page", "title", default="CHOOSE PAYMENT METHOD"),
            font=theme.heavy(32),
            text_color=theme.BLACK
        )
        self.title_label.pack(side="left", expand=True, padx=(0, 130))

        content_wrap = ctk.CTkFrame(self.shell.body, fg_color="transparent")
        content_wrap.pack(expand=True, fill="both")

        content_wrap.grid_columnconfigure(0, weight=1)
        content_wrap.grid_rowconfigure(0, weight=1)
        content_wrap.grid_rowconfigure(1, weight=0)
        content_wrap.grid_rowconfigure(2, weight=1)

        self.main_card = RoundedCard(content_wrap, auto_size=True, pad=18)
        self.main_card.grid(row=1, column=0)

        body = card_body(self.main_card)

        stack = ctk.CTkFrame(body, fg_color=theme.WHITE)
        stack.pack(expand=True, fill="both", padx=20, pady=10)
        stack.grid_columnconfigure(0, weight=1)

        self.desc_label = ctk.CTkLabel(
            stack,
            text=config.get(
                "payment_method_page",
                "description",
                default="Choose how you want to pay for your selected test kit."
            ),
            font=theme.font(20, "bold"),
            text_color=theme.MUTED,
            fg_color=theme.WHITE,
            wraplength=520,
            justify="center"
        )
        self.desc_label.grid(row=0, column=0, padx=20, pady=(10, 20))

        self.cash_tile = self._create_option(
            stack,
            config.get("payment_method_page", "cash_title", default="CASH"),
            config.get("payment_method_page", "cash_subtitle", default="Settle payment via the machine slot"),
            lambda: self.proceed_payment("cash"),
            add_logo_row=False
        )
        self.cash_tile.grid(row=1, column=0, pady=(0, 16), padx=40, sticky="ew")

        self.online_tile = self._create_option(
            stack,
            config.get("payment_method_page", "online_title", default="E-WALLETS"),
            config.get("payment_method_page", "online_subtitle", default="Pay via GCash, Maya, or QRPh"),
            lambda: self.proceed_payment("online"),
            add_logo_row=False
        )
        self.online_tile.grid(row=2, column=0, pady=(0, 16), padx=40, sticky="ew")

        self.status_label = ctk.CTkLabel(
            stack,
            text="",
            font=theme.font(18, "bold"),
            text_color=theme.MUTED,
            fg_color=theme.WHITE,
            wraplength=560,
            justify="center"
        )
        self.status_label.grid(row=3, column=0, pady=(15, 6), padx=20)

        self._start_config_refresh()

    def _create_option(self, master, title, subtitle, command, add_logo_row=False):
        tile = OutlineTile(master, auto_size=True, pad=25)
        body = card_body(tile)

        title_label = ctk.CTkLabel(
            body,
            text=title,
            font=theme.heavy(28),
            text_color=theme.BLACK,
            fg_color=theme.WHITE,
            justify="center"
        )
        title_label.pack(pady=(12, 4), anchor="center")

        subtitle_label = ctk.CTkLabel(
            body,
            text=subtitle,
            font=theme.font(17, "bold"),
            text_color=theme.MUTED,
            fg_color=theme.WHITE,
            wraplength=350,
            justify="center"
        )
        subtitle_label.pack(pady=(0, 12), anchor="center")

        for w in (tile, tile.canvas, body, title_label, subtitle_label):
            w.bind("<Button-1>", lambda e: command())

        tile._title_label = title_label
        tile._subtitle_label = subtitle_label
        return tile

    def _refresh_from_config(self):
        try:
            self.back_btn.configure(
                text=config.get("payment_method_page", "back_button_text", default="Back")
            )
            self.title_label.configure(
                text=config.get("payment_method_page", "title", default="CHOOSE PAYMENT METHOD")
            )
            self.desc_label.configure(
                text=config.get(
                    "payment_method_page",
                    "description",
                    default="Choose how you want to pay for your selected test kit."
                )
            )

            self.cash_tile._title_label.configure(
                text=config.get("payment_method_page", "cash_title", default="CASH")
            )
            self.cash_tile._subtitle_label.configure(
                text=config.get("payment_method_page", "cash_subtitle", default="Settle payment via the machine slot")
            )

            self.online_tile._title_label.configure(
                text=config.get("payment_method_page", "online_title", default="E-WALLETS")
            )
            self.online_tile._subtitle_label.configure(
                text=config.get("payment_method_page", "online_subtitle", default="Pay via GCash, Maya, or QRPh")
            )

        except Exception as e:
            print(f"[PAYMENT METHOD] Config refresh failed: {e}", flush=True)

    def _start_config_refresh(self):
        self._refresh_from_config()
        self._config_refresh_job = self.after(self.REFRESH_MS, self._start_config_refresh)

    def update_data(self, user_data=None, selected_product=None, discount=0, **kwargs):
        self.user_data = user_data or {}
        self.selected_product = selected_product
        self.discount = discount or 0
        self.shell.set_header_right(f"Welcome, {self.user_data.get('username', 'User')}!")
        self.status_label.configure(text="", text_color=theme.MUTED)

    def go_back(self):
        self.controller.show_loading_then(
            config.get(
                "payment_method_page",
                "back_loading_text",
                default="Returning to product selection"
            ),
            "PurchasePage",
            delay=1000,
            user_data=self.user_data,
            selected_product=self.selected_product,
            discount=self.discount
        )

    def proceed_payment(self, method):
        self.status_label.configure(text="", text_color=theme.MUTED)

        if method == "cash":
            self.controller.show_loading_then(
                config.get(
                    "payment_method_page",
                    "cash_loading_text",
                    default="Preparing cash amount entry"
                ),
                "CashBillCheckPage",
                delay=1000,
                user_data=self.user_data,
                selected_product=self.selected_product,
                discount=self.discount
            )
            return

        self.controller.show_loading_then(
            config.get(
                "payment_method_page",
                "online_loading_text",
                default="Preparing online payment"
            ),
            "OnlinePaymentPage",
            delay=1000,
            user_data=self.user_data,
            selected_product=self.selected_product,
            discount=self.discount
        )