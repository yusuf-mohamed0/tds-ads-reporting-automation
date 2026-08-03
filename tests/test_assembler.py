from __future__ import annotations

import unittest
from unittest.mock import patch

from tds_ads_reporting.config import Client, GoogleAdsConfig, MetaConfig
from tds_ads_reporting.manual_inputs.loader import ManualInputs
from tds_ads_reporting.meta.ads import AdsSummary, CampaignRow
from tds_ads_reporting.meta.page import InstagramMetrics, PageMetrics, PostRow
from tds_ads_reporting.google_ads.ads import GoogleAdsSummary, GoogleCampaign
from tds_ads_reporting.reporting.assembler import FetchedData, build_context
from tds_ads_reporting.reporting.pdf import render_pdf


def _client() -> Client:
    return Client(
        id="lodge",
        name="Lodge",
        report_recipient="reports@trafficdigitalsolutions.com",
        currency="EGP",
        meta=MetaConfig(
            ad_accounts=["act_123"],
            page_id="123",
            instagram_id="456",
        ),
        google_ads=GoogleAdsConfig(customer_ids=["777"]),
    )


def _data() -> FetchedData:
    return FetchedData(
        meta_ads=AdsSummary(
            account_id="act_123",
            month="2026-03",
            currency="EGP",
            campaigns=[
                CampaignRow(
                    campaign_id="1",
                    campaign_name="Leads Campaign",
                    objective="LEAD_GENERATION",
                    results=12,
                    cost_per_result=150.5,
                    spend=1806.0,
                    impressions=50000,
                    reach=40000,
                    frequency=1.25,
                    ctr=1.5,
                    cpc=3.0,
                    cpm=36.12,
                    inline_link_clicks=750,
                )
            ],
        ),
        page=PageMetrics(
            page_id="123",
            media_views=6000,
            organic_views=2500,
            paid_views=3500,
            followers_total=12345,
            followers_delta=6,
            new_conversations=7,
            messages_sent=30,
        ),
        top_posts=[
            PostRow(
                post_id="123_1",
                created_time="2026-03-05T10:00:00+0000",
                permalink="https://fb.com/p1",
                message="Spring promo is live",
                views=1500,
            )
        ],
        instagram=InstagramMetrics(
            ig_id="456",
            reach=300,
            views=700,
            accounts_engaged=50,
            followers_count=5000,
            top_media=[{"id": "ig_1", "timestamp": "2026-03-10T10:00:00+0000", "reach": 300, "views": 400}],
            demographics=[
                {"values": [{"value": {"18-24": {"F": 10, "M": 5}, "25-34": {"F": 20, "M": 15}}}]}
            ],
        ),
        google_ads=GoogleAdsSummary(
            customer_id="777",
            month="2026-03",
            currency="EGP",
            timezone="Africa/Cairo",
            campaigns=[
                GoogleCampaign(
                    campaign_id=999,
                    name="Search Campaign",
                    status="ENABLED",
                    channel_type="SEARCH",
                    results=12.0,
                    cost_per_result=188.0,
                    cost=2256.0,
                    impressions=5000,
                    clicks=100,
                    ctr=2.0,
                )
            ],
        ),
    )


class TestBuildContext(unittest.TestCase):
    def test_context(self):
        manual = ManualInputs(
            client_id="lodge",
            month="2026-03",
            budget={"amount": 63600, "spent": 42834, "vat": 48830, "remaining": 14770},
            scope_prose="Scope prose.",
            insights=["Good month"],
        )
        ctx = build_context(_client(), "2026-03", manual, _data(), "March 2026", "2026-03-01", "2026-03-31")

        self.assertEqual(ctx["platforms_label"], "Meta (Facebook & Instagram) & Google Ads")
        self.assertEqual(len(ctx["reach"]), 2)
        self.assertEqual(len(ctx["messaging"]), 1)
        self.assertEqual(len(ctx["content"]), 2)
        self.assertEqual(len(ctx["audience"]), 2)
        self.assertEqual(len(ctx["ads"]), 2)
        self.assertEqual(ctx["budget"]["amount"], "63,600 EGP")
        self.assertEqual(ctx["ads"][0]["campaigns"][0]["name"], "Leads Campaign")
        self.assertEqual(ctx["audience"][1]["demographics"][0]["female"], "10")


class TestRenderPdf(unittest.TestCase):
    @patch("tds_ads_reporting.reporting.pdf.build_context")
    def test_render(self, mock_build):
        cfg = type("Cfg", (), {"client": lambda self, i: _client()})()
        mock_build.return_value = {
            "client": {"name": "Lodge", "email": "reports@trafficdigitalsolutions.com"},
            "month_label": "March 2026",
            "date_start": "2026-03-01",
            "date_stop": "2026-03-31",
            "platforms_label": "Meta & Google Ads",
            "toc": ["Report Scope"],
            "scope_prose": "x",
            "scope_notes": "",
            "insights": ["ok"],
            "recommendations": [],
            "budget": {"amount": "1", "spent": "2", "vat": "3", "remaining": "4"},
            "reach": [],
            "messaging": [],
            "content": [],
            "audience": [],
            "ads": [],
        }
        out = render_pdf(cfg, _client(), "2026-03", ManualInputs("lodge", "2026-03"), None)
        self.assertTrue(out.exists())
        self.assertGreater(out.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
