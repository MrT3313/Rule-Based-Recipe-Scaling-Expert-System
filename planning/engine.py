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

            # Equipment removal: TransferEquipment where source is not BAKING_SHEET
            # (e.g., OVEN → COUNTERTOP)
            if isinstance(step, TransferEquipment) and step.source_equipment_name != 'BAKING_SHEET':
                success, error = self._execute_equipment_removal_step(step, recipe)
                if not success:
                    return (False, error)
                continue

            # Item transfer to SURFACE equipment (e.g., BAKING_SHEET → COOLING_RACK)
            if isinstance(step, TransferItem) and step.target_equipment_name == 'COOLING_RACK':
                success, error = self._execute_item_transfer_step(step, recipe)
                if not success:
                    return (False, error)
                continue

            # TransferItem handles its own equipment resolution iteratively
            if isinstance(step, TransferItem):
                success, error = self._execute_transfer_step(step, recipe)
                if not success:
                    return (False, error)
                continue

            # TransferEquipment: equipment-to-equipment transfers (e.g., sheet → oven)
            if isinstance(step, TransferEquipment):
                success, error = self._execute_equipment_transfer_step(step, recipe)
                if not success:
                    return (False, error)
                continue

            # CookStep: equipment transfer + cooking wait
            if isinstance(step, CookStep):
                success, error = self._execute_cook_step(step, recipe)
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
        """Execute a TransferItem: discover sources from mixed_contents, plan, then loop per target sheet."""
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

                # Append a per-sheet TransferItem to the plan
                sheet_step = TransferItem(
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

    def _execute_equipment_transfer_step(self, step, recipe):
        """Execute a TransferEquipment: discover sources, preheat wait, plan, then loop per rack."""
        # Phase 0 — Discover source equipment (IN_USE sheets with DOUGH_BALLS contents)
        source_contents = self.working_memory.query_facts(
            fact_title='equipment_contents',
            equipment_name=step.source_equipment_name,
            content_type='DOUGH_BALLS',
        )
        if not source_contents:
            return (False, f"No {step.source_equipment_name} found with DOUGH_BALLS contents")

        # Collect unique source equipment IDs
        source_ids = []
        for content in source_contents:
            sid = content.attributes['equipment_id']
            if sid not in source_ids:
                source_ids.append(sid)

        if self.verbose:
            print(f"\n  Found {len(source_ids)} {step.source_equipment_name}(s) with dough balls: {source_ids}")

        # Phase 1 — Preheat wait: assert preheat_check_request → fire rule
        preheat_request = Fact(
            fact_title='preheat_check_request',
            target_equipment_name=step.target_equipment_name,
        )
        self.working_memory.add_fact(fact=preheat_request, indent="  ")

        matches = self._find_matching_rules(preheat_request)
        if not matches:
            return (False, "No rule matched for preheat_check_request")

        best_rule, best_bindings = self._resolve_conflict(matches)
        derived = self._fire_rule(best_rule, best_bindings)

        if '?error' in best_bindings:
            return (False, best_bindings['?error'])

        if self.verbose:
            print(f"  [Rule fired] {best_rule.rule_name}")
            if derived is not None:
                print(f"  [Derived] {derived}")

        # Phase 2 — Plan: assert equipment_transfer_planning_request → fire rule
        planning_request = Fact(
            fact_title='equipment_transfer_planning_request',
            source_equipment_name=step.source_equipment_name,
            target_equipment_name=step.target_equipment_name,
            num_source_items=len(source_ids),
        )
        self.working_memory.add_fact(fact=planning_request, indent="  ")

        matches = self._find_matching_rules(planning_request)
        if not matches:
            return (False, "No rule matched for equipment_transfer_planning_request")

        best_rule, best_bindings = self._resolve_conflict(matches)
        derived = self._fire_rule(best_rule, best_bindings)

        if '?error' in best_bindings:
            return (False, best_bindings['?error'])

        if self.verbose:
            print(f"  [Rule fired] {best_rule.rule_name}")
            if derived is not None:
                print(f"  [Derived] {derived}")

        # Read equipment_transfer_plan from WM
        transfer_plan = self.working_memory.query_facts(
            fact_title='equipment_transfer_plan',
            first=True,
        )
        if transfer_plan is None:
            return (False, "equipment_transfer_plan fact not found after planning rule")

        items_per_rack = transfer_plan.attributes['items_per_rack']
        capacity_per_target = transfer_plan.attributes['capacity_per_target']
        num_targets_needed = transfer_plan.attributes['num_targets_needed']

        if self.verbose:
            print(f"\n  Transfer plan: {len(source_ids)} sheets, {items_per_rack}/rack, "
                  f"{capacity_per_target}/oven, {num_targets_needed} oven(s) needed")

        # Phase 3 — Demand-driven loop: ask rule system for available racks, resolve new ovens on-demand
        remaining_sources = list(source_ids)

        while remaining_sources:
            # Step A — Ask rule system: "Is there an available rack?"
            rack_request = Fact(
                fact_title='available_rack_request',
                target_equipment_name=step.target_equipment_name,
            )
            self.working_memory.add_fact(fact=rack_request, indent="    ")

            matches = self._find_matching_rules(rack_request)
            if not matches:
                return (False, "No rule matched for available_rack_request")

            best_rule, best_bindings = self._resolve_conflict(matches)
            derived = self._fire_rule(best_rule, best_bindings)

            if self.verbose:
                print(f"    [Rule fired] {best_rule.rule_name}")
                if derived is not None:
                    print(f"    [Derived] {derived}")

            rack_found = best_bindings.get('?rack_found', False)

            # Step B — If no rack found, resolve a new oven and transition to IN_USE
            if not rack_found:
                equipment_need = {'equipment_name': step.target_equipment_name, 'required_count': 1}
                resolved_list = self._resolve_equipment(equipment_need)
                if resolved_list is None:
                    return (False, f"Could not resolve additional {step.target_equipment_name}")

                new_oven = resolved_list[0]
                new_oven.attributes['state'] = 'IN_USE'
                new_oven_id = new_oven.attributes['equipment_id']

                # Add preheat wait step to plan (same as Phase 1 does for oven #1)
                self.plan.append(WaitStep(
                    description=f"Wait for {step.target_equipment_name} #{new_oven_id} to preheat",
                    equipment_name=step.target_equipment_name,
                    equipment_id=new_oven_id,
                ))

                if self.verbose:
                    print(f"\n  -> Resolved and preheated {step.target_equipment_name} #{new_oven_id}")

                # Re-ask the rule system now that a new oven is IN_USE
                rack_request2 = Fact(
                    fact_title='available_rack_request',
                    target_equipment_name=step.target_equipment_name,
                )
                self.working_memory.add_fact(fact=rack_request2, indent="    ")

                matches2 = self._find_matching_rules(rack_request2)
                if not matches2:
                    return (False, "No rule matched for available_rack_request after resolving new equipment")

                best_rule2, best_bindings2 = self._resolve_conflict(matches2)
                derived2 = self._fire_rule(best_rule2, best_bindings2)

                if self.verbose:
                    print(f"    [Rule fired] {best_rule2.rule_name}")
                    if derived2 is not None:
                        print(f"    [Derived] {derived2}")

                rack_found = best_bindings2.get('?rack_found', False)
                if not rack_found:
                    return (False, f"Still no available rack after resolving {step.target_equipment_name}")

                # Use the re-derived bindings
                best_bindings = best_bindings2

            oven_id = best_bindings['?equipment_id']
            rack_num = best_bindings['?rack_number']
            source_id = remaining_sources.pop(0)

            if self.verbose:
                print(f"\n  {step.target_equipment_name} #{oven_id}, Rack {rack_num}: "
                      f"placing {step.source_equipment_name} #{source_id}")

            # Step C — Assert equipment_transfer_request → fire execute_equipment_transfer rule
            transfer_request = Fact(
                fact_title='equipment_transfer_request',
                target_equipment_name=step.target_equipment_name,
                target_equipment_id=oven_id,
                slot_number=rack_num,
                source_equipment_name=step.source_equipment_name,
                source_equipment_id=source_id,
            )
            self.working_memory.add_fact(fact=transfer_request, indent="    ")

            matches = self._find_matching_rules(transfer_request)
            if not matches:
                return (False, f"No rule matched for equipment_transfer_request on rack {rack_num}")

            best_rule, best_bindings = self._resolve_conflict(matches)
            derived = self._fire_rule(best_rule, best_bindings)

            if '?error' in best_bindings:
                return (False, best_bindings['?error'])

            if self.verbose:
                print(f"    [Rule fired] {best_rule.rule_name}")
                if derived is not None:
                    print(f"    [Derived] {derived}")

            # Append per-rack TransferEquipment to plan
            rack_step = TransferEquipment(
                description=f"Place {step.source_equipment_name} #{source_id} on {step.target_equipment_name} #{oven_id} rack {rack_num}",
                source_equipment_name=step.source_equipment_name,
                target_equipment_name=step.target_equipment_name,
            )
            self.plan.append(rack_step)

        return (True, None)

    def _execute_cook_step(self, step, recipe):
        """Execute a CookStep: reuse equipment transfer phases 0-2, then track oven fullness for cooking waits.
        Creates one CookStep per oven, each with its own substeps (preheat, transfers, wait)."""
        # Read source/target from the TransferEquipment template in substeps
        transfer_template = None
        for sub in step.substeps:
            if isinstance(sub, TransferEquipment):
                transfer_template = sub
                break

        if transfer_template is None:
            return (False, "CookStep has no TransferEquipment substep template")

        # Read duration from WaitStep template in substeps
        wait_template = next((s for s in step.substeps if isinstance(s, WaitStep)), None)
        if wait_template is None:
            return (False, "CookStep has no WaitStep substep template")

        duration = wait_template.duration
        duration_unit = wait_template.duration_unit

        source_equipment_name = transfer_template.source_equipment_name
        target_equipment_name = transfer_template.target_equipment_name

        # Per-oven substep tracking
        oven_substeps = {}  # oven_id -> list of substeps
        current_oven_id = None

        # Phase 0 — Discover source equipment (IN_USE sheets with DOUGH_BALLS contents)
        source_contents = self.working_memory.query_facts(
            fact_title='equipment_contents',
            equipment_name=source_equipment_name,
            content_type='DOUGH_BALLS',
        )
        if not source_contents:
            return (False, f"No {source_equipment_name} found with DOUGH_BALLS contents")

        source_ids = []
        for content in source_contents:
            sid = content.attributes['equipment_id']
            if sid not in source_ids:
                source_ids.append(sid)

        if self.verbose:
            print(f"\n  Found {len(source_ids)} {source_equipment_name}(s) with dough balls: {source_ids}")

        # Phase 1 — Preheat wait: assert preheat_check_request → fire rule
        preheat_request = Fact(
            fact_title='preheat_check_request',
            target_equipment_name=target_equipment_name,
        )
        self.working_memory.add_fact(fact=preheat_request, indent="  ")

        matches = self._find_matching_rules(preheat_request)
        if not matches:
            return (False, "No rule matched for preheat_check_request")

        best_rule, best_bindings = self._resolve_conflict(matches)

        # Get oven_id from bindings for the first oven
        current_oven_id = best_bindings.get('?equipment_id')
        if current_oven_id is None:
            # Fallback: query the first IN_USE oven
            first_oven = self.working_memory.query_equipment(
                equipment_name=target_equipment_name,
                state='IN_USE',
                first=True,
            )
            if first_oven:
                current_oven_id = first_oven.attributes['equipment_id']
            else:
                return (False, "No IN_USE oven found for preheat")

        oven_substeps[current_oven_id] = []
        derived = self._fire_rule(best_rule, best_bindings, plan_override=oven_substeps[current_oven_id])

        if '?error' in best_bindings:
            return (False, best_bindings['?error'])

        if self.verbose:
            print(f"  [Rule fired] {best_rule.rule_name}")
            if derived is not None:
                print(f"  [Derived] {derived}")

        # Phase 2 — Plan: assert equipment_transfer_planning_request → fire rule
        planning_request = Fact(
            fact_title='equipment_transfer_planning_request',
            source_equipment_name=source_equipment_name,
            target_equipment_name=target_equipment_name,
            num_source_items=len(source_ids),
        )
        self.working_memory.add_fact(fact=planning_request, indent="  ")

        matches = self._find_matching_rules(planning_request)
        if not matches:
            return (False, "No rule matched for equipment_transfer_planning_request")

        best_rule, best_bindings = self._resolve_conflict(matches)
        derived = self._fire_rule(best_rule, best_bindings)

        if '?error' in best_bindings:
            return (False, best_bindings['?error'])

        if self.verbose:
            print(f"  [Rule fired] {best_rule.rule_name}")
            if derived is not None:
                print(f"  [Derived] {derived}")

        # Read equipment_transfer_plan from WM
        transfer_plan = self.working_memory.query_facts(
            fact_title='equipment_transfer_plan',
            first=True,
        )
        if transfer_plan is None:
            return (False, "equipment_transfer_plan fact not found after planning rule")

        if self.verbose:
            items_per_rack = transfer_plan.attributes['items_per_rack']
            capacity_per_target = transfer_plan.attributes['capacity_per_target']
            num_targets_needed = transfer_plan.attributes['num_targets_needed']
            print(f"\n  Transfer plan: {len(source_ids)} sheets, {items_per_rack}/rack, "
                  f"{capacity_per_target}/oven, {num_targets_needed} oven(s) needed")

        # Phase 3 — Demand-driven loop with cooking wait tracking
        remaining_sources = list(source_ids)
        # Track which ovens have already had a cooking_wait_request fired
        ovens_with_cooking_started = set()

        while remaining_sources:
            # Step A — Ask rule system: "Is there an available rack?"
            rack_request = Fact(
                fact_title='available_rack_request',
                target_equipment_name=target_equipment_name,
            )
            self.working_memory.add_fact(fact=rack_request, indent="    ")

            matches = self._find_matching_rules(rack_request)
            if not matches:
                return (False, "No rule matched for available_rack_request")

            best_rule, best_bindings = self._resolve_conflict(matches)
            derived = self._fire_rule(best_rule, best_bindings)

            if self.verbose:
                print(f"    [Rule fired] {best_rule.rule_name}")
                if derived is not None:
                    print(f"    [Derived] {derived}")

            rack_found = best_bindings.get('?rack_found', False)

            # Step B — If no rack found, the current oven is full → fire cooking wait, finalize CookStep, then resolve new oven
            if not rack_found:
                # Fire cooking_wait_request for all full ovens that haven't had one yet
                in_use_ovens = self.working_memory.query_equipment(
                    equipment_name=target_equipment_name,
                    state='IN_USE',
                )
                for oven in in_use_ovens:
                    oven_id = oven.attributes['equipment_id']
                    if oven_id not in ovens_with_cooking_started:
                        num_racks = oven.attributes.get('number_of_racks', 1)
                        existing_contents = self.working_memory.query_facts(
                            fact_title='equipment_contents',
                            equipment_name=target_equipment_name,
                            equipment_id=oven_id,
                        )
                        if len(existing_contents) >= num_racks:
                            self._fire_cooking_wait(duration, duration_unit, oven_id, target_equipment_name, oven_substeps[oven_id])
                            ovens_with_cooking_started.add(oven_id)
                            # Finalize this oven's CookStep
                            self._finalize_oven_cook_step(step, oven_id, target_equipment_name, oven_substeps)

                # Resolve a new oven
                equipment_need = {'equipment_name': target_equipment_name, 'required_count': 1}
                resolved_list = self._resolve_equipment(equipment_need)
                if resolved_list is None:
                    return (False, f"Could not resolve additional {target_equipment_name}")

                new_oven = resolved_list[0]
                new_oven.attributes['state'] = 'IN_USE'
                new_oven_id = new_oven.attributes['equipment_id']

                # Initialize substeps for the new oven with preheat wait
                oven_substeps[new_oven_id] = []
                oven_substeps[new_oven_id].append(WaitStep(
                    description=f"Wait for {target_equipment_name} #{new_oven_id} to preheat",
                    equipment_name=target_equipment_name,
                    equipment_id=new_oven_id,
                ))
                current_oven_id = new_oven_id

                if self.verbose:
                    print(f"\n  -> Resolved and preheated {target_equipment_name} #{new_oven_id}")

                # Re-ask the rule system now that a new oven is IN_USE
                rack_request2 = Fact(
                    fact_title='available_rack_request',
                    target_equipment_name=target_equipment_name,
                )
                self.working_memory.add_fact(fact=rack_request2, indent="    ")

                matches2 = self._find_matching_rules(rack_request2)
                if not matches2:
                    return (False, "No rule matched for available_rack_request after resolving new equipment")

                best_rule2, best_bindings2 = self._resolve_conflict(matches2)
                derived2 = self._fire_rule(best_rule2, best_bindings2)

                if self.verbose:
                    print(f"    [Rule fired] {best_rule2.rule_name}")
                    if derived2 is not None:
                        print(f"    [Derived] {derived2}")

                rack_found = best_bindings2.get('?rack_found', False)
                if not rack_found:
                    return (False, f"Still no available rack after resolving {target_equipment_name}")

                best_bindings = best_bindings2

            oven_id = best_bindings['?equipment_id']
            rack_num = best_bindings['?rack_number']
            source_id = remaining_sources.pop(0)

            if self.verbose:
                print(f"\n  {target_equipment_name} #{oven_id}, Rack {rack_num}: "
                      f"placing {source_equipment_name} #{source_id}")

            # Step C — Assert equipment_transfer_request → fire execute_equipment_transfer rule
            transfer_request = Fact(
                fact_title='equipment_transfer_request',
                target_equipment_name=target_equipment_name,
                target_equipment_id=oven_id,
                slot_number=rack_num,
                source_equipment_name=source_equipment_name,
                source_equipment_id=source_id,
            )
            self.working_memory.add_fact(fact=transfer_request, indent="    ")

            matches = self._find_matching_rules(transfer_request)
            if not matches:
                return (False, f"No rule matched for equipment_transfer_request on rack {rack_num}")

            best_rule, best_bindings = self._resolve_conflict(matches)
            derived = self._fire_rule(best_rule, best_bindings)

            if '?error' in best_bindings:
                return (False, best_bindings['?error'])

            if self.verbose:
                print(f"    [Rule fired] {best_rule.rule_name}")
                if derived is not None:
                    print(f"    [Derived] {derived}")

            # Append per-rack TransferEquipment to the oven's substeps
            rack_step = TransferEquipment(
                description=f"Place {source_equipment_name} #{source_id} on {target_equipment_name} #{oven_id} rack {rack_num}",
                source_equipment_name=source_equipment_name,
                target_equipment_name=target_equipment_name,
            )
            oven_substeps[oven_id].append(rack_step)

            # Check if this was the last sheet — fire cooking wait for any oven with sheets that hasn't started cooking
            if not remaining_sources:
                in_use_ovens = self.working_memory.query_equipment(
                    equipment_name=target_equipment_name,
                    state='IN_USE',
                )
                for oven in in_use_ovens:
                    oid = oven.attributes['equipment_id']
                    if oid not in ovens_with_cooking_started:
                        # Check this oven actually has contents
                        existing_contents = self.working_memory.query_facts(
                            fact_title='equipment_contents',
                            equipment_name=target_equipment_name,
                            equipment_id=oid,
                        )
                        if len(existing_contents) > 0:
                            self._fire_cooking_wait(duration, duration_unit, oid, target_equipment_name, oven_substeps[oid])
                            ovens_with_cooking_started.add(oid)
                            # Finalize this oven's CookStep
                            self._finalize_oven_cook_step(step, oid, target_equipment_name, oven_substeps)

        return (True, None)

    def _execute_equipment_removal_step(self, step, recipe):
        """Execute an equipment removal step: remove contents from source equipment to target surface."""
        source_equipment_name = step.source_equipment_name
        target_equipment_name = step.target_equipment_name

        # Find source equipment that has been cooking (via cooking_started facts)
        cooking_started_facts = self.working_memory.query_facts(
            fact_title='cooking_started',
        )
        if not cooking_started_facts:
            return (False, f"No cooking_started facts found for removal")

        # Resolve target surface equipment
        target_eq = self.working_memory.query_equipment(
            equipment_name=target_equipment_name,
            first=True,
        )
        if target_eq is None:
            return (False, f"No {target_equipment_name} equipment found")

        target_eq_id = target_eq.attributes['equipment_id']

        # Pre-assert item_transfer_target for DFS chaining
        # Look ahead in recipe for a TransferItem step to get the target
        item_transfer_target = None
        for future_step in recipe.steps:
            if isinstance(future_step, TransferItem) and future_step.source_equipment_name == 'BAKING_SHEET':
                item_transfer_target = future_step
                break

        if item_transfer_target:
            target_surface_eq = self.working_memory.query_equipment(
                equipment_name=item_transfer_target.target_equipment_name, first=True)
            if target_surface_eq:
                self.working_memory.add_fact(fact=Fact(
                    fact_title='item_transfer_target',
                    target_equipment_name=item_transfer_target.target_equipment_name,
                    target_equipment_id=target_surface_eq.attributes['equipment_id'],
                ), indent="  ")

        # Track which sources we've already added a wait step for
        sources_waited = set()

        for cooking_fact in cooking_started_facts:
            source_eq_name = cooking_fact.attributes['equipment_name']
            source_eq_id = cooking_fact.attributes['equipment_id']
            duration = cooking_fact.attributes['duration']
            duration_unit = cooking_fact.attributes['duration_unit']

            # Only process sources matching our step's source_equipment_name
            if source_eq_name != source_equipment_name:
                continue

            # Find equipment_contents on this source
            contents = self.working_memory.query_facts(
                fact_title='equipment_contents',
                equipment_name=source_equipment_name,
                equipment_id=source_eq_id,
            )

            if not contents:
                continue

            # Add a wait step (once per source)
            if source_eq_id not in sources_waited:
                self.plan.append(WaitStep(
                    description=f"Wait for {source_equipment_name} #{source_eq_id} cooking to complete",
                    equipment_name=source_equipment_name,
                    equipment_id=source_eq_id,
                    duration=duration,
                    duration_unit=duration_unit,
                ))
                sources_waited.add(source_eq_id)

                if self.verbose:
                    print(f"\n  Waiting for {source_equipment_name} #{source_eq_id} "
                          f"({duration} {duration_unit})")

            # Per-slot removal
            for content_fact in contents:
                slot_number = content_fact.attributes['slot_number']
                content_equipment_id = content_fact.attributes['content_equipment_id']
                content_type = content_fact.attributes['content_type']

                # Append per-slot TransferEquipment to plan BEFORE firing rule,
                # so DFS-chained TransferItem appears after it in the plan
                removal_step = TransferEquipment(
                    description=f"Remove {content_type} #{content_equipment_id} from {source_equipment_name} #{source_eq_id} to {target_equipment_name}",
                    source_equipment_name=source_equipment_name,
                    target_equipment_name=target_equipment_name,
                )
                self.plan.append(removal_step)

                # Assert equipment_removal_request trigger
                removal_request = Fact(
                    fact_title='equipment_removal_request',
                    source_equipment_name=source_equipment_name,
                    source_equipment_id=source_eq_id,
                    slot_number=slot_number,
                    target_equipment_name=target_equipment_name,
                    target_equipment_id=target_eq_id,
                )
                self.working_memory.add_fact(fact=removal_request, indent="    ")

                matches = self._find_matching_rules(removal_request)
                if not matches:
                    return (False, f"No rule matched for equipment_removal_request")

                best_rule, best_bindings = self._resolve_conflict(matches)
                derived = self._fire_rule(best_rule, best_bindings)

                if '?error' in best_bindings:
                    return (False, best_bindings['?error'])

                if self.verbose:
                    print(f"    [Rule fired] {best_rule.rule_name}")
                    if derived is not None:
                        print(f"    [Derived] {derived}")

        return (True, None)

    def _execute_item_transfer_step(self, step, recipe):
        """Execute an item transfer step: graceful no-op if DFS already handled everything."""
        source_equipment_name = step.source_equipment_name
        target_equipment_name = step.target_equipment_name

        # Resolve target surface equipment
        target_eq = self.working_memory.query_equipment(
            equipment_name=target_equipment_name,
            first=True,
        )
        if target_eq is None:
            return (False, f"No {target_equipment_name} equipment found")

        target_eq_id = target_eq.attributes['equipment_id']

        # Find source equipment on any intermediate surface (e.g., COUNTERTOP)
        # Look for equipment_contents facts where content_type matches the source_equipment_name
        intermediate_contents = self.working_memory.query_facts(
            fact_title='equipment_contents',
            content_type=source_equipment_name,
        )

        if not intermediate_contents:
            # DFS already handled everything — graceful no-op
            return (True, None)

        for content_fact in intermediate_contents:
            source_eq_id = content_fact.attributes['content_equipment_id']

            # Find what's on this source equipment (e.g., DOUGH_BALLS on BAKING_SHEET)
            source_contents = self.working_memory.query_facts(
                fact_title='equipment_contents',
                equipment_name=source_equipment_name,
                equipment_id=source_eq_id,
            )

            if not source_contents:
                continue

            for source_content in source_contents:
                content_type = source_content.attributes['content_type']

                # Assert item_transfer_request trigger
                transfer_request = Fact(
                    fact_title='item_transfer_request',
                    source_equipment_name=source_equipment_name,
                    source_equipment_id=source_eq_id,
                    target_equipment_name=target_equipment_name,
                    target_equipment_id=target_eq_id,
                    content_type=content_type,
                )
                self.working_memory.add_fact(fact=transfer_request, indent="    ")

                matches = self._find_matching_rules(transfer_request)
                if not matches:
                    return (False, f"No rule matched for item_transfer_request")

                best_rule, best_bindings = self._resolve_conflict(matches)
                derived = self._fire_rule(best_rule, best_bindings)

                if '?error' in best_bindings:
                    return (False, best_bindings['?error'])

                if self.verbose:
                    print(f"    [Rule fired] {best_rule.rule_name}")
                    if derived is not None:
                        print(f"    [Derived] {derived}")

                quantity = best_bindings.get('?quantity', 0)

                # Append per-sheet TransferItem to plan
                transfer_step = TransferItem(
                    description=f"Transfer {content_type} from {source_equipment_name} #{source_eq_id} to {target_equipment_name}",
                    source_equipment_name=source_equipment_name,
                    target_equipment_name=target_equipment_name,
                    scoop_size_amount=step.scoop_size_amount,
                    scoop_size_unit=step.scoop_size_unit,
                )
                self.plan.append(transfer_step)

        return (True, None)

    def _finalize_oven_cook_step(self, step, oven_id, target_equipment_name, oven_substeps):
        """Create a CookStep for a specific oven and append it to the plan."""
        cook = CookStep(
            description=f"{step.description} ({target_equipment_name} #{oven_id})",
            substeps=oven_substeps[oven_id],
        )
        self.plan.append(cook)

    def _fire_cooking_wait(self, duration, duration_unit, oven_id, target_equipment_name, substeps_list):
        """Assert a cooking_wait_request and fire the start_cooking rule for a given oven."""
        cooking_request = Fact(
            fact_title='cooking_wait_request',
            target_equipment_name=target_equipment_name,
            target_equipment_id=oven_id,
            duration=duration,
            duration_unit=duration_unit,
        )
        self.working_memory.add_fact(fact=cooking_request, indent="    ")

        matches = self._find_matching_rules(cooking_request)
        if matches:
            best_rule, best_bindings = self._resolve_conflict(matches)
            derived = self._fire_rule(best_rule, best_bindings, plan_override=substeps_list)

            if self.verbose:
                print(f"    [Rule fired] {best_rule.rule_name}")
                if derived is not None:
                    print(f"    [Derived] {derived}")

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

    def _fire_rule(self, rule, bindings, plan_override=None):
        """Fire a rule: run action_fn if present, then derive consequent if present.
        DFS: if the derived fact triggers further rules, fire them recursively."""
        if rule.action_fn:
            target_plan = plan_override if plan_override is not None else self.plan
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
                self._fire_rule(best_chain_rule, best_chain_bindings, plan_override=plan_override)

            return derived

        return None

    def _resolve_conflict(self, matches):
        """Pick the best (rule, bindings) from a list. Priority-based."""
        return max(matches, key=lambda x: x[0].priority)
