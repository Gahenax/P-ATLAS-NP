import os
import sys
import pytest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.solvers.dpll import DPLLSolver

def test_dpll_simple_sat():
    solver = DPLLSolver()
    # (x1 OR x2) AND (-x1 OR -x2) -> SAT e.g., x1=1, x2=-1
    formula = [[1, 2], [-1, -2]]
    is_sat, _ = solver.solve(formula, 2)
    assert is_sat == True

def test_dpll_simple_unsat():
    solver = DPLLSolver()
    # (x1) AND (-x1) -> UNSAT
    formula = [[1], [-1]]
    is_sat, _ = solver.solve(formula, 1)
    assert is_sat == False

def test_dpll_3sat_sat():
    solver = DPLLSolver()
    # (x1 V x2 V x3) AND (-x1 V -x2 V -x3) AND (x1 V -x2 V x3)
    formula = [[1, 2, 3], [-1, -2, -3], [1, -2, 3]]
    is_sat, _ = solver.solve(formula, 3)
    assert is_sat == True

def test_dpll_unsat_3vars():
    solver = DPLLSolver()
    # All 8 combinations for 3 variables -> UNSAT
    formula = [
        [1, 2, 3], [1, 2, -3], [1, -2, 3], [1, -2, -3],
        [-1, 2, 3], [-1, 2, -3], [-1, -2, 3], [-1, -2, -3]
    ]
    is_sat, _ = solver.solve(formula, 3)
    assert is_sat == False
