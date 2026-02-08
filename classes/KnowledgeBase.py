class KnowledgeBase:
    """Stores permanent rules and reference facts"""
    def __init__(self):
        self.rules = []
        self.reference_facts = []  # Static facts like conversion rates
    
    def add_rules(self, *, rules):
        """Add a rule to the knowledge base"""
        self.rules.extend(rules)

    def add_reference_facts(self, *, facts):
        """Add permanent domain knowledge"""
        self.reference_facts.extend(facts)