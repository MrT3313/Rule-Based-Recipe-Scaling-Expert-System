# classes
from classes.Rule import Rule
from classes.Fact import Fact
from classes.NegatedFact import NegatedFact

# action functions
from scaling.rules.action_functions.calculate_optimally_scaled_measurement_unit_conversion import calculate_optimal_unit


def get_optimal_unit_conversion_rules():
    rules = []

    rules.append(
        Rule(
            rule_name='convert_scaled_ingredient_to_optimal_measurement_unit',
            priority=400,
            antecedents=[
                # wm: has scaled ingredient name, scaled amount, unit, and measurement category
                Fact(fact_title='scaled_ingredient',
                     ingredient_name='?ingredient_name',
                     scaled_amount='?scaled_amount',
                     unit='?unit',
                     measurement_category='?measurement_category'),
                # kb (reference facts): has unit conversion for scaled ingredient unit and measurement category
                Fact(fact_title='unit_conversion',
                     unit='?unit',
                     to_base='?current_to_base',
                     base_unit='?base_unit',
                     measurement_type='?measurement_category'),
                # wm: does not have optimally scaled ingredient for ingredient name
                NegatedFact(fact_title='optimally_scaled_ingredient',
                            ingredient_name='?ingredient_name')
            ],
            # wm: is updated with optimally scaled ingredient
            consequent=Fact(fact_title='optimally_scaled_ingredient',
                           ingredient_name='?ingredient_name',
                           components='?optimal_components',
                           original_amount='?original_amount',
                           original_unit='?unit'),
            # action function to calculate optimally scaled ingredient based on consequent bindings
            action_fn=calculate_optimal_unit,
        )
    )

    return rules
