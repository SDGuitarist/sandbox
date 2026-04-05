"""Verify-first: cycle detection in the dependency DAG."""
import pytest

from flags.db import add_dependency, create_flag, init_db, remove_dependency


@pytest.fixture
def db(tmp_path):
    path = str(tmp_path / "test.db")
    init_db(path=path)
    # Create test flags: A, B, C, D, E
    for key in ["A", "B", "C", "D", "E"]:
        create_flag(key, f"Flag {key}", db_path=path)
    return path


def test_linear_chain_no_cycle(db):
    """A → B → C is a valid DAG (no cycle)."""
    add_dependency("A", "B", db_path=db)
    add_dependency("B", "C", db_path=db)
    # No exception means no cycle detected — correct


def test_diamond_no_cycle(db):
    """Diamond: A→B, A→C, B→D, C→D — two paths to D, no cycle."""
    add_dependency("A", "B", db_path=db)
    add_dependency("A", "C", db_path=db)
    add_dependency("B", "D", db_path=db)
    add_dependency("C", "D", db_path=db)
    # No exception — correct, diamond is a valid DAG


def test_true_cycle_detected(db):
    """A → B → C → A forms a cycle; adding C→A must be rejected."""
    add_dependency("A", "B", db_path=db)
    add_dependency("B", "C", db_path=db)
    with pytest.raises(ValueError, match="cycle"):
        add_dependency("C", "A", db_path=db)


def test_self_cycle_detected(db):
    """A → A is a self-cycle."""
    with pytest.raises(ValueError):
        add_dependency("A", "A", db_path=db)


def test_diamond_then_cycle_detected(db):
    """Diamond A→B, A→C, B→D, C→D. Adding D→A creates a cycle."""
    add_dependency("A", "B", db_path=db)
    add_dependency("A", "C", db_path=db)
    add_dependency("B", "D", db_path=db)
    add_dependency("C", "D", db_path=db)
    with pytest.raises(ValueError, match="cycle"):
        add_dependency("D", "A", db_path=db)


def test_two_hop_cycle_detected(db):
    """A → B → A (two-hop cycle)."""
    add_dependency("A", "B", db_path=db)
    with pytest.raises(ValueError, match="cycle"):
        add_dependency("B", "A", db_path=db)


def test_remove_dependency(db):
    """Removing a dependency works and allows re-adding."""
    add_dependency("A", "B", db_path=db)
    assert remove_dependency("A", "B", db_path=db) is True
    # Can now re-add without error
    add_dependency("A", "B", db_path=db)


def test_remove_nonexistent_dependency(db):
    assert remove_dependency("A", "B", db_path=db) is False


def test_long_chain_no_cycle(db):
    """A → B → C → D → E is valid."""
    add_dependency("A", "B", db_path=db)
    add_dependency("B", "C", db_path=db)
    add_dependency("C", "D", db_path=db)
    add_dependency("D", "E", db_path=db)
    # No exception


def test_long_chain_cycle_at_end(db):
    """A → B → C → D → E → A is a cycle."""
    add_dependency("A", "B", db_path=db)
    add_dependency("B", "C", db_path=db)
    add_dependency("C", "D", db_path=db)
    add_dependency("D", "E", db_path=db)
    with pytest.raises(ValueError, match="cycle"):
        add_dependency("E", "A", db_path=db)
