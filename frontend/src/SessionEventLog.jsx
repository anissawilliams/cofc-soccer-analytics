import { useEffect, useMemo, useState } from 'react';
import { staffApiFetch } from './staffApi';

const GARNET = '#800000';
const GOLD = '#CFB53B';
const EVENT_TYPES = [
  ['yellow_card', 'Yellow card'],
  ['red_card', 'Red card'],
  ['injury', 'Injury / availability'],
  ['training_action', 'Training action'],
  ['coach_observation', 'Coach observation'],
  ['other', 'Other'],
];

const emptyForm = {
  session_id: '',
  athlete_id: '',
  event_type: 'yellow_card',
  minute: '',
  notes: '',
  recorded_by: '',
  weighted: false,
  metric_weight_id: '',
  raw_value: '1',
};

export default function SessionEventLog() {
  const [season, setSeason] = useState('');
  const [seasons, setSeasons] = useState([]);
  const [options, setOptions] = useState({ sessions: [], athletes: [], weights: [] });
  const [events, setEvents] = useState([]);
  const [form, setForm] = useState(emptyForm);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  useEffect(() => {
    staffApiFetch('/api/seasons')
      .then(payload => {
        const available = Array.isArray(payload) ? payload : payload.seasons || [];
        const active = Array.isArray(payload) ? available[0] : payload.active_season;
        const normalized = Array.from(new Set([active, ...available].map(String).filter(Boolean)))
          .sort((a, b) => b.localeCompare(a, undefined, { numeric: true }));
        setSeasons(normalized);
        setSeason(normalized[0] || '2026');
      })
      .catch(err => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    if (!season) return;
    setLoading(true);
    setError('');
    Promise.all([
      staffApiFetch(`/api/staff/session-events/options?season=${encodeURIComponent(season)}`),
      staffApiFetch(`/api/staff/session-events?season=${encodeURIComponent(season)}`),
    ])
      .then(([optionPayload, eventPayload]) => {
        setOptions(optionPayload);
        setEvents(eventPayload);
        setForm(current => ({
          ...emptyForm,
          recorded_by: current.recorded_by,
          session_id: optionPayload.sessions?.[0]?.id || '',
        }));
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  }, [season]);

  const selectedSession = options.sessions.find(item => item.id === form.session_id);
  const availableWeights = useMemo(() => options.weights.filter(weight => (
    !selectedSession
    || !weight.applies_to_session_type
    || weight.applies_to_session_type === 'both'
    || weight.applies_to_session_type === selectedSession.session_type
  )), [options.weights, selectedSession]);
  const selectedWeight = availableWeights.find(item => item.id === form.metric_weight_id);
  const proposedScore = selectedWeight
    ? Number(selectedWeight.weight) * Number(form.raw_value || 1)
    : null;

  function update(field, value) {
    setForm(current => ({ ...current, [field]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    setError('');
    setSuccess('');
    if (form.weighted && (!form.athlete_id || !form.metric_weight_id)) {
      setError('Choose an athlete and a COUG weight for a weighted event.');
      return;
    }
    setSaving(true);
    try {
      const payload = {
        session_id: form.session_id,
        athlete_id: form.athlete_id || null,
        event_type: form.event_type,
        metric_weight_id: form.weighted ? form.metric_weight_id : null,
        raw_value: form.weighted ? Number(form.raw_value || 1) : 1,
        event_time: form.minute === '' ? null : Number(form.minute) * 60,
        notes: form.notes || null,
        recorded_by: form.recorded_by || null,
      };
      await staffApiFetch('/api/staff/session-events', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      const refreshed = await staffApiFetch(`/api/staff/session-events?season=${encodeURIComponent(season)}`);
      setEvents(refreshed);
      setSuccess(form.weighted
        ? 'Event saved and queued for COUG score review.'
        : 'Event saved as an informational note.');
      setForm(current => ({
        ...emptyForm,
        session_id: current.session_id,
        recorded_by: current.recorded_by,
      }));
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={styles.shell}>
      <div style={styles.header}>
        <div>
          <h2 style={styles.title}>Staff Event Log</h2>
          <p style={styles.subtitle}>Record match or training events in one consistent place.</p>
        </div>
        <select value={season} onChange={event => setSeason(event.target.value)} style={styles.select}>
          {seasons.map(item => <option key={item} value={item}>{item} Season</option>)}
        </select>
      </div>

      {error && <div role="alert" style={styles.error}>{error}</div>}
      {success && <div role="status" style={styles.success}>{success}</div>}

      {loading ? (
        <div style={styles.card}>Loading event log…</div>
      ) : options.sessions.length === 0 ? (
        <div style={styles.card}>No sessions are available for the {season} season yet.</div>
      ) : (
        <div style={styles.grid}>
          <form onSubmit={submit} style={styles.card}>
            <h3 style={styles.cardTitle}>Add session event</h3>

            <Field label="Session">
              <select required value={form.session_id} onChange={event => update('session_id', event.target.value)} style={styles.input}>
                {options.sessions.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}
              </select>
            </Field>

            <div style={styles.twoColumns}>
              <Field label="Event type">
                <select value={form.event_type} onChange={event => update('event_type', event.target.value)} style={styles.input}>
                  {EVENT_TYPES.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </Field>
              <Field label={selectedSession?.session_type === 'match' ? 'Match minute (optional)' : 'Minute (optional)'}>
                <input type="number" min="0" max="180" step="0.1" value={form.minute} onChange={event => update('minute', event.target.value)} style={styles.input} placeholder="e.g. 64" />
              </Field>
            </div>

            <Field label="Athlete (optional for notes)">
              <select value={form.athlete_id} onChange={event => update('athlete_id', event.target.value)} style={styles.input}>
                <option value="">Team / session-wide</option>
                {options.athletes.map(item => (
                  <option key={item.id} value={item.id}>{item.name}{item.position ? ` · ${item.position}` : ''}</option>
                ))}
              </select>
            </Field>

            <label style={styles.toggleRow}>
              <input
                type="checkbox"
                checked={form.weighted}
                onChange={event => setForm(current => ({
                  ...current,
                  weighted: event.target.checked,
                  metric_weight_id: '',
                }))}
              />
              <span style={styles.toggleCopy}>
                <strong>Propose a COUG score contribution</strong>
                <small>Uses an approved weight and queues the entry for review.</small>
              </span>
            </label>

            {form.weighted && (
              <div style={styles.weightBox}>
                <Field label="COUG metric and weight">
                  <select required value={form.metric_weight_id} onChange={event => update('metric_weight_id', event.target.value)} style={styles.input}>
                    <option value="">Select approved weight…</option>
                    {availableWeights.map(item => (
                      <option key={item.id} value={item.id}>
                        {item.metric_name} · {Number(item.weight) > 0 ? '+' : ''}{item.weight}
                      </option>
                    ))}
                  </select>
                  {availableWeights.length === 0 && (
                    <span style={styles.helper}>No approved weights apply to this session type.</span>
                  )}
                </Field>
                <Field label="Count">
                  <input type="number" min="0.1" max="100" step="0.1" value={form.raw_value} onChange={event => update('raw_value', event.target.value)} style={styles.input} />
                </Field>
                {selectedWeight && (
                  <div style={styles.scorePreview}>
                    Proposed contribution: <strong>{proposedScore > 0 ? '+' : ''}{proposedScore.toFixed(2)}</strong>
                    <span>Pending review—not yet added to the published table.</span>
                  </div>
                )}
              </div>
            )}

            <Field label="Notes">
              <textarea value={form.notes} onChange={event => update('notes', event.target.value)} style={{ ...styles.input, minHeight: 92, resize: 'vertical' }} placeholder="What happened? Add context coaches will recognize." />
            </Field>

            <Field label="Recorded by (optional)">
              <input value={form.recorded_by} onChange={event => update('recorded_by', event.target.value)} style={styles.input} placeholder="Name or initials" />
            </Field>

            <button type="submit" disabled={saving} style={styles.button}>
              {saving ? 'Saving…' : 'Save event'}
            </button>
          </form>

          <div style={styles.card}>
            <div style={styles.listHeader}>
              <h3 style={styles.cardTitle}>Recent entries</h3>
              <span>{events.length}</span>
            </div>
            {events.length === 0 ? (
              <p style={styles.empty}>No events have been logged for {season}.</p>
            ) : (
              <div style={styles.eventList}>
                {events.map(item => <EventCard key={item.id} event={item} />)}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, children }) {
  return (
    <label style={styles.field}>
      <span>{label}</span>
      {children}
    </label>
  );
}

function EventCard({ event }) {
  const type = EVENT_TYPES.find(([value]) => value === event.event_type)?.[1]
    || event.event_type.replaceAll('_', ' ');
  return (
    <article style={styles.eventCard}>
      <div style={styles.eventTopline}>
        <strong>{type}</strong>
        <span style={event.score_status === 'pending_review' ? styles.pendingChip : styles.infoChip}>
          {event.score_status === 'pending_review' ? 'Score review' : 'Info'}
        </span>
      </div>
      <div style={styles.meta}>
        {event.session?.session_date} · {event.session?.session_type}
        {event.event_time != null ? ` · ${Math.round(event.event_time / 60)}'` : ''}
      </div>
      <div style={styles.athlete}>{event.athlete?.name || 'Team / session-wide'}</div>
      {event.metric_name && (
        <div style={styles.metric}>
          {event.metric_name} · proposed {event.proposed_score > 0 ? '+' : ''}{Number(event.proposed_score).toFixed(2)}
        </div>
      )}
      {event.notes && <p style={styles.notes}>{event.notes}</p>}
      <div style={styles.recordedBy}>Recorded by {event.recorded_by || 'Staff portal'}</div>
    </article>
  );
}

const styles = {
  shell: { display: 'grid', gap: '1rem' },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'end', gap: '1rem' },
  title: { color: GARNET, margin: 0 },
  subtitle: { color: '#6b7280', margin: '0.35rem 0 0' },
  select: { padding: '0.7rem', border: '1px solid #d1d5db', borderRadius: 7, background: '#fff', fontWeight: 700 },
  grid: { display: 'grid', gridTemplateColumns: 'minmax(320px, 0.9fr) minmax(320px, 1.1fr)', gap: '1rem', alignItems: 'start' },
  card: { background: '#fff', border: '1px solid #e5e7eb', borderRadius: 9, padding: '1.25rem', boxShadow: '0 1px 3px rgba(0,0,0,0.05)', display: 'grid', gap: '1rem' },
  cardTitle: { color: '#111827', margin: 0 },
  twoColumns: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' },
  field: { display: 'grid', gap: 5, color: '#374151', fontSize: 12, fontWeight: 800 },
  input: { width: '100%', boxSizing: 'border-box', padding: '0.7rem', border: '1px solid #d1d5db', borderRadius: 6, background: '#fff', color: '#111827', fontSize: 14 },
  helper: { color: '#92400e', fontSize: 11, fontWeight: 700 },
  toggleRow: { display: 'flex', gap: '0.65rem', alignItems: 'start', padding: '0.85rem', border: `1px solid ${GOLD}`, borderRadius: 7, background: '#fffbeb', color: '#374151', cursor: 'pointer' },
  toggleCopy: { display: 'grid', gap: 3, lineHeight: 1.35 },
  weightBox: { display: 'grid', gridTemplateColumns: 'minmax(0, 1fr) 90px', gap: '0.75rem', padding: '0.9rem', borderRadius: 7, background: '#f9fafb' },
  scorePreview: { gridColumn: '1 / -1', display: 'flex', flexWrap: 'wrap', gap: 6, color: '#374151', fontSize: 13 },
  button: { border: 0, borderRadius: 6, padding: '0.8rem 1rem', background: GARNET, color: '#fff', fontWeight: 900, cursor: 'pointer' },
  error: { padding: '0.8rem 1rem', borderRadius: 7, color: '#991b1b', background: '#fef2f2', border: '1px solid #fecaca' },
  success: { padding: '0.8rem 1rem', borderRadius: 7, color: '#166534', background: '#f0fdf4', border: '1px solid #bbf7d0' },
  listHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
  eventList: { display: 'grid', gap: '0.75rem' },
  eventCard: { border: '1px solid #e5e7eb', borderLeft: `4px solid ${GARNET}`, borderRadius: 7, padding: '0.9rem' },
  eventTopline: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', color: '#111827', textTransform: 'capitalize' },
  pendingChip: { background: '#fffbeb', color: '#92400e', borderRadius: 999, padding: '3px 8px', fontSize: 10, fontWeight: 900 },
  infoChip: { background: '#f3f4f6', color: '#4b5563', borderRadius: 999, padding: '3px 8px', fontSize: 10, fontWeight: 900 },
  meta: { color: '#6b7280', fontSize: 12, marginTop: 5, textTransform: 'capitalize' },
  athlete: { color: '#111827', fontWeight: 800, marginTop: 8 },
  metric: { color: GARNET, fontWeight: 800, fontSize: 13, marginTop: 4 },
  notes: { color: '#4b5563', fontSize: 13, lineHeight: 1.45, margin: '0.65rem 0' },
  recordedBy: { color: '#9ca3af', fontSize: 11 },
  empty: { color: '#6b7280', margin: 0 },
};
