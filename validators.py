# validators.py - Centralized Validation Module for Pharmacy Debt System
# This module contains all validation functions to ensure data integrity

from datetime import datetime


class ValidationError(Exception):
    """Custom exception for validation errors"""
    def __init__(self, message, field=None):
        self.message = message
        self.field = field
        super().__init__(self.message)


# ============== AMOUNT VALIDATION ==============

def validate_amount(value, field_name="amount", allow_zero=False, allow_negative=False, max_value=1000000):
    """
    Validate monetary amounts
    - Converts to float safely
    - Rejects negative values (unless explicitly allowed)
    - Rejects zero values (unless explicitly allowed)
    - Sets maximum allowed value

    Returns: float - validated and rounded amount
    Raises: ValidationError if validation fails
    """
    if value is None or value == '':
        raise ValidationError(f"{field_name} is required", field_name)

    try:
        amount = float(value)
    except (ValueError, TypeError):
        raise ValidationError(f"{field_name} must be a valid number", field_name)

    if not allow_negative and amount < 0:
        raise ValidationError(f"{field_name} cannot be negative", field_name)

    if not allow_zero and amount == 0:
        raise ValidationError(f"{field_name} cannot be zero", field_name)

    if amount > max_value:
        raise ValidationError(f"{field_name} exceeds maximum allowed value of ${max_value:,.2f}", field_name)

    # Round to 2 decimal places for currency
    return round(amount, 2)


def validate_quantity(value, field_name="quantity"):
    """
    Validate quantity values - must be positive integers

    Returns: int - validated quantity (defaults to 1 if empty)
    Raises: ValidationError if validation fails
    """
    if value is None or value == '':
        return 1  # Default quantity

    try:
        quantity = int(value)
    except (ValueError, TypeError):
        raise ValidationError(f"{field_name} must be a valid integer", field_name)

    if quantity <= 0:
        raise ValidationError(f"{field_name} must be greater than zero", field_name)

    if quantity > 10000:
        raise ValidationError(f"{field_name} exceeds maximum allowed value of 10,000", field_name)

    return quantity


# ============== PAYMENT VALIDATION ==============

def validate_payment_amount(amount, current_balance, allow_overpayment=False):
    """
    Validate payment against current balance
    - Prevents overpayment unless explicitly allowed
    - Prevents payments when balance is zero or negative

    Returns: tuple (validated_amount, is_overpayment)
    Raises: ValidationError if validation fails
    """
    validated_amount = validate_amount(amount, "Payment amount")

    if current_balance <= 0:
        if current_balance < 0:
            raise ValidationError(
                f"Customer has a credit balance of ${abs(current_balance):.2f}. Cannot accept additional payments.",
                "amount"
            )
        else:
            raise ValidationError("Customer has no outstanding balance to pay", "amount")

    if not allow_overpayment and validated_amount > current_balance:
        raise ValidationError(
            f"Payment amount (${validated_amount:.2f}) exceeds current balance (${current_balance:.2f}). "
            f"Maximum payment allowed: ${current_balance:.2f}",
            "amount"
        )

    return validated_amount, validated_amount > current_balance


# ============== DATE VALIDATION ==============

def validate_date(date_str, field_name="date"):
    """
    Validate date string format (YYYY-MM-DD)

    Returns: datetime.date - parsed date object
    Raises: ValidationError if validation fails
    """
    if not date_str:
        raise ValidationError(f"{field_name} is required", field_name)

    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        raise ValidationError(f"{field_name} must be in YYYY-MM-DD format", field_name)


def validate_date_range(start_date, end_date):
    """
    Validate that start_date is before or equal to end_date

    Returns: tuple (start_date, end_date) as date objects
    Raises: ValidationError if validation fails
    """
    start = validate_date(start_date, "Start date")
    end = validate_date(end_date, "End date")

    if start > end:
        raise ValidationError("Start date must be before or equal to end date")

    return start, end


# ============== CUSTOMER VALIDATION ==============

def validate_customer_active(customer):
    """
    Check if customer exists and is active

    Returns: True if customer is valid and active
    Raises: ValidationError if validation fails
    """
    if not customer:
        raise ValidationError("Customer not found")

    if not customer.get('is_active', True):
        raise ValidationError("Cannot perform operations on deactivated customer")

    return True


# ============== STRING VALIDATION ==============

def validate_string(value, field_name, min_length=1, max_length=500, required=True):
    """
    Validate string fields

    Returns: str - trimmed string value, or None if not required and empty
    Raises: ValidationError if validation fails
    """
    if value is None or (isinstance(value, str) and value.strip() == ''):
        if required:
            raise ValidationError(f"{field_name} is required", field_name)
        return None

    value = str(value).strip()

    if len(value) < min_length:
        raise ValidationError(f"{field_name} must be at least {min_length} characters", field_name)

    if len(value) > max_length:
        raise ValidationError(f"{field_name} must not exceed {max_length} characters", field_name)

    return value


# ============== FILE VALIDATION ==============

def validate_filename(filename):
    """
    Validate uploaded filename - returns sanitized filename or raises error

    Returns: str - validated filename
    Raises: ValidationError if validation fails
    """
    if not filename or filename.strip() == '':
        raise ValidationError("Filename is empty")

    # Remove path components
    filename = filename.split('/')[-1].split('\\')[-1]

    if filename == '':
        raise ValidationError("Invalid filename")

    return filename


def validate_file_type(file, allowed_extensions, allowed_mimetypes=None):
    """
    Validate file extension and optionally MIME type by checking file header bytes

    Returns: True if file is valid
    Raises: ValidationError if validation fails
    """
    if not file or not file.filename:
        raise ValidationError("No file provided")

    filename = file.filename.lower()
    ext = filename.rsplit('.', 1)[-1] if '.' in filename else ''

    if ext not in allowed_extensions:
        raise ValidationError(f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}")

    if allowed_mimetypes:
        # Check MIME type from file headers (magic bytes)
        file.seek(0)
        header = file.read(12)
        file.seek(0)

        # Common image file signatures
        detected_mime = None

        # PNG: 89 50 4E 47 0D 0A 1A 0A
        if header[:8] == b'\x89PNG\r\n\x1a\n':
            detected_mime = 'image/png'
        # JPEG: FF D8 FF
        elif header[:3] == b'\xff\xd8\xff':
            detected_mime = 'image/jpeg'
        # GIF: GIF87a or GIF89a
        elif header[:6] in (b'GIF87a', b'GIF89a'):
            detected_mime = 'image/gif'
        # WebP: RIFF....WEBP
        elif header[:4] == b'RIFF' and header[8:12] == b'WEBP':
            detected_mime = 'image/webp'

        if detected_mime is None:
            raise ValidationError("Unable to verify file type. File may be corrupted.")

        if detected_mime not in allowed_mimetypes:
            raise ValidationError(f"File content does not match expected image type")

    return True


# ============== ITEM LIST VALIDATION ==============

def validate_debt_items(items):
    """
    Validate a list of debt items
    - Each item must have product_name
    - Each item must have valid price > 0
    - Each item must have valid quantity >= 1

    Returns: tuple (validated_items, total)
    Raises: ValidationError if validation fails
    """
    if not items or len(items) == 0:
        raise ValidationError("At least one item is required")

    validated_items = []
    total = 0

    for i, item in enumerate(items):
        product_name = validate_string(
            item.get('product_name'),
            f"Product name (item {i+1})",
            max_length=200
        )

        price = validate_amount(
            item.get('price'),
            f"Price (item {i+1})",
            allow_zero=False
        )

        quantity = validate_quantity(
            item.get('quantity', 1),
            f"Quantity (item {i+1})"
        )

        item_total = price * quantity
        total += item_total

        validated_items.append({
            'product_name': product_name,
            'price': price,
            'quantity': quantity
        })

    return validated_items, round(total, 2)


# ============== DONATION VALIDATION ==============

def validate_donation_usage(donation, amount):
    """
    Validate that donation has sufficient funds for requested usage

    Returns: float - validated amount
    Raises: ValidationError if validation fails
    """
    if not donation:
        raise ValidationError("Donation not found")

    amount_remaining = donation.get('amount_remaining', 0)

    validated_amount = validate_amount(amount, "Usage amount")

    if validated_amount > amount_remaining:
        raise ValidationError(
            f"Requested amount (${validated_amount:.2f}) exceeds available funds (${amount_remaining:.2f})"
        )

    return validated_amount
