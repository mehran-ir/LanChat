# -*- coding: utf-8 -*-
"""
ماژول کشف کامپیوترها در شبکه محلی با استفاده از UDP Broadcast
"""
import socket
import threading
import time

from utils import get_hostname, get_local_ip, get_broadcast_addresses

DISCOVERY_PORT = 54545
MAGIC = "LANCHAT"


def start_responder(tcp_port: int, stop_event: threading.Event):
    """
    یک ترد که همیشه در پس‌زمینه اجرا می‌شود و به درخواست‌های کشف کامپیوترهای دیگر پاسخ می‌دهد.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    except (AttributeError, OSError):
        pass  # در ویندوز SO_REUSEPORT وجود ندارد
    sock.bind(("", DISCOVERY_PORT))
    sock.settimeout(1.0)

    my_hostname = get_hostname()

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
            # پاسخ می‌دهیم: نام کامپیوتر خودمان + پورت TCP که برای چت گوش می‌دهیم
            reply = f"{MAGIC}|RESPONSE|{my_hostname}|{tcp_port}"
            try:
                sock.sendto(reply.encode("utf-8"), addr)
            except Exception:
                pass

    sock.close()


def scan_network(tcp_port: int, timeout: float = 2.5) -> list:
    """
    درخواست کشف را به کل شبکه Broadcast می‌کند و پاسخ‌ها را جمع‌آوری می‌کند.
    خروجی: لیستی از دیکشنری {"name": ..., "ip": ..., "port": ...}
    """
    results = {}
    my_ip = get_local_ip()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(0.3)

    message = f"{MAGIC}|DISCOVER|{get_hostname()}|{tcp_port}".encode("utf-8")

    for addr in get_broadcast_addresses():
        try:
            sock.sendto(message, (addr, DISCOVERY_PORT))
        except Exception:
            pass

    end_time = time.time() + timeout
    while time.time() < end_time:
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
        if len(parts) >= 4 and parts[0] == MAGIC and parts[1] == "RESPONSE":
            name = parts[2]
            port = int(parts[3])
            ip = addr[0]
            if ip == my_ip:
                continue  # خودمان را در لیست نشان نمی‌دهیم
            results[ip] = {"name": name, "ip": ip, "port": port}

    sock.close()
    return list(results.values())


def probe_single_ip(ip: str, tcp_port: int, timeout: float = 2.0):
    """
    برای افزودن دستی یک کامپیوتر با آی‌پی مشخص: تلاش می‌کند نام آن را با ارسال یک
    درخواست کشف مستقیم (unicast) به همان آی‌پی پیدا کند.
    خروجی: دیکشنری {"name":..., "ip":..., "port":...} یا None در صورت عدم پاسخ.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(timeout)
    message = f"{MAGIC}|DISCOVER|{get_hostname()}|{tcp_port}".encode("utf-8")
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
