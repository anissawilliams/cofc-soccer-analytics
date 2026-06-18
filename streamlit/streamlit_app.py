"""
streamlit_app.py
================
CofC Soccer Analytics — Coaching Staff Dashboard
Password protected. Three tabs:
  1. Match Scouting    — Monte Carlo simulation + pre-match report
  2. Player Development — targets, trends, positional comparisons
  3. Ask the Data      — placeholder for AI query interface

Run:
    streamlit run streamlit_app.py

Environment variables (.env):
    SUPABASE_URL
    SUPABASE_SERVICE_KEY
    STREAMLIT_PASSWORD
"""

import os
import sys
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from dotenv import load_dotenv
sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CofC Soccer — Coaching Dashboard",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Colors ────────────────────────────────────────────────────────────────────
GARNET = "#800000"
GOLD   = "#CFB53B"
DARK   = "#1A1A1A"
GRAY   = "#666666"

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown(f"""
<style>
    .stApp {{ background-color: #f3f4f6; }}
    .main-header {{
        background-color: white;
        padding: 1.2rem 2rem;
        border-bottom: 3px solid {GARNET};
        margin-bottom: 1.5rem;
    }}
    .main-header h1 {{
        color: {GARNET};
        margin: 0;
        font-size: 1.6rem;
        font-weight: 700;
    }}
    .main-header p {{
        color: {GRAY};
        margin: 0.2rem 0 0;
        font-size: 0.85rem;
    }}
    .metric-card {{
        background: white;
        border-radius: 10px;
        padding: 1rem 1.2rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.06);
    }}
    .pending-box {{
        background: #f9fafb;
        border: 1px dashed #d1d5db;
        border-radius: 8px;
        padding: 1.5rem;
        text-align: center;
        color: #6b7280;
    }}
    .stTabs [data-baseweb="tab-list"] {{
        gap: 8px;
    }}
    .stTabs [data-baseweb="tab"] {{
        background-color: white;
        border-radius: 6px 6px 0 0;
        padding: 8px 20px;
        font-weight: 600;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: {GARNET} !important;
        color: white !important;
    }}
</style>
""", unsafe_allow_html=True)


# ── Password gate ─────────────────────────────────────────────────────────────
def check_password():
    if st.session_state.get("authenticated"):
        return True

    st.markdown(f"""
    <div style="max-width:400px; margin:5rem auto; background:white;
                padding:2.5rem; border-radius:12px;
                box-shadow:0 4px 12px rgba(0,0,0,0.1);
                border-top: 4px solid {GARNET};">
        <h2 style="color:{GARNET}; margin:0 0 0.5rem;">⚽ CofC Soccer</h2>
        <p style="color:{GRAY}; margin:0 0 1.5rem; font-size:0.9rem;">
            Coaching Staff Dashboard — Restricted Access
        </p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("login"):
        password = st.text_input("Password", type="password", placeholder="Enter staff password")
        submitted = st.form_submit_button("Sign In", use_container_width=True)
        if submitted:
            expected = os.environ.get("STREAMLIT_PASSWORD", "cougars2025")
            if password == expected:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Incorrect password")
    return False


if not check_password():
    st.stop()


# ── Import db + simulation modules ────────────────────────────────────────────
try:
    sys.path.insert(0, str(Path(__file__).parent))
    sys.path.insert(0, str(Path(__file__).parent.parent))
    import db
    DB_CONNECTED = True
except Exception as e:
    DB_CONNECTED = False
    import traceback
    st.error(traceback.format_exc())  # shows full traceback in the app
    st.warning(f"Database connection issue: {e}")

try:
    sys.path.insert(0, str(Path(__file__).parent))                          # streamlit/ folder
    sys.path.insert(0, str(Path(__file__).parent.parent))                   # project root
    sys.path.insert(0, str(Path(__file__).parent.parent / "pipeline" / "analytics"))  # simulate.py, report.py, ingest.py, config.py
    from simulate import simulate_match
    from report import generate_scouting_report, get_team_season_profile, get_recent_form
    from ingest import load_matches, build_match_features
    from config import TEAM_INGEST_DIR
    SIMULATION_AVAILABLE = True
except Exception as e:
    SIMULATION_AVAILABLE = False
    print(f"[streamlit_app] simulation modules not available: {e}")


# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>Charleston Cougars · Coaching Dashboard</h1>
    <p>Match Scouting · Player Development · Staff Only</p>
</div>
""", unsafe_allow_html=True)


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("https://upload.wikimedia.org/wikipedia/en/thumb/5/5e/College_of_Charleston_Cougars_logo.svg/200px-College_of_Charleston_Cougars_logo.svg.png", width=120)
    st.markdown(f"### Season Controls")
    season = st.selectbox("Season", ["2025", "2026"], index=0)
    st.divider()
    st.markdown(f"<small style='color:{GRAY}'>CofC Soccer Analytics<br>Staff access only</small>", unsafe_allow_html=True)
    if st.button("Sign Out", use_container_width=True):
        st.session_state["authenticated"] = False
        st.rerun()


# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["🔍 Match Scouting", "📈 Player Development", "🤖 Ask the Data"])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — MATCH SCOUTING
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.subheader("Pre-Match Scouting Report")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("#### Opponent Details")
        with st.form("scouting_form"):
            opponent_name   = st.text_input("Opponent", placeholder="e.g. UNCW Seahawks")
            match_date      = st.date_input("Match Date")
            competition     = st.selectbox("Competition", ["CAA", "Non-Conference", "Preseason", "Tournament"])

            st.markdown("#### Opponent Season Averages")
            opp_xg_for      = st.number_input("xG For (per match)",     min_value=0.0, max_value=5.0, value=1.20, step=0.05)
            opp_xg_against  = st.number_input("xG Against (per match)", min_value=0.0, max_value=5.0, value=1.10, step=0.05)
            opp_pass_acc    = st.number_input("Pass Accuracy %",         min_value=0.0, max_value=100.0, value=72.0, step=0.5)
            opp_possession  = st.number_input("Possession %",            min_value=0.0, max_value=100.0, value=48.0, step=0.5)
            n_sims          = st.select_slider("Simulations", options=[1000, 5000, 10000], value=10000)

            generate = st.form_submit_button("Generate Report", use_container_width=True)

    with col2:
        if generate and opponent_name:
            if SIMULATION_AVAILABLE:
                try:
                    df = load_matches(TEAM_INGEST_DIR + "cofc_matches_2025.xlsx")
                    features = build_match_features(df)

                    sim = simulate_match(
                        xg_home=get_team_season_profile(features)["avg_xg_for"],
                        xg_away=opp_xg_for,
                        n_simulations=n_sims
                    )

                    # Win probability gauge
                    st.markdown("#### Match Probabilities")
                    c1, c2, c3 = st.columns(3)
                    c1.metric("CofC Win",  f"{sim['home_win_pct']:.1%}", delta=None)
                    c2.metric("Draw",      f"{sim['draw_pct']:.1%}",     delta=None)
                    c3.metric("CofC Loss", f"{sim['away_win_pct']:.1%}", delta=None)

                    # Probability bar
                    fig = go.Figure(go.Bar(
                        x=[sim['home_win_pct'], sim['draw_pct'], sim['away_win_pct']],
                        y=["Win", "Draw", "Loss"],
                        orientation="h",
                        marker_color=[GARNET, GOLD, GRAY],
                        text=[f"{v:.1%}" for v in [sim['home_win_pct'], sim['draw_pct'], sim['away_win_pct']]],
                        textposition="inside",
                    ))
                    fig.update_layout(
                        height=180, margin=dict(l=0, r=0, t=10, b=0),
                        paper_bgcolor="white", plot_bgcolor="white",
                        xaxis=dict(showticklabels=False, showgrid=False),
                        yaxis=dict(showgrid=False),
                    )
                    st.plotly_chart(fig, use_container_width=True)

                    # Scoreline distribution
                    st.markdown("#### Most Likely Scorelines")
                    scores = sim["top_scorelines"]
                    score_df = pd.DataFrame([
                        {"Scoreline": f"CofC {s[0]}–{s[1]} {opponent_name}", "Probability": count / n_sims}
                        for s, count in scores.items()
                    ])
                    fig2 = px.bar(
                        score_df, x="Scoreline", y="Probability",
                        color_discrete_sequence=[GARNET],
                        text=score_df["Probability"].apply(lambda x: f"{x:.1%}"),
                    )
                    fig2.update_layout(height=250, margin=dict(l=0, r=0, t=10, b=0),
                                       paper_bgcolor="white", plot_bgcolor="white",
                                       yaxis=dict(tickformat=".0%"))
                    fig2.update_traces(textposition="outside")
                    st.plotly_chart(fig2, use_container_width=True)

                    # Full text report
                    st.markdown("#### Full Scouting Report")
                    report = generate_scouting_report(
                        features=features,
                        opponent_name=opponent_name,
                        opponent_xg_for=opp_xg_for,
                        opponent_xg_against=opp_xg_against,
                        opponent_pass_acc=opp_pass_acc,
                        opponent_possession=opp_possession,
                        match_date=str(match_date),
                        n_simulations=n_sims,
                    )
                    st.code(report, language=None)
                    st.download_button(
                        "Download Report",
                        data=report,
                        file_name=f"scouting_{opponent_name.replace(' ', '_')}_{match_date}.txt",
                        mime="text/plain",
                        use_container_width=True,
                    )

                except Exception as e:
                    st.error(f"Simulation error: {e}")
                    st.info("Make sure cofc_matches_2025.xlsx is in the configured TEAM_INGEST_DIR.")
            else:
                # Simulation modules not available — use db.py match data
                st.markdown("#### Match Probabilities")
                st.info("Monte Carlo simulation available when match data file is configured. Showing season record from Supabase.")
                if DB_CONNECTED:
                    summary = db.get_team_summary(season)
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Record", summary.get("record", "—"))
                    c2.metric("Goals For", summary.get("goals_for", "—"))
                    c3.metric("Goals Against", summary.get("goals_against", "—"))
                    c4.metric("Clean Sheets", summary.get("clean_sheets", "—"))

        elif generate and not opponent_name:
            st.warning("Please enter an opponent name.")
        else:
            # Default state — show season summary
            st.markdown("#### Season Summary")
            if DB_CONNECTED:
                summary = db.get_team_summary(season)
                if summary.get("matches", 0) > 0:
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Record",       summary.get("record", "—"))
                    c2.metric("Goals For",    summary.get("goals_for", "—"))
                    c3.metric("Goals Against",summary.get("goals_against", "—"))
                    c4.metric("Clean Sheets", summary.get("clean_sheets", "—"))

                    matches = db.get_match_results(season)
                    if matches:
                        st.markdown("#### Match Results")
                        df = pd.DataFrame(matches)
                        df["Result"] = df["result"].map({"W": "✅ W", "D": "➖ D", "L": "❌ L"})
                        st.dataframe(
                            df[["date", "opponent", "goals_for", "goals_against", "Result", "competition"]].rename(columns={
                                "date": "Date", "opponent": "Opponent",
                                "goals_for": "GF", "goals_against": "GA",
                                "competition": "Competition"
                            }),
                            use_container_width=True, hide_index=True
                        )
                else:
                    st.markdown('<div class="pending-box">⏳ Match results will appear here once data is loaded into Supabase.</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="pending-box">⚠️ Database not connected. Check your .env file.</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TACTICAL SCENARIO SIMULATOR (inside Tab 1, below scouting report)
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.divider()
    st.subheader("🎛️ Tactical Scenario Simulator")
    st.markdown("Drag the sliders to explore how different match conditions affect win probability in real time.")

    if SIMULATION_AVAILABLE:
        try:
            df_sim = load_matches(TEAM_INGEST_DIR + "cofc_matches_2025.xlsx")
            features_sim = build_match_features(df_sim)
            profile_sim  = get_team_season_profile(features_sim)

            sc1, sc2 = st.columns(2)

            with sc1:
                st.markdown("**CofC Conditions**")
                cofc_xg_scenario   = st.slider("Our xG",            0.0, 4.0, float(round(profile_sim["avg_xg_for"], 2)),   0.05, key="cofc_xg")
                cofc_poss_scenario = st.slider("Our Possession %",   30,  70,  int(profile_sim["avg_possession"]),            1,    key="cofc_poss")
                cofc_pass_scenario = st.slider("Our Pass Accuracy %",50,  95,  int(profile_sim["avg_pass_acc"]),              1,    key="cofc_pass")

            with sc2:
                st.markdown("**Opponent Conditions**")
                opp_xg_scenario    = st.slider("Opponent xG",            0.0, 4.0, float(round(profile_sim["avg_xg_against"], 2)), 0.05, key="opp_xg")
                opp_poss_scenario  = st.slider("Opponent Possession %",   30,  70,  100 - int(profile_sim["avg_possession"]),        1,    key="opp_poss")
                opp_pass_scenario  = st.slider("Opponent Pass Accuracy %", 50,  95,  70,                                              1,    key="opp_pass")

            # Run simulation on every slider change
            scenario_sim = simulate_match(
                xg_home=cofc_xg_scenario,
                xg_away=opp_xg_scenario,
                n_simulations=10000,
            )

            # Results
            rc1, rc2, rc3 = st.columns(3)
            rc1.metric(
                "Win Probability",
                f"{scenario_sim['home_win_pct']:.1%}",
                delta=f"{scenario_sim['home_win_pct'] - profile_sim['avg_xg_for'] / (profile_sim['avg_xg_for'] + profile_sim['avg_xg_against'] + 0.001):.1%} vs baseline",
            )
            rc2.metric("Draw Probability", f"{scenario_sim['draw_pct']:.1%}")
            rc3.metric("Loss Probability", f"{scenario_sim['away_win_pct']:.1%}")

            # Visual gauge
            fig_sc = go.Figure(go.Bar(
                x=[scenario_sim['home_win_pct'], scenario_sim['draw_pct'], scenario_sim['away_win_pct']],
                y=["CofC Win", "Draw", "CofC Loss"],
                orientation="h",
                marker_color=[GARNET, GOLD, GRAY],
                text=[f"{v:.1%}" for v in [scenario_sim['home_win_pct'], scenario_sim['draw_pct'], scenario_sim['away_win_pct']]],
                textposition="inside",
            ))
            fig_sc.update_layout(
                height=160, margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor="white", plot_bgcolor="white",
                xaxis=dict(showticklabels=False, showgrid=False, range=[0, 1]),
                yaxis=dict(showgrid=False),
            )
            st.plotly_chart(fig_sc, use_container_width=True)

            # Tactical insight callouts
            insights = []
            if cofc_poss_scenario >= 55:
                insights.append(f"✅ Possession dominance ({cofc_poss_scenario}%) — high press supported, transition risk lower")
            elif cofc_poss_scenario <= 42:
                insights.append(f"⚠️ Low possession ({cofc_poss_scenario}%) — counter-attack and set piece focus recommended")

            if cofc_xg_scenario >= 1.5:
                insights.append(f"✅ High xG scenario ({cofc_xg_scenario:.2f}) — attacking shape creating quality chances")
            elif cofc_xg_scenario <= 0.7:
                insights.append(f"⚠️ Low xG ({cofc_xg_scenario:.2f}) — chance creation needs attention in this scenario")

            if opp_xg_scenario >= 1.8:
                insights.append(f"⚠️ High opponent xG ({opp_xg_scenario:.2f}) — defensive shape and set piece discipline critical")

            if cofc_pass_scenario >= 80:
                insights.append(f"✅ High pass accuracy ({cofc_pass_scenario}%) — PEAK phase sequences more likely to complete")

            if insights:
                st.markdown("**Tactical Read:**")
                for insight in insights:
                    st.markdown(f"- {insight}")

            # Pitch visualization placeholder
            st.divider()
            st.markdown(f"""
            <div style="background:#f9fafb; border:1px dashed #d1d5db; border-radius:8px;
                        padding:1.5rem; text-align:center; color:#6b7280;">
                <p style="margin:0; font-size:1.1rem;">🏟️ <strong>Pitch Visualization — Coming Soon</strong></p>
                <p style="margin:0.5rem 0 0; font-size:0.85rem;">
                    Formation overlays, pressing triggers, and player movement animations
                    will appear here once Catapult tracking data is integrated.
                </p>
            </div>
            """, unsafe_allow_html=True)

        except Exception as e:
            st.markdown(f'<div class="pending-box">⏳ Tactical simulator available once match data file is configured.<br><small>{e}</small></div>', unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="background:#f9fafb; border:1px dashed #d1d5db; border-radius:8px;
                    padding:1.5rem; text-align:center; color:#6b7280;">
            <p style="margin:0; font-size:1.1rem;">🎛️ <strong>Tactical Simulator — Coming Soon</strong></p>
            <p style="margin:0.5rem 0 0; font-size:0.85rem;">
                Available once the match data file is configured and simulation modules are loaded.
            </p>
        </div>
        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — PLAYER DEVELOPMENT
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("Player Development Tracker")

    if not DB_CONNECTED:
        st.markdown('<div class="pending-box">⚠️ Database not connected. Check your .env file.</div>', unsafe_allow_html=True)
    else:
        dev_data = db.get_roster_development(season)
        players  = db.get_players()
        scores   = db.get_coug_scores(season=season)

        # ── Development targets table ─────────────────────────────────────
        st.markdown("#### Development Targets by Position")
        if dev_data:
            df = pd.DataFrame(dev_data)

            # Color status
            def status_color(val):
                if val == "On Target":    return "background-color: #fef9c3; color: #713f12"
                if val == "Developing":   return "background-color: #fee2e2; color: #991b1b"
                if val == "Pending Data": return "background-color: #f3f4f6; color: #6b7280"
                return ""

            display_cols = ["name", "position", "Metric", "Value", "Goal", "Status"]
            styled = df[display_cols].rename(columns={"name": "Player", "position": "Position"})
            st.dataframe(
                styled.style.applymap(status_color, subset=["Status"]),
                use_container_width=True, hide_index=True
            )

            # Summary counts
            c1, c2, c3 = st.columns(3)
            on_target  = len(df[df["Status"] == "On Target"])
            developing = len(df[df["Status"] == "Developing"])
            pending    = len(df[df["Status"] == "Pending Data"])
            c1.metric("On Target",    on_target)
            c2.metric("Developing",   developing)
            c3.metric("Pending Data", pending)

        else:
            st.markdown('<div class="pending-box">⏳ Player development data will appear here once athletes are loaded into Supabase.</div>', unsafe_allow_html=True)

        st.divider()

        # ── COUG Score leaderboard ────────────────────────────────────────
        st.markdown("#### COUG Table — Season Leaderboard")
        if scores:
            leaderboard = db.get_season_coug_leaderboard(season)
            if leaderboard:
                lb_df = pd.DataFrame(leaderboard)
                fig = px.bar(
                    lb_df.head(15), x="name", y="total_score",
                    color="position_group",
                    color_discrete_map={"GK": GRAY, "DEF": "#1d4ed8", "MID": GOLD, "FWD": GARNET},
                    labels={"name": "Player", "total_score": "Total Score", "position_group": "Position"},
                    title="Season COUG Scores (Top 15)",
                )
                fig.update_layout(
                    height=350, paper_bgcolor="white", plot_bgcolor="white",
                    xaxis_tickangle=-30, margin=dict(l=0, r=0, t=40, b=0),
                )
                st.plotly_chart(fig, use_container_width=True)

                # Score breakdown
                st.markdown("#### Score Breakdown")
                breakdown_df = lb_df[["name", "aset_score", "peak_score", "set_piece_score", "positional_score", "load_score", "total_score", "matches"]].copy()
                breakdown_df.columns = ["Player", "ASET", "PEAK", "Set Piece", "Positional", "Load", "Total", "Matches"]
                st.dataframe(breakdown_df, use_container_width=True, hide_index=True)
        else:
            st.markdown('<div class="pending-box">⏳ COUG scores will appear here once the XML pipeline runs and scores are calculated.</div>', unsafe_allow_html=True)

        st.divider()

        # ── Individual player view ────────────────────────────────────────
        st.markdown("#### Individual Player")
        if players:
            player_names = ["Select a player..."] + [p["name"] for p in players]
            selected = st.selectbox("Player", player_names)

            if selected != "Select a player...":
                player = next((p for p in players if p["name"] == selected), None)
                if player:
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Position",       player.get("position", "—"))
                    c2.metric("Position Group", player.get("position_group", "—"))

                    # Per-match COUG scores
                    player_scores = [s for s in scores if s.get("name") == selected] if scores else []
                    if player_scores:
                        c3.metric("Matches Scored", len(player_scores))
                        ps_df = pd.DataFrame(player_scores)
                        fig = px.line(
                            ps_df, x="session_date", y="total_score",
                            markers=True, title=f"{selected} — COUG Score per Match",
                            color_discrete_sequence=[GARNET],
                        )
                        fig.add_hline(y=ps_df["total_score"].mean(), line_dash="dash",
                                     line_color=GOLD, annotation_text="Season avg")
                        fig.update_layout(height=300, paper_bgcolor="white", plot_bgcolor="white",
                                         margin=dict(l=0, r=0, t=40, b=0))
                        st.plotly_chart(fig, use_container_width=True)

                        # Score component breakdown per match
                        components = ["aset_score", "peak_score", "set_piece_score", "positional_score"]
                        fig2 = px.bar(
                            ps_df, x="session_date", y=components,
                            title=f"{selected} — Score Components per Match",
                            color_discrete_map={
                                "aset_score": "#1d4ed8", "peak_score": GARNET,
                                "set_piece_score": GOLD, "positional_score": "#16a34a"
                            },
                            labels={"value": "Score", "session_date": "Match", "variable": "Component"},
                            barmode="stack",
                        )
                        fig2.update_layout(height=280, paper_bgcolor="white", plot_bgcolor="white",
                                          margin=dict(l=0, r=0, t=40, b=0))
                        st.plotly_chart(fig2, use_container_width=True)
                    else:
                        c3.metric("Matches Scored", 0)
                        st.markdown('<div class="pending-box">⏳ Per-match scores will appear here after the XML pipeline runs.</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="pending-box">⏳ Player roster will appear here once athletes are loaded into Supabase.</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — ASK THE DATA (Placeholder)
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("Ask the Data")

    st.markdown(f"""
    <div style="background:white; border-radius:12px; padding:2rem;
                border-left: 5px solid {GOLD}; margin-bottom:1.5rem;">
        <h3 style="color:{GARNET}; margin:0 0 0.75rem;">🤖 AI Query Interface — Coming Soon</h3>
        <p style="color:{GRAY}; margin:0 0 1rem;">
            This tab will let you ask plain-English questions about your team's data.
            Type a question, get an answer — no SQL required.
        </p>
        <p style="color:{GRAY}; margin:0; font-size:0.9rem;"><strong>Example questions:</strong></p>
        <ul style="color:{GRAY}; font-size:0.9rem; margin:0.5rem 0 0 1rem;">
            <li>Who has the highest ASET score in CAA matches?</li>
            <li>Which players are below their development target?</li>
            <li>How do we perform in the second half vs the first?</li>
            <li>Who are our top 3 players in possession regains?</li>
            <li>Show me all matches where we conceded from set pieces</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    # Disabled query box as preview
    st.text_input(
        "Ask a question about your team...",
        placeholder="e.g. Who has the most PEAK actions this season?",
        disabled=True,
        help="AI queries require an Anthropic API key. Coming soon!"
    )

    st.button("Ask", disabled=True, use_container_width=False)

    st.markdown(f"""
    <div style="background:#f9fafb; border-radius:8px; padding:1rem 1.5rem; margin-top:1rem;">
        <p style="color:{GRAY}; margin:0; font-size:0.85rem;">
            ⏳ <strong>Status:</strong> Pending API access.
            When enabled, this feature will use Claude (Anthropic) to answer questions
            about your Supabase data in plain English.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Manual query filters as a useful interim
    st.markdown("#### Manual Filters — Available Now")
    st.markdown("While AI queries are pending, use these filters to explore your data.")

    if DB_CONNECTED:
        filter_col1, filter_col2 = st.columns(2)
        with filter_col1:
            metric_filter = st.selectbox(
                "View leaders by metric",
                ["total_score", "aset_score", "peak_score", "set_piece_score"],
                format_func=lambda x: x.replace("_", " ").title()
            )
        with filter_col2:
            pos_filter = st.selectbox("Position group", ["All", "GK", "DEF", "MID", "FWD"])

        scores = db.get_coug_scores(season=season)
        if scores:
            leaderboard = db.get_season_coug_leaderboard(season)
            df = pd.DataFrame(leaderboard)
            if pos_filter != "All":
                df = df[df["position_group"] == pos_filter]
            df = df.sort_values(metric_filter, ascending=False)
            st.dataframe(
                df[["name", "position", "matches", metric_filter]].rename(columns={
                    "name": "Player", "position": "Position",
                    "matches": "Matches", metric_filter: metric_filter.replace("_", " ").title()
                }),
                use_container_width=True, hide_index=True
            )
        else:
            st.markdown('<div class="pending-box">⏳ Data available after XML pipeline runs.</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="pending-box">⚠️ Database not connected.</div>', unsafe_allow_html=True)