import os
from migrator.app import create_app

db_path = os.environ.get("MIGRATIONS_DB", "migrator.db")
migrations_dir = os.environ.get("MIGRATIONS_DIR", "migrations")

app = create_app(db_path=db_path, migrations_dir=migrations_dir)

if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug, port=5003)
