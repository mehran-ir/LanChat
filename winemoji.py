# -*- coding: utf-8 -*-
"""
باز کردن پنل ایموجی رنگی رسمی ویندوز (همان پنلی که با کلید ترکیبی Win + . باز می‌شود)
با شبیه‌سازی همان کلید ترکیبی. این کار تضمین می‌کند ایموجی‌های نمایش داده‌شده دقیقاً
همان ایموجی‌های رنگی رسمی ویندوز باشند، چون Tkinter به‌تنهایی نمی‌تواند گلیف‌های رنگی
فونت Segoe UI Emoji را رندر کند.
"""
import sys

IS_WINDOWS = sys.platform.startswith("win")

if IS_WINDOWS:
    import ctypes

    VK_LWIN = 0x5B
    VK_OEM_PERIOD = 0xBE
    KEYEVENTF_KEYUP = 0x0002

    def open_windows_emoji_panel() -> bool:
        """
        کلید ترکیبی Win + . را به‌صورت برنامه‌نویسی فشار و رها می‌کند تا پنل ایموجی
        رنگی رسمی ویندوز، دقیقاً کنار مکان‌نمای فعلی، باز شود. ایموجی انتخاب‌شده توسط
        کاربر مستقیماً در همان جعبه متنی که فوکوس دارد (پیام‌رسان) تایپ می‌شود.
        """
        try:
            user32 = ctypes.windll.user32
            user32.keybd_event(VK_LWIN, 0, 0, 0)
            user32.keybd_event(VK_OEM_PERIOD, 0, 0, 0)
            user32.keybd_event(VK_OEM_PERIOD, 0, KEYEVENTF_KEYUP, 0)
            user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)
            return True
        except Exception:
            return False

else:
    def open_windows_emoji_panel() -> bool:
        return False
