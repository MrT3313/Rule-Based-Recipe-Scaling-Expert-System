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

    def _match_antecedents(self, antecedents, bindings):
        if not antecedents:
            return [bindings]
        
        first_antecedent = antecedents[0]
        rest_antecedents = antecedents[1:]
        
        all_facts = self.knowledge_base.reference_facts + self.working_memory.facts
        
        if isinstance(first_antecedent, NegatedFact):
            pattern = first_antecedent.fact
            for fact in all_facts:
                if self._match_pattern(pattern, fact, bindings) is not None:
                    return []
            return self._match_antecedents(rest_antecedents, bindings)
        else:
            results = []
            for fact in all_facts:
                new_bindings = self._match_pattern(first_antecedent, fact, bindings)
                if new_bindings is not None:
                    sub_results = self._match_antecedents(rest_antecedents, new_bindings)
                    results.extend(sub_results)
            return results

    def _find_matching_rules(self):
        matches = []
        for rule in self.knowledge_base.rules:
            bindings_list = self._match_antecedents(rule.antecedents, {})
            for bindings in bindings_list:
                derived_fact = self._apply_bindings(rule.consequent, bindings)
                if not self._fact_exists(derived_fact):
                    matches.append((rule, bindings))
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
        return max(matches, key=lambda x: x[0].priority)

    def _fact_exists(self, fact):
        for existing_fact in self.working_memory.facts:
            if existing_fact.fact_title == fact.fact_title:
                if existing_fact.attributes == fact.attributes:
                    return True
        return False

    def run(self):
        self.cycle_count = 0
        
        if self.verbose:
            print("="*70)
            print("STARTING FORWARD CHAINING INFERENCE ENGINE (DFS)")
            print("="*70)
            print("")
        
        while True:
            self.cycle_count += 1
            
            if self.verbose:
                print(f"--- Cycle {self.cycle_count} ---")
            
            matches = self._find_matching_rules()
            
            if not matches:
                if self.verbose:
                    print("No rules can fire. Inference complete.")
                break
            
            selected_rule, bindings = self._resolve_conflict(matches)
            
            if self.verbose:
                print(f"Selected: {selected_rule.rule_name} with bindings {bindings}")
            
            derived_fact = self._apply_bindings(selected_rule.consequent, bindings)
            
            derived_fact.set_derivation(
                fact_id=self.working_memory.next_fact_id,
                derived_by_rule=selected_rule.rule_name,
                derived_at_cycle=self.cycle_count,
                derived_from=[]
            )
            self.working_memory.add_fact(derived_fact, silent=not self.verbose)
        
        if self.verbose:
            print("")
            print(f"Inference complete after {self.cycle_count} cycles")
            print(f"Working memory now contains {len(self.working_memory.facts)} facts")
