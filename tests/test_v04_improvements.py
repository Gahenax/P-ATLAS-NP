import os
import sys
import tempfile
from pathlib import Path

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.solvers import RealSolver
from src.core.generators import SATGenerator
from src.campaign_memory import CampaignMemory


# --- Test RealSolver ---

def test_real_solver_sat():
    gen = SATGenerator()
    inst = gen.planted_sat(10, 30, 3, seed=42)
    solver = RealSolver()
    tel = solver.solve(inst, timeout=60)
    assert tel["result"] == "SAT"
    assert tel["runtime_seconds"] >= 0
    assert tel["decisions"] >= 0

def test_real_solver_unsat():
    solver = RealSolver()
    inst = {
        "instance_id": "test_unsat",
        "generator": "random_kcnf",
        "n_vars": 2,
        "ratio": 4.0,
        "n_clauses": 4,
        "clauses": [[1, 2], [1, -2], [-1, 2], [-1, -2]],
        "metadata": {}
    }
    tel = solver.solve(inst, timeout=60)
    assert tel["result"] == "UNSAT"
    assert tel["conflicts"] > 0

def test_real_solver_telemetry_schema():
    gen = SATGenerator()
    inst = gen.random_kcnf(10, 30, 3, seed=99)
    solver = RealSolver()
    tel = solver.solve(inst)
    required_keys = ["instance_id", "result", "runtime_seconds", "decisions",
                     "conflicts", "propagations", "lbd_mean",
                     "clause_db_growth_rate", "n_restarts"]
    for k in required_keys:
        assert k in tel, f"Missing key: {k}"


# --- Test Community Generator ---

def test_community_generator_valid():
    gen = SATGenerator()
    inst = gen.community_structured(20, 60, 3, seed=42, n_communities=4, p_inter=0.1)
    assert inst["generator"] == "community_structured"
    assert inst["n_vars"] == 20
    assert len(inst["clauses"]) == 60
    assert inst["metadata"]["n_communities"] == 4

def test_community_generator_determinism():
    gen = SATGenerator()
    inst1 = gen.community_structured(20, 60, 3, seed=42)
    inst2 = gen.community_structured(20, 60, 3, seed=42)
    assert inst1["clauses"] == inst2["clauses"]

def test_community_generator_different_seeds():
    gen = SATGenerator()
    inst1 = gen.community_structured(20, 60, 3, seed=42)
    inst2 = gen.community_structured(20, 60, 3, seed=99)
    assert inst1["clauses"] != inst2["clauses"]


# --- Test Campaign Memory ---

def test_campaign_memory_write_read():
    with tempfile.TemporaryDirectory() as tmpdir:
        mem = CampaignMemory(working_dir=tmpdir)

        # Initially empty
        explored = mem.load_explored_points()
        assert len(explored) == 0

        # Save campaign
        v = {"coordinates": ["x1", "x2"], "stability_score": 0.9}
        gates = {
            "gate_1": {"status": "PASS", "score": 1.0},
            "final_verdict": "VECTOR_VALIDATED",
        }
        keys = {mem.point_key(80, 4.0, 0, "random_kcnf"),
                mem.point_key(80, 4.0, 0, "planted_sat")}
        mem.save_campaign_summary("TEST-001", v, gates, 10, keys)

        # MEMORY.md should exist
        assert (Path(tmpdir) / "MEMORY.md").exists()

        # Read back
        explored2 = mem.load_explored_points()
        assert len(explored2) == 2

def test_campaign_memory_daily_log():
    with tempfile.TemporaryDirectory() as tmpdir:
        mem = CampaignMemory(working_dir=tmpdir)
        v = {"coordinates": ["x1"], "stability_score": 0.5}
        gates = {"gate_1": {"status": "FAIL", "score": 0.3}, "final_verdict": "VECTOR_REJECTED"}
        mem.save_campaign_summary("TEST-002", v, gates, 5, set())

        # Check daily log exists
        memory_dir = Path(tmpdir) / "memory"
        logs = list(memory_dir.glob("*.md"))
        assert len(logs) == 1
