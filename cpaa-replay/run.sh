#!/usr/bin/env bash
set -euo pipefail

export FLASK_APP=app:create_app

exec flask run --host=127.0.0.1 --port="${PORT:-5000}"
