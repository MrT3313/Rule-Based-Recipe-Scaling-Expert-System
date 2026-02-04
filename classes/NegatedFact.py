from classes.Fact import Fact


class NegatedFact:
    def __init__(self, *, fact_title, **attributes):
        self.fact = Fact(fact_title=fact_title, **attributes)
        self.is_negated = True
    
    def __repr__(self):
        return f"NOT {self.fact}"
