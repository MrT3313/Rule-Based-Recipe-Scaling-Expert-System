import argparse
import re
from typing import List

# Import our parser
from logic_parser import parse_kb, Predicate, Term, Constant, Variable

# Import the student's solver functions
try:
    from logic_solver import fol_fc_ask, fol_bc_ask
except ImportError:
    print("Error: Could not import functions from logic_solver.py.")
    print("Make sure that file exists and is in the same directory.")
    exit(1)
except Exception as e:
    print(f"Error importing logic_solver.py: {e}")
    exit(1)

# Regex helpers for parsing a query string, adapted from logic_parser.py
PREDICATE_REGEX = re.compile(r"^(\w+)\((.*)\)$")


def _parse_term(term_str: str) -> Term:
    """Parses a string into a Constant or Variable."""
    if not term_str:
        raise ValueError("Term string cannot be empty.")
    if term_str[0].islower():
        return Variable(term_str)
    return Constant(term_str)


def parse_query(query_str: str) -> Predicate:
    """Parses a query string (e.g., "Ancestor(Uther, Galahad)") into a Predicate."""
    match = PREDICATE_REGEX.match(query_str.strip())
    if not match:
        raise ValueError(
            f"Invalid query format: {query_str}. Must be Predicate(Term, ...)"
        )

    name, terms_str = match.groups()
    if not terms_str:
        return Predicate(name, [])

    try:
        terms = [_parse_term(t.strip()) for t in terms_str.split(",")]
        return Predicate(name, terms)
    except ValueError as e:
        raise ValueError(f"Invalid term in query: {query_str}. {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Runs First-Order Logic inference algorithms on a Knowledge Base.",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "--kb",
        type=str,
        required=True,
        help="Path to the Knowledge Base file (e.g., camelot.kb)",
    )
    parser.add_argument(
        "--method",
        type=str,
        required=True,
        choices=["FC", "BC"],
        help="Inference method to use: \n"
        "  FC: Forward Chaining (prints all inferred facts)\n"
        "  BC: Backward Chaining (requires --query)",
    )
    parser.add_argument(
        "--query",
        type=str,
        help="The query to prove (required for BC).\n"
        'Example: "Ancestor(Uther, Galahad)"',
    )

    args = parser.parse_args()

    # --- Load the Knowledge Base ---
    try:
        facts, rules = parse_kb(args.kb)
        print(f"Successfully loaded Knowledge Base from {args.kb}.")
        print(f"  {len(facts)} facts, {len(rules)} rules.\n")
    except FileNotFoundError:
        print(f"Error: Knowledge Base file not found at {args.kb}")
        return
    except Exception as e:
        print(f"Error parsing Knowledge Base: {e}")
        return

    # --- Run Forward Chaining ---
    if args.method == "FC":
        if args.query:
            print(
                "Warning: --query argument is ignored when using Forward Chaining (FC)."
            )

        # The fol_fc_ask function should print its own trace
        all_facts = fol_fc_ask(facts, rules)

        # Print a summary of final facts
        print("\n" + "---" * 10)
        print("Final Inferred Facts (Sorted):")
        # Use a set to ensure uniqueness and sort for stable output
        facts_set = set(all_facts)
        sorted_facts = sorted(list(facts_set), key=str)

        for i, fact in enumerate(sorted_facts):
            print(f"  {i+1:03d}: {fact}")
        print("---" * 10)

    # --- Run Backward Chaining ---
    elif args.method == "BC":
        if not args.query:
            print("Error: --query argument is required for Backward Chaining (BC).")
            parser.print_help()
            return

        try:
            query = parse_query(args.query)
        except ValueError as e:
            print(f"Error parsing query: {e}")
            return

        print("---" * 10)
        print(f"Running Backward Chaining for query: {query}\n")

        # The fol_bc_ask function is a generator
        # It should print its own trace as it searches
        proofs = fol_bc_ask(query, facts, rules)

        found_proof = False
        for i, proof in enumerate(proofs):
            found_proof = True
            print(f"\n  --- Proof {i+1} Found ---")
            if not proof:
                print("  Result: True (no variable substitutions)")
            else:
                print(f"  Result: {proof}")

        if not found_proof:
            print("\n  --- No Proof Found ---")

        print("\n" + "---" * 10)


if __name__ == "__main__":
    main()
