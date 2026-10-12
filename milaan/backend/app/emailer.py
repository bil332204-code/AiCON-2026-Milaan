"""SMTP delivery: secrets and verification codes are never logged or returned."""
import smtplib
import ssl
from email.message import EmailMessage

def send_verification(settings, email, code):
    if not settings.smtp_host or not settings.smtp_from:
        raise RuntimeError("Email is not configured")
    message = EmailMessage()
    message["Subject"] = "Your Milaan verification code"
    message["From"] = settings.smtp_from
    message["To"] = email
    message.set_content(f"Your Milaan verification code is: {code}\n\nIt expires in 10 minutes. If you did not request this, ignore this email. Never share this code.")
    context = ssl.create_default_context()
    if settings.smtp_security == "ssl":
        connection = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15, context=context)
    else:
        connection = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
    with connection as smtp:
        if settings.smtp_security == "starttls":
            smtp.starttls(context=context)
        if settings.smtp_user:
            smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)
