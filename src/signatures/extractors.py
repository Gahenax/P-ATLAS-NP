import math
import statistics
import numpy as np
from typing import Dict, Any, Tuple, List
from src.utils import rng_for_instance

class SignatureExtractor:
    """
    Extractor de firmas. Soporta modo DEMO (proxies) y PROD_LITE (NetworkX/SciPy reales).
    """
    def __init__(self, plan: Dict[str, Any] = None):
        self.plan = plan or {}
        self.mode = self.plan.get("signature_mode", {}).get("mode", "demo")
        self.families = self.plan.get("signature_families", {})

    def extract_spectral_demo(self, instance: Dict[str, Any]) -> Dict[str, Any]:
        rng = rng_for_instance(instance["instance_id"], salt="spectral")
        n = instance["n_vars"]
        m = instance["n_clauses"]
        ratio = instance["ratio"]
        return {
            "spectral_gap_proxy": round(0.1 + 0.4 / (1 + ratio / 4), 6),
            "spectral_entropy_proxy": round(2.0 + 2.0 * math.log1p(ratio), 6),
            "primal_trace_k2": round(m * 2 / max(n, 1), 6),
            "incidence_rank_proxy": round(min(n, m) * (0.8 + 0.2 * rng.random()), 6),
        }

    def extract_thermo_demo(self, instance: Dict[str, Any]) -> Dict[str, Any]:
        rng = rng_for_instance(instance["instance_id"], salt="thermo")
        ratio = instance["ratio"]
        beta_critical = 1.0 / (ratio + 0.1)
        return {
            "thermo_beta_critical_proxy": round(beta_critical, 6),
            "thermo_susceptibility_peak": round(0.5 + 1.5 * math.exp(-(ratio - 4.26) ** 2), 6),
            "thermo_log_Z_slope": round(-ratio * (0.8 + 0.4 * rng.random()), 6),
        }

    def extract_algebra_demo(self, instance: Dict[str, Any]) -> Dict[str, Any]:
        rng = rng_for_instance(instance["instance_id"], salt="algebra")
        clauses = instance["clauses"]
        n = instance["n_vars"]
        lengths = [len(c) for c in clauses] if clauses else [0]
        horn = sum(1 for c in clauses if sum(1 for lit in c if lit > 0) <= 1)
        return {
            "algebra_mean_clause_len": round(statistics.mean(lengths), 6),
            "algebra_horn_fraction": round(horn / max(1, len(clauses)), 6),
            "algebra_unit_prop_fixations": int(len(clauses) * 0.1 * rng.random()),
            "resistance_to_2sat": round(min(1.0, len(clauses) / max(n, 1) * 0.3), 6),
        }

    def extract_prod_lite(self, instance: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
        import networkx as nx
        import scipy.sparse as sp
        import scipy.sparse.linalg as spla

        n = instance["n_vars"]
        m = instance["n_clauses"]
        clauses = instance["clauses"]
        features = {}

        B = nx.Graph()
        B.add_nodes_from(range(1, n + 1), bipartite=0)
        B.add_nodes_from([f"c{i}" for i in range(m)], bipartite=1)

        for i, c in enumerate(clauses):
            c_node = f"c{i}"
            for lit in c:
                v = abs(lit)
                B.add_edge(v, c_node)

        topo_cfg = self.families.get("topology", {})
        if topo_cfg.get("enabled", False):
            degrees = [d for _, d in B.degree()]
            deg_mean = statistics.mean(degrees) if degrees else 0.0
            deg_std = statistics.stdev(degrees) if len(degrees) > 1 else 0.0
            
            from scipy.stats import skew
            deg_skew = skew(degrees) if len(degrees) > 2 else 0.0

            components = list(nx.connected_components(B))
            n_comp = len(components)
            lg_comp_frac = len(max(components, key=len)) / B.number_of_nodes() if components else 0.0

            try:
                proj_v = nx.bipartite.projected_graph(B, range(1, n + 1))
                clustering = nx.average_clustering(proj_v)
            except Exception:
                clustering = 0.0

            features.update({
                "degree_mean": float(deg_mean),
                "degree_std": float(deg_std),
                "degree_skew": float(deg_skew),
                "components": float(n_comp),
                "largest_component_frac": float(lg_comp_frac),
                "projection_clustering": float(clustering)
            })

        spec_cfg = self.families.get("spectral_lite", {})
        if spec_cfg.get("enabled", False):
            try:
                import scipy.linalg as la
                L_dense = nx.normalized_laplacian_matrix(B).toarray()
                eigs = la.eigvalsh(L_dense)
                eigs = np.sort(np.abs(eigs))
            except Exception:
                eigs = np.zeros(2)

            lambda2 = eigs[1] if len(eigs) > 1 else 0.0
            gap = eigs[2] - eigs[1] if len(eigs) > 2 else 0.0

            p = eigs / (np.sum(eigs) + 1e-12)
            p = p[p > 0]
            entropy = -np.sum(p * np.log(p))

            features.update({
                "lambda2": float(lambda2),
                "spectral_gap": float(gap),
                "spectral_entropy": float(entropy)
            })

        if "algebra" in self.families and self.families["algebra"].get("enabled", False):
            alg = self.extract_algebra_demo(instance)
            features.update(alg)
        else:
            horn = sum(1 for c in clauses if sum(1 for lit in c if lit > 0) <= 1)
            features["algebra_horn_fraction"] = round(horn / max(1, len(clauses)), 6)

        return features, "PROD"

    def extract_all(self, instance: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
        if self.mode == "prod_lite":
            return self.extract_prod_lite(instance)

        spec = self.extract_spectral_demo(instance)
        thermo = self.extract_thermo_demo(instance)
        alg = self.extract_algebra_demo(instance)
        merged = {**spec, **thermo, **alg}
        return merged, "DEMO"
