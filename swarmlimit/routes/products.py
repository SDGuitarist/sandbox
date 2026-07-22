"""Products blueprint (product route agent).

``Blueprint('products', __name__)`` with NO ``url_prefix``; every route declares
its FULL absolute path exactly as written in the Route Table (spec §4 / §Route
Table -> products). Pure JSON API.

Envelope contract (spec §4 / brief H4 -- emit these EXACT keys):
  * ``GET /products``            -> ``{"products": [ ... ]}``
  * ``POST /products`` (201) and ``GET /products/<int:pid>``
                                  -> ``{"product": { ...incl "id", "category_ids" }}``
  * every error via ``error(code, status)`` -> ``{"error": code, ...}``.

Auth (spec §6):
  * GET list + GET detail -> ``auth`` (any logged-in) via ``login_required``.
  * POST / PATCH / DELETE / PUT categories -> ``admin`` via
    ``role_required('admin')`` (its pinned two-branch contract already returns
    401 for anonymous, 403 for authenticated wrong-role -- see swarmlimit.auth).

Soft-delete semantics (spec §Model Functions / §3):
  * ``GET /products`` excludes soft-deleted rows (``list_products`` default).
  * ``GET /products/<int:pid>`` -> 404 if soft-deleted OR absent
    (``get_product`` returns None for both).
  * ``DELETE /products/<int:pid>`` -> ``soft_delete_product`` -> 200; **404 ONLY
    if the id never existed** (an already-soft-deleted product -> 200 idempotent
    no-op, a live product -> 200 setting ``deleted_at``).

Audit (spec §4): every create/update/delete/set-categories view calls
``record(...)`` EXACTLY once, AFTER the model call returns and has committed --
never inside a transaction. Class-A model writers autocommit, so "post-commit"
here means simply after the model call returns.

Validation (spec §3): sku+name non-empty; supplier exists; ``price_cents >= 0``
int; ``stock >= 0`` int; ``category_ids`` all exist (400); 409 on duplicate sku.
"""

from flask import Blueprint, request

from swarmlimit import error
from swarmlimit.auth import current_user, login_required, role_required
from swarmlimit.models.audit_models import record
from swarmlimit.models.category_models import get_category
from swarmlimit.models.product_models import (
    create_product,
    get_product,
    list_products,
    set_product_categories,
    soft_delete_product,
    update_product,
)
from swarmlimit.models.supplier_models import get_supplier

bp = Blueprint("products", __name__)


def _is_nonempty_str(value) -> bool:
    """True iff ``value`` is a non-empty string (bool excluded elsewhere)."""
    return isinstance(value, str) and bool(value)


def _is_nonneg_int(value) -> bool:
    """True iff ``value`` is a non-negative int (rejects bool and float)."""
    # ``bool`` is an ``int`` subclass -> reject it explicitly so True/False are
    # not accepted as 1/0 for price_cents/stock.
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _validate_category_ids(category_ids):
    """Return (ok, cleaned_list). ``ok`` is False when the input is malformed or
    any referenced category id does not exist.

    Accepts ``None`` (treated as no categories). Otherwise requires a list of
    ints, each referencing an existing category (else 400 per §3).
    """
    if category_ids is None:
        return True, []
    if not isinstance(category_ids, list):
        return False, []
    cleaned = []
    for cid in category_ids:
        if not isinstance(cid, int) or isinstance(cid, bool):
            return False, []
        if get_category(cid) is None:
            return False, []
        cleaned.append(cid)
    return True, cleaned


@bp.route("/products", methods=["GET"])
@login_required
def list_products_view():
    """List live products (soft-deleted excluded). Auth: any logged-in."""
    products = list_products()
    return {"products": products}, 200


@bp.route("/products", methods=["POST"])
@role_required("admin")
def create_product_view():
    """Create a product. Admin only. Returns 201 ``{"product": {...}}``.

    Validates sku+name non-empty, supplier exists, price_cents/stock non-negative
    ints, and all category_ids exist (§3). Duplicate sku -> 409 ``conflict``.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("validation", 400)

    sku = data.get("sku")
    name = data.get("name")
    supplier_id = data.get("supplier_id")
    price_cents = data.get("price_cents")
    stock = data.get("stock", 0)
    category_ids = data.get("category_ids")

    if not _is_nonempty_str(sku):
        return error("validation", 400)
    if not _is_nonempty_str(name):
        return error("validation", 400)
    if not isinstance(supplier_id, int) or isinstance(supplier_id, bool):
        return error("validation", 400)
    if not _is_nonneg_int(price_cents):
        return error("validation", 400)
    if not _is_nonneg_int(stock):
        return error("validation", 400)
    if get_supplier(supplier_id) is None:
        return error("validation", 400)

    ok, clean_category_ids = _validate_category_ids(category_ids)
    if not ok:
        return error("validation", 400)

    try:
        pid = create_product(
            sku=sku,
            name=name,
            supplier_id=supplier_id,
            price_cents=price_cents,
            stock=stock,
            category_ids=clean_category_ids,
        )
    except ValueError as exc:
        # 'sku exists' (UNIQUE) -> 409; 'supplier not found' -> validation (already
        # guarded above, but stay fail-closed on any other ValueError).
        if "sku" in str(exc):
            return error("conflict", 409, message=str(exc))
        return error("validation", 400, message=str(exc))

    # Post-commit audit (class-A create already persisted).
    record(current_user()["id"], "create", "product", pid)

    product = get_product(pid)
    return {"product": product}, 201


@bp.route("/products/<int:pid>", methods=["GET"])
@login_required
def get_product_view(pid):
    """Return one product. 404 if soft-deleted or absent. Auth: any logged-in."""
    product = get_product(pid)
    if product is None:
        return error("not_found", 404)
    return {"product": product}, 200


@bp.route("/products/<int:pid>", methods=["PATCH"])
@role_required("admin")
def update_product_view(pid):
    """Update whitelisted product fields (name/price_cents/stock/supplier_id).

    Admin only. 404 if the product does not exist (live or soft-deleted). 400 on
    malformed input. Returns 200 ``{"product": {...}}``.
    """
    # Existence check first (id must exist -- live OR soft-deleted).
    existing = get_product(pid, include_deleted=True)
    if existing is None:
        return error("not_found", 404)

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("validation", 400)

    allowed = ("name", "price_cents", "stock", "supplier_id")
    updates = {k: data[k] for k in allowed if k in data}
    if not updates:
        return error("validation", 400)

    if "name" in updates and not _is_nonempty_str(updates["name"]):
        return error("validation", 400)
    if "price_cents" in updates and not _is_nonneg_int(updates["price_cents"]):
        return error("validation", 400)
    if "stock" in updates and not _is_nonneg_int(updates["stock"]):
        return error("validation", 400)
    if "supplier_id" in updates:
        sid = updates["supplier_id"]
        if not isinstance(sid, int) or isinstance(sid, bool):
            return error("validation", 400)
        if get_supplier(sid) is None:
            return error("validation", 400)

    update_product(pid, **updates)

    # Post-commit audit (class-A update already persisted).
    record(current_user()["id"], "update", "product", pid)

    product = get_product(pid, include_deleted=True)
    return {"product": product}, 200


@bp.route("/products/<int:pid>", methods=["DELETE"])
@role_required("admin")
def delete_product_view(pid):
    """Soft-delete a product. Admin only.

    404 ONLY if the id never existed. An already-soft-deleted product -> 200
    (idempotent no-op); a live product -> 200 (sets ``deleted_at``).
    """
    # 404 ONLY if the id never existed -- include soft-deleted rows in the check.
    existing = get_product(pid, include_deleted=True)
    if existing is None:
        return error("not_found", 404)

    soft_delete_product(pid)

    # Post-commit audit (class-A soft-delete already persisted).
    record(current_user()["id"], "delete", "product", pid)

    return {"product": {"id": pid}}, 200


@bp.route("/products/<int:pid>/categories", methods=["PUT"])
@role_required("admin")
def set_product_categories_view(pid):
    """Replace a product's M2M category set. Admin only.

    ``category_ids`` must be a list of existing category ids (400 otherwise). 404
    if the product does not exist (live or soft-deleted). Returns 200
    ``{"product": {...}}``.
    """
    existing = get_product(pid, include_deleted=True)
    if existing is None:
        return error("not_found", 404)

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error("validation", 400)

    category_ids = data.get("category_ids")
    if category_ids is None or not isinstance(category_ids, list):
        return error("validation", 400)

    ok, clean_category_ids = _validate_category_ids(category_ids)
    if not ok:
        return error("validation", 400)

    set_product_categories(pid, clean_category_ids)

    # Post-commit audit (class-A category-set already persisted).
    record(current_user()["id"], "update", "product", pid)

    product = get_product(pid, include_deleted=True)
    return {"product": product}, 200
