"""Tests for demographic stats report rendering with period dropdown."""
import unittest
from stem_telebot.templates import demographic_stats_template


class DemographicStatsTemplateTests(unittest.TestCase):
    def test_render_with_periods_data(self):
        periods_data = {
            "all": {
                "label_en": "All Time",
                "label_ms": "Keseluruhan",
                "period_desc_en": "All Time (Whole DB)",
                "period_desc_ms": "Keseluruhan (Semua Rekod)",
                "total_applications": 20,
                "approved": 15,
                "pending": 3,
                "rejected": 2,
                "course_distribution": [{"label": "CS", "count": 10, "pct": 66.7}],
                "birth_year_distribution": [{"label": "2002", "count": 8, "pct": 53.3}],
                "members": ["Ahmad", "Siti"],
            },
            "month": {
                "label_en": "This Month",
                "label_ms": "Bulan Ini",
                "period_desc_en": "This Month (November 2026)",
                "period_desc_ms": "Bulan Ini (November 2026)",
                "total_applications": 5,
                "approved": 4,
                "pending": 1,
                "rejected": 0,
                "course_distribution": [{"label": "CS", "count": 4, "pct": 100.0}],
                "birth_year_distribution": [{"label": "2002", "count": 4, "pct": 100.0}],
                "members": ["Ahmad"],
            },
            "today": {
                "label_en": "Today",
                "label_ms": "Hari Ini",
                "period_desc_en": "Today (16 Nov 2026)",
                "period_desc_ms": "Hari Ini (16 Nov 2026)",
                "total_applications": 1,
                "approved": 1,
                "pending": 0,
                "rejected": 0,
                "course_distribution": [{"label": "CS", "count": 1, "pct": 100.0}],
                "birth_year_distribution": [{"label": "2002", "count": 1, "pct": 100.0}],
                "members": ["Ahmad"],
            },
        }

        html = demographic_stats_template.render_demographic_report(
            favicon_tag="",
            stats_month_year="November 2026",
            generated_at="2026-11-16 20:00:00",
            total=15,
            course_labels=["CS"],
            course_vals=[66.7],
            birth_labels=["2002"],
            birth_vals=[53.3],
            periods_data=periods_data,
            lang="MS",
        )

        self.assertIn("Dashboard Statistik Keahlian", html)
        self.assertIn('<select id="periodSelect"', html)
        self.assertIn('value="month"', html)
        self.assertIn('value="today"', html)
        self.assertIn('value="all"', html)
        self.assertIn('id="memberSearch"', html)
        self.assertIn('id="courseChart"', html)
        self.assertIn('id="birthChart"', html)

    def test_render_without_periods_data_fallback(self):
        html = demographic_stats_template.render_demographic_report(
            favicon_tag="",
            stats_month_year="November 2026",
            generated_at="2026-11-16 20:00:00",
            total=42,
            course_labels=["CS", "IT"],
            course_vals=[60.0, 40.0],
            birth_labels=["2001", "2002"],
            birth_vals=[50.0, 50.0],
            periods_data=None,
            lang="EN",
        )

        self.assertIn("Demographic & Stats Dashboard", html)
        self.assertIn('<select id="periodSelect"', html)
        self.assertIn('value="all"', html)


if __name__ == "__main__":
    unittest.main()
