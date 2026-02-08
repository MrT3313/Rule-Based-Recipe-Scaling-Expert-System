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

    parser.add_argument(
        "--planning_conflict_resolution",
        type=str,
        default="priority",
        choices=["priority"],
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

    scaling.main.main(wm=wm, kb=kb, recipe=recipe, args=args)
    success, plan = planning.main.main(wm=wm, kb=kb, recipe=recipe, args=args)

    if not success:
        print(f"\n❌ Planning failed: {plan}")
    else:
        print(f"\n✅ Planning complete — {len(plan)} action(s) in plan")

        if args.explain:
            explanation = ExplanationFacility(wm=wm, kb=kb, label="Combined")
            explanation.run_repl()

        print_plan(plan)


