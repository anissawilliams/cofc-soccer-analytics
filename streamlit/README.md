# CofC Soccer Analytics — Application Layer

Analytics dashboards, coaching tools, and data APIs for the College of Charleston Men's Soccer program.

Built on top of the [CofC Soccer Pipeline](https://github.com/your-org/cofc-soccer-pipeline) which handles data ingestion and Supabase loading.

---

## What's in here

```
├── api/
│   ├── main.py          FastAPI backend — serves React frontend
│   └── db.py            Unified Supabase query layer (shared by API + Streamlit)
├── streamlit/
│   └── streamlit_app.py Coaching staff dashboard (password protected)
├── frontend/            React/TypeScript public-facing app
│   ├── src/
│   │   ├── App.jsx           Team analytics + COUG Table tabs
│   │   └── coug_dashboard.jsx COUG Table leaderboard
│   └── package.json
├── .env.example         Required environment variables (copy to .env)
└── requirements.txt     Python dependencies
```

---

## Apps

### Public — React Dashboard
The player-facing COUG Table and team analytics dashboard.
- COUG Table leaderboard (public, no login)
- Team analytics — attacking threat, defensive output, roster development
- Connects to FastAPI backend → Supabase

### Private — Streamlit Coaching Dashboard
Staff-only tools. Password protected.
- **Match Scouting** — opponent analysis, Monte Carlo win probability, full pre-match report
- **Tactical Scenario Simulator** — live sliders for possession, xG, pass accuracy → win probability updates in real time
- **Player Development** — COUG score trends, development targets, individual player breakdowns
- **Ask the Data** — AI query interface (coming soon, requires Anthropic API key)

---

## Setup

### 1. Clone and install
```bash
git clone https://github.com/your-org/cofc-soccer-analytics
cd cofc-soccer-analytics
pip install -r requirements.txt
```

### 2. Environment variables
```bash
cp .env.example .env
# Fill in SUPABASE_URL, SUPABASE_SERVICE_KEY, STREAMLIT_PASSWORD
```

### 3. Run the FastAPI backend
```bash
cd api
uvicorn main:app --reload --port 8000
```

### 4. Run the Streamlit dashboard
```bash
cd streamlit
streamlit run streamlit_app.py
```

### 5. Run the React frontend
```bash
cd frontend
npm install
npm run dev
```

---

## Data flow

```
Wyscout XML / Spiideo XML
        ↓
  [cofc-soccer-pipeline repo]
  parse → attribute → load
        ↓
    Supabase (PostgreSQL)
        ↓
      db.py  ←─────────────────────────────┐
      ↙           ↘                         │
FastAPI          Streamlit            (shared layer)
   ↓
React App
```

---

## Architecture decisions

**`db.py` is the single source of truth** for all Supabase queries. Both the FastAPI backend and Streamlit import from it. Add new queries here, not inline in the apps.

**Pending states everywhere** — charts and tables gracefully show "pending data" when Supabase doesn't have data yet (pre-XML pipeline). Nothing breaks, nothing is hardcoded.

**Trust tiers** — data source priority is handled in the pipeline repo. This repo just reads from Supabase and trusts what's there.

---

## Roadmap

- [ ] AI query interface (Tab 3) — requires Anthropic API key
- [ ] Pitch visualization — formation overlays, pressing triggers (requires Catapult tracking data)
- [ ] Jersey number filtering — upstream fix in pipeline repo
- [ ] Season-over-season comparisons
- [ ] Export to PDF for match day briefing packets

---

## Contributing

Data pipeline changes → [cofc-soccer-pipeline repo](https://github.com/your-org/cofc-soccer-pipeline)

Application/dashboard changes → this repo

Questions → Anissa Williams
