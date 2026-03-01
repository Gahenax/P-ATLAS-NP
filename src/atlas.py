import numpy as np
from typing import List, Dict, Any

def knn_indices(vmat: np.ndarray, k: int) -> List[List[int]]:
    """
    kNN por distancia euclídea O(N^2) (evita dependencia sklearn).
    Para N moderado (demo) está bien.
    """
    n = vmat.shape[0]
    out: List[List[int]] = []
    for i in range(n):
        d = np.sum((vmat - vmat[i]) ** 2, axis=1)
        idx = np.argsort(d)
        idx = [int(j) for j in idx if int(j) != i][:k]
        out.append(idx)
    return out

def build_frontier_knn(df, coords: List[str], k: int = 10, quantile: float = 0.8) -> Dict[str, Any]:
    """
    frontera = puntos con alta std(local) de target_H entre kNN en espacio v.
    """
    vmat = df[coords].to_numpy(dtype=float)
    mu = vmat.mean(axis=0)
    sd = vmat.std(axis=0) + 1e-8
    vmat_z = (vmat - mu) / sd

    neigh = knn_indices(vmat_z, k=k)
    H = df["target_H"].to_numpy(dtype=float)

    local_std = np.zeros(len(df), dtype=float)
    for i, ns in enumerate(neigh):
        if not ns:
            local_std[i] = 0.0
        else:
            local_std[i] = float(np.std(H[ns]))

    thr = float(np.quantile(local_std, quantile))
    frontier_mask = local_std >= thr
    width = float(np.std(local_std[frontier_mask])) if frontier_mask.any() else 0.0

    return {
        "k": k,
        "quantile": quantile,
        "threshold": round(thr, 6),
        "frontier_fraction": round(float(frontier_mask.mean()), 6),
        "frontier_width": round(width, 6),
        "law_of_frontier": f"Frontier = top {int((1-quantile)*100)}% local-std(H) in kNN(v), width≈{width:.4f}",
        "local_std_summary": {
            "min": round(float(local_std.min()), 6),
            "median": round(float(np.median(local_std)), 6),
            "max": round(float(local_std.max()), 6),
        },
        "frontier_mask": frontier_mask.tolist(),
        "local_std": local_std.tolist(),
    }
