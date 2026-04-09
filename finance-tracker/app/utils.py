import math

MAX_AMOUNT_CENTS = 99_999_999  # $999,999.99


def dollars_to_cents(value_str):
    """Convert user input like '45.99' to integer cents 4599.
    Raises ValueError on invalid input."""
    value = float(value_str)
    if math.isnan(value) or math.isinf(value):
        raise ValueError("Invalid amount")
    if value <= 0:
        raise ValueError("Amount must be positive")
    cents = int(round(value * 100))
    if cents <= 0:
        raise ValueError("Amount too small (rounds to zero)")
    if cents > MAX_AMOUNT_CENTS:
        raise ValueError("Amount too large (max $999,999.99)")
    return cents


def format_dollars(cents):
    """Format integer cents as dollar string. 4599 -> '$45.99'"""
    if cents is None:
        return "\u2014"
    return f"${cents / 100:.2f}"


def validate_year_month(value):
    """Validate 'YYYY-MM' format. Raises ValueError if invalid."""
    import re
    if not re.match(r'^\d{4}-\d{2}$', value):
        raise ValueError("Invalid month format")
    year, month = int(value[:4]), int(value[5:7])
    if month < 1 or month > 12:
        raise ValueError("Invalid month")
    return value
