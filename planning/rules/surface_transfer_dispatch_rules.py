from classes.Rule import Rule
from classes.Fact import Fact
from classes.NegatedFact import NegatedFact
from planning.classes.TransferItem import TransferItem


def _transfer_item_to_surface(*, bindings, wm, kb, plan):
    """Transfer items from a source equipment to a surface target.
    For each source with contents, assert item_transfer_request and append TransferItem to plan."""
    engine = bindings['_engine']
    step_idx = bindings['?step_idx']
    step = engine.recipe.steps[step_idx]

    source_equipment_name = step.source_equipment_name
    target_equipment_name = step.target_equipment_name

    # Resolve target surface equipment
    target_eq = wm.query_equipment(equipment_name=target_equipment_name, first=True)
    if target_eq is None:
        bindings['?error'] = f"No {target_equipment_name} equipment found"
        return bindings

    target_eq_id = target_eq.attributes['equipment_id']

    # Find intermediate contents (e.g., BAKING_SHEET on COUNTERTOP)
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

            _, derived = engine._forward_chain(trigger_fact=transfer_request)

            if engine.last_error:
                bindings['?error'] = engine.last_error
                return bindings

            if engine.verbose and derived is not None:
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


def get_surface_transfer_dispatch_rules():
    rules = []

    # ITS1: Transfer items from source equipment to surface target
    rules.append(Rule(
        rule_name='transfer_item_to_surface',
        priority=200,
        antecedents=[
            Fact(fact_title='step_request',
                 step_type='ITEM_TRANSFER_TO_SURFACE',
                 step_idx='?step_idx'),
        ],
        action_fn=_transfer_item_to_surface,
        consequent=Fact(
            fact_title='surface_transfer_completed',
            step_idx='?step_idx',
        ),
    ))

    return rules
