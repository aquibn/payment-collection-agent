"""
ConversationManager — the state machine that drives the payment collection flow.

State transitions:
  GREETING → ACCOUNT_LOOKUP → VERIFICATION → BALANCE_PRESENTATION
  → PAYMENT_AMOUNT → CARD_COLLECTION → PAYMENT_PROCESSING → CLOSED

Context is persisted entirely in self._ctx (a ConversationContext instance).
Each call to process_turn() maps to exactly one user turn.
"""

from state_models import ConversationState, ConversationContext, CardData
import api_client as api
import input_parser as parser


class ConversationManager:

    def __init__(self):
        self._ctx = ConversationContext()

    # ──────────────────────────────────────────
    # Public entry point
    # ──────────────────────────────────────────

    def process_turn(self, user_input: str) -> str:
        """Route the user's message to the correct state handler."""
        state = self._ctx.state

        if state == ConversationState.GREETING:
            return self._handle_greeting(user_input)
        elif state == ConversationState.ACCOUNT_LOOKUP:
            return self._handle_account_lookup(user_input)
        elif state == ConversationState.VERIFICATION:
            return self._handle_verification(user_input)
        elif state == ConversationState.BALANCE_PRESENTATION:
            return self._handle_balance_presentation(user_input)
        elif state == ConversationState.PAYMENT_AMOUNT:
            return self._handle_payment_amount(user_input)
        elif state == ConversationState.CARD_COLLECTION:
            return self._handle_card_collection(user_input)
        elif state == ConversationState.PAYMENT_PROCESSING:
            # Shouldn't normally receive input here, but handle gracefully
            return self._handle_payment_processing()
        elif state == ConversationState.CLOSED:
            return (
                "This session has already been closed. "
                "Please start a new conversation if you need further assistance."
            )
        return "Something went wrong. Please start a new conversation."

    # ──────────────────────────────────────────
    # State handlers
    # ──────────────────────────────────────────

    def _handle_greeting(self, user_input: str) -> str:
        """
        GREETING: Emit welcome message and prompt for account ID.
        We immediately transition to ACCOUNT_LOOKUP after greeting so that
        if the user includes their account ID in the first message, we pick it up.
        """
        self._ctx.state = ConversationState.ACCOUNT_LOOKUP

        # Check if account ID was already provided in the greeting message
        account_id = parser.extract_account_id(user_input)
        if account_id:
            return self._do_account_lookup(account_id)

        return (
            "Hello! Welcome to the Payment Collection Service. "
            "I'm here to help you review your outstanding balance and process a payment.\n\n"
            "To get started, could you please share your **Account ID**? "
            "(It looks like ACC1001.)"
        )

    def _handle_account_lookup(self, user_input: str) -> str:
        """ACCOUNT_LOOKUP: Extract account ID and call the API."""
        account_id = parser.extract_account_id(user_input)
        if not account_id:
            return (
                "I couldn't find an account ID in what you shared. "
                "Please provide your Account ID — it should look like ACC1001."
            )
        return self._do_account_lookup(account_id)

    def _do_account_lookup(self, account_id: str) -> str:
        """Perform the account lookup API call and transition state."""
        result = api.lookup_account(account_id)

        if not result["success"]:
            if result["error"] == "account_not_found":
                return (
                    f"I couldn't find any account with the ID **{account_id}**. "
                    "Please double-check and try again with the correct Account ID."
                )
            # Network/unexpected error
            return (
                "I'm having trouble connecting to the account service right now. "
                "Please try again in a moment."
            )

        self._ctx.account_id = account_id
        self._ctx.account_data = result["account"]
        self._ctx.state = ConversationState.VERIFICATION

        return (
            f"I found the account **{account_id}**. "
            "For security, I need to verify your identity before proceeding.\n\n"
            "Could you please provide your **full name** as registered on the account?"
        )

    def _handle_verification(self, user_input: str) -> str:
        """
        VERIFICATION: Collect name + one secondary factor.
        State stays in VERIFICATION until verified or retries exhausted.
        """
        ctx = self._ctx
        account = ctx.account_data

        # ── Try to extract name if not yet collected ──
        if ctx.provided_name is None:
            name = parser.extract_name(user_input)
            if name:
                # Check if name fails — count as attempt and reset so user can retry
                if not parser.names_match(name, account.full_name):
                    ctx.verification_attempts += 1
                    # Keep provided_name as None so agent re-asks for name
                    remaining = ctx.MAX_VERIFICATION_ATTEMPTS - ctx.verification_attempts
                    if remaining <= 0:
                        return self._verification_failed()
                    return (
                        "The name you provided does not match our records. "
                        f"You have {remaining} attempt(s) remaining.\n\n"
                        "Please re-enter your **full name** exactly as registered."
                    )
                # Name matched — store and ask for secondary factor
                ctx.provided_name = name
                return (
                    "Thank you. To complete verification, I need one more piece of information.\n\n"
                    "Please provide **one** of the following:\n"
                    "• Date of birth (YYYY-MM-DD)\n"
                    "• Last 4 digits of your Aadhaar\n"
                    "• Your registered Pincode"
                )
            else:
                return (
                    "I need your **full name** to proceed with identity verification. "
                    "Please enter your full name as registered on the account."
                )

        # ── Name is collected; now check secondary factor ──
        # Name check (in case user re-entered it with something else mixed in)
        # Attempt to parse a secondary factor from the message
        verified = False
        factor_provided = False

        # DOB check
        dob_str = parser.extract_dob(user_input)
        if dob_str:
            factor_provided = True
            if not parser.is_valid_date(dob_str):
                ctx.verification_attempts += 1
                remaining = ctx.MAX_VERIFICATION_ATTEMPTS - ctx.verification_attempts
                if remaining <= 0:
                    return self._verification_failed()
                return (
                    f"**{dob_str}** is not a valid calendar date. "
                    "Please check and re-enter your date of birth in YYYY-MM-DD format, "
                    f"or provide your Aadhaar last 4 or Pincode. "
                    f"({remaining} attempt(s) remaining.)"
                )
            if dob_str == account.dob:
                verified = True

        # Aadhaar check
        if not factor_provided:
            aadhaar = parser.extract_aadhaar_last4(user_input)
            if aadhaar:
                factor_provided = True
                if aadhaar == account.aadhaar_last4:
                    verified = True

        # Pincode check
        if not factor_provided:
            pincode = parser.extract_pincode(user_input)
            if pincode:
                factor_provided = True
                if pincode == account.pincode:
                    verified = True

        if not factor_provided:
            return (
                "I couldn't identify a verification factor in your message. "
                "Please provide **one** of:\n"
                "• Date of birth (YYYY-MM-DD)\n"
                "• Last 4 digits of your Aadhaar\n"
                "• Your registered Pincode"
            )

        if verified:
            return self._verification_succeeded()
        else:
            ctx.verification_attempts += 1
            remaining = ctx.MAX_VERIFICATION_ATTEMPTS - ctx.verification_attempts
            if remaining <= 0:
                return self._verification_failed()
            return (
                "The information you provided does not match our records. "
                f"You have {remaining} attempt(s) remaining.\n\n"
                "Please try a different verification factor:\n"
                "• Date of birth (YYYY-MM-DD)\n"
                "• Last 4 digits of your Aadhaar\n"
                "• Your registered Pincode"
            )

    def _verification_succeeded(self) -> str:
        account = self._ctx.account_data
        self._ctx.state = ConversationState.BALANCE_PRESENTATION
        balance = account.balance
        return (
            "✅ Identity verified successfully.\n\n"
            f"Your outstanding balance is **₹{balance:,.2f}**.\n\n"
            "Would you like to make a payment now? If so, please confirm and I'll guide you through it."
        )

    def _verification_failed(self) -> str:
        self._ctx.state = ConversationState.CLOSED
        return (
            "❌ Identity verification failed after the maximum number of attempts. "
            "For your security, this session has been closed.\n\n"
            "If you believe this is an error, please contact our support team directly."
        )

    def _handle_balance_presentation(self, user_input: str) -> str:
        """BALANCE_PRESENTATION: User confirms they want to pay → move to amount collection."""
        lower = user_input.lower()
        negative_words = {"no", "nope", "not", "don't", "dont", "cancel", "exit", "quit", "stop"}
        if any(w in lower for w in negative_words):
            self._ctx.state = ConversationState.CLOSED
            return (
                "Understood. No payment has been made today. "
                "If you'd like to make a payment in the future, please start a new session. "
                "Have a great day! 👋"
            )
        # Treat any affirmative or non-negative response as a yes
        self._ctx.state = ConversationState.PAYMENT_AMOUNT
        balance = self._ctx.account_data.balance
        return (
            f"Great! Your outstanding balance is **₹{balance:,.2f}**.\n\n"
            "How much would you like to pay? "
            "You can pay the full amount or a partial amount (minimum ₹1.00)."
        )

    def _handle_payment_amount(self, user_input: str) -> str:
        """PAYMENT_AMOUNT: Parse and validate payment amount."""
        balance = self._ctx.account_data.balance
        amount, error = parser.extract_amount(user_input, balance)
        if error:
            return error
        self._ctx.payment_amount = amount
        self._ctx.state = ConversationState.CARD_COLLECTION
        return (
            f"I'll process a payment of **₹{amount:,.2f}**.\n\n"
            "Please provide your card details. You can share them all at once or one by one:\n"
            "• **Cardholder name** (as on the card)\n"
            "• **Card number** (16 digits)\n"
            "• **CVV** (3 or 4 digits)\n"
            "• **Expiry date** (MM/YYYY)\n\n"
            "_Your card details are used only to process this payment and are not stored._"
        )

    def _handle_card_collection(self, user_input: str) -> str:
        """
        CARD_COLLECTION: Accumulate card fields across one or more turns.
        Attempt to parse all fields from the current message and fill gaps.
        """
        card = self._ctx.card

        # Try to fill any missing fields from this message
        if not card.cardholder_name:
            name = parser.extract_cardholder_name(user_input)
            if name:
                card.cardholder_name = name

        if not card.card_number:
            num = parser.extract_card_number(user_input)
            if num:
                card.card_number = num

        if not card.cvv:
            cvv = parser.extract_cvv(user_input)
            if cvv:
                card.cvv = cvv

        if not card.expiry_month or not card.expiry_year:
            month, year = parser.extract_expiry(user_input)
            if month and year:
                valid, err = parser.validate_expiry(month, year)
                if not valid:
                    return err  # Stay in CARD_COLLECTION so user can re-enter
                card.expiry_month = month
                card.expiry_year = year

        # Check what's still missing
        missing = card.missing_fields()
        if missing:
            missing_str = "\n• ".join(missing)
            return (
                f"I still need the following to proceed:\n• {missing_str}\n\n"
                "Please provide the missing information."
            )

        # All fields collected — process payment
        self._ctx.state = ConversationState.PAYMENT_PROCESSING
        return self._handle_payment_processing()

    def _handle_payment_processing(self) -> str:
        """PAYMENT_PROCESSING: Call the payment API and respond."""
        ctx = self._ctx
        card = ctx.card

        result = api.process_payment(
            account_id=ctx.account_id,
            amount=ctx.payment_amount,
            cardholder_name=card.cardholder_name,
            card_number=card.card_number,
            cvv=card.cvv,
            expiry_month=card.expiry_month,
            expiry_year=card.expiry_year,
        )

        if result["success"]:
            ctx.transaction_id = result["transaction_id"]
            ctx.state = ConversationState.CLOSED
            return self._payment_success_message()

        error_code = result.get("error", "unknown_error")
        retryable = result.get("retryable", False)
        error_msg = api.payment_error_message(error_code)

        if retryable:
            # Reset specific card fields so the user can re-enter them
            if error_code in ("invalid_card",):
                card.card_number = None
            elif error_code == "invalid_cvv":
                card.cvv = None
            elif error_code == "invalid_expiry":
                card.expiry_month = None
                card.expiry_year = None
            elif error_code == "invalid_amount":
                ctx.payment_amount = None
                ctx.state = ConversationState.PAYMENT_AMOUNT
                return f"❌ {error_msg}"
            # Stay in CARD_COLLECTION for card errors
            ctx.state = ConversationState.CARD_COLLECTION
            return f"❌ {error_msg}"

        # Terminal error
        ctx.state = ConversationState.CLOSED
        return (
            f"❌ Payment could not be completed: {error_msg}\n\n"
            "This session has been closed. Please contact our support team for assistance."
        )

    def _payment_success_message(self) -> str:
        ctx = self._ctx
        return (
            f"✅ **Payment Successful!**\n\n"
            f"**Amount paid:** ₹{ctx.payment_amount:,.2f}\n"
            f"**Transaction ID:** `{ctx.transaction_id}`\n\n"
            "Please save your Transaction ID for your records. "
            "A confirmation will be sent via your registered contact details.\n\n"
            "Thank you for using our Payment Service. Have a great day! 👋"
        )
