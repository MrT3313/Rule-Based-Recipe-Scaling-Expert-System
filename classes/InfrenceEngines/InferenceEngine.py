from classes.NegatedFact import NegatedFact
from classes.Fact import Fact


class InferenceEngine:
    def __init__(self, wm, kb, conflict_resolution_strategy='priority', verbose=True):
        self.working_memory = wm
        self.knowledge_base = kb
        self.cycle_count = 0
        self.conflict_resolution_strategy = conflict_resolution_strategy
        self.verbose = verbose

    def _match_pattern(self, pattern, fact, bindings):
        """Try to unify a single rule pattern against a single fact, returning updated bindings or None."""

        # Patterns and facts must refer to the same fact type (e.g. "ingredient")
        if pattern.fact_title != fact.fact_title:
            return None

        # Work on a copy so failed matches don't corrupt bindings
        new_bindings = bindings.copy()

        for key, pattern_value in pattern.attributes.items():
            # Pattern requires an attribute the fact doesn't have — no match
            if key not in fact.attributes:
                return None

            fact_value = fact.attributes[key]

            # Pattern value is a variable (e.g. "?amount")
            if isinstance(pattern_value, str) and pattern_value.startswith('?'):
                if pattern_value in new_bindings:
                    # Variable already bound — check consistency with the existing binding
                    if new_bindings[pattern_value] != fact_value:
                        return None
                else:
                    # First occurrence of this variable — bind it to the fact's value
                    new_bindings[pattern_value] = fact_value
            else:
                # Literal value — must match exactly
                if pattern_value != fact_value:
                    return None

        return new_bindings

    def _match_antecedents(self, antecedents, bindings):
        """Recursively match a list of antecedents, returning all valid binding sets."""

        # Base case: all antecedents matched — return the accumulated bindings
        if not antecedents:
            return [bindings]

        # Process antecedents left-to-right, one at a time
        first_antecedent = antecedents[0]
        rest_antecedents = antecedents[1:]
        all_facts = self.knowledge_base.reference_facts + self.working_memory.facts

        # Handle negated conditions
        if isinstance(first_antecedent, NegatedFact):
            pattern = first_antecedent.fact
            # If ANY fact matches the negated pattern, the whole rule fails
            for fact in all_facts:
                if self._match_pattern(pattern, fact, bindings) is not None:
                    return []
            # No matching fact found — negation satisfied, continue with remaining antecedents
            return self._match_antecedents(rest_antecedents, bindings)

        # Positive condition: try every fact and collect all successful binding paths
        results = []
        for fact in all_facts:
            new_bindings = self._match_pattern(first_antecedent, fact, bindings)
            if new_bindings is not None:
                # This fact matched — recurse on the remaining antecedents with updated bindings
                sub_results = self._match_antecedents(
                    rest_antecedents, new_bindings
                )
                results.extend(sub_results)
        return results

    def _find_matching_rules(self):
        """Return all (rule, bindings) pairs whose antecedents are satisfied."""
        matches = []
        for rule in self.knowledge_base.rules:
            bindings_list = self._match_antecedents(rule.antecedents, {})
            for bindings in bindings_list:
                matches.append((rule, bindings))
        return matches

    def _find_rules_using_fact(self, fact):
        matches = []
        for rule in self.knowledge_base.rules:
            for antecedent in rule.antecedents:
                if isinstance(antecedent, NegatedFact):
                    continue
                initial_bindings = self._match_pattern(antecedent, fact, {})
                if initial_bindings is not None:
                    bindings_list = self._match_antecedents(rule.antecedents, {})
                    for bindings in bindings_list:
                        matches.append((rule, bindings))
                    break
        return matches

    def _apply_bindings(self, fact_template, bindings):
        new_attributes = {}
        for key, value in fact_template.attributes.items():
            if isinstance(value, str) and value.startswith('?'):
                new_attributes[key] = bindings[value]
            else:
                new_attributes[key] = value
        return Fact(fact_template.fact_title, **new_attributes)

    def _resolve_conflict(self, matches):
        if self.conflict_resolution_strategy == "specificity":
            return max(matches, key=lambda x: len(x[0].antecedents))
        return max(matches, key=lambda x: x[0].priority)

    def _fact_exists(self, fact):
        for existing_fact in self.working_memory.facts:
            if existing_fact.fact_title == fact.fact_title:
                if existing_fact.attributes == fact.attributes:
                    return True
        return False

    def _fire_rules_dfs(self, depth=0, triggering_fact=None):
        if triggering_fact is None:
            matches = self._find_matching_rules()
        else:
            # we have just derived a new fact and want to check if there are NEW rules that can fire based SOLELY on this new rule
            matches = self._find_rules_using_fact(triggering_fact)

        while matches:
            selected_rule, bindings = self._resolve_conflict(matches)

            # Compute final bindings and derive the consequent fact
            final_bindings = bindings.copy()
            if selected_rule.action_fn is not None:
                computed_bindings = selected_rule.action_fn(final_bindings, self.working_memory, self.knowledge_base)
                final_bindings = {**final_bindings, **computed_bindings}

            derived_fact = self._apply_bindings(selected_rule.consequent, final_bindings)

            # If this fact already exists, discard this match and try the next best
            if self._fact_exists(derived_fact):
                matches.remove((selected_rule, bindings))
                continue

            indent = "\t" * depth
            if self.verbose:
                print(f"{indent}Selected: {selected_rule.rule_name} with bindings {bindings}")

            self.working_memory.add_fact(derived_fact, indent=indent, silent=not self.verbose)

            rules_fired_deeper = self._fire_rules_dfs(depth + 1, triggering_fact=derived_fact)

            return 1 + rules_fired_deeper

        return False