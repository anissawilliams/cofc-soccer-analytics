import { useEffect, useMemo, useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, Cell,
  CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { cachedApiFetch } from './apiCache';
import MatchStory from './MatchStory.jsx';
import { staffApiFetch, staffLogin, staffLogout, verifyStaffSession } from './staffApi';

const T = {
  garnet: '#800000',
  gold: '#CFB53B',
  goldText: '#8B7500',
  success: '#166534',
};

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000';

async function apiFetch(path) {
  return cachedApiFetch(API, path);
}

const UPCOMING_MATCHES_2026 = [
  { id: '2026-08-07_wofford', date: '2026-08-07', opponent: 'Wofford', short: 'WOF', homeAway: 'A', competition: 'Exhibition', conference: false, venue: 'Spartanburg' },
  { id: '2026-08-10_usc_lancaster', date: '2026-08-10', opponent: 'USC Lancaster', short: 'USCL', homeAway: 'H', competition: 'Exhibition', conference: false, venue: 'Ralph Lundy Field' },
  { id: '2026-08-14_jacksonville', date: '2026-08-14', opponent: 'Jacksonville', short: 'JAX', homeAway: 'A', competition: 'Exhibition', conference: false, venue: 'Jacksonville' },
  { id: '2026-08-20_davidson', date: '2026-08-20', opponent: 'Davidson', short: 'Davidson', homeAway: 'H', competition: 'Non-Conference', conference: false, venue: 'Ralph Lundy Field' },
  { id: '2026-08-23_florida_gulf_coast', date: '2026-08-23', opponent: 'Florida Gulf Coast', short: 'FGCU', homeAway: 'H', competition: 'Non-Conference', conference: false, venue: 'Ralph Lundy Field' },
  { id: '2026-08-28_campbell', date: '2026-08-28', opponent: 'Campbell', short: 'Campbell', homeAway: 'H', competition: 'CAA', conference: true, venue: 'Ralph Lundy Field' },
  { id: '2026-09-05_william_mary', date: '2026-09-05', opponent: 'William & Mary', short: 'W&M', homeAway: 'A', competition: 'CAA', conference: true, venue: 'Williamsburg' },
  { id: '2026-09-08_winthrop', date: '2026-09-08', opponent: 'Winthrop', short: 'Winthrop', homeAway: 'H', competition: 'Non-Conference', conference: false, venue: 'Ralph Lundy Field' },
  { id: '2026-09-12_usc_upstate', date: '2026-09-12', opponent: 'USC Upstate', short: 'USC Upstate', homeAway: 'A', competition: 'Non-Conference', conference: false, venue: 'Spartanburg' },
  { id: '2026-09-15_south_carolina', date: '2026-09-15', opponent: 'South Carolina', short: 'South Carolina', homeAway: 'A', competition: 'Non-Conference', conference: false, venue: 'Columbia' },
  { id: '2026-09-19_elon', date: '2026-09-19', opponent: 'Elon', short: 'Elon', homeAway: 'A', competition: 'CAA', conference: true, venue: 'Elon' },
  { id: '2026-09-27_uncw', date: '2026-09-27', opponent: 'UNCW', short: 'UNCW', homeAway: 'H', competition: 'CAA', conference: true, venue: 'Ralph Lundy Field' },
  { id: '2026-10-03_campbell', date: '2026-10-03', opponent: 'Campbell', short: 'Campbell', homeAway: 'A', competition: 'CAA', conference: true, venue: 'Buies Creek' },
  { id: '2026-10-06_furman', date: '2026-10-06', opponent: 'Furman', short: 'Furman', homeAway: 'H', competition: 'Non-Conference', conference: false, venue: 'Ralph Lundy Field' },
  { id: '2026-10-10_elon', date: '2026-10-10', opponent: 'Elon', short: 'Elon', homeAway: 'H', competition: 'CAA', conference: true, venue: 'Ralph Lundy Field' },
  { id: '2026-10-13_north_florida', date: '2026-10-13', opponent: 'North Florida', short: 'North Florida', homeAway: 'A', competition: 'Non-Conference', conference: false, venue: 'Jacksonville' },
  { id: '2026-10-17_william_mary', date: '2026-10-17', opponent: 'William & Mary', short: 'W&M', homeAway: 'H', competition: 'CAA', conference: true, venue: 'Ralph Lundy Field' },
  { id: '2026-10-24_uncw', date: '2026-10-24', opponent: 'UNCW', short: 'UNCW', homeAway: 'A', competition: 'CAA', conference: true, venue: 'Wilmington' },
  { id: '2026-10-30_mercer', date: '2026-10-30', opponent: 'Mercer', short: 'Mercer', homeAway: 'A', competition: 'Non-Conference', conference: false, venue: 'Macon' },
];

export default function StaffPortal({ analytics }) {
  return (
    <StaffGate>
      <StaffDashboard analytics={analytics} />
    </StaffGate>
  );
}

function StaffGate({ children }) {
  const [entered, setEntered] = useState(false);
  const [checking, setChecking] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [value, setValue] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    verifyStaffSession().then(valid => {
      setEntered(valid);
      setChecking(false);
    });
  }, []);

  async function submit(e) {
    e.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      await staffLogin(value);
      setEntered(true);
      setValue('');
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
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
        <button type="submit" style={styles.primaryButton} disabled={checking || submitting}>
          {checking ? 'Checking session…' : submitting ? 'Signing in…' : 'Enter Staff Area'}
        </button>
      </form>
      <p style={styles.note}>
        Staff access is validated by the backend. Sessions expire automatically.
      </p>
    </div>
  );
}

function StaffDashboard({ analytics }) {
  const [section, setSection] = useState('analytics');
  const sections = [
    ['analytics', 'Team Analytics'],
    ['simulator', 'Prediction Simulator'],
    ['story', 'Match Story'],
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
            staffLogout();
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
      {section === 'analytics' && analytics}
      {section === 'story' && <MatchStory />}
      {section === 'scouting' && (
        <StaffPlaceholder
          title="Scouting"
          body="Opponent reports, readiness status, match shells, and pre-match prep will surface here from pipeline/scouting outputs."
        />
      )}
      {section === 'development' && (
        <PlayerDevelopmentTrace />
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

function PlayerDevelopmentTrace() {
  const [season, setSeason] = useState('');
  const [seasons, setSeasons] = useState([]);
  const [players, setPlayers] = useState([]);
  const [selectedAthleteId, setSelectedAthleteId] = useState('');
  const [trace, setTrace] = useState(null);
  const [matchHistory, setMatchHistory] = useState([]);
  const [loadingPlayers, setLoadingPlayers] = useState(true);
  const [loadingTrace, setLoadingTrace] = useState(false);
  const [error, setError] = useState('');
  const [showScoringReference, setShowScoringReference] = useState(false);

  useEffect(() => {
    apiFetch('/api/seasons')
      .then(data => {
        const available = Array.isArray(data) ? data : data.seasons || [];
        const activeSeason = Array.isArray(data) ? available[0] : data.active_season;
        const normalized = Array.from(new Set([activeSeason, ...available].map(String).filter(Boolean)))
          .sort((a, b) => b.localeCompare(a, undefined, { numeric: true }));
        const seasonsToUse = normalized.length ? normalized : ['2026'];
        setSeasons(seasonsToUse);
        setSeason(seasonsToUse[0]);
      })
      .catch(() => {
        setSeasons(['2026']);
        setSeason('2026');
      });
  }, []);

  useEffect(() => {
    if (!season) return;
    apiFetch(`/api/coug-leaderboard-with-minutes/${season}`)
      .then(data => {
        setPlayers(data);
        setLoadingTrace(data.length > 0);
        setSelectedAthleteId(current => current || data[0]?.athlete_id || '');
        setLoadingPlayers(false);
      })
      .catch(e => {
        setError(e.message);
        setLoadingPlayers(false);
      });
  }, [season]);

  useEffect(() => {
    if (!selectedAthleteId || !season) return;
    Promise.all([
      staffApiFetch(`/api/player-coug-trace/${selectedAthleteId}?season=${season}`),
      staffApiFetch(`/api/player-match-history/${selectedAthleteId}?season=${season}`),
    ])
      .then(([traceData, matchData]) => {
        setTrace(traceData);
        setMatchHistory(matchData);
        setLoadingTrace(false);
      })
      .catch(e => {
        setError(e.message);
        setLoadingTrace(false);
      });
  }, [selectedAthleteId, season]);

  const selectedPlayer = players.find(player => player.athlete_id === selectedAthleteId);
  const matchGroups = useMemo(
    () => groupEventsByMatch(trace?.events || [], matchHistory),
    [trace, matchHistory],
  );
  const cougTableTotal = Number(selectedPlayer?.total_score || 0);
  const eventLedgerTotal = Number(trace?.summary?.total || 0);
  const rollupDifference = Math.abs(cougTableTotal - eventLedgerTotal);
  const rollupAligned = rollupDifference < 0.01;

  return (
    <div style={styles.developmentShell}>
      <div style={styles.developmentHeader}>
        <div>
          <h2 style={{ color: T.garnet, margin: 0 }}>Player COUG Trace</h2>
          <p style={{ ...styles.muted, margin: '0.35rem 0 0' }}>
            Player conversation prep: what counted, how it was weighted, and where the evidence came from.
          </p>
        </div>
        <div style={styles.traceControls}>
          <select value={season} onChange={e => {
            setLoadingPlayers(true);
            setLoadingTrace(false);
            setError('');
            setTrace(null);
            setSeason(e.target.value);
            setSelectedAthleteId('');
          }} style={styles.select}>
            {seasons.map(item => <option key={item} value={item}>{item} Season</option>)}
          </select>
          <select
            value={selectedAthleteId}
            onChange={e => {
              setLoadingTrace(true);
              setError('');
              setTrace(null);
              setSelectedAthleteId(e.target.value);
            }}
            style={styles.select}
            disabled={loadingPlayers || players.length === 0}
          >
            {players.length === 0 && <option value="">No players</option>}
            {players.map(player => (
              <option key={player.athlete_id} value={player.athlete_id}>
                {player.name} - {player.position || 'POS'}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && <div style={styles.errorBanner}>{error}</div>}

      {loadingPlayers || loadingTrace ? (
        <div style={styles.card}>Loading player trace...</div>
      ) : !selectedPlayer ? (
        <div style={styles.card}>No COUG scores are available for this season yet.</div>
      ) : (
        <>
          <div style={styles.traceSummaryGrid}>
            <TraceTile label="Total" value={selectedPlayer.total_score} tone="total" />
            <TraceTile label="ASET" value={selectedPlayer.aset_score} tone="aset" />
            <TraceTile label="PEAK" value={selectedPlayer.peak_score} tone="peak" />
            <TraceTile label="Set Piece" value={selectedPlayer.set_piece_score} />
            <TraceTile label="Events" value={trace?.summary?.event_count ?? 0} />
            <TraceTile label="Minutes" value={selectedPlayer.minutes_played} suffix="'" />
          </div>

          <div style={styles.rollupGuide}>
            <div style={styles.rollupGuideText}>
              <strong>How this rolls into the COUG table</strong>
              <span>Scoring event → category contribution → match contribution → season COUG total</span>
            </div>
            <div style={rollupAligned ? styles.rollupAligned : styles.rollupReview}>
              <span>COUG table {formatScore(cougTableTotal)}</span>
              <span>Event ledger {formatScore(eventLedgerTotal)}</span>
              <strong>{rollupAligned ? 'Aligned' : `Review ${formatScore(rollupDifference)} difference`}</strong>
            </div>
          </div>

          <div style={styles.tracePanel}>
            <div style={styles.panelHeader}>
              <div>
                <h3 style={styles.panelTitle}>Category Totals From Events</h3>
                <span style={styles.panelMeta}>
                  {trace?.summary?.weighted_event_count ?? 0} weighted rows
                </span>
              </div>
            </div>
            <div style={styles.categoryRows}>
              {['aset', 'peak', 'set_piece', 'positional', 'load', 'team'].map(bucket => (
                <div key={bucket} style={styles.categoryRow}>
                  <span>{formatBucket(bucket)}</span>
                  <strong>{formatScore(trace?.summary?.[bucket] || 0)}</strong>
                </div>
              ))}
            </div>
            <div style={styles.positionalNote}>
              <strong>What is Positional?</strong>
              <span>
                Role-specific, event-derived metrics assigned through the active metric definitions and weights.
                This screen reports the official calculated value; it does not calculate a separate positional score.
              </span>
            </div>
          </div>

          <div style={styles.tracePanel}>
            <div style={styles.panelHeader}>
              <div>
                <h3 style={styles.panelTitle}>Match Contributions</h3>
                <span style={styles.panelMeta}>Open a match to review its event ledger</span>
              </div>
              <span style={styles.panelMeta}>{matchGroups.length} matches</span>
            </div>

            {(trace?.events || []).length === 0 ? (
              <p style={styles.muted}>
                No player-level event rows are loaded yet. The panel is ready for 2026 once athlete_event provenance is populated.
              </p>
            ) : (
              <div style={styles.matchLedger}>
                {matchGroups.map((match, index) => (
                  <details key={match.sessionId} open={index === 0} style={styles.matchDisclosure}>
                    <summary style={styles.matchSummary}>
                      <div>
                        <strong style={styles.matchTitle}>{match.label}</strong>
                        <span style={styles.matchDate}>{match.dateLabel}</span>
                      </div>
                      <div style={styles.matchSummaryStats}>
                        <span>{match.events.length} events</span>
                        <strong>{formatScore(match.score)}</strong>
                      </div>
                    </summary>
                    <div style={styles.matchEventBody}>
                      {Object.entries(groupEvents(match.events)).map(([bucket, events]) => (
                        <div key={bucket}>
                          <div style={{ ...styles.ledgerBucket, color: bucketColor(bucket) }}>
                            {formatBucket(bucket)} ({events.length})
                          </div>
                          {events.map(event => <EventRow key={event.event_id} event={event} />)}
                        </div>
                      ))}
                    </div>
                  </details>
                ))}
              </div>
            )}
          </div>

          <div style={styles.referenceFooter}>
            <button
              type="button"
              onClick={() => setShowScoringReference(current => !current)}
              style={styles.referenceLink}
              aria-expanded={showScoringReference}
              aria-controls="scoring-reference"
            >
              {showScoringReference ? 'Hide scoring reference' : 'View included event families'}
            </button>
            <span>Reference only · active scoring configuration</span>
          </div>

          {showScoringReference && (
            <div id="scoring-reference" style={styles.referencePanel}>
              <div style={styles.panelHeader}>
                <div>
                  <h3 style={styles.panelTitle}>Included Event Families</h3>
                  <span style={styles.panelMeta}>Reference from the active scoring configuration</span>
                </div>
              </div>
              <div style={styles.ruleGrid}>
                {(trace?.score_rules || []).map(rule => (
                  <div key={rule.bucket} style={styles.ruleBlock}>
                    <div style={{ ...styles.ruleBucket, color: bucketColor(rule.bucket) }}>{rule.bucket}</div>
                    <div style={styles.ruleLabel}>{rule.label}</div>
                    <div style={styles.ruleEvents}>
                      {rule.events.map(eventName => <span key={eventName}>{eventName}</span>)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function TraceTile({ label, value, tone, suffix = '' }) {
  const color = tone === 'aset' ? '#c0263b' : tone === 'peak' ? T.goldText : tone === 'total' ? T.garnet : '#111827';
  const display = label === 'Minutes' || label === 'Events'
    ? `${Math.round(value || 0)}${suffix}`
    : formatScore(value || 0);
  return (
    <div style={styles.traceTile}>
      <div style={styles.traceTileLabel}>{label}</div>
      <div style={{ ...styles.traceTileValue, color }}>{display}</div>
    </div>
  );
}

function EventRow({ event }) {
  const reviewStatuses = new Set(['needs_confirmation', 'proxy_review', 'duplicate', 'unreviewed']);
  const reviewNeeded = event.review_status
    ? reviewStatuses.has(event.review_status) || event.weight == null
    : event.manual_tag_required || !event.coach_confirmed || event.weight == null;
  const explanation = event.coach_explanation || formatContributionExplanation(event);
  const technicalNote = event.technical_notes || event.metric_notes || event.weight_notes;
  return (
    <div style={styles.eventRow}>
      <div>
        <div style={styles.eventTitle}>
          <span>{event.metric_name}</span>
          {event.aset_letter && <span style={styles.smallChip}>ASET {event.aset_letter}</span>}
          {event.peak_phase && <span style={styles.smallChip}>PEAK {event.peak_phase}</span>}
          {reviewNeeded && <span style={styles.reviewChip}>Review</span>}
        </div>
        <div style={styles.eventMeta}>
          {event.session_date || 'No date'} · Match time {formatTime(event.event_time)} · {event.source_platform || event.source_name || 'source pending'} · {event.collection_method || 'method pending'}
        </div>
        {explanation && (
          <div style={styles.eventNotes}>{explanation}</div>
        )}
        {technicalNote && (
          <details style={styles.technicalDetails}>
            <summary>Technical details</summary>
            <div>{technicalNote}</div>
          </details>
        )}
      </div>
      <div style={styles.eventMath}>
        <span>{formatScore(event.raw_value)} x {event.weight == null ? '-' : formatScore(event.weight)}</span>
        <strong>{event.calculated_score == null ? '-' : formatScore(event.calculated_score)}</strong>
      </div>
    </div>
  );
}

function formatContributionExplanation(event) {
  if (event.calculated_score == null || event.weight == null) {
    return 'Recorded as event evidence; no active scoring contribution was returned.';
  }
  const points = formatScore(event.calculated_score);
  const direction = Number(event.calculated_score) < 0 ? 'reduced the score by' : 'contributed';
  return `${event.metric_name || 'This event'} ${direction} ${points.replace('-', '')} points.`;
}

function groupEvents(events) {
  return events.reduce((groups, event) => {
    const bucket = event.score_bucket || 'team';
    groups[bucket] = groups[bucket] || [];
    groups[bucket].push(event);
    return groups;
  }, {});
}

function groupEventsByMatch(events, matchHistory = []) {
  const historyBySession = new Map(
    matchHistory.filter(match => match.session_id).map(match => [match.session_id, match]),
  );
  const historyByDate = new Map(
    matchHistory.filter(match => match.session_date).map(match => [match.session_date, match]),
  );
  const matches = new Map();
  events.forEach(event => {
    const sessionId = event.session_id || `undated-${event.session_date || 'unknown'}`;
    const matchRecord = historyBySession.get(event.session_id) || historyByDate.get(event.session_date);
    if (!matches.has(sessionId)) {
      matches.set(sessionId, {
        sessionId,
        label: matchRecord?.opponent || event.competition || 'Opponent pending',
        dateLabel: formatMatchDateLabel(event.session_date),
        events: [],
        score: 0,
      });
    }
    const match = matches.get(sessionId);
    match.events.push(event);
    if (event.calculated_score != null) {
      match.score += Number(event.calculated_score);
    }
  });
  return Array.from(matches.values());
}

function formatMatchDateLabel(value) {
  if (!value) return 'Date pending';
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function bucketColor(bucket) {
  const key = String(bucket).toLowerCase();
  if (key.includes('aset')) return '#c0263b';
  if (key.includes('peak')) return T.goldText;
  if (key.includes('set')) return '#7c6a3a';
  return '#374151';
}

function formatBucket(bucket) {
  return String(bucket)
    .replace(/_/g, ' ')
    .replace(/\b\w/g, letter => letter.toUpperCase());
}

function formatScore(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-';
  return Number(value).toFixed(2);
}

function formatTime(seconds) {
  if (seconds === null || seconds === undefined) return 'time pending';
  const total = Math.max(0, Math.round(Number(seconds)));
  const mins = Math.floor(total / 60);
  const secs = String(total % 60).padStart(2, '0');
  return `${mins}:${secs}`;
}

function PredictionSimulator() {
  const [selectedMatchId, setSelectedMatchId] = useState(UPCOMING_MATCHES_2026[0].id);
  const selectedMatch = UPCOMING_MATCHES_2026.find(match => match.id === selectedMatchId) || UPCOMING_MATCHES_2026[0];
  const [inputs, setInputs] = useState(() => baselineInputsForMatch(selectedMatch));

  const model = useMemo(() => scenarioModel(inputs), [inputs]);
  const baseline = useMemo(() => baselineInputsForMatch(selectedMatch), [selectedMatch]);
  const probabilityData = [
    { name: 'Win', value: Math.round(model.win * 100) },
    { name: 'Draw', value: Math.round(model.draw * 100) },
    { name: 'Loss', value: Math.round(model.loss * 100) },
  ];

  function chooseMatch(matchId) {
    const match = UPCOMING_MATCHES_2026.find(item => item.id === matchId) || UPCOMING_MATCHES_2026[0];
    setSelectedMatchId(match.id);
    setInputs(baselineInputsForMatch(match));
  }

  function update(key, value) {
    setInputs(current => ({ ...current, [key]: Number(value) }));
  }

  return (
    <div style={{ display: 'grid', gap: '1rem' }}>
      <div style={styles.matchSelectorCard}>
        <div>
          <h2 style={{ color: T.garnet, margin: 0 }}>Match Scenario</h2>
          <p style={{ ...styles.muted, margin: '0.35rem 0 0' }}>
            Start from a 2026 schedule baseline, then adjust the dials for lineup, tactical, or opponent assumptions.
          </p>
        </div>
        <select value={selectedMatchId} onChange={e => chooseMatch(e.target.value)} style={styles.select}>
          {UPCOMING_MATCHES_2026.map(match => (
            <option key={match.id} value={match.id}>
              {formatMatchDate(match.date)} - {match.homeAway === 'H' ? 'vs' : 'at'} {match.opponent}
            </option>
          ))}
        </select>
      </div>

      <div style={styles.matchMetaGrid}>
        <MetaTile label="Opponent" value={selectedMatch.opponent} />
        <MetaTile label="Date" value={formatMatchDate(selectedMatch.date)} />
        <MetaTile label="Site" value={selectedMatch.homeAway === 'H' ? 'Home' : 'Away'} />
        <MetaTile label="Competition" value={selectedMatch.competition} />
      </div>

      <div style={styles.simulatorGrid}>
        <div style={styles.card}>
          <div style={styles.dialCardHeader}>
            <h2 style={{ color: T.garnet, margin: 0 }}>Scenario Dials</h2>
            <button type="button" onClick={() => setInputs(baseline)} style={styles.resetButton}>
              Reset baseline
            </button>
          </div>
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
            Prototype model: Poisson scoreline simulation seeded from schedule context and adjusted by scenario dials. Use for coaching discussion, not final match odds.
          </p>
        </div>
      </div>
    </div>
    </div>
  );
}

function MetaTile({ label, value }) {
  return (
    <div style={styles.metaTile}>
      <div style={styles.metaLabel}>{label}</div>
      <div style={styles.metaValue}>{value}</div>
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

function baselineInputsForMatch(match) {
  const isHome = match.homeAway === 'H';
  const isConference = Boolean(match.conference);
  const isExhibition = match.competition === 'Exhibition';
  const opponentStrength = opponentStrengthAdjustment(match.short || match.opponent);

  return {
    cofcXg: roundDial(1.42 + (isHome ? 0.12 : -0.08) - opponentStrength * 0.12 + (isExhibition ? 0.08 : 0)),
    oppXg: roundDial(1.18 + (isHome ? -0.08 : 0.12) + opponentStrength * 0.16 - (isExhibition ? 0.05 : 0)),
    possession: Math.round(51 + (isHome ? 2 : -1) - opponentStrength * 2),
    shotEdge: Math.round((isHome ? 2 : 0) - opponentStrength * 2),
    pressEdge: isConference ? 1 : 0,
    setPieceEdge: isHome ? 1 : 0,
    home: isHome ? 0.15 : -0.05,
  };
}

function opponentStrengthAdjustment(opponentKey) {
  const key = String(opponentKey).toLowerCase();
  const known = {
    campbell: 0.35,
    'w&m': 0.3,
    elon: 0.25,
    uncw: 0.25,
    'south carolina': 0.45,
    'florida gulf coast': 0.2,
    davidson: 0.15,
    jacksonville: 0.1,
    mercer: 0.1,
    furman: 0.05,
    wofford: 0,
    winthrop: 0,
    'north florida': 0,
    'usc upstate': -0.05,
    'usc lancaster': -0.35,
  };
  return known[key] ?? 0;
}

function formatMatchDate(dateText) {
  const [year, month, day] = dateText.split('-').map(Number);
  return new Date(year, month - 1, day).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
  });
}

function roundDial(value) {
  return Number(value.toFixed(2));
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
  developmentShell: {
    display: 'grid',
    gap: '1rem',
  },
  developmentHeader: {
    display: 'grid',
    gridTemplateColumns: 'minmax(280px, 1fr) minmax(280px, 520px)',
    gap: '1rem',
    alignItems: 'center',
  },
  traceControls: {
    display: 'grid',
    gridTemplateColumns: 'minmax(130px, 0.7fr) minmax(180px, 1.3fr)',
    gap: '0.75rem',
  },
  errorBanner: {
    background: '#fef2f2',
    border: '1px solid #fecaca',
    borderRadius: 6,
    color: '#991b1b',
    padding: '0.75rem 1rem',
    fontSize: 13,
    fontWeight: 700,
  },
  traceSummaryGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(6, minmax(120px, 1fr))',
    gap: '0.75rem',
  },
  traceTile: {
    background: '#fff',
    border: '1px solid #e5e7eb',
    borderRadius: 8,
    padding: '0.85rem 1rem',
  },
  traceTileLabel: {
    color: '#6b7280',
    fontSize: 11,
    fontWeight: 900,
    letterSpacing: 0.8,
    textTransform: 'uppercase',
  },
  traceTileValue: {
    marginTop: 4,
    fontSize: 24,
    fontWeight: 900,
    fontVariantNumeric: 'tabular-nums',
  },
  tracePanel: {
    background: '#fff',
    border: '1px solid #e5e7eb',
    borderRadius: 8,
    padding: '1.1rem',
    boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
  },
  rollupGuide: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: '0.9rem',
    padding: '0.85rem 1rem',
    borderRadius: 8,
    background: '#f8fafc',
    border: '1px solid #e5e7eb',
    color: '#374151',
    fontSize: 12,
  },
  rollupGuideText: {
    display: 'grid',
    gap: 3,
  },
  rollupAligned: {
    display: 'flex',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: '0.65rem',
    color: '#166534',
  },
  rollupReview: {
    display: 'flex',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: '0.65rem',
    color: '#9a3412',
  },
  panelHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    gap: '1rem',
    alignItems: 'center',
    flexWrap: 'wrap',
    marginBottom: '0.85rem',
  },
  panelTitle: {
    margin: 0,
    color: '#111827',
    fontSize: 16,
  },
  panelMeta: {
    color: '#6b7280',
    fontSize: 12,
    fontWeight: 800,
    display: 'block',
    marginTop: 3,
  },
  referenceFooter: {
    display: 'flex',
    justifyContent: 'flex-end',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: '0.55rem',
    color: '#9ca3af',
    fontSize: 11,
  },
  referenceLink: {
    border: 0,
    background: 'transparent',
    color: '#6b7280',
    padding: 0,
    fontSize: 11,
    fontWeight: 800,
    cursor: 'pointer',
    textDecoration: 'underline',
    textUnderlineOffset: 2,
  },
  referencePanel: {
    background: '#fffcf2',
    border: '1px solid #eadca4',
    borderRadius: 8,
    padding: '1.1rem',
  },
  ruleGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(3, minmax(160px, 1fr))',
    gap: '0.75rem',
  },
  ruleBlock: {
    border: '1px solid #e5e7eb',
    borderRadius: 6,
    padding: '0.85rem',
    background: '#fafafa',
  },
  ruleBucket: {
    fontSize: 12,
    fontWeight: 900,
    letterSpacing: 1,
  },
  ruleLabel: {
    color: '#374151',
    fontSize: 12,
    fontWeight: 800,
    marginTop: 3,
  },
  ruleEvents: {
    display: 'grid',
    gap: 4,
    marginTop: 9,
    color: '#4b5563',
    fontSize: 12,
    lineHeight: 1.25,
  },
  categoryRows: {
    display: 'grid',
    gap: 8,
  },
  categoryRow: {
    display: 'flex',
    justifyContent: 'space-between',
    gap: '1rem',
    borderBottom: '1px solid #f3f4f6',
    paddingBottom: 8,
    color: '#374151',
    fontSize: 13,
  },
  positionalNote: {
    display: 'grid',
    gridTemplateColumns: 'max-content minmax(0, 1fr)',
    gap: '0.65rem',
    alignItems: 'start',
    marginTop: '0.9rem',
    padding: '0.75rem 0.85rem',
    borderRadius: 6,
    background: '#f8fafc',
    color: '#4b5563',
    fontSize: 12,
    lineHeight: 1.45,
  },
  matchLedger: {
    display: 'grid',
    gap: '0.65rem',
  },
  matchDisclosure: {
    border: '1px solid #e5e7eb',
    borderRadius: 7,
    overflow: 'hidden',
    background: '#fff',
  },
  matchSummary: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: '1rem',
    padding: '0.9rem 1rem',
    cursor: 'pointer',
    background: '#fafafa',
  },
  matchTitle: {
    display: 'block',
    color: '#111827',
    fontSize: 14,
  },
  matchDate: {
    display: 'block',
    color: '#6b7280',
    fontSize: 11,
    marginTop: 3,
  },
  matchSummaryStats: {
    display: 'flex',
    alignItems: 'center',
    gap: '0.8rem',
    color: '#6b7280',
    fontSize: 12,
    whiteSpace: 'nowrap',
  },
  matchEventBody: {
    display: 'grid',
    gap: '1rem',
    padding: '0.85rem 1rem 0.25rem',
  },
  ledgerBucket: {
    fontSize: 12,
    fontWeight: 900,
    letterSpacing: 1,
    textTransform: 'uppercase',
    marginBottom: 6,
  },
  eventRow: {
    display: 'grid',
    gridTemplateColumns: 'minmax(220px, 1fr) 116px',
    gap: '0.75rem',
    alignItems: 'start',
    borderTop: '1px solid #f3f4f6',
    padding: '0.75rem 0',
  },
  eventTitle: {
    display: 'flex',
    gap: 6,
    alignItems: 'center',
    flexWrap: 'wrap',
    color: '#111827',
    fontWeight: 900,
    fontSize: 13,
  },
  eventMeta: {
    color: '#6b7280',
    fontSize: 12,
    marginTop: 4,
  },
  eventNotes: {
    color: '#4b5563',
    fontSize: 12,
    lineHeight: 1.35,
    marginTop: 6,
  },
  technicalDetails: {
    color: '#6b7280',
    fontSize: 11,
    lineHeight: 1.35,
    marginTop: 6,
  },
  smallChip: {
    background: '#f3f4f6',
    color: '#374151',
    borderRadius: 4,
    padding: '2px 5px',
    fontSize: 10,
    fontWeight: 900,
  },
  reviewChip: {
    background: '#fffbeb',
    color: '#92400e',
    border: '1px solid #fde68a',
    borderRadius: 4,
    padding: '2px 5px',
    fontSize: 10,
    fontWeight: 900,
  },
  eventMath: {
    display: 'grid',
    gap: 4,
    justifyItems: 'end',
    color: '#6b7280',
    fontSize: 12,
    fontVariantNumeric: 'tabular-nums',
  },
  matchSelectorCard: {
    background: '#fff',
    border: '1px solid #e5e7eb',
    borderRadius: 8,
    padding: '1.25rem',
    boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
    display: 'grid',
    gridTemplateColumns: 'minmax(260px, 1fr) minmax(260px, 420px)',
    gap: '1rem',
    alignItems: 'center',
  },
  select: {
    width: '100%',
    padding: '0.75rem',
    border: '1px solid #d1d5db',
    borderRadius: 6,
    background: '#fff',
    color: '#111827',
    fontSize: 14,
    fontWeight: 700,
  },
  matchMetaGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(4, minmax(140px, 1fr))',
    gap: '0.75rem',
  },
  metaTile: {
    background: '#fff',
    border: '1px solid #e5e7eb',
    borderRadius: 8,
    padding: '0.85rem 1rem',
  },
  metaLabel: {
    color: '#6b7280',
    fontSize: 12,
    fontWeight: 800,
  },
  metaValue: {
    color: '#111827',
    fontSize: 16,
    fontWeight: 900,
    marginTop: 3,
  },
  simulatorGrid: {
    display: 'grid',
    gridTemplateColumns: 'minmax(280px, 0.9fr) minmax(320px, 1.1fr)',
    gap: '1.25rem',
  },
  dialCardHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    gap: '1rem',
    alignItems: 'center',
    marginBottom: '1rem',
  },
  resetButton: {
    border: '1px solid #d1d5db',
    background: '#fff',
    borderRadius: 6,
    padding: '0.45rem 0.65rem',
    cursor: 'pointer',
    color: '#374151',
    fontWeight: 800,
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
