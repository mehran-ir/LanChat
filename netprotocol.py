# -*- coding: utf-8 -*-
"""
پروتکل ارسال/دریافت پیام، فایل، لغو پیام (recall) و بازر (buzz) روی TCP
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
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(min(CHUNK_SIZE, n - len(buf)))
        if not chunk:
            raise ConnectionError("اتصال قبل از تکمیل دریافت داده قطع شد")
        buf.extend(chunk)
    return bytes(buf)


def _send_header_only(sock: socket.socket, header: dict):
    header_bytes = json.dumps(header, ensure_ascii=False).encode("utf-8")
    sock.sendall(struct.pack(">I", len(header_bytes)))
    sock.sendall(header_bytes)


def send_message(sock: socket.socket, from_name: str, text: str, msg_id: str,
                  group_id: str = None, group_name: str = None, members: list = None):
    header = {"type": "msg", "from": from_name, "text": text, "id": msg_id}
    if group_id:
        header["group_id"] = group_id
        header["group_name"] = group_name
        header["members"] = members
    _send_header_only(sock, header)


def send_file(sock: socket.socket, from_name: str, filepath: str, msg_id: str,
              group_id: str = None, group_name: str = None, members: list = None,
              progress_cb=None):
    filesize = os.path.getsize(filepath)
    filename = os.path.basename(filepath)
    header = {
        "type": "file",
        "from": from_name,
        "filename": filename,
        "filesize": filesize,
        "id": msg_id,
    }
    if group_id:
        header["group_id"] = group_id
        header["group_name"] = group_name
        header["members"] = members

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


def send_recall(sock: socket.socket, from_name: str, target_id: str, group_id: str = None):
    header = {"type": "recall", "from": from_name, "target_id": target_id}
    if group_id:
        header["group_id"] = group_id
    _send_header_only(sock, header)


def send_buzz(sock: socket.socket, from_name: str, group_id: str = None):
    header = {"type": "buzz", "from": from_name}
    if group_id:
        header["group_id"] = group_id
    _send_header_only(sock, header)


def recv_frame(sock: socket.socket, save_dir: str):
    """
    یک فریم کامل را از سوکت می‌خواند و دیکشنری هدر را برمی‌گرداند.
    برای نوع 'file'، فایل را در save_dir ذخیره کرده و مسیر آن را در header['path'] می‌گذارد.
    """
    header_len_bytes = _recv_exact(sock, HEADER_LEN_SIZE)
    (header_len,) = struct.unpack(">I", header_len_bytes)
    header_bytes = _recv_exact(sock, header_len)
    header = json.loads(header_bytes.decode("utf-8"))

    if header.get("type") == "file":
        os.makedirs(save_dir, exist_ok=True)
        filename = header.get("filename", "received_file")
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
