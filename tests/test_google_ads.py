from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from tds_ads_reporting.google_ads.ads import (
    GoogleAdsSummary,
    GoogleCampaign,
    _micros,
    fetch_campaigns,
)


class TestUtils(unittest.TestCase):
    def test_micros(self):
        self.assertEqual(_micros(2256000000), 2256.0)
        self.assertEqual(_micros(None), 0.0)


class _FakeMetrics:
    clicks = 100
    impressions = 5000
    ctr = 2.0
    average_cpc = 5000000
    cost_micros = 2256000000
    conversions = 12.0
    conversions_value = 1000.0
    cost_per_conversion = 188000000


class _FakeCampaign:
    id = 999001
    name = "Google Campaign A"
    status_ = MagicMock()
    status_.name = "ENABLED"
    advertising_channel_type_ = MagicMock()
    advertising_channel_type_.name = "SEARCH"


class _FakeRow:
    campaign = _FakeCampaign()
    metrics = _FakeMetrics()


class _FakeCustomer:
    currency_code = "EGP"
    time_zone = "Africa/Cairo"


class _FakeCustomerRow:
    customer = _FakeCustomer()


class _FakeBatch:
    results = [_FakeRow()]


class _FakeStream:
    def __iter__(self):
        yield _FakeBatch()


class _FakeCurBatch:
    results = [_FakeCustomerRow()]


class _FakeCurStream:
    def __iter__(self):
        yield _FakeCurBatch()


class _FakeGaService:
    def __init__(self):
        self.requests = []

    def search_stream(self, request):
        self.requests.append(request)
        if "FROM customer" in request.query:
            return _FakeCurStream()
        return _FakeStream()


class _Req:
    def __init__(self):
        self.customer_id = ""
        self.query = ""


class _FakeClient:
    def __init__(self):
        self._svc = _FakeGaService()

    def get_service(self, name):
        return self._svc

    def get_type(self, name):
        return _Req()


class TestFetchCampaigns(unittest.TestCase):
    @patch("tds_ads_reporting.google_ads.ads._get_client")
    def test_fetch(self, mock_get_client):
        mock_get_client.return_value = _FakeClient()
        summary = fetch_campaigns("/fake/google-ads.yaml", "1234567890", "2026-03")

        self.assertIsInstance(summary, GoogleAdsSummary)
        self.assertEqual(len(summary.campaigns), 1)
        self.assertEqual(summary.currency, "EGP")
        self.assertEqual(summary.timezone, "Africa/Cairo")
        self.assertEqual(summary.total_cost, 2256.0)
        self.assertEqual(summary.total_impressions, 5000)
        self.assertEqual(summary.total_clicks, 100)

        camp: GoogleCampaign = summary.campaigns[0]
        self.assertEqual(camp.name, "Google Campaign A")
        self.assertEqual(camp.results, 12.0)
        self.assertEqual(camp.cost_per_result, 188.0)
        self.assertEqual(camp.cost, 2256.0)
        self.assertEqual(camp.clicks, 100)

        # GAQL date range should be inclusive last day of month
        campaign_req = [r for r in mock_get_client.return_value._svc.requests if "FROM customer" not in r.query][0]
        query = campaign_req.query
        self.assertIn(">= '2026-03-01'", query)
        self.assertIn("<= '2026-03-31'", query)


if __name__ == "__main__":
    unittest.main()
