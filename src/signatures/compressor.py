from typing import Dict, Any, List
import numpy as np
import pandas as pd

class VectorCompressor:
    def compress(self, df: pd.DataFrame, target_H: pd.Series, target_D: pd.Series, max_dims: int = 7) -> Dict[str, Any]:
        # columnas numéricas (excluye ids/strings)
        exclude = {"instance_id", "generator", "target_H", "target_D", "n_vars", "n_clauses"}
        feature_cols = [c for c in df.columns if c not in exclude and pd.api.types.is_numeric_dtype(df[c])]
        if len(feature_cols) < 3:
            feature_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]

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
