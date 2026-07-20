# -*- coding: utf-8 -*-
"""
مدل داده برای چت‌های تکی و گروهی و پیام‌ها + تبدیل به/از دیکشنری برای ذخیره‌سازی
"""
import uuid
from datetime import datetime


def new_id() -> str:
    return uuid.uuid4().hex


class ChatEntry:
    def __init__(self, key, name, is_group=False, members=None, ip=None, port=None, bg_image=None):
        self.key = key
        self.name = name
        self.is_group = is_group
        self.members = members or []  # لیست دیکشنری {"name":..,"ip":..,"port":..}
        self.ip = ip      # فقط برای چت تکی
        self.port = port  # فقط برای چت تکی
        self.messages = []  # لیست دیکشنری پیام
        self.bg_image = bg_image  # مسیر فایل تصویر پس‌زمینه اختصاصی این چت

    @property
    def display_name(self):
        prefix = "👥 " if self.is_group else ""
        suffix = f"  ({self.ip})" if not self.is_group and self.ip else ""
        return f"{prefix}{self.name}{suffix}"

    def targets(self, my_ip):
        """لیست (ip, port) مقصدهایی که باید پیام برایشان ارسال شود"""
        if self.is_group:
            return [(m["ip"], m["port"]) for m in self.members if m["ip"] != my_ip]
        return [(self.ip, self.port)]

    def all_members_including_me(self, my_name, my_ip, my_port):
        """لیست کامل اعضای گروه به‌همراه خودم؛ برای اطلاع‌رسانی گروه به اعضای جدید هنگام ارسال پیام"""
        result = list(self.members)
        if not any(m["ip"] == my_ip for m in result):
            result.append({"name": my_name, "ip": my_ip, "port": my_port})
        return result

    def find_message(self, msg_id):
        for m in self.messages:
            if m.get("id") == msg_id:
                return m
        return None

    def to_dict(self):
        return {
            "key": self.key,
            "name": self.name,
            "is_group": self.is_group,
            "members": self.members,
            "ip": self.ip,
            "port": self.port,
            "messages": self.messages,
            "bg_image": self.bg_image,
        }

    @staticmethod
    def from_dict(d):
        c = ChatEntry(
            key=d["key"],
            name=d["name"],
            is_group=d.get("is_group", False),
            members=d.get("members", []),
            ip=d.get("ip"),
            port=d.get("port"),
            bg_image=d.get("bg_image"),
        )
        c.messages = d.get("messages", [])
        return c


def make_message(msg_id, sender, sender_ip, msg_type, text=None, path=None,
                  status="sent", outgoing=False, timestamp=None):
    return {
        "id": msg_id,
        "sender": sender,
        "sender_ip": sender_ip,
        "type": msg_type,       # 'text' | 'file' | 'system'
        "text": text,
        "path": path,
        "status": status,       # 'pending' | 'sent' | 'failed' | 'recalled' | 'cancelled'
        "outgoing": outgoing,
        "timestamp": (timestamp or datetime.now()).isoformat(),
    }
