from classes.Rule import Rule
from classes.Fact import Fact
from planning.classes.WaitStep import WaitStep


def _start_cooking(*, bindings, wm, kb, plan):
    target_equipment_name = bindings['?target_equipment_name']
    target_equipment_id = bindings['?target_equipment_id']
    duration = bindings['?duration']
    duration_unit = bindings['?duration_unit']

    # Query WM for the target equipment fact
    target_eq = wm.query_equipment(
        equipment_name=target_equipment_name,
        equipment_id=target_equipment_id,
        first=True,
    )

    if target_eq is None:
        bindings['?error'] = f"No {target_equipment_name} #{target_equipment_id} found"
        return bindings

    # Append a WaitStep to the plan with the cook duration
    plan.append(WaitStep(
        description=f"Wait {duration} {duration_unit} for {target_equipment_name} #{target_equipment_id} to cook",
        equipment_name=target_equipment_name,
        equipment_id=target_equipment_id,
        duration=duration,
        duration_unit=duration_unit,
    ))

    bindings['?equipment_name'] = target_equipment_name
    bindings['?equipment_id'] = target_equipment_id
    return bindings


def get_cooking_rules():
    rules = []

    rules.append(
        Rule(
            rule_name='start_cooking',
            priority=100,
            antecedents=[
                Fact(fact_title='cooking_wait_request',
                     target_equipment_name='?target_equipment_name',
                     target_equipment_id='?target_equipment_id',
                     duration='?duration',
                     duration_unit='?duration_unit'),
            ],
            action_fn=_start_cooking,
            consequent=Fact(
                fact_title='cooking_started',
                equipment_name='?equipment_name',
                equipment_id='?equipment_id',
                duration='?duration',
                duration_unit='?duration_unit',
            ),
        )
    )

    return rules
