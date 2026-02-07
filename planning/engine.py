from classes.Fact import Fact
from planning.classes.MixingStep import MixingStep
from planning.classes.TransferStep import TransferStep


class PlanningEngine:
    def __init__(self, *, wm, kb, verbose=True):
        self.working_memory = wm
        self.knowledge_base = kb
        self.verbose = verbose

    def run(self, *, recipe):
        self.plan = []

        for idx, step in enumerate(recipe.steps):
            print(f"\nStep {idx + 1}: {step.description}")

            # VERIFY: all equipment is available (and reserve it)
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

            # TransferStep handles its own equipment resolution iteratively
            if isinstance(step, TransferStep):
                success, error = self._execute_transfer_step(step, recipe)
                if not success:
                    return (False, error)
                continue

            # Transition resolved equipment from RESERVED -> IN_USE
            for eq in resolved_equipment:
                eq.attributes['state'] = 'IN_USE'
                if self.verbose:
                    print(f"  -> {eq.attributes['equipment_name']} #{eq.attributes['equipment_id']} is now IN_USE")

            # EXECUTE SUBSTEPS (if any)
            if hasattr(step, 'substeps') and step.substeps:
                success, error = self._execute_substeps(step, recipe, resolved_equipment)
                if not success:
                    return (False, error)

            # After MixingStep substeps succeed, derive mixed_contents via rules
            if isinstance(step, MixingStep):
                for eq in resolved_equipment:
                    if eq.attributes.get('equipment_type') == 'CONTAINER':
                        trigger = Fact(
                            fact_title='mixing_completed',
                            equipment_name=eq.attributes['equipment_name'],
                            equipment_id=eq.attributes['equipment_id'],
                        )
                        self.working_memory.add_fact(fact=trigger, indent="  ")
                        matches = self._find_matching_rules(trigger)
                        if matches:
                            best_rule, best_bindings = self._resolve_conflict(matches)
                            derived = self._fire_rule(best_rule, best_bindings)
                            if self.verbose:
                                print(f"  [Rule fired] {best_rule.rule_name}")
                                if derived is not None:
                                    print(f"  [Derived] {derived}")

            # APPEND TO PLAN
            self.plan.append(step)

        return (True, self.plan)

    def _execute_substeps(self, step, recipe, resolved_equipment):
        """Execute substeps by asserting ingredient_addition_request facts and firing rules."""
        # Build ingredient lookup by id
        ingredient_map = {ing.id: ing for ing in recipe.ingredients}

        # Use the first resolved CONTAINER equipment for mixing substeps
        target_equipment = None
        for eq in resolved_equipment:
            if eq.attributes.get('equipment_type') == 'CONTAINER':
                target_equipment = eq
                break

        if target_equipment is None:
            return (False, "No CONTAINER equipment resolved for substeps")

        eq_name = target_equipment.attributes['equipment_name']
        eq_id = target_equipment.attributes['equipment_id']
        eq_volume = target_equipment.attributes.get('volume', 0)
        eq_volume_unit = target_equipment.attributes.get('volume_unit', '')

        for substep_idx, substep in enumerate(step.substeps):
            print(f"\n  Substep {substep_idx + 1}: {substep.description}")

            for ingredient_id in substep.ingredient_ids:
                ingredient = ingredient_map.get(ingredient_id)
                if ingredient is None:
                    return (False, f"Ingredient id={ingredient_id} not found in recipe")

                # Assert the trigger fact
                request_fact = Fact(
                    fact_title='ingredient_addition_request',
                    ingredient_id=ingredient.id,
                    ingredient_name=ingredient.ingredient_name,
                    amount=ingredient.amount,
                    unit=ingredient.unit,
                    measurement_category=ingredient.measurement_category,
                    equipment_name=eq_name,
                    equipment_id=eq_id,
                    equipment_volume=eq_volume,
                    equipment_volume_unit=eq_volume_unit,
                )
                self.working_memory.add_fact(fact=request_fact, indent="    ")

                # Find and fire matching rules
                matches = self._find_matching_rules(request_fact)
                if not matches:
                    return (False, f"No rule matched for ingredient {ingredient.ingredient_name}")

                best_rule, best_bindings = self._resolve_conflict(matches)
                derived = self._fire_rule(best_rule, best_bindings)

                if self.verbose:
                    print(f"    [Rule fired] {best_rule.rule_name}")
                    if derived is not None:
                        print(f"    [Derived] {derived}")

                # Check for errors from the action_fn
                if '?error' in best_bindings:
                    return (False, best_bindings['?error'])

        return (True, None)

    def _execute_transfer_step(self, step, recipe):
        """Execute a TransferStep: discover sources from mixed_contents, plan, then loop per target sheet."""
        # Phase 0 — Discover sources from derived mixed_contents facts
        sources = self.working_memory.query_facts(
            fact_title='mixed_contents',
            equipment_name=step.source_equipment_name,
        )
        if not sources:
            return (False, f"No mixed_contents found for {step.source_equipment_name}")

        for source in sources:
            source_equipment_id = source.attributes['equipment_id']

            if self.verbose:
                print(f"\n  Processing {step.source_equipment_name} #{source_equipment_id} "
                      f"(total_volume={source.attributes['total_volume']:.2f} {source.attributes['volume_unit']})")

            # Phase 1 — Fire planning rule (domain logic in rule)
            planning_request = Fact(
                fact_title='transfer_planning_request',
                source_equipment_name=step.source_equipment_name,
                source_equipment_id=source_equipment_id,
                scoop_size_amount=step.scoop_size_amount,
                scoop_size_unit=step.scoop_size_unit,
                target_equipment_name=step.target_equipment_name,
            )
            self.working_memory.add_fact(fact=planning_request, indent="  ")

            matches = self._find_matching_rules(planning_request)
            if not matches:
                return (False, "No rule matched for transfer_planning_request")

            best_rule, best_bindings = self._resolve_conflict(matches)
            derived = self._fire_rule(best_rule, best_bindings)

            if '?error' in best_bindings:
                return (False, best_bindings['?error'])

            if self.verbose:
                print(f"  [Rule fired] {best_rule.rule_name}")
                if derived is not None:
                    print(f"  [Derived] {derived}")

            # Read transfer_plan from WM
            transfer_plan = self.working_memory.query_facts(
                fact_title='transfer_plan',
                first=True,
            )
            if transfer_plan is None:
                return (False, "transfer_plan fact not found after planning rule")

            num_dough_balls = transfer_plan.attributes['num_dough_balls']
            capacity_per_sheet = transfer_plan.attributes['capacity_per_sheet']
            num_sheets_needed = transfer_plan.attributes['num_sheets_needed']

            if self.verbose:
                print(f"\n  Transfer plan: {num_dough_balls} dough balls, {capacity_per_sheet}/sheet, {num_sheets_needed} sheet(s) needed")

            # Phase 2 — Loop per sheet (engine orchestration)
            remaining = num_dough_balls
            for sheet_idx in range(num_sheets_needed):
                equipment_need = {'equipment_name': step.target_equipment_name, 'required_count': 1}
                resolved_list = self._resolve_equipment(equipment_need)
                if resolved_list is None:
                    return (False, f"Could not resolve {step.target_equipment_name} for sheet {sheet_idx + 1}")

                target_eq = resolved_list[0]
                target_eq.attributes['state'] = 'IN_USE'
                target_eq_id = target_eq.attributes['equipment_id']

                quantity = min(remaining, capacity_per_sheet)

                if self.verbose:
                    print(f"\n  Sheet {sheet_idx + 1}: {step.target_equipment_name} #{target_eq_id} — placing {quantity} dough balls")

                # Assert transfer_request trigger fact
                transfer_request = Fact(
                    fact_title='transfer_request',
                    source_equipment_name=step.source_equipment_name,
                    source_equipment_id=source_equipment_id,
                    target_equipment_name=step.target_equipment_name,
                    target_equipment_id=target_eq_id,
                    quantity=quantity,
                    scoop_size_amount=step.scoop_size_amount,
                    scoop_size_unit=step.scoop_size_unit,
                )
                self.working_memory.add_fact(fact=transfer_request, indent="    ")

                matches = self._find_matching_rules(transfer_request)
                if not matches:
                    return (False, f"No rule matched for transfer_request on sheet {sheet_idx + 1}")

                best_rule, best_bindings = self._resolve_conflict(matches)
                derived = self._fire_rule(best_rule, best_bindings)

                if '?error' in best_bindings:
                    return (False, best_bindings['?error'])

                if self.verbose:
                    print(f"    [Rule fired] {best_rule.rule_name}")
                    if derived is not None:
                        print(f"    [Derived] {derived}")

                remaining -= quantity

                # Append a per-sheet TransferStep to the plan
                sheet_step = TransferStep(
                    description=f"Transfer {quantity} dough balls to {step.target_equipment_name} #{target_eq_id}",
                    source_equipment_name=step.source_equipment_name,
                    target_equipment_name=step.target_equipment_name,
                    scoop_size_amount=step.scoop_size_amount,
                    scoop_size_unit=step.scoop_size_unit,
                )
                self.plan.append(sheet_step)

            # Phase 3 — Cleanup: mark source equipment DIRTY
            source_eq = self.working_memory.query_equipment(
                equipment_name=step.source_equipment_name,
                equipment_id=source_equipment_id,
                first=True,
            )
            if source_eq:
                source_eq.attributes['state'] = 'DIRTY'
                if self.verbose:
                    print(f"\n  -> {step.source_equipment_name} #{source_equipment_id} is now DIRTY")

        return (True, None)

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

        # Skip consequent if action_fn signaled an error
        if '?error' in bindings:
            return None

        if rule.consequent is not None:
            derived = self._apply_bindings(rule.consequent, bindings)
            self.working_memory.add_fact(fact=derived)
            return derived

        return None

    def _resolve_conflict(self, matches):
        """Pick the best (rule, bindings) from a list. Priority-based."""
        return max(matches, key=lambda x: x[0].priority)
