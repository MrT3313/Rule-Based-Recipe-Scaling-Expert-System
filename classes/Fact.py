class Fact:
    def __init__(self, fact_title, **attributes):
        self.fact_title = fact_title
        self.attributes = attributes

        self.fact_id = None
        self.derived_from = []
        self.derived_by_rule = None
        self.derived_at_cycle = None
    
    def set_derivation(self, fact_id, derived_by_rule=None, derived_at_cycle=None, derived_from=None):
        self.fact_id = fact_id
        self.derived_by_rule = derived_by_rule
        self.derived_at_cycle = derived_at_cycle
        if derived_from:
            self.derived_from = derived_from
    
    def __repr__(self):
        attrs = ', '.join(f"{k}={v}" for k, v in self.attributes.items())
        if self.fact_id is not None:
            return f"Fact #{self.fact_id} ('{self.fact_title}', {attrs})"
        return f"Fact ('{self.fact_title}', {attrs})"
    
    def get(self, key, default=None):
        return self.attributes.get(key, default)