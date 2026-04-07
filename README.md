# Meihua Forest Planner (Python / Streamlit)

R2 path planning болон layout validation хийх Streamlit app.

## Quick Start

1. Project folder руу орно:
```bash
cd /path/to/forest_path
```

2. Dependency суулгана:
```bash
python3 -m pip install -r requirements.txt
```

3. App ажиллуулна:
```bash
streamlit run app.py
```

4. Browser:
- `http://localhost:8501`

## ROS Bridge

The planner can also publish the best route directly to the robot project as `nav_msgs/Path`.

Requirements:

- source your ROS 2 environment first,
- run this from the same machine that can talk to `automate_robot`.

Example:

```bash
cd /home/saruul/Meihua_Forest
source /opt/ros/humble/setup.bash

python3 planner_ros_bridge.py \
  --r2-blocks 1,3,5,8 \
  --r1-blocks 10,11,12 \
  --fake-blocks 6 \
  --field-side blue \
  --top-left-x 0.0 \
  --top-left-y 0.0 \
  --block-pitch-x 0.40 \
  --block-pitch-y 0.40 \
  --publish-enter-event
```

What it does:

- computes the best legal plan using `planner_backend.py`,
- converts the route blocks into map-frame anchor poses,
- publishes `nav_msgs/Path` on `/planner/path`,
- optionally publishes `enter_meihua_forest` on `/main/event`,
- matches the current `automate_robot` contract where `main` buffers `/planner/path` and only consumes it in the `MEIHUA_FOREST` phase.

Important note:

- the default block-to-pose mapping is only a simple configurable grid,
- before real robot use, you should tune `top_left_x`, `top_left_y`, `block_pitch_x`, `block_pitch_y`, and yaw so the published path matches the real field anchors,
- the current bridge is good enough for path-interface integration, not yet for final match-calibrated forest execution.

## Tabs

## `Manual Layout + Plan`
- `R2 blocks`, `R1 blocks`, `Fake block`-ийг comma (`1,3,5`) хэлбэрээр оруулна.
- `Validate + Plan` дарна.
- Хэрэв бүрэн layout өгвөл шууд legal plan-уудыг бодно.
- Хэрэв дутуу layout өгвөл үлдсэн block-уудыг автоматаар нөхөж, хамгийн бага score-тэй legal completion + path-ийг сонгоно.
- `Top N plans`-оор хамгийн сайн plan-уудын тоог харуулна.
- `Planning mode`: `practical` эсвэл `strict`.

## `Scenario Generator`
- Random rule-valid layout-ууд үүсгэнэ.
- Layout бүрийн best plan-ийг бодож worst-case жагсаалт гаргана.
- `All feasible scenarios` эсвэл `Worst-only view` горимоор үзнэ.

## `Opponent Analysis`
- Opponent robot-ийн assumption-уудыг манай robot-оос тусад нь тохируулна.
- Preset-үүд: standard, single-scroll, four-scroll, 40cm climber, full threat.
- Exit mode-ийг `Official exits` эсвэл `Any block` болгож болно.
- Weight profile-уудыг preset-ээр сонгох эсвэл custom override хийж болно.
- Carry capacity, climb delta, min pickups, exits, weights-ийг opponent-only config дээрээс тусад нь сольж болно.

## Scoring Controls

`Action Scoring (Adjustable)` хэсгээс дараах жингүүдийг өөрчилж болно:
- Step
- Pickup
- Drop
- Turn
- Wait
- One-scroll penalty
- Strict mode exit bonuses

## Planner Constraints (Current)

- Grid: 3x4 blocks (1..12)
- Entrance anchor: block `2`
- Protected entry lane: blocks `1,2,3`
- Exit: `10`, `12`
- Height transitions: robot limits (`<=200mm`, allowed transition pair-ууд)
- Strict counts (complete layout үед):
  - `R2 = 4`
  - `R1 = 3`
  - `FAKE = 1`
- Fake block protected entry lane дээр (`1,2,3`) байж болохгүй

## Sanity Check

```bash
python3 -m py_compile app.py planner_backend.py tests/test_backend.py
python3 -m pytest -q
```
