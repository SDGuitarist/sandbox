"""
Email queue helpers -- owned by email-queue agent (26).

Ownership:
  - job_queue (UPDATE status): worker claims and updates via CTE+RETURNING
  - campaign_progress: worker writes after each job

The actual worker process lives in send_worker.py (separate from Flask).
All DB mutations go through app.models functions:
  - complete_job()
  - update_recipient_status()
  - increment_campaign_counter()
  - update_campaign_progress()
  - render_template_with_lead()

This module re-exports those functions for callers that reference app.email_queue.
"""

from app.models import (
    complete_job,
    update_recipient_status,
    increment_campaign_counter,
    update_campaign_progress,
    render_template_with_lead,
)

__all__ = [
    'complete_job',
    'update_recipient_status',
    'increment_campaign_counter',
    'update_campaign_progress',
    'render_template_with_lead',
]
