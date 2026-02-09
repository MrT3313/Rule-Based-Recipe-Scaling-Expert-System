from classes.Rule import Rule
from classes.Fact import Fact
from classes.NegatedFact import NegatedFact


def get_scaled_ingredient_rules():
    rules = []

    rules.append(
        Rule(
            rule_name='scale_ingredient_amount',
            priority=300,
            antecedents=[
                # wm: has ingredient name, amount, unit, and measurement category
                Fact(fact_title='recipe_ingredient',
                     ingredient_name='?ingredient_name',
                     amount='?original_amount',
                     unit='?unit',
                     measurement_category='?measurement_category'),
                # wm: has ingredient scaling multiplier for ingredient name
                Fact(fact_title='ingredient_scaling_multiplier',
                     ingredient_name='?ingredient_name',
                     scaling_multiplier='?scaling_multiplier'),
                # wm: does not have scaled ingredient for ingredient name
                NegatedFact(fact_title='scaled_ingredient',
                            ingredient_name='?ingredient_name')
            ],
            # wm is updated with scaled ingredient
            consequent=Fact(fact_title='scaled_ingredient',
                           ingredient_name='?ingredient_name',
                           original_amount='?original_amount',
                           scaled_amount='?scaled_amount',
                           unit='?unit',
                           measurement_category='?measurement_category',
                           scaling_multiplier='?scaling_multiplier'),
            # action function to calculate scaled ingredient amount based on consequent bindings
            action_fn=lambda *, bindings, wm, kb: {
                **bindings,
                '?scaled_amount': bindings['?original_amount'] * bindings['?scaling_multiplier']
            },
        )
    )

    return rules
