class KnowledgeBase:
    """Stores permanent rules and reference facts"""
    def __init__(self):
        self.rules = []
        self.reference_facts = []  # Static facts like conversion rates
    
    def add_rule(self, *, rule):
        """Add a rule to the knowledge base"""
        self.rules.extend(rule)

    def add_reference_fact(self, *, fact):
        """Add permanent domain knowledge"""
        self.reference_facts.extend(fact)