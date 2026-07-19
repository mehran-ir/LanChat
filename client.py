# -*- coding: utf-8 -*-
"""
توابع کلاینت: اتصال به کامپیوتر مقصد و ارسال پیام یا فایل
"""
import socket

from netprotocol import send_message as _send_message, send_file as _send_file


def send_message(ip: str, port: int, from_name: str, text: str, timeout: float = 5.0):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((ip, port))
        sock.settimeout(None)
        _send_message(sock, from_name, text)
    finally:
        sock.close()


def send_file(ip: str, port: int, from_name: str, filepath: str, progress_cb=None, timeout: float = 5.0):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((ip, port))
        sock.settimeout(None)
        _send_file(sock, from_name, filepath, progress_cb=progress_cb)
    finally:
        sock.close()
