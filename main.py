import argparse

from recipes.chocolate_chip_cookies import chocolate_chip_cookies_recipe
from classes.KnowledgeBase import KnowledgeBase
from classes.WorkingMemory import WorkingMemory

import scaling.main
import planning.main

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

    parser.add_argument(
        "--conflict_resolution",
        type=str,
        default="priority",
        choices=["priority", "specificity"],
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

    kb = KnowledgeBase()
    wm = WorkingMemory()

    scaling.main.main(wm=wm, kb=kb, recipe=recipe, args=args)
    # planning.main.main(wm=wm, kb=kb, recipe=recipe, args=args)
