# -*- coding: utf-8 -*-
"""
تبدیل تاریخ میلادی به شمسی (جلالی) و دریافت ساعت به وقت تهران
بدون نیاز به هیچ کتابخانه خارجی
"""
from datetime import datetime, timezone, timedelta

TEHRAN_TZ = timezone(timedelta(hours=3, minutes=30))  # ایران از سال ۱۴۰۱ بدون تغییر ساعت تابستانی

WEEKDAY_FA = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه", "شنبه", "یکشنبه"]
MONTH_FA = [
    "فروردین", "اردیبهشت", "خرداد", "تیر", "مرداد", "شهریور",
    "مهر", "آبان", "آذر", "دی", "بهمن", "اسفند",
]


def gregorian_to_jalali(g_y, g_m, g_d):
    """الگوریتم استاندارد تبدیل تاریخ میلادی به جلالی (شمسی)"""
    g_days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    j_days_in_month = [31, 31, 31, 31, 31, 31, 30, 30, 30, 30, 30, 29]

    gy = g_y - 1600
    gm = g_m - 1
    gd = g_d - 1

    g_day_no = 365 * gy + (gy + 3) // 4 - (gy + 99) // 100 + (gy + 399) // 400
    for i in range(gm):
        g_day_no += g_days_in_month[i]
    if gm > 1 and ((g_y % 4 == 0 and g_y % 100 != 0) or (g_y % 400 == 0)):
        g_day_no += 1
    g_day_no += gd

    j_day_no = g_day_no - 79

    j_np = j_day_no // 12053
    j_day_no %= 12053

    jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
    j_day_no %= 1461

    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365

    for i in range(11):
        if j_day_no < j_days_in_month[i]:
            jm = i + 1
            jd = j_day_no + 1
            break
        j_day_no -= j_days_in_month[i]
    else:
        jm = 12
        jd = j_day_no + 1

    return jy, jm, jd


def now_tehran() -> datetime:
    """زمان فعلی به وقت تهران (UTC+3:30)"""
    return datetime.now(timezone.utc).astimezone(TEHRAN_TZ)


def today_jalali_str() -> str:
    """رشته تاریخ شمسی امروز، مثل: شنبه ۱۴۰۳/۰۴/۳۰"""
    now = now_tehran()
    jy, jm, jd = gregorian_to_jalali(now.year, now.month, now.day)
    weekday = WEEKDAY_FA[now.weekday()]
    return f"{weekday} {jy:04d}/{jm:02d}/{jd:02d}"


def tehran_time_str() -> str:
    """رشته ساعت به وقت تهران، مثل: 14:32:07"""
    now = now_tehran()
    return now.strftime("%H:%M:%S")


def jalali_datetime_str(dt: datetime) -> str:
    """یک datetime میلادی دلخواه را به رشته شمسی + ساعت تبدیل می‌کند (برای برچسب زمان پیام‌ها)"""
    jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
    return f"{jy:04d}/{jm:02d}/{jd:02d} - {dt.strftime('%H:%M:%S')}"
