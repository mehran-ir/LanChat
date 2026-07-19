# -*- coding: utf-8 -*-
"""
رابط گرافیکی برنامه چت تحت شبکه محلی (LAN Chat)
"""
import os
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from datetime import datetime

from utils import get_hostname, get_local_ip
from discovery import start_responder, scan_network, probe_single_ip, DISCOVERY_PORT
from server import ChatServer, TCP_PORT
import client


def resource_base_dir():
    """پوشه محل اجرای برنامه (سازگار با PyInstaller --onefile)"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


RECEIVED_DIR = os.path.join(resource_base_dir(), "received_files")


class Contact:
    def __init__(self, name, ip, port):
        self.name = name
        self.ip = ip
        self.port = port
        self.history = []  # لیستی از (زمان, فرستنده, متن)

    @property
    def key(self):
        return f"{self.ip}:{self.port}"

    @property
    def display(self):
        return f"{self.name}  ({self.ip})"


class LANChatApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.my_name = get_hostname()
        self.my_ip = get_local_ip()

        self.root.title(f"LAN Chat - {self.my_name}")
        self.root.geometry("880x560")
        self.root.minsize(700, 450)

        self.contacts = {}  # key(ip:port) -> Contact
        self.selected_key = None
        self.incoming_queue = queue.Queue()

        os.makedirs(RECEIVED_DIR, exist_ok=True)

        self._build_ui()
        self._start_networking()
        self._poll_queue()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------------------------------------------------------------- UI ---
    def _build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass

        top_bar = ttk.Frame(self.root, padding=8)
        top_bar.pack(side="top", fill="x")

        ttk.Label(
            top_bar,
            text=f"این کامپیوتر: {self.my_name}   ({self.my_ip})",
            font=("Tahoma", 10, "bold"),
        ).pack(side="right")

        main = ttk.Frame(self.root)
        main.pack(fill="both", expand=True)

        # --- پنل چپ: لیست کامپیوترها ---
        left = ttk.Frame(main, padding=6, width=260)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        ttk.Label(left, text="کامپیوترهای شبکه", font=("Tahoma", 10, "bold")).pack(
            anchor="e", pady=(0, 6)
        )

        self.contact_listbox = tk.Listbox(left, font=("Tahoma", 10), activestyle="dotbox")
        self.contact_listbox.pack(fill="both", expand=True)
        self.contact_listbox.bind("<<ListboxSelect>>", self._on_select_contact)

        btns = ttk.Frame(left)
        btns.pack(fill="x", pady=6)

        self.scan_btn = ttk.Button(btns, text="اسکن شبکه", command=self._on_scan_clicked)
        self.scan_btn.pack(side="right", expand=True, fill="x", padx=2)

        self.add_btn = ttk.Button(btns, text="افزودن دستی", command=self._on_add_manual)
        self.add_btn.pack(side="right", expand=True, fill="x", padx=2)

        self.open_folder_btn = ttk.Button(
            left, text="باز کردن پوشه فایل‌های دریافتی", command=self._open_received_folder
        )
        self.open_folder_btn.pack(fill="x", pady=(6, 0))

        self.status_label = ttk.Label(left, text="آماده", foreground="#1a7a1a")
        self.status_label.pack(fill="x", pady=(8, 0))

        # --- پنل راست: چت ---
        right = ttk.Frame(main, padding=6)
        right.pack(side="right", fill="both", expand=True)

        self.chat_title = ttk.Label(right, text="یک کامپیوتر را انتخاب کنید", font=("Tahoma", 11, "bold"))
        self.chat_title.pack(anchor="e", pady=(0, 6))

        self.chat_text = tk.Text(
            right, state="disabled", wrap="word", font=("Tahoma", 10), padx=8, pady=8
        )
        self.chat_text.pack(fill="both", expand=True)
        self.chat_text.tag_configure("me", foreground="#0a5fb4", justify="right")
        self.chat_text.tag_configure("other", foreground="#1a1a1a", justify="right")
        self.chat_text.tag_configure("sys", foreground="#888888", justify="center")
        self.chat_text.tag_configure("time", foreground="#999999", font=("Tahoma", 8))

        bottom = ttk.Frame(right)
        bottom.pack(fill="x", pady=(8, 0))

        self.msg_entry = ttk.Entry(bottom, font=("Tahoma", 10), justify="right")
        self.msg_entry.pack(side="right", fill="x", expand=True, padx=(6, 6))
        self.msg_entry.bind("<Return>", lambda e: self._on_send_message())

        self.send_btn = ttk.Button(bottom, text="ارسال", command=self._on_send_message)
        self.send_btn.pack(side="right")

        self.file_btn = ttk.Button(bottom, text="ارسال فایل", command=self._on_send_file)
        self.file_btn.pack(side="left")

    # --------------------------------------------------------- NETWORKING ---
    def _start_networking(self):
        self._stop_event = threading.Event()

        self.responder_thread = threading.Thread(
            target=start_responder, args=(TCP_PORT, self._stop_event), daemon=True
        )
        self.responder_thread.start()

        self.server = ChatServer(
            on_message_received=self._on_message_received_threadsafe,
            save_dir=RECEIVED_DIR,
            port=TCP_PORT,
        )
        self.server.start()

        # یک اسکن اولیه خودکار هنگام باز شدن برنامه
        self.root.after(400, self._on_scan_clicked)

    def _on_message_received_threadsafe(self, header):
        # این تابع از یک ترد جداگانه (سرور) صدا زده می‌شود؛ فقط داده را در صف می‌گذاریم
        self.incoming_queue.put(header)

    def _poll_queue(self):
        try:
            while True:
                header = self.incoming_queue.get_nowait()
                self._handle_incoming(header)
        except queue.Empty:
            pass
        self.root.after(200, self._poll_queue)

    def _handle_incoming(self, header):
        ip = header.get("ip")
        from_name = header.get("from", ip)
        key = None
        # سعی می‌کنیم مخاطب موجود با همین آی‌پی را پیدا کنیم
        for k, c in self.contacts.items():
            if c.ip == ip:
                key = k
                break
        if key is None:
            contact = Contact(from_name, ip, TCP_PORT)
            key = contact.key
            self.contacts[key] = contact
            self._refresh_contact_list()

        contact = self.contacts[key]
        contact.name = from_name  # به‌روزرسانی نام در صورت تغییر

        if header.get("type") == "msg":
            contact.history.append((datetime.now(), from_name, header.get("text", "")))
        elif header.get("type") == "file":
            filename = header.get("filename", "فایل")
            path = header.get("path", "")
            text = f"📎 فایل دریافت شد: {filename}\n({path})"
            contact.history.append((datetime.now(), from_name, text))

        if key == self.selected_key:
            self._render_chat(contact)
        else:
            self._refresh_contact_list(highlight_key=key)

    # ------------------------------------------------------------ ACTIONS ---
    def _on_scan_clicked(self):
        self.status_label.config(text="در حال اسکن شبکه...", foreground="#b46a00")
        self.scan_btn.config(state="disabled")

        def worker():
            found = scan_network(TCP_PORT, timeout=2.5)
            self.root.after(0, lambda: self._on_scan_done(found))

        threading.Thread(target=worker, daemon=True).start()

    def _on_scan_done(self, found):
        added = 0
        for item in found:
            contact = Contact(item["name"], item["ip"], item["port"])
            if contact.key not in self.contacts:
                self.contacts[contact.key] = contact
                added += 1
        self._refresh_contact_list()
        self.scan_btn.config(state="normal")
        self.status_label.config(
            text=f"اسکن پایان یافت — {added} کامپیوتر جدید یافت شد", foreground="#1a7a1a"
        )

    def _on_add_manual(self):
        ip = simpledialog.askstring("افزودن دستی", "آدرس IP کامپیوتر مقصد را وارد کنید:", parent=self.root)
        if not ip:
            return
        ip = ip.strip()

        self.status_label.config(text=f"در حال بررسی {ip} ...", foreground="#b46a00")

        def worker():
            info = probe_single_ip(ip, TCP_PORT, timeout=2.5)
            self.root.after(0, lambda: self._on_probe_done(ip, info))

        threading.Thread(target=worker, daemon=True).start()

    def _on_probe_done(self, ip, info):
        if info:
            contact = Contact(info["name"], info["ip"], info["port"])
        else:
            # پاسخی نیامد؛ همچنان با نام IP اضافه می‌کنیم (شاید برنامه دیگر روی پورت پیش‌فرض گوش می‌دهد)
            contact = Contact(ip, ip, TCP_PORT)
            messagebox.showwarning(
                "بدون پاسخ",
                f"کامپیوتر {ip} به درخواست شناسایی پاسخ نداد.\n"
                "با این حال به لیست اضافه شد؛ مطمئن شوید LAN Chat روی آن سیستم اجرا و فایروال آن اجازه می‌دهد.",
            )
        if contact.key not in self.contacts:
            self.contacts[contact.key] = contact
            self._refresh_contact_list()
        self.status_label.config(text="آماده", foreground="#1a7a1a")

    def _refresh_contact_list(self, highlight_key=None):
        self.contact_listbox.delete(0, "end")
        self._contact_keys_in_order = list(self.contacts.keys())
        for key in self._contact_keys_in_order:
            c = self.contacts[key]
            label = c.display
            if highlight_key == key and key != self.selected_key:
                label = "🔵 " + label
            self.contact_listbox.insert("end", label)
            if key == self.selected_key:
                idx = self._contact_keys_in_order.index(key)
                self.contact_listbox.selection_set(idx)

    def _on_select_contact(self, event):
        sel = self.contact_listbox.curselection()
        if not sel:
            return
        key = self._contact_keys_in_order[sel[0]]
        self.selected_key = key
        contact = self.contacts[key]
        self.chat_title.config(text=f"گفتگو با {contact.name} ({contact.ip})")
        self._render_chat(contact)
        self._refresh_contact_list()

    def _render_chat(self, contact: Contact):
        self.chat_text.config(state="normal")
        self.chat_text.delete("1.0", "end")
        for ts, sender, text in contact.history:
            time_str = ts.strftime("%H:%M")
            who = "من" if sender == self.my_name else sender
            self.chat_text.insert("end", f"[{time_str}] ", "time")
            tag = "me" if sender == self.my_name else "other"
            self.chat_text.insert("end", f"{who}: {text}\n", tag)
        self.chat_text.config(state="disabled")
        self.chat_text.see("end")

    def _on_send_message(self):
        if not self.selected_key:
            messagebox.showinfo("انتخاب مقصد", "ابتدا یک کامپیوتر را از لیست انتخاب کنید.")
            return
        text = self.msg_entry.get().strip()
        if not text:
            return
        contact = self.contacts[self.selected_key]
        self.msg_entry.delete(0, "end")

        def worker():
            try:
                client.send_message(contact.ip, contact.port, self.my_name, text)
                contact.history.append((datetime.now(), self.my_name, text))
                self.root.after(0, lambda: self._render_chat(contact) if self.selected_key == contact.key else None)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("خطا در ارسال", f"ارسال پیام ناموفق بود:\n{e}"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_send_file(self):
        if not self.selected_key:
            messagebox.showinfo("انتخاب مقصد", "ابتدا یک کامپیوتر را از لیست انتخاب کنید.")
            return
        filepath = filedialog.askopenfilename(title="انتخاب فایل برای ارسال")
        if not filepath:
            return
        contact = self.contacts[self.selected_key]
        filename = os.path.basename(filepath)

        self.status_label.config(text=f"در حال ارسال {filename} ...", foreground="#b46a00")

        def progress_cb(sent, total):
            percent = int(sent * 100 / total) if total else 100
            self.root.after(0, lambda: self.status_label.config(text=f"ارسال {filename}: {percent}%"))

        def worker():
            try:
                client.send_file(contact.ip, contact.port, self.my_name, filepath, progress_cb=progress_cb)
                contact.history.append((datetime.now(), self.my_name, f"📎 فایل ارسال شد: {filename}"))
                self.root.after(0, lambda: (
                    self._render_chat(contact) if self.selected_key == contact.key else None,
                    self.status_label.config(text="آماده", foreground="#1a7a1a"),
                ))
            except Exception as e:
                self.root.after(0, lambda: (
                    messagebox.showerror("خطا در ارسال فایل", f"ارسال فایل ناموفق بود:\n{e}"),
                    self.status_label.config(text="آماده", foreground="#1a7a1a"),
                ))

        threading.Thread(target=worker, daemon=True).start()

    def _open_received_folder(self):
        os.makedirs(RECEIVED_DIR, exist_ok=True)
        try:
            if sys.platform.startswith("win"):
                os.startfile(RECEIVED_DIR)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                os.system(f'open "{RECEIVED_DIR}"')
            else:
                os.system(f'xdg-open "{RECEIVED_DIR}"')
        except Exception as e:
            messagebox.showerror("خطا", f"باز کردن پوشه ممکن نشد:\n{e}")

    def _on_close(self):
        self._stop_event.set()
        self.server.stop()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = LANChatApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
