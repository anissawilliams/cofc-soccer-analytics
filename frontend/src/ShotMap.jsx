import { useEffect, useMemo, useState } from 'react';
import { staffApiFetch } from './staffApi';
import './ShotMap.css';

const FALLBACK_SEASON = '2026';

const C = {
  bg: '#120907', surface: '#1d0d0c', surface2: '#291210', border: '#4a2722',
  garnet: '#9f182c', gold: '#cfb53b', text: '#f8eee5', muted: '#b89987',
  cofc: '#cfb53b', opponent: '#65aebc', pitch: '#173d2c', line: '#89a995', danger: '#e34b5f',
};

function minuteLabel(shot) {
  if (shot.minute_label) return `${shot.minute_label}′`;
  return `${Math.floor(Number(shot.minute || 0))}′`;
}

function valueLabel(value, display) {
  if (display) return display;
  return value === null || value === undefined ? '—' : Number(value).toFixed(2);
}

function outcomeLabel(outcome) {
  return {
    goal: 'Goal', on_goal: 'On goal', on_post: 'On post', blocked: 'Blocked', wide: 'Wide',
  }[outcome] || outcome;
}

function markerRadius(shot) {
  const xg = Number(shot.xg);
  return Number.isFinite(xg) ? Math.min(18, 7 + Math.sqrt(Math.max(0, xg)) * 15) : 7;
}

function ShotMarker({ shot, color, selected, onSelect }) {
  const cx = 10 + (Number(shot.x) / 100) * 320;
  const cy = 510 - (Number(shot.y) / 100) * 500;
  const radius = markerRadius(shot);
  const common = {
    fill: shot.outcome === 'goal' ? color : C.pitch,
    stroke: selected ? C.text : color,
    strokeWidth: selected ? 3 : 2,
  };
  const label = `${minuteLabel(shot)} ${shot.player || 'Unknown player'}, ${outcomeLabel(shot.outcome)}, xG ${valueLabel(shot.xg, shot.xg_display)}`;

  return (
    <g
      role="button"
      tabIndex="0"
      aria-label={label}
      onClick={() => onSelect(shot)}
      onKeyDown={event => {
        if (event.key === 'Enter' || event.key === ' ') onSelect(shot);
      }}
      style={{ cursor: 'pointer' }}
    >
      <title>{label}</title>
      <circle cx={cx} cy={cy} r={Math.max(16, radius + 6)} fill="transparent" />
      {shot.outcome === 'goal' ? (
        <rect x={cx - radius * 0.72} y={cy - radius * 0.72} width={radius * 1.44} height={radius * 1.44} transform={`rotate(45 ${cx} ${cy})`} {...common} />
      ) : shot.outcome === 'blocked' ? (
        <rect x={cx - radius} y={cy - radius} width={radius * 2} height={radius * 2} {...common} />
      ) : (
        <circle cx={cx} cy={cy} r={radius} {...common} strokeDasharray={shot.outcome === 'wide' ? '3 3' : undefined} />
      )}
      {shot.outcome === 'on_post' && <circle cx={cx} cy={cy} r={Math.max(2, radius * 0.3)} fill={color} />}
      <text x={cx} y={cy + 3.5} textAnchor="middle" fill={shot.outcome === 'goal' ? C.bg : C.text} fontSize="9" fontWeight="900">
        {shot.sequence}
      </text>
    </g>
  );
}

function Pitch({ team, shots, color, selectedShot, onSelect }) {
  return (
    <div style={{ minWidth: 0 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'baseline', marginBottom: 8 }}>
        <strong style={{ color, fontSize: 14 }}>{team}</strong>
        <span style={{ color: C.muted, fontSize: 10, letterSpacing: 1.2 }}>ATTACKING ↑</span>
      </div>
      <svg viewBox="0 0 340 520" role="img" aria-label={`${team} shot locations, attacking toward the top goal`} style={{ width: '100%', display: 'block', background: C.pitch, border: `1px solid ${C.border}` }}>
        <rect x="10" y="10" width="320" height="500" fill="none" stroke={C.line} strokeWidth="2" />
        <line x1="10" x2="330" y1="260" y2="260" stroke={C.line} strokeWidth="1.5" />
        <circle cx="170" cy="260" r="48" fill="none" stroke={C.line} strokeWidth="1.5" />
        <circle cx="170" cy="260" r="2" fill={C.line} />
        <rect x="83" y="10" width="174" height="82" fill="none" stroke={C.line} strokeWidth="1.5" />
        <rect x="125" y="10" width="90" height="31" fill="none" stroke={C.line} strokeWidth="1.5" />
        <path d="M 126 92 A 48 48 0 0 0 214 92" fill="none" stroke={C.line} strokeWidth="1.5" />
        <circle cx="170" cy="65" r="2.5" fill={C.line} />
        <rect x="83" y="428" width="174" height="82" fill="none" stroke={C.line} strokeWidth="1.5" />
        <rect x="125" y="479" width="90" height="31" fill="none" stroke={C.line} strokeWidth="1.5" />
        <path d="M 126 428 A 48 48 0 0 1 214 428" fill="none" stroke={C.line} strokeWidth="1.5" />
        <circle cx="170" cy="455" r="2.5" fill={C.line} />
        {shots.map(shot => (
          <ShotMarker
            key={shot.shot_id}
            shot={shot}
            color={color}
            selected={selectedShot?.shot_id === shot.shot_id}
            onSelect={onSelect}
          />
        ))}
      </svg>
    </div>
  );
}

function TeamSummary({ team, summary, color }) {
  const metrics = [
    ['SHOTS', summary?.shots ?? 0],
    ['xG', Number(summary?.xg ?? 0).toFixed(2)],
    ['ON GOAL', summary?.on_goal ?? 0],
    ['xG ≥ .25', summary?.big_chances ?? 0],
  ];
  return (
    <div style={{ borderTop: `3px solid ${color}`, background: C.surface2, padding: '12px 14px' }}>
      <strong style={{ display: 'block', marginBottom: 10 }}>{team}</strong>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, minmax(0, 1fr))', gap: 8 }}>
        {metrics.map(([label, value]) => (
          <div key={label}>
            <div style={{ color: C.muted, fontSize: 8, letterSpacing: 1 }}>{label}</div>
            <div style={{ color: C.text, fontSize: 18, fontWeight: 900, marginTop: 2 }}>{value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function ShotDetail({ shot }) {
  if (!shot) {
    return <div style={{ color: C.muted, fontSize: 13 }}>Select a marker or row to inspect a chance.</div>;
  }
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, alignItems: 'baseline' }}>
        <div style={{ fontSize: 24, fontWeight: 900 }}>{minuteLabel(shot)}</div>
        <strong style={{ color: shot.outcome === 'goal' ? C.gold : C.text }}>{outcomeLabel(shot.outcome)}</strong>
      </div>
      <div style={{ fontSize: 17, fontWeight: 800, marginTop: 8 }}>{shot.player || 'Unknown player'}</div>
      <div style={{ color: C.muted, fontSize: 12, marginTop: 3 }}>{shot.team}</div>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, borderTop: `1px solid ${C.border}`, marginTop: 14, paddingTop: 14 }}>
        <div><span style={{ color: C.muted, fontSize: 10 }}>xG</span><br /><b>{valueLabel(shot.xg, shot.xg_display)}</b></div>
        <div><span style={{ color: C.muted, fontSize: 10 }}>POST-SHOT xG</span><br /><b>{valueLabel(shot.psxg, shot.psxg_display)}</b></div>
        <div><span style={{ color: C.muted, fontSize: 10 }}>SHOT TYPE</span><br /><b>{shot.shot_type || '—'}</b></div>
        <div><span style={{ color: C.muted, fontSize: 10 }}>LOCATION</span><br /><b>{Number(shot.x).toFixed(1)}, {Number(shot.y).toFixed(1)}</b></div>
      </div>
    </div>
  );
}

export default function ShotMap() {
  const [seasons, setSeasons] = useState([]);
  const [season, setSeason] = useState('');
  const [matches, setMatches] = useState([]);
  const [sessionId, setSessionId] = useState('');
  const [payload, setPayload] = useState(null);
  const [selectedShot, setSelectedShot] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    staffApiFetch('/api/seasons')
      .then(data => {
        const items = Array.isArray(data) ? data : data.seasons || [];
        const sorted = [...new Set(items.map(String).filter(Boolean))]
          .sort((a, b) => b.localeCompare(a, undefined, { numeric: true }));
        const available = sorted.length ? sorted : [FALLBACK_SEASON];
        setSeasons(available);
        setSeason(available[0]);
      })
      .catch(() => {
        setSeasons([FALLBACK_SEASON]);
        setSeason(FALLBACK_SEASON);
      });
  }, []);

  useEffect(() => {
    if (!season) return;
    staffApiFetch(`/api/team/matches?season=${season}`)
      .then(items => {
        setMatches(items);
        setSessionId(items[0]?.session_id || '');
        if (!items.length) setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, [season]);

  useEffect(() => {
    if (!sessionId) return;
    staffApiFetch(`/api/shot-map/${sessionId}`)
      .then(data => {
        setPayload(data);
        const shots = data.shot_map?.shots || [];
        setSelectedShot([...shots].sort((a, b) => Number(b.xg || 0) - Number(a.xg || 0))[0] || null);
        setLoading(false);
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, [sessionId]);

  const shotMap = payload?.shot_map;
  const homeShots = useMemo(() => (shotMap?.shots || []).filter(shot => shot.team === shotMap.home_team), [shotMap]);
  const awayShots = useMemo(() => (shotMap?.shots || []).filter(shot => shot.team === shotMap.away_team), [shotMap]);
  const orderedShots = useMemo(() => [...(shotMap?.shots || [])].sort((a, b) => Number(a.minute) - Number(b.minute)), [shotMap]);
  const match = payload?.match;
  const cofcTeam = match?.home ? shotMap?.home_team : shotMap?.away_team;
  const homeColor = shotMap?.home_team === cofcTeam ? C.cofc : C.opponent;
  const awayColor = shotMap?.away_team === cofcTeam ? C.cofc : C.opponent;
  const control = { background: C.surface2, border: `1px solid ${C.border}`, color: C.text, padding: '8px 10px', borderRadius: 4 };

  return (
    <div style={{ minHeight: '100vh', background: C.bg, color: C.text, padding: '24px 28px', fontFamily: 'Inter, system-ui, sans-serif' }}>
      <div style={{ maxWidth: 1240, margin: '0 auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 20, alignItems: 'flex-start', marginBottom: 22, flexWrap: 'wrap' }}>
          <div>
            <div style={{ color: C.gold, fontSize: 11, letterSpacing: 2.5, fontWeight: 800 }}>COFC MATCH ANALYSIS</div>
            <h1 style={{ margin: '5px 0 4px', fontSize: 30, letterSpacing: 1 }}>SHOT MAP & CHANCE QUALITY</h1>
            <div style={{ color: C.muted, fontSize: 13 }}>Where chances came from, who took them, and how dangerous they were.</div>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <select value={season} onChange={event => {
              setLoading(true);
              setError('');
              setPayload(null);
              setSelectedShot(null);
              setSessionId('');
              setSeason(event.target.value);
            }} style={control}>
              {seasons.map(item => <option key={item} value={item}>{item} Season</option>)}
            </select>
            <select value={sessionId} onChange={event => {
              setLoading(true);
              setError('');
              setPayload(null);
              setSelectedShot(null);
              setSessionId(event.target.value);
            }} style={{ ...control, minWidth: 230 }}>
              {!matches.length && <option value="">No matches available</option>}
              {matches.map(item => <option key={item.session_id} value={item.session_id}>{item.date} · {item.opponent}</option>)}
            </select>
          </div>
        </div>

        {match && (
          <div style={{ background: `linear-gradient(110deg, ${C.surface2}, ${C.surface})`, border: `1px solid ${C.border}`, padding: '16px 20px', marginBottom: 14, display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            <div>
              <div style={{ color: C.muted, fontSize: 10, letterSpacing: 1.3 }}>{match.date} · {match.competition || 'Match'} · {match.home ? 'HOME' : 'AWAY'}</div>
              <strong style={{ display: 'block', fontSize: 20, marginTop: 4 }}>COFC vs {match.opponent}</strong>
            </div>
            <div style={{ color: C.gold, fontSize: 28, fontWeight: 900 }}>{match.goals_for ?? '–'} <span style={{ color: C.muted }}>:</span> {match.goals_against ?? '–'}</div>
          </div>
        )}

        {loading ? <div style={{ padding: 70, textAlign: 'center', color: C.muted }}>LOADING SHOT DATA…</div>
          : error ? <div style={{ padding: 40, color: C.danger, border: `1px solid ${C.border}` }}>{error}</div>
          : !sessionId ? <div style={{ padding: 60, textAlign: 'center', color: C.muted, border: `1px solid ${C.border}` }}>No completed matches are available for this season yet.</div>
          : !shotMap?.available ? (
            <div style={{ background: C.surface, border: `1px solid ${C.border}`, padding: '34px 28px' }}>
              <div style={{ color: C.gold, fontSize: 11, letterSpacing: 1.8, fontWeight: 800 }}>SHOT DATA PENDING</div>
              <h2 style={{ margin: '8px 0', fontSize: 20 }}>The match shell is ready.</h2>
              <p style={{ color: C.muted, maxWidth: 660, lineHeight: 1.6, marginBottom: 0 }}>{shotMap?.reason || 'A reviewed shot-map snapshot has not been published.'}</p>
            </div>
          ) : (
            <>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 12, marginBottom: 12 }}>
                <TeamSummary team={shotMap.home_team} summary={shotMap.team_summaries[shotMap.home_team]} color={homeColor} />
                <TeamSummary team={shotMap.away_team} summary={shotMap.team_summaries[shotMap.away_team]} color={awayColor} />
              </div>

              <div className="shot-map-analysis-grid">
                <div style={{ background: C.surface, border: `1px solid ${C.border}`, padding: 18, minWidth: 0 }}>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: 18 }}>
                    <Pitch team={shotMap.home_team} shots={homeShots} color={homeColor} selectedShot={selectedShot} onSelect={setSelectedShot} />
                    <Pitch team={shotMap.away_team} shots={awayShots} color={awayColor} selectedShot={selectedShot} onSelect={setSelectedShot} />
                  </div>
                  <div style={{ display: 'flex', gap: 14, flexWrap: 'wrap', color: C.muted, fontSize: 10, marginTop: 12 }}>
                    <span>Marker area = xG</span><span>◆ Goal</span><span>○ On goal</span><span>⊙ On post</span><span>□ Blocked</span><span>Dashed = wide</span>
                  </div>
                </div>

                <aside style={{ background: C.surface, border: `1px solid ${C.border}`, padding: 18 }}>
                  <div style={{ color: C.gold, fontSize: 10, letterSpacing: 2, fontWeight: 800, marginBottom: 14 }}>CHANCE DETAIL</div>
                  <ShotDetail shot={selectedShot} />
                </aside>
              </div>

              <div style={{ background: C.surface, border: `1px solid ${C.border}`, marginTop: 12, overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: 690, textAlign: 'left', fontSize: 12 }}>
                  <thead><tr style={{ color: C.muted, borderBottom: `1px solid ${C.border}` }}>
                    {['MIN', 'TEAM', 'PLAYER', 'OUTCOME', 'SHOT TYPE', 'xG', 'PSxG'].map(label => <th key={label} style={{ padding: '11px 12px', fontSize: 9, letterSpacing: 1.2 }}>{label}</th>)}
                  </tr></thead>
                  <tbody>{orderedShots.map(shot => (
                    <tr key={shot.shot_id} onClick={() => setSelectedShot(shot)} style={{ borderBottom: `1px solid ${C.border}`, cursor: 'pointer', background: selectedShot?.shot_id === shot.shot_id ? C.surface2 : 'transparent' }}>
                      <td style={{ padding: '10px 12px', color: C.gold, fontWeight: 900 }}>{minuteLabel(shot)}</td>
                      <td style={{ padding: '10px 12px' }}>{shot.team}</td>
                      <td style={{ padding: '10px 12px', fontWeight: 800 }}>{shot.player}</td>
                      <td style={{ padding: '10px 12px' }}>{outcomeLabel(shot.outcome)}</td>
                      <td style={{ padding: '10px 12px', color: C.muted }}>{shot.shot_type}</td>
                      <td style={{ padding: '10px 12px' }}>{valueLabel(shot.xg, shot.xg_display)}</td>
                      <td style={{ padding: '10px 12px' }}>{valueLabel(shot.psxg, shot.psxg_display)}</td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
              <div style={{ color: C.muted, fontSize: 10, marginTop: 10 }}>
                {shotMap.source?.label || 'Reviewed source'} · {shotMap.coverage?.located_shots ?? orderedShots.length}/{shotMap.coverage?.shots ?? orderedShots.length} shots located · coordinates normalized to 0–100
              </div>
            </>
          )}
      </div>
    </div>
  );
}
