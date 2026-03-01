# NP-ATLAS v0.3 — POINCARÉ×BSD Vector Hunt

> *Computational hardness mapping through geometric signatures.*

## Overview

**NP-ATLAS** is a deterministic, auditable framework for studying the complexity landscape of SAT (Boolean Satisfiability) instances by projecting them into a continuous geometric space. 

Instead of relying purely on runtime metrics, this laboratory extracts **structural signatures** from problem instances (e.g., spectral gap, thermo-critical beta limits, unit-propagation normalization) and compresses them into a lower-dimensional *v-vector*. We define Phase Transitions functionally using a K-Nearest Neighbors (kNN) variance threshold.

## Mathematical Core

The engine extracts features across three broad families:

1. **Topology & Connectivity (Discrete Poincaré):**
   - We construct a bipartite incidence graph $B(V, C)$ of variables and clauses.
   - Spectral Gap & Fiedler eigenvalue ($\lambda_2$) of the normalized Laplacian matrix proxy the "expander" qualities of the graph.
2. **Thermodynamics (Energy Landscape):**
   - We project clause-to-variable ratios into a pseudo-temperature paradigm ($\beta \sim 1/T$) where phase transitions reflect spin-glass freezing barriers.
3. **Algebraic Simplification (Horn Normalization):**
   - Resistance to 2-SAT collapses via unit-propagation chains.

## Adversarial Gates Protocol

To prevent overfitting or discovering computational "mirages," any extracted structure vector $\vec{v}$ must survive **5 Adversarial Gates**:

1. **Semantics:** Can $\vec{v}$ differentiate between purely random $k$-CNF and Planted SAT solutions?
2. **Permutation (Isomorphism):** Does the vector remain strictly invariant $\Delta v \ll \epsilon$ if variables are arbitrarily relabeled?
3. **Scale (Generalization):** Does the property hold across variable scales (e.g., $N=80 \rightarrow N=120$)?
4. **Generator Drift:** Is the cross-generator variance sufficiently small?
5. **Perturbation (Rigidity):** Does the vector resist minor structural perturbations ($\sim 2\%$ clause noise)?

## Usage

The system leverages an append-only cryptographic `Ledger` to ensure reproducibility. Executing a campaign requires a JSON plan:

```bash
# Requires Python 3.10+
pip install numpy pandas pytest networkx scipy
```

**To run the default probe:**
```bash
python np_atlas.py --plan plan.json
```

**Artefacts generated in `./evidence/`:**
* `vector.json`: The surviving $\vec{v}$ configuration and stability scores.
* `atlas.csv`: Dimensional coordinates for tracking.
* `frontier.json`: kNN variance limits identifying the actual hardness phase transitions.
* `obstructions.jsonl`: Adversarial gate failure logs.
* `report.md`: Human-readable markdown summaries.

## Verification

The integrity of the structural refactor (including the split of Generators, Solvers, Signatures, and Gates) is overseen by `pytest`.

```bash
set PYTHONPATH=.
pytest tests/
```
