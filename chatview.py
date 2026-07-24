# -*- coding: utf-8 -*-
"""
ویجت نمایش گفتگو (Canvas-based) با پشتیبانی از:
- تصویر پس‌زمینه اختصاصی برای هر چت
- حباب‌های پیام برای ارسالی/دریافتی با ساعت شمسی/تهران کنارشان
- کلیک راست روی پیام‌های خودم برای «لغو ارسال» / «پاسخ»
- فیلتر کردن بر اساس عبارت جستجو

نکته مهم: متن پیام‌ها همیشه با canvas.create_text (موتور بومی رندر متن Tkinter)
رسم می‌شود، نه با چیدمان دستی کلمه‌به‌کلمه — چون چیدمان دستی، ترتیب صحیح
راست‌به‌چپ متن فارسی/عربی را به‌هم می‌زند. موتور بومی Tk این ترتیب را درست
رعایت می‌کند.
"""
import os
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

from jalali import jalali_datetime_str
from theme import contrast_text_color, DEFAULT_CHATBOX_COLOR
from emoji_render import get_emoji_icon, is_emoji_only, split_emoji_clusters

try:
    from PIL import Image, ImageTk
    HAVE_PIL = True
except Exception:
    HAVE_PIL = False

BUBBLE_WIDTH = 340


class ChatView(tk.Frame):
    def __init__(self, parent, on_recall, on_open_file, theme_color="#AFEEEE",
                 box_color=None, on_reply=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.on_recall = on_recall
        self.on_open_file = on_open_file
        self.on_reply = on_reply
        self.theme_color = theme_color
        self.box_color = box_color or DEFAULT_CHATBOX_COLOR

        self.canvas = tk.Canvas(self, highlightthickness=0, bg=self.box_color)
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self._on_yscroll)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.vbar.pack(side="right", fill="y")

        self._body_font = tkfont.Font(family="Tahoma", size=10)
        self._header_font = tkfont.Font(family="Tahoma", size=9, weight="bold")
        self._quote_font = tkfont.Font(family="Tahoma", size=8, slant="italic")
        self._ts_font = ("Tahoma", 7)

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
        self._reposition_background()

    def _on_yscroll(self, first, last):
        """هر بار نمای بوم اسکرول شود (چه با ماوس، چه با اسکرول‌بار، چه برنامه‌ای) این فراخوانی می‌شود"""
        self.vbar.set(first, last)
        self._reposition_background()

    def _reposition_background(self):
        """تصویر پس‌زمینه را همیشه بالای همان ناحیه‌ای که الان دیده می‌شود نگه می‌دارد تا با اسکرول از بین نرود"""
        if not self.bg_path:
            return
        try:
            top_y = self.canvas.canvasy(0)
            if self.canvas.find_withtag("bg"):
                self.canvas.coords("bg", 0, top_y)
        except Exception:
            pass

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
            self.canvas.create_image(0, self.canvas.canvasy(0), image=self._bg_photo, anchor="nw", tags=("bg",))
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

            if (
                msg.get("type") == "text"
                and status in ("sent", "read")
                and not msg.get("reply_to")
                and is_emoji_only(text_val)
            ):
                y = self._draw_jumbo_emoji_bubble(y, msg, outgoing, sender, chat.is_group)
                continue

            y = self._draw_bubble(y, msg, display_text, outgoing, sender, chat.is_group)

        self.canvas.configure(scrollregion=(0, 0, self.canvas.winfo_width(), y + 20))
        self.canvas.yview_moveto(1.0)

    def _draw_system_line(self, y, text):
        w = max(self.canvas.winfo_width(), 200)
        self.canvas.create_text(
            w / 2, y, text=text, fill="#666666", font=("Tahoma", 8), tags=("msg",)
        )
        return y + 24

    def _draw_jumbo_emoji_bubble(self, y, msg, outgoing, sender, is_group):
        """پیام‌هایی که فقط شامل ایموجی هستند را بزرگ‌تر و رنگی (بدون باکس متنی) نشان می‌دهد"""
        w = max(self.canvas.winfo_width(), 200)
        icon_size = 40
        gap = 4
        pad = 10

        clusters = split_emoji_clusters(msg.get("text") or "")
        rendered = []
        for cluster in clusters:
            icon = get_emoji_icon(cluster, size=icon_size)
            rendered.append((cluster, icon))

        header = sender if (is_group and not outgoing) else ""
        header_h = 18 if header else 0

        content_w = 0
        for _, icon in rendered:
            content_w += (icon.width() if icon else icon_size) + gap
        content_w = max(content_w - gap, icon_size)

        bubble_w = content_w + pad * 2
        bubble_h = header_h + icon_size + pad * 2

        if outgoing:
            x2 = w - 20
            x1 = x2 - bubble_w
        else:
            x1 = 20
            x2 = x1 + bubble_w

        if header:
            self.canvas.create_text(
                x1 + pad, y + 2, text=header, font=("Tahoma", 8, "bold"),
                anchor="nw", fill="#666666", tags=("msg",),
            )

        cx = x1 + pad
        cy = y + header_h + pad
        for cluster, icon in rendered:
            if icon:
                self._photo_refs.append(icon)
                self.canvas.create_image(cx, cy, image=icon, anchor="nw", tags=("msg",))
                cx += icon.width() + gap
            else:
                # نسخه پشتیبان اگر رندر رنگی ممکن نشد: همان ایموجی با فونت بزرگ‌تر معمولی
                tid = self.canvas.create_text(
                    cx, cy, text=cluster, font=("Segoe UI Emoji", 22), anchor="nw", tags=("msg",)
                )
                bbox = self.canvas.bbox(tid)
                cx += (bbox[2] - bbox[0] if bbox else icon_size) + gap

        ts_str = self._format_timestamp(msg)
        status_icon = ""
        if msg.get("status") == "read":
            status_icon = " ✔✔"
        elif msg.get("status") == "sent":
            status_icon = " ✔"
        self.canvas.create_text(
            x2 if outgoing else x1, y + bubble_h + 2,
            text=ts_str + status_icon, font=("Tahoma", 7), fill="#888888",
            anchor="ne" if outgoing else "nw", tags=("msg",),
        )

        bottom = y + bubble_h + 16
        self._registry.append((x1, y, x2, bottom, msg, outgoing))
        return bottom

    def _truncate_to_width(self, font_obj, text, max_w):
        text = (text or "").replace("\n", " ").strip()
        if font_obj.measure(text) <= max_w:
            return text
        while text and font_obj.measure(text + "…") > max_w:
            text = text[:-1]
        return text + "…" if text else "…"

    def _draw_bubble(self, y, msg, text, outgoing, sender, is_group):
        w = max(self.canvas.winfo_width(), 200)
        bubble_color = "#dcf8dc" if outgoing else "#ffffff"
        text_color = "#111111"
        pad = 10
        inner_max_w = BUBBLE_WIDTH

        header_text = sender if (is_group and not outgoing) else ""
        header_h = 0
        header_w = 0
        if header_text:
            header_h = self._header_font.metrics("linespace") + 3
            header_w = min(inner_max_w, self._header_font.measure(header_text))

        reply_to = msg.get("reply_to")
        quote_line = ""
        quote_h = 0
        quote_w = 0
        if reply_to:
            reply_sender = msg.get("reply_sender") or ""
            reply_snippet = self._truncate_to_width(self._quote_font, msg.get("reply_text") or "", inner_max_w - 20)
            quote_line = f"↩ {reply_sender}: {reply_snippet}"
            quote_h = self._quote_font.metrics("linespace") + 8
            quote_w = min(inner_max_w, self._quote_font.measure(quote_line) + 10)

        # اندازه‌گیری متن اصلی با رندر بومی Tkinter (که ترتیب راست‌به‌چپ فارسی را درست رعایت می‌کند)
        tmp_id = self.canvas.create_text(
            0, 0, text=text, font=self._body_font, width=inner_max_w, anchor="nw"
        )
        bbox = self.canvas.bbox(tmp_id)
        self.canvas.delete(tmp_id)
        body_w = (bbox[2] - bbox[0]) if bbox else 30
        body_h = (bbox[3] - bbox[1]) if bbox else self._body_font.metrics("linespace")

        content_w = max(header_w, body_w, quote_w, 30)
        content_h = header_h + quote_h + (4 if reply_to else 0) + body_h

        bubble_w = content_w + pad * 2
        bubble_h = content_h + pad * 2

        if outgoing:
            x2 = w - 20
            x1 = x2 - bubble_w
        else:
            x1 = 20
            x2 = x1 + bubble_w

        outline_color = "#8fd98f" if outgoing else "#bbbbbb"
        self.canvas.create_rectangle(
            x1, y, x2, y + bubble_h, fill=bubble_color, outline=outline_color, width=1, tags=("msg",)
        )

        cursor_y = y + pad

        if header_text:
            self.canvas.create_text(
                x1 + pad, cursor_y, text=header_text, font=self._header_font,
                anchor="nw", fill="#0a6f6f", tags=("msg",),
            )
            cursor_y += header_h

        if reply_to:
            quote_top = cursor_y
            self.canvas.create_rectangle(
                x1 + pad, quote_top, x1 + pad + 3, quote_top + quote_h - 4,
                fill="#7fa8c9", outline="", tags=("msg",),
            )
            self.canvas.create_text(
                x1 + pad + 8, quote_top + (quote_h - 4) / 2, text=quote_line,
                font=self._quote_font, anchor="w", fill="#4a4a4a", tags=("msg",),
            )
            cursor_y += quote_h + 4

        # رسم مستقیم متن اصلی با canvas.create_text — موتور بومی Tkinter، بدون چیدمان دستی کلمه‌به‌کلمه
        self.canvas.create_text(
            x1 + pad, cursor_y, text=text, font=self._body_font, width=inner_max_w,
            anchor="nw", fill=text_color, tags=("msg",),
        )

        ts_str = self._format_timestamp(msg)
        status_icon = ""
        if msg.get("status") == "pending":
            status_icon = " ⏳"
        elif outgoing and msg.get("status") == "read":
            status_icon = " ✔✔"
        elif outgoing and msg.get("status") == "sent":
            status_icon = " ✔"

        self.canvas.create_text(
            x2 if outgoing else x1, y + bubble_h + 2,
            text=ts_str + status_icon, font=self._ts_font, fill="#888888",
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
                if msg.get("type") not in ("text", "file") or msg.get("status") == "recalled":
                    return
                menu = tk.Menu(self, tearoff=0)
                if self.on_reply:
                    menu.add_command(
                        label="↩️ پاسخ",
                        command=lambda m=msg: self.on_reply(m),
                    )
                if outgoing and msg.get("status") in ("sent", "read", "pending"):
                    menu.add_command(
                        label="🚫 لغو ارسال / حذف برای همه",
                        command=lambda m=msg: self.on_recall(m),
                    )
                if menu.index("end") is not None:
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
