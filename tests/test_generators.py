from src.core import SATGenerator

def test_random_kcnf_determinism():
    gen = SATGenerator()
    inst1 = gen.random_kcnf(10, 30, 3, seed=123)
    inst2 = gen.random_kcnf(10, 30, 3, seed=123)
    inst_diff = gen.random_kcnf(10, 30, 3, seed=124)
    
    assert inst1["clauses"] == inst2["clauses"]
    assert inst1["clauses"] != inst_diff["clauses"]
    assert len(inst1["clauses"]) == 30

def test_planted_sat():
    gen = SATGenerator()
    inst = gen.planted_sat(10, 42, 3, seed=42)
    
    assert "planted_solution" in inst["metadata"]
    assert len(inst["clauses"]) == 42
    
    sol = inst["metadata"]["planted_solution"]
    # Verify the planted solution satisfies all clauses
    for clause in inst["clauses"]:
        ok = False
        for lit in clause:
            v = abs(lit) - 1
            val = sol[v]
            if lit * val > 0:
                ok = True
                break
        assert ok is True
