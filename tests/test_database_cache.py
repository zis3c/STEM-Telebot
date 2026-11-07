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


if __name__ == "__main__":
    unittest.main()
