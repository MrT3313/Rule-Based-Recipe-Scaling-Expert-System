# classes
from planning.engine import PlanningEngine
from classes.Fact import Fact

# rules
from planning.rules.equipment_status import get_equipment_status_rules
from planning.rules.ingredient_rules import get_ingredient_rules
from planning.rules.transfer_rules import get_transfer_rules
from planning.rules.equipment_transfer_rules import get_equipment_transfer_rules

# reference facts
from scaling.facts.measurement_unit_conversions import get_measurement_unit_conversion_facts
from planning.facts.transfer_reference_facts import get_transfer_reference_facts

def main(*, wm, kb, recipe, args):
    print("*"*70)
    print("⚙️⚙️ CONFIGURE KNOWLEDGE BASE ⚙️⚙️")
    # The knowledge base holds permanent knowledge: rules and reference facts
    # Reference facts are static domain "background" knowledge (unit conversions, classifications, etc.)
    print("*"*70)
    print("")

    # configure available equipment
    # this will eventually be input from a query to the user
    for idx in range(3):
        wm.add_fact(fact=Fact(
            fact_title='EQUIPMENT',
            equipment_type='APPLIANCE',
            equipment_name='OVEN',
            equipment_id=idx + 1,
            state='AVAILABLE',
            number_of_racks=2,
        ), silent=True)

    wm.add_fact(fact=Fact(
        fact_title='EQUIPMENT', 
        equipment_type='CONTAINER', 
        equipment_name='BOWL',
        equipment_id=1,
        state='AVAILABLE',
        volume=4,
        volume_unit='QUARTS',
    ), silent=True)

    for idx in range(5):
        wm.add_fact(fact=Fact(
            fact_title='EQUIPMENT',
            equipment_type='TRAY',
            equipment_name='BAKING_SHEET',
            equipment_id=idx + 1,
            state='AVAILABLE',
        ), silent=True)

    equipment_status_rules = get_equipment_status_rules()
    kb.add_rules(rules=equipment_status_rules)
    print(f"Added {len(equipment_status_rules)} equipment status rules")

    ingredient_rules = get_ingredient_rules()
    kb.add_rules(rules=ingredient_rules)
    print(f"Added {len(ingredient_rules)} ingredient rules")

    transfer_rules = get_transfer_rules()
    kb.add_rules(rules=transfer_rules)
    print(f"Added {len(transfer_rules)} transfer rules")

    equipment_transfer_rules = get_equipment_transfer_rules()
    kb.add_rules(rules=equipment_transfer_rules)
    print(f"Added {len(equipment_transfer_rules)} equipment transfer rules")

    unit_conversion_facts = get_measurement_unit_conversion_facts()
    kb.add_reference_fact(fact=unit_conversion_facts)
    print(f"Added {len(unit_conversion_facts)} unit conversion reference facts")

    transfer_reference_facts = get_transfer_reference_facts()
    kb.add_reference_fact(fact=transfer_reference_facts)
    print(f"Added {len(transfer_reference_facts)} transfer reference facts")

    print("*"*70)
    print("⚙️⚙️ RUN PLANNING ENGINE ⚙️⚙️")
    print("*"*70)
    print("")

    PLANNING_ENGINE = PlanningEngine(wm=wm, kb=kb, verbose=True)
    success, result = PLANNING_ENGINE.run(recipe=recipe)

    if not success:
        print(f"\n❌ Planning failed: {result}")
    else:
        print(f"\n✅ Planning complete — {len(result)} action(s) in plan")

    return success, result