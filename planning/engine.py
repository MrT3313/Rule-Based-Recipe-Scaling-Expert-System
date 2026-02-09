from classes.Fact import Fact
from classes.NegatedFact import NegatedFact


class PlanningEngine:
    def __init__(self, *, wm, kb, verbose=True):
        self.working_memory = wm
        self.knowledge_base = kb
        self.verbose = verbose
        self.cycle = 0

    def run(self, *, recipe):
        self.plan = []
        self.recipe = recipe
        self.last_error = None

        for idx, step in enumerate(recipe.steps):
            if self.verbose:
                print(f"\nStep {idx + 1}: {step.description}")

            # Resolve all equipment for this step
            resolved_equipment = []
            for equipment_need in step.required_equipment:
                resolved_list = self._resolve_equipment(equipment_need=equipment_need)
                if resolved_list is not None:
                    for eq in resolved_list:
                        if self.verbose:
                            print(f"  -> Resolved: {eq}")
                        resolved_equipment.append(eq)
                else:
                    equipment_name = equipment_need.get('equipment_name', equipment_need)
                    if self.verbose:
                        print(f"  -> FAILED to resolve equipment: {equipment_name}")
                    return (False, f"{equipment_name} could not be resolved")

            self._current_resolved_equipment = resolved_equipment

            # Boundary translation: Step object -> step_request Fact
            step_request = self._build_step_request(step=step, step_idx=idx, resolved_equipment=resolved_equipment)
            self.working_memory.add_fact(fact=step_request)

            # Forward-chain: orchestration rules handle dispatch + execution
            step_type = step_request.attributes['step_type']
            rule_fired, _ = self._forward_chain(trigger_fact=step_request)

            # Error check
            if self.last_error:
                return (False, self.last_error)

            # Check that a non-GENERIC step was handled by at least one rule
            if step_type != 'GENERIC' and not rule_fired:
                return (False, f"No rule matched for step {idx}: {step_type} ({step.description})")

            # For generic steps (no dispatch rule matched), handle directly
            if step_type == 'GENERIC':
                # Transition resolved equipment from RESERVED -> IN_USE
                for eq in resolved_equipment:
                    eq.attributes['state'] = 'IN_USE'
                    if self.verbose:
                        print(f"  -> {eq.attributes['equipment_name']} #{eq.attributes['equipment_id']} is now IN_USE")
                self.plan.append(step)

        return (True, self.plan)

    def _build_step_request(self, *, step, step_idx, resolved_equipment):
        """Convert a recipe Step object to a step_request Fact for rule-based dispatch.
        Uses step_type class attribute for base classification, with attribute-based
        overrides for context-dependent types (EQUIPMENT_REMOVAL, ITEM_TRANSFER_TO_SURFACE)."""

        base_type = getattr(step, 'step_type', 'GENERIC')

        # Attribute-based overrides for context-dependent classification
        if base_type == 'TRANSFER_EQUIPMENT' and step.source_equipment_name != 'BAKING_SHEET':
            base_type = 'EQUIPMENT_REMOVAL'
        elif base_type == 'TRANSFER_ITEM' and step.target_equipment_name == 'COOLING_RACK':
            base_type = 'ITEM_TRANSFER_TO_SURFACE'

        # MIXING needs extra equipment info in the step_request
        if base_type == 'MIXING':
            target_equipment = None
            for eq in resolved_equipment:
                if eq.attributes.get('equipment_type') == 'CONTAINER':
                    target_equipment = eq
                    break

            if target_equipment is None:
                return Fact(
                    fact_title='step_request',
                    step_type='MIXING',
                    step_idx=step_idx,
                    equipment_name='UNKNOWN',
                    equipment_id=0,
                    equipment_volume=0,
                    equipment_volume_unit='',
                )

            # Transition resolved equipment from RESERVED -> IN_USE
            for eq in resolved_equipment:
                eq.attributes['state'] = 'IN_USE'
                if self.verbose:
                    print(f"  -> {eq.attributes['equipment_name']} #{eq.attributes['equipment_id']} is now IN_USE")

            return Fact(
                fact_title='step_request',
                step_type='MIXING',
                step_idx=step_idx,
                equipment_name=target_equipment.attributes['equipment_name'],
                equipment_id=target_equipment.attributes['equipment_id'],
                equipment_volume=target_equipment.attributes.get('volume', 0),
                equipment_volume_unit=target_equipment.attributes.get('volume_unit', ''),
            )

        return Fact(
            fact_title='step_request',
            step_type=base_type,
            step_idx=step_idx,
        )

    def _forward_chain(self, *, trigger_fact):
        """Find matching rules for a trigger fact, resolve conflict, fire via DFS.
        Uses a while-loop to exhaust all matches for the trigger (e.g., T1 fires
        once per mixed_contents source). Returns (rule_fired, last_derived_fact).
        Sets self.last_error on failure."""
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
            if self.last_error:
                break

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

            best_idx = max(
                range(len(fresh)),
                key=lambda i: fresh[i][0].priority,
            )
            best_rule, best_bindings, fire_key = fresh[best_idx]
            fired.add(fire_key)

            self._last_bindings = best_bindings
            any_rule_fired = True
            derived = self._fire_rule_dfs(rule=best_rule, bindings=best_bindings)
            if '?error' in best_bindings:
                self.last_error = best_bindings['?error']
            if derived is not None:
                last_derived = derived

            if self.last_error:
                break

            # Re-evaluate: new facts may have changed what matches
            matches = self._find_matching_rules(trigger_fact=trigger_fact)
            print("")
            print(f"🧠 Matches Found {len(matches)}")

        return (any_rule_fired, last_derived)

    def _resolve_equipment(self, *, equipment_need):
        """Resolve required_count pieces of equipment, returning a list or None on failure."""
        equipment_name = equipment_need.get('equipment_name')
        required_count = equipment_need.get('required_count', 1)
        resolved = []

        for _ in range(required_count):
            # 1. Look for AVAILABLE equipment
            available = self.working_memory.query_equipment(
                equipment_name=equipment_name,
                first=True,
                state='AVAILABLE',
            )
            if available:
                available.attributes['state'] = 'RESERVED'
                resolved.append(available)
                continue

            # 2. Look for DIRTY equipment and try to clean it via rules
            dirty = self.working_memory.query_equipment(
                equipment_name=equipment_name,
                first=True,
                state='DIRTY',
            )
            if dirty:
                matches = self._find_matching_rules(trigger_fact=dirty)
                if matches:
                    best_rule, best_bindings = self._resolve_conflict(matches=matches)
                    best_bindings['reserve_after_cleaning'] = True
                    derived = self._fire_rule_dfs(rule=best_rule, bindings=best_bindings)
                    if self.verbose:
                        print(f"    [Rule fired] {best_rule.rule_name} -> updated Fact #{dirty.fact_id}")
                        if derived is not None:
                            print(f"    [Rule fired] {best_rule.rule_name} -> derived {derived}")
                    resolved.append(dirty)
                    continue

            # Not enough equipment available
            return None

        return resolved

    def _match_antecedents(self, *, antecedents, bindings):
        """Recursively match a list of antecedents against ALL facts in WM + KB.
        Returns all valid binding sets. Handles NegatedFact via negation-as-failure."""
        if not antecedents:
            return [bindings]

        first = antecedents[0]
        rest = antecedents[1:]
        all_facts = self.working_memory.facts

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

    def _find_matching_rules(self, *, trigger_fact):
        """Return all (rule, bindings) pairs whose antecedents are satisfied.
        Uses trigger_fact as a cheap filter: only consider rules where at least one
        positive antecedent unifies with the trigger. Then do full multi-antecedent
        matching, but anchor one antecedent to the trigger fact specifically."""
        matches = []
        for rule in self.knowledge_base.rules:
            print("")
            print(f'👀 Attempting to match: \trule "{rule.rule_name}" 👉 fact "{trigger_fact.fact_title}"')

            # Find which positive antecedent(s) unify with trigger_fact
            for ant_idx, antecedent in enumerate(rule.antecedents):
                if isinstance(antecedent, NegatedFact):
                    continue

                initial_bindings = self._unify(pattern=antecedent, fact=trigger_fact, bindings={})
                if initial_bindings is None:
                    print(f'❌ Match Failed')
                    break
                    # continue

                initial_bindings['_matched_facts'] = [trigger_fact]

                # Anchor: this antecedent MUST bind to trigger_fact.
                # Match remaining antecedents against all WM facts.
                remaining = rule.antecedents[:ant_idx] + rule.antecedents[ant_idx + 1:]
                bindings_list = self._match_antecedents(antecedents=remaining, bindings=initial_bindings)
                if not bindings_list:
                    print(f'❌ Match Failed')
                for bindings in bindings_list:
                    # Deduplicate: avoid adding the same bindings twice
                    if (rule, bindings) not in matches:
                        print(f'✅ Match succeeded')
                        matches.append((rule, bindings))
                break  # Only anchor to first matching antecedent per rule

        return matches

    def _fact_exists(self, *, fact):
        """Check if an identical fact is already in working memory."""
        for existing in self.working_memory.facts:
            if existing.fact_title == fact.fact_title and existing.attributes == fact.attributes:
                return True
        return False

    def _unify(self, *, pattern, fact, bindings):
        """Try to match one antecedent pattern against one fact.
        Returns updated bindings dict or None on failure. Pure function."""
        if pattern.fact_title != fact.fact_title:
            return None

        new_bindings = bindings.copy()

        for key, pattern_value in pattern.attributes.items():
            if key not in fact.attributes:
                return None

            fact_value = fact.attributes[key]

            if isinstance(pattern_value, str) and pattern_value.startswith('?'):
                # Variable — check consistency or bind
                if pattern_value in new_bindings:
                    if new_bindings[pattern_value] != fact_value:
                        return None
                else:
                    new_bindings[pattern_value] = fact_value
            else:
                # Literal — must match exactly
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
                    new_attrs[key] = value  # leave unbound variables as-is
            else:
                new_attrs[key] = value
        return Fact(fact_title=fact_template.fact_title, **new_attrs)

    def _fire_rule_dfs(self, *, rule, bindings, plan_override=None):
        """Fire a rule: run action_fn if present, then derive consequent if present.
        DFS: if the derived fact triggers further rules, fire them recursively.
        After DFS chaining on a consequent, re-evaluate matches for the derived fact
        to enable data-driven iteration (e.g., processing multiple pending_ingredient facts)."""
        matched_facts = bindings.get('_matched_facts', [])
        derivation = {'rule_name': rule.rule_name, 'antecedent_facts': list(matched_facts)}
        prev_derivation = self.working_memory._current_derivation
        self.working_memory._current_derivation = derivation

        if rule.action_fn:
            target_plan = plan_override if plan_override is not None else self.plan
            bindings['_engine'] = self  # orchestration rules use this
            bindings = rule.action_fn(bindings=bindings, wm=self.working_memory, kb=self.knowledge_base, plan=target_plan)

        # Skip consequent if action_fn signaled an error
        if '?error' in bindings:
            self.last_error = bindings['?error']
            self.working_memory._current_derivation = prev_derivation
            return None

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

            # DFS: check if derived fact triggers further rules.
            # Track fired (rule_name, bindings) to prevent re-firing the same match.
            # Rules with NegatedFact antecedents can re-fire with same bindings when
            # WM changes (the negated guard may flip), so include wm_size in their key.
            fired = set()
            chain_matches = self._find_matching_rules(trigger_fact=derived)
            print("")
            print(f"🧠 Matches Found {len(chain_matches)}")
            while chain_matches:
                if self.last_error:
                    break

                wm_size = len(self.working_memory.facts)

                # Filter out already-fired matches
                fresh = []
                for m_rule, m_bindings in chain_matches:
                    binding_key = frozenset(
                        (k, v) for k, v in m_bindings.items()
                        if isinstance(k, str) and k.startswith('?')
                    )
                    # Rules with NegatedFact guards may validly re-fire when WM
                    # changes (e.g., T2 iterates sheets via NOT all_sheets_transferred).
                    # Include wm_size so new WM state = fresh firing chance.
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

                best_idx = max(
                    range(len(fresh)),
                    key=lambda i: fresh[i][0].priority,
                )
                best_chain_rule, best_chain_bindings, fire_key = fresh[best_idx]
                fired.add(fire_key)

                self._fire_rule_dfs(rule=best_chain_rule, bindings=best_chain_bindings, plan_override=plan_override)

                if self.last_error:
                    break

                # Re-evaluate: new facts may enable new matches for the derived trigger
                chain_matches = self._find_matching_rules(trigger_fact=derived)
                print("")
                print(f"🧠 Matches Found {len(chain_matches)}")

            return derived
        else:
            print(f"👀 No new WM assertions")

        self.working_memory._current_derivation = prev_derivation
        return None

    def _resolve_conflict(self, *, matches):
        """Pick the best (rule, bindings) from a list. Priority-based."""
        return max(matches, key=lambda x: x[0].priority)
