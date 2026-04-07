from __future__ import annotations

import argparse
import math
from typing import Iterable, List, Sequence

import rclpy
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Path
from rclpy.node import Node
from std_msgs.msg import String

from planner_backend import Layout, PlannerConfig, block_position, plan_routes


def parse_csv_ids(raw: str) -> List[int]:
    raw = (raw or "").strip()
    if not raw:
        return []
    out: List[int] = []
    for token in raw.split(","):
        value = token.strip()
        if not value:
            continue
        if not value.isdigit():
            raise ValueError(f"Invalid block id: {value}")
        block_id = int(value)
        if block_id < 1 or block_id > 12:
            raise ValueError(f"Block id out of range: {block_id}")
        out.append(block_id)
    return sorted(out)


def quaternion_from_yaw(yaw: float) -> Sequence[float]:
    return (0.0, 0.0, math.sin(yaw / 2.0), math.cos(yaw / 2.0))


def normalize_field_side(raw_value: str) -> str:
    value = str(raw_value).strip().lower()
    if value not in {"blue", "red"}:
        raise ValueError("field_side must be 'blue' or 'red'")
    return value


class PlannerRosBridge(Node):
    def __init__(self, args: argparse.Namespace) -> None:
        super().__init__("planner_ros_bridge")
        self.args = args
        self.path_pub = self.create_publisher(Path, args.path_topic, 10)
        self.event_pub = self.create_publisher(String, args.event_topic, 10)

        layout = Layout.from_lists(
            r2_blocks=parse_csv_ids(args.r2_blocks),
            r1_blocks=parse_csv_ids(args.r1_blocks),
            fake_blocks=parse_csv_ids(args.fake_blocks),
        )
        self.plan = self._select_plan(layout, args.mode, args.top_n)
        self.path_msg = self._build_path_message(self.plan.route)
        self.enter_event_sent = False

        self.get_logger().info(
            "Planner route ready: "
            f"route={self.plan.route} pickups={self.plan.pickups} "
            f"exit={self.plan.exit_block} score={self.plan.score:.2f}"
        )
        self.create_timer(1.0 / max(args.publish_hz, 0.1), self.on_timer)

    def _select_plan(self, layout: Layout, mode: str, top_n: int):
        plans = plan_routes(layout, PlannerConfig(), top_n=top_n, mode=mode)
        if not plans:
            raise RuntimeError("Planner produced no legal route for the given layout")
        return plans[0]

    def _build_path_message(self, route_blocks: Iterable[int]) -> Path:
        msg = Path()
        msg.header.frame_id = self.args.frame_id
        now_msg = self.get_clock().now().to_msg()
        msg.header.stamp = now_msg

        for block_id in route_blocks:
            x, y, yaw = self._block_anchor_pose(block_id)
            pose = PoseStamped()
            pose.header.frame_id = self.args.frame_id
            pose.header.stamp = now_msg
            pose.pose.position.x = x
            pose.pose.position.y = y
            qx, qy, qz, qw = quaternion_from_yaw(yaw)
            pose.pose.orientation.x = qx
            pose.pose.orientation.y = qy
            pose.pose.orientation.z = qz
            pose.pose.orientation.w = qw
            msg.poses.append(pose)
        return msg

    def _block_anchor_pose(self, block_id: int):
        row, col = block_position(block_id)
        blue_x = self.args.top_left_x + (col * self.args.block_pitch_x)
        blue_y = self.args.top_left_y - (row * self.args.block_pitch_y)
        blue_yaw = math.radians(self.args.default_yaw_deg)

        if self.args.field_side == "blue":
            return blue_x, blue_y, blue_yaw

        red_x = self.args.field_width_m - blue_x
        red_y = blue_y
        red_yaw = math.atan2(math.sin(math.pi - blue_yaw), math.cos(math.pi - blue_yaw))
        return red_x, red_y, red_yaw

    def on_timer(self) -> None:
        stamp = self.get_clock().now().to_msg()
        self.path_msg.header.stamp = stamp
        for pose in self.path_msg.poses:
            pose.header.stamp = stamp
        self.path_pub.publish(self.path_msg)

        if self.args.publish_enter_event and not self.enter_event_sent:
            msg = String()
            msg.data = "enter_meihua_forest"
            self.event_pub.publish(msg)
            self.enter_event_sent = True
            self.get_logger().info("Published enter_meihua_forest event")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish the best Meihua Forest plan as nav_msgs/Path")
    parser.add_argument("--r2-blocks", required=True, help="Comma-separated R2 block ids, e.g. 1,3,5,8")
    parser.add_argument("--r1-blocks", required=True, help="Comma-separated R1 block ids, e.g. 10,11,12")
    parser.add_argument("--fake-blocks", required=True, help="Comma-separated fake block ids, usually one value")
    parser.add_argument("--mode", default="practical", choices=["practical", "strict"])
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--path-topic", default="/planner/path")
    parser.add_argument("--event-topic", default="/main/event")
    parser.add_argument("--publish-enter-event", action="store_true")
    parser.add_argument("--frame-id", default="map")
    parser.add_argument("--field-side", type=normalize_field_side, default="blue")
    parser.add_argument("--field-width-m", type=float, default=12.15)
    parser.add_argument(
        "--top-left-x",
        type=float,
        default=0.0,
        help="Blue-side x coordinate for block 1 anchor in the map frame",
    )
    parser.add_argument(
        "--top-left-y",
        type=float,
        default=0.0,
        help="Blue-side y coordinate for block 1 anchor in the map frame",
    )
    parser.add_argument("--block-pitch-x", type=float, default=0.40)
    parser.add_argument("--block-pitch-y", type=float, default=0.40)
    parser.add_argument("--default-yaw-deg", type=float, default=0.0)
    parser.add_argument("--publish-hz", type=float, default=2.0)
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    rclpy.init()
    node = PlannerRosBridge(args)
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
