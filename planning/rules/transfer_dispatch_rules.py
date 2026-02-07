from classes.Rule import Rule
from classes.Fact import Fact
from classes.NegatedFact import NegatedFact
from planning.classes.TransferItem import TransferItem


def _initialize_transfer(*, bindings, wm, kb, plan):
    """Read recipe step, fire planning rule, store step info for T2."""
    engine = bindings['_engine']
    step_idx = bindings['?step_idx']
    step = engine.recipe.steps[step_idx]
    source_name = bindings['?source_equipment_name']
    source_id = bindings['?source_equipment_id']

    if engine.verbose:
        total_volume = bindings.get('?total_volume', 0)
        volume_unit = bindings.get('?volume_unit', '')
        print(f"\n  Processing {source_name} #{source_id} "
              f"(total_volume={total_volume:.2f} {volume_unit})")

    # Fire planning rule to derive transfer_plan
    planning_request = Fact(
        fact_title='transfer_planning_request',
        source_equipment_name=source_name,
        source_equipment_id=source_id,
        scoop_size_amount=step.scoop_size_amount,
        scoop_size_unit=step.scoop_size_unit,
        target_equipment_name=step.target_equipment_name,
    )
    wm.add_fact(fact=planning_request, indent="  ")
    _, derived = engine._forward_chain(planning_request)

    if engine.last_error:
        bindings['?error'] = engine.last_error
        return bindings

    if engine.verbose and derived is not None:
        print(f"  [Derived] {derived}")

    # Verify transfer_plan was derived
    transfer_plan = wm.query_facts(fact_title='transfer_plan', first=True)
    if transfer_plan is None:
        bindings['?error'] = "transfer_plan fact not found after planning rule"
        return bindings

    if engine.verbose:
        print(f"\n  Transfer plan: {transfer_plan.attributes['num_dough_balls']} dough balls, "
              f"{transfer_plan.attributes['capacity_per_sheet']}/sheet, "
              f"{transfer_plan.attributes['num_sheets_needed']} sheet(s) needed")

    # Store step info for T2 to use
    wm.add_fact(fact=Fact(
        fact_title='transfer_step_info',
        step_idx=step_idx,
        source_equipment_name=source_name,
        source_equipment_id=source_id,
        target_equipment_name=step.target_equipment_name,
        scoop_size_amount=step.scoop_size_amount,
        scoop_size_unit=step.scoop_size_unit,
    ), indent="  ")

    return bindings


def _allocate_next_sheet(*, bindings, wm, kb, plan):
    """Resolve one sheet, calculate quantity, assert transfer_request, append TransferItem to plan."""
    engine = bindings['_engine']
    step_idx = bindings['?step_idx']
    source_name = bindings['?source_equipment_name']
    source_id = bindings['?source_equipment_id']
    num_dough_balls = bindings['?num_dough_balls']
    capacity_per_sheet = bindings['?capacity_per_sheet']
    num_sheets_needed = bindings['?num_sheets_needed']
    target_equipment_name = bindings['?target_equipment_name']
    scoop_size_amount = bindings['?scoop_size_amount']
    scoop_size_unit = bindings['?scoop_size_unit']

    # Count existing transfer_completed facts for this source to know how many sheets done
    completed = wm.query_facts(
        fact_title='transfer_completed',
        source_equipment_name=source_name,
        source_equipment_id=source_id,
    )
    sheets_done = len(completed)

    if sheets_done >= num_sheets_needed:
        # All sheets done — assert completion marker
        wm.add_fact(fact=Fact(
            fact_title='all_sheets_transferred',
            step_idx=step_idx,
            source_equipment_id=source_id,
        ), indent="  ")
        bindings['?target_equipment_id'] = 0
        bindings['?quantity'] = 0
        return bindings

    # Resolve one target sheet
    equipment_need = {'equipment_name': target_equipment_name, 'required_count': 1}
    resolved_list = engine._resolve_equipment(equipment_need)
    if resolved_list is None:
        bindings['?error'] = f"Could not resolve {target_equipment_name} for sheet {sheets_done + 1}"
        return bindings

    target_eq = resolved_list[0]
    target_eq.attributes['state'] = 'IN_USE'
    target_eq_id = target_eq.attributes['equipment_id']

    # Calculate quantity for this sheet
    remaining = num_dough_balls - (sheets_done * capacity_per_sheet)
    quantity = min(remaining, capacity_per_sheet)

    if engine.verbose:
        print(f"\n  Sheet {sheets_done + 1}: {target_equipment_name} #{target_eq_id} — placing {quantity} dough balls")

    # Fire execute_transfer rule
    transfer_request = Fact(
        fact_title='transfer_request',
        source_equipment_name=source_name,
        source_equipment_id=source_id,
        target_equipment_name=target_equipment_name,
        target_equipment_id=target_eq_id,
        quantity=quantity,
        scoop_size_amount=scoop_size_amount,
        scoop_size_unit=scoop_size_unit,
    )
    wm.add_fact(fact=transfer_request, indent="    ")
    _, derived = engine._forward_chain(transfer_request)

    if engine.last_error:
        bindings['?error'] = engine.last_error
        return bindings

    if engine.verbose and derived is not None:
        print(f"    [Derived] {derived}")

    # Append TransferItem to plan
    sheet_step = TransferItem(
        description=f"Transfer {quantity} dough balls to {target_equipment_name} #{target_eq_id}",
        source_equipment_name=source_name,
        target_equipment_name=target_equipment_name,
        scoop_size_amount=scoop_size_amount,
        scoop_size_unit=scoop_size_unit,
    )
    plan.append(sheet_step)

    bindings['?target_equipment_id'] = target_eq_id
    bindings['?quantity'] = quantity
    return bindings


def _finalize_transfer_source(*, bindings, wm, kb, plan):
    """Mark source equipment as DIRTY after all sheets are transferred."""
    engine = bindings['_engine']
    source_name = bindings['?source_equipment_name']
    source_id = bindings['?source_equipment_id']

    source_eq = wm.query_equipment(
        equipment_name=source_name,
        equipment_id=source_id,
        first=True,
    )
    if source_eq:
        source_eq.attributes['state'] = 'DIRTY'
        if engine.verbose:
            print(f"\n  -> {source_name} #{source_id} is now DIRTY")

    return bindings


def get_transfer_dispatch_rules():
    rules = []

    # T1: Initialize transfer — for each mixed_contents source, plan the transfer
    rules.append(Rule(
        rule_name='initialize_transfer',
        priority=200,
        antecedents=[
            Fact(fact_title='step_request',
                 step_type='TRANSFER_ITEM',
                 step_idx='?step_idx'),
            Fact(fact_title='mixed_contents',
                 equipment_name='?source_equipment_name',
                 equipment_id='?source_equipment_id',
                 total_volume='?total_volume',
                 volume_unit='?volume_unit'),
            NegatedFact(fact_title='transfer_source_processed',
                        step_idx='?step_idx',
                        equipment_id='?source_equipment_id'),
        ],
        action_fn=_initialize_transfer,
        consequent=Fact(
            fact_title='transfer_source_started',
            step_idx='?step_idx',
            source_equipment_name='?source_equipment_name',
            source_equipment_id='?source_equipment_id',
        ),
    ))

    # T2: Allocate next sheet — resolve one sheet, transfer dough balls
    # Iterates via while-matches loop: after each transfer_completed,
    # re-evaluates and fires for the next sheet.
    rules.append(Rule(
        rule_name='allocate_next_sheet',
        priority=190,
        antecedents=[
            Fact(fact_title='transfer_source_started',
                 step_idx='?step_idx',
                 source_equipment_name='?source_equipment_name',
                 source_equipment_id='?source_equipment_id'),
            Fact(fact_title='transfer_plan',
                 num_dough_balls='?num_dough_balls',
                 capacity_per_sheet='?capacity_per_sheet',
                 num_sheets_needed='?num_sheets_needed'),
            Fact(fact_title='transfer_step_info',
                 step_idx='?step_idx',
                 target_equipment_name='?target_equipment_name',
                 scoop_size_amount='?scoop_size_amount',
                 scoop_size_unit='?scoop_size_unit'),
            NegatedFact(fact_title='all_sheets_transferred',
                        step_idx='?step_idx',
                        source_equipment_id='?source_equipment_id'),
        ],
        action_fn=_allocate_next_sheet,
        consequent=Fact(
            fact_title='sheet_allocated',
            step_idx='?step_idx',
            source_equipment_id='?source_equipment_id',
            target_equipment_id='?target_equipment_id',
            quantity='?quantity',
        ),
    ))

    # T3: Finalize transfer source — mark source equipment DIRTY
    rules.append(Rule(
        rule_name='finalize_transfer_source',
        priority=100,
        antecedents=[
            Fact(fact_title='transfer_source_started',
                 step_idx='?step_idx',
                 source_equipment_name='?source_equipment_name',
                 source_equipment_id='?source_equipment_id'),
            Fact(fact_title='all_sheets_transferred',
                 step_idx='?step_idx',
                 source_equipment_id='?source_equipment_id'),
        ],
        action_fn=_finalize_transfer_source,
        consequent=Fact(
            fact_title='transfer_source_processed',
            step_idx='?step_idx',
            equipment_id='?source_equipment_id',
        ),
    ))

    return rules
