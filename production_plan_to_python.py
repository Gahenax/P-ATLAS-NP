#!/usr/bin/env python3
"""
production_plan_to_python.py
Imprint um plan.json para NP-ATLAS (Producción 0.1 A/B/C).

Uso:
  python production_plan_to_python.py > plan_prod_0_1.json
"""

import json
from datetime import datetime, timezone

def build_plan() -> dict:
    return {
        "schema_version": "NP-ATLAS-v0.3",
        "campaign_id": "NPX-PROD-0.1",
        "timestamp_created": datetime.now(timezone.utc).isoformat(),

        "parameter_space": {
            "n_variables": [80, 100, 120],
            "ratios_m_n": [3.5, 4.0, 4.26, 4.5, 5.0, 5.5],
            "seeds_per_point": 10,
            "generators": [
                "random_kcnf",
                "planted_sat"
            ]
        },

        "signature_mode": {
            # "demo"        -> proxies (tu v0.3)
            # "prod_lite"   -> topología real + spectral-lite sparse (Producción 0.1A)
            # "prod_thermo" -> añade MCMC/tempering (Producción 0.1B)
            "mode": "prod_lite"
        },

        "signature_families": {
            "topology": {
                "enabled": True,
                "graph": "bipartite_var_clause",
                "features": [
                    "degree_mean",
                    "degree_std",
                    "degree_skew",
                    "components",
                    "largest_component_frac",
                    "projection_clustering"
                ]
            },
            "spectral_lite": {
                "enabled": True,
                "matrix": "normalized_laplacian",
                "k_eigs": 16,
                "features": [
                    "lambda2",
                    "spectral_gap",
                    "spectral_entropy"
                ]
            },
            "thermo": {
                "enabled": False,  # Activa en Producción 0.1B
                "temperatures": [0.2, 0.5, 1.0, 2.0],
                "steps": 20000,
                "burn_in": 2000,
                "swap_every": 50
            },
            "algebra": {
                "enabled": False  # dejar apagado hasta Producción 0.2
            }
        },

        "solver_config": {
            # "mock"      -> tu solver simulado
            # "external"  -> subprocess a kissat/cadical (Producción 0.1C)
            "engine": "mock",
            "timeout_seconds": 120,
            "external": {
                "enabled": False,
                "binary_path": "kissat",   # o ruta absoluta
                "args": ["--quiet"]        # ajusta según binario
            }
        },

        "compression": {
            "target_dimensions": 7,
            "method": "corr_joint",  # luego lasso+mi
            "stability_threshold": 0.85
        },

        "adversarial_gates": {
            "gate_1_semantics": {
                "enabled": True,
                "pairs": "planted_vs_random_matched"
            },
            "gate_2_permutation": {
                "enabled": True,
                "n_permutations": 5
            },
            "gate_3_scale": {
                "enabled": True,
                "train_n": 80,
                "test_n": 120
            },
            "gate_4_generator": {
                "enabled": True,
                "holdout_generator": "planted_sat"
            },
            "gate_5_perturbation": {
                "enabled": True,
                "perturbation_rate": 0.02
            }
        },

        "atlas": {
            "method": "knn_local_variance",
            "k": 10,
            "frontier_quantile": 0.80
        },

        "ledger": {
            "path": "ledger.jsonl",
            "hash_algorithm": "sha256"
        }
    }

def main():
    plan = build_plan()
    print(json.dumps(plan, indent=2, sort_keys=False))

if __name__ == "__main__":
    main()
