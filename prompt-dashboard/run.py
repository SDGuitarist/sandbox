# Run with: .venv/bin/python run.py
from app import create_app

app = create_app()
app.run(host='127.0.0.1', port=5050, debug=True, threaded=True)
# threaded=True REQUIRED — without it, Claude API calls (up to 60s)
# block the single-threaded dev server, freezing the entire UI.
# SQLite WAL mode + per-request connections (flask.g) are thread-safe.
