import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import click

from tds_ads_reporting.config import load_config
from tds_ads_reporting.reporting.pdf import render_pdf
from tds_ads_reporting.manual_inputs.loader import load_manual_inputs


@click.group()
def cli():
    """TDS Ads Reporting Automation (local)."""


@cli.command()
@click.option("--client", "client_id", required=True)
@click.option("--month", "month", required=True, help="YYYY-MM")
@click.option("--dry-run", is_flag=True)
def run(client_id: str, month: str, dry_run: bool) -> None:
    """Generate a monthly report for one client."""
    cfg = load_config()
    client = cfg.client(client_id)
    manual = load_manual_inputs(client_id, month)
    if dry_run:
        click.echo(f"[dry-run] {client.name} {month}: platforms={client.platforms()}")
        return
    pdf = render_pdf(cfg, client, month, manual)
    click.echo(f"wrote {pdf}")


@cli.command()
@click.option("--month", "month", required=True)
def run_all(month: str) -> None:
    """Generate reports for all active clients."""
    cfg = load_config()
    for client in cfg.active_clients():
        try:
            pdf = render_pdf(cfg, client, month, load_manual_inputs(client.id, month))
            click.echo(f"ok {client.id} -> {pdf}")
        except Exception as exc:  # noqa: BLE001
            click.echo(f"fail {client.id}: {exc}")


if __name__ == "__main__":
    cli()
