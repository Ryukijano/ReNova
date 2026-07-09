import React, { useState } from 'react';
import { API_BASE_URL } from './config';

function App() {
  const [disease, setDisease] = useState('cystic fibrosis');
  const [mock, setMock] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [results, setResults] = useState([]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResults([]);

    try {
      const response = await fetch(`${API_BASE_URL}/inference/renova`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ disease, mock }),
      });

      if (!response.ok) {
        throw new Error(`API Error: ${response.status} ${response.statusText}`);
      }

      const data = await response.json();
      if (data.status === 'success') {
        const sortedResults = (data.results || []).sort((a, b) => b.composite_score - a.composite_score);
        setResults(sortedResults);
      } else {
        throw new Error(data.message || 'Pipeline failed to return a success status');
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
      <header style={{ borderBottom: '2px solid #eaeaea', paddingBottom: '10px', marginBottom: '20px' }}>
        <h1 style={{ margin: 0, color: '#1a73e8' }}>ReNova ADMET Pipeline</h1>
        <p style={{ color: '#5f6368', margin: '5px 0 0 0' }}>Repurposing and ADMET prediction pipeline runner</p>
      </header>

      <form onSubmit={handleSubmit} style={{ display: 'flex', gap: '15px', alignItems: 'center', flexWrap: 'wrap', background: '#f8f9fa', padding: '15px', borderRadius: '8px', marginBottom: '20px', border: '1px solid #e0e0e0' }}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
          <label htmlFor="disease-input" style={{ fontWeight: 'bold', fontSize: '14px' }}>Disease Name</label>
          <input
            id="disease-input"
            type="text"
            value={disease}
            onChange={(e) => setDisease(e.target.value)}
            required
            style={{ padding: '8px 12px', border: '1px solid #ccc', borderRadius: '4px', width: '250px' }}
          />
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '20px' }}>
          <input
            id="mock-checkbox"
            type="checkbox"
            checked={mock}
            onChange={(e) => setMock(e.target.checked)}
            style={{ width: '18px', height: '18px' }}
          />
          <label htmlFor="mock-checkbox" style={{ fontWeight: 'bold', fontSize: '14px', cursor: 'pointer' }}>Mock Mode</label>
        </div>

        <button
          type="submit"
          disabled={loading}
          style={{
            marginTop: '20px',
            padding: '10px 20px',
            background: loading ? '#ccc' : '#1a73e8',
            color: '#fff',
            border: 'none',
            borderRadius: '4px',
            fontWeight: 'bold',
            cursor: loading ? 'not-allowed' : 'pointer',
            transition: 'background 0.2s'
          }}
        >
          {loading ? 'Running...' : 'Run ADMET Pipeline'}
        </button>
      </form>

      {loading && (
        <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '40px', background: '#f1f3f4', borderRadius: '8px', marginBottom: '20px' }}>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px' }}>
            <div style={{ border: '4px solid #f3f3f3', borderTop: '4px solid #1a73e8', borderRadius: '50%', width: '40px', height: '40px', animation: 'spin 1s linear infinite' }} />
            <span style={{ fontWeight: '500', color: '#3c4043' }}>Executing ADMET repurposing pipeline. This may take a minute...</span>
          </div>
          <style>{`
            @keyframes spin {
              0% { transform: rotate(0deg); }
              100% { transform: rotate(360deg); }
            }
          `}</style>
        </div>
      )}

      {error && (
        <div style={{ background: '#fce8e6', border: '1px solid #f28b82', color: '#c5221f', padding: '15px', borderRadius: '8px', marginBottom: '20px', fontWeight: '500' }}>
          Error: {error}
        </div>
      )}

      {results.length > 0 && (
        <div>
          <h2 style={{ color: '#202124', borderBottom: '1px solid #e0e0e0', paddingBottom: '8px' }}>Pipeline Results (Sorted by Composite Score)</h2>
          <div style={{ overflowX: 'auto', border: '1px solid #e0e0e0', borderRadius: '8px' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', background: '#fff' }}>
              <thead>
                <tr style={{ background: '#f8f9fa', borderBottom: '2px solid #e0e0e0' }}>
                  <th style={{ padding: '12px 15px', fontSize: '14px', fontWeight: 'bold' }}>Compound Name</th>
                  <th style={{ padding: '12px 15px', fontSize: '14px', fontWeight: 'bold' }}>ChEMBL ID</th>
                  <th style={{ padding: '12px 15px', fontSize: '14px', fontWeight: 'bold' }}>SMILES</th>
                  <th style={{ padding: '12px 15px', fontSize: '14px', fontWeight: 'bold' }}>Target Genes</th>
                  <th style={{ padding: '12px 15px', fontSize: '14px', fontWeight: 'bold' }}>pChEMBL Value</th>
                  <th style={{ padding: '12px 15px', fontSize: '14px', fontWeight: 'bold' }}>Clinical Phase</th>
                  <th style={{ padding: '12px 15px', fontSize: '14px', fontWeight: 'bold' }}>Toxicity Score</th>
                  <th style={{ padding: '12px 15px', fontSize: '14px', fontWeight: 'bold' }}>RO5 Pass</th>
                  <th style={{ padding: '12px 15px', fontSize: '14px', fontWeight: 'bold' }}>BBB Perm.</th>
                  <th style={{ padding: '12px 15px', fontSize: '14px', fontWeight: 'bold' }}>Top Adverse Reactions</th>
                  <th style={{ padding: '12px 15px', fontSize: '14px', fontWeight: 'bold' }}>Active Trials</th>
                  <th style={{ padding: '12px 15px', fontSize: '14px', fontWeight: 'bold', background: '#e8f0fe', color: '#1a73e8' }}>Composite Score</th>
                </tr>
              </thead>
              <tbody>
                {results.map((item, idx) => (
                  <tr key={item.chembl_id || idx} style={{ borderBottom: '1px solid #f1f3f4', fontSize: '13px' }}>
                    <td style={{ padding: '12px 15px', fontWeight: '500' }}>{item.compound_name}</td>
                    <td style={{ padding: '12px 15px' }}>
                      <a href={`https://www.ebi.ac.uk/chembl/compound_report_card/${item.chembl_id}/`} target="_blank" rel="noopener noreferrer" style={{ color: '#1a73e8', textDecoration: 'none' }}>
                        {item.chembl_id}
                      </a>
                    </td>
                    <td style={{ padding: '12px 15px', fontFamily: 'monospace', maxWidth: '150px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={item.smiles}>
                      {item.smiles}
                    </td>
                    <td style={{ padding: '12px 15px' }}>{item.target_genes}</td>
                    <td style={{ padding: '12px 15px' }}>{item.pchembl_value !== null && item.pchembl_value !== undefined ? Number(item.pchembl_value).toFixed(3) : 'N/A'}</td>
                    <td style={{ padding: '12px 15px' }}>{item.clinical_phase}</td>
                    <td style={{ padding: '12px 15px' }}>{item.toxicity_score !== null && item.toxicity_score !== undefined ? Number(item.toxicity_score).toFixed(3) : 'N/A'}</td>
                    <td style={{ padding: '12px 15px' }}>
                      <span style={{ padding: '3px 8px', borderRadius: '4px', background: item.ro5_pass ? '#e6f4ea' : '#fce8e6', color: item.ro5_pass ? '#137333' : '#c5221f', fontWeight: 'bold', fontSize: '11px' }}>
                        {item.ro5_pass ? 'Yes' : 'No'}
                      </span>
                    </td>
                    <td style={{ padding: '12px 15px' }}>{item.bbb_permeability !== null && item.bbb_permeability !== undefined ? Number(item.bbb_permeability).toFixed(3) : 'N/A'}</td>
                    <td style={{ padding: '12px 15px', maxWidth: '150px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={item.top_adverse_reactions}>
                      {item.top_adverse_reactions || 'None'}
                    </td>
                    <td style={{ padding: '12px 15px' }}>{item.active_trial_count}</td>
                    <td style={{ padding: '12px 15px', background: '#e8f0fe', color: '#1a73e8', fontWeight: 'bold' }}>{item.composite_score !== null && item.composite_score !== undefined ? Number(item.composite_score).toFixed(4) : 'N/A'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
