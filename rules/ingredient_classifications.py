from classes.Rule import Rule
from classes.Fact import Fact
from classes.NegatedFact import NegatedFact


def get_ingredient_classification_rules():
    rules = []
    
    rules.append(
        Rule(
            antecedents=[
                Fact('ingredient_classification', 
                     ingredient_name='?ingredient_name', 
                     ingredient_classification='?ingredient_classification'),
                Fact('recipe_ingredient',
                     ingredient_name='?ingredient_name')
            ],
            consequent=Fact('classified_ingredient',
                            ingredient_name='?ingredient_name',
                            classification='?ingredient_classification'),
            priority=100,
            rule_name='classify_known_ingredient'
        )
    )
    
    rules.append(
        Rule(
            antecedents=[
                Fact('recipe_ingredient',
                     ingredient_name='?ingredient_name'),
                NegatedFact('ingredient_classification',
                            ingredient_name='?ingredient_name'),
                NegatedFact('classified_ingredient',
                            ingredient_name='?ingredient_name')
            ],
            consequent=Fact('classified_ingredient',
                            ingredient_name='?ingredient_name',
                            classification='DEFAULT'),
            priority=50,
            rule_name='classify_default_ingredient'
        )
    )
    
    return rules
