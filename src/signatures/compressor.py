from typing import Dict, Any, List
import numpy as np
import pandas as pd

try:
    from sklearn.feature_selection import mutual_info_regression as _mi_regression
    _HAVE_SKLEARN = True
except ImportError:
    _HAVE_SKLEARN = False


def _score_features(df: pd.DataFrame, feature_cols: List[str], target: pd.Series) -> List[tuple]:
    """
    Score each feature against target using mutual information when sklearn is available,
    falling back to Pearson |r| otherwise. Returns sorted list of (col, score) desc.
    """
    if _HAVE_SKLEARN:
        X = df[feature_cols].fillna(0.0).to_numpy(dtype=float)
        y = target.fillna(0.0).to_numpy(dtype=float)
        try:
            scores = _mi_regression(X, y, random_state=42)
            # Normalize to [0, 1] so they're comparable to Pearson r
            max_s = scores.max() + 1e-12
            pairs = [(c, float(s / max_s)) for c, s in zip(feature_cols, scores)]
            pairs.sort(key=lambda x: x[1], reverse=True)
            return pairs
        except Exception:
            pass  # Fall through to Pearson

    # Pearson |r| fallback
    pairs = []
    for c in feature_cols:
        try:
            r = abs(float(df[c].corr(target)))
            pairs.append((c, 0.0 if pd.isna(r) else r))
        except Exception:
            pairs.append((c, 0.0))
    pairs.sort(key=lambda x: x[1], reverse=True)
    return pairs


class VectorCompressor:
    def compress(self, df: pd.DataFrame, target_H: pd.Series, target_D: pd.Series, max_dims: int = 7) -> Dict[str, Any]:
        exclude = {"instance_id", "generator", "target_H", "target_D", "n_vars", "n_clauses"}
        feature_cols = [c for c in df.columns if c not in exclude and pd.api.types.is_numeric_dtype(df[c])]
        if len(feature_cols) < 3:
            feature_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]

        scores_H = _score_features(df, feature_cols, target_H)
        scores_D = _score_features(df, feature_cols, target_D)

        # Also compute Pearson |r| for reporting (always)
        cors_H = []
        cors_D = []
        for c in feature_cols:
            try:
                h = abs(float(df[c].corr(target_H)))
                d = abs(float(df[c].corr(target_D)))
                cors_H.append((c, 0.0 if pd.isna(h) else h))
                cors_D.append((c, 0.0 if pd.isna(d) else d))
            except Exception:
                cors_H.append((c, 0.0))
                cors_D.append((c, 0.0))

        top_H = [c for c, _ in scores_H[: max_dims * 2]]
        top_D = [c for c, _ in scores_D[: max_dims * 2]]

        selected = list(set(top_H) & set(top_D))
        if len(selected) < 3:
            selected = top_H[:max_dims]
        selected = selected[:max_dims]

        # Stability proxy: lower coefficient of variation → more stable
        stability_scores = {}
        for c in selected:
            mu = float(df[c].mean())
            sd = float(df[c].std())
            var_ratio = sd / (abs(mu) + 1e-8)
            stability_scores[c] = 1.0 / (1.0 + abs(var_ratio))

        selector = "mutual_info" if _HAVE_SKLEARN else "pearson_r"
        return {
            "coordinates": selected,
            "formula": {c: f"zscore({c})" for c in selected},
            "stability_score": round(float(np.mean(list(stability_scores.values()))), 6),
            "correlation_H": {c: round(dict(cors_H).get(c, 0.0), 6) for c in selected},
            "correlation_D": {c: round(dict(cors_D).get(c, 0.0), 6) for c in selected},
            "feature_selector": selector,
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
