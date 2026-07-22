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

_EMOJI_RANGES = (
    (0x1F300, 0x1FAFF),  # پیکتوگرام‌ها، صورتک‌ها، حمل‌ونقل، نمادها
    (0x2600, 0x27BF),    # نمادهای متفرقه و دینگبت
    (0x1F1E6, 0x1F1FF),  # پرچم‌ها (حروف منطقه‌ای)
    (0x1F900, 0x1F9FF),
    (0x2190, 0x21FF),    # فلش‌ها (گاهی به‌صورت ایموجی استفاده می‌شوند)
)
_ZWJ = "\u200d"
_VARIATION_SELECTOR = "\ufe0f"


def _is_emoji_codepoint(cp: int) -> bool:
    if cp in (ord(_ZWJ), ord(_VARIATION_SELECTOR)):
        return True
    for lo, hi in _EMOJI_RANGES:
        if lo <= cp <= hi:
            return True
    return False


def split_emoji_clusters(text: str):
    """
    متن را به «خوشه‌های» ایموجی می‌شکند؛ دنباله‌های به‌هم‌پیوسته با ZWJ (مثل ایموجی خانواده)
    یا همراه با variation selector، یک خوشه واحد در نظر گرفته می‌شوند تا درست رندر شوند.
    """
    clusters = []
    current = ""
    for ch in text:
        if ch == " ":
            continue
        if ch in (_ZWJ, _VARIATION_SELECTOR):
            current += ch
            continue
        if current and current[-1] == _ZWJ:
            current += ch
            continue
        if current:
            clusters.append(current)
        current = ch
    if current:
        clusters.append(current)
    return clusters


def is_emoji_only(text: str, max_clusters: int = 10) -> bool:
    """آیا متن فقط شامل ایموجی است (و طول قابل قبولی دارد)؟"""
    if not text or not text.strip():
        return False
    stripped = text.replace(" ", "")
    for ch in stripped:
        if not _is_emoji_codepoint(ord(ch)):
            return False
    clusters = split_emoji_clusters(text)
    return 0 < len(clusters) <= max_clusters


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
