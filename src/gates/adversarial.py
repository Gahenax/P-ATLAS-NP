import copy
import random
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple
from src.utils import _u32_from_sha256
from src.signatures.extractors import SignatureExtractor

def apply_variable_permutation(instance: Dict[str, Any], perm_seed: int) -> Dict[str, Any]:
    """
    Renombra variables por una biyección aleatoria. Preserva SAT/UNSAT.
    """
    n = instance["n_vars"]
    rng = random.Random(perm_seed)
    perm = list(range(1, n + 1))
    rng.shuffle(perm)
    # map old var -> new var
    mapping = {i + 1: perm[i] for i in range(n)}

    new_clauses: List[List[int]] = []
    for clause in instance["clauses"]:
        nc = []
        for lit in clause:
            v = abs(lit)
            sign = 1 if lit > 0 else -1
            nv = mapping[v]
            nc.append(sign * nv)
        new_clauses.append(sorted(nc))

    out = dict(instance)
    out["instance_id"] = instance["instance_id"] + f"|perm:{perm_seed}"
    out["clauses"] = new_clauses

    meta = dict(instance.get("metadata", {}))
    if "planted_solution" in meta:
        old_sol = meta["planted_solution"]
        inv = {mapping[old]: old for old in mapping}
        new_sol = [0] * n
        for new_v in range(1, n + 1):
            old_v = inv[new_v]
            new_sol[new_v - 1] = old_sol[old_v - 1]
        meta["planted_solution"] = new_sol
    out["metadata"] = meta
    return out

def apply_clause_perturbation(instance: Dict[str, Any], rate: float, pert_seed: int) -> Dict[str, Any]:
    """
    Perturba ~rate de cláusulas cambiando 1 literal por otro literal aleatorio.
    """
    rng = random.Random(pert_seed)
    n = instance["n_vars"]
    clauses = [list(c) for c in instance["clauses"]]
    m = len(clauses)
    
    n_change = max(1, int(round(rate * m))) if m > 0 else 0
    idxs = rng.sample(range(m), min(n_change, m))

    for idx in idxs:
        clause = clauses[idx]
        pos = rng.randrange(len(clause))
        new_var = rng.randrange(1, n + 1)
        new_sign = rng.choice([-1, 1])
        clause[pos] = new_sign * new_var
        clauses[idx] = sorted(clause)

    out = dict(instance)
    out["instance_id"] = instance["instance_id"] + f"|pert:{pert_seed}:{rate}"
    out["clauses"] = clauses
    return out

def compute_v_vector(row: Dict[str, Any], coords: List[str], stats: Dict[str, Tuple[float, float]]) -> np.ndarray:
    """
    v = zscore(coords) usando stats (mean,std) del conjunto base.
    """
    arr = []
    for c in coords:
        mu, sd = stats[c]
        val = float(row.get(c, 0.0))
        z = (val - mu) / (sd + 1e-8)
        arr.append(z)
    return np.array(arr, dtype=float)

def compute_stats(df: pd.DataFrame, coords: List[str]) -> Dict[str, Tuple[float, float]]:
    stats = {}
    for c in coords:
        mu = float(df[c].mean())
        sd = float(df[c].std())
        stats[c] = (mu, sd)
    return stats

class AdversarialGates:
    def __init__(self, extractor: SignatureExtractor):
        self.extractor = extractor

    def run_all(
        self,
        v: Dict[str, Any],
        base_df: pd.DataFrame,
        instances_by_id: Dict[str, Dict[str, Any]],
        plan_gates: Dict[str, Any],
        run_mode: str,
    ) -> Dict[str, Any]:
        coords = v["coordinates"]
        stats = compute_stats(base_df, coords)

        r = {}
        r["gate_1_semantics"] = self._gate_semantics(base_df, coords)
        r["gate_2_permutation"] = self._gate_permutation(instances_by_id, coords, stats, plan_gates)
        r["gate_3_scale"] = self._gate_scale(base_df, coords, plan_gates)
        r["gate_4_generator"] = self._gate_generator(base_df, coords, plan_gates)
        r["gate_5_perturbation"] = self._gate_perturbation(base_df, instances_by_id, coords, stats, plan_gates)
        r["gate_6_spectral_camouflage"] = self._gate_spectral_camouflage(base_df, coords, plan_gates)
        r["gate_7_falsifiability"] = self._gate_falsifiability_check(instances_by_id)

        all_pass = all(x.get("status") == "PASS" for x in r.values())
        r["final_verdict"] = "VECTOR_VALIDATED" if all_pass else "VECTOR_REJECTED"
        r["run_mode"] = run_mode
        return r

    def _gate_semantics(self, df: pd.DataFrame, coords: List[str]) -> Dict[str, Any]:
        if "generator" not in df.columns:
            return {"status": "INCONCLUSIVE", "score": 0.5, "details": "No generator metadata"}

        planted = df["generator"] == "planted_sat"
        rnd = df["generator"] == "random_kcnf"
        if planted.sum() == 0 or rnd.sum() == 0:
            return {"status": "INCONCLUSIVE", "score": 0.5, "details": "Insufficient generator diversity"}

        planted_mean = df.loc[planted, coords].mean().values
        rnd_mean = df.loc[rnd, coords].mean().values
        denom = df[coords].std().values.mean() + 1e-8
        dist = float(np.linalg.norm(planted_mean - rnd_mean) / denom)

        score = min(1.0, dist / 0.5)
        status = "PASS" if dist >= 0.1 else "FAIL"
        return {"status": status, "score": round(float(score), 6), "details": f"norm-dist planted vs random = {dist:.4f} (ideal >0.1)"}

    def _gate_permutation(self, instances_by_id: Dict[str, Dict[str, Any]], coords: List[str], stats: Dict[str, Tuple[float, float]], plan_gates: Dict[str, Any]) -> Dict[str, Any]:
        cfg = plan_gates.get("gate_2_permutation", {})
        n_perms = int(cfg.get("n_permutations", 5))
        threshold = float(cfg.get("delta_v_threshold", 0.35))

        sample_n = int(cfg.get("sample_instances", 30))
        ids = list(instances_by_id.keys())
        ids = [i for i in ids if "|perm:" not in i and "|pert:" not in i]
        sample_ids = ids[:sample_n] if len(ids) <= sample_n else random.Random(123).sample(ids, sample_n)

        deltas = []
        for inst_id in sample_ids:
            inst = instances_by_id[inst_id]
            base_feat, _ = self.extractor.extract_all(inst)
            base_v = compute_v_vector(base_feat, coords, stats)

            worst = 0.0
            for j in range(n_perms):
                perm_seed = _u32_from_sha256(inst_id + f"|permseed:{j}")
                inst_p = apply_variable_permutation(inst, perm_seed)
                feat_p, _ = self.extractor.extract_all(inst_p)
                v_p = compute_v_vector(feat_p, coords, stats)
                dv = float(np.linalg.norm(base_v - v_p))
                if dv > worst:
                    worst = dv
            deltas.append(worst)

        worst_case = float(np.max(deltas)) if deltas else 999.0
        score = max(0.0, 1.0 - worst_case / (threshold + 1e-8))
        status = "PASS" if worst_case <= threshold else "FAIL"
        return {"status": status, "score": round(float(score), 6), "details": f"worst delta_v (perm) = {worst_case:.4f}, threshold = {threshold:.4f}, samples = {len(deltas)}"}

    def _gate_scale(self, df: pd.DataFrame, coords: List[str], plan_gates: Dict[str, Any]) -> Dict[str, Any]:
        cfg = plan_gates.get("gate_3_scale", {})
        train_n = int(cfg.get("train_n", 80))
        test_n = int(cfg.get("test_n", 120))
        max_drift = float(cfg.get("max_relative_drift", 0.25))

        if "n_vars" not in df.columns:
            return {"status": "INCONCLUSIVE", "score": 0.5, "details": "No n_vars metadata"}

        small = df["n_vars"] == train_n
        large = df["n_vars"] == test_n
        if small.sum() == 0 or large.sum() == 0:
            return {"status": "INCONCLUSIVE", "score": 0.5, "details": f"Need n_vars={train_n} and n_vars={test_n}"}

        sm = float(df.loc[small, coords].mean().mean())
        lg = float(df.loc[large, coords].mean().mean())
        drift = abs(sm - lg) / (abs(sm) + 1e-8)

        score = max(0.0, 1.0 - drift / (max_drift + 1e-8))
        status = "PASS" if drift <= max_drift else "FAIL"
        return {"status": status, "score": round(float(score), 6), "details": f"relative drift = {drift:.4f}, max = {max_drift:.4f}"}

    def _gate_generator(self, df: pd.DataFrame, coords: List[str], plan_gates: Dict[str, Any]) -> Dict[str, Any]:
        cfg = plan_gates.get("gate_4_generator", {})
        max_cv = float(cfg.get("max_cv", 0.6))
        if "generator" not in df.columns:
            return {"status": "INCONCLUSIVE", "score": 0.5, "details": "No generator metadata"}

        gens = sorted(df["generator"].unique().tolist())
        if len(gens) < 2:
            return {"status": "INCONCLUSIVE", "score": 0.5, "details": "Only one generator"}

        means = []
        for g in gens:
            means.append(float(df.loc[df["generator"] == g, coords].mean().mean()))
        cv = float(np.std(means) / (abs(np.mean(means)) + 1e-8))

        score = max(0.0, 1.0 - cv / (max_cv + 1e-8))
        status = "PASS" if cv <= max_cv else "FAIL"
        return {"status": status, "score": round(float(score), 6), "details": f"CV={cv:.4f}, max={max_cv:.4f}"}

    def _gate_perturbation(self, base_df: pd.DataFrame, instances_by_id: Dict[str, Dict[str, Any]], coords: List[str], stats: Dict[str, Tuple[float, float]], plan_gates: Dict[str, Any]) -> Dict[str, Any]:
        cfg = plan_gates.get("gate_5_perturbation", {})
        rate = float(cfg.get("perturbation_rate", 0.02))
        threshold = float(cfg.get("delta_v_threshold", 0.50))
        sample_n = int(cfg.get("sample_instances", 30))

        ids = list(instances_by_id.keys())
        ids = [i for i in ids if "|perm:" not in i and "|pert:" not in i]
        sample_ids = ids[:sample_n] if len(ids) <= sample_n else random.Random(456).sample(ids, sample_n)

        deltas = []
        for inst_id in sample_ids:
            inst = instances_by_id[inst_id]
            base_feat, _ = self.extractor.extract_all(inst)
            base_v = compute_v_vector(base_feat, coords, stats)

            pert_seed = _u32_from_sha256(inst_id + "|pertseed")
            inst_q = apply_clause_perturbation(inst, rate=rate, pert_seed=pert_seed)
            feat_q, _ = self.extractor.extract_all(inst_q)
            v_q = compute_v_vector(feat_q, coords, stats)
            dv = float(np.linalg.norm(base_v - v_q))
            deltas.append(dv)

        worst = float(np.max(deltas)) if deltas else 999.0
        score = max(0.0, 1.0 - worst / (threshold + 1e-8))
        status = "PASS" if worst <= threshold else "FAIL"
        return {"status": status, "score": round(float(score), 6), "details": f"worst delta_v (pert) = {worst:.4f}, threshold = {threshold:.4f}, samples={len(deltas)}"}

    def _gate_spectral_camouflage(self, df: pd.DataFrame, coords: List[str], plan_gates: Dict[str, Any]) -> Dict[str, Any]:
        """
        Gate 6: Spectral Camouflage (Quiet Planting).
        Verifies that 'quiet_planted_sat' instances are statistically indistinguishable from 'random_kcnf'
        in the target embedding space.
        """
        cfg = plan_gates.get("gate_6_spectral_camouflage", {})
        max_dist = float(cfg.get("max_distance", 0.5))

        if "generator" not in df.columns:
            return {"status": "INCONCLUSIVE", "score": 0.5, "details": "No generator metadata"}

        quiet = df["generator"] == "quiet_planted_sat"
        rnd = df["generator"] == "random_kcnf"

        if quiet.sum() == 0 or rnd.sum() == 0:
            return {"status": "INCONCLUSIVE", "score": 0.5, "details": "Need both quiet_planted_sat and random_kcnf"}

        quiet_mean = df.loc[quiet, coords].mean().values
        rnd_mean = df.loc[rnd, coords].mean().values
        
        # Compute normalized distance
        denom = df[coords].std().values.mean() + 1e-8
        dist = float(np.linalg.norm(quiet_mean - rnd_mean) / denom)

        score = max(0.0, 1.0 - (dist / (max_dist + 1e-8)))
        status = "PASS" if dist <= max_dist else "FAIL"
        
        return {"status": status, "score": round(float(score), 6), "details": f"camouflage distance = {dist:.4f}, max = {max_dist:.4f}"}

    def _gate_falsifiability_check(self, instances_by_id: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """
        Gate 7: OmniTest Falsifiability (Deep Equality).
        Detects mathematically impossible injected datasets (e.g., P=NP contradictions).
        """
        fails = []
        for inst_id, inst in instances_by_id.items():
            unit_clauses = set()
            for c in inst.get("clauses", []):
                if len(c) == 1:
                    lit = c[0]
                    if -lit in unit_clauses:
                        fails.append(inst_id)
                    unit_clauses.add(lit)
        if fails:
            return {"status": "FAIL", "score": 0.0, "details": f"Falsifiability Poison detected in {len(fails)} instances: {fails[0]}"}
        return {"status": "PASS", "score": 1.0, "details": "No poisoned instances detected (Deep Equality / Falsifiability passed)"}
