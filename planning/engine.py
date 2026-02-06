from classes.Fact import Fact


class PlanningEngine:
    def __init__(self, *, wm, kb, verbose=True):
        self.working_memory = wm
        self.knowledge_base = kb
        self.verbose = verbose

    def run(self, *, recipe):
        self.plan = []

        for idx, step in enumerate(recipe.steps):
            print(f"Step {idx + 1}: {step.description}")

            # VERIFY: all equipment is available (and reserve it)
            for equipment_need in step.required_equipment:
                resolved_list = self._resolve_equipment(equipment_need)
                if resolved_list is not None:
                    for eq in resolved_list:
                        if self.verbose:
                            print(f"  -> Resolved: {eq}")
                else:
                    equipment_name = equipment_need.get('equipment_name', equipment_need)
                    if self.verbose:
                        print(f"  -> FAILED to resolve equipment: {equipment_name}")
                    return (False, f"{equipment_name} could not be resolved")

        return (True, self.plan)

    def _resolve_equipment(self, equipment_need):
        """Resolve required_count pieces of equipment, returning a list or None on failure."""
        equipment_name = equipment_need.get('equipment_name')
        required_count = equipment_need.get('required_count', 1)
        resolved = []

        for _ in range(required_count):
            # 1. Look for AVAILABLE equipment
            available = self.working_memory.query_equipment(
                equipment_name=equipment_name,
                first=True,
                state='AVAILABLE',
            )
            if available:
                available.attributes['state'] = 'RESERVED'
                resolved.append(available)
                continue

            # 2. Look for DIRTY equipment and try to clean it via rules
            dirty = self.working_memory.query_equipment(
                equipment_name=equipment_name,
                first=True,
                state='DIRTY',
            )
            if dirty:
                matches = self._find_matching_rules(dirty)
                if matches:
                    best_rule, best_bindings = self._resolve_conflict(matches)
                    best_bindings['reserve_after_cleaning'] = True
                    derived = self._fire_rule(best_rule, best_bindings)
                    if self.verbose:
                        print(f"    [Rule fired] {best_rule.rule_name} -> updated Fact #{dirty.fact_id}")
                        if derived is not None:
                            print(f"    [Rule fired] {best_rule.rule_name} -> derived {derived}")
                    resolved.append(dirty)
                    continue

            # Not enough equipment available
            return None

        return resolved

    def _find_matching_rules(self, fact):
        """Return all (rule, bindings) pairs whose antecedents match the given fact."""
        matches = []
        for rule in self.knowledge_base.rules:
            bindings = {}
            all_matched = True
            for antecedent in rule.antecedents:
                result = self._unify(antecedent, fact, bindings)
                if result is None:
                    all_matched = False
                    break
                bindings = result
            if all_matched:
                matches.append((rule, bindings))
        return matches

    def _unify(self, pattern, fact, bindings):
        """Try to match one antecedent pattern against one fact.
        Returns updated bindings dict or None on failure. Pure function."""
        if pattern.fact_title != fact.fact_title:
            return None

        new_bindings = bindings.copy()

        for key, pattern_value in pattern.attributes.items():
            if key not in fact.attributes:
                return None

            fact_value = fact.attributes[key]

            if isinstance(pattern_value, str) and pattern_value.startswith('?'):
                # Variable — check consistency or bind
                if pattern_value in new_bindings:
                    if new_bindings[pattern_value] != fact_value:
                        return None
                else:
                    new_bindings[pattern_value] = fact_value
            else:
                # Literal — must match exactly
                if pattern_value != fact_value:
                    return None

        return new_bindings

    def _apply_bindings(self, fact_template, bindings):
        """Substitute ?variables in a consequent template with concrete values from bindings."""
        new_attrs = {}
        for key, value in fact_template.attributes.items():
            if isinstance(value, str) and value.startswith('?'):
                if value in bindings:
                    new_attrs[key] = bindings[value]
                else:
                    new_attrs[key] = value  # leave unbound variables as-is
            else:
                new_attrs[key] = value
        return Fact(fact_title=fact_template.fact_title, **new_attrs)

    def _fire_rule(self, rule, bindings):
        """Fire a rule: run action_fn if present, then derive consequent if present."""
        if rule.action_fn:
            bindings = rule.action_fn(bindings=bindings, wm=self.working_memory, kb=self.knowledge_base, plan=self.plan)

        if rule.consequent is not None:
            derived = self._apply_bindings(rule.consequent, bindings)
            self.working_memory.add_fact(fact=derived)
            return derived

        return None

    def _resolve_conflict(self, matches):
        """Pick the best (rule, bindings) from a list. Priority-based."""
        return max(matches, key=lambda x: x[0].priority)
