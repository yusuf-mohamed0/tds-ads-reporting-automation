from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from tds_ads_reporting.meta.ads import (
    AdsSummary,
    CampaignRow,
    MetaAdsDataset,
    fetch_campaign_insights,
    fetch_meta_dataset,
    month_range,
    parse_float,
    parse_int,
)


class TestUtils(unittest.TestCase):
    def test_month_range(self):
        self.assertEqual(month_range("2026-03"), ("2026-03-01", "2026-03-31"))
        self.assertEqual(month_range("2026-12"), ("2026-12-01", "2026-12-31"))

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
        self.assertEqual(call_kwargs["params"]["time_range"], {"since": "2026-03-01", "until": "2026-03-31"})


class TestFetchMetaDataset(unittest.TestCase):
    """fetch_meta_dataset drives many get_insights calls; the mock dispatches on
    the params (level / breakdowns / time_increment) and fields."""

    def _mock_account(self, get_insights_side_effect):
        mock_account = MagicMock()
        mock_account.get_insights.side_effect = get_insights_side_effect
        mock_account.get_campaigns.return_value = [
            _FakeRow({"id": "111", "name": "Campaign A", "status": "ACTIVE"}),
            _FakeRow({"id": "222", "name": "Campaign B", "status": "PAUSED"}),
        ]
        return mock_account

    def _side_effect(self):
        def _dispatch(fields, params):
            level = params.get("level")
            breakdowns = params.get("breakdowns") or []
            if level == "adset":
                return [
                    _FakeRow(
                        {
                            "adset_id": "a1",
                            "adset_name": "LAL 1%",
                            "campaign_id": "111",
                            "campaign_name": "Campaign A",
                            "objective": "LEAD_GENERATION",
                            "results": "80",
                            "cost_per_result": "150.0",
                            "spend": "12000.00",
                            "impressions": "300000",
                            "reach": "240000",
                            "frequency": "1.25",
                            "ctr": "1.6",
                            "cpc": "3.0",
                            "cpm": "40.0",
                            "inline_link_clicks": "4000",
                        }
                    )
                ]
            if level == "account":
                return [
                    _FakeRow({"date_start": "2026-03-01", "spend": "1000.00"}),
                    _FakeRow({"date_start": "2026-03-02", "spend": "3000.00"}),
                ]
            if "hourly_stats_aggregated_by_audience_time_zone" in breakdowns:
                return [
                    _FakeRow({"hourly_stats_aggregated_by_audience_time_zone": "1:14", "spend": "500.00"}),
                    _FakeRow({"hourly_stats_aggregated_by_audience_time_zone": "2:09", "spend": "300.00"}),
                ]
            if breakdowns:
                if "age" in breakdowns:
                    return [
                        _FakeRow(
                            {
                                "age": "18-24",
                                "gender": "F",
                                "spend": "1200.00",
                                "impressions": "30000",
                                "inline_link_clicks": "100",
                                "results": "10",
                            }
                        )
                    ]
                return [
                    _FakeRow(
                        {
                            breakdowns[0]: "mobile",
                            "spend": "2000.00",
                            "impressions": "50000",
                            "inline_link_clicks": "100",
                            "results": "5",
                        }
                    )
                ]
            if "results" in fields:
                # per-campaign insights (current or previous month)
                return _make_fake_rows()
            # conversion breakdown
            return [
                _FakeRow(
                    {
                        "campaign_id": "111",
                        "campaign_name": "Campaign A",
                        "spend": "1806.00",
                        "actions": [{"action_type": "lead", "value": "12"}],
                        "cost_per_action_type": [{"action_type": "lead", "value": "1806.00"}],
                    }
                )
            ]

        return _dispatch

    @patch("facebook_business.adobjects.adaccount.AdAccount")
    @patch("facebook_business.api.FacebookAdsApi")
    def test_fetch_full_dataset(self, mock_api, mock_adaccount_cls):
        mock_account = self._mock_account(self._side_effect())
        mock_adaccount_cls.return_value = mock_account

        ds = fetch_meta_dataset("tok", "v26.0", "123456789", "2026-03")

        self.assertIsInstance(ds, MetaAdsDataset)
        self.assertEqual(len(ds.campaigns), 2)
        self.assertEqual(ds.campaigns[0].status, "ACTIVE")
        self.assertEqual(ds.campaigns[1].status, "PAUSED")
        self.assertEqual(ds.adsets[0]["adset_name"], "LAL 1%")
        self.assertEqual(ds.conversions["lead"]["count"], 12)
        self.assertEqual(ds.conversions["lead"]["cpa"], 150.5)
        self.assertEqual(ds.devices[0]["label"], "mobile")
        self.assertEqual(ds.devices[0]["pct"], 100.0)
        self.assertEqual(ds.publishers[0]["label"], "mobile")
        self.assertEqual(ds.countries[0]["label"], "mobile")
        self.assertEqual(ds.demographics[0]["age"], "18-24")
        self.assertEqual(ds.demographics[0]["gender"], "F")
        self.assertEqual(ds.dow_pacing["Monday"]["spend"], 500.0)
        self.assertEqual(ds.dow_pacing["Sunday"]["spend"], 0.0)
        self.assertEqual(ds.hour_pacing["14"]["spend"], 500.0)
        self.assertEqual(ds.hour_pacing["09"]["spend"], 300.0)
        self.assertEqual(ds.daily_spend[0], {"date": "2026-03-01", "spend": 1000.0})
        self.assertEqual(ds.totals["spend"], 2256.0)
        self.assertEqual(ds.totals["results"], 17)
        self.assertEqual(ds.prev_month["month"], "2026-02")
        self.assertEqual(ds.prev_month["totals"]["spend"], 2256.0)
        self.assertEqual(ds.prev_month["campaigns"][0]["campaign_id"], "111")

    @patch("facebook_business.adobjects.adaccount.AdAccount")
    @patch("facebook_business.api.FacebookAdsApi")
    def test_graceful_degradation(self, mock_api, mock_adaccount_cls):
        """A failing optional breakdown must not kill the dataset fetch."""
        calls = {"n": 0}

        def _flaky(fields, params):
            calls["n"] += 1
            if calls["n"] == 2:  # second get_insights call = adsets fetch
                raise RuntimeError("breakdown not supported")
            return self._side_effect()(fields, params)

        mock_account = self._mock_account(_flaky)
        mock_adaccount_cls.return_value = mock_account

        ds = fetch_meta_dataset("tok", "v26.0", "123456789", "2026-03")

        self.assertEqual(len(ds.campaigns), 2)
        self.assertEqual(ds.adsets, [])
        self.assertEqual(ds.conversions["lead"]["count"], 12)
        self.assertEqual(ds.totals["spend"], 2256.0)

    @patch("facebook_business.adobjects.adaccount.AdAccount")
    @patch("facebook_business.api.FacebookAdsApi")
    def test_campaign_fetch_failure_returns_empty(self, mock_api, mock_adaccount_cls):
        mock_account = MagicMock()
        mock_account.get_insights.side_effect = RuntimeError("api down")
        mock_adaccount_cls.return_value = mock_account

        ds = fetch_meta_dataset("tok", "v26.0", "123456789", "2026-03")
        self.assertIsInstance(ds, MetaAdsDataset)
        self.assertEqual(ds.campaigns, [])


if __name__ == "__main__":
    unittest.main()
