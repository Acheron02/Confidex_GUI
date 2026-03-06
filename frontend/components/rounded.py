import tkinter as tk


def _parent_bg(master, default="#F5F2DE"):
    try:
        return master.cget("bg")
    except Exception:
        return default


def round_rect_points(x1, y1, x2, y2, r):
    return [
        x1 + r, y1,
        x2 - r, y1,
        x2, y1,
        x2, y1 + r,
        x2, y2 - r,
        x2, y2,
        x2 - r, y2,
        x1 + r, y2,
        x1, y2,
        x1, y2 - r,
        x1, y1 + r,
        x1, y1,
    ]


class RoundedContainer(tk.Frame):
    def __init__(
        self,
        master,
        width=None,
        height=None,
        fg_color="#FFFFFF",
        border_color="#1E1E1E",
        border_width=2,
        radius=26,
        pad=10,
        **kwargs,
    ):
        bg = _parent_bg(master)
        super().__init__(
            master,
            bg=bg,
            width=width,
            height=height,
            bd=0,
            highlightthickness=0,
            **kwargs,
        )

        self.width = width or 0
        self.height = height or 0
        self.fg_color = fg_color

        self._fill = fg_color
        self._border = border_color
        self._border_width = border_width
        self._radius = radius
        self._pad = pad
        self._bg = bg

        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        self.canvas.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.content = tk.Frame(self, bg=fg_color, bd=0, highlightthickness=0)
        self.content.place(
            x=pad,
            y=pad,
            relwidth=1,
            relheight=1,
            width=-2 * pad,
            height=-2 * pad,
        )

        self.bind("<Configure>", self._redraw)
        self.after(0, self._redraw)

    def _redraw(self, event=None):
        w = max(2, self.winfo_width())
        h = max(2, self.winfo_height())
        r = min(self._radius, w // 2, h // 2)

        self.width = w
        self.height = h
        self.fg_color = self._fill

        self.canvas.delete("all")

        if self._border_width > 0:
            self._draw_shape(0, 0, w, h, self._border, r)
            inset = self._border_width
        else:
            inset = 0

        self._draw_shape(
            inset,
            inset,
            w - inset,
            h - inset,
            self._fill,
            max(0, r - inset),
        )

        self.content.configure(bg=self._fill)
        tk.Frame.configure(self, bg=self._bg)
        tk.Canvas.configure(self.canvas, bg=self._bg)

    def _draw_shape(self, x1, y1, x2, y2, fill, r):
        if x2 <= x1 or y2 <= y1:
            return

        self.canvas.create_polygon(
            round_rect_points(x1, y1, x2, y2, r),
            smooth=True,
            splinesteps=24,
            fill=fill,
            outline=fill,
        )

    def configure(self, cnf=None, **kw):
        if "fg_color" in kw:
            self._fill = kw.pop("fg_color")
        if "border_color" in kw:
            self._border = kw.pop("border_color")
        if "border_width" in kw:
            self._border_width = kw.pop("border_width")
        if "corner_radius" in kw:
            self._radius = kw.pop("corner_radius")
        if "radius" in kw:
            self._radius = kw.pop("radius")
        if "bg" in kw:
            self._bg = kw.pop("bg")

        width_changed = False
        if "width" in kw:
            self.width = kw["width"]
            width_changed = True
        if "height" in kw:
            self.height = kw["height"]
            width_changed = True

        result = tk.Frame.configure(self, cnf or {}, **kw)

        if width_changed:
            self.after_idle(self._redraw)
        else:
            self.after_idle(self._redraw)

        return result

    config = configure

    def pack_propagate(self, flag=True):
        self.content.pack_propagate(flag)

    def grid_propagate(self, flag=True):
        self.content.grid_propagate(flag)


class RoundedCard(RoundedContainer):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", "#FFFFFF")
        kwargs.setdefault("border_color", "#1E1E1E")
        kwargs.setdefault("border_width", 2)
        kwargs.setdefault("radius", 28)
        kwargs.setdefault("pad", 14)
        super().__init__(master, **kwargs)


class OutlineTile(RoundedContainer):
    def __init__(self, master, **kwargs):
        kwargs.setdefault("fg_color", "#FFFFFF")
        kwargs.setdefault("border_color", "#1E1E1E")
        kwargs.setdefault("border_width", 2)
        kwargs.setdefault("radius", 22)
        kwargs.setdefault("pad", 10)
        super().__init__(master, **kwargs)


class PillButton(tk.Canvas):
    def __init__(
        self,
        master,
        text,
        command=None,
        width=180,
        height=56,
        fg_color="#C46A2A",
        text_color="#FFFFFF",
        disabled_color="#C9A58D",
        font=("Arial", 18, "bold"),
        radius=None,
        state="normal",
        **kwargs,
    ):
        bg = _parent_bg(master)
        super().__init__(
            master,
            width=width,
            height=height,
            bg=bg,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
            **kwargs,
        )
        self._outer_bg = bg
        self._fill = fg_color
        self._text_color = text_color
        self._disabled_color = disabled_color
        self._font = font
        self._command = command
        self._text = text
        self._state = state
        self._radius = radius or height // 2

        self.bind("<Configure>", self._redraw)
        self.bind("<Button-1>", self._on_click)
        self.after(0, self._redraw)

    def _redraw(self, event=None):
        w = max(2, self.winfo_width())
        h = max(2, self.winfo_height())
        r = min(self._radius, w // 2, h // 2)
        fill = self._fill if self._state != "disabled" else self._disabled_color

        self.delete("all")
        tk.Canvas.configure(self, bg=self._outer_bg)

        self.create_polygon(
            round_rect_points(0, 0, w, h, r),
            smooth=True,
            splinesteps=24,
            fill=fill,
            outline=fill,
        )
        self.create_text(
            w / 2,
            h / 2,
            text=self._text,
            fill=self._text_color,
            font=self._font,
        )

    def _on_click(self, event=None):
        if self._state == "disabled":
            return
        if callable(self._command):
            self._command()

    def configure(self, cnf=None, **kw):
        if "text" in kw:
            self._text = kw.pop("text")
        if "command" in kw:
            self._command = kw.pop("command")
        if "state" in kw:
            self._state = kw.pop("state")
            tk.Canvas.configure(
                self,
                cursor="arrow" if self._state == "disabled" else "hand2",
            )
        if "fg_color" in kw:
            self._fill = kw.pop("fg_color")
        if "text_color" in kw:
            self._text_color = kw.pop("text_color")
        if "font" in kw:
            self._font = kw.pop("font")

        result = tk.Canvas.configure(self, cnf or {}, **kw)
        self.after_idle(self._redraw)
        return result

    config = configure