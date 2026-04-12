from frontend import tk_compat as ctk
from pynput import keyboard
import uuid
import threading
import requests
import json
from frontend import theme
from frontend.widgets import AppShell, RoundedCard, PillButton, OutlineTile, card_body
from backend.util import api_client
from config_manager import config


class ProductTile(OutlineTile):
    TILE_HEIGHT = 220

    def __init__(self, master, product, select_callback):
        super().__init__(
            master,
            pad=16,
            auto_size=False,
            height=self.TILE_HEIGHT,
        )
        self.product = product
        self.select_callback = select_callback
        self.selected = False
        self.available = bool(product.get("available", True))

        self.grid_propagate(False)

        body = self.content
        body.grid_rowconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)
        body.grid_rowconfigure(2, weight=1)
        body.grid_rowconfigure(3, weight=0)
        body.grid_columnconfigure(0, weight=1)

        icon_text = config.get("purchase_page", "product_icon_text", default="KIT")

        self.icon = ctk.CTkLabel(
            body,
            text=icon_text,
            font=theme.heavy(26),
            text_color=theme.ORANGE if self.available else theme.MUTED,
            fg_color=theme.WHITE
        )
        self.icon.grid(row=0, column=0, sticky="s", pady=(6, 4))

        self.name = ctk.CTkLabel(
            body,
            text=product["type"],
            font=theme.font(20, "bold"),
            text_color=theme.BLACK if self.available else theme.MUTED,
            fg_color=theme.WHITE,
            wraplength=260,
            justify="center"
        )
        self.name.grid(row=1, column=0, sticky="n", padx=12, pady=4)

        self.price = ctk.CTkLabel(
            body,
            text=f"₱{product['price']}",
            font=theme.font(18, "bold"),
            text_color=theme.MUTED,
            fg_color=theme.WHITE
        )
        self.price.grid(row=2, column=0, sticky="n", pady=(4, 4))

        stock = int(product.get("stock", 0))
        stock_text = (
            f"{config.get('purchase_page', 'stock_label_prefix', default='Stock')}: {stock}"
            if self.available else
            config.get("purchase_page", "out_of_stock_text", default="OUT OF STOCK")
        )

        stock_color = theme.MUTED if self.available else theme.ERROR

        self.stock_label = ctk.CTkLabel(
            body,
            text=stock_text,
            font=theme.font(14, "bold"),
            text_color=stock_color,
            fg_color=theme.WHITE
        )
        self.stock_label.grid(row=3, column=0, sticky="n", pady=(0, 6))

        self.bind("<Configure>", self._on_resize, add="+")
        body.bind("<Configure>", self._on_resize, add="+")

        if self.available:
            for w in (self, self.canvas, body, self.icon, self.name, self.price, self.stock_label):
                w.bind("<Button-1>", lambda e: self.select_callback(self))

    def _on_resize(self, event=None):
        try:
            width = max(180, self.content.winfo_width() - 24)
            self.name.configure(wraplength=width)
        except Exception:
            pass

    def set_selected(self, selected: bool):
        if not self.available:
            return

        self.selected = selected
        fill = theme.ORANGE if selected else theme.WHITE
        self.configure(fg_color=fill)

        text_color = theme.WHITE if selected else theme.BLACK
        price_color = theme.WHITE if selected else theme.MUTED
        stock_color = theme.WHITE if selected else theme.MUTED

        for widget in (self.icon, self.name, self.price, self.stock_label):
            widget.configure(fg_color=fill)

        self.name.configure(text_color=text_color)
        self.price.configure(text_color=price_color)
        self.stock_label.configure(text_color=stock_color)
        self.icon.configure(text_color=theme.WHITE if selected else theme.ORANGE)

    def update_product(self, product):
        self.product = product
        self.available = bool(product.get("available", True))

        self.icon.configure(
            text=config.get("purchase_page", "product_icon_text", default="KIT"),
            text_color=theme.ORANGE if self.available else theme.MUTED,
            fg_color=theme.WHITE
        )
        self.name.configure(
            text=product["type"],
            text_color=theme.BLACK if self.available else theme.MUTED,
            fg_color=theme.WHITE
        )
        self.price.configure(
            text=f"₱{product['price']}",
            fg_color=theme.WHITE
        )

        stock = int(product.get("stock", 0))
        stock_text = (
            f"{config.get('purchase_page', 'stock_label_prefix', default='Stock')}: {stock}"
            if self.available else
            config.get("purchase_page", "out_of_stock_text", default="OUT OF STOCK")
        )

        self.stock_label.configure(
            text=stock_text,
            text_color=theme.MUTED if self.available else theme.ERROR,
            fg_color=theme.WHITE
        )

        if not self.available:
            self.set_selected(False)


class PurchasePage(ctk.CTkFrame):
    REFRESH_MS = 1500

    def __init__(self, master, controller, user_data=None):
        super().__init__(master, fg_color=theme.CREAM)
        self.controller = controller
        self.user_data = user_data or {}
        self.username = self.user_data.get("username", "User")
        self.userID = self.user_data.get("userID")

        self.selected_tile = None
        self.selected_product = None
        self.discount = None

        self.qr_buffer = ""
        self.scan_disabled = False
        self.listener = None

        self.validation_in_progress = False
        self.last_scanned_token = None
        self.discount_applied_token = None
        self._config_refresh_job = None
        self._last_products_signature = None
        self._empty_tiles_label = None

        self.shell = AppShell(self, title_right=f"Welcome, {self.username}!")
        self.shell.pack(fill="both", expand=True)

        self.logout_btn = PillButton(
            self.shell.header_inner,
            text=config.get("purchase_page", "logout_button_text", default="Logout"),
            width=140,
            height=46,
            command=self.logout,
            font=theme.font(16, "bold")
        )
        self.logout_btn.pack(side="right", padx=24)

        self.title_label = ctk.CTkLabel(
            self.shell.body,
            text=config.get("purchase_page", "title", default="SELECT A PRODUCT"),
            font=theme.heavy(34),
            text_color=theme.BLACK
        )
        self.title_label.pack(pady=(18, 12))

        content = ctk.CTkFrame(self.shell.body, fg_color="transparent")
        content.pack(expand=True, fill="both", padx=28, pady=(0, 18))
        content.grid_columnconfigure(0, weight=1, uniform="purchase-col")
        content.grid_columnconfigure(1, weight=1, uniform="purchase-col")
        content.grid_rowconfigure(0, weight=1)

        left = RoundedCard(content, auto_size=False)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14), pady=8)

        right = RoundedCard(content, auto_size=False)
        right.grid(row=0, column=1, sticky="nsew", padx=(14, 0), pady=8)

        left_body = card_body(left)
        right_body = card_body(right)

        left_body.grid_rowconfigure(0, weight=0)
        left_body.grid_rowconfigure(1, weight=1)
        left_body.grid_columnconfigure(0, weight=1)

        self.left_title = ctk.CTkLabel(
            left_body,
            text=config.get("purchase_page", "section_title", default="Testing Kits"),
            font=theme.heavy(28),
            text_color=theme.BLACK,
            fg_color=theme.WHITE
        )
        self.left_title.grid(row=0, column=0, pady=(16, 10))

        self.tiles_frame = ctk.CTkFrame(left_body, fg_color=theme.WHITE)
        self.tiles_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=(0, 12))

        right_body.grid_rowconfigure(0, weight=0)
        right_body.grid_rowconfigure(1, weight=1)
        right_body.grid_rowconfigure(2, weight=0)
        right_body.grid_rowconfigure(3, weight=0)
        right_body.grid_columnconfigure(0, weight=1)

        self.right_title = ctk.CTkLabel(
            right_body,
            text=config.get("purchase_page", "order_title", default="Order Details"),
            font=theme.heavy(28),
            text_color=theme.BLACK,
            fg_color=theme.WHITE
        )
        self.right_title.grid(row=0, column=0, pady=(16, 10))

        self.order_box = ctk.CTkFrame(
            right_body,
            fg_color="#FAFAFA",
            border_color="#E5E5E5",
            border_width=2,
            corner_radius=16,
            width=620,
            height=560
        )
        self.order_box.grid(row=1, column=0, pady=10, padx=10, sticky="")
        self.order_box.grid_propagate(False)

        self.order_content = ctk.CTkFrame(self.order_box, fg_color="transparent")
        self.order_content.place(
            relx=0.5,
            rely=0.5,
            anchor="center",
            relwidth=0.94,
            relheight=0.92
        )

        self.empty_order_label = ctk.CTkLabel(
            self.order_content,
            text=config.get(
                "purchase_page",
                "no_item_selected_text",
                default="Select a product to view details"
            ),
            font=theme.font(22, "bold"),
            text_color=theme.MUTED,
            justify="center",
            wraplength=500
        )
        self.empty_order_label.place(relx=0.5, rely=0.5, anchor="center")

        self.status_label = ctk.CTkLabel(
            right_body,
            text="",
            font=theme.font(18, "bold"),
            text_color=theme.ERROR,
            wraplength=520,
            justify="center",
            anchor="center",
            fg_color=theme.WHITE
        )
        self.status_label.grid(row=2, column=0, sticky="nsew", padx=20, pady=(5, 10))

        btns = ctk.CTkFrame(right_body, fg_color=theme.WHITE)
        btns.grid(row=3, column=0, sticky="ew", pady=(8, 18))
        btns.grid_columnconfigure(0, weight=1)
        btns.grid_columnconfigure(1, weight=0)
        btns.grid_columnconfigure(2, weight=0)
        btns.grid_columnconfigure(3, weight=1)

        self.scan_btn = PillButton(
            btns,
            text=config.get("purchase_page", "discount_button_text", default="Discount"),
            width=260,
            height=80,
            command=self.start_scan,
            state="disabled",
            font=theme.font(19, "bold")
        )
        self.scan_btn.grid(row=0, column=1, padx=20)

        self.pay_btn = PillButton(
            btns,
            text=config.get("purchase_page", "pay_button_text", default="Pay"),
            width=260,
            height=80,
            command=self.go_to_payment,
            state="disabled",
            font=theme.font(19, "bold")
        )
        self.pay_btn.grid(row=0, column=2, padx=20)

        self.tiles = []
        self.products = []
        self.reload_products(force=True)
        self._start_config_refresh()

    def _build_products_from_config(self):
        products = []
        for product in config.get_enabled_products():
            product_id = product.get("product_id")
            if not product_id:
                continue

            stock = config.get_product_stock(product_id)
            merged = product.copy()
            merged["stock"] = stock
            merged["available"] = stock > 0 and bool(product.get("enabled", True))
            products.append(merged)
        return products

    def _make_products_signature(self, products):
        return json.dumps(products, sort_keys=True)

    def _clear_tiles_frame(self):
        for child in self.tiles_frame.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass

        self.tiles = []
        self._empty_tiles_label = None

        for col in range(3):
            self.tiles_frame.grid_columnconfigure(col, weight=0, uniform="")
        for row in range(10):
            self.tiles_frame.grid_rowconfigure(row, weight=0)

    def _get_column_count(self, item_count: int) -> int:
        if item_count <= 0:
            return 1
        if item_count == 1:
            return 1
        if item_count == 2:
            return 2
        return 3

    def _clear_order_content(self):
        for child in self.order_content.winfo_children():
            try:
                child.destroy()
            except Exception:
                pass

    def _make_summary_row(self, parent, label, value, value_color=None, large=False):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=12, padx=12)

        left = ctk.CTkLabel(
            row,
            text=label,
            font=theme.font(18, "bold"),
            text_color=theme.MUTED,
            fg_color="transparent",
            anchor="w",
            justify="left",
            wraplength=180
        )
        left.pack(side="left", anchor="w")

        right = ctk.CTkLabel(
            row,
            text=value,
            font=theme.font(28 if large else 22, "bold"),
            text_color=value_color or theme.BLACK,
            fg_color="transparent",
            anchor="e",
            justify="right",
            wraplength=260
        )
        right.pack(side="right", anchor="e")

        return row

    def _make_divider(self, parent):
        divider = ctk.CTkFrame(parent, fg_color="#E7E7E7", height=2, corner_radius=999)
        divider.pack(fill="x", padx=10, pady=14)

    def reload_products(self, force=False):
        new_products = self._build_products_from_config()
        new_signature = self._make_products_signature(new_products)

        if not force and new_signature == self._last_products_signature:
            return

        self._last_products_signature = new_signature
        self.products = new_products

        self._clear_tiles_frame()

        if not self.products:
            self.tiles_frame.grid_columnconfigure(0, weight=1)
            self.tiles_frame.grid_rowconfigure(0, weight=1)

            self._empty_tiles_label = ctk.CTkLabel(
                self.tiles_frame,
                text="No products available",
                font=theme.font(18, "bold"),
                text_color=theme.MUTED,
                fg_color=theme.WHITE
            )
            self._empty_tiles_label.grid(row=0, column=0, pady=24, sticky="n")
            self.tiles.append(self._empty_tiles_label)
            self.update_order_summary()
            return

        column_count = self._get_column_count(len(self.products))

        for col in range(column_count):
            self.tiles_frame.grid_columnconfigure(col, weight=1, uniform="product-col")

        row_count = (len(self.products) + column_count - 1) // column_count
        for row in range(row_count):
            self.tiles_frame.grid_rowconfigure(row, weight=1)

        for index, product in enumerate(self.products):
            row = index // column_count
            col = index % column_count

            tile = ProductTile(self.tiles_frame, product, self.on_tile_selected)
            tile.grid(row=row, column=col, sticky="nsew", padx=10, pady=10)
            self.tiles.append(tile)

        if self.selected_product:
            selected_id = self.selected_product.get("product_id")
            still_exists = None

            for product in self.products:
                if product.get("product_id") == selected_id and product.get("available"):
                    still_exists = product.copy()
                    break

            if still_exists:
                self.selected_product = still_exists
                self.selected_tile = None
                for tile in self.tiles:
                    if isinstance(tile, ProductTile) and tile.product.get("product_id") == selected_id:
                        self.selected_tile = tile
                        tile.set_selected(True)
                        break
            else:
                self.selected_tile = None
                self.selected_product = None
                self.discount = None
                self.scan_disabled = False

        self.update_order_summary()

    def _refresh_text_only(self):
        self.title_label.configure(
            text=config.get("purchase_page", "title", default="SELECT A PRODUCT")
        )
        self.left_title.configure(
            text=config.get("purchase_page", "section_title", default="Testing Kits")
        )
        self.right_title.configure(
            text=config.get("purchase_page", "order_title", default="Order Details")
        )
        self.logout_btn.configure(
            text=config.get("purchase_page", "logout_button_text", default="Logout")
        )
        self.scan_btn.configure(
            text=config.get("purchase_page", "discount_button_text", default="Discount")
        )
        self.pay_btn.configure(
            text=config.get("purchase_page", "pay_button_text", default="Pay")
        )

    def _refresh_from_config(self):
        try:
            self._refresh_text_only()
            self.reload_products(force=False)
        except Exception as e:
            print(f"[PURCHASE] Config refresh failed: {e}", flush=True)

    def _start_config_refresh(self):
        self._refresh_from_config()
        self._config_refresh_job = self.after(self.REFRESH_MS, self._start_config_refresh)

    def _resolve_latest_selected_product(self):
        if not self.selected_product:
            return None

        selected_id = (
            self.selected_product.get("product_id")
            or self.selected_product.get("productID")
            or self.selected_product.get("id")
        )

        if not selected_id:
            return None

        latest_product = config.get_product_by_id(selected_id)
        if not latest_product:
            return None

        stock = config.get_product_stock(selected_id)
        merged = latest_product.copy()
        merged["stock"] = stock
        merged["available"] = stock > 0 and bool(latest_product.get("enabled", True))
        return merged

    def update_order_summary(self):
        self._clear_order_content()

        if not self.selected_product:
            self.empty_order_label = ctk.CTkLabel(
                self.order_content,
                text=config.get(
                    "purchase_page",
                    "no_item_selected_text",
                    default="Select a product to view details"
                ),
                font=theme.font(22, "bold"),
                text_color=theme.MUTED,
                justify="center",
                wraplength=500
            )
            self.empty_order_label.place(relx=0.5, rely=0.5, anchor="center")
            self.pay_btn.configure(state="disabled")
            self.scan_btn.configure(state="disabled")
            return

        price = float(self.selected_product["price"])
        discount_value = float(self.discount or 0)
        discount_text = "-" if discount_value <= 0 else f"{discount_value:.0f}%"
        total = price * (1 - discount_value / 100.0)

        item_label = config.get("purchase_page", "summary_item_label", default="Item")
        type_label = config.get("purchase_page", "summary_type_label", default="Type")
        discount_label = config.get("purchase_page", "summary_discount_label", default="Discount")
        total_label = config.get("purchase_page", "summary_total_label", default="Total Price")

        content_wrap = ctk.CTkFrame(
            self.order_content,
            fg_color="transparent"
        )
        content_wrap.place(
            relx=0.5,
            rely=0.5,
            anchor="center",
            relwidth=0.92
        )

        header = ctk.CTkLabel(
            content_wrap,
            text="Selected Product",
            font=theme.font(20, "bold"),
            text_color=theme.ORANGE,
            fg_color="transparent"
        )
        header.pack(anchor="w", padx=10, pady=(0, 10))

        self._make_summary_row(
            content_wrap,
            item_label,
            str(self.selected_product["name"]),
            value_color=theme.BLACK
        )
        self._make_summary_row(
            content_wrap,
            type_label,
            str(self.selected_product["type"]),
            value_color=theme.BLACK
        )

        self._make_divider(content_wrap)

        discount_color = theme.SUCCESS if discount_value > 0 else theme.MUTED

        self._make_summary_row(
            content_wrap,
            discount_label,
            discount_text,
            value_color=discount_color
        )
        self._make_summary_row(
            content_wrap,
            "Quantity",
            "1 pc",
            value_color=theme.BLACK
        )

        self._make_divider(content_wrap)

        self._make_summary_row(
            content_wrap,
            total_label,
            f"₱{total:.2f}",
            value_color=theme.ORANGE,
            large=True
        )

        is_available = bool(self.selected_product.get("available", False))
        self.pay_btn.configure(state="normal" if is_available else "disabled")
        self.scan_btn.configure(
            state="normal" if is_available and not self.scan_disabled else "disabled"
        )

    def update_data(self, user_data=None, **kwargs):
        if user_data:
            self.user_data = user_data
            self.username = user_data.get("username", "User")
            self.userID = user_data.get("userID")
            self.shell.set_header_right(f"Welcome, {self.username}!")

        self.reload_products(force=True)

    def logout(self):
        if self.listener:
            self.listener.stop()
            self.listener = None

        self.reset_fields()
        self.user_data = {}
        self.username = "User"
        self.userID = None
        self.shell.set_header_right("Welcome, User!")

        if hasattr(self.controller, "current_user"):
            self.controller.current_user = None

        if hasattr(self.controller, "frames"):
            qr_page = self.controller.frames.get("QRLoginPage")
            if qr_page and hasattr(qr_page, "reset_fields"):
                qr_page.reset_fields()

        self.controller.show_frame("WelcomePage")

    def on_tile_selected(self, tile):
        if not tile.available:
            self.status_label.configure(
                text=config.get("purchase_page", "out_of_stock_text", default="OUT OF STOCK"),
                text_color=theme.ERROR
            )
            return

        if self.selected_tile:
            self.selected_tile.set_selected(False)

        tile.set_selected(True)
        self.selected_tile = tile
        self.selected_product = tile.product.copy()
        self.selected_product["selection_id"] = str(uuid.uuid4())

        self.discount = None
        self.scan_disabled = False
        self.validation_in_progress = False
        self.qr_buffer = ""
        self.last_scanned_token = None
        self.discount_applied_token = None

        if self.listener:
            self.listener.stop()
            self.listener = None

        self.status_label.configure(text="", text_color=theme.ERROR)
        self.update_order_summary()

    def start_scan(self):
        if self.scan_disabled or not self.selected_product or self.validation_in_progress:
            return

        latest = self._resolve_latest_selected_product()
        if latest is None or not latest.get("available", False):
            self.selected_product = None
            self.selected_tile = None
            self.discount = None
            self.scan_disabled = False
            self.reload_products(force=True)
            self.status_label.configure(
                text=config.get("purchase_page", "out_of_stock_text", default="OUT OF STOCK"),
                text_color=theme.ERROR
            )
            return

        self.selected_product = latest
        self.update_order_summary()

        self.qr_buffer = ""
        self.last_scanned_token = None

        if self.listener:
            self.listener.stop()
            self.listener = None

        self.listener = keyboard.Listener(on_press=self.on_key_press)
        self.listener.start()

        self.status_label.configure(
            text=config.get(
                "purchase_page",
                "discount_ready_text",
                default="Ready to scan discount QR."
            ),
            text_color=theme.INFO
        )
        print("[PURCHASE] Discount QR scan started", flush=True)

    def on_key_press(self, key):
        if self.validation_in_progress or self.scan_disabled:
            return

        try:
            if hasattr(key, "char") and key.char:
                self.qr_buffer += key.char
        except AttributeError:
            pass

        if key == keyboard.Key.enter:
            scanned = self.qr_buffer.strip()
            self.qr_buffer = ""

            print(f"[PURCHASE] Raw scanned QR token: {repr(scanned)}", flush=True)

            if not scanned:
                self.after(
                    0,
                    lambda: self.status_label.configure(
                        text=config.get(
                            "purchase_page",
                            "empty_qr_text",
                            default="Empty QR scan detected."
                        ),
                        text_color=theme.ERROR
                    )
                )
                return

            if self.discount_applied_token == scanned:
                print(f"[PURCHASE] Ignoring already applied token: {repr(scanned)}", flush=True)
                self.after(
                    0,
                    lambda: self.status_label.configure(
                        text=config.get(
                            "purchase_page",
                            "discount_success_text",
                            default="QR token valid. Discount applied."
                        ),
                        text_color=theme.SUCCESS
                    )
                )
                self.after(0, self.update_order_summary)
                return

            if self.last_scanned_token == scanned:
                print(f"[PURCHASE] Ignoring duplicate token: {repr(scanned)}", flush=True)
                return

            self.last_scanned_token = scanned
            self.validation_in_progress = True

            if self.listener:
                self.listener.stop()
                self.listener = None

            threading.Thread(
                target=self._validate_and_apply_discount,
                args=(scanned,),
                daemon=True
            ).start()

    def _apply_discount_success(self, scanned):
        self.discount = float(config.get("purchase_page", "discount_percent", default=10))
        self.scan_disabled = True
        self.discount_applied_token = scanned

        self.status_label.configure(
            text=config.get(
                "purchase_page",
                "discount_success_text",
                default="QR token valid. Discount applied."
            ),
            text_color=theme.SUCCESS
        )
        self.update_order_summary()

    def _validate_and_apply_discount(self, scanned):
        try:
            print(f"[PURCHASE] Validating token for userID={repr(self.userID)} token={repr(scanned)}", flush=True)

            response = api_client.validate_discount_token(self.userID, scanned)

            content_type = response.headers.get("content-type", "")
            data = response.json() if content_type.startswith("application/json") else {}

            print(f"[PURCHASE] Validate response status={response.status_code}", flush=True)
            print(f"[PURCHASE] Validate response data={data}", flush=True)

            valid = response.ok and data.get("valid", False)

            if valid:
                self.after(0, lambda s=scanned: self._apply_discount_success(s))
                return

            msg = data.get("error") or config.get(
                "purchase_page",
                "invalid_discount_text",
                default="Invalid or expired QR token."
            )

            if msg == "Token already used." and self.discount_applied_token == scanned:
                print(f"[PURCHASE] Ignoring already-used response after successful apply: {repr(scanned)}", flush=True)
                self.after(0, lambda s=scanned: self._apply_discount_success(s))
                return

            self.after(
                0,
                lambda m=msg: self.status_label.configure(
                    text=m,
                    text_color=theme.ERROR
                )
            )

        except requests.RequestException as e:
            self.after(
                0,
                lambda err=str(e): self.status_label.configure(
                    text=f"{config.get('purchase_page', 'discount_error_prefix', default='QR validation failed:')} {err}",
                    text_color=theme.ERROR
                )
            )
        finally:
            self.validation_in_progress = False

    def go_to_payment(self):
        if not self.selected_product or not self.user_data:
            return

        latest = self._resolve_latest_selected_product()
        if latest is None or not latest.get("available", False):
            self.selected_product = None
            self.selected_tile = None
            self.discount = None
            self.scan_disabled = False
            self.reload_products(force=True)
            self.status_label.configure(
                text=config.get("purchase_page", "out_of_stock_text", default="OUT OF STOCK"),
                text_color=theme.ERROR
            )
            return

        self.selected_product = latest
        self.update_order_summary()

        self.controller.show_loading_then(
            config.get(
                "purchase_page",
                "payment_loading_text",
                default="Preparing payment options"
            ),
            "PaymentMethodPage",
            delay=1000,
            user_data=self.user_data,
            selected_product=self.selected_product.copy(),
            discount=self.discount or 0
        )

    def reset_fields(self, **kwargs):
        if self.listener:
            self.listener.stop()
            self.listener = None

        self.selected_tile = None
        self.selected_product = None
        self.discount = None
        self.qr_buffer = ""
        self.scan_disabled = False
        self.validation_in_progress = False
        self.last_scanned_token = None
        self.discount_applied_token = None

        for tile in getattr(self, "tiles", []):
            if isinstance(tile, ProductTile):
                tile.set_selected(False)

        self._clear_order_content()
        self.empty_order_label = ctk.CTkLabel(
            self.order_content,
            text=config.get(
                "purchase_page",
                "no_item_selected_text",
                default="Select a product to view details"
            ),
            font=theme.font(22, "bold"),
            text_color=theme.MUTED,
            justify="center",
            wraplength=500
        )
        self.empty_order_label.place(relx=0.5, rely=0.5, anchor="center")

        self.status_label.configure(text="", text_color=theme.ERROR)
        self.pay_btn.configure(state="disabled")
        self.scan_btn.configure(state="disabled")
        self.reload_products(force=True)