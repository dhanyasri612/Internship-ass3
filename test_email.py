"""Simple test script to exercise notifications.send_email

Usage:
  python3 test_email.py [recipient] [subject] [body]

If recipient is omitted, the script will try to use NOTIFICATION_EMAIL env var.
"""
import sys
import os
from notifications import send_email

def main():
    recipient = sys.argv[1] if len(sys.argv) > 1 else os.getenv("NOTIFICATION_EMAIL")
    subject = sys.argv[2] if len(sys.argv) > 2 else "Test: Compliance Notification"
    body = sys.argv[3] if len(sys.argv) > 3 else "This is a test notification from the Contract Analyzer."

    if not recipient:
        print("No recipient specified and NOTIFICATION_EMAIL not set. Exiting.")
        sys.exit(2)

    print(f"Sending test email to: {recipient}")
    try:
        send_email(recipient, subject, body)
        print("Email sent successfully (no exception raised by send_email). Check recipient inbox.")
    except Exception as e:
        print("send_email raised an exception:")
        print(repr(e))
        sys.exit(1)

if __name__ == '__main__':
    main()
