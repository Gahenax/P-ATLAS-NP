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
        return 1 / (1 + math.exp(6 * (ratio - 4.267)))

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
            # planted_solution intentionally NOT in output metadata to prevent
            # adversarial detection via JSON inspection. Store separately if needed.
            "metadata": {"expected_sat": 0.99}
        }

    def quiet_planted_sat(self, n: int, m: int, k: int, seed: int) -> Dict[str, Any]:
        rng = random.Random(seed)
        solution = [rng.choice([-1, 1]) for _ in range(n)]
        clauses: List[List[int]] = []
        
        # P(t) = C(k, t) / (2^k - 1) for t in 1..k
        weights = [math.comb(k, t) for t in range(1, k + 1)]
        
        for _ in range(m):
            vars_ = rng.sample(range(1, n + 1), k)
            t = rng.choices(range(1, k + 1), weights=weights, k=1)[0]
            true_vars = set(rng.sample(vars_, t))
            
            clause: List[int] = []
            for v in vars_:
                sol_sign = solution[v - 1]
                if v in true_vars:
                    # literal is true under planted solution
                    lit = sol_sign * v
                else:
                    # literal is false under planted solution
                    lit = -sol_sign * v
                clause.append(lit)
                
            clause = sorted(clause)
            clauses.append(clause)

        ratio = m / n
        instance_id = f"qpt_n{n}_m{m}_r{ratio:.3f}_s{seed}"
        return {
            "instance_id": instance_id,
            "generator": "quiet_planted_sat",
            "n_vars": n,
            "n_clauses": m,
            "ratio": ratio,
            "clauses": clauses,
            "metadata": {"planted_solution": solution, "expected_sat": 0.99}
        }

    def community_structured(self, n: int, m: int, k: int, seed: int,
                              n_communities: int = 4, p_inter: float = 0.1) -> Dict[str, Any]:
        """
        Generates a k-CNF with community structure.
        Variables are partitioned into `n_communities` groups.
        Each clause draws variables from the same community with probability (1 - p_inter),
        or from any community with probability p_inter.
        """
        rng = random.Random(seed)
        community_size = n // n_communities
        communities: List[List[int]] = []
        for c_idx in range(n_communities):
            start = c_idx * community_size + 1
            end = start + community_size
            if c_idx == n_communities - 1:
                end = n + 1  # last community absorbs remainder
            communities.append(list(range(start, end)))

        all_vars = list(range(1, n + 1))
        clauses: List[List[int]] = []

        for _ in range(m):
            if rng.random() > p_inter:
                # Intra-community clause
                comm = rng.choice(communities)
                if len(comm) < k:
                    pool = all_vars
                else:
                    pool = comm
            else:
                # Inter-community clause
                pool = all_vars

            vars_ = rng.sample(pool, min(k, len(pool)))
            signs = [rng.choice([-1, 1]) for _ in range(len(vars_))]
            clause = sorted([s * v for s, v in zip(signs, vars_)])
            clauses.append(clause)

        ratio = m / n
        instance_id = f"com_n{n}_m{m}_r{ratio:.3f}_c{n_communities}_s{seed}"
        return {
            "instance_id": instance_id,
            "generator": "community_structured",
            "n_vars": n,
            "n_clauses": m,
            "ratio": ratio,
            "clauses": clauses,
            "metadata": {
                "n_communities": n_communities,
                "p_inter": p_inter,
                "expected_sat": self._sat_probability(ratio),
            }
        }
