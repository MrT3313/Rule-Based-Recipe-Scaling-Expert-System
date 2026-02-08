# Rule Based Depth First Expert System for Recipe Scaling

## Brain

### Knowledge Base

> The Knowledge Base holds permanent knowledge: Rules & Reference Facts
> 
> A Reference Fact is "background" knowledge (unit conversions, classification, etc. relevant to the domain)

### Working Memory

> Working Memory is the "current state" of the application holding the current facts that have been derived based on the matching and unification of the Knowledge Base Rules with the Working Memory facts.

## Inference Engines

### Scaling

The `ScalingEngine` is a forward-chaining production system that takes recipe ingredient facts and derives scaled/classified outputs by matching rules against working memory and knowledge base reference facts.

#### Functions

| Method | Purpose |
|---|---|
| `run()` | Entry point — snapshots `recipe_ingredient` facts as triggers, then forward-chains on each one |
| `_forward_chain(*, trigger_fact)` | Core loop — finds matching rules for a trigger, resolves conflicts, fires via DFS; exhausts all matches using a while-loop with fired-set tracking. Returns `(any_rule_fired, last_derived_fact)` |
| `_find_matching_rules(*, trigger_fact)` | Returns all `(rule, bindings)` pairs whose antecedents are satisfied, using `trigger_fact` as an anchor filter |
| `_match_antecedents(*, antecedents, bindings)` | Recursively matches remaining antecedents against KB reference facts + WM facts; handles `NegatedFact` via negation-as-failure |
| `_unify(*, pattern, fact, bindings)` | Pattern matching — unifies one antecedent pattern against one fact, binding `?variables`. Returns updated bindings or `None` on failure |
| `_apply_bindings(*, fact_template, bindings)` | Substitutes `?variables` in a consequent template with concrete values from bindings |
| `_fact_exists(*, fact)` | Duplicate check — returns `True` if an identical fact is already in working memory |
| `_resolve_conflict(*, matches)` | Picks the best rule from candidates using priority (default) or specificity strategy |
| `_fire_rule_dfs(*, rule, bindings)` | Fires a rule (runs `action_fn`, derives consequent, adds to WM), then DFS-chases any rules triggered by the derived fact |

#### Flow Diagram

```mermaid
flowchart TD
    A["run: begin scaling"] --> B["Snapshot all recipe ingredient facts as triggers"]
    B --> C{"Any triggers remaining?"}
    C -- Yes --> D["_forward_chain: process next trigger fact"]
    C -- No --> Z["Scaling complete"]
    D --> E["_find_matching_rules: search KB for rules matching trigger"]
    E --> F{"Any rules matched?"}
    F -- No --> G["Advance to next trigger"]
    G --> C
    F -- Yes --> H["Filter out rules already fired for this trigger"]
    H --> I{"Any unfired matches left?"}
    I -- No --> G
    I -- Yes --> J["_resolve_conflict: pick best rule by priority or specificity"]
    J --> K["_fire_rule_dfs: execute winning rule and chase derived facts"]
    K --> E

    style E fill:#e6d5f5,stroke:#333,color:#000
    style K fill:#e6d5f5,stroke:#333,color:#000
    style Z fill:#d4edda,stroke:#333,color:#000
```

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'lineColor': '#000000', 'edgeLabelBackground': '#000000', 'primaryTextColor': '#ffffff'}}}%%
flowchart TD
    classDef default color:#000
    subgraph fire["_fire_rule_dfs: execute rule and DFS-chain"]
        FR1["Execute action_fn side-effect if rule defines one"] --> FR2{"Does rule have a consequent?"}
        FR2 -- "No consequent" --> FR10["Return None"]
        FR2 -- "Yes" --> FR3["_apply_bindings: substitute ?variables into consequent template"]
        FR3 --> FR4{"_fact_exists: is derived fact already in WM?"}
        FR4 -- "New fact" --> FR5["Add derived fact to Working Memory"]
        FR4 -- "Duplicate — skip add" --> FR6["DFS: _find_matching_rules using derived fact as new trigger"]
        FR5 --> FR6
        FR6 --> FR7{"Did the derived fact trigger any new rules?"}
        FR7 -- Yes --> FR8["_resolve_conflict: pick best, then recurse into _fire_rule_dfs"]
        FR8 --> FR6
        FR7 -- No --> FR9["Return derived fact to caller"]
    end

    subgraph find["_find_matching_rules: search for satisfied rules"]
        FM1{"More KB rules to check?"} -- Yes --> FM2["_unify: try to bind trigger fact to each rule antecedent"]
        FM2 --> FM3{"Does the trigger unify with an antecedent?"}
        FM3 -- No --> FM1
        FM3 -- Yes --> FM4["_match_antecedents: recursively match remaining antecedents against KB + WM facts"]
        FM4 --> FM5["Collect valid rule, bindings pairs"]
        FM5 --> FM1
        FM1 -- "All rules checked" --> FM6["Return list of matched rules with their bindings"]
    end

    style fire fill:#e6d5f5,stroke:#333,color:#000
    style find fill:#e6d5f5,stroke:#333,color:#000
    style FR9 fill:#ffd700,stroke:#333,color:#000
    style FR10 fill:#ffd700,stroke:#333,color:#000
    style FM6 fill:#ffd700,stroke:#333,color:#000
```

### Planning

The `PlanningEngine` is a forward-chaining production system that translates recipe steps into executable plans. It iterates over each recipe step, resolves required equipment, classifies the step type, and dispatches a `step_request` fact to specialized rules via forward chaining. Orchestration rules receive the engine instance via `bindings['_engine']`, enabling nested forward chaining and multi-level rule composition.

#### Functions

| Method | Purpose |
|---|---|
| `run(*, recipe)` | Entry point — iterates recipe steps, resolves equipment, builds `step_request` facts, forward-chains dispatch rules, handles GENERIC fallback. Returns `(success, plan_or_error)` |
| `_resolve_equipment(*, equipment_need)` | Finds AVAILABLE equipment and reserves it; if none available, tries cleaning DIRTY equipment via rules. Returns resolved list or `None` on failure |
| `_build_step_request(*, step, step_idx, resolved_equipment)` | Boundary translation — converts a recipe Step object into a `step_request` Fact with step_type classification and attribute-based overrides |
| `_forward_chain(*, trigger_fact)` | Core loop — finds matching rules for a trigger, resolves conflicts by priority, fires via DFS; exhausts all matches with fired-set tracking. Returns `(any_rule_fired, last_derived_fact)` |
| `_find_matching_rules(*, trigger_fact)` | Returns all `(rule, bindings)` pairs whose antecedents are satisfied, using `trigger_fact` as an anchor filter |
| `_match_antecedents(*, antecedents, bindings)` | Recursively matches remaining antecedents against WM facts; handles `NegatedFact` via negation-as-failure |
| `_unify(*, pattern, fact, bindings)` | Pattern matching — unifies one antecedent pattern against one fact, binding `?variables`. Returns updated bindings or `None` |
| `_apply_bindings(*, fact_template, bindings)` | Substitutes `?variables` in a consequent template with concrete values from bindings |
| `_fact_exists(*, fact)` | Duplicate check — returns `True` if an identical fact is already in working memory |
| `_resolve_conflict(*, matches)` | Picks the highest-priority rule from candidates (priority-only, no specificity option) |
| `_fire_rule_dfs(*, rule, bindings, plan_override=None)` | Fires a rule (injects `_engine`, runs `action_fn` with plan, derives consequent), then DFS-chases triggered rules. Supports `plan_override` for per-oven substep lists. Propagates errors via `?error` |

#### Flow Diagram

Purple boxes = functions detailed in Diagram 2 subgraphs.

```mermaid
flowchart TD
    A["run: begin planning"] --> B["Initialize plan, recipe, and error state"]
    B --> C{"Any recipe steps remaining?"}
    C -- No --> Z["Planning complete — return (True, plan)"]
    C -- Yes --> D["_resolve_equipment: resolve all equipment for next step"]
    D --> E{"Equipment resolved successfully?"}
    E -- No --> F["Return (False, equipment unavailable)"]
    E -- Yes --> G["_build_step_request: classify step type and create step_request Fact"]
    G --> H["Add step_request to Working Memory"]
    H --> I["_find_matching_rules: search KB for dispatch rules matching step_request"]
    I --> J{"Any rules matched?"}
    J -- Yes --> K["Filter out rules already fired for this trigger"]
    K --> L{"Any unfired matches left?"}
    L -- Yes --> M["_resolve_conflict: pick best rule by priority"]
    M --> N["_fire_rule_dfs: execute rule, inject _engine, chase derived facts"]
    N --> NE{"Error from rule execution?"}
    NE -- "Yes — break loop" --> O
    NE -- No --> I
    J -- No --> O
    L -- No --> O
    O{"self.last_error set?"}
    O -- Yes --> P["Return (False, error message)"]
    O -- No --> Q{"Non-GENERIC step with no rule fired?"}
    Q -- Yes --> R["Return (False, no matching dispatch rule)"]
    Q -- No --> S{"Is step_type GENERIC?"}
    S -- "Yes — no dispatch rules" --> T["Transition equipment RESERVED → IN_USE, append step to plan"]
    T --> U["Advance to next recipe step"]
    S -- "No — dispatch rules handled it" --> U
    U --> C

    style D fill:#e6d5f5,stroke:#333,color:#000
    style I fill:#e6d5f5,stroke:#333,color:#000
    style N fill:#e6d5f5,stroke:#333,color:#000
    style Z fill:#d4edda,stroke:#333,color:#000
    style F fill:#ffd700,stroke:#333,color:#000
    style P fill:#ffd700,stroke:#333,color:#000
    style R fill:#ffd700,stroke:#333,color:#000
```
```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'lineColor': '#000000', 'edgeLabelBackground': '#000000', 'primaryTextColor': '#ffffff'}}}%%
flowchart TD
    classDef default color:#000
    subgraph equip["_resolve_equipment: find and reserve equipment for a step"]
        RE1{"Any equipment needs remaining?"} -- Yes --> RE2["Query WM for AVAILABLE equipment by name"]
        RE2 --> RE3{"Found AVAILABLE?"}
        RE3 -- "Yes" --> RE4["Set state → RESERVED, add to resolved list"]
        RE4 --> RE1
        RE3 -- "No" --> RE5["Query WM for DIRTY equipment by name"]
        RE5 --> RE6{"Found DIRTY?"}
        RE6 -- "Yes" --> RE7["Fire cleaning rule: _find_matching_rules + _fire_rule_dfs"]
        RE7 --> RE8["Equipment cleaned → RESERVED, add to resolved list"]
        RE8 --> RE1
        RE6 -- "No — insufficient equipment" --> RE9["Return None (failure)"]
        RE1 -- "All needs met" --> RE10["Return resolved equipment list"]
    end

    style equip fill:#e6d5f5,stroke:#333,color:#000
    style RE9 fill:#ffd700,stroke:#333,color:#000
    style RE10 fill:#ffd700,stroke:#333,color:#000
```

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'lineColor': '#000000', 'edgeLabelBackground': '#000000', 'primaryTextColor': '#ffffff'}}}%%
flowchart TD
    classDef default color:#000
    subgraph find["_find_matching_rules: search for satisfied rules"]
        FM1{"More KB rules to check?"} -- Yes --> FM2["_unify: try binding trigger fact to each positive antecedent"]
        FM2 --> FM3{"Does the trigger unify with an antecedent?"}
        FM3 -- No --> FM1
        FM3 -- Yes --> FM4["_match_antecedents: recursively match remaining antecedents against WM facts"]
        FM4 --> FM5["Collect valid rule, bindings pairs"]
        FM5 --> FM1
        FM1 -- "All rules checked" --> FM6["Return list of matched rules with their bindings"]
    end

    style find fill:#e6d5f5,stroke:#333,color:#000
    style FM6 fill:#ffd700,stroke:#333,color:#000
```

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'lineColor': '#000000', 'edgeLabelBackground': '#000000', 'primaryTextColor': '#ffffff'}}}%%
flowchart TD
    classDef default color:#000
    subgraph fire["_fire_rule_dfs: execute rule with error handling and DFS-chain"]
        FR0["Seed bindings: _engine = self for orchestration rule callbacks"] --> FR1
        FR1["Execute action_fn if present — passes plan list and engine reference"] --> FR1E{"?error in bindings?"}
        FR1E -- "Yes — error signaled" --> FR10["Set self.last_error, return None"]
        FR1E -- "No" --> FR2{"Does rule have a consequent?"}
        FR2 -- "No consequent" --> FR11["Return None"]
        FR2 -- "Yes" --> FR3["_apply_bindings: substitute ?variables into consequent template"]
        FR3 --> FR4{"_fact_exists: is derived fact already in WM?"}
        FR4 -- "New fact" --> FR5["Add derived fact to Working Memory"]
        FR4 -- "Duplicate — skip add" --> FR6
        FR5 --> FR6["DFS: _find_matching_rules using derived fact as new trigger"]
        FR6 --> FR7{"Did the derived fact trigger any new rules?"}
        FR7 -- Yes --> FR8["Pick best by priority, recurse into _fire_rule_dfs with plan_override"]
        FR8 --> FR6
        FR7 -- No --> FR9["Return derived fact to caller"]
    end

    style fire fill:#e6d5f5,stroke:#333,color:#000
    style FR9 fill:#ffd700,stroke:#333,color:#000
    style FR10 fill:#ffd700,stroke:#333,color:#000
    style FR11 fill:#ffd700,stroke:#333,color:#000
```

## Running Tests

```bash
make test
```
