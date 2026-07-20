# -*- coding: utf-8 -*-
"""
رندر ایموجی‌های رنگی واقعی ویندوز (همان فونت Segoe UI Emoji که با کلید میانبر
Win + . نمایش داده می‌شود) به‌صورت تصویر، برای استفاده در دکمه‌های Tkinter.

Tkinter به‌طور پیش‌فرض نمی‌تواند گلیف‌های رنگی فونت‌های Emoji را نمایش دهد و
آن‌ها را به‌صورت تک‌رنگ/خطی رسم می‌کند. این ماژول با Pillow و پارامتر
embedded_color، مستقیماً از فونت رنگی نصب‌شده روی ویندوز رندر می‌کند.

اگر Pillow نصب نباشد یا فونت پیدا نشود (مثلاً روی سیستم‌عامل دیگر)، به‌صورت
شفاف None برمی‌گرداند تا کد فراخوان از یک دکمه متنی معمولی استفاده کند.
"""
import os
import sys

try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
    HAVE_PIL = True
except Exception:
    HAVE_PIL = False

_image_cache = {}
_font_cache = {}


def _find_emoji_font_path():
    windir = os.environ.get("WINDIR", r"C:\Windows")
    candidates = [
        os.path.join(windir, "Fonts", "seguiemj.ttf"),   # Segoe UI Emoji (ویندوز ۱۰/۱۱)
        os.path.join(windir, "Fonts", "seguiemoji.ttf"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def _get_font(px_size: int):
    if px_size in _font_cache:
        return _font_cache[px_size]
    font = None
    if HAVE_PIL and sys.platform.startswith("win"):
        font_path = _find_emoji_font_path()
        if font_path:
            try:
                font = ImageFont.truetype(font_path, px_size)
            except Exception:
                font = None
    _font_cache[px_size] = font
    return font


def get_emoji_icon(emoji_char: str, size: int = 28):
    """
    تصویر PhotoImage رنگی برای یک ایموجی برمی‌گرداند (نتیجه کش می‌شود).
    اگر رندر رنگی ممکن نباشد، None برمی‌گرداند.
    """
    key = (emoji_char, size)
    if key in _image_cache:
        return _image_cache[key]

    font = _get_font(size)
    if font is None:
        _image_cache[key] = None
        return None

    try:
        canvas_size = size + 8
        img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        try:
            # embedded_color=True دقیقاً همان مکانیزمی است که رنگ واقعی
            # ایموجی‌های ویندوز (Segoe UI Emoji) را رندر می‌کند
            draw.text((4, 4), emoji_char, font=font, embedded_color=True)
        except TypeError:
            # پشتیبانی برای نسخه‌های قدیمی‌تر Pillow که این پارامتر را ندارند
            draw.text((4, 4), emoji_char, font=font, fill=(0, 0, 0, 255))
        photo = ImageTk.PhotoImage(img)
        _image_cache[key] = photo
        return photo
    except Exception:
        _image_cache[key] = None
        return None
