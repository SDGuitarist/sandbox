def sanitize_csv_cell(value):
    """Prevent CSV formula injection and strip control characters."""
    if not value or not isinstance(value, str):
        return value
    # Strip tab, carriage return, newline (can break CSV rows or enable injection)
    value = value.replace("\t", " ").replace("\r", "").replace("\n", " ")
    # Prefix dangerous leading characters that trigger formulas in Excel/Sheets
    if value[0] in ("=", "-", "+", "@", "|"):
        return "'" + value
    return value
