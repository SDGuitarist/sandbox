from datetime import datetime

def register_filters(app):
    @app.template_filter('dollars')
    def dollars_filter(cents):
        if cents is None:
            return '$0.00'
        return f'${cents / 100:.2f}'

    @app.template_filter('dollars_raw')
    def dollars_raw_filter(cents):
        if cents is None:
            return '0.00'
        return f'{cents / 100:.2f}'

    @app.template_filter('date_format')
    def date_format_filter(date_str, fmt='%b %d, %Y'):
        if not date_str:
            return ''
        return datetime.fromisoformat(date_str).strftime(fmt)

    @app.template_filter('time_format')
    def time_format_filter(time_str):
        if not time_str:
            return ''
        return datetime.strptime(time_str, '%H:%M').strftime('%-I:%M %p')
