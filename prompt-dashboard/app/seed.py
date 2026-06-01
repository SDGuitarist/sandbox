import click
from flask.cli import with_appcontext
from app.database import get_db
from app.models import create_prompt


@click.command('seed')
@with_appcontext
def seed_command():
    """Insert development seed data."""
    with get_db() as conn:
        # Create 3 sample prompts with tags
        create_prompt(conn, 'Code Reviewer', 'Reviews code for bugs and improvements',
                      'You are an expert code reviewer. Be thorough but constructive.',
                      'Review this {{language}} code:\n\n{{code}}',
                      ['coding', 'review'])
        create_prompt(conn, 'Story Writer', 'Generates creative short stories',
                      'You are a creative fiction writer.',
                      'Write a short story about {{topic}} in the style of {{author}}.',
                      ['creative', 'writing'])
        create_prompt(conn, 'SQL Helper', 'Converts natural language to SQL queries',
                      'You are a SQL expert. Return only the SQL query, no explanation.',
                      'Convert this to a {{dialect}} SQL query: {{request}}',
                      ['coding', 'sql', 'database'])
    click.echo('Seed data inserted: 3 prompts, 5 tags.')


def register_seed_command(app):
    app.cli.add_command(seed_command)
