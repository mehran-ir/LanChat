# -*- coding: utf-8 -*-
"""
نمایش Badge (شمارنده پیام‌های خوانده‌نشده) روی آیکون برنامه در نوار وظیفه (Taskbar)
ویندوز، با استفاده از رابط COM رسمی ITaskbarList3 (همان مکانیزمی که برنامه‌هایی
مثل Teams/Telegram برای نمایش عدد پیام‌های نخوانده روی آیکون‌شان استفاده می‌کنند).

اگر comtypes یا Pillow در دسترس نباشد، یا هر خطای غیرمنتظره‌ای رخ دهد، این ماژول
کاملاً بی‌صدا (no-op) عمل می‌کند تا هرگز باعث خطا در بقیه برنامه نشود.
"""
import os
import sys
import tempfile

IS_WINDOWS = sys.platform.startswith("win")
_available = False

if IS_WINDOWS:
    try:
        import ctypes
        from ctypes import wintypes
        import comtypes
        import comtypes.client
        from comtypes import GUID, COMMETHOD, HRESULT, IUnknown
        from PIL import Image, ImageDraw, ImageFont
        _available = True
    except Exception:
        _available = False

if _available:
    CLSID_TaskbarList = GUID("{56FDF344-FD6D-11D0-958A-006097C9A090}")
    IID_ITaskbarList3 = GUID("{EA1AFB91-9E28-4B86-90E9-9E9F8A5EEFAF}")

    class ITaskbarList3(IUnknown):
        _iid_ = IID_ITaskbarList3
        _methods_ = [
            COMMETHOD([], HRESULT, "HrInit"),
            COMMETHOD([], HRESULT, "AddTab", (["in"], wintypes.HWND, "hwnd")),
            COMMETHOD([], HRESULT, "DeleteTab", (["in"], wintypes.HWND, "hwnd")),
            COMMETHOD([], HRESULT, "ActivateTab", (["in"], wintypes.HWND, "hwnd")),
            COMMETHOD([], HRESULT, "SetActiveAlt", (["in"], wintypes.HWND, "hwnd")),
            COMMETHOD([], HRESULT, "MarkFullscreenWindow",
                      (["in"], wintypes.HWND, "hwnd"), (["in"], wintypes.BOOL, "fFullscreen")),
            COMMETHOD([], HRESULT, "SetProgressValue",
                      (["in"], wintypes.HWND, "hwnd"),
                      (["in"], ctypes.c_ulonglong, "ullCompleted"),
                      (["in"], ctypes.c_ulonglong, "ullTotal")),
            COMMETHOD([], HRESULT, "SetProgressState",
                      (["in"], wintypes.HWND, "hwnd"), (["in"], ctypes.c_int, "tbpFlags")),
            COMMETHOD([], HRESULT, "RegisterTab",
                      (["in"], wintypes.HWND, "hwndTab"), (["in"], wintypes.HWND, "hwndMDI")),
            COMMETHOD([], HRESULT, "UnregisterTab", (["in"], wintypes.HWND, "hwndTab")),
            COMMETHOD([], HRESULT, "SetTabOrder",
                      (["in"], wintypes.HWND, "hwndTab"), (["in"], wintypes.HWND, "hwndInsertBefore")),
            COMMETHOD([], HRESULT, "SetTabActive",
                      (["in"], wintypes.HWND, "hwndTab"), (["in"], wintypes.HWND, "hwndMDI"),
                      (["in"], ctypes.c_int, "tbatFlags")),
            COMMETHOD([], HRESULT, "ThumbBarAddButtons",
                      (["in"], wintypes.HWND, "hwnd"), (["in"], wintypes.UINT, "cButtons"),
                      (["in"], ctypes.c_void_p, "pButtons")),
            COMMETHOD([], HRESULT, "ThumbBarUpdateButtons",
                      (["in"], wintypes.HWND, "hwnd"), (["in"], wintypes.UINT, "cButtons"),
                      (["in"], ctypes.c_void_p, "pButtons")),
            COMMETHOD([], HRESULT, "ThumbBarSetImageList",
                      (["in"], wintypes.HWND, "hwnd"), (["in"], ctypes.c_void_p, "himl")),
            COMMETHOD([], HRESULT, "SetOverlayIcon",
                      (["in"], wintypes.HWND, "hwnd"), (["in"], wintypes.HICON, "hIcon"),
                      (["in"], wintypes.LPCWSTR, "pszDescription")),
            COMMETHOD([], HRESULT, "SetThumbnailTooltip",
                      (["in"], wintypes.HWND, "hwnd"), (["in"], wintypes.LPCWSTR, "pszTip")),
            COMMETHOD([], HRESULT, "SetThumbnailClip",
                      (["in"], wintypes.HWND, "hwnd"), (["in"], ctypes.c_void_p, "prcClip")),
        ]

    _taskbar_obj = [None]
    _icon_cache = {}
    _co_initialized = [False]

    def _get_taskbar():
        if _taskbar_obj[0] is None:
            if not _co_initialized[0]:
                try:
                    comtypes.CoInitialize()
                except Exception:
                    pass
                _co_initialized[0] = True
            obj = comtypes.client.CreateObject(CLSID_TaskbarList, interface=ITaskbarList3)
            obj.HrInit()
            _taskbar_obj[0] = obj
        return _taskbar_obj[0]

    def _render_badge_icon(count: int, size: int = 32):
        cache_key = count if count <= 99 else 100
        if cache_key in _icon_cache:
            return _icon_cache[cache_key]

        text = str(count) if count <= 99 else "99+"
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.ellipse((0, 0, size - 1, size - 1), fill=(211, 47, 47, 255))

        font_size = int(size * 0.55) if len(text) <= 2 else int(size * 0.36)
        try:
            font_path = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "segoeuib.ttf")
            font = ImageFont.truetype(font_path, font_size)
        except Exception:
            font = ImageFont.load_default()

        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text(((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1]), text, font=font, fill=(255, 255, 255, 255))
        except Exception:
            draw.text((size * 0.2, size * 0.15), text, font=font, fill=(255, 255, 255, 255))

        fd, path = tempfile.mkstemp(suffix=".ico")
        os.close(fd)
        hicon = None
        try:
            img.save(path, format="ICO", sizes=[(size, size)])
            IMAGE_ICON = 1
            LR_LOADFROMFILE = 0x00000010
            hicon = ctypes.windll.user32.LoadImageW(None, path, IMAGE_ICON, size, size, LR_LOADFROMFILE)
        except Exception:
            hicon = None
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

        _icon_cache[cache_key] = hicon
        return hicon

    def set_badge(hwnd_int: int, count: int):
        """
        عدد count را روی آیکون برنامه در Taskbar نمایش می‌دهد.
        count برابر یا کمتر از صفر یعنی حذف کامل Badge.
        """
        try:
            taskbar = _get_taskbar()
            hwnd = wintypes.HWND(hwnd_int)
            if count and count > 0:
                hicon = _render_badge_icon(count)
                if not hicon:
                    return
                taskbar.SetOverlayIcon(hwnd, hicon, f"{count} پیام خوانده‌نشده")
            else:
                taskbar.SetOverlayIcon(hwnd, 0, None)
        except Exception as e:
            print(f"خطا در نمایش Badge روی Taskbar: {e}")

else:
    def set_badge(hwnd_int: int, count: int):
        pass
