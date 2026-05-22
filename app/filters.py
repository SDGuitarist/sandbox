def dollars(cents):
    """Format integer cents as dollar string: 1250 -> '$12.50'"""
    return f'${cents / 100:.2f}'


def format_date(date_str):
    """Format ISO date string: '2026-05-22' -> 'May 22, 2026'"""
    from datetime import datetime
    try:
        dt = datetime.strptime(date_str[:10], '%Y-%m-%d')
        return dt.strftime('%b %d, %Y')
    except (ValueError, TypeError):
        return date_str or ''
