# classes
from planning.engine import PlanningEngine
from classes.Fact import Fact

# rules
from planning.rules.equipment_status import get_equipment_status_rules

def main(*, wm, kb, recipe, args):
    print("*"*70)
    print("⚙️⚙️ CONFIGURE KNOWLEDGE BASE ⚙️⚙️")
    # The knowledge base holds permanent knowledge: rules and reference facts
    # Reference facts are static domain "background" knowledge (unit conversions, classifications, etc.)
    print("*"*70)
    print("")

    # configure available equipment
    # this will eventually be input from a query to the user
    wm.add_fact(fact=Fact(
        fact_title='EQUIPMENT', 
        equipment_type='APPLIANCE', 
        equipment_name='OVEN',
        equipment_id=1,
        # state='AVAILABLE'
        state='DIRTY' # TESTING
    ), silent=True)
    wm.add_fact(fact=Fact(
        fact_title='EQUIPMENT', 
        equipment_type='CONTAINER', 
        equipment_name='BOWL',
        equipment_id=1,
        state='IN_USE'
    ), silent=True)
    wm.add_fact(fact=Fact(
        fact_title='EQUIPMENT', 
        equipment_type='CONTAINER', 
        equipment_name='BOWL',
        equipment_id=2,
        state='DIRTY'
    ), silent=True)

    # OVEN_STATE = wm.query_equipment_state(
    #     equipment_name='OVEN',
    #     equipment_id=1,
    # )

    # BOWL_STATE = wm.query_equipment_state(
    #     equipment_name='BOWL',
    #     equipment_id=1,
    # )

    # DIRTY_BOWL_STATE = wm.query_equipment_state(
    #     equipment_name='BOWL',
    #     equipment_id=2,
    # )

    # print(f"OVEN STATE: {OVEN_STATE}")
    # print(f"BOWL STATE: {BOWL_STATE}")
    # print(f"DIRTY BOWL STATE: {DIRTY_BOWL_STATE}")

    equipment_status_rules = get_equipment_status_rules()
    kb.add_rules(rules=equipment_status_rules)
    print(f"Added {len(equipment_status_rules)} equipment status rules")

    print("*"*70)
    print("⚙️⚙️ RUN PLANNING ENGINE ⚙️⚙️")
    print("*"*70)
    print("")

    PLANNING_ENGINE = PlanningEngine(wm=wm, kb=kb, verbose=True)
    PLANNING_ENGINE.run(recipe=recipe)

    exit()