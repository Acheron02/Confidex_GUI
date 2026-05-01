import os
from pathlib import Path

from frontend import tk_compat as ctk
import tkinter as tk
import vlc

from frontend import theme
from frontend.widgets import AppShell, RoundedCard, PillButton, card_body
from config_manager import config


class HowToUsePage(ctk.CTkFrame):
    REFRESH_MS = 1500
    VIDEO_MONITOR_MS = 500
    SAFE_MAX_VOLUME = 70
    DEFAULT_AUTOPLAY_VOLUME = 70

    def __init__(self, master, controller):
        super().__init__(master, fg_color=theme.CREAM)
        self.controller = controller
        self.user_data = {}
        self.selected_product = None
        self.transaction_id = None

        self._config_refresh_job = None
        self._video_monitor_job = None
        self._redirecting = False

        self.instance = vlc.Instance()
        self.media_player = self.instance.media_player_new()
        self.video_loaded = False
        self.current_video_path = None

        self.shell = AppShell(
            self,
            title_right=config.get("how_to_use_page", "header_title", default="Instructions")
        )
        self.shell.pack(fill="both", expand=True)

        self._build_ui()
        self._start_config_refresh()

    def _build_ui(self):
        body_root = self.shell.body

        self.title_label = ctk.CTkLabel(
            body_root,
            text=config.get("how_to_use_page", "title", default="HOW TO USE THE TEST KIT"),
            font=theme.heavy(30),
            text_color=theme.BLACK,
            fg_color=theme.CREAM
        )
        self.title_label.pack(pady=(10, 4))

        self.card = RoundedCard(body_root)
        self.card.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        body = card_body(self.card)

        self.content_wrap = ctk.CTkFrame(body, fg_color=theme.WHITE)
        self.content_wrap.pack(fill="both", expand=True, padx=14, pady=12)

        self.top_info = ctk.CTkFrame(self.content_wrap, fg_color=theme.WHITE)
        self.top_info.pack(fill="x", pady=(0, 6))

        self.video_outer = ctk.CTkFrame(
            self.content_wrap,
            fg_color="#111111",
            corner_radius=22,
            border_width=2,
            border_color="#1f1f1f"
        )
        self.video_outer.pack(fill="x", pady=(8, 8))

        self.video_header = ctk.CTkFrame(self.video_outer, fg_color="#111111")
        self.video_header.pack(fill="x", padx=12, pady=(10, 6))

        self.video_header_left = ctk.CTkLabel(
            self.video_header,
            text="Tutorial Video",
            font=theme.font(16, "bold"),
            text_color=theme.WHITE,
            fg_color="#111111"
        )
        self.video_header_left.pack(side="left")

        self.video_status_badge = ctk.CTkLabel(
            self.video_header,
            text="Loading...",
            font=theme.font(12, "bold"),
            text_color=theme.WHITE,
            fg_color="#2d2d2d",
            corner_radius=12,
            padx=10,
            pady=4
        )
        self.video_status_badge.pack(side="right")

        self.video_panel = tk.Frame(
            self.video_outer,
            bg="black",
            width=780,
            height=600,
            highlightthickness=0,
            bd=0
        )
        self.video_panel.pack(fill="x", padx=12, pady=(0, 10))
        self.video_panel.pack_propagate(False)

        self.video_status = ctk.CTkLabel(
            self.content_wrap,
            text="",
            font=theme.font(14, "bold"),
            text_color=theme.MUTED,
            wraplength=780,
            justify="center",
            fg_color=theme.WHITE
        )
        self.video_status.pack(pady=(0, 8))

        self.footer_wrap = ctk.CTkFrame(self.content_wrap, fg_color=theme.WHITE)
        self.footer_wrap.pack(fill="x", pady=(4, 0))

        self.insert_button = PillButton(
            self.footer_wrap,
            text=config.get(
                "how_to_use_page",
                "continue_text",
                default="Proceed to Kit Insertion"
            ),
            width=300,
            height=70,
            command=self.go_to_insert_kit,
            fg_color=theme.ORANGE,
            text_color=theme.WHITE,
            font=theme.font(17, "bold")
        )
        self.insert_button.pack(pady=(0, 4))

    def _refresh_from_config(self):
        try:
            self.title_label.configure(
                text=config.get("how_to_use_page", "title", default="HOW TO USE THE TEST KIT")
            )
            self.insert_button.configure(
                text=config.get(
                    "how_to_use_page",
                    "continue_text",
                    default="Proceed to Kit Insertion"
                )
            )
        except Exception as e:
            print(f"[HOWTO] Config refresh failed: {e}", flush=True)

    def _start_config_refresh(self):
        self._refresh_from_config()
        self._config_refresh_job = self.after(self.REFRESH_MS, self._start_config_refresh)

    def _cancel_video_monitor(self):
        if self._video_monitor_job:
            try:
                self.after_cancel(self._video_monitor_job)
            except Exception:
                pass
            self._video_monitor_job = None

    def _start_video_monitor(self):
        self._cancel_video_monitor()
        self._video_monitor_job = self.after(self.VIDEO_MONITOR_MS, self._monitor_video_completion)

    def _monitor_video_completion(self):
        self._video_monitor_job = None

        if self._redirecting:
            return

        try:
            state = self.media_player.get_state()
            if state == vlc.State.Ended:
                self.video_status.configure(
                    text=config.get(
                        "how_to_use_page",
                        "video_finished_text",
                        default="Tutorial finished. Redirecting to kit insertion..."
                    ),
                    text_color=theme.MUTED
                )
                self.video_status_badge.configure(text="Finished", fg_color="#027A48")
                self.go_to_insert_kit()
                return

            if state not in (vlc.State.Stopped, vlc.State.Error, vlc.State.Ended):
                self._start_video_monitor()
        except Exception as e:
            print(f"[HOWTO] _monitor_video_completion failed: {e}", flush=True)

    def _get_video_candidates(self):
        candidates = []

        product = self.selected_product or {}
        product_id = str(
            product.get("productID")
            or product.get("product_id")
            or product.get("id")
            or ""
        ).strip()
        product_name = str(product.get("name") or "").strip()
        product_type = str(product.get("type") or "").strip()
        dispense_slot = str(product.get("dispense_slot") or "").strip()

        for key in (
            "video_path",
            "tutorial_video_path",
            "how_to_use_video",
            "instruction_video",
            "instruction_video_path",
        ):
            value = product.get(key)
            if value:
                candidates.append(value)

        video_map = config.get("how_to_use_page", "video_map", default={}) or {}
        for lookup_key in (product_id, product_name, product_type, dispense_slot):
            if lookup_key and isinstance(video_map, dict):
                mapped = video_map.get(lookup_key)
                if mapped:
                    candidates.append(mapped)

        default_video = config.get(
            "how_to_use_page",
            "video_path",
            default=os.path.join(
                os.path.dirname(os.path.dirname(__file__)),
                "videos",
                "tutorial.mp4"
            )
        )
        candidates.append(default_video)

        return candidates

    def _resolve_video_path(self):
        base_dir = Path(os.path.dirname(os.path.dirname(__file__)))

        for candidate in self._get_video_candidates():
            if not candidate:
                continue

            candidate_path = Path(candidate)
            if not candidate_path.is_absolute():
                candidate_path = base_dir / candidate_path

            if candidate_path.exists():
                return str(candidate_path)

        return None

    def _get_safe_volume(self):
        configured = config.get(
            "how_to_use_page",
            "video_volume",
            default=self.DEFAULT_AUTOPLAY_VOLUME
        )
        try:
            configured = int(configured)
        except Exception:
            configured = self.DEFAULT_AUTOPLAY_VOLUME

        configured = max(0, configured)
        configured = min(configured, self.SAFE_MAX_VOLUME)
        return configured

    def _apply_safe_audio(self):
        try:
            safe_volume = self._get_safe_volume()
            self.media_player.audio_set_mute(False)
            self.media_player.audio_set_volume(safe_volume)
        except Exception as e:
            print(f"[HOWTO] _apply_safe_audio failed: {e}", flush=True)

    def update_data(self, user_data=None, selected_product=None, product=None, transaction_id=None, **kwargs):
        self.user_data = user_data or {}
        self.selected_product = selected_product or product
        self._redirecting = False

        self.transaction_id = (
            transaction_id
            or kwargs.get("transaction_id")
            or self.user_data.get("transaction_id")
            or self.user_data.get("transactionID")
            or self.user_data.get("latest_transaction_id")
        )

        if self.transaction_id:
            self.user_data["transaction_id"] = self.transaction_id
            self.user_data["latest_transaction_id"] = self.transaction_id

        self.shell.set_header_right(f"Welcome, {self.user_data.get('username', 'User')}!")
        self.video_status.configure(text="")
        self.video_status_badge.configure(text="Loading...", fg_color="#2d2d2d")
        self.reset_video()
        self.after(150, self.show_video)

    def go_to_insert_kit(self):
        if self._redirecting:
            return

        self._redirecting = True
        self._cancel_video_monitor()
        self.stop_video()

        self.controller.show_loading_then(
            config.get(
                "how_to_use_page",
                "next_loading_text",
                default="Preparing reverse vending machine"
            ),
            "KitInsertionPage",
            delay=1000,
            user_data=self.user_data,
            selected_product=self.selected_product,
            transaction_id=self.transaction_id
        )

    def show_video(self):
        try:
            self.video_panel.update_idletasks()

            if os.name == "nt":
                self.media_player.set_hwnd(self.video_panel.winfo_id())
            else:
                self.media_player.set_xwindow(self.video_panel.winfo_id())

            video_path = self._resolve_video_path()
            if not video_path:
                msg = config.get(
                    "how_to_use_page",
                    "video_not_found_text",
                    default="Tutorial video not found."
                )
                self.video_status.configure(text=msg, text_color=theme.ERROR)
                self.video_status_badge.configure(text="Unavailable", fg_color="#B42318")
                return

            if (not self.video_loaded) or (self.current_video_path != video_path):
                media = self.instance.media_new(video_path)
                self.media_player.set_media(media)
                self.video_loaded = True
                self.current_video_path = video_path

            self.video_status.configure(text="")
            self.video_status_badge.configure(text="Ready", fg_color="#027A48")
            self.after(100, self.play_video)

        except Exception as e:
            print(f"[HOWTO] show_video failed: {e}", flush=True)
            self.video_status.configure(
                text=f"{config.get('how_to_use_page', 'video_error_prefix', default='Video error:')} {e}",
                text_color=theme.ERROR
            )
            self.video_status_badge.configure(text="Error", fg_color="#B42318")

    def play_video(self):
        try:
            self._apply_safe_audio()
            self.media_player.play()
            self.after(250, self._apply_safe_audio)
            self.after(1000, self._apply_safe_audio)
            self.video_status_badge.configure(
                text=f"Playing • Vol {self._get_safe_volume()}",
                fg_color="#027A48"
            )
            self._start_video_monitor()
        except Exception as e:
            print(f"[HOWTO] play_video failed: {e}", flush=True)

    def pause_video(self):
        try:
            self.media_player.pause()
            self._cancel_video_monitor()
            self.video_status_badge.configure(text="Paused", fg_color="#9A6700")
        except Exception as e:
            print(f"[HOWTO] pause_video failed: {e}", flush=True)

    def stop_video(self):
        try:
            self._cancel_video_monitor()
            self.media_player.stop()
            self.media_player.audio_set_volume(0)
            self.video_status_badge.configure(text="Stopped", fg_color="#667085")
        except Exception as e:
            print(f"[HOWTO] stop_video failed: {e}", flush=True)

    def reset_video(self):
        self.stop_video()
        self.video_loaded = False
        self.current_video_path = None
        self.video_status.configure(text="")

    def destroy(self):
        self._cancel_video_monitor()
        self.reset_video()
        super().destroy()