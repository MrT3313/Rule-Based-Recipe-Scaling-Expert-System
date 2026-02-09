from scaling.engine import ScalingEngine
from classes.Fact import Fact
from classes.ExplanationFacility import ExplanationFacility

from scaling.facts.ingredient_classifications import get_ingredient_classification_facts
from scaling.facts.ingredient_classification_scale_factors import get_ingredient_classification_scale_factor_facts
from scaling.facts.measurement_unit_conversions import get_measurement_unit_conversion_facts

from scaling.rules.ingredient_classifications import get_ingredient_classification_rules
from scaling.rules.ingredient_classification_scaling_multipliers import get_ingredient_classification_scaling_multiplier_rules
from scaling.rules.scaled_ingredients import get_scaled_ingredient_rules
from scaling.rules.optimally_scaled_measurement_unit_conversions import get_optimal_unit_conversion_rules


def main(*, wm, kb, recipe, args):
    print("*"*70)
    print("⚙️⚙️ CONFIGURE KNOWLEDGE BASE ⚙️⚙️")
    print("*"*70)
    print("")

    ingredient_classification_facts = get_ingredient_classification_facts()
    kb.add_reference_facts(facts=ingredient_classification_facts)

    ingredient_classification_scale_factors = get_ingredient_classification_scale_factor_facts()
    kb.add_reference_facts(facts=ingredient_classification_scale_factors)

    measurement_unit_conversions = get_measurement_unit_conversion_facts()
    kb.add_reference_facts(facts=measurement_unit_conversions)

    ingredient_classification_rules = get_ingredient_classification_rules()
    kb.add_rules(rules=ingredient_classification_rules)

    scaling_multiplier_rules = get_ingredient_classification_scaling_multiplier_rules()
    kb.add_rules(rules=scaling_multiplier_rules)

    scaled_ingredient_rules = get_scaled_ingredient_rules()
    kb.add_rules(rules=scaled_ingredient_rules)

    optimal_unit_conversion_rules = get_optimal_unit_conversion_rules()
    kb.add_rules(rules=optimal_unit_conversion_rules)

    print("*"*70)
    print("⚙️⚙️ CONFIGURE WORKING MEMORY ⚙️⚙️")
    print("*"*70)
    print("")

    for ingredient in recipe.ingredients:
        wm.add_fact(
            fact=Fact(fact_title='recipe_ingredient',
                ingredient_name=ingredient.ingredient_name,
                amount=ingredient.amount,
                unit=ingredient.unit,
                measurement_category=ingredient.measurement_category
            ),
            silent=True
        )

    print("*"*70)
    print("⚙️⚙️ RUN SCALING INFERENCE ENGINE ⚙️⚙️")
    print("*"*70)
    print("")

    SCALING_ENGINE = ScalingEngine(wm=wm, kb=kb, conflict_resolution_strategy=args.scaling_conflict_resolution, verbose=True)
    SCALING_ENGINE.run()
