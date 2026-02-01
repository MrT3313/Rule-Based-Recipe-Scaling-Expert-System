from classes.Rule import Rule
from classes.Fact import Fact


def get_ingredient_classification_scaling_multiplier_rules():
    rules = []
    
    rules.append(
        Rule(
            antecedents=[
                Fact('classified_ingredient',
                     ingredient_name='?ingredient_name',
                     classification='?classification'),
                Fact('ingredient_classification_scale_factor',
                     classification_name='?classification',
                     scaling_factor='?scale_factor'),
                Fact('target_recipe_scale_factor',
                     target_recipe_scale_factor='?target_scale')
            ],
            consequent=Fact('ingredient_scaling_multiplier',
                           ingredient_name='?ingredient_name',
                           scaling_multiplier='?scaling_multiplier'),
            action_fn=lambda bindings, wm, kb: {
                '?scaling_multiplier': bindings['?target_scale'] * bindings['?scale_factor']
            },
            priority=200,
            rule_name='calculate_ingredient_scaling_multiplier'
        )
    )
    
    return rules
