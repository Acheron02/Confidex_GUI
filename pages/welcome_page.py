import os
from PIL import Image
from frontend import tk_compat as ctk
from frontend import theme
from frontend.widgets import AppShell, RoundedCard, card_body
from config_manager import config


class WelcomePage(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color=theme.CREAM)
        self.controller = controller

        self.shell = AppShell(self)
        self.shell.pack(fill="both", expand=True)

        self.main_container = RoundedCard(
            self.shell.body,
            fg_color=theme.WHITE,
            radius=40,
            height=600,
            width=700,
            auto_size=False
        )
        self.main_container.pack(expand=True, padx=80, pady=40)

        self.container_body = card_body(self.main_container)

        self.logo_label = None
        self.title_label = None
        self.subtitle_label = None
        self.tap_card = None
        self.tap_body = None
        self.tap_text_label = None
        self.hint_label = None

        self._build_ui()
        self._bind_clicks()
        self._start_config_refresh()

    def _build_ui(self):
        try:
            logo_path = os.path.join("assets", "logo2.png")
            from PIL import ImageTk

            img = Image.open(logo_path)
            img.thumbnail((350, 100))
            logo_image = ImageTk.PhotoImage(img)

            self.logo_label = ctk.CTkLabel(
                self.container_body,
                image=logo_image,
                text=""
            )
            self.logo_label.image = logo_image
            self.logo_label.pack(pady=(40, 10))

        except Exception as e:
            print("Logo load failed:", e, flush=True)
            self.logo_label = ctk.CTkLabel(
                self.container_body,
                text=config.get("branding", "app_name", default="CONFIDEX"),
                font=theme.heavy(42)
            )
            self.logo_label.pack(pady=(40, 10))

        self.title_label = ctk.CTkLabel(
            self.container_body,
            text=config.get("welcome_page", "title", default="WELCOME"),
            font=theme.heavy(64),
            text_color=theme.TEXT
        )
        self.title_label.pack(pady=(10, 5))

        self.subtitle_label = ctk.CTkLabel(
            self.container_body,
            text=config.get(
                "welcome_page",
                "subtitle",
                default="Anonymous Health Screening"
            ),
            font=theme.font(22, "bold"),
            text_color=theme.MUTED
        )
        self.subtitle_label.pack(pady=(0, 40))

        self.tap_card = RoundedCard(
            self.container_body,
            fg_color=theme.ORANGE,
            border_width=0,
            radius=25,
            pad=10,
            auto_size=True
        )
        self.tap_card.pack(pady=20)

        self.tap_body = card_body(self.tap_card)

        self.tap_text_label = ctk.CTkLabel(
            self.tap_body,
            text=config.get("welcome_page", "tap_text", default="TAP TO PROCEED"),
            font=theme.font(24, "bold"),
            text_color=theme.WHITE
        )
        self.tap_text_label.pack(padx=80, pady=20)

        self.hint_label = ctk.CTkLabel(
            self.container_body,
            text=config.get(
                "welcome_page",
                "hint_text",
                default="Tap anywhere to start your QR login"
            ),
            font=theme.font(16, "normal"),
            text_color=theme.MUTED
        )
        self.hint_label.pack(pady=(20, 40))

    def _bind_clicks(self):
        all_widgets = [
            self,
            self.shell,
            self.shell.body,
            self.main_container,
            self.container_body,
            self.logo_label,
            self.title_label,
            self.subtitle_label,
            self.tap_card,
            self.tap_body,
            self.tap_text_label,
            self.hint_label,
        ]

        for widget in all_widgets:
            if widget is None:
                continue

            if hasattr(widget, "canvas"):
                widget.canvas.bind("<Button-1>", self.go_to_login)

            widget.bind("<Button-1>", self.go_to_login)

    def _refresh_from_config(self):
        try:
            self.title_label.configure(
                text=config.get("welcome_page", "title", default="WELCOME")
            )

            self.subtitle_label.configure(
                text=config.get(
                    "welcome_page",
                    "subtitle",
                    default="Anonymous Health Screening"
                )
            )

            self.tap_text_label.configure(
                text=config.get("welcome_page", "tap_text", default="TAP TO PROCEED")
            )

            self.hint_label.configure(
                text=config.get(
                    "welcome_page",
                    "hint_text",
                    default="Tap anywhere to start your QR login"
                )
            )

            # If logo failed and fallback text is shown, keep app name live too
            try:
                if not getattr(self.logo_label, "image", None):
                    self.logo_label.configure(
                        text=config.get("branding", "app_name", default="CONFIDEX")
                    )
            except Exception:
                pass

        except Exception as e:
            print(f"[WELCOME] Config refresh failed: {e}", flush=True)

    def _start_config_refresh(self):
        self._refresh_from_config()
        self.after(1000, self._start_config_refresh)

    def go_to_login(self, event=None):
        self.controller.show_frame("QRLoginPage")