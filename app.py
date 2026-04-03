import random
from dataclasses import replace
from itertools import combinations
from typing import Iterable

import streamlit as st

from planner_backend import (
    DEFAULT_HEIGHTS,
    ENTRANCE_BLOCKS,
    ENTRY_LANE_BLOCKS,
    Layout,
    OfficialRules,
    PlannerConfig,
    RobotLimits,
    StrategyPreferences,
    plan_routes,
    validate_layout,
)

HEIGHT_COLORS = {
    200: "rgb(41,82,16)",
    400: "rgb(42,113,56)",
    600: "rgb(152,166,80)",
}

ALL_FIELD_BLOCKS = tuple(range(1, 13))

OPPONENT_ROBOT_PRESETS = {
    "Standard opponent": {"carry_capacity": 2, "max_step_mm": 200, "exit_mode": "Official exits"},
    "Single-scroll runner": {"carry_capacity": 1, "max_step_mm": 200, "exit_mode": "Official exits"},
    "Four-scroll carrier": {"carry_capacity": 4, "max_step_mm": 200, "exit_mode": "Official exits"},
    "40cm climber": {"carry_capacity": 2, "max_step_mm": 400, "exit_mode": "Official exits"},
    "Full threat": {"carry_capacity": 4, "max_step_mm": 400, "exit_mode": "Any block"},
}

OPPONENT_SCORING_PRESETS = {
    "Balanced": {
        "min_pickups_required": 1,
        "step_weight": 1.5,
        "pickup_weight": 4.0,
        "drop_weight": 4.0,
        "turn_weight": 4.0,
        "wait_weight": 4.0,
        "one_scroll_penalty": 30.0,
    },
    "Speed-first": {
        "min_pickups_required": 1,
        "step_weight": 5.0,
        "pickup_weight": 1.0,
        "drop_weight": 1.0,
        "turn_weight": 1.0,
        "wait_weight": 1.0,
        "one_scroll_penalty": 0.0,
    },
    "Wait-averse": {
        "min_pickups_required": 1,
        "step_weight": 1.0,
        "pickup_weight": 2.0,
        "drop_weight": 2.0,
        "turn_weight": 2.0,
        "wait_weight": 8.0,
        "one_scroll_penalty": 20.0,
    },
    "Handling-averse": {
        "min_pickups_required": 1,
        "step_weight": 1.0,
        "pickup_weight": 4.0,
        "drop_weight": 9.0,
        "turn_weight": 4.0,
        "wait_weight": 5.0,
        "one_scroll_penalty": 20.0,
    },
    "Collector": {
        "min_pickups_required": 2,
        "step_weight": 1.0,
        "pickup_weight": 2.0,
        "drop_weight": 2.0,
        "turn_weight": 2.0,
        "wait_weight": 3.0,
        "one_scroll_penalty": 45.0,
    },
}


def parse_csv_ids(raw: str):
    raw = (raw or "").strip()
    if not raw:
        return []
    out = []
    for p in raw.split(","):
        t = p.strip()
        if not t:
            continue
        if not t.isdigit():
            raise ValueError(f"Invalid block id: {t}")
        bid = int(t)
        if bid < 1 or bid > 12:
            raise ValueError(f"Block id out of range: {bid}")
        out.append(bid)
    return sorted(out)


def token_at(layout: Layout, bid: int) -> str:
    r2_blocks = set(layout.r2_blocks)
    r1_blocks = set(layout.r1_blocks)
    fake_blocks = set(layout.fake_blocks)
    if bid in r2_blocks:
        return "R2"
    if bid in r1_blocks:
        return "R1"
    if bid in fake_blocks:
        return "FAKE"
    return "EMPTY"


def render_field_spec():
    st.markdown("**Field Spec (Rulebook-like)**")
    st.caption(
        f"Grid 3x4 | Entrance anchor: {','.join(map(str, ENTRANCE_BLOCKS))} | "
        f"Protected entry lane: {','.join(map(str, ENTRY_LANE_BLOCKS))} | Exit blocks: 10,12"
    )
    st.caption("Heights only: 200/400/600mm | Color legend follows Meihua standard RGB")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            '<div style="background:rgb(41,82,16);padding:10px;border-radius:8px;color:white;text-align:center;">200mm</div>',
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            '<div style="background:rgb(42,113,56);padding:10px;border-radius:8px;color:white;text-align:center;">400mm</div>',
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            '<div style="background:rgb(152,166,80);padding:10px;border-radius:8px;color:#111;text-align:center;">600mm</div>',
            unsafe_allow_html=True,
        )


def render_meihua_map(layout: Layout, route=None):
    route = route or []
    route_index = {b: i + 1 for i, b in enumerate(route)}
    route_set = set(route)

    html = [
        """
        <style>
          .mf-wrap {border:1px solid #263145; border-radius:14px; padding:12px; background:#0b1020;}
          .mf-grid {display:grid; grid-template-columns:repeat(3, minmax(120px,1fr)); gap:8px;}
          .mf-cell {
            position:relative; min-height:96px; border-radius:10px; border:1px solid rgba(255,255,255,0.20);
            padding:8px; color:#f6f7fb; overflow:hidden;
          }
          .mf-title {font-weight:800; font-size:14px;}
          .mf-sub {font-size:12px; opacity:0.94;}
          .mf-badge {
            position:absolute; right:8px; bottom:8px; font-size:11px; font-weight:700;
            border-radius:999px; padding:2px 8px; background:rgba(0,0,0,0.45); border:1px solid rgba(255,255,255,0.35);
          }
          .mf-step {
            position:absolute; left:8px; bottom:8px; width:24px; height:24px; border-radius:50%;
            display:flex; align-items:center; justify-content:center; background:#1c63d5; color:white; font-weight:800;
          }
          .mf-route {outline:3px solid #45a5ff; outline-offset:-2px;}
          .mf-entry {box-shadow:inset 0 0 0 2px #0ae593;}
          .mf-exit {box-shadow:inset 0 0 0 2px #ff8963;}
        </style>
        """
    ]
    html.append('<div class="mf-wrap"><div class="mf-grid">')

    exit_blocks = {10, 12}
    for bid in range(1, 13):
        token = token_at(layout, bid)
        cls = ["mf-cell"]
        if bid in route_set:
            cls.append("mf-route")
        if bid in set(ENTRANCE_BLOCKS):
            cls.append("mf-entry")
        if bid in exit_blocks:
            cls.append("mf-exit")

        title_parts = [f"#{bid}"]
        if bid in set(ENTRANCE_BLOCKS):
            title_parts.append("ENT")
        if bid in exit_blocks:
            title_parts.append("EXIT")

        step_html = f'<div class="mf-step">{route_index[bid]}</div>' if bid in route_index else ""

        html.append(
            f'<div class="{" ".join(cls)}" style="background:{HEIGHT_COLORS[layout.heights[bid]]};">'
            f'<div class="mf-title">{" | ".join(title_parts)}</div>'
            f'<div class="mf-sub">H={layout.heights[bid]}mm</div>'
            f'<div class="mf-badge">{token}</div>'
            f"{step_html}"
            "</div>"
        )

    html.append("</div></div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def random_valid_layout(cfg: PlannerConfig, max_tries: int = 2000):
    all_blocks = list(range(1, 13))
    forbidden_fake_blocks = set(cfg.official.fake_forbidden_blocks)
    r1_pool = list(cfg.official.legal_r1_boundary_blocks)

    for _ in range(max_tries):
        r1 = sorted(random.sample(r1_pool, 3))
        occupied = set(r1)

        fake_pool = [b for b in all_blocks if b not in forbidden_fake_blocks and b not in occupied]
        if not fake_pool:
            continue
        fake = random.choice(fake_pool)
        occupied.add(fake)

        r2_pool = [b for b in all_blocks if b not in occupied]
        if len(r2_pool) < 4:
            continue
        r2 = sorted(random.sample(r2_pool, 4))

        layout = Layout.from_lists(r2_blocks=r2, r1_blocks=r1, fake_blocks=[fake], heights=DEFAULT_HEIGHTS)
        ok, _ = validate_layout(layout, cfg, strict_counts=True)
        if ok:
            return layout

    return None


def iter_layout_candidates(
    base_r2, base_r1, base_fake, cfg: PlannerConfig, max_candidates: int = 40000
) -> Iterable[Layout]:
    need_r2 = 4 - len(base_r2)
    need_r1 = 3 - len(base_r1)
    need_fake = 1 - len(base_fake)
    if need_r2 < 0 or need_r1 < 0 or need_fake < 0:
        return

    occupied = set(base_r2) | set(base_r1) | set(base_fake)
    unknown = sorted(set(range(1, 13)) - occupied)
    legal_r1 = set(cfg.official.legal_r1_boundary_blocks)
    forbidden_fake_blocks = set(cfg.official.fake_forbidden_blocks)

    yielded = 0
    for add_r2 in combinations(unknown, need_r2):
        add_r2_set = set(add_r2)
        rem_after_r2 = [b for b in unknown if b not in add_r2_set]
        r1_pool = [b for b in rem_after_r2 if b in legal_r1]
        for add_r1 in combinations(r1_pool, need_r1):
            add_r1_set = set(add_r1)
            rem_after_r1 = [b for b in rem_after_r2 if b not in add_r1_set]
            fake_pool = [b for b in rem_after_r1 if b not in forbidden_fake_blocks]
            for add_fake in combinations(fake_pool, need_fake):
                layout = Layout.from_lists(
                    r2_blocks=list(base_r2) + list(add_r2),
                    r1_blocks=list(base_r1) + list(add_r1),
                    fake_blocks=list(base_fake) + list(add_fake),
                    heights=DEFAULT_HEIGHTS,
                )
                ok, _ = validate_layout(layout, cfg, strict_counts=True)
                if ok:
                    yield layout
                    yielded += 1
                    if yielded >= max_candidates:
                        return


def infer_best_plan_for_incomplete_layout(
    base_r2, base_r1, base_fake, cfg: PlannerConfig, mode: str, top_n: int
):
    best_layout = None
    best_plan = None
    best_score = float("inf")

    for layout in iter_layout_candidates(base_r2, base_r1, base_fake, cfg):
        plans = plan_routes(layout, cfg, top_n=1, mode=mode)
        if not plans:
            continue
        p = plans[0]
        if (p.score, p.steps) < (best_score, getattr(best_plan, "steps", 10**9)):
            best_score = p.score
            best_plan = p
            best_layout = layout

    if best_layout is None:
        return None, []
    return best_layout, plan_routes(best_layout, cfg, top_n=top_n, mode=mode)


def render_strategy_controls(prefix: str, default_min_pickups: int = 2) -> StrategyPreferences:
    st.markdown("**Action Scoring (Adjustable)**")
    s1, s2, s3 = st.columns(3)
    with s1:
        min_pickups_required = st.number_input(
            "Minimum R2 pickups (hard rule)",
            min_value=1,
            max_value=2,
            value=default_min_pickups,
            step=1,
            key=f"{prefix}_min_pickups_required",
        )
        step_weight = st.number_input(
            "Step weight",
            min_value=0.0,
            max_value=20.0,
            value=1.5,
            step=0.5,
            key=f"{prefix}_step_weight",
        )
        pickup_weight = st.number_input(
            "Pickup action weight",
            min_value=0.0,
            max_value=20.0,
            value=4.0,
            step=0.5,
            key=f"{prefix}_pickup_weight",
        )
    with s2:
        drop_weight = st.number_input(
            "Drop action weight",
            min_value=0.0,
            max_value=20.0,
            value=4.0,
            step=0.5,
            key=f"{prefix}_drop_weight",
        )
        turn_weight = st.number_input(
            "Turn action weight",
            min_value=0.0,
            max_value=20.0,
            value=4.0,
            step=0.5,
            key=f"{prefix}_turn_weight",
        )
        wait_weight = st.number_input(
            "Wait action weight",
            min_value=0.0,
            max_value=20.0,
            value=4.0,
            step=0.5,
            key=f"{prefix}_wait_weight",
        )
    with s3:
        one_scroll_penalty = st.number_input(
            "One-scroll penalty",
            min_value=0.0,
            max_value=100.0,
            value=30.0,
            step=1.0,
            key=f"{prefix}_one_scroll_penalty",
        )
        strict_exit10_bonus = st.number_input(
            "Strict mode exit#10 bonus",
            min_value=0.0,
            max_value=20.0,
            value=3.0,
            step=0.5,
            key=f"{prefix}_strict_exit10_bonus",
        )
        strict_exit12_bonus = st.number_input(
            "Strict mode exit#12 bonus",
            min_value=0.0,
            max_value=20.0,
            value=0.0,
            step=0.5,
            key=f"{prefix}_strict_exit12_bonus",
        )

    return StrategyPreferences(
        prefer_two_pickups=True,
        practical_sort_wait_drop_first=True,
        min_pickups_required=int(min_pickups_required),
        step_weight=float(step_weight),
        pickup_weight=float(pickup_weight),
        drop_weight=float(drop_weight),
        turn_weight=float(turn_weight),
        wait_weight=float(wait_weight),
        one_scroll_penalty=float(one_scroll_penalty),
        strict_exit10_bonus=float(strict_exit10_bonus),
        strict_exit12_bonus=float(strict_exit12_bonus),
    )


def build_allowed_transitions(max_step_mm: int):
    heights = (0, 200, 400, 600)
    return tuple(
        (src, dst)
        for src in heights
        for dst in heights
        if src != dst and abs(dst - src) <= max_step_mm
    )


def build_robot_limits_for_capacity(carry_capacity: int, max_step_mm: int) -> RobotLimits:
    grip_slots = 1
    hidden_slots = max(0, carry_capacity - grip_slots)
    return RobotLimits(
        max_step_mm=int(max_step_mm),
        max_total_scrolls=int(carry_capacity),
        max_hidden_slot=int(hidden_slots),
        max_grip_slot=int(grip_slots),
        allowed_height_transitions=build_allowed_transitions(int(max_step_mm)),
    )


def render_opponent_profile_controls(prefix: str) -> tuple[PlannerConfig, str]:
    st.markdown("**Opponent Assumptions**")
    c1, c2 = st.columns(2)
    with c1:
        robot_profile = st.selectbox(
            "Opponent robot profile",
            list(OPPONENT_ROBOT_PRESETS.keys()),
            index=0,
            key=f"{prefix}_robot_profile",
        )
    with c2:
        scoring_profile = st.selectbox(
            "Opponent scoring profile",
            list(OPPONENT_SCORING_PRESETS.keys()),
            index=0,
            key=f"{prefix}_scoring_profile",
        )

    robot_defaults = OPPONENT_ROBOT_PRESETS[robot_profile]
    scoring_defaults = OPPONENT_SCORING_PRESETS[scoring_profile]

    with st.expander("Advanced opponent overrides"):
        o1, o2, o3 = st.columns(3)
        with o1:
            carry_capacity = st.number_input(
                "Carry capacity",
                min_value=1,
                max_value=4,
                value=int(robot_defaults["carry_capacity"]),
                step=1,
                key=f"{prefix}_carry_capacity",
            )
            min_pickups_required = st.number_input(
                "Minimum R2 pickups (hard rule)",
                min_value=1,
                max_value=4,
                value=int(scoring_defaults["min_pickups_required"]),
                step=1,
                key=f"{prefix}_min_pickups_required",
            )
        with o2:
            max_step_mm = st.selectbox(
                "Max climb delta",
                [200, 400],
                index=0 if int(robot_defaults["max_step_mm"]) == 200 else 1,
                key=f"{prefix}_max_step_mm",
            )
            exit_mode = st.selectbox(
                "Exit options",
                ["Official exits", "Any block"],
                index=0 if robot_defaults["exit_mode"] == "Official exits" else 1,
                key=f"{prefix}_exit_mode",
            )
        with o3:
            customize_weights = st.checkbox(
                "Customize weights",
                value=False,
                key=f"{prefix}_customize_weights",
            )

        if customize_weights:
            w1, w2, w3 = st.columns(3)
            with w1:
                step_weight = st.number_input(
                    "Step weight",
                    min_value=0.0,
                    max_value=20.0,
                    value=float(scoring_defaults["step_weight"]),
                    step=0.5,
                    key=f"{prefix}_step_weight",
                )
                pickup_weight = st.number_input(
                    "Pickup weight",
                    min_value=0.0,
                    max_value=20.0,
                    value=float(scoring_defaults["pickup_weight"]),
                    step=0.5,
                    key=f"{prefix}_pickup_weight",
                )
            with w2:
                drop_weight = st.number_input(
                    "Drop weight",
                    min_value=0.0,
                    max_value=20.0,
                    value=float(scoring_defaults["drop_weight"]),
                    step=0.5,
                    key=f"{prefix}_drop_weight",
                )
                turn_weight = st.number_input(
                    "Turn weight",
                    min_value=0.0,
                    max_value=20.0,
                    value=float(scoring_defaults["turn_weight"]),
                    step=0.5,
                    key=f"{prefix}_turn_weight",
                )
            with w3:
                wait_weight = st.number_input(
                    "Wait weight",
                    min_value=0.0,
                    max_value=20.0,
                    value=float(scoring_defaults["wait_weight"]),
                    step=0.5,
                    key=f"{prefix}_wait_weight",
                )
                one_scroll_penalty = st.number_input(
                    "One-scroll penalty",
                    min_value=0.0,
                    max_value=100.0,
                    value=float(scoring_defaults["one_scroll_penalty"]),
                    step=1.0,
                    key=f"{prefix}_one_scroll_penalty",
                )
        else:
            step_weight = float(scoring_defaults["step_weight"])
            pickup_weight = float(scoring_defaults["pickup_weight"])
            drop_weight = float(scoring_defaults["drop_weight"])
            turn_weight = float(scoring_defaults["turn_weight"])
            wait_weight = float(scoring_defaults["wait_weight"])
            one_scroll_penalty = float(scoring_defaults["one_scroll_penalty"])

    strategy = StrategyPreferences(
        prefer_two_pickups=True,
        practical_sort_wait_drop_first=True,
        min_pickups_required=int(min_pickups_required),
        step_weight=float(step_weight),
        pickup_weight=float(pickup_weight),
        drop_weight=float(drop_weight),
        turn_weight=float(turn_weight),
        wait_weight=float(wait_weight),
        one_scroll_penalty=float(one_scroll_penalty),
        strict_exit10_bonus=3.0,
        strict_exit12_bonus=0.0,
    )
    official = OfficialRules(
        official_exit_blocks=ALL_FIELD_BLOCKS if exit_mode == "Any block" else OfficialRules().official_exit_blocks
    )
    robot = build_robot_limits_for_capacity(int(carry_capacity), int(max_step_mm))
    summary = (
        f"{robot_profile} | {scoring_profile} | carry={carry_capacity} | "
        f"climb={max_step_mm}mm | exits={exit_mode}"
    )
    return PlannerConfig(official=official, robot=robot, strategy=strategy), summary


def run_manual_planner_tab():
    c1, c2, c3 = st.columns(3)
    with c1:
        r2_text = st.text_input("R2 blocks", value="1,3,5,8")
    with c2:
        r1_text = st.text_input("R1 blocks", value="10,11,12")
    with c3:
        fake_text = st.text_input("Fake block", value="6")

    c4, c5 = st.columns(2)
    with c4:
        mode = st.selectbox("Planning mode", ["practical", "strict"], index=0, key="manual_mode")
    with c5:
        top_n = st.number_input("Top N plans", min_value=1, max_value=20, value=5, step=1, key="manual_top")
    strategy = render_strategy_controls(prefix="manual", default_min_pickups=2)

    if "last_layout" not in st.session_state:
        st.session_state.last_layout = Layout.from_lists([1, 3, 5, 8], [10, 11, 12], [6], DEFAULT_HEIGHTS)
    if "last_plans" not in st.session_state:
        st.session_state.last_plans = []

    if st.button("Validate + Plan", key="manual_run"):
        try:
            r2_list = parse_csv_ids(r2_text)
            r1_list = parse_csv_ids(r1_text)
            fake_list = parse_csv_ids(fake_text)
            layout = Layout.from_lists(r2_blocks=r2_list, r1_blocks=r1_list, fake_blocks=fake_list)
        except ValueError as e:
            st.error(str(e))
            return

        cfg = replace(PlannerConfig(), strategy=strategy)
        ok_partial, partial_errors = validate_layout(layout, cfg, strict_counts=False)
        if not ok_partial:
            st.session_state.last_plans = []
            st.error("Layout invalid")
            for e in partial_errors:
                st.write(f"- {e}")
            return

        is_complete = len(r2_list) == 4 and len(r1_list) == 3 and len(fake_list) == 1
        if is_complete:
            ok, errors = validate_layout(layout, cfg, strict_counts=True)
            st.session_state.last_layout = layout
            if not ok:
                st.session_state.last_plans = []
                st.error("Layout invalid")
                for e in errors:
                    st.write(f"- {e}")
            else:
                st.success("Layout valid")
                plans = plan_routes(layout, cfg, top_n=int(top_n), mode=mode)
                st.session_state.last_plans = plans
                if not plans:
                    st.warning("No legal plan found for this layout")
        else:
            st.info("Incomplete layout detected. Searching for the best-scoring legal completion and path...")
            with st.spinner("Evaluating legal completions for the partial layout..."):
                inferred_layout, plans = infer_best_plan_for_incomplete_layout(
                    r2_list, r1_list, fake_list, cfg, mode=mode, top_n=int(top_n)
                )
            if inferred_layout is None or not plans:
                st.session_state.last_plans = []
                st.warning("Could not infer a feasible completion from current partial blocks")
            else:
                st.session_state.last_layout = inferred_layout
                st.session_state.last_plans = plans
                best = plans[0]
                st.success("Best-scoring legal completion + path found")
                st.caption(
                    f"Inferred layout: R2={list(inferred_layout.r2_blocks)} | "
                    f"R1={list(inferred_layout.r1_blocks)} | Fake={list(inferred_layout.fake_blocks)}"
                )
                st.caption(
                    f"Best predicted path: E->{ '->'.join(map(str, best.route)) } | "
                    f"exit={best.exit_block} | pickups={best.pickups} | score={best.score}"
                )

    layout = st.session_state.last_layout
    plans = st.session_state.last_plans

    st.subheader("Meihua Forest Map")
    selected_route = []
    if plans:
        labels = [
            f"#{i+1} score={p.score} route=E->{ '->'.join(map(str, p.route)) } pickups={p.pickups}"
            for i, p in enumerate(plans)
        ]
        pick = st.radio("Select plan", range(len(plans)), format_func=lambda i: labels[i], index=0)
        chosen = plans[pick]
        selected_route = chosen.route

        st.markdown(
            f"**Selected:** exit={chosen.exit_block} | steps={chosen.steps} | "
            f"pickup={chosen.pickup_actions} | drop={chosen.drop_actions} | "
            f"wait={chosen.wait_actions} | turns={chosen.turn_actions} | score={chosen.score}"
        )

    render_meihua_map(layout, selected_route)


def run_opponent_analysis_tab():
    st.caption("Keep opponent assumptions separate from our robot. Use presets or override carry, climb, exits, and weights.")

    c1, c2, c3 = st.columns(3)
    with c1:
        r2_text = st.text_input("R2 blocks", value="1,3,5,8", key="opp_r2")
    with c2:
        r1_text = st.text_input("R1 blocks", value="10,11,12", key="opp_r1")
    with c3:
        fake_text = st.text_input("Fake block", value="6", key="opp_fake")

    c4, c5 = st.columns(2)
    with c4:
        mode = st.selectbox("Planning mode", ["practical", "strict"], index=0, key="opp_mode")
    with c5:
        top_n = st.number_input("Top N plans", min_value=1, max_value=20, value=5, step=1, key="opp_top")

    cfg, profile_summary = render_opponent_profile_controls(prefix="opponent")
    st.caption(f"Using opponent profile: {profile_summary}")

    if "opp_last_layout" not in st.session_state:
        st.session_state.opp_last_layout = Layout.from_lists([1, 3, 5, 8], [10, 11, 12], [6], DEFAULT_HEIGHTS)
    if "opp_last_plans" not in st.session_state:
        st.session_state.opp_last_plans = []

    if st.button("Evaluate Opponent", key="opp_run"):
        try:
            r2_list = parse_csv_ids(r2_text)
            r1_list = parse_csv_ids(r1_text)
            fake_list = parse_csv_ids(fake_text)
            layout = Layout.from_lists(r2_blocks=r2_list, r1_blocks=r1_list, fake_blocks=fake_list)
        except ValueError as e:
            st.error(str(e))
            return

        ok_partial, partial_errors = validate_layout(layout, cfg, strict_counts=False)
        if not ok_partial:
            st.session_state.opp_last_plans = []
            st.error("Layout invalid")
            for e in partial_errors:
                st.write(f"- {e}")
            return

        is_complete = len(r2_list) == 4 and len(r1_list) == 3 and len(fake_list) == 1
        if is_complete:
            ok, errors = validate_layout(layout, cfg, strict_counts=True)
            st.session_state.opp_last_layout = layout
            if not ok:
                st.session_state.opp_last_plans = []
                st.error("Layout invalid")
                for e in errors:
                    st.write(f"- {e}")
            else:
                plans = plan_routes(layout, cfg, top_n=int(top_n), mode=mode)
                st.session_state.opp_last_plans = plans
                if plans:
                    st.success("Opponent plan set computed")
                else:
                    st.warning("No legal opponent plan found under these assumptions")
        else:
            with st.spinner("Searching best-scoring legal completion for the opponent assumptions..."):
                inferred_layout, plans = infer_best_plan_for_incomplete_layout(
                    r2_list, r1_list, fake_list, cfg, mode=mode, top_n=int(top_n)
                )
            if inferred_layout is None or not plans:
                st.session_state.opp_last_plans = []
                st.warning("Could not infer a feasible completion under these opponent assumptions")
            else:
                st.session_state.opp_last_layout = inferred_layout
                st.session_state.opp_last_plans = plans
                st.success("Opponent completion + path found")
                st.caption(
                    f"Inferred layout: R2={list(inferred_layout.r2_blocks)} | "
                    f"R1={list(inferred_layout.r1_blocks)} | Fake={list(inferred_layout.fake_blocks)}"
                )

    layout = st.session_state.opp_last_layout
    plans = st.session_state.opp_last_plans

    st.subheader("Opponent Map")
    selected_route = []
    if plans:
        labels = [
            f"#{i+1} score={p.score} route=E->{ '->'.join(map(str, p.route)) } pickups={p.pickups}"
            for i, p in enumerate(plans)
        ]
        pick = st.radio("Select opponent plan", range(len(plans)), format_func=lambda i: labels[i], index=0, key="opp_pick")
        chosen = plans[pick]
        selected_route = chosen.route
        st.markdown(
            f"**Selected:** exit={chosen.exit_block} | steps={chosen.steps} | "
            f"pickup={chosen.pickup_actions} | drop={chosen.drop_actions} | "
            f"wait={chosen.wait_actions} | turns={chosen.turn_actions} | score={chosen.score}"
        )

    render_meihua_map(layout, selected_route)


def run_scenario_generator_tab():
    st.subheader("Scenario Generator")
    st.caption("Generate many rule-valid layouts, compute legal plans, then inspect all or worst-ranked scenarios.")

    c1, c2, c3 = st.columns(3)
    with c1:
        samples = st.number_input("Scenarios to sample", min_value=10, max_value=3000, value=300, step=10)
    with c2:
        worst_n = st.number_input("Worst cases to keep", min_value=1, max_value=50, value=10, step=1)
    with c3:
        mode = st.selectbox("Planning mode", ["practical", "strict"], index=0, key="worst_mode")
    strategy = render_strategy_controls(prefix="scenario", default_min_pickups=2)

    if "scenario_rows" not in st.session_state:
        st.session_state.scenario_rows = []
        st.session_state.worst_cases = []
        st.session_state.worst_stats = None

    if st.button("Generate Scenarios", key="gen_worst"):
        cfg = replace(PlannerConfig(), strategy=strategy)
        rows = []
        valid_layouts = 0
        infeasible = 0

        progress = st.progress(0, text="Generating scenarios...")
        for i in range(int(samples)):
            layout = random_valid_layout(cfg)
            if not layout:
                continue
            valid_layouts += 1

            plans = plan_routes(layout, cfg, top_n=20, mode=mode)
            if not plans:
                infeasible += 1
                continue

            best = plans[0]
            rows.append(
                {
                    "layout": layout,
                    "best": best,
                }
            )

            if (i + 1) % 10 == 0 or i == int(samples) - 1:
                progress.progress(int((i + 1) * 100 / int(samples)), text=f"Processed {i+1}/{int(samples)}")

        rows.sort(
            key=lambda x: (
                x["best"].score,
                x["best"].wait_actions,
                x["best"].drop_actions,
                x["best"].steps,
            ),
            reverse=True,
        )

        st.session_state.scenario_rows = rows
        st.session_state.worst_cases = rows[: int(worst_n)]
        st.session_state.worst_stats = {
            "sampled": int(samples),
            "valid_layouts": valid_layouts,
            "feasible": len(rows),
            "infeasible": infeasible,
        }

    stats = st.session_state.worst_stats
    all_cases = st.session_state.scenario_rows
    worst_cases = st.session_state.worst_cases

    if stats:
        st.info(
            f"Sampled={stats['sampled']} | Valid layouts={stats['valid_layouts']} | "
            f"Feasible={stats['feasible']} | Infeasible(no legal plan)={stats['infeasible']}"
        )

    if not all_cases:
        st.caption("No scenario results yet. Click Generate Scenarios.")
        return

    view_mode = st.radio(
        "View mode",
        ["All feasible scenarios", "Worst-only view"],
        index=0,
        horizontal=True,
        key="scenario_view_mode",
    )
    cases = all_cases if view_mode == "All feasible scenarios" else worst_cases

    labels = []
    for i, row in enumerate(cases, start=1):
        p = row["best"]
        labels.append(
            f"#{i} score={p.score} route=E->{ '->'.join(map(str, p.route)) } "
            f"pickups={p.pickups} waits={p.wait_actions} drops={p.drop_actions}"
        )

    idx = st.radio("Select scenario", range(len(cases)), format_func=lambda i: labels[i], index=0)
    picked = cases[idx]
    layout = picked["layout"]
    plan = picked["best"]

    st.markdown(
        f"**Scenario detail:** exit={plan.exit_block} | steps={plan.steps} | "
        f"pickup={plan.pickup_actions} | drop={plan.drop_actions} | wait={plan.wait_actions} | "
        f"turn180={plan.turn_actions} | score={plan.score}"
    )
    st.markdown(
        f"**Layout:** R2={list(layout.r2_blocks)} | R1={list(layout.r1_blocks)} | Fake={list(layout.fake_blocks)}"
    )

    render_meihua_map(layout, plan.route)


def main():
    st.set_page_config(page_title="Meihua Planner (Rulebook UI)", layout="wide")
    st.title("Meihua Planner (Backend-first Minimal UI)")
    st.caption("Rulebook-style map view: 3x4 forest blocks, official entrance/exit markers, and route overlay.")

    render_field_spec()

    tabs = st.tabs(["Manual Layout + Plan", "Opponent Analysis", "Scenario Generator"])
    with tabs[0]:
        run_manual_planner_tab()
    with tabs[1]:
        run_opponent_analysis_tab()
    with tabs[2]:
        run_scenario_generator_tab()


if __name__ == "__main__":
    main()
