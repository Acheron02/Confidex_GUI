from frontend import tk_compat as ctk
from frontend import theme
from frontend.widgets import AppShell, RoundedCard, card_body


class WelcomePage(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color=theme.CREAM)
        self.controller = controller

        shell = AppShell(self)
        shell.pack(fill='both', expand=True)

        center_frame = ctk.CTkFrame(shell.body, fg_color='transparent')
        center_frame.pack(expand=True)

        accent = ctk.CTkLabel(
            center_frame,
            text='●    ●    ●',
            font=theme.font(22, 'bold'),
            text_color=theme.ORANGE
        )
        accent.pack(pady=(0, 6))

        title = ctk.CTkLabel(
            center_frame,
            text='WELCOME!',
            font=theme.heavy(58),
            text_color=theme.TEXT
        )
        title.pack(pady=(10, 10))

        subtitle = ctk.CTkLabel(
            center_frame,
            text='Anonymous blood-based health screening starts here.',
            font=theme.font(22, 'bold'),
            text_color=theme.MUTED
        )
        subtitle.pack(pady=(0, 18))

        self.notice_label = ctk.CTkLabel(
            center_frame,
            text='',
            font=theme.font(18, 'bold'),
            text_color=theme.ORANGE,
            wraplength=720,
            justify='center'
        )
        self.notice_label.pack(pady=(0, 14))

        tap_card = RoundedCard(
            center_frame,
            fg_color=theme.ORANGE,
            border_width=0,
            width=360,
            height=92
        )
        tap_card.pack(pady=12)
        tap_body = card_body(tap_card)

        tap_text = ctk.CTkLabel(
            tap_body,
            text='TAP TO PROCEED!',
            font=theme.heavy(28),
            text_color=theme.WHITE,
            fg_color=theme.ORANGE
        )
        tap_text.pack(expand=True)

        hint = ctk.CTkLabel(
            center_frame,
            text='Tap anywhere on the screen to continue to QR login.',
            font=theme.font(18, 'bold'),
            text_color=theme.MUTED
        )
        hint.pack(pady=(20, 0))

        for widget in (
            self, shell, shell.body, center_frame, title, subtitle,
            tap_card, tap_card.canvas, tap_body, tap_text, hint,
            accent, self.notice_label
        ):
            widget.bind('<Button-1>', self.go_to_login)

    def set_notice(self, message=''):
        self.notice_label.configure(text=message or '')

    def go_to_login(self, event=None):
        self.set_notice('')
        self.controller.show_frame('QRLoginPage')