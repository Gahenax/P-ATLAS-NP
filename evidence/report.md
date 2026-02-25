# NP-ATLAS Campaign Report (v0.3)
## Metadata
- **campaign_id**: NPX-PROD-0.1
- **timestamp**: 2026-02-25T08:01:33.904681Z
- **run_mode**: PROD
- **ledger_valid**: ✓ (Chain valid, 1282 events)

## Vector v
- **dims**: 7
- **coords**: `['lambda2', 'ratio', 'spectral_entropy', 'spectral_gap', 'largest_component_frac', 'degree_skew', 'degree_mean']`
- **interpretation**: Espectral/estructura (Poincaré discreto)
- **stability_score (proxy)**: 0.905179

### Coordinate detail
| coord | corr(H) | corr(D) | formula |
|---|---:|---:|---|
| lambda2 | 0.151531 | 0.833006 | zscore(lambda2) |
| ratio | 0.196871 | 0.926689 | zscore(ratio) |
| spectral_entropy | 0.156258 | 0.598263 | zscore(spectral_entropy) |
| spectral_gap | 0.167545 | 0.124772 | zscore(spectral_gap) |
| largest_component_frac | 0.0 | 0.0 | zscore(largest_component_frac) |
| degree_skew | 0.150378 | 0.77484 | zscore(degree_skew) |
| degree_mean | 0.16387 | 0.921664 | zscore(degree_mean) |

## Adversarial gates
**final_verdict**: VECTOR_REJECTED

| gate | status | score | details |
|---|---|---:|---|
| gate_1_semantics | FAIL | 0.006508 | norm-dist planted vs random = 0.0065 (ideal ~1.0) |
| gate_2_permutation | PASS | 1.0 | worst Δv (perm) = 0.0000, threshold = 0.3500, samples = 30 |
| gate_3_scale | PASS | 0.915873 | relative drift = 0.0210, max = 0.2500 |
| gate_4_generator | PASS | 0.999672 | generator means=[2.7037171203426853, 2.7047814506657906], CV=0.0002, max=0.6000 |
| gate_5_perturbation | FAIL | 0.0 | worst Δv (pert rate=0.02) = 1.8356, threshold = 0.5000, samples=30 |

## Atlas / Frontier
- **frontier_identified**: True
- **law_of_frontier**: Frontier = top 19% local-std(H) in kNN(v), width≈0.0175
- **frontier_fraction**: 0.2
- **frontier_width**: 0.017507
- **local_std(H) summary**: {'min': 0.038811, 'median': 0.203669, 'max': 0.32007}

## Notes
- Gates 2 and 5 are *real* (transform instance -> recompute features -> compute Δv).
- Frontier is defined by kNN-local variability of hardness H, capturing local→global breakdown.
