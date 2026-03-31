import itertools
import math
import random
from copy import deepcopy

import streamlit as st

TOKENS = ["EMPTY", "R2", "R1", "FAKE"]
EXIT_BLOCKS = {10, 12}
ENTRANCE_LINKS = [2]
ENTRANCE_HEIGHT = 0
STEP_MM = 600
FORBIDDEN_R1_BLOCKS = {5, 8}
R1_AVOID_RADIUS = 2

DEFAULT_HEIGHTS = {
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

GRAPH = {
    1: [2, 4],
    2: [1, 3, 5],
    3: [2, 6],
    4: [1, 5, 7],
    5: [2, 4, 6, 8],
    6: [3, 5, 9],
    7: [4, 8, 10],
    8: [5, 7, 9, 11],
    9: [6, 8, 12],
    10: [7, 11],
    11: [8, 10, 12],
    12: [9, 11],
}


def create_default_blocks():
    return [{"id": i, "h": DEFAULT_HEIGHTS[i], "token": "EMPTY"} for i in range(1, 13)]


def clone_blocks(blocks):
    return deepcopy(blocks)


def get_block(blocks, block_id):
    for b in blocks:
        if b["id"] == block_id:
            return b
    return None


def get_neighbors(node):
    if node == "E":
        return list(ENTRANCE_LINKS)
    return GRAPH.get(node, [])


def get_height(blocks, node):
    if node == "E":
        return ENTRANCE_HEIGHT
    return get_block(blocks, node)["h"]


def validate_move(blocks, from_node, to_node):
    if to_node not in get_neighbors(from_node):
        return {"ok": False, "reason": "Not adjacent"}

    to_block = None if to_node == "E" else get_block(blocks, to_node)
    if to_block and to_block["token"] == "FAKE":
        return {"ok": False, "reason": "Violation: touched FAKE KFS"}

    dh = abs(get_height(blocks, to_node) - get_height(blocks, from_node))
    if dh > 200:
        return {"ok": False, "reason": "|dH| > 200mm"}
    if from_node == "E" and dh != 200:
        return {"ok": False, "reason": "Entry boundary must be exactly 200mm"}

    angle = math.degrees(math.atan2(dh, STEP_MM))
    if angle > 20:
        return {"ok": False, "reason": "Slope > 20"}

    return {"ok": True, "reason": "OK", "dh": dh}


def validate_exit_boundary(blocks, exit_block_id):
    if exit_block_id not in EXIT_BLOCKS:
        return {"ok": False, "reason": "Not valid exit"}
    dh = abs(get_height(blocks, exit_block_id) - ENTRANCE_HEIGHT)
    if dh != 200:
        return {"ok": False, "reason": "Exit boundary must be exactly 200mm"}
    return {"ok": True, "reason": "OK"}


def shortest_path(blocks, start, goal):
    queue = [{"node": start, "cost": 0.0}]
    prev = {}
    dist = {start: 0.0}

    while queue:
        queue.sort(key=lambda x: x["cost"])
        current = queue.pop(0)

        if current["node"] == goal:
            break

        for nb in get_neighbors(current["node"]):
            mv = validate_move(blocks, current["node"], nb)
            if not mv["ok"]:
                continue
            step_cost = 1 + mv["dh"] / 200
            nd = current["cost"] + step_cost
            if nb not in dist or nd < dist[nb]:
                dist[nb] = nd
                prev[nb] = current["node"]
                queue.append({"node": nb, "cost": nd})

    if goal not in dist:
        return None

    path = []
    cur = goal
    while cur is not None:
        path.append(cur)
        cur = prev.get(cur)
    path.reverse()
    return path


def path_cost(blocks, path):
    if not path or len(path) <= 1:
        return 0.0
    cost = 0.0
    for i in range(1, len(path)):
        mv = validate_move(blocks, path[i - 1], path[i])
        if not mv["ok"]:
            return math.inf
        cost += 1 + mv["dh"] / 200
    return cost


def can_pickup_from(current_node, target_block_id):
    return target_block_id in get_neighbors(current_node)


def count_r1_touches_on_path(blocks, path):
    n = 0
    for node in path or []:
        if node == "E":
            continue
        b = get_block(blocks, node)
        if b and b["token"] == "R1":
            n += 1
    return n


def get_adjacent_r2_targets(blocks, node):
    out = []
    for nb in get_neighbors(node):
        b = get_block(blocks, nb)
        if b and b["token"] == "R2":
            out.append(nb)
    return out


def get_pickup_anchors(target_block_id):
    anchors = set(get_neighbors(target_block_id))
    if target_block_id in ENTRANCE_LINKS:
        anchors.add("E")
    return list(anchors)


def plan_pickup_sequence(blocks, start_node, pickup_order):
    best = None

    def dfs(idx, current_node, parts, total_cost, total_touch):
        nonlocal best
        if idx == len(pickup_order):
            best = {
                "parts": parts,
                "endNode": current_node,
                "totalCost": total_cost,
                "totalTouch": total_touch,
            }
            return

        target = pickup_order[idx]
        for anchor in get_pickup_anchors(target):
            seg = shortest_path(blocks, current_node, anchor)
            if not seg:
                continue
            if not can_pickup_from(anchor, target):
                continue

            seg_cost = path_cost(blocks, seg)
            if not math.isfinite(seg_cost):
                continue
            seg_touch = count_r1_touches_on_path(blocks, seg)

            next_cost = total_cost + seg_cost
            next_touch = total_touch + seg_touch
            if best:
                if next_cost > best["totalCost"]:
                    continue
                if next_cost == best["totalCost"] and next_touch >= best["totalTouch"]:
                    continue
            dfs(idx + 1, anchor, parts + [seg], next_cost, next_touch)

    dfs(0, start_node, [], 0.0, 0)
    return best


def find_nearest_pickup_from_entrance(blocks, targets):
    best_target = None
    best_cost = math.inf
    for t in targets:
        for a in get_pickup_anchors(t):
            seg = shortest_path(blocks, "E", a)
            if not seg:
                continue
            if not can_pickup_from(a, t):
                continue
            c = path_cost(blocks, seg)
            if c < best_cost:
                best_cost = c
                best_target = t
    return best_target


def encounter_order_along_route(blocks, route):
    order = []
    seen = set()
    for node in route:
        for t in get_adjacent_r2_targets(blocks, node):
            if t not in seen:
                seen.add(t)
                order.append(t)
    return order


def combine_paths(parts):
    result = []
    for idx, seg in enumerate(parts):
        if not seg:
            continue
        if idx == 0:
            result.extend(seg)
        else:
            result.extend(seg[1:])
    return result


def validate_layout(blocks, strict=True):
    errors = []
    counts = {"R2": 0, "R1": 0, "FAKE": 0}

    for b in blocks:
        if b["token"] == "R2":
            counts["R2"] += 1
        if b["token"] == "R1":
            counts["R1"] += 1
            if b["id"] in FORBIDDEN_R1_BLOCKS:
                errors.append(f"R1 KFS cannot be placed on block {b['id']}.")
        if b["token"] == "FAKE":
            counts["FAKE"] += 1
            if b["id"] in [1, 2, 3]:
                errors.append("Fake KFS cannot be placed on entrance blocks 1,2,3.")

    if strict:
        if counts["R2"] != 4:
            errors.append("R2 KFS count must be exactly 4.")
        if counts["R1"] != 3:
            errors.append("R1 KFS count must be exactly 3.")
        if counts["FAKE"] != 1:
            errors.append("Fake KFS count must be exactly 1.")
    else:
        if counts["R2"] < 1:
            errors.append("Need at least 1 R2 KFS for planning.")

    return {"ok": len(errors) == 0, "errors": errors, "counts": counts}


def min_hop_distance(start, goal_nodes):
    if start in goal_nodes:
        return 0
    q = [(start, 0)]
    visited = {start}
    while q:
        node, d = q.pop(0)
        for nb in get_neighbors(node):
            if nb in visited:
                continue
            if nb in goal_nodes:
                return d + 1
            visited.add(nb)
            q.append((nb, d + 1))
    return 99


def evaluate_plan(blocks, route, pickups, planning_mode="practical", scenario_label=""):
    steps = 0
    climb = 0
    risky_edges = 0
    climb_actions = 0
    descend_actions = 0
    pickup_actions = 0
    drop_actions = 0
    wait_actions = 0
    grip_occupied = False

    r1_touch_count = 0
    r1_near_count = 0
    r1_proximity_cost = 0
    policy_drop_actions = 0
    policy_penalty = 0

    for i in range(1, len(route)):
        from_node = route[i - 1]
        to_node = route[i]
        mv = validate_move(blocks, from_node, to_node)
        if not mv["ok"]:
            return {"valid": False, "reason": mv["reason"]}

        steps += 1
        delta = get_height(blocks, to_node) - get_height(blocks, from_node)
        climb += max(0, delta)
        if delta > 0:
            climb_actions += 1
        if delta < 0:
            descend_actions += 1
        if mv["dh"] == 200:
            risky_edges += 1

    r1_blocks = [b["id"] for b in blocks if b["token"] == "R1"]
    if r1_blocks:
        for node in route:
            d = min_hop_distance(node, r1_blocks)
            if d == 0:
                r1_touch_count += 1
                wait_actions += 1
            if d == 1:
                r1_near_count += 1
            if d <= R1_AVOID_RADIUS:
                r1_proximity_cost += (R1_AVOID_RADIUS + 1 - d)

    for _ in pickups:
        if grip_occupied:
            drop_actions += 1
            grip_occupied = False
        pickup_actions += 1
        grip_occupied = True

    if planning_mode == "strict":
        encounter = encounter_order_along_route(blocks, route)
        if encounter and pickups:
            preferred_first = encounter[0]
            preferred_last = encounter[-1]
            nearest_from_entry = find_nearest_pickup_from_entrance(blocks, encounter) or preferred_first

            if pickups[0] != preferred_first and pickups[0] != nearest_from_entry:
                policy_penalty += 8
            if pickups[-1] != preferred_last:
                policy_penalty += 6

            for p in pickups:
                if p != preferred_first and p != preferred_last:
                    policy_drop_actions += 1

        drop_actions += policy_drop_actions

    terrain_actions = climb_actions + descend_actions
    ops = pickup_actions + drop_actions + wait_actions + terrain_actions
    pickup_time = pickup_actions * 0.8 + drop_actions * 0.6
    wait_time = wait_actions * 1.4
    move_time = steps * 1.2
    time_s = round(pickup_time + wait_time + move_time, 2)
    energy = round(steps * 0.1 + climb * 0.002, 2)
    one_scroll_penalty = 10 if len(pickups) == 1 else 0
    strategic_exit_points = 8 if planning_mode == "strict" and route[-1] == 10 else 0

    exit_block = route[-1]
    exit_block_obj = get_block(blocks, exit_block)
    has_exit_pickup = exit_block in pickups
    exit_pickup_points = 7 if exit_block_obj and exit_block_obj["token"] == "R2" and has_exit_pickup else 0
    missed_exit_pick_penalty = 7 if exit_block_obj and exit_block_obj["token"] == "R2" and not has_exit_pickup else 0

    risk = round(risky_edges * 1.5 + drop_actions * 1.2 + wait_actions * 1.4 + r1_proximity_cost * 1.6, 2)
    mode_is_practical = planning_mode == "practical"
    op_weight = 4.5 if mode_is_practical else 2.5
    risk_weight = 1.3 if mode_is_practical else 1.8

    wait_drop_penalty = wait_actions * 4 + drop_actions * 3
    score = round(
        time_s * 1
        + risk * risk_weight
        + steps * 0.3
        + energy * 0.7
        + ops * op_weight
        + wait_drop_penalty
        + one_scroll_penalty
        + missed_exit_pick_penalty
        + policy_penalty
        - strategic_exit_points
        - exit_pickup_points,
        2,
    )

    return {
        "valid": True,
        "scenarioLabel": scenario_label,
        "route": route,
        "pickups": pickups,
        "exit": route[-1],
        "steps": steps,
        "climb": climb,
        "time": time_s,
        "energy": energy,
        "risk": risk,
        "pickupActions": pickup_actions,
        "dropActions": drop_actions,
        "waitActions": wait_actions,
        "climbActions": climb_actions,
        "descendActions": descend_actions,
        "terrainActions": terrain_actions,
        "ops": ops,
        "waitDropActions": wait_actions + drop_actions,
        "waitDropPenalty": wait_drop_penalty,
        "r1TouchCount": r1_touch_count,
        "r1NearCount": r1_near_count,
        "r1ProximityCost": round(r1_proximity_cost, 2),
        "policyDropActions": policy_drop_actions,
        "policyPenalty": policy_penalty,
        "oneScrollPenalty": one_scroll_penalty,
        "strategicExitPoints": strategic_exit_points,
        "exitPickupPoints": exit_pickup_points,
        "missedExitPickupPenalty": missed_exit_pick_penalty,
        "score": score,
    }


def compute_plans(blocks, top_n=5, planning_mode="practical"):
    r2_blocks = [b["id"] for b in blocks if b["token"] == "R2"]
    if not r2_blocks:
        return []

    target_sets = []
    preferred_sizes = [2, 1] if len(r2_blocks) >= 2 else [1]
    for size in preferred_sizes:
        target_sets.extend(itertools.combinations(r2_blocks, size))

    plans = []

    for targets in target_sets:
        for order in itertools.permutations(targets):
            for exit_block in EXIT_BLOCKS:
                exit_obj = get_block(blocks, exit_block)
                if exit_obj and exit_obj["token"] == "R2" and exit_block not in order:
                    continue

                current = "E"
                parts = []
                pickup_plan = plan_pickup_sequence(blocks, current, list(order))
                if not pickup_plan:
                    continue
                parts.extend(pickup_plan["parts"])
                current = pickup_plan["endNode"]

                exit_seg = shortest_path(blocks, current, exit_block)
                if not exit_seg:
                    continue
                if not validate_exit_boundary(blocks, exit_block)["ok"]:
                    continue
                parts.append(exit_seg)

                full_route = combine_paths(parts)
                if full_route[-1] not in EXIT_BLOCKS:
                    continue

                pl = evaluate_plan(blocks, full_route, list(order), planning_mode=planning_mode)
                if pl["valid"]:
                    plans.append(pl)

    def sort_key(p):
        if planning_mode == "practical":
            return (p["waitDropActions"], p["ops"], p["score"])
        return (p["score"],)

    plans.sort(key=sort_key)

    unique = []
    seen = set()
    for p in plans:
        key = (tuple(p["route"]), tuple(p["pickups"]))
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)

    two_scroll = [p for p in unique if len(p["pickups"]) == 2]
    if two_scroll:
        return two_scroll[:top_n]
    return unique[:top_n]


def random_scenario_blocks():
    blocks = create_default_blocks()
    for b in blocks:
        b["token"] = "EMPTY"

    ids = [b["id"] for b in blocks]
    random.shuffle(ids)

    for bid in ids[:4]:
        get_block(blocks, bid)["token"] = "R2"

    remaining = [bid for bid in ids if get_block(blocks, bid)["token"] == "EMPTY"]
    r1_candidates = [bid for bid in remaining if bid not in FORBIDDEN_R1_BLOCKS]
    for bid in r1_candidates[:3]:
        get_block(blocks, bid)["token"] = "R1"

    rem2 = [bid for bid in ids if get_block(blocks, bid)["token"] == "EMPTY"]
    fake_candidates = [bid for bid in rem2 if bid not in [1, 2, 3]]
    if fake_candidates:
        get_block(blocks, fake_candidates[0])["token"] = "FAKE"

    return blocks


def color_by_height(h):
    if h == 200:
        return "rgb(41,82,16)"
    if h == 400:
        return "rgb(42,113,56)"
    return "rgb(152,166,80)"


def render_map(blocks, path):
    path = path or []
    path_set = set(path)

    html = [
        """
        <style>
        .map-grid {display:grid; grid-template-columns:repeat(3,1fr); gap:8px;}
        .cell {border:1px solid #6f9e54; border-radius:10px; min-height:90px; padding:6px; color:#f6fff2; position:relative;}
        .cell.dimmed {opacity:0.3; filter:saturate(0.6);}
        .cell.path {outline:6px solid #0b4ea2; outline-offset:-3px; box-shadow:0 0 0 4px rgba(11,78,162,0.34),0 0 22px rgba(11,78,162,0.55);}
        .cell.start {outline-color:#0d8f46;}
        .cell.end {outline-color:#bf1020;}
        .kfs {position:absolute; right:6px; bottom:6px; font-size:11px; border-radius:6px; padding:2px 6px; color:#fff; background:#63755b;}
        .step {position:absolute; left:6px; bottom:6px; width:22px; height:22px; border-radius:50%; background:#0f4c9a; text-align:center; line-height:22px; font-size:12px; font-weight:700;}
        .title {font-weight:700;}
        .sub {font-size:12px;}
        </style>
        """
    ]
    html.append('<div class="map-grid">')
    for b in blocks:
        cls = ["cell"]
        if path and b["id"] not in path_set:
            cls.append("dimmed")
        if b["id"] in path_set:
            cls.append("path")
            idx = path.index(b["id"])
            if idx == 0:
                cls.append("start")
            if idx == len(path) - 1:
                cls.append("end")
        title = f"#{b['id']}"
        if b["id"] in ENTRANCE_LINKS:
            title += " (Ent)"
        if b["id"] in EXIT_BLOCKS:
            title += " (Exit)"

        step_badge = ""
        if b["id"] in path_set:
            step_badge = f'<div class="step">{path.index(b["id"]) + 1}</div>'

        html.append(
            f'<div class="{" ".join(cls)}" style="background:{color_by_height(b["h"])};">'
            f'<div class="title">{title}</div>'
            f'<div class="sub">H={b["h"]}mm</div>'
            f'<div class="kfs">{b["token"]}</div>'
            f"{step_badge}"
            "</div>"
        )

    html.append("</div>")
    st.markdown("".join(html), unsafe_allow_html=True)


def show_plan_detail(plan):
    st.markdown(f"**Route:** E -> {' -> '.join(map(str, plan['route']))}")
    st.markdown(f"**Pickups:** {', '.join(map(str, plan['pickups'])) if plan['pickups'] else '-'} | **Exit:** {plan['exit']}")
    st.markdown(
        f"**Steps:** {plan['steps']} | **Climb:** {plan['climb']}mm | "
        f"**Time:** {plan['time']}s | **Risk:** {plan['risk']}"
    )
    st.markdown(
        f"**Actions:** pickup={plan['pickupActions']}, drop={plan['dropActions']}, wait={plan['waitActions']}, "
        f"climb={plan['climbActions']}, descend={plan['descendActions']}, terrain={plan['terrainActions']}, total={plan['ops']}"
    )
    st.markdown(
        f"**Wait+Drop:** {plan['waitDropActions']} (penalty {plan['waitDropPenalty']}) | "
        f"**Score:** {plan['score']}"
    )


def seed_manual_default(blocks):
    for b in blocks:
        b["token"] = "EMPTY"
    get_block(blocks, 1)["token"] = "R2"
    get_block(blocks, 3)["token"] = "R2"
    get_block(blocks, 6)["token"] = "R2"
    get_block(blocks, 11)["token"] = "R2"
    get_block(blocks, 2)["token"] = "R1"
    get_block(blocks, 4)["token"] = "R1"
    get_block(blocks, 8)["token"] = "R1"
    get_block(blocks, 12)["token"] = "FAKE"


def init_state():
    if "manual_blocks" not in st.session_state:
        st.session_state.manual_blocks = create_default_blocks()
        seed_manual_default(st.session_state.manual_blocks)
    if "manual_plans" not in st.session_state:
        st.session_state.manual_plans = []
    if "auto_blocks" not in st.session_state:
        st.session_state.auto_blocks = create_default_blocks()
    if "auto_plans" not in st.session_state:
        st.session_state.auto_plans = []


def main():
    st.set_page_config(page_title="Meihua Forest Planner (Python)", layout="wide")
    init_state()

    st.title("Meihua Forest Planner (Python)")
    st.caption("Robocon 2026 - rule-aware path planning")

    planning_mode = st.selectbox(
        "Planning Mode",
        ["practical", "strict"],
        index=0,
        help="Practical mode prioritizes lower wait/drop and total actions.",
    )

    tabs = st.tabs(["Auto Optimize", "Manual Layout + Plan"])

    with tabs[0]:
        c1, c2, c3 = st.columns(3)
        with c1:
            scenarios = st.number_input("Scenarios", min_value=1, max_value=200, value=30, step=1)
        with c2:
            top_n = st.number_input("Top Plans", min_value=1, max_value=20, value=5, step=1)
        with c3:
            strict_layout = st.checkbox("Strict Layout", value=True)

        if st.button("Generate + Compute", key="auto_run"):
            all_plans = []
            for i in range(int(scenarios)):
                blocks = random_scenario_blocks()
                lv = validate_layout(blocks, strict_layout)
                if not lv["ok"]:
                    continue
                plans = compute_plans(blocks, int(top_n), planning_mode)
                for p in plans:
                    p["scenarioLabel"] = f"S{i + 1}"
                    p["_blocks"] = clone_blocks(blocks)
                all_plans.extend(plans)

            all_plans.sort(key=lambda p: p["score"])
            st.session_state.auto_plans = all_plans[: int(top_n)]
            if st.session_state.auto_plans:
                st.session_state.auto_blocks = clone_blocks(st.session_state.auto_plans[0]["_blocks"])

        auto_plans = st.session_state.auto_plans
        if auto_plans:
            st.success(
                f"Computed {len(auto_plans)} plan(s). Best score: {auto_plans[0]['score']} | "
                f"Scenario {auto_plans[0].get('scenarioLabel', '-') }"
            )
            labels = [
                f"#{i+1} score={p['score']} route=E->{'->'.join(map(str,p['route']))} pickups={p['pickups']}"
                for i, p in enumerate(auto_plans)
            ]
            choice = st.radio("Select plan", range(len(auto_plans)), format_func=lambda i: labels[i], index=0)
            chosen = auto_plans[choice]
            st.session_state.auto_blocks = clone_blocks(chosen["_blocks"])

            left, right = st.columns([1.05, 1])
            with left:
                st.subheader("Plan Details")
                show_plan_detail(chosen)
            with right:
                st.subheader("Scenario Map")
                render_map(st.session_state.auto_blocks, chosen["route"])
        else:
            st.info("No plans yet. Click Generate + Compute.")

    with tabs[1]:
        st.subheader("Manual Token Placement")
        st.caption("Heights are fixed by field constant. Set token for each block.")

        for row in range(4):
            cols = st.columns(3)
            for col in range(3):
                idx = row * 3 + col
                b = st.session_state.manual_blocks[idx]
                with cols[col]:
                    token = st.selectbox(
                        f"#{b['id']} (H={b['h']})",
                        TOKENS,
                        index=TOKENS.index(b["token"]),
                        key=f"blk_{b['id']}",
                    )
                    b["token"] = token

        m1, m2, m3 = st.columns(3)
        with m1:
            manual_top_n = st.number_input("Top plans", min_value=1, max_value=20, value=5, step=1, key="m_top")
        with m2:
            manual_strict = st.checkbox("Strict Layout", value=True, key="m_strict")
        with m3:
            if st.button("Reset default layout"):
                st.session_state.manual_blocks = create_default_blocks()
                seed_manual_default(st.session_state.manual_blocks)
                st.session_state.manual_plans = []
                st.rerun()

        cval, cplan = st.columns(2)
        with cval:
            if st.button("Validate Layout", key="validate_manual"):
                lv = validate_layout(st.session_state.manual_blocks, manual_strict)
                if lv["ok"]:
                    st.success(
                        f"Layout valid | R2={lv['counts']['R2']} R1={lv['counts']['R1']} FAKE={lv['counts']['FAKE']}"
                    )
                else:
                    st.error("Layout invalid")
                    for err in lv["errors"]:
                        st.write(f"- {err}")

        with cplan:
            if st.button("Compute Path", key="compute_manual"):
                lv = validate_layout(st.session_state.manual_blocks, manual_strict)
                if lv["ok"]:
                    st.session_state.manual_plans = compute_plans(
                        st.session_state.manual_blocks, int(manual_top_n), planning_mode
                    )
                else:
                    st.session_state.manual_plans = []
                    st.error("Layout invalid. Fix errors first.")

        manual_plans = st.session_state.manual_plans
        left, right = st.columns([1.05, 1])
        with left:
            st.subheader("Manual Map")
            selected_route = manual_plans[0]["route"] if manual_plans else []
            if manual_plans:
                label_options = [
                    f"#{i+1} score={p['score']} route=E->{'->'.join(map(str,p['route']))} pickups={p['pickups']}"
                    for i, p in enumerate(manual_plans)
                ]
                pick_idx = st.radio(
                    "Select plan",
                    range(len(manual_plans)),
                    format_func=lambda i: label_options[i],
                    index=0,
                    key="manual_plan_pick",
                )
                selected_route = manual_plans[pick_idx]["route"]

            render_map(st.session_state.manual_blocks, selected_route)

        with right:
            st.subheader("Validation / Plans")
            if manual_plans:
                p = manual_plans[st.session_state.get("manual_plan_pick", 0)]
                show_plan_detail(p)
            else:
                st.info("No valid plans found yet.")


if __name__ == "__main__":
    main()
