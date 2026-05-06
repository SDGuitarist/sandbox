---
title: init_db() Wipes Live Data -- Never Call It to Query
date: 2026-05-05
tags: [lead-scraper, database, data-loss]
failure_class: destructive-operation
---

## Problem

After two successful scrape runs (568 + 204 = 772 leads), all data was lost. The database was empty.

## Root Cause

To check lead counts after the scrape, a Python script called `init_db()` from `db.py` before querying. `init_db()` recreates the database schema from scratch, which drops and recreates tables -- wiping all existing data.

## Fix

**Never call `init_db()` to inspect data.** To query the database, connect directly:

```python
import sqlite3
conn = sqlite3.connect('leads.db')
conn.row_factory = sqlite3.Row
total = conn.execute('SELECT COUNT(*) FROM leads').fetchone()[0]
```

Or use the CLI: `sqlite3 leads.db "SELECT COUNT(*) FROM leads;"`

## Prevention

- `init_db()` should only be called at application startup (inside `run.py main()`), never in ad-hoc scripts
- Ideally, `init_db()` should use `CREATE TABLE IF NOT EXISTS` instead of dropping tables -- but that's a code change for another day
- Before any database operation, ask: "Does this function write or just read?"

## Cost

772 leads lost. Recovered ~734 by re-running both keyword sets in a single combined scrape. Some leads may have been lost due to Apify result variation.
