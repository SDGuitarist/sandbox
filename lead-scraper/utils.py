def sanitize_cell_value(value):
    """Sanitize a string value for safe storage and CSV export.

    Used at both import (defense in depth) and export (formula injection
    prevention). Strips control characters and prefixes dangerous leading
    characters that trigger formulas in Excel/Sheets.
    """
    if not value or not isinstance(value, str):
        return value
    # Strip null bytes, tab, carriage return, newline
    value = value.replace("\x00", "").replace("\t", " ").replace("\r", "").replace("\n", " ")
    # Prefix dangerous leading characters that trigger formulas in Excel/Sheets
    if value and value[0] in ("=", "-", "+", "@", "|"):
        return "'" + value
    return value


# Backwards-compatible alias
sanitize_csv_cell = sanitize_cell_value
