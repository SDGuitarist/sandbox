from markupsafe import Markup, escape


def register_filters(app):
    @app.template_filter('status_badge')
    def status_badge(status):
        colors = {
            'new': 'primary',
            'reviewed': 'info',
            'assessment-ready': 'warning',
            'audit-scheduled': 'success',
            'completed': 'secondary',
            'declined': 'danger',
            'archived': 'dark',
        }
        color = colors.get(status, 'secondary')
        return Markup(f'<span class="badge bg-{color}">{escape(status)}</span>')

    @app.template_filter('datetime_format')
    def datetime_format(value):
        if not value:
            return ''
        from datetime import datetime
        try:
            dt = datetime.fromisoformat(value)
            return dt.strftime('%b %d, %Y %I:%M %p')
        except (ValueError, TypeError):
            return value
