from datetime import datetime


def register_filters(app):
    @app.template_filter('dollars')
    def dollars_filter(cents):
        """Convert cents to dollar display: 1500 -> '$15.00'"""
        if cents is None:
            return '$0.00'
        return f'${cents / 100:.2f}'

    @app.template_filter('date_format')
    def date_format_filter(date_str, fmt='%b %d, %Y'):
        """Format ISO date string: '2026-05-21' -> 'May 21, 2026'"""
        if not date_str:
            return ''
        return datetime.fromisoformat(date_str).strftime(fmt)

    @app.template_filter('time_format')
    def time_format_filter(time_str):
        """Format time string: '14:30' -> '2:30 PM'"""
        if not time_str:
            return ''
        return datetime.strptime(time_str, '%H:%M').strftime('%-I:%M %p')
