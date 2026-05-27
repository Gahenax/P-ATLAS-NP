#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GAHENAX_LLL_WARFARE_PATCHKIT.py
==============================
Drop-in patchkit for "P over NP" hardening to compete vs LLL at DIM >= 8.
"""

from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

@dataclass(frozen=True)
class FileSpec:
    path: str
    content: str

SAFE_MATH = r'''# -*- coding: utf-8 -*-
# safe_math.py
from __future__ import annotations

import numpy as np
from dataclasses import dataclass


@dataclass
class SanityStats:
    clamp_log1p_frac: float = 0.0
    clamp_log1p_count: int = 0
    clamp_sqrt_count: int = 0
    clamp_div_count: int = 0
    nonfinite_hits: int = 0


def sanitize_array(x: np.ndarray, stats: SanityStats) -> np.ndarray:
    m = ~np.isfinite(x)
    if m.any():
        stats.nonfinite_hits += int(m.sum())
        x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    return x


def safe_log1p(x: np.ndarray, eps_dom: float, stats: SanityStats) -> np.ndarray:
    lo = -1.0 + eps_dom
    m = x <= lo
    if m.any():
        stats.clamp_log1p_count += int(m.sum())
        stats.clamp_log1p_frac = float(m.mean())
        x = x.copy()
        x[m] = lo
    return np.log1p(x)


def safe_sqrt(x: np.ndarray, eps_dom: float, stats: SanityStats) -> np.ndarray:
    m = x < 0.0
    if m.any():
        stats.clamp_sqrt_count += int(m.sum())
        x = x.copy()
        x[m] = 0.0
    return np.sqrt(x + eps_dom)


def safe_div(a: np.ndarray, b: np.ndarray, eps_div: float, stats: SanityStats) -> np.ndarray:
    m = np.abs(b) < eps_div
    if m.any():
        stats.clamp_div_count += int(m.sum())
        b = b.copy()
        b[m] = np.sign(b[m]) * eps_div
        b[b == 0.0] = eps_div
    return a / b
'''

HARDENING = r'''# -*- coding: utf-8 -*-
# hardening.py
from __future__ import annotations

import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass
class HardeningConfig:
    eps_norm: float = 1e-12
    eps_dom: float = 1e-12
    eps_div: float = 1e-12

    fuse_window: int = 32
    tau_growth: float = 0.35          # median delta(log(norm)) above this => abort
    tau_cond_proxy: float = 1e10      # condition proxy above this => abort
    tau_sanitize_frac: float = 0.02   # clamp fraction above this => abort

    max_repeat_fail: int = 3
    toxic_cooldown: int = 200         # iterations to skip a toxic seed

    stagnation_window: int = 64       # optional: abort if no improvement
    stagnation_tol: float = 0.0       # improvement threshold (score must improve by > tol)


@dataclass
class UAStats:
    allocated: float
    spent: float = 0.0
    refund: float = 0.0


@dataclass
class SeedScore:
    fail_count: int = 0
    toxic_until_iter: int = 0
    last_fail_mode: str = ""


@dataclass
class FuseState:
    norm_log_hist: List[float] = field(default_factory=list)
    cond_proxy_hist: List[float] = field(default_factory=list)
    sanitize_frac_hist: List[float] = field(default_factory=list)
    score_hist: List[float] = field(default_factory=list)


def condition_proxy(A: np.ndarray, eps_norm: float) -> float:
    # Cheap proxy: Frobenius norm divided by min row norm.
    fro = float(np.linalg.norm(A, ord="fro"))
    row = np.linalg.norm(A, axis=1)
    mn = float(max(np.min(row), eps_norm))
    return fro / mn


def find_bad_rows(A: np.ndarray, eps_norm: float) -> List[int]:
    row = np.linalg.norm(A, axis=1)
    m = (~np.isfinite(row)) | (row < eps_norm)
    return np.where(m)[0].tolist()


def zero_isolation_reset(A: np.ndarray, idx: int, rng: np.random.Generator, eps_norm: float) -> np.ndarray:
    """
    Replace only row idx with a bounded random vector and light re-orthogonalization.
    Keeps universe alive without full restart.
    """
    n = A.shape[1]
    r = rng.standard_normal(n)

    others = np.delete(A, idx, axis=0)
    denom = np.sum(others * others, axis=1) + eps_norm
    proj = (others @ r) / denom
    r = r - (proj[:, None] * others).sum(axis=0)

    nr = float(max(np.linalg.norm(r), eps_norm))
    r = r / nr

    A2 = A.copy()
    A2[idx] = r
    return A2


def fuse_should_abort(fuse: FuseState, cfg: HardeningConfig) -> Tuple[bool, str]:
    w = cfg.fuse_window

    # 1) Growth fuse
    if len(fuse.norm_log_hist) >= w:
        hist = np.array(fuse.norm_log_hist[-w:], float)
        d = np.diff(hist)
        if float(np.median(d)) > cfg.tau_growth:
            return True, "entropy_growth"

    # 2) Condition fuse
    if len(fuse.cond_proxy_hist) >= w:
        if float(np.median(fuse.cond_proxy_hist[-w:])) > cfg.tau_cond_proxy:
            return True, "condition_collapse"

    # 3) Sanitization fuse
    if len(fuse.sanitize_frac_hist) >= w:
        if float(np.median(fuse.sanitize_frac_hist[-w:])) > cfg.tau_sanitize_frac:
            return True, "sanitize_overuse"

    return False, ""


def stagnation_should_abort(fuse: FuseState, cfg: HardeningConfig) -> Tuple[bool, str]:
    w = cfg.stagnation_window
    if w <= 1:
        return False, ""
    if len(fuse.score_hist) < w:
        return False, ""

    hist = np.array(fuse.score_hist[-w:], float)
    best_prev = float(np.min(hist[:-1]))
    now = float(hist[-1])
    # If no improvement beyond tol
    if now >= best_prev - cfg.stagnation_tol:
        return True, "stagnation"
    return False, ""


def ua_refund_on_abort(ua: UAStats) -> None:
    ua.refund += max(0.0, ua.allocated - ua.spent)


def seed_is_toxic(scores: Dict[int, SeedScore], seed: int, iter_i: int) -> bool:
    s = scores.get(seed)
    return (s is not None) and (iter_i < s.toxic_until_iter)


def mark_seed_fail(scores: Dict[int, SeedScore], seed: int, iter_i: int, cfg: HardeningConfig, mode: str) -> None:
    s = scores.setdefault(seed, SeedScore())
    s.fail_count += 1
    s.last_fail_mode = mode
    if s.fail_count >= cfg.max_repeat_fail:
        s.toxic_until_iter = iter_i + cfg.toxic_cooldown


def adaptive_retry_tweak(cfg: HardeningConfig, fail_mode: str) -> HardeningConfig:
    """
    Returns a modified config for retry attempts based on failure mode.
    Keep this conservative and monotonic.
    """
    c = HardeningConfig(**cfg.__dict__)
    if fail_mode == "entropy_growth":
        c.eps_norm *= 10.0
        c.tau_growth *= 0.9
    elif fail_mode == "condition_collapse":
        c.eps_norm *= 10.0
        c.tau_cond_proxy *= 0.9
    elif fail_mode == "sanitize_overuse":
        c.eps_dom *= 10.0
        c.tau_sanitize_frac *= 0.9
    elif fail_mode == "nonfinite":
        c.eps_norm *= 10.0
        c.eps_dom *= 10.0
        c.eps_div *= 10.0
    elif fail_mode == "stagnation":
        c.tau_growth *= 0.95
    return c
'''

GOV_RUNTIME = r'''# -*- coding: utf-8 -*-
# governance_runtime.py
from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional

import numpy as np

from safe_math import SanityStats, sanitize_array
from hardening import (
    HardeningConfig, UAStats, FuseState,
    condition_proxy, find_bad_rows, zero_isolation_reset,
    fuse_should_abort, stagnation_should_abort,
    ua_refund_on_abort, seed_is_toxic, mark_seed_fail,
    adaptive_retry_tweak
)

StepFn = Callable[[np.ndarray, np.random.Generator, HardeningConfig, SanityStats], np.ndarray]
ScoreFn = Callable[[np.ndarray], float]


def run_universe_hardened(
    seed: int,
    A_init: np.ndarray,
    step_fn: StepFn,
    score_fn: ScoreFn,
    ua_budget: float,
    iter_max: int,
    cfg: HardeningConfig,
    seed_scores: Dict[int, Any],
    global_iter0: int = 0,
) -> Dict[str, Any]:
    """
    Executes a single universe with:
    - SafeMath sanitation
    - Zero Isolation
    - Entropy fuse + optional stagnation fuse
    - UA accounting + refund
    """
    if seed_is_toxic(seed_scores, seed, global_iter0):
        return {"status": "SKIP_TOXIC", "seed": seed}

    rng = np.random.default_rng(seed)
    ua = UAStats(allocated=ua_budget)
    fuse = FuseState()
    sanity = SanityStats()
    A = A_init.copy()

    t0 = time.time()

    for t in range(iter_max):
        # 1) Sanitize
        A = sanitize_array(A, sanity)

        # 2) Zero Isolation
        for idx in find_bad_rows(A, cfg.eps_norm):
            A = zero_isolation_reset(A, idx, rng, cfg.eps_norm)

        # 3) Track fuse metrics (pre-step)
        fuse.cond_proxy_hist.append(condition_proxy(A, cfg.eps_norm))
        fuse.norm_log_hist.append(float(np.log(np.linalg.norm(A, ord="fro") + cfg.eps_norm)))
        fuse.sanitize_frac_hist.append(float(sanity.clamp_log1p_frac))

        # 4) Step
        A = step_fn(A, rng, cfg, sanity)

        ua.spent += 1.0
        if ua.spent >= ua.allocated:
            dt = time.time() - t0
            return {"status": "BUDGET_END", "seed": seed, "ua": ua, "sanity": sanity, "seconds": dt}

        # 5) Score and stagnation tracking (optional but useful)
        sc = float(score_fn(A))
        fuse.score_hist.append(sc)

        # 6) Hard invariants
        if not np.isfinite(A).all():
            ua_refund_on_abort(ua)
            mark_seed_fail(seed_scores, seed, global_iter0 + t, cfg, "nonfinite")
            dt = time.time() - t0
            return {"status": "ABORT", "seed": seed, "fail_mode": "nonfinite", "ua": ua, "sanity": sanity, "seconds": dt}

        # 7) Fuse checks
        abort, mode = fuse_should_abort(fuse, cfg)
        if abort:
            ua_refund_on_abort(ua)
            mark_seed_fail(seed_scores, seed, global_iter0 + t, cfg, mode)
            dt = time.time() - t0
            return {"status": "ABORT", "seed": seed, "fail_mode": mode, "ua": ua, "sanity": sanity, "seconds": dt}

        abort2, mode2 = stagnation_should_abort(fuse, cfg)
        if abort2:
            ua_refund_on_abort(ua)
            mark_seed_fail(seed_scores, seed, global_iter0 + t, cfg, mode2)
            dt = time.time() - t0
            return {"status": "ABORT", "seed": seed, "fail_mode": mode2, "ua": ua, "sanity": sanity, "seconds": dt}

    dt = time.time() - t0
    return {"status": "SURVIVE", "seed": seed, "ua": ua, "sanity": sanity, "seconds": dt, "score": float(score_fn(A)), "A": A}


def run_with_retries(
    seed: int,
    A_init: np.ndarray,
    step_fn: StepFn,
    score_fn: ScoreFn,
    ua_budget: float,
    iter_max: int,
    cfg: HardeningConfig,
    seed_scores: Dict[int, Any],
    retries: int = 2,
    global_iter0: int = 0,
) -> Dict[str, Any]:
    """
    Retry policy: if ABORT, tweak cfg based on fail_mode and retry with a derived seed.
    """
    out = run_universe_hardened(seed, A_init, step_fn, score_fn, ua_budget, iter_max, cfg, seed_scores, global_iter0)
    if out.get("status") != "ABORT":
        return out

    base_mode = str(out.get("fail_mode", "unknown"))
    cfg2 = adaptive_retry_tweak(cfg, base_mode)

    for k in range(retries):
        # Derived seed to avoid repeating identical chaos
        seed_k = (seed ^ (0x9E3779B97F4A7C15 & 0xFFFFFFFF)) + (k + 1) * 1337
        out_k = run_universe_hardened(seed_k, A_init, step_fn, score_fn, ua_budget, iter_max, cfg2, seed_scores, global_iter0)
        if out_k.get("status") != "ABORT":
            out_k["retry_from_seed"] = seed
            out_k["retry_fail_mode"] = base_mode
            return out_k

        cfg2 = adaptive_retry_tweak(cfg2, str(out_k.get("fail_mode", "unknown")))

    return out
'''

BENCH = r'''# -*- coding: utf-8 -*-
# bench_dim8_warfare.py
from __future__ import annotations

import json
import time
import os
import sys
from typing import Any, Dict, List, Optional

import numpy as np

# Path injection if root
sys.path.append(os.path.join(os.getcwd(), 'core'))

from governance_runtime import run_with_retries
from hardening import HardeningConfig


def example_step_fn(A: np.ndarray, rng: np.random.Generator, cfg: HardeningConfig, sanity) -> np.ndarray:
    noise = 0.01 * rng.standard_normal(A.shape)
    A2 = A + noise
    row_norms = np.linalg.norm(A2, axis=1, keepdims=True)
    row_norms = np.maximum(row_norms, cfg.eps_norm)
    A2 = A2 / row_norms
    return A2


def example_score_fn(A: np.ndarray) -> float:
    return float(np.linalg.norm(A, ord="fro"))


def run_benchmark(
    dims: List[int],
    seeds: List[int],
    ua_budget: float,
    iter_max: int,
    out_jsonl: str = "warfare_runs.jsonl",
) -> None:
    cfg = HardeningConfig()
    seed_scores: Dict[int, Any] = {}

    rows: List[Dict[str, Any]] = []
    t0 = time.time()

    for dim in dims:
        for seed in seeds:
            rng = np.random.default_rng(seed)
            A0 = rng.standard_normal((dim, dim)).astype(np.float64)

            ours = run_with_retries(
                seed=seed,
                A_init=A0,
                step_fn=example_step_fn,
                score_fn=example_score_fn,
                ua_budget=ua_budget,
                iter_max=iter_max,
                cfg=cfg,
                seed_scores=seed_scores,
                retries=2,
                global_iter0=0,
            )

            row = {
                "dim": dim,
                "seed": seed,
                "ours_status": ours.get("status"),
                "ours_fail_mode": ours.get("fail_mode", ""),
                "ours_score": ours.get("score", None),
                "ours_ua_spent": float(getattr(ours.get("ua"), "spent", ours.get("ua", {}).get("spent", 0.0)) if ours.get("ua") is not None else 0.0),
                "ours_ua_refund": float(getattr(ours.get("ua"), "refund", ours.get("ua", {}).get("refund", 0.0)) if ours.get("ua") is not None else 0.0),
                "ours_seconds": ours.get("seconds", None),
            }
            rows.append(row)

    with open(out_jsonl, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    dt = time.time() - t0

    # Summary
    succ = [r for r in rows if r["ours_status"] == "SURVIVE"]
    survival_rate = (len(succ) / max(1, len(rows)))

    print("Warfare summary")
    print(f"runs={len(rows)} dims={dims} ua_budget={ua_budget} iter_max={iter_max} wall_seconds={dt:.2f}")
    print(f"survival_rate={survival_rate:.4f}")

if __name__ == "__main__":
    dims = [8, 9, 10]
    seeds = list(range(0, 10))
    run_benchmark(dims=dims, seeds=seeds, ua_budget=200.0, iter_max=100)
'''

TESTS = r'''# -*- coding: utf-8 -*-
# tests_hardening_minimal.py
from __future__ import annotations
import numpy as np
from hardening import HardeningConfig, FuseState, fuse_should_abort, find_bad_rows, zero_isolation_reset, UAStats, ua_refund_on_abort
from safe_math import SanityStats, sanitize_array

def test_zero_isolation():
    cfg = HardeningConfig()
    rng = np.random.default_rng(123)
    A = rng.standard_normal((8, 8))
    A[3] = 0.0
    bad = find_bad_rows(A, cfg.eps_norm)
    assert 3 in bad
    A2 = zero_isolation_reset(A, 3, rng, cfg.eps_norm)
    assert np.isfinite(A2).all()

def test_sanitize():
    stats = SanityStats()
    A = np.array([[np.nan, 1.0], [np.inf, -np.inf]])
    A2 = sanitize_array(A, stats)
    assert np.isfinite(A2).all()

if __name__ == "__main__":
    test_zero_isolation()
    test_sanitize()
    print("OK")
'''

def write_files(root: Path, files: Dict[str, str]) -> None:
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

def main() -> None:
    root = Path("core").resolve()
    files: Dict[str, str] = {
        "safe_math.py": SAFE_MATH,
        "hardening.py": HARDENING,
        "governance_runtime.py": GOV_RUNTIME,
        "bench_dim8_warfare.py": BENCH,
        "tests_hardening_minimal.py": TESTS,
    }
    write_files(root, files)
    print("Patchkit written to core/")

if __name__ == "__main__":
    main()
