import { useEffect, useMemo, useState } from 'react';

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';
const FALLBACK_SEASON = '2026';

const C = {
  bg: '#120907', surface: '#1d0d0c', surface2: '#291210', border: '#4a2722',
  garnet: '#9f182c', gold: '#cfb53b', text: '#f8eee5', muted: '#b89987',
  aset: '#e34b5f', peak: '#e5bf39', set_piece: '#65b5a6', other: '#9d87c7',
};

async function apiFetch(path) {
  const response = await fetch(`${API}${path}`);
  if (!response.ok) throw new Error(`API ${response.status}: ${path}`);
  return response.json();
}

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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    apiFetch('/api/seasons')
      .then(items => {
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
    apiFetch(`/api/team/matches?season=${season}`)
      .then(items => {
        setMatches(items);
        setSessionId(items[0]?.session_id || '');
        if (!items.length) setLoading(false);
      })
      .catch(err => { setError(err.message); setLoading(false); });
  }, [season]);

  useEffect(() => {
    if (!sessionId) return;
    apiFetch(`/api/match-story/${sessionId}`)
      .then(data => { setStory(data); setLoading(false); })
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
              setSeason(e.target.value);
            }} style={control}>
              {seasons.map(item => <option key={item} value={item}>{item} Season</option>)}
            </select>
            <select value={sessionId} onChange={e => {
              setLoading(true);
              setError('');
              setSelectedEvent(null);
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
