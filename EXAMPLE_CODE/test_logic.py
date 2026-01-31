import pytest
from logic_parser import parse_kb, Predicate, Variable, Constant
from logic_solver import unify, fol_fc_ask, fol_bc_ask

# --- Fixtures ---


@pytest.fixture(scope="module")
def kb():
    """
    A fixture that loads the Camelot Knowledge Base once per test module.
    Provides (facts, rules) to any test function that needs it.
    """
    facts, rules = parse_kb("camelot.kb")
    return facts, rules


# --- Basic Smoke Tests ---


def test_imports():
    """Basic sanity test that all imports work."""
    assert Predicate is not None
    assert Variable is not None
    assert Constant is not None
    assert unify is not None
    assert fol_fc_ask is not None
    assert fol_bc_ask is not None


def test_fc_returns_list(kb):
    """Tests that forward chaining returns a list."""
    facts, rules = kb
    result = fol_fc_ask(facts, rules)
    assert isinstance(result, list), "fol_fc_ask should return a list of facts"


def test_bc_is_generator(kb):
    """Tests that backward chaining returns a generator."""
    facts, rules = kb
    query = Predicate("King", [Constant("Arthur")])
    result = fol_bc_ask(query, facts, rules)
    # Generators have __next__ method
    assert hasattr(result, "__next__"), "fol_bc_ask should return a generator"


# ---
# Note: This file contains only basic tests to verify your code structure.
# You should write your own comprehensive tests to validate your implementation.
#
# We strongly encourage you to write additional tests to check different cases!
# ---
