# imports
import argparse

# recipes
from recipes.chocolate_chip_cookies import chocolate_chip_cookies_recipe

# classes
from classes.InfrenceEngines.ScalingEngine import ScalingEngine
from classes.KnowledgeBase import KnowledgeBase
from classes.WorkingMemory import WorkingMemory
from classes.Fact import Fact
# from classes.ExplanationComponent import ExplanationComponent

# facts
from facts.ingredient_classifications import get_ingredient_classification_facts
from facts.ingredient_classification_scale_factors import get_ingredient_classification_scale_factor_facts
from facts.measurement_unit_conversions import get_measurement_unit_conversion_facts

# rules
from rules.ingredient_classifications import get_ingredient_classification_rules
from rules.ingredient_classification_scaling_multipliers import get_ingredient_classification_scaling_multiplier_rules
from rules.scaled_ingredients import get_scaled_ingredient_rules
from rules.optimally_scaled_measurement_unit_conversions import get_optimal_unit_conversion_rules

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
    # Recency: gives priority to rules that match the most recently added or modified facts. This strategy assumes that newer information is more relevant to the current problem-solving state.
    # Specificity: more antecedent conditions = more specific, fires first.
    parser.add_argument(
        "--conflict_resolution",
        type=str,
        default="priority",
        choices=["priority", "recency", "specificity"],
        help="Conflict resolution strategy",
    )

    parser.add_argument(
        "--explain",
        action="store_true",
        default=False,
        help="Run interactive explanation REPL at the end",
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
    
    scaling_multiplier_rules = get_ingredient_classification_scaling_multiplier_rules()
    kb.add_rule(scaling_multiplier_rules)
    print(f"Added {len(scaling_multiplier_rules)} ingredient scaling multiplier rules")
    
    scaled_ingredient_rules = get_scaled_ingredient_rules()
    kb.add_rule(scaled_ingredient_rules)
    print(f"Added {len(scaled_ingredient_rules)} scaled ingredient rules")
    
    optimal_unit_conversion_rules = get_optimal_unit_conversion_rules()
    kb.add_rule(optimal_unit_conversion_rules)
    print(f"Added {len(optimal_unit_conversion_rules)} optimal unit conversion rules")
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
                unit=ingredient.unit,
                measurement_category=ingredient.measurement_category
            ), 
            silent=True
        )
    print(f"Added {len(recipe.ingredients)} recipe ingredient facts to working memory")
    print("")

    print(f"Working Memory Base size: {len(wm.facts)} facts")
    print("")

    print("*"*70)
    print("⚙️⚙️ RUN INFERENCE ENGINE ⚙️⚙️")
    print("*"*70)
    print("")
    
    SCALING_ENGINE = ScalingEngine(wm, kb, conflict_resolution_strategy=args.conflict_resolution, verbose=True)
    SCALING_ENGINE.run()
    
    print("")
    print("*"*70)
    print("FINAL RESULTS")
    print("*"*70)
    print("")
    print(f"Total facts in working memory: {len(wm.facts)}")
    print("")
    
    classified_ingredients = [f for f in wm.facts if f.fact_title == 'classified_ingredient']
    print(f"Classified ingredients: {len(classified_ingredients)}")
    for fact in classified_ingredients:
        print(f"  {fact}")
    print("")
    
    scaling_multipliers = [f for f in wm.facts if f.fact_title == 'ingredient_scaling_multiplier']
    print(f"Ingredient scaling multipliers: {len(scaling_multipliers)}")
    for fact in scaling_multipliers:
        print(f"  {fact}")
    print("")
    
    scaled_ingredients = [f for f in wm.facts if f.fact_title == 'scaled_ingredient']
    print(f"Scaled ingredients: {len(scaled_ingredients)}")
    for fact in scaled_ingredients:
        name = fact.get('ingredient_name')
        original = fact.get('original_amount')
        scaled = fact.get('scaled_amount')
        unit = fact.get('unit')
        multiplier = fact.get('scaling_multiplier')
        print(f"  {name}: {original} → {scaled:.2f} {unit} (×{multiplier:.2f})")
    print("")
    
    optimal_ingredients = [f for f in wm.facts if f.fact_title == 'optimally_scaled_ingredient']
    print(f"Optimal ingredients: {len(optimal_ingredients)}")
    for fact in optimal_ingredients:
        name = fact.get('ingredient_name')
        components = fact.get('components')
        original_amount = fact.get('original_amount')
        original_unit = fact.get('original_unit')
        
        if components:
            conversion_happened = False
            
            if len(components) == 1:
                if components[0]['unit'] != original_unit:
                    conversion_happened = True
            else:
                conversion_happened = True
            
            if len(components) > 1:
                parts = [f"{c['amount']:.4g} {c['unit']}" for c in components]
                display = " + ".join(parts)
                if conversion_happened:
                    print(f"  {name}: {display} (converted from {original_amount:.4g} {original_unit})")
                else:
                    print(f"  {name}: {display}")
            else:
                amount = components[0]['amount']
                unit = components[0]['unit']
                if conversion_happened:
                    print(f"  {name}: {amount:.4g} {unit} (converted from {original_amount:.4g} {original_unit})")
                else:
                    print(f"  {name}: {amount:.4g} {unit}")
        else:
            print(f"  {name}: [no components]")
    print("")

    print("*"*70)
    print("ALL FACTS IN WORKING MEMORY")
    print("*"*70)
    print("")
    for fact in wm.facts:
        print(f"  #{fact.fact_id}  {fact}")
    print("")

    # if args.explain:
    #     explainer = ExplanationComponent(wm)
    #     print("*"*70)
    #     print("EXPLANATION: Enter fact ID, 'list' to relist facts, or 'q' to quit")
    #     print("*"*70)
    #     print("")
    #     while True:
    #         try:
    #             raw = input("Enter fact ID, 'list' to relist facts, or 'q' to quit: ").strip().lower()
    #         except EOFError:
    #             break
    #         if raw in ("q", "quit", ""):
    #             break
    #         if raw in ("list", "l"):
    #             print("")
    #             for fact in wm.facts:
    #                 print(f"  #{fact.fact_id}  {fact}")
    #             print("")
    #             continue
    #         try:
    #             fact_id = int(raw)
    #         except ValueError:
    #             print("Invalid input. Enter a fact ID (number), 'list', or 'q' to quit.")
    #             continue
    #         print("")
    #         print(explainer.explain(fact_id))
    #         print("")
