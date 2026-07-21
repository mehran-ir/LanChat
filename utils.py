# -*- coding: utf-8 -*-
"""
توابع کمکی برای دریافت نام کامپیوتر و آی‌پی محلی
"""
import socket
import platform


def get_hostname() -> str:
    """نام کامپیوتر فعلی را برمی‌گرداند (همان نامی که در شبکه ویندوز نمایش داده می‌شود)"""
    try:
        return platform.node() or socket.gethostname()
    except Exception:
        return "Unknown-PC"


def get_local_ip() -> str:
    """آی‌پی محلی کامپیوتر را در شبکه پیدا می‌کند (بدون نیاز به اتصال واقعی به اینترنت)"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # به یک آی‌پی خارجی "وصل" می‌شویم (بدون ارسال داده واقعی) تا اینترفیس صحیح پیدا شود
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def get_all_local_ips() -> list:
    """
    آی‌پی تمام کارت‌های شبکه فعال کامپیوتر را برمی‌گرداند (نه فقط اینترفیس پیش‌فرض).
    این برای کامپیوترهایی که چند کارت شبکه دارند (مثلاً هم Wi-Fi هم اترنت، یا
    آداپتور مجازی VPN/VMware/Hyper-V) مهم است تا Broadcast از همه فرستاده شود.
    """
    ips = set()
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        pass
    try:
        ips.add(get_local_ip())
    except Exception:
        pass
    return list(ips) if ips else ["0.0.0.0"]


def get_broadcast_addresses() -> list:
    """
    تلاش برای یافتن آدرس broadcast شبکه‌های محلی متصل.
    اگر نتوانستیم، از broadcast عمومی 255.255.255.255 استفاده می‌کنیم.
    """
    addresses = set()
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if ip.startswith("127."):
                continue
            parts = ip.split(".")
            if len(parts) == 4:
                # فرض بر subnet مسک /24 (رایج‌ترین حالت در شبکه‌های خانگی/اداری کوچک)
                broadcast = ".".join(parts[:3] + ["255"])
                addresses.add(broadcast)
    except Exception:
        pass
    addresses.add("255.255.255.255")
    return list(addresses)
