import { useState, useEffect, useMemo } from "react";
import { cachedApiFetch } from "./apiCache";

// ─── Design tokens — Cougars identity ────────────────────────────────────────
const T = {
  bg:           "#1a0a0a",
  surface:      "#220d0d",
  surface2:     "#2d1010",
  border:       "#3d1a1a",
  borderGold:   "#4a3800",
  garnet:       "#800000",
  garnetBright: "#a01020",
  garnetLight:  "#c0263b",
  gold:         "#CFB53B",
  goldDim:      "#8a7a28",
  goldFaint:    "#CFB53B14",
  goldBg:       "#CFB53B22",
  text:         "#f5ede0",
  textMuted:    "#c8a888",
  muted:        "#7a5a4a",
  dim:          "#3d1a1a",
  green:        "#1a5c2a",
  greenText:    "#4ade80",
  redText:      "#f87171",
  drawText:     "#CFB53B",
};

const ASET_COLOR = "#c0263b";
const PEAK_COLOR = "#CFB53B";
const SP_COLOR   = "#8a7a55";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
const CONFIGURED_ACTIVE_SEASON = import.meta.env.VITE_ACTIVE_SEASON || "2026";

async function apiFetch(path) {
  return cachedApiFetch(API, path);
}

function per90(score, minutes) {
  if (!minutes || minutes < 20) return null;
  return (score / minutes) * 90;
}
function fmtScore(v) {
  if (v === null || v === undefined) return "—";
  return Number(v).toFixed(2);
}
function fmtMins(v) {
  if (!v && v !== 0) return "—";
  return `${Math.round(v)}'`;
}

// ─── Score bar ────────────────────────────────────────────────────────────────
function ScoreBar({ value, max, color }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div style={{ flex: 1, height: 4, background: T.dim, borderRadius: 2, overflow: "hidden", minWidth: 40 }}>
        <div style={{ width: `${pct}%`, height: "100%", background: color, borderRadius: 2,
          boxShadow: pct > 60 ? `0 0 6px ${color}88` : "none" }} />
      </div>
      <span style={{ fontSize: 12, fontVariantNumeric: "tabular-nums", color: T.text,
        minWidth: 38, textAlign: "right", fontWeight: 500 }}>
        {fmtScore(value)}
      </span>
    </div>
  );
}

// ─── Minutes display ──────────────────────────────────────────────────────────
function MinutesDisplay({ minutes }) {
  return (
    <span style={{ fontSize: 12, color: T.textMuted, fontVariantNumeric: "tabular-nums" }}>
      {fmtMins(minutes)}
    </span>
  );
}

// ─── Result chip ─────────────────────────────────────────────────────────────
function ResultChip({ result, gf, ga }) {
  if (!result) return null;
  const color = result === "W" ? T.greenText : result === "L" ? T.redText : T.drawText;
  const bg    = result === "W" ? "#14532d44" : result === "L" ? "#7f1d1d44" : "#78350f44";
  return (
    <span style={{
      fontSize: 10, fontWeight: 700, padding: "2px 6px",
      borderRadius: 3, background: bg, color,
    }}>
      {result} {gf !== null && ga !== null ? `${gf}–${ga}` : ""}
    </span>
  );
}

// ─── Table header ─────────────────────────────────────────────────────────────
const COLS_SEASON = "28px 60px minmax(130px,1fr) 110px 44px 1fr 1fr 80px 88px 72px";
const COLS_MATCH  = "28px 60px minmax(130px,1fr) 110px 1fr 1fr 80px 88px";

function TableHeader({ isSeason }) {
  const h = { fontSize: 12, color: T.muted, letterSpacing: 2, fontWeight: 800, textTransform: "uppercase" };
  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: isSeason ? COLS_SEASON : COLS_MATCH,
      gap: 8, alignItems: "center",
      padding: "10px 28px",
      background: T.surface,
      borderBottom: `1px solid ${T.border}`,
      position: "sticky", top: 0, zIndex: 10,
    }}>
      <span style={h}>#</span>
      <span style={{ ...h }}>POS</span>
      <span style={h}>PLAYER</span>
      <span style={h}>MINS</span>
      {isSeason && <span style={{ ...h, textAlign: "center" }}>MP</span>}
      <span style={{ ...h, color: ASET_COLOR }}>ASET</span>
      <span style={{ ...h, color: PEAK_COLOR }}>PEAK</span>
      <span style={{ ...h, color: SP_COLOR }}>SP</span>
      <span style={{ ...h, textAlign: "right" }}>TOTAL</span>
      {isSeason && <span style={{ ...h, textAlign: "right", color: T.gold }}>/90</span>}
    </div>
  );
}

// ─── Player row ───────────────────────────────────────────────────────────────
function PlayerRow({ player, rank, maxTotal, isSeason, selected, onClick }) {
  const p90 = per90(player.total_score, player.minutes_played);
  const isTop3 = rank <= 3;
  const bg = selected ? T.surface2 : "transparent";
  const rankColor = rank === 1 ? T.gold : rank === 2 ? T.textMuted : rank === 3 ? "#cd7f32" : T.muted;

  return (
    <div
      onClick={onClick}
      style={{
        display: "grid",
        gridTemplateColumns: isSeason ? COLS_SEASON : COLS_MATCH,
        gap: 8, alignItems: "center",
        padding: "11px 28px",
        borderBottom: `1px solid ${T.border}`,
        background: bg,
        cursor: "pointer",
        transition: "background 0.1s",
        borderLeft: selected ? `3px solid ${T.gold}` : "3px solid transparent",
      }}
      onMouseEnter={e => { if (!selected) e.currentTarget.style.background = T.surface; }}
      onMouseLeave={e => { if (!selected) e.currentTarget.style.background = bg; }}
    >
      {/* Rank */}
      <span style={{
        fontSize: isTop3 ? 13 : 11,
        fontWeight: isTop3 ? 800 : 400,
        color: rankColor,
        fontVariantNumeric: "tabular-nums",
        textAlign: "center",
      }}>
        {rank}
      </span>

      {/* Position */}
      <span style={{
        fontSize: 12, fontWeight: 700, letterSpacing: 1,
        color: T.muted,
        background: T.dim, borderRadius: 3,
        padding: "2px 6px", textAlign: "center",
        whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
      }}>
        {player.position || "—"}
      </span>

      {/* Name */}
      <span style={{
        fontSize: 13, fontWeight: selected ? 700 : 600,
        color: selected ? T.gold : T.text,
        letterSpacing: 0.2,
        whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
      }}>
        {player.name}
      </span>

      {/* Minutes */}
      <MinutesDisplay minutes={player.minutes_played} />

      {/* MP — season only */}
      {isSeason && (
        <span style={{ fontSize: 12, color: T.textMuted, textAlign: "center",
          fontVariantNumeric: "tabular-nums" }}>
          {player.matches || "—"}
        </span>
      )}

      {/* ASET */}
      <ScoreBar value={player.aset_score} max={maxTotal * 0.65} color={ASET_COLOR} />

      {/* PEAK */}
      <ScoreBar value={player.peak_score} max={maxTotal * 0.65} color={PEAK_COLOR} />

      {/* SP */}
      <ScoreBar value={player.set_piece_score || 0} max={maxTotal * 0.3} color={SP_COLOR} />

      {/* Total */}
      <div style={{ textAlign: "right" }}>
        <span style={{
          fontSize: isTop3 ? 15 : 13,
          fontWeight: 800,
          color: isTop3 ? T.gold : T.text,
          fontVariantNumeric: "tabular-nums",
        }}>
          {fmtScore(player.total_score)}
        </span>
      </div>

      {/* /90 — season only */}
      {isSeason && (
        <div style={{ textAlign: "right" }}>
          <span style={{
            fontSize: 12, fontWeight: 500,
            color: p90 !== null ? T.goldDim : T.muted,
            fontVariantNumeric: "tabular-nums",
          }}>
            {p90 !== null ? fmtScore(p90) : "—"}
          </span>
        </div>
      )}
    </div>
  );
}

// ─── Player detail panel ──────────────────────────────────────────────────────
function PlayerPanel({ player, history }) {
  if (!player) return null;
  const avg = history.length
    ? history.reduce((s, m) => s + (m.total_score || 0), 0) / history.length
    : 0;
  const p90 = per90(player.total_score, player.minutes_played);

  return (
    <div style={{
      background: T.surface,
      borderLeft: `1px solid ${T.border}`,
      overflowY: "auto",
      display: "flex", flexDirection: "column",
    }}>
      {/* Player header */}
      <div style={{
        padding: "20px 20px 16px",
        borderBottom: `1px solid ${T.border}`,
        background: `linear-gradient(135deg, ${T.garnet}33 0%, transparent 100%)`,
      }}>
        <div style={{
          fontSize: 12, fontWeight: 800, letterSpacing: 2,
          color: T.muted, marginBottom: 6,
        }}>PLAYER PROFILE</div>
        <div style={{ fontSize: 20, fontWeight: 800, color: T.text, letterSpacing: 0.5 }}>
          {player.name}
        </div>
        <div style={{ display: "flex", gap: 8, marginTop: 8, alignItems: "center" }}>
          <span style={{
            fontSize: 12, fontWeight: 700, letterSpacing: 1,
            background: T.dim, color: T.muted,
            padding: "3px 8px", borderRadius: 3,
          }}>{player.position}</span>
          <span style={{ fontSize: 12, color: T.muted }}>
            {player.position_group}
          </span>
        </div>
      </div>

      {/* Score breakdown */}
      <div style={{ padding: "16px 20px", borderBottom: `1px solid ${T.border}` }}>
        <div style={{ fontSize: 12, color: T.muted, letterSpacing: 2, fontWeight: 800, marginBottom: 10 }}>
          SCORE BREAKDOWN
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          {[
            { label: "ASET", value: player.aset_score, color: ASET_COLOR, sub: "Defense" },
            { label: "PEAK", value: player.peak_score, color: PEAK_COLOR, sub: "Offense" },
            { label: "SET PIECE", value: player.set_piece_score || 0, color: SP_COLOR, sub: "Restarts" },
            { label: "TOTAL", value: player.total_score, color: T.gold, sub: "Combined" },
          ].map(s => (
            <div key={s.label} style={{
              background: T.surface2,
              border: `1px solid ${s.label === "TOTAL" ? T.borderGold : T.border}`,
              borderRadius: 6, padding: "10px 12px",
            }}>
              <div style={{ fontSize: 11, color: s.color, letterSpacing: 1.5, fontWeight: 800 }}>{s.label}</div>
              <div style={{ fontSize: 11, color: T.muted, marginBottom: 4 }}>{s.sub}</div>
              <div style={{ fontSize: 22, fontWeight: 800, color: s.label === "TOTAL" ? T.gold : T.text,
                fontVariantNumeric: "tabular-nums" }}>
                {fmtScore(s.value)}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Minutes & efficiency */}
      <div style={{ padding: "16px 20px", borderBottom: `1px solid ${T.border}` }}>
        <div style={{ fontSize: 12, color: T.muted, letterSpacing: 2, fontWeight: 800, marginBottom: 10 }}>
          EFFICIENCY
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          <div style={{ background: T.surface2, border: `1px solid ${T.border}`, borderRadius: 6, padding: "10px 12px" }}>
            <div style={{ fontSize: 11, color: T.muted, letterSpacing: 1 }}>MINUTES</div>
            <div style={{ fontSize: 20, fontWeight: 700, color: T.text }}>{fmtMins(player.minutes_played)}</div>
          </div>
          <div style={{ background: T.surface2, border: `1px solid ${T.borderGold}`, borderRadius: 6, padding: "10px 12px" }}>
            <div style={{ fontSize: 11, color: T.muted, letterSpacing: 1 }}>SCORE / 90</div>
            <div style={{ fontSize: 20, fontWeight: 700, color: T.gold }}>
              {p90 !== null ? fmtScore(p90) : "—"}
            </div>
          </div>
        </div>
      </div>

      {/* Match history */}
      {history.length > 0 && (
        <div style={{ padding: "16px 20px", flex: 1 }}>
          <div style={{ fontSize: 12, color: T.muted, letterSpacing: 2, fontWeight: 800, marginBottom: 10 }}>
            MATCH HISTORY
          </div>
          {history.map((m, i) => (
            <div key={i} style={{
              display: "grid", gridTemplateColumns: "80px 1fr 50px 36px 44px",
              gap: 6, alignItems: "center",
              padding: "7px 0",
              borderBottom: `1px solid ${T.border}`,
            }}>
              <span style={{ fontSize: 10, color: T.muted }}>{m.session_date}</span>
              <span style={{ fontSize: 11, color: T.text, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {m.opponent || "—"}
              </span>
              <ResultChip result={m.result} gf={m.goals_for} ga={m.goals_against} />
              <span style={{ fontSize: 11, color: T.muted, textAlign: "center" }}>
                {fmtMins(m.minutes_played)}
              </span>
              <span style={{
                fontSize: 12, fontWeight: 700, textAlign: "right",
                color: (m.total_score || 0) > avg ? T.gold : T.muted,
                fontVariantNumeric: "tabular-nums",
              }}>
                {fmtScore(m.total_score)}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Main ─────────────────────────────────────────────────────────────────────
export default function CougTable() {
  const [tab, setTab]                   = useState("season");
  const [season, setSeason]             = useState(CONFIGURED_ACTIVE_SEASON);
  const [seasons, setSeasons]           = useState([CONFIGURED_ACTIVE_SEASON]);
  const [matches, setMatches]           = useState([]);
  const [selectedMatch, setSelectedMatch] = useState(null);
  const [seasonData, setSeasonData]     = useState([]);
  const [matchData, setMatchData]       = useState([]);
  const [selectedPlayer, setSelectedPlayer] = useState(null);
  const [playerHistory, setPlayerHistory] = useState([]);
  const [sortBy, setSortBy]             = useState("total");
  const [filterPos, setFilterPos]       = useState("ALL");
  const [loading, setLoading]           = useState(true);
  const [error, setError]               = useState(null);

  useEffect(() => {
    apiFetch("/api/seasons")
      .then(payload => {
        // Accept the old array response during rolling deployments.
        const available = Array.isArray(payload) ? payload : payload.seasons || [];
        const configured = Array.isArray(payload)
          ? CONFIGURED_ACTIVE_SEASON
          : payload.active_season || CONFIGURED_ACTIVE_SEASON;
        const normalized = Array.from(new Set([configured, ...available].map(String).filter(Boolean)))
          .sort((a, b) => b.localeCompare(a, undefined, { numeric: true }));
        setSeasons(normalized);
        setSeason(normalized[0]);
      })
      .catch(() => {
        setSeasons([CONFIGURED_ACTIVE_SEASON]);
        setSeason(CONFIGURED_ACTIVE_SEASON);
      });
  }, []);

  useEffect(() => {
    if (!season) return;
    apiFetch(`/api/team/matches?season=${season}`)
      .then(m => {
        setMatches(m);
        if (m.length > 0) setSelectedMatch(m[0]);
      })
      .catch(e => setError(e.message));
  }, [season]);

  useEffect(() => {
    if (!season || tab !== "season") return;
    setLoading(true);
    apiFetch(`/api/coug-leaderboard-with-minutes/${season}`)
      .then(d => { setSeasonData(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, [season, tab]);

  useEffect(() => {
    if (!selectedMatch || tab !== "match") return;
    setLoading(true);
    // Use session_id (from the match object) not match_id
    const sid = selectedMatch.session_id || selectedMatch.match_id;
    apiFetch(`/api/coug-scores-with-minutes?session_id=${sid}&season=${season}`)
      .then(d => { setMatchData(d); setLoading(false); })
      .catch(e => { setError(e.message); setLoading(false); });
  }, [selectedMatch, tab]);

  useEffect(() => {
    if (!selectedPlayer) { setPlayerHistory([]); return; }
    apiFetch(`/api/player-match-history/${selectedPlayer.athlete_id}?season=${season}`)
      .then(setPlayerHistory)
      .catch(() => setPlayerHistory([]));
  }, [selectedPlayer, season]);

  const data = tab === "season" ? seasonData : matchData;

  const posGroups = useMemo(() => (
    ["ALL", ...new Set(data.map(p => p.position_group).filter(Boolean))]
  ), [data]);

  const filtered = useMemo(() => {
    let d = filterPos === "ALL" ? data : data.filter(p => p.position_group === filterPos);
    const sorts = {
      total: (a, b) => (b.total_score || 0) - (a.total_score || 0),
      aset:  (a, b) => (b.aset_score  || 0) - (a.aset_score  || 0),
      peak:  (a, b) => (b.peak_score  || 0) - (a.peak_score  || 0),
      per90: (a, b) => (per90(b.total_score, b.minutes_played) ?? -1) - (per90(a.total_score, a.minutes_played) ?? -1),
    };
    return [...d].sort(sorts[sortBy] || sorts.total);
  }, [data, sortBy, filterPos]);

  const maxTotal = useMemo(() => Math.max(...filtered.map(p => p.total_score || 0), 1), [filtered]);

  const teamTotals = useMemo(() => ({
    aset: data.reduce((s, p) => s + (p.aset_score || 0), 0),
    peak: data.reduce((s, p) => s + (p.peak_score || 0), 0),
    sp:   data.reduce((s, p) => s + (p.set_piece_score || 0), 0),
  }), [data]);

  const selectStyle = {
    background: T.surface2, border: `1px solid ${T.border}`,
    color: T.text, padding: "6px 12px", borderRadius: 4,
    fontSize: 12, cursor: "pointer", outline: "none",
  };

  return (
    <div style={{
      height: "100vh", display: "flex", flexDirection: "column",
      background: T.bg, color: T.text,
      fontFamily: "'Inter', 'SF Pro Display', system-ui, sans-serif",
      overflow: "hidden",
    }}>

      {/* ── Header ── */}
      <div style={{
        background: `linear-gradient(90deg, ${T.garnet} 0%, #5a0000 100%)`,
        padding: "14px 28px",
        display: "flex", justifyContent: "space-between", alignItems: "center",
        borderBottom: `2px solid ${T.gold}`,
        flexShrink: 0,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div>
            <div style={{
              fontFamily: "'Oswald', 'Barlow Condensed', 'Impact', sans-serif",
              fontSize: 26, fontWeight: 700, letterSpacing: 4,
              color: T.gold, textTransform: "uppercase", lineHeight: 1,
            }}>
              COUGS TABLE
            </div>
            <div style={{ fontSize: 12, color: "#f0c0c0", letterSpacing: 3, marginTop: 3 }}>
              COLLEGE OF CHARLESTON · MEN'S SOCCER
            </div>
          </div>
        </div>

        <select value={season} onChange={e => setSeason(e.target.value)} style={{
          ...selectStyle,
          background: T.garnet + "88",
          border: `1px solid ${T.gold}44`,
          color: T.gold, fontWeight: 700,
        }}>
          {seasons.map(item => <option key={item} value={item}>{item} Season</option>)}
        </select>
      </div>

      {/* ── Team totals bar ── */}
      {!loading && data.length > 0 && (
        <div style={{
          display: "flex",
          background: T.surface,
          borderBottom: `1px solid ${T.border}`,
          flexShrink: 0,
        }}>
          {[
            { label: "ASET", sub: "DEFENSE",  val: teamTotals.aset, color: ASET_COLOR },
            { label: "PEAK", sub: "OFFENSE",  val: teamTotals.peak, color: PEAK_COLOR },
            { label: "SP",   sub: "RESTARTS", val: teamTotals.sp,   color: SP_COLOR   },
          ].map((t, i) => (
            <div key={t.label} style={{
              flex: 1, padding: "10px 28px",
              borderRight: i < 2 ? `1px solid ${T.border}` : "none",
              display: "flex", justifyContent: "space-between", alignItems: "center",
            }}>
              <div>
                <div style={{ fontSize: 11, color: t.color, letterSpacing: 2, fontWeight: 800 }}>{t.label}</div>
                <div style={{ fontSize: 11, color: T.muted, letterSpacing: 1.5, marginTop: 1 }}>{t.sub}</div>
              </div>
              <div style={{
                fontFamily: "'Oswald', 'Impact', sans-serif",
                fontSize: 24, fontWeight: 700, color: t.color,
                fontVariantNumeric: "tabular-nums",
              }}>
                {t.val.toFixed(1)}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Tab + controls bar ── */}
      <div style={{
        display: "flex", alignItems: "center",
        background: T.surface,
        borderBottom: `1px solid ${T.border}`,
        padding: "0 28px", gap: 0,
        flexShrink: 0,
      }}>
        {/* Tabs */}
        {["season", "match"].map(t => (
          <button key={t} onClick={() => { setTab(t); setSelectedPlayer(null); }} style={{
            background: "transparent", border: "none",
            borderBottom: tab === t ? `2px solid ${T.gold}` : "2px solid transparent",
            color: tab === t ? T.gold : T.muted,
            fontFamily: "'Oswald', sans-serif",
            fontSize: 14, fontWeight: 700, letterSpacing: 2,
            padding: "13px 24px", cursor: "pointer",
            textTransform: "uppercase", transition: "color 0.15s",
            marginBottom: -1,
          }}>
            {t === "season" ? "Season" : "Match"}
          </button>
        ))}

        {/* Match dropdown */}
        {tab === "match" && matches.length > 0 && (
          <div style={{ marginLeft: 16, display: "flex", alignItems: "center", gap: 8 }}>
            <span style={{ fontSize: 11, color: T.muted, letterSpacing: 1.5, fontWeight: 700 }}>VS</span>
            <select
              value={selectedMatch?.session_id || selectedMatch?.match_id || ""}
              onChange={e => {
                const m = matches.find(m =>
                  (m.session_id || m.match_id) === e.target.value
                );
                setSelectedMatch(m);
                setSelectedPlayer(null);
              }}
              style={selectStyle}
            >
              {matches.map(m => {
                const sid = m.session_id || m.match_id;
                return (
                  <option key={sid} value={sid}>
                    {m.date} · {m.opponent} {m.result ? `(${m.result} ${m.goals_for ?? ""}–${m.goals_against ?? ""})` : ""}
                  </option>
                );
              })}
            </select>
          </div>
        )}

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* Position filter */}
        <div style={{ display: "flex", gap: 4, alignItems: "center", marginRight: 12 }}>
          {posGroups.map(g => (
            <button key={g} onClick={() => setFilterPos(g)} style={{
              background: filterPos === g ? T.garnet : "transparent",
              border: `1px solid ${filterPos === g ? T.garnetLight : T.border}`,
              color: filterPos === g ? T.gold : T.muted,
              fontSize: 12, fontWeight: 800, letterSpacing: 1.5,
              padding: "6px 14px", borderRadius: 3, cursor: "pointer",
              transition: "all 0.12s",
            }}>{g}</button>
          ))}
        </div>

        {/* Sort */}
        <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
          <span style={{ fontSize: 11, color: T.muted, letterSpacing: 1.5, fontWeight: 700 }}>SORT</span>
          {[
            { key: "total", label: "TOTAL" },
            { key: "aset",  label: "ASET"  },
            { key: "peak",  label: "PEAK"  },
            ...(tab === "season" ? [{ key: "per90", label: "/90" }] : []),
          ].map(s => (
            <button key={s.key} onClick={() => setSortBy(s.key)} style={{
              background: sortBy === s.key ? T.goldBg : "transparent",
              border: `1px solid ${sortBy === s.key ? T.gold : T.border}`,
              color: sortBy === s.key ? T.gold : T.muted,
              fontSize: 12, fontWeight: 800, letterSpacing: 1.5,
              padding: "6px 14px", borderRadius: 3, cursor: "pointer",
              transition: "all 0.12s",
            }}>{s.label}</button>
          ))}
        </div>
      </div>

      {/* ── Content ── */}
      <div style={{ flex: 1, display: "grid", gridTemplateColumns: selectedPlayer ? "1fr 300px" : "1fr", overflow: "hidden" }}>

        {/* Table */}
        <div style={{ overflowY: "auto" }}>
          {loading ? (
            <div style={{ padding: "4rem", textAlign: "center" }}>
              <div style={{ fontFamily: "'Oswald', sans-serif", fontSize: 13, letterSpacing: 3, color: T.muted }}>
                LOADING...
              </div>
            </div>
          ) : error ? (
            <div style={{ padding: "3rem", textAlign: "center", color: T.redText }}>
              {error}
            </div>
          ) : (
            <>
              <TableHeader isSeason={tab === "season"} />
              {filtered.length === 0 ? (
                <div style={{ padding: "4rem", textAlign: "center" }}>
                  <div style={{ fontFamily: "'Oswald', sans-serif", fontSize: 13, letterSpacing: 3, color: T.muted }}>
                    NO DATA
                  </div>
                  <div style={{ fontSize: 12, color: T.muted, marginTop: 8 }}>
                    {tab === "match" ? "Select a match above" : "No data for this season"}
                  </div>
                </div>
              ) : filtered.map((p, i) => (
                <PlayerRow
                  key={p.athlete_id || p.name}
                  player={p}
                  rank={i + 1}
                  maxTotal={maxTotal}
                  isSeason={tab === "season"}
                  selected={selectedPlayer?.athlete_id === p.athlete_id}
                  onClick={() => setSelectedPlayer(
                    selectedPlayer?.athlete_id === p.athlete_id ? null : p
                  )}
                />
              ))}
            </>
          )}
        </div>

        {/* Player panel */}
        {selectedPlayer && (
          <PlayerPanel player={selectedPlayer} history={playerHistory} />
        )}
      </div>

      {/* ── Footer ── */}
      <div style={{
        padding: "8px 28px",
        borderTop: `1px solid ${T.border}`,
        display: "flex", justifyContent: "space-between", alignItems: "center",
        background: T.surface, flexShrink: 0,
      }}>
        <div style={{ display: "flex", gap: 16 }}>
          {[[" ASET — Defense", ASET_COLOR], ["PEAK — Offense", PEAK_COLOR], ["Set Piece", SP_COLOR]].map(([l, c]) => (
            <div key={l} style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <div style={{ width: 8, height: 8, borderRadius: 2, background: c }} />
              <span style={{ fontSize: 11, color: T.muted }}>{l}</span>
            </div>
          ))}
        </div>
        <span style={{ fontSize: 11, color: T.muted, letterSpacing: 1.5 }}>
          WYSCOUT · TRIAL_1 WEIGHTS · {season}
        </span>
      </div>
    </div>
  );
}
