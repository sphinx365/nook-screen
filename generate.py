#!/usr/bin/env python3
import calendar
import datetime as dt
import math
import os
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageDraw, ImageFont

LAT = os.environ.get("LAT")
LON = os.environ.get("LON")
TZ = os.environ.get("TZ", "")
CITY = os.environ.get("CITY", "")

W, H = 600, 800
CAL_TOP = 600                 # calendar: 600..800 = 1/4 of the screen
OUT = "site/screen.png"

WD_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
MONTHS = ["Січень", "Лютий", "Березень", "Квітень", "Травень", "Червень",
          "Липень", "Серпень", "Вересень", "Жовтень", "Листопад", "Грудень"]
KIND_TEXT = {
    "clear": "Сонячно, краса",
    "partly": "Трохи хмарок",
    "cloudy": "Хмарно, сіро",
    "fog": "Туман, як у фільмі",
    "rain": "Дощ, парасолька",
    "snow": "Сніжить, ура",
    "storm": "Гроза, краще вдома",
}

REG_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
]
BOLD_FONTS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
]


def font(size, bold=False):
    for path in (BOLD_FONTS if bold else REG_FONTS):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


# ---------- weather kinds and icons ----------

def base_kind(code):
    if code == 0:
        return "clear"
    if code in (1, 2):
        return "partly"
    if code == 3:
        return "cloudy"
    if code in (45, 48):
        return "fog"
    if 51 <= code <= 67 or 80 <= code <= 82:
        return "rain"
    if 71 <= code <= 77 or code in (85, 86):
        return "snow"
    if code >= 95:
        return "storm"
    return "cloudy"


def icon_name(code, is_day):
    kind = base_kind(code)
    if not is_day and kind == "clear":
        return "moon"
    if not is_day and kind == "partly":
        return "night_partly"
    return kind


def draw_sun(d, cx, cy, r):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=0)
    for i in range(8):
        a = math.pi * i / 4
        d.line((cx + math.cos(a) * (r + 3), cy + math.sin(a) * (r + 3),
                cx + math.cos(a) * (r + 7), cy + math.sin(a) * (r + 7)),
               fill=0, width=max(2, int(r / 3)))


def draw_moon(d, cx, cy, r):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=0)
    o = r * 0.5
    d.ellipse((cx - r + o, cy - r - o * 0.6, cx + r + o, cy + r - o * 0.6), fill=255)


def draw_cloud(d, cx, cy, s):
    def blob(x, y, r):
        d.ellipse((cx + (x - r) * s, cy + (y - r) * s,
                   cx + (x + r) * s, cy + (y + r) * s), fill=0)
    blob(-8, 4, 7)
    blob(0, 0, 10)
    blob(10, 5, 7)
    d.rectangle((cx - 15 * s, cy + 4 * s, cx + 17 * s, cy + 12 * s), fill=0)


def draw_icon(d, name, x, y, size):
    s = size / 44
    cx, cy = x + size / 2, y + size / 2
    if name == "clear":
        draw_sun(d, cx, cy, 9 * s)
    elif name == "moon":
        draw_moon(d, cx, cy, 12 * s)
    elif name == "partly":
        draw_sun(d, cx - 7 * s, cy - 7 * s, 7 * s)
        draw_cloud(d, cx + 4 * s, cy + 5 * s, 0.85 * s)
    elif name == "night_partly":
        draw_moon(d, cx - 7 * s, cy - 7 * s, 7 * s)
        draw_cloud(d, cx + 4 * s, cy + 5 * s, 0.85 * s)
    elif name == "cloudy":
        draw_cloud(d, cx, cy, s)
    elif name == "fog":
        for i in range(3):
            yy = cy - 10 * s + i * 10 * s
            d.line((x + 6 * s, yy, x + size - 6 * s, yy), fill=0,
                   width=max(2, int(3 * s)))
    elif name == "rain":
        draw_cloud(d, cx, cy - 5 * s, 0.85 * s)
        for i in range(3):
            xx = cx - 9 * s + i * 9 * s
            d.line((xx, cy + 10 * s, xx - 3 * s, cy + 17 * s), fill=0,
                   width=max(2, int(2.5 * s)))
    elif name == "snow":
        draw_cloud(d, cx, cy - 5 * s, 0.85 * s)
        r = max(2, 2.5 * s)
        for i in range(3):
            xx = cx - 9 * s + i * 9 * s
            d.ellipse((xx - r, cy + 14 * s - r, xx + r, cy + 14 * s + r), fill=0)
    elif name == "storm":
        draw_cloud(d, cx, cy - 6 * s, 0.85 * s)
        d.polygon([(cx + 1 * s, cy + 6 * s), (cx - 4 * s, cy + 14 * s),
                   (cx, cy + 14 * s), (cx - 2 * s, cy + 22 * s),
                   (cx + 5 * s, cy + 12 * s), (cx + 0.5 * s, cy + 12 * s)], fill=0)


# ---------- layout ----------

def render(data, now):
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)

    f_city = font(34, True)
    f_big = font(120)
    f_cond = font(24)
    f_small = font(22)
    f_hour_lbl = font(20, True)
    f_hour_t = font(24)
    f_day = font(24, True)
    f_day_t = font(24)
    f_cal_title = font(22, True)
    f_cal_wd = font(16, True)
    f_cal_day = font(17)

    cur, hourly, daily = data["current"], data["hourly"], data["daily"]

    # Header: city, current temp, condition, high/low
    d.text((30, 22), CITY, font=f_city, fill=0)
    d.text((30, 70), f"{round(cur['temperature_2m'])}°", font=f_big, fill=0)
    base = base_kind(cur["weather_code"])
    cond = "Ясна ніч" if base == "clear" and not cur["is_day"] else KIND_TEXT[base]
    draw_icon(d, icon_name(cur["weather_code"], cur["is_day"]), 470, 16, 64)
    d.text((570, 92), cond, font=f_cond, fill=0, anchor="ra")
    hi0, lo0 = round(daily["temperature_2m_max"][0]), round(daily["temperature_2m_min"][0])
    d.text((570, 124), f"Макс. {hi0}°   Мін. {lo0}°", font=f_small, fill=0, anchor="ra")
    d.line((30, 205, 570, 205), fill=0, width=2)

    # Hourly strip: now + next 5 hours
    now_key = cur["time"][:13] + ":00"
    times = hourly["time"]
    start = next((i for i, t in enumerate(times) if t >= now_key), 0)
    for i in range(6):
        idx = start + i
        cx = 30 + 45 + 90 * i
        label = "Зараз" if i == 0 else times[idx][11:16]
        d.text((cx, 222), label, font=f_hour_lbl, fill=0, anchor="ma")
        draw_icon(d, icon_name(hourly["weather_code"][idx], hourly["is_day"][idx]),
                  cx - 22, 250, 44)
        d.text((cx, 306), f"{round(hourly['temperature_2m'][idx])}°",
               font=f_hour_t, fill=0, anchor="ma")
    d.line((30, 342, 570, 342), fill=0, width=1)

    # 5-day list with range bars scaled to the whole week
    dates = [dt.date.fromisoformat(s) for s in daily["time"][:5]]
    highs = daily["temperature_2m_max"][:5]
    lows = daily["temperature_2m_min"][:5]
    wmin, wmax = min(lows), max(highs)
    span = max(wmax - wmin, 1)
    for i in range(5):
        cy = 362 + i * 44 + 16
        name = "Сьогодні" if i == 0 else WD_SHORT[dates[i].weekday()]
        d.text((30, cy), name, font=f_day, fill=0, anchor="lm")
        draw_icon(d, icon_name(daily["weather_code"][i], 1), 168, cy - 16, 32)
        d.text((240, cy), f"{round(lows[i])}°", font=f_day_t, fill=0, anchor="rm")
        d.rounded_rectangle((256, cy - 4, 488, cy + 4), radius=4, fill=215)
        x0 = 256 + (lows[i] - wmin) / span * 232
        x1 = max(256 + (highs[i] - wmin) / span * 232, x0 + 8)
        d.rounded_rectangle((x0, cy - 4, x1, cy + 4), radius=4, fill=0)
        d.text((570, cy), f"{round(highs[i])}°", font=f_day_t, fill=0, anchor="rm")

     # Calendar: bottom quarter, selected day inverted
    d.line((0, CAL_TOP, W, CAL_TOP), fill=0, width=2)
    today = now.date()
    d.text((30, CAL_TOP + 8), f"{MONTHS[today.month - 1]} {today.year}",
           font=f_cal_title, fill=0)
    cw = (W - 60) / 7
    for c, name in enumerate(WD_SHORT):
        d.text((30 + cw * (c + 0.5), CAL_TOP + 34), name,
               font=f_cal_wd, fill=0, anchor="ma")
    weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(today.year, today.month)
    row_h = 24
    for r, week in enumerate(weeks):
        for c, day_num in enumerate(week):
            if not day_num:
                continue
            cx = 30 + cw * (c + 0.5)
            cy = CAL_TOP + 54 + r * row_h + row_h / 2
            if day_num == today.day:
                d.ellipse((cx - 12, cy - 12, cx + 12, cy + 12), fill=0)
                d.text((cx, cy), str(day_num), font=f_cal_day, fill=255, anchor="mm")
            else:
                d.text((cx, cy), str(day_num), font=f_cal_day, fill=0, anchor="mm")
    return img


# ---------- data and main ----------

def fetch():
    if not LAT or not LON:
        raise SystemExit("Set LAT and LON environment variables")
    r = requests.get("https://api.open-meteo.com/v1/forecast", timeout=15, params={
        "latitude": LAT, "longitude": LON, "timezone": TZ,
        "current": "temperature_2m,weather_code,is_day",
        "hourly": "temperature_2m,weather_code,is_day",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min",
        "forecast_days": 6,
    })
    r.raise_for_status()
    return r.json()


def main():
    if not (LAT and LON and TZ):
        raise SystemExit("Set LAT, LON and TZ environment variables")
    now = dt.datetime.now(ZoneInfo(TZ))
    img = render(fetch(), now)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT, optimize=True)


if __name__ == "__main__":
    main()
