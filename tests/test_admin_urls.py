"""Tests for admin document URL normalization."""
import os
import unittest

os.environ.setdefault("SHEET_ID", "test-sheet")
os.environ.setdefault("GOOGLE_CREDENTIALS", "{\"type\":\"service_account\"}")

from stem_telebot.handlers import admin  # noqa: E402


class DocUrlTests(unittest.TestCase):
    def test_drive_open_url_is_normalized_and_trusted(self):
        url, trusted = admin._normalize_doc_url("https://drive.google.com/open?id=abc")
        self.assertTrue(trusted)
        self.assertEqual(url, "https://drive.google.com/uc?export=download&id=abc")

    def test_untrusted_host_is_rejected(self):
        url, trusted = admin._normalize_doc_url(
            "https://evil.com/drive.google.com/open?id=abc"
        )
        self.assertFalse(trusted)
        self.assertEqual(url, "https://evil.com/drive.google.com/open?id=abc")

    def test_http_scheme_is_rejected(self):
        _, trusted = admin._normalize_doc_url("http://drive.google.com/open?id=abc")
        self.assertFalse(trusted)


if __name__ == "__main__":
    unittest.main()
