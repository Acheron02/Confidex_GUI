from frontend import tk_compat as ctk
import threading
from pynput import keyboard
import requests
from frontend import theme
from frontend.widgets import AppShell, RoundedCard, card_body
from backend.util import api_client


class QRLoginPage(ctk.CTkFrame):
    def __init__(self, master, controller=None):
        super().__init__(master, fg_color=theme.CREAM)
        self.controller = controller
        self.buffer = ''
        self.disabled = False
        self.listener = None

        self.shell = AppShell(self)
        self.shell.pack(fill='both', expand=True)

        self.card = RoundedCard(self.shell.body, width=420, height=300)
        self.card.place(relx=0.5, rely=0.46, anchor='center')
        body = card_body(self.card)

        self.title_label = ctk.CTkLabel(
            body,
            text='SCAN QR TO LOGIN',
            font=theme.font(28, 'bold'),
            text_color=theme.BLACK,
            fg_color=theme.WHITE
        )
        self.title_label.pack(pady=(48, 18))

        self.result_label = ctk.CTkLabel(
            body,
            text='Waiting for QR scan...',
            font=theme.font(22, 'bold'),
            text_color=theme.MUTED,
            wraplength=320,
            justify='center',
            fg_color=theme.WHITE
        )
        self.result_label.pack(pady=(12, 10), padx=20)

        self.status_label = ctk.CTkLabel(
            self.shell.body,
            text='',
            font=theme.font(20, 'bold'),
            text_color=theme.INFO
        )
        self.status_label.place(relx=0.5, rely=0.77, anchor='center')

        self.start_key_listener()

    def start_key_listener(self):
        if self.listener:
            self.listener.stop()

        def on_press(key):
            if self.disabled:
                return
            try:
                if key.char:
                    self.buffer += key.char
            except AttributeError:
                if key == keyboard.Key.enter:
                    scanned = self.buffer.strip()
                    self.buffer = ''
                    if scanned:
                        self.after(0, self.show_loading)
                        threading.Thread(
                            target=self.process_scan,
                            args=(scanned,),
                            daemon=True
                        ).start()

        self.listener = keyboard.Listener(on_press=on_press)
        self.listener.start()

    def show_loading(self):
        self.status_label.configure(text='Validating QR... Please wait', text_color=theme.ORANGE)
        self.result_label.configure(text='')

    def process_scan(self, scanned_code):
        if self.disabled:
            return

        if not scanned_code.startswith('LOGIN-'):
            self.after(0, lambda: (
                self.status_label.configure(text='Not a login QR code', text_color=theme.ERROR),
                self.result_label.configure(text='Scan a valid login QR code')
            ))
            return

        try:
            response = api_client.verify_login_qr(scanned_code)
            try:
                data = response.json()
            except ValueError:
                data = {'error': f'Non-JSON response ({response.status_code})'}

            if response.ok and data.get('user'):
                user = data['user']
                user_data = {
                    'username': user.get('username', 'User'),
                    'userID': user.get('_id')
                }

                self.after(0, lambda: (
                    self.status_label.configure(text='Login successful', text_color=theme.SUCCESS),
                    self.result_label.configure(text=f"Logged in as: {user_data['username']}")
                ))
                self.after(50, self.disable_page)
                self.after(150, lambda: self.redirect_to_purchase(user_data))
            else:
                err = data.get('error') or 'Login failed'

                if 'already used' in err.lower() or 'expired' in err.lower():
                    err = 'This login QR code is no longer valid. Please generate a new QR code from the website.'

                self.after(0, lambda: (
                    self.status_label.configure(text='Login failed', text_color=theme.ERROR),
                    self.result_label.configure(text=err)
                ))

        except requests.RequestException as e:
            self.after(0, lambda: (
                self.status_label.configure(text='Network error', text_color=theme.ERROR),
                self.result_label.configure(text=f'Request failed: {e}')
            ))

    def disable_page(self):
        self.disabled = True
        if self.listener:
            self.listener.stop()
            self.listener = None

    def redirect_to_purchase(self, user_data):
        if self.controller:
            self.controller.current_user = user_data
            self.controller.show_frame('PurchasePage', user_data=user_data)

    def reset_fields(self, **kwargs):
        self.buffer = ''
        self.disabled = False

        if self.listener:
            self.listener.stop()
            self.listener = None

        self.result_label.configure(text='Waiting for QR scan...', text_color=theme.MUTED)
        self.status_label.configure(text='', text_color=theme.INFO)
        self.start_key_listener()