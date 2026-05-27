# -*- coding: utf-8 -*-
# bench_p_over_np.py
import sys
import os
import numpy as np
import time
from pathlib import Path

# Fix paths
core_dir = Path("core").resolve()
sys.path.append(str(core_dir))

from GAHENAX_UA_ENGINE_V2_HARDENED import lattice_step_fn, lattice_score_fn
from governance_runtime import run_universe_hardened
from hardening import HardeningConfig

def run_test(dim, seed=1000):
    rng = np.random.default_rng(seed)
    # Challenging Knapsack-like lattice
    q = 10**8
    basis = np.eye(dim) * q
    basis[:, -1] = rng.integers(1, q, dim)
    basis = basis.astype(np.float64)
    
    ua_budget = dim * dim * 5
    iter_max = 300
    cfg = HardeningConfig(
        tau_growth=1.5,
        stagnation_window=50, 
        stagnation_tol=1e-3,
        eps_norm=1e-18
    )
    seed_scores = {}
    
    res = run_universe_hardened(seed, basis, lattice_step_fn, lattice_score_fn, ua_budget, iter_max, cfg, seed_scores)
    return res

def main():
    dims = [20, 24, 28, 32]
    seeds = [1000, 1001, 1002]
    
    print("="*110)
    print(f"{'DIM':>4}   {'Seed':>6}   {'Status':>12}   {'FailMode':>18}   {'StartNorm':>12}   {'EndNorm':>12}   {'UA':>6}   {'Rst':>4}   {'Clp':>4}")
    print("-"*110)
    
    for dim in dims:
        for seed in seeds:
            res = run_test(dim, seed)
            status = res.get("status")
            fail_mode = res.get("fail_mode", "-")
            start = res.get("initial_score", 0.0)
            end = res.get("final_score", 0.0)
            spent = res.get("ua").spent if res.get("ua") else 0
            resets = res.get("resets", 0)
            clamps = res.get("sanity").clamp_log1p_count if res.get("sanity") else 0
            
            # Progress signal check
            delta = end - start
            progress = "YES" if delta < -1.0 else "NO"
            
            print(f"{dim:4}   {seed:6}   {status:>12}   {fail_mode:>18}   {start:12.1f}   {end:12.1f}   {spent:6.0f}   {resets:4}   {clamps:4}   Prog: {progress}")
            
    print("="*110)

if __name__ == "__main__":
    main()
