from classes.Rule import Rule
from classes.Fact import Fact
from classes.NegatedFact import NegatedFact
from planning.classes.TransferEquipment import TransferEquipment
from planning.classes.CookStep import CookStep
from planning.classes.WaitStep import WaitStep


def _initialize_cook(*, bindings, wm, kb, plan):
    """C1: Extract templates, discover sources, preheat first oven, plan, seed pending_cook_placement facts."""
    engine = bindings['_engine']
    step_idx = bindings['?step_idx']
    step = engine.recipe.steps[step_idx]

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

    # Phase 0 — Discover sources
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

    # Phase 1 — Preheat (manually fire into oven_substeps, not main plan)
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

    # Initialize per-oven substep tracking on the engine
    if not hasattr(engine, '_cook_oven_substeps'):
        engine._cook_oven_substeps = {}
    engine._cook_oven_substeps[current_oven_id] = []

    derived = engine._fire_rule_dfs(best_rule, best_bindings_preheat,
                                     plan_override=engine._cook_oven_substeps[current_oven_id])

    if '?error' in best_bindings_preheat:
        bindings['?error'] = best_bindings_preheat['?error']
        return bindings

    if engine.verbose:
        print(f"  [Rule fired] {best_rule.rule_name}")
        if derived is not None:
            print(f"  [Derived] {derived}")

    # Phase 2 — Plan
    planning_request = Fact(
        fact_title='equipment_transfer_planning_request',
        source_equipment_name=source_equipment_name,
        target_equipment_name=target_equipment_name,
        num_source_items=len(source_ids),
    )
    wm.add_fact(fact=planning_request, indent="  ")

    _, derived = engine._forward_chain(planning_request)

    if engine.last_error:
        bindings['?error'] = engine.last_error
        return bindings

    if engine.verbose and derived is not None:
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

    # Phase 3 — Assert pending_cook_placement facts
    for seq, source_id in enumerate(source_ids):
        wm.add_fact(fact=Fact(
            fact_title='pending_cook_placement',
            step_idx=step_idx,
            seq=seq,
            source_equipment_name=source_equipment_name,
            source_equipment_id=source_id,
            target_equipment_name=target_equipment_name,
        ), indent="  ")

    # Store cook metadata for C2/C3 to use
    engine._cook_step_ref = step
    engine._cook_duration = duration
    engine._cook_duration_unit = duration_unit
    engine._cook_ovens_with_cooking_started = set()

    bindings['?source_equipment_name'] = source_equipment_name
    bindings['?target_equipment_name'] = target_equipment_name
    bindings['?duration'] = duration
    bindings['?duration_unit'] = duration_unit
    bindings['?num_sources'] = len(source_ids)
    return bindings


def _place_sheet_for_cooking(*, bindings, wm, kb, plan):
    """C2: Find rack, place sheet. If oven full, fire cooking wait and resolve new oven."""
    engine = bindings['_engine']
    step_idx = bindings['?step_idx']
    source_equipment_name = bindings['?source_equipment_name']
    source_equipment_id = bindings['?source_equipment_id']
    target_equipment_name = bindings['?target_equipment_name']

    duration = engine._cook_duration
    duration_unit = engine._cook_duration_unit
    step = engine._cook_step_ref
    oven_substeps = engine._cook_oven_substeps
    ovens_with_cooking_started = engine._cook_ovens_with_cooking_started

    # Find available rack
    rack_request = Fact(
        fact_title='available_rack_request',
        target_equipment_name=target_equipment_name,
    )
    wm.add_fact(fact=rack_request, indent="    ")

    _, rack_result = engine._forward_chain(rack_request)
    rack_bindings = engine._last_bindings

    if engine.verbose and rack_result is not None:
        print(f"    [Derived] {rack_result}")

    rack_found = rack_bindings.get('?rack_found', False)

    if not rack_found:
        # Fire cooking waits for full ovens
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

        if engine.verbose:
            print(f"\n  -> Resolved and preheated {target_equipment_name} #{new_oven_id}")

        # Retry rack request
        rack_request2 = Fact(
            fact_title='available_rack_request',
            target_equipment_name=target_equipment_name,
        )
        wm.add_fact(fact=rack_request2, indent="    ")

        _, rack_result2 = engine._forward_chain(rack_request2)
        rack_bindings2 = engine._last_bindings

        if engine.verbose and rack_result2 is not None:
            print(f"    [Derived] {rack_result2}")

        rack_found = rack_bindings2.get('?rack_found', False)
        if not rack_found:
            bindings['?error'] = f"Still no available rack after resolving {target_equipment_name}"
            return bindings

        rack_bindings = rack_bindings2

    oven_id = rack_bindings['?equipment_id']
    rack_num = rack_bindings['?rack_number']

    # Ensure oven_substeps dict has an entry for this oven
    if oven_id not in oven_substeps:
        oven_substeps[oven_id] = []

    if engine.verbose:
        print(f"\n  {target_equipment_name} #{oven_id}, Rack {rack_num}: "
              f"placing {source_equipment_name} #{source_equipment_id}")

    # Execute transfer
    transfer_request = Fact(
        fact_title='equipment_transfer_request',
        target_equipment_name=target_equipment_name,
        target_equipment_id=oven_id,
        slot_number=rack_num,
        source_equipment_name=source_equipment_name,
        source_equipment_id=source_equipment_id,
    )
    wm.add_fact(fact=transfer_request, indent="    ")

    _, derived = engine._forward_chain(transfer_request)

    if engine.last_error:
        bindings['?error'] = engine.last_error
        return bindings

    if engine.verbose and derived is not None:
        print(f"    [Derived] {derived}")

    rack_step = TransferEquipment(
        description=f"Place {source_equipment_name} #{source_equipment_id} on {target_equipment_name} #{oven_id} rack {rack_num}",
        source_equipment_name=source_equipment_name,
        target_equipment_name=target_equipment_name,
    )
    oven_substeps[oven_id].append(rack_step)

    return bindings


def _fire_remaining_cooking_waits(*, bindings, wm, kb, plan):
    """C3: Fire cooking waits for all ovens that have contents but haven't started cooking yet."""
    engine = bindings['_engine']
    step_idx = bindings['?step_idx']
    target_equipment_name = bindings['?target_equipment_name']

    duration = engine._cook_duration
    duration_unit = engine._cook_duration_unit
    step = engine._cook_step_ref
    oven_substeps = engine._cook_oven_substeps
    ovens_with_cooking_started = engine._cook_ovens_with_cooking_started

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

    # Clean up transient state
    if hasattr(engine, '_cook_oven_substeps'):
        del engine._cook_oven_substeps
    if hasattr(engine, '_cook_step_ref'):
        del engine._cook_step_ref
    if hasattr(engine, '_cook_duration'):
        del engine._cook_duration
    if hasattr(engine, '_cook_duration_unit'):
        del engine._cook_duration_unit
    if hasattr(engine, '_cook_ovens_with_cooking_started'):
        del engine._cook_ovens_with_cooking_started

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


def get_cook_dispatch_rules():
    rules = []

    # C1: Initialize cook step — discover, preheat, plan, seed pending_cook_placement facts
    rules.append(Rule(
        rule_name='initialize_cook',
        priority=200,
        antecedents=[
            Fact(fact_title='step_request',
                 step_type='COOK',
                 step_idx='?step_idx'),
        ],
        action_fn=_initialize_cook,
        consequent=Fact(
            fact_title='cook_initialized',
            step_idx='?step_idx',
            source_equipment_name='?source_equipment_name',
            target_equipment_name='?target_equipment_name',
            duration='?duration',
            duration_unit='?duration_unit',
            num_sources='?num_sources',
        ),
    ))

    # C2: Place next sheet for cooking — iterates via NegatedFact guard
    rules.append(Rule(
        rule_name='place_sheet_for_cooking',
        priority=190,
        antecedents=[
            Fact(fact_title='cook_initialized',
                 step_idx='?step_idx',
                 source_equipment_name='?source_equipment_name',
                 target_equipment_name='?target_equipment_name'),
            Fact(fact_title='pending_cook_placement',
                 step_idx='?step_idx',
                 source_equipment_name='?source_equipment_name',
                 source_equipment_id='?source_equipment_id',
                 target_equipment_name='?target_equipment_name'),
            NegatedFact(
                fact_title='cook_placement_completed',
                step_idx='?step_idx',
                source_equipment_id='?source_equipment_id',
            ),
        ],
        action_fn=_place_sheet_for_cooking,
        consequent=Fact(
            fact_title='cook_placement_completed',
            step_idx='?step_idx',
            source_equipment_id='?source_equipment_id',
        ),
    ))

    # C3: Fire remaining cooking waits — fires after all C2 instances complete (lower priority)
    rules.append(Rule(
        rule_name='fire_remaining_cooking_waits',
        priority=100,
        antecedents=[
            Fact(fact_title='cook_initialized',
                 step_idx='?step_idx',
                 target_equipment_name='?target_equipment_name'),
        ],
        action_fn=_fire_remaining_cooking_waits,
        consequent=Fact(
            fact_title='cook_completed',
            step_idx='?step_idx',
        ),
    ))

    return rules
