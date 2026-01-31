import argparse

from recipes.chocolate_chip_cookies import chocolate_chip_cookies_recipe

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
