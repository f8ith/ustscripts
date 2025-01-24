from beautiful_date import Sept, Nov

### CONFIG ###
SEMESTER = "Fall 24-25"
START_DATE = (2 / Sept / 2024)
END_DATE = (30 / Nov / 2024)
COOKIES = {}
CANVAS_TOKEN = ""
IPRS = {
    "PHPSESSID":  "",
    "POOL_SIZE":  10
}

def assign_color(course: dict):
    match course["subject"]:
        case _:
            return "8"
