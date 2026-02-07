from classes.Fact import Fact
from planning.classes.MixingStep import MixingStep
from planning.classes.TransferStep import TransferStep
from planning.classes.TransferEquipment import TransferEquipment
from planning.classes.TransferItem import TransferItem
from planning.classes.CookStep import CookStep
from planning.classes.WaitStep import WaitStep


class PlanningEngine:
    def __init__(self, *, wm, kb, verbose=True):
        self.working_memory = wm
        self.knowledge_base = kb
        self.verbose = verbose

    def run(self, *, recipe):
        self.plan = []
        self.recipe = recipe
        self.last_error = None

        for idx, step in enumerate(recipe.steps):
            if self.verbose:
                print(f"\nStep {idx + 1}: {step.description}")

            # Resolve all equipment for this step
            resolved_equipment = []
            for equipment_need in step.required_equipment:
                resolved_list = self._resolve_equipment(equipment_need)
                if resolved_list is not None:
                    for eq in resolved_list:
                        if self.verbose:
                            print(f"  -> Resolved: {eq}")
                        resolved_equipment.append(eq)
                else:
                    equipment_name = equipment_need.get('equipment_name', equipment_need)
                    if self.verbose:
                        print(f"  -> FAILED to resolve equipment: {equipment_name}")
                    return (False, f"{equipment_name} could not be resolved")

            self._current_resolved_equipment = resolved_equipment

            # Boundary translation: Step object -> step_request Fact
            step_request = self._build_step_request(step, idx, resolved_equipment)
            self.working_memory.add_fact(fact=step_request)

            # Forward-chain: orchestration rules handle dispatch + execution
            self._forward_chain(step_request)

            # Error check
            if self.last_error:
                return (False, self.last_error)

            # For generic steps (no dispatch rule matched), handle directly
            if step_request.attributes['step_type'] == 'GENERIC':
                # Transition resolved equipment from RESERVED -> IN_USE
                for eq in resolved_equipment:
                    eq.attributes['state'] = 'IN_USE'
                    if self.verbose:
                        print(f"  -> {eq.attributes['equipment_name']} #{eq.attributes['equipment_id']} is now IN_USE")
                self.plan.append(step)

        return (True, self.plan)

    def _build_step_request(self, step, step_idx, resolved_equipment):
        """Convert a recipe Step object to a step_request Fact for rule-based dispatch.
        This is the ONE place where isinstance is used — at the boundary between
        the recipe domain model (Python objects) and the rule system (facts)."""

        # Equipment removal: TransferEquipment where source is not BAKING_SHEET
        if isinstance(step, TransferEquipment) and step.source_equipment_name != 'BAKING_SHEET':
            return Fact(
                fact_title='step_request',
                step_type='EQUIPMENT_REMOVAL',
                step_idx=step_idx,
            )

        # Item transfer to SURFACE equipment (e.g., BAKING_SHEET -> COOLING_RACK)
        if isinstance(step, TransferItem) and step.target_equipment_name == 'COOLING_RACK':
            return Fact(
                fact_title='step_request',
                step_type='ITEM_TRANSFER_TO_SURFACE',
                step_idx=step_idx,
            )

        # TransferItem (e.g., scoop dough onto baking sheets)
        if isinstance(step, TransferItem):
            return Fact(
                fact_title='step_request',
                step_type='TRANSFER_ITEM',
                step_idx=step_idx,
            )

        # TransferEquipment (e.g., sheet -> oven)
        if isinstance(step, TransferEquipment):
            return Fact(
                fact_title='step_request',
                step_type='TRANSFER_EQUIPMENT',
                step_idx=step_idx,
            )

        # CookStep
        if isinstance(step, CookStep):
            return Fact(
                fact_title='step_request',
                step_type='COOK',
                step_idx=step_idx,
            )

        # MixingStep
        if isinstance(step, MixingStep):
            target_equipment = None
            for eq in resolved_equipment:
                if eq.attributes.get('equipment_type') == 'CONTAINER':
                    target_equipment = eq
                    break

            if target_equipment is None:
                return Fact(
                    fact_title='step_request',
                    step_type='MIXING',
                    step_idx=step_idx,
                    equipment_name='UNKNOWN',
                    equipment_id=0,
                    equipment_volume=0,
                    equipment_volume_unit='',
                )

            # Transition resolved equipment from RESERVED -> IN_USE
            for eq in resolved_equipment:
                eq.attributes['state'] = 'IN_USE'
                if self.verbose:
                    print(f"  -> {eq.attributes['equipment_name']} #{eq.attributes['equipment_id']} is now IN_USE")

            return Fact(
                fact_title='step_request',
                step_type='MIXING',
                step_idx=step_idx,
                equipment_name=target_equipment.attributes['equipment_name'],
                equipment_id=target_equipment.attributes['equipment_id'],
                equipment_volume=target_equipment.attributes.get('volume', 0),
                equipment_volume_unit=target_equipment.attributes.get('volume_unit', ''),
            )

        # Generic step (no special handling needed)
        return Fact(
            fact_title='step_request',
            step_type='GENERIC',
            step_idx=step_idx,
        )

    def _forward_chain(self, trigger_fact):
        """Find matching rules for a trigger fact, resolve conflict, fire via DFS.
        Returns the derived fact (or None). Sets self.last_error on failure."""
        matches = self._find_matching_rules(trigger_fact)
        if not matches:
            return None
        best_rule, best_bindings = self._resolve_conflict(matches)
        self._last_bindings = best_bindings
        derived = self._fire_rule_dfs(best_rule, best_bindings)
        if '?error' in best_bindings:
            self.last_error = best_bindings['?error']
        return derived

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
                    derived = self._fire_rule_dfs(best_rule, best_bindings)
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

    def _fire_rule_dfs(self, rule, bindings, plan_override=None):
        """Fire a rule: run action_fn if present, then derive consequent if present.
        DFS: if the derived fact triggers further rules, fire them recursively."""
        if rule.action_fn:
            target_plan = plan_override if plan_override is not None else self.plan
            bindings['_engine'] = self  # orchestration rules use this
            bindings = rule.action_fn(bindings=bindings, wm=self.working_memory, kb=self.knowledge_base, plan=target_plan)

        # Skip consequent if action_fn signaled an error
        if '?error' in bindings:
            return None

        if rule.consequent is not None:
            derived = self._apply_bindings(rule.consequent, bindings)
            self.working_memory.add_fact(fact=derived)

            # DFS: check if derived fact triggers further rules
            chain_matches = self._find_matching_rules(derived)
            if chain_matches:
                best_chain_rule, best_chain_bindings = self._resolve_conflict(chain_matches)
                self._fire_rule_dfs(best_chain_rule, best_chain_bindings, plan_override=plan_override)

            return derived

        return None

    def _resolve_conflict(self, matches):
        """Pick the best (rule, bindings) from a list. Priority-based."""
        return max(matches, key=lambda x: x[0].priority)
