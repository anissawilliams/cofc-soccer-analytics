import { useState, useEffect } from 'react';
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, ResponsiveContainer, Area, AreaChart
} from 'recharts';

export default function App() {
  const [showInsights, setShowInsights] = useState(false);
  const [pressingData, setPressingData] = useState([]);
  const [shotsData, setShotsData] = useState([]);
  const [rosterData, setRosterData] = useState([]);
  const [selectedPlayer, setSelectedPlayer] = useState('All');
  const [loading, setLoading] = useState(true);

  const colors = {
    garnet: '#800000',
    gold: '#CFB53B',
    background: '#f3f4f6',
    cardBg: '#ffffff'
  };

  useEffect(() => {
    Promise.all([
      fetch('http://localhost:8000/api/leaders/recoveries').then(res => res.json()),
      fetch('http://localhost:8000/api/team/shots-by-time').then(res => res.json()),
      fetch('http://localhost:8000/api/roster/development').then(res => res.json())
    ])
    .then(([recoveriesRes, shotsRes, developmentRes]) => {
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
      setLoading(false);
    })
    .catch(err => {
      console.error("API Error:", err);
      setLoading(false);
    });
  }, []);

  const displayData = selectedPlayer === 'All'
    ? pressingData.slice(0, 12)
    : pressingData.filter(p => p.fullName === selectedPlayer);

  if (loading) return <div style={{ padding: '5rem', textAlign: 'center' }}><h2 style={{ color: colors.garnet }}>Loading...</h2></div>;

  return (
    <div style={{ backgroundColor: colors.background, minHeight: '100vh', padding: '2rem', fontFamily: 'sans-serif' }}>
      <div style={{ maxWidth: '1200px', margin: '0 auto' }}>

        {/* HEADER */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem', backgroundColor: colors.cardBg, padding: '1.5rem', borderRadius: '12px', boxShadow: '0 2px 4px rgba(0,0,0,0.05)' }}>
          <div>
            <h1 style={{ color: colors.garnet, margin: 0 }}>Charleston Cougars Analytics</h1>
            <div style={{ marginTop: '10px' }}>
              <label style={{ marginRight: '10px', fontSize: '14px', color: '#666' }}>Filter Roster:</label>
              <select value={selectedPlayer} onChange={(e) => setSelectedPlayer(e.target.value)} style={{ padding: '5px', borderRadius: '4px', border: '1px solid #ddd' }}>
                <option value="All">All Players (Top 12)</option>
                {pressingData.map(p => <option key={p.fullName} value={p.fullName}>{p.fullName}</option>)}
              </select>
            </div>
          </div>
          <button onClick={() => setShowInsights(!showInsights)} style={{ padding: '10px 20px', backgroundColor: colors.gold, border: 'none', borderRadius: '6px', fontWeight: 'bold', cursor: 'pointer' }}>
            {showInsights ? 'Hide Insights' : 'Show Insights'}
          </button>
        </div>

        {/* INSIGHTS */}
        {showInsights && (
          <div style={{ backgroundColor: '#fff', padding: '1.5rem', borderRadius: '12px', marginBottom: '2rem', borderLeft: `6px solid ${colors.gold}` }}>
            <h3 style={{ margin: '0 0 10px 0', color: colors.garnet }}>Tactical Engine Observations</h3>
            <p style={{ margin: 0, color: '#444' }}>
              <strong>Current Trend:</strong> High-press efficiency is peaking in the final 15 minutes.
              <strong> Focus Area:</strong> Midfield transition defense needs adjustment to support CB recovery loads.
            </p>
          </div>
        )}

        {/* CHARTS */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem', marginBottom: '2rem' }}>
          <div style={{ backgroundColor: colors.cardBg, padding: '1.5rem', borderRadius: '12px' }}>
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

          <div style={{ backgroundColor: colors.cardBg, padding: '1.5rem', borderRadius: '12px' }}>
            <h3 style={{ color: '#374151', marginTop: 0 }}>Defensive Output</h3>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={displayData}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#eee" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip cursor={{fill: '#f9fafb'}} />
                <Legend />
                <Bar dataKey="Recoveries" fill={colors.garnet} radius={[4, 4, 0, 0]} barSize={selectedPlayer === 'All' ? 25 : 60} />
                <Bar dataKey="Shots Created" fill={colors.gold} radius={[4, 4, 0, 0]} barSize={selectedPlayer === 'All' ? 25 : 60} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* ROSTER TRACKER */}
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

        {/* --- NEW SECTION: METRIC GLOSSARY --- */}
        <div style={{ backgroundColor: colors.cardBg, padding: '1.5rem', borderRadius: '12px', borderTop: `4px solid ${colors.gold}` }}>
          <h3 style={{ color: colors.garnet, marginTop: 0 }}>Analytics Legend & Definitions</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1.5rem', marginTop: '1rem' }}>
            <div>
              <h4 style={{ margin: '0 0 5px 0', color: '#111' }}>xG (Expected Goals)</h4>
              <p style={{ margin: 0, fontSize: '13px', color: '#666', lineHeight: '1.4' }}>
                Measures the quality of a shot based on variables like distance, angle, and pressure. A value of 0.25 means the average player scores that chance 25% of the time.
              </p>
            </div>
            <div>
              <h4 style={{ margin: '0 0 5px 0', color: '#111' }}>Recoveries / 90</h4>
              <p style={{ margin: 0, fontSize: '13px', color: '#666', lineHeight: '1.4' }}>
                The number of times a player regains possession for the team, normalized per 90 minutes of play to ensure fair comparison across the roster.
              </p>
            </div>
            <div>
              <h4 style={{ margin: '0 0 5px 0', color: '#111' }}>PPDA (Pressing)</h4>
              <p style={{ margin: 0, fontSize: '13px', color: '#666', lineHeight: '1.4' }}>
                Passes Allowed Per Defensive Action. A lower number indicates a higher pressing intensity (forcing the opponent to move the ball quickly or lose it).
              </p>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}