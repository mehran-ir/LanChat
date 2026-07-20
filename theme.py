# -*- coding: utf-8 -*-
"""
پالت رنگی برنامه و محاسبه رنگ متن مناسب (روشن/تیره) بر اساس روشنایی پس‌زمینه
"""

DEFAULT_THEME = "#E0FFFF"
THEME_OPTIONS = ["#E0FFFF", "#FFDDF4", "#010B13", "#ACE1AF"]

# رنگ پیش‌فرض خود باکس نمایش گفتگو — عمداً از رنگ زمینه کلی برنامه متفاوت است
DEFAULT_CHATBOX_COLOR = "#F0F8FF"

THEME_NAMES = {
    "#E0FFFF": "آبی روشن (پیش‌فرض)",
    "#FFDDF4": "صورتی",
    "#010B13": "تیره",
    "#ACE1AF": "سبز",
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
