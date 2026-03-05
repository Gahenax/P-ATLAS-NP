"""
MPI Multi-Node Dispatch for P-ATLAS-NP Phase Transition SAT Generation.

Distributes the generation of SAT instances across multiple cluster nodes
to parallelize the massive matrix multiplications and generator logic.
"""
import sys
import argparse
import time
import json
from pathlib import Path
from datetime import datetime

try:
    from mpi4py import MPI
except ImportError:
    print("FATAL: mpi4py is required. Install with: pip install mpi4py")
    sys.exit(1)

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Mock import for the actual generation logic (replace with core function)
# from src.core.generators import generate_sat_batch

def mock_generate_sat_batch(n_vars, ratio, count):
    """Placeholder for instance generation."""
    return [{"vars": n_vars, "clauses": int(n_vars * ratio), "status": "generated"} for _ in range(count)]

def main():
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()

    ap = argparse.ArgumentParser()
    ap.add_argument("--vars", type=int, default=100)
    ap.add_argument("--ratio", type=float, default=4.26)
    ap.add_argument("--total_instances", type=int, default=1000)
    args = ap.parse_args()

    if rank == 0:
        print("=" * 70)
        print(f" P-ATLAS-NP MPI SUPERCOMPUTING DISPATCH")
        print(f" Vars: {args.vars} | Ratio: {args.ratio} | Total: {args.total_instances}")
        print(f" Cluster Workers: {size}")
        print("=" * 70)

        # Distribute the instance count among workers
        base_count = args.total_instances // size
        remainder = args.total_instances % size
        
        chunks = []
        for i in range(size):
            chunks.append(base_count + (1 if i < remainder else 0))
        start_time = time.time()
    else:
        chunks = None

    # SCATTER
    my_count = comm.scatter(chunks, root=0)

    # PROCESS
    # local_instances = generate_sat_batch(args.vars, args.ratio, my_count)
    local_instances = mock_generate_sat_batch(args.vars, args.ratio, my_count)

    # GATHER
    all_instances_lists = comm.gather(local_instances, root=0)

    # NODE 0: Ledger Write
    if rank == 0:
        elapsed = time.time() - start_time
        all_instances = [item for sublist in all_instances_lists for item in sublist]

        out_dir = Path("evidence/supercomputing")
        out_dir.mkdir(parents=True, exist_ok=True)
        
        manifest = {
            "cluster_size": size,
            "vars": args.vars,
            "ratio": args.ratio,
            "n_generated": len(all_instances),
            "wall_time_s": round(elapsed, 2),
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        mf_path = out_dir / f"mpi_atlas_manifest_v{args.vars}_r{args.ratio}.json"
        mf_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        print(f"\n{'=' * 70}")
        print(f" MPI RUN COMPLETE | Generated: {len(all_instances)}")
        print(f" Total Time: {elapsed:.1f}s")
        print(f" Evidence saved to: {out_dir}")
        print(f" {'=' * 70}")

if __name__ == "__main__":
    main()
