def register_filters(app):
    @app.template_filter('dollars')
    def dollars_filter(cents):
        if cents is None:
            return '$0.00'
        return f'${cents / 100:.2f}'

    @app.template_filter('stage_label')
    def stage_label_filter(stage):
        return stage.replace('_', ' ').title()
