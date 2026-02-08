class ExplanationFacility:
    def __init__(self, *, wm, kb, label):
        self.wm = wm
        self.kb = kb
        self.label = label

    def run_repl(self):
        print("")
        print("=" * 70)
        print(f"EXPLANATION FACILITY ({self.label})")
        print("=" * 70)
        print("")
        print(f"Facts in working memory: {len(self.wm.facts)}")
        for fact in self.wm.facts:
            print(f"\t{fact}")
        print("")

        while True:
            try:
                user_input = input(f"🔎🔎 {self.label.upper()} ENGINE EXPLANATION FACILITY 🔎🔎\n{len(self.wm.facts)} Working Memory Facts\nEnter a fact number to explain (or 'c' to continue): ").strip()
            except (EOFError, KeyboardInterrupt):
                print("")
                break

            if user_input.lower() in ('c', 'continue', 'q', 'quit'):
                break

            try:
                fact_id = int(user_input)
            except ValueError:
                print(f"Invalid input: '{user_input}'. Enter a fact number or 'c'.")
                continue

            fact = self._find_fact(fact_id)
            if fact is None:
                print(f"No fact with ID #{fact_id} found.")
                continue

            print("")
            self._print_derivation(fact, indent=0)
            print("")

    def _find_fact(self, fact_id):
        for fact in self.wm.facts:
            if fact.fact_id == fact_id:
                return fact
        return None

    def _print_derivation(self, fact, indent=0):
        prefix = "\t" * indent
        connector = "+-- " if indent > 0 else ""

        if fact.derivation is None:
            leaf_label = self._classify_leaf(fact)
            print(f"{prefix}{connector}{fact}  [{leaf_label}]")
            return

        rule_name = fact.derivation['rule_name']
        antecedent_facts = fact.derivation['antecedent_facts']

        print(f"{prefix}{connector}{fact}")
        print(f"{prefix}    derived by rule: '{rule_name}'")

        if antecedent_facts:
            print(f"{prefix}    antecedents:")
            for ant_fact in antecedent_facts:
                self._print_derivation(ant_fact, indent=indent + 1)

    def _classify_leaf(self, fact):
        for ref in self.kb.reference_facts:
            if ref.fact_title == fact.fact_title and ref.attributes == fact.attributes:
                return "REFERENCE"
        return "INPUT"
