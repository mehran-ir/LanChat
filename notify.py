# -*- coding: utf-8 -*-
"""
نمایش نوتیفیکیشن (Toast/Popup) در ویندوز هنگام دریافت پیام، وقتی برنامه
Minimize شده یا فوکوس ندارد. فقط با ctypes پیاده‌سازی شده (بدون نیاز به pip install).
در سیستم‌عامل‌های غیر از ویندوز، به‌صورت بی‌اثر (no-op) عمل می‌کند.

نکته فنی: نسخه قبلی این فایل یک باگ داشت — توابع ویندوزی LoadIconW و
Shell_NotifyIconW بدون تعریف دقیق نوع بازگشتی (restype/argtypes) فراخوانی
می‌شدند. در ویندوز ۶۴ بیتی، ctypes به‌صورت پیش‌فرض مقدار بازگشتی را ۳۲ بیتی
در نظر می‌گیرد که باعث می‌شد handle آیکن (HICON) قطع (truncate) شود و
Shell_NotifyIconW به‌طور بی‌صدا شکست بخورد. این نسخه آن مشکل را رفع کرده و
از توالی NIM_ADD -> NIM_SETVERSION -> NIM_MODIFY استفاده می‌کند که روش
مستند و قابل‌اعتماد برای نمایش Toast در Action Center ویندوز ۱۰/۱۱ است.
"""
import sys
import threading
import time

IS_WINDOWS = sys.platform.startswith("win")

if IS_WINDOWS:
    import ctypes
    from ctypes import wintypes

    NIF_INFO = 0x00000010
    NIF_ICON = 0x00000002
    NIF_MESSAGE = 0x00000001
    NIF_TIP = 0x00000004
    NIM_ADD = 0x00000000
    NIM_MODIFY = 0x00000001
    NIM_DELETE = 0x00000002
    NIM_SETVERSION = 0x00000004
    NIIF_INFO = 0x00000001
    NOTIFYICON_VERSION_4 = 4
    WM_USER = 0x0400
    WM_TRAYICON = WM_USER + 20
    IDI_APPLICATION = 32512

    class NOTIFYICONDATA(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("hWnd", wintypes.HWND),
            ("uID", wintypes.UINT),
            ("uFlags", wintypes.UINT),
            ("uCallbackMessage", wintypes.UINT),
            ("hIcon", wintypes.HICON),
            ("szTip", wintypes.WCHAR * 128),
            ("dwState", wintypes.DWORD),
            ("dwStateMask", wintypes.DWORD),
            ("szInfo", wintypes.WCHAR * 256),
            ("uTimeoutOrVersion", wintypes.UINT),
            ("szInfoTitle", wintypes.WCHAR * 64),
            ("dwInfoFlags", wintypes.DWORD),
        ]

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    shell32 = ctypes.WinDLL("shell32", use_last_error=True)

    # تعریف دقیق نوع آرگومان‌ها و مقدار بازگشتی — رفع باگ اصلی
    user32.LoadIconW.restype = wintypes.HICON
    user32.LoadIconW.argtypes = [wintypes.HINSTANCE, wintypes.LPCWSTR]

    shell32.Shell_NotifyIconW.restype = wintypes.BOOL
    shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.POINTER(NOTIFYICONDATA)]

    _uid_counter = [1]
    _app_icon_cache = [None]

    def _load_app_icon():
        if _app_icon_cache[0] is None:
            try:
                # MAKEINTRESOURCE(IDI_APPLICATION) به‌صورت صحیح برای ctypes
                icon_res = ctypes.cast(IDI_APPLICATION, wintypes.LPCWSTR)
                _app_icon_cache[0] = user32.LoadIconW(None, icon_res)
            except Exception:
                _app_icon_cache[0] = None
        return _app_icon_cache[0]

    def show_notification(title: str, message: str, hwnd_int: int, duration_ms: int = 5000):
        """یک نوتیفیکیشن Toast کنار ساعت ویندوز نمایش می‌دهد و پس از چند ثانیه حذف می‌کند."""

        def worker():
            try:
                hwnd = wintypes.HWND(hwnd_int) if hwnd_int else wintypes.HWND(0)
                uid = _uid_counter[0]
                _uid_counter[0] += 1
                hicon = _load_app_icon()

                nid = NOTIFYICONDATA()
                nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
                nid.hWnd = hwnd
                nid.uID = uid
                nid.uCallbackMessage = WM_TRAYICON
                nid.hIcon = hicon if hicon else 0
                nid.szTip = "LanChat by MGH"

                # مرحله ۱: افزودن آیکن به‌صورت پایه
                nid.uFlags = NIF_ICON | NIF_TIP | NIF_MESSAGE
                ok = shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))
                if not ok:
                    print(f"Shell_NotifyIconW(NIM_ADD) failed, error={ctypes.get_last_error()}")
                    return

                # مرحله ۲: فعال‌سازی رفتار مدرن (Toast در Action Center)
                nid.uTimeoutOrVersion = NOTIFYICON_VERSION_4
                shell32.Shell_NotifyIconW(NIM_SETVERSION, ctypes.byref(nid))

                # مرحله ۳: نمایش متن نوتیفیکیشن
                nid.uFlags = NIF_INFO
                nid.szInfo = (message or "")[:255]
                nid.szInfoTitle = (title or "")[:63]
                nid.dwInfoFlags = NIIF_INFO
                ok2 = shell32.Shell_NotifyIconW(NIM_MODIFY, ctypes.byref(nid))
                if not ok2:
                    print(f"Shell_NotifyIconW(NIM_MODIFY) failed, error={ctypes.get_last_error()}")

                time.sleep(max(duration_ms, 4000) / 1000.0 + 1.5)

                nid.uFlags = 0
                shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
            except Exception as e:
                print(f"خطا در نمایش نوتیفیکیشن: {e}")

        threading.Thread(target=worker, daemon=True).start()

else:
    def show_notification(title: str, message: str, hwnd_int: int, duration_ms: int = 5000):
        # روی سیستم‌عامل‌های غیر ویندوز کاری انجام نمی‌شود
        pass
