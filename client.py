# -*- coding: utf-8 -*-
"""
توابع کلاینت: اتصال به کامپیوتر مقصد و ارسال پیام، فایل، لغو پیام یا بازر (buzz)
"""
import socket

from netprotocol import (
    send_message as _send_message,
    send_file as _send_file,
    send_recall as _send_recall,
    send_buzz as _send_buzz,
)


def send_message(ip: str, port: int, from_name: str, text: str, msg_id: str,
                  group_id=None, group_name=None, members=None, timeout: float = 5.0):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((ip, port))
        sock.settimeout(None)
        _send_message(sock, from_name, text, msg_id, group_id, group_name, members)
    finally:
        sock.close()


def send_file(ip: str, port: int, from_name: str, filepath: str, msg_id: str,
              group_id=None, group_name=None, members=None, progress_cb=None, timeout: float = 5.0):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((ip, port))
        sock.settimeout(None)
        _send_file(sock, from_name, filepath, msg_id, group_id, group_name, members, progress_cb=progress_cb)
    finally:
        sock.close()


def send_recall(ip: str, port: int, from_name: str, target_id: str, group_id=None, timeout: float = 5.0):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((ip, port))
        sock.settimeout(None)
        _send_recall(sock, from_name, target_id, group_id)
    finally:
        sock.close()


def send_buzz(ip: str, port: int, from_name: str, group_id=None, timeout: float = 5.0):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((ip, port))
        sock.settimeout(None)
        _send_buzz(sock, from_name, group_id)
    finally:
        sock.close()
