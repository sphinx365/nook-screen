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

# Inter (installed by the workflow with: sudo apt-get install -y fonts-inter)
FONT_PATHS = {
    "reg": ["/usr/share/fonts/opentype/inter/Inter-Regular.otf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
    "bold": ["/usr/share/fonts/opentype/inter/Inter-Bold.otf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"],
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


# ---------- weather kinds ----------

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


# ---------- icons (drawn on a 100x100 grid, solid black) ----------

def icon(d, name, x, y, size):
    k = size / 100.0

    def P(u, v):
        return x + u * k, y + v * k

    def disc(u, v, r, fill=0):
        cx, cy = P(u, v)
        rr = r * k
        d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=fill)

    def stroke(u1, v1, u2, v2, w):
        x1, y1 = P(u1, v1)
        x2, y2 = P(u2, v2)
        ww = w * k
        d.line((x1, y1, x2, y2), fill=0, width=max(1, round(ww)))
        for cx, cy in ((x1, y1), (x2, y2)):
            r = ww / 2
            d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=0)

    def cloud(ou, ov, sc, fill=0, grow=0):
        def c(u, v, r):
            cx, cy = P(ou + u * sc, ov + v * sc)
            rr = (r + grow) * sc * k
            d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), fill=fill)
        c(36, 58, 18)
        c(60, 46, 24)
        c(80, 62, 16)
        x1, y1 = P(ou + (18 - grow) * sc, ov + (58 - grow) * sc)
        x2, y2 = P(ou + (96 + grow) * sc, ov + (78 + grow) * sc)
        d.rounded_rectangle((x1, y1, x2, y2), radius=(10 + grow) * sc * k, fill=fill)

    def sun_rays(cu, cv, r_in, r_out, w):
        for i in range(8):
            a = math.pi * i / 4
            stroke(cu + math.cos(a) * r_in, cv + math.sin(a) * r_in,
                   cu + math.cos(a) * r_out, cv + math.sin(a) * r_out, w)

    if name == "clear":
        disc(50, 50, 22)
        sun_rays(50, 50, 32, 44, 7)
    elif name == "moon":
        disc(50, 50, 36)
        disc(64, 40, 30, fill=255)
    elif name == "night_partly":
        disc(34, 34, 20)
        disc(42, 28, 16, fill=255)
        cloud(30, 40, 0.72, fill=255, grow=6)
        cloud(30, 40, 0.72)
    elif name == "partly":
        disc(34, 34, 18)
        sun_rays(34, 34, 25, 34, 6)
        cloud(30, 40, 0.72, fill=255, grow=6)
        cloud(30, 40, 0.72)
    elif name == "cloudy":
        cloud(-7, 0, 1.0)
    elif name == "rain":
        cloud(-7, -12, 0.9)
        for u in (34, 50, 66):
            stroke(u, 68, u - 6, 92, 7)
    elif name == "snow":
        cloud(-7, -12, 0.9)
        for u in (34, 50, 66):
            disc(u, 82, 6)
    elif name == "storm":
        cloud(-7, -12, 0.9)
        d.polygon([P(54, 60), P(38, 82), P(50, 82), P(42, 98),
                   P(64, 72), P(52, 72), P(60, 60)], fill=0)
    elif name == "fog":
        stroke(14, 36, 86, 36, 8)
        stroke(26, 54, 74, 54, 8)
        stroke(14, 72, 86, 72, 8)


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
    d.rounded_rectangle((l - 7, t - 4, r + 7, b + 4), radius=6, outline=0, width=2)
    d.text((x, y), text, font=f, fill=0, anchor="lm")
    return r + 7


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

    f_city = font("bold", 30)
    f_temp = font("bold", 84)
    f_cond = font("bold", 22)
    f_lbl = font("reg", 18)
    f_val = font("bold", 19)
    f_pill = font("bold", 17)
    f_sec = font("bold", 16)
    f_day = font("bold", 17)
    f_small = font("reg", 15)
    f_mm = font("bold", 12)
    f_axis = font("reg", 13)
    f_legend = font("bold", 12)
    f_bottom = font("reg", 15)

    cur, hourly, daily = fc["current"], fc["hourly"], fc["daily"]
    T = 1  # index of today; past_days=1 puts yesterday at index 0

    # Top left: city, temperature, min and max pills
    d.text((24, 22), CITY, font=f_city, fill=0, anchor="lt")
    d.text((20, 150), f"{round(cur['temperature_2m'])}°", font=f_temp, fill=0, anchor="ls")
    lo = round(daily["temperature_2m_min"][T])
    hi = round(daily["temperature_2m_max"][T])
    x = pill(d, 24, 182, f"Мін {deg(lo)}", f_pill)
    pill(d, x + 10, 182, f"Макс {deg(hi)}", f_pill)
    d.line((262, 22, 262, 200), fill=0, width=2)

    # Top middle: condition icon and text
    base = base_kind(cur["weather_code"])
    cond = "Ясна ніч" if base == "clear" and not cur["is_day"] else KIND_TEXT[base]
    icon(d, icon_name(cur["weather_code"], cur["is_day"]), 327, 22, 96)
    d.text((375, 150), cond, font=f_cond, fill=0, anchor="ms")
    d.line((486, 22, 486, 200), fill=0, width=2)
    
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
        y = 48 + i * 36
        d.text((500, y), label, font=f_lbl, fill=0, anchor="lm")
        d.text((776, y), value, font=f_val, fill=0, anchor="rm")
        if i < len(stats) - 1:
            dotted_h(d, 500, 776, y + 18)
    d.line((20, 214, 780, 214), fill=0, width=3)

    # Hourly precipitation: next 24 hours
    times = hourly["time"]
    now_key = now.strftime("%Y-%m-%dT%H:00")
    start = next((i for i, t in enumerate(times) if t >= now_key), 0)

    d.text((24, 236), "ОПАДИ, НАСТУПНІ 24 ГОД", font=f_sec, fill=0, anchor="lm")
    legend = "ЙМОВІРНІСТЬ / ОБ'ЄМ (ММ)"
    l, t, r, b = d.textbbox((0, 0), legend, font=f_legend)
    box_w = (r - l) + 14
    d.rectangle((776 - box_w, 226, 776, 246), fill=0)
    d.text((776 - box_w / 2, 236), legend, font=f_legend, fill=255, anchor="mm")

    base_y, chart_h = 352, 100
    x0_chart, x1_chart = 64, 776
    slot = (x1_chart - x0_chart) / 24
    y50 = base_y - chart_h / 2
    dotted_h(d, x0_chart, x1_chart, int(y50))
    d.text((24, int(y50)), "50%", font=f_axis, fill=0, anchor="lm")
    for i in range(24):
        idx = start + i
        p = hourly["precipitation_probability"][idx] or 0
        mm = hourly["precipitation"][idx] or 0
        xc = x0_chart + slot * i + slot / 2
        h = p / 100 * chart_h
        if p > 0:
            d.rectangle((xc - 8, base_y - h, xc + 8, base_y), fill=0)
        if mm >= 0.1:
            d.text((xc, base_y - h - 4), f"{mm:.1f}", font=f_mm, fill=0, anchor="ms")
        if i % 3 == 0:
            d.text((xc, base_y + 6), times[idx][11:13] + ":00",
                   font=f_axis, fill=0, anchor="ma")
    d.line((x0_chart, base_y, x1_chart, base_y), fill=0, width=2)
    d.line((20, 382, 780, 382), fill=0, width=3)

    # Five-day list with range bars scaled to the whole week
    days = list(range(T, T + 5))
    lows = [daily["temperature_2m_min"][k] for k in days]
    highs = [daily["temperature_2m_max"][k] for k in days]
    wmin, wmax = min(lows), max(highs)
    span = max(wmax - wmin, 1)
    TX0, TX1 = 200, 500
    for row, k in enumerate(days):
        cy = 400 + row * 27
        date = dt.date.fromisoformat(daily["time"][k])
        name = "Сьогодні" if k == T else WD_SHORT[date.weekday()]
        d.text((24, cy), name, font=f_day, fill=0, anchor="lm")
        icon(d, icon_name(daily["weather_code"][k], 1), 116, cy - 14, 28)
        d.text((186, cy), deg(lows[row]), font=f_day, fill=0, anchor="rm")
        d.rounded_rectangle((TX0, cy - 4, TX1, cy + 4), radius=4, fill=225)
        x0 = TX0 + (lows[row] - wmin) / span * (TX1 - TX0)
        x1 = max(TX0 + (highs[row] - wmin) / span * (TX1 - TX0), x0 + 10)
        d.rounded_rectangle((x0, cy - 4, x1, cy + 4), radius=4, fill=0)
        d.text((512, cy), deg(highs[row]), font=f_day, fill=0, anchor="lm")
        prob = daily["precipitation_probability_max"][k] or 0
        d.text((776, cy), f"Опади {prob}%", font=f_small, fill=0, anchor="rm")
    d.line((20, 528, 780, 528), fill=0, width=3)

    # Bottom bar: sun times, update time, air and UV, rain today
    sr, ss = daily["sunrise"][T], daily["sunset"][T]
    day_change = round(minutes_between(sr, ss)
                       - minutes_between(daily["sunrise"][T - 1], daily["sunset"][T - 1]))
    d.text((24, 546), f"↑ Схід {clock(sr)}", font=f_bottom, fill=0, anchor="lm")
    d.text((24, 566), f"↓ Захід {clock(ss)}", font=f_bottom, fill=0, anchor="lm")
    d.text((24, 586), f"Світлового дня {signed(day_change)} хв", font=f_bottom, fill=0, anchor="lm")

    d.line((262, 536, 262, 594), fill=0, width=1)
    draw_clock(d, 282, 566, 9)
    d.text((300, 566), f"Оновлено {now:%H:%M}", font=f_bottom, fill=0, anchor="lm")

    d.line((512, 536, 512, 594), fill=0, width=1)
    today_str = now.strftime("%Y-%m-%d")
    precip_today = sum((v or 0) for t, v in zip(times, hourly["precipitation"])
                       if t.startswith(today_str))
    d.text((524, 546), f"Повітря: {aqi_text(aq)}", font=f_bottom, fill=0, anchor="lm")
    d.text((524, 566), f"УФ-індекс: {round(daily['uv_index_max'][T])}", font=f_bottom, fill=0, anchor="lm")
    d.text((524, 586), f"Опади сьогодні: {precip_today:.1f} мм", font=f_bottom, fill=0, anchor="lm")

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
