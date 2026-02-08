import pytest
from io import StringIO

from classes.Fact import Fact
from classes.Rule import Rule
from classes.KnowledgeBase import KnowledgeBase
from classes.WorkingMemory import WorkingMemory
from classes.ExplanationFacility import ExplanationFacility
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


# ── Derivation tracking ──────────────────────────────────────────────

class TestDerivationTracking:
    def test_initial_facts_have_no_derivation(self):
        """Facts added before inference should have derivation=None."""
        wm = WorkingMemory()
        f = Fact(fact_title='input', value=1)
        wm.add_fact(fact=f, silent=True)
        assert f.derivation is None

    def test_derived_fact_has_derivation(self):
        """A fact produced by a rule should carry a derivation dict."""
        input_fact = Fact(fact_title='ingredient', name='SALT')
        rule = Rule(
            rule_name='classify_salt',
            antecedents=[Fact(fact_title='ingredient', name='SALT')],
            consequent=Fact(fact_title='classified', name='SALT', category='MINERAL'),
            priority=1,
        )
        engine = _make_engine(wm_facts=[input_fact], kb_rules=[rule])
        engine._forward_chain(trigger_fact=input_fact)

        derived = [f for f in engine.working_memory.facts if f.fact_title == 'classified']
        assert len(derived) == 1
        assert derived[0].derivation is not None
        assert derived[0].derivation['rule_name'] == 'classify_salt'

    def test_derivation_antecedent_facts_populated(self):
        """The derivation should list the concrete facts that matched antecedents."""
        input_fact = Fact(fact_title='ingredient', name='SALT')
        rule = Rule(
            rule_name='classify_salt',
            antecedents=[Fact(fact_title='ingredient', name='SALT')],
            consequent=Fact(fact_title='classified', name='SALT', category='MINERAL'),
            priority=1,
        )
        engine = _make_engine(wm_facts=[input_fact], kb_rules=[rule])
        engine._forward_chain(trigger_fact=input_fact)

        derived = [f for f in engine.working_memory.facts if f.fact_title == 'classified'][0]
        antecedent_facts = derived.derivation['antecedent_facts']
        assert len(antecedent_facts) >= 1
        assert any(f.fact_title == 'ingredient' and f.attributes.get('name') == 'SALT'
                    for f in antecedent_facts)

    def test_chained_derivation(self):
        """Facts derived by chained rules should each have their own derivation."""
        input_fact = Fact(fact_title='ingredient', name='SUGAR')
        rule1 = Rule(
            rule_name='classify_sugar',
            antecedents=[Fact(fact_title='ingredient', name='?n')],
            consequent=Fact(fact_title='classified', name='?n', category='DRY'),
            priority=1,
        )
        rule2 = Rule(
            rule_name='scale_classified',
            antecedents=[Fact(fact_title='classified', name='?n', category='?c')],
            consequent=Fact(fact_title='scaled', name='?n', factor=2),
            priority=1,
        )
        engine = _make_engine(wm_facts=[input_fact], kb_rules=[rule1, rule2])
        engine._forward_chain(trigger_fact=input_fact)

        classified = [f for f in engine.working_memory.facts if f.fact_title == 'classified']
        scaled = [f for f in engine.working_memory.facts if f.fact_title == 'scaled']

        assert len(classified) == 1
        assert classified[0].derivation['rule_name'] == 'classify_sugar'

        assert len(scaled) == 1
        assert scaled[0].derivation['rule_name'] == 'scale_classified'
        # The scaled fact's antecedents should include the classified fact
        ant_titles = [f.fact_title for f in scaled[0].derivation['antecedent_facts']]
        assert 'classified' in ant_titles

    def test_multi_antecedent_derivation(self):
        """A rule with multiple antecedents should track all matched facts."""
        fact_a = Fact(fact_title='a', x=1)
        fact_b = Fact(fact_title='b', x=1)
        rule = Rule(
            rule_name='join_ab',
            antecedents=[
                Fact(fact_title='a', x='?x'),
                Fact(fact_title='b', x='?x'),
            ],
            consequent=Fact(fact_title='joined', x='?x'),
            priority=1,
        )
        engine = _make_engine(wm_facts=[fact_a, fact_b], kb_rules=[rule])
        engine._forward_chain(trigger_fact=fact_a)

        joined = [f for f in engine.working_memory.facts if f.fact_title == 'joined']
        assert len(joined) == 1
        assert joined[0].derivation is not None
        assert len(joined[0].derivation['antecedent_facts']) == 2

    def test_action_fn_side_effect_facts_get_derivation(self):
        """Facts added by action_fn via wm.add_fact should pick up the current derivation."""
        input_fact = Fact(fact_title='trigger', v=1)

        def my_action(*, bindings, wm, kb):
            wm.add_fact(fact=Fact(fact_title='side_effect', v=bindings['?v']), silent=True)
            return bindings

        rule = Rule(
            rule_name='trigger_action',
            antecedents=[Fact(fact_title='trigger', v='?v')],
            consequent=Fact(fact_title='done', v='?v'),
            action_fn=my_action,
            priority=1,
        )
        engine = _make_engine(wm_facts=[input_fact], kb_rules=[rule])
        engine._forward_chain(trigger_fact=input_fact)

        side_effects = [f for f in engine.working_memory.facts if f.fact_title == 'side_effect']
        assert len(side_effects) == 1
        assert side_effects[0].derivation is not None
        assert side_effects[0].derivation['rule_name'] == 'trigger_action'

    def test_reference_fact_in_antecedents(self):
        """When a rule matches a reference fact as an antecedent, it should appear in derivation."""
        input_fact = Fact(fact_title='ingredient', name='SALT')
        ref_fact = Fact(fact_title='classification', name='SALT', category='MINERAL')
        rule = Rule(
            rule_name='classify_with_ref',
            antecedents=[
                Fact(fact_title='ingredient', name='?n'),
                Fact(fact_title='classification', name='?n', category='?c'),
            ],
            consequent=Fact(fact_title='classified', name='?n', category='?c'),
            priority=1,
        )
        engine = _make_engine(
            wm_facts=[input_fact],
            kb_rules=[rule],
            kb_ref_facts=[ref_fact],
        )
        engine._forward_chain(trigger_fact=input_fact)

        classified = [f for f in engine.working_memory.facts if f.fact_title == 'classified']
        assert len(classified) == 1
        ant_titles = [f.fact_title for f in classified[0].derivation['antecedent_facts']]
        assert 'ingredient' in ant_titles
        assert 'classification' in ant_titles


# ── ExplanationFacility ──────────────────────────────────────────────

class TestExplanationFacility:
    def test_classify_leaf_input(self):
        """An initial WM fact not in KB reference should be classified as INPUT."""
        wm = WorkingMemory()
        kb = KnowledgeBase()
        f = Fact(fact_title='input', value=1)
        wm.add_fact(fact=f, silent=True)
        ef = ExplanationFacility(wm=wm, kb=kb, label="Test")
        assert ef._classify_leaf(fact=f) == "INPUT"

    def test_classify_leaf_reference(self):
        """A fact matching a KB reference fact should be classified as REFERENCE."""
        wm = WorkingMemory()
        kb = KnowledgeBase()
        ref = Fact(fact_title='conversion', from_unit='CUP', to_unit='TBSP', factor=16)
        kb.add_reference_facts(facts=[ref])
        # Create an identical fact in WM
        wm_fact = Fact(fact_title='conversion', from_unit='CUP', to_unit='TBSP', factor=16)
        wm.add_fact(fact=wm_fact, silent=True)
        ef = ExplanationFacility(wm=wm, kb=kb, label="Test")
        assert ef._classify_leaf(fact=wm_fact) == "REFERENCE"

    def test_print_derivation_leaf(self, capsys):
        """Printing a leaf fact should show [INPUT]."""
        wm = WorkingMemory()
        kb = KnowledgeBase()
        f = Fact(fact_title='input', value=1)
        wm.add_fact(fact=f, silent=True)
        ef = ExplanationFacility(wm=wm, kb=kb, label="Test")
        ef._print_derivation(fact=f)
        captured = capsys.readouterr()
        assert "[INPUT]" in captured.out

    def test_print_derivation_derived(self, capsys):
        """Printing a derived fact should show the rule name and antecedents."""
        wm = WorkingMemory()
        kb = KnowledgeBase()

        input_fact = Fact(fact_title='ingredient', name='SALT')
        wm.add_fact(fact=input_fact, silent=True)

        derived = Fact(fact_title='classified', name='SALT', category='MINERAL')
        derived.derivation = {
            'rule_name': 'classify_salt',
            'antecedent_facts': [input_fact],
        }
        wm.add_fact(fact=derived, silent=True)

        ef = ExplanationFacility(wm=wm, kb=kb, label="Test")
        ef._print_derivation(fact=derived)
        captured = capsys.readouterr()
        assert "classify_salt" in captured.out
        assert "antecedents:" in captured.out
        assert "[INPUT]" in captured.out

    def test_repl_continue(self, monkeypatch, capsys):
        """Typing 'c' should exit the REPL."""
        wm = WorkingMemory()
        kb = KnowledgeBase()
        f = Fact(fact_title='input', value=1)
        wm.add_fact(fact=f, silent=True)

        monkeypatch.setattr('builtins.input', lambda prompt: 'c')
        ef = ExplanationFacility(wm=wm, kb=kb, label="Test")
        ef.run_repl()
        # Should complete without error

    def test_repl_explain_fact(self, monkeypatch, capsys):
        """Querying a fact ID should print its derivation."""
        wm = WorkingMemory()
        kb = KnowledgeBase()
        f = Fact(fact_title='input', value=1)
        wm.add_fact(fact=f, silent=True)

        inputs = iter(['1', 'c'])
        monkeypatch.setattr('builtins.input', lambda prompt: next(inputs))
        ef = ExplanationFacility(wm=wm, kb=kb, label="Test")
        ef.run_repl()
        captured = capsys.readouterr()
        assert "[INPUT]" in captured.out

    def test_repl_invalid_input(self, monkeypatch, capsys):
        """Invalid input should print an error message and continue."""
        wm = WorkingMemory()
        kb = KnowledgeBase()
        f = Fact(fact_title='input', value=1)
        wm.add_fact(fact=f, silent=True)

        inputs = iter(['abc', 'c'])
        monkeypatch.setattr('builtins.input', lambda prompt: next(inputs))
        ef = ExplanationFacility(wm=wm, kb=kb, label="Test")
        ef.run_repl()
        captured = capsys.readouterr()
        assert "Invalid input" in captured.out

    def test_repl_nonexistent_fact(self, monkeypatch, capsys):
        """Querying a nonexistent fact ID should print a not-found message."""
        wm = WorkingMemory()
        kb = KnowledgeBase()
        f = Fact(fact_title='input', value=1)
        wm.add_fact(fact=f, silent=True)

        inputs = iter(['999', 'c'])
        monkeypatch.setattr('builtins.input', lambda prompt: next(inputs))
        ef = ExplanationFacility(wm=wm, kb=kb, label="Test")
        ef.run_repl()
        captured = capsys.readouterr()
        assert "No fact with ID #999" in captured.out
