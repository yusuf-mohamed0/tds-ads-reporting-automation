#!/usr/bin/env python3
"""Fetch Meta Ads data for August 2026 for all clients and store in SQLite."""

from __future__ import annotations

import sys
import time
import traceback
from dataclasses import asdict
from pathlib import Path

# Ensure the repo root is on the path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tds_ads_reporting.config import load_config
from tds_ads_reporting.meta.ads import fetch_meta_dataset
from tds_ads_reporting.meta.credentials import init_credentials
from tds_ads_reporting.storage.cache import SummaryCache

MONTH = "2026-08"
PLATFORM = "meta_ads"


def main() -> None:
    cfg = load_config()
    creds = init_credentials()
    cache = SummaryCache()

    meta_clients = [c for c in cfg.clients if c.meta.ad_accounts]
    total = len(meta_clients)
    print(f"Found {total} clients with Meta Ads enabled.")
    print(f"Fetching data for month: {MONTH}")
    print("=" * 70)

    succeeded = 0
    failed = 0
    skipped = 0

    for idx, client in enumerate(meta_clients, 1):
        client_id = client.id
        ad_account_id = client.meta.ad_accounts[0]  # first ad account

        # Check if already cached
        existing = cache.get(client_id, MONTH, PLATFORM)
        if existing:
            print(f"[{idx}/{total}] {client.name} ({client_id}) — ALREADY CACHED, skipping")
            skipped += 1
            continue

        print(f"[{idx}/{total}] {client.name} ({client_id}) — account={ad_account_id} ...", end=" ", flush=True)
        t0 = time.time()

        try:
            dataset = fetch_meta_dataset(
                access_token=creds.meta_access_token,
                api_version=creds.meta_api_version,
                ad_account_id=ad_account_id,
                month=MONTH,
            )
            payload = asdict(dataset)
            cache.set(client_id, MONTH, PLATFORM, payload)
            elapsed = time.time() - t0
            n_campaigns = len(dataset.campaigns)
            spend = dataset.totals.get("spend", 0)
            results = dataset.totals.get("results", 0)
            print(f"OK ({elapsed:.1f}s) — {n_campaigns} campaigns, spend={spend:,.2f} {dataset.currency}, results={results}")
            succeeded += 1
        except Exception as exc:
            elapsed = time.time() - t0
            print(f"FAILED ({elapsed:.1f}s) — {exc}")
            traceback.print_exc()
            failed += 1

        # Small delay to avoid rate limiting
        if idx < total:
            time.sleep(0.5)

    cache.close()

    print("=" * 70)
    print(f"Done. Succeeded: {succeeded}, Failed: {failed}, Skipped: {skipped}, Total: {total}")

    # Verify storage
    print("\nVerifying stored data...")
    cache2 = SummaryCache()
    rows = cache2._conn.execute(
        "SELECT client_id, month, length(payload) FROM summaries WHERE month=? AND platform=? ORDER BY client_id",
        (MONTH, PLATFORM),
    ).fetchall()
    print(f"Found {len(rows)} rows in summaries for {MONTH}/{PLATFORM}:")
    for client_id, month, payload_size in rows:
        print(f"  {client_id}: {month} — {payload_size:,} bytes")
    cache2.close()


if __name__ == "__main__":
    main()
