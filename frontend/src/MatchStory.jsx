import { useEffect, useMemo, useState } from 'react';
import { staffApiFetch } from './staffApi';

const FALLBACK_SEASON = '2026';

const C = {
  bg: '#120907', surface: '#1d0d0c', surface2: '#291210', border: '#4a2722',
  garnet: '#9f182c', gold: '#cfb53b', text: '#f8eee5', muted: '#b89987',
  aset: '#e34b5f', peak: '#e5bf39', set_piece: '#65b5a6', other: '#9d87c7', opponent: '#65aebc',
};

function bucketLabel(bucket) {
  return bucket === 'set_piece' ? 'Set Piece' : bucket === 'aset' ? 'ASET' : bucket === 'peak' ? 'PEAK' : 'Other';
}

function bucketColor(bucket) {
  return C[bucket] || C.other;
}

function minuteLabel(value) {
  if (value === null || value === undefined) return '—';
  return `${Math.max(0, Math.floor(Number(value)))}′`;
}

function score(value) {
  return Number(value || 0).toFixed(2);
}

function isAttackingEvent(event) {
  if (event.score_bucket === 'peak' || event.score_bucket === 'positional') return true;
  return /goal|assist|shot|opportun|key pass|smart pass/i.test(event.metric_name || '');
}

function buildPulseBins(events, endMinute) {
  const binCount = Math.max(18, Math.ceil(endMinute / 5));
  const bins = Array.from({ length: binCount }, (_, index) => ({
    start: index * 5,
    attack: 0,
    defense: 0,
    events: [],
  }));

  events.forEach(event => {
    const minute = Number(event.match_minute);
    if (!Number.isFinite(minute) || minute < 0) return;
    const index = Math.min(bins.length - 1, Math.floor(minute / 5));
    const contribution = Math.abs(Number(event.contribution));
    if (!Number.isFinite(contribution)) return;
    bins[index].events.push(event);
    if (isAttackingEvent(event)) bins[index].attack += contribution;
    if (event.score_bucket === 'aset') bins[index].defense += contribution;
  });

  return bins;
}

function strongestPulseWindow(events) {
  const endMinute = Math.max(90, Math.ceil(Math.max(90, ...events.map(event => Number(event.match_minute || 90))) / 5) * 5);
  return buildPulseBins(events, endMinute).reduce(
    (strongest, item) => item.attack + item.defense > strongest.attack + strongest.defense ? item : strongest,
    { start: 0, attack: 0, defense: 0 },
  ).start;
}

function strongestFlowWindow(flow, events) {
  if (!flow?.available || !flow.bins?.length) return strongestPulseWindow(events);
  return flow.bins.reduce(
    (strongest, item) => Number(item.home || 0) + Number(item.away || 0) > Number(strongest.home || 0) + Number(strongest.away || 0) ? item : strongest,
    flow.bins[0],
  ).start;
}

function OptaMatchFlow({ flow, selectedWindow, onSelectWindow }) {
  const bins = flow.bins || [];
  const width = 960;
  const height = 320;
  const pad = { left: 58, right: 22, top: 42, bottom: 42 };
  const middle = 160;
  const halfHeight = 98;
  const hasStoppage = bins.some(item => Number(item.start) >= 90);
  const endMinute = hasStoppage ? 95 : 90;
  const plotWidth = width - pad.left - pad.right;
  const binWidth = bins.length ? plotWidth / bins.length : plotWidth;
  const pressureMax = Math.max(1, ...bins.flatMap(item => [Number(item.home || 0), Number(item.away || 0)]));
  const selected = bins.find(item => Number(item.start) === Number(selectedWindow)) || bins[0];
  const windowMinutes = Number(flow.window_minutes || 5);

  return (
    <div style={{ marginBottom: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'flex-start', marginBottom: 10, flexWrap: 'wrap' }}>
        <div>
          <div style={{ display: 'flex', gap: 9, alignItems: 'center', flexWrap: 'wrap' }}>
            <h2 style={{ fontSize: 19, margin: 0 }}>Match Flow</h2>
            <span style={{ color: C.bg, background: C.gold, fontSize: 9, fontWeight: 900, letterSpacing: 1.2, padding: '3px 6px' }}>FULL TEAM EVENT FLOW</span>
          </div>
          <p style={{ color: C.muted, fontSize: 12, margin: '6px 0 0' }}>
            Five-minute pressure windows from both teams · goals and major momentum swings annotated
          </p>
        </div>
        <div style={{ display: 'flex', gap: 16, color: C.text, fontSize: 12, fontWeight: 700 }}>
          <span><i style={{ display: 'inline-block', width: 9, height: 9, background: C.gold, marginRight: 5 }} />{flow.home_team}</span>
          <span><i style={{ display: 'inline-block', width: 9, height: 9, background: C.opponent, marginRight: 5 }} />{flow.away_team}</span>
        </div>
      </div>

      <div style={{ overflowX: 'auto', border: `1px solid ${C.border}`, background: 'linear-gradient(180deg, #17100f 0%, #100908 100%)' }}>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={`${flow.home_team} and ${flow.away_team} match pressure by five-minute window`} style={{ width: '100%', minWidth: 720, display: 'block' }}>
        <text x={pad.left} y={23} fill={C.gold} fontSize="12" fontWeight="900" letterSpacing="1.4">{flow.home_team.toUpperCase()} PRESSURE</text>
        <text x={pad.left} y={height - 11} fill={C.opponent} fontSize="12" fontWeight="900" letterSpacing="1.4">{flow.away_team.toUpperCase()} PRESSURE</text>
        {[0, 15, 30, 45, 60, 75, 90].map(minute => {
          const x = pad.left + (minute / endMinute) * plotWidth;
          return <g key={minute}>
            <line x1={x} x2={x} y1={pad.top} y2={height - pad.bottom} stroke={minute === 45 ? C.gold : C.border} strokeWidth={minute === 45 ? 1.5 : 1} opacity={minute === 45 ? 0.48 : 0.55} />
            <text x={x} y={middle + 5} textAnchor="middle" fill={minute === 45 ? C.gold : C.muted} fontSize="12" fontWeight={minute === 45 ? 800 : 600}>{minute}′</text>
          </g>;
        })}
        {hasStoppage && <text x={width - pad.right} y={middle + 5} textAnchor="end" fill={C.muted} fontSize="11" fontWeight="700">90+</text>}
        <line x1={pad.left} x2={width - pad.right} y1={middle} y2={middle} stroke="#a78d7f" strokeWidth="1.25" />

        {bins.map((item, index) => {
          const x = pad.left + index * binWidth + 1;
          const barWidth = Math.max(5, binWidth - 5);
          const homeHeight = (Number(item.home || 0) / pressureMax) * halfHeight;
          const awayHeight = (Number(item.away || 0) / pressureMax) * halfHeight;
          const isSelected = Number(item.start) === Number(selected?.start);
          const label = `${item.start} to ${Number(item.start) + windowMinutes} minutes: ${flow.home_team} ${score(item.home)}, ${flow.away_team} ${score(item.away)}`;
          return <g key={item.start} onClick={() => onSelectWindow(Number(item.start))} onKeyDown={event => {
            if (event.key === 'Enter' || event.key === ' ') onSelectWindow(Number(item.start));
          }} role="button" tabIndex="0" aria-label={label} style={{ cursor: 'pointer', opacity: isSelected ? 1 : 0.72 }}>
            <title>{label}</title>
            {isSelected && <rect x={x - 3} y={pad.top} width={barWidth + 6} height={height - pad.top - pad.bottom} fill={C.gold} opacity="0.1" />}
            <rect x={x} y={middle - homeHeight} width={barWidth} height={homeHeight} fill={C.gold} rx="2" opacity="0.94" />
            <rect x={x} y={middle + 1} width={barWidth} height={awayHeight} fill={C.opponent} rx="2" opacity="0.94" />
          </g>;
        })}

        {(flow.goals || []).map((goal, index) => {
          const x = pad.left + (Math.min(endMinute, Number(goal.minute || 0)) / endMinute) * plotWidth;
          const isHome = goal.team === flow.home_team;
          return <g key={`${goal.minute}-${index}`}>
            <line x1={x} x2={x} y1={pad.top} y2={height - pad.bottom} stroke={C.text} strokeDasharray="3 4" opacity="0.45" />
            <circle cx={x} cy={isHome ? middle - 7 : middle + 7} r="4" fill={C.text} />
            <text x={x + (Number(goal.minute) > 84 ? -7 : 7)} y={isHome ? pad.top - 8 : height - pad.bottom + 19} textAnchor={Number(goal.minute) > 84 ? 'end' : 'start'} fill={C.text} fontSize="11" fontWeight="800">
              {minuteLabel(goal.minute)} GOAL
            </text>
          </g>;
        })}
      </svg>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '110px minmax(0, 1fr) auto', gap: 14, alignItems: 'center', padding: '12px 4px 0', borderTop: `1px solid ${C.border}`, marginTop: 10 }}>
        <div style={{ color: C.gold, fontSize: 20, fontWeight: 900 }}>
          {selected?.start ?? 0}′–{Number(selected?.start ?? 0) + windowMinutes}′
          <div style={{ color: C.muted, fontSize: 9, letterSpacing: 1.2 }}>SELECTED WINDOW</div>
        </div>
        <div style={{ color: C.text, fontSize: 12, lineHeight: 1.5 }}>{selected?.note || 'No canonical team events in this window.'}</div>
        <div style={{ textAlign: 'right', color: C.muted, fontSize: 11 }}>
          <strong style={{ display: 'block', color: C.text, fontSize: 14 }}>
            {Number(selected?.home || 0) > Number(selected?.away || 0)
              ? `${flow.home_team} surge`
              : Number(selected?.away || 0) > Number(selected?.home || 0)
                ? `${flow.away_team} surge`
                : 'Balanced window'}
          </strong>
          {score(selected?.home)} vs {score(selected?.away)}
        </div>
      </div>
      <div style={{ color: C.muted, fontSize: 10, marginTop: 9, display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <span>{flow.coverage?.canonical_events ?? 0} canonical events</span>
        <span>{flow.coverage?.mirrored_events ?? 0} mirrored confirmations</span>
        <span>{flow.coverage?.unmapped_labels ?? 0} unmapped labels</span>
      </div>
    </div>
  );
}

function MatchPulse({ events, endMinute, selectedWindow, onSelectWindow }) {
  const bins = useMemo(() => buildPulseBins(events, endMinute), [events, endMinute]);
  const width = 960;
  const height = 286;
  const pad = { left: 50, right: 16, top: 32, bottom: 34 };
  const middle = 142;
  const halfHeight = 92;
  const plotWidth = width - pad.left - pad.right;
  const binWidth = plotWidth / bins.length;
  const pulseMax = Math.max(1, ...bins.flatMap(item => [item.attack, item.defense]));
  const selected = bins.find(item => item.start === selectedWindow) || bins[0];
  const selectedEvents = [...(selected?.events || [])]
    .sort((a, b) => Math.abs(Number(b.contribution || 0)) - Math.abs(Number(a.contribution || 0)))
    .slice(0, 3);
  const goalEvents = events.filter(event => /goal \(scorer\)/i.test(event.metric_name || ''));

  return (
    <div style={{ marginBottom: 22 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 16, alignItems: 'flex-start', marginBottom: 10, flexWrap: 'wrap' }}>
        <div>
          <div style={{ display: 'flex', gap: 9, alignItems: 'center', flexWrap: 'wrap' }}>
            <h2 style={{ fontSize: 19, margin: 0 }}>COUG Scoring Pulse</h2>
            <span style={{ color: C.text, border: `1px solid ${C.aset}`, fontSize: 9, fontWeight: 900, letterSpacing: 1.2, padding: '3px 6px' }}>PARTIAL VIEW</span>
          </div>
          <p style={{ color: C.muted, fontSize: 12, margin: '6px 0 0', maxWidth: 620 }}>
            Full two-team Match Flow is pending. This view shows only score-bearing COUG events, so empty windows do not mean the match was inactive.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 14, color: C.muted, fontSize: 11 }}>
          <span><i style={{ display: 'inline-block', width: 9, height: 9, background: C.gold, marginRight: 5 }} />Attack</span>
          <span><i style={{ display: 'inline-block', width: 9, height: 9, background: C.aset, marginRight: 5 }} />Defense</span>
        </div>
      </div>

      <div style={{ overflowX: 'auto', border: `1px solid ${C.border}` }}>
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="COFC attacking and defensive contribution by five-minute window" style={{ width: '100%', minWidth: 720, display: 'block', background: '#120a09' }}>
        <text x={pad.left} y={18} fill={C.gold} fontSize="10" fontWeight="800" letterSpacing="1.2">ATTACKING CONTRIBUTION</text>
        <text x={pad.left} y={height - 8} fill={C.aset} fontSize="10" fontWeight="800" letterSpacing="1.2">DEFENSIVE CONTRIBUTION</text>
        {[0, 15, 30, 45, 60, 75, 90].filter(minute => minute <= endMinute).map(minute => {
          const x = pad.left + (minute / endMinute) * plotWidth;
          return <g key={minute}>
            <line x1={x} x2={x} y1={pad.top} y2={height - pad.bottom} stroke={C.border} strokeWidth="1" opacity="0.55" />
            <text x={x} y={middle + 4} textAnchor="middle" fill={C.muted} fontSize="10">{minute}</text>
          </g>;
        })}
        <line x1={pad.left} x2={width - pad.right} y1={middle} y2={middle} stroke="#7f665b" strokeWidth="1" />

        {bins.map((item, index) => {
          const x = pad.left + index * binWidth + 1;
          const barWidth = Math.max(3, binWidth - 3);
          const attackHeight = (item.attack / pulseMax) * halfHeight;
          const defenseHeight = (item.defense / pulseMax) * halfHeight;
          const isSelected = item.start === selected?.start;
          const label = `${item.start} to ${item.start + 5} minutes: attack ${score(item.attack)}, defense ${score(item.defense)}`;
          return <g key={item.start} onClick={() => onSelectWindow(item.start)} onKeyDown={event => {
            if (event.key === 'Enter' || event.key === ' ') onSelectWindow(item.start);
          }} role="button" tabIndex="0" aria-label={label} style={{ cursor: 'pointer', opacity: isSelected ? 1 : 0.72 }}>
            <title>{label}</title>
            {isSelected && <rect x={x - 2} y={pad.top} width={barWidth + 4} height={height - pad.top - pad.bottom} fill={C.gold} opacity="0.07" />}
            <rect x={x} y={middle - attackHeight} width={barWidth} height={attackHeight} fill={C.gold} rx="1" />
            <rect x={x} y={middle + 1} width={barWidth} height={defenseHeight} fill={C.aset} rx="1" />
          </g>;
        })}

        {goalEvents.map(event => {
          const x = pad.left + (Math.min(endMinute, Number(event.match_minute || 0)) / endMinute) * plotWidth;
          return <g key={event.event_id}>
            <line x1={x} x2={x} y1={pad.top} y2={height - pad.bottom} stroke={C.text} strokeDasharray="3 4" opacity="0.45" />
            <circle cx={x} cy={middle - 7} r="4" fill={C.text} />
            <text x={x + 5} y={pad.top - 6} fill={C.text} fontSize="9">{minuteLabel(event.match_minute)} GOAL</text>
          </g>;
        })}
      </svg>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '110px minmax(0, 1fr) auto', gap: 14, alignItems: 'center', padding: '12px 4px 0', borderTop: `1px solid ${C.border}`, marginTop: 10 }}>
        <div style={{ color: C.gold, fontSize: 20, fontWeight: 900 }}>
          {selected?.start ?? 0}′–{(selected?.start ?? 0) + 5}′
          <div style={{ color: C.muted, fontSize: 9, letterSpacing: 1.2 }}>SELECTED WINDOW</div>
        </div>
        <div style={{ color: C.text, fontSize: 12, lineHeight: 1.5 }}>
          {selectedEvents.length
            ? selectedEvents.map(event => `${minuteLabel(event.match_minute)} ${event.player}: ${event.metric_name}`).join(' · ')
            : 'No weighted COUG events in this window.'}
        </div>
        <div style={{ textAlign: 'right', color: C.muted, fontSize: 11 }}>
          <strong style={{ display: 'block', color: C.text, fontSize: 14 }}>
            {selected?.attack >= selected?.defense ? 'Attacking surge' : 'Defensive work'}
          </strong>
          {score(selected?.attack)} attack · {score(selected?.defense)} defense
        </div>
      </div>
    </div>
  );
}

function PeakCoverage({ summary }) {
  const timed = Number(summary?.peak || 0);
  const published = Number(summary?.published_peak || 0);
  const untimed = Number(summary?.untimed_peak || 0);
  const ratio = published > 0 ? Math.min(timed / published, 1) : 0;

  return (
    <div style={{ border: `1px solid ${C.border}`, background: C.surface2, padding: '12px 14px', marginBottom: 18 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 14, alignItems: 'baseline', flexWrap: 'wrap' }}>
        <strong style={{ fontSize: 12 }}>PEAK evidence coverage</strong>
        <span style={{ color: C.muted, fontSize: 11 }}>
          Timed <b style={{ color: C.gold }}>{score(timed)}</b> / Published <b style={{ color: C.text }}>{score(published)}</b>
          {untimed > 0 && <> · <b style={{ color: C.other }}>{score(untimed)} untimed legacy PEAK</b></>}
        </span>
      </div>
      <div style={{ height: 5, background: C.bg, marginTop: 9 }}>
        <div style={{ width: `${ratio * 100}%`, height: '100%', background: C.gold }} />
      </div>
      <div style={{ color: C.muted, fontSize: 10, marginTop: 7 }}>
        Untimed legacy points remain in the published COUG score but are not placed at an invented match minute.
      </div>
    </div>
  );
}

function TimelineHalf({ half, events, selectedId, onSelect, endMinute }) {
  const start = half === 1 ? 0 : 45;
  const end = half === 1 ? 45 : endMinute;
  const lanes = ['aset', 'peak', 'set_piece', 'other'];
  const ticks = [0, 1, 2, 3].map(index => Math.round(start + ((end - start) * index) / 3));

  return (
    <div style={{ borderTop: `1px solid ${C.border}`, paddingTop: 14 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
        <strong style={{ color: C.text, fontSize: 13 }}>{half === 1 ? 'FIRST HALF' : 'SECOND HALF'}</strong>
        <span style={{ color: C.muted, fontSize: 12 }}>{start}′–{end}′</span>
      </div>
      <div style={{ display: 'grid', gridTemplateColumns: '78px 1fr', gap: 10 }}>
        <div style={{ display: 'grid', gridTemplateRows: 'repeat(4, 34px)', gap: 4 }}>
          {lanes.map(lane => (
            <span key={lane} style={{ color: bucketColor(lane), fontSize: 10, fontWeight: 800, letterSpacing: 1, alignSelf: 'center' }}>
              {bucketLabel(lane).toUpperCase()}
            </span>
          ))}
        </div>
        <div style={{ position: 'relative', minWidth: 0 }}>
          <div style={{ display: 'grid', gridTemplateRows: 'repeat(4, 34px)', gap: 4 }}>
            {lanes.map(lane => (
              <div key={lane} style={{ position: 'relative', background: '#120a09', border: `1px solid ${C.border}`, borderRadius: 3 }}>
                {events.filter(event => (event.score_bucket || 'other') === lane).map(event => {
                  const minute = Math.min(end, Math.max(start, Number(event.match_minute ?? start)));
                  const left = ((minute - start) / (end - start)) * 100;
                  const selected = selectedId === event.event_id;
                  return (
                    <button
                      key={event.event_id}
                      type="button"
                      title={`${minuteLabel(event.match_minute)} ${event.player}: ${event.metric_name}`}
                      onClick={() => onSelect(event)}
                      style={{
                        position: 'absolute', left: `${left}%`, top: '50%', transform: 'translate(-50%, -50%)',
                        width: selected ? 15 : 11, height: selected ? 15 : 11, borderRadius: '50%',
                        border: selected ? `3px solid ${C.text}` : '2px solid #120907',
                        background: bucketColor(lane), cursor: 'pointer', padding: 0,
                        boxShadow: selected ? `0 0 0 3px ${bucketColor(lane)}55` : 'none', zIndex: selected ? 3 : 1,
                      }}
                    />
                  );
                })}
              </div>
            ))}
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 5, color: C.muted, fontSize: 10 }}>
            {ticks.map(tick => <span key={tick}>{tick}′</span>)}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function MatchStory() {
  const [seasons, setSeasons] = useState([]);
  const [season, setSeason] = useState('');
  const [matches, setMatches] = useState([]);
  const [sessionId, setSessionId] = useState('');
  const [story, setStory] = useState(null);
  const [bucket, setBucket] = useState('all');
  const [player, setPlayer] = useState('all');
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [selectedWindow, setSelectedWindow] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    staffApiFetch('/api/seasons')
      .then(payload => {
        const items = Array.isArray(payload) ? payload : payload.seasons || [];
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
      .catch(err => { setError(err.message); setLoading(false); });
  }, [season]);

  useEffect(() => {
    if (!sessionId) return;
    staffApiFetch(`/api/match-story/${sessionId}`)
      .then(data => {
        setStory(data);
        setSelectedWindow(strongestFlowWindow(data.flow, data.events || []));
        setLoading(false);
      })
      .catch(err => { setError(err.message); setLoading(false); });
  }, [sessionId]);

  const players = useMemo(() => [...new Set((story?.events || []).map(event => event.player).filter(Boolean))].sort(), [story]);
  const filtered = useMemo(() => (story?.events || []).filter(event => {
    const eventBucket = ['aset', 'peak', 'set_piece'].includes(event.score_bucket) ? event.score_bucket : 'other';
    return (bucket === 'all' || eventBucket === bucket) && (player === 'all' || event.player === player);
  }), [story, bucket, player]);
  const firstHalf = filtered.filter(event => Number(event.match_minute ?? 0) < 45);
  const secondHalf = filtered.filter(event => Number(event.match_minute ?? 0) >= 45);
  const timelineEnd = Math.max(90, Math.ceil(Math.max(90, ...secondHalf.map(event => Number(event.match_minute || 90))) / 5) * 5);
  const pulseEnd = Math.max(90, Math.ceil(Math.max(90, ...(story?.events || []).map(event => Number(event.match_minute || 90))) / 5) * 5);
  const match = story?.match;

  const control = { background: C.surface2, border: `1px solid ${C.border}`, color: C.text, padding: '8px 10px', borderRadius: 4 };

  return (
    <div style={{ minHeight: '100vh', background: C.bg, color: C.text, padding: '24px 28px', fontFamily: "Inter, system-ui, sans-serif" }}>
      <div style={{ maxWidth: 1240, margin: '0 auto' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', gap: 20, alignItems: 'flex-start', marginBottom: 22, flexWrap: 'wrap' }}>
          <div>
            <div style={{ color: C.gold, fontSize: 11, letterSpacing: 2.5, fontWeight: 800 }}>COFC MATCH ANALYSIS</div>
            <h1 style={{ margin: '5px 0 4px', fontSize: 30, letterSpacing: 1 }}>MATCH STORY</h1>
            <div style={{ color: C.muted, fontSize: 13 }}>A chronological, source-traceable view of what counted and when.</div>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <select value={season} onChange={e => {
              setLoading(true);
              setError('');
              setStory(null);
              setSelectedEvent(null);
              setSelectedWindow(0);
              setSeason(e.target.value);
            }} style={control}>
              {seasons.map(item => <option key={item} value={item}>{item} Season</option>)}
            </select>
            <select value={sessionId} onChange={e => {
              setLoading(true);
              setError('');
              setSelectedEvent(null);
              setSelectedWindow(0);
              setSessionId(e.target.value);
            }} style={{ ...control, minWidth: 230 }}>
              {!matches.length && <option value="">No matches available</option>}
              {matches.map(item => <option key={item.session_id} value={item.session_id}>{item.date} · {item.opponent}</option>)}
            </select>
          </div>
        </div>

        {match && (
          <div style={{ background: `linear-gradient(110deg, ${C.surface2}, ${C.surface})`, border: `1px solid ${C.border}`, padding: '18px 22px', marginBottom: 14 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 16 }}>
              <div>
                <div style={{ color: C.muted, fontSize: 11, letterSpacing: 1.5 }}>{match.date} · {match.competition || 'Match'} · {match.home ? 'HOME' : 'AWAY'}</div>
                <div style={{ fontSize: 22, fontWeight: 800, marginTop: 5 }}>COFC vs {match.opponent}</div>
              </div>
              <div style={{ fontSize: 30, fontWeight: 900, color: C.gold }}>
                {match.goals_for ?? '–'} <span style={{ color: C.muted }}>:</span> {match.goals_against ?? '–'}
              </div>
              <div style={{ display: 'flex', gap: 24 }}>
                {[['EVENTS', story.summary.events], ['PLAYERS', story.summary.players], ['COUG', score(story.summary.total)]].map(([label, value]) => (
                  <div key={label} style={{ textAlign: 'right' }}><div style={{ color: C.muted, fontSize: 9, letterSpacing: 1.5 }}>{label}</div><strong style={{ fontSize: 18 }}>{value}</strong></div>
                ))}
              </div>
            </div>
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 300px', gap: 14 }}>
          <div style={{ background: C.surface, border: `1px solid ${C.border}`, padding: 20, minWidth: 0 }}>
            {story?.summary && <PeakCoverage summary={story.summary} />}
            {story?.flow?.available ? (
              <OptaMatchFlow
                flow={story.flow}
                selectedWindow={selectedWindow}
                onSelectWindow={setSelectedWindow}
              />
            ) : !!story?.events?.length && (
              <MatchPulse
                events={story.events}
                endMinute={pulseEnd}
                selectedWindow={selectedWindow}
                onSelectWindow={setSelectedWindow}
              />
            )}
            <div style={{ display: 'flex', gap: 8, justifyContent: 'space-between', marginBottom: 18, flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
                {['all', 'aset', 'peak', 'set_piece', 'other'].map(item => (
                  <button key={item} type="button" onClick={() => setBucket(item)} style={{
                    background: bucket === item ? bucketColor(item === 'all' ? 'other' : item) : 'transparent',
                    color: bucket === item ? C.bg : C.muted, border: `1px solid ${bucket === item ? 'transparent' : C.border}`,
                    padding: '6px 10px', fontSize: 10, fontWeight: 800, letterSpacing: 1, cursor: 'pointer',
                  }}>{item === 'all' ? 'ALL' : bucketLabel(item).toUpperCase()}</button>
                ))}
              </div>
              <select value={player} onChange={e => setPlayer(e.target.value)} style={control}>
                <option value="all">All players</option>
                {players.map(item => <option key={item} value={item}>{item}</option>)}
              </select>
            </div>

            {loading ? <div style={{ padding: 60, textAlign: 'center', color: C.muted }}>LOADING MATCH EVENTS…</div>
              : error ? <div style={{ padding: 40, color: C.aset }}>{error}</div>
              : !story?.events?.length ? <div style={{ padding: 60, textAlign: 'center', color: C.muted }}>No player events are loaded for this match yet.</div>
              : <div style={{ display: 'grid', gap: 24 }}>
                  <TimelineHalf half={1} events={firstHalf} selectedId={selectedEvent?.event_id} onSelect={setSelectedEvent} endMinute={45} />
                  <TimelineHalf half={2} events={secondHalf} selectedId={selectedEvent?.event_id} onSelect={setSelectedEvent} endMinute={timelineEnd} />
                </div>}
          </div>

          <aside style={{ background: C.surface, border: `1px solid ${C.border}`, padding: 18 }}>
            <div style={{ color: C.gold, fontSize: 10, letterSpacing: 2, fontWeight: 800, marginBottom: 14 }}>EVENT DETAIL</div>
            {selectedEvent ? <>
              <div style={{ fontSize: 28, fontWeight: 900 }}>{minuteLabel(selectedEvent.match_minute)}</div>
              <div style={{ marginTop: 10, fontSize: 18, fontWeight: 800 }}>{selectedEvent.player}</div>
              <div style={{ color: bucketColor(selectedEvent.score_bucket), fontWeight: 800, marginTop: 4 }}>{selectedEvent.metric_name}</div>
              <div style={{ borderTop: `1px solid ${C.border}`, marginTop: 18, paddingTop: 14, display: 'grid', gap: 10, fontSize: 12 }}>
                <div><span style={{ color: C.muted }}>Outcome</span><br />{selectedEvent.outcome || 'Not supplied'}</div>
                <div><span style={{ color: C.muted }}>Contribution</span><br />{selectedEvent.contribution === null ? 'Unweighted evidence' : score(selectedEvent.contribution)}</div>
                <div><span style={{ color: C.muted }}>Source</span><br />{selectedEvent.source_platform || selectedEvent.source_name || 'Source pending'}</div>
                <div><span style={{ color: C.muted }}>Labels</span><br />{selectedEvent.labels?.join(' · ') || 'None'}</div>
              </div>
            </> : <div style={{ color: C.muted, fontSize: 13, lineHeight: 1.6 }}>Select an event marker to inspect the player, outcome, scoring contribution and source evidence.</div>}
          </aside>
        </div>
      </div>
    </div>
  );
}
