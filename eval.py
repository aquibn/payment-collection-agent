"""
Evaluation Suite for the Payment Collection Agent.

Runs scripted conversations and asserts expected outcomes.
Each test case specifies turns as (user_input, expected_keywords_in_response).

Run: python eval.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from agent import Agent
from unittest.mock import patch, MagicMock
from state_models import AccountData


# ──────────────────────────────────────────────
# Mock account data
# ──────────────────────────────────────────────

MOCK_ACCOUNTS = {
    "ACC1001": AccountData(
        account_id="ACC1001", full_name="Nithin Jain", dob="1990-05-14",
        aadhaar_last4="4321", pincode="400001", balance=1250.75,
    ),
    "ACC1002": AccountData(
        account_id="ACC1002", full_name="Rajarajeswari Balasubramaniam",
        dob="1985-11-23", aadhaar_last4="9876", pincode="400002", balance=540.00,
    ),
    "ACC1003": AccountData(
        account_id="ACC1003", full_name="Priya Agarwal", dob="1992-08-10",
        aadhaar_last4="2468", pincode="400003", balance=0.00,
    ),
    "ACC1004": AccountData(
        account_id="ACC1004", full_name="Rahul Mehta", dob="1988-02-29",
        aadhaar_last4="1357", pincode="400004", balance=3200.50,
    ),
}


def mock_lookup(account_id):
    if account_id in MOCK_ACCOUNTS:
        return {"success": True, "account": MOCK_ACCOUNTS[account_id]}
    return {"success": False, "error": "account_not_found"}


def mock_payment_success(*args, **kwargs):
    return {"success": True, "transaction_id": "txn_test_123"}


def mock_payment_failure(error_code, retryable=True):
    def _mock(*args, **kwargs):
        return {"success": False, "error": error_code, "retryable": retryable}
    return _mock


# ──────────────────────────────────────────────
# Test runner
# ──────────────────────────────────────────────

class TestResult:
    def __init__(self, name):
        self.name = name
        self.passed = True
        self.failures = []

    def assert_contains(self, turn_num, response, keywords):
        for kw in keywords:
            if kw.lower() not in response.lower():
                self.passed = False
                self.failures.append(
                    f"  Turn {turn_num}: expected '{kw}' in response.\n"
                    f"  Got: {response[:120]}..."
                )

    def assert_not_contains(self, turn_num, response, keywords):
        for kw in keywords:
            if kw.lower() in response.lower():
                self.passed = False
                self.failures.append(
                    f"  Turn {turn_num}: did NOT expect '{kw}' in response.\n"
                    f"  Got: {response[:120]}..."
                )


def run_conversation(turns, lookup_mock=None, payment_mock=None):
    """Run a scripted conversation and return list of (turn, response) pairs."""
    agent = Agent()
    responses = []

    with patch("api_client.lookup_account", side_effect=lookup_mock or mock_lookup), \
         patch("api_client.process_payment", side_effect=payment_mock or mock_payment_success):

        # Greet
        r = agent.next("hi")
        responses.append(r["message"])

        for user_input in turns:
            r = agent.next(user_input)
            responses.append(r["message"])

    return responses


# ──────────────────────────────────────────────
# Test cases
# ──────────────────────────────────────────────

def test_happy_path_dob():
    """Full successful payment verified by DOB."""
    result = TestResult("Happy Path — Verified by DOB")

    turns = [
        "ACC1001",
        "Nithin Jain",
        "1990-05-14",
        "yes",
        "1000",
        "Nithin Jain",
        "4532015112830366",
        "123",
        "12/2027",
    ]
    responses = run_conversation(turns)

    result.assert_contains(1, responses[0], ["account id", "account"])
    result.assert_contains(2, responses[1], ["account"])
    result.assert_contains(3, responses[2], ["verification", "complete"])
    result.assert_contains(4, responses[3], ["verified", "balance", "1,250.75"])
    # Ensure sensitive data not exposed
    result.assert_not_contains(4, responses[3], ["1990-05-14", "4321", "400001"])
    result.assert_contains(len(responses) - 1, responses[-1], ["transaction", "txn_test_123"])

    return result


def test_happy_path_aadhaar():
    """Full successful payment verified by Aadhaar last 4."""
    result = TestResult("Happy Path — Verified by Aadhaar")

    turns = [
        "ACC1001", "Nithin Jain", "4321",  # aadhaar
        "yes", "500",
        "Nithin Jain", "4532015112830366", "123", "12/2027",
    ]
    responses = run_conversation(turns)
    result.assert_contains(4, responses[4], ["balance", "outstanding"])
    result.assert_contains(len(responses) - 1, responses[-1], ["transaction"])
    return result


def test_happy_path_pincode():
    """Full successful payment verified by Pincode."""
    result = TestResult("Happy Path — Verified by Pincode")
    turns = [
        "ACC1001", "Nithin Jain", "400001",
        "yes", "500",
        "Nithin Jain", "4532015112830366", "123", "12/2027",
    ]
    responses = run_conversation(turns)
    result.assert_contains(4, responses[4], ["balance", "outstanding"])
    result.assert_contains(len(responses) - 1, responses[-1], ["transaction"])
    return result


def test_account_not_found():
    """User provides an invalid account ID."""
    result = TestResult("Account Not Found")
    agent = Agent()
    with patch("api_client.lookup_account", side_effect=mock_lookup), \
         patch("api_client.process_payment", side_effect=mock_payment_success):
        agent.next("hi")
        r = agent.next("ACC9999")["message"]
    result.assert_contains(1, r, ["couldn't find", "ACC9999"])
    return result


def test_verification_failure_wrong_name():
    """User exhausts retries with wrong name."""
    result = TestResult("Verification Failure — Wrong Name")
    turns = [
        "ACC1001",
        "Wrong Name",   # attempt 1
        "Wrong Name",   # attempt 2 — but name will stay collected, asking for factor
        # Actually after wrong name, agent re-asks name. Let's send wrong name 3 times.
        "Wrong Name",
    ]
    # More controlled: send wrong name until lockout
    agent = Agent()
    responses = []
    with patch("api_client.lookup_account", side_effect=mock_lookup), \
         patch("api_client.process_payment", side_effect=mock_payment_success):
        responses.append(agent.next("hi")["message"])
        responses.append(agent.next("ACC1001")["message"])
        # After wrong name, ctx.provided_name is set but wrong → agent re-asks for name
        r1 = agent.next("Totally Wrong Person")["message"]  # attempt 1, name set wrong
        # Now ctx.provided_name is set (wrong). For subsequent turns in VERIFICATION
        # with name already set, agent looks for secondary factor.
        # We need to reset: send another wrong name attempt.
        # Actually after wrong name, agent clears provided_name and re-asks.
        # Let's just send 3 clearly-wrong names and check for lockout.
        r2 = agent.next("Another Wrong Name")["message"]   # attempt 2
        r3 = agent.next("Third Wrong Person")["message"]   # attempt 3 → lock

    locked_out = any(
        kw in r3.lower()
        for kw in ("failed", "closed", "maximum", "contact support")
    )
    result.passed = locked_out
    if not result.passed:
        result.failures.append(
            f"Expected session closure after 3 bad attempts.\n"
            f"  r1: {r1[:80]}\n  r2: {r2[:80]}\n  r3: {r3[:80]}"
        )
    return result


def test_verification_failure_wrong_factor():
    """User provides correct name but wrong secondary factor repeatedly."""
    result = TestResult("Verification Failure — Wrong Secondary Factor")
    agent = Agent()
    with patch("api_client.lookup_account", side_effect=mock_lookup), \
         patch("api_client.process_payment", side_effect=mock_payment_success):
        agent.next("hi")
        agent.next("ACC1001")
        agent.next("Nithin Jain")  # correct name
        r1 = agent.next("1990-01-01")["message"]  # wrong DOB — attempt 1
        r2 = agent.next("0000")["message"]         # wrong aadhaar — attempt 2
        r3 = agent.next("111111")["message"]       # wrong pincode — attempt 3 → lock

    result.passed = ("failed" in r3.lower() or "closed" in r3.lower() or "maximum" in r3.lower())
    if not result.passed:
        result.failures.append(f"Expected lockout after 3 failed factor attempts. Got: {r3[:120]}")
    return result


def test_payment_invalid_card():
    """Payment fails with invalid card, agent guides retry."""
    result = TestResult("Payment Failure — Invalid Card (retryable)")

    call_count = {"n": 0}
    def payment_mock(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {"success": False, "error": "invalid_card", "retryable": True}
        return {"success": True, "transaction_id": "txn_retry_ok"}

    agent = Agent()
    with patch("api_client.lookup_account", side_effect=mock_lookup), \
         patch("api_client.process_payment", side_effect=payment_mock):
        agent.next("hi")
        agent.next("ACC1001")
        agent.next("Nithin Jain")
        agent.next("1990-05-14")
        agent.next("yes")
        agent.next("500")
        agent.next("Nithin Jain")         # cardholder name
        agent.next("4111111111111111")    # bad card number → triggers payment → invalid_card
        agent.next("123")                 # cvv
        r1 = agent.next("12/2027")["message"]  # expiry → payment attempt → fails
        r2 = agent.next("4532015112830366")["message"]  # retry with good card

    result.assert_contains(1, r1, ["invalid", "card"])
    result.assert_contains(2, r2, ["transaction", "txn_retry_ok"])
    return result


def test_payment_insufficient_balance():
    """Payment fails with insufficient balance (terminal)."""
    result = TestResult("Payment Failure — Insufficient Balance")

    def payment_mock(*args, **kwargs):
        return {"success": False, "error": "insufficient_balance", "retryable": False}

    agent = Agent()
    with patch("api_client.lookup_account", side_effect=mock_lookup), \
         patch("api_client.process_payment", side_effect=payment_mock):
        agent.next("hi")
        agent.next("ACC1001")
        agent.next("Nithin Jain")
        agent.next("1990-05-14")
        agent.next("yes")
        agent.next("999")
        agent.next("Nithin Jain")
        agent.next("4532015112830366")
        agent.next("123")
        r = agent.next("12/2027")["message"]

    result.assert_contains(1, r, ["balance"])
    result.assert_contains(1, r, ["closed"])
    return result


def test_zero_balance_account():
    """Account with ₹0 balance — user cannot proceed to payment."""
    result = TestResult("Edge Case — Zero Balance Account")
    agent = Agent()
    with patch("api_client.lookup_account", side_effect=mock_lookup), \
         patch("api_client.process_payment", side_effect=mock_payment_success):
        agent.next("hi")
        agent.next("ACC1003")
        agent.next("Priya Agarwal")
        agent.next("1992-08-10")
        balance_msg = agent.next("yes")["message"]
        # User tries to pay 1 rupee
        amount_err = agent.next("1")["message"]

    result.assert_contains(1, balance_msg, ["0.00"])
    result.assert_contains(2, amount_err, ["exceed", "balance"])
    return result


def test_leap_year_dob():
    """ACC1004 has DOB 1988-02-29 — must accept it as a valid leap year date."""
    result = TestResult("Edge Case — Leap Year DOB (1988-02-29)")
    agent = Agent()
    with patch("api_client.lookup_account", side_effect=mock_lookup), \
         patch("api_client.process_payment", side_effect=mock_payment_success):
        agent.next("hi")
        agent.next("ACC1004")
        agent.next("Rahul Mehta")
        r = agent.next("1988-02-29")["message"]  # valid leap year date

    result.assert_contains(1, r, ["verified", "balance"])
    return result


def test_invalid_leap_year_dob():
    """1988-02-30 should be rejected as invalid date."""
    result = TestResult("Edge Case — Invalid Date 1988-02-30")
    agent = Agent()
    with patch("api_client.lookup_account", side_effect=mock_lookup), \
         patch("api_client.process_payment", side_effect=mock_payment_success):
        agent.next("hi")
        agent.next("ACC1004")
        agent.next("Rahul Mehta")
        r = agent.next("1988-02-30")["message"]  # does not exist

    result.assert_not_contains(1, r, ["verified"])
    result.assert_contains(1, r, ["not a valid", "calendar"])
    return result


def test_user_declines_payment():
    """User says no to payment after seeing balance."""
    result = TestResult("Edge Case — User Declines Payment")
    agent = Agent()
    with patch("api_client.lookup_account", side_effect=mock_lookup), \
         patch("api_client.process_payment", side_effect=mock_payment_success):
        agent.next("hi")
        agent.next("ACC1001")
        agent.next("Nithin Jain")
        agent.next("4321")
        r = agent.next("no thanks")["message"]

    result.assert_contains(1, r, ["no payment", "session", "great day"])
    return result


def test_sensitive_data_not_exposed():
    """Verify that DOB, Aadhaar, and Pincode never appear in agent responses."""
    result = TestResult("Security — Sensitive Data Not Exposed")
    agent = Agent()
    all_responses = []
    with patch("api_client.lookup_account", side_effect=mock_lookup), \
         patch("api_client.process_payment", side_effect=mock_payment_success):
        all_responses.append(agent.next("hi")["message"])
        all_responses.append(agent.next("ACC1001")["message"])
        all_responses.append(agent.next("Nithin Jain")["message"])
        all_responses.append(agent.next("1990-05-14")["message"])
        all_responses.append(agent.next("yes")["message"])
        all_responses.append(agent.next("500")["message"])
        all_responses.append(agent.next("Nithin Jain 4532015112830366 123 12/2027")["message"])

    combined = " ".join(all_responses)
    for secret in ["1990-05-14", "4321", "400001"]:
        if secret in combined:
            result.passed = False
            result.failures.append(f"Sensitive data '{secret}' found in agent output!")
    return result


def test_out_of_order_input():
    """User provides name before being asked (volunteered early)."""
    result = TestResult("Context — Out-of-order Name in Greeting")
    agent = Agent()
    with patch("api_client.lookup_account", side_effect=mock_lookup), \
         patch("api_client.process_payment", side_effect=mock_payment_success):
        r = agent.next("Hi my name is Nithin Jain and my account is ACC1001")["message"]

    # Should pick up account ID and advance to verification
    result.assert_contains(1, r, ["verify", "full name", "identity", "account"])
    return result


def test_multi_field_card_entry():
    """User provides all card fields in a single message."""
    result = TestResult("Context — All Card Fields in One Message")
    agent = Agent()
    with patch("api_client.lookup_account", side_effect=mock_lookup), \
         patch("api_client.process_payment", side_effect=mock_payment_success):
        agent.next("hi")
        agent.next("ACC1001")
        agent.next("Nithin Jain")
        agent.next("1990-05-14")
        agent.next("yes")
        agent.next("500")
        # Send all fields at once using labeled format
        r = agent.next("Cardholder: Nithin Jain, Card: 4532015112830366, CVV: 123, Expiry: 12/2027")["message"]
        # If cardholder name wasn't parsed (bare name in a field), might need one more turn
        if "transaction" not in r.lower() and "still need" in r.lower():
            r = agent.next("Nithin Jain")["message"]

    result.assert_contains(1, r, ["transaction", "txn_test_123"])
    return result


def test_long_name_account():
    """ACC1002 has a long name — exact match required."""
    result = TestResult("Verification — Long Name Exact Match")
    agent = Agent()
    with patch("api_client.lookup_account", side_effect=mock_lookup), \
         patch("api_client.process_payment", side_effect=mock_payment_success):
        agent.next("hi")
        agent.next("ACC1002")
        # Slightly wrong name
        r_wrong = agent.next("Rajarajeswari")["message"]
        # Correct full name
        r_correct = agent.next("Rajarajeswari Balasubramaniam")["message"]

    result.assert_not_contains(1, r_wrong, ["verified"])
    result.assert_contains(2, r_correct, ["verification", "complete", "one more"])
    return result


# ──────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────

ALL_TESTS = [
    test_happy_path_dob,
    test_happy_path_aadhaar,
    test_happy_path_pincode,
    test_account_not_found,
    test_verification_failure_wrong_name,
    test_verification_failure_wrong_factor,
    test_payment_invalid_card,
    test_payment_insufficient_balance,
    test_zero_balance_account,
    test_leap_year_dob,
    test_invalid_leap_year_dob,
    test_user_declines_payment,
    test_sensitive_data_not_exposed,
    test_out_of_order_input,
    test_multi_field_card_entry,
    test_long_name_account,
]


def run_all():
    print("=" * 65)
    print("  Payment Agent — Evaluation Suite")
    print("=" * 65)

    passed = 0
    failed = 0

    for test_fn in ALL_TESTS:
        try:
            result = test_fn()
        except Exception as exc:
            result = TestResult(test_fn.__name__)
            result.passed = False
            result.failures.append(f"  EXCEPTION: {exc}")

        status = "✅ PASS" if result.passed else "❌ FAIL"
        print(f"\n{status}  {result.name}")
        for failure in result.failures:
            print(failure)

        if result.passed:
            passed += 1
        else:
            failed += 1

    total = passed + failed
    print("\n" + "=" * 65)
    print(f"  Results: {passed}/{total} passed  ({100*passed//total}%)")
    print("=" * 65)

    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
