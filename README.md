# Meihua Forest Planner (Robocon 2026)

R2-ийн Meihua Forest path planning, rule validation, estimation хийх энгийн web app.

## Quick Start

1. Folder руу орно:
```bash
cd /home/doska/Desktop/forest_path
```

2. Static server асаана:
```bash
python3 -m http.server 8080
```

3. Browser дээр нээнэ:
- http://localhost:8080

## Project Files

- `index.html` - UI layout
- `styles.css` - UI style
- `app.js` - planner, rule engine, scoring
- `robocon_meihua_requirements.md` - requirements/spec

## App Tabs

## `Auto Optimize`
- Random scenario үүсгэнэ (layout rules-ийг баримтална)
- Top-N route-уудыг score-оор эрэмбэлнэ
- Сонгосон route-ийг симуляцлана

## `Manual Layout + Plan`
- Block дээр click хийж `R2/R1/Fake/Empty` байрлуулна
- `Validate Layout` дарж rule шалгана
- `Compute Path` дарж route тооцоолно
- `Simulate` дарж замын явцыг үзнэ

## Implemented Key Rules (Summary)

- Entrance link: block `2`
- Exit blocks: `10`, `12`
- Height matrix: `[400,200,400] / [200,400,600] / [400,600,400] / [200,400,200]`
- Move: adjacent only, `|Δh| <= 200`, slope <= 20
- Entry/Exit boundary: `|Δh| == 200`
- R2 pickup: adjacent anchor block-оос (target block дээр заавал гарахгүй)
- Fake KFS touched: violation
- R1 KFS block: wait action-тайгаар pass
- Exit block дээр R2 KFS байвал: заавал түүнийг pickup хийж байж exit
- Action model: pickup, drop, wait, climb, descend бүгд тооцогдоно

## Scoring (High-level)

Score бага байх тусам сайн.

Score-д дараахууд орно:
- time, risk, steps, energy
- handling actions (pickup/drop/wait/climb/descend)
- one-scroll penalty
- R1 proximity penalties
- strategic exit bonus (`10`)
- exit-pickup bonuses/penalties
- first-last pickup policy penalty

## Troubleshooting

- Хэрвээ page update харагдахгүй байвал browser refresh (`Ctrl+Shift+R`) хийгээрэй.
- Server port ашиглагдаж байвал өөр port ашигла:
```bash
python3 -m http.server 8090
```

## Sanity Check (optional)

```bash
node --check /home/doska/Desktop/forest_path/app.js
```
