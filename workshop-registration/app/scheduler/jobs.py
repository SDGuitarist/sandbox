import click
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from app.db import get_db
from app.email import send_email

WINDOW_7D = datetime(2026, 5, 23, 17, 0, 0, tzinfo=timezone.utc)
WINDOW_1D = datetime(2026, 5, 29, 17, 0, 0, tzinfo=timezone.utc)
WORKSHOP = datetime(2026, 5, 30, 17, 0, 0, tzinfo=timezone.utc)
WINDOW_POST = datetime(2026, 6, 1, 17, 0, 0, tzinfo=timezone.utc)


def register_commands(app):
    @app.cli.command("send-reminders")
    def send_reminders():
        """Send time-windowed reminder and post-workshop emails."""
        now = datetime.now(timezone.utc)

        with get_db() as conn:
            registrants = conn.execute(
                "SELECT id FROM registrants WHERE status = 'paid'"
            ).fetchall()

        templates = []
        if now >= WINDOW_POST:
            templates.append("post_workshop")
        if now >= WINDOW_1D and now < WORKSHOP:
            templates.append("reminder_1d")
        if now >= WINDOW_7D and now < WINDOW_1D:
            templates.append("reminder_7d")

        tasks = [(row["id"], t) for row in registrants for t in templates]
        if not tasks:
            click.echo("No emails to send.")
            return

        sent = 0
        failed = 0
        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {pool.submit(send_email, rid, tmpl): (rid, tmpl) for rid, tmpl in tasks}
            for future in futures:
                try:
                    if future.result():
                        sent += 1
                    else:
                        failed += 1
                except Exception:
                    failed += 1
        click.echo(f"Done: {sent} sent, {failed} failed out of {len(tasks)} total.")
