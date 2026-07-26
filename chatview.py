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
from tkinter import ttk, messagebox

from jalali import jalali_datetime_str
from theme import contrast_text_color, DEFAULT_CHATBOX_COLOR
from emoji_render import get_emoji_icon, is_emoji_only, split_emoji_clusters

try:
    from PIL import Image, ImageTk
    HAVE_PIL = True
except Exception:
    HAVE_PIL = False

BUBBLE_WIDTH = 340
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}


def _is_image_file(path):
    if not path:
        return False
    return os.path.splitext(path)[1].lower() in IMAGE_EXTENSIONS


def _hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


class ChatView(tk.Frame):
    def __init__(self, parent, on_recall, on_open_file, theme_color="#AFEEEE",
                 box_color=None, on_reply=None, on_show_in_folder=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.on_recall = on_recall
        self.on_open_file = on_open_file
        self.on_reply = on_reply
        self.on_show_in_folder = on_show_in_folder
        self.theme_color = theme_color
        self.box_color = box_color or DEFAULT_CHATBOX_COLOR
        self._thumb_cache = {}
        self._glass_cache = {}

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

            if (
                msg.get("type") == "file"
                and status in ("sent", "read")
                and not msg.get("reply_to")
                and _is_image_file(msg.get("path"))
            ):
                y = self._draw_image_bubble(y, msg, outgoing, sender, chat.is_group)
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

    def _get_glass_bubble_image(self, width, height, base_hex, border_hex, radius=16):
        """
        تصویر شیشه‌ای/کریستالی برای پس‌زمینه‌ی حباب پیام می‌سازد: گوشه‌های گرد،
        گرادیان عمودی نرم، و یک جلوه‌ی براقی (Shine) بالای حباب.
        """
        width = max(int(width), 2 * radius + 4)
        height = max(int(height), 2 * radius + 4)
        key = (width, height, base_hex, border_hex, radius)
        if key in self._glass_cache:
            return self._glass_cache[key]

        photo = None
        try:
            base_rgb = _hex_to_rgb(base_hex)
            light_rgb = tuple(min(255, c + 45) for c in base_rgb)

            grad = Image.new("RGB", (1, height))
            for y in range(height):
                t = y / max(height - 1, 1)
                rgb = tuple(int(light_rgb[i] * (1 - t) + base_rgb[i] * t) for i in range(3))
                grad.putpixel((0, y), rgb)
            grad = grad.resize((width, height))

            mask = Image.new("L", (width, height), 0)
            ImageDraw.Draw(mask).rounded_rectangle((0, 0, width - 1, height - 1), radius=radius, fill=255)

            img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            img.paste(grad, (0, 0), mask)

            shine = Image.new("RGBA", (width, height), (0, 0, 0, 0))
            ImageDraw.Draw(shine).ellipse(
                (-width * 0.15, -height * 0.7, width * 0.85, height * 0.45), fill=(255, 255, 255, 60)
            )
            shine.putalpha(Image.composite(shine.split()[3], Image.new("L", (width, height), 0), mask))
            img = Image.alpha_composite(img, shine)

            border_rgb = _hex_to_rgb(border_hex)
            ImageDraw.Draw(img).rounded_rectangle(
                (0, 0, width - 1, height - 1), radius=radius, outline=border_rgb + (200,), width=1
            )
            photo = ImageTk.PhotoImage(img)
        except Exception:
            photo = None

        self._glass_cache[key] = photo
        return photo

    def _draw_bubble_background(self, x1, y, x2, bottom_y, base_color, border_color):
        """پس‌زمینه‌ی حباب پیام را با جلوه‌ی کریستالی رسم می‌کند (یا در نبود Pillow، مستطیل ساده)"""
        width = x2 - x1
        height = bottom_y - y
        photo = self._get_glass_bubble_image(width, height, base_color, border_color) if HAVE_PIL else None
        if photo:
            self._photo_refs.append(photo)
            return self.canvas.create_image(x1, y, image=photo, anchor="nw", tags=("msg",))
        return self.canvas.create_rectangle(
            x1, y, x2, bottom_y, fill=base_color, outline=border_color, width=1, tags=("msg",)
        )

    def _load_thumbnail(self, path, max_w=220, max_h=220):
        try:
            mtime = os.path.getmtime(path)
        except Exception:
            return None
        key = (path, max_w, max_h, mtime)
        if key in self._thumb_cache:
            return self._thumb_cache[key]
        photo = None
        try:
            if HAVE_PIL:
                img = Image.open(path)
                img = img.convert("RGB") if img.mode not in ("RGB", "RGBA") else img
                img.thumbnail((max_w, max_h))
                photo = ImageTk.PhotoImage(img)
            else:
                photo = tk.PhotoImage(file=path)
                factor = max(1, photo.width() // max_w, photo.height() // max_h)
                if factor > 1:
                    photo = photo.subsample(factor, factor)
        except Exception:
            photo = None
        self._thumb_cache[key] = photo
        return photo

    def _draw_image_bubble(self, y, msg, outgoing, sender, is_group):
        """پیام‌های حاوی فایل تصویری را با پیش‌نمایش کوچک شبیه واتساپ نشان می‌دهد"""
        w = max(self.canvas.winfo_width(), 200)
        pad = 6
        path = msg.get("path")
        thumb = self._load_thumbnail(path) if path and os.path.exists(path) else None

        header_text = sender if (is_group and not outgoing) else ""
        header_h = (self._header_font.metrics("linespace") + 3) if header_text else 0
        header_w = self._header_font.measure(header_text) if header_text else 0

        if thumb:
            img_w, img_h = thumb.width(), thumb.height()
        else:
            img_w, img_h = 200, 50

        bubble_w = max(img_w, header_w) + pad * 2
        bubble_h = header_h + img_h + pad * 2

        if outgoing:
            x2 = w - 20
            x1 = x2 - bubble_w
        else:
            x1 = 20
            x2 = x1 + bubble_w

        bubble_color = "#dcf8dc" if outgoing else "#ffffff"
        outline_color = "#8fd98f" if outgoing else "#bbbbbb"
        rect_id = self._draw_bubble_background(x1, y, x2, y + bubble_h, bubble_color, outline_color)

        cursor_y = y + pad
        if header_text:
            self.canvas.create_text(
                x1 + pad, cursor_y, text=header_text, font=self._header_font,
                anchor="nw", fill="#0a6f6f", tags=("msg",),
            )
            cursor_y += header_h

        if thumb:
            self._photo_refs.append(thumb)
            img_id = self.canvas.create_image(x1 + pad, cursor_y, image=thumb, anchor="nw", tags=("msg",))
            self.canvas.tag_bind(img_id, "<Button-1>", lambda e, p=path: self._open_image_zoom(p))
            if rect_id is not None:
                self.canvas.tag_bind(rect_id, "<Button-1>", lambda e, p=path: self._open_image_zoom(p))
            try:
                self.canvas.itemconfigure(img_id, cursor="hand2")
            except Exception:
                pass
        else:
            self.canvas.create_text(
                x1 + pad, cursor_y, text="🖼 تصویر در دسترس نیست", font=self._body_font,
                anchor="nw", fill="#999999", tags=("msg",),
            )

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

    def _open_image_zoom(self, path):
        """پنجره بزرگ‌نمایی تصویر با دکمه بستن و نمایش در پوشه"""
        if not path or not os.path.exists(path):
            messagebox.showerror("خطا", "فایل تصویر دیگر در دسترس نیست.")
            return

        top = tk.Toplevel(self)
        top.title(os.path.basename(path))
        top.configure(bg="#1a1a1a")

        try:
            if HAVE_PIL:
                img = Image.open(path)
                max_w, max_h = 900, 650
                ratio = min(max_w / img.width, max_h / img.height, 1.0)
                new_size = (max(1, int(img.width * ratio)), max(1, int(img.height * ratio)))
                img = img.resize(new_size)
                photo = ImageTk.PhotoImage(img)
            else:
                photo = tk.PhotoImage(file=path)
        except Exception as e:
            top.destroy()
            messagebox.showerror("خطا", f"نمایش تصویر ممکن نشد:\n{e}")
            return

        top._photo_ref = photo  # جلوگیری از garbage collection

        img_label = tk.Label(top, image=photo, bg="#1a1a1a")
        img_label.pack(padx=10, pady=(10, 4))

        btns = tk.Frame(top, bg="#1a1a1a")
        btns.pack(fill="x", padx=10, pady=(0, 10))

        tk.Button(
            btns, text="✕ بستن", command=top.destroy,
            bg="#e53935", fg="#ffffff", relief="flat", padx=12, pady=4,
        ).pack(side="left")

        def show_folder():
            if self.on_show_in_folder:
                self.on_show_in_folder(path)

        tk.Button(
            btns, text="📁 نمایش در پوشه", command=show_folder,
            bg="#4a90d9", fg="#ffffff", relief="flat", padx=12, pady=4,
        ).pack(side="right")

        top.bind("<Escape>", lambda e: top.destroy())
        top.transient(self.winfo_toplevel())
        top.focus_set()

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
        self._draw_bubble_background(x1, y, x2, y + bubble_h, bubble_color, outline_color)

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
