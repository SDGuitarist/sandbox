"""Component definition queries — reads from component_definitions table."""


def get_all_components(conn):
    """Returns: list[sqlite3.Row] ordered by position (1-12)
    Usage:
        components = get_all_components(conn)
        for comp in components: print(comp['name'], comp['cluster'])
    """
    return conn.execute(
        'SELECT * FROM component_definitions ORDER BY position'
    ).fetchall()


def get_components_grouped(conn):
    """Returns: dict[str, list[sqlite3.Row]] grouped by cluster
    Usage:
        clusters = get_components_grouped(conn)
        for cluster_name, comps in clusters.items(): ...
    """
    rows = get_all_components(conn)
    groups = {}
    for row in rows:
        cluster = row['cluster']
        if cluster not in groups:
            groups[cluster] = []
        groups[cluster].append(row)
    return groups


def get_component(conn, component_id):
    """Returns: sqlite3.Row or None
    Usage:
        comp = get_component(conn, component_id)
        if comp is None: abort(404)
    """
    return conn.execute(
        'SELECT * FROM component_definitions WHERE id = ?', (component_id,)
    ).fetchone()
