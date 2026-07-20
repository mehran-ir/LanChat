# -*- coding: utf-8 -*-
"""
ویجت نمایش گفتگو (Canvas-based) با پشتیبانی از:
- تصویر پس‌زمینه اختصاصی برای هر چت
- حباب‌های پیام برای ارسالی/دریافتی با ساعت شمسی/تهران کنارشان
- کلیک راست روی پیام‌های خودم برای «لغو ارسال»
- فیلتر کردن بر اساس عبارت جستجو
"""
import os
import tkinter as tk
from tkinter import ttk

from jalali import jalali_datetime_str
from theme import contrast_text_color, DEFAULT_CHATBOX_COLOR

try:
    from PIL import Image, ImageTk
    HAVE_PIL = True
except Exception:
    HAVE_PIL = False

BUBBLE_WIDTH = 340


class ChatView(tk.Frame):
    def __init__(self, parent, on_recall, on_open_file, theme_color="#AFEEEE",
                 box_color=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.on_recall = on_recall
        self.on_open_file = on_open_file
        self.theme_color = theme_color
        self.box_color = box_color or DEFAULT_CHATBOX_COLOR

        self.canvas = tk.Canvas(self, highlightthickness=0, bg=self.box_color)
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vbar.pack(side="right", fill="y")

        self.bg_path = None
        self._bg_photo = None
        self._photo_refs = []
        self._registry = []  # لیست (x1,y1,x2,y2,msg,outgoing)
        self._current_chat = None
        self._current_my_name = None
        self._current_search = None

        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)      # ویندوز
        self.canvas.bind("<Button-4>", self._on_mousewheel)        # لینوکس (اسکرول بالا)
        self.canvas.bind("<Button-5>", self._on_mousewheel)        # لینوکس (اسکرول پایین)

    # ---------------------------------------------------------------- API ---
    def set_theme(self, color):
        self.theme_color = color

    def set_box_color(self, color):
        self.box_color = color or DEFAULT_CHATBOX_COLOR
        if not self.bg_path:
            self.canvas.configure(bg=self.box_color)

    def set_background_image(self, path):
        self.bg_path = path
        self._render_background()

    def render(self, chat, my_name, search_term=None):
        self._current_chat = chat
        self._current_my_name = my_name
        self._current_search = (search_term or "").strip().lower()
        self._redraw()

    def clear(self):
        self.canvas.delete("all")
        self._current_chat = None
        self._registry = []

    # ------------------------------------------------------------ INTERNAL ---
    def _on_resize(self, _event):
        self._render_background()
        if self._current_chat is not None:
            self._redraw()

    def _on_mousewheel(self, event):
        if event.num == 4:
            self.canvas.yview_scroll(-3, "units")
        elif event.num == 5:
            self.canvas.yview_scroll(3, "units")
        else:
            self.canvas.yview_scroll(int(-1 * (event.delta / 120) * 3), "units")

    def _render_background(self):
        self.canvas.delete("bg")
        w = max(self.canvas.winfo_width(), 10)
        h = max(self.canvas.winfo_height(), 10)
        if not self.bg_path or not os.path.exists(self.bg_path):
            self.canvas.configure(bg=self.box_color)
            self._bg_photo = None
            return
        try:
            if HAVE_PIL:
                img = Image.open(self.bg_path).convert("RGB")
                img = img.resize((w, h))
                self._bg_photo = ImageTk.PhotoImage(img)
            else:
                self._bg_photo = tk.PhotoImage(file=self.bg_path)
            self.canvas.create_image(0, 0, image=self._bg_photo, anchor="nw", tags=("bg",))
            self.canvas.tag_lower("bg")
        except Exception:
            self.canvas.configure(bg=self.box_color)
            self._bg_photo = None

    def _redraw(self):
        chat = self._current_chat
        my_name = self._current_my_name
        self.canvas.delete("msg")
        self._registry = []
        self._photo_refs = []

        y = 16
        messages = chat.messages
        search = self._current_search

        for msg in messages:
            text_val = msg.get("text") or ""
            if search:
                haystack = (text_val or "").lower()
                if search not in haystack:
                    continue

            outgoing = bool(msg.get("outgoing"))
            status = msg.get("status", "sent")
            sender = msg.get("sender", "")

            if msg.get("type") == "system":
                y = self._draw_system_line(y, text_val)
                continue

            if status == "recalled":
                display_text = "🚫 این پیام لغو / حذف شد"
            elif status == "pending":
                display_text = text_val + "   (در حال ارسال...)"
            elif msg.get("type") == "file":
                display_text = f"📎 {text_val}"
            else:
                display_text = text_val

            y = self._draw_bubble(y, msg, display_text, outgoing, sender, chat.is_group)

        self.canvas.configure(scrollregion=(0, 0, self.canvas.winfo_width(), y + 20))
        self.canvas.yview_moveto(1.0)

    def _draw_system_line(self, y, text):
        w = max(self.canvas.winfo_width(), 200)
        self.canvas.create_text(
            w / 2, y, text=text, fill="#666666", font=("Tahoma", 8), tags=("msg",)
        )
        return y + 24

    def _draw_bubble(self, y, msg, text, outgoing, sender, is_group):
        w = max(self.canvas.winfo_width(), 200)
        bubble_color = "#dcf3f3" if outgoing else "#ffffff"
        if self.bg_path:
            bubble_color = "#dff8f8" if outgoing else "#f4f4f4"
        text_color = "#111111"

        header = ""
        if is_group and not outgoing:
            header = sender

        full_text = (header + "\n" if header else "") + text
        tmp_id = self.canvas.create_text(
            0, 0, text=full_text, font=("Tahoma", 10), width=BUBBLE_WIDTH, anchor="nw"
        )
        bbox = self.canvas.bbox(tmp_id)
        self.canvas.delete(tmp_id)
        text_h = (bbox[3] - bbox[1]) if bbox else 20
        text_w = (bbox[2] - bbox[0]) if bbox else 40

        pad = 10
        bubble_h = text_h + pad * 2
        bubble_w = min(BUBBLE_WIDTH, text_w) + pad * 2

        if outgoing:
            x2 = w - 20
            x1 = x2 - bubble_w
        else:
            x1 = 20
            x2 = x1 + bubble_w

        rect_id = self.canvas.create_rectangle(
            x1, y, x2, y + bubble_h, fill=bubble_color, outline="#bbbbbb", width=1, tags=("msg",)
        )
        text_id = self.canvas.create_text(
            x1 + pad, y + pad, text=full_text, font=("Tahoma", 10),
            width=BUBBLE_WIDTH, anchor="nw", fill=text_color, tags=("msg",)
        )

        ts_str = self._format_timestamp(msg)
        status_icon = ""
        if msg.get("status") == "pending":
            status_icon = " ⏳"
        elif outgoing and msg.get("status") == "sent":
            status_icon = " ✔"

        ts_id = self.canvas.create_text(
            x2 if outgoing else x1, y + bubble_h + 2,
            text=ts_str + status_icon, font=("Tahoma", 7), fill="#888888",
            anchor="ne" if outgoing else "nw", tags=("msg",),
        )

        bottom = y + bubble_h + 16
        self._registry.append((x1, y, x2, bottom, msg, outgoing))
        return bottom

    def _format_timestamp(self, msg):
        from datetime import datetime
        ts = msg.get("timestamp")
        try:
            dt = datetime.fromisoformat(ts)
        except Exception:
            return ""
        try:
            return jalali_datetime_str(dt).split(" - ")[-1]
        except Exception:
            return dt.strftime("%H:%M")

    def _on_right_click(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        for x1, y1, x2, y2, msg, outgoing in self._registry:
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                if outgoing and msg.get("status") == "sent" and msg.get("type") in ("text", "file"):
                    menu = tk.Menu(self, tearoff=0)
                    menu.add_command(
                        label="🚫 لغو ارسال / حذف برای همه",
                        command=lambda m=msg: self.on_recall(m),
                    )
                    menu.tk_popup(event.x_root, event.y_root)
                return

    def _on_double_click(self, event):
        cx = self.canvas.canvasx(event.x)
        cy = self.canvas.canvasy(event.y)
        for x1, y1, x2, y2, msg, outgoing in self._registry:
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                if msg.get("type") == "file" and msg.get("path"):
                    self.on_open_file(msg["path"])
                return
