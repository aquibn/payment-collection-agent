"""
API integration layer.

All external HTTP calls are isolated here. Functions return typed dicts so
the rest of the agent never touches raw HTTP or JSON.
"""

import requests
from typing import Optional
from state_models import AccountData

BASE_URL = "https://se-payment-verification-api.service.external.usea2.aws.prodigaltech.com/openapi"

# HTTP timeout (seconds)
REQUEST_TIMEOUT = 10


# ──────────────────────────────────────────────
# Account Lookup
# ──────────────────────────────────────────────

def lookup_account(account_id: str) -> dict:
    """
    POST /api/lookup-account

    Returns:
        {"success": True, "account": AccountData}
        {"success": False, "error": "account_not_found" | "network_error" | "unexpected_error"}
    """
    try:
        resp = requests.post(
            f"{BASE_URL}/api/lookup-account",
            json={"account_id": account_id},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.Timeout:
        return {"success": False, "error": "network_error", "detail": "Request timed out."}
    except requests.exceptions.RequestException as exc:
        return {"success": False, "error": "network_error", "detail": str(exc)}

    if resp.status_code == 200:
        data = resp.json()
        account = AccountData(
            account_id=data["account_id"],
            full_name=data["full_name"],
            dob=data["dob"],
            aadhaar_last4=str(data["aadhaar_last4"]),
            pincode=str(data["pincode"]),
            balance=float(data["balance"]),
        )
        return {"success": True, "account": account}

    if resp.status_code == 404:
        return {"success": False, "error": "account_not_found"}

    return {
        "success": False,
        "error": "unexpected_error",
        "detail": f"HTTP {resp.status_code}",
    }


# ──────────────────────────────────────────────
# Payment Processing
# ──────────────────────────────────────────────

def process_payment(
    account_id: str,
    amount: float,
    cardholder_name: str,
    card_number: str,
    cvv: str,
    expiry_month: int,
    expiry_year: int,
) -> dict:
    """
    POST /api/process-payment

    Returns:
        {"success": True, "transaction_id": str}
        {"success": False, "error": str, "retryable": bool}
    """
    payload = {
        "account_id": account_id,
        "amount": amount,
        "payment_method": {
            "type": "card",
            "card": {
                "cardholder_name": cardholder_name,
                "card_number": card_number,
                "cvv": cvv,
                "expiry_month": expiry_month,
                "expiry_year": expiry_year,
            },
        },
    }

    try:
        resp = requests.post(
            f"{BASE_URL}/api/process-payment",
            json=payload,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.Timeout:
        return {"success": False, "error": "network_error", "retryable": True,
                "detail": "Request timed out."}
    except requests.exceptions.RequestException as exc:
        return {"success": False, "error": "network_error", "retryable": True,
                "detail": str(exc)}

    if resp.status_code == 200:
        data = resp.json()
        if data.get("success"):
            return {"success": True, "transaction_id": data["transaction_id"]}

    # 422 or unexpected failure
    try:
        err_data = resp.json()
        error_code = err_data.get("error_code", "unknown_error")
    except Exception:
        error_code = "unknown_error"

    # Classify retryability
    user_fixable = {
        "invalid_card",
        "invalid_cvv",
        "invalid_expiry",
        "invalid_amount",
    }
    retryable = error_code in user_fixable

    return {
        "success": False,
        "error": error_code,
        "retryable": retryable,
    }


# ──────────────────────────────────────────────
# Error code → human message mapping
# ──────────────────────────────────────────────

PAYMENT_ERROR_MESSAGES = {
    "insufficient_balance": (
        "The amount you entered exceeds your outstanding balance. "
        "Please enter an amount equal to or less than your balance."
    ),
    "invalid_amount": (
        "The amount is invalid — it must be greater than zero and have at most "
        "two decimal places. Please re-enter the amount."
    ),
    "invalid_card": (
        "The card number appears to be invalid (failed format check). "
        "Please double-check and re-enter your 16-digit card number."
    ),
    "invalid_cvv": (
        "The CVV you provided is invalid. Please re-enter the 3-digit CVV "
        "(or 4 digits for Amex) from the back of your card."
    ),
    "invalid_expiry": (
        "The card expiry date is invalid or the card has already expired. "
        "Please re-enter a valid expiry date (MM/YYYY)."
    ),
    "network_error": (
        "I'm having trouble reaching the payment server right now. "
        "Please try again in a moment."
    ),
}


def payment_error_message(error_code: str) -> str:
    return PAYMENT_ERROR_MESSAGES.get(
        error_code,
        "An unexpected error occurred while processing your payment. "
        "Please try again or contact support.",
    )
