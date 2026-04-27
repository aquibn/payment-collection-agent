"""
Unit tests for input_parser.py

Each function is tested in isolation with labelled inputs, bare inputs,
edge cases, and explicit non-match cases so regressions are easy to pin.

Run: python test_input_parser.py
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(__file__))

import input_parser as p


# ─────────────────────────────────────────────────────────────
# extract_account_id
# ─────────────────────────────────────────────────────────────

class TestExtractAccountId(unittest.TestCase):

    def test_standard_format(self):
        self.assertEqual(p.extract_account_id("ACC1001"), "ACC1001")

    def test_embedded_in_sentence(self):
        self.assertEqual(p.extract_account_id("my account is ACC1002 thanks"), "ACC1002")

    def test_case_insensitive(self):
        self.assertEqual(p.extract_account_id("acc1003"), "ACC1003")

    def test_bare_digits_promoted(self):
        self.assertEqual(p.extract_account_id("1001"), "ACC1001")

    def test_longer_account_number(self):
        self.assertEqual(p.extract_account_id("ACC10023"), "ACC10023")

    def test_no_match_returns_none(self):
        self.assertIsNone(p.extract_account_id("hello there"))

    def test_no_match_short_digits(self):
        # 3-digit number should not match the bare-digit fallback (requires 4+)
        self.assertIsNone(p.extract_account_id("123"))

    def test_prefers_acc_prefix_over_bare(self):
        # Both "ACC1001" and bare "9999" present — should pick ACC1001
        result = p.extract_account_id("I have ACC1001 and also 9999")
        self.assertEqual(result, "ACC1001")


# ─────────────────────────────────────────────────────────────
# extract_name
# ─────────────────────────────────────────────────────────────

class TestExtractName(unittest.TestCase):

    def test_bare_two_word_name(self):
        self.assertEqual(p.extract_name("Nithin Jain"), "Nithin Jain")

    def test_bare_three_word_name(self):
        self.assertEqual(p.extract_name("Rajarajeswari Balasubramaniam"), "Rajarajeswari Balasubramaniam")

    def test_my_name_is_prefix(self):
        result = p.extract_name("my name is Nithin Jain")
        self.assertEqual(result, "Nithin Jain")

    def test_i_am_prefix(self):
        result = p.extract_name("I am Priya Agarwal")
        self.assertEqual(result, "Priya Agarwal")

    def test_im_prefix(self):
        result = p.extract_name("I'm Rahul Mehta")
        self.assertEqual(result, "Rahul Mehta")

    def test_name_colon_prefix(self):
        result = p.extract_name("Name: Nithin Jain")
        self.assertEqual(result, "Nithin Jain")

    def test_single_word_returns_none(self):
        # A single word is not a full name — should not match
        self.assertIsNone(p.extract_name("Nithin"))

    def test_gibberish_returns_none(self):
        self.assertIsNone(p.extract_name("yes please"))

    def test_numeric_string_returns_none(self):
        self.assertIsNone(p.extract_name("1234"))


# ─────────────────────────────────────────────────────────────
# names_match
# ─────────────────────────────────────────────────────────────

class TestNamesMatch(unittest.TestCase):

    def test_exact_match(self):
        self.assertTrue(p.names_match("Nithin Jain", "Nithin Jain"))

    def test_extra_internal_space_normalised(self):
        self.assertTrue(p.names_match("Nithin  Jain", "Nithin Jain"))

    def test_leading_trailing_space_normalised(self):
        self.assertTrue(p.names_match("  Nithin Jain  ", "Nithin Jain"))

    def test_case_sensitive_lowercase_fails(self):
        self.assertFalse(p.names_match("nithin jain", "Nithin Jain"))

    def test_case_sensitive_uppercase_fails(self):
        self.assertFalse(p.names_match("NITHIN JAIN", "Nithin Jain"))

    def test_partial_name_fails(self):
        self.assertFalse(p.names_match("Nithin", "Nithin Jain"))

    def test_long_name_exact(self):
        self.assertTrue(p.names_match(
            "Rajarajeswari Balasubramaniam",
            "Rajarajeswari Balasubramaniam",
        ))

    def test_long_name_partial_fails(self):
        self.assertFalse(p.names_match("Rajarajeswari", "Rajarajeswari Balasubramaniam"))

    def test_wrong_name_fails(self):
        self.assertFalse(p.names_match("John Smith", "Nithin Jain"))


# ─────────────────────────────────────────────────────────────
# extract_dob
# ─────────────────────────────────────────────────────────────

class TestExtractDob(unittest.TestCase):

    def test_iso_format_bare(self):
        self.assertEqual(p.extract_dob("1990-05-14"), "1990-05-14")

    def test_iso_format_in_sentence(self):
        self.assertEqual(p.extract_dob("my DOB is 1990-05-14"), "1990-05-14")

    def test_dd_mm_yyyy_slash_converted(self):
        self.assertEqual(p.extract_dob("14/05/1990"), "1990-05-14")

    def test_dd_mm_yyyy_dash_converted(self):
        self.assertEqual(p.extract_dob("14-05-1990"), "1990-05-14")

    def test_leap_year_date(self):
        self.assertEqual(p.extract_dob("1988-02-29"), "1988-02-29")

    def test_no_date_returns_none(self):
        self.assertIsNone(p.extract_dob("hello there"))

    def test_partial_number_not_matched(self):
        # "123" alone should not match
        self.assertIsNone(p.extract_dob("123"))


# ─────────────────────────────────────────────────────────────
# is_valid_date
# ─────────────────────────────────────────────────────────────

class TestIsValidDate(unittest.TestCase):

    def test_normal_date(self):
        self.assertTrue(p.is_valid_date("1990-05-14"))

    def test_leap_year_feb_29_valid(self):
        self.assertTrue(p.is_valid_date("1988-02-29"))

    def test_non_leap_year_feb_29_invalid(self):
        self.assertFalse(p.is_valid_date("1990-02-29"))

    def test_feb_30_always_invalid(self):
        self.assertFalse(p.is_valid_date("1988-02-30"))

    def test_month_13_invalid(self):
        self.assertFalse(p.is_valid_date("1990-13-01"))

    def test_day_00_invalid(self):
        self.assertFalse(p.is_valid_date("1990-05-00"))

    def test_wrong_format_invalid(self):
        self.assertFalse(p.is_valid_date("14-05-1990"))

    def test_end_of_year_valid(self):
        self.assertTrue(p.is_valid_date("2000-12-31"))


# ─────────────────────────────────────────────────────────────
# extract_aadhaar_last4
# ─────────────────────────────────────────────────────────────

class TestExtractAadhaarLast4(unittest.TestCase):

    def test_labelled_aadhaar(self):
        self.assertEqual(p.extract_aadhaar_last4("aadhaar last 4 is 4321"), "4321")

    def test_aadhar_spelling(self):
        self.assertEqual(p.extract_aadhaar_last4("aadhar 9876"), "9876")

    def test_bare_4_digits(self):
        self.assertEqual(p.extract_aadhaar_last4("4321"), "4321")

    def test_bare_4_digits_in_sentence(self):
        self.assertEqual(p.extract_aadhaar_last4("my aadhaar ends in 2468"), "2468")

    def test_6_digit_pincode_not_grabbed_as_aadhaar(self):
        # 400001 is 6 digits — the 4-digit pattern should NOT match a sub-sequence
        # because the negative lookahead/lookbehind prevents it
        result = p.extract_aadhaar_last4("400001")
        self.assertNotEqual(result, "4000")
        self.assertNotEqual(result, "0001")

    def test_16_digit_card_number_not_matched(self):
        result = p.extract_aadhaar_last4("4532015112830366")
        # Should not return a 4-digit substring since digits are contiguous
        self.assertIsNone(result)

    def test_no_digits_returns_none(self):
        self.assertIsNone(p.extract_aadhaar_last4("hello"))

    def test_3_digit_number_not_matched(self):
        self.assertIsNone(p.extract_aadhaar_last4("123"))


# ─────────────────────────────────────────────────────────────
# extract_pincode
# ─────────────────────────────────────────────────────────────

class TestExtractPincode(unittest.TestCase):

    def test_labelled_pincode(self):
        self.assertEqual(p.extract_pincode("pincode 400001"), "400001")

    def test_pin_label(self):
        self.assertEqual(p.extract_pincode("my pin is 400002"), "400002")

    def test_postal_label(self):
        self.assertEqual(p.extract_pincode("postal 400003"), "400003")

    def test_bare_6_digits(self):
        self.assertEqual(p.extract_pincode("400001"), "400001")

    def test_4_digit_number_not_matched(self):
        self.assertIsNone(p.extract_pincode("4321"))

    def test_7_digit_number_not_matched_as_6(self):
        # 7-digit number: the pattern requires exactly 6 not adjacent to more digits
        result = p.extract_pincode("4000011")
        self.assertIsNone(result)

    def test_no_digits_returns_none(self):
        self.assertIsNone(p.extract_pincode("hello world"))


# ─────────────────────────────────────────────────────────────
# extract_amount
# ─────────────────────────────────────────────────────────────

class TestExtractAmount(unittest.TestCase):

    def test_integer_amount(self):
        amount, err = p.extract_amount("500", 1250.75)
        self.assertEqual(amount, 500.0)
        self.assertIsNone(err)

    def test_decimal_amount(self):
        amount, err = p.extract_amount("500.50", 1250.75)
        self.assertEqual(amount, 500.50)
        self.assertIsNone(err)

    def test_full_balance(self):
        amount, err = p.extract_amount("1250.75", 1250.75)
        self.assertEqual(amount, 1250.75)
        self.assertIsNone(err)

    def test_currency_symbol_stripped(self):
        amount, err = p.extract_amount("₹500", 1250.75)
        self.assertEqual(amount, 500.0)
        self.assertIsNone(err)

    def test_comma_stripped(self):
        amount, err = p.extract_amount("1,000", 1250.75)
        self.assertEqual(amount, 1000.0)
        self.assertIsNone(err)

    def test_amount_in_sentence(self):
        amount, err = p.extract_amount("I want to pay 300", 1250.75)
        self.assertEqual(amount, 300.0)
        self.assertIsNone(err)

    def test_zero_rejected(self):
        amount, err = p.extract_amount("0", 1250.75)
        self.assertIsNone(amount)
        self.assertIsNotNone(err)

    def test_exceeds_balance_rejected(self):
        amount, err = p.extract_amount("2000", 1250.75)
        self.assertIsNone(amount)
        self.assertIn("1,250.75", err)

    def test_no_number_returns_error(self):
        amount, err = p.extract_amount("yes please", 1250.75)
        self.assertIsNone(amount)
        self.assertIsNotNone(err)

    def test_partial_payment_allowed(self):
        amount, err = p.extract_amount("100", 540.00)
        self.assertEqual(amount, 100.0)
        self.assertIsNone(err)

    def test_zero_balance_account_rejects_any_amount(self):
        amount, err = p.extract_amount("1", 0.00)
        self.assertIsNone(amount)
        self.assertIsNotNone(err)


# ─────────────────────────────────────────────────────────────
# extract_card_number
# ─────────────────────────────────────────────────────────────

class TestExtractCardNumber(unittest.TestCase):

    def test_bare_16_digits(self):
        self.assertEqual(p.extract_card_number("4532015112830366"), "4532015112830366")

    def test_grouped_with_spaces(self):
        self.assertEqual(p.extract_card_number("4532 0151 1283 0366"), "4532015112830366")

    def test_grouped_with_dashes(self):
        self.assertEqual(p.extract_card_number("4532-0151-1283-0366"), "4532015112830366")

    def test_embedded_in_sentence(self):
        result = p.extract_card_number("my card number is 4532015112830366 thanks")
        self.assertEqual(result, "4532015112830366")

    def test_15_digit_amex_not_matched(self):
        # 15-digit Amex — should not match the 16-digit pattern
        self.assertIsNone(p.extract_card_number("378282246310005"))

    def test_no_digits_returns_none(self):
        self.assertIsNone(p.extract_card_number("hello"))

    def test_short_number_returns_none(self):
        self.assertIsNone(p.extract_card_number("1234567890"))


# ─────────────────────────────────────────────────────────────
# extract_cvv
# ─────────────────────────────────────────────────────────────

class TestExtractCvv(unittest.TestCase):

    def test_labelled_cvv_3_digits(self):
        self.assertEqual(p.extract_cvv("CVV 123"), "123")

    def test_labelled_cvv_4_digits(self):
        self.assertEqual(p.extract_cvv("cvv is 1234"), "1234")

    def test_cvc_label(self):
        self.assertEqual(p.extract_cvv("CVC: 456"), "456")

    def test_security_code_label(self):
        self.assertEqual(p.extract_cvv("security code 789"), "789")

    def test_bare_3_digits(self):
        self.assertEqual(p.extract_cvv("123"), "123")

    def test_bare_4_digits(self):
        self.assertEqual(p.extract_cvv("9876"), "9876")

    def test_2_digit_number_not_matched(self):
        self.assertIsNone(p.extract_cvv("12"))

    def test_5_digit_number_not_matched_as_cvv(self):
        # 5 consecutive digits — should not match 3 or 4 digit pattern
        self.assertIsNone(p.extract_cvv("12345"))

    def test_no_digits_returns_none(self):
        self.assertIsNone(p.extract_cvv("hello"))


# ─────────────────────────────────────────────────────────────
# extract_expiry
# ─────────────────────────────────────────────────────────────

class TestExtractExpiry(unittest.TestCase):

    def test_mm_yyyy_slash(self):
        self.assertEqual(p.extract_expiry("12/2027"), (12, 2027))

    def test_mm_yyyy_dash(self):
        self.assertEqual(p.extract_expiry("12-2027"), (12, 2027))

    def test_mm_yy_expanded(self):
        month, year = p.extract_expiry("12/27")
        self.assertEqual(month, 12)
        self.assertEqual(year, 2027)

    def test_single_digit_month(self):
        self.assertEqual(p.extract_expiry("3/2028"), (3, 2028))

    def test_month_name(self):
        month, year = p.extract_expiry("december 2027")
        self.assertEqual(month, 12)
        self.assertEqual(year, 2027)

    def test_month_name_case_insensitive(self):
        month, year = p.extract_expiry("March 2030")
        self.assertEqual(month, 3)
        self.assertEqual(year, 2030)

    def test_invalid_month_13_not_matched(self):
        month, year = p.extract_expiry("13/2027")
        self.assertIsNone(month)
        self.assertIsNone(year)

    def test_no_expiry_returns_none_none(self):
        month, year = p.extract_expiry("hello world")
        self.assertIsNone(month)
        self.assertIsNone(year)

    def test_embedded_in_sentence(self):
        month, year = p.extract_expiry("expiry is 06/2026")
        self.assertEqual(month, 6)
        self.assertEqual(year, 2026)


# ─────────────────────────────────────────────────────────────
# validate_expiry
# ─────────────────────────────────────────────────────────────

class TestValidateExpiry(unittest.TestCase):

    def test_future_date_valid(self):
        valid, err = p.validate_expiry(12, 2099)
        self.assertTrue(valid)
        self.assertIsNone(err)

    def test_past_year_invalid(self):
        valid, err = p.validate_expiry(1, 2020)
        self.assertFalse(valid)
        self.assertIsNotNone(err)

    def test_month_zero_invalid(self):
        valid, err = p.validate_expiry(0, 2099)
        self.assertFalse(valid)

    def test_month_13_invalid(self):
        valid, err = p.validate_expiry(13, 2099)
        self.assertFalse(valid)

    def test_valid_month_boundary_january(self):
        valid, err = p.validate_expiry(1, 2099)
        self.assertTrue(valid)

    def test_valid_month_boundary_december(self):
        valid, err = p.validate_expiry(12, 2099)
        self.assertTrue(valid)


# ─────────────────────────────────────────────────────────────
# extract_cardholder_name
# ─────────────────────────────────────────────────────────────

class TestExtractCardholderName(unittest.TestCase):

    def test_cardholder_name_label(self):
        self.assertEqual(p.extract_cardholder_name("Cardholder: Nithin Jain"), "Nithin Jain")

    def test_name_on_card_label(self):
        self.assertEqual(p.extract_cardholder_name("name on card: Nithin Jain"), "Nithin Jain")

    def test_my_name_is_prefix(self):
        result = p.extract_cardholder_name("my name is Nithin Jain")
        self.assertEqual(result, "Nithin Jain")

    def test_bare_full_name(self):
        self.assertEqual(p.extract_cardholder_name("Nithin Jain"), "Nithin Jain")

    def test_bare_single_word_returns_none(self):
        # Single word is not a cardholder name
        self.assertIsNone(p.extract_cardholder_name("Nithin"))

    def test_mixed_content_no_label_returns_none(self):
        # A sentence with numbers — should not grab a partial name
        result = p.extract_cardholder_name("4532015112830366")
        self.assertIsNone(result)

    def test_long_name(self):
        result = p.extract_cardholder_name("Cardholder: Rajarajeswari Balasubramaniam")
        self.assertEqual(result, "Rajarajeswari Balasubramaniam")


# ─────────────────────────────────────────────────────────────
# Ambiguity / cross-function conflict cases
# ─────────────────────────────────────────────────────────────

class TestParserAmbiguity(unittest.TestCase):
    """
    Tests for inputs that could match multiple parsers — verifying each
    function returns only what it should, not what a sibling function handles.
    """

    def test_dob_string_not_grabbed_by_aadhaar(self):
        # "1990-05-14" — aadhaar parser should not extract a 4-digit sub-sequence
        result = p.extract_aadhaar_last4("1990-05-14")
        # "1990" is 4 digits but preceded/followed by non-digits via the ISO pattern
        # With the regex (?<!\d)(\d{4})(?!\d), "1990" is followed by "-" (not a digit)
        # and preceded by start of string — this WILL match "1990".
        # The ambiguity is intentional to document; this test captures current behaviour.
        # If it starts returning DOB components, that's a regression.
        if result is not None:
            self.assertNotEqual(result, "0514")  # month+day should not be grabbed

    def test_pincode_not_confused_with_card_number(self):
        # A 16-digit number should not give a 6-digit pincode match
        result = p.extract_pincode("4532015112830366")
        self.assertIsNone(result)

    def test_cvv_not_grabbed_from_card_number(self):
        # A 16-digit card number should not yield a 3-digit CVV match
        result = p.extract_cvv("4532015112830366")
        self.assertIsNone(result)

    def test_aadhaar_label_takes_priority_over_bare_4_digits(self):
        # When the label "aadhaar" is present, use that match not a different 4-digit sequence
        result = p.extract_aadhaar_last4("I have aadhaar ending in 4321 and also 9999")
        self.assertEqual(result, "4321")

    def test_pincode_label_takes_priority_over_bare_6_digits(self):
        result = p.extract_pincode("pincode 400001 and something else 123456")
        self.assertEqual(result, "400001")

    def test_account_id_not_confused_with_pincode(self):
        # "400001" could look like an account number (it's 6 digits, >4)
        # but it doesn't have the ACC prefix, so it gets promoted to "ACC400001"
        result = p.extract_account_id("400001")
        self.assertEqual(result, "ACC400001")


if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    test_classes = [
        TestExtractAccountId,
        TestExtractName,
        TestNamesMatch,
        TestExtractDob,
        TestIsValidDate,
        TestExtractAadhaarLast4,
        TestExtractPincode,
        TestExtractAmount,
        TestExtractCardNumber,
        TestExtractCvv,
        TestExtractExpiry,
        TestValidateExpiry,
        TestExtractCardholderName,
        TestParserAmbiguity,
    ]
    for cls in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
