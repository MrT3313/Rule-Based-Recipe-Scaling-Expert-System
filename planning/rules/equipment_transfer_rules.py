import math
from classes.Rule import Rule
from classes.Fact import Fact
from planning.classes.Step import Step


def _check_oven_preheated(*, bindings, wm, kb, plan):
    target_equipment_name = bindings['?target_equipment_name']

    # Query for IN_USE ovens (preheated via PreheatStep)
    in_use_ovens = wm.query_equipment(
        equipment_name=target_equipment_name,
        state='IN_USE',
    )

    if not in_use_ovens:
        bindings['?error'] = f"No {target_equipment_name} is currently preheated (IN_USE)"
        return bindings

    oven = in_use_ovens[0]
    oven_id = oven.attributes['equipment_id']

    # Add a wait step to the plan
    plan.append(Step(
        description=f"Wait for {target_equipment_name} #{oven_id} to preheat",
    ))

    bindings['?equipment_id'] = oven_id
    return bindings


def _plan_equipment_transfer(*, bindings, wm, kb, plan):
    source_equipment_name = bindings['?source_equipment_name']
    target_equipment_name = bindings['?target_equipment_name']
    num_source_items = bindings['?num_source_items']

    # Look up source equipment dimensions (baking sheet)
    sheet_dims = None
    rack_dims = None
    for fact in kb.reference_facts:
        if fact.fact_title == 'baking_sheet_dimensions':
            sheet_dims = fact
        elif fact.fact_title == 'oven_rack_dimensions':
            rack_dims = fact

    if sheet_dims is None:
        bindings['?error'] = "Missing baking_sheet_dimensions reference fact"
        return bindings
    if rack_dims is None:
        bindings['?error'] = "Missing oven_rack_dimensions reference fact"
        return bindings

    # Calculate how many sheets fit per rack
    sheet_width = sheet_dims.attributes['width']
    sheet_length = sheet_dims.attributes['length']
    rack_width = rack_dims.attributes['width']
    rack_length = rack_dims.attributes['length']

    items_per_rack = math.floor(rack_width / sheet_width) * math.floor(rack_length / sheet_length)

    # Query IN_USE target equipment for capacity (number_of_racks)
    in_use_targets = wm.query_equipment(
        equipment_name=target_equipment_name,
        state='IN_USE',
    )

    if not in_use_targets:
        bindings['?error'] = f"No {target_equipment_name} is IN_USE"
        return bindings

    racks_per_target = in_use_targets[0].attributes.get('number_of_racks', 1)
    capacity_per_target = items_per_rack * racks_per_target
    num_targets_needed = math.ceil(num_source_items / capacity_per_target)

    bindings['?items_per_rack'] = items_per_rack
    bindings['?capacity_per_target'] = capacity_per_target
    bindings['?num_targets_needed'] = num_targets_needed

    return bindings


def _find_available_rack(*, bindings, wm, kb, plan):
    target_equipment_name = bindings['?target_equipment_name']

    # Query all IN_USE equipment of the target type
    in_use_targets = wm.query_equipment(
        equipment_name=target_equipment_name,
        state='IN_USE',
    )

    for target in in_use_targets:
        target_id = target.attributes['equipment_id']
        num_racks = target.attributes.get('number_of_racks', 1)

        # Count existing equipment_contents facts for this equipment
        existing_contents = wm.query_facts(
            fact_title='equipment_contents',
            equipment_name=target_equipment_name,
            equipment_id=target_id,
        )
        occupied = len(existing_contents)

        if occupied < num_racks:
            bindings['?equipment_id'] = target_id
            bindings['?rack_number'] = occupied + 1
            bindings['?rack_found'] = True
            return bindings

    # All racks full (or no IN_USE equipment at all)
    bindings['?equipment_id'] = None
    bindings['?rack_number'] = None
    bindings['?rack_found'] = False
    return bindings


def _execute_equipment_transfer(*, bindings, wm, kb, plan):
    target_equipment_name = bindings['?target_equipment_name']
    target_equipment_id = bindings['?target_equipment_id']
    slot_number = bindings['?slot_number']
    source_equipment_name = bindings['?source_equipment_name']
    source_equipment_id = bindings['?source_equipment_id']

    # Assert equipment_contents on the target slot
    wm.add_fact(fact=Fact(
        fact_title='equipment_contents',
        equipment_name=target_equipment_name,
        equipment_id=target_equipment_id,
        slot_number=slot_number,
        content_type=source_equipment_name,
        content_equipment_id=source_equipment_id,
    ), indent="    ")

    return bindings


def get_equipment_transfer_rules():
    rules = []

    # Rule 1: Check that the oven is preheated
    rules.append(
        Rule(
            rule_name='check_oven_preheated',
            priority=110,
            antecedents=[
                Fact(fact_title='preheat_check_request',
                     target_equipment_name='?target_equipment_name'),
            ],
            action_fn=_check_oven_preheated,
            consequent=Fact(
                fact_title='preheat_completed',
                equipment_name='?target_equipment_name',
                equipment_id='?equipment_id',
            ),
        )
    )

    # Rule 2: Plan the equipment transfer (calculate capacity, targets needed)
    rules.append(
        Rule(
            rule_name='plan_equipment_transfer',
            priority=100,
            antecedents=[
                Fact(fact_title='equipment_transfer_planning_request',
                     source_equipment_name='?source_equipment_name',
                     target_equipment_name='?target_equipment_name',
                     num_source_items='?num_source_items'),
            ],
            action_fn=_plan_equipment_transfer,
            consequent=Fact(
                fact_title='equipment_transfer_plan',
                items_per_rack='?items_per_rack',
                capacity_per_target='?capacity_per_target',
                num_targets_needed='?num_targets_needed',
            ),
        )
    )

    # Rule 3: Find an available rack on an IN_USE target equipment
    rules.append(
        Rule(
            rule_name='find_available_rack',
            priority=110,
            antecedents=[
                Fact(fact_title='available_rack_request',
                     target_equipment_name='?target_equipment_name'),
            ],
            action_fn=_find_available_rack,
            consequent=Fact(
                fact_title='available_rack',
                equipment_name='?target_equipment_name',
                equipment_id='?equipment_id',
                rack_number='?rack_number',
                rack_found='?rack_found',
            ),
        )
    )

    # Rule 4: Execute a single equipment transfer (place source onto target slot)
    rules.append(
        Rule(
            rule_name='execute_equipment_transfer',
            priority=100,
            antecedents=[
                Fact(fact_title='equipment_transfer_request',
                     target_equipment_name='?target_equipment_name',
                     target_equipment_id='?target_equipment_id',
                     slot_number='?slot_number',
                     source_equipment_name='?source_equipment_name',
                     source_equipment_id='?source_equipment_id'),
            ],
            action_fn=_execute_equipment_transfer,
            consequent=Fact(
                fact_title='equipment_transfer_completed',
                target_equipment_id='?target_equipment_id',
                slot_number='?slot_number',
                source_equipment_id='?source_equipment_id',
            ),
        )
    )

    return rules
