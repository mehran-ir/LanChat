# -*- coding: utf-8 -*-
"""
ماژول کشف کامپیوترها در شبکه محلی با استفاده از UDP Broadcast
"""
import select
import socket
import threading
import time

from utils import get_hostname, get_local_ip, get_broadcast_addresses, get_all_local_ips

DISCOVERY_PORT = 54545
MAGIC = "LANCHAT"


def start_responder(tcp_port: int, stop_event: threading.Event, get_display_name=None):
    """
    یک ترد که همیشه در پس‌زمینه اجرا می‌شود و به درخواست‌های کشف کامپیوترهای دیگر پاسخ می‌دهد.
    get_display_name: تابعی بدون آرگومان که نام نمایشی فعلی را برمی‌گرداند (اگر کاربر
    بعداً نامش را عوض کند، بدون نیاز به راه‌اندازی مجدد این ترد، نام جدید اعمال می‌شود).
    اگر داده نشود، از نام کامپیوتر (hostname) استفاده می‌شود.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except (AttributeError, OSError):
        pass  # در ویندوز SO_REUSEPORT وجود ندارد
    sock.bind(("", DISCOVERY_PORT))
    sock.settimeout(1.0)

    def current_name():
        if get_display_name:
            try:
                return get_display_name() or get_hostname()
            except Exception:
                return get_hostname()
        return get_hostname()

    while not stop_event.is_set():
        try:
            data, addr = sock.recvfrom(1024)
        except socket.timeout:
            continue
        except OSError:
            break

        try:
            text = data.decode("utf-8", errors="ignore")
        except Exception:
            continue

        parts = text.split("|")
        if len(parts) >= 2 and parts[0] == MAGIC and parts[1] == "DISCOVER":
            # پاسخ می‌دهیم: نام نمایشی فعلی + پورت TCP که برای چت گوش می‌دهیم
            reply = f"{MAGIC}|RESPONSE|{current_name()}|{tcp_port}"
            try:
                sock.sendto(reply.encode("utf-8"), addr)
            except Exception:
                pass

    sock.close()


def scan_network(tcp_port: int, timeout: float = 2.5, retransmits: int = 4, display_name: str = None) -> list:
    """
    درخواست کشف را به کل شبکه Broadcast می‌کند و پاسخ‌ها را جمع‌آوری می‌کند.
    برای قابلیت‌اطمینان بیشتر:
      - از تمام کارت‌های شبکه فعال کامپیوتر ارسال می‌شود (نه فقط اینترفیس پیش‌فرض)
      - چندبار طی بازه اسکن تکرار می‌شود (چون UDP Broadcast می‌تواند گم شود)
    خروجی: لیستی از دیکشنری {"name": ..., "ip": ..., "port": ...}
    """
    results = {}
    my_ip = get_local_ip()
    local_ips = set(get_all_local_ips())
    local_ips.add(my_ip)

    message = f"{MAGIC}|DISCOVER|{display_name or get_hostname()}|{tcp_port}".encode("utf-8")
    broadcast_targets = get_broadcast_addresses()

    sockets = []
    for local_ip in local_ips:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.bind((local_ip, 0))
            s.setblocking(False)
            sockets.append(s)
        except Exception:
            continue

    if not sockets:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            s.setblocking(False)
            sockets.append(s)
        except Exception:
            return []

    def broadcast_once():
        for s in sockets:
            for addr in broadcast_targets:
                try:
                    s.sendto(message, (addr, DISCOVERY_PORT))
                except Exception:
                    pass

    retransmits = max(retransmits, 1)
    interval = timeout / retransmits
    broadcast_once()
    remaining_retransmits = retransmits - 1
    next_retransmit = time.time() + interval

    end_time = time.time() + timeout
    while time.time() < end_time:
        if remaining_retransmits > 0 and time.time() >= next_retransmit:
            broadcast_once()
            remaining_retransmits -= 1
            next_retransmit += interval

        try:
            readable, _, _ = select.select(sockets, [], [], 0.2)
        except Exception:
            break

        for s in readable:
            try:
                data, addr = s.recvfrom(1024)
            except Exception:
                continue
            try:
                text = data.decode("utf-8", errors="ignore")
            except Exception:
                continue

            parts = text.split("|")
            if len(parts) >= 4 and parts[0] == MAGIC and parts[1] == "RESPONSE":
                name = parts[2]
                port = int(parts[3])
                ip = addr[0]
                if ip in local_ips:
                    continue  # خودمان را در لیست نشان نمی‌دهیم
                results[ip] = {"name": name, "ip": ip, "port": port}

    for s in sockets:
        try:
            s.close()
        except Exception:
            pass

    return list(results.values())


def probe_single_ip(ip: str, tcp_port: int, timeout: float = 2.0, display_name: str = None):
    """
    برای افزودن دستی یک کامپیوتر با آی‌پی مشخص: تلاش می‌کند نام آن را با ارسال یک
    درخواست کشف مستقیم (unicast) به همان آی‌پی پیدا کند.
    خروجی: دیکشنری {"name":..., "ip":..., "port":...} یا None در صورت عدم پاسخ.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    message = f"{MAGIC}|DISCOVER|{display_name or get_hostname()}|{tcp_port}".encode("utf-8")
    try:
        sock.sendto(message, (ip, DISCOVERY_PORT))
        data, addr = sock.recvfrom(1024)
        text = data.decode("utf-8", errors="ignore")
        parts = text.split("|")
        if len(parts) >= 4 and parts[0] == MAGIC and parts[1] == "RESPONSE":
            return {"name": parts[2], "ip": addr[0], "port": int(parts[3])}
    except Exception:
        pass
    finally:
        sock.close()
    return None
