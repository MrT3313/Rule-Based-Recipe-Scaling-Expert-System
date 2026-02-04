from classes.InfrenceEngines.InferenceEngine import InferenceEngine


class ScalingEngine(InferenceEngine):
    def __init__(self, *, wm, kb, conflict_resolution_strategy='priority', verbose=True):
        super().__init__(wm=wm, kb=kb, conflict_resolution_strategy=conflict_resolution_strategy, verbose=verbose)

    def _resolve_conflict(self, *, matches):
        # TODO: should this be a rule we fetch from wm instead of a key:value on the ScalingEngine class?
        if self.conflict_resolution_strategy == "specificity":
            # match based on the most antecedents
            return max(matches, key=lambda x: len(x[0].antecedents))
        if self.conflict_resolution_strategy == "recency":
            # match based on the most recently derived fact (highest fact_id
            return max(
                matches,
                key=lambda x: max(
                    (f.fact_id for f in x[2] if f.fact_id is not None), default=0
                ),
            )
        # (default) match based on rule priority
        return max(matches, key=lambda x: x[0].priority)

    def run(self):
        self.cycle_count = 0

        if self.verbose:
            print("=" * 70)
            print("STARTING FORWARD CHAINING INFERENCE ENGINE (DFS)")
            print("=" * 70)
            print("")

        while True:
            self.cycle_count += 1

            if self.verbose:
                print(f"--- Cycle {self.cycle_count} ---")

            rules_fired = self._fire_rules_dfs()

            if not rules_fired:
                if self.verbose:
                    print("No rules can fire. Inference complete.")
                break

        if self.verbose:
            print("")
            print(f"Inference complete after {self.cycle_count} cycles")
            print(f"Working memory now contains {len(self.working_memory.facts)} facts")