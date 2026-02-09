from classes.Fact import Fact
from classes.NegatedFact import NegatedFact


class ScalingEngine:
    def __init__(self, *, wm, kb, conflict_resolution_strategy='priority', verbose=True):
        self.working_memory = wm
        self.knowledge_base = kb
        self.conflict_resolution_strategy = conflict_resolution_strategy
        self.verbose = verbose
        self.cycle = 0

    def run(self):
        # Snapshot recipe_ingredient facts — these are the triggers
        # triggers = self.working_memory.facts
        triggers = [f for f in self.working_memory.facts]

        # for trigger in self.working_memory.facts:
        for trigger in triggers:
            self._forward_chain(trigger_fact=trigger)

    def _forward_chain(self, *, trigger_fact):
        """Find matching rules for a trigger fact, resolve conflict, fire via DFS.
        Uses a while-loop to exhaust all matches for the trigger.
        Returns (any_rule_fired, last_derived_fact)."""
        self.cycle += 1
        last_derived = None
        any_rule_fired = False
        fired = set()

        print("")
        print(f'🔁 CYCLE: {self.cycle}')
        print(f'🧠 CURRENT WORKING MEMORY ({len(self.working_memory.facts)})\n')
        for fact in self.working_memory.facts:
            print(f"\t{fact}")
        print('###############################################################################')

        matches = self._find_matching_rules(trigger_fact=trigger_fact)
        print("")
        print(f"🧠 Matches Found {len(matches)}")
        if not matches:
            print(f"No rules matched trigger - nothing new added to working memory")
        while matches:
            wm_size = len(self.working_memory.facts)

            # Filter out already-fired matches
            fresh = []
            for m_rule, m_bindings in matches:
                binding_key = frozenset(
                    (k, v) for k, v in m_bindings.items()
                    if isinstance(k, str) and k.startswith('?')
                )
                has_negated = any(
                    isinstance(a, NegatedFact) for a in m_rule.antecedents
                )
                if has_negated:
                    key = (m_rule.rule_name, wm_size, binding_key)
                else:
                    key = (m_rule.rule_name, binding_key)
                if key not in fired:
                    fresh.append((m_rule, m_bindings, key))
            if not fresh:
                break

            best_rule, best_bindings, fire_key = self._resolve_conflict(matches=fresh)
            fired.add(fire_key)

            any_rule_fired = True
            derived = self._fire_rule_dfs(rule=best_rule, bindings=best_bindings)
            if derived is not None:
                last_derived = derived

            # Re-evaluate: new facts may have changed what matches
            matches = self._find_matching_rules(trigger_fact=trigger_fact)
            print("")
            print(f"🧠 Matches Found {len(matches)}")

        return (any_rule_fired, last_derived)

    def _find_matching_rules(self, *, trigger_fact):
        """Return all (rule, bindings) pairs whose antecedents are satisfied.
        Uses trigger_fact as a cheap filter: only consider rules where at least one
        positive antecedent unifies with the trigger."""
        matches = []
        for rule in self.knowledge_base.rules:
            print("")
            print(f'👀 Attempting to match: \trule "{rule.rule_name}" 👉 fact "{trigger_fact.fact_title}"')

            for ant_idx, antecedent in enumerate(rule.antecedents):
                if isinstance(antecedent, NegatedFact):
                    continue

                initial_bindings = self._unify(pattern=antecedent, fact=trigger_fact, bindings={})
                if initial_bindings is None:
                    print(f'❌ Match Failed')
                    break
                    # continue

                initial_bindings['_matched_facts'] = [trigger_fact]

                # Anchor: this antecedent binds to trigger_fact.
                # Match remaining antecedents against all KB + WM facts.
                remaining = rule.antecedents[:ant_idx] + rule.antecedents[ant_idx + 1:]
                bindings_list = self._match_antecedents(antecedents=remaining, bindings=initial_bindings)
                if not bindings_list:
                    print(f'❌ Match Failed')
                for bindings in bindings_list:
                    if (rule, bindings) not in matches:
                        print(f'✅ Match succeeded')
                        matches.append((rule, bindings))
                break  # Only anchor to first matching antecedent per rule

        return matches

    def _match_antecedents(self, *, antecedents, bindings):
        """Recursively match a list of antecedents against KB reference facts + WM facts.
        Returns all valid binding sets. Handles NegatedFact via negation-as-failure."""
        if not antecedents:
            return [bindings]

        first = antecedents[0]
        rest = antecedents[1:]
        all_facts = self.knowledge_base.reference_facts + self.working_memory.facts

        if isinstance(first, NegatedFact):
            pattern = first.fact
            for fact in all_facts:
                if self._unify(pattern=pattern, fact=fact, bindings=bindings) is not None:
                    return []
            return self._match_antecedents(antecedents=rest, bindings=bindings)

        results = []
        for fact in all_facts:
            new_bindings = self._unify(pattern=first, fact=fact, bindings=bindings)
            if new_bindings is not None:
                new_bindings['_matched_facts'] = bindings.get('_matched_facts', []) + [fact]
                sub_results = self._match_antecedents(antecedents=rest, bindings=new_bindings)
                results.extend(sub_results)
        return results

    def _unify(self, *, pattern, fact, bindings):
        """Try to match one antecedent pattern against one fact.
        Returns updated bindings dict or None on failure."""
        if pattern.fact_title != fact.fact_title:
            return None

        new_bindings = bindings.copy()

        for key, pattern_value in pattern.attributes.items():
            if key not in fact.attributes:
                return None

            fact_value = fact.attributes[key]

            if isinstance(pattern_value, str) and pattern_value.startswith('?'):
                if pattern_value in new_bindings:
                    if new_bindings[pattern_value] != fact_value:
                        return None
                else:
                    new_bindings[pattern_value] = fact_value
            else:
                if pattern_value != fact_value:
                    return None

        return new_bindings

    def _apply_bindings(self, *, fact_template, bindings):
        """Substitute ?variables in a consequent template with concrete values from bindings."""
        new_attrs = {}
        for key, value in fact_template.attributes.items():
            if isinstance(value, str) and value.startswith('?'):
                if value in bindings:
                    new_attrs[key] = bindings[value]
                else:
                    new_attrs[key] = value
            else:
                new_attrs[key] = value
        return Fact(fact_title=fact_template.fact_title, **new_attrs)

    def _fact_exists(self, *, fact):
        """Check if an identical fact is already in working memory."""
        for existing in self.working_memory.facts:
            if existing.fact_title == fact.fact_title and existing.attributes == fact.attributes:
                return True
        return False

    def _resolve_conflict(self, *, matches):
        """Pick the best (rule, bindings, fire_key) from a list.
        Supports priority (default) and specificity strategies."""
        if self.conflict_resolution_strategy == "specificity":
            return max(matches, key=lambda x: len(x[0].antecedents))
        return max(matches, key=lambda x: x[0].priority)

    def _fire_rule_dfs(self, *, rule, bindings):
        """Fire a rule: run action_fn if present, then derive consequent.
        DFS: if the derived fact triggers further rules, fire them recursively
        via a while-loop with explicit fired-set tracking."""
        matched_facts = bindings.get('_matched_facts', [])
        derivation = {'rule_name': rule.rule_name, 'antecedent_facts': list(matched_facts)}
        prev_derivation = self.working_memory._current_derivation
        self.working_memory._current_derivation = derivation

        if rule.action_fn:
            bindings = rule.action_fn(bindings=bindings, wm=self.working_memory, kb=self.knowledge_base)

        if rule.consequent is not None:
            derived = self._apply_bindings(fact_template=rule.consequent, bindings=bindings)
            if not self._fact_exists(fact=derived):
                derived.derivation = derivation

                if self.verbose:
                    print(f"[Rule fired] {rule.rule_name} -> {derived}")

                self.working_memory.add_fact(fact=derived, silent=not self.verbose)
            else:
                if self.verbose:
                    print(f"[Rule fired] {rule.rule_name} -> No new WM assertions (fact already exists)")

            self.working_memory._current_derivation = prev_derivation

            # DFS: chase rules triggered by the derived fact
            fired = set()
            chain_matches = self._find_matching_rules(trigger_fact=derived)

            print("")
            print(f"🧠 Matches Found {len(chain_matches)}")
            while chain_matches:
                wm_size = len(self.working_memory.facts)

                fresh = []
                for m_rule, m_bindings in chain_matches:
                    binding_key = frozenset(
                        (k, v) for k, v in m_bindings.items()
                        if isinstance(k, str) and k.startswith('?')
                    )
                    has_negated = any(
                        isinstance(a, NegatedFact) for a in m_rule.antecedents
                    )
                    if has_negated:
                        key = (m_rule.rule_name, wm_size, binding_key)
                    else:
                        key = (m_rule.rule_name, binding_key)
                    if key not in fired:
                        fresh.append((m_rule, m_bindings, key))
                if not fresh:
                    break

                best_chain_rule, best_chain_bindings, fire_key = self._resolve_conflict(matches=fresh)
                fired.add(fire_key)

                self._fire_rule_dfs(rule=best_chain_rule, bindings=best_chain_bindings)

                chain_matches = self._find_matching_rules(trigger_fact=derived)
                print("")
                print(f"🧠 Matches Found {len(chain_matches)}")

            return derived
        else:
            print(f"👀 No new WM assertions")

        self.working_memory._current_derivation = prev_derivation
        return None
