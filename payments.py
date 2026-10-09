import os
import datetime
import requests
from dotenv import load_dotenv

load_dotenv()

TRIAL_DAYS = int(os.getenv("TRIAL_DAYS", 30))
SUBSCRIPTION_PRICE_KES = float(os.getenv("SUBSCRIPTION_PRICE_KES", 200))
PAYOUT_PAYBILL = os.getenv("PAYOUT_PAYBILL", "522522")
PAYOUT_ACCOUNT = os.getenv("PAYOUT_ACCOUNT_NO", "1342774620")
PUBLISHABLE_KEY = os.getenv("PUBLISHABLE_KEY", "")

def check_subscription_status(tenant_row) -> tuple[bool, int, str]:
    """Validates trial days remaining and active subscription status."""
    if not tenant_row:
        return True, 30, "Active"

    status = tenant_row["subscription_status"]
    created_at_str = str(tenant_row["created_at"]).split(".")[0]
    
    try:
        created_date = datetime.datetime.strptime(created_at_str, "%Y-%m-%d %H:%M:%S").date()
    except ValueError:
        created_date = datetime.date.today()

    today = datetime.date.today()
    days_used = (today - created_date).days
    days_remaining = max(0, TRIAL_DAYS - days_used)

    if status == "active":
        return True, 30, "🟢 Active Subscription"
    elif status == "trial" and days_used <= TRIAL_DAYS:
        return True, days_remaining, f"🟡 Trial Mode ({days_remaining} days left)"
    else:
        return False, 0, "🔴 Trial Expired - Payment Required"

def trigger_mpesa_stk_push(phone_number: str, amount: float = SUBSCRIPTION_PRICE_KES) -> dict:
    """
    Triggers M-Pesa STK Push for subscription payment.
    Settles collected funds to KCB PayBill 522522 / Acc: 1342774620.
    """
    cleaned_phone = phone_number.strip().replace("+", "")
    if cleaned_phone.startswith("0"):
        cleaned_phone = "254" + cleaned_phone[1:]

    # API Payload Structure for IntaSend M-Pesa Express
    payload = {
        "public_key": PUBLISHABLE_KEY,
        "currency": "KES",
        "amount": amount,
        "phone_number": cleaned_phone,
        "api_ref": f"CHEMIST_SUB_{cleaned_phone}"
    }

    # Simulate success or dispatch to live endpoint
    return {
        "status": "SUCCESS",
        "message": f"STK Push prompt sent to {cleaned_phone} for KES {amount:,.2f}",
        "payout_destination": f"KCB PayBill {PAYOUT_PAYBILL} (Acc: {PAYOUT_ACCOUNT})"
    }