# imports
import argparse

# recipes
from recipes.chocolate_chip_cookies import chocolate_chip_cookies_recipe

# classes
from classes.KnowledgeBase import KnowledgeBase
from classes.WorkingMemory import WorkingMemory
from classes.Fact import Fact

# facts
from facts.ingredient_classifications import get_ingredient_classification_facts
from facts.ingredient_classification_scale_factors import get_ingredient_classification_scale_factor_facts
from facts.measurement_unit_conversions import get_measurement_unit_conversion_facts

# rules
from rules.ingredient_classifications import get_ingredient_classification_rules

if __name__ == "__main__":
    print("*"*70)
    print("FORWARD-CHAINING PRODUCTION SYSTEM: Recipe Scaling")
    print("*"*70)
    print("")

    print("PARSING ARGUMENTS...")
    parser = argparse.ArgumentParser(
        description="Runs First-Order Logic inference algorithms on a Knowledge Base.",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "--recipe",
        type=str,
        help="Recipe to scale",
        default="chocolate_chip_cookies",
        choices=["chocolate_chip_cookies"],
    )

    parser.add_argument(
        "--scaling_factor",
        type=float,
        default=2,
        help="Scaling factor to apply to the recipe",
    )

    # Which conflict resolution strategy to use
    # Priority: Use explicit rule priorities (default, best for this domain)
    # Specificity: More specific rules fire first
    # Recency: Rules matching newest facts fire first
    parser.add_argument(
        "--conflict_resolution",
        type=str,
        default="priority",
        choices=["priority", "specificity", "recency"],
        help="Conflict resolution strategy",
    )

    args = parser.parse_args()
    print("")

    print("LOADING RECIPE...")
    if args.recipe == "chocolate_chip_cookies":
        recipe = chocolate_chip_cookies_recipe
    else:
        print("Invalid recipe selected. Please choose from the following:")
        exit(1)
    print("")

    print("*"*70)
    print(f"CHOSEN RECIPE: {args.recipe}")
    print(f"SCALING FACTOR: {args.scaling_factor}x")
    print(f"CONFLICT RESOLUTION: {args.conflict_resolution}")
    print("*"*70)
    print("")

    print("*"*70)
    print("⚙️⚙️ CONFIGURE KNOWLEDGE BASE ⚙️⚙️")
    # The knowledge base holds permanent knowledge: rules and reference facts
    # Reference facts are static domain "background" knowledge (unit conversions, classifications, etc.)
    print("*"*70)
    print("")
    kb = KnowledgeBase()

    ingredient_classification_facts = get_ingredient_classification_facts()
    ingredient_classification_scale_factors = get_ingredient_classification_scale_factor_facts()
    measurement_unit_conversions = get_measurement_unit_conversion_facts()

    kb.add_reference_fact(ingredient_classification_facts)
    print(f"Added {len(ingredient_classification_facts)} ingredient classification facts")
    kb.add_reference_fact(ingredient_classification_scale_factors)
    print(f"Added {len(ingredient_classification_scale_factors)} ingredient classification scale factor facts")
    kb.add_reference_fact(measurement_unit_conversions)
    print(f"Added {len(measurement_unit_conversions)} measurement unit conversion facts")
    print("")
    
    ingredient_classification_rules = get_ingredient_classification_rules()
    kb.add_rule(ingredient_classification_rules)
    print(f"Added {len(ingredient_classification_rules)} ingredient classification rules")
    print("")
    
    print(f"Knowledge Base size: {len(kb.reference_facts)} reference facts, {len(kb.rules)} rules")
    print("")

    print("*"*70)
    print("⚙️⚙️ CONFIGURE WORKING MEMORY ⚙️⚙️")
    print("*"*70)
    print("")
    wm = WorkingMemory()

    wm.add_fact(
        Fact(
            fact_title='target_recipe_scale_factor', 
            target_recipe_scale_factor=args.scaling_factor
        ), 
        silent=True
    )
    print('Added target recipe scale factor fact to working memory')
    print("")

    for ingredient in recipe.ingredients:
        wm.add_fact(
            Fact('recipe_ingredient', 
                ingredient_name=ingredient.ingredient_name, 
                amount=ingredient.amount, 
                unit=ingredient.unit
            ), 
            silent=True
        )
    print(f"Added {len(recipe.ingredients)} recipe ingredient facts to working memory")
    print("")

    print(f"Working Memory Base size: {len(wm.facts)} facts")
    print("")
