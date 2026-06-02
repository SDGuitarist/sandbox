# Run with: .venv/bin/python run.py
import os
from app import create_app

app = create_app()
app.run(host='127.0.0.1', port=5050,
        debug=os.environ.get('FLASK_DEBUG', '0') == '1',
        threaded=True)
# threaded=True REQUIRED — without it, Claude API calls (up to 60s)
# block the single-threaded dev server, freezing the entire UI.
# SQLite WAL mode + per-request connections (flask.g) are thread-safe.
