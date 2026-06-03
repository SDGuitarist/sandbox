import csv
import io
import json
from app.encryption import decrypt_field


def export_user_prompts_csv(conn, user_id):
    """Export a user's prompts as CSV string. Decrypts content.
    Returns: str (CSV content)
    Usage:
        csv_data = export_user_prompts_csv(conn, user_id)
    """
    # Single JOIN query to avoid N+1 (one query per prompt was the prior pattern).
    rows = conn.execute(
        '''SELECT p.id as prompt_id, p.title, p.completeness, p.created_at,
                  i.name as industry_name,
                  cd.name as component_name, cd.position,
                  pc.content
           FROM prompts p
           JOIN industries i ON p.industry_id = i.id
           LEFT JOIN prompt_components pc ON pc.prompt_id = p.id
           LEFT JOIN component_definitions cd ON pc.component_id = cd.id
           WHERE p.user_id = ?
           ORDER BY p.created_at, cd.position''',
        (user_id,)
    ).fetchall()

    # Group rows by prompt in Python
    prompts = {}
    for r in rows:
        pid = r['prompt_id']
        if pid not in prompts:
            prompts[pid] = {
                'title': r['title'],
                'industry_name': r['industry_name'],
                'completeness': r['completeness'],
                'created_at': r['created_at'],
                'components': [],
            }
        if r['component_name']:
            decrypted = decrypt_field(r['content']) if r['content'] else ''
            if decrypted.strip():
                prompts[pid]['components'].append(
                    f"{r['component_name']}: {decrypted}"
                )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Title', 'Industry', 'Completeness', 'Components', 'Created'])
    for p in prompts.values():
        writer.writerow([
            p['title'], p['industry_name'],
            f"{p['completeness']:.0%}",
            '; '.join(p['components']),
            p['created_at'],
        ])

    return output.getvalue()


def export_all_prompts_json(conn):
    """Admin: export all prompts as JSON string. Decrypts content.
    Returns: str (JSON)
    Usage:
        json_data = export_all_prompts_json(conn)
    """
    prompts = conn.execute(
        '''SELECT p.*, i.name as industry_name, u.username
           FROM prompts p
           JOIN industries i ON p.industry_id = i.id
           JOIN users u ON p.user_id = u.id
           ORDER BY p.created_at'''
    ).fetchall()

    result = []
    for prompt in prompts:
        components = conn.execute(
            '''SELECT cd.name, cd.cluster, pc.content
               FROM prompt_components pc
               JOIN component_definitions cd ON pc.component_id = cd.id
               WHERE pc.prompt_id = ? ORDER BY cd.position''',
            (prompt['id'],)
        ).fetchall()
        grade = conn.execute(
            'SELECT * FROM prompt_grades WHERE prompt_id = ?', (prompt['id'],)
        ).fetchone()

        result.append({
            'title': prompt['title'],
            'industry': prompt['industry_name'],
            'user': prompt['username'],
            'completeness': prompt['completeness'],
            'components': [
                {'name': c['name'], 'cluster': c['cluster'],
                 'content': decrypt_field(c['content'])}
                for c in components
            ],
            'grade': {
                'score': grade['score'],
                'worked_well': decrypt_field(grade['worked_well']),
                'needs_improvement': decrypt_field(grade['needs_improvement']),
                'notes': decrypt_field(grade['notes'])
            } if grade else None,
            'created_at': prompt['created_at']
        })

    return json.dumps(result, indent=2)
