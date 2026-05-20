def register_filters(app):
    @app.template_filter('dollars')
    def dollars_filter(cents):
        """Convert integer cents to dollar string. Usage: {{ amount|dollars }}"""
        if cents is None:
            return '$0.00'
        return f"${cents / 100:,.2f}"

    @app.template_filter('day_name')
    def day_name_filter(day_num):
        """Convert 0-6 to day name. Usage: {{ day_of_week|day_name }}"""
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        return days[day_num] if 0 <= day_num <= 6 else str(day_num)
