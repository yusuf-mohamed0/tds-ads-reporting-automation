from __future__ import annotations

import unittest
from datetime import date

from tds_ads_reporting.config import Client, MetaConfig
from tds_ads_reporting.insights.engine import generate_insights
from tds_ads_reporting.manual_inputs.loader import ManualInputs
from tds_ads_reporting.meta.ads import CampaignRow, MetaAdsDataset


def _client() -> Client:
    return Client(
        id="lodge",
        name="Lodge",
        report_recipient="reports@trafficdigitalsolutions.com",
        currency="EGP",
        goals={"primary": "leads"},
        meta=MetaConfig(
            ad_accounts=["act_123"],
            page_id="123",
            instagram_id="456",
            conversion_actions={"leads": ["lead"]},
        ),
    )


def _manual(**overrides) -> ManualInputs:
    kwargs = {
        "client_id": "lodge",
        "month": "2026-03",
        "budget": {"amount": 63600, "spent": 42834, "vat": 48830, "remaining": 14770, "revenue": 90000},
        "scope_prose": "Scope.",
        "insights": ["Good month"],
        "recommendations": ["Keep going"],
    }
    kwargs.update(overrides)
    return ManualInputs(**kwargs)


def _dataset(**overrides) -> MetaAdsDataset:
    kwargs = {
        "account_id": "act_123",
        "month": "2026-03",
        "currency": "EGP",
        "campaigns": [
            CampaignRow(
                campaign_id="1",
                campaign_name="Leads Pro",
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
                campaign_name="Retarget",
                objective="LEAD_GENERATION",
                status="ACTIVE",
                results=40,
                cost_per_result=90.0,
                spend=3600.0,
                impressions=200000,
                reach=150000,
                frequency=1.33,
                ctr=0.9,
                cpc=2.5,
                cpm=22.5,
                inline_link_clicks=1800,
            ),
            CampaignRow(
                campaign_id="3",
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
        "conversions": {
            "lead": {"count": 120, "cost": 18060.0, "cpa": 150.5},
            "link_click": {"count": 7500, "cost": 0.0, "cpa": 0.0},
        },
        "devices": [
            {"label": "mobile", "spend": 20000.0, "impressions": 600000, "clicks": 9000, "results": 150, "ctr": 1.5, "pct": 75.0}
        ],
        "publishers": [
            {"label": "instagram", "spend": 18000.0, "impressions": 500000, "clicks": 8000, "results": 130, "ctr": 1.6, "pct": 67.5},
            {"label": "facebook", "spend": 8660.0, "impressions": 300000, "clicks": 2550, "results": 30, "ctr": 0.85, "pct": 32.5},
        ],
        "countries": [
            {"label": "Egypt", "spend": 20000.0, "impressions": 600000, "clicks": 9000, "results": 150, "ctr": 1.5, "pct": 75.0},
            {"label": "Saudi Arabia", "spend": 6660.0, "impressions": 200000, "clicks": 1550, "results": 10, "ctr": 0.8, "pct": 25.0},
        ],
        "demographics": [
            {"age": "18-24", "gender": "F", "spend": 12000.0, "impressions": 300000, "results": 80, "pct": 45.0},
            {"age": "25-34", "gender": "M", "spend": 8000.0, "impressions": 200000, "results": 50, "pct": 30.0},
        ],
        "dow_pacing": {
            "Sunday": {"spend": 0.0, "pct": 0.0},
            "Monday": {"spend": 5000.0, "pct": 18.7},
            "Tuesday": {"spend": 3000.0, "pct": 11.3},
        },
        "hour_pacing": {f"{h:02d}": {"spend": 0.0, "pct": 0.0} for h in range(24)},
        "daily_spend": [
            {"date": "2026-03-01", "spend": 1000.0},
            {"date": "2026-03-02", "spend": 3000.0},
        ],
        "totals": {
            "spend": 26660.0,
            "impressions": 800000,
            "reach": 640000,
            "results": 160,
            "clicks": 10550,
            "ctr": 1.32,
            "cpc": 2.53,
            "cpm": 33.33,
            "cpr": 166.63,
            "frequency": 1.25,
        },
        "prev_month": {
            "month": "2026-02",
            "totals": {
                "spend": 20000.0,
                "impressions": 600000,
                "reach": 500000,
                "results": 100,
                "clicks": 8000,
                "ctr": 1.33,
                "cpc": 2.5,
                "cpm": 33.33,
                "cpr": 200.0,
                "frequency": 1.2,
            },
            "campaigns": [
                {
                    "campaign_id": "1",
                    "campaign_name": "Leads Pro",
                    "spend": 15000.0,
                    "results": 90,
                    "impressions": 400000,
                    "reach": 320000,
                    "ctr": 1.4,
                    "cpr": 166.67,
                }
            ],
        },
        "adsets": [
            {
                "adset_id": "a1",
                "adset_name": "LAL 1%",
                "campaign_id": "1",
                "campaign_name": "Leads Pro",
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
    }
    kwargs.update(overrides)
    return MetaAdsDataset(**kwargs)


class TestGenerateInsights(unittest.TestCase):
    def test_full_payload(self):
        payload = generate_insights(_dataset(), _manual(), _client(), today=date(2026, 3, 31))
        self.assertIn("executive_summary", payload)
        self.assertIn("kpis", payload)
        self.assertIn("top_campaigns", payload)
        self.assertIn("bottom_campaigns", payload)
        self.assertIn("anomalies", payload)
        self.assertIn("recommendations", payload)
        self.assertIn("pacing", payload)
        self.assertIn("mom", payload)
        self.assertEqual(payload["prev_month_label"], "February 2026")

    def test_kpis_math(self):
        kpis = generate_insights(_dataset(), _manual(), _client())["kpis"]
        self.assertEqual(kpis["spend"], 26660.0)
        self.assertEqual(kpis["results"], 160)
        self.assertEqual(kpis["impressions"], 800000)
        self.assertEqual(kpis["cpr"], 166.63)
        self.assertEqual(kpis["cpa_primary"], 150.5)
        self.assertEqual(kpis["primary_action"], "lead")
        self.assertEqual(kpis["roas"], 3.38)
        self.assertEqual(kpis["budget_utilization"], 41.9)
        self.assertEqual(kpis["spend_fmt"], "26,660 EGP")

    def test_top_bottom_campaigns(self):
        payload = generate_insights(_dataset(), _manual(), _client())
        top = payload["top_campaigns"]
        bottom = payload["bottom_campaigns"]
        self.assertEqual(top[0]["campaign_id"], "1")
        self.assertEqual(top[0]["why"], "highest results")
        self.assertEqual(bottom[0]["campaign_id"], "3")
        self.assertIn("zero results", bottom[0]["flags"])

    def test_anomalies(self):
        anomalies = generate_insights(_dataset(), _manual(), _client())["anomalies"]
        joined = " | ".join(anomalies)
        self.assertIn("instagram delivers 62% of impressions", joined)
        self.assertIn("mobile drives 85% of clicks", joined)
        self.assertIn("Spend moved up 33% vs the previous month", joined)
        self.assertIn("Dead Spend spent 5,000 EGP with no results", joined)
        self.assertIn("Egypt accounts for 75% of spend", joined)

    def test_recommendations(self):
        recs = generate_insights(_dataset(), _manual(), _client())["recommendations"]
        joined = " | ".join(recs)
        self.assertIn("Scale budget for 'Leads Pro'", joined)
        self.assertIn("Pause 'Dead Spend'", joined)
        self.assertIn("Shift budget toward instagram", joined)
        self.assertIn("Test audience segment 18-24 / F", joined)
        self.assertIn("Expand geo targeting toward Egypt", joined)
        self.assertIn("only 42% utilized", joined)
        self.assertIn("Duplicate or scale adset 'LAL 1%'", joined)
        self.assertLessEqual(len(recs), 8)

    def test_pacing(self):
        pacing = generate_insights(_dataset(), _manual(), _client(), today=date(2026, 3, 31))["pacing"]
        self.assertEqual(pacing["days_elapsed"], 31)
        self.assertEqual(pacing["days_in_month"], 31)
        self.assertEqual(pacing["daily_avg"], 860.0)
        self.assertEqual(pacing["projected"], 26660.0)
        self.assertEqual(pacing["spike_days"], [{"date": "2026-03-02", "spend": 3000.0}])

    def test_mom(self):
        mom = generate_insights(_dataset(), _manual(), _client())["mom"]
        self.assertEqual(mom["spend"]["delta_pct"], 33.3)
        self.assertEqual(mom["results"]["delta_pct"], 60.0)
        self.assertEqual(mom["cpr"]["delta_pct"], -16.7)
        self.assertEqual(mom["campaigns"]["1"]["spend_prev"], 15000.0)
        self.assertEqual(mom["campaigns"]["1"]["spend_delta_pct"], 20.4)

    def test_executive_summary(self):
        text = generate_insights(_dataset(), _manual(), _client())["executive_summary"]
        self.assertIn("Lodge invested 26,660 EGP", text)
        self.assertIn("160 results from 800,000 impressions", text)
        self.assertIn("'Leads Pro' led performance", text)
        self.assertIn("42% of the 63,600 EGP monthly budget", text)
        self.assertIn("spend rose 33%", text)
        self.assertIn("results rose 60%", text)

    def test_empty_dataset_no_crash(self):
        ds = _dataset(campaigns=[], totals={}, conversions={}, prev_month={})
        payload = generate_insights(ds, _manual(), _client())
        self.assertEqual(payload["kpis"]["spend"], 0.0)
        self.assertEqual(payload["top_campaigns"], [])
        self.assertEqual(payload["bottom_campaigns"], [])
        self.assertEqual(payload["mom"]["spend"]["delta_pct"], None)
        self.assertIn("No previous-month data was available", payload["executive_summary"])

    def test_zero_results_no_crash(self):
        ds = _dataset(
            campaigns=[
                CampaignRow(campaign_id="1", campaign_name="A", spend=100.0, impressions=1000, reach=800)
            ],
            totals={"spend": 100.0, "impressions": 1000, "reach": 800, "results": 0},
            conversions={},
            prev_month={},
        )
        manual = _manual(budget={"amount": 63600, "spent": 42834, "vat": 48830, "remaining": 14770})
        payload = generate_insights(ds, manual, _client())
        self.assertEqual(payload["kpis"]["cpr"], 0.0)
        self.assertEqual(payload["kpis"]["roas"], None)
        self.assertEqual(payload["top_campaigns"][0]["why"], "highest spend (no results)")
        self.assertIn("zero results", payload["bottom_campaigns"][0]["flags"])

    def test_manual_revenue_fallback(self):
        ds = _dataset()
        manual = _manual(budget={"amount": 63600, "spent": 42834, "vat": 48830, "remaining": 14770})
        manual.revenue = 90000.0
        kpis = generate_insights(ds, manual, _client())["kpis"]
        self.assertEqual(kpis["roas"], 3.38)


if __name__ == "__main__":
    unittest.main()