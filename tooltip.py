# -*- coding: utf-8 -*-
"""
Tooltip ساده: با نگه‌داشتن ماوس روی یک ویجت (مثلاً یک دکمه آیکونی)، بعد از
مدت کوتاهی یک برچسب کوچک با توضیح کنار آن نمایش داده می‌شود.
"""
import tkinter as tk


class Tooltip:
    def __init__(self, widget, text, delay=450):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tip_window = None
        self._after_id = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, event=None):
        self._unschedule()
        self._after_id = self.widget.after(self.delay, self._show)

    def _unschedule(self):
        if self._after_id:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self):
        if self.tip_window or not self.text:
            return
        try:
            x = self.widget.winfo_rootx() + (self.widget.winfo_width() // 2) - 10
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        except Exception:
            return
        self.tip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        try:
            tw.wm_attributes("-topmost", True)
        except Exception:
            pass
        tw.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            tw, text=self.text, justify="right", background="#333333", foreground="#ffffff",
            relief="solid", borderwidth=1, font=("Tahoma", 8), padx=7, pady=3,
        )
        label.pack()

    def _hide(self, event=None):
        self._unschedule()
        if self.tip_window:
            try:
                self.tip_window.destroy()
            except Exception:
                pass
            self.tip_window = None


def add_tooltip(widget, text, delay=450):
    """یک Tooltip روی ویجت اضافه می‌کند و نمونه‌اش را برمی‌گرداند (برای جلوگیری از garbage collection نگه دارید)"""
    return Tooltip(widget, text, delay=delay)
