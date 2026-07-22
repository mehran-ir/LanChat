# -*- coding: utf-8 -*-
"""
آیکون برنامه در Tray (کنار ساعت ویندوز) با منوی کلیک‌راست «باز کردن» و «خروج».
از کتابخانه پایدار و تست‌شده pystray استفاده می‌کند تا نیازی به دستکاری دستی و
پرریسک پیام‌های سطح پایین ویندوز نباشد.

اگر pystray یا Pillow نصب نباشند (یا سیستم‌عامل ویندوز نباشد)، start() مقدار
False برمی‌گرداند و برنامه باید به رفتار عادی (بستن کامل با دکمه X) برگردد.
"""
import sys
import threading

IS_WINDOWS = sys.platform.startswith("win")

try:
    import pystray
    from PIL import Image, ImageDraw
    HAVE_PYSTRAY = True
except Exception:
    HAVE_PYSTRAY = False


def _make_icon_image(size: int = 64):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((2, 2, size - 2, size - 2), fill=(15, 145, 145, 255))
    draw.ellipse(
        (size * 0.24, size * 0.28, size * 0.76, size * 0.60),
        fill=(255, 255, 255, 255),
    )
    draw.polygon(
        [
            (size * 0.32, size * 0.58),
            (size * 0.46, size * 0.58),
            (size * 0.30, size * 0.74),
        ],
        fill=(255, 255, 255, 255),
    )
    return img


class TrayIcon:
    def __init__(self, on_open=None, on_quit=None, tooltip="LanChat by MGH"):
        self.on_open = on_open
        self.on_quit = on_quit
        self.tooltip = tooltip
        self.icon = None
        self.thread = None

    def start(self) -> bool:
        if not HAVE_PYSTRAY:
            return False
        try:
            image = _make_icon_image()
            menu = pystray.Menu(
                pystray.MenuItem("باز کردن LanChat", self._handle_open, default=True),
                pystray.MenuItem("خروج", self._handle_quit),
            )
            self.icon = pystray.Icon("lanchat_by_mgh", image, self.tooltip, menu)
            self.thread = threading.Thread(target=self._run_safe, daemon=True)
            self.thread.start()
            return True
        except Exception:
            return False

    def _run_safe(self):
        try:
            self.icon.run()
        except Exception:
            pass

    def _handle_open(self, icon, item):
        if self.on_open:
            try:
                self.on_open()
            except Exception:
                pass

    def _handle_quit(self, icon, item):
        if self.on_quit:
            try:
                self.on_quit()
            except Exception:
                pass

    def stop(self):
        if self.icon:
            try:
                self.icon.stop()
            except Exception:
                pass
