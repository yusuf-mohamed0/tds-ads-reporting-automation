import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import click

from tds_ads_reporting.config import load_config
from tds_ads_reporting.mailer.sender import send_report
from tds_ads_reporting.manual_inputs.loader import load_manual_inputs
from tds_ads_reporting.meta.credentials import init_credentials
from tds_ads_reporting.observability.logging import setup_logging
from tds_ads_reporting.reporting.assembler import fetch_all
from tds_ads_reporting.reporting.pdf import render_pdf
from tds_ads_reporting.storage.cache import SummaryCache


@click.group()
def cli():
    """TDS Ads Reporting Automation (local)."""


@cli.command()
@click.option("--client", "client_id", required=True)
@click.option("--month", "month", required=True, help="YYYY-MM")
@click.option("--dry-run", is_flag=True, help="Fetch nothing, show what would run")
@click.option("--no-fetch", is_flag=True, help="Render with manual inputs only")
@click.option("--no-cache", is_flag=True, help="Bypass the SQLite summary cache")
@click.option("--email", is_flag=True, help="Send the PDF to the report recipient")
def run(client_id: str, month: str, dry_run: bool, no_fetch: bool, no_cache: bool, email: bool) -> None:
    """Generate a monthly report for one client."""
    setup_logging()
    cfg = load_config()
    client = cfg.client(client_id)
    manual = load_manual_inputs(client_id, month)

    if dry_run:
        click.echo(f"[dry-run] {client.name} {month}")
        click.echo(f"  platforms: {', '.join(client.platforms()) or 'none'}")
        click.echo(f"  meta accounts: {client.meta.ad_accounts or []}")
        click.echo(f"  page: {client.meta.page_id}  ig: {client.meta.instagram_id}")
        click.echo(f"  google customers: {client.google_ads.customer_ids or []}")
        return

    cache = None if no_cache else SummaryCache()

    if no_fetch:
        pdf = render_pdf(cfg, client, month, manual, None)
        click.echo(f"wrote {pdf}")
        if email:
            send_report(client=client, pdf_path=pdf, month=month)
        return

    creds = init_credentials()

    data = fetch_all(
        meta_token=creds.meta_access_token,
        meta_version=creds.meta_api_version,
        google_yaml=creds.google_ads_yaml,
        client=client,
        month=month,
        cache=cache,
    )
    pdf = render_pdf(cfg, client, month, manual, data)
    click.echo(f"wrote {pdf}")

    if email:
        send_report(client=client, pdf_path=pdf, month=month)


@cli.command()
@click.option("--month", "month", required=True)
@click.option("--email", is_flag=True)
@click.option("--no-cache", is_flag=True, help="Bypass the SQLite summary cache")
def run_all(month: str, email: bool, no_cache: bool) -> None:
    """Generate reports for all active clients."""
    setup_logging()
    cfg = load_config()
    cache = None if no_cache else SummaryCache()
    creds = init_credentials()
    for client in cfg.active_clients():
        try:
            manual = load_manual_inputs(client.id, month)
            data = fetch_all(
                meta_token=creds.meta_access_token,
                meta_version=creds.meta_api_version,
                google_yaml=creds.google_ads_yaml,
                client=client,
                month=month,
                cache=cache,
            )
            pdf = render_pdf(cfg, client, month, manual, data)
            click.echo(f"ok {client.id} -> {pdf}")
            if email:
                send_report(client=client, pdf_path=pdf, month=month)
        except Exception as exc:  # noqa: BLE001
            click.echo(f"fail {client.id}: {exc}")


@cli.command()
def cache_list() -> None:
    """List months present in the SQLite summary cache."""
    cache = SummaryCache()
    for month in cache.list_months():
        click.echo(month)


if __name__ == "__main__":
    cli()
