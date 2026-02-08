import argparse

# modules
import scaling.main
import planning.main

# classes
from recipes.chocolate_chip_cookies import chocolate_chip_cookies_recipe
from classes.KnowledgeBase import KnowledgeBase
from classes.WorkingMemory import WorkingMemory
from classes.Fact import Fact
from classes.ExplanationFacility import ExplanationFacility

# utils
from utils.print_plan import print_plan

if __name__ == "__main__":
    # parse arguments
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

    parser.add_argument(
        "--scaling_conflict_resolution",
        type=str,
        default="priority",
        choices=["priority", "specificity"],
        help="Conflict resolution strategy",
    )

    # parser.add_argument(
    #     "--planning_conflict_resolution",
    #     type=str,
    #     default="priority",
    #     choices=["priority"],
    #     help="Conflict resolution strategy",
    # )

    parser.add_argument(
        "--num_ovens",
        type=int,
        default=4,
        help="Number of ovens",
    )

    parser.add_argument(
        "--num_bowls",
        type=int,
        default=1,
        help="Number of bowls",
    )

    parser.add_argument(
        "--num_baking_sheets",
        type=int,
        default=5,
        help="Number of baking sheets",
    )

    parser.add_argument(
        "--run_planning_engine",
        action="store_true",
        default=False,
        help="Run planning engine",
    )

    parser.add_argument(
        "--explain",
        action="store_true",
        default=False,
        help="Run interactive explanation REPL at the end",
    )

    args = parser.parse_args()
    print("")

    if args.recipe == "chocolate_chip_cookies":
        recipe = chocolate_chip_cookies_recipe
    else:
        print("Invalid recipe selected. Please choose from the following:")
        exit(1)
    print("")

    print("*"*70)
    print("RULE BASED DEPTH FIRST EXPERT SYSTEM FOR RECIPE SCALING")
    print(f"Chosen Recipe: {args.recipe}")
    print(f"Scaling Factor: {args.scaling_factor}x")
    print(f"Conflict Resolution (Scaling): {args.scaling_conflict_resolution}")
    print(f"Conflict Resolution (Planning): {args.planning_conflict_resolution}")
    print("*"*70)
    print("")

    kb = KnowledgeBase()
    wm = WorkingMemory()

    wm.add_fact(
        fact=Fact(
            fact_title='target_recipe_scale_factor',
            target_recipe_scale_factor=args.scaling_factor
        ),
        silent=True
    )

    # SCALING #################################################################
    scaling.main.main(wm=wm, kb=kb, recipe=recipe, args=args)

    # SCALING > results #######################################################
    print("")
    classified_ingredients = [f for f in wm.facts if f.fact_title == 'classified_ingredient']
    print(f"Classified ingredients: {len(classified_ingredients)}")
    for fact in classified_ingredients:
        print(f"\t{fact}")
    print("")

    scaling_multipliers = [f for f in wm.facts if f.fact_title == 'ingredient_scaling_multiplier']
    print(f"Ingredient scaling multipliers: {len(scaling_multipliers)}")
    for fact in scaling_multipliers:
        print(f"\t{fact}")
    print("")

    scaled_ingredients = [f for f in wm.facts if f.fact_title == 'scaled_ingredient']
    print(f"Scaled ingredients: {len(scaled_ingredients)}")
    for fact in scaled_ingredients:
        name = fact.get(key='ingredient_name')
        original = fact.get(key='original_amount')
        scaled = fact.get(key='scaled_amount')
        unit = fact.get(key='unit')
        multiplier = fact.get(key='scaling_multiplier')
        print(f"\t{name}: {original} → {scaled:.2f} {unit} (×{multiplier:.2f})")
    print("")

    optimal_ingredients = [f for f in wm.facts if f.fact_title == 'optimally_scaled_ingredient']
    print(f"Optimal ingredients: {len(optimal_ingredients)}")
    for fact in optimal_ingredients:
        name = fact.get(key='ingredient_name')
        components = fact.get(key='components')
        original_amount = fact.get(key='original_amount')
        original_unit = fact.get(key='original_unit')

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
                    print(f"\t{name}: {display} (converted from {original_amount:.4g} {original_unit})")
                else:
                    print(f"\t{name}: {display}")
            else:
                amount = components[0]['amount']
                unit = components[0]['unit']
                if conversion_happened:
                    print(f"\t{name}: {amount:.4g} {unit} (converted from {original_amount:.4g} {original_unit})")
                else:
                    print(f"\t{name}: {amount:.4g} {unit}")
        else:
            print(f"\t{name}: [no components]")
    print("")

    print("*" * 70)
    print(f"ALL FACTS IN WORKING MEMORY: {len(wm.facts)}")
    print("*" * 70)
    print("")
    for fact in wm.facts:
        print(f"\t{fact}")
    print("")

    if args.run_planning_engine:
        # PLANNING ################################################################
        success, plan = planning.main.main(wm=wm, kb=kb, recipe=recipe, args=args)

        # PLANNING > results ######################################################
        if not success:
            print(f"\n❌ Planning failed: {plan}")
        else:
            print(f"\n✅ Planning complete — {len(plan)} action(s) in plan")

            if args.explain:
                explanation = ExplanationFacility(wm=wm, kb=kb, label="Combined")
                explanation.run_repl()

            print_plan(plan=plan)


