import os
from frontend import tk_compat as ctk
import tkinter as tk
import vlc
from frontend import theme
from frontend.widgets import AppShell, RoundedCard, PillButton, card_body
from config_manager import config


class HowToUsePage(ctk.CTkFrame):
    REFRESH_MS = 1500

    def __init__(self, master, controller):
        super().__init__(master, fg_color=theme.CREAM)
        self.controller = controller
        self.user_data = {}
        self.selected_product = None
        self.transaction_id = None
        self._config_refresh_job = None

        self.instance = vlc.Instance()
        self.media_player = self.instance.media_player_new()
        self.video_loaded = False

        self.shell = AppShell(
            self,
            title_right=config.get("how_to_use_page", "header_title", default="Instructions")
        )
        self.shell.pack(fill="both", expand=True)

        self.title_label = ctk.CTkLabel(
            self.shell.body,
            text=config.get("how_to_use_page", "title", default="HOW TO USE THE TEST KIT"),
            font=theme.heavy(32),
            text_color=theme.BLACK
        )
        self.title_label.pack(pady=(20, 10))

        self.card = RoundedCard(self.shell.body)
        self.card.pack(fill="both", expand=True, padx=24, pady=18)
        body = card_body(self.card)

        self.desc = ctk.CTkLabel(
            body,
            text=config.get(
                "how_to_use_page",
                "description",
                default="Watch the tutorial video or proceed to insert the used test kit when ready."
            ),
            font=theme.font(22, "bold"),
            text_color=theme.MUTED,
            wraplength=760,
            justify="center",
            fg_color=theme.WHITE
        )
        self.desc.pack(pady=(18, 12))

        btn_row = ctk.CTkFrame(body, fg_color=theme.WHITE)
        btn_row.pack(pady=(6, 14))

        self.play_button = PillButton(
            btn_row,
            text=config.get(
                "how_to_use_page",
                "play_video_button_text",
                default="Play Video Tutorial"
            ),
            width=220,
            command=self.show_video,
            font=theme.font(18, "bold")
        )
        self.play_button.pack(side="left", padx=10)

        self.insert_button = PillButton(
            btn_row,
            text=config.get(
                "how_to_use_page",
                "insert_kit_button_text",
                default="Insert Used Test Kit"
            ),
            width=240,
            command=self.go_to_insert_kit,
            font=theme.font(18, "bold")
        )
        self.insert_button.pack(side="left", padx=10)

        self.video_panel = tk.Frame(body, bg=theme.BLACK, width=860, height=420)
        self.video_controls = ctk.CTkFrame(body, fg_color=theme.WHITE)
        controls = self.video_controls

        self.play_ctl = ctk.CTkButton(
            controls,
            text=config.get("how_to_use_page", "video_play_text", default="Play"),
            width=110,
            command=self.play_video,
            fg_color=theme.ORANGE,
            text_color=theme.WHITE
        )
        self.play_ctl.grid(row=0, column=0, padx=6)

        self.pause_ctl = ctk.CTkButton(
            controls,
            text=config.get("how_to_use_page", "video_pause_text", default="Pause"),
            width=110,
            command=self.pause_video,
            fg_color=theme.ORANGE,
            text_color=theme.WHITE
        )
        self.pause_ctl.grid(row=0, column=1, padx=6)

        self.stop_ctl = ctk.CTkButton(
            controls,
            text=config.get("how_to_use_page", "video_stop_text", default="Stop"),
            width=110,
            command=self.stop_video,
            fg_color=theme.ORANGE,
            text_color=theme.WHITE
        )
        self.stop_ctl.grid(row=0, column=2, padx=6)

        self._start_config_refresh()

    def _refresh_from_config(self):
        try:
            self.title_label.configure(
                text=config.get("how_to_use_page", "title", default="HOW TO USE THE TEST KIT")
            )
            self.desc.configure(
                text=config.get(
                    "how_to_use_page",
                    "description",
                    default="Watch the tutorial video or proceed to insert the used test kit when ready."
                )
            )
            self.play_button.configure(
                text=config.get(
                    "how_to_use_page",
                    "play_video_button_text",
                    default="Play Video Tutorial"
                )
            )
            self.insert_button.configure(
                text=config.get(
                    "how_to_use_page",
                    "insert_kit_button_text",
                    default="Insert Used Test Kit"
                )
            )
            self.play_ctl.configure(
                text=config.get("how_to_use_page", "video_play_text", default="Play")
            )
            self.pause_ctl.configure(
                text=config.get("how_to_use_page", "video_pause_text", default="Pause")
            )
            self.stop_ctl.configure(
                text=config.get("how_to_use_page", "video_stop_text", default="Stop")
            )
        except Exception as e:
            print(f"[HOWTO] Config refresh failed: {e}", flush=True)

    def _start_config_refresh(self):
        self._refresh_from_config()
        self._config_refresh_job = self.after(self.REFRESH_MS, self._start_config_refresh)

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

        if self.transaction_id:
            self.user_data["transaction_id"] = self.transaction_id
            self.user_data["latest_transaction_id"] = self.transaction_id

        self.shell.set_header_right(f"Welcome, {self.user_data.get('username', 'User')}!")

    def go_to_insert_kit(self):
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
        self.video_panel.pack(pady=12)
        self.video_controls.pack(pady=(0, 14))
        self.video_panel.update_idletasks()

        if os.name == "nt":
            self.media_player.set_hwnd(self.video_panel.winfo_id())
        else:
            self.media_player.set_xwindow(self.video_panel.winfo_id())

        if not self.video_loaded:
            video_path = config.get(
                "how_to_use_page",
                "video_path",
                default=os.path.join(
                    os.path.dirname(os.path.dirname(__file__)),
                    "videos",
                    "tutorial.mp4"
                )
            )
            if not os.path.exists(video_path):
                print("Video not found:", video_path, flush=True)
                return

            media = self.instance.media_new(video_path)
            self.media_player.set_media(media)
            self.video_loaded = True

        self.after(100, self.play_video)

    def play_video(self):
        self.media_player.play()

    def pause_video(self):
        self.media_player.pause()

    def stop_video(self):
        self.media_player.stop()

    def reset_video(self):
        self.media_player.stop()
        self.video_panel.pack_forget()
        self.video_controls.pack_forget()
        self.video_loaded = False