from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tds_ads_reporting.meta.ads import AdsSummary, CampaignRow
from tds_ads_reporting.storage.cache import SummaryCache
from tds_ads_reporting.reporting.assembler import _deserialize, _serialize


class TestSummaryCache(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.cache = SummaryCache(self.tmp / "test.sqlite")

    def tearDown(self):
        self.cache.close()

    def test_roundtrip(self):
        self.assertIsNone(self.cache.get("lodge", "2026-03", "meta_ads"))
        self.cache.set("lodge", "2026-03", "meta_ads", {"n": 1})
        self.assertEqual(self.cache.get("lodge", "2026-03", "meta_ads"), {"n": 1})
        self.assertEqual(self.cache.list_months(), ["2026-03"])
        self.assertEqual(self.cache.list_months("lodge"), ["2026-03"])
        self.assertEqual(self.cache.list_months("other"), [])

    def test_upsert(self):
        self.cache.set("lodge", "2026-03", "meta_ads", {"n": 1})
        self.cache.set("lodge", "2026-03", "meta_ads", {"n": 2})
        self.assertEqual(self.cache.get("lodge", "2026-03", "meta_ads"), {"n": 2})


class TestSerializeRoundtrip(unittest.TestCase):
    def test_ads_summary(self):
        summary = AdsSummary(
            account_id="act_123",
            month="2026-03",
            currency="EGP",
            campaigns=[
                CampaignRow(campaign_id="1", campaign_name="A", results=5, spend=100.0)
            ],
        )
        restored = _deserialize(_serialize(summary), "meta_ads")
        self.assertIsInstance(restored, AdsSummary)
        self.assertEqual(restored.total_spend, 100.0)
        self.assertEqual(restored.campaigns[0].campaign_name, "A")


if __name__ == "__main__":
    unittest.main()
