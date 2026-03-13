from typing import Dict

MAX_RECURSION_DEPTH = 5000  # Guard against stack overflow on large instances


class DPLLTracker:
    def __init__(self):
        self.backtracks = 0
        self.unit_propagations = 0
        self.decisions = 0
        self.depth_cutoffs = 0

    def reset(self):
        self.backtracks = 0
        self.unit_propagations = 0
        self.decisions = 0
        self.depth_cutoffs = 0


class DPLLSolver:
    """
    A Davis-Putnam-Logemann-Loveland (DPLL) algorithm implementation
    for solving SAT problems in Conjunctive Normal Form (CNF).
    
    Variables are represented as integers (1 to N).
    Negations are represented as negative integers (-1 to -N).
    A clause is a list of integers.
    A CNF formula is a list of clauses.
    """
    def __init__(self):
        self.tracker = DPLLTracker()

    def solve(self, cnf_formula, num_vars):
        """
        Solves the given CNF formula.
        
        Args:
            cnf_formula: List of lists of integers representing the CNF.
            num_vars: Total number of variables.
            
        Returns:
            (satisfiable, model):
                satisfiable: Boolean indicating if the formula is SAT.
                model: A dictionary mapping variables to boolean values if SAT, else None.
        """
        self.tracker.reset()
        assignment = {}
        result, final_assignment = self._dpll(cnf_formula, assignment, depth=0)
        return result, final_assignment

    def _simplify(self, formula, unit_literal):
        """
        Simplifies the formula given a unit literal (Unit Propagation).
        Removes clauses containing the unit literal.
        Removes the negation of the unit literal from other clauses.
        """
        new_formula = []
        for clause in formula:
            if unit_literal in clause:
                continue # Clause is satisfied
            if -unit_literal in clause:
               # Remove negated literal
               new_clause = [l for l in clause if l != -unit_literal]
               if not new_clause:
                   return None # Empty clause created -> UNSAT
               new_formula.append(new_clause)
            else:
               new_formula.append(clause)
        return new_formula

    def _dpll(self, formula, assignment, depth: int = 0):
        """
        Recursive core of the DPLL algorithm.
        """
        # Depth limit guard against stack overflow on large instances
        if depth >= MAX_RECURSION_DEPTH:
            self.tracker.depth_cutoffs += 1
            return False, None

        # Base cases
        if not formula:
            return True, assignment

        # Check for empty clauses (UNSAT context)
        for clause in formula:
            if not clause:
                self.tracker.backtracks += 1
                return False, None

        # 1. Unit Propagation
        unit_propagated = True
        while unit_propagated:
            unit_propagated = False
            for clause in formula:
                if len(clause) == 1:
                    unit_literal = clause[0]
                    self.tracker.unit_propagations += 1
                    var = abs(unit_literal)
                    val = unit_literal > 0
                    assignment[var] = val
                    
                    formula = self._simplify(formula, unit_literal)
                    if formula is None:
                        self.tracker.backtracks += 1
                        return False, None
                    if not formula:
                        return True, assignment
                        
                    unit_propagated = True
                    break # Restart scan since formula changed
        
        # 2. Pure Literal Elimination (Optional, omitted for simplicity and raw backtrack counting)
        # In hard random 3-SAT, pure literals are rare during the core search phase.
        
        # 3. Decision (Branching)
        # Choose the variable that appears most frequently (MOM-like heuristic).
        # Falls back to first literal if formula is trivially small.
        self.tracker.decisions += 1
        decision_literal = self._choose_literal(formula)
        var = abs(decision_literal)

        # Branch True (try the literal as given)
        new_assignment = assignment.copy()
        new_assignment[var] = decision_literal > 0
        new_formula = self._simplify(formula, decision_literal)

        if new_formula is not None:
            res, final_assn = self._dpll(new_formula, new_assignment, depth + 1)
            if res:
                return True, final_assn
        else:
            self.tracker.backtracks += 1

        # Branch False (try the negation of the literal)
        new_assignment = assignment.copy()
        new_assignment[var] = decision_literal < 0
        new_formula = self._simplify(formula, -decision_literal)

        if new_formula is not None:
            return self._dpll(new_formula, new_assignment, depth + 1)
        else:
            self.tracker.backtracks += 1
            return False, None

    def _choose_literal(self, formula) -> int:
        """
        Most-Occurring literal heuristic: pick the literal that appears most
        frequently across all clauses. Better than always picking first literal.
        """
        freq: Dict[int, int] = {}
        for clause in formula:
            for lit in clause:
                freq[lit] = freq.get(lit, 0) + 1
        return max(freq, key=freq.__getitem__)
