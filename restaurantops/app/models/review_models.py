"""Review CRUD and rating summary functions.

All functions receive a sqlite3.Connection and do NOT commit.
The caller (route) is responsible for BEGIN/commit.
"""

import sqlite3


def create_review(
    conn: sqlite3.Connection,
    menu_item_id: int | None,
    rating: int,
    guest_name: str,
    comment: str,
) -> int:
    """Insert a new review and return its id.

    Args:
        conn: Database connection (caller manages transactions).
        menu_item_id: FK to menu_items, or None for a general review.
        rating: Integer 1-5.
        guest_name: Guest display name.
        comment: Review text.

    Returns:
        The id of the newly created review row.
    """
    cursor = conn.execute(
        """INSERT INTO reviews (menu_item_id, rating, guest_name, comment)
           VALUES (?, ?, ?, ?)""",
        (menu_item_id, rating, guest_name, comment),
    )
    return cursor.lastrowid


def get_all_reviews(conn: sqlite3.Connection) -> list:
    """Return all reviews ordered by newest first.

    Joins menu_items to include the item name for display.
    """
    return conn.execute(
        """SELECT r.*, m.name AS menu_item_name
           FROM reviews r
           LEFT JOIN menu_items m ON r.menu_item_id = m.id
           ORDER BY r.created_at DESC""",
    ).fetchall()


def get_reviews_for_menu_item(
    conn: sqlite3.Connection, menu_item_id: int
) -> list:
    """Return all reviews for a specific menu item, newest first."""
    return conn.execute(
        """SELECT * FROM reviews
           WHERE menu_item_id = ?
           ORDER BY created_at DESC""",
        (menu_item_id,),
    ).fetchall()


def get_review(conn: sqlite3.Connection, review_id: int):
    """Return a single review by id, or None if not found.

    Joins menu_items to include the item name for display.
    """
    return conn.execute(
        """SELECT r.*, m.name AS menu_item_name
           FROM reviews r
           LEFT JOIN menu_items m ON r.menu_item_id = m.id
           WHERE r.id = ?""",
        (review_id,),
    ).fetchone()


def delete_review(conn: sqlite3.Connection, review_id: int) -> None:
    """Delete a review by id. Does NOT commit."""
    conn.execute("DELETE FROM reviews WHERE id = ?", (review_id,))


def get_menu_item_avg_rating(
    conn: sqlite3.Connection, menu_item_id: int
) -> float | None:
    """Return the average rating for a menu item, or None if no reviews.

    Returns:
        float | None -- average rating as a float, or None when there are
        no reviews for the given menu item.
    """
    row = conn.execute(
        "SELECT AVG(rating) AS avg_rating FROM reviews WHERE menu_item_id = ?",
        (menu_item_id,),
    ).fetchone()
    if row is None or row["avg_rating"] is None:
        return None
    return float(row["avg_rating"])


def get_review_summary(conn: sqlite3.Connection) -> dict:
    """Return overall review statistics.

    Returns:
        dict with keys:
            total_reviews (int): Count of all reviews.
            avg_rating (float | None): Overall average, None if no reviews.
            rating_distribution (dict[int, int]): Mapping of rating (1-5) to
                count of reviews with that rating.
    """
    # Total and average
    stats_row = conn.execute(
        "SELECT COUNT(*) AS total, AVG(rating) AS avg FROM reviews",
    ).fetchone()

    total_reviews = stats_row["total"]
    avg_rating = float(stats_row["avg"]) if stats_row["avg"] is not None else None

    # Rating distribution -- always include all 5 buckets even if count is 0
    rating_distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    rows = conn.execute(
        "SELECT rating, COUNT(*) AS cnt FROM reviews GROUP BY rating",
    ).fetchall()
    for row in rows:
        rating_distribution[row["rating"]] = row["cnt"]

    return {
        "total_reviews": total_reviews,
        "avg_rating": avg_rating,
        "rating_distribution": rating_distribution,
    }
