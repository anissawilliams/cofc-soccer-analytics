cofc_soccer_analytics_2026/
├── .env
├── .env.example
├── requirements.txt
├── pyproject.toml              ← makes this an installable package, kills path hacks for good
├── README.md
│
├── cofc_analytics/              ← single top-level package, everything importable as cofc_analytics.X
│   ├── __init__.py
│   ├── db.py                    ← the one true db.py
│   │
│   ├── ingestion/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── ingest.py
│   │   ├── load_match.py
│   │   ├── load_season.py
│   │   ├── load_season_scores.py
│   │   ├── parse_wyscout.py
│   │   ├── parse_spiideo.py
│   │   ├── write_db.py
│   │   ├── attribute.py
│   │   ├── compress.py
│   │   ├── manifest.py
│   │   ├── generate_manifest.py
│   │   ├── full_pipeline.py
│   │   ├── rename_coug_tables.py
│   │   ├── spiideo_only.py
│   │   └── wyscout_only.py
│   │
│   ├── analytics/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── coug_table.py
│   │   ├── model.py
│   │   ├── report.py
│   │   ├── simulate.py
│   │   └── match_ingest.py      ← renamed from ingest.py to avoid confusion even with packages
│   │
│   └── api/
│       ├── __init__.py
│       └── main.py              ← FastAPI backend
│
├── streamlit_app/
│   └── app.py                   ← renamed from streamlit_app.py for clarity
│
├── schema/                       ← unchanged, SQL migrations
│
├── docs/                         ← unchanged
│
└── archive/                      ← dead code, never imported
    ├── db_v1.py
    ├── older_db.py
    └── main_v1.py