from __future__ import annotations

import unittest
from unittest.mock import patch

from tds_ads_reporting.meta.page import (
    InstagramMetrics,
    PageMetrics,
    fetch_instagram_metrics,
    fetch_page_metrics,
    fetch_top_posts,
)


def _insight(metric: str, period: str, values: list[float], extra: dict | None = None):
    return {
        "data": [
            {
                "name": metric,
                "period": period,
                "values": [{"value": v, **(extra or {})} for v in values],
            }
        ]
    }


class TestFetchPageMetrics(unittest.TestCase):
    @patch("tds_ads_reporting.meta.page._request")
    def test_page_metrics(self, mock_request):
        calls = {"n": 0}

        def fake_request(token, ver, path, params):
            metric = params.get("metric", "")
            if metric == "page_total_media_view_unique":
                return _insight(metric, "day", [1000, 2000, 3000])
            if metric == "page_media_view":
                return {
                    "data": [
                        {
                            "values": [
                                {
                                    "value": 2500,
                                    "breakdowns": [
                                        {"dimension": "is_from_ads", "value": "false"}
                                    ],
                                },
                                {
                                    "value": 3500,
                                    "breakdowns": [
                                        {"dimension": "is_from_ads", "value": "true"}
                                    ],
                                },
                            ]
                        }
                    ]
                }
            if metric == "page_follows":
                if params.get("period") == "lifetime":
                    return _insight(metric, "lifetime", [12345])
                return _insight(metric, "day", [5, -2, 3])
            if metric == "page_messages_new_conversations_unique":
                return _insight(metric, "total_over_range", [7])
            if metric == "page_messages_sent":
                return _insight(metric, "day", [10, 20])
            if metric == "page_follows_country":
                return {"data": [{"values": [{"value": [{"name": "Egypt", "value": 100}]}]}]}
            calls["n"] += 1
            return {"data": []}

        mock_request.side_effect = fake_request
        m = fetch_page_metrics("tok", "v26.0", "123", "2026-03")

        self.assertIsInstance(m, PageMetrics)
        self.assertEqual(m.media_views, 6000)
        self.assertEqual(m.organic_views, 2500)
        self.assertEqual(m.paid_views, 3500)
        self.assertEqual(m.followers_total, 12345)
        self.assertEqual(m.followers_delta, 6)
        self.assertEqual(m.new_conversations, 7)
        self.assertEqual(m.messages_sent, 30)
        self.assertEqual(m.organic_pct, 42)


class TestFetchTopPosts(unittest.TestCase):
    @patch("tds_ads_reporting.meta.page._request")
    @patch("tds_ads_reporting.meta.page._paginate")
    def test_top_posts(self, mock_paginate, mock_request):
        mock_paginate.return_value = [
            {
                "id": "123_1",
                "created_time": "2026-03-05T10:00:00+0000",
                "permalink_url": "https://fb.com/p1",
                "message": "First post",
            },
            {
                "id": "123_2",
                "created_time": "2026-03-15T10:00:00+0000",
                "permalink_url": "https://fb.com/p2",
                "message": "Second post",
            },
        ]

        def fake_request(token, ver, path, params):
            return _insight("post_total_media_view_unique", "lifetime", [500])

        mock_request.side_effect = fake_request
        rows = fetch_top_posts("tok", "v26.0", "123", "2026-03")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].views, 500)


class TestFetchInstagram(unittest.TestCase):
    @patch("tds_ads_reporting.meta.page._request")
    @patch("tds_ads_reporting.meta.page._paginate")
    def test_ig_metrics(self, mock_paginate, mock_request):
        def fake_request(token, ver, path, params):
            if "media" in path and "insights" in path:
                return _insight("reach", "lifetime", [300])
            if "followers_count" in params.get("fields", ""):
                return {"followers_count": 5000}
            if "follower_demographics" in params.get("metric", ""):
                return {"data": [{"values": [{"value": {"18-24": {"F": 10, "M": 5}}}]}]}
            metric = params.get("metric", "")
            if metric == "reach":
                return _insight(metric, "day", [100, 200])
            if metric == "views":
                return _insight(metric, "day", [300, 400])
            if metric == "accounts_engaged":
                return _insight(metric, "day", [50])
            return {"data": []}

        mock_request.side_effect = fake_request
        mock_paginate.return_value = [
            {"id": "ig_1", "timestamp": "2026-03-10T10:00:00+0000"}
        ]

        m = fetch_instagram_metrics("tok", "v26.0", "ig123", "2026-03")
        self.assertIsInstance(m, InstagramMetrics)
        self.assertEqual(m.reach, 300)
        self.assertEqual(m.views, 700)
        self.assertEqual(m.accounts_engaged, 50)
        self.assertEqual(m.followers_count, 5000)


if __name__ == "__main__":
    unittest.main()
