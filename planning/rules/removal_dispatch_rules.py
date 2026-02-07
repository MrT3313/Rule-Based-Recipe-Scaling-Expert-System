from classes.Rule import Rule
from classes.Fact import Fact
from classes.NegatedFact import NegatedFact
from planning.classes.TransferEquipment import TransferEquipment
from planning.classes.TransferItem import TransferItem
from planning.classes.WaitStep import WaitStep


def _initialize_removal(*, bindings, wm, kb, plan):
    """Read recipe step, pre-assert item_transfer_target for DFS chaining."""
    engine = bindings['_engine']
    step_idx = bindings['?step_idx']
    step = engine.recipe.steps[step_idx]

    source_equipment_name = step.source_equipment_name
    target_equipment_name = step.target_equipment_name

    # Verify cooking_started facts exist
    cooking_started_facts = wm.query_facts(fact_title='cooking_started')
    if not cooking_started_facts:
        bindings['?error'] = "No cooking_started facts found for removal"
        return bindings

    # Verify target equipment exists
    target_eq = wm.query_equipment(equipment_name=target_equipment_name, first=True)
    if target_eq is None:
        bindings['?error'] = f"No {target_equipment_name} equipment found"
        return bindings

    target_eq_id = target_eq.attributes['equipment_id']

    # Pre-assert item_transfer_target for DFS chaining
    for future_step in engine.recipe.steps:
        if isinstance(future_step, TransferItem) and future_step.source_equipment_name == 'BAKING_SHEET':
            target_surface_eq = wm.query_equipment(
                equipment_name=future_step.target_equipment_name, first=True)
            if target_surface_eq:
                wm.add_fact(fact=Fact(
                    fact_title='item_transfer_target',
                    target_equipment_name=future_step.target_equipment_name,
                    target_equipment_id=target_surface_eq.attributes['equipment_id'],
                ), indent="  ")
            break

    bindings['?source_equipment_name'] = source_equipment_name
    bindings['?target_equipment_name'] = target_equipment_name
    bindings['?target_equipment_id'] = target_eq_id
    return bindings


def _process_oven_slot_removal(*, bindings, wm, kb, plan):
    """For one oven slot: append WaitStep (once per oven), append TransferEquipment,
    forward-chain equipment_removal_request."""
    engine = bindings['_engine']
    source_equipment_name = bindings['?source_equipment_name']
    source_equipment_id = bindings['?source_eq_id']
    target_equipment_name = bindings['?target_equipment_name']
    target_equipment_id = bindings['?target_equipment_id']
    slot_number = bindings['?slot_number']
    duration = bindings['?duration']
    duration_unit = bindings['?duration_unit']

    # Append WaitStep once per oven (check if we already waited for this oven)
    wait_exists = wm.query_facts(
        fact_title='oven_wait_completed',
        equipment_id=source_equipment_id,
        first=True,
    )
    if not wait_exists:
        plan.append(WaitStep(
            description=f"Wait for {source_equipment_name} #{source_equipment_id} cooking to complete",
            equipment_name=source_equipment_name,
            equipment_id=source_equipment_id,
            duration=duration,
            duration_unit=duration_unit,
        ))
        wm.add_fact(fact=Fact(
            fact_title='oven_wait_completed',
            equipment_id=source_equipment_id,
        ), indent="  ")

        if engine.verbose:
            print(f"\n  Waiting for {source_equipment_name} #{source_equipment_id} "
                  f"({duration} {duration_unit})")

    # Get content info for the removal step description
    contents_fact = wm.query_facts(
        fact_title='equipment_contents',
        equipment_name=source_equipment_name,
        equipment_id=source_equipment_id,
        slot_number=slot_number,
        first=True,
    )
    if contents_fact is None:
        bindings['?error'] = (
            f"No equipment_contents found for {source_equipment_name} "
            f"#{source_equipment_id} slot {slot_number}"
        )
        return bindings

    content_equipment_id = contents_fact.attributes['content_equipment_id']
    content_type = contents_fact.attributes['content_type']

    # Append TransferEquipment step to plan
    removal_step = TransferEquipment(
        description=f"Remove {content_type} #{content_equipment_id} from {source_equipment_name} #{source_equipment_id} to {target_equipment_name}",
        source_equipment_name=source_equipment_name,
        target_equipment_name=target_equipment_name,
    )
    plan.append(removal_step)

    # Fire removal rule via forward-chain
    removal_request = Fact(
        fact_title='equipment_removal_request',
        source_equipment_name=source_equipment_name,
        source_equipment_id=source_equipment_id,
        slot_number=slot_number,
        target_equipment_name=target_equipment_name,
        target_equipment_id=target_equipment_id,
    )
    wm.add_fact(fact=removal_request, indent="    ")
    _, derived = engine._forward_chain(removal_request)

    if engine.last_error:
        bindings['?error'] = engine.last_error
        return bindings

    if engine.verbose and derived is not None:
        print(f"    [Derived] {derived}")

    return bindings


def get_removal_dispatch_rules():
    rules = []

    # R1: Initialize removal — read recipe, pre-assert item_transfer_target
    rules.append(Rule(
        rule_name='initialize_removal',
        priority=200,
        antecedents=[
            Fact(fact_title='step_request',
                 step_type='EQUIPMENT_REMOVAL',
                 step_idx='?step_idx'),
        ],
        action_fn=_initialize_removal,
        consequent=Fact(
            fact_title='removal_initialized',
            step_idx='?step_idx',
            source_equipment_name='?source_equipment_name',
            target_equipment_name='?target_equipment_name',
            target_equipment_id='?target_equipment_id',
        ),
    ))

    # R2: Process one oven slot — for each cooking_started oven with contents,
    # wait (once per oven) then remove each slot's contents.
    # Iterates via while-matches: after each removal_slot_processed,
    # re-evaluates and fires for the next slot.
    rules.append(Rule(
        rule_name='process_oven_slot_removal',
        priority=190,
        antecedents=[
            Fact(fact_title='removal_initialized',
                 step_idx='?step_idx',
                 source_equipment_name='?source_equipment_name',
                 target_equipment_name='?target_equipment_name',
                 target_equipment_id='?target_equipment_id'),
            Fact(fact_title='cooking_started',
                 equipment_name='?source_equipment_name',
                 equipment_id='?source_eq_id',
                 duration='?duration',
                 duration_unit='?duration_unit'),
            Fact(fact_title='equipment_contents',
                 equipment_name='?source_equipment_name',
                 equipment_id='?source_eq_id',
                 slot_number='?slot_number'),
            NegatedFact(fact_title='removal_slot_processed',
                        step_idx='?step_idx',
                        equipment_id='?source_eq_id',
                        slot_number='?slot_number'),
        ],
        action_fn=_process_oven_slot_removal,
        consequent=Fact(
            fact_title='removal_slot_processed',
            step_idx='?step_idx',
            equipment_id='?source_eq_id',
            slot_number='?slot_number',
        ),
    ))

    # R3: Complete removal — fires after all R2 instances complete (lower priority)
    rules.append(Rule(
        rule_name='complete_removal',
        priority=100,
        antecedents=[
            Fact(fact_title='removal_initialized',
                 step_idx='?step_idx'),
        ],
        action_fn=None,
        consequent=Fact(
            fact_title='removal_completed',
            step_idx='?step_idx',
        ),
    ))

    return rules
