"""Unit tests for validators.py — all validation functions."""

import io
import pytest
from validators import (
    ValidationError,
    validate_amount,
    validate_quantity,
    validate_payment_amount,
    validate_date,
    validate_date_range,
    validate_customer_active,
    validate_string,
    validate_filename,
    validate_file_type,
    validate_debt_items,
    validate_donation_usage,
)


# ── validate_amount ──────────────────────────────────────────────

class TestValidateAmount:
    def test_valid_float(self):
        assert validate_amount("10.50") == 10.50

    def test_valid_integer_string(self):
        assert validate_amount("7") == 7.0

    def test_rounds_to_two_decimals(self):
        assert validate_amount("10.556") == 10.56

    def test_none_raises(self):
        with pytest.raises(ValidationError, match="required"):
            validate_amount(None)

    def test_empty_string_raises(self):
        with pytest.raises(ValidationError, match="required"):
            validate_amount("")

    def test_non_numeric_raises(self):
        with pytest.raises(ValidationError, match="valid number"):
            validate_amount("abc")

    def test_negative_rejected_by_default(self):
        with pytest.raises(ValidationError, match="cannot be negative"):
            validate_amount("-5")

    def test_negative_allowed_when_flagged(self):
        assert validate_amount("-5", allow_negative=True) == -5.0

    def test_zero_rejected_by_default(self):
        with pytest.raises(ValidationError, match="cannot be zero"):
            validate_amount("0")

    def test_zero_allowed_when_flagged(self):
        assert validate_amount("0", allow_zero=True) == 0.0

    def test_exceeds_max(self):
        with pytest.raises(ValidationError, match="exceeds maximum"):
            validate_amount("2000000")

    def test_custom_max(self):
        with pytest.raises(ValidationError, match="exceeds maximum"):
            validate_amount("101", max_value=100)

    def test_custom_field_name(self):
        with pytest.raises(ValidationError, match="Price"):
            validate_amount(None, field_name="Price")


# ── validate_quantity ────────────────────────────────────────────

class TestValidateQuantity:
    def test_valid(self):
        assert validate_quantity("3") == 3

    def test_none_defaults_to_1(self):
        assert validate_quantity(None) == 1

    def test_empty_defaults_to_1(self):
        assert validate_quantity("") == 1

    def test_non_integer_raises(self):
        with pytest.raises(ValidationError, match="valid integer"):
            validate_quantity("2.5")

    def test_zero_raises(self):
        with pytest.raises(ValidationError, match="greater than zero"):
            validate_quantity("0")

    def test_negative_raises(self):
        with pytest.raises(ValidationError, match="greater than zero"):
            validate_quantity("-1")

    def test_exceeds_max(self):
        with pytest.raises(ValidationError, match="exceeds maximum"):
            validate_quantity("10001")


# ── validate_payment_amount ──────────────────────────────────────

class TestValidatePaymentAmount:
    def test_valid_payment(self):
        amount, is_over = validate_payment_amount("50", 100.0)
        assert amount == 50.0
        assert is_over is False

    def test_exact_balance_payment(self):
        amount, _ = validate_payment_amount("100", 100.0)
        assert amount == 100.0

    def test_overpayment_blocked(self):
        with pytest.raises(ValidationError, match="exceeds current balance"):
            validate_payment_amount("150", 100.0)

    def test_overpayment_allowed(self):
        amount, is_over = validate_payment_amount("150", 100.0, allow_overpayment=True)
        assert amount == 150.0
        assert is_over is True

    def test_zero_balance_raises(self):
        with pytest.raises(ValidationError, match="no outstanding balance"):
            validate_payment_amount("10", 0)

    def test_credit_balance_raises(self):
        with pytest.raises(ValidationError, match="credit balance"):
            validate_payment_amount("10", -50.0)


# ── validate_date / validate_date_range ──────────────────────────

class TestValidateDate:
    def test_valid_date(self):
        d = validate_date("2025-06-15")
        assert d.year == 2025 and d.month == 6 and d.day == 15

    def test_empty_raises(self):
        with pytest.raises(ValidationError, match="required"):
            validate_date("")

    def test_bad_format_raises(self):
        with pytest.raises(ValidationError, match="YYYY-MM-DD"):
            validate_date("15/06/2025")


class TestValidateDateRange:
    def test_valid_range(self):
        s, e = validate_date_range("2025-01-01", "2025-12-31")
        assert s < e

    def test_same_day(self):
        s, e = validate_date_range("2025-06-01", "2025-06-01")
        assert s == e

    def test_reversed_raises(self):
        with pytest.raises(ValidationError, match="before or equal"):
            validate_date_range("2025-12-31", "2025-01-01")


# ── validate_customer_active ─────────────────────────────────────

class TestValidateCustomerActive:
    def test_active_customer(self):
        assert validate_customer_active({"id": 1, "is_active": True}) is True

    def test_none_raises(self):
        with pytest.raises(ValidationError, match="not found"):
            validate_customer_active(None)

    def test_inactive_raises(self):
        with pytest.raises(ValidationError, match="deactivated"):
            validate_customer_active({"id": 1, "is_active": False})

    def test_missing_is_active_defaults_true(self):
        assert validate_customer_active({"id": 1}) is True


# ── validate_string ──────────────────────────────────────────────

class TestValidateString:
    def test_valid(self):
        assert validate_string("hello", "Name") == "hello"

    def test_strips_whitespace(self):
        assert validate_string("  hello  ", "Name") == "hello"

    def test_required_none_raises(self):
        with pytest.raises(ValidationError, match="required"):
            validate_string(None, "Name")

    def test_required_empty_raises(self):
        with pytest.raises(ValidationError, match="required"):
            validate_string("   ", "Name")

    def test_not_required_empty_returns_none(self):
        assert validate_string("", "Name", required=False) is None

    def test_too_short(self):
        with pytest.raises(ValidationError, match="at least"):
            validate_string("ab", "Name", min_length=3)

    def test_too_long(self):
        with pytest.raises(ValidationError, match="must not exceed"):
            validate_string("a" * 11, "Name", max_length=10)


# ── validate_filename ────────────────────────────────────────────

class TestValidateFilename:
    def test_simple_filename(self):
        assert validate_filename("photo.jpg") == "photo.jpg"

    def test_strips_path(self):
        assert validate_filename("/some/path/photo.jpg") == "photo.jpg"

    def test_strips_windows_path(self):
        assert validate_filename("C:\\Users\\file.png") == "file.png"

    def test_empty_raises(self):
        with pytest.raises(ValidationError, match="empty"):
            validate_filename("")

    def test_none_raises(self):
        with pytest.raises(ValidationError, match="empty"):
            validate_filename(None)


# ── validate_file_type ───────────────────────────────────────────

class TestValidateFileType:
    def _make_file(self, filename, header=b"\xff\xd8\xff"):
        f = io.BytesIO(header + b"\x00" * 100)
        f.filename = filename
        f.name = filename
        return f

    def test_valid_extension(self):
        f = self._make_file("img.jpg")
        assert validate_file_type(f, {"jpg", "png"}) is True

    def test_invalid_extension(self):
        f = self._make_file("data.exe")
        with pytest.raises(ValidationError, match="not allowed"):
            validate_file_type(f, {"jpg", "png"})

    def test_mime_check_jpeg(self):
        f = self._make_file("img.jpg", b"\xff\xd8\xff" + b"\x00" * 9)
        assert validate_file_type(
            f, {"jpg"}, allowed_mimetypes=["image/jpeg"]
        ) is True

    def test_mime_check_png(self):
        header = b"\x89PNG\r\n\x1a\n" + b"\x00" * 4
        f = self._make_file("img.png", header)
        assert validate_file_type(
            f, {"png"}, allowed_mimetypes=["image/png"]
        ) is True

    def test_mime_mismatch(self):
        f = self._make_file("img.png", b"\xff\xd8\xff" + b"\x00" * 9)
        with pytest.raises(ValidationError, match="does not match"):
            validate_file_type(f, {"png"}, allowed_mimetypes=["image/png"])

    def test_no_file_raises(self):
        with pytest.raises(ValidationError, match="No file"):
            validate_file_type(None, {"jpg"})


# ── validate_debt_items ──────────────────────────────────────────

class TestValidateDebtItems:
    def test_single_item(self):
        items, total = validate_debt_items([
            {"product_name": "Aspirin", "price": "9.99", "quantity": "2"}
        ])
        assert len(items) == 1
        assert items[0]["price"] == 9.99
        assert items[0]["quantity"] == 2
        assert total == 19.98

    def test_multiple_items(self):
        items, total = validate_debt_items([
            {"product_name": "A", "price": "10", "quantity": "1"},
            {"product_name": "B", "price": "5", "quantity": "3"},
        ])
        assert total == 25.0

    def test_empty_list_raises(self):
        with pytest.raises(ValidationError, match="(?i)at least one"):
            validate_debt_items([])

    def test_none_raises(self):
        with pytest.raises(ValidationError, match="(?i)at least one"):
            validate_debt_items(None)

    def test_missing_product_name_raises(self):
        with pytest.raises(ValidationError, match="Product name"):
            validate_debt_items([{"price": "10"}])

    def test_zero_price_raises(self):
        with pytest.raises(ValidationError, match="cannot be zero"):
            validate_debt_items([{"product_name": "X", "price": "0"}])

    def test_default_quantity(self):
        items, _ = validate_debt_items([
            {"product_name": "X", "price": "10"}
        ])
        assert items[0]["quantity"] == 1


# ── validate_donation_usage ──────────────────────────────────────

class TestValidateDonationUsage:
    def test_valid(self):
        donation = {"amount_remaining": 200.0}
        assert validate_donation_usage(donation, "100") == 100.0

    def test_exceeds_remaining(self):
        donation = {"amount_remaining": 50.0}
        with pytest.raises(ValidationError, match="exceeds available"):
            validate_donation_usage(donation, "100")

    def test_none_donation_raises(self):
        with pytest.raises(ValidationError, match="not found"):
            validate_donation_usage(None, "10")

    def test_exact_remaining(self):
        donation = {"amount_remaining": 75.0}
        assert validate_donation_usage(donation, "75") == 75.0
