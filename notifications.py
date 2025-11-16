# notifications.py
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from slack_sdk import WebClient
import gspread


def send_email(
    to_email: str,
    subject: str,
    body: str,
    from_email: str = None,
    smtp_host: str = None,
    smtp_port: int = None,
    smtp_use_ssl: bool = None,
    smtp_password: str = None,
    attachment_path: str = None,
    attachment_name: str | None = None,
):
    """Send an email using SMTP.

    Configured via env vars (tries multiple naming conventions):
      - EMAIL_SENDER or EMAIL_USER (from_email)
      - EMAIL_SMTP_PASS or EMAIL_PASS (password)
      - SMTP_HOST or EMAIL_HOST (defaults to smtp.gmail.com)
      - SMTP_PORT or EMAIL_PORT (defaults to 465)
      - SMTP_USE_SSL or EMAIL_USE_TLS (default true for SSL, check EMAIL_USE_TLS for TLS)

    Raises RuntimeError with details on failure.
    """
    # Determine sender email
    sender = from_email or os.getenv("EMAIL_SENDER") or os.getenv("EMAIL_USER")
    
    # Determine SMTP password (try multiple names)
    password = smtp_password if smtp_password is not None else (os.getenv("EMAIL_SMTP_PASS") or os.getenv("EMAIL_PASS"))
    
    # Determine SMTP host
    smtp_host = smtp_host or os.getenv("SMTP_HOST") or os.getenv("EMAIL_HOST", "smtp.gmail.com")
    
    # Determine SMTP port and whether to use SSL/TLS
    smtp_port_raw = os.getenv("SMTP_PORT") or os.getenv("EMAIL_PORT")
    if smtp_port:
        smtp_port = int(smtp_port)
    elif smtp_port_raw:
        smtp_port = int(smtp_port_raw)
    else:
        smtp_port = 465  # default
    
    # Determine SSL/TLS usage
    if smtp_use_ssl is None:
        # Check EMAIL_USE_TLS first (if set to True, use TLS on port 587)
        email_use_tls = os.getenv("EMAIL_USE_TLS", "").lower() in ("true", "1", "yes")
        if email_use_tls:
            smtp_use_ssl = False  # TLS uses STARTTLS, not SSL
        else:
            smtp_use_ssl = os.getenv("SMTP_USE_SSL", "1") not in ("0", "false", "False")

    if not sender:
        raise RuntimeError("EMAIL_SENDER (or EMAIL_USER) not set")

    if attachment_path:
        # build a multipart message with attachment
        msg = MIMEMultipart()
        msg.attach(MIMEText(body))
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to_email

        # attach file
        try:
            with open(attachment_path, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            filename = attachment_name or os.path.basename(attachment_path)
            part.add_header("Content-Disposition", f"attachment; filename=\"{filename}\"")
            msg.attach(part)
        except Exception as e:
            # if attachment fails, fall back to plain message body
            msg = MIMEText(body + f"\n\n(Attachment failed: {e})")
            msg["Subject"] = subject
            msg["From"] = sender
            msg["To"] = to_email
    else:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to_email

    try:
        if smtp_use_ssl:
            with smtplib.SMTP_SSL(smtp_host, smtp_port) as smtp:
                # if password provided, attempt login; otherwise send without auth
                if password:
                    smtp.login(sender, password)
                smtp.sendmail(sender, [to_email], msg.as_string())
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as smtp:
                smtp.ehlo()
                # try STARTTLS if a real server and not local debug
                try:
                    smtp.starttls()
                except Exception:
                    # some debug servers (like smtpd.DebuggingServer) won't support STARTTLS
                    pass
                if password:
                    try:
                        smtp.login(sender, password)
                    except Exception:
                        # login may fail for debug servers; continue to attempt send
                        pass
                smtp.sendmail(sender, [to_email], msg.as_string())
    except Exception as e:
        # raise a RuntimeError with the underlying exception message for easier debugging
        raise RuntimeError(f"Failed to send email via SMTP ({smtp_host}:{smtp_port}): {e}")

def send_slack_to_user(slack_user_or_channel: str, message: str):
    token = os.getenv("SLACK_BOT_TOKEN")
    if not token:
        raise RuntimeError("SLACK_BOT_TOKEN not set")
    client = WebClient(token=token)
    # slack_user_or_channel can be user ID (U...) or channel (#channel)
    client.chat_postMessage(channel=slack_user_or_channel, text=message)

def append_to_google_sheet(sheet_name: str, row_values: list):
    creds_file = os.getenv("GOOGLE_CREDS_FILE", "credentials.json")
    if not os.path.exists(creds_file):
        raise RuntimeError("Google credentials file missing")
    gc = gspread.service_account(filename=creds_file)
    sheet = gc.open(sheet_name).sheet1
    sheet.append_row(row_values)
