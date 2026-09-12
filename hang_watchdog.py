# -*- coding: utf-8 -*-
"""
نگهبان تشخیص هنگ کردن (Hang Watchdog).
اگر ترد اصلی رابط کاربری (Tkinter) برای چند ثانیه پاسخ ندهد، این ماژول محل دقیق
گیر کردن هر ترد را (Stack Trace کامل) در یک فایل لاگ کنار برنامه ذخیره می‌کند.
این کمک می‌کند علت واقعی هنگ کردن، به‌جای حدس زدن، دقیقاً مشخص شود.
"""
import os
import sys
import threading
import time
import traceback

_last_heartbeat = [time.time()]
_dumped_at = [0.0]


def heartbeat():
    """باید هر ۱ ثانیه از ترد اصلی Tkinter (با root.after) صدا زده شود"""
    _last_heartbeat[0] = time.time()


def _dump_stacks(log_path):
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n{'='*60}\n=== هنگ شناسایی شد — {time.ctime()} ===\n{'='*60}\n")
            frames = sys._current_frames()
            for th in threading.enumerate():
                f.write(f"\n--- ترد: {th.name} (id={th.ident}, daemon={th.daemon}) ---\n")
                frame = frames.get(th.ident)
                if frame:
                    f.write("".join(traceback.format_stack(frame)))
                else:
                    f.write("(stack در دسترس نبود)\n")
            f.write("\n")
    except Exception:
        pass


def start_watchdog(log_path, hang_threshold=6.0, check_interval=2.0):
    """این تابع یک‌بار در شروع برنامه صدا زده می‌شود"""
    def loop():
        while True:
            time.sleep(check_interval)
            idle = time.time() - _last_heartbeat[0]
            if idle > hang_threshold:
                # هر ۳۰ ثانیه یک‌بار دوباره دامپ می‌گیرد تا اگر هنگ ادامه داشت، تازه بماند
                if time.time() - _dumped_at[0] > 30:
                    _dumped_at[0] = time.time()
                    _dump_stacks(log_path)

    t = threading.Thread(target=loop, daemon=True, name="HangWatchdog")
    t.start()
