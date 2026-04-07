# Robocon 2026 Meihua Forest R2 Planner Requirements

## Goal
Build a Python app that validates Meihua Forest layouts and computes legal R2 plans.

The app must separate:
1. Official competition rules
2. Robot physical limits
3. Team strategy preferences

Do not mix these three categories.

---

## A. Official rules (hard constraints)

These are mandatory and must never be violated.

### Field
- Meihua Forest has 12 blocks, IDs 1..12, arranged as official 3x4 layout.
- Entrance block is 2.
- Exit blocks are 10, 12.

### Setup layout
- Exactly 3 R1 KFS
- Exactly 4 R2 KFS
- Exactly 1 Fake KFS
- At most one KFS per block

### Placement rules
- R1 KFS may only be placed on boundary blocks adjacent to the pathway.
- R2 KFS may be placed on any vacant block within the Forest.
- Fake KFS may be placed on any vacant block within the Forest except blocks 1, 2, 3.

### R2 movement / pickup rules
- R2 enters Forest from the R2 Entrance Zone.
- R2 exits Forest through one of 10, 12.
- R2 may pick up only R2 KFS.
- R2 may pick up only from an adjacent block (4-neighbor adjacency only, no diagonal).
- If any of 1,2,3 contains an R2 KFS, then R2’s first pickup must be from the Entrance Zone.
- R2 must carry at least one R2 KFS when exiting Forest.
- R2 must never touch Fake KFS.
- R2 must never touch R1 KFS.
- R2 must never move onto a Forest block that currently contains any KFS (R1, R2, or Fake).

### Important modeling rule
- Pickup is performed from an adjacent anchor block.
- The robot does NOT climb onto the target KFS block to pick it.

---

## B. Robot physical limits (our robot only)

These are NOT official rules. They are robot-specific feasibility constraints.

- R2 can carry at most 2 R2 KFS total:
  - 1 hidden/internal slot
  - 1 gripper slot
- R2 can move only if one-step height change is <= 200 mm.
- Robot technical movement transitions are only:
  - `0 -> 200`, `200 -> 0`
  - `200 -> 400`, `400 -> 200`
  - `400 -> 600`, `600 -> 400`
- Any other transition is mechanically impossible (including same-height transitions such as `200 -> 200`).
- Field baseline outside forest is 0 mm.
- Entry/exit transition must satisfy the same robot step-height rule.
- Robot uses only 4-neighbor moves.

Use these as robot feasibility checks, not as official rule validation.

---

## C. Team strategy preferences (soft constraints)

These are preferences for ranking, not legality.

- Prefer collecting 2 R2 KFS before exit when feasible.
- Prefer fewer handling operations.
- Prefer lower wait time.
- Prefer routes farther from R1 KFS if multiple legal routes exist.
- Prefer simpler routes with fewer moves.

These affect scoring only. They must never invalidate an otherwise legal route.

---

## D. Data model

Represent:
- block_id: 1..12
- block height
- block type: empty / R1 / R2 / Fake
- adjacency list
- robot state:
  - current anchor position
  - hidden slot occupied yes/no
  - gripper occupied yes/no
  - carry_count 0..2

---

## E. Required functions

### Layout validation
Implement:

- validate_layout(layout)
  - checks counts: 3 R1, 4 R2, 1 Fake
  - checks no overlap
  - checks Fake not in 1,2,3
  - checks R1 only on legal boundary blocks

### Move validation
Implement:

- validate_move(from_block, to_block, layout, robot_limits)
  - adjacent move only
  - destination must be empty
  - height delta within robot limit

### Pickup validation
Implement:

- validate_pickup(anchor_block, target_block, layout, robot_state)
  - target must contain R2 KFS
  - target must be adjacent to anchor
  - carry_count < 2
  - robot remains on anchor block
  - target block becomes empty after pickup

### Exit validation
Implement:

- validate_exit(anchor_block, robot_state)
  - anchor block must be one of 10,12
  - carry_count >= 1

### Planner
Implement:

- find_all_legal_plans(layout, robot_limits)
- rank_plans(plans, strategy_preferences)

Planner must:
- generate only legal plans
- never step onto occupied blocks
- support 1-scroll and 2-scroll routes
- return detailed action traces

---

## F. Output format

For each plan return:
- plan_id
- anchor path (sequence of anchor blocks)
- pickup targets in order
- exit block
- total moves
- total pickups
- total drops
- total waits
- carry count by step
- legality status
- rejection reason if invalid
- score

---

## G. UI requirements

Two tabs:

### Tab 1: Manual Layout + Plan
- manual placement of R1, R2, Fake
- validate layout
- compute legal plans
- simulate selected plan

### Tab 2: Scenario Browser
- generate valid layouts
- compute and rank top plans
- allow browsing scenarios one by one

---

## H. Acceptance criteria

A solution is correct only if:

1. It never generates a route that steps onto an occupied block.
2. It never treats strategy preferences as hard legality rules.
3. It uses entrance set {2}.
4. It uses exit set {10,12}.
5. It treats pickup as adjacent-anchor pickup, not stepping onto target.
6. It cleanly separates:
   - official rules
   - robot limits
   - strategy preferences
7. It explains why any rejected route is invalid.
8. It includes at least 10 unit tests.

---

## I. Implementation notes

- Use Python
- Keep logic modular
- Start with CLI / backend planner first
- Then add Streamlit GUI
- Write tests before GUI integration

## J. Robot bridge

For robot integration, the planner should expose:

- route as ordered anchor blocks,
- pickup targets,
- exit block,
- a ROS-facing bridge that can publish the chosen route as `nav_msgs/Path`,
- and a mapping from block IDs to real field anchor poses instead of only a placeholder grid.

Current integration note:

- `/home/saruul/Meihua_Forest/planner_ros_bridge.py` now publishes `/planner/path` for `automate_robot`,
- `automate_robot/src/main` buffers that path and only consumes it in the `MEIHUA_FOREST` phase after `enter_meihua_forest`,
- the remaining gap is replacing the bridge's configurable grid mapping with field-calibrated Meihua anchor coordinates.

The bridge may keep block IDs internal, but the robot-facing side should publish map-frame anchor poses so the robot project can subscribe directly.
