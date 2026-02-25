import os
import sys
import time
import numpy as np
import pandas as pd
from tqdm import tqdm
import mlflow

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.solvers.dpll import DPLLSolver
from src.generators.random_k_sat import generate_random_k_sat

def run_experiment(num_vars=20, m_n_ratios=None, samples_per_ratio=50, output_dir="data/output"):
    if m_n_ratios is None:
        m_n_ratios = np.linspace(3.0, 5.5, 26) # 3.0 to 5.5 in steps of 0.1
        
    os.makedirs(output_dir, exist_ok=True)
    results = []
    
    solver = DPLLSolver()
    
    # Configure MLflow if tracking
    mlflow.set_experiment("3-SAT Phase Transition")
    
    with mlflow.start_run():
        mlflow.log_param("num_vars", num_vars)
        mlflow.log_param("samples_per_ratio", samples_per_ratio)
        mlflow.log_param("ratios", list(m_n_ratios))
        
        print(f"Running 3-SAT Phase Transition Experiment")
        print(f"N (Variables): {num_vars}")
        print(f"Ratios (m/n): {m_n_ratios[0]} to {m_n_ratios[-1]}")
        print(f"Samples per ratio: {samples_per_ratio}")
        
        for ratio in tqdm(m_n_ratios, desc="Ratios"):
            num_clauses = int(num_vars * ratio)
            
            satisfiable_count = 0
            total_backtracks = []
            total_time = []
            
            for _ in range(samples_per_ratio):
                formula = generate_random_k_sat(num_vars, num_clauses, k=3)
                
                start_time = time.time()
                is_sat, _ = solver.solve(formula, num_vars)
                end_time = time.time()
                
                if is_sat:
                    satisfiable_count += 1
                    
                total_backtracks.append(solver.tracker.backtracks)
                total_time.append(end_time - start_time)
                
            sat_prob = satisfiable_count / samples_per_ratio
            median_backtracks = np.median(total_backtracks)
            mean_time = np.mean(total_time)
            
            mlflow.log_metric(f"sat_prob_ratio_{ratio:.1f}", sat_prob)
            mlflow.log_metric(f"median_backtracks_ratio_{ratio:.1f}", median_backtracks)
            
            results.append({
                "m_n_ratio": ratio,
                "num_vars": num_vars,
                "num_clauses": num_clauses,
                "sat_probability": sat_prob,
                "median_backtracks": median_backtracks,
                "mean_time_sec": mean_time
            })
            
        df = pd.DataFrame(results)
        output_path = os.path.join(output_dir, f"phase_transition_N{num_vars}.csv")
        df.to_csv(output_path, index=False)
        mlflow.log_artifact(output_path)
        
        print(f"Experiment completed. Results saved to {output_path}")

if __name__ == "__main__":
    # Small experiment for validation
    run_experiment(num_vars=20, samples_per_ratio=50)
