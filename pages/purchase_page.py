from frontend import tk_compat as ctk
from pynput import keyboard
import uuid
import threading
import requests
from tkinter import messagebox
from frontend import theme
from frontend.widgets import AppShell, RoundedCard, PillButton, OutlineTile, card_body
from backend.util import api_client


class ProductTile(OutlineTile):
    def __init__(self, master, product, select_callback):
        super().__init__(master, width=170, height=190)
        self.product = product
        self.select_callback = select_callback
        self.selected = False
        body = self.content

        self.icon = ctk.CTkLabel(body, text='KIT', font=theme.heavy(26), text_color=theme.ORANGE, fg_color=theme.WHITE)
        self.icon.pack(pady=(22, 12))

        self.name = ctk.CTkLabel(body, text=product['type'], font=theme.font(20, 'bold'), text_color=theme.BLACK, fg_color=theme.WHITE)
        self.name.pack(pady=(0, 4))

        self.price = ctk.CTkLabel(body, text=f"₱{product['price']}", font=theme.font(18, 'bold'), text_color=theme.MUTED, fg_color=theme.WHITE)
        self.price.pack()

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

        self.shell = AppShell(self, title_right='Welcome, User!')
        self.shell.pack(fill='both', expand=True)

        top_bar = ctk.CTkFrame(self.shell.body, fg_color='transparent')
        top_bar.pack(fill='x', padx=28, pady=(16, 6))

        title = ctk.CTkLabel(top_bar, text='SELECT A PRODUCT', font=theme.heavy(34), text_color=theme.BLACK)
        title.pack(side='left')

        self.logout_btn = PillButton(
            top_bar,
            text='Logout',
            width=130,
            command=self.prompt_logout,
            font=theme.font(18, 'bold')
        )
        self.logout_btn.pack(side='right')

        content = ctk.CTkFrame(self.shell.body, fg_color='transparent')
        content.pack(expand=True, fill='both', padx=28, pady=(0, 18))
        content.grid_columnconfigure((0, 1), weight=1)
        content.grid_rowconfigure(0, weight=1)

        left = RoundedCard(content)
        left.grid(row=0, column=0, sticky='nsew', padx=(0, 14), pady=8)

        right = RoundedCard(content)
        right.grid(row=0, column=1, sticky='nsew', padx=(14, 0), pady=8)

        left_body = card_body(left)
        right_body = card_body(right)

        ctk.CTkLabel(left_body, text='Testing Kits', font=theme.heavy(28), text_color=theme.BLACK, fg_color=theme.WHITE).pack(pady=(22, 18))

        tiles = ctk.CTkFrame(left_body, fg_color=theme.WHITE)
        tiles.pack(pady=(0, 20))

        self.products = [
            {'name': 'Confidex Kit', 'product_id': 'HIV123', 'type': 'HIV Test', 'price': 300},
            {'name': 'Confidex Kit', 'product_id': 'DENGUE123', 'type': 'Dengue Test', 'price': 250},
        ]

        self.tiles = []
        for product in self.products:
            tile = ProductTile(tiles, product, self.on_tile_selected)
            tile.pack(side='left', padx=12, pady=16)
            self.tiles.append(tile)

        ctk.CTkLabel(right_body, text='Order Details', font=theme.heavy(28), text_color=theme.BLACK, fg_color=theme.WHITE).pack(pady=(22, 18))

        self.order_text = ctk.CTkLabel(
            right_body,
            text='No item selected',
            font=theme.font(22, 'bold'),
            text_color=theme.MUTED,
            justify='left',
            fg_color=theme.WHITE
        )
        self.order_text.pack(padx=28, pady=(16, 8), anchor='w')

        self.status_label = ctk.CTkLabel(
            right_body,
            text='',
            font=theme.font(18, 'bold'),
            text_color=theme.ERROR,
            wraplength=380,
            justify='left',
            fg_color=theme.WHITE
        )
        self.status_label.pack(padx=28, pady=(10, 8), anchor='w')

        btns = ctk.CTkFrame(right_body, fg_color=theme.WHITE)
        btns.pack(side='bottom', pady=24)

        self.scan_btn = PillButton(
            btns,
            text='Discount',
            width=170,
            command=self.start_scan,
            state='disabled',
            font=theme.font(20, 'bold')
        )
        self.scan_btn.pack(side='left', padx=10)

        self.pay_btn = PillButton(
            btns,
            text='Pay',
            width=170,
            command=self.go_to_payment,
            state='disabled',
            font=theme.font(20, 'bold')
        )
        self.pay_btn.pack(side='left', padx=10)

    def update_data(self, user_data=None, selected_product=None, discount=None, **kwargs):
        if user_data:
            self.user_data = user_data
            self.username = user_data.get('username', 'User')
            self.userID = user_data.get('userID')
            self.shell.set_header_right(f'Welcome, {self.username}!')

        if selected_product:
            self.selected_product = selected_product.copy()
            self.discount = discount or 0
            self.scan_disabled = bool(self.discount)

            matched_tile = None
            for tile in self.tiles:
                tile.set_selected(False)
                if tile.product.get('type') == self.selected_product.get('type'):
                    matched_tile = tile

            if matched_tile:
                matched_tile.set_selected(True)
                self.selected_tile = matched_tile

            self.update_order_summary()

    def prompt_logout(self):
        if messagebox.askyesno(
            'Confirm Logout',
            'Are you sure you want to cancel this transaction?\n\nYou will need to generate a new login QR code from the website.'
        ):
            self.controller.cancel_session_and_return_home(
                'Session cancelled. Please generate a new login QR code from the website.'
            )

    def on_tile_selected(self, tile):
        if self.selected_tile:
            self.selected_tile.set_selected(False)

        tile.set_selected(True)
        self.selected_tile = tile
        self.selected_product = tile.product.copy()
        self.selected_product['product_id'] = str(uuid.uuid4())
        self.discount = None
        self.scan_disabled = False
        self.status_label.configure(text='')
        self.update_order_summary()

    def update_order_summary(self):
        if not self.selected_product:
            self.order_text.configure(text='No item selected', text_color=theme.MUTED)
            self.pay_btn.configure(state='disabled')
            self.scan_btn.configure(state='disabled')
            return

        price = self.selected_product['price']
        discount_text = '-' if not self.discount else f'{self.discount}%'
        total = price * (1 - (self.discount or 0) / 100)

        self.order_text.configure(
            text=(
                f"Item: {self.selected_product['name']}\n"
                f"Type: {self.selected_product['type']}\n"
                f"Amount: ₱{price}\n"
                f"Discount: {discount_text}\n"
                f"Total Price: ₱{total:.2f}"
            ),
            text_color=theme.BLACK,
        )
        self.pay_btn.configure(state='normal')
        self.scan_btn.configure(state='normal' if not self.scan_disabled else 'disabled')

    def start_scan(self):
        if self.scan_disabled or not self.selected_product:
            return

        self.qr_buffer = ''
        if self.listener:
            self.listener.stop()

        self.listener = keyboard.Listener(on_press=self.on_key_press)
        self.listener.start()
        self.status_label.configure(text='Ready to scan discount QR.', text_color=theme.INFO)

    def on_key_press(self, key):
        try:
            if key.char:
                self.qr_buffer += key.char
        except AttributeError:
            if key == keyboard.Key.enter:
                scanned = self.qr_buffer.strip()
                self.qr_buffer = ''
                threading.Thread(
                    target=self._validate_and_apply_discount,
                    args=(scanned,),
                    daemon=True
                ).start()

    def _validate_and_apply_discount(self, scanned):
        try:
            response = api_client.validate_discount_token(self.userID, scanned)
            data = response.json() if response.headers.get('content-type', '').startswith('application/json') else {}
            valid = response.ok and data.get('valid', False)

            if valid:
                self.discount = 10
                self.scan_disabled = True
                self.after(0, lambda: self.status_label.configure(text='QR token valid. Discount applied.', text_color=theme.SUCCESS))
                self.after(0, self.update_order_summary)

                if self.listener:
                    self.listener.stop()
                    self.listener = None
            else:
                msg = data.get('error') or 'Invalid or expired QR token.'
                self.after(0, lambda: self.status_label.configure(text=msg, text_color=theme.ERROR))

        except requests.RequestException as e:
            self.after(0, lambda: self.status_label.configure(text=f'QR validation failed: {e}', text_color=theme.ERROR))

    def go_to_payment(self):
        if self.selected_product and self.user_data:
            self.controller.show_frame(
                'PaymentMethodPage',
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

        for tile in self.tiles:
            tile.set_selected(False)

        self.order_text.configure(text='No item selected', text_color=theme.MUTED)
        self.status_label.configure(text='', text_color=theme.ERROR)
        self.pay_btn.configure(state='disabled')
        self.scan_btn.configure(state='disabled')