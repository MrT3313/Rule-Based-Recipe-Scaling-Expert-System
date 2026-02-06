from classes.InferenceEngine import InferenceEngine


class PlanningEngine(InferenceEngine):
    def __init__(self, *, wm, kb, verbose=True):
        super().__init__(wm=wm, kb=kb, verbose=verbose)

    def _resolve_conflict(self, *, matches):
        # TODO: should this be a rule we fetch from wm instead of a key:value on the ScalingEngine class?
        if self.conflict_resolution_strategy == "specificity":
            # match based on the most antecedents
            return max(matches, key=lambda x: len(x[0].antecedents))
        # (default) match based on rule priority
        return max(matches, key=lambda x: x[0].priority)
    
    # def _match_antecedents(self, *, antecedents, bindings):
    #     """Recursively match a list of antecedents, returning all valid binding sets."""
    #     exit()

    def _apply_bindings(self):
        exit()

    # def _match_pattern(self, *, pattern, fact):
    #     """Try to unify a single rule pattern against a single fact"""
    #     for key, pattern_value in pattern.attributes.items():
    #         # Pattern requires an attribute the fact doesn't have — no match
    #         if key not in fact.attributes:
    #             return None
    #     exit()

    def _match_rule_antecedents_to_fact_attributes(self, *, rule_antecedents, fact):
        # for key, pattern_value in rule_antecedents.attributes.items():
        for _ in rule_antecedents:
            for key, pattern_value in _.attributes.items():
                # Pattern requires an attribute the fact doesn't have — no match
                if key not in fact.attributes:
                    return False
        return True

    def _find_matching_rules(self, *, fact=None):
        """Return all (rule, bindings) pairs whose antecedents are satisfied."""
        matches = []
        for rule in self.knowledge_base.rules:


            # for each RULE see if there is a matching FACT in the WM / KB
            all_facts = self.knowledge_base.reference_facts + self.working_memory.facts
            if fact:
                all_facts = [_ for _ in all_facts if _.fact_title == fact.fact_title]

            # loop through facts
            for fact in all_facts:
                is_match = self._match_rule_antecedents_to_fact_attributes(rule_antecedents=rule.antecedents, fact=fact)
                if is_match:
                    new_bindings = self._apply_bindings()
                exit()






            bindings_list = self._match_antecedents(antecedents=rule.antecedents, bindings={})
            for bindings in bindings_list:
                matches.append((rule, bindings))
        return matches

    def _fire_rules_dfs(self, *, triggering_fact=None):
        """Fire one matching rule, then recursively chase any new rules enabled by the derived fact."""
        matches = self._find_matching_rules() if triggering_fact is None else self._find_matching_rules(fact=triggering_fact)
    
    def run(self, *, recipe):
        plan = []
        
        for idx, step in enumerate(recipe.steps):
            print(f"Step {idx + 1}: {step.description}")

            for equipment in step.required_equipment:
                # select available equipment
                selected_equipment = self.working_memory.query_equipment(
                    equipment_name=equipment.get('equipment_name'),
                    first=True,
                    state='AVAILABLE'
                )

                if not selected_equipment:
                    # try to rule rules to make something available
                    ## is there a dirty piece of equipment that can be cleaned?
                    dirty_equipment =self.working_memory.query_equipment(
                        equipment_name=equipment.get('equipment_name'),
                        first=True,
                        state='DIRTY'
                    )

                    # run rules to clean the dirty equipment
                    self._fire_rules_dfs(
                        triggering_fact=dirty_equipment
                    )

                exit()

            
            exit()

