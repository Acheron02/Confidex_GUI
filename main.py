import os
import sys
from frontend import tk_compat as ctk

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from pages.welcome_page import WelcomePage
from pages.qr_login_page import QRLoginPage
from pages.purchase_page import PurchasePage
from pages.payment_method_page import PaymentMethodPage
from pages.cash_payment_page import CashPaymentPage
from pages.receipt_page import ReceiptPage
from pages.how_to_use_page import HowToUsePage
from pages.kit_insertion_page import KitInsertionPage


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title('CONFIDEX')
        self.configure(fg_color='#F5F2DE')
        self.frames = {}
        self.current_user = None

        self.bind('<Escape>', lambda e: self.destroy())

        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        self.geometry(f"{screen_w}x{screen_h}+0+0")
        self.minsize(screen_w, screen_h)

        self.update_idletasks()
        self.after(100, self.enable_fullscreen)

        for PageClass in (
            WelcomePage,
            QRLoginPage,
            PurchasePage,
            PaymentMethodPage,
            CashPaymentPage,
            ReceiptPage,
            HowToUsePage,
            KitInsertionPage,
        ):
            page = PageClass(self, self)
            self.frames[PageClass.__name__] = page
            page.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.show_frame('WelcomePage')

    def enable_fullscreen(self):
        try:
            self.attributes('-fullscreen', True)
        except Exception as e:
            print("Fullscreen failed:", e)
            try:
                self.state('zoomed')
            except Exception as e2:
                print("Zoomed mode failed:", e2)

        self.lift()
        self.focus_force()

    def cancel_session_and_return_home(self, message=None):
        self.current_user = None

        for page_name in ("QRLoginPage", "PurchasePage", "PaymentMethodPage", "CashPaymentPage"):
            frame = self.frames.get(page_name)
            if frame and hasattr(frame, "reset_fields"):
                try:
                    frame.reset_fields()
                except Exception as e:
                    print(f"Failed resetting {page_name}: {e}")

        welcome = self.frames.get("WelcomePage")
        if welcome and hasattr(welcome, "set_notice"):
            welcome.set_notice(
                message or "Session cancelled. Please generate a new login QR code from the website."
            )

        self.show_frame("WelcomePage")

    def show_frame(self, page_name, **kwargs):
        frame = self.frames.get(page_name)
        if not frame:
            print(f"Frame '{page_name}' does not exist")
            return

        if hasattr(frame, 'update_data'):
            try:
                frame.update_data(**kwargs)
            except TypeError:
                if kwargs:
                    print(f'update_data mismatch for {page_name}: {kwargs}')

        frame.tkraise()


if __name__ == '__main__':
    ctk.set_appearance_mode('light')
    app = App()
    app.mainloop()