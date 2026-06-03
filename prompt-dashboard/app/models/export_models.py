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
    prompts = conn.execute(
        '''SELECT p.*, i.name as industry_name
           FROM prompts p JOIN industries i ON p.industry_id = i.id
           WHERE p.user_id = ? ORDER BY p.created_at''',
        (user_id,)
    ).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Title', 'Industry', 'Completeness', 'Components', 'Created'])

    for prompt in prompts:
        components = conn.execute(
            '''SELECT cd.name, pc.content
               FROM prompt_components pc
               JOIN component_definitions cd ON pc.component_id = cd.id
               WHERE pc.prompt_id = ? ORDER BY cd.position''',
            (prompt['id'],)
        ).fetchall()
        # Decrypt once per component (P1 fix: was calling decrypt_field twice)
        decrypted = [(c['name'], decrypt_field(c['content'])) for c in components]
        comp_text = '; '.join(
            f"{name}: {content}" for name, content in decrypted if content.strip()
        )
        writer.writerow([
            prompt['title'], prompt['industry_name'],
            f"{prompt['completeness']:.0%}", comp_text, prompt['created_at']
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
