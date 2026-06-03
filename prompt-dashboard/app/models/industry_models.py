"""Industry models for the prompt wizard.

Defines industries with per-component guidance text.
Industries are static data (no DB tables) — returned as dicts.
FC29: No conn.commit() — read-only module.
"""

# ---------------------------------------------------------------------------
# Industry Definitions
# ---------------------------------------------------------------------------

# Each industry has: id, name, description, icon, and guidance (per component)
INDUSTRIES = [
    {
        'id': 'software',
        'name': 'Software Engineering',
        'description': 'Code generation, debugging, architecture, and DevOps.',
        'icon': 'code',
        'guidance': {
            'role': 'Define the programming language, framework, and seniority level.',
            'persona': 'Technical and precise. Use code terminology naturally.',
            'expertise': 'Specify languages, frameworks, design patterns, and tools.',
            'background': 'Describe the codebase, tech stack, or project context.',
            'constraints': 'Note version requirements, forbidden patterns, or performance limits.',
            'audience': 'Specify developer experience level (junior, mid, senior).',
            'objective': 'State the exact coding task: write, refactor, debug, or review.',
            'instructions': 'Break the task into numbered steps with clear acceptance criteria.',
            'examples': 'Provide sample input/output pairs or code snippets.',
            'format': 'Specify code format: language, style guide, include tests or not.',
            'tone': 'Technical documentation style — clear, concise, no fluff.',
            'quality_criteria': 'Require error handling, type hints, docstrings, and tests.',
        },
    },
    {
        'id': 'marketing',
        'name': 'Marketing & Copywriting',
        'description': 'Ad copy, landing pages, email campaigns, and brand voice.',
        'icon': 'megaphone',
        'guidance': {
            'role': 'Define the marketing role: copywriter, strategist, or brand manager.',
            'persona': 'Match the brand voice — playful, authoritative, empathetic, etc.',
            'expertise': 'Specify industry knowledge: B2B SaaS, DTC, fintech, etc.',
            'background': 'Describe the product, target market, and campaign goals.',
            'constraints': 'Note word limits, brand guidelines, or compliance rules.',
            'audience': 'Define the target persona: demographics, pain points, desires.',
            'objective': 'State the deliverable: headline, email sequence, landing page, etc.',
            'instructions': 'Include structure (hook, body, CTA) and persuasion framework.',
            'examples': 'Show competitor examples or past high-performing copy.',
            'format': 'Specify format: email, social post, blog, ad copy with char limits.',
            'tone': 'Conversational, urgent, aspirational — match the brand.',
            'quality_criteria': 'Must include clear CTA, emotional hook, and benefit-led copy.',
        },
    },
    {
        'id': 'education',
        'name': 'Education & Training',
        'description': 'Lesson plans, explanations, quizzes, and curriculum design.',
        'icon': 'book',
        'guidance': {
            'role': 'Define the educator role: teacher, tutor, curriculum designer.',
            'persona': 'Patient, encouraging, and adaptive to learning pace.',
            'expertise': 'Specify subject area, grade level, and pedagogical approach.',
            'background': 'Describe student level, prior knowledge, and learning context.',
            'constraints': 'Note time limits, accessibility needs, or curriculum standards.',
            'audience': 'Define learner profile: age, level, learning style.',
            'objective': 'State the learning outcome: explain concept, create quiz, design lesson.',
            'instructions': 'Structure with scaffolding: build from simple to complex.',
            'examples': 'Provide worked examples that demonstrate the concept.',
            'format': 'Specify format: lesson plan, quiz, flashcards, or explanation.',
            'tone': 'Encouraging and clear — avoid jargon unless teaching it.',
            'quality_criteria': 'Must include learning checks, varied difficulty, and engagement.',
        },
    },
    {
        'id': 'creative',
        'name': 'Creative Writing',
        'description': 'Fiction, poetry, scripts, worldbuilding, and storytelling.',
        'icon': 'pen',
        'guidance': {
            'role': 'Define the writer role: novelist, poet, screenwriter, editor.',
            'persona': 'Match the literary voice: lyrical, gritty, whimsical, etc.',
            'expertise': 'Specify genre knowledge: sci-fi, romance, thriller, literary fiction.',
            'background': 'Describe the story world, characters, and narrative context.',
            'constraints': 'Note genre conventions, word count, or content boundaries.',
            'audience': 'Define the reader: age group, genre expectations, reading level.',
            'objective': 'State the creative task: write scene, develop character, outline plot.',
            'instructions': 'Include narrative structure: setup, conflict, resolution.',
            'examples': 'Provide style samples or reference works for tone matching.',
            'format': 'Specify format: prose, dialogue, screenplay format, or poetry form.',
            'tone': 'Match the genre and emotional register of the piece.',
            'quality_criteria': 'Must show (not tell), use sensory detail, and maintain voice.',
        },
    },
    {
        'id': 'data',
        'name': 'Data & Analytics',
        'description': 'Data analysis, SQL queries, visualizations, and reporting.',
        'icon': 'graph-up',
        'guidance': {
            'role': 'Define the analyst role: data analyst, BI developer, data scientist.',
            'persona': 'Precise and methodical. Explain statistical concepts clearly.',
            'expertise': 'Specify tools: SQL, Python/pandas, R, Tableau, Excel.',
            'background': 'Describe the dataset, schema, and business question.',
            'constraints': 'Note data privacy rules, query performance limits, or tool versions.',
            'audience': 'Specify who reads the analysis: executives, engineers, or analysts.',
            'objective': 'State the analytical task: write query, build dashboard, find insights.',
            'instructions': 'Structure analysis: define metric, gather data, analyze, conclude.',
            'examples': 'Provide sample data rows or expected output format.',
            'format': 'Specify output: SQL query, chart description, written report.',
            'tone': 'Data-driven and objective. Lead with findings, support with evidence.',
            'quality_criteria': 'Must include data validation, edge cases, and clear methodology.',
        },
    },
    {
        'id': 'general',
        'name': 'General Purpose',
        'description': 'Versatile prompts for any task or domain.',
        'icon': 'lightning',
        'guidance': {
            'role': 'Define what kind of assistant or expert the AI should be.',
            'persona': 'Describe the communication style you want.',
            'expertise': 'List any specific knowledge areas needed.',
            'background': 'Provide relevant context for the task.',
            'constraints': 'Note any rules or limitations.',
            'audience': 'Describe who will use or read the output.',
            'objective': 'Clearly state what you want the AI to do.',
            'instructions': 'Break the task into clear steps.',
            'examples': 'Show what good output looks like.',
            'format': 'Describe the desired output structure.',
            'tone': 'Specify the tone: formal, casual, technical, etc.',
            'quality_criteria': 'Define what "done well" means for this task.',
        },
    },
]


# ---------------------------------------------------------------------------
# Public Functions
# ---------------------------------------------------------------------------

def get_all_industries() -> list[dict]:
    """Return all industries as a list of dicts.

    Returns: list[dict] with keys: id, name, description, icon, guidance
    Usage:
        industries = get_all_industries()
    """
    return list(INDUSTRIES)


def get_industry(industry_id: str) -> dict | None:
    """Get a single industry by its string ID.

    Returns: dict or None if not found.
    Usage:
        industry = get_industry('software')
        if industry is None: abort(404)
    """
    for industry in INDUSTRIES:
        if industry['id'] == industry_id:
            return dict(industry)
    return None


def get_guidance_for_industry(industry_id: str) -> dict[str, str]:
    """Get per-component guidance text for an industry.

    Returns: dict mapping component_id -> guidance string.
             Empty dict if industry not found.
    Usage:
        guidance = get_guidance_for_industry('software')
        # guidance['role'] == 'Define the programming language...'
    """
    industry = get_industry(industry_id)
    if industry is None:
        return {}
    return dict(industry.get('guidance', {}))
