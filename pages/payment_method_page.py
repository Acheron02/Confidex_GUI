from frontend import tk_compat as ctk
from frontend import theme
from frontend.widgets import AppShell, RoundedCard, OutlineTile, PillButton, card_body
from PIL import Image


class PaymentMethodPage(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color=theme.CREAM)
        self.controller = controller
        self.user_data = {}
        self.selected_product = None
        self.discount = 0
        self.logo_refs = []  # Persistent storage for images

        self.shell = AppShell(self, title_right='Welcome, User!')
        self.shell.pack(fill='both', expand=True)

        # --- FIX: Top Bar with Absolute Centering ---
        # We use a frame where the title is centered and the back button is placed independently
        top_bar = ctk.CTkFrame(self.shell.body, fg_color='transparent')
        top_bar.pack(fill='x', padx=28, pady=(16, 8))
        
        # Back Button (Left Aligned)
        self.back_btn = PillButton(
            top_bar,
            text='Back',
            width=130,
            height=58,
            command=self.go_back,
            font=theme.font(18, 'bold')
        )
        self.back_btn.pack(side='left')

        # Title Label (Centered in the remaining space)
        # We use a second frame or just pack with expand to force true center
        self.title_label = ctk.CTkLabel(
            top_bar,
            text='CHOOSE PAYMENT METHOD',
            font=theme.heavy(32),
            text_color=theme.BLACK
        )
        # Pack with expand=True will center it relative to the whole top_bar
        self.title_label.pack(side='left', expand=True, padx=(0, 130)) # padx offsets the back button width

        # --- Main content ---
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
        stack.pack(expand=True, fill='both', padx=20, pady=10)
        stack.grid_columnconfigure(0, weight=1)

        self.desc_label = ctk.CTkLabel(
            stack,
            text='Choose how you want to pay for your selected test kit.',
            font=theme.font(20, 'bold'),
            text_color=theme.MUTED,
            fg_color=theme.WHITE,
            wraplength=520,
            justify='center'
        )
        self.desc_label.grid(row=0, column=0, padx=20, pady=(10, 20))

        # Cash payment tile
        self.cash_tile = self._create_option(
            stack,
            'CASH',
            'Settle payment via the machine slot',
            lambda: self.proceed_payment('cash')
        )
        self.cash_tile.grid(row=1, column=0, pady=(0, 16), padx=40, sticky='ew')

        # E-Payment tile
        self.online_tile = self._create_option(
            stack,
            'E-WALLETS',
            'Pay via GCash, Maya, or QRPh',
            lambda: self.proceed_payment('online'),
            add_logo_row=True
        )
        self.online_tile.grid(row=2, column=0, pady=(0, 16), padx=40, sticky='ew')

        self.status_label = ctk.CTkLabel(
            stack,
            text='',
            font=theme.font(18, 'bold'),
            text_color=theme.MUTED,
            fg_color=theme.WHITE,
            wraplength=560,
            justify='center'
        )
        self.status_label.grid(row=3, column=0, pady=(15, 6), padx=20)

    def _create_option(self, master, title, subtitle, command, add_logo_row=False):
        # Increased pad to ensure internal elements aren't cut off
        tile = OutlineTile(master, auto_size=True, pad=25) 
        body = card_body(tile)

        title_label = ctk.CTkLabel(
            body,
            text=title,
            font=theme.heavy(28),
            text_color=theme.BLACK,
            fg_color=theme.WHITE,
            justify='center'
        )
        title_label.pack(pady=(12, 4), anchor='center')

        subtitle_label = ctk.CTkLabel(
            body,
            text=subtitle,
            font=theme.font(17, 'bold'),
            text_color=theme.MUTED,
            fg_color=theme.WHITE,
            wraplength=350,
            justify='center'
        )
        subtitle_label.pack(pady=(0, 12), anchor='center')

        if add_logo_row:
            # Dedicated frame for logos
            logos_frame = ctk.CTkFrame(body, fg_color='transparent')
            logos_frame.pack(pady=(10, 15), anchor='center')

            try:
                # GCash
                gcash_img = ctk.CTkImage(Image.open("assets/gcash.png"), size=(10, 10))
                g_lbl = ctk.CTkLabel(logos_frame, image=gcash_img, text="")
                g_lbl.pack(side='left', padx=15)
                self.logo_refs.append(gcash_img) # Reference

                # Maya
                maya_img = ctk.CTkImage(Image.open("assets/maya.png"), size=(10, 10))
                m_lbl = ctk.CTkLabel(logos_frame, image=maya_img, text="")
                m_lbl.pack(side='left', padx=15)
                self.logo_refs.append(maya_img) # Reference

                # QRPH
                qrph_img = ctk.CTkImage(Image.open("assets/qrph.png"), size=(10, 10))
                q_lbl = ctk.CTkLabel(logos_frame, image=qrph_img, text="")
                q_lbl.pack(side='left', padx=15)
                self.logo_refs.append(qrph_img) # Reference

                # Bind logos to command
                for lbl in (g_lbl, m_lbl, q_lbl):
                    lbl.bind('<Button-1>', lambda e: command())

            except Exception as e:
                print(f"Error loading logos: {e}")

        # Bind whole tile
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
        self.status_label.configure(text='', text_color=theme.MUTED)

        if method == 'cash':
            self.controller.show_loading_then(
                'Preparing cash amount entry',
                'CashBillCheckPage',
                delay=1000,
                user_data=self.user_data,
                selected_product=self.selected_product,
                discount=self.discount
            )
            return

        self.controller.show_loading_then(
            'Preparing online payment',
            'OnlinePaymentPage',
            delay=1000,
            user_data=self.user_data,
            selected_product=self.selected_product,
            discount=self.discount
        )