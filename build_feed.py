#!/usr/bin/env python3
"""
Salahadeen Al-Ayubi Masjid: today's Begins + Iqamah times from the homepage
-> subscribable .ics calendar with reminders.

Each run:
  1. Fetches https://salahadeenmosque.org.uk/ and reads the "Prayer Times" table
     (table.dptTimetable) - the date in its title and the Begins / Iqamah columns.
  2. Stores that day in data/times.json (history is kept, 30 days).
  3. Writes docs/prayer.ics with reminders:
       - an alarm at Begins
       - an alarm at Iqamah minus 10 min
       - if Begins and Iqamah are the same time, alarms 10 min before and on time.

No third-party packages needed (Python 3.9+ standard library).
"""
import datetime as dt
import html
import json
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

HOME = "https://salahadeenmosque.org.uk/"
TZ = ZoneInfo("Europe/London")
UTC = dt.timezone.utc
REMIND_BEFORE_IQAMAH = dt.timedelta(minutes=10)
EVENT_LENGTH = dt.timedelta(minutes=15)
PRAYERS = ["Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"]   # Sunrise is not a prayer

ROOT = Path(__file__).parent
DATA_FILE = ROOT / "data" / "times.json"
ICS_FILE = ROOT / "docs" / "prayer.ics"


class TimetableParser(HTMLParser):
    """Collects the text of every <th>/<td> inside table.dptTimetable, row by row."""

    def __init__(self):
        super().__init__()
        self.in_table = False
        self.depth = 0
        self.in_cell = False
        self.cell = []
        self.row = []
        self.rows = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table" and "dptTimetable" in (a.get("class") or ""):
            self.in_table = True
        if not self.in_table:
            return
        if tag == "table":
            self.depth += 1
        if tag == "tr":
            self.row = []
        if tag in ("th", "td"):
            self.in_cell = True
            self.cell = []

    def handle_endtag(self, tag):
        if not self.in_table:
            return
        if tag in ("th", "td") and self.in_cell:
            self.in_cell = False
            self.row.append(" ".join("".join(self.cell).split()))
        elif tag == "tr" and self.row:
            self.rows.append(self.row)
        elif tag == "table":
            self.depth -= 1
            if self.depth == 0:
                self.in_table = False

    def handle_data(self, data):
        if self.in_cell:
            self.cell.append(data)


def parse_homepage(page: str):
    """Return (date, {prayer: {'begin': 'HH:MM', 'iqamah': 'HH:MM'}}) from the homepage."""
    p = TimetableParser()
    p.feed(page)

    # Title cell contains e.g. "Prayer Times October 10, 2026 00:00:00 ..."
    m = re.search(r"Prayer Times\s+([A-Za-z]+ \d{1,2}, \d{4})", page)
    if not m:
        raise ValueError("date not found in timetable title")
    day = dt.datetime.strptime(m.group(1), "%B %d, %Y").date()

    def to24(s: str) -> str:
        t = dt.datetime.strptime(s.strip().lower(), "%I:%M %p")   # "1:45 pm" -> 13:45
        return t.strftime("%H:%M")

    times = {}
    for row in p.rows:
        if len(row) == 3 and row[0] in PRAYERS:
            times[row[0]] = {"begin": to24(row[1]), "iqamah": to24(row[2])}
    missing = [x for x in PRAYERS if x not in times]
    if missing:
        raise ValueError(f"missing prayers in table: {missing}")
    return day, times


def fetch_homepage() -> str:
    req = urllib.request.Request(HOME, headers={"User-Agent": "Mozilla/5.0 prayer-feed"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "ignore")


def to_dt(day: dt.date, hhmm: str) -> dt.datetime:
    h, m = map(int, hhmm.split(":"))
    return dt.datetime(day.year, day.month, day.day, h, m, tzinfo=TZ)


def ics_utc(d: dt.datetime) -> str:
    return d.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", r"\;").replace(",", r"\,").replace("\n", r"\n")


def build_ics(days: dict) -> str:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0",
             "PRODID:-//Salahadeen Masjid Prayer Times//EN",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
             "X-WR-CALNAME:Salahadeen Masjid Prayers",
             "X-WR-TIMEZONE:Europe/London",
             "REFRESH-INTERVAL;VALUE=DURATION:PT1H",
             "X-PUBLISHED-TTL:PT1H"]
    for day_s in sorted(days):
        day = dt.date.fromisoformat(day_s)
        for p in PRAYERS:
            info = days[day_s].get(p)
            if not info:
                continue
            B = to_dt(day, info["begin"])
            I = to_dt(day, info["iqamah"])
            R = I - REMIND_BEFORE_IQAMAH                 # 10 min before iqamah
            if B == I:                                   # prayer and iqamah at the same time
                alarms = [(R, f"{p} Iqamah at {info['iqamah']} in 10 min"),
                          (B, f"{p} begins and Iqamah now ({info['begin']})")]
            else:                                        # different times -> separate alerts
                alarms = [(B, f"{p} begins now ({info['begin']})"),
                          (R, f"{p} Iqamah at {info['iqamah']} in 10 min")]

            summary = f"{p} - Begins {info['begin']} / Iqamah {info['iqamah']}"
            desc = f"Begins {info['begin']}, Iqamah {info['iqamah']}. Source: salahadeenmosque.org.uk"
            lines += ["BEGIN:VEVENT",
                      f"UID:{day_s}-{p}@salahadeen-masjid-feed",
                      f"DTSTAMP:{ics_utc(to_dt(day, '00:00'))}",   # fixed per day, so unchanged runs produce identical files
                      f"DTSTART:{ics_utc(B)}",
                      f"DTEND:{ics_utc(B + EVENT_LENGTH)}",
                      f"SUMMARY:{esc(summary)}",
                      f"DESCRIPTION:{esc(desc)}",
                      "TRANSP:TRANSPARENT"]
            for when, msg in alarms:
                lines += ["BEGIN:VALARM",
                          "ACTION:DISPLAY",
                          f"DESCRIPTION:{esc(msg)}",
                          f"TRIGGER;VALUE=DATE-TIME:{ics_utc(when)}",
                          "END:VALARM"]
            lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def main():
    today_local = dt.datetime.now(TZ).date()
    days = json.loads(DATA_FILE.read_text()) if DATA_FILE.exists() else {}

    day, times = parse_homepage(fetch_homepage())
    print(f"homepage shows {day.isoformat()}: {times}")
    days[day.isoformat()] = times

    cutoff = (today_local - dt.timedelta(days=30)).isoformat()
    days = {d: v for d, v in days.items() if d >= cutoff}

    DATA_FILE.parent.mkdir(exist_ok=True)
    ICS_FILE.parent.mkdir(exist_ok=True)
    DATA_FILE.write_text(json.dumps(days, indent=1, sort_keys=True))
    ICS_FILE.write_text(build_ics(days), encoding="utf-8", newline="")
    print(f"wrote {ICS_FILE} with {len(days)} day(s)")


if __name__ == "__main__":
    main()
