from classes.Rule import Rule
from classes.Fact import Fact
from classes.NegatedFact import NegatedFact


def _initialize_mixing(*, bindings, wm, kb, plan):
    """Read recipe step, assert one pending_ingredient fact per ingredient, append MixingStep to plan."""
    engine = bindings['_engine']
    step_idx = bindings['?step_idx']
    step = engine.recipe.steps[step_idx]

    ingredient_map = {ing.id: ing for ing in engine.recipe.ingredients}

    seq = 0
    for substep_idx, substep in enumerate(step.substeps):
        if engine.verbose:
            print(f"\n  Substep {substep_idx + 1}: {substep.description}")

        for ingredient_id in substep.ingredient_ids:
            ingredient = ingredient_map.get(ingredient_id)
            if ingredient is None:
                bindings['?error'] = f"Ingredient id={ingredient_id} not found in recipe"
                return bindings

            wm.add_fact(fact=Fact(
                fact_title='pending_ingredient',
                step_idx=step_idx,
                seq=seq,
                ingredient_id=ingredient.id,
                ingredient_name=ingredient.ingredient_name,
                amount=ingredient.amount,
                unit=ingredient.unit,
                measurement_category=ingredient.measurement_category,
            ), indent="    ")
            seq += 1

    plan.append(step)
    return bindings


def get_mixing_dispatch_rules():
    rules = []

    # M1: Initialize mixing — read recipe, assert pending_ingredient facts, append step to plan
    rules.append(Rule(
        rule_name='initialize_mixing',
        priority=200,
        antecedents=[
            Fact(fact_title='step_request',
                 step_type='MIXING',
                 step_idx='?step_idx',
                 equipment_name='?equipment_name',
                 equipment_id='?equipment_id',
                 equipment_volume='?equipment_volume',
                 equipment_volume_unit='?equipment_volume_unit'),
            NegatedFact(fact_title='mixing_initialized', step_idx='?step_idx'),
        ],
        action_fn=_initialize_mixing,
        consequent=Fact(
            fact_title='mixing_initialized',
            step_idx='?step_idx',
            equipment_name='?equipment_name',
            equipment_id='?equipment_id',
            equipment_volume='?equipment_volume',
            equipment_volume_unit='?equipment_volume_unit',
        ),
    ))

    # M2: Process next ingredient — PURE PATTERN RULE
    # Fires for each pending_ingredient that hasn't been processed yet.
    # The engine's while-matches loop re-evaluates after each M2b fires,
    # picking the next unprocessed ingredient.
    rules.append(Rule(
        rule_name='process_next_ingredient',
        priority=190,
        antecedents=[
            Fact(fact_title='mixing_initialized',
                 step_idx='?step_idx',
                 equipment_name='?equipment_name',
                 equipment_id='?equipment_id',
                 equipment_volume='?equipment_volume',
                 equipment_volume_unit='?equipment_volume_unit'),
            Fact(fact_title='pending_ingredient',
                 step_idx='?step_idx',
                 ingredient_id='?ingredient_id',
                 ingredient_name='?ingredient_name',
                 amount='?amount',
                 unit='?unit',
                 measurement_category='?measurement_category'),
            NegatedFact(fact_title='ingredient_processed',
                        step_idx='?step_idx',
                        ingredient_id='?ingredient_id'),
        ],
        action_fn=None,
        consequent=Fact(
            fact_title='ingredient_addition_request',
            ingredient_id='?ingredient_id',
            ingredient_name='?ingredient_name',
            amount='?amount',
            unit='?unit',
            measurement_category='?measurement_category',
            equipment_name='?equipment_name',
            equipment_id='?equipment_id',
            equipment_volume='?equipment_volume',
            equipment_volume_unit='?equipment_volume_unit',
        ),
    ))

    # M2b: Mark ingredient as processed — PURE PATTERN RULE
    # After add_volume_ingredient fires and derives ingredient_added,
    # this rule marks it processed so M2 won't re-fire for the same ingredient.
    rules.append(Rule(
        rule_name='mark_ingredient_processed',
        priority=185,
        antecedents=[
            Fact(fact_title='ingredient_added',
                 ingredient_id='?ingredient_id',
                 equipment_name='?equipment_name',
                 equipment_id='?equipment_id'),
            Fact(fact_title='pending_ingredient',
                 step_idx='?step_idx',
                 ingredient_id='?ingredient_id'),
            NegatedFact(fact_title='ingredient_processed',
                        step_idx='?step_idx',
                        ingredient_id='?ingredient_id'),
        ],
        action_fn=None,
        consequent=Fact(
            fact_title='ingredient_processed',
            step_idx='?step_idx',
            ingredient_id='?ingredient_id',
        ),
    ))

    # M3: Finalize mixing — fires after all M2 instances complete (lower priority)
    # Derives mixing_completed which chains to summarize_mixed_contents
    rules.append(Rule(
        rule_name='finalize_mixing',
        priority=100,
        antecedents=[
            Fact(fact_title='mixing_initialized',
                 step_idx='?step_idx',
                 equipment_name='?equipment_name',
                 equipment_id='?equipment_id'),
        ],
        action_fn=None,
        consequent=Fact(
            fact_title='mixing_completed',
            equipment_name='?equipment_name',
            equipment_id='?equipment_id',
        ),
    ))

    return rules
