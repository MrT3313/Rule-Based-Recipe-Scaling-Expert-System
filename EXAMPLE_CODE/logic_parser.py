import re
from typing import List, Dict, Union, Tuple

# Regex to capture the components of facts and rules
# e.g., "Parent(x, z) && Ancestor(z, y) => Ancestor(x, y)"
# or "King(Arthur)"
RULE_REGEX = re.compile(r"^(.*) => (.*)$")
ANTECEDENT_REGEX = re.compile(r" && ")
PREDICATE_REGEX = re.compile(r"^(\w+)\((.*)\)$")

class Term:
    """Base class for a term (Constant or Variable)."""
    def __init__(self, value: str):
        self.value = value

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.value})"

    def __eq__(self, other) -> bool:
        return isinstance(other, self.__class__) and self.value == other.value

    def __hash__(self) -> int:
        return hash(repr(self))

class Constant(Term):
    """A constant, e.g., 'Arthur', 'Eldoria'."""
    pass

class Variable(Term):
    """A variable, e.g., 'x', 'p', 'c'."""
    pass

class Predicate:
    """A predicate, e.g., Parent(Uther, Arthur) or Ancestor(x, y)."""
    def __init__(self, name: str, terms: List[Term]):
        self.name = name
        self.terms = terms

    def __repr__(self) -> str:
        return f"{self.name}({', '.join(map(str, self.terms))})"

    def __eq__(self, other) -> bool:
        return (
            isinstance(other, Predicate) and
            self.name == other.name and
            self.terms == other.terms
        )

    def __hash__(self) -> int:
        return hash(repr(self))

class Rule:
    """A rule, e.g., Parent(x, z) && Ancestor(z, y) => Ancestor(x, y)."""
    def __init__(self, antecedents: List[Predicate], consequent: Predicate):
        self.antecedents = antecedents
        self.consequent = consequent

    def __repr__(self) -> str:
        ant_str = " && ".join(map(str, self.antecedents))
        return f"{ant_str} => {self.consequent}"

def _parse_term(term_str: str) -> Term:
    """Parses a string into a Constant or Variable."""
    # Strip quotes if present
    term_str = term_str.strip('"').strip("'")
    if term_str[0].islower():
        return Variable(term_str)
    return Constant(term_str)

def _parse_predicate(pred_str: str) -> Predicate:
    """Parses a string into a Predicate."""
    match = PREDICATE_REGEX.match(pred_str.strip())
    if not match:
        raise ValueError(f"Invalid predicate format: {pred_str}")
    
    name, terms_str = match.groups()
    if not terms_str:
        return Predicate(name, [])
        
    terms = [_parse_term(t.strip()) for t in terms_str.split(",")]
    return Predicate(name, terms)

def parse_kb(filepath: str) -> Tuple[List[Predicate], List[Rule]]:
    """
    Parses a Knowledge Base file.

    Args:
        filepath: The path to the .kb file.

    Returns:
        A tuple containing (list_of_facts, list_of_rules).
    """
    facts = []
    rules = []
    
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('%'):
                continue  # Skip empty lines and comments

            rule_match = RULE_REGEX.match(line)
            
            if rule_match:
                # This is a rule
                antecedents_str, consequent_str = rule_match.groups()
                antecedents = [
                    _parse_predicate(p) for p in ANTECEDENT_REGEX.split(antecedents_str)
                ]
                consequent = _parse_predicate(consequent_str)
                rules.append(Rule(antecedents, consequent))
            else:
                # This must be a fact
                try:
                    facts.append(_parse_predicate(line))
                except ValueError as e:
                    print(f"Warning: Skipping malformed line: {line} ({e})")

    return facts, rules

if __name__ == '__main__':
    # Example usage:
    print("Testing parser with a dummy KB...")
    dummy_kb_path = "dummy.kb"
    with open(dummy_kb_path, "w") as f:
        f.write("% This is a test KB\n")
        f.write("King(Arthur)\n")
        f.write("Parent(Uther, Arthur)\n")
        f.write("Parent(p, c) && Male(p) => Father(p, c)\n")

    facts, rules = parse_kb(dummy_kb_path)
    
    print("\n--- Facts ---")
    for fact in facts:
        print(fact)
        
    print("\n--- Rules ---")
    for rule in rules:
        print(rule)
        
    import os
    os.remove(dummy_kb_path)
