def log_audit_event(conn, user_id, action, resource_type, resource_id=None):
    """Log an audit event.
    Returns: None
    Usage:
        log_audit_event(conn, user_id, 'create', 'prompt', prompt_id)
        log_audit_event(conn, None, 'view_share', 'template', template_id)
    """
    conn.execute(
        'INSERT INTO audit_events (user_id, action, resource_type, resource_id) VALUES (?, ?, ?, ?)',
        (user_id, action, resource_type, resource_id)
    )
    # No conn.commit() -- autocommit=True
