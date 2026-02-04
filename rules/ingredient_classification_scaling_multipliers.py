from classes.Rule import Rule
from classes.Fact import Fact
from classes.NegatedFact import NegatedFact


def get_ingredient_classification_scaling_multiplier_rules():
    rules = []

    rules.append(
        Rule(
            rule_name='calculate_ingredient_scaling_multiplier',
            priority=200,
            antecedents=[
                # wm: has classified ingredient for ingredient name and classification
                Fact(fact_title='classified_ingredient',
                     ingredient_name='?ingredient_name',
                     classification='?classification'),
                # kb (reference facts): has ingredient classification and scale factor for matching ingredient classification
                Fact(fact_title='ingredient_classification_scale_factor',
                     classification_name='?classification',
                     scaling_factor='?scale_factor'),
                # wm: has target recipe scale factor
                Fact(fact_title='target_recipe_scale_factor',
                     target_recipe_scale_factor='?target_scale'),
                # wm: does not have ingredient scaling multiplier for ingredient name
                NegatedFact(fact_title='ingredient_scaling_multiplier',
                            ingredient_name='?ingredient_name')
            ],
            # wm: is updated with ingredient scaling multiplier
            consequent=Fact(fact_title='ingredient_scaling_multiplier',
                           ingredient_name='?ingredient_name',
                           scaling_multiplier='?scaling_multiplier'),
            # action function to calculate ingredient scaling multiplier based on consequent bindings
            action_fn=lambda *, bindings, wm, kb: {
                '?scaling_multiplier': bindings['?target_scale'] * bindings['?scale_factor']
            },
        )
    )

    return rules
