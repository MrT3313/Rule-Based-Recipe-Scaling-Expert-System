# HW2: Rule Based Depth First Expert System for Recipe Scaling

## General Retrospective

Wow. This was much harder than I anticipated.

Ultimately what you are seeing the third attempt at this assignment and I have a completely different perspective of the two subsections I was required to split the assignment up into in order to remain somewhat sane. Scaling & Planning.  

Part of the reason I chose to pursue the implementation of my groups HW1 rules for a Rule Based Expert System for Recipe Scaling was because I knew things would get _interesting_ when scaled to the limit. Some of these interesting aspects would be ingredient and equipment substitution which in and of itself would require changes to the underlying recipe. Two examples of this would be cooking a stew in a wider pot required lowering the cooking temperature because the liquid would evaporate faster and changing baking equipment from a glass to a ceramic might required adjustments to the cooking temperature and timing due to how heat is retained and transferred in different materials.

> [!IMPORTANT]
> 
> If I had chosen to focus on this substitution based logic and built a "Substitution Engine" instead of a "Scaling Engine" I believe I would have a "better" submission (or at least something I am happer with / prouder of). 

Instead, I decided to test the durability of my forehead against how the scaling and equipment constraints turn this problem into a planning problem where batching needs to be calculated dynamically potentially at multiple "levels" of the steps (main vs nested substeps). 

> [!IMPORTANT]
> 
> Because of this I am asking that you grade this assignment from two perspectives. The [Scaling Ingredients](/DOCS/scaling/1.Scaling.md) part and the [Planning Scaled Recipe Steps](/DOCS/planning/2.Planning.md) part.

The `Scaling Ingredients` part of the assignment follows very closely to the rules and approach from HW1. This includes rules for classifying individual ingredients and then chaining those classifications to specific scaling tolerance rules as well as adhering to heuristic measurements when below a threshold ("a pinch" / "a dash"). 

The `Planning Scaled Recipe Steps` part of the assignment itself went through countless attempts to adhere to the If-Then approach for Rule Based Expert Systems but I kept on finding myself "needing" to fall back to various "helper functions" to take specific actions. While the final submission has much less of them they are still there, particularly regarding the actual batch planning, while the closer you get to the individual steps & substeps we get closer to a true Rule Based Expert System.

> [!WARNING]
> 
> I did use AI (Claude code) on the Planning Scaled Recipe Steps after **multiple** attempts at batching with the hopes of discovering some baseline approach that I was missing and therefore getting _something_ to submit. With the level of slop I sifted through I am unsure how helpful this even was at the end of the day (but I did get to _a_ solution so I guess there is that). AI was also used to build the test suites to "lockin" the logic after it was built (I did not follow a TDD approach). 
> 
> Some of the structural improvements made in the Planning Inference Engine were brought back to the Scaling Inference Engine **after** I had a fully working solution that answered all assignments components like the Rule Based Expert Systems if/then logic, multiple conflict resolution, an explanation component, etc...  

My initial approach was to focus on simply getting the recipe planning working based on the assumption of enough equipment but in retrospect knowing that I wanted to scale to the limit I should have focused on the batching logic at the very start with a dumbed down mock recipe (1 or 2 ingredients with 1 or 2 steps). 

> [!NOTE]
> 
> Both the `Scaling Ingredients` and `Planning Scaled Recipe Steps` utilize pattern matching and binding of rule antecedent variables through unification against a Knowledge Based & Working Memory in order to derive new facts through rule consequents. Actual calculations or Working Memory modifications (ex: calculating the actual scaled value of a classified ingredient / transitioning an oven state from RESERVED to IN_USE) are triggered through rule `action functions` that also utilize the bindings of a matched and unified rule.

> [!NOTE]
> 
> Due to the complexities / struggles outlined above the planning engine is NOT run by default. The user must pass the --run_planning_engine script argument to enable planning. 
> 
> Further script augmentation is outlined in the specific [Submission Part](#submission-parts) documentation.

## [Part2 Assignment Answers](/DOCS/Part2.Answers.md)

## Submission Parts

### [Scaling Ingredients](/DOCS/scaling/1.Scaling.md)

### [Planning Scaled Recipe Steps](/DOCS/planning/2.Planning.md)
