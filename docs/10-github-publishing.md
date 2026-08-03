# GitHub Publishing

## Current Situation

This project can be committed locally immediately.

GitHub publishing requires one of these:

- GitHub CLI authenticated with `gh auth login`.
- A remote repository URL and working SSH/HTTPS credentials.
- A GitHub token configured securely outside this repository.

## Recommended Repository Name

```text
tds-ads-reporting-automation
```

## Recommended Visibility

Private repository, because the project will eventually reference client reporting logic and credential setup.

## Commands After GitHub Auth

```bash
gh auth login
gh repo create tds-ads-reporting-automation --private --source=. --remote=origin --push
```

## If Repository Already Exists

```bash
git remote add origin git@github.com:<ORG_OR_USER>/tds-ads-reporting-automation.git
git push -u origin main
```

## Security Reminder

Before pushing:

- Confirm `.env` is not committed.
- Confirm `secrets/` is not committed.
- Confirm generated PDFs are not committed.
- Confirm client real account IDs are not committed unless repo is private and approved.
