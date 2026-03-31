# Robocon 2026 Meihua Forest Path Planner + Estimator + GUI Requirements

## 1. Rule Extraction (from ABU Robocon 2026 Rulebook V1.0)

### 1.1 Meihua Forest Overview
- Section 4.4: Meihua Forest. R1 and R2 collaborate to collect Kung-Fu Scrolls (KFS).
- R2 is an automatic robot and must operate autonomously in Meihua Forest.

### 1.2 R2-specific rules
- 4.4.13: R2 must enter Forest via R2 Entrance Zone.
- 4.4.14: R2 can only pick up KFS from blocks adjacent to the current block.
- 4.4.15: If blocks 1, 2, or 3 contain R2 KFS, R2 must collect its first KFS from the R2 Entrance Zone.
- 4.4.16: R2 must collect and carry at least one R2 KFS to exit Forest.
- 4.4.19: R2 must exit Forest via one of the designated blocks: 10, 11, or 12.
- User additional rule: R2 boundary transition at entry and exit must be exactly 200 mm (20 cm).
- User additional field constants:
  - Entrance link is only block `2`.
  - Exit blocks are only `10` and `12`.

### 1.3 Path and block height
- The field uses three Meihua Forest block heights:
  - Forest (200mm)
  - Forest (400mm)
  - Forest (600mm)
- User requirement (updated): one-step height change must satisfy `|Δh| <= 200 mm`.
  - Allowed: 0↔200, 200↔400, 400↔600
  - Not allowed: 0↔400, 200↔600, 0↔600, 400↔0
- Additional robot constraint (user): maximum ramp angle ≤ 20° for moves.

### 1.4 Scroll capacity
- User requirement (updated): R2 can carry up to two scrolls total:
  - one stored/hidden slot
  - one gripped/held slot
- Rulebook requirement: R2 must exit with at least one R2 KFS.
- User strategy requirement:
  - If possible, R2 should collect `2` R2 scrolls before exit.
  - R2 should avoid R1 scroll zones as much as possible (because R1 has priority to collect R1 KFS first).

## 2. Derived Robot Constraints

| Requirement | Rulebook | Robot capability | Validation rule |
|---|---|---|---|
| R2 entry path | 4.4.13 + user field constraint | via Entrance link block 2 | first forest link == 2 |
| Adjacent pick-up | 4.4.14 | adjacent block only | Manhattan(d)=1 or adjacent edge |
| Pickup without climbing | user clarification | pick from neighbor block without moving onto target block | robot_position remains on anchor block; target KFS removed |
| First KFS from entrance when 1-3 holds| 4.4.15 | entrance starting pick | if KFS in 1-3 then first pickup location must be on entrance block |
| Minimum carry to exit | 4.4.16 | carries ≥1 KFS at exit | carry_count >= 1 at exit block |
| Exit block set | 4.4.19 + user field constraint | block in [10,12] | exit_block ∈ {10,12} |
| Max step height | User update | one-step absolute change ≤200 mm | abs(target_height - current_height) <= 200 |
| Max slope | E.g. user maximum angle =20° | angle ≤20° | atan2(Δh, horizontal_distance) ≤ 20° |
| Max scroll load | user addition | carry_count ≤2 (hidden+grip) | carry_count <=2 |
| Entry boundary drop | user addition | E→Forest must be 200 mm | abs(height(entry_block)-0) == 200 |
| Exit boundary drop | user addition | Forest→Exit zone must be 200 mm | abs(height(exit_block)-0) == 200 |
| R1 no-place blocks | user addition | R1 KFS not allowed at 5,8 | block_id not in {5,8} for R1 |
| Prefer 2-scroll plan | user strategy | choose 2-scroll route when valid | if exists(valid_2_scroll_route) then rank ahead of 1-scroll |
| R1-zone avoidance | user strategy | keep distance from R1 KFS blocks | add penalty for touch/near/proximity to R1 blocks |
| Touching Fake KFS | Section 8 + user strict mode | treated as violation | move_to_block with token == FAKE is invalid |
| Passing R1 KFS block | user strategy | allowed after waiting R1 clear | if move_to_block token==R1 then add wait action before pass |
| Exit preference | user strategy | exiting from 10 has higher strategic value than 12 | add bonus points for exit 10 |
| Exit pickup rule | user strategy (hard) | if exit block has R2 KFS, must pick that block before exit | exit plan invalid unless pickup list includes exit block |
| First-last pickup policy | user strategy | take earliest encountered and late path-blocking target | middle target selection gets drop action / policy penalty |

## 3. App Requirements

### 3.1 Input model
- Forest grid: 12 blocks (layout as per rulebook, with known entrance and exit positions).
- Each block attributes:
  - ID (1..12), position (x,y), height (200/400/600 mm), KFS type (R2 / R1 / Fake / empty)
  - Adjacency list for up/down/left/right (plus diagonal if allowed by rules, but 4.4.14 implies edge adjacency).
- Robot state:
  - Current block id
  - Carry count (0..2)
  - Hidden slot count (0 or 1)
  - Grip slot count (0 or 1)
  - Carry type (R2 KFS only for this module)
  - Max slope (20 degrees), max step (200 mm)
  - Max total carried scrolls = 2 (hidden 1 + grip 1)
- Field constants from provided drawing:
  - Forest block layout is `3 columns x 4 rows` (total 12 blocks).
  - Default block-height matrix (top→down, left→right):
    - Row 1: `400, 200, 400`
    - Row 2: `200, 400, 600`
    - Row 3: `400, 600, 400`
    - Row 4: `200, 400, 200`
  - Surrounding pathway width around forest: `1200 mm` (as shown in drawing).
  - Pathway/zone level for planner baseline: `0 mm`.
  - Entrance links: `2` only.
  - Exit blocks: `10, 12`.

### 3.2 Two-tab software structure
- Tab A: `Auto Optimize`
  - System auto-generates or loads valid KFS layouts.
  - System computes and ranks the best route candidates.
  - Shows Top-N plans (e.g., Top 3 or Top 5).
- Tab B: `Manual Layout + Plan`
  - Team manually places R2/R1/Fake KFS on blocks.
  - System validates placement against rules.
  - System computes best path for that exact user-defined layout.
- Planning modes:
  - `Strict Competition`: strict rule priority (including entrance-first when applicable).
  - `Practical Fast Path`: lower total action count is prioritized first.
  - `Practical Fast Path` additional priority: minimize `wait + drop` actions first.
  - User override: first pickup is not forced to be from entrance-side targets.

### 3.3 Planner functionality
- Path finder (A*/Dijkstra) from entrance zone to a valid exit block (10/12)
- Move constraints:
  - Move to adjacent block only
  - Absolute pile height difference ≤200 mm (`|Δh| ≤200`)
  - If modeling incline, require angle(Δh, block_distance) ≤20°
  - 200→400 and 400→600 are valid; 0→400 or 400→0 are invalid (same for all jumps >200 mm).
  - Entry transition `E -> first Forest block` must satisfy `|Δh| = 200 mm`.
  - Exit transition `last Forest block -> Exit zone` must satisfy `|Δh| = 200 mm`.
- Pickup rules:
  - Robot can pick the KFS if target block has R2 KFS and carry_count < 2.
  - Robot may pick R2 KFS from an adjacent block without climbing onto that target block.
  - Planner must route to a valid adjacent anchor block, then perform pickup.
  - New KFS is taken by grip.
  - If grip is already occupied and robot wants next R2 KFS, it executes `drop grip` first, then `pickup`.
  - After pickup, carry_count reflects currently carried amount and block becomes empty.
  - User mechanical rule: if grip already holds a box and next target block has R2 KFS, robot performs `drop grip` then `pickup`.
  - Planner must minimize total handling actions: `pickup_count + drop_count`.
  - Planner should prioritize two-scroll collection when valid.
  - If only one-scroll plan is selected while valid two-scroll plan exists, planner score must include penalty.
  - If route needs to pass an `R1` block, planner inserts a `wait-for-R1-clear` action before passing.
  - Policy: pick earliest encountered feasible target first, and pick late path-blocking/last encountered target near the end.
  - If a picked target is in the middle (neither first nor last encountered), planner adds middle-drop action and penalty.
  - Overall objective: minimize unnecessary `wait` and `drop` actions as much as possible.
  - In `Practical Fast Path`, first/last pickup policy penalties are disabled to favor minimum-action routes.
- Exit rules:
  - Robot must reach 10 or 12 with carry_count ≥1.
  - If selected exit block contains R2 KFS, robot must collect that exit-block R2 KFS before crossing exit.
  - Optionally allow tries if fails: retry mechanism as in 4.4.21.
- Capacity rules:
  - carry_count must not exceed 2.
  - If carry_count == 2, pickup action is blocked.

### 3.4 Estimation and ranking
- For each candidate path, estimate:
  - total steps (moves)
  - total delta height climbed
  - terrain actions: `climb_actions + descend_actions`
  - estimated time (step_time + load_time + pickup_time)
  - risk score (illegal moves, retry incidence)
- Score function for ranking in Tab A:
  - `score = w1*time + w2*risk + w3*steps + w4*energy + w5*handling_ops`
  - Add `w6*one_scroll_penalty + w7*r1_proximity_penalty`
  - Include `wait_action` penalty/time to discourage unnecessary waiting.
  - Add strategic exit points: `exit=10` gets bonus over `exit=12`.
  - Exit-block R2 pickup is enforced as a hard feasibility rule before scoring.
  - Add first-last pickup policy penalty for middle-target selection.
  - `handling_ops` must include `pickup + drop + wait + climb + descend`.
  - Lower score = better candidate.
  - In `Practical Fast Path`, plans are primarily sorted by lower `Handling Ops Total`, then by score.
  - In `Practical Fast Path`, apply stronger penalty to `wait` and `drop`, and sort by lower `wait+drop` first.
  - In `Practical Fast Path`, exit-10 strategic bonus is disabled.

### 3.5 GUI
- Shared map view:
  - 12-block forest map with color coded heights (green gradient)
  - Show current robot position, relevant path line
  - Distinguish blocks: entrance, exits, R2 KFS, R1 KFS, Fake KFS.
- Tab A controls:
  - `Generate/Load scenarios`
  - `Compute Top Plans`
  - `Show Rank #1..#N`
  - `Simulate selected plan`
- Tab B controls:
  - `Place R2 KFS`
  - `Place R1 KFS`
  - `Place Fake KFS`
  - `Validate Layout`
  - `Compute Path`
  - `Simulate`
  - `Reset`
- Indicators:
  - `NW` path (good / invalid moves, rule violations)
  - `Current load` and `Pickup status`.
- Reporting panel:
  - Final route (block sequence)
  - `Total Steps`, `Height Gain`, `Time`, `Risk`, `KFS collected`.
  - `Pickup Actions`, `Drop Actions`, `Wait Actions`, `Climb Actions`, `Descend Actions`, `Terrain Actions`, `Handling Ops Total`.
  - `Wait+Drop Actions`, `Wait+Drop Penalty`.
  - `R1 Touch Count`, `R1 Near Count`, `R1 Proximity Penalty`, `One-scroll Penalty`.
  - `Strategic Exit Points` (exit 10 > exit 12).
  - `Exit Pickup Bonus`, `Missed Exit Pickup Penalty`.
  - `Policy Drop Actions`, `Policy Penalty`.
  - `Plan Rank` (for Tab A)

### 3.6 Rules validation engine
- `validate_move(from, to)` returns true/false plus reason:
  - adjacency
  - destination block must not contain `Fake` KFS (violation if touched)
  - destination block with `R1` KFS is passable only with wait action
  - abs(height diff) ≤200 mm
  - slope ≤20°
- `validate_pickup(block)`:
  - target block has R2 KFS
  - current robot block is adjacent to target block
  - carry_count < 2
  - available slot exists (hidden_slot or grip_slot)
- `validate_exit(block)`:
  - block in {10,12}
  - carry_count >= 1
  - abs(height(block) - 0) == 200
- `validate_layout(layout)`:
  - Fake KFS not at blocks {1,2,3}
  - R1 KFS not at blocks {5,8}
  - KFS count check (3 R1, 4 R2, 1 Fake) for full match mode
  - No illegal overlap of multiple KFS in one block
- `rank_policy(plans)`:
  - Prefer valid plans with `2` pickups.
  - Among same pickup-count plans, choose lower total score.
  - Penalize plans that pass through/near R1 KFS blocks.

### 3.7 Visual and field-spec requirements (from your provided field image)
- App must include a `Field Spec` panel that displays official-like constants used by planner:
  - Forest heights: `200H/400H/600H` only.
  - Forest footprint: `3x4 blocks`.
  - Pathway ring: `1200 mm`.
  - Entrance links: `2`.
  - Exit blocks: `10,12`.
- App must include color legend (RGB) only for Meihua blocks:
  - Meihua Forest (200mm): `41-82-16`
  - Meihua Forest (400mm): `42-113-56`
  - Meihua Forest (600mm): `152-166-80`
- UI map rendering must use these RGB values (or nearest CSS color) for consistency with test field visualization.

## 4. Test cases
- TC1: 12-block all 200 mm; R2 start at entrance; one R2 KFS at adjacent block; exit at 10.
- TC2: mix 200/400/600 with pathway(0); verify 200→400 is allowed but 0→400 and 400→0 are rejected.
- TC3: 1-3 contain R2 KFS, verify first pick-up from entrance block and not skipping.
- TC4: carry two-scroll limit; third pickup attempt must fail.
- TC5: invalid route that goes to 4/5 etc without KFS and remains stuck; validate fail-status.
- TC6 (Tab A): auto mode returns ranked Top-N plans with rule-compliant routes only.
- TC7 (Tab B): manual placement with Fake KFS in block 1 must fail layout validation.
- TC8 (Tab B): after valid manual placement, planner computes a legal path and simulation runs end-to-end.
- TC9: placing R1 KFS on block 5 or 8 must fail layout validation.
- TC10: entry boundary with 0→400 (or 0→600) must be rejected; only 0→200 accepted.
- TC11: exit boundary from 400/600-height exit block to 0 level must be rejected; only 200→0 accepted.
- TC12: if grip has a box and robot picks next R2 KFS, planner inserts `drop -> pickup` and counts both operations.
- TC13: among valid plans, planner prefers fewer handling operations (`pickup+drop`) when total travel is similar.
- TC14: if both 1-scroll and 2-scroll routes are valid, planner ranks 2-scroll route higher.
- TC15: route passing near/through R1 KFS receives higher penalty and ranks lower than farther route.
- TC16: any route that enters a block with `Fake` KFS must be rejected as violation.
- TC17: route passing through `R1` KFS block is valid only with inserted wait action.
- TC18: pickup is valid when robot stays on adjacent anchor block and does not climb onto target R2 block.
- TC19: if two plans are similar, plan exiting from block 10 must rank higher than plan exiting from block 12.
- TC20: when exit block has R2 KFS, plan skipping that exit pickup (e.g., picking 9 then exit 12) must be rejected as invalid.
- TC21: planner prefers first encountered pickup and last encountered/path-blocking pickup; middle pickup adds penalty.
- TC22: moving across height changes must increase action count via climb/descend actions.
- TC23: in `Practical Fast Path`, a lower-action route must rank above a higher-action route when both are valid.
- TC24: if two routes are similar, route with lower `wait+drop` must rank higher.
- TC25: in `Practical Fast Path`, a route like `2-3-6-9-12` with lower actions can rank above entrance-side pickup routes.

## 5. Next steps
1. Implement this as Python CLI first (graph + rule engine).
2. Add Tkinter/Qt (or web with React/Vue) GUI.
3. Add route planner for R1 if needed.
4. Add random map scenario generator and build analytics (mean completion time, success probability).

---

### Notes
- “Angle 20°” rule not explicitly textually confirmed in rulebook excerpt, but user described requirement.
- Must align with official rulebook for Robocon 2026; if the real rule text differs, adjust accordingly.
- Field geometry constants above are taken from your provided drawing screenshot; before final competition use, verify against official Appendix dimension sheet.
