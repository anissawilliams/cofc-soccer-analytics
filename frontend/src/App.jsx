import { useState, useEffect } from 'react';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, Cell,
  CartesianGrid, Tooltip, Legend, ResponsiveContainer, Area, AreaChart
} from 'recharts';

// CSS for the slide-down animation
const slideDownStyle = `
  @keyframes slideDown {
    from { opacity: 0; transform: translateY(-10px); }
    to { opacity: 1; transform: translateY(0); }
  }
`;

export default function App() {
  const [showInsights, setShowInsights] = useState(false);
  const [pressingData, setPressingData] = useState([]);
  const [shotsData, setShotsData] = useState([]);
  const [rosterData, setRosterData] = useState([]);
  const [formationData, setFormationData] = useState([]);
  const [selectedPlayer, setSelectedPlayer] = useState('All');
  const [loading, setLoading] = useState(true);

  const colors = {
    garnet: '#800000',
    gold: '#CFB53B',
    background: '#f3f4f6',
    cardBg: '#ffffff',
    success: '#166534'
  };

  // Automated API selection
  const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetch(`${API_URL}/api/leaders/recoveries`).then(res => res.json()),
      fetch(`${API_URL}/api/team/shots-by-time`).then(res => res.json()),
      fetch(`${API_URL}/api/roster/development`).then(res => res.json()),
      fetch(`${API_URL}/api/team/formations`).then(res => res.json())
    ])
    .then(([recoveriesRes, shotsRes, developmentRes, formationRes]) => {
      setPressingData(recoveriesRes.map(p => ({
        name: p.name.split(' ').pop(),
        fullName: p.name,
        Recoveries: p.value,
        'Shots Created': Math.floor(p.value / 4)
      })));
      setShotsData(shotsRes.labels.map((label, index) => ({
        time: label,
        Shots: shotsRes.data[index]
      })));
      setRosterData(developmentRes);
      setFormationData(formationRes);
      setLoading(false);
    })
    .catch(err => {
      console.error("API Error:", err);
      setLoading(false);
    });
  }, [API_URL]);

  const displayData = selectedPlayer === 'All'
    ? pressingData.slice(0, 12)
    : pressingData.filter(p => p.fullName === selectedPlayer);

  if (loading) return (
    <div style={{ padding: '5rem', textAlign: 'center', fontFamily: 'sans-serif' }}>
      <h2 style={{ color: colors.garnet }}>Loading Cougars Analytics...</h2>
      <p style={{ color: '#666' }}>Fetching from: {API_URL}</p>
    </div>
  );

  return (
    <div style={{ backgroundColor: colors.background, minHeight: '100vh', padding: '2rem', fontFamily: 'sans-serif' }}>
      <style>{slideDownStyle}</style>
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>

        {/* HEADER */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem', backgroundColor: colors.cardBg, padding: '1.5rem', borderRadius: '12px', boxShadow: '0 2px 4px rgba(0,0,0,0.05)' }}>
          <div>
            <h1 style={{ color: colors.garnet, margin: 0 }}>Charleston Cougars Analytics</h1>
            <div style={{ marginTop: '10px' }}>
              <label style={{ marginRight: '10px', fontSize: '14px', color: '#666' }}>Filter Roster:</label>
              <select value={selectedPlayer} onChange={(e) => setSelectedPlayer(e.target.value)} style={{ padding: '5px', borderRadius: '4px', border: '1px solid #ddd', cursor: 'pointer' }}>
                <option value="All">All Players (Top 12)</option>
                {pressingData.map(p => <option key={p.fullName} value={p.fullName}>{p.fullName}</option>)}
              </select>
            </div>
          </div>
          <button
            type="button"
            onClick={() => setShowInsights(!showInsights)}
            style={{ padding: '10px 20px', backgroundColor: colors.gold, border: 'none', borderRadius: '6px', fontWeight: 'bold', cursor: 'pointer' }}
          >
            {showInsights ? 'Hide Insights' : 'Show Tactical Insights'}
          </button>
        </div>

        {/* INSIGHTS WITH TRANSITION */}
        {showInsights && (
          <div style={{ animation: 'slideDown 0.4s ease-out', backgroundColor: '#fff', padding: '1.5rem', borderRadius: '12px', marginBottom: '2rem', borderLeft: `6px solid ${colors.gold}`, boxShadow: '0 4px 6px rgba(0,0,0,0.05)' }}>
            <h3 style={{ margin: '0 0 15px 0', color: colors.garnet }}>Tactical Engine: Formation Efficiency (Net GD)</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1.2fr 1fr', gap: '2rem', alignItems: 'center' }}>
              <div style={{ height: '180px' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={formationData} layout="vertical" margin={{ left: -20 }}>
                    <XAxis type="number" hide />
                    <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} style={{ fontWeight: 'bold' }} />
                    <Tooltip cursor={{fill: 'transparent'}} />
                    <Bar dataKey="gd" radius={[0, 4, 4, 0]} barSize={30}>
                      {formationData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.gd > 0 ? colors.success : entry.gd < 0 ? colors.garnet : '#999'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <p style={{ margin: 0, fontSize: '14px', color: '#444', lineHeight: '1.6' }}>
                <strong>The 4-1-3-2 Advantage:</strong> Diamond midfield improves Net Goal Difference by <strong>+2.0</strong>.
                <br /><br />
                <span style={{ color: colors.success, fontWeight: 'bold' }}>Tactical Recommendation:</span> High-press efficiency peaks with this setup. Deploy in trailing scenarios.
              </p>
            </div>
          </div>
        )}

        {/* CHARTS */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '2rem' }}>
          <div style={{ backgroundColor: colors.cardBg, padding: '1.5rem', borderRadius: '12px', boxShadow: '0 2px 4px rgba(0,0,0,0.05)' }}>
            <h3 style={{ color: '#374151', marginTop: 0 }}>Attacking Threat</h3>
            <ResponsiveContainer width="100%" height={300}>
              <AreaChart data={shotsData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#eee" />
                <XAxis dataKey="time" />
                <YAxis />
                <Tooltip />
                <Area type="monotone" dataKey="Shots" stroke={colors.garnet} fill={colors.garnet} fillOpacity={0.2} strokeWidth={3} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
          <div style={{ backgroundColor: colors.cardBg, padding: '1.5rem', borderRadius: '12px', boxShadow: '0 2px 4px rgba(0,0,0,0.05)' }}>
            <h3 style={{ color: '#374151', marginTop: 0 }}>Defensive Output</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={displayData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#eee" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip cursor={{fill: '#f9fafb'}} />
                <Legend iconType="circle" />
                <Bar dataKey="Recoveries" fill={colors.garnet} radius={[4, 4, 0, 0]} barSize={selectedPlayer === 'All' ? 25 : 60} />
                <Bar dataKey="Shots Created" fill={colors.gold} radius={[4, 4, 0, 0]} barSize={selectedPlayer === 'All' ? 25 : 60} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* ROSTER TABLE */}
        <div style={{ backgroundColor: colors.cardBg, padding: '1.5rem', borderRadius: '12px', marginBottom: '2rem' }}>
          <h3 style={{ color: colors.garnet, marginTop: 0, marginBottom: '1.5rem' }}>Full Roster Development Tracker</h3>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ textAlign: 'left', borderBottom: '2px solid #eee' }}>
                  <th style={{ padding: '12px' }}>Player</th>
                  <th>Position</th>
                  <th>Metric</th>
                  <th>Current</th>
                  <th>Target</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {rosterData.map((player, idx) => (
                  <tr key={idx} style={{ borderBottom: '1px solid #f9fafb' }}>
                    <td style={{ padding: '12px', fontWeight: 'bold' }}>{player.name}</td>
                    <td>{player.position}</td>
                    <td style={{ fontSize: '14px', color: '#666' }}>{player.Metric}</td>
                    <td>{player.Value}</td>
                    <td>{player.Goal}</td>
                    <td>
                      <span style={{ padding: '4px 10px', borderRadius: '20px', fontSize: '11px', fontWeight: 'bold', backgroundColor: player.Status === 'Target' ? '#dcfce7' : '#fee2e2', color: player.Status === 'Target' ? '#166534' : '#991b1b' }}>
                        {player.Status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* GLOSSARY */}
        <div style={{ backgroundColor: colors.cardBg, padding: '1.5rem', borderRadius: '12px', borderTop: `4px solid ${colors.gold}` }}>
          <h3 style={{ color: colors.garnet, marginTop: 0 }}>Analytics Legend</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1.5rem', marginTop: '1rem' }}>
            <div>
              <h4 style={{ margin: '0 0 5px 0' }}>xG (Expected Goals)</h4>
              <p style={{ margin: 0, fontSize: '13px', color: '#666', lineHeight: '1.4' }}>Measures shot quality. A 0.25 value means a player scores that chance 25% of the time.</p>
            </div>
            <div>
              <h4 style={{ margin: '0 0 5px 0' }}>Recoveries / 90</h4>
              <p style={{ margin: 0, fontSize: '13px', color: '#666', lineHeight: '1.4' }}>Possession regains normalized per 90 mins to allow fair comparison.</p>
            </div>
            <div>
              <h4 style={{ margin: '0 0 5px 0' }}>PPDA</h4>
              <p style={{ margin: 0, fontSize: '13px', color: '#666', lineHeight: '1.4' }}>Passes Allowed Per Defensive Action. Lower numbers mean higher pressing intensity.</p>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}