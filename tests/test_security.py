import random
import secrets
import pytest
from src.generators.random_k_sat import generate_random_k_sat, generate_planted_k_sat

def test_random_k_sat_security():
    """
    Verify that generate_random_k_sat is non-deterministic even with random.seed().
    """
    random.seed(42)
    formula1 = generate_random_k_sat(10, 20, k=3)

    random.seed(42)
    formula2 = generate_random_k_sat(10, 20, k=3)

    # In a cryptographically secure RNG, it's extremely unlikely to get
    # the same formula twice for these parameters.
    assert formula1 != formula2

def test_planted_k_sat_security():
    """
    Verify that generate_planted_k_sat is non-deterministic even with random.seed().
    """
    random.seed(42)
    formula1, solution1 = generate_planted_k_sat(10, k=3)

    random.seed(42)
    formula2, solution2 = generate_planted_k_sat(10, k=3)

    assert (formula1, solution1) != (formula2, solution2)

def test_generators_output_validity():
    """
    Basic sanity check that generators still produce valid-looking CNF.
    """
    num_vars = 10
    num_clauses = 20
    k = 3
    formula = generate_random_k_sat(num_vars, num_clauses, k)

    assert len(formula) == num_clauses
    for clause in formula:
        assert len(clause) == k
        for lit in clause:
            assert 1 <= abs(lit) <= num_vars

    formula, solution = generate_planted_k_sat(num_vars, k)
    assert len(solution) == num_vars
    for clause in formula:
        assert len(clause) == k
        # Verify it's satisfied by the planted solution
        satisfied = False
        for lit in clause:
            var_idx = abs(lit) - 1
            if (lit > 0 and solution[var_idx] > 0) or (lit < 0 and solution[var_idx] < 0):
                satisfied = True
                break
        assert satisfied, f"Clause {clause} not satisfied by {solution}"
