# classes
from planning.engine import PlanningEngine
from classes.Fact import Fact
from classes.ExplanationFacility import ExplanationFacility

# rules
from planning.rules.equipment_status import get_equipment_status_rules
from planning.rules.ingredient_rules import get_ingredient_rules
from planning.rules.transfer_rules import get_transfer_rules
from planning.rules.equipment_transfer_rules import get_equipment_transfer_rules
from planning.rules.cooking_rules import get_cooking_rules
from planning.rules.removal_rules import get_removal_rules
from planning.rules.step_dispatch_rules import get_step_dispatch_rules
from planning.rules.mixing_dispatch_rules import get_mixing_dispatch_rules
from planning.rules.transfer_dispatch_rules import get_transfer_dispatch_rules
from planning.rules.removal_dispatch_rules import get_removal_dispatch_rules
from planning.rules.surface_transfer_dispatch_rules import get_surface_transfer_dispatch_rules
from planning.rules.equipment_transfer_dispatch_rules import get_equipment_transfer_dispatch_rules
from planning.rules.cook_dispatch_rules import get_cook_dispatch_rules

# reference facts
from scaling.facts.measurement_unit_conversions import get_measurement_unit_conversion_facts
from planning.facts.transfer_reference_facts import get_transfer_reference_facts

def main(*, wm, kb, recipe, args):
    print("*"*70)
    print("⚙️⚙️ CONFIGURE KNOWLEDGE BASE ⚙️⚙️")
    print("*"*70)
    print("")

    equipment_status_rules = get_equipment_status_rules()
    kb.add_rules(rules=equipment_status_rules)

    ingredient_rules = get_ingredient_rules()
    kb.add_rules(rules=ingredient_rules)

    transfer_rules = get_transfer_rules()
    kb.add_rules(rules=transfer_rules)

    equipment_transfer_rules = get_equipment_transfer_rules()
    kb.add_rules(rules=equipment_transfer_rules)

    cooking_rules = get_cooking_rules()
    kb.add_rules(rules=cooking_rules)

    removal_rules = get_removal_rules()
    kb.add_rules(rules=removal_rules)

    step_dispatch_rules = get_step_dispatch_rules()
    kb.add_rules(rules=step_dispatch_rules)

    mixing_dispatch_rules = get_mixing_dispatch_rules()
    kb.add_rules(rules=mixing_dispatch_rules)

    transfer_dispatch_rules = get_transfer_dispatch_rules()
    kb.add_rules(rules=transfer_dispatch_rules)

    removal_dispatch_rules = get_removal_dispatch_rules()
    kb.add_rules(rules=removal_dispatch_rules)

    surface_transfer_dispatch_rules = get_surface_transfer_dispatch_rules()
    kb.add_rules(rules=surface_transfer_dispatch_rules)

    equipment_transfer_dispatch_rules = get_equipment_transfer_dispatch_rules()
    kb.add_rules(rules=equipment_transfer_dispatch_rules)

    cook_dispatch_rules = get_cook_dispatch_rules()
    kb.add_rules(rules=cook_dispatch_rules)

    unit_conversion_facts = get_measurement_unit_conversion_facts()
    kb.add_reference_facts(facts=unit_conversion_facts)

    transfer_reference_facts = get_transfer_reference_facts()
    kb.add_reference_facts(facts=transfer_reference_facts)

    print("*"*70)
    print("⚙️⚙️ CONFIGURE WORKING MEMORY > User Equipment ⚙️⚙️")
    # this is currently hardcoded but will eventually become a query to the user at the start of the process to confirm what equipment they have at their disposal
    print("*"*70)
    print("")

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

    wm.add_fact(fact=Fact(
        fact_title='EQUIPMENT',
        equipment_type='SURFACE',
        equipment_name='COUNTERTOP',
        equipment_id=1,
        state='AVAILABLE',
    ), silent=True)

    wm.add_fact(fact=Fact(
        fact_title='EQUIPMENT',
        equipment_type='SURFACE',
        equipment_name='COOLING_RACK',
        equipment_id=1,
        state='AVAILABLE',
    ), silent=True)

    print("*"*70)
    print("⚙️⚙️ RUN PLANNING ENGINE ⚙️⚙️")
    print("*"*70)
    print("")

    PLANNING_ENGINE = PlanningEngine(wm=wm, kb=kb, verbose=True)
    success, result = PLANNING_ENGINE.run(recipe=recipe)

    return success, result