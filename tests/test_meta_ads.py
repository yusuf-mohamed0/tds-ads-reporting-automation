from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from tds_ads_reporting.meta.ads import (
    AdsSummary,
    CampaignRow,
    fetch_campaign_insights,
    month_range,
    parse_float,
    parse_int,
)


class TestUtils(unittest.TestCase):
    def test_month_range(self):
        self.assertEqual(month_range("2026-03"), ("2026-03-01", "2026-04-01"))
        self.assertEqual(month_range("2026-12"), ("2026-12-01", "2027-01-01"))

    def test_parse(self):
        self.assertEqual(parse_float("42.5"), 42.5)
        self.assertEqual(parse_float(None), 0.0)
        self.assertEqual(parse_int("100"), 100)
        self.assertEqual(parse_int(None), 0)


class _FakeRow(dict):
    def export_all_data(self) -> dict:
        return dict(self)


def _make_fake_rows():
    return [
        _FakeRow(
            {
                "campaign_id": "111",
                "campaign_name": "Campaign A",
                "objective": "MESSENGER",
                "results": "12",
                "cost_per_result": "150.5",
                "spend": "1806.00",
                "impressions": "50000",
                "reach": "40000",
                "frequency": "1.25",
                "ctr": "1.5",
                "cpc": "3.0",
                "cpm": "36.12",
                "inline_link_clicks": "750",
                "account_currency": "EGP",
            }
        ),
        _FakeRow(
            {
                "campaign_id": "222",
                "campaign_name": "Campaign B",
                "objective": "LEAD_GENERATION",
                "results": "5",
                "cost_per_result": "90.0",
                "spend": "450.00",
                "impressions": "20000",
                "reach": "15000",
                "frequency": "1.33",
                "ctr": "0.9",
                "cpc": "2.5",
                "cpm": "22.50",
                "inline_link_clicks": "180",
                "account_currency": "EGP",
            }
        ),
    ]


class TestFetchCampaignInsights(unittest.TestCase):
    @patch("facebook_business.adobjects.adaccount.AdAccount")
    @patch("facebook_business.api.FacebookAdsApi")
    def test_fetch(self, mock_api, mock_adaccount_cls):
        mock_account = MagicMock()
        mock_account.get_insights.return_value = _make_fake_rows()
        mock_adaccount_cls.return_value = mock_account

        summary = fetch_campaign_insights("tok", "v26.0", "123456789", "2026-03")

        self.assertIsInstance(summary, AdsSummary)
        self.assertEqual(len(summary.campaigns), 2)
        self.assertEqual(summary.total_spend, 2256.0)
        self.assertEqual(summary.total_impressions, 70000)
        self.assertEqual(summary.total_results, 17)
        self.assertEqual(summary.currency, "EGP")

        first: CampaignRow = summary.campaigns[0]
        self.assertEqual(first.campaign_name, "Campaign A")
        self.assertEqual(first.results, 12)
        self.assertEqual(first.cost_per_result, 150.5)
        self.assertEqual(first.spend, 1806.0)
        self.assertEqual(first.clicks, 750)

        mock_adaccount_cls.assert_called_once_with("act_123456789")
        call_kwargs = mock_account.get_insights.call_args[1]
        self.assertEqual(call_kwargs["params"]["level"], "campaign")
        self.assertEqual(call_kwargs["params"]["time_range"], {"since": "2026-03-01", "until": "2026-04-01"})


if __name__ == "__main__":
    unittest.main()
