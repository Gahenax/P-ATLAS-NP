#!/usr/bin/env python3
"""
NP-ATLAS v0.3 - POINCARÉ×BSD Vector Hunt
Single-file, reproducible, auditable, con gates reales y atlas kNN.

Ejecutar:
  python np_atlas.py --plan plan.json

Artefactos:
  evidence/vector.json
  evidence/atlas.csv
  evidence/frontier.json
  evidence/obstructions.jsonl
  evidence/report.md
  ledger.jsonl
"""

import json
import hashlib
import random
import math
import statistics
import argparse
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional


# =============================================================================
# UTILIDADES: determinismo por instancia
# =============================================================================

def _u32_from_sha256(s: str) -> int:
    h = hashlib.sha256(s.encode("utf-8")).hexdigest()
    return int(h[:8], 16)  # 32-bit

def rng_for_instance(instance_id: str, salt: str = "") -> random.Random:
    seed = _u32_from_sha256(instance_id + "|" + salt)
    return random.Random(seed)

def now_z() -> str:
    return datetime.utcnow().isoformat() + "Z"


# =============================================================================
# LEDGER: append-only + validación de hash-chain
# =============================================================================

class Ledger:
    def __init__(self, path: str = "ledger.jsonl"):
        self.path = Path(path)
        self.prev_hash = "0" * 64
        if self.path.exists():
            self._load_tail()

    def _load_tail(self) -> None:
        with open(self.path, "r", encoding="utf-8") as f:
            last_line = None
            for last_line in f:
                pass
            if last_line:
                last = json.loads(last_line)
                self.prev_hash = last.get("self_hash", "0" * 64)

    def record(self, event_type: str, data: Dict[str, Any]) -> str:
        event = {
            "event_type": event_type,
            "ts": now_z(),
            "prev_hash": self.prev_hash,
            **data
        }
        # hash excluyendo self_hash
        event_for_hash = {k: v for k, v in event.items() if k != "self_hash"}
        event_str = json.dumps(event_for_hash, sort_keys=True, default=str)
        self_hash = hashlib.sha256(event_str.encode("utf-8")).hexdigest()
        event["self_hash"] = self_hash

        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event) + "\n")

        self.prev_hash = self_hash
        return self_hash

    def count_events(self) -> int:
        if not self.path.exists():
            return 0
        with open(self.path, "r", encoding="utf-8") as f:
            return sum(1 for _ in f)

    def validate_chain(self) -> Tuple[bool, str]:
        if not self.path.exists():
            return True, "No ledger to validate"

        prev_hash = "0" * 64
        errors: List[str] = []
        with open(self.path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as e:
                    return False, f"Line {line_num}: Invalid JSON ({e})"

                if event.get("prev_hash") != prev_hash:
                    errors.append(f"Line {line_num}: Hash-chain break")

                test_event = {k: v for k, v in event.items() if k != "self_hash"}
                test_str = json.dumps(test_event, sort_keys=True, default=str)
                computed = hashlib.sha256(test_str.encode("utf-8")).hexdigest()
                if computed != event.get("self_hash"):
                    errors.append(f"Line {line_num}: Hash mismatch (tampering)")

                prev_hash = event.get("self_hash", "0" * 64)

        if errors:
            return False, "; ".join(errors[:3])
        return True, f"Chain valid, {self.count_events()} events"


# =============================================================================
# SAT GENERATORS (DEMO): random_kcnf, planted_sat
# =============================================================================

class SATGenerator:
    def __init__(self, seed: int = 42):
        self.base_rng = random.Random(seed)

    def _sat_probability(self, ratio: float) -> float:
        # Transición suave centrada ~4.26
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

        # genera cláusulas asegurando satisfacibilidad por solución plantada
        while len(clauses) < target and attempts < target * 20:
            vars_ = rng.sample(range(1, n + 1), k)
            sat_idx = rng.randrange(k)
            clause: List[int] = []
            for i, v in enumerate(vars_):
                if i == sat_idx:
                    lit = solution[v - 1] * v  # satisface solución
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


# =============================================================================
# TRANSFORMACIONES PARA GATES (reales)
# =============================================================================

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

    # Ajustar planted_solution si existe (para mantener coherencia si se re-chequea)
    meta = dict(instance.get("metadata", {}))
    if "planted_solution" in meta:
        old_sol = meta["planted_solution"]  # list indexed by old var-1
        # new solution over new vars: value at new var = value of old var that mapped to it
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
    k = len(clauses[0]) if clauses else 3

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


# =============================================================================
# MOCK SOLVER (DEMO) con RNG determinista por instancia
# =============================================================================

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
        return 1 / (1 + math.exp(6 * (ratio - 4.26)))

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
        peak = 4.26
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


# =============================================================================
# SIGNATURES (DEMO PROXIES) con RNG determinista por instancia
# =============================================================================

class SignatureExtractor:
    """
    Extractor de firmas. Soporta modo DEMO (proxies) y PROD_LITE (NetworkX/SciPy reales).
    """
    def __init__(self, plan: Dict[str, Any] = None):
        self.plan = plan or {}
        self.mode = self.plan.get("signature_mode", {}).get("mode", "demo")
        self.families = self.plan.get("signature_families", {})

    def extract_spectral_demo(self, instance: Dict[str, Any]) -> Dict[str, Any]:
        rng = rng_for_instance(instance["instance_id"], salt="spectral")
        n = instance["n_vars"]
        m = instance["n_clauses"]
        ratio = instance["ratio"]
        return {
            "spectral_gap_proxy": round(0.1 + 0.4 / (1 + ratio / 4), 6),
            "spectral_entropy_proxy": round(2.0 + 2.0 * math.log1p(ratio), 6),
            "primal_trace_k2": round(m * 2 / max(n, 1), 6),
            "incidence_rank_proxy": round(min(n, m) * (0.8 + 0.2 * rng.random()), 6),
        }

    def extract_thermo_demo(self, instance: Dict[str, Any]) -> Dict[str, Any]:
        rng = rng_for_instance(instance["instance_id"], salt="thermo")
        ratio = instance["ratio"]
        beta_critical = 1.0 / (ratio + 0.1)
        return {
            "thermo_beta_critical_proxy": round(beta_critical, 6),
            "thermo_susceptibility_peak": round(0.5 + 1.5 * math.exp(-(ratio - 4.26) ** 2), 6),
            "thermo_log_Z_slope": round(-ratio * (0.8 + 0.4 * rng.random()), 6),
        }

    def extract_algebra_demo(self, instance: Dict[str, Any]) -> Dict[str, Any]:
        rng = rng_for_instance(instance["instance_id"], salt="algebra")
        clauses = instance["clauses"]
        n = instance["n_vars"]
        lengths = [len(c) for c in clauses] if clauses else [0]
        horn = sum(1 for c in clauses if sum(1 for lit in c if lit > 0) <= 1)
        return {
            "algebra_mean_clause_len": round(statistics.mean(lengths), 6),
            "algebra_horn_fraction": round(horn / max(1, len(clauses)), 6),
            "algebra_unit_prop_fixations": int(len(clauses) * 0.1 * rng.random()),
            "resistance_to_2sat": round(min(1.0, len(clauses) / max(n, 1) * 0.3), 6),
        }

    def extract_prod_lite(self, instance: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
        import networkx as nx
        import scipy.sparse as sp
        import scipy.sparse.linalg as spla

        n = instance["n_vars"]
        m = instance["n_clauses"]
        clauses = instance["clauses"]
        features = {}

        B = nx.Graph()
        B.add_nodes_from(range(1, n + 1), bipartite=0)
        B.add_nodes_from([f"c{i}" for i in range(m)], bipartite=1)

        for i, c in enumerate(clauses):
            c_node = f"c{i}"
            for lit in c:
                v = abs(lit)
                B.add_edge(v, c_node)

        topo_cfg = self.families.get("topology", {})
        if topo_cfg.get("enabled", False):
            degrees = [d for _, d in B.degree()]
            deg_mean = statistics.mean(degrees) if degrees else 0.0
            deg_std = statistics.stdev(degrees) if len(degrees) > 1 else 0.0
            
            from scipy.stats import skew
            deg_skew = skew(degrees) if len(degrees) > 2 else 0.0

            components = list(nx.connected_components(B))
            n_comp = len(components)
            lg_comp_frac = len(max(components, key=len)) / B.number_of_nodes() if components else 0.0

            try:
                proj_v = nx.bipartite.projected_graph(B, range(1, n + 1))
                clustering = nx.average_clustering(proj_v)
            except Exception:
                clustering = 0.0

            features.update({
                "degree_mean": float(deg_mean),
                "degree_std": float(deg_std),
                "degree_skew": float(deg_skew),
                "components": float(n_comp),
                "largest_component_frac": float(lg_comp_frac),
                "projection_clustering": float(clustering)
            })

        spec_cfg = self.families.get("spectral_lite", {})
        if spec_cfg.get("enabled", False):
            try:
                import scipy.linalg as la
                L_dense = nx.normalized_laplacian_matrix(B).toarray()
                eigs = la.eigvalsh(L_dense)
                eigs = np.sort(np.abs(eigs))
            except Exception:
                eigs = np.zeros(2)

            lambda2 = eigs[1] if len(eigs) > 1 else 0.0
            gap = eigs[2] - eigs[1] if len(eigs) > 2 else 0.0

            p = eigs / (np.sum(eigs) + 1e-12)
            p = p[p > 0]
            entropy = -np.sum(p * np.log(p))

            features.update({
                "lambda2": float(lambda2),
                "spectral_gap": float(gap),
                "spectral_entropy": float(entropy)
            })

        # Add some fallback logic to copy basic data directly so it doesn't fail vector extraction
        if "algebra" in self.families and self.families["algebra"].get("enabled", False):
            alg = self.extract_algebra_demo(instance)
            features.update(alg)
        else:
            # We must output algo so target_D can be established if algebra is disabled
            horn = sum(1 for c in clauses if sum(1 for lit in c if lit > 0) <= 1)
            features["algebra_horn_fraction"] = round(horn / max(1, len(clauses)), 6)

        return features, "PROD"


    def extract_all(self, instance: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
        if self.mode == "prod_lite":
            return self.extract_prod_lite(instance)

        spec = self.extract_spectral_demo(instance)
        thermo = self.extract_thermo_demo(instance)
        alg = self.extract_algebra_demo(instance)
        merged = {**spec, **thermo, **alg}
        return merged, "DEMO"


# =============================================================================
# VECTOR COMPRESSION (DEMO): correlaciones H y D
# =============================================================================

class VectorCompressor:
    def compress(self, df, target_H, target_D, max_dims: int = 7) -> Dict[str, Any]:
        import pandas as pd

        # columnas numéricas (excluye ids/strings)
        exclude = {"instance_id", "generator", "target_H", "target_D", "n_vars", "n_clauses"}
        feature_cols = [c for c in df.columns if c not in exclude and pd.api.types.is_numeric_dtype(df[c])]
        if len(feature_cols) < 3:
            feature_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]

        cors_H = []
        cors_D = []
        for c in feature_cols:
            try:
                h = abs(df[c].corr(target_H))
                d = abs(df[c].corr(target_D))
                cors_H.append((c, 0.0 if pd.isna(h) else float(h)))
                cors_D.append((c, 0.0 if pd.isna(d) else float(d)))
            except Exception:
                cors_H.append((c, 0.0))
                cors_D.append((c, 0.0))

        cors_H.sort(key=lambda x: x[1], reverse=True)
        cors_D.sort(key=lambda x: x[1], reverse=True)

        top_H = [c for c, _ in cors_H[: max_dims * 2]]
        top_D = [c for c, _ in cors_D[: max_dims * 2]]

        selected = list(set(top_H) & set(top_D))
        if len(selected) < 3:
            selected = top_H[:max_dims]
        selected = selected[:max_dims]

        # estabilidad proxy (no gate): var/mean
        stability_scores = {}
        for c in selected:
            mu = float(df[c].mean())
            sd = float(df[c].std())
            var_ratio = sd / (abs(mu) + 1e-8)
            stability_scores[c] = 1 / (1 + abs(var_ratio))

        return {
            "coordinates": selected,
            "formula": {c: f"zscore({c})" for c in selected},
            "stability_score": round(float(np.mean(list(stability_scores.values()))), 6),
            "correlation_H": {c: round(dict(cors_H).get(c, 0.0), 6) for c in selected},
            "correlation_D": {c: round(dict(cors_D).get(c, 0.0), 6) for c in selected},
            "interpretation": self._interpret(selected),
        }

    def _interpret(self, coords: List[str]) -> str:
        fam = []
        if any("spectral" in c or "trace" in c or "rank" in c for c in coords):
            fam.append("Espectral/estructura (Poincaré discreto)")
        if any("thermo" in c or "beta" in c or "Z" in c for c in coords):
            fam.append("Termodinámica (paisaje energético)")
        if any("algebra" in c or "horn" in c or "2sat" in c for c in coords):
            fam.append("Álgebra/simplificación (normalización)")
        if not fam:
            fam.append("Señales mixtas")
        return " | ".join(fam)


# =============================================================================
# GATES REALES: Δv sobre transformaciones
# =============================================================================

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

def compute_stats(df, coords: List[str]) -> Dict[str, Tuple[float, float]]:
    stats = {}
    for c in coords:
        mu = float(df[c].mean())
        sd = float(df[c].std())
        stats[c] = (mu, sd)
    return stats

class AdversarialGates:
    """
    Gates:
      1) Semantics (planted vs random) - señal moderada
      2) Permutation invariance - Δv pequeño tras renombrar variables
      3) Scale generalization - drift acotado entre tamaños
      4) Cross-generator - CV acotado entre generadores
      5) Perturbation robustness - Δv pequeño tras perturbar 2% cláusulas
    """
    def __init__(self, extractor: SignatureExtractor):
        self.extractor = extractor

    def run_all(
        self,
        v: Dict[str, Any],
        base_df,
        instances_by_id: Dict[str, Dict[str, Any]],
        plan_gates: Dict[str, Any],
        run_mode: str,
    ) -> Dict[str, Any]:
        coords = v["coordinates"]
        stats = compute_stats(base_df, coords)

        r = {}
        r["gate_1_semantics"] = self._gate_semantics(base_df, coords)
        r["gate_2_permutation"] = self._gate_permutation(base_df, instances_by_id, coords, stats, plan_gates)
        r["gate_3_scale"] = self._gate_scale(base_df, coords, plan_gates)
        r["gate_4_generator"] = self._gate_generator(base_df, coords, plan_gates)
        r["gate_5_perturbation"] = self._gate_perturbation(base_df, instances_by_id, coords, stats, plan_gates)

        all_pass = all(x.get("status") == "PASS" for x in r.values())
        r["final_verdict"] = "VECTOR_VALIDATED" if all_pass else "VECTOR_REJECTED"
        r["run_mode"] = run_mode
        return r

    def _gate_semantics(self, df, coords: List[str]) -> Dict[str, Any]:
        if "generator" not in df.columns:
            return {"status": "INCONCLUSIVE", "score": 0.5, "details": "No generator metadata"}

        planted = df["generator"] == "planted_sat"
        rnd = df["generator"] == "random_kcnf"
        if planted.sum() == 0 or rnd.sum() == 0:
            return {"status": "INCONCLUSIVE", "score": 0.5, "details": "Insufficient generator diversity"}

        planted_mean = float(df.loc[planted, coords].mean().mean())
        rnd_mean = float(df.loc[rnd, coords].mean().mean())
        denom = float(df[coords].std().mean()) + 1e-8
        dist = abs(planted_mean - rnd_mean) / denom

        # “moderado deseable”: ni 0 (no ve diferencia) ni enorme (trivial)
        score = max(0.0, 1.0 - abs(dist - 1.0) / 1.0)  # ideal dist≈1
        status = "PASS" if score >= 0.5 else "FAIL"
        return {"status": status, "score": round(float(score), 6), "details": f"norm-dist planted vs random = {dist:.4f} (ideal ~1.0)"}

    def _gate_permutation(self, base_df, instances_by_id, coords, stats, plan_gates) -> Dict[str, Any]:
        cfg = plan_gates.get("gate_2_permutation", {})
        n_perms = int(cfg.get("n_permutations", 5))
        threshold = float(cfg.get("delta_v_threshold", 0.35))

        # muestrea instancias base
        sample_n = int(cfg.get("sample_instances", 30))
        ids = list(instances_by_id.keys())
        ids = [i for i in ids if "|perm:" not in i and "|pert:" not in i]
        sample_ids = ids[:sample_n] if len(ids) <= sample_n else random.Random(123).sample(ids, sample_n)

        deltas = []
        for inst_id in sample_ids:
            inst = instances_by_id[inst_id]
            base_feat, _ = self.extractor.extract_all(inst)
            base_v = compute_v_vector(base_feat, coords, stats)

            # varias permutaciones
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
        return {
            "status": status,
            "score": round(float(score), 6),
            "details": f"worst Δv (perm) = {worst_case:.4f}, threshold = {threshold:.4f}, samples = {len(deltas)}",
        }

    def _gate_scale(self, df, coords, plan_gates) -> Dict[str, Any]:
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

    def _gate_generator(self, df, coords, plan_gates) -> Dict[str, Any]:
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
        return {"status": status, "score": round(float(score), 6), "details": f"generator means={means}, CV={cv:.4f}, max={max_cv:.4f}"}

    def _gate_perturbation(self, base_df, instances_by_id, coords, stats, plan_gates) -> Dict[str, Any]:
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
        return {
            "status": status,
            "score": round(float(score), 6),
            "details": f"worst Δv (pert rate={rate}) = {worst:.4f}, threshold = {threshold:.4f}, samples={len(deltas)}",
        }


# =============================================================================
# ATLAS: frontera por variabilidad local kNN de H
# =============================================================================

def knn_indices(vmat: np.ndarray, k: int) -> List[List[int]]:
    """
    kNN por distancia euclídea O(N^2) (evita dependencia sklearn).
    Para N moderado (demo) está bien.
    """
    n = vmat.shape[0]
    out: List[List[int]] = []
    for i in range(n):
        d = np.sum((vmat - vmat[i]) ** 2, axis=1)
        # argsort, excluye i
        idx = np.argsort(d)
        idx = [int(j) for j in idx if int(j) != i][:k]
        out.append(idx)
    return out

def build_frontier_knn(df, coords: List[str], k: int = 10, quantile: float = 0.8) -> Dict[str, Any]:
    """
    frontera = puntos con alta std(local) de target_H entre kNN en espacio v.
    """
    vmat = df[coords].to_numpy(dtype=float)
    # normaliza coords para distancia
    mu = vmat.mean(axis=0)
    sd = vmat.std(axis=0) + 1e-8
    vmat_z = (vmat - mu) / sd

    neigh = knn_indices(vmat_z, k=k)
    H = df["target_H"].to_numpy(dtype=float)

    local_std = np.zeros(len(df), dtype=float)
    for i, ns in enumerate(neigh):
        if not ns:
            local_std[i] = 0.0
        else:
            local_std[i] = float(np.std(H[ns]))

    thr = float(np.quantile(local_std, quantile))
    frontier_mask = local_std >= thr
    width = float(np.std(local_std[frontier_mask])) if frontier_mask.any() else 0.0

    return {
        "k": k,
        "quantile": quantile,
        "threshold": round(thr, 6),
        "frontier_fraction": round(float(frontier_mask.mean()), 6),
        "frontier_width": round(width, 6),
        "law_of_frontier": f"Frontier = top {int((1-quantile)*100)}% local-std(H) in kNN(v), width≈{width:.4f}",
        "local_std_summary": {
            "min": round(float(local_std.min()), 6),
            "median": round(float(np.median(local_std)), 6),
            "max": round(float(local_std.max()), 6),
        },
        "frontier_mask": frontier_mask.tolist(),
        "local_std": local_std.tolist(),
    }


# =============================================================================
# ORCHESTRATOR
# =============================================================================

class NPAtlasDriver:
    def __init__(self, plan_path: str):
        with open(plan_path, "r", encoding="utf-8") as f:
            self.plan = json.load(f)

        self.ps = self.plan.get("parameter_space", {})
        self.sc = self.plan.get("solver_config", {})
        self.comp = self.plan.get("compression", {})
        self.gates_cfg = self.plan.get("adversarial_gates", {})
        self.ledger_cfg = self.plan.get("ledger", {})

        self.ledger = Ledger(self.ledger_cfg.get("path", "ledger.jsonl"))
        self.gen = SATGenerator(seed=42)
        self.solver = MockSolver()
        self.extractor = SignatureExtractor(self.plan)
        self.compressor = VectorCompressor()
        self.gates = AdversarialGates(self.extractor)

        Path("evidence").mkdir(exist_ok=True)
        Path("data").mkdir(exist_ok=True)

    def run_campaign(self) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        print("=" * 72)
        print("NP-ATLAS v0.3 - POINCARÉ×BSD Vector Hunt")
        print("=" * 72)
        print(f"campaign_id: {self.plan.get('campaign_id', 'unnamed')}")
        print(f"ledger: {self.ledger.path}")

        instances = self._generate_instances()
        instances_by_id = {x["instance_id"]: x for x in instances}

        telemetry = self._solve_instances(instances)
        df, run_mode = self._extract_signatures(instances)

        v, df = self._compress_vector(df, telemetry, run_mode)
        gate_results = self.gates.run_all(v, df, instances_by_id, self.gates_cfg, run_mode)
        atlas = self._build_atlas(df, v)

        self._finalize(v, gate_results, atlas, df)
        return v, gate_results, atlas

    def _generate_instances(self) -> List[Dict[str, Any]]:
        print("\n[PHASE 1] Generate instances")
        n_vars_list = self.ps.get("n_variables", [80, 100, 120])
        ratios = self.ps.get("ratios_m_n", [3.5, 4.0, 4.5, 5.0, 5.5])
        seeds_per = int(self.ps.get("seeds_per_point", 5))
        k = int(self.ps.get("k", 3))

        instances: List[Dict[str, Any]] = []
        for n in n_vars_list:
            for ratio in ratios:
                m = int(round(n * float(ratio)))
                for s in range(seeds_per):
                    # Determinismo: seed de generador = función del grid-point
                    seed_rnd = _u32_from_sha256(f"rnd|n={n}|m={m}|k={k}|s={s}")
                    seed_plt = _u32_from_sha256(f"plt|n={n}|m={m}|k={k}|s={s}")

                    instances.append(self.gen.random_kcnf(n, m, k=k, seed=seed_rnd))
                    instances.append(self.gen.planted_sat(n, m, k=k, seed=seed_plt))

        self.ledger.record("GENERATION_DONE", {
            "n_instances": len(instances),
            "n_variables": n_vars_list,
            "ratios": ratios,
            "seeds_per_point": seeds_per,
            "k": k,
        })
        print(f"  generated: {len(instances)}")
        return instances

    def _solve_instances(self, instances: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        print("\n[PHASE 2] Solve instances (MockSolver DEMO)")
        timeout = int(self.sc.get("timeout_seconds", 3600))
        telemetry: List[Dict[str, Any]] = []
        for i, inst in enumerate(instances):
            tel = self.solver.solve(inst, timeout=timeout)
            telemetry.append(tel)
            if i % 25 == 0:
                print(f"  progress: {i}/{len(instances)}")

            self.ledger.record("INSTANCE_SOLVED", {
                "instance_id": inst["instance_id"],
                "generator": inst["generator"],
                "n_vars": inst["n_vars"],
                "ratio": inst["ratio"],
                "result": tel["result"],
                "runtime_seconds": tel["runtime_seconds"],
                "decisions": tel["decisions"],
                "conflicts": tel["conflicts"],
            })
        return telemetry

    def _extract_signatures(self, instances: List[Dict[str, Any]]):
        print("\n[PHASE 3] Extract signatures (DEMO proxies, deterministic)")
        import pandas as pd

        records = []
        run_modes = set()
        for inst in instances:
            feats, run_mode = self.extractor.extract_all(inst)
            run_modes.add(run_mode)
            records.append({
                "instance_id": inst["instance_id"],
                "generator": inst["generator"],
                "n_vars": inst["n_vars"],
                "ratio": inst["ratio"],
                **feats,
            })

        df = pd.DataFrame(records)
        run_mode = "DEMO" if "DEMO" in run_modes else "PROD"
        print(f"  instances: {len(df)} | features: {len(df.columns) - 4} | run_mode: {run_mode}")
        self.ledger.record("SIGNATURES_DONE", {
            "n_instances": len(df),
            "n_features": int(len(df.columns) - 4),
            "run_mode": run_mode,
        })
        return df, run_mode

    def _compress_vector(self, df, telemetry: List[Dict[str, Any]], run_mode: str) -> Tuple[Dict[str, Any], Any]:
        print("\n[PHASE 4] Compress -> vector v")
        import pandas as pd

        tel_df = pd.DataFrame(telemetry)
        # Alineación 1:1 por orden de generación (mismo orden)
        df = df.copy()
        df["target_H"] = np.log1p(tel_df["runtime_seconds"].to_numpy(dtype=float))

        # target_D robusto: usa horn_fraction si existe, si no rellena 0.5
        if "algebra_horn_fraction" in df.columns:
            horn = df["algebra_horn_fraction"].astype(float).fillna(0.5)
        else:
            horn = 0.5
        df["target_D"] = df["ratio"].astype(float) * (1.0 - horn)

        max_dims = int(self.comp.get("target_dimensions", 7))
        v = self.compressor.compress(df, df["target_H"], df["target_D"], max_dims=max_dims)
        v["run_mode"] = run_mode
        v["schema_version"] = "NP-ATLAS-v0.3"
        self.ledger.record("VECTOR_COMPRESSION_DONE", {
            "dimensions": len(v["coordinates"]),
            "coordinates": v["coordinates"],
            "stability_score": v.get("stability_score"),
            "run_mode": run_mode,
        })
        print(f"  dims={len(v['coordinates'])} coords={v['coordinates']}")
        return v, df

    def _build_atlas(self, df, v: Dict[str, Any]) -> Dict[str, Any]:
        print("\n[PHASE 6] Build NP-Atlas (frontier via kNN local std of H)")
        coords = v["coordinates"]
        if len(coords) < 2:
            return {"frontier_identified": False, "reason": "insufficient_dims", "n_points": int(len(df))}

        k = int(self.plan.get("atlas", {}).get("knn_k", 10))
        q = float(self.plan.get("atlas", {}).get("frontier_quantile", 0.8))
        atlas = build_frontier_knn(df, coords=coords, k=k, quantile=q)
        atlas["frontier_identified"] = True
        atlas["n_points"] = int(len(df))
        atlas["coords"] = coords

        # guardar atlas.csv (primeras 2 coords + frontier flag + local_std)
        import pandas as pd
        mask = np.array(atlas["frontier_mask"], dtype=bool)
        local_std = np.array(atlas["local_std"], dtype=float)

        out = df[["instance_id", "generator", "n_vars", "ratio"] + coords[:2] + ["target_H", "target_D"]].copy()
        out["frontier_flag"] = mask
        out["local_std_H_knn"] = local_std
        out.to_csv("evidence/atlas.csv", index=False)

        self.ledger.record("ATLAS_DONE", {
            "n_points": int(len(df)),
            "knn_k": k,
            "frontier_quantile": q,
            "frontier_fraction": atlas.get("frontier_fraction"),
            "frontier_width": atlas.get("frontier_width"),
        })
        print(f"  frontier_fraction={atlas.get('frontier_fraction')} width={atlas.get('frontier_width')}")
        return atlas

    def _finalize(self, v, gates, atlas, df) -> None:
        print("\n[PHASE 7] Finalize artifacts")
        # vector.json
        with open("evidence/vector.json", "w", encoding="utf-8") as f:
            json.dump(v, f, indent=2)

        # frontier.json
        with open("evidence/frontier.json", "w", encoding="utf-8") as f:
            json.dump(atlas, f, indent=2)

        # obstructions.jsonl
        with open("evidence/obstructions.jsonl", "w", encoding="utf-8") as f:
            for gate_id, res in gates.items():
                if gate_id in ("final_verdict", "run_mode"):
                    continue
                f.write(json.dumps({"gate": gate_id, "ts": now_z(), **res}) + "\n")

        # ledger validation
        valid, msg = self.ledger.validate_chain()

        # report.md
        report = self._report(v, gates, atlas, valid, msg, df)
        with open("evidence/report.md", "w", encoding="utf-8") as f:
            f.write(report)

        # campaign done
        self.ledger.record("CAMPAIGN_DONE", {
            "final_verdict": gates.get("final_verdict"),
            "ledger_valid": bool(valid),
            "ledger_msg": msg,
            "artifacts": [
                "evidence/vector.json",
                "evidence/atlas.csv",
                "evidence/frontier.json",
                "evidence/obstructions.jsonl",
                "evidence/report.md",
                str(self.ledger.path),
            ],
        })

        print("  [OK] evidence/vector.json")
        print("  [OK] evidence/atlas.csv")
        print("  [OK] evidence/frontier.json")
        print("  [OK] evidence/obstructions.jsonl")
        print("  [OK] evidence/report.md")
        print(f"  [OK] ledger.jsonl ({msg})")
        print("\n" + "=" * 72)
        print("CAMPAIGN COMPLETE")
        print("=" * 72)
        print(f"verdict: {gates.get('final_verdict')}")
        passed = sum(1 for k, x in gates.items() if isinstance(x, dict) and x.get("status") == "PASS")
        print(f"gates passed: {passed}/5")
        print(f"run_mode: {gates.get('run_mode')}")
        print("=" * 72)

    def _report(self, v, gates, atlas, ledger_valid, ledger_msg, df) -> str:
        coords = v["coordinates"]
        lines = []
        lines.append("# NP-ATLAS Campaign Report (v0.3)\n")
        lines.append("## Metadata\n")
        lines.append(f"- **campaign_id**: {self.plan.get('campaign_id','unnamed')}\n")
        lines.append(f"- **timestamp**: {now_z()}\n")
        lines.append(f"- **run_mode**: {gates.get('run_mode')}\n")
        lines.append(f"- **ledger_valid**: {'✓' if ledger_valid else '✗'} ({ledger_msg})\n")

        lines.append("\n## Vector v\n")
        lines.append(f"- **dims**: {len(coords)}\n")
        lines.append(f"- **coords**: `{coords}`\n")
        lines.append(f"- **interpretation**: {v.get('interpretation')}\n")
        lines.append(f"- **stability_score (proxy)**: {v.get('stability_score')}\n")

        lines.append("\n### Coordinate detail\n")
        lines.append("| coord | corr(H) | corr(D) | formula |\n")
        lines.append("|---|---:|---:|---|\n")
        for c in coords:
            ch = v.get("correlation_H", {}).get(c, "NA")
            cd = v.get("correlation_D", {}).get(c, "NA")
            fm = v.get("formula", {}).get(c, "NA")
            lines.append(f"| {c} | {ch} | {cd} | {fm} |\n")

        lines.append("\n## Adversarial gates\n")
        lines.append(f"**final_verdict**: {gates.get('final_verdict')}\n\n")
        lines.append("| gate | status | score | details |\n")
        lines.append("|---|---|---:|---|\n")
        for k, res in gates.items():
            if not isinstance(res, dict):
                continue
            if k.startswith("gate_"):
                lines.append(f"| {k} | {res.get('status')} | {res.get('score')} | {res.get('details')} |\n")

        lines.append("\n## Atlas / Frontier\n")
        lines.append(f"- **frontier_identified**: {atlas.get('frontier_identified')}\n")
        lines.append(f"- **law_of_frontier**: {atlas.get('law_of_frontier')}\n")
        lines.append(f"- **frontier_fraction**: {atlas.get('frontier_fraction')}\n")
        lines.append(f"- **frontier_width**: {atlas.get('frontier_width')}\n")
        if "local_std_summary" in atlas:
            lines.append(f"- **local_std(H) summary**: {atlas['local_std_summary']}\n")

        lines.append("\n## Notes\n")
        if gates.get("run_mode") == "DEMO":
            lines.append("- This run uses DEMO_PROXY signatures (deterministic). Replace SignatureExtractor for production.\n")
        lines.append("- Gates 2 and 5 are *real* (transform instance -> recompute features -> compute Δv).\n")
        lines.append("- Frontier is defined by kNN-local variability of hardness H, capturing local→global breakdown.\n")

        return "".join(lines)


# =============================================================================
# MAIN
# =============================================================================

def ensure_default_plan(path: str) -> None:
    p = Path(path)
    if p.exists():
        return

    default = {
        "schema_version": "NP-ATLAS-v0.3",
        "campaign_id": "NPX-DEMO-003",
        "parameter_space": {
            "n_variables": [80, 100, 120],
            "ratios_m_n": [3.5, 4.0, 4.5, 5.0, 5.5],
            "seeds_per_point": 6,
            "k": 3
        },
        "solver_config": {
            "timeout_seconds": 3600
        },
        "compression": {
            "target_dimensions": 7
        },
        "adversarial_gates": {
            "gate_2_permutation": {
                "n_permutations": 5,
                "sample_instances": 30,
                "delta_v_threshold": 0.35
            },
            "gate_3_scale": {
                "train_n": 80,
                "test_n": 120,
                "max_relative_drift": 0.25
            },
            "gate_4_generator": {
                "max_cv": 0.6
            },
            "gate_5_perturbation": {
                "perturbation_rate": 0.02,
                "sample_instances": 30,
                "delta_v_threshold": 0.50
            }
        },
        "atlas": {
            "knn_k": 10,
            "frontier_quantile": 0.8
        },
        "ledger": {
            "path": "ledger.jsonl"
        }
    }
    with open(p, "w", encoding="utf-8") as f:
        json.dump(default, f, indent=2)
    print(f"Created default plan: {path}")

def main() -> int:
    parser = argparse.ArgumentParser(description="NP-ATLAS v0.3 - Vector Hunt")
    parser.add_argument("--plan", default="plan.json", help="Path to plan.json")
    args = parser.parse_args()

    ensure_default_plan(args.plan)

    driver = NPAtlasDriver(args.plan)
    _, gates, _ = driver.run_campaign()
    return 0 if gates.get("final_verdict") == "VECTOR_VALIDATED" else 1

if __name__ == "__main__":
    raise SystemExit(main())
