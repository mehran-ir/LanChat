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
    send_read as _send_read,
    send_group_update as _send_group_update,
    send_presence as _send_presence,
)


def send_message(ip: str, port: int, from_name: str, text: str, msg_id: str,
                  group_id=None, group_name=None, members=None, timeout: float = 5.0,
                  reply_to=None, reply_sender=None, reply_text=None, admin_ip=None):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((ip, port))
        sock.settimeout(None)
        _send_message(sock, from_name, text, msg_id, group_id, group_name, members,
                      reply_to, reply_sender, reply_text, admin_ip)
    finally:
        sock.close()


def send_file(ip: str, port: int, from_name: str, filepath: str, msg_id: str,
              group_id=None, group_name=None, members=None, progress_cb=None, timeout: float = 5.0,
              admin_ip=None):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((ip, port))
        sock.settimeout(None)
        _send_file(sock, from_name, filepath, msg_id, group_id, group_name, members,
                   progress_cb=progress_cb, admin_ip=admin_ip)
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


def send_presence(ip: str, port: int, from_name: str, status: str, timeout: float = 1.0):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((ip, port))
        sock.settimeout(None)
        _send_presence(sock, from_name, status)
    finally:
        sock.close()


def send_read(ip: str, port: int, from_name: str, message_ids: list, group_id=None, timeout: float = 5.0):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((ip, port))
        sock.settimeout(None)
        _send_read(sock, from_name, message_ids, group_id)
    finally:
        sock.close()


def send_group_update(ip: str, port: int, from_name: str, group_id: str, group_name: str,
                       members: list, admin_ip: str, timeout: float = 5.0):
    """فقط ادمین گروه این را برای اطلاع‌رسانی لیست کامل و نهایی اعضا به یک عضو خاص می‌فرستد"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((ip, port))
        sock.settimeout(None)
        _send_group_update(sock, from_name, group_id, group_name, members, admin_ip)
    finally:
        sock.close()
