# -*- coding: utf-8 -*-
"""
پالت رنگی برنامه و محاسبه رنگ متن مناسب (روشن/تیره) بر اساس روشنایی پس‌زمینه
"""

DEFAULT_THEME = "#F5F5F5"
THEME_OPTIONS = ["#F5F5F5", "#FFDDF4", "#1E1E1E", "#ACE1AF"]

# رنگ پیش‌فرض خود باکس نمایش گفتگو — سفید
DEFAULT_CHATBOX_COLOR = "#FFFFFF"

THEME_NAMES = {
    "#F5F5F5": "خاکستری روشن (پیش‌فرض)",
    "#FFDDF4": "صورتی",
    "#1E1E1E": "تیره (Dark)",
    "#ACE1AF": "سبز",
}

# پالت رنگی دکمه‌ها — عمداً محدود به فقط ۳ رنگ هماهنگ برای حفظ توازن بصری برنامه:
# یک رنگ اصلی برای اکثر عملیات، یک خاکستری خنثی برای عملیات کم‌اهمیت‌تر،
# و قرمز فقط و فقط برای عملیات حذف/غیرقابل‌بازگشت (برای وضوح و امنیت داده).
BUTTON_PALETTE = {
    "primary": "#3AAFA9",   # فیروزه‌ای آرام — همه عملیات اصلی/مثبت (ارسال، اسکن، ایجاد، بازر و...)
    "neutral": "#8A94A6",   # خاکستری‌آبی ملایم — عملیات خنثی (بستن، لغو، بازگشت به حالت پیش‌فرض)
    "danger": "#E15554",    # قرمز — فقط برای حذف/عملیات غیرقابل‌بازگشت
}


def hex_to_rgb(hex_color: str):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def relative_luminance(hex_color: str) -> float:
    r, g, b = hex_to_rgb(hex_color)
    return 0.299 * r + 0.587 * g + 0.114 * b


def contrast_text_color(hex_color: str) -> str:
    """برای پس‌زمینه روشن، متن تیره؛ برای پس‌زمینه تیره، متن روشن برمی‌گرداند"""
    return "#101010" if relative_luminance(hex_color) > 140 else "#f5f5f5"


def shade(hex_color: str, factor: float) -> str:
    """رنگ را کمی روشن‌تر یا تیره‌تر می‌کند. factor مثبت = روشن‌تر، منفی = تیره‌تر (بازه تقریبی -1..1)"""
    r, g, b = hex_to_rgb(hex_color)
    if factor >= 0:
        r = int(r + (255 - r) * factor)
        g = int(g + (255 - g) * factor)
        b = int(b + (255 - b) * factor)
    else:
        r = int(r * (1 + factor))
        g = int(g * (1 + factor))
        b = int(b * (1 + factor))
    r, g, b = max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b))
    return f"#{r:02x}{g:02x}{b:02x}"
