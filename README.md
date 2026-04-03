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
