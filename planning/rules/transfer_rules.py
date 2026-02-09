import math
from classes.Rule import Rule
from classes.Fact import Fact


def _plan_transfer(*, bindings, wm, kb, plan):
    source_equipment_name = bindings['?source_equipment_name']
    source_equipment_id = bindings['?source_equipment_id']
    scoop_size_amount = bindings['?scoop_size_amount']
    scoop_size_unit = bindings['?scoop_size_unit']

    # 1. Sum equipment_contents from source bowl -> total volume in equipment's volume unit
    source_equipment = wm.query_equipment(
        equipment_name=source_equipment_name,
        equipment_id=source_equipment_id,
        first=True,
    )
    if source_equipment is None:
        bindings['?error'] = f"Source equipment {source_equipment_name} #{source_equipment_id} not found"
        return bindings

    equipment_volume_unit = source_equipment.attributes.get('volume_unit', '')

    existing_contents = wm.query_facts(
        fact_title='equipment_contents',
        equipment_name=source_equipment_name,
        equipment_id=source_equipment_id,
    )
    total_volume_in_eq_unit = sum(
        f.attributes.get('volume_in_equipment_unit', 0) for f in existing_contents
    )

    # 2. Convert total volume and scoop size to base unit (teaspoons)
    eq_conversion = None
    scoop_conversion = None
    for fact in kb.reference_facts:
        if fact.fact_title == 'unit_conversion':
            if fact.attributes.get('unit') == equipment_volume_unit:
                eq_conversion = fact
            if fact.attributes.get('unit') == scoop_size_unit:
                scoop_conversion = fact

    if eq_conversion is None:
        bindings['?error'] = f"No unit_conversion found for {equipment_volume_unit}"
        return bindings
    if scoop_conversion is None:
        bindings['?error'] = f"No unit_conversion found for {scoop_size_unit}"
        return bindings

    total_tsp = total_volume_in_eq_unit * eq_conversion.attributes['to_base']
    scoop_tsp = scoop_size_amount * scoop_conversion.attributes['to_base']

    # 3. Calculate num_dough_balls
    num_dough_balls = int(total_tsp / scoop_tsp)

    # 4. Calculate capacity_per_sheet via grid layout using reference facts
    sheet_dims = None
    cookie_specs = None
    sheet_margin = None
    for fact in kb.reference_facts:
        if fact.fact_title == 'baking_sheet_dimensions':
            sheet_dims = fact
        elif fact.fact_title == 'cookie_specifications':
            cookie_specs = fact
        elif fact.fact_title == 'baking_sheet_margin':
            sheet_margin = fact

    if sheet_dims is None or cookie_specs is None or sheet_margin is None:
        bindings['?error'] = "Missing baking sheet reference facts"
        return bindings

    width = sheet_dims.attributes['width']
    length = sheet_dims.attributes['length']
    margin = sheet_margin.attributes['edge_margin']
    diameter = cookie_specs.attributes['diameter']
    spacing = cookie_specs.attributes['spacing']

    usable_width = width - 2 * margin
    usable_length = length - 2 * margin
    grid_spacing = diameter + spacing

    cols = math.floor(usable_width / grid_spacing)
    rows = math.floor(usable_length / grid_spacing)
    capacity_per_sheet = cols * rows

    # 5. Calculate num_sheets_needed
    num_sheets_needed = math.ceil(num_dough_balls / capacity_per_sheet)

    bindings['?num_dough_balls'] = num_dough_balls
    bindings['?capacity_per_sheet'] = capacity_per_sheet
    bindings['?num_sheets_needed'] = num_sheets_needed

    return bindings


def _execute_transfer(*, bindings, wm, kb, plan):
    target_equipment_name = bindings['?target_equipment_name']
    target_equipment_id = bindings['?target_equipment_id']
    quantity = bindings['?quantity']
    scoop_size_amount = bindings['?scoop_size_amount']
    scoop_size_unit = bindings['?scoop_size_unit']

    # Assert equipment_contents on target sheet
    wm.add_fact(fact=Fact(
        fact_title='equipment_contents',
        equipment_name=target_equipment_name,
        equipment_id=target_equipment_id,
        content_type='DOUGH_BALLS',
        quantity=quantity,
        scoop_size_amount=scoop_size_amount,
        scoop_size_unit=scoop_size_unit,
    ), indent="    ")

    # Mark target sheet IN_USE
    target_equipment = wm.query_equipment(
        equipment_name=target_equipment_name,
        equipment_id=target_equipment_id,
        first=True,
    )
    if target_equipment:
        target_equipment.attributes['state'] = 'IN_USE'

    return bindings


def get_transfer_rules():
    rules = []

    # Rule 1: Plan the transfer (calculate dough balls, capacity, sheets needed)
    rules.append(
        Rule(
            rule_name='plan_transfer',
            priority=100,
            antecedents=[
                Fact(fact_title='transfer_planning_request',
                     source_equipment_name='?source_equipment_name',
                     source_equipment_id='?source_equipment_id',
                     scoop_size_amount='?scoop_size_amount',
                     scoop_size_unit='?scoop_size_unit',
                     target_equipment_name='?target_equipment_name'),
            ],
            action_fn=_plan_transfer,
            consequent=Fact(
                fact_title='transfer_plan',
                num_dough_balls='?num_dough_balls',
                capacity_per_sheet='?capacity_per_sheet',
                num_sheets_needed='?num_sheets_needed',
            ),
        )
    )

    # Rule 2: Execute a single transfer onto one sheet
    rules.append(
        Rule(
            rule_name='execute_transfer',
            priority=100,
            antecedents=[
                Fact(fact_title='transfer_request',
                     source_equipment_name='?source_equipment_name',
                     source_equipment_id='?source_equipment_id',
                     target_equipment_name='?target_equipment_name',
                     target_equipment_id='?target_equipment_id',
                     quantity='?quantity',
                     scoop_size_amount='?scoop_size_amount',
                     scoop_size_unit='?scoop_size_unit'),
            ],
            action_fn=_execute_transfer,
            consequent=Fact(
                fact_title='transfer_completed',
                source_equipment_name='?source_equipment_name',
                source_equipment_id='?source_equipment_id',
                target_equipment_name='?target_equipment_name',
                target_equipment_id='?target_equipment_id',
                quantity='?quantity',
            ),
        )
    )

    return rules
