import { useMemo, useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, Cell,
  CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';

const T = {
  garnet: '#800000',
  gold: '#CFB53B',
  goldText: '#8B7500',
  success: '#166534',
};

export default function StaffPortal() {
  return (
    <StaffGate>
      <StaffDashboard />
    </StaffGate>
  );
}

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
    <div style={styles.gate}>
      <h2 style={{ marginTop: 0, color: T.garnet }}>Staff Access</h2>
      <p style={styles.muted}>
        Private scouting, player development, prediction simulator, and recruiting tools.
      </p>
      <form onSubmit={submit} style={{ display: 'grid', gap: '0.75rem' }}>
        <label style={styles.label}>Passcode</label>
        <input
          type="password"
          value={value}
          onChange={e => setValue(e.target.value)}
          style={styles.input}
        />
        {error && <div style={styles.error}>{error}</div>}
        <button type="submit" style={styles.primaryButton}>Enter Staff Area</button>
      </form>
      <p style={styles.note}>
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
    <div style={styles.page}>
      <div style={styles.header}>
        <div>
          <h1 style={styles.title}>Staff Dashboard</h1>
          <p style={styles.subtitle}>Private scouting, simulation, development, and recruiting workspace.</p>
        </div>
        <button
          type="button"
          onClick={() => {
            window.localStorage.removeItem('cofc_staff_access');
            window.location.reload();
          }}
          style={styles.lockButton}
        >
          Lock
        </button>
      </div>

      <div style={styles.sectionTabs}>
        {sections.map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setSection(id)}
            style={{
              ...styles.sectionButton,
              ...(section === id ? styles.sectionButtonActive : {}),
            }}
          >
            {label}
          </button>
        ))}
      </div>

      {section === 'simulator' && <PredictionSimulator />}
      {section === 'scouting' && (
        <StaffPlaceholder
          title="Scouting"
          body="Opponent reports, readiness status, match shells, and pre-match prep will surface here from pipeline/scouting outputs."
        />
      )}
      {section === 'development' && (
        <StaffPlaceholder
          title="Player Development"
          body="Private player trends, COUG score explainers, and development targets will live here."
        />
      )}
      {section === 'recruiting' && (
        <StaffPlaceholder
          title="Recruiting"
          body="Recruiting readiness, profile imports, similarity scores, comps, and shortlists will live here once recruit profiles exist."
        />
      )}
    </div>
  );
}

function StaffPlaceholder({ title, body }) {
  return (
    <div style={styles.card}>
      <h2 style={{ marginTop: 0, color: T.garnet }}>{title}</h2>
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
    <div style={styles.simulatorGrid}>
      <div style={styles.card}>
        <h2 style={{ color: T.garnet, marginTop: 0 }}>Scenario Dials</h2>
        <Dial label="CofC xG" value={inputs.cofcXg} min={0.2} max={3.5} step={0.05} onChange={v => update('cofcXg', v)} />
        <Dial label="Opponent xG" value={inputs.oppXg} min={0.2} max={3.5} step={0.05} onChange={v => update('oppXg', v)} />
        <Dial label="Possession %" value={inputs.possession} min={35} max={65} step={1} onChange={v => update('possession', v)} />
        <Dial label="Shot edge" value={inputs.shotEdge} min={-8} max={8} step={1} onChange={v => update('shotEdge', v)} />
        <Dial label="Press/recovery edge" value={inputs.pressEdge} min={-5} max={5} step={1} onChange={v => update('pressEdge', v)} />
        <Dial label="Set-piece edge" value={inputs.setPieceEdge} min={-3} max={3} step={1} onChange={v => update('setPieceEdge', v)} />
        <Dial label="Home advantage" value={inputs.home} min={-0.15} max={0.25} step={0.05} onChange={v => update('home', v)} />
      </div>

      <div style={{ display: 'grid', gap: '1rem' }}>
        <div style={styles.card}>
          <h2 style={{ color: T.garnet, marginTop: 0 }}>Projected Outcome</h2>
          <div style={styles.probabilityTiles}>
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
                  {probabilityData.map(entry => (
                    <Cell key={entry.name} fill={entry.name === 'Win' ? T.success : entry.name === 'Loss' ? T.garnet : T.gold} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div style={styles.card}>
          <h3 style={{ color: '#374151', marginTop: 0 }}>Most Likely Scorelines</h3>
          <div style={{ display: 'grid', gap: 8 }}>
            {model.scorelines.map(row => (
              <div key={row.score} style={styles.scorelineRow}>
                <strong>{row.score}</strong>
                <div style={styles.scorelineTrack}>
                  <div style={{ ...styles.scorelineBar, width: `${Math.max(3, row.probability * 100)}%` }} />
                </div>
                <span style={styles.scorelinePercent}>{Math.round(row.probability * 100)}%</span>
              </div>
            ))}
          </div>
          <p style={styles.note}>
            Prototype model: Poisson scoreline simulation adjusted by scenario dials. Use for coaching discussion, not final match odds.
          </p>
        </div>
      </div>
    </div>
  );
}

function Dial({ label, value, min, max, step, onChange }) {
  return (
    <label style={styles.dial}>
      <span style={styles.dialHeader}>
        {label}
        <span style={styles.dialValue}>{value}</span>
      </span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={e => onChange(e.target.value)} />
    </label>
  );
}

function ProbabilityTile({ label, value, tone }) {
  const bg = tone === 'good' ? '#ecfdf5' : tone === 'bad' ? '#fef2f2' : '#fffbeb';
  const fg = tone === 'good' ? T.success : tone === 'bad' ? T.garnet : T.goldText;
  return (
    <div style={{ ...styles.probabilityTile, background: bg }}>
      <div style={styles.probabilityLabel}>{label}</div>
      <div style={{ ...styles.probabilityValue, color: fg }}>{Math.round(value * 100)}%</div>
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

const styles = {
  gate: {
    maxWidth: 460,
    margin: '4rem auto',
    background: '#fff',
    padding: '2rem',
    borderRadius: 8,
    boxShadow: '0 2px 10px rgba(0,0,0,0.08)',
  },
  page: {
    maxWidth: 1180,
    margin: '0 auto',
    padding: '2rem',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    gap: '1rem',
    alignItems: 'flex-end',
    marginBottom: '1.25rem',
  },
  title: {
    color: T.garnet,
    margin: 0,
  },
  subtitle: {
    color: '#4b5563',
    margin: '0.4rem 0 0',
  },
  card: {
    background: '#fff',
    border: '1px solid #e5e7eb',
    borderRadius: 8,
    padding: '1.25rem',
    boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
  },
  muted: {
    color: '#4b5563',
    lineHeight: 1.5,
  },
  note: {
    marginTop: '1rem',
    color: '#6b7280',
    fontSize: 12,
    lineHeight: 1.5,
  },
  label: {
    fontSize: 13,
    fontWeight: 700,
    color: '#374151',
  },
  input: {
    padding: '0.75rem',
    border: '1px solid #d1d5db',
    borderRadius: 6,
    fontSize: 15,
  },
  error: {
    color: '#991b1b',
    fontSize: 13,
  },
  primaryButton: {
    padding: '0.8rem 1rem',
    border: 'none',
    borderRadius: 6,
    background: T.garnet,
    color: '#fff',
    fontWeight: 800,
    cursor: 'pointer',
  },
  lockButton: {
    border: '1px solid #d1d5db',
    background: '#fff',
    borderRadius: 6,
    padding: '0.55rem 0.8rem',
    cursor: 'pointer',
    color: '#374151',
  },
  sectionTabs: {
    display: 'flex',
    gap: 8,
    flexWrap: 'wrap',
    marginBottom: '1.5rem',
  },
  sectionButton: {
    border: '1px solid #d1d5db',
    background: '#fff',
    color: '#374151',
    borderRadius: 6,
    padding: '0.7rem 0.95rem',
    fontWeight: 800,
    cursor: 'pointer',
  },
  sectionButtonActive: {
    border: `2px solid ${T.garnet}`,
    background: '#fff7ed',
    color: T.garnet,
  },
  simulatorGrid: {
    display: 'grid',
    gridTemplateColumns: 'minmax(280px, 0.9fr) minmax(320px, 1.1fr)',
    gap: '1.25rem',
  },
  probabilityTiles: {
    display: 'grid',
    gridTemplateColumns: 'repeat(3, 1fr)',
    gap: '0.75rem',
    marginBottom: '1rem',
  },
  probabilityTile: {
    borderRadius: 8,
    padding: '1rem',
    textAlign: 'center',
  },
  probabilityLabel: {
    color: '#6b7280',
    fontSize: 12,
    fontWeight: 800,
    letterSpacing: 0.5,
  },
  probabilityValue: {
    fontSize: 30,
    fontWeight: 900,
  },
  dial: {
    display: 'grid',
    gap: 6,
    marginBottom: '1rem',
  },
  dialHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    color: '#374151',
    fontWeight: 700,
    fontSize: 13,
  },
  dialValue: {
    color: T.garnet,
    fontVariantNumeric: 'tabular-nums',
  },
  scorelineRow: {
    display: 'grid',
    gridTemplateColumns: '70px 1fr 54px',
    gap: 10,
    alignItems: 'center',
  },
  scorelineTrack: {
    height: 8,
    background: '#f3f4f6',
    borderRadius: 999,
    overflow: 'hidden',
  },
  scorelineBar: {
    height: '100%',
    background: T.gold,
  },
  scorelinePercent: {
    textAlign: 'right',
    fontVariantNumeric: 'tabular-nums',
  },
};
