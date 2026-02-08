import pytest

from classes.Fact import Fact
from classes.NegatedFact import NegatedFact
from classes.Rule import Rule
from classes.KnowledgeBase import KnowledgeBase
from classes.WorkingMemory import WorkingMemory
from scaling.engine import ScalingEngine


def _make_engine(*, wm_facts=None, kb_rules=None, kb_ref_facts=None):
    wm = WorkingMemory()
    kb = KnowledgeBase()
    for f in (wm_facts or []):
        wm.add_fact(fact=f, silent=True)
    if kb_ref_facts:
        kb.add_reference_facts(facts=kb_ref_facts)
    if kb_rules:
        kb.add_rules(rules=kb_rules)
    return ScalingEngine(wm=wm, kb=kb, verbose=False)


# ── _unify ────────────────────────────────────────────────────────────

class TestUnify:
    def test_variable_binding(self):
        engine = _make_engine()
        pattern = Fact(fact_title='ingredient', name='?n')
        fact = Fact(fact_title='ingredient', name='SALT')
        result = engine._unify(pattern, fact, {})
        assert result == {'?n': 'SALT'}

    def test_literal_match(self):
        engine = _make_engine()
        pattern = Fact(fact_title='ingredient', name='SALT')
        fact = Fact(fact_title='ingredient', name='SALT')
        result = engine._unify(pattern, fact, {})
        assert result == {}

    def test_literal_mismatch(self):
        engine = _make_engine()
        pattern = Fact(fact_title='ingredient', name='SUGAR')
        fact = Fact(fact_title='ingredient', name='SALT')
        assert engine._unify(pattern, fact, {}) is None

    def test_title_mismatch(self):
        engine = _make_engine()
        pattern = Fact(fact_title='a', name='?n')
        fact = Fact(fact_title='b', name='SALT')
        assert engine._unify(pattern, fact, {}) is None

    def test_binding_consistency(self):
        engine = _make_engine()
        pattern = Fact(fact_title='pair', x='?v', y='?v')
        fact = Fact(fact_title='pair', x=1, y=1)
        assert engine._unify(pattern, fact, {}) == {'?v': 1}

    def test_binding_inconsistency(self):
        engine = _make_engine()
        pattern = Fact(fact_title='pair', x='?v', y='?v')
        fact = Fact(fact_title='pair', x=1, y=2)
        assert engine._unify(pattern, fact, {}) is None

    def test_existing_bindings_preserved(self):
        engine = _make_engine()
        pattern = Fact(fact_title='item', name='?n')
        fact = Fact(fact_title='item', name='SALT')
        result = engine._unify(pattern, fact, {'?other': 42})
        assert result == {'?other': 42, '?n': 'SALT'}

    def test_missing_attribute_in_fact(self):
        engine = _make_engine()
        pattern = Fact(fact_title='item', name='?n', extra='?e')
        fact = Fact(fact_title='item', name='SALT')
        assert engine._unify(pattern, fact, {}) is None


# ── _match_antecedents ────────────────────────────────────────────────

class TestMatchAntecedents:
    def test_matches_kb_reference_facts(self):
        ref = Fact(fact_title='classification', name='SALT', cls='SEASONING')
        engine = _make_engine(kb_ref_facts=[ref])
        pattern = Fact(fact_title='classification', name='?n', cls='?c')
        results = engine._match_antecedents([pattern], {})
        assert len(results) == 1
        assert results[0]['?n'] == 'SALT'
        assert results[0]['?c'] == 'SEASONING'

    def test_matches_wm_facts(self):
        wm_fact = Fact(fact_title='ingredient', name='SALT')
        engine = _make_engine(wm_facts=[wm_fact])
        pattern = Fact(fact_title='ingredient', name='?n')
        results = engine._match_antecedents([pattern], {})
        assert len(results) == 1
        assert results[0]['?n'] == 'SALT'

    def test_matches_across_kb_and_wm(self):
        """Two antecedents: one matches KB, one matches WM."""
        ref = Fact(fact_title='classification', name='SALT', cls='SEASONING')
        wm_fact = Fact(fact_title='recipe_ingredient', ingredient_name='SALT')
        engine = _make_engine(wm_facts=[wm_fact], kb_ref_facts=[ref])

        antecedents = [
            Fact(fact_title='recipe_ingredient', ingredient_name='?n'),
            Fact(fact_title='classification', name='?n', cls='?c'),
        ]
        results = engine._match_antecedents(antecedents, {})
        assert len(results) == 1
        assert results[0]['?n'] == 'SALT'
        assert results[0]['?c'] == 'SEASONING'

    def test_negated_fact_blocks(self):
        wm_fact = Fact(fact_title='classified', name='SALT')
        engine = _make_engine(wm_facts=[wm_fact])
        antecedents = [NegatedFact(fact_title='classified', name='SALT')]
        results = engine._match_antecedents(antecedents, {})
        assert results == []

    def test_negated_fact_passes(self):
        engine = _make_engine()
        antecedents = [NegatedFact(fact_title='classified', name='SALT')]
        results = engine._match_antecedents(antecedents, {})
        assert len(results) == 1

    def test_negated_fact_with_variable(self):
        """NegatedFact with a bound variable should block when matching fact exists."""
        wm_fact = Fact(fact_title='classified', name='SALT')
        engine = _make_engine(wm_facts=[wm_fact])
        antecedents = [NegatedFact(fact_title='classified', name='?n')]
        results = engine._match_antecedents(antecedents, {'?n': 'SALT'})
        assert results == []

    def test_empty_antecedents(self):
        engine = _make_engine()
        results = engine._match_antecedents([], {'?x': 1})
        assert results == [{'?x': 1}]


# ── _find_matching_rules ─────────────────────────────────────────────

class TestFindMatchingRules:
    def test_trigger_based_filtering(self):
        """Only rules whose positive antecedent matches the trigger are returned."""
        rule_a = Rule(
            rule_name='match_a',
            antecedents=[Fact(fact_title='type_a', val='?v')],
            consequent=Fact(fact_title='result_a', val='?v'),
        )
        rule_b = Rule(
            rule_name='match_b',
            antecedents=[Fact(fact_title='type_b', val='?v')],
            consequent=Fact(fact_title='result_b', val='?v'),
        )
        trigger = Fact(fact_title='type_a', val=1)
        engine = _make_engine(wm_facts=[trigger], kb_rules=[rule_a, rule_b])
        matches = engine._find_matching_rules(trigger)
        assert len(matches) == 1
        assert matches[0][0].rule_name == 'match_a'

    def test_no_match_returns_empty(self):
        rule = Rule(
            rule_name='r',
            antecedents=[Fact(fact_title='x', val='?v')],
            consequent=Fact(fact_title='y', val='?v'),
        )
        trigger = Fact(fact_title='z', val=1)
        engine = _make_engine(wm_facts=[trigger], kb_rules=[rule])
        assert engine._find_matching_rules(trigger) == []

    def test_multi_antecedent_with_kb_ref(self):
        """Rule needs trigger in WM + reference fact in KB."""
        ref = Fact(fact_title='lookup', key='A', value=10)
        trigger = Fact(fact_title='request', key='A')
        rule = Rule(
            rule_name='join',
            antecedents=[
                Fact(fact_title='request', key='?k'),
                Fact(fact_title='lookup', key='?k', value='?v'),
            ],
            consequent=Fact(fact_title='result', key='?k', value='?v'),
        )
        engine = _make_engine(wm_facts=[trigger], kb_rules=[rule], kb_ref_facts=[ref])
        matches = engine._find_matching_rules(trigger)
        assert len(matches) == 1
        assert matches[0][1]['?v'] == 10


# ── _fact_exists ─────────────────────────────────────────────────────

class TestFactExists:
    def test_existing_fact(self):
        f = Fact(fact_title='x', val=1)
        engine = _make_engine(wm_facts=[f])
        assert engine._fact_exists(Fact(fact_title='x', val=1)) is True

    def test_nonexistent_fact(self):
        engine = _make_engine()
        assert engine._fact_exists(Fact(fact_title='x', val=1)) is False

    def test_different_attributes(self):
        f = Fact(fact_title='x', val=1)
        engine = _make_engine(wm_facts=[f])
        assert engine._fact_exists(Fact(fact_title='x', val=2)) is False


# ── _apply_bindings ──────────────────────────────────────────────────

class TestApplyBindings:
    def test_substitutes_variables(self):
        engine = _make_engine()
        template = Fact(fact_title='result', name='?n', amount='?a')
        result = engine._apply_bindings(template, {'?n': 'SALT', '?a': 5})
        assert result.fact_title == 'result'
        assert result.attributes == {'name': 'SALT', 'amount': 5}

    def test_literal_values_preserved(self):
        engine = _make_engine()
        template = Fact(fact_title='result', kind='VOLUME', name='?n')
        result = engine._apply_bindings(template, {'?n': 'CUPS'})
        assert result.attributes == {'kind': 'VOLUME', 'name': 'CUPS'}

    def test_unbound_variable_left_as_is(self):
        engine = _make_engine()
        template = Fact(fact_title='result', name='?n')
        result = engine._apply_bindings(template, {})
        assert result.attributes == {'name': '?n'}


# ── _resolve_conflict ────────────────────────────────────────────────

class TestResolveConflict:
    def test_priority_default(self):
        engine = _make_engine()
        r1 = Rule(rule_name='low', priority=10, antecedents=[], consequent=None)
        r2 = Rule(rule_name='high', priority=100, antecedents=[], consequent=None)
        best = engine._resolve_conflict([(r1, {}, 'k1'), (r2, {}, 'k2')])
        assert best[0].rule_name == 'high'

    def test_specificity_strategy(self):
        engine = _make_engine()
        engine.conflict_resolution_strategy = 'specificity'
        r1 = Rule(rule_name='few', priority=100, antecedents=[Fact(fact_title='a')], consequent=None)
        r2 = Rule(rule_name='many', priority=10, antecedents=[Fact(fact_title='a'), Fact(fact_title='b')], consequent=None)
        best = engine._resolve_conflict([(r1, {}, 'k1'), (r2, {}, 'k2')])
        assert best[0].rule_name == 'many'
