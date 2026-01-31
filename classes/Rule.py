class Rule:
    def __init__(self, antecedents, consequent, priority=0, rule_name=None):
        self.antecedents = antecedents
        self.consequent = consequent
        self.priority = priority
        self.rule_name = rule_name
    
    def __repr__(self):
        return f"Rule('{self.rule_name}', priority={self.priority}, antecedents={len(self.antecedents)})"
