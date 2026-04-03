import unittest
from dataclasses import replace

from app import infer_best_plan_for_incomplete_layout
from planner_backend import (
    ENTRY_LANE_BLOCKS,
    Layout,
    OfficialRules,
    Plan,
    PlannerConfig,
    RobotLimits,
    StrategyPreferences,
    count_route_turns,
    plan_routes,
    rank_plans,
    validate_candidate_plan,
    validate_exit,
    validate_layout,
    validate_move,
    validate_pickup,
)


class PlannerBackendTests(unittest.TestCase):
    def setUp(self):
        self.cfg = PlannerConfig(
            official=OfficialRules(),
            robot=RobotLimits(),
            strategy=StrategyPreferences(),
        )

    def test_layout_valid_example(self):
        layout = Layout.from_lists(r2_blocks=[1, 3, 5, 8], r1_blocks=[10, 11, 12], fake_blocks=[6])
        ok, errors = validate_layout(layout, self.cfg, strict_counts=True)
        self.assertTrue(ok, errors)

    def test_layout_requires_exact_counts(self):
        layout = Layout.from_lists(r2_blocks=[1, 3, 5], r1_blocks=[10, 11], fake_blocks=[6])
        ok, errors = validate_layout(layout, self.cfg, strict_counts=True)
        self.assertFalse(ok)
        self.assertTrue(any("R2 count" in e for e in errors))
        self.assertTrue(any("R1 count" in e for e in errors))

    def test_fake_in_entrance_set_is_invalid(self):
        layout = Layout.from_lists(r2_blocks=[4, 5, 8, 9], r1_blocks=[6, 10, 12], fake_blocks=[ENTRY_LANE_BLOCKS[0]])
        ok, errors = validate_layout(layout, self.cfg, strict_counts=True)
        self.assertFalse(ok)
        self.assertTrue(any("Fake KFS cannot be placed" in e for e in errors))

    def test_fake_forbidden_blocks_follow_configuration(self):
        custom_cfg = PlannerConfig(
            official=OfficialRules(fake_forbidden_blocks=(2,)),
            robot=RobotLimits(),
            strategy=StrategyPreferences(),
        )
        layout = Layout.from_lists(r2_blocks=[4, 5, 8, 9], r1_blocks=[6, 10, 12], fake_blocks=[1])
        ok, errors = validate_layout(layout, custom_cfg, strict_counts=True)
        self.assertTrue(ok, errors)

    def test_r1_must_be_on_boundary_blocks(self):
        layout = Layout.from_lists(r2_blocks=[1, 3, 9, 12], r1_blocks=[5, 10, 11], fake_blocks=[6])
        ok, errors = validate_layout(layout, self.cfg, strict_counts=True)
        self.assertFalse(ok)
        self.assertTrue(any("legal boundary" in e for e in errors))

    def test_move_must_be_adjacent(self):
        layout = Layout.from_lists(r2_blocks=[1, 3, 5, 8], r1_blocks=[10, 11, 12], fake_blocks=[6])
        ok_move, reason = validate_move(layout, 2, 8, set(layout.r2_blocks), set(layout.r1_blocks), self.cfg)
        self.assertFalse(ok_move)
        self.assertIn("not adjacent", reason)

    def test_move_cannot_step_onto_any_kfs(self):
        layout = Layout.from_lists(r2_blocks=[1, 3, 5, 8], r1_blocks=[10, 11, 12], fake_blocks=[6])
        ok_move, reason = validate_move(layout, 2, 1, set(layout.r2_blocks), set(layout.r1_blocks), self.cfg)
        self.assertFalse(ok_move)
        self.assertIn("contains KFS", reason)
        ok_move2, reason2 = validate_move(layout, 3, 6, set(layout.r2_blocks), set(layout.r1_blocks), self.cfg)
        self.assertFalse(ok_move2)
        self.assertIn("contains KFS", reason2)
        ok_move3, reason3 = validate_move(layout, 7, 10, set(layout.r2_blocks), set(layout.r1_blocks), self.cfg)
        self.assertTrue(ok_move3)
        self.assertEqual("ok_with_r1_wait", reason3)

    def test_cleared_r1_block_is_traversable_without_waiting_again(self):
        layout = Layout.from_lists(r2_blocks=[4, 5, 8, 9], r1_blocks=[10, 11, 12], fake_blocks=[6])
        ok_move, reason = validate_move(layout, 8, 11, set(layout.r2_blocks), set(layout.r1_blocks), self.cfg)
        self.assertTrue(ok_move)
        self.assertEqual("ok_with_r1_wait", reason)

        remaining_r1_after_clear = {10, 12}
        ok_move2, reason2 = validate_move(layout, 8, 11, set(layout.r2_blocks), remaining_r1_after_clear, self.cfg)
        self.assertTrue(ok_move2)
        self.assertEqual("ok", reason2)

    def test_pickup_must_be_adjacent_and_r2(self):
        layout = Layout.from_lists(r2_blocks=[1, 3, 5, 8], r1_blocks=[10, 11, 12], fake_blocks=[6])
        ok_pick, _ = validate_pickup(2, 1, set(layout.r2_blocks), 0, 0, self.cfg)
        self.assertTrue(ok_pick)
        bad_pick, reason = validate_pickup(2, 8, set(layout.r2_blocks), 0, 0, self.cfg)
        self.assertFalse(bad_pick)
        self.assertIn("not adjacent", reason)

    def test_exit_requires_carry_count(self):
        layout = Layout.from_lists(r2_blocks=[1, 3, 5, 8], r1_blocks=[10, 11, 12], fake_blocks=[6])
        ok_exit, reason = validate_exit(layout, 10, 0, self.cfg)
        self.assertFalse(ok_exit)
        self.assertIn("at least one", reason)

    def test_first_pickup_from_entrance_is_enforced(self):
        layout = Layout.from_lists(r2_blocks=[2, 3, 5, 8], r1_blocks=[10, 11, 12], fake_blocks=[6])
        route = [2, 5, 4, 7, 10]
        pickups = [5]
        ok, reasons = validate_candidate_plan(layout, route, pickups, self.cfg)
        self.assertFalse(ok)
        self.assertTrue(any("first pickup" in r for r in reasons))

    def test_first_pickup_can_be_done_from_block_2_for_entry_lane_r2(self):
        layout = Layout.from_lists(r2_blocks=[1, 3, 5, 8], r1_blocks=[10, 11, 12], fake_blocks=[6])
        route = [2, 5, 4, 7, 10]
        pickups = [1, 3, 5]
        ok, reasons = validate_candidate_plan(layout, route, pickups, self.cfg)
        self.assertTrue(ok, reasons)

    def test_count_route_turns_counts_direction_changes(self):
        self.assertEqual(count_route_turns([2, 5, 8, 11]), 0)
        self.assertEqual(count_route_turns([2, 5, 8, 11, 10]), 1)
        self.assertEqual(count_route_turns([2, 5, 4, 7, 8, 11]), 4)

    def test_capacity_allows_drop_then_pick(self):
        layout = Layout.from_lists(r2_blocks=[2, 5, 8, 9], r1_blocks=[1, 4, 7], fake_blocks=[6])
        route = [2, 5, 8, 11, 10]
        pickups = [2, 5, 8]
        ok, reasons = validate_candidate_plan(layout, route, pickups, self.cfg)
        self.assertTrue(ok, reasons)

    def test_planner_returns_only_legal_ranked_plans(self):
        layout = Layout.from_lists(r2_blocks=[2, 5, 8, 9], r1_blocks=[1, 4, 7], fake_blocks=[6])
        plans = plan_routes(layout, self.cfg, top_n=5, mode="practical")
        self.assertGreaterEqual(len(plans), 1)
        for p in plans:
            ok, reasons = validate_candidate_plan(layout, list(p.route), list(p.pickups), self.cfg)
            self.assertTrue(ok, reasons)
            self.assertIn(p.exit_block, {10, 12})

    def test_layout_with_r1_on_exits_can_still_plan_via_wait_clearance(self):
        layout = Layout.from_lists(r2_blocks=[4, 5, 8, 9], r1_blocks=[10, 11, 12], fake_blocks=[6])
        plans = plan_routes(layout, self.cfg, top_n=5, mode="practical")
        self.assertGreaterEqual(len(plans), 1)
        self.assertTrue(any(p.wait_actions >= 1 for p in plans))

    def test_min_pickups_required_filters_one_scroll_plans(self):
        layout = Layout.from_lists(r2_blocks=[2, 5, 8, 9], r1_blocks=[1, 4, 7], fake_blocks=[6])
        strict_pick_cfg = replace(self.cfg, strategy=replace(self.cfg.strategy, min_pickups_required=2))
        plans = plan_routes(layout, strict_pick_cfg, top_n=10, mode="practical")
        self.assertGreaterEqual(len(plans), 1)
        self.assertTrue(all(len(p.pickups) >= 2 for p in plans))

    def test_action_weights_change_score(self):
        layout = Layout.from_lists(r2_blocks=[2, 5, 8, 9], r1_blocks=[1, 4, 7], fake_blocks=[6])
        base_plans = plan_routes(layout, self.cfg, top_n=1, mode="practical")
        heavy_step_cfg = replace(self.cfg, strategy=replace(self.cfg.strategy, step_weight=10.0))
        heavy_step_plans = plan_routes(layout, heavy_step_cfg, top_n=1, mode="practical")
        self.assertGreaterEqual(len(base_plans), 1)
        self.assertGreaterEqual(len(heavy_step_plans), 1)
        self.assertNotEqual(base_plans[0].score, heavy_step_plans[0].score)

    def test_strict_exit_10_12_have_independent_weights(self):
        p10 = Plan(
            route=[2, 5, 8, 11, 10],
            pickups=[2, 5],
            exit_block=10,
            steps=5,
            pickup_actions=2,
            drop_actions=0,
            turn_actions=0,
            wait_actions=0,
            carried_count=2,
            score=0.0,
        )
        p12 = Plan(
            route=[2, 5, 8, 9, 12],
            pickups=[2, 5],
            exit_block=12,
            steps=5,
            pickup_actions=2,
            drop_actions=0,
            turn_actions=0,
            wait_actions=0,
            carried_count=2,
            score=0.0,
        )

        cfg_exit10 = replace(self.cfg, strategy=replace(self.cfg.strategy, strict_exit10_bonus=5.0, strict_exit12_bonus=0.0))
        ranked10 = rank_plans([p10, p12], cfg_exit10, mode="strict")
        self.assertEqual(ranked10[0].exit_block, 10)

        cfg_exit12 = replace(self.cfg, strategy=replace(self.cfg.strategy, strict_exit10_bonus=0.0, strict_exit12_bonus=5.0))
        ranked12 = rank_plans([p10, p12], cfg_exit12, mode="strict")
        self.assertEqual(ranked12[0].exit_block, 12)

    def test_planner_records_actual_turn_counts(self):
        layout = Layout.from_lists(r2_blocks=[2, 5, 8, 9], r1_blocks=[1, 4, 7], fake_blocks=[6])
        plans = plan_routes(layout, self.cfg, top_n=10, mode="practical")
        self.assertGreaterEqual(len(plans), 1)
        for plan in plans:
            self.assertEqual(plan.turn_actions, count_route_turns(plan.route))

    def test_incomplete_layout_inference_returns_legal_completion(self):
        inferred_layout, plans = infer_best_plan_for_incomplete_layout([2, 5], [1], [], self.cfg, mode="practical", top_n=3)
        self.assertIsNotNone(inferred_layout)
        self.assertGreaterEqual(len(plans), 1)
        ok, errors = validate_layout(inferred_layout, self.cfg, strict_counts=True)
        self.assertTrue(ok, errors)

    def test_planner_finds_route_for_layout_with_entry_lane_r2_and_r1_exit_wait(self):
        layout = Layout.from_lists(r2_blocks=[1, 3, 5, 8], r1_blocks=[10, 11, 12], fake_blocks=[6])
        plans = plan_routes(layout, self.cfg, top_n=5, mode="practical")
        self.assertGreaterEqual(len(plans), 1)
        self.assertTrue(any(p.wait_actions >= 1 for p in plans))

    def test_anywhere_exit_profile_can_use_non_official_exit(self):
        any_exit_cfg = PlannerConfig(
            official=OfficialRules(official_exit_blocks=tuple(range(1, 13))),
            robot=RobotLimits(),
            strategy=replace(self.cfg.strategy, min_pickups_required=1),
        )
        layout = Layout.from_lists(r2_blocks=[1, 3, 5, 8], r1_blocks=[10, 11, 12], fake_blocks=[6])
        plans = plan_routes(layout, any_exit_cfg, top_n=10, mode="practical")
        self.assertGreaterEqual(len(plans), 1)
        self.assertTrue(any(p.exit_block not in {10, 12} for p in plans))

    def test_four_scroll_capacity_profile_can_collect_four_r2(self):
        four_scroll_cfg = PlannerConfig(
            official=OfficialRules(official_exit_blocks=tuple(range(1, 13))),
            robot=RobotLimits(
                max_step_mm=200,
                max_total_scrolls=4,
                max_hidden_slot=3,
                max_grip_slot=1,
                allowed_height_transitions=((0, 200), (200, 0), (200, 400), (400, 200), (400, 600), (600, 400)),
            ),
            strategy=replace(self.cfg.strategy, min_pickups_required=4, one_scroll_penalty=0.0),
        )
        layout = Layout.from_lists(r2_blocks=[1, 3, 5, 11], r1_blocks=[6, 10, 12], fake_blocks=[7])
        plans = plan_routes(layout, four_scroll_cfg, top_n=10, mode="practical")
        self.assertGreaterEqual(len(plans), 1)
        self.assertTrue(any(len(p.pickups) >= 4 for p in plans))


if __name__ == "__main__":
    unittest.main()
