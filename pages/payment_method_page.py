from frontend import tk_compat as ctk
from frontend import theme
from frontend.widgets import AppShell, RoundedCard, OutlineTile, PillButton, card_body


class PaymentMethodPage(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color=theme.CREAM)
        self.controller = controller
        self.user_data = {}
        self.selected_product = None
        self.discount = 0

        self.shell = AppShell(self, title_right='Welcome, User!')
        self.shell.pack(fill='both', expand=True)

        top_bar = ctk.CTkFrame(self.shell.body, fg_color='transparent')
        top_bar.pack(fill='x', padx=28, pady=(16, 8))
        top_bar.grid_columnconfigure(0, weight=0)
        top_bar.grid_columnconfigure(1, weight=1)
        top_bar.grid_columnconfigure(2, weight=0)

        self.back_btn = PillButton(
            top_bar,
            text='Back',
            width=130,
            height=58,
            command=self.go_back,
            font=theme.font(18, 'bold')
        )
        self.back_btn.grid(row=0, column=0, sticky='w')

        self.title_label = ctk.CTkLabel(
            top_bar,
            text='CHOOSE PAYMENT METHOD',
            font=theme.heavy(32),
            text_color=theme.BLACK
        )
        self.title_label.grid(row=0, column=1)

        content_wrap = ctk.CTkFrame(self.shell.body, fg_color='transparent')
        content_wrap.pack(expand=True, fill='both')

        content_wrap.grid_columnconfigure(0, weight=1)
        content_wrap.grid_rowconfigure(0, weight=1)
        content_wrap.grid_rowconfigure(1, weight=0)
        content_wrap.grid_rowconfigure(2, weight=1)

        self.main_card = RoundedCard(content_wrap, auto_size=True, pad=18)
        self.main_card.grid(row=1, column=0)

        body = card_body(self.main_card)

        stack = ctk.CTkFrame(body, fg_color=theme.WHITE)
        stack.pack(expand=True, fill='both')

        stack.grid_columnconfigure(0, weight=1)
        stack.grid_columnconfigure(1, weight=1)

        self.desc_label = ctk.CTkLabel(
            stack,
            text='Choose how you want to pay for your selected test kit.',
            font=theme.font(20, 'bold'),
            text_color=theme.MUTED,
            fg_color=theme.WHITE,
            wraplength=520,
            justify='center'
        )
        self.desc_label.grid(row=0, column=0, columnspan=2, padx=20, pady=(6, 16))

        self.cash_tile = self._create_option(
            stack,
            'CASH',
            'Cash Payment',
            lambda: self.proceed_payment('cash')
        )
        self.cash_tile.grid(row=1, column=0, padx=14, pady=12, sticky='nsew')

        self.online_tile = self._create_option(
            stack,
            'E-WALLETS',
            'PayMongo / GCash / Maya',
            lambda: self.proceed_payment('online')
        )
        self.online_tile.grid(row=1, column=1, padx=14, pady=12, sticky='nsew')

        self.status_label = ctk.CTkLabel(
            stack,
            text='',
            font=theme.font(18, 'bold'),
            text_color=theme.MUTED,
            fg_color=theme.WHITE,
            wraplength=560,
            justify='center'
        )
        self.status_label.grid(row=2, column=0, columnspan=2, pady=(10, 6), padx=20)

    def _create_option(self, master, title, subtitle, command):
        tile = OutlineTile(master, auto_size=True, pad=16)
        body = card_body(tile)

        title_label = ctk.CTkLabel(
            body,
            text=title,
            font=theme.heavy(26),
            text_color=theme.BLACK,
            fg_color=theme.WHITE
        )
        title_label.pack(padx=30, pady=(12, 6))

        subtitle_label = ctk.CTkLabel(
            body,
            text=subtitle,
            font=theme.font(18, 'bold'),
            text_color=theme.MUTED,
            fg_color=theme.WHITE,
            wraplength=320,
            justify='center'
        )
        subtitle_label.pack(padx=30, pady=(0, 12))

        for w in (tile, tile.canvas, body, title_label, subtitle_label):
            w.bind('<Button-1>', lambda e: command())

        return tile

    def update_data(self, user_data=None, selected_product=None, discount=0, **kwargs):
        self.user_data = user_data or {}
        self.selected_product = selected_product
        self.discount = discount or 0
        self.shell.set_header_right(f"Welcome, {self.user_data.get('username', 'User')}!")
        self.status_label.configure(text='', text_color=theme.MUTED)

    def go_back(self):
        self.controller.show_loading_then(
            'Returning to product selection',
            'PurchasePage',
            delay=1000,
            user_data=self.user_data,
            selected_product=self.selected_product,
            discount=self.discount
        )

    def proceed_payment(self, method):
        if method == 'cash':
            self.status_label.configure(text='', text_color=theme.MUTED)
            self.controller.show_loading_then(
                'Preparing cash payment',
                'CashPaymentPage',
                delay=1000,
                user_data=self.user_data,
                selected_product=self.selected_product,
                discount=self.discount
            )
            return

        if method == 'online':
            self.status_label.configure(text='', text_color=theme.MUTED)
            self.controller.show_loading_then(
                'Preparing online payment',
                'OnlinePaymentPage',
                delay=1000,
                user_data=self.user_data,
                selected_product=self.selected_product,
                discount=self.discount
            )