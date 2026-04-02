from frontend import tk_compat as ctk
import threading
from pynput import keyboard
import requests
from frontend import theme
from frontend.widgets import AppShell, RoundedCard, card_body
from backend.util import api_client
from config_manager import config


class QRLoginPage(ctk.CTkFrame):
    def __init__(self, master, controller=None):
        super().__init__(master, fg_color=theme.CREAM)
        self.controller = controller
        self.buffer = ""
        self.disabled = False
        self.processing = False
        self.listener = None

        self._waiting_base_text = config.get(
            "qr_login_page",
            "waiting_base_text",
            default="Waiting for QR scan"
        )
        self._waiting_dots = 0
        self._waiting_anim_job = None
        self._waiting_anim_running = False
        self._config_refresh_job = None

        self.shell = AppShell(self)
        self.shell.pack(fill="both", expand=True)

        content_wrap = ctk.CTkFrame(self.shell.body, fg_color="transparent")
        content_wrap.pack(expand=True, fill="both")

        content_wrap.grid_columnconfigure(0, weight=1)
        content_wrap.grid_rowconfigure(0, weight=1)
        content_wrap.grid_rowconfigure(1, weight=0)
        content_wrap.grid_rowconfigure(2, weight=1)

        self.card = RoundedCard(content_wrap, pad=50, auto_size=True)
        self.card.grid(row=1, column=0)

        body = card_body(self.card)

        self.title_label = ctk.CTkLabel(
            body,
            text=config.get("qr_login_page", "title", default="SCAN QR TO LOGIN"),
            font=theme.font(32, "bold"),
            text_color=theme.BLACK,
            fg_color=theme.WHITE
        )
        self.title_label.pack(padx=20, pady=(25, 10))

        self.instruction_box = ctk.CTkFrame(
            body,
            fg_color="transparent",
            border_color="#CCCCCC",
            border_width=2,
            corner_radius=12,
            width=500,
            height=110
        )
        self.instruction_box.pack(padx=40, pady=15)
        self.instruction_box.pack_propagate(False)

        self.instruction_text = ctk.CTkLabel(
            self.instruction_box,
            text=config.get(
                "qr_login_page",
                "instruction_text",
                default="Sign in or sign up on our website to generate a QR code"
            ),
            font=theme.font(16, "bold"),
            text_color=theme.GRAY,
            wraplength=420,
            justify="center"
        )
        self.instruction_text.place(relx=0.5, rely=0.5, anchor="center")

        self.result_label = ctk.CTkLabel(
            body,
            text=config.get(
                "qr_login_page",
                "waiting_text",
                default="Waiting for QR scan..."
            ),
            font=theme.font(24, "bold"),
            text_color=theme.MUTED,
            wraplength=480,
            justify="center",
            fg_color=theme.WHITE
        )
        self.result_label.pack(padx=20, pady=(10, 5))

        self.status_label = ctk.CTkLabel(
            body,
            text="",
            font=theme.font(18, "bold"),
            text_color=theme.INFO,
            wraplength=480,
            justify="center",
            fg_color="transparent"
        )
        self.status_label.pack(padx=20, pady=(0, 25))

        self.start_waiting_animation()
        self.start_key_listener()
        self._start_config_refresh()

    def _refresh_from_config(self):
        try:
            self._waiting_base_text = config.get(
                "qr_login_page",
                "waiting_base_text",
                default="Waiting for QR scan"
            )

            self.title_label.configure(
                text=config.get(
                    "qr_login_page",
                    "title",
                    default="SCAN QR TO LOGIN"
                )
            )

            self.instruction_text.configure(
                text=config.get(
                    "qr_login_page",
                    "instruction_text",
                    default="Sign in or sign up on our website to generate a QR code"
                )
            )

            if not self.processing and not self.disabled:
                self.result_label.configure(
                    text=config.get(
                        "qr_login_page",
                        "waiting_text",
                        default="Waiting for QR scan..."
                    )
                )
        except Exception as e:
            print(f"[QR LOGIN] Config refresh failed: {e}", flush=True)

    def _start_config_refresh(self):
        self._refresh_from_config()
        self._config_refresh_job = self.after(1000, self._start_config_refresh)

    def start_waiting_animation(self):
        self.stop_waiting_animation()
        self._waiting_anim_running = True
        self._waiting_dots = 0
        self._animate_waiting_text()

    def stop_waiting_animation(self):
        self._waiting_anim_running = False
        if self._waiting_anim_job is not None:
            try:
                self.after_cancel(self._waiting_anim_job)
            except Exception:
                pass
            self._waiting_anim_job = None

    def _animate_waiting_text(self):
        if not self._waiting_anim_running:
            return

        self._waiting_dots = (self._waiting_dots + 1) % 4
        dots = "." * self._waiting_dots
        self.result_label.configure(
            text=f"{self._waiting_base_text}{dots}",
            text_color=theme.MUTED
        )
        self._waiting_anim_job = self.after(450, self._animate_waiting_text)

    def start_key_listener(self):
        if self.listener:
            self.listener.stop()

        def on_press(key):
            if self.disabled or self.processing:
                return

            try:
                if key.char:
                    self.buffer += key.char
            except AttributeError:
                if key == keyboard.Key.enter:
                    scanned = self.buffer.strip()
                    self.buffer = ""

                    if not scanned or self.processing:
                        return

                    self.processing = True
                    self.after(0, self.show_loading)

                    threading.Thread(
                        target=self.process_scan,
                        args=(scanned,),
                        daemon=True
                    ).start()

        self.listener = keyboard.Listener(on_press=on_press)
        self.listener.start()

    def show_loading(self):
        self.stop_waiting_animation()
        self.status_label.configure(
            text=config.get(
                "qr_login_page",
                "validating_text",
                default="Validating QR... Please wait"
            ),
            text_color=theme.ORANGE
        )
        self.result_label.configure(text="")

    def process_scan(self, scanned_code):
        if self.disabled:
            return

        if not scanned_code.startswith("LOGIN-"):
            def invalid_qr():
                self.status_label.configure(
                    text=config.get(
                        "qr_login_page",
                        "invalid_qr_status",
                        default="Not a login QR code"
                    ),
                    text_color=theme.ERROR
                )
                self.result_label.configure(
                    text=config.get(
                        "qr_login_page",
                        "invalid_qr_result",
                        default="Scan a valid login QR code"
                    )
                )
                self.processing = False
                self.start_waiting_animation()

            self.after(0, invalid_qr)
            return

        try:
            response = api_client.verify_login_qr(scanned_code)

            try:
                data = response.json()
            except ValueError:
                data = {"error": f"Non-JSON response ({response.status_code})"}

            if response.ok and data.get("user"):
                user = data["user"]
                user_data = {
                    "username": user.get("username", "User"),
                    "userID": user.get("_id")
                }

                def success():
                    self.status_label.configure(
                        text=config.get(
                            "qr_login_page",
                            "login_success_status",
                            default="Login successful"
                        ),
                        text_color=theme.SUCCESS
                    )
                    self.result_label.configure(
                        text=f"{config.get('qr_login_page', 'login_success_prefix', default='Logged in as:')} {user_data['username']}"
                    )
                    self.disable_page()
                    self.redirect_to_purchase(user_data)

                self.after(0, success)

            else:
                err = data.get("error") or config.get(
                    "qr_login_page",
                    "login_failed_result",
                    default="Login failed"
                )

                def fail():
                    if self.disabled:
                        return
                    self.status_label.configure(
                        text=config.get(
                            "qr_login_page",
                            "login_failed_status",
                            default="Login failed"
                        ),
                        text_color=theme.ERROR
                    )
                    self.result_label.configure(text=err)
                    self.processing = False
                    self.start_waiting_animation()

                self.after(0, fail)

        except requests.RequestException as e:
            error_message = f"{config.get('qr_login_page', 'network_error_prefix', default='Request failed:')} {e}"

            def network_fail():
                if self.disabled:
                    return
                self.status_label.configure(
                    text=config.get(
                        "qr_login_page",
                        "network_error_status",
                        default="Network error"
                    ),
                    text_color=theme.ERROR
                )
                self.result_label.configure(text=error_message)
                self.processing = False
                self.start_waiting_animation()

            self.after(0, network_fail)

    def disable_page(self):
        self.disabled = True
        self.processing = False
        self.stop_waiting_animation()

        if self.listener:
            self.listener.stop()
            self.listener = None

    def redirect_to_purchase(self, user_data):
        if self.controller:
            self.controller.current_user = user_data
            self.controller.show_frame("PurchasePage", user_data=user_data)

    def reset_fields(self, **kwargs):
        self.buffer = ""
        self.disabled = False
        self.processing = False

        if self.listener:
            self.listener.stop()
            self.listener = None

        self.status_label.configure(text="", text_color=theme.INFO)
        self.result_label.configure(
            text=config.get(
                "qr_login_page",
                "waiting_text",
                default="Waiting for QR scan..."
            ),
            text_color=theme.MUTED
        )
        self.start_waiting_animation()
        self.start_key_listener()