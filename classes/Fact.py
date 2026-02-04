class Fact:
    def __init__(self, fact_title, **attributes):
        self.fact_title = fact_title
        self.attributes = attributes

        self.fact_id = None
    
    def __repr__(self):
        attrs = ', '.join(f"{k}={v}" for k, v in self.attributes.items())
        if self.fact_id is not None:
            return f"Fact #{self.fact_id} ('{self.fact_title}', {attrs})"
        return f"Fact ('{self.fact_title}', {attrs})"
    
    def get(self, key, default=None):
        return self.attributes.get(key, default)

    def set_fact_id(self, fact_id):
        self.fact_id = fact_id