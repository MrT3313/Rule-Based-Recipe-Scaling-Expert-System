from classes.Rule import Rule
from classes.Fact import Fact
from planning.classes.CleaningStep import CleaningStep


def _clean_equipment(*, bindings, wm, kb, plan):
    equipment_name = bindings['?equipment_name']
    equipment_id = bindings['?equipment_id']

    # Find the DIRTY fact in WM and mutate it to AVAILABLE
    dirty_fact = wm.query_equipment(
        equipment_name=equipment_name,
        equipment_id=equipment_id,
        first=True,
        state='DIRTY',
    )

    # Add a CleaningStep to the plan
    plan.append(CleaningStep(equipment_name=equipment_name, equipment_id=equipment_id))

    if dirty_fact:
        dirty_fact.attributes['state'] = 'AVAILABLE'

    return bindings


def get_equipment_status_rules():
    rules = []

    rules.append(
        Rule(
            rule_name='requires_cleaning',
            priority=100,
            antecedents=[
                Fact(fact_title='EQUIPMENT', state='DIRTY',
                     equipment_name='?equipment_name', equipment_id='?equipment_id'),
            ],
            action_fn=_clean_equipment,
            consequent=None,
        )
    )

    return rules
