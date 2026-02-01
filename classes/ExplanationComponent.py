class ExplanationComponent:
    def __init__(self, working_memory):
        self.working_memory = working_memory

    def _find_fact(self, fact_id):
        for fact in self.working_memory.facts:
            if fact.fact_id == fact_id:
                return fact
        return None

    def _collect_derivation_facts(self, fact_id, collected=None):
        if collected is None:
            collected = {}
        fact = self._find_fact(fact_id)
        if fact is None or fact_id in collected:
            return collected
        collected[fact_id] = fact
        for f in fact.derived_from:
            if f.fact_id is not None:
                self._collect_derivation_facts(f.fact_id, collected)
        return collected

    def get_derivation(self, fact_id):
        fact = self._find_fact(fact_id)
        if fact is None:
            return None
        derived_from = []
        for f in fact.derived_from:
            if f.fact_id is not None:
                derived_from.append({"fact_id": f.fact_id, "repr": repr(f)})
            else:
                derived_from.append({"fact_id": "reference", "repr": repr(f)})
        return {
            "fact_id": fact_id,
            "rule": fact.derived_by_rule,
            "cycle": fact.derived_at_cycle,
            "derived_from": derived_from,
        }

    def explain(self, fact_id):
        fact = self._find_fact(fact_id)
        if fact is None:
            return f"Fact #{fact_id} not found."
        facts_in_chain = self._collect_derivation_facts(fact_id)
        given = [
            (fid, f) for fid, f in facts_in_chain.items()
            if f.derived_by_rule is None
        ]
        derived = [
            (fid, f) for fid, f in facts_in_chain.items()
            if f.derived_by_rule is not None
        ]
        derived.sort(key=lambda x: (x[1].derived_at_cycle, x[0]))
        given.sort(key=lambda x: x[0])
        order = [(fid, f) for fid, f in given] + [
            (fid, f) for fid, f in derived
        ]
        lines = []
        for fid, f in order:
            if f.derived_by_rule is None:
                lines.append(f"Fact #{fid} (given): {f}")
            else:
                lines.append(
                    f"Fact #{fid} was derived at cycle {f.derived_at_cycle} "
                    f"by rule '{f.derived_by_rule}'"
                )
                lines.append("  antecedents:")
                for sup in f.derived_from:
                    if sup.fact_id is not None:
                        lines.append("    WM antecedent: " + repr(sup))
                    else:
                        lines.append("    KB antecedent: " + repr(sup))
        return "\n".join(lines)
