from frontend import tk_compat as ctk
from frontend import theme
from frontend.widgets import AppShell, RoundedCard, OutlineTile, PillButton, card_body
from config_manager import config
from PIL import Image, ImageTk


class PaymentMethodPage(ctk.CTkFrame):
    REFRESH_MS = 1500

    TILE_WIDTH = 680
    TILE_HEIGHT = 250

    LOGO_W = 120
    LOGO_H = 44

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

        # ---------------- TOP BAR ----------------
        top_bar = ctk.CTkFrame(self.shell.body, fg_color="transparent")
        top_bar.pack(fill="x", padx=28, pady=(16, 8))

        self.back_btn = PillButton(
            top_bar,
            text=config.get("payment_method_page", "back_button_text", default="Back"),
            width=130,
            height=56,
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

        # ---------------- CENTER WRAP ----------------
        page_wrap = ctk.CTkFrame(self.shell.body, fg_color="transparent")
        page_wrap.pack(fill="both", expand=True, padx=28, pady=(6, 20))

        page_wrap.grid_columnconfigure(0, weight=1)
        page_wrap.grid_rowconfigure(0, weight=1)
        page_wrap.grid_rowconfigure(1, weight=0)
        page_wrap.grid_rowconfigure(2, weight=1)

        self.main_card = RoundedCard(page_wrap, auto_size=True, pad=20)
        self.main_card.grid(row=1, column=0, sticky="n")

        main_body = card_body(self.main_card)

        self.content_stack = ctk.CTkFrame(main_body, fg_color=theme.WHITE)
        self.content_stack.pack(fill="both", expand=True, padx=28, pady=18)
        self.content_stack.grid_columnconfigure(0, weight=1)

        # ---------------- DESCRIPTION ----------------
        self.desc_label = ctk.CTkLabel(
            self.content_stack,
            text=config.get(
                "payment_method_page",
                "description",
                default="Choose how you want to pay for your selected test kit."
            ),
            font=theme.font(24, "bold"),
            text_color=theme.MUTED,
            fg_color=theme.WHITE,
            wraplength=560,
            justify="center"
        )
        self.desc_label.grid(row=0, column=0, padx=30, pady=(8, 22), sticky="ew")

        # ---------------- CASH TILE ----------------
        self.cash_tile = self._create_option(
            self.content_stack,
            title=config.get("payment_method_page", "cash_title", default="CASH"),
            subtitle=config.get(
                "payment_method_page",
                "cash_subtitle",
                default="Settle payment via the machine slot"
            ),
            command=lambda: self.proceed_payment("cash"),
            logos=[
                ("assets/phcoin.png", (self.LOGO_W, self.LOGO_H))
            ]
        )
        self.cash_tile.grid(row=1, column=0, padx=34, pady=(0, 16))

        # ---------------- ONLINE TILE ----------------
        self.online_tile = self._create_option(
            self.content_stack,
            title=config.get("payment_method_page", "online_title", default="E-WALLETS"),
            subtitle=config.get(
                "payment_method_page",
                "online_subtitle",
                default="Pay via GCash, Maya, or QRPh"
            ),
            command=lambda: self.proceed_payment("online"),
            logos=[
                ("assets/gcash.png", (self.LOGO_W, self.LOGO_H)),
                ("assets/maya.png", (self.LOGO_W, self.LOGO_H)),
                ("assets/qrph.png", (self.LOGO_W, self.LOGO_H)),
            ]
        )
        self.online_tile.grid(row=2, column=0, padx=34, pady=(0, 10))

        # ---------------- STATUS ----------------
        self.status_label = ctk.CTkLabel(
            self.content_stack,
            text="",
            font=theme.font(18, "bold"),
            text_color=theme.MUTED,
            fg_color=theme.WHITE,
            wraplength=560,
            justify="center"
        )
        self.status_label.grid(row=3, column=0, pady=(16, 4), padx=20, sticky="ew")

        self._start_config_refresh()

    def _load_logo_image(self, path, size):
        try:
            img = Image.open(path).convert("RGBA")
            img.thumbnail(size, Image.LANCZOS)

            canvas = Image.new("RGBA", size, (255, 255, 255, 0))
            x = (size[0] - img.width) // 2
            y = (size[1] - img.height) // 2
            canvas.paste(img, (x, y), img)

            tk_img = ImageTk.PhotoImage(canvas)
            self.logo_refs.append(tk_img)
            return tk_img
        except Exception as e:
            print(f"[PAYMENT METHOD] Failed to load logo {path}: {e}", flush=True)
            return None

    def _bind_click_recursive(self, widgets, command):
        for w in widgets:
            try:
                w.bind("<Button-1>", lambda e, cmd=command: cmd())
            except Exception:
                pass

    def _create_option(self, master, title, subtitle, command, logos=None):
        tile = OutlineTile(
            master,
            auto_size=False,
            width=self.TILE_WIDTH,
            height=self.TILE_HEIGHT,
            pad=28
        )
        body = card_body(tile)

        content = ctk.CTkFrame(body, fg_color=theme.WHITE)
        content.pack(fill="both", expand=True, padx=12, pady=8)
        content.pack_propagate(False)

        # balanced vertical layout for both tiles
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=0)
        content.grid_rowconfigure(2, weight=0)
        content.grid_rowconfigure(3, weight=0)
        content.grid_rowconfigure(4, weight=1)

        title_label = ctk.CTkLabel(
            content,
            text=title,
            font=theme.heavy(28),
            text_color=theme.BLACK,
            fg_color=theme.WHITE,
            justify="center"
        )
        title_label.grid(row=1, column=0, pady=(2, 6), padx=12, sticky="n")

        subtitle_label = ctk.CTkLabel(
            content,
            text=subtitle,
            font=theme.font(17, "bold"),
            text_color=theme.MUTED,
            fg_color=theme.WHITE,
            wraplength=440,
            justify="center"
        )
        subtitle_label.grid(row=2, column=0, pady=(0, 14), padx=18, sticky="n")

        logo_container = None
        logo_widgets = []

        if logos:
            logo_container = ctk.CTkFrame(content, fg_color=theme.WHITE)
            logo_container.grid(row=3, column=0, pady=(4, 0), padx=8)

            for path, size in logos:
                tk_img = self._load_logo_image(path, size)
                if tk_img is None:
                    continue

                lbl = ctk.CTkLabel(
                    logo_container,
                    image=tk_img,
                    text="",
                    fg_color=theme.WHITE
                )
                lbl.pack(side="left", padx=18)
                logo_widgets.append(lbl)
        else:
            spacer = ctk.CTkFrame(content, fg_color=theme.WHITE, height=18)
            spacer.grid(row=3, column=0)
            logo_widgets.append(spacer)

        widgets_to_bind = [tile, body, content, title_label, subtitle_label]
        if hasattr(tile, "canvas"):
            widgets_to_bind.append(tile.canvas)
        if logo_container is not None:
            widgets_to_bind.append(logo_container)
        widgets_to_bind.extend(logo_widgets)

        self._bind_click_recursive(widgets_to_bind, command)

        tile._title_label = title_label
        tile._subtitle_label = subtitle_label
        tile._logo_container = logo_container
        tile._logo_widgets = logo_widgets
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
                text=config.get(
                    "payment_method_page",
                    "cash_subtitle",
                    default="Settle payment via the machine slot"
                )
            )

            self.online_tile._title_label.configure(
                text=config.get("payment_method_page", "online_title", default="E-WALLETS")
            )
            self.online_tile._subtitle_label.configure(
                text=config.get(
                    "payment_method_page",
                    "online_subtitle",
                    default="Pay via GCash, Maya, or QRPh"
                )
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