# -*- coding: utf-8 -*-
"""
سرور TCP: به ازای هر پیام یا فایل ورودی، یک اتصال جدید پذیرفته و پردازش می‌شود.
"""
import os
import socket
import threading

from netprotocol import recv_frame

TCP_PORT = 54546


class ChatServer(threading.Thread):
    def __init__(self, on_message_received, save_dir, port: int = TCP_PORT):
        super().__init__(daemon=True)
        self.port = port
        self.on_message_received = on_message_received
        self.save_dir = save_dir
        self._stop_event = threading.Event()
        self._server_sock = None

    def run(self):
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind(("", self.port))
        self._server_sock.listen(20)
        self._server_sock.settimeout(1.0)

        while not self._stop_event.is_set():
            try:
                conn, addr = self._server_sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            t = threading.Thread(
                target=self._handle_connection, args=(conn, addr), daemon=True
            )
            t.start()

        self._server_sock.close()

    def _handle_connection(self, conn: socket.socket, addr):
        try:
            header = recv_frame(conn, self.save_dir)
            header["ip"] = addr[0]
            self.on_message_received(header)
        except Exception as e:
            print(f"خطا در دریافت پیام از {addr}: {e}")
        finally:
            conn.close()

    def stop(self):
        self._stop_event.set()
