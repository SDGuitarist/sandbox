"""Cross-resource ext_ref uniqueness owner (shared-services).

Single authority for the cross-resource ``ext_ref`` uniqueness invariant: no
``ext_ref`` value may appear in ``orders`` UNION ``returns``. The per-table
``UNIQUE`` constraints on ``orders.ext_ref`` / ``returns.ext_ref`` are only
intra-table backstops; this SELECT-based guard is what enforces uniqueness
*across* the two resources.

Class-C in-tx read-only guard (spec §5): it runs on the caller-supplied
transaction ``conn`` (the SAME connection the class-B opener holds under
``BEGIN IMMEDIATE``), issues only a SELECT, writes nothing, and NEVER commits.
Called inside ``order_models.create_order`` and ``return_models.process_return``
BEFORE the respective insert.
"""


def assert_ext_ref_unique(conn, ext_ref) -> None:
    """Raise ``ValueError('ext_ref exists')`` if ``ext_ref`` already appears in
    ``orders`` OR ``returns``.

    Runs on the caller's in-transaction ``conn`` (no commit). Because the
    caller holds a ``BEGIN IMMEDIATE`` write lock, concurrent inserters
    serialize, so this read sees a consistent snapshot of both tables.
    """
    row = conn.execute(
        "SELECT 1 WHERE EXISTS (SELECT 1 FROM orders WHERE ext_ref = ?) "
        "OR EXISTS (SELECT 1 FROM returns WHERE ext_ref = ?)",
        (ext_ref, ext_ref),
    ).fetchone()
    if row is not None:
        raise ValueError("ext_ref exists")
