# -*- coding: utf-8 -*-
"""
رابط گرافیکی برنامه چت تحت شبکه محلی (LAN Chat) — نسخه کامل
"""
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from utils import get_hostname, get_local_ip
from discovery import start_responder, scan_network, probe_single_ip
from server import ChatServer, TCP_PORT
import client
import jalali
import notify
import soundfx
import persistence
from chatmodel import ChatEntry, make_message, new_id
from chatview import ChatView
from theme import DEFAULT_THEME, THEME_OPTIONS, contrast_text_color

EMOJIS = [
    "😀", "😂", "😍", "👍", "👎", "🙏", "🎉", "❤️",
    "😢", "😮", "🔥", "👏", "🤔", "😅", "🙌", "💯",
    "😡", "🥳", "😴", "🤝", "✅", "❌", "⏰", "🔔",
    "🥰", "😊", "🙁", "💪", "👋", "📎", "🎂", "☕",
]


def resource_base_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = resource_base_dir()
RECEIVED_DIR = os.path.join(BASE_DIR, "received_files")
STATE_PATH = os.path.join(BASE_DIR, "lanchat_data.json")


class LANChatApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.my_name = get_hostname()
        self.my_ip = get_local_ip()

        self.root.title(f"LanChat by MGH - {self.my_name}")
        self.root.geometry("980x620")
        self.root.minsize(760, 480)

        os.makedirs(RECEIVED_DIR, exist_ok=True)

        raw_state = persistence.load_state(STATE_PATH)
        self.contacts = {k: ChatEntry.from_dict(v) for k, v in raw_state.get("contacts", {}).items()}
        self.groups = {k: ChatEntry.from_dict(v) for k, v in raw_state.get("groups", {}).items()}
        self.theme_color = raw_state.get("settings", {}).get("theme_color", DEFAULT_THEME)

        self.selected_key = None
        self.incoming_queue = queue.Queue()
        self.pending_sends = {}
        self._contact_keys_in_order = []
        self._has_focus = True

        self._build_ui()
        self._apply_theme_to_widgets()
        self._start_networking()
        self._poll_queue()
        self._update_clock()

        self.root.bind("<FocusIn>", lambda e: setattr(self, "_has_focus", True))
        self.root.bind("<FocusOut>", lambda e: setattr(self, "_has_focus", False))
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

        # --- گوشه بالا سمت چپ: تاریخ شمسی و ساعت تهران ---
        clock_frame = ttk.Frame(top_bar)
        clock_frame.pack(side="left")
        self.date_label = ttk.Label(clock_frame, font=("Tahoma", 9, "bold"))
        self.date_label.pack(anchor="w")
        self.time_label = ttk.Label(clock_frame, font=("Tahoma", 9))
        self.time_label.pack(anchor="w")

        # --- سمت راست: نام کامپیوتر + دکمه دایره‌ای انتخاب تم ---
        right_top = ttk.Frame(top_bar)
        right_top.pack(side="right")
        ttk.Label(
            right_top, text=f"این کامپیوتر: {self.my_name}   ({self.my_ip})",
            font=("Tahoma", 10, "bold"),
        ).pack(side="right", padx=(8, 0))

        self.theme_btn_canvas = tk.Canvas(right_top, width=30, height=30, highlightthickness=0)
        self.theme_btn_canvas.pack(side="right")
        self._draw_theme_button()
        self.theme_btn_canvas.bind("<Button-1>", lambda e: self._open_theme_popup())

        main = ttk.Frame(self.root)
        main.pack(fill="both", expand=True)

        # ============================================================ LEFT
        left = ttk.Frame(main, padding=6, width=270)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        ttk.Label(left, text="کامپیوترها و گروه‌ها", font=("Tahoma", 10, "bold")).pack(anchor="e")

        self.contact_search_var = tk.StringVar()
        search_entry = ttk.Entry(left, textvariable=self.contact_search_var, justify="right")
        search_entry.pack(fill="x", pady=(4, 4))
        search_entry.bind("<KeyRelease>", lambda e: self._refresh_contact_list())
        self._add_placeholder(search_entry, "جستجوی نام کامپیوتر...")

        self.contact_listbox = tk.Listbox(left, font=("Tahoma", 10), activestyle="dotbox")
        self.contact_listbox.pack(fill="both", expand=True)
        self.contact_listbox.bind("<<ListboxSelect>>", self._on_select_contact)

        btns = ttk.Frame(left)
        btns.pack(fill="x", pady=6)
        ttk.Button(btns, text="اسکن شبکه", command=self._on_scan_clicked).pack(side="right", expand=True, fill="x", padx=2)
        ttk.Button(btns, text="افزودن دستی", command=self._on_add_manual).pack(side="right", expand=True, fill="x", padx=2)

        ttk.Button(left, text="👥 ایجاد گروه جدید", command=self._on_create_group).pack(fill="x", pady=(0, 4))
        ttk.Button(left, text="باز کردن پوشه فایل‌های دریافتی", command=self._open_received_folder).pack(fill="x")

        self.status_label = ttk.Label(left, text="آماده", foreground="#1a7a1a")
        self.status_label.pack(fill="x", pady=(8, 0))

        # =========================================================== RIGHT
        right = ttk.Frame(main, padding=6)
        right.pack(side="right", fill="both", expand=True)

        self.chat_title = ttk.Label(right, text="یک کامپیوتر یا گروه را انتخاب کنید", font=("Tahoma", 11, "bold"))
        self.chat_title.pack(anchor="e", pady=(0, 4))

        toolbar = ttk.Frame(right)
        toolbar.pack(fill="x", pady=(0, 4))

        ttk.Button(toolbar, text="🗑 پاک کردن تاریخچه", command=self._on_clear_history).pack(side="right", padx=2)
        ttk.Button(toolbar, text="🔔 بازر", command=self._on_send_buzz).pack(side="right", padx=2)
        ttk.Button(toolbar, text="🖼 تصویر پس‌زمینه", command=self._on_choose_chat_bg).pack(side="right", padx=2)
        ttk.Button(toolbar, text="حذف پس‌زمینه", command=self._on_remove_chat_bg).pack(side="right", padx=2)

        self.chat_search_var = tk.StringVar()
        chat_search_entry = ttk.Entry(toolbar, textvariable=self.chat_search_var, justify="right", width=22)
        chat_search_entry.pack(side="left", padx=(0, 4))
        chat_search_entry.bind("<KeyRelease>", self._on_chat_search)
        self._add_placeholder(chat_search_entry, "جستجو در این گفتگو...")
        self.search_result_label = ttk.Label(toolbar, text="")
        self.search_result_label.pack(side="left")

        self.chatview = ChatView(
            right, on_recall=self._handle_recall_click, on_open_file=self._open_path,
            theme_color=self.theme_color,
        )
        self.chatview.pack(fill="both", expand=True)

        bottom = ttk.Frame(right)
        bottom.pack(fill="x", pady=(8, 0))

        self.emoji_btn = ttk.Button(bottom, text="😊", width=3, command=self._open_emoji_picker)
        self.emoji_btn.pack(side="left")

        self.file_btn = ttk.Button(bottom, text="ارسال فایل", command=self._on_send_file)
        self.file_btn.pack(side="left", padx=(4, 0))

        self.send_btn = ttk.Button(bottom, text="ارسال", command=self._on_send_message)
        self.send_btn.pack(side="right")

        self.msg_entry = ttk.Entry(bottom, font=("Tahoma", 10), justify="right")
        self.msg_entry.pack(side="right", fill="x", expand=True, padx=(6, 6))
        self.msg_entry.bind("<Return>", lambda e: self._on_send_message())

    def _add_placeholder(self, entry, text):
        entry.configure(foreground="#999999")
        entry.insert(0, text)

        def on_focus_in(_e):
            if entry.get() == text:
                entry.delete(0, "end")
                entry.configure(foreground="#000000")

        def on_focus_out(_e):
            if not entry.get():
                entry.configure(foreground="#999999")
                entry.insert(0, text)

        entry.bind("<FocusIn>", on_focus_in)
        entry.bind("<FocusOut>", on_focus_out)
        entry._placeholder = text

    # --------------------------------------------------------- NETWORKING ---
    def _start_networking(self):
        self._stop_event = threading.Event()
        self.responder_thread = threading.Thread(
            target=start_responder, args=(TCP_PORT, self._stop_event), daemon=True
        )
        self.responder_thread.start()

        self.server = ChatServer(
            on_message_received=self._on_message_received_threadsafe,
            save_dir=RECEIVED_DIR, port=TCP_PORT,
        )
        self.server.start()

        if not self.contacts and not self.groups:
            self.root.after(400, self._on_scan_clicked)
        else:
            self._refresh_contact_list()

    def _on_message_received_threadsafe(self, header):
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
        msg_type = header.get("type")
        ip = header.get("ip")
        from_name = header.get("from", ip)
        group_id = header.get("group_id")

        if group_id:
            chat = self.groups.get(group_id)
            if chat is None:
                members = header.get("members") or []
                # خودم را از لیست اعضا حذف می‌کنم چون خودم را جزو اعضای خودم نگه نمی‌داریم
                members = [m for m in members if m.get("ip") != self.my_ip]
                chat = ChatEntry(key=group_id, name=header.get("group_name") or "گروه جدید",
                                  is_group=True, members=members)
                self.groups[group_id] = chat
            else:
                self._merge_group_members(chat, header.get("members") or [])
        else:
            chat = self._find_or_create_single_contact(ip, from_name)

        notify_needed = False
        notify_title = f"پیام جدید از {from_name}"
        notify_body = ""

        if msg_type == "msg":
            msg = make_message(header.get("id") or new_id(), from_name, ip, "text",
                                text=header.get("text"), outgoing=False, status="sent")
            chat.messages.append(msg)
            notify_needed = True
            notify_body = header.get("text") or ""
        elif msg_type == "file":
            filename = header.get("filename", "فایل")
            msg = make_message(header.get("id") or new_id(), from_name, ip, "file",
                                text=filename, path=header.get("path"), outgoing=False, status="sent")
            chat.messages.append(msg)
            notify_needed = True
            notify_body = f"📎 {filename}"
        elif msg_type == "recall":
            target = chat.find_message(header.get("target_id"))
            if target:
                target["status"] = "recalled"
                target["text"] = None
        elif msg_type == "buzz":
            soundfx.play_buzz_sound()
            soundfx.shake_window(self.root)
            chat.messages.append(make_message(new_id(), from_name, ip, "system",
                                               text=f"🔔 {from_name} یک بازر برایتان فرستاد!",
                                               outgoing=False, status="sent"))
            notify_needed = True
            notify_title = f"بازر از {from_name}"
            notify_body = "🔔 بازر دریافت شد"
        else:
            return

        self._save_state()

        if self.selected_key == chat.key:
            self._render_selected()
        else:
            self._refresh_contact_list(highlight_key=chat.key)

        if notify_needed:
            self._maybe_notify(notify_title, notify_body)

    def _merge_group_members(self, chat, members_list):
        if not members_list:
            return
        known_ips = {m["ip"] for m in chat.members}
        known_ips.add(self.my_ip)
        changed = False
        for m in members_list:
            if m.get("ip") and m["ip"] not in known_ips:
                chat.members.append(m)
                known_ips.add(m["ip"])
                changed = True
        return changed

    def _find_or_create_single_contact(self, ip, from_name):
        for c in self.contacts.values():
            if c.ip == ip:
                c.name = from_name
                return c
        key = f"{ip}:{TCP_PORT}"
        c = ChatEntry(key=key, name=from_name, is_group=False, ip=ip, port=TCP_PORT)
        self.contacts[key] = c
        return c

    # ------------------------------------------------------------ ACTIONS ---
    def _on_scan_clicked(self):
        self.status_label.config(text="در حال اسکن شبکه...", foreground="#b46a00")

        def worker():
            found = scan_network(TCP_PORT, timeout=2.5)
            self.root.after(0, lambda: self._on_scan_done(found))

        threading.Thread(target=worker, daemon=True).start()

    def _on_scan_done(self, found):
        added = 0
        for item in found:
            key = f'{item["ip"]}:{item["port"]}'
            if key not in self.contacts:
                self.contacts[key] = ChatEntry(key=key, name=item["name"], is_group=False,
                                                ip=item["ip"], port=item["port"])
                added += 1
            else:
                self.contacts[key].name = item["name"]
        self._save_state()
        self._refresh_contact_list()
        self.status_label.config(text=f"اسکن پایان یافت — {added} کامپیوتر جدید یافت شد", foreground="#1a7a1a")

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
            key = f'{info["ip"]}:{info["port"]}'
            if key not in self.contacts:
                self.contacts[key] = ChatEntry(key=key, name=info["name"], is_group=False,
                                                ip=info["ip"], port=info["port"])
        else:
            key = f"{ip}:{TCP_PORT}"
            if key not in self.contacts:
                self.contacts[key] = ChatEntry(key=key, name=ip, is_group=False, ip=ip, port=TCP_PORT)
            messagebox.showwarning(
                "بدون پاسخ",
                f"کامپیوتر {ip} به درخواست شناسایی پاسخ نداد.\n"
                "با این حال به لیست اضافه شد؛ مطمئن شوید LAN Chat روی آن سیستم اجرا و فایروال آن اجازه می‌دهد.",
            )
        self._save_state()
        self._refresh_contact_list()
        self.status_label.config(text="آماده", foreground="#1a7a1a")

    def _on_create_group(self):
        if not self.contacts:
            messagebox.showinfo("گروه", "ابتدا حداقل یک کامپیوتر را از طریق اسکن یا افزودن دستی پیدا کنید.")
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("ایجاد گروه جدید")
        dlg.geometry("360x420")
        dlg.transient(self.root)

        ttk.Label(dlg, text="نام گروه:", font=("Tahoma", 10, "bold")).pack(anchor="e", padx=10, pady=(10, 2))
        name_entry = ttk.Entry(dlg, justify="right")
        name_entry.pack(fill="x", padx=10)

        ttk.Label(dlg, text="اعضای گروه را انتخاب کنید:", font=("Tahoma", 10, "bold")).pack(anchor="e", padx=10, pady=(10, 2))
        listbox = tk.Listbox(dlg, selectmode="multiple", font=("Tahoma", 10))
        listbox.pack(fill="both", expand=True, padx=10)
        contacts_list = list(self.contacts.values())
        for c in contacts_list:
            listbox.insert("end", c.display_name)

        def confirm():
            sel = listbox.curselection()
            if not sel:
                messagebox.showinfo("گروه", "حداقل یک عضو را انتخاب کنید.", parent=dlg)
                return
            group_name = name_entry.get().strip() or "گروه جدید"
            members = [{"name": contacts_list[i].name, "ip": contacts_list[i].ip, "port": contacts_list[i].port}
                       for i in sel]
            key = "group:" + new_id()
            self.groups[key] = ChatEntry(key=key, name=group_name, is_group=True, members=members)
            self._save_state()
            self._refresh_contact_list()
            dlg.destroy()

        ttk.Button(dlg, text="ایجاد گروه", command=confirm).pack(pady=10)

    def _refresh_contact_list(self, highlight_key=None):
        filter_text = self._real_text_by_var(self.contact_search_var).strip().lower()
        self.contact_listbox.delete(0, "end")
        items = list(self.contacts.values()) + list(self.groups.values())
        if filter_text:
            items = [c for c in items if filter_text in c.name.lower()]
        self._contact_keys_in_order = [c.key for c in items]
        for c in items:
            label = c.display_name
            if highlight_key == c.key and c.key != self.selected_key:
                label = "🔵 " + label
            self.contact_listbox.insert("end", label)
            if c.key == self.selected_key:
                idx = self._contact_keys_in_order.index(c.key)
                self.contact_listbox.selection_set(idx)

    def _real_text_by_var(self, var):
        val = var.get()
        if val in ("جستجوی نام کامپیوتر...", "جستجو در این گفتگو..."):
            return ""
        return val

    def _get_selected_chat(self):
        if not self.selected_key:
            return None
        return self.contacts.get(self.selected_key) or self.groups.get(self.selected_key)

    def _on_select_contact(self, event):
        sel = self.contact_listbox.curselection()
        if not sel:
            return
        key = self._contact_keys_in_order[sel[0]]
        self.selected_key = key
        chat = self._get_selected_chat()
        if not chat:
            return
        title = f"👥 گروه: {chat.name}" if chat.is_group else f"گفتگو با {chat.name} ({chat.ip})"
        self.chat_title.config(text=title)
        self.chat_search_var.set("")
        self._render_selected()
        self._refresh_contact_list()

    def _render_selected(self):
        chat = self._get_selected_chat()
        if not chat:
            return
        self.chatview.set_background_image(chat.bg_image)
        term = self._real_text_by_var(self.chat_search_var)
        self.chatview.render(chat, self.my_name, search_term=term)

    def _render_if_open(self, chat):
        if self.selected_key == chat.key:
            self._render_selected()

    # ------------------------------------------------------ SEND / RECEIVE ---
    def _on_send_message(self):
        chat = self._get_selected_chat()
        if not chat:
            messagebox.showinfo("انتخاب مقصد", "ابتدا یک کامپیوتر یا گروه را از لیست انتخاب کنید.")
            return
        text = self.msg_entry.get().strip()
        if not text:
            return
        self.msg_entry.delete(0, "end")

        msg_id = new_id()
        msg = make_message(msg_id, self.my_name, self.my_ip, "text", text=text, outgoing=True, status="pending")
        chat.messages.append(msg)
        self._render_if_open(chat)

        job = self.root.after(3000, lambda: self._actually_send_message(chat, msg))
        self.pending_sends[msg_id] = job

    def _actually_send_message(self, chat, msg):
        self.pending_sends.pop(msg["id"], None)

        def worker():
            try:
                for ip, port in chat.targets(self.my_ip):
                    client.send_message(
                        ip, port, self.my_name, msg["text"], msg["id"],
                        group_id=chat.key if chat.is_group else None,
                        group_name=chat.name if chat.is_group else None,
                        members=chat.all_members_including_me(self.my_name, self.my_ip, TCP_PORT) if chat.is_group else None,
                    )
                msg["status"] = "sent"
            except Exception:
                msg["status"] = "failed"
            self.root.after(0, lambda: (self._render_if_open(chat), self._save_state()))

        threading.Thread(target=worker, daemon=True).start()

    def _on_send_file(self):
        chat = self._get_selected_chat()
        if not chat:
            messagebox.showinfo("انتخاب مقصد", "ابتدا یک کامپیوتر یا گروه را از لیست انتخاب کنید.")
            return
        filepath = filedialog.askopenfilename(title="انتخاب فایل برای ارسال")
        if not filepath:
            return

        msg_id = new_id()
        filename = os.path.basename(filepath)
        msg = make_message(msg_id, self.my_name, self.my_ip, "file", text=filename,
                            path=filepath, outgoing=True, status="pending")
        chat.messages.append(msg)
        self._render_if_open(chat)

        job = self.root.after(3000, lambda: self._actually_send_file(chat, msg, filepath))
        self.pending_sends[msg_id] = job

    def _actually_send_file(self, chat, msg, filepath):
        self.pending_sends.pop(msg["id"], None)
        filename = os.path.basename(filepath)

        def progress_cb(sent, total):
            percent = int(sent * 100 / total) if total else 100
            self.root.after(0, lambda: self.status_label.config(text=f"ارسال {filename}: {percent}%"))

        def worker():
            try:
                for ip, port in chat.targets(self.my_ip):
                    client.send_file(
                        ip, port, self.my_name, filepath, msg["id"],
                        group_id=chat.key if chat.is_group else None,
                        group_name=chat.name if chat.is_group else None,
                        members=chat.all_members_including_me(self.my_name, self.my_ip, TCP_PORT) if chat.is_group else None,
                        progress_cb=progress_cb,
                    )
                msg["status"] = "sent"
            except Exception:
                msg["status"] = "failed"
            self.root.after(0, lambda: (
                self._render_if_open(chat), self._save_state(),
                self.status_label.config(text="آماده", foreground="#1a7a1a"),
            ))

        threading.Thread(target=worker, daemon=True).start()

    def _handle_recall_click(self, msg):
        chat = self._get_selected_chat()
        if not chat:
            return
        if msg.get("status") == "pending":
            self._cancel_pending(chat, msg)
        elif msg.get("status") == "sent":
            self._recall_sent_message(chat, msg)

    def _cancel_pending(self, chat, msg):
        job = self.pending_sends.pop(msg["id"], None)
        if job:
            try:
                self.root.after_cancel(job)
            except Exception:
                pass
        chat.messages = [m for m in chat.messages if m["id"] != msg["id"]]
        self._render_if_open(chat)
        self._save_state()

    def _recall_sent_message(self, chat, msg):
        def worker():
            try:
                for ip, port in chat.targets(self.my_ip):
                    client.send_recall(ip, port, self.my_name, msg["id"],
                                        group_id=chat.key if chat.is_group else None)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()
        msg["status"] = "recalled"
        msg["text"] = None
        self._render_if_open(chat)
        self._save_state()

    def _on_send_buzz(self):
        chat = self._get_selected_chat()
        if not chat:
            messagebox.showinfo("بازر", "ابتدا یک گفتگو را انتخاب کنید.")
            return

        def worker():
            try:
                for ip, port in chat.targets(self.my_ip):
                    client.send_buzz(ip, port, self.my_name, group_id=chat.key if chat.is_group else None)
            except Exception:
                pass

        threading.Thread(target=worker, daemon=True).start()
        soundfx.play_buzz_sound()
        soundfx.shake_window(self.root)
        chat.messages.append(make_message(new_id(), self.my_name, self.my_ip, "system",
                                           text="🔔 شما یک بازر ارسال کردید", outgoing=True, status="sent"))
        self._render_if_open(chat)
        self._save_state()

    # -------------------------------------------------------- HISTORY / BG ---
    def _on_clear_history(self):
        chat = self._get_selected_chat()
        if not chat:
            messagebox.showinfo("پاک کردن تاریخچه", "ابتدا یک گفتگو را انتخاب کنید.")
            return
        if not messagebox.askyesno("تایید حذف", f"آیا از پاک کردن تاریخچه گفتگو با «{chat.name}» مطمئن هستید؟"):
            return
        if not messagebox.askyesno(
            "تایید نهایی",
            "این عملیات غیرقابل بازگشت است و پیام‌های این گفتگو فقط از این دستگاه حذف می‌شوند.\n"
            "آیا کاملاً مطمئن هستید؟",
        ):
            return
        chat.messages.clear()
        self._save_state()
        self._render_if_open(chat)

    def _on_choose_chat_bg(self):
        chat = self._get_selected_chat()
        if not chat:
            messagebox.showinfo("تصویر پس‌زمینه", "ابتدا یک گفتگو را انتخاب کنید.")
            return
        path = filedialog.askopenfilename(
            title="انتخاب تصویر پس‌زمینه",
            filetypes=[("فایل‌های تصویری", "*.png *.jpg *.jpeg *.gif *.bmp")],
        )
        if not path:
            return
        chat.bg_image = path
        self.chatview.set_background_image(path)
        self._save_state()

    def _on_remove_chat_bg(self):
        chat = self._get_selected_chat()
        if not chat:
            return
        chat.bg_image = None
        self.chatview.set_background_image(None)
        self._save_state()

    def _on_chat_search(self, event=None):
        chat = self._get_selected_chat()
        if not chat:
            return
        term = self._real_text_by_var(self.chat_search_var)
        self.chatview.render(chat, self.my_name, search_term=term)
        if term:
            count = sum(1 for m in chat.messages if term.lower() in (m.get("text") or "").lower())
            self.search_result_label.config(text=f"{count} نتیجه")
        else:
            self.search_result_label.config(text="")

    # ----------------------------------------------------------- EMOJI ---
    def _open_emoji_picker(self):
        popup = tk.Toplevel(self.root)
        popup.title("ایموجی")
        popup.resizable(False, False)
        popup.transient(self.root)
        frame = tk.Frame(popup, padx=6, pady=6)
        frame.pack()
        cols = 8
        for i, em in enumerate(EMOJIS):
            b = tk.Button(frame, text=em, font=("Segoe UI Emoji", 14), width=2,
                          command=lambda e=em: self._insert_emoji(e, popup))
            b.grid(row=i // cols, column=i % cols, padx=2, pady=2)

    def _insert_emoji(self, emoji, popup):
        self.msg_entry.insert(tk.INSERT, emoji)
        popup.destroy()
        self.msg_entry.focus_set()

    # ----------------------------------------------------------- THEME ---
    def _draw_theme_button(self):
        self.theme_btn_canvas.delete("all")
        self.theme_btn_canvas.create_oval(3, 3, 27, 27, fill=self.theme_color, outline="#666666", width=2)

    def _open_theme_popup(self):
        popup = tk.Toplevel(self.root)
        popup.title("انتخاب رنگ زمینه")
        popup.resizable(False, False)
        popup.transient(self.root)
        frame = tk.Frame(popup, padx=12, pady=12)
        frame.pack()
        ttk.Label(frame, text="یک رنگ زمینه انتخاب کنید:").pack(pady=(0, 8))
        row = tk.Frame(frame)
        row.pack()
        for color in THEME_OPTIONS:
            c = tk.Canvas(row, width=42, height=42, highlightthickness=0)
            c.pack(side="left", padx=6)
            c.create_oval(2, 2, 40, 40, fill=color, outline="#666666", width=2)
            c.bind("<Button-1>", lambda e, col=color: self._apply_theme(col, popup))

    def _apply_theme(self, color, popup=None):
        self.theme_color = color
        self._apply_theme_to_widgets()
        self._save_state()
        if popup:
            popup.destroy()

    def _apply_theme_to_widgets(self):
        fg = contrast_text_color(self.theme_color)
        style = ttk.Style()
        style.configure("TFrame", background=self.theme_color)
        style.configure("TLabel", background=self.theme_color, foreground=fg)
        style.configure("TButton", background=self.theme_color)
        try:
            self.root.configure(bg=self.theme_color)
        except Exception:
            pass
        list_bg = "#ffffff" if fg == "#101010" else "#2b2b2b"
        try:
            self.contact_listbox.configure(bg=list_bg, fg=fg, selectbackground="#4a90d9")
        except Exception:
            pass
        if hasattr(self, "chatview"):
            self.chatview.set_theme(self.theme_color)
        if hasattr(self, "theme_btn_canvas"):
            self._draw_theme_button()

    # ------------------------------------------------------------- CLOCK ---
    def _update_clock(self):
        self.date_label.config(text=jalali.today_jalali_str())
        self.time_label.config(text=jalali.tehran_time_str())
        self.root.after(1000, self._update_clock)

    # ------------------------------------------------------------ HELPERS ---
    def _open_received_folder(self):
        os.makedirs(RECEIVED_DIR, exist_ok=True)
        self._open_path(RECEIVED_DIR)

    def _open_path(self, path):
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                os.system(f'open "{path}"')
            else:
                os.system(f'xdg-open "{path}"')
        except Exception as e:
            messagebox.showerror("خطا", f"باز کردن مسیر ممکن نشد:\n{e}")

    def _is_minimized_or_unfocused(self):
        try:
            return self.root.state() == "iconic" or not self._has_focus
        except Exception:
            return not self._has_focus

    def _maybe_notify(self, title, message):
        if self._is_minimized_or_unfocused():
            try:
                hwnd = self.root.winfo_id()
                notify.show_notification(title, message, hwnd)
            except Exception:
                pass

    def _save_state(self):
        data = {
            "contacts": {k: c.to_dict() for k, c in self.contacts.items()},
            "groups": {k: c.to_dict() for k, c in self.groups.items()},
            "settings": {"theme_color": self.theme_color},
        }
        persistence.save_state(STATE_PATH, data)

    def _on_close(self):
        self._stop_event.set()
        self.server.stop()
        self._save_state()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = LANChatApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
