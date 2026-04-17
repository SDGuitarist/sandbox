def sanitize_csv_cell(value):
    """Prevent CSV formula injection by prefixing dangerous leading characters."""
    if value and isinstance(value, str) and value[0] in ("=", "-", "+", "@", "|"):
        return "'" + value
    return value
