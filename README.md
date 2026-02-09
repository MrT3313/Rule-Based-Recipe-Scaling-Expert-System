# HW2: Rule Based Depth First Expert System for Recipe Scaling

## General Retrospective

This assignment was significantly harder than I anticipated. I am satisfied with the Scaling portion to the degree that it meets the assignment requirements, but I do not typically settle for the baseline. In this case I had to, because the time I would have spent stretching into substitution logic (equipment and ingredient constraint handling) was consumed by batching failures within the planning component of the overall system outlined below.

> [!IMPORTANT]
>
> Because of the challenges outlined below, I am asking that you grade this assignment from two perspectives: the [Scaling Ingredients](/DOCS/scaling/1.Scaling.md) part as the main submission and the [Planning Scaled Recipe Steps](/DOCS/planning/2.Planning.md) as a stretch goal I attempted to accomplish and lost too much time pursuing.

I chose to pursue the implementation of my group's HW1 rules for a Rule Based Expert System for Recipe Scaling because I knew things would get _interesting_ when scaled to the limit. The scaling itself is straightforward. The anticipated interesting parts were the substitutions that arise from equipment and ingredient constraints. For example, cooking a stew in a wider pot requires lowering the temperature because liquid evaporates faster, and switching baking equipment from glass to ceramic requires adjustments to temperature and timing due to differences in heat retention.

> [!IMPORTANT]
>
> In hindsight, if I had focused on this substitution-based logic and built a "Substitution Engine" instead of a "Scaling Engine," I believe I would have a stronger submission.

Instead, I pursued how scaling and equipment constraints turn this problem into a planning problem. The base planning logic (assuming fully available equipment) works. The problem was batching: dynamically calculating how to split work across limited equipment at multiple levels of the steps (main vs. nested substeps). This is where the real complexity emerged, and where I lost the time that should have gone toward substitution logic.

The `Scaling Ingredients` part follows closely the rules and approach from HW1. This includes rules for classifying individual ingredients and then chaining those classifications to specific scaling tolerance rules, as well as adhering to heuristic measurements when below a threshold ("a pinch" / "a dash").

The `Planning Scaled Recipe Steps` part went through numerous attempts to adhere to the If-Then approach for Rule Based Expert Systems. I repeatedly found myself needing to fall back to helper functions for specific actions. While the final submission has far fewer of them, they are still present, particularly around batch planning. The closer you get to individual steps and substeps, the closer the implementation gets to a true Rule Based Expert System.

> [!WARNING]
>
> I used AI (Claude Code) on the Planning Scaled Recipe Steps after initially building out the planning logic assuming no constraints, followed by multiple failed attempts at batching with the hopes of uncovering a baseline approach I was missing. The quality of AI-generated output was inconsistent at best, but its contribution to the partially working Planning part of the codebase was the three-phase dispatch pattern: an initialize rule (priority 200) seeds working memory with context for the step, an iteration rule (priority 190) uses NegatedFact guards to process items one at a time as the engine re-evaluates after each firing, and a finalize rule (priority 100) completes the step. In modules like mixing, cooking, and equipment transfer, the initialization rule seeds one pending fact per item, while other modules (like transfer and removal) iterate over existing working memory facts directly. This pattern was applied across the six dispatch modules (mixing, transfer, equipment transfer, cooking, removal, and surface transfer). AI was also used to build the test suites to lock in the logic after it was built. 

In retrospect, my initial approach of getting recipe planning working under the assumption of sufficient equipment was the wrong starting point. I should have focused on the batching logic from the very start with a minimal mock recipe (1-2 ingredients, 1-2 steps) and built up from there.

This outcome was not a consequence of working alone. It was a consequence of not pulling the ripcord a day or two sooner, wiping the slate, and pivoting to the substitution engine approach. That pivot would have avoided the batching and planning problem entirely, keeping the implementation closer to strictly If-Then logic better suited to Rule Based Expert Systems.

> [!NOTE]
>
> Both the `Scaling Ingredients` and `Planning Scaled Recipe Steps` systems utilize pattern matching and binding of rule antecedent variables through unification against the Knowledge Base and Working Memory to derive new facts through rule consequents. Actual calculations and Working Memory modifications like computing the scaled value of a classified ingredient or transitioning an oven state from RESERVED to IN_USE are triggered through rule `action functions` that also utilize the bindings of a matched and unified rule.

> [!NOTE]
>
> Due to the complexities outlined above, the planning engine is NOT run by default. The user must pass the `--run_planning_engine` script flag to enable planning.
>
> Further script augmentation is outlined in the specific [Submission Part](#submission-parts) documentation.

## [Part2 Assignment Answers](/DOCS/Part2.Answers.md)

## Submission Parts

### [Scaling Ingredients](/DOCS/scaling/1.Scaling.md)

### [Planning Scaled Recipe Steps](/DOCS/planning/2.Planning.md)
