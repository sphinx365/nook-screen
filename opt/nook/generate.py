#!/usr/bin/env python3
import calendar
import datetime as dt
from zoneinfo import ZoneInfo

import requests
from PIL import Image, ImageDraw, ImageFont

LAT, LON = 50.45, 30.52            # ваші координати (приклад — Київ)
TZ = "Europe/Kyiv"
W, H = 600, 800                    # перевірте розмір у README клієнта
OUT = "/opt/nook/www/screen.png"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
FONT_B = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

WMO = {0: "Ясно", 1: "Переважно ясно", 2: "Мінлива хмарн.", 3: "Хмарно",
       45: "Туман", 48: "Туман", 51: "Мряка", 53: "Мряка", 55: "Мряка",
       61: "Дощ", 63: "Дощ", 65: "Сильний дощ", 71: "Сніг", 73: "Сніг",
       75: "Сильний сніг", 80: "Злива", 81: "Злива", 82: "Злива", 95: "Гроза"}
WD_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Нд"]
MONTHS = ["Січень", "Лютий", "Березень", "Квітень", "Травень", "Червень",
          "Липень", "Серпень", "Вересень", "Жовтень", "Листопад", "Грудень"]

f_big = ImageFont.truetype(FONT_B, 64)
f_mid = ImageFont.truetype(FONT, 28)
f_bold = ImageFont.truetype(FONT_B, 28)
f_sm = ImageFont.truetype(FONT, 22)


def get_weather():
    r = requests.get("https://api.open-meteo.com/v1/forecast", timeout=10, params={
        "latitude": LAT, "longitude": LON, "timezone": TZ,
        "current": "temperature_2m,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min,weather_code",
        "forecast_days": 3,
    })
    r.raise_for_status()
    return r.json()


def draw_header(d, data):
    cur, day = data["current"], data["daily"]
    for col in range(3):                       # сьогодні + 2 наступні дні
        x = 20 + col * 195
        if col == 0:
            label = "Сьогодні"
            big = f"{round(cur['temperature_2m'])}°"
            code = cur["weather_code"]
        else:
            label = WD_SHORT[dt.date.fromisoformat(day["time"][col]).weekday()]
            big = f"{round(day['temperature_2m_max'][col])}°"
            code = day["weather_code"][col]
        mn = round(day["temperature_2m_min"][col])
        mx = round(day["temperature_2m_max"][col])
        d.text((x, 20), label, font=f_bold, fill=0)
        d.text((x, 55), big, font=f_big, fill=0)
        d.text((x, 130), f"{mn}°…{mx}°", font=f_sm, fill=0)
        d.text((x, 160), WMO.get(code, ""), font=f_sm, fill=0)


def draw_calendar(d, today):
    top = 240
    d.text((W // 2, top), f"{MONTHS[today.month - 1]} {today.year}",
           font=f_bold, fill=0, anchor="mt")
    cw = W // 7
    y = top + 50
    for i, name in enumerate(WD_SHORT):
        d.text((i * cw + cw // 2, y), name, font=f_sm, fill=0, anchor="mt")
    rh = 72
    weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(today.year, today.month)
    for r, week in enumerate(weeks):
        for c, day in enumerate(week):
            if not day:
                continue
            x0, y0 = c * cw + 4, y + 40 + r * rh
            cx, cy = c * cw + cw // 2, y0 + rh // 2 - 6
            if day == today.day:               # інверсія: білий текст на чорному
                d.rounded_rectangle((x0, y0, x0 + cw - 8, y0 + rh - 12), radius=14, fill=0)
                d.text((cx, cy), str(day), font=f_bold, fill=255, anchor="mm")
            else:
                d.text((cx, cy), str(day), font=f_mid, fill=0, anchor="mm")


def main():
    today = dt.datetime.now(ZoneInfo(TZ)).date()
    img = Image.new("L", (W, H), 255)          # 8-бітна сірі відтінки, добре для e-ink
    d = ImageDraw.Draw(img)
    draw_header(d, get_weather())
    d.line((20, 215, W - 20, 215), fill=0, width=2)
    draw_calendar(d, today)
    img.save(OUT, optimize=True)


if __name__ == "__main__":
    main()
