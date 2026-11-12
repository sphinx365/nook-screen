#!/usr/bin/env python3
import datetime as dt
import math
import os
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageDraw, ImageFont

LAT = os.environ.get("LAT")
LON = os.environ.get("LON")
TZ = os.environ.get("TZ")
CITY = os.environ.get("CITY", "")

W, H = 800, 600
OUT = "site/screen.png"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

WD_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
WIND_DIRS = ["Пн", "ПнСх", "Сх", "ПдСх", "Пд", "ПдЗх", "Зх", "ПнЗх"]
KIND_TEXT = {
    "clear": "Сонячно, краса",
    "partly": "Трохи хмарок",
    "cloudy": "Хмарно, сіро",
    "fog": "Туман, як у фільмі",
    "rain": "Дощ, парасолька",
    "snow": "Сніжить, ура",
    "storm": "Гроза, краще вдома",
}

FONT_PATHS = {
    "sans": ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
             "/usr/share/fonts/TTF/DejaVuSans.ttf"],
    "sans_b": ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
               "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"],
    "mono": ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
             "/usr/share/fonts/TTF/DejaVuSansMono.ttf"],
    "mono_b": ["/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf",
               "/usr/share/fonts/TTF/DejaVuSansMono-Bold.ttf"],
}
_font_cache = {}


def font(kind, size):
    key = (kind, size)
    if key not in _font_cache:
        loaded = None
        for path in FONT_PATHS[kind]:
            if os.path.exists(path):
                loaded = ImageFont.truetype(path, size)
                break
        _font_cache[key] = loaded or ImageFont.load_default(size=size)
    return _font_cache[key]


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


def draw_clock(d, cx, cy, r):
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=0, width=2)
    d.line((cx, cy, cx, cy - r * 0.6), fill=0, width=2)
    d.line((cx, cy, cx + r * 0.5, cy), fill=0, width=2)


# ---------- drawing helpers ----------

def dotted_h(d, x0, x1, y, fill=150, step=3):
    x = x0
    while x < x1:
        d.line((x, y, min(x + step, x1), y), fill=fill, width=1)
        x += step * 2


def pill(d, x, y, text, f):
    l, t, r, b = d.textbbox((x, y), text, font=f, anchor="lm")
    d.rounded_rectangle((l - 8, t - 5, r + 8, b + 5), radius=6, outline=0, width=2)
    d.text((x, y), text, font=f, fill=0, anchor="lm")
    return r + 8


# ---------- text helpers ----------

def signed(n):
    if n > 0:
        return f"+{n}"
    if n < 0:
        return f"−{abs(n)}"
    return "0"


def deg(v):
    return f"{round(v)}°".replace("-", "−")


def aqi_text(v):
    if v is None:
        return "н/д"
    if v <= 50:
        return "добре"
    if v <= 100:
        return "помірно"
    if v <= 150:
        return "погано"
    return "дуже погано"


def clock(iso):
    return dt.datetime.fromisoformat(iso).strftime("%H:%M")


def minutes_between(a, b):
    return (dt.datetime.fromisoformat(b) - dt.datetime.fromisoformat(a)).total_seconds() / 60


# ---------- data ----------

def fetch_forecast():
    r = requests.get(FORECAST_URL, timeout=15, params={
        "latitude": LAT, "longitude": LON, "timezone": TZ,
        "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
                   "pressure_msl,wind_speed_10m,wind_direction_10m,weather_code,is_day",
        "hourly": "temperature_2m,weather_code,is_day,precipitation,precipitation_probability",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
                 "precipitation_probability_max,sunrise,sunset,uv_index_max",
        "past_days": 1,
        "forecast_days": 6,
    })
    r.raise_for_status()
    return r.json()


def fetch_air_quality():
    try:
        r = requests.get(AIR_URL, timeout=10, params={
            "latitude": LAT, "longitude": LON, "timezone": TZ, "current": "us_aqi",
        })
        r.raise_for_status()
        return r.json()["current"]["us_aqi"]
    except (requests.RequestException, KeyError, ValueError):
        return None


# ---------- layout ----------

def render(fc, aq, now):
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)

    f_head = font("mono_b", 15)
    f_sec = font("sans_b", 18)
    f_lbl = font("sans", 18)
    f_val = font("mono_b", 20)
    f_big = font("sans_b", 92)
    f_city = font("sans_b", 30)
    f_cond = font("sans_b", 20)
    f_small = font("mono", 15)
    f_s = font("sans", 16)
    f_xs = font("mono", 13)
    f_bar = font("mono_b", 13)

    cur, hourly, daily = fc["current"], fc["hourly"], fc["daily"]
    T = 1  # index of today; past_days=1 puts yesterday at index 0

    # Header: update time only
    draw_clock(d, 30, 36, 8)
    d.text((46, 36), f"ОНОВЛЕНО {now:%H:%M}", font=f_head, fill=0, anchor="lm")
    d.line((20, 54, 780, 54), fill=0, width=2)

    # Top left: icon and condition
    base = base_kind(cur["weather_code"])
    cond = "Ясна ніч" if base == "clear" and not cur["is_day"] else KIND_TEXT[base]
    draw_icon(d, icon_name(cur["weather_code"], cur["is_day"]), 105, 70, 72)
    d.text((141, 166), cond, font=f_cond, fill=0, anchor="ma")
    d.line((262, 66, 262, 212), fill=0, width=2)

    # Top middle: city, temperature, min and max pills
    d.text((280, 64), CITY, font=f_city, fill=0, anchor="la")
    d.text((276, 92), f"{round(cur['temperature_2m'])}°", font=f_big, fill=0)
    lo = round(daily["temperature_2m_min"][T])
    hi = round(daily["temperature_2m_max"][T])
    x = pill(d, 280, 186, f"Мін {lo}°".replace("-", "−"), f_val)
    pill(d, x + 12, 186, f"Макс {hi}°", f_val)
    d.line((486, 66, 486, 212), fill=0, width=2)

    # Top right: details with dotted separators
    wind = (f"{WIND_DIRS[round(cur['wind_direction_10m'] / 45) % 8]} "
            f"{round(cur['wind_speed_10m'])} км/г")
    stats = [
        ("Відчувається", deg(cur["apparent_temperature"])),
        ("Вологість", f"{round(cur['relative_humidity_2m'])}%"),
        ("Тиск", f"{round(cur['pressure_msl'])} гПа"),
        ("Вітер", wind),
    ]
    for i, (label, value) in enumerate(stats):
        y = 80 + i * 36
        d.text((500, y), label, font=f_lbl, fill=0, anchor="lm")
        d.text((780, y), value, font=f_val, fill=0, anchor="rm")
        if i < len(stats) - 1:
            dotted_h(d, 500, 780, y + 18)
    d.line((20, 222, 780, 222), fill=0, width=3)

    # Hourly precipitation: next 24 hours
    times = hourly["time"]
    now_key = now.strftime("%Y-%m-%dT%H:00")
    start = next((i for i, t in enumerate(times) if t >= now_key), 0)

    d.text((20, 240), "ОПАДИ, НАСТУПНІ 24 ГОД", font=f_sec, fill=0, anchor="lm")
    legend = "ЙМОВІРНІСТЬ / ОБ'ЄМ (ММ)"
    l, t, r, b = d.textbbox((0, 0), legend, font=f_bar)
    box_w = (r - l) + 16
    d.rectangle((780 - box_w, 230, 780, 250), fill=0)
    d.text((780 - box_w / 2, 240), legend, font=f_bar, fill=255, anchor="mm")

    base_y, chart_h = 362, 120
    x0_chart, slot = 50, (780 - 50) / 24
    dotted_h(d, x0_chart, 780, int(base_y - chart_h / 2))
    d.text((20, int(base_y - chart_h / 2)), "50%", font=f_xs, fill=0, anchor="lm")
    for i in range(24):
        idx = start + i
        p = hourly["precipitation_probability"][idx] or 0
        mm = hourly["precipitation"][idx] or 0
        xc = x0_chart + slot * i + slot / 2
        h = p / 100 * chart_h
        if p > 0:
            d.rectangle((xc - 9, base_y - h, xc + 9, base_y), fill=0)
        if mm >= 0.1:
            d.text((xc, base_y - h - 3), f"{mm:.1f}", font=f_bar, fill=0, anchor="ms")
        if i % 3 == 0:
            d.text((xc, base_y + 4), times[idx][11:13] + ":00",
                   font=f_xs, fill=0, anchor="ma")
    d.line((x0_chart, base_y, 780, base_y), fill=0, width=2)
    d.line((20, 386, 780, 386), fill=0, width=3)

    # Five-day list with range bars scaled to the whole week
    days = list(range(T, T + 5))
    lows = [daily["temperature_2m_min"][k] for k in days]
    highs = [daily["temperature_2m_max"][k] for k in days]
    wmin, wmax = min(lows), max(highs)
    span = max(wmax - wmin, 1)
    TX0, TX1 = 210, 520
    for row, k in enumerate(days):
        cy = 404 + row * 24
        date = dt.date.fromisoformat(daily["time"][k])
        name = "Сьогодні" if k == T else WD_SHORT[date.weekday()]
        d.text((20, cy), name, font=f_sec, fill=0, anchor="lm")
        draw_icon(d, icon_name(daily["weather_code"][k], 1), 100, cy - 11, 22)
        d.text((190, cy), deg(lows[row]), font=f_val, fill=0, anchor="rm")
        d.rounded_rectangle((TX0, cy - 5, TX1, cy + 5), radius=5, fill=230)
        x0 = TX0 + (lows[row] - wmin) / span * (TX1 - TX0)
        x1 = max(TX0 + (highs[row] - wmin) / span * (TX1 - TX0), x0 + 10)
        d.rounded_rectangle((x0, cy - 5, x1, cy + 5), radius=5, fill=0)
        d.text((535, cy), deg(highs[row]), font=f_val, fill=0, anchor="lm")
        prob = daily["precipitation_probability_max"][k] or 0
        d.text((780, cy), f"Опади {prob}%", font=f_small, fill=0, anchor="rm")
    d.line((20, 522, 780, 522), fill=0, width=3)

    # Bottom: sun times, update time, air and UV, rain today
    sr, ss = daily["sunrise"][T], daily["sunset"][T]
    day_change = round(minutes_between(sr, ss)
                       - minutes_between(daily["sunrise"][T - 1], daily["sunset"][T - 1]))
    d.text((20, 538), f"↑ Схід {clock(sr)}", font=f_s, fill=0, anchor="lm")
    d.text((20, 558), f"↓ Захід {clock(ss)}", font=f_s, fill=0, anchor="lm")
    d.text((20, 578), f"Світлового дня {signed(day_change)} хв", font=f_s, fill=0, anchor="lm")

    d.line((272, 534, 272, 588), fill=0, width=1)
    draw_clock(d, 300, 558, 9)
    d.text((322, 558), f"Оновлено {now:%H:%M}", font=f_s, fill=0, anchor="lm")

    d.line((520, 534, 520, 588), fill=0, width=1)
    today_str = now.strftime("%Y-%m-%d")
    precip_today = sum((v or 0) for t, v in zip(times, hourly["precipitation"])
                       if t.startswith(today_str))
    d.text((536, 538), f"Повітря: {aqi_text(aq)}", font=f_s, fill=0, anchor="lm")
    d.text((536, 558), f"УФ-індекс: {round(daily['uv_index_max'][T])}", font=f_s, fill=0, anchor="lm")
    d.text((536, 578), f"Опади сьогодні: {precip_today:.1f} мм", font=f_s, fill=0, anchor="lm")

    return img


# ---------- main ----------

def main():
    if not (LAT and LON and TZ):
        raise SystemExit("Set LAT, LON and TZ environment variables")
    now = dt.datetime.now(ZoneInfo(TZ))
    img = render(fetch_forecast(), fetch_air_quality(), now)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT, optimize=True)


if __name__ == "__main__":
    main()
