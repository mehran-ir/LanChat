# -*- coding: utf-8 -*-
"""
ذخیره و بازیابی داده‌های برنامه (لیست کامپیوترها، گروه‌ها، تاریخچه چت، تنظیمات ظاهری)
در یک فایل JSON کنار برنامه، تا با بستن و باز کردن مجدد برنامه از بین نروند.
"""
import json
import os
import threading

_lock = threading.Lock()


def load_state(path: str) -> dict:
    if not os.path.exists(path):
        return {"contacts": {}, "groups": {}, "settings": {}}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("contacts", {})
        data.setdefault("groups", {})
        data.setdefault("settings", {})
        return data
    except Exception as e:
        print(f"خطا در خواندن فایل ذخیره‌سازی: {e}")
        return {"contacts": {}, "groups": {}, "settings": {}}


def save_state(path: str, data: dict):
    with _lock:
        try:
            tmp_path = path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, path)
        except Exception as e:
            print(f"خطا در ذخیره‌سازی داده‌ها: {e}")
