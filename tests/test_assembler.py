from __future__ import annotations

import unittest
from unittest.mock import patch

from tds_ads_reporting.config import Client, MetaConfig
from tds_ads_reporting.manual_inputs.loader import ManualInputs
from tds_ads_reporting.meta.ads import AdsSummary, CampaignRow, MetaAdsDataset
from tds_ads_reporting.meta.page import InstagramMetrics, PageMetrics, PostRow
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
    )


def _rich_data() -> FetchedData:
    return FetchedData(
        meta_ads=MetaAdsDataset(
            account_id="act_123",
            month="2026-03",
            currency="EGP",
            campaigns=[
                CampaignRow(
                    campaign_id="1",
                    campaign_name="Leads Campaign",
                    objective="LEAD_GENERATION",
                    status="ACTIVE",
                    results=120,
                    cost_per_result=150.5,
                    spend=18060.0,
                    impressions=500000,
                    reach=400000,
                    frequency=1.25,
                    ctr=1.5,
                    cpc=3.0,
                    cpm=36.12,
                    inline_link_clicks=7500,
                ),
                CampaignRow(
                    campaign_id="2",
                    campaign_name="Dead Spend",
                    objective="TRAFFIC",
                    status="PAUSED",
                    results=0,
                    cost_per_result=0.0,
                    spend=5000.0,
                    impressions=100000,
                    reach=90000,
                    frequency=1.11,
                    ctr=0.5,
                    cpc=4.0,
                    cpm=50.0,
                    inline_link_clicks=1250,
                ),
            ],
            adsets=[
                {
                    "adset_id": "a1",
                    "adset_name": "LAL 1%",
                    "campaign_id": "1",
                    "campaign_name": "Leads Campaign",
                    "spend": 12000.0,
                    "results": 80,
                    "cost_per_result": 150.0,
                    "impressions": 300000,
                    "reach": 240000,
                    "frequency": 1.25,
                    "ctr": 1.6,
                    "cpc": 3.0,
                    "cpm": 40.0,
                    "inline_link_clicks": 4000,
                }
            ],
            conversions={"lead": {"count": 120, "cost": 18060.0, "cpa": 150.5}},
            devices=[{"label": "mobile", "spend": 20000.0, "impressions": 600000, "clicks": 9000, "results": 150, "ctr": 1.5, "pct": 75.0}],
            publishers=[
                {"label": "instagram", "spend": 18000.0, "impressions": 500000, "clicks": 8000, "results": 130, "ctr": 1.6, "pct": 67.5},
                {"label": "facebook", "spend": 8660.0, "impressions": 300000, "clicks": 2550, "results": 30, "ctr": 0.85, "pct": 32.5},
            ],
            countries=[{"label": "Egypt", "spend": 20000.0, "impressions": 600000, "clicks": 9000, "results": 150, "ctr": 1.5, "pct": 75.0}],
            demographics=[{"age": "18-24", "gender": "F", "spend": 12000.0, "impressions": 300000, "results": 80, "pct": 45.0}],
            dow_pacing={"Sunday": {"spend": 0.0, "pct": 0.0}, "Monday": {"spend": 5000.0, "pct": 18.7}},
            hour_pacing={"14": {"spend": 500.0, "pct": 1.9}},
            daily_spend=[{"date": "2026-03-01", "spend": 1000.0}],
            totals={
                "spend": 23060.0,
                "impressions": 600000,
                "reach": 490000,
                "results": 120,
                "clicks": 8750,
                "ctr": 1.46,
                "cpc": 2.64,
                "cpm": 38.43,
                "cpr": 192.17,
                "frequency": 1.22,
            },
            prev_month={
                "month": "2026-02",
                "totals": {"spend": 20000.0, "impressions": 600000, "reach": 500000, "results": 100, "clicks": 8000, "ctr": 1.33, "cpc": 2.5, "cpm": 33.33, "cpr": 200.0, "frequency": 1.2},
                "campaigns": [{"campaign_id": "1", "campaign_name": "Leads Campaign", "spend": 15000.0, "results": 90, "impressions": 400000, "reach": 320000, "ctr": 1.4, "cpr": 166.67}],
            },
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

        self.assertEqual(ctx["platforms_label"], "Meta (Facebook & Instagram)")
        self.assertEqual(len(ctx["reach"]), 2)
        self.assertEqual(len(ctx["messaging"]), 1)
        self.assertEqual(len(ctx["content"]), 2)
        self.assertEqual(len(ctx["audience"]), 2)
        self.assertEqual(len(ctx["ads"]), 1)
        self.assertEqual(ctx["budget"]["amount"], "63,600 EGP")
        self.assertEqual(ctx["ads"][0]["campaigns"][0]["name"], "Leads Campaign")
        self.assertEqual(ctx["audience"][1]["demographics"][0]["female"], "10")

    def test_rich_context(self):
        manual = ManualInputs(
            client_id="lodge",
            month="2026-03",
            budget={"amount": 63600, "spent": 42834, "vat": 48830, "remaining": 14770, "revenue": 90000},
            scope_prose="Scope prose.",
            insights=["Good month"],
        )
        ctx = build_context(_client(), "2026-03", manual, _rich_data(), "March 2026", "2026-03-01", "2026-03-31")

        self.assertTrue(ctx["has_meta"])
        self.assertEqual(ctx["currency"], "EGP")
        self.assertEqual(ctx["prev_month_label"], "February 2026")
        self.assertIn("executive_summary", ctx)
        self.assertEqual(ctx["kpis"]["spend"], 23060.0)
        self.assertEqual(ctx["kpis"]["roas"], 3.9)
        self.assertEqual(ctx["revenue"], 90000.0)
        self.assertEqual(ctx["revenue_fmt"], "90,000 EGP")

        # campaign table rows: sorted by spend desc, flagged, MoM computed
        rows = ctx["campaigns"]
        self.assertEqual([r["name"] for r in rows], ["Leads Campaign", "Dead Spend"])
        self.assertTrue(rows[0]["is_top"])
        self.assertFalse(rows[0]["is_bottom"])
        self.assertTrue(rows[1]["is_bottom"])
        self.assertFalse(rows[1]["is_top"])
        self.assertEqual(rows[0]["mom_spend_delta_pct"], 20.4)
        self.assertIsNone(rows[1]["mom_spend_delta_pct"])
        self.assertEqual(rows[0]["spend_fmt"], "18,060")
        self.assertEqual(rows[0]["cpr_fmt"], "150")

        # breakdown rows
        self.assertEqual(ctx["conversions"][0]["action_type"], "lead")
        self.assertEqual(ctx["devices"][0]["label"], "mobile")
        self.assertEqual(ctx["publishers"][0]["label"], "instagram")
        self.assertEqual(ctx["countries"][0]["label"], "Egypt")
        self.assertEqual(ctx["demographics"][0]["age"], "18-24")
        self.assertEqual(ctx["age_gender"]["18-24"]["F"], "12,000")
        self.assertEqual(ctx["dow_pacing"][0]["label"], "Sunday")
        self.assertEqual(ctx["hour_pacing"][0]["label"], "14")
        self.assertEqual(ctx["top_adsets"][0]["adset_name"], "LAL 1%")
        self.assertEqual(ctx["top_adsets"][0]["spend_fmt"], "12,000")

        # insights payload keys
        self.assertTrue(ctx["top_campaigns"])
        self.assertTrue(ctx["bottom_campaigns"])
        self.assertTrue(ctx["anomalies"])
        self.assertTrue(ctx["recommendations"])
        self.assertIn("pacing", ctx)
        self.assertIn("mom", ctx)

    def test_legacy_ads_summary_promoted(self):
        manual = ManualInputs("lodge", "2026-03")
        ctx = build_context(_client(), "2026-03", manual, _data(), "March 2026", "2026-03-01", "2026-03-31")
        self.assertTrue(ctx["has_meta"])
        self.assertEqual(ctx["campaigns"][0]["name"], "Leads Campaign")
        self.assertEqual(ctx["kpis"]["spend"], 1806.0)


class TestRenderPdf(unittest.TestCase):
    @patch("tds_ads_reporting.reporting.pdf.build_context")
    def test_render(self, mock_build):
        cfg = type("Cfg", (), {"client": lambda self, i: _client()})()
        mock_build.return_value = {
            "client": {"name": "Lodge", "email": "reports@trafficdigitalsolutions.com"},
            "month_label": "March 2026",
            "date_start": "2026-03-01",
            "date_stop": "2026-03-31",
            "platforms_label": "Meta",
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

    def test_render_rich_context(self):
        """Render the full rich context (MetaAdsDataset + insights) end-to-end."""
        cfg = type("Cfg", (), {"client": lambda self, i: _client()})()
        manual = ManualInputs(
            client_id="lodge",
            month="2026-03",
            budget={"amount": 63600, "spent": 42834, "vat": 48830, "remaining": 14770, "revenue": 90000},
            scope_prose="Scope prose.",
            insights=["Good month"],
            recommendations=["Keep going"],
        )
        ctx = build_context(_client(), "2026-03", manual, _rich_data(), "March 2026", "2026-03-01", "2026-03-31")
        out = render_pdf(cfg, _client(), "2026-03", manual, None, context=ctx)
        self.assertTrue(out.exists())
        self.assertGreater(out.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()
