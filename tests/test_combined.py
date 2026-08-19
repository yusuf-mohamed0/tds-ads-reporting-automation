from __future__ import annotations

import unittest

from tds_ads_reporting.config import Client
from tds_ads_reporting.reporting.combined import build_combined_context, render_combined_pdf


def _client(client_id: str, name: str, currency: str = "EGP") -> Client:
    return Client(id=client_id, name=name, report_recipient="reports@trafficdigitalsolutions.com", currency=currency)


def _ctx(
    spend: float,
    results: int,
    impressions: int,
    clicks: int,
    budget_amount: float,
    currency: str = "EGP",
    summary: str = "Good month.",
) -> dict:
    return {
        "date_start": "2026-03-01",
        "date_stop": "2026-03-31",
        "month_label": "March 2026",
        "currency": currency,
        "kpis": {
            "spend": spend,
            "results": results,
            "impressions": impressions,
            "clicks": clicks,
            "budget_amount": budget_amount,
            "spend_fmt": f"{spend:,.0f} {currency}",
            "results_fmt": f"{results:,}",
            "impressions_fmt": f"{impressions:,}",
            "ctr": 0.0,
            "cpr": 0.0,
            "cpr_fmt": "0 EGP",
            "budget_utilization": 0.0,
        },
        "executive_summary": summary,
        "top_campaigns": [
            {
                "campaign_id": "1",
                "campaign_name": "Camp A",
                "results": 10,
                "cost_per_result": 5.0,
                "spend": 50.0,
            }
        ],
        "recommendations": ["Keep going"],
        "mom": {
            "spend": {"delta_pct": 10.0},
            "results": {"delta_pct": 5.0},
            "cpr": {"delta_pct": -2.0},
            "ctr": {"delta_pct": 1.0},
        },
    }


class TestBuildCombinedContext(unittest.TestCase):
    def test_rollup_math(self):
        clients_data = [
            (_client("a", "Alpha"), _ctx(spend=1000.0, results=100, impressions=10000, clicks=500, budget_amount=2000.0)),
            (_client("b", "Beta"), _ctx(spend=2000.0, results=50, impressions=20000, clicks=400, budget_amount=4000.0)),
        ]
        ctx = build_combined_context(clients_data)

        self.assertEqual(ctx["month"], "2026-03")
        self.assertEqual(ctx["month_label"], "March 2026")
        self.assertEqual(ctx["client_count"], 2)
        self.assertIn("generated_at", ctx)

        t = ctx["totals"]
        self.assertEqual(t["spend"], 3000.0)
        self.assertEqual(t["results"], 150)
        self.assertEqual(t["impressions"], 30000)
        self.assertEqual(t["ctr"], 3.0)  # 900 clicks / 30000 impressions * 100
        self.assertEqual(t["cpr"], 20.0)  # 3000 spend / 150 results
        self.assertEqual(t["budget_utilization"], 50.0)  # 3000 / 6000 * 100
        self.assertEqual(t["spend_fmt"], "3,000 EGP")
        self.assertEqual(t["results_fmt"], "150")
        self.assertEqual(t["impressions_fmt"], "30,000")
        self.assertEqual(t["cpr_fmt"], "20 EGP")

        self.assertEqual([c["client_id"] for c in ctx["clients"]], ["a", "b"])
        self.assertEqual(ctx["clients"][0]["name"], "Alpha")
        self.assertEqual(ctx["clients"][0]["currency"], "EGP")
        self.assertEqual(ctx["clients"][0]["executive_summary"], "Good month.")
        self.assertEqual(ctx["clients"][0]["top_campaigns"][0]["campaign_name"], "Camp A")
        self.assertEqual(ctx["clients"][0]["recommendations"], ["Keep going"])
        self.assertEqual(ctx["clients"][0]["mom"]["spend"]["delta_pct"], 10.0)

    def test_zero_divide_guards(self):
        clients_data = [
            (_client("a", "Alpha"), _ctx(spend=100.0, results=0, impressions=0, clicks=0, budget_amount=0.0)),
            (_client("b", "Beta"), _ctx(spend=0.0, results=0, impressions=0, clicks=0, budget_amount=0.0)),
        ]
        ctx = build_combined_context(clients_data)
        t = ctx["totals"]
        self.assertEqual(t["spend"], 100.0)
        self.assertEqual(t["results"], 0)
        self.assertEqual(t["impressions"], 0)
        self.assertEqual(t["ctr"], 0.0)
        self.assertEqual(t["cpr"], 0.0)
        self.assertEqual(t["budget_utilization"], 0.0)

    def test_empty_input(self):
        ctx = build_combined_context([])
        self.assertEqual(ctx["client_count"], 0)
        self.assertEqual(ctx["clients"], [])
        self.assertEqual(ctx["totals"]["spend"], 0.0)
        self.assertEqual(ctx["totals"]["ctr"], 0.0)
        self.assertEqual(ctx["totals"]["cpr"], 0.0)


class TestRenderCombinedPdf(unittest.TestCase):
    def test_render_smoke(self):
        clients_data = [
            (_client("a", "Alpha"), _ctx(spend=1000.0, results=100, impressions=10000, clicks=500, budget_amount=2000.0)),
            (_client("b", "Beta"), _ctx(spend=2000.0, results=50, impressions=20000, clicks=400, budget_amount=4000.0)),
        ]
        out = render_combined_pdf(clients_data, month="2026-03")
        self.assertTrue(out.exists())
        self.assertEqual(out.name, "combined_2026-03.pdf")
        self.assertGreater(out.stat().st_size, 1000)


if __name__ == "__main__":
    unittest.main()