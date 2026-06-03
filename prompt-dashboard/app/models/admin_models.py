def get_dashboard_stats(conn):
    """Get admin dashboard stats.
    Returns: dict with total_users, total_prompts, total_templates, avg_completeness.
    Usage:
        stats = get_dashboard_stats(conn)
        # stats = {'total_users': 5, 'total_prompts': 12, 'total_templates': 3, 'avg_completeness': 0.67}
    """
    total_users = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    total_prompts = conn.execute('SELECT COUNT(*) FROM prompts').fetchone()[0]
    total_templates = conn.execute('SELECT COUNT(*) FROM prompt_templates').fetchone()[0]
    row = conn.execute('SELECT AVG(completeness) FROM prompts').fetchone()
    avg_completeness = row[0] if row[0] is not None else 0.0
    return {
        'total_users': total_users,
        'total_prompts': total_prompts,
        'total_templates': total_templates,
        'avg_completeness': avg_completeness,
    }
