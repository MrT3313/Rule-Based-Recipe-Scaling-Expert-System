from classes.Fact import Fact

# EQUIPMENT STATES
## AVAILABLE | IN_USE | DIRTY

def get_equipment_facts():
    return [
        Fact(
            fact_title='EQUIPMENT',
            equipment_type='APPLIANCE',
            equipment_name='OVEN',
        ),
    ]