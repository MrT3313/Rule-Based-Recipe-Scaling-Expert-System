from classes.Rule import Rule
from classes.Fact import Fact


def get_scaled_ingredient_rules():
    rules = []
    
    rules.append(
        Rule(
            antecedents=[
                Fact('recipe_ingredient',
                     ingredient_name='?ingredient_name',
                     amount='?original_amount',
                     unit='?unit',
                     measurement_category='?measurement_category'),
                Fact('ingredient_scaling_multiplier',
                     ingredient_name='?ingredient_name',
                     scaling_multiplier='?scaling_multiplier')
            ],
            consequent=Fact('scaled_ingredient',
                           ingredient_name='?ingredient_name',
                           original_amount='?original_amount',
                           scaled_amount='?scaled_amount',
                           unit='?unit',
                           measurement_category='?measurement_category',
                           scaling_multiplier='?scaling_multiplier'),
            action_fn=lambda bindings, wm, kb: {
                '?scaled_amount': bindings['?original_amount'] * bindings['?scaling_multiplier']
            },
            priority=300,
            rule_name='scale_ingredient_amount'
        )
    )
    
    return rules
