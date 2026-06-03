import click
from flask import current_app
from app.database import get_db
from app.models.auth_models import create_admin_user, create_user
from app.models.template_models import create_template, save_template_component
from app.models.prompt_models import create_prompt
from app.models.grading_models import save_grade
from app.encryption import encrypt_field


def register_seed_command(app):
    @app.cli.command('seed')
    def seed_db():
        """Seed the database with initial data."""
        conn = get_db()

        # Check if already seeded
        if conn.execute('SELECT COUNT(*) FROM users').fetchone()[0] > 0:
            click.echo('Database already seeded.')
            return

        # 1. Seed component definitions (12 components, 4 clusters)
        components = [
            (1, 'Role', 'Your Reality', 1, 'Define who you are in this context', 'I am a [role] who...'),
            (2, 'Background', 'Your Reality', 2, 'Relevant experience and expertise', 'My background includes...'),
            (3, 'Client Context', 'Your Reality', 3, 'Who you are working for and their situation', 'My client is...'),
            (4, 'Task', 'Your Assignment', 4, 'What specific task needs to be done', 'I need to...'),
            (5, 'Goal', 'Your Assignment', 5, 'The desired outcome of this task', 'The goal is to...'),
            (6, 'Audience', 'Your Assignment', 6, 'Who will consume the output', 'The audience is...'),
            (7, 'Key Complexity', 'Your Voice', 7, 'The main challenge or nuance', 'The key complexity is...'),
            (8, 'Tone', 'Your Voice', 8, 'The voice and style for the output', 'Use a [tone] tone...'),
            (9, 'Avoid', 'Your Voice', 9, 'What to stay away from', 'Avoid...'),
            (10, 'Definition of Done', 'Your Contract', 10, 'How to know when the task is complete', 'Done means...'),
            (11, 'Format', 'Your Contract', 11, 'Structure and format of the output', 'Format as...'),
            (12, 'Process', 'Your Contract', 12, 'Steps or approach to follow', 'Follow these steps...'),
        ]
        for comp_id, name, cluster, position, description, placeholder in components:
            conn.execute(
                '''INSERT INTO component_definitions (id, name, cluster, position, description, placeholder_text)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (comp_id, name, cluster, position, description, placeholder)
            )
        # No conn.commit() -- autocommit=True handles each INSERT

        # 2. Seed industries (4+)
        industries = [
            (1, 'Marketing & Advertising', 'Campaigns, copy, branding, social media'),
            (2, 'Healthcare & Wellness', 'Patient communication, health content, compliance'),
            (3, 'Technology & SaaS', 'Product docs, user guides, developer content'),
            (4, 'Education & Training', 'Curriculum, course materials, assessments'),
            (5, 'Finance & Professional Services', 'Reports, analysis, client communication'),
        ]
        for ind_id, name, description in industries:
            conn.execute(
                'INSERT INTO industries (id, name, description) VALUES (?, ?, ?)',
                (ind_id, name, description)
            )
        # No conn.commit() -- autocommit=True

        # 3. Seed users (1 admin, 1 normal)
        admin_id = create_admin_user(conn, 'alex', 'alex@amplifyai.com', 'admin-password-123')
        user_id = create_user(conn, 'workshop_user', 'user@example.com', 'user-password-123')

        # 4. Seed one template (Marketing Brief)
        template_id = create_template(conn, 'Marketing Campaign Brief', 'A starter template for marketing campaigns', 1, admin_id)
        save_template_component(conn, template_id, 1, 'I am a senior marketing strategist')
        save_template_component(conn, template_id, 4, 'Create a comprehensive marketing campaign brief')
        save_template_component(conn, template_id, 6, 'Marketing team and client stakeholders')
        save_template_component(conn, template_id, 11, 'Professional brief document with sections for objectives, target audience, messaging, channels, timeline, and budget')

        # 5. Seed 5 graded example prompts
        example_prompts = [
            ('Email Campaign for Product Launch', 1, [
                (1, 'Senior email marketing specialist'), (4, 'Write a 5-email drip campaign for a SaaS product launch'),
                (5, 'Generate 40% open rate and 5% click-through'), (6, 'B2B decision makers in mid-market companies'),
                (8, 'Professional but approachable'), (10, 'Five complete emails with subject lines, preview text, and body'),
                (11, 'One email per section with clear headers'),
            ], 4, 'Strong subject lines, good segmentation', 'CTA could be more specific', 'Used for Q3 campaign'),
            ('Patient Education Brochure', 2, [
                (1, 'Health communication specialist'), (2, 'MPH with 10 years in patient education'),
                (3, 'Regional hospital system'), (4, 'Create a diabetes management brochure'),
                (6, 'Patients newly diagnosed with Type 2 diabetes'), (7, 'Must be readable at 6th grade level'),
                (8, 'Warm, supportive, non-clinical'), (9, 'Medical jargon, scare tactics'),
                (10, 'Brochure content ready for design team'), (11, 'Tri-fold brochure format'),
            ], 5, 'Perfect reading level, empathetic tone', 'Could include more visual cues', 'Best example so far'),
            ('API Documentation Guide', 3, [
                (1, 'Technical writer'), (4, 'Document REST API endpoints'),
                (5, 'Developers can integrate within 30 minutes'), (6, 'Junior to mid-level developers'),
                (10, 'Complete endpoint documentation with examples'), (11, 'OpenAPI-style with code samples'),
                (12, 'Start with authentication, then CRUD operations'),
            ], 3, 'Good structure', 'Missing error response examples', 'Needs another pass'),
            ('Course Syllabus Builder', 4, [
                (1, 'Curriculum designer'), (2, 'EdD, 15 years in higher education'),
                (4, 'Design a 12-week online course syllabus'), (5, 'Students complete with measurable skills'),
                (6, 'Adult learners returning to education'), (8, 'Encouraging, structured'),
                (11, 'Week-by-week breakdown with objectives and assessments'),
            ], 4, 'Well-structured progression', 'Assessment rubrics need detail', 'Good starting template'),
            ('Quarterly Financial Report', 5, [
                (1, 'Financial analyst'), (3, 'Mid-size professional services firm'),
                (4, 'Write executive summary for Q2 financial report'), (5, 'Board understands financial position in 5 minutes'),
                (6, 'Board of directors, non-financial executives'), (7, 'Translate complex data into actionable insights'),
                (8, 'Authoritative, concise'), (9, 'Technical accounting terminology'),
                (10, 'One-page executive summary with key metrics'), (11, 'Bullet points with trend arrows'),
                (12, 'Open with headline metric, then trends, then outlook'),
            ], 5, 'Excellent conciseness', 'Minor formatting tweaks', 'Used as template for Q3'),
        ]

        for title, industry_id, comp_data, score, worked, needs, notes in example_prompts:
            prompt_id = create_prompt(conn, title, industry_id, user_id, comp_data)
            save_grade(conn, prompt_id, score, worked, needs, notes)

        click.echo('Database seeded successfully.')
