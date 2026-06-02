"""Testing blueprint — Claude API test execution and result viewing.

Routes:
    GET  /<int:prompt_id>       test_form   — Show test runner form
    POST /<int:prompt_id>       execute     — Run prompt against Claude API
    GET  /runs/<int:run_id>     view_run    — View a saved test run
"""

import json
import logging
import os
import time

import anthropic
from flask import Blueprint, abort, render_template, request

from app.database import get_db
from app.models import (
    create_test_run,
    get_latest_version_id,
    get_prompt,
    get_prompt_version,
    get_test_run,
    substitute_variables,
)

logger = logging.getLogger(__name__)

bp = Blueprint('testing', __name__, url_prefix='/testing')

AVAILABLE_MODELS = [
    ('claude-sonnet-4-5-20250514', 'Claude Sonnet 4.5'),
    ('claude-haiku-4-5-20251001', 'Claude Haiku 4.5'),
]

# Valid model identifiers for input validation (default to first if invalid)
_VALID_MODEL_IDS = {model_id for model_id, _ in AVAILABLE_MODELS}


@bp.route('/<int:prompt_id>')
def test_form(prompt_id):
    """GET /testing/<prompt_id> — Render the test runner form."""
    with get_db() as conn:
        prompt = get_prompt(conn, prompt_id)
        if prompt is None:
            abort(404)

        variables = json.loads(prompt['variables'])

        return render_template(
            'testing/run.html',
            prompt=prompt,
            variables=variables,
        )


@bp.route('/<int:prompt_id>', methods=['POST'])
def execute(prompt_id):
    """POST /testing/<prompt_id> — Execute prompt against Claude API.

    Reads variable values from form fields named var_<name>.
    Sends substituted prompt to Claude API, stores result as a test run,
    and renders the result page directly (no redirect).
    """
    with get_db() as conn:
        prompt = get_prompt(conn, prompt_id)
        if prompt is None:
            abort(404)

        # --- Collect variable values from form ---
        variable_names = json.loads(prompt['variables'])
        variables_used = {}
        for var_name in variable_names:
            variables_used[var_name] = request.form.get(f'var_{var_name}', '')

        # --- Validate model selection ---
        model_name = request.form.get('model', '')
        if model_name not in _VALID_MODEL_IDS:
            model_name = AVAILABLE_MODELS[0][0]  # Default to Sonnet

        # --- Substitute variables into prompts ---
        system_text = substitute_variables(prompt['system_prompt'], variables_used)
        user_text = substitute_variables(prompt['user_prompt'], variables_used)

        # --- Get the latest version for this prompt ---
        version_id = get_latest_version_id(conn, prompt_id)
        if version_id is None:
            abort(404)

        # --- Call Claude API ---
        api_key = os.environ.get('ANTHROPIC_API_KEY', '')

        if not api_key:
            # No API key configured — store error, don't crash
            run_id = create_test_run(
                conn,
                prompt_version_id=version_id,
                model_name=model_name,
                variables_used=variables_used,
                response_text=None,
                input_tokens=None,
                output_tokens=None,
                duration_ms=None,
                error='ANTHROPIC_API_KEY is not configured. Set it in your environment.',
            )
        else:
            # Create client per-request (not at module level — key may change)
            client = anthropic.Anthropic(api_key=api_key)

            start_ms = int(time.time() * 1000)
            try:
                response = client.messages.create(
                    model=model_name,
                    max_tokens=4096,
                    system=system_text,
                    messages=[{'role': 'user', 'content': user_text}],
                    timeout=60.0,
                )
                duration_ms = int(time.time() * 1000) - start_ms
                response_text = response.content[0].text if response.content else None
                input_tokens = response.usage.input_tokens
                output_tokens = response.usage.output_tokens
                error = None
            except anthropic.APITimeoutError:
                duration_ms = int(time.time() * 1000) - start_ms
                response_text = None
                input_tokens = None
                output_tokens = None
                error = (
                    'Request timed out after 60 seconds. '
                    'Try a shorter prompt or a faster model.'
                )
                logger.warning('Claude API timeout for prompt %d', prompt_id)
            except anthropic.APIConnectionError:
                duration_ms = int(time.time() * 1000) - start_ms
                response_text = None
                input_tokens = None
                output_tokens = None
                error = (
                    'Could not connect to Claude API. '
                    'Check your internet connection.'
                )
                logger.warning('Claude API connection error for prompt %d', prompt_id)
            except anthropic.APIStatusError as e:
                duration_ms = int(time.time() * 1000) - start_ms
                response_text = None
                input_tokens = None
                output_tokens = None
                # FC10: Never expose raw e.message to user
                error = (
                    f'API error ({e.status_code}). '
                    'Check your API key and try again.'
                )
                logger.error(
                    'Claude API status error for prompt %d: %s',
                    prompt_id,
                    str(e),
                )
            except Exception:
                duration_ms = int(time.time() * 1000) - start_ms
                response_text = None
                input_tokens = None
                output_tokens = None
                error = 'Unexpected error during API call. Check server logs.'
                logger.exception(
                    'Unexpected error calling Claude API for prompt %d',
                    prompt_id,
                )

            run_id = create_test_run(
                conn,
                prompt_version_id=version_id,
                model_name=model_name,
                variables_used=variables_used,
                response_text=response_text,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                duration_ms=duration_ms,
                error=error,
            )

        # --- Render result directly (no redirect) ---
        run = get_test_run(conn, run_id)

        return render_template(
            'testing/result.html',
            prompt=prompt,
            run=run,
        )


@bp.route('/runs/<int:run_id>')
def view_run(run_id):
    """GET /testing/runs/<run_id> — View a previously saved test run."""
    with get_db() as conn:
        run = get_test_run(conn, run_id)
        if run is None:
            abort(404)

        # Get the prompt via the version — test_runs links to prompt_versions,
        # and prompt_versions links to prompts.
        version = get_prompt_version(conn, run['prompt_version_id'])
        if version is None:
            abort(404)

        prompt = get_prompt(conn, version['prompt_id'])
        if prompt is None:
            abort(404)

        return render_template(
            'testing/result.html',
            prompt=prompt,
            run=run,
        )
