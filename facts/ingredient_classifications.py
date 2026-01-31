from classes.Fact import Fact


def get_ingredient_classification_facts():
    facts = []
    
    facts.append(Fact(fact_title='ingredient_classification', ingredient_name='BAKING_SODA',     ingredient_classification='LEAVENING_AGENT'))
    facts.append(Fact(fact_title='ingredient_classification', ingredient_name='BAKING_POWDER',   ingredient_classification='LEAVENING_AGENT'))
    facts.append(Fact(fact_title='ingredient_classification', ingredient_name='VANILLA_EXTRACT', ingredient_classification='EXTRACT'))
    facts.append(Fact(fact_title='ingredient_classification', ingredient_name='SALT',            ingredient_classification='SEASONING'))
    
    return facts