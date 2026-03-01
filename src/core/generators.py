import random
import math
from typing import Dict, Any, List

class SATGenerator:
    def __init__(self, seed: int = 42):
        self.base_rng = random.Random(seed)

    def _sat_probability(self, ratio: float) -> float:
        if ratio < 3.0:
            return 0.95
        if ratio > 6.0:
            return 0.05
        return 1 / (1 + math.exp(6 * (ratio - 4.26)))

    def random_kcnf(self, n: int, m: int, k: int, seed: int) -> Dict[str, Any]:
        rng = random.Random(seed)
        clauses: List[List[int]] = []
        for _ in range(m):
            vars_ = rng.sample(range(1, n + 1), k)
            signs = [rng.choice([-1, 1]) for _ in range(k)]
            clause = sorted([s * v for s, v in zip(signs, vars_)])
            clauses.append(clause)

        ratio = m / n
        instance_id = f"rnd_n{n}_m{m}_r{ratio:.3f}_s{seed}"
        return {
            "instance_id": instance_id,
            "generator": "random_kcnf",
            "n_vars": n,
            "n_clauses": m,
            "ratio": ratio,
            "clauses": clauses,
            "metadata": {"expected_sat": self._sat_probability(ratio)}
        }

    def planted_sat(self, n: int, m: int, k: int, seed: int) -> Dict[str, Any]:
        rng = random.Random(seed)
        solution = [rng.choice([-1, 1]) for _ in range(n)]
        clauses: List[List[int]] = []
        attempts = 0
        target = m

        while len(clauses) < target and attempts < target * 20:
            vars_ = rng.sample(range(1, n + 1), k)
            sat_idx = rng.randrange(k)
            clause: List[int] = []
            for i, v in enumerate(vars_):
                if i == sat_idx:
                    lit = solution[v - 1] * v
                else:
                    lit = rng.choice([-1, 1]) * v
                clause.append(lit)
            clause = sorted(clause)
            clauses.append(clause)
            attempts += 1

        ratio = len(clauses) / n
        instance_id = f"plt_n{n}_m{len(clauses)}_r{ratio:.3f}_s{seed}"
        return {
            "instance_id": instance_id,
            "generator": "planted_sat",
            "n_vars": n,
            "n_clauses": len(clauses),
            "ratio": ratio,
            "clauses": clauses,
            "metadata": {"planted_solution": solution, "expected_sat": 0.99}
        }
