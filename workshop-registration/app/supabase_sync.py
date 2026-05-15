import os
import time
import logging
import threading
from datetime import datetime, timezone
from supabase import create_client

logger = logging.getLogger(__name__)
_client = None
_client_lock = threading.Lock()


def _get_client():
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                url = os.environ.get("SUPABASE_URL")
                key = os.environ.get("SUPABASE_SERVICE_KEY")
                if url and key:
                    _client = create_client(url, key)
    return _client


def sync_registrant(registrant_id: int):
    thread = threading.Thread(target=_sync_impl, args=(registrant_id,), daemon=True)
    thread.start()


def _sync_impl(registrant_id: int):
    from app.db import get_db
    from app.models import get_registrant

    client = _get_client()
    if client is None:
        logger.warning("Supabase not configured, skipping sync")
        return

    with get_db() as conn:
        reg = get_registrant(conn, registrant_id)
        if reg is None:
            return

    row = {
        "id": reg["id"],
        "status": reg["status"],
        "role": reg["role"],
        "created_at": reg["created_at"],
        "paid_at": reg["paid_at"],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    for attempt in range(3):
        try:
            client.table("registrants_realtime").upsert(row).execute()
            return
        except Exception as e:
            logger.error(f"Supabase sync attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                time.sleep(2 ** attempt)
