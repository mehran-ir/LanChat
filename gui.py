# -*- coding: utf-8 -*-
"""
رابط گرافیکی برنامه چت تحت شبکه محلی (LAN Chat) — نسخه کامل
"""
import os
import queue
import shutil
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from utils import get_hostname, get_local_ip
from discovery import start_responder, scan_network, probe_single_ip
from server import ChatServer, TCP_PORT
import client
import jalali
import soundfx
import persistence
from chatmodel import ChatEntry, make_message, new_id
from chatview import ChatView
from theme import DEFAULT_THEME, THEME_OPTIONS, contrast_text_color, DEFAULT_CHATBOX_COLOR, BUTTON_PALETTE, shade
from emoji_render import get_emoji_icon
import taskbar_badge
import tray_icon

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
BACKGROUNDS_DIR = os.path.join(BASE_DIR, "chat_backgrounds")
STATE_PATH = os.path.join(BASE_DIR, "lanchat_data.json")


class LANChatApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.my_ip = get_local_ip()

        os.makedirs(RECEIVED_DIR, exist_ok=True)
        os.makedirs(BACKGROUNDS_DIR, exist_ok=True)

        raw_state = persistence.load_state(STATE_PATH)
        self.contacts = {k: ChatEntry.from_dict(v) for k, v in raw_state.get("contacts", {}).items()}
        self.groups = {k: ChatEntry.from_dict(v) for k, v in raw_state.get("groups", {}).items()}
        self.theme_color = raw_state.get("settings", {}).get("theme_color", DEFAULT_THEME)
        self.chatbox_color = raw_state.get("settings", {}).get("chatbox_color", DEFAULT_CHATBOX_COLOR)
        self.notifications_enabled = raw_state.get("settings", {}).get("notifications_enabled", True)

        saved_name = raw_state.get("settings", {}).get("display_name")
        if saved_name:
            self.my_name = saved_name
        else:
            # اولین اجرای برنامه: از کاربر نام دلخواه‌اش را می‌پرسیم
            entered = simpledialog.askstring(
                "خوش آمدید به LanChat by MGH",
                "نام خود را برای نمایش به دیگران در شبکه وارد کنید:",
                initialvalue=get_hostname(), parent=self.root,
            )
            self.my_name = (entered or "").strip() or get_hostname()

        self.root.title(f"LanChat by MGH - {self.my_name}")
        self.root.geometry("980x620")
        self.root.minsize(760, 480)

        self.selected_key = None
        self.incoming_queue = queue.Queue()
        self.pending_sends = {}
        self._contact_keys_in_order = []
        self._last_status_kind = "success"
        self._has_focus = True

        self._build_ui()
        self._apply_theme_to_widgets()
        self._start_networking()
        self._poll_queue()
        self._update_clock()
        self._save_state()  # نام تعیین‌شده (پیش‌فرض یا وارد‌شده) را از همین اول ذخیره می‌کنیم

        self.root.bind("<FocusIn>", lambda e: setattr(self, "_has_focus", True))
        self.root.bind("<FocusOut>", lambda e: setattr(self, "_has_focus", False))
        self.root.after(500, self._update_taskbar_badge)

        self.tray = tray_icon.TrayIcon(
            on_open=lambda: self.root.after(0, self._restore_from_tray),
            on_quit=lambda: self.root.after(0, self._quit_app),
            tooltip=f"LanChat by MGH - {self.my_name}",
        )
        self._tray_active = self.tray.start()
        self.root.protocol("WM_DELETE_WINDOW", self._on_window_close)

    # ---------------------------------------------------------------- UI ---
    def _build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        self._configure_button_styles(style)

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
        self.my_name_label = ttk.Label(
            right_top, text=f"این کامپیوتر: {self.my_name}   ({self.my_ip})",
            font=("Tahoma", 10, "bold"),
        )
        self.my_name_label.pack(side="right", padx=(8, 0))

        ttk.Button(right_top, text="✏️", width=3, command=self._on_rename_self, style="Neutral.TButton").pack(side="right", padx=(4, 0))

        self.notif_toggle_btn = ttk.Button(right_top, width=3, command=self._toggle_notifications, style="Pink.TButton")
        self.notif_toggle_btn.pack(side="right", padx=(4, 0))
        self._update_notif_toggle_button()

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
        self.contact_listbox.bind("<Button-3>", self._on_contact_right_click)

        btns = ttk.Frame(left)
        btns.pack(fill="x", pady=6)
        ttk.Button(btns, text="اسکن شبکه", command=self._on_scan_clicked, style="Primary.TButton").pack(side="right", expand=True, fill="x", padx=2)
        ttk.Button(btns, text="افزودن دستی", command=self._on_add_manual, style="Info.TButton").pack(side="right", expand=True, fill="x", padx=2)

        ttk.Button(left, text="👥 ایجاد گروه جدید", command=self._on_create_group, style="Purple.TButton").pack(fill="x", pady=(0, 4))
        ttk.Button(left, text="باز کردن پوشه فایل‌های دریافتی", command=self._open_received_folder, style="Neutral.TButton").pack(fill="x")

        self.status_label = ttk.Label(left, text="آماده", foreground=self._status_color("success"))
        self.status_label.pack(fill="x", pady=(8, 0))

        # =========================================================== RIGHT
        right = ttk.Frame(main, padding=6)
        right.pack(side="right", fill="both", expand=True)

        self.chat_title = ttk.Label(right, text="یک کامپیوتر یا گروه را انتخاب کنید", font=("Tahoma", 11, "bold"))
        self.chat_title.pack(anchor="e", pady=(0, 4))

        toolbar = ttk.Frame(right)
        toolbar.pack(fill="x", pady=(0, 4))

        ttk.Button(toolbar, text="👥 اعضای گروه", command=self._on_show_group_members, style="Purple.TButton").pack(side="right", padx=2)
        ttk.Button(toolbar, text="🗑 پاک کردن تاریخچه", command=self._on_clear_history, style="Danger.TButton").pack(side="right", padx=2)
        ttk.Button(toolbar, text="🔔 بازر", command=self._on_send_buzz, style="Warning.TButton").pack(side="right", padx=2)
        ttk.Button(toolbar, text="🖼 تصویر پس‌زمینه", command=self._on_choose_chat_bg, style="Purple.TButton").pack(side="right", padx=2)
        ttk.Button(toolbar, text="حذف پس‌زمینه", command=self._on_remove_chat_bg, style="Neutral.TButton").pack(side="right", padx=2)

        self.chat_search_var = tk.StringVar()
        chat_search_entry = ttk.Entry(toolbar, textvariable=self.chat_search_var, justify="right", width=22)
        chat_search_entry.pack(side="left", padx=(0, 4))
        chat_search_entry.bind("<KeyRelease>", self._on_chat_search)
        self._add_placeholder(chat_search_entry, "جستجو در این گفتگو...")
        self.search_result_label = ttk.Label(toolbar, text="")
        self.search_result_label.pack(side="left")

        self.chatview = ChatView(
            right, on_recall=self._handle_recall_click, on_open_file=self._open_path,
            theme_color=self.theme_color, box_color=self.chatbox_color,
            on_reply=self._start_reply,
        )
        self.chatview.pack(fill="both", expand=True)

        self.reply_bar = ttk.Frame(right)
        self.reply_bar_label = ttk.Label(self.reply_bar, text="", anchor="e", justify="right")
        self.reply_bar_label.pack(side="right", fill="x", expand=True, padx=(4, 8))
        ttk.Button(self.reply_bar, text="✕", width=2, command=self._cancel_reply, style="Neutral.TButton").pack(side="left")
        self._reply_target = None
        # self.reply_bar تا زمانی که پاسخ فعال نشده pack نمی‌شود

        bottom = ttk.Frame(right)
        self._bottom_frame = bottom
        bottom.pack(fill="x", pady=(8, 0))

        emoji_btn_icon = get_emoji_icon("😊", size=18)
        if emoji_btn_icon:
            self.emoji_btn = ttk.Button(bottom, image=emoji_btn_icon, command=self._open_emoji_picker, style="Pink.TButton")
            self.emoji_btn.image = emoji_btn_icon  # جلوگیری از garbage collection تصویر
        else:
            self.emoji_btn = ttk.Button(bottom, text="😊", width=3, command=self._open_emoji_picker, style="Pink.TButton")
        self.emoji_btn.pack(side="left")

        self.file_btn = ttk.Button(bottom, text="ارسال فایل", command=self._on_send_file, style="Info.TButton")
        self.file_btn.pack(side="left", padx=(4, 0))

        self.send_btn = ttk.Button(bottom, text="ارسال", command=self._on_send_message, style="Success.TButton")
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
            target=start_responder,
            args=(TCP_PORT, self._stop_event, lambda: self.my_name),
            kwargs={"on_error": lambda msg: self.root.after(0, lambda: self._on_responder_error(msg))},
            daemon=True,
        )
        self.responder_thread.start()

        self.server = ChatServer(
            on_message_received=self._on_message_received_threadsafe,
            save_dir=RECEIVED_DIR, port=TCP_PORT,
        )
        self.server.start()

        # broadcast به‌صورت پیش‌فرض فقط با کلیک دستی روی «اسکن شبکه» انجام می‌شود،
        # تا پهنای باند شبکه بدون درخواست کاربر درگیر نشود — با یک استثنا:
        # فقط در همان اولین اجرای برنامه (وقتی هنوز هیچ لیستی ذخیره نشده) یک اسکن
        # خودکار انجام می‌شود تا کاربر مجبور نباشد برای شروع کار دستی کلیک کند.
        self._refresh_contact_list()
        if not self.contacts and not self.groups:
            self._set_status("در حال اسکن اولیه شبکه...", "warning")
            self.root.after(400, self._on_scan_clicked)

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
                # فقط اگر خودم واقعاً در فهرست اعضای این پیام گروهی معرفی شده باشم،
                # گروه را می‌سازم؛ در غیر این صورت این پیام به من ربطی ندارد و نادیده گرفته می‌شود
                if not any(m.get("ip") == self.my_ip for m in members):
                    return
                members = [m for m in members if m.get("ip") != self.my_ip]
                chat = ChatEntry(key=group_id, name=header.get("group_name") or "گروه جدید",
                                  is_group=True, members=members)
                self.groups[group_id] = chat
            else:
                # فقط پیام‌هایی که واقعاً از یکی از اعضای شناخته‌شده همین گروه می‌رسد پذیرفته می‌شود
                known_ips = {m.get("ip") for m in chat.members}
                if ip not in known_ips:
                    return
                self._merge_group_members(chat, header.get("members") or [])
                self._sync_member_name(chat, ip, from_name)
        else:
            chat = self._find_or_create_single_contact(ip, from_name)

        notify_needed = False
        notify_title = f"پیام جدید از {from_name}"
        notify_body = ""

        if msg_type == "msg":
            msg = make_message(header.get("id") or new_id(), from_name, ip, "text",
                                text=header.get("text"), outgoing=False, status="sent",
                                reply_to=header.get("reply_to"), reply_sender=header.get("reply_sender"),
                                reply_text=header.get("reply_text"))
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
        elif msg_type == "read":
            id_set = set(header.get("message_ids") or [])
            for m in chat.messages:
                if m.get("outgoing") and m.get("id") in id_set and m.get("status") == "sent":
                    m["status"] = "read"
        else:
            return

        if self.selected_key == chat.key:
            self._save_state()
            self._render_selected()
        else:
            if notify_needed:
                chat.unread += 1
                self._update_taskbar_badge()
            self._save_state()
            self._refresh_contact_list()

        if notify_needed:
            self._maybe_notify(notify_title, notify_body, chat.key)

    def _merge_group_members(self, chat, members_list):
        if not members_list:
            return
        by_ip = {m["ip"]: m for m in chat.members}
        changed = False
        for m in members_list:
            ip = m.get("ip")
            if not ip or ip == self.my_ip:
                continue
            new_name = m.get("name")
            if ip not in by_ip:
                chat.members.append(m)
                by_ip[ip] = m
                changed = True
            elif new_name and by_ip[ip].get("name") != new_name:
                by_ip[ip]["name"] = new_name
                changed = True
        return changed

    def _sync_member_name(self, chat, ip, name):
        """نام یک عضو گروه را در صورت تغییر، در لیست اعضای همان گروه به‌روزرسانی می‌کند"""
        if not chat.is_group or not name:
            return False
        for m in chat.members:
            if m.get("ip") == ip and m.get("name") != name:
                m["name"] = name
                return True
        return False

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
    def _on_responder_error(self, message):
        self._set_status("⚠️ " + message, "error")
        messagebox.showwarning(
            "مشکل در دریافت درخواست‌های اسکن",
            message + "\n\nپیشنهاد: مطمئن شوید نمونه دیگری از LanChat روی همین کامپیوتر باز نیست، "
            "سپس برنامه را ببندید (از منوی Tray گزینه «خروج») و دوباره اجرا کنید.",
        )

    def _on_scan_clicked(self):
        self._set_status("در حال اسکن شبکه...", "warning")

        def worker():
            found = scan_network(TCP_PORT, timeout=2.5, display_name=self.my_name)
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
        self._set_status(f"اسکن پایان یافت — {added} کامپیوتر جدید یافت شد", "success")

    def _on_add_manual(self):
        ip = simpledialog.askstring("افزودن دستی", "آدرس IP کامپیوتر مقصد را وارد کنید:", parent=self.root)
        if not ip:
            return
        ip = ip.strip()
        self._set_status(f"در حال بررسی {ip} ...", "warning")

        def worker():
            info = probe_single_ip(ip, TCP_PORT, timeout=2.5, display_name=self.my_name)
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
        self._set_status("آماده", "success")

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

        ttk.Button(dlg, text="ایجاد گروه", command=confirm, style="Success.TButton").pack(pady=10)

    def _refresh_contact_list(self):
        filter_text = self._real_text_by_var(self.contact_search_var).strip().lower()
        self.contact_listbox.delete(0, "end")
        items = list(self.contacts.values()) + list(self.groups.values())
        if filter_text:
            items = [c for c in items if filter_text in c.name.lower()]
        self._contact_keys_in_order = [c.key for c in items]
        for i, c in enumerate(items):
            label = c.display_name
            if c.unread > 0:
                badge = c.unread if c.unread <= 99 else "99+"
                label = f"{label}   🔴 {badge}"
            self.contact_listbox.insert("end", label)
            if c.unread > 0:
                self.contact_listbox.itemconfig(i, fg="#c0392b")
            if c.key == self.selected_key:
                self.contact_listbox.selection_set(i)

    def _real_text_by_var(self, var):
        val = var.get()
        if val in ("جستجوی نام کامپیوتر...", "جستجو در این گفتگو..."):
            return ""
        return val

    def _get_selected_chat(self):
        if not self.selected_key:
            return None
        return self.contacts.get(self.selected_key) or self.groups.get(self.selected_key)

    def _chat_title_text(self, chat):
        if chat.is_group:
            count = len(chat.members) + 1  # +۱ برای خودم
            return f"👥 گروه: {chat.name}  ({count} عضو)"
        return f"گفتگو با {chat.name} ({chat.ip})"

    def _on_show_group_members(self):
        chat = self._get_selected_chat()
        if not chat or not chat.is_group:
            messagebox.showinfo("اعضای گروه", "ابتدا یک گروه را از لیست انتخاب کنید.")
            return

        dlg = tk.Toplevel(self.root)
        dlg.title(f"اعضای گروه «{chat.name}»")
        dlg.geometry("340x360")
        dlg.transient(self.root)

        ttk.Label(
            dlg, text=f"گروه «{chat.name}» — {len(chat.members) + 1} عضو",
            font=("Tahoma", 10, "bold"),
        ).pack(anchor="e", padx=10, pady=(10, 6))

        listbox = tk.Listbox(dlg, font=("Tahoma", 10))
        listbox.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        listbox.insert("end", f"👤 {self.my_name} (شما)   —   {self.my_ip}")
        for m in chat.members:
            name = m.get("name") or ""
            ip = m.get("ip", "؟")
            if not name or name == ip:
                listbox.insert("end", f"👤 (نام هنوز دریافت نشده)   —   {ip}")
            else:
                listbox.insert("end", f"👤 {name}   —   {ip}")

        ttk.Button(dlg, text="بستن", command=dlg.destroy, style="Neutral.TButton").pack(pady=(0, 10))

    def _on_contact_right_click(self, event):
        index = self.contact_listbox.nearest(event.y)
        if index < 0 or index >= len(self._contact_keys_in_order):
            return
        # فقط اگر کلیک واقعاً روی محدوده یک ردیف موجود بوده باشد
        bbox = self.contact_listbox.bbox(index)
        if not bbox:
            return
        key = self._contact_keys_in_order[index]
        chat = self.contacts.get(key) or self.groups.get(key)
        if not chat or not chat.is_group:
            return  # منوی کلیک راست فقط برای گروه‌ها فعال است

        self.contact_listbox.selection_clear(0, "end")
        self.contact_listbox.selection_set(index)

        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="✏️ ویرایش نام گروه", command=lambda: self._on_rename_group(chat))
        menu.add_command(label="🗑 حذف گروه", command=lambda: self._on_delete_group(chat))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _on_rename_self(self):
        new_name = simpledialog.askstring(
            "ویرایش نام نمایشی", "نام جدیدی که دیگران در شبکه شما را با آن ببینند:",
            initialvalue=self.my_name, parent=self.root,
        )
        if not new_name or not new_name.strip():
            return
        self.my_name = new_name.strip()
        self.root.title(f"LanChat by MGH - {self.my_name}")
        self.my_name_label.config(text=f"این کامپیوتر: {self.my_name}   ({self.my_ip})")
        self._save_state()

    def _on_rename_group(self, chat):
        new_name = simpledialog.askstring(
            "ویرایش نام گروه", "نام جدید گروه را وارد کنید:",
            initialvalue=chat.name, parent=self.root,
        )
        if not new_name or not new_name.strip():
            return
        chat.name = new_name.strip()
        self._save_state()
        self._refresh_contact_list()
        if self.selected_key == chat.key:
            self.chat_title.config(text=self._chat_title_text(chat))

    def _on_delete_group(self, chat):
        if not messagebox.askyesno(
            "حذف گروه",
            f"آیا از حذف گروه «{chat.name}» مطمئن هستید؟\n"
            "این کار فقط گروه را از این دستگاه حذف می‌کند (تاریخچه گفتگوی آن هم پاک می‌شود).",
        ):
            return
        self.groups.pop(chat.key, None)
        if self.selected_key == chat.key:
            self.selected_key = None
            self.chat_title.config(text="یک کامپیوتر یا گروه را انتخاب کنید")
            self.chatview.clear()
        self._save_state()
        self._refresh_contact_list()

    def _on_select_contact(self, event):
        sel = self.contact_listbox.curselection()
        if not sel:
            return
        key = self._contact_keys_in_order[sel[0]]
        self.selected_key = key
        chat = self._get_selected_chat()
        if not chat:
            return
        self.chat_title.config(text=self._chat_title_text(chat))
        self.chat_search_var.set("")
        self._cancel_reply()
        if chat.unread > 0:
            chat.unread = 0
            self._save_state()
            self._update_taskbar_badge()
        self._send_read_receipts(chat)
        self._render_selected()
        self._refresh_contact_list()

    def _target_for_sender_ip(self, chat, sender_ip):
        if chat.is_group:
            for m in chat.members:
                if m.get("ip") == sender_ip:
                    return (m["ip"], m.get("port", TCP_PORT))
            return None
        return (chat.ip, chat.port)

    def _send_read_receipts(self, chat):
        """برای پیام‌های دریافتی‌ای که هنوز رسید خوانده‌شدن برایشان ارسال نشده، به فرستنده اطلاع می‌دهد"""
        pending = [
            m for m in chat.messages
            if not m.get("outgoing") and m.get("type") in ("text", "file")
            and m.get("status") == "sent" and not m.get("_read_sent")
        ]
        if not pending:
            return

        by_sender = {}
        for m in pending:
            by_sender.setdefault(m.get("sender_ip"), []).append(m["id"])
            m["_read_sent"] = True
        self._save_state()

        def worker():
            for sender_ip, ids in by_sender.items():
                target = self._target_for_sender_ip(chat, sender_ip)
                if not target:
                    continue
                try:
                    client.send_read(target[0], target[1], self.my_name, ids,
                                      group_id=chat.key if chat.is_group else None)
                except Exception:
                    pass

        threading.Thread(target=worker, daemon=True).start()

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

        reply_to = reply_sender = reply_text = None
        if self._reply_target is not None:
            r = self._reply_target
            reply_to = r.get("id")
            reply_sender = self.my_name if r.get("outgoing") else r.get("sender")
            reply_text = r.get("text") if r.get("type") == "text" else (r.get("text") or "فایل")
            self._cancel_reply()

        msg_id = new_id()
        msg = make_message(msg_id, self.my_name, self.my_ip, "text", text=text, outgoing=True, status="pending",
                            reply_to=reply_to, reply_sender=reply_sender, reply_text=reply_text)
        chat.messages.append(msg)
        self._render_if_open(chat)

        job = self.root.after(1000, lambda: self._actually_send_message(chat, msg))
        self.pending_sends[msg_id] = job

    def _start_reply(self, msg):
        if msg.get("status") == "recalled":
            return
        self._reply_target = msg
        preview_sender = self.my_name if msg.get("outgoing") else msg.get("sender", "")
        preview_text = msg.get("text") or ("📎 فایل" if msg.get("type") == "file" else "")
        preview_text = preview_text.replace("\n", " ")
        if len(preview_text) > 60:
            preview_text = preview_text[:60] + "…"
        self.reply_bar_label.config(text=f"↩ در پاسخ به {preview_sender}: {preview_text}")
        self.reply_bar.pack(fill="x", pady=(4, 0), before=self._bottom_frame)
        self.msg_entry.focus_set()

    def _cancel_reply(self):
        self._reply_target = None
        try:
            self.reply_bar.pack_forget()
        except Exception:
            pass

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
                        reply_to=msg.get("reply_to"), reply_sender=msg.get("reply_sender"), reply_text=msg.get("reply_text"),
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

        job = self.root.after(1000, lambda: self._actually_send_file(chat, msg, filepath))
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
                self._set_status("آماده", "success"),
            ))

        threading.Thread(target=worker, daemon=True).start()

    def _handle_recall_click(self, msg):
        chat = self._get_selected_chat()
        if not chat:
            return
        if msg.get("status") == "pending":
            self._cancel_pending(chat, msg)
        elif msg.get("status") in ("sent", "read"):
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

    def _cleanup_managed_bg(self, chat):
        """اگر تصویر پس‌زمینه فعلی این چت از قبل داخل پوشه مدیریت‌شده برنامه کپی شده، آن را پاک می‌کند"""
        old = chat.bg_image
        if old:
            try:
                if os.path.abspath(os.path.dirname(old)) == os.path.abspath(BACKGROUNDS_DIR):
                    os.remove(old)
            except Exception:
                pass

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

        try:
            os.makedirs(BACKGROUNDS_DIR, exist_ok=True)
            ext = os.path.splitext(path)[1].lower() or ".png"
            dest_path = os.path.join(BACKGROUNDS_DIR, f"{new_id()}{ext}")
            shutil.copyfile(path, dest_path)
        except Exception as e:
            messagebox.showerror("خطا", f"کپی تصویر پس‌زمینه در پوشه برنامه ممکن نشد:\n{e}")
            return

        self._cleanup_managed_bg(chat)
        chat.bg_image = dest_path
        self.chatview.set_background_image(dest_path)
        self._save_state()

    def _on_remove_chat_bg(self):
        chat = self._get_selected_chat()
        if not chat:
            return
        self._cleanup_managed_bg(chat)
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
        # از شبیه‌سازی کلید سیستمی Win+. صرف‌نظر شد: چون در سطح کل سیستم‌عامل تزریق
        # می‌شد، می‌توانست با فوکوس/IME باکس پیام تداخل کند و باعث پاک شدن پیام هنگام
        # ارسال شود. به‌جای آن همیشه از پاپ‌آپ داخلی (که کاملاً در کنترل خود برنامه و
        # قابل‌اعتماد است) استفاده می‌کنیم؛ ایموجی‌ها همچنان رنگی نمایش داده می‌شوند.
        self._open_fallback_emoji_popup()

    def _open_fallback_emoji_popup(self):
        popup = tk.Toplevel(self.root)
        popup.title("ایموجی")
        popup.resizable(False, False)
        popup.transient(self.root)
        frame = tk.Frame(popup, padx=6, pady=6)
        frame.pack()
        cols = 8
        icon_refs = []
        for i, em in enumerate(EMOJIS):
            icon = get_emoji_icon(em, size=28)
            if icon:
                b = tk.Button(frame, image=icon, width=36, height=36, bg="#fce4ec",
                              activebackground="#f8bbd0", relief="flat",
                              command=lambda e=em: self._insert_emoji(e, popup))
                icon_refs.append(icon)
            else:
                b = tk.Button(frame, text=em, font=("Segoe UI Emoji", 14), width=2, bg="#fce4ec",
                              activebackground="#f8bbd0", relief="flat",
                              command=lambda e=em: self._insert_emoji(e, popup))
            b.grid(row=i // cols, column=i % cols, padx=2, pady=2)
        popup._icon_refs = icon_refs  # جلوگیری از garbage collection تا زمانی که پاپ‌آپ باز است

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

    def _set_status(self, text: str, kind: str = "success"):
        self._last_status_kind = kind
        self.status_label.config(text=text, foreground=self._status_color(kind))

    def _status_color(self, kind: str) -> str:
        """رنگ مناسب برای پیام‌های وضعیت (موفق/هشدار/خطا) بر اساس روشن یا تیره بودن تم فعلی"""
        is_dark_theme = contrast_text_color(self.theme_color) != "#101010"
        palette = {
            "success": "#6fdc8c" if is_dark_theme else "#1a7a1a",
            "warning": "#ffb74d" if is_dark_theme else "#b46a00",
            "error": "#ff6b6b" if is_dark_theme else "#c0392b",
        }
        return palette.get(kind, contrast_text_color(self.theme_color))

    def _configure_button_styles(self, style):
        """برای هر دسته از دکمه‌ها یک استایل رنگی جدا می‌سازد تا تمام دکمه‌های برنامه رنگی باشند"""
        for key, color in BUTTON_PALETTE.items():
            style_name = f"{key.capitalize()}.TButton"
            hover = shade(color, -0.12)
            pressed = shade(color, -0.22)
            style.configure(
                style_name, background=color, foreground="#ffffff",
                padding=5, borderwidth=0, focusthickness=0,
            )
            style.map(
                style_name,
                background=[("active", hover), ("pressed", pressed), ("disabled", "#cccccc")],
                foreground=[("disabled", "#eeeeee")],
            )

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
        if hasattr(self, "status_label"):
            try:
                self.status_label.config(foreground=self._status_color(self._last_status_kind))
            except Exception:
                pass

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
            return self.root.state() in ("iconic", "withdrawn") or not self._has_focus
        except Exception:
            return not self._has_focus

    def _toggle_notifications(self):
        self.notifications_enabled = not self.notifications_enabled
        self._update_notif_toggle_button()
        self._save_state()

    def _update_notif_toggle_button(self):
        if self.notifications_enabled:
            self.notif_toggle_btn.config(text="🔔")
        else:
            self.notif_toggle_btn.config(text="🔕")

    def _maybe_notify(self, title, message, chat_key=None):
        if not self.notifications_enabled:
            return
        if self._is_minimized_or_unfocused():
            try:
                self._show_toast(title, message, chat_key)
            except Exception:
                pass

    def _show_toast(self, title, message, chat_key):
        """
        یک نوتیفیکیشن داخلی و قابل‌کلیک گوشه پایین-راست صفحه نمایش می‌دهد.
        برخلاف بالن رسمی ویندوز، چون این یک پنجره واقعی Tkinter است، کلیک روی آن
        همیشه به‌طور کامل و مطمئن قابل تشخیص است.
        """
        if getattr(self, "_active_toast", None):
            try:
                if self._active_toast.winfo_exists():
                    self._active_toast.destroy()
            except Exception:
                pass

        toast = tk.Toplevel(self.root)
        self._active_toast = toast
        toast.overrideredirect(True)
        toast.attributes("-topmost", True)
        try:
            toast.attributes("-alpha", 0.97)
        except Exception:
            pass

        width, height = 320, 92
        screen_w = toast.winfo_screenwidth()
        screen_h = toast.winfo_screenheight()
        x = screen_w - width - 18
        y = screen_h - height - 60
        toast.geometry(f"{width}x{height}+{x}+{y}")

        outer = tk.Frame(toast, bg="#cccccc")
        outer.pack(fill="both", expand=True)
        frame = tk.Frame(outer, bg="#ffffff")
        frame.pack(fill="both", expand=True, padx=1, pady=1)

        tk.Label(
            frame, text=title, font=("Tahoma", 10, "bold"), bg="#ffffff", fg="#111111",
            anchor="e", justify="right", wraplength=width - 24,
        ).pack(fill="x", padx=12, pady=(10, 2))
        tk.Label(
            frame, text=(message or "")[:150], font=("Tahoma", 9), bg="#ffffff", fg="#333333",
            anchor="e", justify="right", wraplength=width - 24,
        ).pack(fill="x", padx=12)
        tk.Label(
            frame, text="برای مشاهده کلیک کنید ✕ برای بستن", font=("Tahoma", 7), bg="#ffffff", fg="#999999",
            anchor="e", justify="right",
        ).pack(fill="x", padx=12, pady=(4, 0))

        def on_click(_event=None):
            self._focus_and_open_chat(chat_key)
            try:
                toast.destroy()
            except Exception:
                pass

        for widget in [toast, outer, frame] + list(frame.winfo_children()):
            widget.bind("<Button-1>", on_click)
            try:
                widget.configure(cursor="hand2")
            except Exception:
                pass

        toast.after(6000, lambda: toast.destroy() if toast.winfo_exists() else None)

    def _focus_and_open_chat(self, chat_key):
        """پنجره برنامه را از حالت Minimize/بدون‌فوکوس خارج و به گفتگوی مشخص‌شده می‌رود"""
        try:
            self.root.deiconify()
            self.root.state("normal")
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.after(150, lambda: self.root.attributes("-topmost", False))
            self.root.focus_force()
        except Exception:
            pass

        chat = self.contacts.get(chat_key) or self.groups.get(chat_key)
        if not chat:
            return
        self.selected_key = chat_key
        self.chat_title.config(text=self._chat_title_text(chat))
        if chat.unread > 0:
            chat.unread = 0
            self._save_state()
            self._update_taskbar_badge()
        self._send_read_receipts(chat)
        self._render_selected()
        self._refresh_contact_list()

    def _update_taskbar_badge(self):
        try:
            total = sum(c.unread for c in self.contacts.values()) + sum(c.unread for c in self.groups.values())
            hwnd = self.root.winfo_id()
            taskbar_badge.set_badge(hwnd, total)
        except Exception:
            pass

    def _save_state(self):
        data = {
            "contacts": {k: c.to_dict() for k, c in self.contacts.items()},
            "groups": {k: c.to_dict() for k, c in self.groups.items()},
            "settings": {
                "theme_color": self.theme_color,
                "chatbox_color": self.chatbox_color,
                "display_name": self.my_name,
                "notifications_enabled": self.notifications_enabled,
            },
        }
        persistence.save_state(STATE_PATH, data)

    def _on_window_close(self):
        """با کلیک روی دکمه X پنجره: اگر آیکون Tray فعال باشد، فقط مخفی می‌شویم (نه بسته)"""
        if getattr(self, "_tray_active", False):
            try:
                self.root.withdraw()
            except Exception:
                self._on_close()
        else:
            self._on_close()

    def _restore_from_tray(self):
        try:
            self.root.deiconify()
            self.root.state("normal")
            self.root.lift()
            self.root.attributes("-topmost", True)
            self.root.after(150, lambda: self.root.attributes("-topmost", False))
            self.root.focus_force()
        except Exception:
            pass

    def _quit_app(self):
        """خروج واقعی از برنامه (از طریق گزینه «خروج» در منوی Tray)"""
        try:
            if getattr(self, "tray", None):
                self.tray.stop()
        except Exception:
            pass
        self._on_close()

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
