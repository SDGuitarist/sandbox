def register_filters(app):
    @app.template_filter('dollars')
    def dollars_filter(cents):
        """Convert integer cents to dollar string."""
        if cents is None:
            return '$0.00'
        return f'${cents / 100:.2f}'

    @app.template_filter('datefmt')
    def datefmt_filter(value):
        """Format datetime string for display."""
        if not value:
            return ''
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(value)
            return dt.strftime('%b %d, %Y %I:%M %p')
        except (ValueError, TypeError):
            return value
