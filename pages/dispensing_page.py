import threading
from frontend import tk_compat as ctk
from frontend import theme
from frontend.widgets import AppShell, RoundedCard, card_body

from backend.util.dispenser_serial import send_dispense_command


class DispensingPage(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color=theme.CREAM)
        self.controller = controller

        self.user_data = {}
        self.product = None
        self.discount = 0
        self.total_paid = 0
        self.change = 0
        self.total = 0

        self.processing = False

        self._anim_job = None
        self._anim_running = False
        self._dot_count = 0
        self._base_text = "Please wait, your item is being dispensed"

        self.shell = AppShell(self, title_right="Dispensing Item")
        self.shell.pack(fill="both", expand=True)

        content_wrap = ctk.CTkFrame(self.shell.body, fg_color="transparent")
        content_wrap.pack(expand=True, fill="both", padx=24, pady=20)
        content_wrap.grid_columnconfigure(0, weight=1)
        content_wrap.grid_rowconfigure(0, weight=1)

        self.card = RoundedCard(content_wrap, auto_size=True, pad=18)
        self.card.grid(row=0, column=0)

        body = card_body(self.card)
        body.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            body,
            text="DISPENSING ITEM",
            font=theme.heavy(30),
            text_color=theme.BLACK,
            fg_color=theme.WHITE
        )
        self.title_label.grid(row=0, column=0, padx=20, pady=(16, 12))

        self.message_label = ctk.CTkLabel(
            body,
            text=self._base_text,
            font=theme.font(22, "bold"),
            text_color=theme.INFO,
            fg_color=theme.WHITE,
            wraplength=700,
            justify="center"
        )
        self.message_label.grid(row=1, column=0, padx=20, pady=(8, 14), sticky="ew")

        self.details_label = ctk.CTkLabel(
            body,
            text="Preparing dispense command...",
            font=theme.font(18, "bold"),
            text_color=theme.MUTED,
            fg_color=theme.WHITE,
            wraplength=700,
            justify="center"
        )
        self.details_label.grid(row=2, column=0, padx=20, pady=(4, 12), sticky="ew")

        self.status_label = ctk.CTkLabel(
            body,
            text="",
            font=theme.font(16, "bold"),
            text_color=theme.MUTED,
            fg_color=theme.WHITE,
            wraplength=700,
            justify="center"
        )
        self.status_label.grid(row=3, column=0, padx=20, pady=(0, 14), sticky="ew")

    def update_data(
        self,
        user_data=None,
        product=None,
        discount=0,
        total_paid=0,
        change=0,
        total=0,
        **kwargs
    ):
        self.user_data = user_data or {}
        self.product = product or {}
        self.discount = discount or 0
        self.total_paid = total_paid or 0
        self.change = change or 0
        self.total = total or 0

        self.processing = False

        username = self.user_data.get("username", "User")
        product_name = self.product.get("name") or self.product.get("type") or "Unknown Item"

        self.shell.set_header_right(f"Welcome, {username}!")
        self.message_label.configure(text=self._base_text, text_color=theme.INFO)
        self.details_label.configure(
            text=(
                f"User: {username}\n"
                f"Item: {product_name}\n"
                f"Please do not leave while dispensing is in progress."
            )
        )
        self.status_label.configure(text="", text_color=theme.MUTED)

        self.start_animation()
        self.after(200, self.start_dispensing)

    def start_dispensing(self):
        if self.processing:
            return

        self.processing = True
        threading.Thread(target=self._dispense_item_thread, daemon=True).start()

    def _dispense_item_thread(self):
        try:
            product_id = (
                self.product.get("productID")
                or self.product.get("product_id")
                or self.product.get("id")
                or ""
            )

            product_name = self.product.get("name") or self.product.get("type") or "Unknown Item"

            result = send_dispense_command(
                product_id=product_id,
                product_name=product_name
            )

            self.after(0, lambda: self._on_dispense_done(result))

        except Exception as e:
            self.after(0, lambda: self._on_dispense_error(str(e)))

    def _on_dispense_done(self, result):
        self.processing = False
        self.stop_animation()

        success = bool(result.get("success"))
        message = result.get("message", "")

        if success:
            self.message_label.configure(
                text="Item dispensed successfully",
                text_color=theme.SUCCESS
            )
            self.status_label.configure(
                text=message or "Dispensing completed successfully.",
                text_color=theme.SUCCESS
            )
            print(f"[DISPENSE] success: {result}", flush=True)

            self.after(
                1500,
                lambda: self.controller.show_loading_then(
                    "Loading instructions",
                    "HowToUsePage",
                    delay=800,
                    user_data=self.user_data,
                    selected_product=self.product
                )
            )
        else:
            self.message_label.configure(
                text="Dispensing failed",
                text_color=theme.ERROR
            )
            self.status_label.configure(
                text=message or "Failed to dispense item.",
                text_color=theme.ERROR
            )
            print(f"[DISPENSE] failed: {result}", flush=True)

    def _on_dispense_error(self, error_message):
        self.processing = False
        self.stop_animation()

        self.message_label.configure(
            text="Dispensing failed",
            text_color=theme.ERROR
        )
        self.status_label.configure(
            text=f"Error: {error_message}",
            text_color=theme.ERROR
        )
        print(f"[DISPENSE] error: {error_message}", flush=True)

    def start_animation(self):
        self.stop_animation()
        self._anim_running = True
        self._dot_count = 0
        self._animate_text()

    def stop_animation(self):
        self._anim_running = False
        if self._anim_job is not None:
            try:
                self.after_cancel(self._anim_job)
            except Exception:
                pass
            self._anim_job = None

    def _animate_text(self):
        if not self._anim_running:
            return

        self._dot_count = (self._dot_count + 1) % 4
        dots = "." * self._dot_count

        self.message_label.configure(
            text=f"{self._base_text}{dots}",
            text_color=theme.INFO
        )

        self._anim_job = self.after(450, self._animate_text)

    def destroy(self):
        self.stop_animation()
        super().destroy()