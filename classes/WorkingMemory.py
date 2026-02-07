class WorkingMemory:
    def __init__(self):
        self.facts = []
        self.next_fact_id = 1

    def add_fact(self, *, fact, indent="", silent=False):
        fact.set_fact_id(fact_id=self.next_fact_id)
        self.facts.append(fact)
        self.next_fact_id += 1
        if not silent:
            print(f"{indent}[Asserted] {fact}")

    def remove_fact(self, *, fact, indent="", silent=False):
        if fact in self.facts:
            self.facts.remove(fact)
            if not silent:
                print(f"{indent}[Retracted] {fact}")

    def query_equipment(self, *, equipment_name, first=False, **attributes):
        results = []
        
        for fact in self.facts:
            if (
                    fact.fact_title == 'EQUIPMENT' and
                    fact.attributes.get('equipment_name') == equipment_name and
                    all(fact.attributes.get(key) == value for key, value in attributes.items())
            ):
                if first:
                    return fact
                else:
                    results.append(fact)
        
        if first:
            return None
        else:
            return results
    
    def query_facts(self, *, fact_title, first=False, **attributes):
        results = []

        for fact in self.facts:
            if (
                    fact.fact_title == fact_title and
                    all(fact.attributes.get(key) == value for key, value in attributes.items())
            ):
                if first:
                    return fact
                else:
                    results.append(fact)

        if first:
            return None
        else:
            return results

    def query_equipment_state(self, *, equipment_name, equipment_id):
        for fact in self.facts:
            if (
                    fact.fact_title == 'EQUIPMENT' and
                    fact.attributes.get('equipment_name') == equipment_name and
                    fact.attributes.get('equipment_id') == equipment_id
            ):
                return fact.attributes.get('state')
        return None
