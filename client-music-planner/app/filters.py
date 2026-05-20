def format_date(value):
    """Format ISO date string as 'January 15, 2026'."""
    if not value:
        return ''
    from datetime import datetime
    dt = datetime.fromisoformat(value) if isinstance(value, str) else value
    return dt.strftime('%B %d, %Y')


def format_duration(seconds):
    """Format seconds as 'M:SS'."""
    if not seconds:
        return ''
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}:{secs:02d}"


def format_genre(genre):
    """Format genre slug as display name: 'r_and_b' -> 'R&B'."""
    special = {'r_and_b': 'R&B', 'hip_hop': 'Hip Hop'}
    if genre in special:
        return special[genre]
    return genre.replace('_', ' ').title()


def format_energy(energy):
    """Format energy level as label."""
    labels = {1: 'Low', 2: 'Mellow', 3: 'Moderate', 4: 'Upbeat', 5: 'High'}
    return labels.get(energy, str(energy))


def register_filters(app):
    app.jinja_env.filters['format_date'] = format_date
    app.jinja_env.filters['format_duration'] = format_duration
    app.jinja_env.filters['format_genre'] = format_genre
    app.jinja_env.filters['format_energy'] = format_energy
