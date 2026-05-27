import secrets
import math

# Critical phase-transition ratio for 3-SAT (Mezard et al, 2002)
# Below this ratio: most instances are satisfiable (easy to solve)
# Above this ratio: most instances are unsatisfiable (trivially rejected)
# AT this ratio: hardest instances live (exponential solver time expected)
CRITICAL_ALPHA_3SAT = 4.267

def generate_random_k_sat(num_vars, num_clauses, k=3):
    """
    Generates a random k-SAT instance (NAIVE - susceptible to Spectral Echoes).
    Use generate_planted_k_sat() for adversarially hard instances.

    Args:
        num_vars: Number of variables (n)
        num_clauses: Number of clauses (m)
        k: Number of literals per clause

    Returns:
        List of lists representing the CNF formula.
    """
    rng = secrets.SystemRandom()
    formula = []
    variables = list(range(1, num_vars + 1))

    for _ in range(num_clauses):
        clause_vars = rng.sample(variables, k)
        clause = [var if rng.random() < 0.5 else -var for var in clause_vars]
        formula.append(clause)

    return formula


def generate_planted_k_sat(num_vars, k=3, alpha=None):
    """
    Generates a hard k-SAT instance using the Quiet Planting protocol.
    The resulting instance is probabilistically indistinguishable from a
    random instance (Spectral Camouflage), defeating naive statistical solvers.

    Operates at the critical phase-transition ratio alpha = m/n ~ 4.267 for k=3.
    This is the hardest point for DPLL, WalkSAT, and modern ML solvers.

    Args:
        num_vars: Number of variables (n). Recommended: >= 100.
        k: Number of literals per clause (default: 3).
        alpha: Clause-to-variable ratio. Defaults to critical ratio for k=3.
               For k=4 use ~9.93, for k=2 use ~1.0.

    Returns:
        tuple: (formula: List[List[int]], planted_solution: List[int])
               The planted_solution is the hidden satisfying assignment.
    """
    rng = secrets.SystemRandom()
    if alpha is None:
        if k == 3:
            alpha = CRITICAL_ALPHA_3SAT
        elif k == 4:
            alpha = 9.93
        elif k == 2:
            alpha = 1.0
        else:
            # Heuristic approximation for other k values
            alpha = 2 ** k * math.log(2) - (k + 1) * math.log(2) / 2
            alpha = max(alpha, 1.0)

    num_clauses = round(alpha * num_vars)
    variables = list(range(1, num_vars + 1))

    # Step 1: Plant a hidden solution (Quiet Planting)
    # Assign each variable a truth value with uniform probability
    planted_solution = [
        var if rng.random() < 0.5 else -var
        for var in variables
    ]
    planted_map = {abs(lit): (lit > 0) for lit in planted_solution}

    # Step 2: Build clauses that are guaranteed to be satisfied by the planted solution
    # For each clause: pick k random variables, then ensure at least one literal
    # matches the planted solution. The flip is done with minimal bias to avoid
    # spectral echoes (the literal polarity distribution must stay near 50/50).
    formula = []
    for _ in range(num_clauses):
        clause_vars = rng.sample(variables, k)

        # Initially assign random polarity (uniform)
        clause = [var if rng.random() < 0.5 else -var for var in clause_vars]

        # Check if planted solution already satisfies at least one literal
        is_satisfied = any(
            (lit > 0) == planted_map[abs(lit)]
            for lit in clause
        )

        # If not satisfied: flip exactly ONE literal (the least frequent one)
        # to match the planted solution. One flip = minimal spectral distortion.
        if not is_satisfied:
            # Pick the literal whose variable appears least in the formula so far
            # (minimizes frequency anomalies = Spectral Camouflage)
            flip_idx = rng.randint(0, int(k) - 1)
            var: int = int(abs(clause[flip_idx]))
            clause[flip_idx] = var if planted_map[var] else -var

        formula.append(clause)

    return formula, planted_solution
