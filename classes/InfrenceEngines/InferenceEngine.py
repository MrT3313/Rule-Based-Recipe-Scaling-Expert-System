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
        if pattern.fact_title != fact.fact_title:
            return None
        
        new_bindings = bindings.copy()
        
        for key, pattern_value in pattern.attributes.items():
            if key not in fact.attributes:
                return None
            
            fact_value = fact.attributes[key]
            
            if isinstance(pattern_value, str) and pattern_value.startswith('?'):
                if pattern_value in new_bindings:
                    if new_bindings[pattern_value] != fact_value:
                        return None
                else:
                    new_bindings[pattern_value] = fact_value
            else:
                if pattern_value != fact_value:
                    return None
        
        return new_bindings

    def _match_antecedents(self, antecedents, bindings, derivation_path=None):
        if derivation_path is None:
            derivation_path = []
        if not antecedents:
            return [(bindings, derivation_path)]

        first_antecedent = antecedents[0]
        rest_antecedents = antecedents[1:]
        all_facts = self.knowledge_base.reference_facts + self.working_memory.facts

        if isinstance(first_antecedent, NegatedFact):
            pattern = first_antecedent.fact
            for fact in all_facts:
                if self._match_pattern(pattern, fact, bindings) is not None:
                    return []
            return self._match_antecedents(rest_antecedents, bindings, derivation_path)

        results = []
        for fact in all_facts:
            new_bindings = self._match_pattern(first_antecedent, fact, bindings)
            if new_bindings is not None:
                sub_results = self._match_antecedents(
                    rest_antecedents, new_bindings, derivation_path + [fact]
                )
                results.extend(sub_results)
        return results

    def _find_matching_rules(self):
        matches = []
        for rule in self.knowledge_base.rules:
            bindings_support_list = self._match_antecedents(rule.antecedents, {})
            for bindings, derivation_path in bindings_support_list:
                test_bindings = bindings.copy()
                if rule.action_fn is not None:
                    computed_bindings = rule.action_fn(test_bindings, self.working_memory, self.knowledge_base)
                    test_bindings = {**test_bindings, **computed_bindings}
                derived_fact = self._apply_bindings(rule.consequent, test_bindings)
                if not self._fact_exists(derived_fact):
                    matches.append((rule, bindings, derivation_path))
        return matches

    def _find_rules_using_fact(self, fact):
        matches = []
        for rule in self.knowledge_base.rules:
            for antecedent in rule.antecedents:
                if isinstance(antecedent, NegatedFact):
                    continue
                initial_bindings = self._match_pattern(antecedent, fact, {})
                if initial_bindings is not None:
                    bindings_support_list = self._match_antecedents(rule.antecedents, {})
                    for bindings, derivation_path in bindings_support_list:
                        test_bindings = bindings.copy()
                        if rule.action_fn is not None:
                            computed_bindings = rule.action_fn(test_bindings, self.working_memory, self.knowledge_base)
                            test_bindings = {**test_bindings, **computed_bindings}
                        derived_fact = self._apply_bindings(rule.consequent, test_bindings)
                        if not self._fact_exists(derived_fact):
                            matches.append((rule, bindings, derivation_path))
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
        if self.conflict_resolution_strategy == "recency":
            return max(
                matches,
                key=lambda x: max(
                    (f.fact_id for f in x[2] if f.fact_id is not None), default=0
                ),
            )
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
        
        if not matches:
            return False
        
        selected_rule, bindings, derivation_path = self._resolve_conflict(matches)

        indent = "\t" * depth
        if self.verbose:
            print(f"{indent}Selected: {selected_rule.rule_name} with bindings {bindings}")

        if selected_rule.action_fn is not None:
            computed_bindings = selected_rule.action_fn(bindings, self.working_memory, self.knowledge_base)
            bindings = {**bindings, **computed_bindings}

        derived_fact = self._apply_bindings(selected_rule.consequent, bindings)
        derived_fact.set_derivation(
            fact_id=self.working_memory.next_fact_id,
            derived_by_rule=selected_rule.rule_name,
            derived_at_cycle=self.cycle_count,
            derived_from=derivation_path,
        )
        self.working_memory.add_fact(derived_fact, indent=indent, silent=not self.verbose)
        
        rules_fired_deeper = self._fire_rules_dfs(depth + 1, triggering_fact=derived_fact)
        
        return 1 + rules_fired_deeper