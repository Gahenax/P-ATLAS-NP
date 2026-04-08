from src.core import SATGenerator

def test_random_kcnf_determinism():
    gen = SATGenerator()
    inst1 = gen.random_kcnf(10, 30, 3, seed=123)
    inst2 = gen.random_kcnf(10, 30, 3, seed=123)
    inst_diff = gen.random_kcnf(10, 30, 3, seed=124)
    
    assert inst1["clauses"] == inst2["clauses"]
    assert inst1["clauses"] != inst_diff["clauses"]
    assert len(inst1["clauses"]) == 30

from src.core.solvers import RealSolver

def test_planted_sat():
    gen = SATGenerator()
    inst = gen.planted_sat(10, 42, 3, seed=42)
    
    assert len(inst["clauses"]) == 42
    
    solver = RealSolver()
    result = solver.solve(inst, timeout=5)

    # Ensure that the instance is indeed satisfiable
    assert result["result"] == "SAT"
