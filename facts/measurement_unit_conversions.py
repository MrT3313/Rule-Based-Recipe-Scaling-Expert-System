from classes.Fact import Fact


def get_measurement_unit_conversion_facts():
    facts = []
    
    facts.append(Fact(fact_title='unit_conversion', unit='PINCH',        to_base=0.0625, base_unit='TEASPOONS', measurement_type='VOLUME'))
    facts.append(Fact(fact_title='unit_conversion', unit='DASH',         to_base=0.125,  base_unit='TEASPOONS', measurement_type='VOLUME'))
    facts.append(Fact(fact_title='unit_conversion', unit='TEASPOONS',    to_base=1,      base_unit='TEASPOONS', measurement_type='VOLUME'))
    facts.append(Fact(fact_title='unit_conversion', unit='TABLESPOONS',  to_base=3,      base_unit='TEASPOONS', measurement_type='VOLUME'))
    facts.append(Fact(fact_title='unit_conversion', unit='FLUID_OUNCES', to_base=6,      base_unit='TEASPOONS', measurement_type='VOLUME'))
    facts.append(Fact(fact_title='unit_conversion', unit='CUPS',         to_base=48,     base_unit='TEASPOONS', measurement_type='VOLUME'))
    facts.append(Fact(fact_title='unit_conversion', unit='PINTS',        to_base=96,     base_unit='TEASPOONS', measurement_type='VOLUME'))
    facts.append(Fact(fact_title='unit_conversion', unit='QUARTS',       to_base=192,    base_unit='TEASPOONS', measurement_type='VOLUME'))
    facts.append(Fact(fact_title='unit_conversion', unit='GALLONS',      to_base=768,    base_unit='TEASPOONS', measurement_type='VOLUME'))
    
    facts.append(Fact(fact_title='unit_conversion', unit='OUNCES',       to_base=1,      base_unit='OUNCES',    measurement_type='WEIGHT'))
    facts.append(Fact(fact_title='unit_conversion', unit='POUNDS',       to_base=16,     base_unit='OUNCES',    measurement_type='WEIGHT'))
    
    facts.append(Fact(fact_title='unit_conversion', unit='WHOLE',        to_base=1,      base_unit='WHOLE',     measurement_type='WHOLE'))
    facts.append(Fact(fact_title='unit_conversion', unit='DOZEN',        to_base=12,     base_unit='WHOLE',     measurement_type='WHOLE'))
    facts.append(Fact(fact_title='unit_conversion', unit='SCORE',        to_base=20,     base_unit='WHOLE',     measurement_type='WHOLE'))
    
    return facts