import os
import threading
from frontend import tk_compat as ctk
import cv2
from PIL import Image, ImageTk
from ultralytics import YOLO
from frontend import theme
from frontend.widgets import AppShell, RoundedCard, PillButton, card_body
from backend.util import api_client
from backend.util.capture_manager import create_capture_session, save_capture_set


class KitInsertionPage(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color=theme.CREAM)
        self.controller = controller
        self.user_data = {}
        self.selected_product = None
        model_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'backend', 'ipModel', 'latesttrain.pt')
        self.model = YOLO(model_path)

        self.shell = AppShell(self, title_right='Reverse Vending Machine')
        self.shell.pack(fill='both', expand=True)

        ctk.CTkLabel(self.shell.body, text='REVERSE VENDING MACHINE', font=theme.heavy(30), text_color=theme.BLACK).pack(pady=(18, 10))
        self.card = RoundedCard(self.shell.body)
        self.card.pack(fill='both', expand=True, padx=24, pady=16)
        body = card_body(self.card)

        self.camera_label = ctk.CTkLabel(body, text='', fg_color=theme.WHITE)
        self.camera_label.pack(pady=(16, 8), fill='both', expand=True)
        self.confirmation_label = ctk.CTkLabel(body, text=' ', font=theme.font(20, 'bold'), text_color=theme.SUCCESS, fg_color=theme.WHITE)
        self.confirmation_label.pack(pady=(0, 8))
        self.result_label = ctk.CTkLabel(body, text='Insert your test kit', font=theme.font(28, 'bold'), text_color=theme.BLACK, fg_color=theme.WHITE)
        self.result_label.pack(pady=(0, 12))
        self.insert_btn = PillButton(body, text='Confirm Insertion', command=lambda: self.capture_image(run_yolo=True), width=280, font=theme.font(18, 'bold'))
        self.insert_btn.pack(pady=(0, 20))

        self.cap = None
        self.running = False
        self._after_id = None

    def start_camera(self):
        if self.cap is None:
            self.cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        if not self.cap.isOpened():
            self.result_label.configure(text='Camera not available')
            return
        self.running = True
        self.update_frame()

    def stop_camera(self):
        self.running = False
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None
        if self.cap:
            self.cap.release()
            self.cap = None

    def update_frame(self):
        if self.running and self.cap:
            ret, frame = self.cap.read()
            if ret:
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame_rgb).resize((960, 540))
                imgtk = ImageTk.PhotoImage(image=img)
                self.camera_label.configure(image=imgtk)
                self._camera_imgtk = imgtk
            self._after_id = self.after(30, self.update_frame)

    def capture_image(self, run_yolo=True):
        if not self.cap or not self.cap.isOpened():
            self.result_label.configure(text='Camera not available')
            return
        ret, frame = self.cap.read()
        if not ret:
            self.result_label.configure(text='Failed to capture image')
            return
        self.insert_btn.configure(state='disabled')
        self.running = False
        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb).resize((960, 540))
        imgtk = ImageTk.PhotoImage(image=img)
        self.camera_label.configure(image=imgtk)
        self._camera_imgtk = imgtk
        self.confirmation_label.configure(text='Photo captured successfully!')
        self._captured_frame = frame
        if run_yolo:
            self.after(600, self.generate_result)
        else:
            self.result_label.configure(text='Bill captured')
            self.insert_btn.configure(state='normal')

    def generate_result(self):
        raw_frame = self._captured_frame.copy()
        frame_resized = cv2.resize(raw_frame, (1280, 720))
        annotated_frame = frame_resized.copy()
        result_text = 'No object detected'
        try:
            results = self.model.predict(source=frame_resized, conf=0.3, verbose=False)
            if results and len(results[0].boxes) > 0:
                class_indices = results[0].boxes.cls.cpu().numpy().astype(int)
                class_names = [results[0].names[i] for i in class_indices]
                result_text = ', '.join(class_names)
                annotated_frame = results[0].plot()
        except Exception as e:
            print('Analysis failed:', e)
            result_text = 'Invalid'

        display_rgb = cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(display_rgb).resize((960, 540))
        imgtk = ImageTk.PhotoImage(image=img)
        self.camera_label.configure(image=imgtk)
        self._camera_imgtk = imgtk
        self.result_label.configure(text=f'Result: {result_text}')

        user_id = self.user_data.get('user_id') or self.user_data.get('userID') or 'unknown'
        session_dir = create_capture_session(user_id)
        metadata = {
            'user_id': user_id,
            'username': self.user_data.get('username', 'user'),
            'product_id': (self.selected_product.get('productID') or self.selected_product.get('product_id')) if self.selected_product else None,
            'result': result_text,
        }
        raw_path, annotated_path, _ = save_capture_set(session_dir, raw_frame, annotated_frame, metadata)

        threading.Thread(target=self.send_to_backend, args=(annotated_path, result_text), daemon=True).start()
        self.after(5000, self.logout_user)

    def send_to_backend(self, annotated_filename, result_text):
        try:
            user_id = self.user_data.get('user_id') or self.user_data.get('userID')
            product_id = (self.selected_product.get('productID') or self.selected_product.get('product_id')) if self.selected_product else None
            if not user_id or not product_id:
                print('Skipping backend upload: missing user_id or product_id')
                return
            payload = {
                'user_id': user_id,
                'productID': product_id,
                'result': result_text,
                'result_image': f'/uploads/analyzed_kits/{os.path.basename(annotated_filename)}',
            }
            try:
                api_client.post_result(payload)
            except Exception as e:
                print('Result JSON upload failed:', e)
            try:
                api_client.upload_result_image(user_id, product_id, annotated_filename)
            except Exception as e:
                print('Image upload failed:', e)
        except Exception as e:
            print('send_to_backend encountered an error:', e)

    def update_data(self, user_data=None, selected_product=None, **kwargs):
        self.user_data = user_data or {}
        self.selected_product = selected_product
        self.shell.set_header_right(f"Welcome, {self.user_data.get('username', 'User')}!")
        self.result_label.configure(text='Insert your test kit')
        self.confirmation_label.configure(text=' ')
        self.insert_btn.configure(state='normal')
        self.start_camera()

    def logout_user(self):
        self.stop_camera()
        self.user_data = {}
        self.selected_product = None
        self.result_label.configure(text='Insert your test kit')
        self.confirmation_label.configure(text=' ')
        self.insert_btn.configure(state='normal')
        for page_name in ['QRLoginPage', 'PurchasePage', 'CashPaymentPage', 'HowToUsePage']:
            page = self.controller.frames.get(page_name)
            if page:
                if page_name == 'HowToUsePage' and hasattr(page, 'reset_video'):
                    page.reset_video()
                if hasattr(page, 'reset_fields'):
                    page.reset_fields()
        self.controller.show_loading_then(
            'Logging Out...',
            'WelcomePage',
            delay=1000
        )
