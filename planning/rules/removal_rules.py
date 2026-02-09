from classes.Rule import Rule
from classes.Fact import Fact
from planning.classes.TransferItem import TransferItem


def _remove_equipment(*, bindings, wm, kb, plan):
    source_equipment_name = bindings['?source_equipment_name']
    source_equipment_id = bindings['?source_equipment_id']
    slot_number = bindings['?slot_number']
    target_equipment_name = bindings['?target_equipment_name']
    target_equipment_id = bindings['?target_equipment_id']

    # Find the equipment_contents fact for this source slot
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

    # Retract the source's equipment_contents fact
    wm.remove_fact(fact=contents_fact, indent="    ")

    # Assert equipment_contents on the target surface
    wm.add_fact(fact=Fact(
        fact_title='equipment_contents',
        equipment_name=target_equipment_name,
        equipment_id=target_equipment_id,
        content_type=content_type,
        content_equipment_id=content_equipment_id,
    ), indent="    ")

    # Check if source is now empty
    remaining = wm.query_facts(
        fact_title='equipment_contents',
        equipment_name=source_equipment_name,
        equipment_id=source_equipment_id,
    )
    if len(remaining) == 0:
        source_eq = wm.query_equipment(
            equipment_name=source_equipment_name,
            equipment_id=source_equipment_id,
            first=True,
        )
        if source_eq:
            source_eq.attributes['state'] = 'AVAILABLE'

    bindings['?content_equipment_id'] = content_equipment_id
    bindings['?content_type_name'] = content_type
    return bindings


def _transfer_items(*, bindings, wm, kb, plan):
    source_equipment_name = bindings['?source_equipment_name']
    source_equipment_id = bindings['?source_equipment_id']
    target_equipment_name = bindings['?target_equipment_name']
    target_equipment_id = bindings['?target_equipment_id']
    content_type = bindings['?content_type']

    # Find equipment_contents on the source matching content_type
    contents_fact = wm.query_facts(
        fact_title='equipment_contents',
        equipment_name=source_equipment_name,
        equipment_id=source_equipment_id,
        content_type=content_type,
        first=True,
    )

    if contents_fact is None:
        bindings['?error'] = (
            f"No {content_type} contents found on {source_equipment_name} "
            f"#{source_equipment_id}"
        )
        return bindings

    quantity = contents_fact.attributes.get('quantity', 0)

    # Assert equipment_contents on the target
    wm.add_fact(fact=Fact(
        fact_title='equipment_contents',
        equipment_name=target_equipment_name,
        equipment_id=target_equipment_id,
        content_type=content_type,
        quantity=quantity,
        source_equipment_name=source_equipment_name,
        source_equipment_id=source_equipment_id,
    ), indent="    ")

    # Retract the source's equipment_contents fact
    wm.remove_fact(fact=contents_fact, indent="    ")

    # Mark source equipment as DIRTY
    source_eq = wm.query_equipment(
        equipment_name=source_equipment_name,
        equipment_id=source_equipment_id,
        first=True,
    )
    if source_eq:
        source_eq.attributes['state'] = 'DIRTY'

    bindings['?quantity'] = quantity
    return bindings


def _chain_removal_to_transfer(*, bindings, wm, kb, plan):
    """DFS chaining rule: after equipment removal, transfer items from the removed equipment to the final target."""
    content_equipment_id = bindings['?content_equipment_id']
    content_type_name = bindings['?content_type_name']
    surface_name = bindings['?target_equipment_name']
    surface_id = bindings['?target_equipment_id']

    # Query WM for item_transfer_target fact (pre-asserted by engine)
    item_transfer_target = wm.query_facts(
        fact_title='item_transfer_target',
        first=True,
    )
    if item_transfer_target is None:
        # No chaining target — graceful skip
        return bindings

    final_target_name = item_transfer_target.attributes['target_equipment_name']
    final_target_id = item_transfer_target.attributes['target_equipment_id']

    # Find items on the content equipment (e.g., DOUGH_BALLS on BAKING_SHEET)
    source_contents = wm.query_facts(
        fact_title='equipment_contents',
        equipment_name=content_type_name,
        equipment_id=content_equipment_id,
    )

    if not source_contents:
        return bindings

    total_quantity = 0
    for source_content in source_contents:
        content_type = source_content.attributes['content_type']
        quantity = source_content.attributes.get('quantity', 0)
        total_quantity += quantity

        # Assert equipment_contents on final target
        wm.add_fact(fact=Fact(
            fact_title='equipment_contents',
            equipment_name=final_target_name,
            equipment_id=final_target_id,
            content_type=content_type,
            quantity=quantity,
            source_equipment_name=content_type_name,
            source_equipment_id=content_equipment_id,
        ), indent="    ")

        # Retract from source
        wm.remove_fact(fact=source_content, indent="    ")

    # Mark source equipment as DIRTY
    source_eq = wm.query_equipment(
        equipment_name=content_type_name,
        equipment_id=content_equipment_id,
        first=True,
    )
    if source_eq:
        source_eq.attributes['state'] = 'DIRTY'

    # Also retract the equipment_contents fact on the intermediate surface
    surface_content = wm.query_facts(
        fact_title='equipment_contents',
        equipment_name=surface_name,
        equipment_id=surface_id,
        content_equipment_id=content_equipment_id,
        first=True,
    )
    if surface_content:
        wm.remove_fact(fact=surface_content, indent="    ")

    # Append a TransferItem step to the plan
    transfer_step = TransferItem(
        description=f"Transfer DOUGH_BALLS from {content_type_name} #{content_equipment_id} to {final_target_name}",
        source_equipment_name=content_type_name,
        target_equipment_name=final_target_name,
        scoop_size_amount=1,
        scoop_size_unit='WHOLE',
    )
    plan.append(transfer_step)

    bindings['?final_target_name'] = final_target_name
    bindings['?final_target_id'] = final_target_id
    bindings['?quantity'] = total_quantity
    return bindings


def get_removal_rules():
    rules = []

    # Rule 1: Remove equipment from inside another equipment and place on target
    rules.append(
        Rule(
            rule_name='remove_equipment_from_equipment',
            priority=100,
            antecedents=[
                Fact(fact_title='equipment_removal_request',
                     source_equipment_name='?source_equipment_name',
                     source_equipment_id='?source_equipment_id',
                     slot_number='?slot_number',
                     target_equipment_name='?target_equipment_name',
                     target_equipment_id='?target_equipment_id'),
            ],
            action_fn=_remove_equipment,
            consequent=Fact(
                fact_title='equipment_removal_completed',
                source_equipment_name='?source_equipment_name',
                source_equipment_id='?source_equipment_id',
                slot_number='?slot_number',
                content_equipment_id='?content_equipment_id',
                content_type_name='?content_type_name',
                target_equipment_name='?target_equipment_name',
                target_equipment_id='?target_equipment_id',
            ),
        )
    )

    # Rule 2: Transfer items from one equipment to another
    rules.append(
        Rule(
            rule_name='transfer_items_between_equipment',
            priority=100,
            antecedents=[
                Fact(fact_title='item_transfer_request',
                     source_equipment_name='?source_equipment_name',
                     source_equipment_id='?source_equipment_id',
                     target_equipment_name='?target_equipment_name',
                     target_equipment_id='?target_equipment_id',
                     content_type='?content_type'),
            ],
            action_fn=_transfer_items,
            consequent=Fact(
                fact_title='item_transfer_completed',
                source_equipment_name='?source_equipment_name',
                source_equipment_id='?source_equipment_id',
                target_equipment_name='?target_equipment_name',
                target_equipment_id='?target_equipment_id',
                quantity='?quantity',
            ),
        )
    )

    # Rule 3: DFS chain — after equipment removal, immediately transfer items to final target
    rules.append(
        Rule(
            rule_name='chain_removal_to_item_transfer',
            priority=100,
            antecedents=[
                Fact(fact_title='equipment_removal_completed',
                     content_equipment_id='?content_equipment_id',
                     content_type_name='?content_type_name',
                     target_equipment_name='?target_equipment_name',
                     target_equipment_id='?target_equipment_id'),
            ],
            action_fn=_chain_removal_to_transfer,
            consequent=Fact(
                fact_title='item_transfer_completed',
                source_equipment_name='?content_type_name',
                source_equipment_id='?content_equipment_id',
                target_equipment_name='?final_target_name',
                target_equipment_id='?final_target_id',
                quantity='?quantity',
            ),
        )
    )

    return rules
