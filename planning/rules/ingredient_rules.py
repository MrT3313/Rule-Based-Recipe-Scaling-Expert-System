from classes.Rule import Rule
from classes.Fact import Fact


def _add_ingredient_to_equipment(*, bindings, wm, kb, plan):
    measurement_category = bindings['?measurement_category']
    ingredient_name = bindings['?ingredient_name']
    ingredient_id = bindings['?ingredient_id']
    amount = bindings['?amount']
    unit = bindings['?unit']
    equipment_name = bindings['?equipment_name']
    equipment_id = bindings['?equipment_id']
    equipment_volume = bindings['?equipment_volume']
    equipment_volume_unit = bindings['?equipment_volume_unit']

    if measurement_category == 'WHOLE':
        # WHOLE items (e.g., eggs) don't occupy measurable volume
        volume_in_equipment_unit = 0
    else:
        # Look up unit_conversion for the ingredient's unit
        ingredient_conversion = None
        for fact in kb.reference_facts:
            if (fact.fact_title == 'unit_conversion'
                    and fact.attributes.get('unit') == unit):
                ingredient_conversion = fact
                break

        if ingredient_conversion is None:
            bindings['?error'] = f"No unit_conversion found for {unit}"
            return bindings

        # Look up unit_conversion for the equipment's volume_unit
        equipment_conversion = None
        for fact in kb.reference_facts:
            if (fact.fact_title == 'unit_conversion'
                    and fact.attributes.get('unit') == equipment_volume_unit):
                equipment_conversion = fact
                break

        if equipment_conversion is None:
            bindings['?error'] = f"No unit_conversion found for {equipment_volume_unit}"
            return bindings

        ingredient_to_base = ingredient_conversion.attributes['to_base']
        equipment_to_base = equipment_conversion.attributes['to_base']

        # Convert ingredient amount to equipment's volume unit
        volume_in_equipment_unit = (amount * ingredient_to_base) / equipment_to_base

        # Check capacity: sum existing contents for this equipment
        existing_contents = wm.query_facts(
            fact_title='equipment_contents',
            equipment_name=equipment_name,
            equipment_id=equipment_id,
        )
        used_volume = sum(f.attributes.get('volume_in_equipment_unit', 0) for f in existing_contents)

        if used_volume + volume_in_equipment_unit > equipment_volume:
            bindings['?error'] = (
                f"capacity_exceeded: {ingredient_name} needs {volume_in_equipment_unit:.2f} "
                f"{equipment_volume_unit}, but {equipment_name} #{equipment_id} has "
                f"{used_volume:.2f}/{equipment_volume} {equipment_volume_unit} used"
            )
            return bindings

    # Assert equipment_contents fact
    wm.add_fact(fact=Fact(
        fact_title='equipment_contents',
        equipment_name=equipment_name,
        equipment_id=equipment_id,
        ingredient_id=ingredient_id,
        ingredient_name=ingredient_name,
        volume_in_equipment_unit=volume_in_equipment_unit,
    ), indent="    ")

    bindings['?volume_in_equipment_unit'] = volume_in_equipment_unit
    return bindings


def get_ingredient_rules():
    rules = []

    rules.append(
        Rule(
            rule_name='add_volume_ingredient',
            priority=100,
            antecedents=[
                Fact(fact_title='ingredient_addition_request',
                     ingredient_id='?ingredient_id',
                     ingredient_name='?ingredient_name',
                     amount='?amount',
                     unit='?unit',
                     measurement_category='?measurement_category',
                     equipment_name='?equipment_name',
                     equipment_id='?equipment_id',
                     equipment_volume='?equipment_volume',
                     equipment_volume_unit='?equipment_volume_unit'),
            ],
            action_fn=_add_ingredient_to_equipment,
            consequent=Fact(
                fact_title='ingredient_added',
                ingredient_id='?ingredient_id',
                ingredient_name='?ingredient_name',
                equipment_name='?equipment_name',
                equipment_id='?equipment_id',
                volume_in_equipment_unit='?volume_in_equipment_unit',
            ),
        )
    )

    return rules
