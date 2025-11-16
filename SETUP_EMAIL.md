# Email Notification Setup

This guide shows how to configure the app to send compliance notifications to registered users' email addresses.

## How It Works

1. **User registers** with their email address (e.g., `user@gmail.com`)
2. **User logs in** and uploads a contract
3. **App analyzes** the contract and detects missing clauses
4. **App sends notification email** to the user's registered email address
5. **User receives email** in their inbox with:
   - Summary of missing clauses
   - Link to download amended contract

## Prerequisites

You must configure a real SMTP provider so emails are delivered. Options:

### Option 1: Gmail (Recommended for Development)

#### Step 1: Enable 2-Factor Authentication on your Google account

1. Go to [myaccount.google.com/security](https://myaccount.google.com/security)
2. Click "2-Step Verification" and follow the steps to enable it

#### Step 2: Create an App Password

1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Select "Mail" and "macOS" (or your device)
3. Google will generate a 16-character password. **Copy this password.**

#### Step 3: Set Environment Variables

In the terminal where you run the Flask app, export:

```bash
export SMTP_HOST="smtp.gmail.com"
export SMTP_PORT=465
export SMTP_USE_SSL=1
export EMAIL_SENDER="your.email@gmail.com"
export EMAIL_SMTP_PASS="your-16-char-app-password"
```

**Replace:**

- `your.email@gmail.com` with your actual Gmail address
- `your-16-char-app-password` with the password you copied in Step 2

#### Step 4: Restart Flask

```bash
flask run
```

Now when a registered user uploads a contract, the app will send notifications to their email address.

### Option 2: SendGrid (Free Tier Available)

1. Sign up at [sendgrid.com](https://sendgrid.com)
2. Create an API key in Settings → API Keys
3. Export env vars:

```bash
export SMTP_HOST="smtp.sendgrid.net"
export SMTP_PORT=587
export SMTP_USE_SSL=0
export EMAIL_SENDER="noreply@yourdomain.com"
export EMAIL_SMTP_PASS="SG.your-api-key-here"
```

### Option 3: Persist Config in the App (No Restart Needed)

If you don't want to restart the Flask app every time, save config to the database:

1. Sign in as an admin user (set `ADMIN_EMAILS` env var or POST to admin config endpoint)
2. Use curl to save SMTP settings:

```bash
curl -X POST http://localhost:5000/admin/config \
  -H "Content-Type: application/json" \
  -d '{
    "SMTP_HOST": "smtp.gmail.com",
    "SMTP_PORT": "465",
    "SMTP_USE_SSL": "1",
    "EMAIL_SENDER": "your.email@gmail.com",
    "EMAIL_SMTP_PASS": "your-app-password"
  }'
```

Once saved, the settings persist across server restarts.

## Test It

1. Register a new user with email `test@gmail.com`
2. Log in with that user
3. Upload a contract PDF/DOCX
4. Check your inbox — you should see the notification email within 1-2 minutes

## Troubleshooting

**Email not arriving?**

- Check Flask logs for "Email send failed: ..." message
- Verify env vars are exported correctly: `echo $SMTP_HOST` should show `smtp.gmail.com`
- If using Gmail, confirm the app password is correct (not your Google account password)
- Check the "Less secure apps" setting if using Gmail (though app passwords bypass this)

**Emails going to spam?**

- Sender address matters; use your actual Gmail account as `EMAIL_SENDER`
- Add a proper reply-to header (enhancement for future)

## Production Considerations

For production:

- Store SMTP credentials in a secrets manager (AWS Secrets Manager, HashiCorp Vault, etc.)
- Do NOT commit env var files to Git
- Use environment-specific configs
- Monitor email delivery rates and failures
- Consider dedicated email services (SendGrid, Mailgun, AWS SES) for reliability
