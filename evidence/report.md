# NP-ATLAS Campaign Report (v0.3)
## Metadata
- **campaign_id**: NPX-DEMO-003
- **timestamp**: 2026-03-01T15:39:41.519485Z
- **run_mode**: DEMO
- **ledger_valid**: ✓ (Chain valid, 3480 events)

## Vector v
- **dims**: 7
- **coords**: `['algebra_unit_prop_fixations', 'thermo_log_Z_slope', 'ratio', 'spectral_entropy_proxy', 'spectral_gap_proxy', 'incidence_rank_proxy', 'resistance_to_2sat']`
- **interpretation**: Espectral/estructura (Poincaré discreto) | Termodinámica (paisaje energético) | Álgebra/simplificación (normalización)
- **stability_score (proxy)**: 0.854534

### Coordinate detail
| coord | corr(H) | corr(D) | formula |
|---|---:|---:|---|
| algebra_unit_prop_fixations | 0.08888 | 0.247627 | zscore(algebra_unit_prop_fixations) |
| thermo_log_Z_slope | 0.239695 | 0.732664 | zscore(thermo_log_Z_slope) |
| ratio | 0.214638 | 0.932313 | zscore(ratio) |
| spectral_entropy_proxy | 0.197643 | 0.930053 | zscore(spectral_entropy_proxy) |
| spectral_gap_proxy | 0.192669 | 0.928905 | zscore(spectral_gap_proxy) |
| incidence_rank_proxy | 0.350519 | 0.099221 | zscore(incidence_rank_proxy) |
| resistance_to_2sat | 0.078622 | 0.197244 | zscore(resistance_to_2sat) |

## Adversarial gates
**final_verdict**: VECTOR_REJECTED

| gate | status | score | details |
|---|---|---:|---|
| gate_1_semantics | PASS | 1.0 | norm-dist planted vs random = 0.9759 (ideal >0.1) |
| gate_2_permutation | PASS | 0.180228 | worst delta_v (perm) = 4.0989, threshold = 5.0000, samples = 30 |
| gate_3_scale | PASS | 0.028242 | relative drift = 0.4859, max = 0.5000 |
| gate_4_generator | PASS | 0.971332 | CV=0.0172, max=0.6000 |
| gate_5_perturbation | PASS | 0.390731 | worst delta_v (pert) = 3.0463, threshold = 5.0000, samples=30 |
| gate_6_spectral_camouflage | PASS | 0.389068 | camouflage distance = 0.5193, max = 0.8500 |
| gate_7_falsifiability | FAIL | 0.0 | Falsifiability Poison detected in 1 instances: OMNITEST_POISON_001 |

## Atlas / Frontier
- **frontier_identified**: True
- **law_of_frontier**: Frontier = top 19% local-std(H) in kNN(v), width≈0.0139
- **frontier_fraction**: 0.202952
- **frontier_width**: 0.013949
- **local_std(H) summary**: {'min': 0.060701, 'median': 0.17938, 'max': 0.271273}

## Notes
- This run uses DEMO_PROXY signatures (deterministic). Replace SignatureExtractor for production.
- Gates 2 and 5 are *real* (transform instance -> recompute features -> compute Δv).
- Frontier is defined by kNN-local variability of hardness H, capturing local→global breakdown.
