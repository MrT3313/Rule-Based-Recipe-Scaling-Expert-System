from classes.Rule import Rule
from classes.Fact import Fact
from classes.NegatedFact import NegatedFact
from planning.classes.TransferEquipment import TransferEquipment
from planning.classes.WaitStep import WaitStep


def _initialize_equipment_transfer(*, bindings, wm, kb, plan):
    """ET1: Discover sources, preheat, plan, and assert pending_placement facts."""
    engine = bindings['_engine']
    step = engine.recipe.steps[bindings['?step_idx']]

    source_equipment_name = step.source_equipment_name
    target_equipment_name = step.target_equipment_name

    # Phase 0 — Discover sources with DOUGH_BALLS contents
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

    # Phase 1 — Preheat
    preheat_request = Fact(
        fact_title='preheat_check_request',
        target_equipment_name=target_equipment_name,
    )
    wm.add_fact(fact=preheat_request, indent="  ")

    _, derived = engine._forward_chain(trigger_fact=preheat_request)

    if engine.last_error:
        bindings['?error'] = engine.last_error
        return bindings

    if engine.verbose and derived is not None:
        print(f"  [Derived] {derived}")

    # Phase 2 — Plan
    planning_request = Fact(
        fact_title='equipment_transfer_planning_request',
        source_equipment_name=source_equipment_name,
        target_equipment_name=target_equipment_name,
        num_source_items=len(source_ids),
    )
    wm.add_fact(fact=planning_request, indent="  ")

    _, derived = engine._forward_chain(trigger_fact=planning_request)

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

    # Phase 3 — Assert pending_placement facts for each source
    step_idx = bindings['?step_idx']
    for seq, source_id in enumerate(source_ids):
        wm.add_fact(fact=Fact(
            fact_title='pending_placement',
            step_idx=step_idx,
            seq=seq,
            source_equipment_name=source_equipment_name,
            source_equipment_id=source_id,
            target_equipment_name=target_equipment_name,
        ), indent="  ")

    bindings['?source_equipment_name'] = source_equipment_name
    bindings['?target_equipment_name'] = target_equipment_name
    return bindings


def _place_next_sheet(*, bindings, wm, kb, plan):
    """ET2: Find a rack, place one sheet. If no rack, resolve new oven."""
    engine = bindings['_engine']
    step_idx = bindings['?step_idx']
    source_equipment_name = bindings['?source_equipment_name']
    source_equipment_id = bindings['?source_equipment_id']
    target_equipment_name = bindings['?target_equipment_name']

    # Find available rack
    rack_request = Fact(
        fact_title='available_rack_request',
        target_equipment_name=target_equipment_name,
    )
    wm.add_fact(fact=rack_request, indent="    ")

    _, rack_result = engine._forward_chain(trigger_fact=rack_request)
    rack_bindings = engine._last_bindings

    if engine.verbose and rack_result is not None:
        print(f"    [Derived] {rack_result}")

    rack_found = rack_bindings.get('?rack_found', False)

    if not rack_found:
        # Resolve new oven
        equipment_need = {'equipment_name': target_equipment_name, 'required_count': 1}
        resolved_list = engine._resolve_equipment(equipment_need=equipment_need)
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

        # Retry rack request
        rack_request2 = Fact(
            fact_title='available_rack_request',
            target_equipment_name=target_equipment_name,
        )
        wm.add_fact(fact=rack_request2, indent="    ")

        _, rack_result2 = engine._forward_chain(trigger_fact=rack_request2)
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

    _, derived = engine._forward_chain(trigger_fact=transfer_request)

    if engine.last_error:
        bindings['?error'] = engine.last_error
        return bindings

    if engine.verbose and derived is not None:
        print(f"    [Derived] {derived}")

    # Append plan step
    rack_step = TransferEquipment(
        description=f"Place {source_equipment_name} #{source_equipment_id} on {target_equipment_name} #{oven_id} rack {rack_num}",
        source_equipment_name=source_equipment_name,
        target_equipment_name=target_equipment_name,
    )
    plan.append(rack_step)

    return bindings


def get_equipment_transfer_dispatch_rules():
    rules = []

    # ET1: Initialize equipment transfer — discover, preheat, plan, seed pending_placement facts
    rules.append(Rule(
        rule_name='initialize_equipment_transfer',
        priority=200,
        antecedents=[
            Fact(fact_title='step_request',
                 step_type='TRANSFER_EQUIPMENT',
                 step_idx='?step_idx'),
        ],
        action_fn=_initialize_equipment_transfer,
        consequent=Fact(
            fact_title='equipment_transfer_initialized',
            step_idx='?step_idx',
            source_equipment_name='?source_equipment_name',
            target_equipment_name='?target_equipment_name',
        ),
    ))

    # ET2: Place next sheet — iterates via NegatedFact guard
    rules.append(Rule(
        rule_name='place_next_sheet',
        priority=190,
        antecedents=[
            Fact(fact_title='equipment_transfer_initialized',
                 step_idx='?step_idx',
                 source_equipment_name='?source_equipment_name',
                 target_equipment_name='?target_equipment_name'),
            Fact(fact_title='pending_placement',
                 step_idx='?step_idx',
                 source_equipment_name='?source_equipment_name',
                 source_equipment_id='?source_equipment_id',
                 target_equipment_name='?target_equipment_name'),
            NegatedFact(
                fact_title='placement_completed',
                step_idx='?step_idx',
                source_equipment_id='?source_equipment_id',
            ),
        ],
        action_fn=_place_next_sheet,
        consequent=Fact(
            fact_title='placement_completed',
            step_idx='?step_idx',
            source_equipment_id='?source_equipment_id',
        ),
    ))

    # ET3: Complete equipment transfer — fires after all ET2 instances complete (lower priority)
    rules.append(Rule(
        rule_name='complete_equipment_transfer',
        priority=100,
        antecedents=[
            Fact(fact_title='equipment_transfer_initialized',
                 step_idx='?step_idx'),
        ],
        action_fn=None,
        consequent=Fact(
            fact_title='equipment_transfer_completed',
            step_idx='?step_idx',
        ),
    ))

    return rules
