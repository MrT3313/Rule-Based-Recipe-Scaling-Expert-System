from classes.Fact import Fact


def get_ingredient_classification_scale_factor_facts():
    facts = []
    
    facts.append(Fact(fact_title='ingredient_classification_scale_factor', classification_name='LEAVENING_AGENT', scaling_factor=0.7))
    facts.append(Fact(fact_title='ingredient_classification_scale_factor', classification_name='EXTRACT',         scaling_factor=0.6))
    facts.append(Fact(fact_title='ingredient_classification_scale_factor', classification_name='SEASONING',       scaling_factor=0.8))
    facts.append(Fact(fact_title='ingredient_classification_scale_factor', classification_name='DEFAULT',         scaling_factor=1.0))
    
    return facts