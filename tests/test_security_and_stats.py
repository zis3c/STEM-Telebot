"""Unit tests for security_utils and stats_web."""
import os
import unittest

os.environ.setdefault("STATS_LINK_SECRET", "test-secret-demo-only-key")

import security_utils  # noqa: E402
import stats_web  # noqa: E402


class SecurityUtilsTests(unittest.TestCase):
    def test_parse_networks_and_ip_allowed(self):
        nets = security_utils.parse_networks("149.154.160.0/20, 91.108.4.0/22, invalid-cidr")
        self.assertEqual(len(nets), 2)
        self.assertTrue(security_utils.ip_allowed("149.154.161.10", nets))
        self.assertFalse(security_utils.ip_allowed("8.8.8.8", nets))
        self.assertFalse(security_utils.ip_allowed("not-an-ip", nets))

    def test_extract_client_ip_with_proxy_hops(self):
        self.assertEqual(
            security_utils.extract_client_ip("10.0.0.1", "203.0.113.5, 198.51.100.2", trust_proxy_hops=0),
            "10.0.0.1",
        )
        self.assertEqual(
            security_utils.extract_client_ip("10.0.0.1", "203.0.113.5, 198.51.100.2", trust_proxy_hops=1),
            "203.0.113.5",
        )

    def test_sliding_window_limiter(self):
        limiter = security_utils.SlidingWindowLimiter()
        ok1, _ = limiter.check("user:1", window_sec=60, max_req=2)
        ok2, _ = limiter.check("user:1", window_sec=60, max_req=2)
        ok3, retry = limiter.check("user:1", window_sec=60, max_req=2)
        self.assertTrue(ok1)
        self.assertTrue(ok2)
        self.assertFalse(ok3)
        self.assertGreaterEqual(retry, 1)

    def test_sanitize_sensitive_text(self):
        raw = "token=abc123XYZ email=user.name@example.com ic=990101081234 https://secret.example.test/a"
        cleaned = security_utils.sanitize_sensitive_text(raw)
        self.assertNotIn("abc123XYZ", cleaned)
        self.assertIn("token=***", cleaned)
        self.assertIn("u***@example.com", cleaned)
        self.assertIn("***REDACTED***", cleaned)
        self.assertIn("<url>", cleaned)


class StatsWebTests(unittest.TestCase):
    def test_demographic_report_token_lifecycle(self):
        payload = {"demographic_total": 42}
        token1 = stats_web.create_demographic_report(payload, ttl_seconds=600)
        read_payload, err = stats_web.read_demographic_report(token1)
        self.assertIsNone(err)
        self.assertEqual(read_payload, payload)

        # Creating a new report invalidates the previous token
        token2 = stats_web.create_demographic_report({"demographic_total": 99}, ttl_seconds=600)
        _, err_old = stats_web.read_demographic_report(token1)
        self.assertEqual(err_old, "not_found")
        read_new, err_new = stats_web.read_demographic_report(token2)
        self.assertIsNone(err_new)
        self.assertEqual(read_new, {"demographic_total": 99})

    def test_member_profile_report_and_tamper_detection(self):
        payload = {"matric": "D25317414", "status": "Verified"}
        token = stats_web.create_member_profile_report(payload, subject="D25317414", ttl_seconds=600)
        data, err = stats_web.read_member_profile_report(token)
        self.assertIsNone(err)
        self.assertEqual(data, payload)

        tampered = token[:-4] + "0000"
        _, err_tampered = stats_web.read_member_profile_report(tampered)
        self.assertEqual(err_tampered, "bad_signature")


if __name__ == "__main__":
    unittest.main()
