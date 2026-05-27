import sys
import os
import numpy as np
import time

# Ensure core is in path
sys.path.append(os.path.join(os.getcwd(), 'core'))

from hardened_runner import run_universe_hardened
from hardening import HardeningConfig
from LATTICE_SVP_OUROBOROS_WARFARE_ALLINONE import lll_reduce
from GAHENAX_UA_ENGINE_V2 import norm2_exact

def svp_step_fn(A, rng, cfg, sanity):
    """
    A single 'step' for the hardened runner.
    For this bench, we'll perform a partial LLL-like reduction 
    or a small 'mix and reduce' cycle.
    """
    n = A.shape[0]
    # Chaos move
    i, j = rng.integers(0, n, size=2)
    if i != j:
        k = rng.integers(-1, 2)
        A[i] += k * A[j]
    
    # Minimal LLL-ish greedy pass
    for i in range(1, n):
        for j in range(i-1, -1, -1):
            dot = np.dot(A[i].astype(float), A[j].astype(float))
            den = np.dot(A[j].astype(float), A[j].astype(float))
            if den > 1e-12:
                q = round(dot / den)
                if q != 0:
                    A[i] -= q * A[j]
    return A

def svp_score_fn(A):
    """Min norm found in the basis."""
    norms = np.linalg.norm(A.astype(float), axis=1)
    return float(np.min(norms))

def run_bench():
    dim = 8
    n_seeds = 10
    cfg = HardeningConfig()
    seed_scores = {}
    
    print(f"=== HARDENED BENCHMARK DIM={dim} (P over NP) ===")
    print(f"{'Seed':>6} | {'LLL Score':>12} | {'UA Score':>12} | {'Status':>12}")
    print("-" * 60)
    
    for seed in range(1000, 1000 + n_seeds):
        rng = np.random.default_rng(seed)
        # Generate a hard lattice (high condition number)
        base = rng.standard_normal((dim, dim)) * 1000
        # Add some near-dependency
        base[1] = base[0] * 1.0000001 + rng.standard_normal(dim) * 1e-6
        
        # LLL Baseline
        B_lll, _, _, _ = lll_reduce(base.copy())
        lll_score = np.linalg.norm(B_lll.astype(float), axis=1).min()
        
        # Hardened UA Run
        res = run_universe_hardened(
            seed=seed,
            A_init=base.copy(),
            step_fn=svp_step_fn,
            score_fn=svp_score_fn,
            ua_budget=1000,
            iter_max=100,
            cfg=cfg,
            seed_scores=seed_scores
        )
        
        ua_score = res.get('score', float('inf'))
        status = res['status']
        if status == "ABORT":
            status = f"ABORT({res['fail_mode']})"
            
        print(f"{seed:>6} | {lll_score:>12.4f} | {ua_score:>12.4f} | {status:>12}")

if __name__ == "__main__":
    run_bench()
