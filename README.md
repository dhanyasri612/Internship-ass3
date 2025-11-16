Compliance Checker — Multi-platform Integration (Assignment 3)

This repository implements a contract Compliance Checker that analyzes uploaded contracts, detects missing clauses, generates amended contracts, and notifies users via Email, Slack, and Google Sheets.

This README explains how the multi-platform notification system is wired, how to configure credentials, and how to test the integrations locally.

## Project structure (important files)

- `app.py` — Flask backend. Key endpoints:
  - `POST /upload` — upload a PDF/DOCX file, runs clause extraction, Phase 1 classification and risk analysis; generates amended contract when clauses missing; sends notifications (email/Slack/Sheets) and stores in-memory notifications for the frontend.
  - `GET /download/amended` — download the most recently generated amended contract.
  - `GET /notifications/latest` — returns recent notifications for the logged-in user.
  - `/admin/*` endpoints — admin config and test-email helpers.
- `notifications.py` — helpers for sending email (SMTP), Slack (Slack WebClient) and appending to Google Sheets (`gspread`).
- `models.py` — SQLAlchemy models for admin `Config` and optional `User` model skeleton.
- `frontend/` — React frontend (Upload form, notifications polling, charts, etc.).

## Integration overview

1. Email

   - Uses `smtplib` via `send_email()` in `notifications.py`.
   - Supports both SSL (465) and STARTTLS (587). The helper reads environment variables or accepts call-time values.
   - Environment variables used (any of these names will work if present):

     - `EMAIL_SENDER` or `EMAIL_USER` (sender address)
     - `EMAIL_SMTP_PASS` or `EMAIL_PASS` (sender password or app-password)
     - `SMTP_HOST` or `EMAIL_HOST` (defaults to `smtp.gmail.com`)
     - `SMTP_PORT` or `EMAIL_PORT` (defaults to `465`)
     - `EMAIL_USE_TLS` (if `true`, uses STARTTLS on port 587)

   - For Gmail, create an App Password (recommended) and set `EMAIL_USER` and `EMAIL_PASS` in the environment used to run the Flask server.

2. Google Sheets

   - Uses `gspread` and a service account credentials JSON file.
   - Set `GOOGLE_CREDS_FILE` to point to your service account JSON (defaults to `credentials.json`).
   - `append_to_google_sheet(sheet_name, row_values)` appends a row to the first worksheet of the spreadsheet named `sheet_name`.

3. Slack
   - Uses `slack_sdk.WebClient` with a bot token in `SLACK_BOT_TOKEN`.
   - `send_slack_to_user(channel_or_user, message)` sends a message to a channel or user ID.

## Example email body (as requested)

Subject: Compliance update

Body:

```
Hello team,
This is to inform regarding a real-time update in the contract 19:
'Data privacy protection clause is missing.'
regards,
Finance team (Masthan)
```

When the backend finds missing clauses during an upload, it generates an amended file and will attempt to:

- send this email to the logged-in user,
- append a row to a configured Google Sheet,
- post a message to a Slack channel.

## Quick setup & testing

1. Install Python deps (backend):

```bash
python3 -m pip install -r requirements.txt
```

2. Set environment variables for email/Slack/Google Sheets. Example (macOS zsh):

```bash
export EMAIL_USER="youremail@example.com"
export EMAIL_PASS="your_smtp_or_app_password"
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT=587
export EMAIL_USE_TLS=true

export SLACK_BOT_TOKEN="xoxb-..."
export GOOGLE_CREDS_FILE="/path/to/creds.json"
```

3. Start the backend (run from repo root):

```bash
python3 app.py
```

4. Start the frontend (open a separate terminal):

```bash
cd frontend
npm install
npm start
```

5. Upload a contract via the frontend Upload form. If missing clauses are detected:
   - You should see a notification in the web UI (polls `/notifications/latest`).
   - An email will be attempted to the authenticated user's email.
   - A row will be appended to the configured Google Sheet (if credentials and sheet name match).
   - A Slack message will be posted (if `SLACK_BOT_TOKEN` is set correctly).

## Test helpers

A small helper script `notifications_test.py` is included to exercise the integrations without going through the upload UI. Run it to verify each platform is configured.

## Security & production notes

- Do not keep plaintext credentials in code. Use environment variables, secret managers, or a secure config service in production.
- Persist notifications in a durable DB rather than in-memory `NOTIFICATIONS` (so dismissals and history survive restarts).
- Rate-limit and monitor outgoing messages to avoid being blocked by providers.

## Next steps / Improvements

- Persist notifications with SQLAlchemy and associate them with user accounts.
- Add retry queues for failed notifications (Celery/RQ + Redis).
- Improve templates for amended contract generation (generate `.docx` instead of `.txt`).

---

If you want, I can now: run a quick import check of the backend, add the `notifications_test.py` script, or wire a simple README in the `frontend/` folder. Which would you like next?
