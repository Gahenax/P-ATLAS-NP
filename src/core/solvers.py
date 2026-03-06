import random
import math
from typing import Dict, Any
from src.utils import rng_for_instance

class MockSolver:
    """
    DEMO ONLY. Coherente con transición de fase y generadores.
    Determinista por instance_id.
    """
    def _sat_probability(self, ratio: float) -> float:
        if ratio < 3.0:
            return 0.95
        if ratio > 6.0:
            return 0.05
        return 1 / (1 + math.exp(6 * (ratio - 4.267)))

    def _check_planted_consistency(self, instance: Dict[str, Any]) -> bool:
        sol = instance.get("metadata", {}).get("planted_solution")
        if not sol:
            return True
        for clause in instance["clauses"]:
            ok = False
            for lit in clause:
                v = abs(lit) - 1
                val = sol[v]
                if lit * val > 0:
                    ok = True
                    break
            if not ok:
                return False
        return True

    def _compute_hardness(self, n: int, ratio: float, gen: str, result: str, rng: random.Random) -> Dict[str, Any]:
        peak = 4.267  # Updated to precise critical ratio
        dist = abs(ratio - peak)
        base = 0.1 + 0.9 * math.exp(-(dist ** 2) / 2)
        scale = (n / 100) ** 1.5

        if gen == "planted_sat":
            base *= 0.3
        elif gen == "community_structured":
            base *= 0.7

        if result == "UNSAT" and 4.0 < ratio < 5.0:
            base *= 1.2

        runtime = base * scale * (0.8 + 0.4 * rng.random())
        decisions = int(runtime * 1000 * (1 + ratio / 4))
        conflicts = int(decisions / (5 + rng.random() * 5))
        return {
            "runtime": max(0.001, runtime),
            "decisions": decisions,
            "conflicts": conflicts,
            "propagations": decisions * 10,
            "lbd_mean": 5 + rng.random() * 10 + (ratio - 4.26) ** 2,
            "growth_rate": rng.random() * 0.5 * base,
            "restarts": max(1, int(conflicts / 100)),
        }

    def solve(self, instance: Dict[str, Any], timeout: int = 3600) -> Dict[str, Any]:
        rng = rng_for_instance(instance["instance_id"], salt="solver")
        n = instance["n_vars"]
        ratio = instance["ratio"]
        gen = instance["generator"]
        meta = instance.get("metadata", {})

        if gen == "planted_sat":
            result = "SAT" if self._check_planted_consistency(instance) else "UNSAT"
        else:
            p_sat = float(meta.get("expected_sat", self._sat_probability(ratio)))
            result = "SAT" if rng.random() < p_sat else "UNSAT"

        h = self._compute_hardness(n, ratio, gen, result, rng)
        return {
            "instance_id": instance["instance_id"],
            "result": result,
            "runtime_seconds": round(h["runtime"], 6),
            "decisions": h["decisions"],
            "conflicts": h["conflicts"],
            "propagations": h["propagations"],
            "lbd_mean": round(h["lbd_mean"], 4),
            "clause_db_growth_rate": round(h["growth_rate"], 6),
            "n_restarts": h["restarts"],
        }


class RealSolver:
    """
    Production solver wrapping the real DPLLSolver.
    Produces telemetry compatible with MockSolver's output schema.
    """
    def __init__(self):
        from src.solvers.dpll import DPLLSolver
        self._dpll = DPLLSolver()

    def solve(self, instance: Dict[str, Any], timeout: int = 3600) -> Dict[str, Any]:
        import time

        clauses = instance["clauses"]
        n = instance["n_vars"]

        t0 = time.perf_counter()
        try:
            is_sat, _model = self._dpll.solve(clauses, n)
        except RecursionError:
            is_sat = None
        elapsed = time.perf_counter() - t0

        result = "TIMEOUT" if is_sat is None else ("SAT" if is_sat else "UNSAT")
        tracker = self._dpll.tracker

        return {
            "instance_id": instance["instance_id"],
            "result": result,
            "runtime_seconds": round(elapsed, 6),
            "decisions": tracker.decisions,
            "conflicts": tracker.backtracks,
            "propagations": tracker.unit_propagations * 10,
            "lbd_mean": 0.0,
            "clause_db_growth_rate": 0.0,
            "n_restarts": 0,
        }
