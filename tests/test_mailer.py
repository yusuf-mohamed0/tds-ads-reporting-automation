from __future__ import annotations

import base64
import email.policy
import os
import sys
import tempfile
import unittest
from contextlib import contextmanager
from email import message_from_bytes
from email.header import decode_header
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

from tds_ads_reporting.config import Client
from tds_ads_reporting.mailer.sender import (
    DEFAULT_RECIPIENT,
    EmailError,
    send_combined_report,
    send_report,
)


def _decoded(value: str) -> str:
    return "".join(
        part.decode(charset or "utf-8") if isinstance(part, bytes) else part
        for part, charset in decode_header(value)
    )


def _plain_body(msg) -> str:
    for part in msg.walk():
        if part.get_content_type() == "text/plain":
            return part.get_payload(decode=True).decode()
    return ""


def _parse(raw: bytes):
    return message_from_bytes(raw, policy=email.policy.default)


def _client(recipient: str | None = "client@example.com") -> Client:
    return Client(id="lodge", name="Lodge", report_recipient=recipient or "")


def _pdf(dir_path: str) -> Path:
    p = Path(dir_path) / "lodge_2026-03.pdf"
    p.write_bytes(b"%PDF-1.4 fake pdf bytes for attachment test")
    return p


class _FakeSMTP:
    def __init__(self, *args, **kwargs):
        self.sent: list = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def ehlo(self):
        pass

    def starttls(self):
        pass

    def login(self, user, password):
        pass

    def send_message(self, msg):
        self.sent.append(msg)


@contextmanager
def _smtp_env():
    with patch.dict(
        os.environ,
        {
            "SMTP_HOST": "smtp.test",
            "SMTP_PORT": "587",
            "SMTP_USER": "user",
            "SMTP_PASSWORD": "pass",
            "SMTP_SENDER": "sender@test.com",
        },
    ):
        os.environ.pop("GMAIL_SENDER", None)
        os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
        yield


def _fake_google_modules(service: MagicMock) -> dict[str, ModuleType]:
    modules: dict[str, ModuleType] = {}
    for name in (
        "google",
        "google.auth",
        "google.auth.transport",
        "google.auth.transport.requests",
        "google.oauth2",
        "google.oauth2.credentials",
        "google_auth_oauthlib",
        "google_auth_oauthlib.flow",
        "googleapiclient",
        "googleapiclient.discovery",
    ):
        modules[name] = ModuleType(name)
    modules["google.auth.transport.requests"].Request = MagicMock
    modules["google.oauth2.credentials"].Credentials = MagicMock()
    creds = MagicMock()
    creds.valid = True
    creds.to_json.return_value = "{}"
    modules["google.oauth2.credentials"].Credentials.from_authorized_user_file = MagicMock(
        return_value=creds
    )
    modules["google_auth_oauthlib.flow"].InstalledAppFlow = MagicMock()
    modules["googleapiclient.discovery"].build = MagicMock(return_value=service)
    return modules


class TestSendReportSMTP(unittest.TestCase):
    def test_smtp_send_report_uses_client_recipient_and_attaches_pdf(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = _pdf(tmp)
            fake = _FakeSMTP()
            with _smtp_env(), patch("tds_ads_reporting.mailer.sender.smtplib.SMTP", return_value=fake):
                send_report(_client("client@example.com"), pdf, "2026-03")
            self.assertEqual(len(fake.sent), 1)
            msg = fake.sent[0]
            self.assertEqual(msg["Subject"], "Lodge — 2026-03 Performance Report")
            self.assertEqual(msg["To"], "client@example.com")
            self.assertEqual(msg["From"], "sender@test.com")
            parts = list(msg.iter_attachments())
            self.assertEqual(len(parts), 1)
            self.assertEqual(parts[0].get_filename(), "lodge_2026-03.pdf")
            self.assertEqual(parts[0].get_content_type(), "application/pdf")

    def test_smtp_send_report_falls_back_to_default_recipient(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = _pdf(tmp)
            fake = _FakeSMTP()
            with _smtp_env(), patch("tds_ads_reporting.mailer.sender.smtplib.SMTP", return_value=fake):
                send_report(_client(recipient=None), pdf, "2026-03")
            self.assertEqual(fake.sent[0]["To"], DEFAULT_RECIPIENT)

    def test_smtp_raises_when_not_configured(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = _pdf(tmp)
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("SMTP_HOST", None)
                os.environ.pop("SMTP_USER", None)
                os.environ.pop("SMTP_PASSWORD", None)
                os.environ.pop("SMTP_SENDER", None)
                os.environ.pop("GMAIL_SENDER", None)
                os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
                with self.assertRaises(EmailError):
                    send_report(_client(), pdf, "2026-03")


class TestSendCombinedReportSMTP(unittest.TestCase):
    def test_recipient_arg_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = _pdf(tmp)
            fake = _FakeSMTP()
            with _smtp_env(), patch("tds_ads_reporting.mailer.sender.smtplib.SMTP", return_value=fake):
                send_combined_report(pdf, "2026-03", recipient="boss@example.com")
            msg = fake.sent[0]
            self.assertEqual(msg["To"], "boss@example.com")
            self.assertEqual(msg["Subject"], "Combined Media Buying Report — 2026-03")
            self.assertIn("all active clients", _plain_body(msg))
            parts = list(msg.iter_attachments())
            self.assertEqual(len(parts), 1)
            self.assertEqual(parts[0].get_filename(), pdf.name)

    def test_env_recipient_used_when_no_arg(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = _pdf(tmp)
            fake = _FakeSMTP()
            with _smtp_env(), patch.dict(os.environ, {"REPORT_RECIPIENT": "env@example.com"}):
                with patch("tds_ads_reporting.mailer.sender.smtplib.SMTP", return_value=fake):
                    send_combined_report(pdf, "2026-03")
            self.assertEqual(fake.sent[0]["To"], "env@example.com")

    def test_default_recipient_when_nothing_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdf = _pdf(tmp)
            fake = _FakeSMTP()
            with _smtp_env(), patch.dict(os.environ, {}, clear=False):
                os.environ.pop("REPORT_RECIPIENT", None)
                with patch("tds_ads_reporting.mailer.sender.smtplib.SMTP", return_value=fake):
                    send_combined_report(pdf, "2026-03")
            self.assertEqual(fake.sent[0]["To"], DEFAULT_RECIPIENT)


class TestSendReportGmail(unittest.TestCase):
    def test_gmail_api_send_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            token_file = Path(tmp) / "gmail_token.json"
            token_file.write_text("{}")
            pdf = _pdf(tmp)
            service = MagicMock()
            send_mock = service.users.return_value.messages.return_value.send
            fake_modules = _fake_google_modules(service)
            with patch.dict(sys.modules, fake_modules):
                with patch.dict(
                    os.environ,
                    {
                        "GMAIL_SENDER": "reports@test.com",
                        "GOOGLE_APPLICATION_CREDENTIALS": "/tmp/creds.json",
                        "GMAIL_TOKEN_FILE": str(token_file),
                    },
                ):
                    send_report(_client("client@example.com"), pdf, "2026-03")
            self.assertEqual(send_mock.call_count, 1)
            kwargs = send_mock.call_args.kwargs
            self.assertEqual(kwargs["userId"], "me")
            parsed = _parse(base64.urlsafe_b64decode(kwargs["body"]["raw"]))
            self.assertEqual(_decoded(parsed["Subject"]), "Lodge — 2026-03 Performance Report")
            self.assertEqual(parsed["To"], "client@example.com")
            parts = list(parsed.iter_attachments())
            self.assertEqual(len(parts), 1)
            self.assertEqual(parts[0].get_filename(), "lodge_2026-03.pdf")

    def test_gmail_api_send_combined_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            token_file = Path(tmp) / "gmail_token.json"
            token_file.write_text("{}")
            pdf = _pdf(tmp)
            service = MagicMock()
            send_mock = service.users.return_value.messages.return_value.send
            fake_modules = _fake_google_modules(service)
            with patch.dict(sys.modules, fake_modules):
                with patch.dict(
                    os.environ,
                    {
                        "GMAIL_SENDER": "reports@test.com",
                        "GOOGLE_APPLICATION_CREDENTIALS": "/tmp/creds.json",
                        "GMAIL_TOKEN_FILE": str(token_file),
                    },
                ):
                    send_combined_report(pdf, "2026-03", recipient="boss@example.com")
            kwargs = send_mock.call_args.kwargs
            parsed = _parse(base64.urlsafe_b64decode(kwargs["body"]["raw"]))
            self.assertEqual(_decoded(parsed["Subject"]), "Combined Media Buying Report — 2026-03")
            self.assertEqual(parsed["To"], "boss@example.com")
            self.assertIn("all active clients", _plain_body(parsed))


if __name__ == "__main__":
    unittest.main()