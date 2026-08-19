# QA Checklist

## Preflight

- `.env` exists and is not committed.
- Client config validates.
- Meta token works.
- Google refresh token works.
- Email sender works.
- Reports directory is writable.
- Logs directory is writable.

## Data Accuracy

For each test client:

- Meta spend matches Ads Manager for same date range.
- Meta impressions match Ads Manager.
- Meta results match selected action mapping.
- Meta CPA matches spend / mapped results.
- Date range is previous calendar month.
- Currency is correct.

## PDF Accuracy

- Client name is correct.
- Month/year is correct.
- Platforms included are correct.
- Missing platforms are not shown.
- KPI cards calculate correctly.
- Charts match table data.
- Campaign table sorts correctly.
- Recommendations are reasonable.
- No placeholder text remains.
- No internal errors appear in report.

## Email Accuracy

- Email sent to `reports@trafficdigitalsolutions.com`.
- Subject includes client name and month.
- PDF is attached.
- Attachment opens successfully.
- Email status is saved.

## Failure Testing

- Invalid Meta account does not stop other clients.
- Email failure leaves PDF saved locally.
- Rerun does not duplicate rows.
- Logs contain enough information to fix issue.

## Production Approval

- At least 3 clients verified against manual reports.
- One Meta-only client verified.
- Agency approves final PDF design.
- First production run reviewed manually before trusting automation.
