# -*- coding: utf-8 -*-
"""
افکت صدا (بوق بازر) و لرزش پنجره برای قابلیت Buzzer
"""
import sys


def play_buzz_sound():
    if sys.platform.startswith("win"):
        try:
            import winsound
            winsound.Beep(900, 150)
            winsound.Beep(1300, 150)
            winsound.Beep(900, 150)
            return
        except Exception:
            pass
    try:
        print("\a", end="", flush=True)
    except Exception:
        pass


def shake_window(root, times: int = 8, distance: int = 12, delay_ms: int = 35):
    """پنجره را چند بار به چپ و راست تکان می‌دهد (افکت بصری بازر)"""
    try:
        root.update_idletasks()
        if root.state() == "iconic":
            return  # اگر مینیمایز است تکان دادن معنی ندارد
        x0, y0 = root.winfo_x(), root.winfo_y()
    except Exception:
        return

    positions = []
    for i in range(times):
        dx = distance if i % 2 == 0 else -distance
        positions.append((x0 + dx, y0))
    positions.append((x0, y0))

    def step(i=0):
        if i >= len(positions):
            return
        x, y = positions[i]
        try:
            root.geometry(f"+{x}+{y}")
        except Exception:
            return
        root.after(delay_ms, lambda: step(i + 1))

    step()
