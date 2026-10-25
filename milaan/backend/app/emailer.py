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


def send_password_reset(settings, email, token):
    if not settings.smtp_host or not settings.smtp_from:
        raise RuntimeError('Email is not configured')
    message = EmailMessage()
    message['Subject'] = 'Reset your Milaan password'
    message['From'], message['To'] = settings.smtp_from, email
    # A fragment avoids sending the token to HTTP access logs or referrers.
    url = settings.public_origin + '/reset-password#token=' + token
    message.set_content('Reset your password using this one-time link (expires in 15 minutes):\n\n'+url+'\n\nIf you did not request this, ignore this email. Never share the link.')
    context = ssl.create_default_context()
    connection = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15, context=context) if settings.smtp_security == 'ssl' else smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
    with connection as smtp:
        if settings.smtp_security == 'starttls': smtp.starttls(context=context)
        if settings.smtp_user: smtp.login(settings.smtp_user, settings.smtp_password)
        smtp.send_message(message)
