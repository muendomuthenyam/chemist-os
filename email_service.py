import smtplib
import os
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

def generate_otp() -> str:
    """Generates a secure 6-digit numeric verification code."""
    return f"{random.randint(100000, 999999)}"

def send_otp_email(to_email: str, otp_code: str) -> bool:
    """Sends 6-digit OTP verification email or prints to console if local."""
    # Local fallback for testing without active SMTP setup
    if not SMTP_USER or not SMTP_PASSWORD:
        print("\n" + "="*50)
        print(f" [LOCAL DEMO OTP VERIFICATION]")
        print(f" Recipient: {to_email}")
        print(f" Verification Code: {otp_code}")
        print("="*50 + "\n")
        return True

    msg = MIMEMultipart()
    msg["From"] = f"ChemistOS Security <{SMTP_USER}>"
    msg["To"] = to_email
    msg["Subject"] = f"{otp_code} is your ChemistOS Verification Code"

    body = f"""
    Hello,

    Thank you for registering your business on ChemistOS Mobile.

    Your 6-digit email verification code is: {otp_code}

    If you did not request this, please ignore this email.

    Regards,
    ChemistOS Security Team
    """
    msg.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
        server.close()
        return True
    except Exception as e:
        print(f"Email delivery error: {e}")
        return False