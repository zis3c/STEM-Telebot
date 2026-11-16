"""Regression tests for duplicate-aware student cache consumers."""
import time
import unittest

from stem_telebot.core.database import Database


def _row(name, matric, ic="990101012345", entry="2026-01-01", status="Approved"):
    row = [""] * 18
    row[0] = "2026-01-01 00:00:00"
    row[2] = name
    row[3] = matric
    row[4] = "CS"
    row[9] = ic
    row[10] = "1999-01-01"
    row[13] = entry
    row[15] = "MID1"
    row[17] = status
    return row


class StudentCacheConsumerTests(unittest.TestCase):
    def _db(self, cache):
        obj = object.__new__(Database)
        obj.CACHE_TTL = 600
        obj.last_student_refresh = time.time()
        obj.student_cache = cache
        obj._student_refresh_lock = None
        obj._student_refresh_in_progress = False
        return obj

    def test_find_member_returns_single_latest_entry(self):
        old = _row("Old Name", "A1234567")
        new = _row("New Name", "A1234567")
        db = self._db({"A1234567": [(old, 2), (new, 5)]})

        row, idx = db.find_member("a1234567")

        self.assertIs(row, new)
        self.assertEqual(idx, 5)

    def test_find_member_missing_returns_none_tuple(self):
        db = self._db({"A1234567": [(_row("X", "A1234567"), 2)]})
        self.assertEqual(db.find_member("ZZ999999"), (None, None))

    def test_get_stats_handles_duplicate_registrations(self):
        db = self._db({
            "A1234567": [
                (_row("One", "A1234567"), 2),
                (_row("Two", "A1234567"), 5),
            ]
        })
        stats = db.get_stats()
        self.assertEqual(stats["demographic_total"], 2)

    def test_get_members_flattens_duplicates(self):
        db = self._db({
            "A1234567": [
                (_row("One", "A1234567"), 2),
                (_row("Two", "A1234567"), 5),
            ]
        })
        self.assertEqual(len(db.get_members()), 2)

    def test_search_members_flattens_duplicates(self):
        db = self._db({
            "A1234567": [
                (_row("One", "A1234567"), 2),
                (_row("Two", "A1234567"), 5),
            ]
        })
        self.assertEqual(len(db.search_members("A1234567")), 2)

    def test_get_public_stats_counts_latest_non_expired_approved_only(self):
        from datetime import datetime, timedelta

        fresh_date = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")
        old_date = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")
        db = self._db({
            # Renewed member: old expired row + new active row -> counts once
            "A1": [
                (_row("One", "A1", entry=old_date, status="Expired"), 2),
                (_row("One", "A1", entry=fresh_date, status="Approved"), 3),
            ],
            # Active verified member
            "A2": [(_row("Two", "A2", entry=fresh_date, status="Verified"), 4)],
            # Expired by date even if sheet says Approved
            "A3": [(_row("Three", "A3", entry=old_date, status="Approved"), 5)],
            # Pending & rejected should not count
            "A4": [(_row("Four", "A4", entry=fresh_date, status="Pending"), 6)],
            "A5": [(_row("Five", "A5", entry=fresh_date, status="Rejected"), 7)],
        })

        stats = db.get_public_stats()

        self.assertEqual(set(stats.keys()), {"active_members", "cached_at"})
        self.assertEqual(stats["active_members"], 2)
        self.assertGreater(stats["cached_at"], 0)

    def test_get_registration_stats_all_filters(self):
        from datetime import datetime, timedelta

        # Reference anchor: mid-November 2026
        now = datetime(2026, 11, 16, 14, 30, 0)

        # Row builder helper
        def _date_row(name, matric, applied_dt, status="Approved"):
            row = [""] * 18
            row[0] = applied_dt.strftime("%Y-%m-%d %H:%M:%S")
            row[2] = name
            row[3] = matric
            row[4] = "CS"
            row[10] = "2000-01-01"
            row[13] = applied_dt.strftime("%Y-%m-%d")
            row[17] = status
            return row

        today_app = _date_row("Today Person", "M01", datetime(2026, 11, 16, 9, 0, 0), "Approved")
        today_pending = _date_row("Today Pending", "M02", datetime(2026, 11, 16, 10, 0, 0), "Pending")
        earlier_this_month = _date_row("Month Person", "M03", datetime(2026, 11, 5, 12, 0, 0), "Approved")
        prev_month_app = _date_row("Oct Person", "M04", datetime(2026, 10, 20, 11, 0, 0), "Approved")
        prev_month_rej = _date_row("Oct Rejected", "M05", datetime(2026, 10, 22, 16, 0, 0), "Rejected")
        prev_year_app = _date_row("2025 Person", "M06", datetime(2025, 6, 15, 10, 0, 0), "Approved")
        old_year_app = _date_row("2024 Person", "M07", datetime(2024, 3, 1, 10, 0, 0), "Approved")

        db = self._db({
            "M01": [(today_app, 2)],
            "M02": [(today_pending, 3)],
            "M03": [(earlier_this_month, 4)],
            "M04": [(prev_month_app, 5)],
            "M05": [(prev_month_rej, 6)],
            "M06": [(prev_year_app, 7)],
            "M07": [(old_year_app, 8)],
        })

        # 1. Today filter
        stats_today = db.get_registration_stats(filter_type="today", now=now)
        self.assertEqual(stats_today["total_applications"], 2)
        self.assertEqual(stats_today["approved_count"], 1)
        self.assertEqual(stats_today["pending_count"], 1)
        self.assertEqual(stats_today["rejected_count"], 0)
        self.assertEqual(stats_today["approved_names"], ["Today Person"])

        # 2. Month filter (November 2026)
        stats_month = db.get_registration_stats(filter_type="month", now=now)
        self.assertEqual(stats_month["total_applications"], 3)
        self.assertEqual(stats_month["approved_count"], 2)
        self.assertEqual(stats_month["pending_count"], 1)
        self.assertIn("Today Person", stats_month["approved_names"])
        self.assertIn("Month Person", stats_month["approved_names"])

        # 3. Previous month filter (October 2026)
        stats_prev_month = db.get_registration_stats(filter_type="prev_month", now=now)
        self.assertEqual(stats_prev_month["total_applications"], 2)
        self.assertEqual(stats_prev_month["approved_count"], 1)
        self.assertEqual(stats_prev_month["rejected_count"], 1)
        self.assertEqual(stats_prev_month["approved_names"], ["Oct Person"])

        # 4. Previous year filter (2025)
        stats_prev_year = db.get_registration_stats(filter_type="prev_year", now=now)
        self.assertEqual(stats_prev_year["total_applications"], 1)
        self.assertEqual(stats_prev_year["approved_count"], 1)
        self.assertEqual(stats_prev_year["approved_names"], ["2025 Person"])

        # 5. Dashboard stats with period breakdown
        dash = db.get_dashboard_stats(now=now)
        self.assertIn("periods", dash)
        self.assertEqual(set(dash["periods"].keys()), {"all", "today", "month", "prev_month", "prev_year"})
        self.assertEqual(dash["periods"]["today"]["approved"], 1)
        self.assertEqual(dash["periods"]["month"]["approved"], 2)
        self.assertEqual(dash["periods"]["prev_month"]["approved"], 1)
        self.assertEqual(dash["periods"]["prev_year"]["approved"], 1)
        self.assertEqual(dash["periods"]["all"]["approved"], 5)
        self.assertEqual(dash["periods"]["all"]["total_applications"], 7)


if __name__ == "__main__":
    unittest.main()
