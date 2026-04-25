"""
Input parsing and validation helpers.

All user-facing parsing lives here so ConversationManager stays readable.
"""

import re
from datetime import date, datetime
from typing import Optional, Tuple


# ──────────────────────────────────────────────
# Account ID
# ──────────────────────────────────────────────

def extract_account_id(text: str) -> Optional[str]:
    """Extract an account ID like ACC1001 from free text."""
    match = re.search(r'\bACC\d{4,}\b', text, re.IGNORECASE)
    if match:
        return match.group().upper()
    # Also accept bare numbers if the user just typed "1001"
    match = re.search(r'\b(\d{4,})\b', text)
    if match:
        return f"ACC{match.group(1)}"
    return None


# ──────────────────────────────────────────────
# Name
# ──────────────────────────────────────────────

def extract_name(text: str) -> Optional[str]:
    """
    Best-effort name extraction from free text.
    Strips common lead-in phrases so 'my name is Nithin Jain' → 'Nithin Jain'.
    Returns None only when there is clearly no name present.
    """
    patterns = [
        r"(?:my name is|i am|i'm|name:?)\s+([A-Za-z][\w\s'-]+)",
        r"(?:it's|its)\s+([A-Za-z][\w\s'-]+)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()

    # If input looks like a bare name (2-4 capitalised tokens, no other content)
    bare = text.strip()
    if re.fullmatch(r"[A-Za-z][\w'-]+(?:\s+[A-Za-z][\w'-]+){1,3}", bare):
        return bare

    return None


def names_match(provided: str, expected: str) -> bool:
    """
    Strict exact match after normalising internal whitespace.
    Case-sensitive as per spec.
    """
    normalise = lambda s: " ".join(s.strip().split())
    return normalise(provided) == normalise(expected)


# ──────────────────────────────────────────────
# Secondary verification factors
# ──────────────────────────────────────────────

def extract_dob(text: str) -> Optional[str]:
    """
    Extract a date in YYYY-MM-DD format from free text.
    Returns the string as-is so the caller can compare strictly.
    """
    # Direct YYYY-MM-DD
    m = re.search(r'\b(\d{4})-(\d{2})-(\d{2})\b', text)
    if m:
        return m.group(0)
    # DD/MM/YYYY or DD-MM-YYYY → convert
    m = re.search(r'\b(\d{2})[/-](\d{2})[/-](\d{4})\b', text)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    return None


def is_valid_date(date_str: str) -> bool:
    """Validate that a YYYY-MM-DD string is a real calendar date (handles leap years)."""
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def extract_aadhaar_last4(text: str) -> Optional[str]:
    """Extract exactly 4 consecutive digits intended as Aadhaar last 4."""
    # Prefer explicit label
    m = re.search(r'(?:aadhaar|aadhar)[^\d]*(\d{4})\b', text, re.IGNORECASE)
    if m:
        return m.group(1)
    # Standalone 4-digit sequence (not part of a longer number)
    m = re.search(r'(?<!\d)(\d{4})(?!\d)', text)
    if m:
        return m.group(1)
    return None


def extract_pincode(text: str) -> Optional[str]:
    """Extract a 6-digit pincode from free text."""
    m = re.search(r'(?:pincode|pin|postal)[^\d]*(\d{6})\b', text, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r'(?<!\d)(\d{6})(?!\d)', text)
    if m:
        return m.group(1)
    return None


# ──────────────────────────────────────────────
# Payment amount
# ──────────────────────────────────────────────

def extract_amount(text: str, max_amount: float) -> Tuple[Optional[float], Optional[str]]:
    """
    Parse a payment amount from text.

    Returns (amount, None) on success or (None, error_message) on failure.
    """
    # Strip currency symbols and commas
    cleaned = re.sub(r'[₹$,]', '', text)
    m = re.search(r'\b(\d+(?:\.\d{1,2})?)\b', cleaned)
    if not m:
        return None, "I couldn't find a valid amount. Please enter a number, e.g. 500 or 1250.75."

    amount = float(m.group(1))

    if amount <= 0:
        return None, "The amount must be greater than zero."

    # Validate max 2 decimal places
    if round(amount, 2) != amount or len(str(amount).split('.')[-1]) > 2:
        return None, "Please enter an amount with at most two decimal places."

    if amount > max_amount:
        return None, (
            f"The amount ₹{amount:,.2f} exceeds your outstanding balance of "
            f"₹{max_amount:,.2f}. Please enter a smaller amount."
        )

    return amount, None


# ──────────────────────────────────────────────
# Card details
# ──────────────────────────────────────────────

def extract_card_number(text: str) -> Optional[str]:
    """Extract a 16-digit card number (spaces/dashes allowed between groups)."""
    # Remove spaces and dashes, find 16-digit sequence
    digits_only = re.sub(r'[\s\-]', '', text)
    m = re.search(r'\b(\d{16})\b', digits_only)
    return m.group(1) if m else None


def extract_cvv(text: str) -> Optional[str]:
    """Extract a 3- or 4-digit CVV."""
    m = re.search(r'(?:cvv|cvc|security code)[^\d]*(\d{3,4})\b', text, re.IGNORECASE)
    if m:
        return m.group(1)
    # Standalone 3-4 digit number
    m = re.search(r'(?<!\d)(\d{3,4})(?!\d)', text)
    return m.group(1) if m else None


def extract_expiry(text: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Extract expiry month and year.
    Supports: MM/YYYY, MM/YY, MM-YYYY, MM-YY, 'expires MM YYYY'
    Returns (month, year) with 4-digit year, or (None, None).
    """
    # MM/YYYY or MM-YYYY
    m = re.search(r'\b(0?[1-9]|1[0-2])[/-](\d{4})\b', text)
    if m:
        return int(m.group(1)), int(m.group(2))
    # MM/YY or MM-YY
    m = re.search(r'\b(0?[1-9]|1[0-2])[/-](\d{2})\b', text)
    if m:
        year = 2000 + int(m.group(2))
        return int(m.group(1)), year
    # "expires in March 2027" — not required but nice to have
    month_names = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12,
    }
    m = re.search(
        r'(%s)\s+(\d{4})' % '|'.join(month_names.keys()),
        text, re.IGNORECASE
    )
    if m:
        return month_names[m.group(1).lower()], int(m.group(2))
    return None, None


def validate_expiry(month: int, year: int) -> Tuple[bool, Optional[str]]:
    """Check that expiry is in the future."""
    today = date.today()
    # Card is valid through the last day of the expiry month
    if year < today.year or (year == today.year and month < today.month):
        return False, f"The card expired on {month:02d}/{year}. Please use a valid card."
    if month < 1 or month > 12:
        return False, "Invalid expiry month. Please enter MM/YYYY."
    return True, None


def extract_cardholder_name(text: str) -> Optional[str]:
    """Extract cardholder name — prioritise labeled formats."""
    patterns = [
        r"(?:cardholder(?:'s)?\s*(?:name)?|name\s+on\s+card)[:\s]+([A-Za-z][\w\s'-]+?)(?:\s*[,\n]|$)",
        r"(?:my name is|i am|name:?)\s+([A-Za-z][\w\s'-]+?)(?:\s*[,\n]|$)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip().rstrip(',')

    # Bare name only if the whole input looks like a name (no other content)
    bare = text.strip()
    if re.fullmatch(r"[A-Za-z][\w'-]+(?:\s+[A-Za-z][\w'-]+){1,3}", bare):
        return bare
    return None
