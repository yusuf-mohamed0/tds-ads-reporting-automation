from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

from tds_ads_reporting.config import Client


class EmailError(RuntimeError):
    pass


def send_report(client: Client, pdf_path: Path, month: str) -> None:
    """Send a report PDF via SMTP (simple) or Gmail API (if configured).

    Preference: if GOOGLE_APPLICATION_CREDENTIALS + GMAIL_SENDER are set,
    use Gmail API. Otherwise fall back to SMTP env vars.
    """
    if os.environ.get("GMAIL_SENDER") and os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        _send_gmail_api(client, pdf_path, month)
    else:
        _send_smtp(client, pdf_path, month)


def _send_smtp(client: Client, pdf_path: Path, month: str) -> None:
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    sender = os.environ.get("SMTP_SENDER")
    if not (host and user and password and sender):
        raise EmailError(
            "SMTP not configured. Set SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_SENDER "
            "(or use Gmail API via GMAIL_SENDER + GOOGLE_APPLICATION_CREDENTIALS)."
        )

    to_addr = client.report_recipient or "reports@trafficdigitalsolutions.com"
    msg = EmailMessage()
    msg["Subject"] = f"{client.name} — {month} Performance Report"
    msg["From"] = sender
    msg["To"] = to_addr
    msg.set_content(
        f"Dear {client.name} team,\n\n"
        f"Please find attached the {month} performance report for {client.name}.\n\n"
        "Best regards,\nTraffic Digital Solutions"
    )
    msg.add_attachment(
        pdf_path.read_bytes(),
        maintype="application",
        subtype="pdf",
        filename=pdf_path.name,
    )

    with smtplib.SMTP(host, port, timeout=30) as server:
        server.ehlo()
        if os.environ.get("SMTP_STARTTLS", "1") != "0":
            server.starttls()
        server.login(user, password)
        server.send_message(msg)


def _send_gmail_api(client: Client, pdf_path: Path, month: str) -> None:
    import base64

    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    sender = os.environ.get("GMAIL_SENDER")
    token_file = Path(os.environ.get("GMAIL_TOKEN_FILE", "gmail_token.json"))
    client_secrets = Path(os.environ.get("GMAIL_CLIENT_SECRETS", "client_secret.json"))
    SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

    creds = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets), SCOPES)
            creds = flow.run_local_server(port=0)
        token_file.write_text(creds.to_json())

    service = build("gmail", "v1", credentials=creds)

    message = EmailMessage()
    message["Subject"] = f"{client.name} — {month} Performance Report"
    message["To"] = client.report_recipient or "reports@trafficdigitalsolutions.com"
    message.set_content(
        f"Dear {client.name} team,\n\n"
        f"Please find attached the {month} performance report for {client.name}.\n\n"
        "Best regards,\nTraffic Digital Solutions"
    )
    message.add_attachment(
        pdf_path.read_bytes(),
        maintype="application",
        subtype="pdf",
        filename=pdf_path.name,
    )

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(userId="me", body={"raw": raw}).execute()
