
import tkinter as tk
from tkinter import font as tkfont


def _parent_bg(master, default='#F5F2DE'):
    try:
        return master.cget('bg')
    except Exception:
        return default


def _normalize_color(color, master=None, default='#F5F2DE'):
    if color in (None, '', 'transparent'):
        return _parent_bg(master, default)
    if isinstance(color, tuple) and color:
        return color[0]
    return color


class CTkFont(tkfont.Font):
    def __init__(self, family='Arial', size=12, weight='normal', **kwargs):
        super().__init__(family=family, size=size, weight=weight, **kwargs)


class CTk(tk.Tk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.configure(bg='#F5F2DE')

    def configure(self, cnf=None, **kw):
        if 'fg_color' in kw:
            kw['bg'] = kw.pop('fg_color')
        return super().configure(cnf or {}, **kw)

    config = configure


class _BaseMixin:
    def _apply_common(self, master=None, kwargs=None):
        kwargs = dict(kwargs or {})
        if 'fg_color' in kwargs:
            kwargs['bg'] = _normalize_color(kwargs.pop('fg_color'), master)
        if 'text_color' in kwargs:
            kwargs['fg'] = kwargs.pop('text_color')
        if 'hover_color' in kwargs:
            kwargs.pop('hover_color')
        if 'corner_radius' in kwargs:
            kwargs.pop('corner_radius')
        if 'border_spacing' in kwargs:
            kwargs.pop('border_spacing')
        if 'textvariable' in kwargs:
            pass
        if 'border_color' in kwargs:
            bc = kwargs.pop('border_color')
            kwargs['highlightbackground'] = bc
            kwargs['highlightcolor'] = bc
        if 'border_width' in kwargs:
            kwargs['highlightthickness'] = kwargs.pop('border_width')
        if 'font' in kwargs and isinstance(kwargs['font'], tuple):
            kwargs['font'] = kwargs['font']
        return kwargs

    def configure(self, cnf=None, **kw):
        kw = self._apply_common(self.master, kw)
        return super().configure(cnf or {}, **kw)

    config = configure


class CTkFrame(_BaseMixin, tk.Frame):
    def __init__(self, master=None, **kwargs):
        kwargs = self._apply_common(master, kwargs)
        kwargs.setdefault('bd', 0)
        super().__init__(master, **kwargs)


class CTkLabel(_BaseMixin, tk.Label):
    def __init__(self, master=None, **kwargs):
        kwargs = self._apply_common(master, kwargs)
        kwargs.setdefault('bg', _parent_bg(master))
        super().__init__(master, **kwargs)


class CTkButton(_BaseMixin, tk.Button):
    def __init__(self, master=None, **kwargs):
        command = kwargs.get('command')
        kwargs = self._apply_common(master, kwargs)
        bg = kwargs.get('bg', '#C46A2A')
        fg = kwargs.get('fg', '#FFFFFF')
        kwargs.setdefault('activebackground', bg)
        kwargs.setdefault('activeforeground', fg)
        kwargs.setdefault('relief', 'flat')
        kwargs.setdefault('cursor', 'hand2' if command else 'arrow')
        kwargs.setdefault('bd', 0)
        kwargs.setdefault('disabledforeground', '#DDDDDD')
        super().__init__(master, **kwargs)


def set_appearance_mode(mode):
    return None
