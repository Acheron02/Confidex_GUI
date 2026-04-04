import os
import sys
import subprocess
import time
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
from frontend.components.loading import LoadingPage
from pages.online_payment_page import OnlinePaymentPage
from pages.dispensing_page import DispensingPage
from pages.cash_bill_check_page import CashBillCheckPage
from pages.change_dispensing_page import ChangeDispensingPage

from backend.util.dispenser_serial import send_bill_off_command
from backend.device_sync import start_background_sync


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


def start_fastapi():
    try:
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "backend.server:app",
                "--host",
                "0.0.0.0",
                "--port",
                "5000",
            ],
            cwd=ROOT_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print(f"[FASTAPI] Started using {sys.executable} -m uvicorn", flush=True)
    except Exception as e:
        print(f"[FASTAPI] Failed to start: {e}", flush=True)


def ensure_bill_acceptor_off():
    try:
        result = send_bill_off_command()
        print(f"[STARTUP] BILL_OFF result: {result}", flush=True)
    except Exception as e:
        print(f"[STARTUP] Failed to force bill acceptor OFF: {e}", flush=True)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("CONFIDEX")
        self.configure(fg_color="#F5F2DE")
        self.frames = {}
        self.current_user = None

        self.bind("<Escape>", lambda e: self.destroy())

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
            CashBillCheckPage,
            CashPaymentPage,
            ChangeDispensingPage,
            OnlinePaymentPage,
            ReceiptPage,
            DispensingPage,
            HowToUsePage,
            KitInsertionPage,
            LoadingPage,
        ):
            page = PageClass(self, self)
            self.frames[PageClass.__name__] = page
            page.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.show_frame("WelcomePage")

    def enable_fullscreen(self):
        try:
            self.attributes("-fullscreen", True)
        except Exception as e:
            print("Fullscreen failed:", e, flush=True)
            try:
                self.state("zoomed")
            except Exception as e2:
                print("Zoomed mode failed:", e2, flush=True)
        self.lift()
        self.focus_force()

    def show_frame(self, page_name, **kwargs):
        frame = self.frames.get(page_name)
        if not frame:
            print(f"Frame '{page_name}' does not exist", flush=True)
            return

        if hasattr(frame, "update_data"):
            try:
                frame.update_data(**kwargs)
            except TypeError:
                if kwargs:
                    print(f"update_data mismatch for {page_name}: {kwargs}", flush=True)

        frame.tkraise()

    def show_loading_then(self, message, next_page, delay=900, **kwargs):
        self.show_frame(
            "LoadingPage",
            message=message,
            next_page=next_page,
            next_kwargs=kwargs,
            delay=delay,
        )


if __name__ == "__main__":
    ctk.set_appearance_mode("light")

    start_fastapi()
    time.sleep(1)

    ensure_bill_acceptor_off()

    start_background_sync()

    app = App()
    app.mainloop()