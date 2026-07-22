"""swarmlimit smoke harness.

Run as:
    python -m swarmlimit.smoke                         # full default suite
    python -m swarmlimit.smoke --case <name>           # a single Path-B case
    python -m swarmlimit.smoke --manifest <R>/planned-manifest.json
                                                       # full suite + manifest-equality + C2 report

The harness builds its OWN app via ``from swarmlimit import create_app`` against a throwaway
on-disk SQLite file at a NOT-YET-EXISTING child path of a ``tempfile.TemporaryDirectory()`` so
``create_app()``'s "init_db only if the DB file is absent" check fires and ``init_db()`` runs
exactly once (FC49: a real on-disk file, never ``:memory:``, never a pre-created tempfile whose
existence would make the absence check false and skip schema creation).

Manifest-equality is driven ONLY under ``--manifest``: the exercised (method, path) set is built
per-request from ``(request.method, request.url_rule.rule)`` captured in an ``after_request`` hook
(never inferred from ``app.url_map``), and compared against the manifest ``endpoints``. The report
is written to the manifest's parent directory as ``<R>/c2-smoke-report.md`` with a line-1
``STATUS: PASS|FAIL`` and expected-status-aware pass semantics (asserted negatives 400/401/403/404/
409 are EXPECTED and pass; only an unexpected/unasserted status mismatch fails C2).

NOTE: this module cannot be fully RUN until the route agents land (Wave 2); it is authored to the
converged spec, parse-checked at the Wave-0 gate (``python -m compileall swarmlimit``), and executed
at assembly C2.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import threading
from pathlib import Path

from flask import request

from swarmlimit import create_app

# Admin seed credentials (database agent seeds `admin@swarm.test` / `swarmpass` in init_db).
ADMIN_EMAIL = "admin@swarm.test"
ADMIN_PASSWORD = "swarmpass"

# The asserted-negative status codes: a test case may deliberately drive one of these and PASS.
# Any status a case does NOT explicitly assert is compared against 2xx-expectation only.
ASSERTED_NEGATIVES = frozenset({400, 401, 403, 404, 409})

# Module-level exercised-set: EVERY request the suite drives records the exact
# (request.method, request.url_rule.rule) pair Flask matched. Populated by the after_request hook
# registered in build_app(); NEVER inferred from app.url_map. Requests that matched no rule
# (request.url_rule is None — e.g. a 404 on an unknown path) are skipped.
_EXERCISED: set[tuple[str, str]] = set()

# Ordered log of every driven request's observed status + whether the case asserted it.
# Each entry: {"method", "path", "status", "expected", "matched"}.
_OBSERVATIONS: list[dict] = []


class SmokeError(AssertionError):
    """A smoke assertion failed."""


# --------------------------------------------------------------------------------------------------
# App / client construction
# --------------------------------------------------------------------------------------------------

def build_app():
    """Build a fresh app against a throwaway temp DB whose file does NOT yet exist.

    Returns (app, tmpdir). The caller MUST keep `tmpdir` alive for the app's lifetime and call
    `tmpdir.cleanup()` when done (holding it open keeps the on-disk SQLite file around).
    """
    tmpdir = tempfile.TemporaryDirectory()
    # A child path of the temp dir that does NOT yet exist → create_app()'s absence check fires
    # → init_db() runs exactly once. NEVER a pre-created NamedTemporaryFile/mkstemp path (FC49/P0-4).
    db_path = os.path.join(tmpdir.name, "swarmlimit.sqlite")
    assert not os.path.exists(db_path), "temp DB path must NOT pre-exist (init_db must run)"

    # assembly-fix 083 [H9, cross-agent config seam]: create_app reads SECRET_KEY from ENV and
    # runs its fail-closed check BEFORE applying the config dict, so passing SECRET_KEY in config
    # is ineffective -> the working-app suite could not build (RuntimeError). Ensure a key is in
    # env. The SECRET_KEY-fail-closed case pops+restores SECRET_KEY itself, so this does not weaken it.
    os.environ.setdefault("SECRET_KEY", "smoke-083-secret-key")
    app = create_app({"DATABASE": db_path, "TESTING": True})

    @app.after_request
    def _capture(response):  # pragma: no cover - exercised at C2
        # Record what smoke ACTUALLY drove, per request (the manifest-equality source of truth).
        if request.url_rule is not None:
            _EXERCISED.add((request.method, request.url_rule.rule))
        return response

    return app, tmpdir


def _reset_observations() -> None:
    _EXERCISED.clear()
    _OBSERVATIONS.clear()


# --------------------------------------------------------------------------------------------------
# Request helpers (thin wrappers over the Flask test client that log observations)
# --------------------------------------------------------------------------------------------------

def _record(method: str, path: str, status: int, expected: int | None) -> None:
    matched = True if expected is None else (status == expected)
    _OBSERVATIONS.append(
        {"method": method, "path": path, "status": status, "expected": expected, "matched": matched}
    )


def _csrf_headers(token: str | None) -> dict:
    return {"X-CSRF-Token": token} if token else {}


def _req(client, method: str, path: str, *, json_body=None, token=None, expected=None):
    """Issue a request via the test client, log the observation, return the response."""
    headers = _csrf_headers(token)
    fn = getattr(client, method.lower())
    if method in ("GET", "DELETE"):
        resp = fn(path, headers=headers)
    else:
        resp = fn(path, json=(json_body if json_body is not None else {}), headers=headers)
    _record(method, path, resp.status_code, expected)
    return resp


def _login(client, email: str, password: str) -> str:
    """Log in; assert 200 + csrf_token in the body; return the token."""
    resp = _req(client, "POST", "/auth/login", json_body={"email": email, "password": password},
                expected=200)
    if resp.status_code != 200:
        raise SmokeError(f"login({email}) expected 200, got {resp.status_code}")
    body = resp.get_json()
    token = (body or {}).get("csrf_token")
    if not token:
        raise SmokeError(f"login({email}) response missing csrf_token: {body!r}")
    return token


def _logout(client, token: str) -> None:
    _req(client, "POST", "/auth/logout", token=token, expected=200)


def _admin_session(client) -> str:
    return _login(client, ADMIN_EMAIL, ADMIN_PASSWORD)


def _json(resp):
    body = resp.get_json()
    if body is None:
        raise SmokeError(f"expected JSON body, got status={resp.status_code} data={resp.data!r}")
    return body


def _assert(cond, msg: str) -> None:
    if not cond:
        raise SmokeError(msg)


def _assert_no_object_leak(body) -> None:
    """No stringified-dict / [object Object] leakage anywhere in the serialized body."""
    raw = json.dumps(body)
    _assert("[object Object]" not in raw, "response leaks [object Object]")
    _assert("{'" not in raw, "response leaks a stringified Python dict ({'...)")


# --------------------------------------------------------------------------------------------------
# Fixture builders (drive real endpoints to reach a known state)
# --------------------------------------------------------------------------------------------------

def _create_supplier(client, token, name="Acme Supply") -> int:
    resp = _req(client, "POST", "/suppliers", json_body={"name": name}, token=token, expected=201)
    _assert(resp.status_code == 201, f"create supplier expected 201, got {resp.status_code}")
    return int(_json(resp)["supplier"]["id"])


def _create_category(client, token, name="Widgets") -> int:
    resp = _req(client, "POST", "/categories", json_body={"name": name}, token=token, expected=201)
    _assert(resp.status_code == 201, f"create category expected 201, got {resp.status_code}")
    return int(_json(resp)["category"]["id"])


def _create_product(client, token, supplier_id, category_ids, *, sku, name="Gadget",
                    price_cents=1000, stock=5) -> int:
    resp = _req(client, "POST", "/products", token=token, expected=201, json_body={
        "sku": sku, "name": name, "supplier_id": supplier_id,
        "price_cents": price_cents, "stock": stock, "category_ids": category_ids,
    })
    _assert(resp.status_code == 201, f"create product expected 201, got {resp.status_code}")
    return int(_json(resp)["product"]["id"])


def _create_order(client, token, ext_ref, items, *, user_id=None, expected=201) -> "object":
    payload = {"ext_ref": ext_ref, "items": items}
    if user_id is not None:
        payload["user_id"] = user_id
    return _req(client, "POST", "/orders", json_body=payload, token=token, expected=expected)


def _create_shipment(client, token, oid, *, expected=201) -> "object":
    return _req(client, "POST", f"/orders/{oid}/shipments", json_body={"carrier": "UPS"},
                token=token, expected=expected)


def _advance(client, token, sid, to_status, *, expected) -> "object":
    return _req(client, "POST", f"/shipments/{sid}/advance", json_body={"to_status": to_status},
                token=token, expected=expected)


def _get_product(client, token, pid, *, expected) -> "object":
    return _req(client, "GET", f"/products/{pid}", token=token, expected=expected)


def _list_products(client, token) -> "object":
    return _req(client, "GET", "/products", token=token, expected=200)


def _process_return(client, token, order_id, ext_ref, refund_cents, *, reason="defective",
                    expected) -> "object":
    return _req(client, "POST", "/returns", token=token, expected=expected, json_body={
        "order_id": order_id, "ext_ref": ext_ref, "reason": reason, "refund_cents": refund_cents,
    })


def _db_count(app, table: str, where: str = "", params: tuple = ()) -> int:
    """COUNT(*) on a table via a direct app-context DB connection (read-only)."""
    from swarmlimit.database import get_db
    with app.app_context():
        conn = get_db()
        sql = f"SELECT COUNT(*) AS n FROM {table}"
        if where:
            sql += f" WHERE {where}"
        row = conn.execute(sql, params).fetchone()
        return int(row["n"])


def _db_scalar(app, sql: str, params: tuple = ()):
    from swarmlimit.database import get_db
    with app.app_context():
        conn = get_db()
        row = conn.execute(sql, params).fetchone()
        return None if row is None else row[0]


# A standard fixture: admin session + supplier + category + a product with known stock, plus a
# delivered shipment on a fresh order — enough to exercise most Path-B cases.
def _fixture_delivered_order(client, app, token, *, sku, ext_ref, qty=1, stock=5, price_cents=1000):
    supplier_id = _create_supplier(client, token, name=f"S-{sku}")
    category_id = _create_category(client, token, name=f"C-{sku}")
    pid = _create_product(client, token, supplier_id, [category_id], sku=sku, stock=stock,
                          price_cents=price_cents)
    order_resp = _create_order(client, token, ext_ref, [{"product_id": pid, "qty": qty}])
    _assert(order_resp.status_code == 201, "fixture order create failed")
    oid = int(_json(order_resp)["order"]["id"])
    ship_resp = _create_shipment(client, token, oid)
    sid = int(_json(ship_resp)["shipment"]["id"])
    _advance(client, token, sid, "shipped", expected=200)
    _advance(client, token, sid, "delivered", expected=200)
    return {"supplier_id": supplier_id, "category_id": category_id, "product_id": pid,
            "order_id": oid, "shipment_id": sid, "qty": qty, "price_cents": price_cents}


# --------------------------------------------------------------------------------------------------
# The 10 Path-B --cases
# --------------------------------------------------------------------------------------------------

def case_state_machine_legal(client, app) -> None:
    token = _admin_session(client)
    fx_sup = _create_supplier(client, token, name="S-legal")
    fx_cat = _create_category(client, token, name="C-legal")
    pid = _create_product(client, token, fx_sup, [fx_cat], sku="SKU-legal", stock=3)
    order_resp = _create_order(client, token, "ext-legal", [{"product_id": pid, "qty": 1}])
    oid = int(_json(order_resp)["order"]["id"])
    ship_resp = _create_shipment(client, token, oid)
    sid = int(_json(ship_resp)["shipment"]["id"])
    r1 = _advance(client, token, sid, "shipped", expected=200)
    _assert(r1.status_code == 200, "pending->shipped expected 200")
    r2 = _advance(client, token, sid, "delivered", expected=200)
    _assert(r2.status_code == 200, "shipped->delivered expected 200")
    # audit rows written for the two advances.
    audit_n = _db_count(app, "audit_logs", "action = ? AND entity_type = ?", ("advance", "shipment"))
    _assert(audit_n >= 2, f"expected >=2 advance audit rows, got {audit_n}")


def case_state_machine_illegal(client, app) -> None:
    token = _admin_session(client)

    def _status(sid):
        return _db_scalar(app, "SELECT status FROM shipments WHERE id = ?", (sid,))

    def _fresh_delivered():
        sup = _create_supplier(client, token, name=f"S-ill-{_status_counter[0]}")
        cat = _create_category(client, token, name=f"C-ill-{_status_counter[0]}")
        pid = _create_product(client, token, sup, [cat], sku=f"SKU-ill-{_status_counter[0]}", stock=3)
        order = _create_order(client, token, f"ext-ill-{_status_counter[0]}",
                              [{"product_id": pid, "qty": 1}])
        oid = int(_json(order)["order"]["id"])
        ship = _create_shipment(client, token, oid)
        sid = int(_json(ship)["shipment"]["id"])
        _status_counter[0] += 1
        return sid

    _status_counter = [0]

    # (a) delivered->pending → 409, status stays 'delivered'.
    sid = _fresh_delivered()
    _advance(client, token, sid, "shipped", expected=200)
    _advance(client, token, sid, "delivered", expected=200)
    r = _advance(client, token, sid, "pending", expected=409)
    _assert(r.status_code == 409, "delivered->pending expected 409")
    _assert(_status(sid) == "delivered", "status must stay 'delivered' after illegal delivered->pending")

    # (b) pending->delivered (skip shipped) → 409, status stays 'pending'.
    sid = _fresh_delivered()
    r = _advance(client, token, sid, "delivered", expected=409)
    _assert(r.status_code == 409, "pending->delivered skip expected 409")
    _assert(_status(sid) == "pending", "status must stay 'pending' after illegal skip")

    # (c) advance -> 'returned' from EVERY source status ∈ {pending, shipped, delivered} → 409,
    #     status stays the source.
    # source = pending
    sid = _fresh_delivered()
    r = _advance(client, token, sid, "returned", expected=409)
    _assert(r.status_code == 409, "pending->returned expected 409")
    _assert(_status(sid) == "pending", "status must stay 'pending' after ->returned")
    # source = shipped
    sid = _fresh_delivered()
    _advance(client, token, sid, "shipped", expected=200)
    r = _advance(client, token, sid, "returned", expected=409)
    _assert(r.status_code == 409, "shipped->returned expected 409")
    _assert(_status(sid) == "shipped", "status must stay 'shipped' after ->returned")
    # source = delivered
    sid = _fresh_delivered()
    _advance(client, token, sid, "shipped", expected=200)
    _advance(client, token, sid, "delivered", expected=200)
    r = _advance(client, token, sid, "returned", expected=409)
    _assert(r.status_code == 409, "delivered->returned expected 409")
    _assert(_status(sid) == "delivered", "status must stay 'delivered' after ->returned")


def case_uniqueness_ok(client, app) -> None:
    token = _admin_session(client)
    fx = _fixture_delivered_order(client, app, token, sku="SKU-uok", ext_ref="ext-uok-order",
                                  stock=3, price_cents=1000)
    # A distinct ext_ref on the return → both order and return persist.
    r = _process_return(client, token, fx["order_id"], "ext-uok-return",
                        refund_cents=fx["price_cents"], expected=201)
    _assert(r.status_code == 201, f"unique return ext_ref expected 201, got {r.status_code}")
    ret_n = _db_count(app, "returns", "ext_ref = ?", ("ext-uok-return",))
    _assert(ret_n == 1, "return row must persist for a unique ext_ref")


def case_uniqueness_collision(client, app) -> None:
    token = _admin_session(client)
    fx = _fixture_delivered_order(client, app, token, sku="SKU-ucol", ext_ref="ext-ucol-order",
                                  stock=3, price_cents=1000)
    before = _db_count(app, "returns")
    # Reuse the order's ext_ref on the return → 409, no return row.
    r = _process_return(client, token, fx["order_id"], "ext-ucol-order",
                        refund_cents=fx["price_cents"], expected=409)
    _assert(r.status_code == 409, f"ext_ref collision expected 409, got {r.status_code}")
    after = _db_count(app, "returns")
    _assert(after == before, "COUNT(returns) must be unchanged after an ext_ref collision")


def case_soft_delete(client, app) -> None:
    token = _admin_session(client)
    sup = _create_supplier(client, token, name="S-sd")
    cat = _create_category(client, token, name="C-sd")
    pid = _create_product(client, token, sup, [cat], sku="SKU-sd", stock=5, price_cents=1000)
    # Place an order referencing it so we can prove order_items are preserved after delete.
    order = _create_order(client, token, "ext-sd", [{"product_id": pid, "qty": 1}])
    _assert(order.status_code == 201, "soft-delete fixture order failed")
    items_before = _db_count(app, "order_items", "product_id = ?", (pid,))
    _assert(items_before >= 1, "expected order_items referencing the product")
    # Soft-delete → 200; deleted_at set.
    d = _req(client, "DELETE", f"/products/{pid}", token=token, expected=200)
    _assert(d.status_code == 200, "soft-delete expected 200")
    deleted_at = _db_scalar(app, "SELECT deleted_at FROM products WHERE id = ?", (pid,))
    _assert(deleted_at is not None, "deleted_at must be set after soft-delete")
    # Absent from GET /products.
    listed = _json(_list_products(client, token))
    ids = [int(p["id"]) for p in listed.get("products", [])]
    _assert(pid not in ids, "soft-deleted product must be absent from GET /products")
    # GET /products/<pid> → 404 (soft-deleted hidden).
    _get_product(client, token, pid, expected=404)
    # Historical order_items preserved.
    items_after = _db_count(app, "order_items", "product_id = ?", (pid,))
    _assert(items_after == items_before, "order_items must be preserved after soft-delete")


def case_soft_delete_order(client, app) -> None:
    token = _admin_session(client)
    sup = _create_supplier(client, token, name="S-sdo")
    cat = _create_category(client, token, name="C-sdo")
    pid = _create_product(client, token, sup, [cat], sku="SKU-sdo", stock=5, price_cents=1000)
    _req(client, "DELETE", f"/products/{pid}", token=token, expected=200)
    stock_before = _db_scalar(app, "SELECT stock FROM products WHERE id = ?", (pid,))
    orders_before = _db_count(app, "orders")
    items_before = _db_count(app, "order_items")
    # create_order referencing the soft-deleted product → 409, no order/items/stock delta.
    r = _create_order(client, token, "ext-sdo", [{"product_id": pid, "qty": 1}], expected=409)
    _assert(r.status_code == 409, f"order on deleted product expected 409, got {r.status_code}")
    _assert(_db_count(app, "orders") == orders_before, "no order row on rejected create_order")
    _assert(_db_count(app, "order_items") == items_before, "no order_items on rejected create_order")
    stock_after = _db_scalar(app, "SELECT stock FROM products WHERE id = ?", (pid,))
    _assert(stock_after == stock_before, "stock VALUE must be unchanged on rejected create_order")


def case_process_return(client, app) -> None:
    token = _admin_session(client)
    fx = _fixture_delivered_order(client, app, token, sku="SKU-pr", ext_ref="ext-pr-order",
                                  qty=2, stock=5, price_cents=1000)
    pid, sid, oid = fx["product_id"], fx["shipment_id"], fx["order_id"]
    stock_after_order = _db_scalar(app, "SELECT stock FROM products WHERE id = ?", (pid,))
    r = _process_return(client, token, oid, "ext-pr-return",
                        refund_cents=fx["price_cents"] * fx["qty"], expected=201)
    _assert(r.status_code == 201, f"process_return expected 201, got {r.status_code}")
    # All four writes visible together.
    _assert(_db_count(app, "returns", "order_id = ?", (oid,)) == 1, "return row missing")
    ship_status = _db_scalar(app, "SELECT status FROM shipments WHERE id = ?", (sid,))
    _assert(ship_status == "returned", "shipment must be 'returned'")
    restocked = _db_scalar(app, "SELECT stock FROM products WHERE id = ?", (pid,))
    _assert(restocked == stock_after_order + fx["qty"], "stock must be restocked by qty")
    _assert(_db_count(app, "payments", "order_id = ? AND kind = 'refund'", (oid,)) == 1,
            "refund payment row missing")


def case_process_return_rollback(client, app) -> None:
    import swarmlimit.models.return_models as rm
    token = _admin_session(client)
    fx = _fixture_delivered_order(client, app, token, sku="SKU-prr", ext_ref="ext-prr-order",
                                  qty=2, stock=5, price_cents=1000)
    pid, sid, oid = fx["product_id"], fx["shipment_id"], fx["order_id"]

    returns_before = _db_count(app, "returns")
    payments_before = _db_count(app, "payments")
    ship_before = _db_scalar(app, "SELECT status FROM shipments WHERE id = ?", (sid,))
    stock_before = _db_scalar(app, "SELECT stock FROM products WHERE id = ?", (pid,))
    _assert(ship_before == "delivered", "fixture shipment should be 'delivered' before rollback")

    # Inject a fault that raises AFTER add_refund_in_tx (the last of the four writes), inside the
    # process_return transaction. The raise must propagate OUT of the `with transaction()` block
    # → the context manager ROLLBACKs all four writes.
    class _Boom(RuntimeError):
        pass

    def _raiser():
        raise _Boom("injected mid-transaction fault (post add_refund_in_tx)")

    rm._TX_FAULT = _raiser
    raised = False
    try:
        # Drive a VALID process_return unit; the seam fires and the exception surfaces.
        _process_return(client, token, oid, "ext-prr-return",
                        refund_cents=fx["price_cents"] * fx["qty"], expected=None)
    except _Boom:
        raised = True
    finally:
        rm._TX_FAULT = None  # ALWAYS reset the seam.

    _assert(raised, "_TX_FAULT must propagate OUT of process_return's transaction (→ ROLLBACK)")
    # INSERT rollback (count compare).
    _assert(_db_count(app, "returns") == returns_before, "returns count must be unchanged (rollback)")
    _assert(_db_count(app, "payments") == payments_before, "payments count must be unchanged (rollback)")
    # UPDATE rollback (VALUE compare).
    ship_after = _db_scalar(app, "SELECT status FROM shipments WHERE id = ?", (sid,))
    _assert(ship_after == "delivered", "shipment status VALUE must still be 'delivered' (rollback)")
    stock_after = _db_scalar(app, "SELECT stock FROM products WHERE id = ?", (pid,))
    _assert(stock_after == stock_before, "product stock VALUE must be unchanged (rollback)")


def case_process_return_guard_refund(client, app) -> None:
    token = _admin_session(client)
    fx = _fixture_delivered_order(client, app, token, sku="SKU-prgr", ext_ref="ext-prgr-order",
                                  qty=1, stock=3, price_cents=1000)
    pid, sid, oid = fx["product_id"], fx["shipment_id"], fx["order_id"]
    returns_before = _db_count(app, "returns")
    payments_before = _db_count(app, "payments")
    ship_before = _db_scalar(app, "SELECT status FROM shipments WHERE id = ?", (sid,))
    stock_before = _db_scalar(app, "SELECT stock FROM products WHERE id = ?", (pid,))
    # refund_cents exceeding the order's remaining original (order_total = 1000) → 409, zero writes.
    r = _process_return(client, token, oid, "ext-prgr-return",
                        refund_cents=fx["price_cents"] + 1, expected=409)
    _assert(r.status_code == 409, f"refund>original expected 409, got {r.status_code}")
    _assert(_db_count(app, "returns") == returns_before, "no return row (guard fires pre-write)")
    _assert(_db_count(app, "payments") == payments_before, "no refund row (guard fires pre-write)")
    _assert(_db_scalar(app, "SELECT status FROM shipments WHERE id = ?", (sid,)) == ship_before,
            "shipment status VALUE unchanged (guard pre-write)")
    _assert(_db_scalar(app, "SELECT stock FROM products WHERE id = ?", (pid,)) == stock_before,
            "product stock VALUE unchanged (guard pre-write)")


def case_process_return_guard_shipment(client, app) -> None:
    token = _admin_session(client)
    # A fresh order whose shipment is NOT delivered (leave it 'pending').
    sup = _create_supplier(client, token, name="S-prgs")
    cat = _create_category(client, token, name="C-prgs")
    pid = _create_product(client, token, sup, [cat], sku="SKU-prgs", stock=3, price_cents=1000)
    order = _create_order(client, token, "ext-prgs-order", [{"product_id": pid, "qty": 1}])
    oid = int(_json(order)["order"]["id"])
    ship = _create_shipment(client, token, oid)  # status 'pending', NOT delivered
    sid = int(_json(ship)["shipment"]["id"])

    returns_before = _db_count(app, "returns")
    payments_before = _db_count(app, "payments")
    ship_before = _db_scalar(app, "SELECT status FROM shipments WHERE id = ?", (sid,))
    stock_before = _db_scalar(app, "SELECT stock FROM products WHERE id = ?", (pid,))
    # process_return on a not-delivered shipment → 409, zero writes.
    r = _process_return(client, token, oid, "ext-prgs-return", refund_cents=1000, expected=409)
    _assert(r.status_code == 409, f"shipment-not-delivered expected 409, got {r.status_code}")
    _assert(_db_count(app, "returns") == returns_before, "no return row (state guard pre-write)")
    _assert(_db_count(app, "payments") == payments_before, "no refund row (state guard pre-write)")
    _assert(_db_scalar(app, "SELECT status FROM shipments WHERE id = ?", (sid,)) == ship_before,
            "shipment status VALUE unchanged (state guard)")
    _assert(_db_scalar(app, "SELECT stock FROM products WHERE id = ?", (pid,)) == stock_before,
            "product stock VALUE unchanged (state guard)")


PATH_B_CASES = {
    "state-machine-legal": case_state_machine_legal,
    "state-machine-illegal": case_state_machine_illegal,
    "uniqueness-ok": case_uniqueness_ok,
    "uniqueness-collision": case_uniqueness_collision,
    "soft-delete": case_soft_delete,
    "soft-delete-order": case_soft_delete_order,
    "process-return": case_process_return,
    "process-return-rollback": case_process_return_rollback,
    "process-return-guard-refund": case_process_return_guard_refund,
    "process-return-guard-shipment": case_process_return_guard_shipment,
}


# --------------------------------------------------------------------------------------------------
# Core (default-suite) cases
# --------------------------------------------------------------------------------------------------

def core_create_order_values(client, app) -> None:
    """create_order commits atomically; response has integer ids and no object/dict leakage."""
    token = _admin_session(client)
    sup = _create_supplier(client, token, name="S-cov")
    cat = _create_category(client, token, name="C-cov")
    pid = _create_product(client, token, sup, [cat], sku="SKU-cov", stock=5, price_cents=1500)
    resp = _create_order(client, token, "ext-cov", [{"product_id": pid, "qty": 2}])
    _assert(resp.status_code == 201, f"create_order expected 201, got {resp.status_code}")
    body = _json(resp)
    _assert_no_object_leak(body)
    order = body["order"]
    _assert(isinstance(order["id"], int), "order id must be an integer")
    _assert(order["id"] == int(order["id"]), "order id integer round-trip")
    # order_items + stock committed atomically.
    _assert(_db_count(app, "order_items", "order_id = ?", (int(order["id"]),)) == 1,
            "order_items must be committed with the order")
    _assert(_db_scalar(app, "SELECT stock FROM products WHERE id = ?", (pid,)) == 3,
            "stock must be decremented atomically (5 - 2 = 3)")


def core_concurrency_stock_race(client, app) -> None:
    """Two create_order calls race the last unit of stock: exactly one wins, the other → 409."""
    token = _admin_session(client)
    sup = _create_supplier(client, token, name="S-race")
    cat = _create_category(client, token, name="C-race")
    pid = _create_product(client, token, sup, [cat], sku="SKU-race", stock=1, price_cents=1000)

    results: dict[str, int] = {}
    barrier = threading.Barrier(2)

    def _place(tag, ext):
        # Each thread uses its own test client (own request context) but the SAME app/DB.
        c = app.test_client()
        tok = _login(c, ADMIN_EMAIL, ADMIN_PASSWORD)
        barrier.wait()
        resp = c.post("/orders", json={"ext_ref": ext, "items": [{"product_id": pid, "qty": 1}]},
                      headers={"X-CSRF-Token": tok})
        results[tag] = resp.status_code

    t1 = threading.Thread(target=_place, args=("a", "ext-race-a"))
    t2 = threading.Thread(target=_place, args=("b", "ext-race-b"))
    t1.start(); t2.start(); t1.join(); t2.join()

    codes = sorted(results.values())
    _assert(codes == [201, 409], f"stock race must be exactly one 201 + one 409, got {codes}")
    final_stock = _db_scalar(app, "SELECT stock FROM products WHERE id = ?", (pid,))
    _assert(final_stock == 0, f"final stock must be 0 (last unit taken once), got {final_stock}")
    _assert(final_stock >= 0, "final stock must be non-negative")
    # Record the two driven POST /orders for exercised-set completeness (test-client requests above
    # bypass _req logging; register the rule explicitly since they DID drive it).
    _EXERCISED.add(("POST", "/orders"))


def core_create_order_mid_tx_rollback(client, app) -> None:
    """Forced fault after the first item write rolls back the whole create_order unit (value-compare)."""
    import swarmlimit.models.order_models as om
    token = _admin_session(client)
    sup = _create_supplier(client, token, name="S-cotx")
    cat = _create_category(client, token, name="C-cotx")
    pid = _create_product(client, token, sup, [cat], sku="SKU-cotx", stock=5, price_cents=1000)
    orders_before = _db_count(app, "orders")
    items_before = _db_count(app, "order_items")
    stock_before = _db_scalar(app, "SELECT stock FROM products WHERE id = ?", (pid,))

    class _Boom(RuntimeError):
        pass

    def _raiser():
        raise _Boom("injected mid-tx fault (post first order_item insert)")

    om._TX_FAULT = _raiser
    raised = False
    try:
        _create_order(client, token, "ext-cotx", [{"product_id": pid, "qty": 1}], expected=None)
    except _Boom:
        raised = True
    finally:
        om._TX_FAULT = None

    _assert(raised, "_TX_FAULT must propagate OUT of create_order's transaction (→ ROLLBACK)")
    _assert(_db_count(app, "orders") == orders_before, "orders count unchanged (rollback)")
    _assert(_db_count(app, "order_items") == items_before, "order_items count unchanged (rollback)")
    stock_after = _db_scalar(app, "SELECT stock FROM products WHERE id = ?", (pid,))
    _assert(stock_after == stock_before, "product stock VALUE unchanged (rollback, value compare)")


def core_idor_404(client, app) -> None:
    """A customer requesting another customer's order → 404 (not 403)."""
    # Register + login two customers.
    _req(client, "POST", "/auth/register",
         json_body={"email": "c1@swarm.test", "password": "password1", "name": "C1"}, expected=201)
    _req(client, "POST", "/auth/register",
         json_body={"email": "c2@swarm.test", "password": "password2", "name": "C2"}, expected=201)

    # c1 places an order (needs an admin-created product first).
    admin_tok = _admin_session(client)
    sup = _create_supplier(client, admin_tok, name="S-idor")
    cat = _create_category(client, admin_tok, name="C-idor")
    pid = _create_product(client, admin_tok, sup, [cat], sku="SKU-idor", stock=5, price_cents=1000)
    _logout(client, admin_tok)

    tok1 = _login(client, "c1@swarm.test", "password1")
    order = _create_order(client, tok1, "ext-idor", [{"product_id": pid, "qty": 1}])
    oid = int(_json(order)["order"]["id"])
    _logout(client, tok1)

    tok2 = _login(client, "c2@swarm.test", "password2")
    r = _req(client, "GET", f"/orders/{oid}", token=tok2, expected=404)
    _assert(r.status_code == 404, f"IDOR read must be 404 (not 403), got {r.status_code}")
    _logout(client, tok2)


def core_admin_403(client, app) -> None:
    """A customer POSTing to an admin route → 403."""
    _req(client, "POST", "/auth/register",
         json_body={"email": "cust403@swarm.test", "password": "password1", "name": "Cust"},
         expected=201)
    tok = _login(client, "cust403@swarm.test", "password1")
    r = _req(client, "POST", "/suppliers", json_body={"name": "Nope"}, token=tok, expected=403)
    _assert(r.status_code == 403, f"customer on admin route must be 403, got {r.status_code}")
    _logout(client, tok)


def core_anon_401(client, app) -> None:
    """An anonymous request to a protected route → 401 (even a mutating/admin one; auth precedes CSRF)."""
    r_get = _req(client, "GET", "/orders", expected=401)
    _assert(r_get.status_code == 401, f"anon GET /orders must be 401, got {r_get.status_code}")
    # Anonymous mutating request → 401 (auth precedes CSRF; never 400 csrf, never 403).
    r_post = _req(client, "POST", "/suppliers", json_body={"name": "X"}, expected=401)
    _assert(r_post.status_code == 401, f"anon POST /suppliers must be 401, got {r_post.status_code}")


def core_csrf_400(client, app) -> None:
    """An authenticated mutating request that omits X-CSRF-Token → 400 csrf."""
    token = _admin_session(client)  # establish a session; keep the real token for later requests
    # Same authenticated session, but omit the header on a mutating request → 400 csrf.
    r = _req(client, "POST", "/suppliers", json_body={"name": "NoToken"}, token=None, expected=400)
    _assert(r.status_code == 400, f"authed mutation without CSRF must be 400, got {r.status_code}")
    body = _json(r)
    _assert(body.get("error") == "csrf", f"expected error 'csrf', got {body!r}")
    _logout(client, token)


def core_secret_key_fail_closed(client, app) -> None:
    """create_app() raises when SECRET_KEY is unset and FLASK_ENV != development."""
    saved_secret = os.environ.pop("SECRET_KEY", None)
    saved_env = os.environ.get("FLASK_ENV")
    os.environ["FLASK_ENV"] = "production"
    raised = False
    try:
        create_app()
    except Exception:
        raised = True
    finally:
        if saved_secret is not None:
            os.environ["SECRET_KEY"] = saved_secret
        if saved_env is None:
            os.environ.pop("FLASK_ENV", None)
        else:
            os.environ["FLASK_ENV"] = saved_env
    _assert(raised, "create_app() must raise when SECRET_KEY unset and FLASK_ENV != development")


def core_register_role_ignored(client, app) -> None:
    """Public register with role=admin → a customer (201, no session); login + admin route → 403."""
    resp = _req(client, "POST", "/auth/register", expected=201, json_body={
        "email": "sneaky@swarm.test", "password": "password1", "name": "Sneaky", "role": "admin",
    })
    _assert(resp.status_code == 201, f"register expected 201, got {resp.status_code}")
    # Registration does NOT establish a session → an immediate admin POST without login is 401.
    role = _db_scalar(app, "SELECT role FROM users WHERE email = ?", ("sneaky@swarm.test",))
    _assert(role == "customer", f"public register must create a customer, got role={role!r}")
    # Now log in and read csrf_token from the login body, then POST an admin route → 403.
    tok = _login(client, "sneaky@swarm.test", "password1")
    r = _req(client, "POST", "/products", token=tok, expected=403, json_body={
        "sku": "SKU-x", "name": "X", "supplier_id": 1, "price_cents": 100, "stock": 1,
    })
    _assert(r.status_code == 403, f"self-registered 'admin' must be 403 on an admin route, got {r.status_code}")
    _logout(client, tok)


def core_shipment_unique(client, app) -> None:
    """A 2nd POST /orders/<oid>/shipments → 409, no row — incl. after the first is 'returned'."""
    token = _admin_session(client)
    fx = _fixture_delivered_order(client, app, token, sku="SKU-shipuniq", ext_ref="ext-shipuniq",
                                  qty=1, stock=3, price_cents=1000)
    oid = fx["order_id"]
    ships_before = _db_count(app, "shipments", "order_id = ?", (oid,))
    _assert(ships_before == 1, "fixture must have exactly one shipment")
    # 2nd shipment on the same order → 409, no new row.
    r = _create_shipment(client, token, oid, expected=409)
    _assert(r.status_code == 409, f"2nd shipment expected 409, got {r.status_code}")
    _assert(_db_count(app, "shipments", "order_id = ?", (oid,)) == 1,
            "no 2nd shipment row may be created")
    # Return the order (shipment → 'returned'), then a 2nd shipment STILL 409 (no fresh mint).
    _process_return(client, token, oid, "ext-shipuniq-return", refund_cents=fx["price_cents"],
                    expected=201)
    r2 = _create_shipment(client, token, oid, expected=409)
    _assert(r2.status_code == 409, "2nd shipment after 'returned' must still be 409")
    _assert(_db_count(app, "shipments", "order_id = ?", (oid,)) == 1,
            "still exactly one shipment after a return")
    _logout(client, token)


def core_supplier_in_use_409(client, app) -> None:
    """DELETE /suppliers/<sid> with products → 409 conflict (FK RESTRICT), deletes nothing."""
    token = _admin_session(client)
    sup = _create_supplier(client, token, name="S-inuse")
    cat = _create_category(client, token, name="C-inuse")
    _create_product(client, token, sup, [cat], sku="SKU-inuse", stock=1, price_cents=100)
    before = _db_count(app, "suppliers", "id = ?", (sup,))
    r = _req(client, "DELETE", f"/suppliers/{sup}", token=token, expected=409)
    _assert(r.status_code == 409, f"delete supplier-in-use expected 409, got {r.status_code}")
    _assert(_db_count(app, "suppliers", "id = ?", (sup,)) == before,
            "supplier must not be deleted while in use")
    _logout(client, token)


def core_manifest_coverage(client, app) -> None:
    """Drive the remaining GET endpoints not covered by other cases so the exercised set == manifest.

    The Path-B + core cases above already exercise most write endpoints; this case rounds out the
    read/list endpoints (and PATCH/PUT/DELETE variants) so every one of the 31 manifest endpoints is
    hit at least once by the per-request capture hook.
    """
    token = _admin_session(client)
    sup = _create_supplier(client, token, name="S-cover")
    cat = _create_category(client, token, name="C-cover")
    pid = _create_product(client, token, sup, [cat], sku="SKU-cover", stock=5, price_cents=1000)
    order = _create_order(client, token, "ext-cover", [{"product_id": pid, "qty": 1}])
    oid = int(_json(order)["order"]["id"])
    ship = _create_shipment(client, token, oid)
    sid = int(_json(ship)["shipment"]["id"])

    # --- reads / lists ---
    _req(client, "GET", "/suppliers", token=token, expected=200)
    _req(client, "GET", f"/suppliers/{sup}", token=token, expected=200)
    _req(client, "GET", "/categories", token=token, expected=200)
    _req(client, "GET", f"/categories/{cat}", token=token, expected=200)
    _req(client, "GET", "/products", token=token, expected=200)
    _req(client, "GET", f"/products/{pid}", token=token, expected=200)
    _req(client, "GET", "/orders", token=token, expected=200)
    _req(client, "GET", f"/orders/{oid}", token=token, expected=200)
    _req(client, "GET", f"/shipments/{sid}", token=token, expected=200)
    _req(client, "GET", "/returns", token=token, expected=200)
    _req(client, "GET", "/payments", token=token, expected=200)
    _req(client, "GET", "/audit", token=token, expected=200)

    # --- mutations rounding out the manifest surface ---
    _req(client, "PATCH", f"/suppliers/{sup}", json_body={"name": "S-cover-2"}, token=token, expected=200)
    _req(client, "PATCH", f"/categories/{cat}", json_body={"name": "C-cover-2"}, token=token, expected=200)
    _req(client, "PATCH", f"/products/{pid}", json_body={"price_cents": 1100}, token=token, expected=200)
    _req(client, "PUT", f"/products/{pid}/categories", json_body={"category_ids": [cat]},
         token=token, expected=200)

    # A refund payment so GET /payments/<pid> is a live row: deliver + return the order.
    _advance(client, token, sid, "shipped", expected=200)
    _advance(client, token, sid, "delivered", expected=200)
    ret = _process_return(client, token, oid, "ext-cover-return", refund_cents=1000, expected=201)
    _assert(ret.status_code == 201, "coverage return must succeed")
    pay_id = _db_scalar(app, "SELECT id FROM payments WHERE order_id = ? AND kind = 'refund'", (oid,))
    _assert(pay_id is not None, "coverage refund payment must exist")
    _req(client, "GET", f"/payments/{int(pay_id)}", token=token, expected=200)
    ret_id = _db_scalar(app, "SELECT id FROM returns WHERE order_id = ?", (oid,))
    _req(client, "GET", f"/returns/{int(ret_id)}", token=token, expected=200)

    # DELETE endpoints: a category delete (unused → 200) exercises DELETE /categories/<cid>;
    # DELETE /suppliers/<sid> and DELETE /products/<pid> are already exercised by other cases,
    # but hit an unused supplier + a spare product here to be self-contained.
    spare_cat = _create_category(client, token, name="C-spare")
    _req(client, "DELETE", f"/categories/{spare_cat}", token=token, expected=200)
    spare_sup = _create_supplier(client, token, name="S-spare")
    _req(client, "DELETE", f"/suppliers/{spare_sup}", token=token, expected=200)
    spare_pid = _create_product(client, token, sup, [cat], sku="SKU-spare", stock=1, price_cents=10)
    _req(client, "DELETE", f"/products/{spare_pid}", token=token, expected=200)
    _logout(client, token)


# Core cases that need a live app + routes (run in the full/default suite and under --manifest).
CORE_CASES = [
    core_create_order_values,
    core_concurrency_stock_race,
    core_create_order_mid_tx_rollback,
    core_idor_404,
    core_admin_403,
    core_anon_401,
    core_csrf_400,
    core_register_role_ignored,
    core_shipment_unique,
    core_supplier_in_use_409,
    core_manifest_coverage,
]


# --------------------------------------------------------------------------------------------------
# Manifest handling
# --------------------------------------------------------------------------------------------------

def _canonical_hash(manifest: dict) -> str:
    """SHA-256 over the canonicalized JSON with the content_hash field removed.

    Canonicalization = json.dumps(payload, sort_keys=True, separators=(",", ":")) utf-8 — the SAME
    form the freeze step used, so the comparison is well-defined regardless of on-disk formatting.
    """
    payload = {k: v for k, v in manifest.items() if k != "content_hash"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _load_manifest(manifest_path: str) -> dict:
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    expected = manifest.get("content_hash")
    actual = _canonical_hash(manifest)
    if expected != actual:
        raise SmokeError(
            f"manifest content_hash mismatch: stored={expected!r} recomputed={actual!r}"
        )
    return manifest


def _manifest_endpoint_set(manifest: dict) -> set[tuple[str, str]]:
    return {(e["method"], e["path"]) for e in manifest["endpoints"]}


# --------------------------------------------------------------------------------------------------
# Suite runners
# --------------------------------------------------------------------------------------------------

def _run_single_case(name: str) -> None:
    if name not in PATH_B_CASES:
        raise SystemExit(f"unknown --case {name!r}; valid: {', '.join(sorted(PATH_B_CASES))}")
    app, tmpdir = build_app()
    try:
        _reset_observations()
        with app.test_client() as client:
            PATH_B_CASES[name](client, app)
    finally:
        tmpdir.cleanup()


def _run_full_suite() -> tuple[bool, list[str]]:
    """Run every Path-B case + every core case in one fresh app. Returns (ok, failure_messages)."""
    app, tmpdir = build_app()
    failures: list[str] = []
    try:
        _reset_observations()
        with app.test_client() as client:
            for name, fn in PATH_B_CASES.items():
                try:
                    fn(client, app)
                except Exception as exc:  # noqa: BLE001 - collect every failure
                    failures.append(f"path-b case {name}: {exc}")
            for fn in CORE_CASES:
                try:
                    fn(client, app)
                except Exception as exc:  # noqa: BLE001
                    failures.append(f"core case {fn.__name__}: {exc}")
    finally:
        # The DB-count assertions and the app object are what we need; snapshot before cleanup.
        exercised_snapshot = set(_EXERCISED)
        tmpdir.cleanup()
        # Re-populate the module set so a subsequent manifest-equality check can read it.
        _EXERCISED.clear()
        _EXERCISED.update(exercised_snapshot)
    return (len(failures) == 0, failures)


# --------------------------------------------------------------------------------------------------
# C2 report (only under --manifest)
# --------------------------------------------------------------------------------------------------

def _write_c2_report(report_dir: Path, *, status_pass: bool, exercised: set[tuple[str, str]],
                     planned: set[tuple[str, str]], suite_failures: list[str]) -> Path:
    planned_minus_exercised = sorted(planned - exercised)
    exercised_minus_planned = sorted(exercised - planned)
    unexpected = [o for o in _OBSERVATIONS if not o["matched"]]

    report_path = report_dir / "c2-smoke-report.md"
    lines: list[str] = []
    lines.append(f"STATUS: {'PASS' if status_pass else 'FAIL'}")
    lines.append("")
    lines.append("# swarmlimit C2 smoke report")
    lines.append("")
    lines.append(f"- planned endpoints: {len(planned)}")
    lines.append(f"- exercised endpoints: {len(exercised)}")
    lines.append(f"- planned_minus_exercised: {len(planned_minus_exercised)}")
    lines.append(f"- exercised_minus_planned: {len(exercised_minus_planned)}")
    lines.append(f"- suite failures: {len(suite_failures)}")
    lines.append(f"- unexpected/unasserted status mismatches: {len(unexpected)}")
    lines.append("")

    lines.append("## planned_minus_exercised")
    if planned_minus_exercised:
        for method, path in planned_minus_exercised:
            lines.append(f"- {method} {path}")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## exercised_minus_planned")
    if exercised_minus_planned:
        for method, path in exercised_minus_planned:
            lines.append(f"- {method} {path}")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## exercised set")
    for method, path in sorted(exercised):
        lines.append(f"- {method} {path}")
    lines.append("")

    lines.append("## suite failures")
    if suite_failures:
        for f in suite_failures:
            lines.append(f"- {f}")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## unexpected status mismatches (asserted negatives 400/401/403/404/409 are EXPECTED)")
    if unexpected:
        for o in unexpected:
            lines.append(
                f"- {o['method']} {o['path']}: observed {o['status']}, expected {o['expected']}"
            )
    else:
        lines.append("- (none)")
    lines.append("")

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def _run_with_manifest(manifest_path: str) -> bool:
    manifest = _load_manifest(manifest_path)
    planned = _manifest_endpoint_set(manifest)
    report_dir = Path(manifest_path).resolve().parent

    ok, suite_failures = _run_full_suite()
    exercised = set(_EXERCISED)

    planned_minus_exercised = planned - exercised
    exercised_minus_planned = exercised - planned
    unexpected = [o for o in _OBSERVATIONS if not o["matched"]]

    # Expected-status-aware C2 pass rule (the ONE contract):
    #   PASS iff no suite failures AND both endpoint-set deltas empty AND no unexpected status.
    status_pass = (
        ok
        and not planned_minus_exercised
        and not exercised_minus_planned
        and not unexpected
    )

    report_path = _write_c2_report(
        report_dir,
        status_pass=status_pass,
        exercised=exercised,
        planned=planned,
        suite_failures=suite_failures,
    )
    print(f"C2 smoke report written to {report_path}")
    print(f"STATUS: {'PASS' if status_pass else 'FAIL'}")
    if not status_pass:
        if suite_failures:
            print(f"  {len(suite_failures)} suite failure(s)")
        if planned_minus_exercised:
            print(f"  planned_minus_exercised: {sorted(planned_minus_exercised)}")
        if exercised_minus_planned:
            print(f"  exercised_minus_planned: {sorted(exercised_minus_planned)}")
        if unexpected:
            print(f"  {len(unexpected)} unexpected status mismatch(es)")
    return status_pass


def _run_default() -> bool:
    """Plain no-arg run: full suite, print pass/fail. No <R> source → no report, no manifest-equality."""
    ok, failures = _run_full_suite()
    if ok:
        print("STATUS: PASS")
        print(f"  {len(PATH_B_CASES)} path-b cases + {len(CORE_CASES)} core cases passed")
    else:
        print("STATUS: FAIL")
        for f in failures:
            print(f"  {f}")
    return ok


# --------------------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m swarmlimit.smoke",
                                     description="swarmlimit smoke harness")
    parser.add_argument("--case", help="run a single Path-B case by name", default=None)
    parser.add_argument("--manifest", help="path to <R>/planned-manifest.json (runs C2 + report)",
                        default=None)
    args = parser.parse_args(argv)

    if args.case is not None and args.manifest is not None:
        parser.error("--case and --manifest are mutually exclusive")

    if args.case is not None:
        try:
            _run_single_case(args.case)
        except Exception as exc:  # noqa: BLE001
            print(f"CASE FAIL {args.case}: {exc}", file=sys.stderr)
            return 1
        print(f"CASE PASS {args.case}")
        return 0

    if args.manifest is not None:
        return 0 if _run_with_manifest(args.manifest) else 1

    return 0 if _run_default() else 1


if __name__ == "__main__":
    raise SystemExit(main())
