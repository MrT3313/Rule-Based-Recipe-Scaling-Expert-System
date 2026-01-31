class WorkingMemory:
    def __init__(self):
        self.facts = []
        self.next_fact_id = 1

    def add_fact(self, fact, indent="", silent=False):
        fact.set_fact_id(self.next_fact_id)
        self.facts.append(fact)
        self.next_fact_id += 1
        if not silent:
            print(f"{indent}[Asserted] {fact}")
