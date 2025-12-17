"""
Test cases for holiday service.
"""

from datetime import date
from freezegun import freeze_time

from meeting_scheduler_mcp.holidays import HolidayChecker


class TestHolidayChecker:

    @freeze_time("2024-01-01")
    def test_german_fixed_holidays(self):
        checker = HolidayChecker("DE")

        assert checker.is_holiday(date(2025, 1, 1))   # Neujahr
        assert checker.is_holiday(date(2025, 5, 1))   # Tag der Arbeit
        assert checker.is_holiday(date(2025, 10, 3))  # Tag der Deutschen Einheit
        assert checker.is_holiday(date(2025, 12, 25)) # Weihnachten
        assert checker.is_holiday(date(2025, 12, 26))

    @freeze_time("2024-01-01")
    def test_german_easter_holidays_2025(self):
        checker = HolidayChecker("DE")

        # Ostern 2025: 20. April
        assert checker.is_holiday(date(2025, 4, 18))  # Karfreitag
        assert checker.is_holiday(date(2025, 4, 21))  # Ostermontag
        assert checker.is_holiday(date(2025, 5, 29))  # Christi Himmelfahrt
        assert checker.is_holiday(date(2025, 6, 9))   # Pfingstmontag

    def test_regular_day_not_holiday(self):
        checker = HolidayChecker("DE")

        assert not checker.is_holiday(date(2025, 3, 15))  # Normaler Samstag
        assert not checker.is_holiday(date(2025, 7, 14))  # Normaler Montag

    def test_no_holidays_without_country(self):
        checker = HolidayChecker(None)

        assert not checker.is_holiday(date(2025, 12, 25))

    def test_holiday_name(self):
        checker = HolidayChecker("DE")

        assert checker.get_holiday_name(date(2025, 1, 1)) == "New Year's Day"
        assert checker.get_holiday_name(date(2025, 12, 25)) == "Christmas Day"