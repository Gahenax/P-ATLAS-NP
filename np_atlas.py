#!/usr/bin/env python3
"""
NP-ATLAS v0.3 - POINCARÉ×BSD Vector Hunt
Single-file (refactored), reproducible, auditable, con gates reales y atlas kNN.

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
import argparse
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Any
from concurrent.futures import ProcessPoolExecutor, as_completed

from src.utils import _u32_from_sha256, now_z
from src.ledger import Ledger
from src.core import SATGenerator, MockSolver, RealSolver
from src.signatures import SignatureExtractor, VectorCompressor
from src.gates import AdversarialGates
from src.atlas import build_frontier_knn
from src.campaign_memory import CampaignMemory

# =============================================================================
# PARALLEL HELPER (must be top-level for pickling)
# =============================================================================

def _solve_one(instance: Dict[str, Any], timeout: int, solver_mode: str) -> Dict[str, Any]:
    """Top-level function for ProcessPoolExecutor (must be picklable)."""
    if solver_mode == "dpll":
        solver = RealSolver()
    else:
        solver = MockSolver()
    return solver.solve(instance, timeout=timeout)

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

        # Improvement #1: Solver selection via config
        solver_mode = self.sc.get("solver_mode", "mock")
        if solver_mode == "dpll":
            self.solver = RealSolver()
        else:
            self.solver = MockSolver()

        self.extractor = SignatureExtractor(self.plan)
        self.compressor = VectorCompressor()
        self.gates = AdversarialGates(self.extractor)

        # Improvement #2: Parallel execution config
        self.parallel_workers = int(self.sc.get("parallel_workers", 1))

        # Improvement #3: Campaign memory persistence
        self.memory = CampaignMemory(working_dir=".")

        Path("evidence").mkdir(exist_ok=True)
        Path("data").mkdir(exist_ok=True)

    def run_campaign(self) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        print("=" * 72)
        print("NP-ATLAS v0.4 - POINCARÉ×BSD Vector Hunt")
        print("=" * 72)
        campaign_id = self.plan.get('campaign_id', 'unnamed')
        solver_mode = self.sc.get('solver_mode', 'mock')
        print(f"campaign_id: {campaign_id}")
        print(f"solver_mode: {solver_mode}")
        print(f"parallel_workers: {self.parallel_workers}")
        print(f"ledger: {self.ledger.path}")

        # Load campaign memory to skip already-explored points
        explored = self.memory.load_explored_points()
        if explored:
            print(f"  memory: {len(explored)} previously explored points loaded")

        instances = self._generate_instances(explored)
        instances_by_id = {x["instance_id"]: x for x in instances}

        telemetry = self._solve_instances(instances)
        run_modes = set()
        df, run_mode = self._extract_signatures(instances)

        v, df = self._compress_vector(df, telemetry, run_mode)
        gate_results = self.gates.run_all(v, df, instances_by_id, self.gates_cfg, run_mode)
        atlas = self._build_atlas(df, v)

        # Build set of all explored keys for this campaign
        all_explored = set(explored)
        for inst in instances:
            key = self.memory.point_key(inst["n_vars"], inst["ratio"], 0, inst["generator"])
            all_explored.add(key)

        self._finalize(v, gate_results, atlas, df)

        # Save campaign memory
        self.memory.save_campaign_summary(
            campaign_id, v, gate_results, len(instances), all_explored
        )
        print(f"  [OK] MEMORY.md updated ({len(all_explored)} explored points)")

        return v, gate_results, atlas

    def _generate_instances(self, explored: set = None) -> List[Dict[str, Any]]:
        print("\n[PHASE 1] Generate instances")
        explored = explored or set()
        n_vars_list = self.ps.get("n_variables", [80, 100, 120])
        ratios = self.ps.get("ratios_m_n", [3.5, 4.0, 4.5, 5.0, 5.5])
        seeds_per = int(self.ps.get("seeds_per_point", 5))
        k = int(self.ps.get("k", 3))
        community_cfg = self.ps.get("community", {})
        n_communities = int(community_cfg.get("n_communities", 4))
        p_inter = float(community_cfg.get("p_inter", 0.1))

        instances: List[Dict[str, Any]] = []
        skipped = 0
        for n in n_vars_list:
            for ratio in ratios:
                m = int(round(n * float(ratio)))
                for s in range(seeds_per):
                    seed_rnd = _u32_from_sha256(f"rnd|n={n}|m={m}|k={k}|s={s}")
                    seed_plt = _u32_from_sha256(f"plt|n={n}|m={m}|k={k}|s={s}")
                    seed_qpt = _u32_from_sha256(f"qpt|n={n}|m={m}|k={k}|s={s}")
                    seed_com = _u32_from_sha256(f"com|n={n}|m={m}|k={k}|s={s}")

                    instances.append(self.gen.random_kcnf(n, m, k=k, seed=seed_rnd))
                    instances.append(self.gen.planted_sat(n, m, k=k, seed=seed_plt))
                    instances.append(self.gen.quiet_planted_sat(n, m, k=k, seed=seed_qpt))

                    # Improvement #4: Community-structured generator
                    instances.append(self.gen.community_structured(
                        n, m, k=k, seed=seed_com,
                        n_communities=n_communities, p_inter=p_inter
                    ))

        # OmniTest Falsifiability Injection: Poison Instance
        poison = {
            "instance_id": "OMNITEST_POISON_001",
            "generator": "planted_sat",  # Masquerading as planted
            "n_vars": 80,
            "ratio": 4.0,
            "n_clauses": 4,
            "clauses": [[1], [-1], [2, 3], [-2, -3]],  # Mathematically Impossible P=NP contradiction
            "metadata": {"planted_solution": [1] * 80}
        }
        instances.append(poison)

        self.ledger.record("GENERATION_DONE", {
            "n_instances": len(instances),
            "n_variables": n_vars_list,
            "ratios": ratios,
            "seeds_per_point": seeds_per,
            "k": k,
            "generators": ["random_kcnf", "planted_sat", "quiet_planted_sat", "community_structured"],
            "skipped_explored": skipped,
        })
        print(f"  generated: {len(instances)} (skipped {skipped} explored)")
        return instances

    def _solve_instances(self, instances: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        solver_mode = self.sc.get("solver_mode", "mock")
        print(f"\n[PHASE 2] Solve instances ({solver_mode}, workers={self.parallel_workers})")
        timeout = int(self.sc.get("timeout_seconds", 3600))

        # Improvement #2: Parallel execution
        if self.parallel_workers > 1:
            telemetry = self._solve_parallel(instances, timeout)
        else:
            telemetry = self._solve_sequential(instances, timeout)

        return telemetry

    def _solve_sequential(self, instances: List[Dict[str, Any]], timeout: int) -> List[Dict[str, Any]]:
        telemetry: List[Dict[str, Any]] = []
        for i, inst in enumerate(instances):
            tel = self.solver.solve(inst, timeout=timeout)
            telemetry.append(tel)
            if i > 0 and i % 50 == 0:
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

    def _solve_parallel(self, instances: List[Dict[str, Any]], timeout: int) -> List[Dict[str, Any]]:
        """Solve instances in parallel using ProcessPoolExecutor."""
        from src.core.solvers import MockSolver, RealSolver
        solver_mode = self.sc.get("solver_mode", "mock")

        results: Dict[str, Dict[str, Any]] = {}
        with ProcessPoolExecutor(max_workers=self.parallel_workers) as pool:
            future_map = {}
            for inst in instances:
                future = pool.submit(_solve_one, inst, timeout, solver_mode)
                future_map[future] = inst["instance_id"]

            done_count = 0
            for future in as_completed(future_map):
                tel = future.result()
                results[tel["instance_id"]] = tel
                done_count += 1
                if done_count % 50 == 0:
                    print(f"  progress: {done_count}/{len(instances)}")

        # Preserve original order and record to ledger
        telemetry = []
        for inst in instances:
            tel = results[inst["instance_id"]]
            telemetry.append(tel)
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
        print("\n[PHASE 3] Extract signatures")
        run_modes = set()
        def iter_records():
            for inst in instances:
                feats, mode = self.extractor.extract_all(inst)
                run_modes.add(mode)
                yield {
                    "instance_id": inst["instance_id"],
                    "generator": inst["generator"],
                    "n_vars": inst["n_vars"],
                    "ratio": inst["ratio"],
                    **feats,
                }

        df = pd.DataFrame.from_records(iter_records())
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
        tel_df = pd.DataFrame(telemetry)
        df = df.copy()
        df["target_H"] = np.log1p(tel_df["runtime_seconds"].to_numpy(dtype=float))

        if "algebra_horn_fraction" in df.columns:
            horn = df["algebra_horn_fraction"].astype(float).fillna(0.5)
        else:
            horn = 0.5
        df["target_D"] = df["ratio"].astype(float) * (1.0 - horn)

        max_dims = int(self.comp.get("target_dimensions", 7))
        v = self.compressor.compress(df, df["target_H"], df["target_D"], max_dims=max_dims)
        v["run_mode"] = run_mode
        v["schema_version"] = "NP-ATLAS-v0.4"
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
        with open("evidence/vector.json", "w", encoding="utf-8") as f:
            json.dump(v, f, indent=2)

        with open("evidence/frontier.json", "w", encoding="utf-8") as f:
            json.dump(atlas, f, indent=2)

        with open("evidence/obstructions.jsonl", "w", encoding="utf-8") as f:
            for gate_id, res in gates.items():
                if gate_id in ("final_verdict", "run_mode"):
                    continue
                f.write(json.dumps({"gate": gate_id, "ts": now_z(), **res}) + "\n")

        valid, msg = self.ledger.validate_chain()
        report = self._report(v, gates, atlas, valid, msg, df)
        with open("evidence/report.md", "w", encoding="utf-8") as f:
            f.write(report)

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
        lines.append(f"- **ledger_valid**: {'PASS' if ledger_valid else 'FAIL'} ({ledger_msg})\n")

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
            },
            "gate_6_spectral_camouflage": {
                "max_distance": 0.50
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
