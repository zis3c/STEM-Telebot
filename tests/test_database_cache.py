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


if __name__ == "__main__":
    unittest.main()
