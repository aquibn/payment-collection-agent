"""
State definitions, enums, and data models for the Payment Collection Agent.
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Optional


class ConversationState(Enum):
    """Ordered states in the payment collection flow."""
    GREETING = auto()
    ACCOUNT_LOOKUP = auto()
    VERIFICATION = auto()
    BALANCE_PRESENTATION = auto()
    PAYMENT_AMOUNT = auto()
    CARD_COLLECTION = auto()
    PAYMENT_PROCESSING = auto()
    CLOSED = auto()


@dataclass
class AccountData:
    """Holds account information fetched from the lookup API."""
    account_id: str
    full_name: str
    dob: str                  # YYYY-MM-DD — NEVER expose to user
    aadhaar_last4: str        # 4-digit string — NEVER expose to user
    pincode: str              # 6-digit string — NEVER expose to user
    balance: float


@dataclass
class CardData:
    """Accumulates card fields across multiple turns."""
    cardholder_name: Optional[str] = None
    card_number: Optional[str] = None
    cvv: Optional[str] = None
    expiry_month: Optional[int] = None
    expiry_year: Optional[int] = None

    def missing_fields(self) -> list[str]:
        missing = []
        if not self.cardholder_name:
            missing.append("cardholder name")
        if not self.card_number:
            missing.append("card number (16 digits)")
        if not self.cvv:
            missing.append("CVV")
        if not self.expiry_month or not self.expiry_year:
            missing.append("expiry date (MM/YYYY)")
        return missing

    def is_complete(self) -> bool:
        return not self.missing_fields()


@dataclass
class ConversationContext:
    """All mutable state for one conversation session."""
    state: ConversationState = ConversationState.GREETING
    account_id: Optional[str] = None
    account_data: Optional[AccountData] = None

    # Verification tracking
    provided_name: Optional[str] = None
    verification_attempts: int = 0
    MAX_VERIFICATION_ATTEMPTS: int = field(default=3, init=False, repr=False)

    # Payment tracking
    payment_amount: Optional[float] = None
    card: CardData = field(default_factory=CardData)

    # Result
    transaction_id: Optional[str] = None
