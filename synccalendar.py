import logging
import os
import time
import traceback
import config
import pickle
from gcsa.calendar import Calendar
from gcsa.event import Event
from gcsa.google_calendar import GoogleCalendar
from gcsa.recurrence import FRIDAY, THURSDAY, TUESDAY, WEDNESDAY, MONDAY, Recurrence, WEEKLY

from beautiful_date import days
import requests
import webview

### CONSTS ##
URL = "https://admlu65.ust.hk/course/enrl/2410?enrolled=Y"
START_DATE_WEEKDAY = config.START_DATE.weekday()
START_DATES = []
WEEKDAYS = [MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY]

for i in range(5):
    if i >= START_DATE_WEEKDAY:
        START_DATES.append((config.START_DATE + (i - START_DATE_WEEKDAY) * days))
    else:
        START_DATES.append(config.START_DATE + (7 + i - START_DATE_WEEKDAY) * days)

gc = GoogleCalendar()  # type: ignore
headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
}
session = requests.Session()
session.headers = headers  # type: ignore
calendar = Calendar(config.SEMESTER)  # type: ignore

cookies: dict = {}

if config.COOKIES:
    cookies = config.COOKIES
elif os.path.exists("cookies.pickle"):
    with open("cookies.pickle", "rb") as f:
        cookies = pickle.load(f)


def detect_login(window):
    global cookies
    while True:
        time.sleep(3)
        if URL in window.get_current_url():
            for cookie in window.get_cookies():
                cookies.update({k: v.value for k, v in cookie.items()})
            window.destroy()
            with open("cookies.pickle", "wb") as f:
                f.seek(0)
                pickle.dump(cookies, f, pickle.HIGHEST_PROTOCOL)
            break

if not cookies:
    window = webview.create_window("Login to Microsoft SSO", URL)
    webview.start(detect_login, window, private_mode=False)  # type: ignore

try:
    r = requests.get(URL, cookies=cookies)
    courses = r.json()
    calendar = gc.add_calendar(calendar)
    for index, c in enumerate(courses):
        if c["sessions"]:
            n = 0
            session_weekdays = []
            while n < len(c["sessions"]):
                s = c["sessions"][n]
                session_weekdays.append(WEEKDAYS[s['dayOfWeek'] - 1])
                timing = [c["sessions"][n+1]["startTime"], c["sessions"][n+1]["endTime"]] if n+1 < len(c["sessions"]) else 0
                if s["startTime"] != 0 and [s["startTime"], s["endTime"]] != timing:
                    event = Event(
                        f"{c['subject']} {c['code']} - {s['section']}",
                        start=START_DATES[s["dayOfWeek"] - 1][
                            int(s["startTime"][0:2]) : int(s["startTime"][2:])
                        ],
                        end=START_DATES[s["dayOfWeek"] - 1][
                            int(s["endTime"][0:2]) : int(s["endTime"][2:])
                        ],
                        color_id=config.assign_color(c),
                        location=s["venue"],
                        recurrence=[
                            Recurrence.rule(freq=WEEKLY, until=config.END_DATE,by_week_day=session_weekdays),
                        ],
                    )
                    print(event)
                    gc.add_event(event, calendar_id=calendar.id)  # type: ignore
                    session_weekdays = []
                n += 1
except Exception as e:
    logging.error(traceback.format_exc())
    os.error(1)

session.close()
