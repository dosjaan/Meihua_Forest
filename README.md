# Meihua Forest Planner (Robocon 2026)

R2-ийн Meihua Forest path planning, rule validation, estimation хийх app.

## Python Version (New)

JS app-ийн planner логикийг Python руу хөрвүүлсэн (`Streamlit`) хувилбар нэмсэн.

### Run (Python)

1. Folder руу орно:
```bash
cd /Your_repo_path/forest_path
```

2. Dependency суулгана:
```bash
python3 -m pip install -r requirements.txt
```

3. App асаана:
```bash
streamlit run app.py
```

4. Browser дээр нээнэ:
- http://localhost:8501

## Web Version (Original JS)

### Run (JS)

1. Static server асаана:
```bash
python3 -m http.server 8080
```

2. Browser дээр нээнэ:
- http://localhost:8080

## Project Files

- `app.py` - Python Streamlit UI + planner engine
- `requirements.txt` - Python dependencies
- `index.html` - original JS UI layout
- `styles.css` - original JS UI style
- `app.js` - original JS planner/scoring engine
- `robocon_meihua_requirements.md` - requirements/spec

## Python App Tabs

## `Auto Optimize`
- Random scenario үүсгэнэ
- Top-N plan тооцоолж score-оор эрэмбэлнэ
- Сонгосон route-г map дээр тодруулж харуулна

## `Manual Layout + Plan`
- 12 block тус бүр дээр `EMPTY / R2 / R1 / FAKE` сонгоно
- `Validate Layout` хийж rule шалгана
- `Compute Path` хийж route гаргана
- Сонгосон plan-ийн дэлгэрэнгүй metrics харна

## Implemented Core Rules

- Entrance link: block `2`
- Exit blocks: `10`, `12`
- Height matrix fixed: `[400,200,400] / [200,400,600] / [400,600,400] / [200,400,200]`
- Move: adjacent only, `|Δh| <= 200`, slope <= 20
- Entry/Exit boundary: `|Δh| == 200`
- Fake KFS touched: violation
- R1 forbidden blocks: `5, 8`
- Exit дээр R2 байвал тухайн exit block-ийг pickup хийх hard rule
- Action model: pickup, drop, wait, climb, descend, terrain
- Practical mode: wait/drop болон нийт actions-ийг давуу багасгаж эрэмбэлнэ

## Sanity Check

```bash
python3 -m py_compile app.py
node --check app.js
```
