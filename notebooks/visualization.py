import os
import pandas as pd
import matplotlib.pyplot as plt

def plot_results(csv_path="data/output/phase_transition_N20.csv", output_path="data/output/phase_transition.png"):
    if not os.path.exists(csv_path):
        print(f"File {csv_path} not found.")
        return

    df = pd.read_csv(csv_path)
    
    fig, ax1 = plt.subplots(figsize=(10, 6))

    color = 'tab:blue'
    ax1.set_xlabel('Ratio (m/n) - Clauses / Variables')
    ax1.set_ylabel('Probability of Satisfiability', color=color)
    ax1.plot(df['m_n_ratio'], df['sat_probability'], color=color, marker='o', label='P(SAT)')
    ax1.tick_params(axis='y', labelcolor=color)
    
    # Adding a vertical line at the theoretical threshold ~4.26
    ax1.axvline(x=4.26, color='r', linestyle='--', label='Theoretical Threshold 4.26')

    ax2 = ax1.twinx()
    color = 'tab:red'
    ax2.set_ylabel('Median Backtracks', color=color)
    ax2.plot(df['m_n_ratio'], df['median_backtracks'], color=color, marker='s', linestyle='-', alpha=0.7, label='Backtracks')
    ax2.tick_params(axis='y', labelcolor=color)

    fig.tight_layout()
    plt.title(f"3-SAT Phase Transition (N={df['num_vars'].iloc[0]})")
    
    # Combined legend
    lines, labels = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax2.legend(lines + lines2, labels + labels2, loc='upper right')

    plt.savefig(output_path)
    print(f"Plot saved to {output_path}")

if __name__ == "__main__":
    plot_results()
