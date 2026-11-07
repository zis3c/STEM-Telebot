"""Tests for restart-safe scheduled message deletions."""
import json
import os
import tempfile
import time
import unittest

from stem_telebot.core import pending_deletions


class FakeJobQueue:
    def __init__(self):
        self.calls = []

    def run_once(self, callback, when, data=None, name=None):
        self.calls.append({"callback": callback, "when": when, "data": data, "name": name})


class FakeBot:
    def __init__(self):
        self.deleted = []

    async def delete_message(self, chat_id, message_id):
        self.deleted.append((chat_id, message_id))


class FakeApplication:
    def __init__(self):
        self.job_queue = FakeJobQueue()
        self.bot = FakeBot()


class PendingDeletionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_path = pending_deletions.PENDING_DELETIONS_PATH
        pending_deletions.PENDING_DELETIONS_PATH = os.path.join(self.tmp.name, "pending.json")

    def tearDown(self):
        pending_deletions.PENDING_DELETIONS_PATH = self.original_path
        self.tmp.cleanup()

    def _read(self):
        with open(pending_deletions.PENDING_DELETIONS_PATH, encoding="utf-8") as handle:
            return json.load(handle)

    def test_schedule_records_and_schedules(self):
        queue = FakeJobQueue()
        pending_deletions.schedule_message_deletion(queue, 11, 22, delay_seconds=30)
        self.assertEqual(len(queue.calls), 1)
        self.assertEqual(queue.calls[0]["data"], {"chat_id": 11, "message_id": 22})
        items = self._read()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["chat_id"], 11)
        self.assertEqual(items[0]["message_id"], 22)

    async def test_restore_deletes_expired_and_reschedules_future(self):
        pending_deletions._save([
            {"chat_id": 1, "message_id": 10, "delete_at": time.time() - 5},
            {"chat_id": 2, "message_id": 20, "delete_at": time.time() + 60},
        ])
        app = FakeApplication()
        await pending_deletions.restore_pending_deletions(app)
        self.assertEqual(app.bot.deleted, [(1, 10)])
        self.assertEqual(len(app.job_queue.calls), 1)
        self.assertEqual(app.job_queue.calls[0]["data"], {"chat_id": 2, "message_id": 20})
        self.assertGreater(app.job_queue.calls[0]["when"], 0)
        remaining = self._read()
        self.assertEqual([item["message_id"] for item in remaining], [20])

    async def test_restore_tolerates_missing_file(self):
        app = FakeApplication()
        await pending_deletions.restore_pending_deletions(app)
        self.assertEqual(app.bot.deleted, [])
        self.assertEqual(app.job_queue.calls, [])


if __name__ == "__main__":
    unittest.main()
