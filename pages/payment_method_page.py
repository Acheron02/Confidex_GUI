from frontend import tk_compat as ctk
from tkinter import messagebox
from frontend import theme
from frontend.widgets import AppShell, RoundedCard, OutlineTile, PillButton, card_body


class PaymentMethodPage(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color=theme.CREAM)
        self.controller = controller
        self.user_data = {}
        self.selected_product = None
        self.discount = 0
        self.redirect_job = None

        self.shell = AppShell(self, title_right='Welcome, User!')
        self.shell.pack(fill='both', expand=True)

        top_bar = ctk.CTkFrame(self.shell.body, fg_color='transparent')
        top_bar.pack(fill='x', padx=28, pady=(16, 6))

        self.back_btn = PillButton(
            top_bar,
            text='Back',
            width=120,
            command=self.go_back,
            font=theme.font(18, 'bold')
        )
        self.back_btn.pack(side='left')

        ctk.CTkLabel(
            top_bar,
            text='CHOOSE PAYMENT METHOD',
            font=theme.heavy(32),
            text_color=theme.BLACK
        ).pack(side='left', padx=18)

        self.logout_btn = PillButton(
            top_bar,
            text='Logout',
            width=120,
            command=self.prompt_logout,
            font=theme.font(18, 'bold')
        )
        self.logout_btn.pack(side='right')

        self.main_card = RoundedCard(self.shell.body, width=700, height=360)
        self.main_card.place(relx=0.5, rely=0.50, anchor='center')
        body = card_body(self.main_card)

        stack = ctk.CTkFrame(body, fg_color=theme.WHITE)
        stack.pack(expand=True)

        options_row = ctk.CTkFrame(stack, fg_color=theme.WHITE)
        options_row.pack(pady=(28, 18))

        self.cash_tile = self._create_option(
            options_row,
            'CASH',
            'Cash Payment',
            lambda: self.proceed_payment('cash')
        )
        self.cash_tile.pack(side='left', padx=16)

        self.ewallet_tile = self._create_option(
            options_row,
            'E-WALLET',
            'GCash / Maya / Online',
            lambda: self.proceed_payment('ewallet')
        )
        self.ewallet_tile.pack(side='left', padx=16)

        self.status_label = ctk.CTkLabel(
            stack,
            text='',
            font=theme.font(18, 'bold'),
            text_color=theme.MUTED,
            fg_color=theme.WHITE,
            wraplength=520,
            justify='center'
        )
        self.status_label.pack(pady=(8, 0))

    def _create_option(self, master, title, subtitle, command):
        tile = OutlineTile(master, width=220, height=140)
        body = card_body(tile)

        title_label = ctk.CTkLabel(body, text=title, font=theme.heavy(26), text_color=theme.BLACK, fg_color=theme.WHITE)
        title_label.pack(pady=(22, 6))

        subtitle_label = ctk.CTkLabel(body, text=subtitle, font=theme.font(18, 'bold'), text_color=theme.MUTED, fg_color=theme.WHITE)
        subtitle_label.pack()

        for w in (tile, tile.canvas, body, title_label, subtitle_label):
            w.bind('<Button-1>', lambda e: command())

        return tile

    def update_data(self, user_data=None, selected_product=None, discount=0, **kwargs):
        self.user_data = user_data or {}
        self.selected_product = selected_product
        self.discount = discount or 0
        self.shell.set_header_right(f"Welcome, {self.user_data.get('username', 'User')}!")
        self.status_label.configure(text='')

        if self.redirect_job is not None:
            try:
                self.after_cancel(self.redirect_job)
            except Exception:
                pass
            self.redirect_job = None

    def prompt_logout(self):
        if messagebox.askyesno(
            'Confirm Logout',
            'Are you sure you want to cancel this transaction?\n\nYou will need to generate a new login QR code from the website.'
        ):
            self.controller.cancel_session_and_return_home(
                'Session cancelled. Please generate a new login QR code from the website.'
            )

    def go_back(self):
        self.controller.show_frame(
            'PurchasePage',
            user_data=self.user_data,
            selected_product=self.selected_product,
            discount=self.discount
        )

    def proceed_payment(self, method):
        if method == 'cash':
            self.status_label.configure(text='')
            self.controller.show_frame(
                'CashPaymentPage',
                user_data=self.user_data,
                selected_product=self.selected_product,
                discount=self.discount
            )

        elif method == 'ewallet':
            self.status_label.configure(
                text='Online payment is not yet available. Redirecting to cash payment instead.',
                text_color=theme.ORANGE
            )
            self.redirect_job = self.after(1800, self._go_to_cash_fallback)

    def _go_to_cash_fallback(self):
        self.redirect_job = None
        self.controller.show_frame(
            'CashPaymentPage',
            user_data=self.user_data,
            selected_product=self.selected_product,
            discount=self.discount
        )

    def reset_fields(self, **kwargs):
        if self.redirect_job is not None:
            try:
                self.after_cancel(self.redirect_job)
            except Exception:
                pass
            self.redirect_job = None

        self.user_data = {}
        self.selected_product = None
        self.discount = 0
        self.status_label.configure(text='')