import { useState, useMemo, useRef, useEffect } from "react";

// ═══════════════════════════════════════════════════════════════════════════
// COUGS TABLE DASHBOARD — Dynamic CSV Loader
// 1. Load roster.csv once per season (name, number, pos, group)
// 2. Load match CSVs as they're generated — scores come from the CSV
// Zero hardcoded player data.
//
// roster.csv format:
//   name,number,pos,group
//   J. Schumacher,0,GK,GK
//   N. Gold,23,CB,DEF
//   E. White,8,DMF,MID
//   L. Gill,10,CF,ATT
// ═══════════════════════════════════════════════════════════════════════════

const C = {
  maroon: "#76232f", maroonDeep: "#5a1a24", maroonDark: "#3d1119",
  goldMetal: "#9d8958", gold: "#c5b783", goldLight: "#d4c99a",
  gray: "#d9d9d6", grayMid: "#8a8a87",
  bg: "#0e0b09", card: "#1a1614", card2: "#221e1b",
  text: "#f0ebe4", muted: "#9e9589",
};

const catC = {
  ASET:       { bg: "rgba(118,35,47,0.22)",   border: "#76232f",   text: "#e8a0aa", label: "#ff8a98" },
  PEAK:       { bg: "rgba(157,137,88,0.22)",  border: "#9d8958",   text: "#d4c99a", label: "#c5b783" },
  "SET PIECE":{ bg: "rgba(217,217,214,0.12)", border: "#8a8a8755", text: "#b8b8b5", label: "#d9d9d6" },
};

// ═══════════════════════════════════════════════════════════════════════════
// ROSTER CSV PARSER
// Returns: { "E. White": { number: "8", pos: "DMF", group: "MID" }, ... }
// ═══════════════════════════════════════════════════════════════════════════
function parseRosterCSV(text) {
  const lines = text.trim().split("\n").filter(Boolean);
  const headers = lines[0].split(",").map(h => h.trim());
  const roster = {};
  lines.slice(1).forEach(line => {
    const vals = line.split(",").map(v => v.trim());
    const row = {};
    headers.forEach((h, i) => { row[h] = vals[i] ?? ""; });
    if (row.name) {
      roster[row.name] = {
        number: row.number || "?",
        pos:    row.pos    || "?",
        group:  row.group  || "UNK",
      };
    }
  });
  return roster;
}

// ═══════════════════════════════════════════════════════════════════════════
// MATCH CSV PARSER
// ═══════════════════════════════════════════════════════════════════════════
const TEAM_NAME_MAP = {
  "WILLIAMMARY":    "William & Mary",
  "WILLIAM_MARY":   "William & Mary",
  "WILLIAMANDMARY": "William & Mary",
  "UNCW":           "UNCW Seahawks",
  "ELON":           "Elon Phoenix",
  "DREXEL":         "Drexel Dragons",
  "HOFSTRA":        "Hofstra Pride",
  "TOWSON":         "Towson Tigers",
  "NORTHEASTERN":   "Northeastern Huskies",
  "HAMPTON":        "Hampton Pirates",
  "CAMPBELL":       "Campbell Camels",
  "MONMOUTH":       "Monmouth Hawks",
  "STONYBROOK":     "Stony Brook Seawolves",
};

function inferOpponent(filename) {
  const raw = filename.replace(/\.csv$/i,"").replace(/coug_table_/i,"")
    .replace(/_match$/i,"").replace(/[_-]/g,"").toUpperCase();
  if (TEAM_NAME_MAP[raw]) return TEAM_NAME_MAP[raw];
  const rawSpaced = filename.replace(/\.csv$/i,"").replace(/coug_table_/i,"")
    .replace(/_match$/i,"").replace(/_/g," ").trim();
  const up = rawSpaced.toUpperCase().replace(/\s/g,"");
  for (const [k,v] of Object.entries(TEAM_NAME_MAP)) {
    if (up.includes(k) || k.includes(up)) return v;
  }
  return rawSpaced.replace(/\b\w/g, c => c.toUpperCase()) || "Unknown";
}

function formatDate(raw) {
  if (!raw) return "";
  const dmy = raw.match(/^(\d{2})\.(\d{2})\.(\d{4})$/);
  if (dmy) {
    const d = new Date(`${dmy[3]}-${dmy[2]}-${dmy[1]}`);
    return d.toLocaleDateString("en-US", { month:"short", day:"numeric", year:"numeric" });
  }
  const iso = new Date(raw);
  if (!isNaN(iso)) return iso.toLocaleDateString("en-US", { month:"short", day:"numeric", year:"numeric" });
  return raw;
}

function inferDate(filename) {
  const m = filename.match(/(\d{4}[-_]\d{2}[-_]\d{2})/);
  if (m) return formatDate(m[1].replace(/_/g,"-"));
  return "";
}

function parseMatchCSV(text, filename, roster) {
  const lines = text.trim().split("\n").filter(Boolean);
  const headers = lines[0].split(",").map(h => h.trim());

  const rows = lines.slice(1).map(line => {
    const vals = [];
    let cur = "", inQ = false;
    for (const ch of line) {
      if (ch === '"') { inQ = !inQ; }
      else if (ch === "," && !inQ) { vals.push(cur.trim()); cur = ""; }
      else cur += ch;
    }
    vals.push(cur.trim());
    const row = {};
    headers.forEach((h, i) => { row[h] = vals[i] ?? ""; });
    return row;
  }).filter(r => r.player);

  if (!rows.length) return null;

  const first = rows[0];
  const opponent = first.opponent || inferOpponent(filename);
  const date     = formatDate(first.date || "") || inferDate(filename);
  const cofcG    = parseInt(first.cofc_goals ?? 0, 10);
  const oppG     = parseInt(first.opp_goals  ?? 0, 10);
  const result   = (first.cofc_goals != null && first.cofc_goals !== "")
    ? `${cofcG > oppG ? "W" : cofcG < oppG ? "L" : "D"} ${cofcG}\u2013${oppG}`
    : "\u2013";

  const players = rows.map(r => {
    // CSV columns win; roster is fallback
    const re = roster[r.player] || { number: "?", pos: "?", group: "UNK" };
    return {
      name:   r.player,
      number: (r.number && r.number !== "") ? r.number : re.number,
      pos:    (r.pos    && r.pos    !== "") ? r.pos    : re.pos,
      group:  (r.group  && r.group  !== "") ? r.group  : re.group,
      aset:   parseFloat(r.aset_score  || 0),
      peak:   parseFloat(r.peak_score  || 0),
      sp:     parseFloat(r.set_score   || 0),
      total:  parseFloat(r.total_score || 0),
      goals:         parseInt(r.goals           || 0, 10),
      shots:         parseInt(r.shots           || 0, 10),
      sot:           parseInt(r.shots_on_target || 0, 10),
      interceptions: parseInt(r.interceptions   || 0, 10),
      clearances:    parseInt(r.clearances      || 0, 10),
      duelsWon:      parseInt(r.duels_won       || 0, 10),
      passes:        parseInt(r.passes          || 0, 10),
      passAcc:       parseFloat(r.pass_accuracy_pct || 0),
      dribbles:      parseInt(r.dribbles        || 0, 10),
      tackles:       parseInt(r.sliding_tackles || 0, 10),
    };
  });

  return { opponent, date, result, players, filename, isSeason: filename.toLowerCase().includes("season") };
}

// ═══════════════════════════════════════════════════════════════════════════
// SEASON AGGREGATE
// ═══════════════════════════════════════════════════════════════════════════
function buildSeasonRoster(matches) {
  // Season CSVs are pre-aggregated — return them directly without re-summing
  const seasonFile = matches.find(m => m.isSeason);
  if (seasonFile) return seasonFile.players;

  // Match-level CSVs — aggregate normally
  const map = {};
  matches.forEach(m => {
    m.players.forEach(p => {
      if (!map[p.name]) {
        map[p.name] = { ...p, matchCount: 0, aset: 0, peak: 0, sp: 0, total: 0,
          goals: 0, shots: 0, sot: 0, interceptions: 0, clearances: 0,
          duelsWon: 0, passes: 0, dribbles: 0, tackles: 0, passAccSum: 0 };
      }
      const e = map[p.name];
      e.matchCount++;
      e.aset += p.aset; e.peak += p.peak; e.sp += p.sp; e.total += p.total;
      e.goals += p.goals; e.shots += p.shots; e.sot += p.sot;
      e.interceptions += p.interceptions; e.clearances += p.clearances;
      e.duelsWon += p.duelsWon; e.passes += p.passes;
      e.dribbles += p.dribbles; e.tackles += p.tackles;
      e.passAccSum += p.passAcc;
    });
  });
  return Object.values(map).map(p => ({
    ...p, passAcc: p.matchCount > 0 ? p.passAccSum / p.matchCount : 0,
  }));
}

// ═══════════════════════════════════════════════════════════════════════════
// SHARED ROW STYLES
// ═══════════════════════════════════════════════════════════════════════════
function JerseyBubble({ number }) {
  return (
    <div style={{
      width: 34, height: 34, borderRadius: "50%",
      background: `linear-gradient(145deg, ${C.maroon}, ${C.maroonDeep})`,
      display: "flex", alignItems: "center", justifyContent: "center",
      fontFamily: "Oswald, sans-serif", fontSize: 13, fontWeight: 700, color: C.gold,
      border: `1.5px solid ${C.goldMetal}55`, flexShrink: 0,
    }}>{number}</div>
  );
}

function ScoreBar({ aset, peak, sp, maxTotal }) {
  return (
    <div style={{ flex: 1, display: "flex", height: 5, borderRadius: 3, overflow: "hidden", background: "#2a2420" }}>
      <div style={{ width: `${(Math.max(0,aset)/maxTotal)*100}%`, background: `linear-gradient(90deg,${C.maroon},#a03040)`, transition: "width 0.5s" }} />
      <div style={{ width: `${(Math.max(0,peak)/maxTotal)*100}%`, background: `linear-gradient(90deg,${C.goldMetal},${C.gold})`, transition: "width 0.5s" }} />
      <div style={{ width: `${(Math.max(0,sp)/maxTotal)*100}%`, background: `linear-gradient(90deg,${C.grayMid},${C.gray})`, transition: "width 0.5s" }} />
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// PLAYER ROW (match view)
// ═══════════════════════════════════════════════════════════════════════════
function PlayerRow({ player, rank, maxTotal, selected, onClick }) {
  const { aset, peak, sp, total } = player;
  const hasData = total > 0;
  return (
    <div onClick={hasData ? onClick : undefined} style={{
      display: "grid", gridTemplateColumns: "32px 38px 1fr 120px 52px 52px 64px",
      alignItems: "center", gap: 6, padding: "11px 20px",
      background: selected ? C.card2 : "transparent",
      borderLeft: selected ? `3px solid ${C.gold}` : "3px solid transparent",
      cursor: hasData ? "pointer" : "default",
      borderBottom: "1px solid #1f1a16", transition: "background 0.15s",
      opacity: hasData ? 1 : 0.4,
    }}>
      <span style={{ fontFamily: "Oswald, sans-serif", fontSize: 13, color: C.muted, textAlign: "center" }}>{rank}</span>
      <JerseyBubble number={player.number} />
      <div>
        <div style={{ fontFamily: "Oswald, sans-serif", fontSize: 14, fontWeight: 600, color: C.text, letterSpacing: 0.4 }}>{player.name}</div>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 3 }}>
          <span style={{ fontSize: 9, color: C.muted, fontWeight: 700, letterSpacing: 1, width: 28 }}>{player.pos}</span>
          <ScoreBar aset={aset} peak={peak} sp={sp} maxTotal={maxTotal} />
        </div>
      </div>
      <div style={{ display: "flex", gap: 2 }}>
        {[["ASET",aset,catC.ASET],["PEAK",peak,catC.PEAK],["SP",sp,catC["SET PIECE"]]].map(([k,v,cc]) => (
          <span key={k} style={{ fontSize: 12, color: cc.label, fontFamily: "Oswald, sans-serif", width: 38, textAlign: "center" }}>
            {v > 0 ? v.toFixed(1) : "\u2013"}
          </span>
        ))}
      </div>
      <div style={{ textAlign: "center" }}>
        <span style={{ fontSize: 11, color: C.gold, fontFamily: "Oswald, sans-serif" }}>
          {(aset+peak+sp) > 0 ? (aset+peak+sp).toFixed(1) : "\u2013"}
        </span>
      </div>
      <div style={{ textAlign: "center" }}>
        <span style={{ fontSize: 11, color: C.muted, fontFamily: "Oswald, sans-serif" }}>
          {total > 0 ? total.toFixed(1) : "\u2013"}
        </span>
      </div>
      <div style={{ textAlign: "right" }}>
        <span style={{
          fontFamily: "Oswald, sans-serif", fontSize: 22, fontWeight: 700,
          color: total >= 15 ? C.goldLight : total >= 8 ? C.gold : total > 0 ? C.muted : "#3a3530",
          textShadow: total >= 15 ? `0 0 16px ${C.goldMetal}44` : "none",
        }}>{total > 0 ? total.toFixed(1) : "0.0"}</span>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// SEASON ROW — extra MP column
// ═══════════════════════════════════════════════════════════════════════════
function SeasonRow({ player, rank, maxTotal, selected, onClick }) {
  const { aset, peak, sp, total, matchCount } = player;
  const hasData = total > 0;
  return (
    <div onClick={hasData ? onClick : undefined} style={{
      display: "grid", gridTemplateColumns: "32px 38px 1fr 120px 40px 52px 52px 64px",
      alignItems: "center", gap: 6, padding: "11px 20px",
      background: selected ? C.card2 : "transparent",
      borderLeft: selected ? `3px solid ${C.gold}` : "3px solid transparent",
      cursor: hasData ? "pointer" : "default",
      borderBottom: "1px solid #1f1a16", transition: "background 0.15s",
      opacity: hasData ? 1 : 0.4,
    }}>
      <span style={{ fontFamily: "Oswald, sans-serif", fontSize: 13, color: C.muted, textAlign: "center" }}>{rank}</span>
      <JerseyBubble number={player.number} />
      <div>
        <div style={{ fontFamily: "Oswald, sans-serif", fontSize: 14, fontWeight: 600, color: C.text, letterSpacing: 0.4 }}>{player.name}</div>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 3 }}>
          <span style={{ fontSize: 9, color: C.muted, fontWeight: 700, letterSpacing: 1, width: 28 }}>{player.pos}</span>
          <ScoreBar aset={aset} peak={peak} sp={sp} maxTotal={maxTotal} />
        </div>
      </div>
      <div style={{ display: "flex", gap: 2 }}>
        {[["ASET",aset,catC.ASET],["PEAK",peak,catC.PEAK],["SP",sp,catC["SET PIECE"]]].map(([k,v,cc]) => (
          <span key={k} style={{ fontSize: 12, color: cc.label, fontFamily: "Oswald, sans-serif", width: 38, textAlign: "center" }}>
            {v > 0 ? v.toFixed(1) : "\u2013"}
          </span>
        ))}
      </div>
      <div style={{ textAlign: "center" }}>
        <span style={{ fontFamily: "Oswald, sans-serif", fontSize: 11, background: `${C.maroon}55`, color: C.muted, padding: "2px 6px", borderRadius: 3 }}>
          {matchCount}G
        </span>
      </div>
      <div style={{ textAlign: "center" }}>
        <span style={{ fontSize: 11, color: C.gold, fontFamily: "Oswald, sans-serif" }}>
          {(aset+peak+sp) > 0 ? (aset+peak+sp).toFixed(1) : "\u2013"}
        </span>
      </div>
      <div style={{ textAlign: "center" }}>
        <span style={{ fontSize: 11, color: C.muted, fontFamily: "Oswald, sans-serif" }}>
          {total > 0 ? total.toFixed(1) : "\u2013"}
        </span>
      </div>
      <div style={{ textAlign: "right" }}>
        <span style={{
          fontFamily: "Oswald, sans-serif", fontSize: 22, fontWeight: 700,
          color: total >= 30 ? C.goldLight : total >= 15 ? C.gold : total > 0 ? C.muted : "#3a3530",
          textShadow: total >= 30 ? `0 0 16px ${C.goldMetal}44` : "none",
        }}>{total > 0 ? total.toFixed(1) : "0.0"}</span>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// PLAYER DETAIL PANEL
// ═══════════════════════════════════════════════════════════════════════════
function PlayerDetail({ player }) {
  const stats = [
    { label: "Goals",         val: player.goals },
    { label: "Shots",         val: player.shots },
    { label: "On Target",     val: player.sot },
    { label: "Interceptions", val: player.interceptions },
    { label: "Clearances",    val: player.clearances },
    { label: "Duels Won",     val: player.duelsWon },
    { label: "Passes",        val: player.passes },
    { label: "Pass Acc %",    val: player.passAcc.toFixed(1) },
    { label: "Dribbles",      val: player.dribbles },
    { label: "Tackles",       val: player.tackles },
  ];
  return (
    <div style={{ background: C.card, border: `1px solid ${C.maroonDark}`, borderRadius: 10, padding: 20, animation: "fadeIn 0.25s ease" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
        <div style={{ display: "flex", gap: 14, alignItems: "center" }}>
          <div style={{
            width: 50, height: 50, borderRadius: "50%",
            background: `linear-gradient(145deg, ${C.maroon}, ${C.maroonDeep})`,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontFamily: "Oswald, sans-serif", fontSize: 20, fontWeight: 700, color: C.gold,
            border: `2px solid ${C.goldMetal}`,
          }}>{player.number}</div>
          <div>
            <div style={{ fontFamily: "Oswald, sans-serif", fontSize: 22, fontWeight: 700, color: C.text, letterSpacing: 0.8 }}>{player.name}</div>
            <div style={{ fontSize: 11, color: C.muted, fontWeight: 600, letterSpacing: 2 }}>{player.pos}</div>
          </div>
        </div>
        <div style={{ textAlign: "right" }}>
          <div style={{ fontFamily: "Oswald, sans-serif", fontSize: 38, fontWeight: 700, color: C.gold, lineHeight: 1 }}>{player.total.toFixed(1)}</div>
          <div style={{ fontSize: 9, color: C.muted, letterSpacing: 2, fontWeight: 700, marginTop: 3 }}>TOTAL COUGs</div>
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8, marginBottom: 18 }}>
        {[
          { label: "ASET",    val: player.aset, c: catC.ASET },
          { label: "PEAK",    val: player.peak, c: catC.PEAK },
          { label: "SET PCE", val: player.sp,   c: catC["SET PIECE"] },
        ].map(x => (
          <div key={x.label} style={{ background: x.c.bg, border: `1px solid ${x.c.border}`, borderRadius: 6, padding: "8px 10px", textAlign: "center" }}>
            <div style={{ fontSize: 8, color: x.c.text, letterSpacing: 1.5, fontWeight: 700, marginBottom: 3 }}>{x.label}</div>
            <div style={{ fontFamily: "Oswald, sans-serif", fontSize: 22, fontWeight: 700, color: x.c.text }}>
              {x.val > 0 ? x.val.toFixed(1) : "\u2013"}
            </div>
          </div>
        ))}
      </div>
      <div style={{ fontSize: 9, color: C.muted, letterSpacing: 2, fontWeight: 700, marginBottom: 8 }}>WYSCOUT STATS</div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 3 }}>
        {stats.map(s => (
          <div key={s.label} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "5px 8px", borderRadius: 4, background: "rgba(255,255,255,0.03)" }}>
            <span style={{ fontSize: 10, color: C.muted }}>{s.label}</span>
            <span style={{ fontFamily: "Oswald, sans-serif", fontSize: 13, fontWeight: 600, color: C.text }}>{s.val}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// LOCALSTORAGE CACHE HELPERS
// ═══════════════════════════════════════════════════════════════════════════
const CACHE_KEYS = {
  roster:  "coug_table_roster",
  matches: "coug_table_matches",
};

function cacheGet(key) {
  try { return JSON.parse(localStorage.getItem(key)); } catch { return null; }
}

function cacheSet(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) {
    console.warn("localStorage write failed:", e);
  }
}

// ═══════════════════════════════════════════════════════════════════════════
// MAIN DASHBOARD
// ═══════════════════════════════════════════════════════════════════════════
export default function COUGDashboard() {
  const [roster, setRoster]             = useState(() => cacheGet(CACHE_KEYS.roster) || {});
  const [rosterLoaded, setRosterLoaded] = useState(() => Object.keys(cacheGet(CACHE_KEYS.roster) || {}).length > 0);
  const [matches, setMatches]           = useState(() => cacheGet(CACHE_KEYS.matches) || []);
  const [activeIdx, setActiveIdx]       = useState(0);
  const [selectedName, setSelectedName] = useState(null);
  const [sortBy, setSortBy]             = useState("total");
  const [filterPos, setFilterPos]       = useState("ALL");
  const [loadError, setLoadError]       = useState(null);
  const [viewMode, setViewMode]         = useState("match");
  const matchFileRef  = useRef(null);
  const rosterFileRef = useRef(null);

  // Persist roster to cache whenever it changes
  useEffect(() => {
    if (Object.keys(roster).length > 0) cacheSet(CACHE_KEYS.roster, roster);
  }, [roster]);

  // Persist matches to cache whenever they change
  useEffect(() => {
    if (matches.length > 0) cacheSet(CACHE_KEYS.matches, matches);
  }, [matches]);

  // Derive position group buttons from loaded roster — no hardcoding
  const posGroups = useMemo(() => {
    const groups = new Set(Object.values(roster).map(r => r.group).filter(g => g && g !== "UNK"));
    const order = ["GK", "DEF", "MID", "ATT"];
    return ["ALL", ...order.filter(g => groups.has(g)), ...[...groups].filter(g => !order.includes(g))];
  }, [roster]);

  function handleRosterFile(file) {
    setLoadError(null);
    const reader = new FileReader();
    reader.onload = e => {
      const parsed = parseRosterCSV(e.target.result);
      if (!Object.keys(parsed).length) {
        setLoadError("Could not parse roster — check headers: name, number, pos, group");
        return;
      }
      setRoster(parsed);
      setRosterLoaded(true);
      // Backfill metadata on already-loaded matches
      setMatches(prev => prev.map(m => ({
        ...m,
        players: m.players.map(p => {
          const r = parsed[p.name] || {};
          return {
            ...p,
            number: (p.number && p.number !== "?") ? p.number : (r.number || "?"),
            pos:    (p.pos    && p.pos    !== "?") ? p.pos    : (r.pos    || "?"),
            group:  (p.group  && p.group  !== "UNK") ? p.group : (r.group || "UNK"),
          };
        }),
      })));
    };
    reader.readAsText(file);
  }

  function handleMatchFiles(files) {
    setLoadError(null);
    Array.from(files).forEach(file => {
      const reader = new FileReader();
      reader.onload = e => {
        const match = parseMatchCSV(e.target.result, file.name, roster);
        if (!match) { setLoadError(`Could not parse ${file.name}`); return; }
        setMatches(prev => {
          // Same filename = overwrite; new filename = append
          const idx = prev.findIndex(m => m.filename === file.name);
          if (idx >= 0) { const next = [...prev]; next[idx] = match; return next; }
          const next = [...prev, match];
          setActiveIdx(next.length - 1);
          return next;
        });
      };
      reader.readAsText(file);
    });
  }

  function onDrop(e) {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files);
    files.filter(f => f.name.toLowerCase().includes("roster")).forEach(handleRosterFile);
    const matchFiles = files.filter(f => !f.name.toLowerCase().includes("roster"));
    if (matchFiles.length) handleMatchFiles(matchFiles);
  }

  const match = matches[activeIdx] || null;
  const seasonRoster = useMemo(() => buildSeasonRoster(matches), [matches]);
  const seasonTotals = useMemo(() => seasonRoster.reduce((a,p) => ({ aset: a.aset+p.aset, peak: a.peak+p.peak, sp: a.sp+p.sp }), { aset:0, peak:0, sp:0 }), [seasonRoster]);

  const players = useMemo(() => {
    const source = viewMode === "season" ? seasonRoster : (match ? match.players : []);
    let list = [...source];
    if (filterPos !== "ALL") list = list.filter(p => p.group === filterPos);
    list.sort((a,b) => sortBy === "ASET" ? b.aset-a.aset : sortBy === "PEAK" ? b.peak-a.peak : sortBy === "SET PIECE" ? b.sp-a.sp : b.total-a.total);
    return list;
  }, [match, seasonRoster, sortBy, filterPos, viewMode]);

  const maxTotal = useMemo(() => Math.max(...players.map(p => p.total), 1), [players]);

  const teamTotals = useMemo(() => {
    if (viewMode === "season") return seasonTotals;
    if (!match) return { aset:0, peak:0, sp:0 };
    return match.players.reduce((a,p) => ({ aset: a.aset+p.aset, peak: a.peak+p.peak, sp: a.sp+p.sp }), { aset:0, peak:0, sp:0 });
  }, [match, seasonTotals, viewMode]);

  const selectedPlayer = useMemo(() => players.find(p => p.name === selectedName), [players, selectedName]);
  const hasData = matches.length > 0;
  const showTable = viewMode === "season" ? hasData : !!match;

  const filterBtn = (active) => ({
    padding: "4px 12px", borderRadius: 4,
    border: `1px solid ${active ? C.goldMetal : "#2a2420"}`,
    background: active ? `${C.goldMetal}18` : "transparent",
    color: active ? C.gold : C.muted,
    fontFamily: "Oswald, sans-serif", fontSize: 11, fontWeight: 600,
    letterSpacing: 1.5, cursor: "pointer",
  });

  return (
    <div onDragOver={e => e.preventDefault()} onDrop={onDrop}
      style={{ minHeight: "100vh", background: C.bg, color: C.text, fontFamily: "'Source Sans 3', sans-serif" }}>
      <div style={{ maxWidth: 1200, margin: "0 auto" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Oswald:wght@400;500;600;700&family=Source+Sans+3:wght@300;400;600;700&display=swap');
        @keyframes fadeIn { from { opacity:0; transform:translateY(6px) } to { opacity:1; transform:translateY(0) } }
        ::-webkit-scrollbar { width:4px } ::-webkit-scrollbar-track { background:transparent } ::-webkit-scrollbar-thumb { background:${C.maroon}; border-radius:2px }
        * { box-sizing:border-box; margin:0 }
      `}</style>

      {/* ── HEADER ── */}
      <div style={{ background: `linear-gradient(135deg, ${C.maroonDeep}, ${C.maroonDark} 60%, ${C.bg})`, borderBottom: `2px solid ${C.goldMetal}22`, padding: "22px 28px 18px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <div style={{ fontFamily: "Oswald, sans-serif", fontSize: 11, fontWeight: 600, letterSpacing: 4, color: C.goldMetal, marginBottom: 4 }}>
              COLLEGE OF CHARLESTON · MEN'S SOCCER
            </div>
            <div style={{ fontFamily: "Oswald, sans-serif", fontSize: 42, fontWeight: 700, letterSpacing: 3, lineHeight: 1, background: `linear-gradient(90deg, ${C.text}, ${C.gold})`, WebkitBackgroundClip: "text", WebkitTextFillColor: "transparent" }}>
              COUGS TABLE
            </div>
            <div style={{ fontSize: 11, color: C.muted, marginTop: 4, letterSpacing: 1.5 }}>Character · Outcompete · Unity · Grit · Solve</div>
          </div>

          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 10 }}>
            {viewMode === "season" && hasData ? (
              <div style={{ textAlign: "right" }}>
                <div style={{ fontFamily: "Oswald, sans-serif", fontSize: 22, fontWeight: 700, color: C.gold }}>SEASON · {matches.length} {matches.length === 1 ? "MATCH" : "MATCHES"}</div>
                <div style={{ fontSize: 11, color: C.muted, marginTop: 2 }}>{matches.map(m => m.opponent).join(" · ")}</div>
              </div>
            ) : match ? (
              <div style={{ textAlign: "right" }}>
                <div style={{ fontFamily: "Oswald, sans-serif", fontSize: 28, fontWeight: 700, color: "#5cb85c" }}>{match.result}</div>
                <div style={{ fontSize: 13, color: C.text, fontWeight: 600 }}>vs {match.opponent}</div>
                <div style={{ fontSize: 11, color: C.muted, marginTop: 2 }}>{match.date} · CAA Conference</div>
              </div>
            ) : (
              <div style={{ fontSize: 12, color: C.muted }}>No match loaded</div>
            )}

            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              {hasData && (
                <div style={{ display: "flex", borderRadius: 6, overflow: "hidden", border: `1px solid ${C.goldMetal}55` }}>
                  {[["MATCH","match"],["SEASON","season"]].map(([label,mode]) => (
                    <button key={mode} onClick={() => { setViewMode(mode); setSelectedName(null); }} style={{
                      padding: "6px 14px", border: "none",
                      background: viewMode === mode ? C.maroon : "transparent",
                      color: viewMode === mode ? C.gold : C.muted,
                      fontFamily: "Oswald, sans-serif", fontSize: 11, fontWeight: 600,
                      letterSpacing: 1.5, cursor: "pointer", transition: "all 0.15s",
                    }}>{label}</button>
                  ))}
                </div>
              )}

              {/* Clear button */}
              {hasData && (
                <button onClick={() => {
                  if (!window.confirm("Clear all cached matches and roster?")) return;
                  localStorage.removeItem(CACHE_KEYS.roster);
                  localStorage.removeItem(CACHE_KEYS.matches);
                  setMatches([]); setRoster({}); setRosterLoaded(false); setSelectedName(null);
                }} style={{
                  padding: "8px 12px", borderRadius: 6,
                  border: "1px solid #3a3530", background: "transparent",
                  color: C.muted, fontFamily: "Oswald, sans-serif",
                  fontSize: 11, fontWeight: 600, letterSpacing: 1.5, cursor: "pointer",
                }}>✕ CLEAR</button>
              )}

              {/* Roster button */}
              <button onClick={() => rosterFileRef.current?.click()} style={{
                padding: "8px 14px", borderRadius: 6,
                border: `1px solid ${rosterLoaded ? C.goldMetal : "#3a3530"}`,
                background: rosterLoaded ? `${C.goldMetal}18` : "transparent",
                color: rosterLoaded ? C.gold : C.muted,
                fontFamily: "Oswald, sans-serif", fontSize: 11, fontWeight: 600,
                letterSpacing: 1.5, cursor: "pointer",
              }}>
                {rosterLoaded ? "\u2713 ROSTER" : "LOAD ROSTER"}
              </button>
              <input ref={rosterFileRef} type="file" accept=".csv" style={{ display: "none" }}
                onChange={e => e.target.files[0] && handleRosterFile(e.target.files[0])} />

              {/* Match CSV button */}
              <button onClick={() => matchFileRef.current?.click()} style={{
                display: "flex", alignItems: "center", gap: 7,
                padding: "8px 16px", borderRadius: 6,
                border: `1px solid ${C.goldMetal}`, background: `${C.goldMetal}18`,
                color: C.gold, fontFamily: "Oswald, sans-serif", fontSize: 12, fontWeight: 600,
                letterSpacing: 1.5, cursor: "pointer",
              }}
                onMouseOver={e => e.currentTarget.style.background = `${C.goldMetal}35`}
                onMouseOut={e => e.currentTarget.style.background = `${C.goldMetal}18`}
              >
                <span style={{ fontSize: 16, lineHeight: 1 }}>+</span> LOAD MATCH CSV
              </button>
              <input ref={matchFileRef} type="file" accept=".csv" multiple style={{ display: "none" }}
                onChange={e => handleMatchFiles(e.target.files)} />
            </div>
          </div>
        </div>

        {/* Team score pills */}
        {showTable && (
          <div style={{ display: "flex", gap: 12, marginTop: 18 }}>
            {[
              { label: "ASET", sub: "DEFENSE",   val: teamTotals.aset, c: catC.ASET },
              { label: "PEAK", sub: "OFFENSE",   val: teamTotals.peak, c: catC.PEAK },
              { label: "SET PIECE", sub: "RESTARTS", val: teamTotals.sp, c: catC["SET PIECE"] },
            ].map(t => (
              <div key={t.label} style={{ flex: 1, background: t.c.bg, border: `1px solid ${t.c.border}44`, borderRadius: 8, padding: "10px 14px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <div>
                  <div style={{ fontFamily: "Oswald, sans-serif", fontSize: 13, fontWeight: 700, color: t.c.label, letterSpacing: 2 }}>{t.label}</div>
                  <div style={{ fontSize: 8, color: t.c.text, letterSpacing: 1.5, opacity: 0.6, marginTop: 1 }}>{t.sub}</div>
                </div>
                <div style={{ fontFamily: "Oswald, sans-serif", fontSize: 28, fontWeight: 700, color: t.c.text }}>{t.val.toFixed(1)}</div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── MATCH TABS ── */}
      {viewMode === "match" && matches.length > 0 && (
        <div style={{ display: "flex", alignItems: "center", gap: 2, padding: "0 20px", borderBottom: "1px solid #1f1a16", background: "#0c0908", overflowX: "auto" }}>
          {matches.map((m, i) => (
            <button key={m.filename} onClick={() => { setActiveIdx(i); setSelectedName(null); }} style={{
              padding: "10px 16px", border: "none",
              borderBottom: i === activeIdx ? `2px solid ${C.gold}` : "2px solid transparent",
              background: "transparent", color: i === activeIdx ? C.gold : C.muted,
              fontFamily: "Oswald, sans-serif", fontSize: 12, fontWeight: 600,
              letterSpacing: 1.2, cursor: "pointer", whiteSpace: "nowrap", transition: "color 0.15s",
            }}>
              {m.opponent}{m.result !== "\u2013" ? ` · ${m.result}` : ""}
            </button>
          ))}
        </div>
      )}

      {/* ── SEASON BANNER ── */}
      {viewMode === "season" && hasData && (
        <div style={{ padding: "8px 28px", background: `${C.maroon}22`, borderBottom: "1px solid #1f1a16", display: "flex", gap: 6, alignItems: "center" }}>
          <span style={{ fontSize: 9, color: C.muted, letterSpacing: 2, fontWeight: 700 }}>MATCHES INCLUDED:</span>
          {matches.map(m => (
            <span key={m.filename} style={{ fontSize: 10, color: C.gold, fontFamily: "Oswald, sans-serif", background: `${C.maroon}44`, padding: "2px 8px", borderRadius: 3 }}>
              {m.opponent}{m.result !== "\u2013" ? ` ${m.result}` : ""}
            </span>
          ))}
        </div>
      )}

      {/* ── EMPTY STATE ── */}
      {!showTable && (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", minHeight: 400, gap: 16, padding: 40 }}>
          <div style={{ width: 80, height: 80, borderRadius: "50%", border: `2px dashed ${C.maroon}`, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 32, color: C.maroon }}>+</div>
          <div style={{ fontFamily: "Oswald, sans-serif", fontSize: 22, color: C.muted, letterSpacing: 2 }}>NO MATCH LOADED</div>
          <div style={{ fontSize: 13, color: C.muted, textAlign: "center", maxWidth: 440, lineHeight: 1.8 }}>
            {!rosterLoaded && <span>Load <span style={{ color: C.gold, fontWeight: 600 }}>roster.csv</span> first (once per season), then </span>}
            click <span style={{ color: C.gold, fontWeight: 600 }}>+ LOAD MATCH CSV</span> or drag and drop files anywhere.
          </div>
          {loadError && <div style={{ color: "#e85555", fontSize: 12 }}>{loadError}</div>}
        </div>
      )}

      {/* ── CONTROLS + TABLE ── */}
      {showTable && (
        <>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "10px 20px", borderBottom: "1px solid #1f1a16" }}>
            <div style={{ display: "flex", gap: 5 }}>
              {posGroups.map(g => (
                <button key={g} onClick={() => setFilterPos(g)} style={filterBtn(filterPos === g)}>{g}</button>
              ))}
            </div>
            <div style={{ display: "flex", gap: 5, alignItems: "center" }}>
              <span style={{ fontSize: 9, color: C.muted, letterSpacing: 1.5, fontWeight: 600, marginRight: 4 }}>SORT</span>
              {[
                { key: "total",     label: "TOTAL" },
                { key: "ASET",      label: "ASET"  },
                { key: "PEAK",      label: "PEAK"  },
                { key: "SET PIECE", label: "SP"    },
              ].map(s => (
                <button key={s.key} onClick={() => setSortBy(s.key)} style={filterBtn(sortBy === s.key)}>
                  {s.label}
                </button>
              ))}
            </div>
          </div>

          {/* Column headers */}
          <div style={{
            display: "grid",
            gridTemplateColumns: viewMode === "season" ? "32px 38px 1fr 120px 40px 52px 52px 64px" : "32px 38px 1fr 120px 52px 52px 64px",
            gap: 6, padding: "7px 20px", borderBottom: "1px solid #1f1a16",
          }}>
            <span style={{ fontSize: 8, color: C.muted, letterSpacing: 1, textAlign: "center" }}>#</span>
            <span />
            <span style={{ fontSize: 8, color: C.muted, letterSpacing: 1.5 }}>PLAYER</span>
            <div style={{ display: "flex", gap: 2 }}>
              <span style={{ fontSize: 8, color: catC.ASET.label,         width: 38, textAlign: "center", letterSpacing: 0.5 }}>ASET</span>
              <span style={{ fontSize: 8, color: catC.PEAK.label,         width: 38, textAlign: "center", letterSpacing: 0.5 }}>PEAK</span>
              <span style={{ fontSize: 8, color: catC["SET PIECE"].label, width: 38, textAlign: "center", letterSpacing: 0.5 }}>SP</span>
            </div>
            {viewMode === "season" && <span style={{ fontSize: 8, color: C.muted, textAlign: "center", letterSpacing: 0.5 }}>MP</span>}
            <span style={{ fontSize: 8, color: C.muted, textAlign: "center", letterSpacing: 0.5 }}>INDIV</span>
            <span style={{ fontSize: 8, color: C.muted, textAlign: "center", letterSpacing: 0.5 }}>TOTAL</span>
            <span style={{ fontSize: 8, color: C.gold,  textAlign: "right",  letterSpacing: 1 }}>COUGs</span>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: selectedPlayer ? "1fr 360px" : "1fr", transition: "all 0.3s" }}>
            <div>
              {players.map((p, i) => viewMode === "season" ? (
                <SeasonRow key={p.name} player={p} rank={i+1} maxTotal={maxTotal}
                  selected={p.name === selectedName}
                  onClick={() => setSelectedName(p.name === selectedName ? null : p.name)} />
              ) : (
                <PlayerRow key={p.name} player={p} rank={i+1} maxTotal={maxTotal}
                  selected={p.name === selectedName}
                  onClick={() => setSelectedName(p.name === selectedName ? null : p.name)} />
              ))}
            </div>
            {selectedPlayer && (
              <div style={{ padding: "14px 14px 14px 0", borderLeft: "1px solid #1f1a16" }}>
                <PlayerDetail player={selectedPlayer} />
              </div>
            )}
          </div>
        </>
      )}

      {/* ── FOOTER ── */}
      <div style={{ padding: "14px 28px", borderTop: "1px solid #1f1a16", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div style={{ display: "flex", gap: 14 }}>
          {[["ASET (Defense)", C.maroon], ["PEAK (Offense)", C.goldMetal], ["Set Piece", C.grayMid]].map(([l, c]) => (
            <div key={l} style={{ display: "flex", alignItems: "center", gap: 5 }}>
              <div style={{ width: 8, height: 8, borderRadius: 2, background: c }} />
              <span style={{ fontSize: 9, color: C.muted }}>{l}</span>
            </div>
          ))}
        </div>
        <div style={{ fontSize: 9, color: C.muted, letterSpacing: 1.5 }}>
          DATA SOURCE: WYSCOUT + SPIIDEO · COUG TABLE v1
        </div>
      </div>
      </div>
    </div>
  );
}
