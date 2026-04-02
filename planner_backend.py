from __future__ import annotations

import heapq
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Set, Tuple

ENTRANCE_NODE = "E"
ENTRANCE_BLOCKS = (2,)
PATHWAY_HEIGHT_MM = 0

GRAPH: Dict[int, Tuple[int, ...]] = {
    1: (2, 4),
    2: (1, 3, 5),
    3: (2, 6),
    4: (1, 5, 7),
    5: (2, 4, 6, 8),
    6: (3, 5, 9),
    7: (4, 8, 10),
    8: (5, 7, 9, 11),
    9: (6, 8, 12),
    10: (7, 11),
    11: (8, 10, 12),
    12: (9, 11),
}

DEFAULT_HEIGHTS: Dict[int, int] = {
    1: 400,
    2: 200,
    3: 400,
    4: 200,
    5: 400,
    6: 600,
    7: 400,
    8: 600,
    9: 400,
    10: 200,
    11: 400,
    12: 200,
}


@dataclass(frozen=True)
class OfficialRules:
    entrance_blocks: Tuple[int, ...] = ENTRANCE_BLOCKS
    official_exit_blocks: Tuple[int, ...] = (10, 12)
    # Assumption: legal boundary blocks for R1 are perimeter blocks in the 3x4 forest.
    legal_r1_boundary_blocks: Tuple[int, ...] = (1, 2, 3, 4, 6, 7, 9, 10, 11, 12)
    must_exit_with_at_least_one_r2: bool = True
    first_pick_from_entrance_if_r2_in_1_3: bool = True
    # If True, R1 blocks can be cleared by R1 robot after wait.
    allow_r1_clearance_wait: bool = True


@dataclass(frozen=True)
class RobotLimits:
    max_step_mm: int = 200
    max_total_scrolls: int = 2
    max_hidden_slot: int = 1
    max_grip_slot: int = 1
    # Technical mechanical constraint from team robot:
    # only these transitions are physically possible.
    allowed_height_transitions: Tuple[Tuple[int, int], ...] = (
        (0, 200),
        (200, 0),
        (200, 400),
        (400, 200),
        (400, 600),
        (600, 400),
    )


@dataclass(frozen=True)
class StrategyPreferences:
    prefer_two_pickups: bool = True
    practical_sort_wait_drop_first: bool = True
    min_pickups_required: int = 1
    step_weight: float = 1.5
    pickup_weight: float = 4.0
    drop_weight: float = 4.0
    turn_weight: float = 4.0
    wait_weight: float = 4.0
    one_scroll_penalty: float = 30.0
    strict_exit10_bonus: float = 3.0
    strict_exit12_bonus: float = 0.0


@dataclass(frozen=True)
class PlannerConfig:
    official: OfficialRules = OfficialRules()
    robot: RobotLimits = RobotLimits()
    strategy: StrategyPreferences = StrategyPreferences()


@dataclass(frozen=True)
class Layout:
    r2_blocks: Tuple[int, ...]
    r1_blocks: Tuple[int, ...]
    fake_blocks: Tuple[int, ...]
    heights: Dict[int, int]

    @staticmethod
    def from_lists(
        r2_blocks: Iterable[int],
        r1_blocks: Iterable[int],
        fake_blocks: Iterable[int],
        heights: Optional[Dict[int, int]] = None,
    ) -> "Layout":
        return Layout(
            r2_blocks=tuple(sorted(r2_blocks)),
            r1_blocks=tuple(sorted(r1_blocks)),
            fake_blocks=tuple(sorted(fake_blocks)),
            heights=dict(heights or DEFAULT_HEIGHTS),
        )


@dataclass
class Plan:
    route: List[int]
    pickups: List[int]
    exit_block: int
    steps: int
    pickup_actions: int
    drop_actions: int
    turn_actions: int
    wait_actions: int
    carried_count: int
    score: float


def neighbors(node: str | int) -> Tuple[int, ...]:
    if node == ENTRANCE_NODE:
        return ENTRANCE_BLOCKS
    return GRAPH.get(int(node), ())


def block_height(layout: Layout, node: str | int) -> int:
    if node == ENTRANCE_NODE:
        return PATHWAY_HEIGHT_MM
    return layout.heights[int(node)]


def movement_height_ok(layout: Layout, from_node: str | int, to_node: int, robot: RobotLimits) -> bool:
    h_from = block_height(layout, from_node)
    h_to = block_height(layout, to_node)
    if abs(h_to - h_from) > robot.max_step_mm:
        return False
    return (h_from, h_to) in set(robot.allowed_height_transitions)


def validate_layout(layout: Layout, config: PlannerConfig, strict_counts: bool = True) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    all_blocks = set(range(1, 13))

    for group_name, group in (("R2", layout.r2_blocks), ("R1", layout.r1_blocks), ("FAKE", layout.fake_blocks)):
        for b in group:
            if b not in all_blocks:
                errors.append(f"{group_name} block id out of range: {b}")

    overlaps = set(layout.r2_blocks) & set(layout.r1_blocks)
    overlaps |= set(layout.r2_blocks) & set(layout.fake_blocks)
    overlaps |= set(layout.r1_blocks) & set(layout.fake_blocks)
    if overlaps:
        errors.append(f"Overlapping KFS placement at blocks: {sorted(overlaps)}")

    if any(b in {1, 2, 3} for b in layout.fake_blocks):
        errors.append("Fake KFS cannot be placed on blocks 1,2,3")

    legal_r1 = set(config.official.legal_r1_boundary_blocks)
    bad_r1 = [b for b in layout.r1_blocks if b not in legal_r1]
    if bad_r1:
        errors.append(f"R1 KFS must be on legal boundary blocks only: {sorted(bad_r1)}")

    if strict_counts:
        if len(layout.r2_blocks) != 4:
            errors.append("R2 count must be exactly 4")
        if len(layout.r1_blocks) != 3:
            errors.append("R1 count must be exactly 3")
        if len(layout.fake_blocks) != 1:
            errors.append("Fake count must be exactly 1")

    for b in all_blocks:
        h = layout.heights.get(b)
        if h not in {200, 400, 600}:
            errors.append(f"Invalid height on block {b}: {h}")

    return (len(errors) == 0, errors)


def validate_move(
    layout: Layout,
    from_node: str | int,
    to_node: int,
    remaining_r2: Set[int],
    config: PlannerConfig,
) -> Tuple[bool, str]:
    if to_node not in neighbors(from_node):
        return False, "not adjacent (4-neighbor only)"
    if to_node in remaining_r2 or to_node in set(layout.fake_blocks):
        return False, "cannot step onto a block that currently contains KFS"
    if to_node in set(layout.r1_blocks) and not config.official.allow_r1_clearance_wait:
        return False, "cannot step onto a block that currently contains KFS"
    if not movement_height_ok(layout, from_node, to_node, config.robot):
        return False, "height transition is not allowed by robot mechanics"

    if to_node in set(layout.r1_blocks) and config.official.allow_r1_clearance_wait:
        return True, "ok_with_r1_wait"
    return True, "ok"


def validate_exit(layout: Layout, node: int, carried: int, config: PlannerConfig) -> Tuple[bool, str]:
    if node not in set(config.official.official_exit_blocks):
        return False, f"exit block must be one of {sorted(config.official.official_exit_blocks)}"
    if config.official.must_exit_with_at_least_one_r2 and carried < 1:
        return False, "must exit with at least one R2 KFS"
    return True, "ok"


def validate_pickup(
    anchor_node: str | int,
    target_node: int,
    remaining_r2: Set[int],
    hidden: int,
    grip: int,
    config: PlannerConfig,
) -> Tuple[bool, str]:
    if target_node not in remaining_r2:
        return False, "target is not an uncollected R2 KFS"
    if target_node not in neighbors(anchor_node):
        return False, "pickup target is not adjacent to anchor"
    if _pickup_transition(hidden, grip, config) is None:
        return False, "pickup blocked by carry capacity"
    return True, "ok"


def _pickup_transition(hidden: int, grip: int, config: PlannerConfig) -> Optional[Tuple[int, int, int, int]]:
    """Return (next_hidden, next_grip, pickup_actions, drop_actions) or None if impossible."""
    carried = hidden + grip
    if carried >= config.robot.max_total_scrolls:
        # Capacity full: allow dropping currently gripped scroll on field,
        # then picking the new target scroll with grip.
        if grip > 0:
            return hidden, grip, 1, 1
        return None

    if grip < config.robot.max_grip_slot:
        return hidden, grip + 1, 1, 0

    if hidden < config.robot.max_hidden_slot:
        # Move current grip to hidden, then pick new one into grip.
        return hidden + 1, grip, 1, 1

    return None


def validate_candidate_plan(layout: Layout, route: List[int], pickups: List[int], config: PlannerConfig) -> Tuple[bool, List[str]]:
    reasons: List[str] = []
    remaining_r2 = set(layout.r2_blocks)
    pickup_order = list(pickups)

    node: str | int = ENTRANCE_NODE
    hidden = 0
    grip = 0
    wait_actions = 0
    entrance_targets = set(config.official.entrance_blocks)
    if config.official.first_pick_from_entrance_if_r2_in_1_3 and remaining_r2.intersection(entrance_targets):
        if not pickup_order:
            reasons.append("first pickup from entrance required when R2 exists on entrance blocks")
        else:
            first_target = pickup_order[0]
            if first_target not in neighbors(ENTRANCE_NODE):
                reasons.append("first pickup must be done from entrance anchor")
        if reasons:
            return False, reasons

    def consume_pickups_at_anchor(anchor: str | int) -> Optional[str]:
        nonlocal hidden, grip
        while pickup_order and pickup_order[0] in neighbors(anchor):
            target = pickup_order.pop(0)
            ok_pick, pick_reason = validate_pickup(anchor, target, remaining_r2, hidden, grip, config)
            if not ok_pick:
                return f"invalid pickup at anchor {anchor} for target {target}: {pick_reason}"
            transition = _pickup_transition(hidden, grip, config)
            if transition is None:
                return f"pickup blocked by carry capacity before picking {target}"
            hidden, grip, _, _ = transition
            remaining_r2.remove(target)
        return None

    err = consume_pickups_at_anchor(ENTRANCE_NODE)
    if err:
        return False, [err]

    for nxt in route:
        ok, reason = validate_move(layout, node, nxt, remaining_r2, config)
        if not ok:
            reasons.append(f"invalid move {node}->{nxt}: {reason}")
            return False, reasons
        if reason == "ok_with_r1_wait":
            wait_actions += 1
        node = nxt
        err = consume_pickups_at_anchor(node)
        if err:
            return False, [err]

    if pickup_order:
        reasons.append(f"route ended before these pickups were reachable: {pickup_order}")
        return False, reasons

    carried = hidden + grip
    ok, reason = validate_exit(layout, int(route[-1]) if route else -1, carried, config)
    if not ok:
        reasons.append(reason)

    if route and route[-1] in remaining_r2:
        reasons.append("exit block contains unpicked R2 KFS")

    return (len(reasons) == 0, reasons)


def plan_routes(layout: Layout, config: Optional[PlannerConfig] = None, top_n: int = 5, mode: str = "practical") -> List[Plan]:
    cfg = config or PlannerConfig()
    ok, errs = validate_layout(layout, cfg, strict_counts=True)
    if not ok:
        raise ValueError(f"invalid layout: {errs}")

    initial_remaining = frozenset(layout.r2_blocks)
    pq: List[Tuple[Tuple[int, int, int], Tuple[str | int, frozenset, int, int], List[int], List[int], int, int, int]] = []
    # priority tuple: (steps, handling_ops, -picked)
    heapq.heappush(pq, ((0, 0, 0), (ENTRANCE_NODE, initial_remaining, 0, 0), [], [], 0, 0, 0))

    best_cost: Dict[Tuple[str | int, frozenset, int, int], Tuple[int, int, int]] = {}
    finals: List[Plan] = []

    while pq:
        (steps, handling_ops, neg_picked), (node, rem, hidden, grip), route, pickups, pick_actions, drop_actions, wait_actions = heapq.heappop(pq)
        key = (node, rem, hidden, grip)
        cost_here = (steps, handling_ops, neg_picked)
        if key in best_cost and best_cost[key] <= cost_here:
            continue
        best_cost[key] = cost_here

        carried = hidden + grip
        if node != ENTRANCE_NODE:
            exit_ok, _ = validate_exit(layout, int(node), carried, cfg)
            if exit_ok and int(node) not in rem and len(pickups) >= cfg.strategy.min_pickups_required:
                finals.append(
                    Plan(
                        route=list(route),
                        pickups=list(pickups),
                        exit_block=int(node),
                        steps=steps,
                        pickup_actions=pick_actions,
                        drop_actions=drop_actions,
                        turn_actions=drop_actions,
                        wait_actions=wait_actions,
                        carried_count=carried,
                        score=0.0,
                    )
                )

        rem_set = set(rem)
        # Pickup transitions from current anchor.
        for target in neighbors(node):
            if target not in rem_set:
                continue

            if (
                cfg.official.first_pick_from_entrance_if_r2_in_1_3
                and len(pickups) == 0
                and set(rem).intersection(set(cfg.official.entrance_blocks))
            ):
                if node != ENTRANCE_NODE:
                    continue

            transition = _pickup_transition(hidden, grip, cfg)
            if transition is None:
                continue
            n_hidden, n_grip, add_pick, add_drop = transition
            n_rem = frozenset(x for x in rem if x != target)
            n_pickups = list(pickups) + [target]
            n_steps = steps
            n_handling = handling_ops + add_pick + add_drop
            n_neg_picked = -(len(n_pickups))
            heapq.heappush(
                pq,
                (
                    (n_steps, n_handling, n_neg_picked),
                    (node, n_rem, n_hidden, n_grip),
                    list(route),
                    n_pickups,
                    pick_actions + add_pick,
                    drop_actions + add_drop,
                    wait_actions,
                ),
            )

        # Move transitions.
        for nxt in neighbors(node):
            ok_move, move_reason = validate_move(layout, node, nxt, rem_set, cfg)
            if not ok_move:
                continue
            add_wait = 1 if move_reason == "ok_with_r1_wait" else 0
            heapq.heappush(
                pq,
                (
                    (steps + 1, handling_ops + add_wait, neg_picked),
                    (nxt, rem, hidden, grip),
                    list(route) + [nxt],
                    list(pickups),
                    pick_actions,
                    drop_actions,
                    wait_actions + add_wait,
                ),
            )

    ranked = rank_plans(finals, cfg, mode=mode)
    return ranked[:top_n]


def rank_plans(plans: List[Plan], config: PlannerConfig, mode: str = "practical") -> List[Plan]:
    if not plans:
        return []

    exists_two = any(len(p.pickups) >= 2 for p in plans)

    out: List[Plan] = []
    for p in plans:
        one_scroll_penalty = (
            config.strategy.one_scroll_penalty
            if config.strategy.prefer_two_pickups and exists_two and len(p.pickups) < 2
            else 0.0
        )
        strategic_exit_bonus = 0.0
        if mode != "practical":
            if p.exit_block == 10:
                strategic_exit_bonus = config.strategy.strict_exit10_bonus
            elif p.exit_block == 12:
                strategic_exit_bonus = config.strategy.strict_exit12_bonus
        p.score = float(
            p.steps * config.strategy.step_weight
            + p.pickup_actions * config.strategy.pickup_weight
            + p.drop_actions * config.strategy.drop_weight
            + p.turn_actions * config.strategy.turn_weight
            + p.wait_actions * config.strategy.wait_weight
            + one_scroll_penalty
            - strategic_exit_bonus
        )
        out.append(p)

    if mode == "practical" and config.strategy.practical_sort_wait_drop_first:
        out.sort(key=lambda x: (x.wait_actions + x.drop_actions, x.score, x.steps))
    else:
        out.sort(key=lambda x: (x.score, x.steps))
    return out
