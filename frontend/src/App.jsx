import { useState, useEffect, useMemo } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, Cell,
  CartesianGrid, Tooltip, Legend, ResponsiveContainer, Area, AreaChart
} from 'recharts';
import CougTable from './CougTable.jsx';

const slideDownStyle = `
  @keyframes slideDown {
    from { opacity: 0; transform: translateY(-10px); }
    to { opacity: 1; transform: translateY(0); }
  }
`;

const colors = {
  garnet:     '#800000',
  gold:       '#CFB53B',
  goldLight:  '#FFF8DC',
  goldText:   '#8B7500',
  pink:       '#FFE4E6',
  pinkText:   '#991B1B',
  pending:    '#F3F4F6',
  pendingText:'#6B7280',
  background: '#f3f4f6',
  cardBg:     '#ffffff',
  success:    '#166534',
};

// ── Pending placeholder ───────────────────────────────────────────────────────
function PendingCard({ title, message }) {
  return (
    <div style={{
      backgroundColor: colors.cardBg,
      padding: '1.5rem',
      borderRadius: '12px',
      boxShadow: '0 2px 4px rgba(0,0,0,0.05)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '200px',
      gap: '0.75rem',
    }}>
      <h3 style={{ color: '#374151', margin: 0 }}>{title}</h3>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
        backgroundColor: colors.pending,
        borderRadius: '8px',
        padding: '0.75rem 1.25rem',
      }}>
        <span style={{ fontSize: 18 }}>⏳</span>
        <span style={{ fontSize: '13px', color: colors.pendingText }}>{message}</span>
      </div>
    </div>
  );
}

// ── Tab Nav ───────────────────────────────────────────────────────────────────
function TabNav({ active, onChange }) {
  const tabs = [
    { id: 'analytics', label: 'Team Analytics' },
    { id: 'coug',      label: 'COUG Table' },
    { id: 'coug2',     label: 'COUG Table v2' },
    { id: 'staff',     label: 'Staff' },
  ];
  return (
    <div style={{
      display: 'flex', gap: 4,
      backgroundColor: colors.cardBg,
      padding: '0 2rem',
      borderBottom: '2px solid #e5e7eb',
      marginBottom: '0',
    }}>
      {tabs.map(t => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          style={{
            padding: '14px 24px',
            border: 'none',
            borderBottom: active === t.id ? `3px solid ${colors.garnet}` : '3px solid transparent',
            background: 'transparent',
            color: active === t.id ? colors.garnet : '#6b7280',
            fontWeight: active === t.id ? 700 : 500,
            fontSize: 14,
            cursor: 'pointer',
            letterSpacing: 0.5,
            transition: 'all 0.15s',
            marginBottom: -2,
          }}
        >
          {t.label}
          {t.id === 'coug2' && (
            <span style={{
              marginLeft: 6, fontSize: 9, fontWeight: 700,
              background: colors.garnet, color: 'white',
              padding: '2px 5px', borderRadius: 3, letterSpacing: 1,
            }}>NEW</span>
          )}
        </button>
      ))}
    </div>
  );
}

// ── Staff / Private Surface ──────────────────────────────────────────────────
function StaffGate({ children }) {
  const passcode = import.meta.env.VITE_STAFF_PASSCODE || 'cofc-staff';
  const [entered, setEntered] = useState(() => window.localStorage.getItem('cofc_staff_access') === 'true');
  const [value, setValue] = useState('');
  const [error, setError] = useState('');

  function submit(e) {
    e.preventDefault();
    if (value === passcode) {
      window.localStorage.setItem('cofc_staff_access', 'true');
      setEntered(true);
      setError('');
      return;
    }
    setError('Incorrect staff passcode');
  }

  if (entered) return children;

  return (
    <div style={{ maxWidth: 460, margin: '4rem auto', background: '#fff', padding: '2rem', borderRadius: 8, boxShadow: '0 2px 10px rgba(0,0,0,0.08)' }}>
      <h2 style={{ marginTop: 0, color: colors.garnet }}>Staff Access</h2>
      <p style={{ color: '#4b5563', lineHeight: 1.5 }}>
        Private scouting, player development, prediction simulator, and recruiting tools.
      </p>
      <form onSubmit={submit} style={{ display: 'grid', gap: '0.75rem' }}>
        <label style={{ fontSize: 13, fontWeight: 700, color: '#374151' }}>Passcode</label>
        <input
          type="password"
          value={value}
          onChange={e => setValue(e.target.value)}
          style={{ padding: '0.75rem', border: '1px solid #d1d5db', borderRadius: 6, fontSize: 15 }}
        />
        {error && <div style={{ color: '#991b1b', fontSize: 13 }}>{error}</div>}
        <button type="submit" style={{ padding: '0.8rem 1rem', border: 'none', borderRadius: 6, background: colors.garnet, color: '#fff', fontWeight: 800, cursor: 'pointer' }}>
          Enter Staff Area
        </button>
      </form>
      <p style={{ marginTop: '1rem', color: '#6b7280', fontSize: 12, lineHeight: 1.5 }}>
        Local scaffold only. Production deployment should also protect staff API routes server-side.
      </p>
    </div>
  );
}

function StaffDashboard() {
  const [section, setSection] = useState('simulator');
  const sections = [
    ['simulator', 'Prediction Simulator'],
    ['scouting', 'Scouting'],
    ['development', 'Player Development'],
    ['recruiting', 'Recruiting'],
  ];

  return (
    <StaffGate>
      <div style={{ maxWidth: 1180, margin: '0 auto', padding: '2rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: '1rem', alignItems: 'flex-end', marginBottom: '1.25rem' }}>
          <div>
            <h1 style={{ color: colors.garnet, margin: 0 }}>Staff Dashboard</h1>
            <p style={{ color: '#4b5563', margin: '0.4rem 0 0' }}>Private scouting, simulation, development, and recruiting workspace.</p>
          </div>
          <button
            type="button"
            onClick={() => { window.localStorage.removeItem('cofc_staff_access'); window.location.reload(); }}
            style={{ border: '1px solid #d1d5db', background: '#fff', borderRadius: 6, padding: '0.55rem 0.8rem', cursor: 'pointer', color: '#374151' }}
          >
            Lock
          </button>
        </div>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: '1.5rem' }}>
          {sections.map(([id, label]) => (
            <button
              key={id}
              type="button"
              onClick={() => setSection(id)}
              style={{
                border: section === id ? `2px solid ${colors.garnet}` : '1px solid #d1d5db',
                background: section === id ? '#fff7ed' : '#fff',
                color: section === id ? colors.garnet : '#374151',
                borderRadius: 6,
                padding: '0.7rem 0.95rem',
                fontWeight: 800,
                cursor: 'pointer',
              }}
            >
              {label}
            </button>
          ))}
        </div>

        {section === 'simulator' && <PredictionSimulator />}
        {section === 'scouting' && <StaffPlaceholder title="Scouting" body="Opponent reports, readiness status, match shells, and pre-match prep will surface here from pipeline/scouting outputs." />}
        {section === 'development' && <StaffPlaceholder title="Player Development" body="Private player trends, COUG score explainers, and development targets will live here." />}
        {section === 'recruiting' && <StaffPlaceholder title="Recruiting" body="Recruiting readiness, profile imports, similarity scores, comps, and shortlists will live here once recruit profiles exist." />}
      </div>
    </StaffGate>
  );
}

function StaffPlaceholder({ title, body }) {
  return (
    <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8, padding: '1.5rem', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
      <h2 style={{ marginTop: 0, color: colors.garnet }}>{title}</h2>
      <p style={{ marginBottom: 0, color: '#4b5563', lineHeight: 1.6 }}>{body}</p>
    </div>
  );
}

function PredictionSimulator() {
  const [inputs, setInputs] = useState({
    cofcXg: 1.45,
    oppXg: 1.15,
    possession: 52,
    shotEdge: 1,
    pressEdge: 0,
    setPieceEdge: 0,
    home: 0.15,
  });

  const model = useMemo(() => scenarioModel(inputs), [inputs]);
  const probabilityData = [
    { name: 'Win', value: Math.round(model.win * 100) },
    { name: 'Draw', value: Math.round(model.draw * 100) },
    { name: 'Loss', value: Math.round(model.loss * 100) },
  ];

  function update(key, value) {
    setInputs(current => ({ ...current, [key]: Number(value) }));
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(280px, 0.9fr) minmax(320px, 1.1fr)', gap: '1.25rem' }}>
      <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8, padding: '1.25rem' }}>
        <h2 style={{ color: colors.garnet, marginTop: 0 }}>Scenario Dials</h2>
        <Dial label="CofC xG" value={inputs.cofcXg} min={0.2} max={3.5} step={0.05} onChange={v => update('cofcXg', v)} />
        <Dial label="Opponent xG" value={inputs.oppXg} min={0.2} max={3.5} step={0.05} onChange={v => update('oppXg', v)} />
        <Dial label="Possession %" value={inputs.possession} min={35} max={65} step={1} onChange={v => update('possession', v)} />
        <Dial label="Shot edge" value={inputs.shotEdge} min={-8} max={8} step={1} onChange={v => update('shotEdge', v)} />
        <Dial label="Press/recovery edge" value={inputs.pressEdge} min={-5} max={5} step={1} onChange={v => update('pressEdge', v)} />
        <Dial label="Set-piece edge" value={inputs.setPieceEdge} min={-3} max={3} step={1} onChange={v => update('setPieceEdge', v)} />
        <Dial label="Home advantage" value={inputs.home} min={-0.15} max={0.25} step={0.05} onChange={v => update('home', v)} />
      </div>

      <div style={{ display: 'grid', gap: '1rem' }}>
        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8, padding: '1.25rem' }}>
          <h2 style={{ color: colors.garnet, marginTop: 0 }}>Projected Outcome</h2>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.75rem', marginBottom: '1rem' }}>
            <ProbabilityTile label="Win" value={model.win} tone="good" />
            <ProbabilityTile label="Draw" value={model.draw} />
            <ProbabilityTile label="Loss" value={model.loss} tone="bad" />
          </div>
          <div style={{ height: 220 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={probabilityData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#eee" />
                <XAxis dataKey="name" />
                <YAxis domain={[0, 100]} tickFormatter={v => `${v}%`} />
                <Tooltip formatter={v => `${v}%`} />
                <Bar dataKey="value" radius={[4, 4, 0, 0]}>
                  {probabilityData.map((entry) => (
                    <Cell key={entry.name} fill={entry.name === 'Win' ? colors.success : entry.name === 'Loss' ? colors.garnet : colors.gold} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div style={{ background: '#fff', border: '1px solid #e5e7eb', borderRadius: 8, padding: '1.25rem' }}>
          <h3 style={{ color: '#374151', marginTop: 0 }}>Most Likely Scorelines</h3>
          <div style={{ display: 'grid', gap: 8 }}>
            {model.scorelines.map(row => (
              <div key={row.score} style={{ display: 'grid', gridTemplateColumns: '70px 1fr 54px', gap: 10, alignItems: 'center' }}>
                <strong>{row.score}</strong>
                <div style={{ height: 8, background: '#f3f4f6', borderRadius: 999, overflow: 'hidden' }}>
                  <div style={{ height: '100%', width: `${Math.max(3, row.probability * 100)}%`, background: colors.gold }} />
                </div>
                <span style={{ textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>{Math.round(row.probability * 100)}%</span>
              </div>
            ))}
          </div>
          <p style={{ color: '#6b7280', fontSize: 12, lineHeight: 1.5, marginBottom: 0 }}>
            Prototype model: Poisson scoreline simulation adjusted by scenario dials. Use for coaching discussion, not final match odds.
          </p>
        </div>
      </div>
    </div>
  );
}

function Dial({ label, value, min, max, step, onChange }) {
  return (
    <label style={{ display: 'grid', gap: 6, marginBottom: '1rem' }}>
      <span style={{ display: 'flex', justifyContent: 'space-between', color: '#374151', fontWeight: 700, fontSize: 13 }}>
        {label}
        <span style={{ color: colors.garnet, fontVariantNumeric: 'tabular-nums' }}>{value}</span>
      </span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={e => onChange(e.target.value)} />
    </label>
  );
}

function ProbabilityTile({ label, value, tone }) {
  const bg = tone === 'good' ? '#ecfdf5' : tone === 'bad' ? '#fef2f2' : '#fffbeb';
  const fg = tone === 'good' ? colors.success : tone === 'bad' ? colors.garnet : colors.goldText;
  return (
    <div style={{ background: bg, borderRadius: 8, padding: '1rem', textAlign: 'center' }}>
      <div style={{ color: '#6b7280', fontSize: 12, fontWeight: 800, letterSpacing: 0.5 }}>{label}</div>
      <div style={{ color: fg, fontSize: 30, fontWeight: 900 }}>{Math.round(value * 100)}%</div>
    </div>
  );
}

function scenarioModel(inputs) {
  const cofcLambda = clamp(
    inputs.cofcXg
      + (inputs.possession - 50) * 0.015
      + inputs.shotEdge * 0.035
      + inputs.pressEdge * 0.03
      + inputs.setPieceEdge * 0.06
      + inputs.home,
    0.05,
    4.5
  );
  const oppLambda = clamp(
    inputs.oppXg
      - (inputs.possession - 50) * 0.012
      - inputs.pressEdge * 0.025
      - inputs.setPieceEdge * 0.03,
    0.05,
    4.5
  );

  let win = 0;
  let draw = 0;
  let loss = 0;
  const scorelines = [];
  for (let gf = 0; gf <= 6; gf += 1) {
    for (let ga = 0; ga <= 6; ga += 1) {
      const p = poisson(gf, cofcLambda) * poisson(ga, oppLambda);
      if (gf > ga) win += p;
      else if (gf === ga) draw += p;
      else loss += p;
      scorelines.push({ score: `${gf}-${ga}`, probability: p });
    }
  }
  const total = win + draw + loss || 1;
  return {
    win: win / total,
    draw: draw / total,
    loss: loss / total,
    scorelines: scorelines.sort((a, b) => b.probability - a.probability).slice(0, 5),
  };
}

function poisson(k, lambda) {
  let factorial = 1;
  for (let i = 2; i <= k; i += 1) factorial *= i;
  return Math.exp(-lambda) * Math.pow(lambda, k) / factorial;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

// ── Analytics Dashboard ───────────────────────────────────────────────────────
function AnalyticsDashboard() {
  const [showInsights, setShowInsights]       = useState(false);
  const [pressingData, setPressingData]       = useState([]);
  const [shotsData, setShotsData]             = useState([]);
  const [shotsAvailable, setShotsAvailable]   = useState(false);
  const [rosterData, setRosterData]           = useState([]);
  const [formationData, setFormationData]     = useState([]);
  const [formationsAvailable, setFormationsAvailable] = useState(false);
  const [selectedPlayer, setSelectedPlayer]   = useState('All');
  const [loading, setLoading]                 = useState(true);

  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetch(`${API_URL}/api/leaders/recoveries`).then(r => r.json()).catch(() => []),
      fetch(`${API_URL}/api/team/shots-by-time`).then(r => r.json()).catch(() => ({ available: false, labels: [], data: [] })),
      fetch(`${API_URL}/api/roster/development`).then(r => r.json()).catch(() => []),
      fetch(`${API_URL}/api/team/formations`).then(r => r.json()).catch(() => ({ available: false, data: [] })),
    ])
    .then(([recoveriesRes, shotsRes, developmentRes, formationRes]) => {
      if (Array.isArray(recoveriesRes) && recoveriesRes.length > 0) {
        setPressingData(recoveriesRes.map(p => ({
          name:            p.name.split(' ').pop(),
          fullName:        p.name,
          Recoveries:      p.value,
          'Shots Created': Math.floor((p.value || 0) / 4),
        })));
      }
      if (shotsRes.available !== false && Array.isArray(shotsRes.labels)) {
        const hasData = shotsRes.data && shotsRes.data.some(v => v !== null);
        if (hasData) {
          setShotsAvailable(true);
          setShotsData(shotsRes.labels.map((label, i) => ({ time: label, Shots: shotsRes.data[i] ?? 0 })));
        }
      }
      if (Array.isArray(developmentRes)) setRosterData(developmentRes);
      if (formationRes.available !== false && Array.isArray(formationRes.data) && formationRes.data.length > 0) {
        setFormationsAvailable(true);
        setFormationData(formationRes.data);
      } else if (Array.isArray(formationRes) && formationRes.length > 0) {
        setFormationsAvailable(true);
        setFormationData(formationRes);
      }
      setLoading(false);
    })
    .catch(() => setLoading(false));
  }, [API_URL]);

  const displayData = selectedPlayer === 'All'
    ? pressingData.slice(0, 12)
    : pressingData.filter(p => p.fullName === selectedPlayer);

  if (loading) return (
    <div style={{ padding: '5rem', textAlign: 'center' }}>
      <h2 style={{ color: colors.garnet }}>Loading Cougars Analytics...</h2>
    </div>
  );

  return (
    <div style={{ maxWidth: '1200px', margin: '0 auto', padding: '2rem' }}>
      {/* HEADER */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem', backgroundColor: colors.cardBg, padding: '1.5rem', borderRadius: '12px', boxShadow: '0 2px 4px rgba(0,0,0,0.05)' }}>
        <div>
          <h1 style={{ color: colors.garnet, margin: 0 }}>Charleston Cougars Analytics</h1>
          <div style={{ marginTop: '10px' }}>
            <label style={{ marginRight: '10px', fontSize: '14px', color: '#666' }}>Filter Roster:</label>
            <select value={selectedPlayer} onChange={e => setSelectedPlayer(e.target.value)} style={{ padding: '5px', borderRadius: '4px', border: '1px solid #ddd', cursor: 'pointer' }}>
              <option value="All">All Players (Top 12)</option>
              {pressingData.map(p => <option key={p.fullName} value={p.fullName}>{p.fullName}</option>)}
            </select>
          </div>
        </div>
        <button type="button" onClick={() => setShowInsights(!showInsights)}
          style={{ padding: '10px 20px', backgroundColor: colors.gold, border: 'none', borderRadius: '6px', fontWeight: 'bold', cursor: 'pointer' }}>
          {showInsights ? 'Hide Insights' : 'Show Tactical Insights'}
        </button>
      </div>

      {/* INSIGHTS */}
      {showInsights && (
        <div style={{ animation: 'slideDown 0.4s ease-out', backgroundColor: '#fff', padding: '1.5rem', borderRadius: '12px', marginBottom: '2rem', borderLeft: `6px solid ${colors.gold}`, boxShadow: '0 4px 6px rgba(0,0,0,0.05)' }}>
          <h3 style={{ margin: '0 0 15px 0', color: colors.garnet }}>Tactical Engine: Formation Efficiency (Net GD)</h3>
          {formationsAvailable ? (
            <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '2rem', alignItems: 'center' }}>
              <div style={{ height: '180px' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={formationData} layout="vertical" margin={{ left: -20 }}>
                    <XAxis type="number" hide />
                    <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} style={{ fontWeight: 'bold' }} />
                    <Tooltip cursor={{ fill: 'transparent' }} />
                    <Bar dataKey="gd" radius={[0, 4, 4, 0]} barSize={30}>
                      {formationData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.gd > 0 ? colors.success : entry.gd < 0 ? colors.garnet : '#999'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <p style={{ margin: 0, fontSize: '14px', color: '#444', lineHeight: '1.6' }}>
                Formation efficiency data from current season matches.
              </p>
            </div>
          ) : (
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', padding: '1rem', backgroundColor: colors.pending, borderRadius: '8px' }}>
              <span style={{ fontSize: 20 }}>⏳</span>
              <div>
                <p style={{ margin: 0, fontWeight: 600, color: '#374151' }}>Formation data coming soon</p>
                <p style={{ margin: '4px 0 0', fontSize: '13px', color: colors.pendingText }}>Available after match session notes are structured.</p>
              </div>
            </div>
          )}
        </div>
      )}

      {/* CHARTS */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '2rem' }}>
        {shotsAvailable ? (
          <div style={{ backgroundColor: colors.cardBg, padding: '1.5rem', borderRadius: '12px', boxShadow: '0 2px 4px rgba(0,0,0,0.05)' }}>
            <h3 style={{ color: '#374151', marginTop: 0 }}>Attacking Threat</h3>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={shotsData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#eee" />
                <XAxis dataKey="time" /><YAxis /><Tooltip />
                <Area type="monotone" dataKey="Shots" stroke={colors.garnet} fill={colors.garnet} fillOpacity={0.2} strokeWidth={3} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <PendingCard title="Attacking Threat" message="Shot timing data available after XML pipeline runs" />
        )}

        {displayData.length > 0 ? (
          <div style={{ backgroundColor: colors.cardBg, padding: '1.5rem', borderRadius: '12px', boxShadow: '0 2px 4px rgba(0,0,0,0.05)' }}>
            <h3 style={{ color: '#374151', marginTop: 0 }}>Defensive Output</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={displayData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#eee" />
                <XAxis dataKey="name" /><YAxis />
                <Tooltip cursor={{ fill: '#f9fafb' }} />
                <Legend iconType="circle" />
                <Bar dataKey="Recoveries" fill={colors.garnet} radius={[4,4,0,0]} barSize={selectedPlayer === 'All' ? 25 : 60} />
                <Bar dataKey="Shots Created" fill={colors.gold} radius={[4,4,0,0]} barSize={selectedPlayer === 'All' ? 25 : 60} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <PendingCard title="Defensive Output" message="Recovery data available after XML pipeline runs" />
        )}
      </div>

      {/* ROSTER TABLE */}
      <div style={{ backgroundColor: colors.cardBg, padding: '1.5rem', borderRadius: '12px', marginBottom: '2rem' }}>
        <h3 style={{ color: colors.garnet, marginTop: 0, marginBottom: '1.5rem' }}>Full Roster Development Tracker</h3>
        {rosterData.length > 0 ? (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ textAlign: 'left', borderBottom: '2px solid #eee' }}>
                  <th style={{ padding: '12px' }}>Player</th>
                  <th>Position</th><th>Metric</th><th>Current</th><th>Target</th><th>Status</th>
                </tr>
              </thead>
              <tbody>
                {rosterData.map((player, idx) => {
                  const isPending = player.Status === 'Pending Data';
                  return (
                    <tr key={idx} style={{ borderBottom: '1px solid #f9fafb' }}>
                      <td style={{ padding: '12px', fontWeight: 'bold' }}>{player.name}</td>
                      <td>{player.position}</td>
                      <td style={{ fontSize: '14px', color: '#666' }}>{player.Metric}</td>
                      <td style={{ color: isPending ? colors.pendingText : 'inherit' }}>
                        {player.Value !== null && player.Value !== undefined ? player.Value : '—'}
                      </td>
                      <td>{player.Goal}</td>
                      <td>
                        <span style={{
                          padding: '4px 10px', borderRadius: '20px', fontSize: '11px', fontWeight: 'bold',
                          backgroundColor: isPending ? colors.pending : player.Status === 'On Target' ? colors.goldLight : colors.pink,
                          color: isPending ? colors.pendingText : player.Status === 'On Target' ? colors.goldText : colors.pinkText,
                        }}>
                          {player.Status}
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <div style={{ padding: '2rem', textAlign: 'center', color: colors.pendingText }}>
            <span style={{ fontSize: 24 }}>⏳</span>
            <p style={{ margin: '0.5rem 0 0' }}>Roster data loading from Supabase...</p>
          </div>
        )}
      </div>

      {/* GLOSSARY */}
      <div style={{ backgroundColor: colors.cardBg, padding: '1.5rem', borderRadius: '12px', borderTop: `4px solid ${colors.gold}` }}>
        <h3 style={{ color: colors.garnet, marginTop: 0 }}>Analytics Legend</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1.5rem', marginTop: '1rem' }}>
          <div><h4 style={{ margin: '0 0 5px 0' }}>xG (Expected Goals)</h4><p style={{ margin: 0, fontSize: '13px', color: '#666', lineHeight: '1.4' }}>Measures shot quality. A 0.25 value means a player scores that chance 25% of the time.</p></div>
          <div><h4 style={{ margin: '0 0 5px 0' }}>Recoveries / 90</h4><p style={{ margin: 0, fontSize: '13px', color: '#666', lineHeight: '1.4' }}>Possession regains normalized per 90 mins to allow fair comparison.</p></div>
          <div><h4 style={{ margin: '0 0 5px 0' }}>PPDA</h4><p style={{ margin: 0, fontSize: '13px', color: '#666', lineHeight: '1.4' }}>Passes Allowed Per Defensive Action. Lower numbers mean higher pressing intensity.</p></div>
        </div>
      </div>
    </div>
  );
}

// ── Legacy COUG Dashboard wrapper ─────────────────────────────────────────────
// Keeping the old CSV-based dashboard as Tab 2 while Tab 3 is the new Supabase version
import COUGDashboardLegacy from './coug_dashboard.jsx';

// ── Root App ──────────────────────────────────────────────────────────────────
export default function App() {
  const [tab, setTab] = useState('coug2');
  const darkSurface = tab === 'coug2';

  return (
    <div style={{ backgroundColor: darkSurface ? '#0a0806' : colors.background, minHeight: '100vh', fontFamily: 'sans-serif' }}>
      <style>{slideDownStyle}</style>
      <div style={{ backgroundColor: colors.cardBg, borderBottom: '1px solid #e5e7eb', padding: '1rem 2rem 0' }}>
        <h2 style={{ color: colors.garnet, margin: '0 0 0 0', fontSize: 18, letterSpacing: 0.5 }}>
          Charleston Cougars · Soccer Analytics
        </h2>
        <TabNav active={tab} onChange={setTab} />
      </div>
      {tab === 'analytics' && <AnalyticsDashboard />}
      {tab === 'coug'      && <div style={{ padding: '2rem' }}><COUGDashboardLegacy /></div>}
      {tab === 'coug2'     && <CougTable />}
      {tab === 'staff'     && <StaffDashboard />}
    </div>
  );
}
