from typing import List, Dict, Union, Tuple, Generator, Optional
from logic_parser import Predicate, Rule, Term, Variable, Constant

# A substitution is a dictionary mapping variable names (str) to terms (Term)
Substitution = Dict[str, Term]

# Counter for standardizing variables, to ensure unique names
_var_counter = 0


def standardize_variables(rule: Rule) -> Rule:
    """
    Standardizes the variables in a rule to ensure they are unique.
    This prevents variable collisions when applying rules.

    Why is this necessary? Consider applying the rule:
        Parent(x, y) => Ancestor(x, y)
    multiple times. Without standardization, the variable 'x' from one
    application could interfere with 'x' from another application.

    By renaming to x_1, y_1, etc., each rule application uses fresh variables.

    Args:
        rule: The Rule object to standardize.

    Returns:
        A new Rule object with all variables renamed (e.g., x -> x_1, y -> y_1).
    """
    global _var_counter
    _var_counter += 1
    substitution: Substitution = {}

    # --- YOUR CODE HERE ---

    def collect_variables(predicate: Predicate) -> set:
        """Helper to collect all variable names from a predicate."""
        variables = set()
        for term in predicate.terms:
            if isinstance(term, Variable):
                variables.add(term.value)
        return variables

    def substitute_in_predicate(predicate: Predicate, sub: Substitution) -> Predicate:
        """Apply substitution to a predicate, creating a new one."""
        new_terms = []
        for term in predicate.terms:
            if isinstance(term, Variable) and term.value in sub:
                new_terms.append(sub[term.value])
            else:
                new_terms.append(term)
        return Predicate(predicate.name, new_terms)

    # Step 1: Collect all variables from the rule
    all_vars = set()
    for antecedent in rule.antecedents:
        all_vars.update(collect_variables(antecedent))
    all_vars.update(collect_variables(rule.consequent))

    # Step 2: Create the substitution mapping each variable to a unique name
    # For example: x -> x_1, y -> y_1, z -> z_1 (if _var_counter is 1)
    for var_name in all_vars:
        new_var_name = f"{var_name}_{_var_counter}"
        substitution[var_name] = Variable(new_var_name)

    # Step 3: Apply substitution to all antecedents
    new_antecedents = [
        substitute_in_predicate(ant, substitution) for ant in rule.antecedents
    ]

    # Step 4: Apply substitution to the consequent
    new_consequent = substitute_in_predicate(rule.consequent, substitution)

    # Step 5: Return a new Rule with standardized variables
    return Rule(new_antecedents, new_consequent)
    # --- END YOUR CODE ---


def unify(
    x: Union[Term, Predicate, List],
    y: Union[Term, Predicate, List],
    theta: Substitution,
) -> Optional[Substitution]:
    """
    Implements the UNIFY algorithm from AIMA.

    Unification finds a substitution (variable assignments) that makes two
    expressions identical. For example:
    - unify(Father(x, Arthur), Father(Uther, Arthur)) = {x: Uther}
    - unify(Parent(x, y), Parent(Arthur, z)) = {x: Arthur, y: z} or similar

    This is the core algorithm used in both forward and backward chaining
    to match facts with rule patterns.

    Args:
        x: The first expression (Term, Predicate, or List)
        y: The second expression (Term, Predicate, or List)
        theta: The current substitution dictionary

    Returns:
        A new Substitution if unification is possible, None otherwise
    """
    # --- YOUR CODE HERE ---

    # Case 1: Failure propagation
    # If theta is None (previous unification failed), propagate failure
    if theta is None:
        return None

    # Case 2: Already identical
    # If x and y are already equal, no additional substitution needed
    if x == y:
        return theta

    # Case 3: x is a Variable
    # Delegate to unify_var to handle variable binding
    if isinstance(x, Variable):
        return unify_var(x, y, theta)

    # Case 4: y is a Variable
    # Symmetric case - if y is variable, unify it with x
    if isinstance(y, Variable):
        return unify_var(y, x, theta)

    # Case 5: Both are Predicates (compound terms)
    # For predicates like Father(x, y) and Father(Uther, Arthur):
    # 1. Check that predicate names match
    # 2. Recursively unify the argument lists
    if isinstance(x, Predicate) and isinstance(y, Predicate):
        # Predicate names must match exactly
        if x.name != y.name:
            return None
        # Number of arguments must match
        if len(x.terms) != len(y.terms):
            return None
        # Recursively unify the argument lists
        return unify(x.terms, y.terms, theta)

    # Case 6: Both are lists
    # Unify element by element, threading the substitution through
    if isinstance(x, list) and isinstance(y, list):
        # Lists must have same length
        if len(x) != len(y):
            return None
        # Empty lists unify trivially
        if len(x) == 0:
            return theta
        # Unify first elements, then recursively unify the rest
        # The result of unifying first elements becomes the theta for the rest
        return unify(x[1:], y[1:], unify(x[0], y[0], theta))

    # Case 7: Incompatible types or different constants
    # If we reach here, x and y cannot be unified
    return None
    # --- END YOUR CODE ---


def unify_var(
    var: Variable, x: Union[Term, Predicate, List], theta: Substitution
) -> Optional[Substitution]:
    """
    Helper function for UNIFY: unifies a variable with an expression.

    This implements the UNIFY-VAR algorithm from AIMA (Artificial Intelligence:
    A Modern Approach). It handles the case where we need to bind a variable
    to some expression, but first checks if either is already bound.

    Args:
        var: The variable to unify
        x: The expression to unify with (can be Term, Predicate, or List)
        theta: Current substitution dictionary

    Returns:
        A new substitution extending theta, or None if unification fails
    """
    # --- YOUR CODE HERE ---

    # Case 1: var is already bound in theta
    # If var -> someValue in theta, we need to unify someValue with x
    if var.value in theta:
        return unify(theta[var.value], x, theta)

    # Case 2: x is a Variable that is already bound in theta
    # If x -> someValue in theta, we need to unify var with someValue
    if isinstance(x, Variable) and x.value in theta:
        return unify(var, theta[x.value], theta)

    # Case 3: Occurs check - prevent circular structures
    # If var appears inside x, we cannot unify (would create infinite structure)
    # Example: unifying x with F(x) would create x = F(F(F(...)))
    if occurs_check(var, x, theta):
        return None

    # Case 4: Safe to bind var to x
    # Create a new substitution that extends theta with var -> x
    # We use dict unpacking to create a new dict (immutable update)
    new_theta = {**theta, var.value: x}
    return new_theta
    # --- END YOUR CODE ---


def occurs_check(
    var: Variable, x: Union[Term, Predicate, List], theta: Substitution
) -> bool:
    """
    Checks if a variable occurs anywhere in an expression.
    This is used to prevent infinite loops in unification, e.g., unify(x, F(x)).

    The occurs check is essential for sound unification. Without it, we could
    create circular substitutions like {x: F(x)}, which would lead to infinite
    structures when we try to apply the substitution.

    Args:
        var: The variable we're checking for
        x: The expression to search within
        theta: Current substitution (to follow variable bindings)

    Returns:
        True if var appears anywhere in x, False otherwise
    """
    # --- YOUR CODE HERE ---

    # Case 1: x is a Variable
    if isinstance(x, Variable):
        # If x is the same variable as var, we found an occurrence
        if x == var:
            return True
        # If x is bound in theta, check if var occurs in the bound value
        # This handles chains like {y: F(x)} where we need to check inside F(x)
        elif x.value in theta:
            return occurs_check(var, theta[x.value], theta)
        else:
            # x is a different, unbound variable - no occurrence
            return False

    # Case 2: x is a Predicate (compound term like Father(x, y))
    elif isinstance(x, Predicate):
        # Check if var occurs in any of the predicate's arguments
        # For example, in Father(x, Arthur), we check both x and Arthur
        return any(occurs_check(var, term, theta) for term in x.terms)

    # Case 3: x is a list (used when unifying lists of terms)
    elif isinstance(x, list):
        return any(occurs_check(var, item, theta) for item in x)

    # Case 4: x is a Constant - variables never occur in constants
    else:
        return False
    # --- END YOUR CODE ---


def fol_fc_ask(facts: List[Predicate], rules: List[Rule]) -> List[Predicate]:
    """
    Implements the FOL-FC-ASK algorithm (Forward Chaining).

    Forward chaining is a data-driven inference method. Starting with known
    facts, it repeatedly applies rules to derive new facts until no more
    can be derived (fixed-point iteration).

    The algorithm:
    1. Start with initial facts
    2. For each rule, find all ways its antecedents can be satisfied
    3. Apply those substitutions to derive new facts
    4. Repeat until no new facts are generated

    Args:
        facts: A list of initial facts (Predicate objects).
        rules: A list of rules (Rule objects).

    Returns:
        A new list of all facts that can be inferred, including initial facts.
    """
    # Make a copy to avoid modifying the original list
    # Using a set for O(1) membership testing, plus a list for ordering
    known_facts: List[Predicate] = facts[:]
    known_facts_set = set(facts)

    # --- YOUR CODE HERE ---

    def find_all_substitutions(
        antecedents: List[Predicate], facts_list: List[Predicate], theta: Substitution
    ) -> List[Substitution]:
        """
        Recursively find all substitutions that satisfy all antecedents.

        This is the key helper for forward chaining. It tries to match each
        antecedent against every fact, building up substitutions as it goes.

        For example, if we have:
            antecedents = [Parent(p, c), Male(p)]
            facts = [Parent(Uther, Arthur), Male(Uther), ...]

        It will find {p: Uther, c: Arthur} which satisfies both antecedents.

        Args:
            antecedents: List of predicates that must all be satisfied
            facts_list: Available facts to match against
            theta: Current substitution being built up

        Returns:
            List of all valid substitutions (may be empty if no match)
        """
        # Base case: all antecedents satisfied
        if not antecedents:
            return [theta]

        # Take the first antecedent and try to match it
        first_ant = antecedents[0]
        rest_ants = antecedents[1:]

        # Apply current substitution to the antecedent
        # This replaces any already-bound variables with their values
        first_ant_substituted = _substitute(first_ant, theta)

        results = []
        # Try to unify this antecedent with each fact
        for fact in facts_list:
            unified_theta = unify(first_ant_substituted, fact, theta)
            if unified_theta is not None:
                # Successfully unified - recursively match remaining antecedents
                sub_results = find_all_substitutions(rest_ants, facts_list, unified_theta)
                results.extend(sub_results)

        return results

    print("Starting Forward Chaining...")
    cycle = 1

    while True:
        print(f"\n--- Cycle {cycle} ---")
        new_derived: List[Predicate] = []

        # Try each rule
        for rule in rules:
            # Standardize variables to prevent collisions between rule applications
            std_rule = standardize_variables(rule)

            # Find all substitutions that satisfy all antecedents
            substitutions = find_all_substitutions(std_rule.antecedents, known_facts, {})

            # For each valid substitution, derive the consequent
            for theta in substitutions:
                # Apply substitution to get a ground (no variables) consequent
                derived_fact = _substitute(std_rule.consequent, theta)

                # Only add if it's truly new
                if derived_fact not in known_facts_set:
                    new_derived.append(derived_fact)
                    known_facts_set.add(derived_fact)

        # If no new facts derived, we've reached the fixed point
        if not new_derived:
            print("\n--- No new facts added. Halting. ---")
            break

        # Add new facts and print them
        for fact in new_derived:
            print(f"  Derived: {fact}")
            known_facts.append(fact)

        cycle += 1

    print(f"\nForward chaining complete. Final KB size: {len(known_facts)} facts.")
    return known_facts
    # --- END YOUR CODE ---


def fol_bc_ask(
    query: Predicate, facts: List[Predicate], rules: List[Rule]
) -> Generator[Substitution, None, None]:
    """
    Implements the FOL-BC-ASK algorithm (Backward Chaining).

    Backward chaining is a goal-directed inference method. Starting with a
    query (goal), it works backwards to find facts and rules that could
    prove the goal. This is essentially a depth-first search through the
    space of possible proofs.

    The algorithm:
    1. Try to unify the query directly with known facts
    2. For each rule whose consequent matches the query:
       a. Unify query with rule consequent
       b. Recursively prove all antecedents (subgoals)
       c. If all antecedents are proven, yield the combined substitution

    Note: This is a simple implementation without loop prevention.
    For production use, you would track visited goals in a set to prevent
    infinite recursion on cyclic rules (e.g., Ancestor defined recursively).

    Args:
        query: The Predicate to be proven.
        facts: A list of facts in the KB.
        rules: A list of rules in the KB.

    Yields:
        A generator of Substitution dictionaries, each representing a
        valid proof for the query.
    """

    # --- YOUR CODE HERE ---

    def prove_all(
        goals: List[Predicate], theta: Substitution, depth: int
    ) -> Generator[Substitution, None, None]:
        """
        Prove a conjunction of goals (AND).

        This is a helper that proves multiple goals in sequence.
        For each way to prove the first goal, it recursively tries
        to prove the remaining goals.

        Args:
            goals: List of predicates that must all be proven
            theta: Current substitution
            depth: Current depth for indentation in trace output

        Yields:
            Substitutions that prove ALL goals
        """
        # Base case: all goals proven
        if not goals:
            yield theta
            return

        # Take first goal and prove it
        first_goal = goals[0]
        rest_goals = goals[1:]

        # Apply current substitution to the goal
        first_goal_sub = _substitute(first_goal, theta)

        # Try all ways to prove the first goal
        for theta_prime in prove(first_goal_sub, theta, depth):
            # For each proof of first goal, try to prove the rest
            # Apply the new substitution to remaining goals
            yield from prove_all(rest_goals, theta_prime, depth)

    def prove(
        goal: Predicate, theta: Substitution, depth: int
    ) -> Generator[Substitution, None, None]:
        """
        Prove a single goal using backward chaining.

        Tries two approaches:
        1. Match the goal directly with a fact
        2. Find a rule whose consequent matches, then prove its antecedents

        Args:
            goal: The predicate to prove
            theta: Current substitution
            depth: Current depth for indentation

        Yields:
            Substitutions that prove the goal
        """
        indent = "  " * depth

        # NOTE: For loop prevention in a production system, you would:
        # 1. Maintain a set of visited goals (as strings or frozen representations)
        # 2. Before processing a goal, check if it's already being proven
        # 3. If so, skip it to prevent infinite recursion
        # Example: if str(goal) in visited_goals: return
        #          visited_goals.add(str(goal))

        # Approach 1: Try to match with facts
        for fact in facts:
            unified = unify(goal, fact, theta)
            if unified is not None:
                print(f"{indent}Matched fact: {fact}")
                yield unified

        # Approach 2: Try to use rules
        for rule in rules:
            # Standardize variables to get fresh variable names
            std_rule = standardize_variables(rule)

            # Try to unify goal with rule's consequent
            unified = unify(goal, std_rule.consequent, theta)
            if unified is not None:
                print(f"{indent}Trying rule: {rule}")

                # Now we need to prove all the antecedents
                if std_rule.antecedents:
                    print(f"{indent}  Subgoals: {std_rule.antecedents}")

                # Recursively prove all antecedents
                for result in prove_all(std_rule.antecedents, unified, depth + 1):
                    yield result

    # Main entry point - print the query and start proving
    print(f"Query: {query}")

    # Start the proof search
    for substitution in prove(query, {}, 1):
        print(f"Proof found: {substitution}")
        yield substitution
    # --- END YOUR CODE ---


# --- Helper Functions ---

# --- End Helper Functions ---


def _substitute(
    expr: Union[Term, Predicate, List], theta: Substitution
) -> Union[Term, Predicate, List]:
    """
    Applies a substitution `theta` to an expression `expr`.
    """
    if isinstance(expr, Variable):
        if expr.value in theta:
            # Recursively apply substitution to the bound value
            return _substitute(theta[expr.value], theta)
        else:
            return expr  # Unbound variable
    elif isinstance(expr, Predicate):
        new_terms = [_substitute(term, theta) for term in expr.terms]
        return Predicate(expr.name, new_terms)
    elif isinstance(expr, list):
        return [_substitute(item, theta) for item in expr]
    else:  # Constant
        return expr
