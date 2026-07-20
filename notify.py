# -*- coding: utf-8 -*-
"""
نمایش نوتیفیکیشن (Popup / Balloon) در ویندوز هنگام دریافت پیام، وقتی برنامه
Minimize شده یا فوکوس ندارد. فقط با ctypes پیاده‌سازی شده (بدون نیاز به pip install).
در سیستم‌عامل‌های غیر از ویندوز، به‌صورت بی‌اثر (no-op) عمل می‌کند.
"""
import sys
import threading

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
    NIIF_INFO = 0x00000001
    WM_USER = 0x0400
    WM_TRAYICON = WM_USER + 20

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

    _uid_counter = [1]

    def show_notification(title: str, message: str, hwnd_int: int, duration_ms: int = 5000):
        """یک بالن نوتیفیکیشن کنار ساعت ویندوز نمایش می‌دهد و پس از چند ثانیه حذف می‌کند."""

        def worker():
            try:
                shell32 = ctypes.windll.shell32
                user32 = ctypes.windll.user32

                hwnd = wintypes.HWND(hwnd_int)
                uid = _uid_counter[0]
                _uid_counter[0] += 1

                nid = NOTIFYICONDATA()
                nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
                nid.hWnd = hwnd
                nid.uID = uid
                nid.uFlags = NIF_INFO | NIF_ICON | NIF_MESSAGE | NIF_TIP
                nid.uCallbackMessage = WM_TRAYICON
                nid.hIcon = user32.LoadIconW(None, ctypes.c_void_p(32512))  # IDI_APPLICATION
                nid.szTip = "LAN Chat"
                nid.szInfo = message[:255]
                nid.szInfoTitle = title[:63]
                nid.dwInfoFlags = NIIF_INFO
                nid.uTimeoutOrVersion = duration_ms

                shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))

                import time
                time.sleep(duration_ms / 1000.0 + 1)

                shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
            except Exception as e:
                print(f"خطا در نمایش نوتیفیکیشن: {e}")

        threading.Thread(target=worker, daemon=True).start()

else:
    def show_notification(title: str, message: str, hwnd_int: int, duration_ms: int = 5000):
        # روی سیستم‌عامل‌های غیر ویندوز کاری انجام نمی‌شود
        pass
