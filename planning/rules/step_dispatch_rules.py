from classes.Rule import Rule
from classes.Fact import Fact
from planning.classes.TransferItem import TransferItem
from planning.classes.TransferEquipment import TransferEquipment
from planning.classes.CookStep import CookStep
from planning.classes.WaitStep import WaitStep


# ---------------------------------------------------------------------------
# handle_mixing_step
# ---------------------------------------------------------------------------

def _handle_mixing_step(*, bindings, wm, kb, plan):
    engine = bindings['_engine']
    step = engine.recipe.steps[bindings['?step_idx']]
    eq_name = bindings['?equipment_name']
    eq_id = bindings['?equipment_id']
    eq_volume = bindings['?equipment_volume']
    eq_volume_unit = bindings['?equipment_volume_unit']

    ingredient_map = {ing.id: ing for ing in engine.recipe.ingredients}

    for substep_idx, substep in enumerate(step.substeps):
        if engine.verbose:
            print(f"\n  Substep {substep_idx + 1}: {substep.description}")

        for ingredient_id in substep.ingredient_ids:
            ingredient = ingredient_map.get(ingredient_id)
            if ingredient is None:
                bindings['?error'] = f"Ingredient id={ingredient_id} not found in recipe"
                return bindings

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
            wm.add_fact(fact=request_fact, indent="    ")

            derived = engine._forward_chain(request_fact)

            if engine.verbose:
                print(f"    [Rule fired] (ingredient addition)")
                if derived is not None:
                    print(f"    [Derived] {derived}")

            if engine.last_error:
                bindings['?error'] = engine.last_error
                return bindings

    # Assert mixing_completed -> DFS chains to summarize_mixed_contents rule
    for eq in engine._current_resolved_equipment:
        if eq.attributes.get('equipment_type') == 'CONTAINER':
            trigger = Fact(
                fact_title='mixing_completed',
                equipment_name=eq.attributes['equipment_name'],
                equipment_id=eq.attributes['equipment_id'],
            )
            wm.add_fact(fact=trigger, indent="  ")

            derived = engine._forward_chain(trigger)

            if engine.verbose:
                if derived is not None:
                    print(f"  [Derived] {derived}")

    plan.append(step)
    return bindings


# ---------------------------------------------------------------------------
# handle_transfer_item
# ---------------------------------------------------------------------------

def _handle_transfer_item(*, bindings, wm, kb, plan):
    engine = bindings['_engine']
    step = engine.recipe.steps[bindings['?step_idx']]

    sources = wm.query_facts(
        fact_title='mixed_contents',
        equipment_name=step.source_equipment_name,
    )
    if not sources:
        bindings['?error'] = f"No mixed_contents found for {step.source_equipment_name}"
        return bindings

    for source in sources:
        source_equipment_id = source.attributes['equipment_id']

        if engine.verbose:
            print(f"\n  Processing {step.source_equipment_name} #{source_equipment_id} "
                  f"(total_volume={source.attributes['total_volume']:.2f} {source.attributes['volume_unit']})")

        # Phase 1 - Fire planning rule
        planning_request = Fact(
            fact_title='transfer_planning_request',
            source_equipment_name=step.source_equipment_name,
            source_equipment_id=source_equipment_id,
            scoop_size_amount=step.scoop_size_amount,
            scoop_size_unit=step.scoop_size_unit,
            target_equipment_name=step.target_equipment_name,
        )
        wm.add_fact(fact=planning_request, indent="  ")

        derived = engine._forward_chain(planning_request)

        if engine.last_error:
            bindings['?error'] = engine.last_error
            return bindings

        if engine.verbose:
            if derived is not None:
                print(f"  [Derived] {derived}")

        # Read transfer_plan from WM
        transfer_plan = wm.query_facts(fact_title='transfer_plan', first=True)
        if transfer_plan is None:
            bindings['?error'] = "transfer_plan fact not found after planning rule"
            return bindings

        num_dough_balls = transfer_plan.attributes['num_dough_balls']
        capacity_per_sheet = transfer_plan.attributes['capacity_per_sheet']
        num_sheets_needed = transfer_plan.attributes['num_sheets_needed']

        if engine.verbose:
            print(f"\n  Transfer plan: {num_dough_balls} dough balls, {capacity_per_sheet}/sheet, {num_sheets_needed} sheet(s) needed")

        # Phase 2 - Loop per sheet
        remaining = num_dough_balls
        for sheet_idx in range(num_sheets_needed):
            equipment_need = {'equipment_name': step.target_equipment_name, 'required_count': 1}
            resolved_list = engine._resolve_equipment(equipment_need)
            if resolved_list is None:
                bindings['?error'] = f"Could not resolve {step.target_equipment_name} for sheet {sheet_idx + 1}"
                return bindings

            target_eq = resolved_list[0]
            target_eq.attributes['state'] = 'IN_USE'
            target_eq_id = target_eq.attributes['equipment_id']

            quantity = min(remaining, capacity_per_sheet)

            if engine.verbose:
                print(f"\n  Sheet {sheet_idx + 1}: {step.target_equipment_name} #{target_eq_id} — placing {quantity} dough balls")

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
            wm.add_fact(fact=transfer_request, indent="    ")

            derived = engine._forward_chain(transfer_request)

            if engine.last_error:
                bindings['?error'] = engine.last_error
                return bindings

            if engine.verbose:
                if derived is not None:
                    print(f"    [Derived] {derived}")

            remaining -= quantity

            sheet_step = TransferItem(
                description=f"Transfer {quantity} dough balls to {step.target_equipment_name} #{target_eq_id}",
                source_equipment_name=step.source_equipment_name,
                target_equipment_name=step.target_equipment_name,
                scoop_size_amount=step.scoop_size_amount,
                scoop_size_unit=step.scoop_size_unit,
            )
            plan.append(sheet_step)

        # Phase 3 - Mark source DIRTY
        source_eq = wm.query_equipment(
            equipment_name=step.source_equipment_name,
            equipment_id=source_equipment_id,
            first=True,
        )
        if source_eq:
            source_eq.attributes['state'] = 'DIRTY'
            if engine.verbose:
                print(f"\n  -> {step.source_equipment_name} #{source_equipment_id} is now DIRTY")

    return bindings


# ---------------------------------------------------------------------------
# handle_equipment_transfer
# ---------------------------------------------------------------------------

def _handle_equipment_transfer(*, bindings, wm, kb, plan):
    engine = bindings['_engine']
    step = engine.recipe.steps[bindings['?step_idx']]

    return _equipment_transfer_phases(
        engine=engine, bindings=bindings, wm=wm, kb=kb, plan=plan,
        source_equipment_name=step.source_equipment_name,
        target_equipment_name=step.target_equipment_name,
    )


def _equipment_transfer_phases(*, engine, bindings, wm, kb, plan,
                                source_equipment_name, target_equipment_name):
    """Shared equipment transfer logic used by both handle_equipment_transfer and handle_cook_step."""
    # Phase 0 - Discover sources
    source_contents = wm.query_facts(
        fact_title='equipment_contents',
        equipment_name=source_equipment_name,
        content_type='DOUGH_BALLS',
    )
    if not source_contents:
        bindings['?error'] = f"No {source_equipment_name} found with DOUGH_BALLS contents"
        return bindings

    source_ids = []
    for content in source_contents:
        sid = content.attributes['equipment_id']
        if sid not in source_ids:
            source_ids.append(sid)

    if engine.verbose:
        print(f"\n  Found {len(source_ids)} {source_equipment_name}(s) with dough balls: {source_ids}")

    # Phase 1 - Preheat
    preheat_request = Fact(
        fact_title='preheat_check_request',
        target_equipment_name=target_equipment_name,
    )
    wm.add_fact(fact=preheat_request, indent="  ")

    derived = engine._forward_chain(preheat_request)

    if engine.last_error:
        bindings['?error'] = engine.last_error
        return bindings

    if engine.verbose:
        if derived is not None:
            print(f"  [Derived] {derived}")

    # Phase 2 - Plan
    planning_request = Fact(
        fact_title='equipment_transfer_planning_request',
        source_equipment_name=source_equipment_name,
        target_equipment_name=target_equipment_name,
        num_source_items=len(source_ids),
    )
    wm.add_fact(fact=planning_request, indent="  ")

    derived = engine._forward_chain(planning_request)

    if engine.last_error:
        bindings['?error'] = engine.last_error
        return bindings

    if engine.verbose:
        if derived is not None:
            print(f"  [Derived] {derived}")

    transfer_plan = wm.query_facts(fact_title='equipment_transfer_plan', first=True)
    if transfer_plan is None:
        bindings['?error'] = "equipment_transfer_plan fact not found after planning rule"
        return bindings

    if engine.verbose:
        items_per_rack = transfer_plan.attributes['items_per_rack']
        capacity_per_target = transfer_plan.attributes['capacity_per_target']
        num_targets_needed = transfer_plan.attributes['num_targets_needed']
        print(f"\n  Transfer plan: {len(source_ids)} sheets, {items_per_rack}/rack, "
              f"{capacity_per_target}/oven, {num_targets_needed} oven(s) needed")

    # Phase 3 - Demand-driven loop
    remaining_sources = list(source_ids)

    while remaining_sources:
        rack_request = Fact(
            fact_title='available_rack_request',
            target_equipment_name=target_equipment_name,
        )
        wm.add_fact(fact=rack_request, indent="    ")

        rack_result = engine._forward_chain(rack_request)
        rack_bindings = engine._last_bindings

        if engine.verbose:
            if rack_result is not None:
                print(f"    [Derived] {rack_result}")

        rack_found = rack_bindings.get('?rack_found', False)

        if not rack_found:
            equipment_need = {'equipment_name': target_equipment_name, 'required_count': 1}
            resolved_list = engine._resolve_equipment(equipment_need)
            if resolved_list is None:
                bindings['?error'] = f"Could not resolve additional {target_equipment_name}"
                return bindings

            new_oven = resolved_list[0]
            new_oven.attributes['state'] = 'IN_USE'
            new_oven_id = new_oven.attributes['equipment_id']

            plan.append(WaitStep(
                description=f"Wait for {target_equipment_name} #{new_oven_id} to preheat",
                equipment_name=target_equipment_name,
                equipment_id=new_oven_id,
            ))

            if engine.verbose:
                print(f"\n  -> Resolved and preheated {target_equipment_name} #{new_oven_id}")

            rack_request2 = Fact(
                fact_title='available_rack_request',
                target_equipment_name=target_equipment_name,
            )
            wm.add_fact(fact=rack_request2, indent="    ")

            rack_result2 = engine._forward_chain(rack_request2)
            rack_bindings2 = engine._last_bindings

            if engine.verbose:
                if rack_result2 is not None:
                    print(f"    [Derived] {rack_result2}")

            rack_found = rack_bindings2.get('?rack_found', False)
            if not rack_found:
                bindings['?error'] = f"Still no available rack after resolving {target_equipment_name}"
                return bindings

            rack_bindings = rack_bindings2

        oven_id = rack_bindings['?equipment_id']
        rack_num = rack_bindings['?rack_number']
        source_id = remaining_sources.pop(0)

        if engine.verbose:
            print(f"\n  {target_equipment_name} #{oven_id}, Rack {rack_num}: "
                  f"placing {source_equipment_name} #{source_id}")

        transfer_request = Fact(
            fact_title='equipment_transfer_request',
            target_equipment_name=target_equipment_name,
            target_equipment_id=oven_id,
            slot_number=rack_num,
            source_equipment_name=source_equipment_name,
            source_equipment_id=source_id,
        )
        wm.add_fact(fact=transfer_request, indent="    ")

        derived = engine._forward_chain(transfer_request)

        if engine.last_error:
            bindings['?error'] = engine.last_error
            return bindings

        if engine.verbose:
            if derived is not None:
                print(f"    [Derived] {derived}")

        rack_step = TransferEquipment(
            description=f"Place {source_equipment_name} #{source_id} on {target_equipment_name} #{oven_id} rack {rack_num}",
            source_equipment_name=source_equipment_name,
            target_equipment_name=target_equipment_name,
        )
        plan.append(rack_step)

    return bindings


# ---------------------------------------------------------------------------
# handle_cook_step
# ---------------------------------------------------------------------------

def _handle_cook_step(*, bindings, wm, kb, plan):
    engine = bindings['_engine']
    step = engine.recipe.steps[bindings['?step_idx']]

    transfer_template = None
    wait_template = None
    for sub in step.substeps:
        if isinstance(sub, TransferEquipment):
            transfer_template = sub
        elif isinstance(sub, WaitStep):
            wait_template = sub

    if transfer_template is None:
        bindings['?error'] = "CookStep has no TransferEquipment substep template"
        return bindings
    if wait_template is None:
        bindings['?error'] = "CookStep has no WaitStep substep template"
        return bindings

    duration = wait_template.duration
    duration_unit = wait_template.duration_unit
    source_equipment_name = transfer_template.source_equipment_name
    target_equipment_name = transfer_template.target_equipment_name

    oven_substeps = {}
    current_oven_id = None

    # Phase 0 - Discover sources
    source_contents = wm.query_facts(
        fact_title='equipment_contents',
        equipment_name=source_equipment_name,
        content_type='DOUGH_BALLS',
    )
    if not source_contents:
        bindings['?error'] = f"No {source_equipment_name} found with DOUGH_BALLS contents"
        return bindings

    source_ids = []
    for content in source_contents:
        sid = content.attributes['equipment_id']
        if sid not in source_ids:
            source_ids.append(sid)

    if engine.verbose:
        print(f"\n  Found {len(source_ids)} {source_equipment_name}(s) with dough balls: {source_ids}")

    # Phase 1 - Preheat
    preheat_request = Fact(
        fact_title='preheat_check_request',
        target_equipment_name=target_equipment_name,
    )
    wm.add_fact(fact=preheat_request, indent="  ")

    preheat_matches = engine._find_matching_rules(preheat_request)
    if not preheat_matches:
        bindings['?error'] = "No rule matched for preheat_check_request"
        return bindings

    best_rule, best_bindings_preheat = engine._resolve_conflict(preheat_matches)

    current_oven_id = best_bindings_preheat.get('?equipment_id')
    if current_oven_id is None:
        first_oven = wm.query_equipment(
            equipment_name=target_equipment_name,
            state='IN_USE',
            first=True,
        )
        if first_oven:
            current_oven_id = first_oven.attributes['equipment_id']
        else:
            bindings['?error'] = "No IN_USE oven found for preheat"
            return bindings

    oven_substeps[current_oven_id] = []
    derived = engine._fire_rule_dfs(best_rule, best_bindings_preheat, plan_override=oven_substeps[current_oven_id])

    if '?error' in best_bindings_preheat:
        bindings['?error'] = best_bindings_preheat['?error']
        return bindings

    if engine.verbose:
        print(f"  [Rule fired] {best_rule.rule_name}")
        if derived is not None:
            print(f"  [Derived] {derived}")

    # Phase 2 - Plan
    planning_request = Fact(
        fact_title='equipment_transfer_planning_request',
        source_equipment_name=source_equipment_name,
        target_equipment_name=target_equipment_name,
        num_source_items=len(source_ids),
    )
    wm.add_fact(fact=planning_request, indent="  ")

    derived = engine._forward_chain(planning_request)

    if engine.last_error:
        bindings['?error'] = engine.last_error
        return bindings

    if engine.verbose:
        if derived is not None:
            print(f"  [Derived] {derived}")

    transfer_plan = wm.query_facts(fact_title='equipment_transfer_plan', first=True)
    if transfer_plan is None:
        bindings['?error'] = "equipment_transfer_plan fact not found after planning rule"
        return bindings

    if engine.verbose:
        items_per_rack = transfer_plan.attributes['items_per_rack']
        capacity_per_target = transfer_plan.attributes['capacity_per_target']
        num_targets_needed = transfer_plan.attributes['num_targets_needed']
        print(f"\n  Transfer plan: {len(source_ids)} sheets, {items_per_rack}/rack, "
              f"{capacity_per_target}/oven, {num_targets_needed} oven(s) needed")

    # Phase 3 - Demand-driven loop with cooking wait tracking
    remaining_sources = list(source_ids)
    ovens_with_cooking_started = set()

    while remaining_sources:
        rack_request = Fact(
            fact_title='available_rack_request',
            target_equipment_name=target_equipment_name,
        )
        wm.add_fact(fact=rack_request, indent="    ")

        rack_result = engine._forward_chain(rack_request)
        rack_bindings = engine._last_bindings

        if engine.verbose:
            if rack_result is not None:
                print(f"    [Derived] {rack_result}")

        rack_found = rack_bindings.get('?rack_found', False)

        if not rack_found:
            # Fire cooking wait for full ovens
            in_use_ovens = wm.query_equipment(
                equipment_name=target_equipment_name,
                state='IN_USE',
            )
            for oven in in_use_ovens:
                oven_id = oven.attributes['equipment_id']
                if oven_id not in ovens_with_cooking_started:
                    num_racks = oven.attributes.get('number_of_racks', 1)
                    existing_contents = wm.query_facts(
                        fact_title='equipment_contents',
                        equipment_name=target_equipment_name,
                        equipment_id=oven_id,
                    )
                    if len(existing_contents) >= num_racks:
                        _fire_cooking_wait(engine, duration, duration_unit, oven_id,
                                          target_equipment_name, oven_substeps[oven_id])
                        ovens_with_cooking_started.add(oven_id)
                        _finalize_oven_cook_step(step, oven_id, target_equipment_name,
                                                oven_substeps, plan)

            # Resolve new oven
            equipment_need = {'equipment_name': target_equipment_name, 'required_count': 1}
            resolved_list = engine._resolve_equipment(equipment_need)
            if resolved_list is None:
                bindings['?error'] = f"Could not resolve additional {target_equipment_name}"
                return bindings

            new_oven = resolved_list[0]
            new_oven.attributes['state'] = 'IN_USE'
            new_oven_id = new_oven.attributes['equipment_id']

            oven_substeps[new_oven_id] = []
            oven_substeps[new_oven_id].append(WaitStep(
                description=f"Wait for {target_equipment_name} #{new_oven_id} to preheat",
                equipment_name=target_equipment_name,
                equipment_id=new_oven_id,
            ))
            current_oven_id = new_oven_id

            if engine.verbose:
                print(f"\n  -> Resolved and preheated {target_equipment_name} #{new_oven_id}")

            rack_request2 = Fact(
                fact_title='available_rack_request',
                target_equipment_name=target_equipment_name,
            )
            wm.add_fact(fact=rack_request2, indent="    ")

            rack_result2 = engine._forward_chain(rack_request2)
            rack_bindings2 = engine._last_bindings

            if engine.verbose:
                if rack_result2 is not None:
                    print(f"    [Derived] {rack_result2}")

            rack_found = rack_bindings2.get('?rack_found', False)
            if not rack_found:
                bindings['?error'] = f"Still no available rack after resolving {target_equipment_name}"
                return bindings

            rack_bindings = rack_bindings2

        oven_id = rack_bindings['?equipment_id']
        rack_num = rack_bindings['?rack_number']
        source_id = remaining_sources.pop(0)

        if engine.verbose:
            print(f"\n  {target_equipment_name} #{oven_id}, Rack {rack_num}: "
                  f"placing {source_equipment_name} #{source_id}")

        transfer_request = Fact(
            fact_title='equipment_transfer_request',
            target_equipment_name=target_equipment_name,
            target_equipment_id=oven_id,
            slot_number=rack_num,
            source_equipment_name=source_equipment_name,
            source_equipment_id=source_id,
        )
        wm.add_fact(fact=transfer_request, indent="    ")

        derived = engine._forward_chain(transfer_request)

        if engine.last_error:
            bindings['?error'] = engine.last_error
            return bindings

        if engine.verbose:
            if derived is not None:
                print(f"    [Derived] {derived}")

        rack_step = TransferEquipment(
            description=f"Place {source_equipment_name} #{source_id} on {target_equipment_name} #{oven_id} rack {rack_num}",
            source_equipment_name=source_equipment_name,
            target_equipment_name=target_equipment_name,
        )
        oven_substeps[oven_id].append(rack_step)

        # Last sheet: fire cooking wait for all ovens with contents that haven't started
        if not remaining_sources:
            in_use_ovens = wm.query_equipment(
                equipment_name=target_equipment_name,
                state='IN_USE',
            )
            for oven in in_use_ovens:
                oid = oven.attributes['equipment_id']
                if oid not in ovens_with_cooking_started:
                    existing_contents = wm.query_facts(
                        fact_title='equipment_contents',
                        equipment_name=target_equipment_name,
                        equipment_id=oid,
                    )
                    if len(existing_contents) > 0:
                        _fire_cooking_wait(engine, duration, duration_unit, oid,
                                          target_equipment_name, oven_substeps[oid])
                        ovens_with_cooking_started.add(oid)
                        _finalize_oven_cook_step(step, oid, target_equipment_name,
                                                oven_substeps, plan)

    return bindings


def _fire_cooking_wait(engine, duration, duration_unit, oven_id, target_equipment_name, substeps_list):
    cooking_request = Fact(
        fact_title='cooking_wait_request',
        target_equipment_name=target_equipment_name,
        target_equipment_id=oven_id,
        duration=duration,
        duration_unit=duration_unit,
    )
    engine.working_memory.add_fact(fact=cooking_request, indent="    ")

    matches = engine._find_matching_rules(cooking_request)
    if matches:
        best_rule, best_bindings = engine._resolve_conflict(matches)
        derived = engine._fire_rule_dfs(best_rule, best_bindings, plan_override=substeps_list)

        if engine.verbose:
            print(f"    [Rule fired] {best_rule.rule_name}")
            if derived is not None:
                print(f"    [Derived] {derived}")


def _finalize_oven_cook_step(step, oven_id, target_equipment_name, oven_substeps, plan):
    cook = CookStep(
        description=f"{step.description} ({target_equipment_name} #{oven_id})",
        substeps=oven_substeps[oven_id],
    )
    plan.append(cook)


# ---------------------------------------------------------------------------
# handle_equipment_removal
# ---------------------------------------------------------------------------

def _handle_equipment_removal(*, bindings, wm, kb, plan):
    engine = bindings['_engine']
    step = engine.recipe.steps[bindings['?step_idx']]
    recipe = engine.recipe

    source_equipment_name = step.source_equipment_name
    target_equipment_name = step.target_equipment_name

    cooking_started_facts = wm.query_facts(fact_title='cooking_started')
    if not cooking_started_facts:
        bindings['?error'] = "No cooking_started facts found for removal"
        return bindings

    target_eq = wm.query_equipment(
        equipment_name=target_equipment_name,
        first=True,
    )
    if target_eq is None:
        bindings['?error'] = f"No {target_equipment_name} equipment found"
        return bindings

    target_eq_id = target_eq.attributes['equipment_id']

    # Pre-assert item_transfer_target for DFS chaining
    item_transfer_target = None
    for future_step in recipe.steps:
        if isinstance(future_step, TransferItem) and future_step.source_equipment_name == 'BAKING_SHEET':
            item_transfer_target = future_step
            break

    if item_transfer_target:
        target_surface_eq = wm.query_equipment(
            equipment_name=item_transfer_target.target_equipment_name, first=True)
        if target_surface_eq:
            wm.add_fact(fact=Fact(
                fact_title='item_transfer_target',
                target_equipment_name=item_transfer_target.target_equipment_name,
                target_equipment_id=target_surface_eq.attributes['equipment_id'],
            ), indent="  ")

    sources_waited = set()

    for cooking_fact in cooking_started_facts:
        source_eq_name = cooking_fact.attributes['equipment_name']
        source_eq_id = cooking_fact.attributes['equipment_id']
        duration = cooking_fact.attributes['duration']
        duration_unit = cooking_fact.attributes['duration_unit']

        if source_eq_name != source_equipment_name:
            continue

        contents = wm.query_facts(
            fact_title='equipment_contents',
            equipment_name=source_equipment_name,
            equipment_id=source_eq_id,
        )

        if not contents:
            continue

        if source_eq_id not in sources_waited:
            plan.append(WaitStep(
                description=f"Wait for {source_equipment_name} #{source_eq_id} cooking to complete",
                equipment_name=source_equipment_name,
                equipment_id=source_eq_id,
                duration=duration,
                duration_unit=duration_unit,
            ))
            sources_waited.add(source_eq_id)

            if engine.verbose:
                print(f"\n  Waiting for {source_equipment_name} #{source_eq_id} "
                      f"({duration} {duration_unit})")

        for content_fact in contents:
            slot_number = content_fact.attributes['slot_number']
            content_equipment_id = content_fact.attributes['content_equipment_id']
            content_type = content_fact.attributes['content_type']

            removal_step = TransferEquipment(
                description=f"Remove {content_type} #{content_equipment_id} from {source_equipment_name} #{source_eq_id} to {target_equipment_name}",
                source_equipment_name=source_equipment_name,
                target_equipment_name=target_equipment_name,
            )
            plan.append(removal_step)

            removal_request = Fact(
                fact_title='equipment_removal_request',
                source_equipment_name=source_equipment_name,
                source_equipment_id=source_eq_id,
                slot_number=slot_number,
                target_equipment_name=target_equipment_name,
                target_equipment_id=target_eq_id,
            )
            wm.add_fact(fact=removal_request, indent="    ")

            derived = engine._forward_chain(removal_request)

            if engine.last_error:
                bindings['?error'] = engine.last_error
                return bindings

            if engine.verbose:
                if derived is not None:
                    print(f"    [Derived] {derived}")

    return bindings


# ---------------------------------------------------------------------------
# handle_item_transfer_to_surface
# ---------------------------------------------------------------------------

def _handle_item_transfer_to_surface(*, bindings, wm, kb, plan):
    engine = bindings['_engine']
    step = engine.recipe.steps[bindings['?step_idx']]

    source_equipment_name = step.source_equipment_name
    target_equipment_name = step.target_equipment_name

    target_eq = wm.query_equipment(
        equipment_name=target_equipment_name,
        first=True,
    )
    if target_eq is None:
        bindings['?error'] = f"No {target_equipment_name} equipment found"
        return bindings

    target_eq_id = target_eq.attributes['equipment_id']

    intermediate_contents = wm.query_facts(
        fact_title='equipment_contents',
        content_type=source_equipment_name,
    )

    if not intermediate_contents:
        # DFS already handled everything - graceful no-op
        return bindings

    for content_fact in intermediate_contents:
        source_eq_id = content_fact.attributes['content_equipment_id']

        source_contents = wm.query_facts(
            fact_title='equipment_contents',
            equipment_name=source_equipment_name,
            equipment_id=source_eq_id,
        )

        if not source_contents:
            continue

        for source_content in source_contents:
            content_type = source_content.attributes['content_type']

            transfer_request = Fact(
                fact_title='item_transfer_request',
                source_equipment_name=source_equipment_name,
                source_equipment_id=source_eq_id,
                target_equipment_name=target_equipment_name,
                target_equipment_id=target_eq_id,
                content_type=content_type,
            )
            wm.add_fact(fact=transfer_request, indent="    ")

            derived = engine._forward_chain(transfer_request)

            if engine.last_error:
                bindings['?error'] = engine.last_error
                return bindings

            if engine.verbose:
                if derived is not None:
                    print(f"    [Derived] {derived}")

            transfer_step = TransferItem(
                description=f"Transfer {content_type} from {source_equipment_name} #{source_eq_id} to {target_equipment_name}",
                source_equipment_name=source_equipment_name,
                target_equipment_name=target_equipment_name,
                scoop_size_amount=step.scoop_size_amount,
                scoop_size_unit=step.scoop_size_unit,
            )
            plan.append(transfer_step)

    return bindings


# ---------------------------------------------------------------------------
# Rule definitions
# ---------------------------------------------------------------------------

def get_step_dispatch_rules():
    rules = []

    rules.append(Rule(
        rule_name='handle_mixing_step',
        priority=200,
        antecedents=[
            Fact(fact_title='step_request',
                 step_type='MIXING',
                 step_idx='?step_idx',
                 equipment_name='?equipment_name',
                 equipment_id='?equipment_id',
                 equipment_volume='?equipment_volume',
                 equipment_volume_unit='?equipment_volume_unit'),
        ],
        action_fn=_handle_mixing_step,
        consequent=None,
    ))

    rules.append(Rule(
        rule_name='handle_transfer_item',
        priority=200,
        antecedents=[
            Fact(fact_title='step_request',
                 step_type='TRANSFER_ITEM',
                 step_idx='?step_idx'),
        ],
        action_fn=_handle_transfer_item,
        consequent=None,
    ))

    rules.append(Rule(
        rule_name='handle_equipment_transfer',
        priority=200,
        antecedents=[
            Fact(fact_title='step_request',
                 step_type='TRANSFER_EQUIPMENT',
                 step_idx='?step_idx'),
        ],
        action_fn=_handle_equipment_transfer,
        consequent=None,
    ))

    rules.append(Rule(
        rule_name='handle_cook_step',
        priority=200,
        antecedents=[
            Fact(fact_title='step_request',
                 step_type='COOK',
                 step_idx='?step_idx'),
        ],
        action_fn=_handle_cook_step,
        consequent=None,
    ))

    rules.append(Rule(
        rule_name='handle_equipment_removal',
        priority=200,
        antecedents=[
            Fact(fact_title='step_request',
                 step_type='EQUIPMENT_REMOVAL',
                 step_idx='?step_idx'),
        ],
        action_fn=_handle_equipment_removal,
        consequent=None,
    ))

    rules.append(Rule(
        rule_name='handle_item_transfer_to_surface',
        priority=200,
        antecedents=[
            Fact(fact_title='step_request',
                 step_type='ITEM_TRANSFER_TO_SURFACE',
                 step_idx='?step_idx'),
        ],
        action_fn=_handle_item_transfer_to_surface,
        consequent=None,
    ))

    return rules
