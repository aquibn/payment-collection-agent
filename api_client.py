"""
API integration layer.

Supports two modes:
  • Live mode  (default)  — calls the real external API
  • Mock mode  (MOCK_API=1) — returns realistic fake data, no network needed

Set mock mode:
    MOCK_API=1 python app.py        # via env var
"""

import os
import requests
from state_models import AccountData

# ── URL Fix ──────────────────────────────────────────────────────────────────
# The spec says Base URL: .../openapi/
# /openapi/ is the OpenAPI DOCS URL prefix, NOT an API path prefix.
# Real endpoints live at /api/lookup-account and /api/process-payment.
# BUG WAS: BASE_URL = ".../openapi" → ".../openapi/api/..." = 404
# FIX:     BASE_URL = ".../api"     → ".../api/lookup-account" = 200
# ─────────────────────────────────────────────────────────────────────────────

BASE_URL = "https://se-payment-verification-api.service.external.usea2.aws.prodigaltech.com/api"

REQUEST_TIMEOUT = 10

# ── Mock mode detection ───────────────────────────────────────────────────────
MOCK_MODE = os.environ.get("MOCK_API", "").strip() in ("1", "true", "yes")

# Mock data matching the assignment's test accounts
_MOCK_DB = {
    "ACC1001": {
        "account_id": "ACC1001", "full_name": "Nithin Jain",
        "dob": "1990-05-14", "aadhaar_last4": "4321",
        "pincode": "400001", "balance": 1250.75,
    },
    "ACC1002": {
        "account_id": "ACC1002", "full_name": "Rajarajeswari Balasubramaniam",
        "dob": "1985-11-23", "aadhaar_last4": "9876",
        "pincode": "400002", "balance": 540.00,
    },
    "ACC1003": {
        "account_id": "ACC1003", "full_name": "Priya Agarwal",
        "dob": "1992-08-10", "aadhaar_last4": "2468",
        "pincode": "400003", "balance": 0.00,
    },
    "ACC1004": {
        "account_id": "ACC1004", "full_name": "Rahul Mehta",
        "dob": "1988-02-29", "aadhaar_last4": "1357",
        "pincode": "400004", "balance": 3200.50,
    },
}

_MOCK_TXN_COUNTER = [1000]


# ─────────────────────────────────────────────────────────────────────────────
# Account Lookup
# ─────────────────────────────────────────────────────────────────────────────

def lookup_account(account_id: str) -> dict:
    if MOCK_MODE:
        return _mock_lookup(account_id)

    url = f"{BASE_URL}/lookup-account"
    _log_request("POST", url, {"account_id": account_id})

    try:
        resp = requests.post(url, json={"account_id": account_id}, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.Timeout:
        _log_error("Timeout reaching lookup-account")
        return {"success": False, "error": "network_error", "detail": "Request timed out after 10s."}
    except requests.exceptions.ConnectionError as exc:
        _log_error(f"Connection error: {exc}")
        return {"success": False, "error": "network_error", "detail": "Cannot reach the API server."}
    except requests.exceptions.RequestException as exc:
        _log_error(f"Request error: {exc}")
        return {"success": False, "error": "network_error", "detail": str(exc)}

    _log_response(resp)

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

    try:
        err = resp.json()
    except Exception:
        err = {"raw": resp.text[:200]}
    _log_error(f"Unexpected HTTP {resp.status_code}: {err}")
    return {"success": False, "error": "unexpected_error", "detail": f"HTTP {resp.status_code} — {err}"}


# ─────────────────────────────────────────────────────────────────────────────
# Payment Processing
# ─────────────────────────────────────────────────────────────────────────────

def process_payment(account_id, amount, cardholder_name, card_number, cvv, expiry_month, expiry_year):
    if MOCK_MODE:
        return _mock_payment(account_id, amount, card_number, cvv, expiry_month, expiry_year)

    url = f"{BASE_URL}/process-payment"
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
    safe = {**payload, "payment_method": {**payload["payment_method"],
        "card": {**payload["payment_method"]["card"],
                 "card_number": f"****{card_number[-4:]}", "cvv": "***"}}}
    _log_request("POST", url, safe)

    try:
        resp = requests.post(url, json=payload, timeout=REQUEST_TIMEOUT)
    except requests.exceptions.Timeout:
        return {"success": False, "error": "network_error", "retryable": True}
    except requests.exceptions.RequestException as exc:
        return {"success": False, "error": "network_error", "retryable": True, "detail": str(exc)}

    _log_response(resp)

    if resp.status_code == 200:
        data = resp.json()
        if data.get("success"):
            return {"success": True, "transaction_id": data["transaction_id"]}

    try:
        error_code = resp.json().get("error_code", "unknown_error")
    except Exception:
        error_code = "unknown_error"

    # insufficient_balance is retryable — user can enter a smaller amount
    user_fixable = {"invalid_card", "invalid_cvv", "invalid_expiry", "invalid_amount", "insufficient_balance"}
    return {"success": False, "error": error_code, "retryable": error_code in user_fixable}


# ─────────────────────────────────────────────────────────────────────────────
# Mock implementations (offline mode)
# ─────────────────────────────────────────────────────────────────────────────

def _mock_lookup(account_id: str) -> dict:
    _log(f"[MOCK] lookup_account({account_id})")
    raw = _MOCK_DB.get(account_id.upper())
    if not raw:
        return {"success": False, "error": "account_not_found"}
    return {"success": True, "account": AccountData(
        account_id=raw["account_id"], full_name=raw["full_name"],
        dob=raw["dob"], aadhaar_last4=raw["aadhaar_last4"],
        pincode=raw["pincode"], balance=raw["balance"],
    )}


def _mock_payment(account_id, amount, card_number, cvv, expiry_month, expiry_year) -> dict:
    _log(f"[MOCK] process_payment — acc={account_id}, amt={amount}, card=****{card_number[-4:] if len(card_number)>=4 else '??'}")
    from datetime import date
    today = date.today()
    if len(card_number) != 16 or not card_number.isdigit() or not _luhn(card_number):
        return {"success": False, "error": "invalid_card", "retryable": True}
    if len(cvv) not in (3, 4) or not cvv.isdigit():
        return {"success": False, "error": "invalid_cvv", "retryable": True}
    if expiry_year < today.year or (expiry_year == today.year and expiry_month < today.month):
        return {"success": False, "error": "invalid_expiry", "retryable": True}
    if amount <= 0:
        return {"success": False, "error": "invalid_amount", "retryable": True}
    _MOCK_TXN_COUNTER[0] += 1
    txn = f"txn_mock_{_MOCK_TXN_COUNTER[0]:06d}"
    _log(f"[MOCK] → success, txn={txn}")
    return {"success": True, "transaction_id": txn}


def _luhn(n: str) -> bool:
    digits = [int(d) for d in reversed(n)]
    total = sum(d if i % 2 == 0 else (d * 2 - 9 if d * 2 > 9 else d * 2)
                for i, d in enumerate(digits))
    return total % 10 == 0


# ─────────────────────────────────────────────────────────────────────────────
# Debug logging
# ─────────────────────────────────────────────────────────────────────────────

def _log(*args):
    print("  [api]", *args)

def _log_request(method, url, body):
    print(f"\n  [api →] {method} {url}")
    print(f"          body: {body}")

def _log_response(resp):
    try: body = resp.json()
    except Exception: body = resp.text[:120]
    status_icon = "✅" if resp.status_code == 200 else "❌"
    print(f"  [api ←] {status_icon} HTTP {resp.status_code} | {body}")


# ─────────────────────────────────────────────────────────────────────────────
# Error messages
# ─────────────────────────────────────────────────────────────────────────────

PAYMENT_ERROR_MESSAGES = {
    "insufficient_balance": "The amount exceeds your outstanding balance. Please enter a smaller amount.",
    "invalid_amount": "The amount is invalid — must be > 0 with at most 2 decimal places.",
    "invalid_card": "The card number is invalid (failed Luhn check or wrong length). Please re-enter your 16-digit card number.",
    "invalid_cvv": "The CVV is invalid. Please re-enter the 3-digit CVV (4 for Amex) from the back of your card.",
    "invalid_expiry": "The card expiry date is invalid or the card has expired. Please re-enter as MM/YYYY.",
    "network_error": "I'm having trouble reaching the payment server. Please try again in a moment.",
}

def payment_error_message(error_code: str) -> str:
    return PAYMENT_ERROR_MESSAGES.get(error_code,
        "An unexpected error occurred. Please try again or contact support.")
