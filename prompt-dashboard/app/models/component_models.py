"""Component models for the prompt wizard.

Defines the 12 prompt components grouped into 4 clusters.
Components are static data (no DB tables) — returned as dicts.
FC29: No conn.commit() — read-only module.
"""

# ---------------------------------------------------------------------------
# Component Definitions
# ---------------------------------------------------------------------------

# Each component has: id, name, description, placeholder, cluster
COMPONENTS = [
    # Cluster: identity
    {
        'id': 'role',
        'name': 'Role',
        'description': 'Who the AI should act as (e.g., "senior Python developer").',
        'placeholder': 'You are a senior Python developer with 10 years of experience...',
        'cluster': 'identity',
    },
    {
        'id': 'persona',
        'name': 'Persona',
        'description': 'Personality traits and communication style.',
        'placeholder': 'You communicate in a friendly, patient tone and use analogies...',
        'cluster': 'identity',
    },
    {
        'id': 'expertise',
        'name': 'Expertise',
        'description': 'Specific domain knowledge the AI should draw on.',
        'placeholder': 'You have deep expertise in Flask, SQLite, and REST API design...',
        'cluster': 'identity',
    },
    # Cluster: context
    {
        'id': 'background',
        'name': 'Background',
        'description': 'Relevant context or situation the AI needs to understand.',
        'placeholder': 'The user is building a small web app for personal use...',
        'cluster': 'context',
    },
    {
        'id': 'constraints',
        'name': 'Constraints',
        'description': 'Limitations, rules, or boundaries the AI must follow.',
        'placeholder': 'Do not use external libraries beyond the standard library...',
        'cluster': 'context',
    },
    {
        'id': 'audience',
        'name': 'Audience',
        'description': 'Who will read or use the AI output.',
        'placeholder': 'The audience is beginner developers learning Python...',
        'cluster': 'context',
    },
    # Cluster: task
    {
        'id': 'objective',
        'name': 'Objective',
        'description': 'The main goal or task the AI should accomplish.',
        'placeholder': 'Write a function that validates email addresses...',
        'cluster': 'task',
    },
    {
        'id': 'instructions',
        'name': 'Instructions',
        'description': 'Step-by-step directions for completing the task.',
        'placeholder': '1. Parse the input string\n2. Check for @ symbol\n3. Validate domain...',
        'cluster': 'task',
    },
    {
        'id': 'examples',
        'name': 'Examples',
        'description': 'Sample inputs and expected outputs to guide the AI.',
        'placeholder': 'Input: "user@example.com" -> Output: valid\nInput: "not-an-email" -> Output: invalid',
        'cluster': 'task',
    },
    # Cluster: output
    {
        'id': 'format',
        'name': 'Format',
        'description': 'How the output should be structured (e.g., JSON, markdown, list).',
        'placeholder': 'Return the result as a JSON object with keys: valid, reason...',
        'cluster': 'output',
    },
    {
        'id': 'tone',
        'name': 'Tone',
        'description': 'The desired tone of the output (formal, casual, technical).',
        'placeholder': 'Use a professional but approachable tone...',
        'cluster': 'output',
    },
    {
        'id': 'quality_criteria',
        'name': 'Quality Criteria',
        'description': 'Standards the output must meet to be considered good.',
        'placeholder': 'The code must include error handling, type hints, and docstrings...',
        'cluster': 'output',
    },
]

# Cluster metadata
CLUSTERS = {
    'identity': {
        'name': 'Identity',
        'description': 'Define who the AI is and what it knows.',
        'order': 0,
    },
    'context': {
        'name': 'Context',
        'description': 'Provide background, constraints, and audience.',
        'order': 1,
    },
    'task': {
        'name': 'Task',
        'description': 'Specify the objective, instructions, and examples.',
        'order': 2,
    },
    'output': {
        'name': 'Output',
        'description': 'Define the format, tone, and quality standards.',
        'order': 3,
    },
}


# ---------------------------------------------------------------------------
# Public Functions
# ---------------------------------------------------------------------------

def get_all_components() -> list[dict]:
    """Return all 12 components as a flat list of dicts.

    Returns: list[dict] with keys: id, name, description, placeholder, cluster
    Usage:
        components = get_all_components()
        # len(components) == 12
    """
    return list(COMPONENTS)


def get_components_grouped() -> dict[str, list[dict]]:
    """Return components grouped by cluster name.

    Returns: dict mapping cluster name -> list of component dicts,
             ordered by cluster order (identity, context, task, output).
    Usage:
        grouped = get_components_grouped()
        # grouped['identity'] == [role, persona, expertise]
        # grouped['context'] == [background, constraints, audience]
        # grouped['task'] == [objective, instructions, examples]
        # grouped['output'] == [format, tone, quality_criteria]
    """
    grouped: dict[str, list[dict]] = {}
    for cluster_id in sorted(CLUSTERS, key=lambda c: CLUSTERS[c]['order']):
        grouped[cluster_id] = [
            comp for comp in COMPONENTS if comp['cluster'] == cluster_id
        ]
    return grouped
