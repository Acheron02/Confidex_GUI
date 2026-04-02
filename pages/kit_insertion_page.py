import os
import threading
from pathlib import Path

from frontend import tk_compat as ctk
import cv2
from PIL import Image, ImageTk
from ultralytics import YOLO

from frontend import theme
from frontend.widgets import AppShell, RoundedCard, PillButton, card_body
from backend.util import api_client
from backend.util.capture_manager import (
    get_or_create_capture_session,
    get_session_timestamp,
    save_capture_set,
)


class KitInsertionPage(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color=theme.CREAM)
        self.controller = controller
        self.user_data = {}
        self.selected_product = None
        self.transaction_id = None

        model_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "backend",
            "ipModel",
            "latesttrain.pt"
        )
        self.model = YOLO(model_path)

        self.shell = AppShell(self, title_right="Reverse Vending Machine")
        self.shell.pack(fill="both", expand=True)

        ctk.CTkLabel(
            self.shell.body,
            text="REVERSE VENDING MACHINE",
            font=theme.heavy(30),
            text_color=theme.BLACK
        ).pack(pady=(18, 10))

        self.card = RoundedCard(self.shell.body)
        self.card.pack(fill="both", expand=True, padx=24, pady=16)
        body = card_body(self.card)

        self.camera_label = ctk.CTkLabel(body, text="", fg_color=theme.WHITE)
        self.camera_label.pack(pady=(16, 8), fill="both", expand=True)

        self.confirmation_label = ctk.CTkLabel(
            body,
            text=" ",
            font=theme.font(20, "bold"),
            text_color=theme.SUCCESS,
            fg_color=theme.WHITE
        )
        self.confirmation_label.pack(pady=(0, 8))

        self.result_label = ctk.CTkLabel(
            body,
            text="Insert your test kit",
            font=theme.font(28, "bold"),
            text_color=theme.BLACK,
            fg_color=theme.WHITE
        )
        self.result_label.pack(pady=(0, 12))

        self.insert_btn = PillButton(
            body,
            text="Confirm Insertion",
            command=lambda: self.capture_image(run_yolo=True),
            width=280,
            font=theme.font(18, "bold")
        )
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
            self.result_label.configure(text="Camera not available")
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
            self.result_label.configure(text="Camera not available")
            return

        ret, frame = self.cap.read()
        if not ret:
            self.result_label.configure(text="Failed to capture image")
            return

        self.insert_btn.configure(state="disabled")
        self.running = False

        if self._after_id:
            self.after_cancel(self._after_id)
            self._after_id = None

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb).resize((960, 540))
        imgtk = ImageTk.PhotoImage(image=img)
        self.camera_label.configure(image=imgtk)
        self._camera_imgtk = imgtk
        self.confirmation_label.configure(text="Photo captured successfully!")
        self._captured_frame = frame

        if run_yolo:
            self.after(600, self.generate_result)
        else:
            self.result_label.configure(text="Bill captured")
            self.insert_btn.configure(state="normal")

    def generate_result(self):
        raw_frame = self._captured_frame.copy()
        frame_resized = cv2.resize(raw_frame, (1280, 720))
        annotated_frame = frame_resized.copy()
        result_text = "No object detected"

        try:
            results = self.model.predict(source=frame_resized, conf=0.3, verbose=False)
            if results and len(results[0].boxes) > 0:
                class_indices = results[0].boxes.cls.cpu().numpy().astype(int)
                class_names = [results[0].names[i] for i in class_indices]
                result_text = ", ".join(class_names)
                annotated_frame = results[0].plot()
        except Exception as e:
            print("Analysis failed:", e, flush=True)
            result_text = "Invalid"

        display_rgb = cv2.cvtColor(annotated_frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(display_rgb).resize((960, 540))
        imgtk = ImageTk.PhotoImage(image=img)
        self.camera_label.configure(image=imgtk)
        self._camera_imgtk = imgtk
        self.result_label.configure(text=f"Result: {result_text}")

        user_id = self.user_data.get("user_id") or self.user_data.get("userID") or self.user_data.get("_id") or "unknown"
        product_id = (
            self.selected_product.get("productID") or self.selected_product.get("product_id")
        ) if self.selected_product else None

        session_dir = get_or_create_capture_session(user_id)

        metadata = {
            "user_id": user_id,
            "username": self.user_data.get("username", "user"),
            "product_id": product_id,
            "transaction_id": self.transaction_id,
            "result": result_text,
        }

        raw_path, annotated_path, _ = save_capture_set(
            session_dir,
            raw_frame,
            annotated_frame,
            metadata
        )

        print(f"[KIT] session_dir={session_dir}", flush=True)
        print(f"[KIT] raw_path={raw_path}", flush=True)
        print(f"[KIT] annotated_path={annotated_path}", flush=True)
        print(f"[KIT] annotated_exists={Path(annotated_path).exists()}", flush=True)
        print(f"[KIT] transaction_id={self.transaction_id}", flush=True)

        threading.Thread(
            target=self.send_to_backend,
            args=(str(session_dir), result_text),
            daemon=True
        ).start()

        self.after(5000, self.logout_user)

    def send_to_backend(self, session_dir, result_text):
        try:
            user_id = (
                self.user_data.get("user_id")
                or self.user_data.get("userID")
                or self.user_data.get("_id")
            )

            product_id = (
                self.selected_product.get("productID")
                or self.selected_product.get("product_id")
            ) if self.selected_product else None

            transaction_id = self.transaction_id

            if not user_id or not product_id or not transaction_id:
                print(
                    f"[KIT] Skipping backend upload: "
                    f"user_id={user_id}, product_id={product_id}, transaction_id={transaction_id}",
                    flush=True,
                )
                return

            session_dir = Path(session_dir)
            timestamp = get_session_timestamp(session_dir)

            payload = {
                "user_id": user_id,
                "productID": product_id,
                "result": result_text,
                "transaction_id": transaction_id,
            }

            try:
                result_res = api_client.post_result(payload)
                print(f"[KIT] Result JSON upload status: {result_res.status_code}", flush=True)
                print(f"[KIT] Result JSON upload body: {result_res.text}", flush=True)
            except Exception as e:
                print(f"[KIT] Result JSON upload failed: {e}", flush=True)

            try:
                batch_res = api_client.upload_session_images(
                    user_id=user_id,
                    timestamp=timestamp,
                    session_dir=session_dir,
                    product_id=product_id,
                    transaction_id=transaction_id,
                )
                print(f"[KIT] Session image upload results: {batch_res}", flush=True)
            except Exception as e:
                print(f"[KIT] Session image upload failed: {e}", flush=True)

        except Exception as e:
            print(f"[KIT] send_to_backend encountered an error: {e}", flush=True)

    def update_data(self, user_data=None, selected_product=None, product=None, transaction_id=None, **kwargs):
        self.user_data = user_data or {}
        self.selected_product = selected_product or product

        self.transaction_id = (
            transaction_id
            or kwargs.get("transaction_id")
            or self.user_data.get("transaction_id")
            or self.user_data.get("transactionID")
            or self.user_data.get("latest_transaction_id")
        )

        # persist into user_data too so downstream pages can still see it
        if self.transaction_id:
            self.user_data["transaction_id"] = self.transaction_id
            self.user_data["latest_transaction_id"] = self.transaction_id

        self.shell.set_header_right(f"Welcome, {self.user_data.get('username', 'User')}!")
        self.result_label.configure(text="Insert your test kit")
        self.confirmation_label.configure(text=" ")
        self.insert_btn.configure(state="normal")

        print(f"[KIT] update_data transaction_id={self.transaction_id}", flush=True)

        self.start_camera()

    def logout_user(self):
        self.stop_camera()
        self.user_data = {}
        self.selected_product = None
        self.transaction_id = None
        self.result_label.configure(text="Insert your test kit")
        self.confirmation_label.configure(text=" ")
        self.insert_btn.configure(state="normal")

        for page_name in ["QRLoginPage", "PurchasePage", "CashPaymentPage", "HowToUsePage"]:
            page = self.controller.frames.get(page_name)
            if page:
                if page_name == "HowToUsePage" and hasattr(page, "reset_video"):
                    page.reset_video()
                if hasattr(page, "reset_fields"):
                    page.reset_fields()

        self.controller.show_loading_then(
            "Logging Out...",
            "WelcomePage",
            delay=1000
        )