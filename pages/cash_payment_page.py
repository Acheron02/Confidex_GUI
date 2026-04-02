import time
import threading
from frontend import tk_compat as ctk
from frontend import theme
from frontend.widgets import AppShell, RoundedCard, PillButton, card_body
from backend.util import api_client

GPIOZERO_AVAILABLE = True

try:
    from gpiozero import Button, LED
except Exception as e:
    GPIOZERO_AVAILABLE = False
    print(f'[CASH] gpiozero import failed: {e}', flush=True)

    class Button:
        def __init__(self, *a, **k):
            self.when_pressed = None

    class LED:
        def __init__(self, *a, **k):
            pass

        def on(self):
            pass

        def off(self):
            pass


from backend.util.dispenser_serial import (
    send_bill_on_command,
    send_bill_off_command,
)


class CashPaymentPage(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color=theme.CREAM)
        self.controller = controller
        self.selected_product = None
        self.user_data = {}
        self.discount = 0
        self.total_cash_inserted = 0
        self.transaction_in_progress = False
        self.loading_visible = False
        self.planned_cash_bill = None

        self.pulse_count = 0
        self.last_pulse_time = 0.0
        self.last_processed_time = 0.0
        self.tolerance = 0.30
        self.pulse_lock = threading.Lock()

        self._status_anim_job = None
        self._status_anim_running = False
        self._status_base_text = 'Insert bills to pay'
        self._status_dot_count = 0

        self.bill_acceptor_enabled = False
        self._bill_command_lock = threading.Lock()

        print(f'[CASH] Initializing CashPaymentPage | GPIOZERO_AVAILABLE={GPIOZERO_AVAILABLE}', flush=True)

        try:
            if GPIOZERO_AVAILABLE:
                self.bill_acceptor = Button(17, pull_up=True, bounce_time=0.001)
                self.reject_pin = LED(27)
                print('[CASH] GPIO initialized: bill_acceptor=GPIO17, reject_pin=GPIO27', flush=True)
            else:
                self.bill_acceptor = Button(17)
                self.reject_pin = LED(27)
        except Exception as e:
            print(f'[CASH] GPIO setup failed: {e}', flush=True)
            self.bill_acceptor = Button(17)
            self.reject_pin = LED(27)

        self.bill_acceptor.when_pressed = self._pulse_callback
        threading.Thread(target=self._pulse_watcher, daemon=True).start()

        self.shell = AppShell(self, title_right='Cash Payment')
        self.shell.pack(fill='both', expand=True)

        top_bar = ctk.CTkFrame(self.shell.body, fg_color='transparent')
        top_bar.pack(fill='x', padx=28, pady=(16, 8))
        top_bar.grid_columnconfigure(0, weight=0)
        top_bar.grid_columnconfigure(1, weight=1)
        top_bar.grid_columnconfigure(2, weight=0)

        self.back_btn = PillButton(
            top_bar,
            text='Back',
            width=130,
            height=58,
            command=self.go_back,
            font=theme.font(18, 'bold')
        )
        self.back_btn.grid(row=0, column=0, sticky='w')

        self.page_title = ctk.CTkLabel(
            top_bar,
            text='CASH PAYMENT',
            font=theme.heavy(32),
            text_color=theme.BLACK
        )
        self.page_title.grid(row=0, column=1)

        content_wrap = ctk.CTkFrame(self.shell.body, fg_color='transparent')
        content_wrap.pack(expand=True, fill='both')

        content_wrap.grid_columnconfigure(0, weight=1)
        content_wrap.grid_rowconfigure(0, weight=1)
        content_wrap.grid_rowconfigure(1, weight=0)
        content_wrap.grid_rowconfigure(2, weight=1)

        self.card = RoundedCard(content_wrap, auto_size=True, pad=18)
        self.card.grid(row=1, column=0)

        body = card_body(self.card)
        body.grid_columnconfigure(0, weight=1)

        self.title_label = ctk.CTkLabel(
            body,
            text='CASH PAYMENT',
            font=theme.heavy(30),
            text_color=theme.BLACK,
            fg_color=theme.WHITE
        )
        self.title_label.grid(row=0, column=0, padx=20, pady=(10, 14))

        self.order_text = ctk.CTkLabel(
            body,
            text='No item selected',
            font=theme.font(24, 'bold'),
            text_color=theme.MUTED,
            justify='center',
            anchor='center',
            wraplength=700,
            fg_color=theme.WHITE
        )
        self.order_text.grid(row=1, column=0, sticky='ew', padx=20, pady=(4, 10))

        self.status_text = ctk.CTkLabel(
            body,
            text='Insert bills to pay',
            font=theme.font(22, 'bold'),
            text_color=theme.INFO,
            justify='center',
            anchor='center',
            wraplength=700,
            fg_color=theme.WHITE
        )
        self.status_text.grid(row=2, column=0, sticky='ew', padx=20, pady=(4, 10))

        self.progress = ctk.CTkLabel(
            body,
            text='Accepted denominations: 50, 100, 200, 500, 1000',
            font=theme.font(18, 'bold'),
            text_color=theme.MUTED,
            justify='center',
            anchor='center',
            wraplength=700,
            fg_color=theme.WHITE
        )
        self.progress.grid(row=3, column=0, sticky='ew', padx=20, pady=(4, 8))

        self.helper_text = ctk.CTkLabel(
            body,
            text='Insert bills one at a time and wait for the amount to update.',
            font=theme.font(16, 'bold'),
            text_color=theme.MUTED,
            justify='center',
            anchor='center',
            wraplength=700,
            fg_color=theme.WHITE
        )
        self.helper_text.grid(row=4, column=0, sticky='ew', padx=20, pady=(2, 8))

        self.loading_overlay = ctk.CTkFrame(self, fg_color='#E6E1C9')
        self.loading_overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.loading_overlay.lower()

        self.loading_label = ctk.CTkLabel(
            self.loading_overlay,
            text='Processing payment...',
            font=theme.heavy(30),
            text_color=theme.BLACK
        )
        self.loading_label.place(relx=0.5, rely=0.46, anchor='center')

        self.loading_dots = ctk.CTkLabel(
            self.loading_overlay,
            text='',
            font=theme.heavy(28),
            text_color=theme.BLACK
        )
        self.loading_dots.place(relx=0.5, rely=0.55, anchor='center')

        self._dot_count = 0
        self._animate_dots_running = False

    # =========================
    # BILL ACCEPTOR SERIAL CONTROL
    # =========================
    def _enable_bill_acceptor_thread(self):
        with self._bill_command_lock:
            try:
                result = send_bill_on_command()
                print(f'[CASH] BILL_ON result: {result}', flush=True)
                if result.get('success'):
                    self.bill_acceptor_enabled = True
                else:
                    print(f"[CASH] Failed to enable bill acceptor: {result.get('message')}", flush=True)
            except Exception as e:
                print(f'[CASH] BILL_ON exception: {e}', flush=True)

    def _disable_bill_acceptor_thread(self):
        with self._bill_command_lock:
            try:
                result = send_bill_off_command()
                print(f'[CASH] BILL_OFF result: {result}', flush=True)
                if result.get('success'):
                    self.bill_acceptor_enabled = False
                else:
                    print(f"[CASH] Failed to disable bill acceptor: {result.get('message')}", flush=True)
            except Exception as e:
                print(f'[CASH] BILL_OFF exception: {e}', flush=True)

    def enable_bill_acceptor(self, async_mode=True):
        if self.bill_acceptor_enabled:
            return

        if async_mode:
            threading.Thread(target=self._enable_bill_acceptor_thread, daemon=True).start()
        else:
            self._enable_bill_acceptor_thread()


    def disable_bill_acceptor(self, async_mode=True):
        if async_mode:
            threading.Thread(target=self._disable_bill_acceptor_thread, daemon=True).start()
        else:
            self._disable_bill_acceptor_thread()

    def go_back(self):
        print('[CASH] go_back called', flush=True)

        if self.transaction_in_progress or self.loading_visible:
            print('[CASH] go_back blocked', flush=True)
            return

        self.disable_bill_acceptor()
        self.stop_status_animation()
        self.hide_loading()

        self.controller.show_loading_then(
            'Returning to payment options',
            'PaymentMethodPage',
            delay=1000,
            user_data=self.user_data,
            selected_product=self.selected_product,
            discount=self.discount
        )

    def update_data(self, user_data=None, selected_product=None, discount=0, planned_cash_bill=None, **kwargs):
        self.user_data = (user_data or {}).copy()
        self.selected_product = (selected_product or {}).copy() if selected_product else None
        self.discount = discount or 0
        self.planned_cash_bill = planned_cash_bill
        self.total_cash_inserted = 0
        self.transaction_in_progress = False

        with self.pulse_lock:
            self.pulse_count = 0
            self.last_pulse_time = 0.0

        if not self.user_data or not self.selected_product:
            print('[CASH] missing user_data or selected_product', flush=True)
            self.order_text.configure(
                text='No product selected or user data missing',
                text_color=theme.ERROR
            )
            self._set_status(
                text='Please go back and choose a product first.',
                color=theme.ERROR,
                visible=True
            )
            self._set_progress(visible=False)
            self._set_helper(visible=False)
            self.disable_bill_acceptor()
            return

        total = self.selected_product.get('price', 0) * (1 - self.discount / 100)

        planned_line = (
            f"Planned bill: ₱{float(self.planned_cash_bill):.2f}\n"
            if self.planned_cash_bill is not None else ""
        )

        self.order_text.configure(
            text=(
                f"User: {self.user_data.get('username', 'User')}\n"
                f"Product: {self.selected_product.get('name', 'Unknown')}\n"
                f"Type: {self.selected_product.get('type', 'Unknown')}\n"
                f"Total: ₱{total:.2f}\n"
                f"{planned_line}"
            ).strip(),
            text_color=theme.BLACK
        )

        self.start_status_animation('Insert bills to pay', theme.INFO)
        self._set_progress(
            text='Accepted denominations: 50, 100, 200, 500, 1000',
            color=theme.MUTED,
            visible=True
        )
        self._set_helper(
            text='Insert the selected bill first, then wait for the amount to update.',
            color=theme.MUTED,
            visible=True
        )
        self.hide_loading()

        self.enable_bill_acceptor()

    def _set_status(self, text='', color=None, visible=True):
        self.stop_status_animation()

        if not visible or not text:
            self.status_text.grid_remove()
            return

        print(f'[CASH] STATUS: {text}', flush=True)
        self.status_text.configure(
            text=text,
            text_color=color or theme.INFO
        )
        self.status_text.grid()
        self.status_text.update_idletasks()

    def _set_progress(self, text='', color=None, visible=True):
        if not visible or not text:
            self.progress.grid_remove()
            return

        self.progress.configure(
            text=text,
            text_color=color or theme.MUTED
        )
        self.progress.grid()
        self.progress.update_idletasks()

    def _set_helper(self, text='', color=None, visible=True):
        if not visible or not text:
            self.helper_text.grid_remove()
            return

        self.helper_text.configure(
            text=text,
            text_color=color or theme.MUTED
        )
        self.helper_text.grid()
        self.helper_text.update_idletasks()

    def show_loading(self):
        if self.loading_visible:
            return
        print('[CASH] show_loading', flush=True)
        self.loading_visible = True
        self.loading_overlay.lift()
        self._animate_dots_running = True
        self._animate_dots()

    def hide_loading(self):
        print('[CASH] hide_loading', flush=True)
        self.loading_visible = False
        self.loading_overlay.lower()
        self._animate_dots_running = False
        self.loading_dots.configure(text='')

    def _animate_dots(self):
        if not self._animate_dots_running:
            return
        self._dot_count = (self._dot_count + 1) % 4
        self.loading_dots.configure(text='.' * self._dot_count)
        self.after(450, self._animate_dots)

    def reject_bill(self, duration=0.5):
        print(f'[CASH] reject_bill called duration={duration}', flush=True)
        try:
            self.reject_pin.on()
            time.sleep(duration)
            self.reject_pin.off()
            print('[CASH] reject_bill finished', flush=True)
        except Exception as e:
            print(f'[CASH] reject_bill error: {e}', flush=True)

    def _pulse_callback(self):
        now = time.time()
        with self.pulse_lock:
            self.pulse_count += 1
            self.last_pulse_time = now
            current_count = self.pulse_count

        print(f'[CASH] pulse detected | count={current_count} | t={now}', flush=True)

    def _pulse_watcher(self):
        print('[CASH] pulse watcher started', flush=True)

        while True:
            try:
                with self.pulse_lock:
                    count = self.pulse_count
                    last_pulse = self.last_pulse_time

                if count > 0 and (time.time() - last_pulse) > self.tolerance:
                    with self.pulse_lock:
                        stable_count = self.pulse_count
                        self.pulse_count = 0
                        self.last_processed_time = time.time()

                    print(f'[CASH] pulse batch complete | stable_count={stable_count}', flush=True)

                    bill_value = self.map_pulses_to_bill(stable_count)
                    print(f'[CASH] mapped bill_value={bill_value}', flush=True)

                    if bill_value:
                        self.controller.after(0, lambda v=bill_value: self.process_bill(v))
                    else:
                        self.controller.after(
                            0,
                            lambda c=stable_count: self._set_status(
                                text=f'Unknown bill ({c} pulses). Rejecting...',
                                color=theme.ERROR,
                                visible=True
                            )
                        )
                        threading.Thread(target=self.reject_bill, daemon=True).start()
                        self.controller.after(
                            2500,
                            lambda: self.start_status_animation('Insert bills to pay', theme.INFO)
                        )

                time.sleep(0.01)

            except Exception as e:
                print(f'[CASH] pulse watcher error: {e}', flush=True)
                time.sleep(0.2)

    def map_pulses_to_bill(self, count):
        value = {
            5: 50,
            10: 100,
            20: 200,
            50: 500,
            100: 1000
        }.get(count)

        print(f'[CASH] map_pulses_to_bill | count={count} | value={value}', flush=True)
        return value

    def process_bill(self, bill_value):
        print(f'[CASH] process_bill called | bill_value={bill_value}', flush=True)
        self.show_loading()

        if not self.selected_product:
            print('[CASH] no selected product, rejecting bill', flush=True)
            self._set_status(
                text='No product selected - returning bill',
                color=theme.ERROR,
                visible=True
            )
            threading.Thread(target=self.reject_bill, daemon=True).start()
            self.after(1000, self.hide_loading)
            return

        self.total_cash_inserted += bill_value
        total_price = self.selected_product.get('price', 0) * (1 - self.discount / 100)
        remaining = total_price - self.total_cash_inserted

        print(
            f'[CASH] total_cash_inserted={self.total_cash_inserted} | '
            f'total_price={total_price} | remaining={remaining}',
            flush=True
        )

        if remaining > 0:
            self._set_status(
                text=f'Total inserted: ₱{self.total_cash_inserted:.2f}. Insert ₱{remaining:.2f} more',
                color=theme.INFO,
                visible=True
            )
            self._set_helper(
                text='Insert bills one at a time and wait for the amount to update.',
                color=theme.MUTED,
                visible=True
            )
            self.after(700, self.hide_loading)
        else:
            if not self.transaction_in_progress:
                self.transaction_in_progress = True
                print('[CASH] payment complete, proceeding to confirm_payment', flush=True)

                self._set_status(
                    text=f'Total inserted: ₱{self.total_cash_inserted:.2f}. Payment complete!',
                    color=theme.SUCCESS,
                    visible=True
                )
                self._set_helper(
                    text='Saving your transaction...',
                    color=theme.MUTED,
                    visible=True
                )
                self.after(1200, self.confirm_payment)

            self.after(700, self.hide_loading)

    def confirm_payment(self):
        print('[CASH] confirm_payment called', flush=True)

        if not self.selected_product or not self.user_data:
            print('[CASH] confirm_payment aborted: missing data', flush=True)
            self.transaction_in_progress = False
            self._set_status(
                text='No product selected or user data missing',
                color=theme.ERROR,
                visible=True
            )
            self.hide_loading()
            self.disable_bill_acceptor()
            return

        cash = self.total_cash_inserted
        total = self.selected_product.get('price', 0) * (1 - self.discount / 100)
        change = cash - total

        transaction_data = {
            'user_id': self.user_data.get('_id') or self.user_data.get('userID'),
            'status': 'completed',
            'items': [{
                'name': self.selected_product.get('name', 'Unknown'),
                'productID': self.selected_product.get('productID') or self.selected_product.get('product_id') or '',
                'type': self.selected_product.get('type', ''),
                'price': float(self.selected_product.get('price', 0) or 0),
                'discount': float(self.discount or 0),
                'finalPrice': float(total),
                'result': 'Pending',
            }],
            'purchasedDate': None,
        }

        threading.Thread(
            target=self.post_transaction_and_continue,
            args=(transaction_data, cash, change, total),
            daemon=True
        ).start()

    def start_status_animation(self, base_text='Insert bills to pay', color=None):
        self.stop_status_animation()
        self._status_anim_running = True
        self._status_base_text = base_text
        self._status_dot_count = 0

        self.status_text.configure(
            text=base_text,
            text_color=color or theme.INFO
        )
        self.status_text.grid()

        self._animate_status_text()

    def stop_status_animation(self):
        self._status_anim_running = False
        if self._status_anim_job is not None:
            try:
                self.after_cancel(self._status_anim_job)
            except Exception:
                pass
            self._status_anim_job = None

    def _animate_status_text(self):
        if not self._status_anim_running:
            return

        self._status_dot_count = (self._status_dot_count + 1) % 4
        dots = '.' * self._status_dot_count

        self.status_text.configure(
            text=f'{self._status_base_text}{dots}',
            text_color=theme.INFO
        )

        self._status_anim_job = self.after(450, self._animate_status_text)

    def post_transaction_and_continue(self, transaction_data_local, cash, change, total):
        print('[CASH] post_transaction_and_continue started', flush=True)

        try:
            response = api_client.post_transaction(transaction_data_local)
            print(f'[CASH] post_transaction status_code={response.status_code} ok={response.ok}', flush=True)

            if not response.ok:
                self.controller.after(0, lambda: self._handle_transaction_failure(
                    f'Transaction failed ({response.status_code}).'
                ))
                return

            transaction_id = None
            try:
                data = response.json()
                transaction_obj = data.get('transaction') or {}
                transaction_id = (
                    transaction_obj.get('_id')
                    or data.get('_id')
                    or data.get('transaction_id')
                    or data.get('id')
                )
            except Exception as e:
                print(f'[CASH] failed to parse response json: {e}', flush=True)

            self.controller.after(0, lambda: self._handle_transaction_success(
                cash=cash,
                change=change,
                total=total,
                transaction_id=transaction_id
            ))

        except Exception as e:
            print(f'[CASH] post_transaction exception: {e}', flush=True)
            self.controller.after(0, lambda: self._handle_transaction_failure(
                f'Network/API error: {e}'
            ))

    def _handle_transaction_success(self, cash, change, total, transaction_id=None):
        print(f'[CASH] transaction success | transaction_id={transaction_id} | change={change}', flush=True)

        self.disable_bill_acceptor(async_mode=False)
        self.hide_loading()

        if change > 0:
            self._set_status(
                text='Transaction saved successfully. Preparing your change...',
                color=theme.SUCCESS,
                visible=True
            )
            self._set_helper(
                text='Please wait while the machine dispenses your coins.',
                color=theme.MUTED,
                visible=True
            )

            self.controller.show_loading_then(
                'Preparing change',
                'ChangeDispensingPage',
                delay=800,
                user_data=self.user_data,
                product=self.selected_product,
                discount=self.discount,
                total_paid=cash,
                change=change,
                total=total,
                payment_method='cash',
                online_payment=False,
                transaction_id=transaction_id
            )
        else:
            self._set_status(
                text='Transaction saved successfully. Generating receipt...',
                color=theme.SUCCESS,
                visible=True
            )
            self._set_helper(
                text='No change to dispense. Proceeding to receipt.',
                color=theme.MUTED,
                visible=True
            )

            self.controller.show_loading_then(
                'Generating receipt',
                'ReceiptPage',
                delay=800,
                user_data=self.user_data,
                product=self.selected_product,
                discount=self.discount,
                total_paid=cash,
                change=change,
                total=total,
                payment_method='cash',
                online_payment=False,
                transaction_id=transaction_id
            )

        self.after(7000, self.reset_fields)

    def _handle_transaction_failure(self, error_message):
        print(f'[CASH] transaction failure | error={error_message}', flush=True)
        self.transaction_in_progress = False
        self.hide_loading()

        self.disable_bill_acceptor()

        self._set_status(
            text=error_message,
            color=theme.ERROR,
            visible=True
        )
        self._set_helper(
            text='Transaction was not saved. Please contact assistance or try again.',
            color=theme.ERROR,
            visible=True
        )

        threading.Thread(target=self.reject_bill, daemon=True).start()

    def reset_fields(self, **kwargs):
        print('[CASH] reset_fields called', flush=True)

        self.selected_product = None
        self.user_data = {}
        self.discount = 0
        self.total_cash_inserted = 0
        self.transaction_in_progress = False
        self.planned_cash_bill = None

        with self.pulse_lock:
            self.pulse_count = 0
            self.last_pulse_time = 0.0

        self.order_text.configure(
            text='No item selected',
            text_color=theme.MUTED
        )
        self.start_status_animation('Insert bills to pay', theme.INFO)
        self._set_progress(
            text='Accepted denominations: 50, 100, 200, 500, 1000',
            color=theme.MUTED,
            visible=True
        )
        self._set_helper(
            text='Insert bills one at a time and wait for the amount to update.',
            color=theme.MUTED,
            visible=True
        )
        self.hide_loading()

    def destroy(self):
        self.stop_status_animation()
        super().destroy()