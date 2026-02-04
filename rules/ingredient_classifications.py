from classes.Rule import Rule
from classes.Fact import Fact
from classes.NegatedFact import NegatedFact


def get_ingredient_classification_rules():
    rules = []

    rules.append(
        Rule(
            rule_name='classify_known_ingredient',
            priority=100,
            antecedents=[
                # wm: has recipe ingredient name
                Fact(fact_title='recipe_ingredient',
                     ingredient_name='?ingredient_name'),
                # kb (reference facts): has ingredient classification for matching ingredient name
                Fact(fact_title='ingredient_classification',
                     ingredient_name='?ingredient_name',
                     ingredient_classification='?ingredient_classification'),
                # wm: does not have classified ingredient for ingredient name
                NegatedFact(fact_title='classified_ingredient',
                            ingredient_name='?ingredient_name')
            ],
            # wm: is updated with classified ingredient based on consequent bindings
            consequent=Fact(fact_title='classified_ingredient',
                            ingredient_name='?ingredient_name',
                            classification='?ingredient_classification'),
        )
    )

    rules.append(
        Rule(
            rule_name='classify_default_ingredient',
            priority=50,
            antecedents=[
                # wm: has recipe ingredient name
                Fact(fact_title='recipe_ingredient',
                     ingredient_name='?ingredient_name'),
                # kb (reference facts): does not have recipe ingredient classification for recipe ingredient name
                NegatedFact(fact_title='ingredient_classification',
                            ingredient_name='?ingredient_name'),
                # wm: does not have classified ingredient for recipe ingredient name
                NegatedFact(fact_title='classified_ingredient',
                            ingredient_name='?ingredient_name')
            ],
            # wm: is updated with default classified ingredient based on consequent bindings
            consequent=Fact(fact_title='classified_ingredient',
                            ingredient_name='?ingredient_name',
                            classification='DEFAULT'),
        )
    )

    return rules
