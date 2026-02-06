from classes.Rule import Rule
from classes.Fact import Fact

def get_equipment_status_rules():
    rules = []

    rules.append(
        Rule(
            rule_name='requires_cleaning',
            priority=100,
            antecedents=[
                Fact(fact_title='EQUIPMENT', state='DIRTY'),
            ],
            consequent=Fact(fact_title='requires_cleaning', equipment_name='?equipment_name', equipment_id='?equipment_id'),
        )
    )

    return rules