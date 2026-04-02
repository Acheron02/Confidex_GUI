from frontend import tk_compat as ctk
from pynput import keyboard
import uuid
import threading
import requests
from frontend import theme
from frontend.widgets import AppShell, RoundedCard, PillButton, OutlineTile, card_body
from backend.util import api_client


class ProductTile(OutlineTile):
    def __init__(self, master, product, select_callback):
        super().__init__(master, pad=16, auto_size=False)
        self.product = product
        self.select_callback = select_callback
        self.selected = False

        body = self.content
        body.grid_rowconfigure(0, weight=1)
        body.grid_rowconfigure(1, weight=1)
        body.grid_rowconfigure(2, weight=1)
        body.grid_columnconfigure(0, weight=1)

        self.icon = ctk.CTkLabel(
            body,
            text='KIT',
            font=theme.heavy(26),
            text_color=theme.ORANGE,
            fg_color=theme.WHITE
        )
        self.icon.grid(row=0, column=0, sticky='s', pady=(6, 4))

        self.name = ctk.CTkLabel(
            body,
            text=product['type'],
            font=theme.font(20, 'bold'),
            text_color=theme.BLACK,
            fg_color=theme.WHITE,
            wraplength=220,
            justify='center'
        )
        self.name.grid(row=1, column=0, sticky='n', padx=8, pady=4)

        self.price = ctk.CTkLabel(
            body,
            text=f"₱{product['price']}",
            font=theme.font(18, 'bold'),
            text_color=theme.MUTED,
            fg_color=theme.WHITE
        )
        self.price.grid(row=2, column=0, sticky='n', pady=(4, 6))

        for w in (self, self.canvas, body, self.icon, self.name, self.price):
            w.bind('<Button-1>', lambda e: self.select_callback(self))

    def set_selected(self, selected: bool):
        self.selected = selected
        fill = theme.ORANGE if selected else theme.WHITE
        self.configure(fg_color=fill)

        text_color = theme.WHITE if selected else theme.BLACK
        price_color = theme.WHITE if selected else theme.MUTED

        for widget in (self.icon, self.name, self.price):
            widget.configure(fg_color=fill)

        self.name.configure(text_color=text_color)
        self.price.configure(text_color=price_color)
        self.icon.configure(text_color=theme.WHITE if selected else theme.ORANGE)


class PurchasePage(ctk.CTkFrame):
    def __init__(self, master, controller, user_data=None):
        super().__init__(master, fg_color=theme.CREAM)
        self.controller = controller
        self.user_data = user_data or {}
        self.username = self.user_data.get('username', 'User')
        self.userID = self.user_data.get('userID')

        self.selected_tile = None
        self.selected_product = None
        self.discount = None

        self.qr_buffer = ''
        self.scan_disabled = False
        self.listener = None

        self.validation_in_progress = False
        self.last_scanned_token = None
        self.discount_applied_token = None

        self.shell = AppShell(self, title_right='Welcome, User!')
        self.shell.pack(fill='both', expand=True)

        self.logout_btn = PillButton(
            self.shell.header_inner,
            text='Logout',
            width=140,
            height=46,
            command=self.logout,
            font=theme.font(16, 'bold')
        )
        self.logout_btn.pack(side='right', padx=24)

        title = ctk.CTkLabel(
            self.shell.body,
            text='SELECT A PRODUCT',
            font=theme.heavy(34),
            text_color=theme.BLACK
        )
        title.pack(pady=(18, 12))

        content = ctk.CTkFrame(self.shell.body, fg_color='transparent')
        content.pack(expand=True, fill='both', padx=28, pady=(0, 18))
        content.grid_columnconfigure(0, weight=1, uniform='purchase-col')
        content.grid_columnconfigure(1, weight=1, uniform='purchase-col')
        content.grid_rowconfigure(0, weight=1)

        left = RoundedCard(content, auto_size=False)
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 14), pady=8)

        right = RoundedCard(content, auto_size=False)
        right.grid(row=0, column=1, sticky='nsew', padx=(14, 0), pady=8)

        left_body = card_body(left)
        right_body = card_body(right)

        left_body.grid_rowconfigure(0, weight=0)
        left_body.grid_rowconfigure(1, weight=1)
        left_body.grid_columnconfigure(0, weight=1)

        left_title = ctk.CTkLabel(
            left_body,
            text='Testing Kits',
            font=theme.heavy(28),
            text_color=theme.BLACK,
            fg_color=theme.WHITE
        )
        left_title.grid(row=0, column=0, pady=(16, 10))

        tiles = ctk.CTkFrame(left_body, fg_color=theme.WHITE)
        tiles.grid(row=1, column=0, sticky='nsew', padx=12, pady=(0, 12))
        tiles.grid_rowconfigure(0, weight=1)
        tiles.grid_columnconfigure(0, weight=1, uniform='product-col')
        tiles.grid_columnconfigure(1, weight=1, uniform='product-col')

        self.products = [
            {'name': 'Confidex Kit', 'product_id': 'HIV123', 'type': 'HIV Test', 'price': 50},
            {'name': 'Confidex Kit', 'product_id': 'DENGUE123', 'type': 'Dengue Test', 'price': 80},
        ]

        self.tiles = []
        for index, product in enumerate(self.products):
            tile = ProductTile(tiles, product, self.on_tile_selected)
            tile.grid(row=0, column=index, sticky='nsew', padx=10, pady=10)
            self.tiles.append(tile)

        right_body.grid_rowconfigure(0, weight=0)
        right_body.grid_rowconfigure(1, weight=1)
        right_body.grid_rowconfigure(2, weight=0)
        right_body.grid_rowconfigure(3, weight=0)
        right_body.grid_columnconfigure(0, weight=1)

        right_title = ctk.CTkLabel(
            right_body,
            text='Order Details',
            font=theme.heavy(28),
            text_color=theme.BLACK,
            fg_color=theme.WHITE
        )
        right_title.grid(row=0, column=0, pady=(16, 10))

        self.order_box = ctk.CTkFrame(
            right_body,
            fg_color="transparent",
            border_color="#CCCCCC",
            border_width=2,
            corner_radius=12,
            width=440,
            height=320
        )
        self.order_box.grid(row=1, column=0, pady=10)
        self.order_box.grid_propagate(False)

        self.order_text = ctk.CTkLabel(
            self.order_box,
            text='No item selected',
            font=theme.font(18, 'bold'),
            text_color="#999999",
            justify='center',
            wraplength=400
        )
        self.order_text.place(relx=0.5, rely=0.5, anchor='center')

        self.status_label = ctk.CTkLabel(
            right_body,
            text='',
            font=theme.font(18, 'bold'),
            text_color=theme.ERROR,
            wraplength=380,
            justify='center',
            anchor='center',
            fg_color=theme.WHITE
        )
        self.status_label.grid(row=2, column=0, sticky='nsew', padx=20, pady=(5, 10))

        btns = ctk.CTkFrame(right_body, fg_color=theme.WHITE)
        btns.grid(row=3, column=0, sticky='ew', pady=(8, 18))
        btns.grid_columnconfigure(0, weight=1)
        btns.grid_columnconfigure(1, weight=0)
        btns.grid_columnconfigure(2, weight=0)
        btns.grid_columnconfigure(3, weight=1)

        self.scan_btn = PillButton(
            btns,
            text='Discount',
            width=180,
            height=58,
            command=self.start_scan,
            state='disabled',
            font=theme.font(19, 'bold')
        )
        self.scan_btn.grid(row=0, column=1, padx=20)

        self.pay_btn = PillButton(
            btns,
            text='Pay',
            width=180,
            height=58,
            command=self.go_to_payment,
            state='disabled',
            font=theme.font(19, 'bold')
        )
        self.pay_btn.grid(row=0, column=2, padx=20)

    def update_order_summary(self):
        if not self.selected_product:
            self.order_text.configure(text='No item selected', text_color=theme.MUTED)
            self.pay_btn.configure(state='disabled')
            self.scan_btn.configure(state='disabled')
            return

        price = float(self.selected_product['price'])
        discount_value = float(self.discount or 0)
        discount_text = '-' if discount_value <= 0 else f'{discount_value:.0f}%'
        total = price * (1 - discount_value / 100.0)

        self.order_text.configure(
            text=(
                f"Item: {self.selected_product['name']}\n\n"
                f"Type: {self.selected_product['type']}\n\n"
                f"Amount: ₱{price:.2f}\n\n"
                f"Discount: {discount_text}\n\n"
                f"Total Price: ₱{total:.2f}"
            ),
            text_color="#999999",
        )
        self.pay_btn.configure(state='normal')
        self.scan_btn.configure(state='normal' if not self.scan_disabled else 'disabled')

    def update_data(self, user_data=None, **kwargs):
        if user_data:
            self.user_data = user_data
            self.username = user_data.get('username', 'User')
            self.userID = user_data.get('userID')
            self.shell.set_header_right(f'Welcome, {self.username}!')

    def logout(self):
        if self.listener:
            self.listener.stop()
            self.listener = None

        self.reset_fields()
        self.user_data = {}
        self.username = 'User'
        self.userID = None
        self.shell.set_header_right('Welcome, User!')

        if hasattr(self.controller, 'current_user'):
            self.controller.current_user = None

        if hasattr(self.controller, 'frames'):
            qr_page = self.controller.frames.get('QRLoginPage')
            if qr_page and hasattr(qr_page, 'reset_fields'):
                qr_page.reset_fields()

        self.controller.show_frame('WelcomePage')

    def on_tile_selected(self, tile):
        if self.selected_tile:
            self.selected_tile.set_selected(False)

        tile.set_selected(True)
        self.selected_tile = tile
        self.selected_product = tile.product.copy()
        self.selected_product['selection_id'] = str(uuid.uuid4())

        self.discount = None
        self.scan_disabled = False
        self.validation_in_progress = False
        self.qr_buffer = ''
        self.last_scanned_token = None
        self.discount_applied_token = None

        if self.listener:
            self.listener.stop()
            self.listener = None

        self.status_label.configure(text='', text_color=theme.ERROR)
        self.update_order_summary()

    def start_scan(self):
        if self.scan_disabled or not self.selected_product or self.validation_in_progress:
            return

        self.qr_buffer = ''
        self.last_scanned_token = None

        if self.listener:
            self.listener.stop()
            self.listener = None

        self.listener = keyboard.Listener(on_press=self.on_key_press)
        self.listener.start()

        self.status_label.configure(
            text='Ready to scan discount QR.',
            text_color=theme.INFO
        )
        print('[PURCHASE] Discount QR scan started', flush=True)

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
            self.qr_buffer = ''

            print(f'[PURCHASE] Raw scanned QR token: {repr(scanned)}', flush=True)

            if not scanned:
                self.after(
                    0,
                    lambda: self.status_label.configure(
                        text='Empty QR scan detected.',
                        text_color=theme.ERROR
                    )
                )
                return

            if self.discount_applied_token == scanned:
                print(f'[PURCHASE] Ignoring already applied token: {repr(scanned)}', flush=True)
                self.after(
                    0,
                    lambda: self.status_label.configure(
                        text='QR token valid. Discount applied.',
                        text_color=theme.SUCCESS
                    )
                )
                self.after(0, self.update_order_summary)
                return

            if self.last_scanned_token == scanned:
                print(f'[PURCHASE] Ignoring duplicate token: {repr(scanned)}', flush=True)
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
        self.discount = 10
        self.scan_disabled = True
        self.discount_applied_token = scanned

        self.status_label.configure(
            text='QR token valid. Discount applied.',
            text_color=theme.SUCCESS
        )
        self.update_order_summary()

    def _validate_and_apply_discount(self, scanned):
        try:
            print(f'[PURCHASE] Validating token for userID={repr(self.userID)} token={repr(scanned)}', flush=True)

            response = api_client.validate_discount_token(self.userID, scanned)

            content_type = response.headers.get('content-type', '')
            data = response.json() if content_type.startswith('application/json') else {}

            print(f'[PURCHASE] Validate response status={response.status_code}', flush=True)
            print(f'[PURCHASE] Validate response data={data}', flush=True)

            valid = response.ok and data.get('valid', False)

            if valid:
                self.after(0, lambda s=scanned: self._apply_discount_success(s))
                return

            msg = data.get('error') or 'Invalid or expired QR token.'

            if msg == 'Token already used.' and self.discount_applied_token == scanned:
                print(f'[PURCHASE] Ignoring already-used response after successful apply: {repr(scanned)}', flush=True)
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
                    text=f'QR validation failed: {err}',
                    text_color=theme.ERROR
                )
            )
        finally:
            self.validation_in_progress = False

    def go_to_payment(self):
        if self.selected_product and self.user_data:
            self.controller.show_loading_then(
                'Preparing payment options',
                'PaymentMethodPage',
                delay=1000,
                user_data=self.user_data,
                selected_product=self.selected_product,
                discount=self.discount or 0
            )

    def reset_fields(self, **kwargs):
        if self.listener:
            self.listener.stop()
            self.listener = None

        self.selected_tile = None
        self.selected_product = None
        self.discount = None
        self.qr_buffer = ''
        self.scan_disabled = False
        self.validation_in_progress = False
        self.last_scanned_token = None
        self.discount_applied_token = None

        for tile in self.tiles:
            tile.set_selected(False)

        self.order_text.configure(text='No item selected', text_color=theme.MUTED)
        self.status_label.configure(text='', text_color=theme.ERROR)
        self.pay_btn.configure(state='disabled')
        self.scan_btn.configure(state='disabled')