# Payment Collection AI Agent

A production-ready, rule-based conversational AI agent that handles end-to-end payment collection — account lookup, identity verification, and card payment processing.

---

## Project Structure

```
payment_agent/
├── agent.py              # Public interface — Agent class with next()
├── conversation_manager.py  # State machine — all conversation logic
├── state_models.py       # Data classes: ConversationContext, AccountData, CardData
├── api_client.py         # HTTP calls to lookup-account and process-payment APIs
├── input_parser.py       # All regex-based extraction and validation helpers
├── cli.py                # Interactive CLI for manual testing
├── eval.py               # Automated evaluation suite (16 test cases)
└── requirements.txt
```

---

## Setup

```bash
pip install -r requirements.txt
```

No API keys required — the test API is public.

---

## Run Interactively

```bash
python cli.py
```

---

## Run Evaluation Suite

```bash
python eval.py
```

---

## Usage (Programmatic)

```python
from agent import Agent

agent = Agent()
print(agent.next("hi"))
# → {"message": "Hello! Welcome to the Payment Collection Service..."}

print(agent.next("ACC1001"))
# → {"message": "I found the account ACC1001. For security, I need to verify..."}
```

---

## Sample Conversations

### 1. Successful End-to-End Payment

```
You:   hi
Agent: Hello! Welcome to the Payment Collection Service...

You:   ACC1001
Agent: I found account ACC1001. Could you please provide your full name?

You:   Nithin Jain
Agent: Thank you. To complete verification, please provide one of:
       • Date of birth (YYYY-MM-DD)
       • Last 4 digits of Aadhaar
       • Registered Pincode

You:   1990-05-14
Agent: ✅ Identity verified. Your outstanding balance is ₹1,250.75.
       Would you like to make a payment?

You:   yes
Agent: How much would you like to pay? (up to ₹1,250.75)

You:   500
Agent: I'll process ₹500.00. Please provide your card details...

You:   Nithin Jain
Agent: I still need: card number, CVV, expiry date.

You:   4532015112830366
Agent: I still need: CVV, expiry date.

You:   123
Agent: I still need: expiry date (MM/YYYY).

You:   12/2027
Agent: ✅ Payment Successful!
       Amount paid: ₹500.00
       Transaction ID: txn_1762510325322_l1fl4oy
```

---

### 2. Verification Failure — Retries Exhausted

```
You:   ACC1001
Agent: Found account. Please provide your full name.

You:   John Smith        ← wrong name, attempt 1
Agent: Name does not match. 2 attempt(s) remaining.

You:   Jane Doe          ← wrong name, attempt 2
Agent: Name does not match. 1 attempt(s) remaining.

You:   Nobody Here       ← wrong name, attempt 3
Agent: ❌ Identity verification failed after the maximum number of attempts.
       This session has been closed.
```

---

### 3. Payment Failure — Invalid Card (Retryable)

```
[After successful verification and amount entry]

You:   4111111111111111   ← fails Luhn check
Agent: ❌ The card number appears to be invalid. Please re-enter your 16-digit card number.

You:   4532015112830366   ← valid card
Agent: ✅ Payment Successful! Transaction ID: txn_...
```

---

### 4. Edge Case — Leap Year DOB (ACC1004)

```
You:   ACC1004
Agent: Found account. Please provide your full name.

You:   Rahul Mehta
Agent: Thank you. Please provide a verification factor.

You:   1988-02-29         ← valid leap year date
Agent: ✅ Identity verified. Balance: ₹3,200.50

You:   1988-02-30         ← does NOT exist
Agent: 1988-02-30 is not a valid calendar date. Please re-enter...
```

---

## Design Document

### Architecture Overview

The agent uses a **deterministic finite state machine** implemented entirely in Python. No LLM is used for routing or decision-making — this is intentional (see Key Decisions).

```
GREETING → ACCOUNT_LOOKUP → VERIFICATION → BALANCE_PRESENTATION
         → PAYMENT_AMOUNT → CARD_COLLECTION → PAYMENT_PROCESSING → CLOSED
```

Each module has a single responsibility:

| Module | Role |
|--------|------|
| `agent.py` | Public interface only — no logic |
| `conversation_manager.py` | State machine, transitions, response generation |
| `state_models.py` | Pure data structures — no behaviour |
| `api_client.py` | HTTP, JSON, error classification — no conversation |
| `input_parser.py` | Regex extraction/validation — no side effects |

All conversation state is held in a `ConversationContext` dataclass inside `ConversationManager`. Because Python objects persist between calls, the `Agent.next()` interface requirement is satisfied automatically.

---

### Key Decisions

**Rule-based over LLM-driven**

Verification logic and state transitions are deterministic. Using an LLM here would introduce non-determinism and hallucination risk for security-critical decisions (identity verification, payment amounts). Rule-based parsing gives auditability and consistent test results.

**Multi-turn card collection**

Card fields are accumulated across turns in a `CardData` object. This allows users to provide details incrementally or all at once. Each call to `_handle_card_collection()` fills any gaps and only proceeds when complete.

**Strict verification**

Name matching normalises whitespace but preserves case sensitivity exactly per spec. Secondary factors are compared as strings (not parsed further) so "04321" ≠ "4321".

**Retry limit on verification**

The limit is 3 total failed factor attempts (configurable via `MAX_VERIFICATION_ATTEMPTS`). Wrong name increments the counter too, preventing a hybrid brute-force attack on name + factor combinations.

**Sensitive data isolation**

`AccountData` (containing DOB, Aadhaar, Pincode) is stored only in `ConversationContext._account_data`. No field of `AccountData` is ever interpolated into a response string — this is enforced by convention in `conversation_manager.py`.

**Leap year handling**

`input_parser.is_valid_date()` uses `datetime.strptime` which correctly rejects Feb 29 on non-leap years and accepts it on leap years (e.g. 1988). This handles both the valid `1988-02-29` and invalid `1988-02-30` cases.

**Error retryability**

Card errors (invalid number, CVV, expiry) are retryable — only the bad field is cleared. Balance errors and unexpected server errors are terminal and close the session cleanly.

---

### Tradeoffs Accepted

- **No fuzzy matching**: Correct per spec, but means a user with a hyphenated name or trailing space will fail even if genuinely the account holder. A real system would offer an operator escalation path.
- **Regex-based extraction**: Simpler and fully deterministic, but brittle for very unstructured free-text. An NLU layer would improve UX.
- **No persistence**: State lives only in the `Agent` object instance. A production system would store `ConversationContext` in a session store (Redis/DynamoDB).
- **Card data in memory**: Card fields exist in `CardData` only during the active session. A production system would use a PCI-DSS compliant vault.

---

### What I Would Improve with More Time

1. **NLU intent detection** — replace regex extraction with a lightweight NLU model for more natural phrasing support.
2. **Retry limit per field** — separate counters for wrong name vs wrong factor to improve UX fairness.
3. **Operator escalation path** — after max retries, offer to transfer to a human agent instead of hard-closing.
4. **Structured logging** — emit JSON logs per turn with state transitions for observability.
5. **Property-based testing** — use Hypothesis to generate random user inputs and verify state machine invariants.
6. **Async API calls** — replace `requests` with `httpx` (async) for better throughput in multi-user deployments.

---

## Evaluation Approach

The eval suite (`eval.py`) runs 16 scripted test cases with mocked API responses. Each test asserts keyword presence/absence in agent responses.

**Test coverage:**

| Category | Tests |
|----------|-------|
| Happy path (DOB / Aadhaar / Pincode) | 3 |
| Account not found | 1 |
| Verification failure (name / factor exhaustion) | 2 |
| Payment failure (invalid card, insufficient balance) | 2 |
| Edge cases (zero balance, leap year, decline, out-of-order) | 5 |
| Security (no sensitive data in responses) | 1 |
| Context (multi-field card, long name) | 2 |

**Correctness definition per step:**

- Account lookup: correct account found or clear error returned
- Verification: only passes with exact name match + valid factor; locks after 3 fails
- Balance: displayed without any sensitive field
- Payment: succeeds only after complete valid card; retryable errors allow re-entry; terminal errors close cleanly

**Observations (known gaps):**

- Partial name in greeting (e.g. "I'm Nithin") won't match "Nithin Jain" — user must provide full name explicitly
- Very creative card entry formats (spaces within CVV, etc.) may not parse correctly
- The `extract_cardholder_name` heuristic can confuse a plain first-name input with a cardholder name
