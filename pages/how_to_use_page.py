import os
from frontend import tk_compat as ctk
import tkinter as tk
import vlc
from frontend import theme
from frontend.widgets import AppShell, RoundedCard, PillButton, card_body


class HowToUsePage(ctk.CTkFrame):
    def __init__(self, master, controller):
        super().__init__(master, fg_color=theme.CREAM)
        self.controller = controller
        self.user_data = {}
        self.selected_product = None
        self.instance = vlc.Instance()
        self.media_player = self.instance.media_player_new()
        self.video_loaded = False

        self.shell = AppShell(self, title_right='Instructions')
        self.shell.pack(fill='both', expand=True)

        ctk.CTkLabel(self.shell.body, text='HOW TO USE THE TEST KIT', font=theme.heavy(32), text_color=theme.BLACK).pack(pady=(20, 10))

        self.card = RoundedCard(self.shell.body)
        self.card.pack(fill='both', expand=True, padx=24, pady=18)
        body = card_body(self.card)

        self.desc = ctk.CTkLabel(body, text='Watch the tutorial video or proceed to insert the used test kit when ready.', font=theme.font(22, 'bold'), text_color=theme.MUTED, wraplength=760, justify='center', fg_color=theme.WHITE)
        self.desc.pack(pady=(18, 12))

        btn_row = ctk.CTkFrame(body, fg_color=theme.WHITE)
        btn_row.pack(pady=(6, 14))
        PillButton(btn_row, text='Play Video Tutorial', width=220, command=self.show_video, font=theme.font(18, 'bold')).pack(side='left', padx=10)
        PillButton(btn_row, text='Insert Used Test Kit', width=240, command=self.go_to_insert_kit, font=theme.font(18, 'bold')).pack(side='left', padx=10)

        self.video_panel = tk.Frame(body, bg=theme.BLACK, width=860, height=420)
        self.video_controls = ctk.CTkFrame(body, fg_color=theme.WHITE)
        controls = self.video_controls
        ctk.CTkButton(controls, text='Play', width=110, command=self.play_video, fg_color=theme.ORANGE, text_color=theme.WHITE).grid(row=0, column=0, padx=6)
        ctk.CTkButton(controls, text='Pause', width=110, command=self.pause_video, fg_color=theme.ORANGE, text_color=theme.WHITE).grid(row=0, column=1, padx=6)
        ctk.CTkButton(controls, text='Stop', width=110, command=self.stop_video, fg_color=theme.ORANGE, text_color=theme.WHITE).grid(row=0, column=2, padx=6)

    def update_data(self, user_data=None, selected_product=None, **kwargs):
        self.user_data = user_data or {}
        self.selected_product = selected_product
        self.shell.set_header_right(f"Welcome, {self.user_data.get('username', 'User')}!")

    def go_to_insert_kit(self):
        self.controller.show_frame('KitInsertionPage', user_data=self.user_data, selected_product=self.selected_product)

    def show_video(self):
        self.video_panel.pack(pady=12)
        self.video_controls.pack(pady=(0, 14))
        self.video_panel.update_idletasks()
        if os.name == 'nt':
            self.media_player.set_hwnd(self.video_panel.winfo_id())
        else:
            self.media_player.set_xwindow(self.video_panel.winfo_id())
        if not self.video_loaded:
            video_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'videos', 'tutorial.mp4')
            if not os.path.exists(video_path):
                print('Video not found:', video_path)
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
