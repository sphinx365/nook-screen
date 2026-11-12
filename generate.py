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
TZ = os.environ.get("TZ")
CITY = os.environ.get("CITY", "")

W, H = 800, 600
CAL_TOP = 600
OUT = "site/screen.png"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AIR_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

WD_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
MONTHS = ["Січень", "Лютий", "Березень", "Квітень", "Травень", "Червень",
          "Липень", "Серпень", "Вересень", "Жовтень", "Листопад", "Грудень"]
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
SYNODIC = 29.530588853
REF_NEW_MOON = dt.datetime(2000, 1, 6, 18, 14, tzinfo=dt.timezone.utc)

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


# ---------- text helpers ----------

def minus(n):
    if n > 0:
        return f"+{n}"
    if n < 0:
        return f"−{abs(n)}"
    return "0"


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


def moon_text(now_utc):
    days = (now_utc - REF_NEW_MOON).total_seconds() / 86400
    phase = days % SYNODIC
    if phase < SYNODIC / 2:
        name, left = "Повня", SYNODIC / 2 - phase
    else:
        name, left = "Новий місяць", SYNODIC - phase
    n = round(left)
    when = "сьогодні" if n == 0 else f"через {n} дн."
    return f"{name} {when}"


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

    f_big = font(96)
    f_h = font(26, True)
    f_bold = font(18, True)
    f_bold20 = font(20, True)
    f_t = font(22)
    f_s = font(18)
    f_xs = font(15)

    cur, hourly, daily = fc["current"], fc["hourly"], fc["daily"]
    T = 1  # index of today; past_days=1 puts yesterday at index 0

    # Header, left: condition icon and text
    base = base_kind(cur["weather_code"])
    cond = "Ясна ніч" if base == "clear" and not cur["is_day"] else KIND_TEXT[base]
    draw_icon(d, icon_name(cur["weather_code"], cur["is_day"]), 20, 26, 90)
    d.text((20, 124), cond, font=f_t, fill=0)

    # Header, middle: city, temperature, low on left, high on right
    d.text((270, 14), CITY, font=f_h, fill=0)
    d.text((266, 36), f"{round(cur['temperature_2m'])}°", font=f_big, fill=0)
    lo_today = round(daily["temperature_2m_min"][T])
    hi_today = round(daily["temperature_2m_max"][T])
    d.text((270, 150), f"Мін. {lo_today}°   Макс. {hi_today}°", font=f_s, fill=0)

    # Header, right: details
    wind = (f"{WIND_DIRS[round(cur['wind_direction_10m'] / 45) % 8]} "
            f"{round(cur['wind_speed_10m'])} км/год")
    stats = [
        ("Відчувається", f"{round(cur['apparent_temperature'])}°"),
        ("Вологість", f"{round(cur['relative_humidity_2m'])}%"),
        ("Тиск", f"{round(cur['pressure_msl'])} гПа"),
        ("Вітер", wind),
    ]
    for i, (label, value) in enumerate(stats):
        y = 26 + i * 38
        d.text((500, y), label, font=f_s, fill=0)
        d.text((780, y), value, font=f_bold20, fill=0, anchor="ra")
    d.text((780, 4), f"Оновлено {now:%H:%M}", font=f_xs, fill=0, anchor="ra")
    d.line((260, 10, 260, 170), fill=0, width=2)
    d.line((480, 10, 480, 170), fill=0, width=2)
    d.line((20, 180, 780, 180), fill=0, width=2)

    # Hourly precipitation: next 24 hours
    times = hourly["time"]
    now_key = now.strftime("%Y-%m-%dT%H:00")
    start = next((i for i, t in enumerate(times) if t >= now_key), 0)
    d.text((20, 188), "Опади, наступні 24 год", font=f_bold20, fill=0)
    base_y, chart_h = 320, 90
    d.text((50, 275), "50%", font=f_xs, fill=0, anchor="rm")
    d.text((50, base_y), "0", font=f_xs, fill=0, anchor="rm")
    for i in range(24):
        idx = start + i
        p = hourly["precipitation_probability"][idx] or 0
        mm = hourly["precipitation"][idx] or 0
        xc = 60 + 30 * i + 15
        h = p / 100 * chart_h
        if p > 0:
            d.rectangle((xc - 9, base_y - h, xc + 9, base_y), fill=0)
        if mm >= 0.1:
            d.text((xc, base_y - h - 4), f"{mm:.1f}", font=f_xs, fill=0, anchor="ms")
        if i % 3 == 0:
            d.text((xc, base_y + 6), times[idx][11:13] + ":00",
                   font=f_xs, fill=0, anchor="ma")
    d.line((60, base_y, 780, base_y), fill=0, width=1)
    d.line((20, 350, 780, 350), fill=0, width=2)

    # Five-day list with range bars scaled to the whole week
    days = list(range(T, T + 5))
    lows = [daily["temperature_2m_min"][k] for k in days]
    highs = [daily["temperature_2m_max"][k] for k in days]
    wmin, wmax = min(lows), max(highs)
    span = max(wmax - wmin, 1)
    TX0, TX1 = 200, 520
    for row, k in enumerate(days):
        cy = 360 + row * 28 + 14
        date = dt.date.fromisoformat(daily["time"][k])
        name = "Сьогодні" if k == T else WD_SHORT[date.weekday()]
        d.text((20, cy), name, font=f_bold, fill=0, anchor="lm")
        draw_icon(d, icon_name(daily["weather_code"][k], 1), 116, cy - 13, 26)
        d.text((190, cy), f"{round(lows[row])}°", font=f_s, fill=0, anchor="rm")
        d.rounded_rectangle((TX0, cy - 4, TX1, cy + 4), radius=4, fill=215)
        x0 = TX0 + (lows[row] - wmin) / span * (TX1 - TX0)
        x1 = max(TX0 + (highs[row] - wmin) / span * (TX1 - TX0), x0 + 8)
        d.rounded_rectangle((x0, cy - 4, x1, cy + 4), radius=4, fill=0)
        d.text((530, cy), f"{round(highs[row])}°", font=f_s, fill=0, anchor="lm")
        prob = daily["precipitation_probability_max"][k] or 0
        d.text((620, cy), f"Опади {prob}%", font=f_s, fill=0, anchor="lm")
    d.line((20, 500, 780, 500), fill=0, width=2)

    # Bottom bar: sun, moon, air, UV, rain today
    sr, ss = daily["sunrise"][T], daily["sunset"][T]
    day_change = round(minutes_between(sr, ss)
                       - minutes_between(daily["sunrise"][T - 1], daily["sunset"][T - 1]))
    d.text((20, 512), f"Схід {clock(sr)}", font=f_s, fill=0)
    d.text((20, 536), f"Захід {clock(ss)}", font=f_s, fill=0)
    d.text((20, 560), f"Світлового дня {minus(day_change)} хв", font=f_s, fill=0)

    draw_icon(d, "moon", 250, 508, 40)
    d.text((300, 514), moon_text(now.astimezone(dt.timezone.utc)), font=f_s, fill=0)

    today_str = now.strftime("%Y-%m-%d")
    precip_today = sum((v or 0) for t, v in zip(times, hourly["precipitation"])
                       if t.startswith(today_str))
    d.text((520, 512), f"Повітря: {aqi_text(aq)}", font=f_s, fill=0)
    d.text((520, 536), f"УФ-індекс: {round(daily['uv_index_max'][T])}", font=f_s, fill=0)
    d.text((520, 560), f"Опади сьогодні: {precip_today:.1f} мм", font=f_s, fill=0)

    # Calendar: bottom quarter, selected day inverted
    d.line((0, CAL_TOP, W, CAL_TOP), fill=0, width=2)
    today = now.date()
    d.text((30, CAL_TOP + 8), f"{MONTHS[today.month - 1]} {today.year}",
           font=f_bold20, fill=0)
    cw = (W - 60) / 7
    for c, name in enumerate(WD_SHORT):
        d.text((30 + cw * (c + 0.5), CAL_TOP + 34), name,
               font=f_xs, fill=0, anchor="ma")
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
                d.text((cx, cy), str(day_num), font=f_xs, fill=255, anchor="mm")
            else:
                d.text((cx, cy), str(day_num), font=f_xs, fill=0, anchor="mm")
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
