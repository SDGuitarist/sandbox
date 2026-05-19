def dollars(cents, symbol='$'):
    """Display integer cents as dollars. Usage: {{ amount|dollars }}"""
    if cents is None:
        return f'{symbol}0.00'
    return f'{symbol}{cents / 100:,.2f}'


def minutes_to_hours(minutes):
    """Display integer minutes as H:MM. Usage: {{ mins|minutes_to_hours }}"""
    if minutes is None:
        return '0:00'
    h = minutes // 60
    m = minutes % 60
    return f'{h}:{m:02d}'


def minutes_to_decimal(minutes):
    """Display integer minutes as decimal hours. Usage: {{ mins|minutes_to_decimal }}"""
    if minutes is None:
        return '0.0'
    return f'{minutes / 60:.1f}'


def init_app(app):
    app.jinja_env.filters['dollars'] = dollars
    app.jinja_env.filters['minutes_to_hours'] = minutes_to_hours
    app.jinja_env.filters['minutes_to_decimal'] = minutes_to_decimal
