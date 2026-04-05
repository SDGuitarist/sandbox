import os
from dashboard.app import create_app

db_path = os.environ.get("DASHBOARD_DB", "dashboard.db")
app = create_app(db_path=db_path)

if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug, port=5004)
