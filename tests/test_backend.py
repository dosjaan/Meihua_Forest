import unittest
from dataclasses import replace

from planner_backend import (
    Layout,
    OfficialRules,
    Plan,
    PlannerConfig,
    RobotLimits,
    StrategyPreferences,
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
        layout = Layout.from_lists(r2_blocks=[4, 5, 8, 9], r1_blocks=[6, 10, 12], fake_blocks=[2])
        ok, errors = validate_layout(layout, self.cfg, strict_counts=True)
        self.assertFalse(ok)
        self.assertTrue(any("Fake KFS cannot be placed" in e for e in errors))

    def test_r1_must_be_on_boundary_blocks(self):
        layout = Layout.from_lists(r2_blocks=[1, 3, 9, 12], r1_blocks=[5, 10, 11], fake_blocks=[6])
        ok, errors = validate_layout(layout, self.cfg, strict_counts=True)
        self.assertFalse(ok)
        self.assertTrue(any("legal boundary" in e for e in errors))

    def test_move_must_be_adjacent(self):
        layout = Layout.from_lists(r2_blocks=[1, 3, 5, 8], r1_blocks=[10, 11, 12], fake_blocks=[6])
        ok_move, reason = validate_move(layout, 2, 8, set(layout.r2_blocks), self.cfg)
        self.assertFalse(ok_move)
        self.assertIn("not adjacent", reason)

    def test_move_cannot_step_onto_any_kfs(self):
        layout = Layout.from_lists(r2_blocks=[1, 3, 5, 8], r1_blocks=[10, 11, 12], fake_blocks=[6])
        ok_move, reason = validate_move(layout, 2, 1, set(layout.r2_blocks), self.cfg)
        self.assertFalse(ok_move)
        self.assertIn("contains KFS", reason)
        ok_move2, reason2 = validate_move(layout, 3, 6, set(layout.r2_blocks), self.cfg)
        self.assertFalse(ok_move2)
        self.assertIn("contains KFS", reason2)
        ok_move3, reason3 = validate_move(layout, 7, 10, set(layout.r2_blocks), self.cfg)
        self.assertTrue(ok_move3)
        self.assertEqual("ok_with_r1_wait", reason3)

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


if __name__ == "__main__":
    unittest.main()
