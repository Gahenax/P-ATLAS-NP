import random

def generate_random_k_sat(num_vars, num_clauses, k=3):
    """
    Generates a random k-SAT instance.
    
    Args:
        num_vars: Number of variables (n)
        num_clauses: Number of clauses (m)
        k: Number of literals per clause
        
    Returns:
        List of lists representing the CNF formula.
    """
    formula = []
    variables = list(range(1, num_vars + 1))
    
    for _ in range(num_clauses):
        # Select k distinct variables
        clause_vars = random.sample(variables, k)
        
        # Randomly negate literals with 50% probability
        clause = [var if random.random() < 0.5 else -var for var in clause_vars]
        formula.append(clause)
        
    return formula
