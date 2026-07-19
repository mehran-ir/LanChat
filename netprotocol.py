# -*- coding: utf-8 -*-
"""
پروتکل ساده برای ارسال/دریافت پیام متنی و فایل روی TCP
قالب فریم:
    [4 بایت طول هدر (big-endian)] [هدر JSON] [در صورت فایل: بایت‌های خام فایل]
"""
import json
import os
import socket
import struct

HEADER_LEN_SIZE = 4
CHUNK_SIZE = 65536


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    """دقیقا n بایت از سوکت می‌خواند (ممکن است در چند مرحله برسد)"""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(min(CHUNK_SIZE, n - len(buf)))
        if not chunk:
            raise ConnectionError("اتصال قبل از تکمیل دریافت داده قطع شد")
        buf.extend(chunk)
    return bytes(buf)


def send_message(sock: socket.socket, from_name: str, text: str):
    header = {"type": "msg", "from": from_name, "text": text}
    header_bytes = json.dumps(header, ensure_ascii=False).encode("utf-8")
    sock.sendall(struct.pack(">I", len(header_bytes)))
    sock.sendall(header_bytes)


def send_file(sock: socket.socket, from_name: str, filepath: str, progress_cb=None):
    filesize = os.path.getsize(filepath)
    filename = os.path.basename(filepath)
    header = {
        "type": "file",
        "from": from_name,
        "filename": filename,
        "filesize": filesize,
    }
    header_bytes = json.dumps(header, ensure_ascii=False).encode("utf-8")
    sock.sendall(struct.pack(">I", len(header_bytes)))
    sock.sendall(header_bytes)

    sent = 0
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(CHUNK_SIZE)
            if not chunk:
                break
            sock.sendall(chunk)
            sent += len(chunk)
            if progress_cb:
                progress_cb(sent, filesize)


def recv_frame(sock: socket.socket, save_dir: str):
    """
    یک فریم کامل را از سوکت می‌خواند.
    اگر پیام متنی باشد -> {"type": "msg", "from":..., "text":...}
    اگر فایل باشد -> فایل را در save_dir ذخیره می‌کند و
        {"type": "file", "from":..., "filename":..., "filesize":..., "path":...} برمی‌گرداند
    """
    header_len_bytes = _recv_exact(sock, HEADER_LEN_SIZE)
    (header_len,) = struct.unpack(">I", header_len_bytes)
    header_bytes = _recv_exact(sock, header_len)
    header = json.loads(header_bytes.decode("utf-8"))

    if header.get("type") == "file":
        os.makedirs(save_dir, exist_ok=True)
        filename = header.get("filename", "received_file")
        # جلوگیری از رونویسی فایل‌های هم‌نام
        base, ext = os.path.splitext(filename)
        dest_path = os.path.join(save_dir, filename)
        counter = 1
        while os.path.exists(dest_path):
            dest_path = os.path.join(save_dir, f"{base}({counter}){ext}")
            counter += 1

        remaining = header.get("filesize", 0)
        with open(dest_path, "wb") as f:
            while remaining > 0:
                chunk = sock.recv(min(CHUNK_SIZE, remaining))
                if not chunk:
                    raise ConnectionError("اتصال حین دریافت فایل قطع شد")
                f.write(chunk)
                remaining -= len(chunk)

        header["path"] = dest_path
        return header

    return header
