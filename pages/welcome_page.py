import os
from PIL import Image
from frontend import tk_compat as ctk
from frontend import theme
from frontend.widgets import AppShell, RoundedCard, card_body

class WelcomePage(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color=theme.CREAM)
        self.controller = controller

        shell = AppShell(self)
        shell.pack(fill='both', expand=True)

        main_container = RoundedCard(
            shell.body,
            fg_color=theme.WHITE,
            radius=40,
            height=600,
            width=700,
            auto_size=False
        )
        main_container.pack(expand=True, padx=80, pady=40) 
        container_body = card_body(main_container)

        try:
            logo_path = os.path.join("assets/logo2.png")
            from PIL import ImageTk

            img = Image.open(logo_path)
            img.thumbnail((350, 100))  # keep proportion and fit inside box
            logo_image = ImageTk.PhotoImage(img)

            logo_label = ctk.CTkLabel(container_body, image=logo_image, text="")
            logo_label.image = logo_image  # keep reference to prevent GC
            logo_label.pack(pady=(40, 10))
        except Exception as e:
            print("Logo load failed:", e)
            logo_label = ctk.CTkLabel(container_body, text="CONFIDEX", font=theme.heavy(42))
            logo_label.pack(pady=(40, 10))

        title = ctk.CTkLabel(
            container_body,
            text='WELCOME',
            font=theme.heavy(64),
            text_color=theme.TEXT
        )
        title.pack(pady=(10, 5))

        subtitle = ctk.CTkLabel(
            container_body,
            text='Anonymous Health Screening',
            font=theme.font(22, 'bold'),
            text_color=theme.MUTED
        )
        subtitle.pack(pady=(0, 40))

        tap_card = RoundedCard(
            container_body,
            fg_color=theme.ORANGE,
            border_width=0,
            radius=25,
            pad=10,
            auto_size=True
        )
        tap_card.pack(pady=20)
        tap_body = card_body(tap_card)

        tap_text = ctk.CTkLabel(
            tap_body,
            text='TAP TO PROCEED',
            font=theme.font(24, 'bold'),
            text_color=theme.WHITE
        )
        tap_text.pack(padx=80, pady=20)

        hint = ctk.CTkLabel(
            container_body,
            text='Tap anywhere to start your QR login',
            font=theme.font(16, 'normal'),
            text_color=theme.MUTED
        )
        hint.pack(pady=(20, 40))

        all_widgets = [
            self, shell, shell.body, main_container, container_body, 
            logo_label, title, subtitle, tap_card, tap_body, tap_text, hint
        ]
        
        for widget in all_widgets:
            if hasattr(widget, 'canvas'):
                widget.canvas.bind('<Button-1>', self.go_to_login)
            widget.bind('<Button-1>', self.go_to_login)

    def go_to_login(self, event=None):
        self.controller.show_frame('QRLoginPage')