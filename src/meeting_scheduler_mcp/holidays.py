"""
Holiday service for calendar component.
"""

from datetime import date
from typing import Optional, Protocol, cast

import pandas as pd
from pandas.tseries.holiday import (
    AbstractHolidayCalendar,
    EasterMonday,
    GoodFriday,
    Holiday,
)
from pandas.tseries.offsets import Day, Easter


class HolidayRule(Protocol):
    """Protocol for holiday rules that have a name attribute."""

    name: str

    def dates(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DatetimeIndex: ...


class GermanBankHolidays(AbstractHolidayCalendar):
    """German public holidays."""

    rules = [
        Holiday("New Year's Day", month=1, day=1),
        GoodFriday,
        EasterMonday,
        Holiday("Ascension Day", month=1, day=1, offset=[Easter(), Day(39)]),
        Holiday("Whit Monday", month=1, day=1, offset=[Easter(), Day(50)]),
        Holiday("Labor Day", month=5, day=1),
        Holiday("German Unity Day", month=10, day=3),
        Holiday("Reformation Day", month=10, day=31),
        Holiday("Christmas Eve", month=12, day=24),
        Holiday("Christmas Day", month=12, day=25),
        Holiday("Boxing Day", month=12, day=26),
        Holiday("New Year's Eve", month=12, day=31),
    ]


class HolidayChecker:
    """Checks if a date is a holiday."""

    _calendars: dict[str, AbstractHolidayCalendar] = {
        "DE": GermanBankHolidays(),
    }

    def __init__(self, country_code: Optional[str] = None):
        self.country_code = country_code
        self._holidays: set[date] = set()

        if country_code and country_code in self._calendars:
            cal = self._calendars[country_code]
            # Cache holidays for the next 3 years (including current year)
            start = pd.Timestamp.now().floor("D") - pd.DateOffset(years=1)
            end = start + pd.DateOffset(years=3)
            holidays = cal.holidays(start=start, end=end)
            self._holidays = {d.date() for d in holidays}

    def is_holiday(self, d: date) -> bool:
        """Checks if date is a holiday."""
        return d in self._holidays

    def get_holiday_name(self, d: date) -> Optional[str]:
        """Returns holiday name or None."""
        if not self.country_code or self.country_code not in self._calendars:
            return None

        cal = self._calendars[self.country_code]
        ts = pd.Timestamp(d)

        for rule in cal.rules:
            try:
                rule_dates = rule.dates(ts, ts + pd.DateOffset(days=1))
                if len(rule_dates) > 0 and rule_dates[0].date() == d:
                    return cast(HolidayRule, rule).name
            except (ValueError, KeyError, AttributeError):
                continue

        return None
