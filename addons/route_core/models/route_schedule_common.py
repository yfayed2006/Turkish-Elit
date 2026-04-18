from datetime import timedelta

from odoo import fields

WEEKDAY_SELECTION = [
    ("monday", "Monday"),
    ("tuesday", "Tuesday"),
    ("wednesday", "Wednesday"),
    ("thursday", "Thursday"),
    ("friday", "Friday"),
    ("saturday", "Saturday"),
    ("sunday", "Sunday"),
]

WEEKDAY_INDEX = {code: index for index, (code, _label) in enumerate(WEEKDAY_SELECTION)}
WEEKDAY_LABELS = dict(WEEKDAY_SELECTION)


def compute_week_start_date(reference_date, week_start_day="monday"):
    """Return the start date of the work week for the given reference date."""
    reference_date = fields.Date.to_date(reference_date)
    if not reference_date:
        return False

    start_index = WEEKDAY_INDEX.get(week_start_day or "monday", 0)
    current_index = reference_date.weekday()
    delta_days = (current_index - start_index) % 7
    return reference_date - timedelta(days=delta_days)



def compute_weekday_date(week_start_date, weekday_code, week_start_day="monday"):
    week_start_date = fields.Date.to_date(week_start_date)
    if not week_start_date:
        return False

    start_index = WEEKDAY_INDEX.get(week_start_day or "monday", 0)
    weekday_index = WEEKDAY_INDEX.get(weekday_code or "monday", 0)
    day_offset = (weekday_index - start_index) % 7
    return week_start_date + timedelta(days=day_offset)
