import React, { useState } from 'react';
import { createStitches, keyframes } from '@stitches/react';
import { API_BASE_URL } from './config';

// -------------------------------------------------------------
// Stitches Design System & Theme
// -------------------------------------------------------------
const { styled, css } = createStitches({
  theme: {
    colors: {
      bgMain: '#08090f',
      bgCard: 'rgba(15, 17, 28, 0.7)',
      textPrimary: '#f8fafc',
      textSecondary: '#94a3b8',
      brand: '#8b5cf6',
      brandHover: '#7c3aed',
      brandGlow: 'rgba(139, 92, 246, 0.35)',
      accent: '#06b6d4',
      accentGlow: 'rgba(6, 182, 212, 0.2)',
      successBg: 'rgba(16, 185, 129, 0.1)',
      successText: '#10b981',
      dangerBg: 'rgba(239, 68, 68, 0.1)',
      dangerText: '#ef4444',
      border: 'rgba(255, 255, 255, 0.06)',
      tableHeaderBg: 'rgba(30, 41, 59, 0.5)',
      inputBg: '#1e293b',
    },
    fonts: {
      sans: 'Outfit, Inter, system-ui, -apple-system, sans-serif',
    },
    radii: {
      sm: '6px',
      md: '12px',
      lg: '20px',
      full: '9999px',
    },
    shadows: {
      card: '0 8px 32px 0 rgba(0, 0, 0, 0.37)',
      glow: '0 0 20px rgba(139, 92, 246, 0.15)',
    },
    transitions: {
      smooth: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
    }
  }
});

// Animations
const spin = keyframes({
  '0%': { transform: 'rotate(0deg)' },
  '100%': { transform: 'rotate(360deg)' }
});

const pulse = keyframes({
  '0%, 100%': { opacity: 0.6 },
  '50%': { opacity: 1 }
});

const fadeInUp = keyframes({
  '0%': { opacity: 0, transform: 'translateY(10px)' },
  '100%': { opacity: 1, transform: 'translateY(0)' }
});

// -------------------------------------------------------------
// Styled Components using Stitches
// -------------------------------------------------------------

const AppContainer = styled('div', {
  fontFamily: '$sans',
  background: 'radial-gradient(circle at 50% 0%, #1e1b4b 0%, $bgMain 60%)',
  color: '$textPrimary',
  minHeight: '100vh',
  padding: '40px 20px',
  boxSizing: 'border-box',
});

const Wrapper = styled('div', {
  maxWidth: '1200px',
  margin: '0 auto',
});

const Header = styled('header', {
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  textAlign: 'center',
  marginBottom: '40px',
  animation: `${fadeInUp} 0.6s ease-out`,
});

const Badge = styled('div', {
  background: '$brandGlow',
  color: '#c084fc',
  padding: '6px 14px',
  borderRadius: '$full',
  fontSize: '13px',
  fontWeight: 600,
  letterSpacing: '0.05em',
  textTransform: 'uppercase',
  border: '1px solid rgba(192, 132, 252, 0.2)',
  marginBottom: '16px',
});

const Title = styled('h1', {
  fontSize: '42px',
  fontWeight: 800,
  margin: 0,
  background: 'linear-gradient(to right, #ffffff, #c084fc, #818cf8)',
  WebkitBackgroundClip: 'text',
  WebkitTextFillColor: 'transparent',
  letterSpacing: '-0.02em',
});

const Subtitle = styled('p', {
  color: '$textSecondary',
  fontSize: '16px',
  marginTop: '10px',
  maxWidth: '600px',
  lineHeight: 1.6,
});

const FormCard = styled('form', {
  background: '$bgCard',
  backdropFilter: 'blur(16px)',
  border: '1px solid $border',
  borderRadius: '$lg',
  padding: '24px',
  boxShadow: '$card',
  display: 'flex',
  gap: '20px',
  alignItems: 'flex-end',
  flexWrap: 'wrap',
  marginBottom: '30px',
  animation: `${fadeInUp} 0.8s ease-out`,
});

const FormGroup = styled('div', {
  display: 'flex',
  flexDirection: 'column',
  gap: '8px',
  flex: '1 1 250px',
});

const Label = styled('label', {
  fontSize: '14px',
  fontWeight: 600,
  color: '$textSecondary',
});

const Input = styled('input', {
  background: '$inputBg',
  border: '1px solid $border',
  borderRadius: '$md',
  padding: '12px 16px',
  color: '$textPrimary',
  fontSize: '15px',
  fontFamily: '$sans',
  transition: '$smooth',
  '&:focus': {
    outline: 'none',
    borderColor: '$brand',
    boxShadow: '$glow',
  }
});

const ToggleContainer = styled('div', {
  display: 'flex',
  alignItems: 'center',
  gap: '12px',
  cursor: 'pointer',
  padding: '10px 0',
  userSelect: 'none',
});

const ToggleSwitch = styled('div', {
  width: '44px',
  height: '24px',
  borderRadius: '$full',
  background: '$inputBg',
  border: '1px solid $border',
  position: 'relative',
  transition: '$smooth',
  variants: {
    active: {
      true: {
        background: '$brand',
        borderColor: '$brand',
      }
    }
  }
});

const ToggleCircle = styled('div', {
  width: '16px',
  height: '16px',
  borderRadius: '$full',
  background: '$textPrimary',
  position: 'absolute',
  top: '3px',
  left: '4px',
  transition: '$smooth',
  variants: {
    active: {
      true: {
        transform: 'translateX(18px)',
      }
    }
  }
});

const SubmitButton = styled('button', {
  background: 'linear-gradient(135deg, $brand, $brandHover)',
  color: '$white',
  border: 'none',
  borderRadius: '$md',
  padding: '14px 28px',
  fontSize: '15px',
  fontWeight: 700,
  cursor: 'pointer',
  transition: '$smooth',
  boxShadow: '$glow',
  '&:hover': {
    transform: 'translateY(-2px)',
    filter: 'brightness(1.1)',
  },
  '&:disabled': {
    background: '#475569',
    cursor: 'not-allowed',
    transform: 'none',
    boxShadow: 'none',
  }
});

const LoadingCard = styled('div', {
  background: '$bgCard',
  border: '1px solid $border',
  borderRadius: '$lg',
  padding: '40px',
  textAlign: 'center',
  display: 'flex',
  flexDirection: 'column',
  alignItems: 'center',
  gap: '16px',
  boxShadow: '$card',
  animation: `${pulse} 1.5s infinite`,
});

const Spinner = styled('div', {
  border: '4px solid rgba(255,255,255,0.05)',
  borderTop: '4px solid $brand',
  borderRadius: '$full',
  width: '48px',
  height: '48px',
  animation: `${spin} 1s linear infinite`,
});

const ErrorCard = styled('div', {
  background: '$dangerBg',
  border: '1px solid rgba(239, 68, 68, 0.2)',
  color: '$dangerText',
  padding: '16px 20px',
  borderRadius: '$md',
  marginBottom: '20px',
  fontWeight: 500,
  fontSize: '15px',
  animation: `${fadeInUp} 0.4s ease-out`,
});

const TableSection = styled('section', {
  animation: `${fadeInUp} 0.8s ease-out`,
});

const TableHeaderContainer = styled('div', {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  marginBottom: '16px',
});

const TableTitle = styled('h2', {
  fontSize: '22px',
  fontWeight: 700,
  margin: 0,
});

const TableCard = styled('div', {
  background: '$bgCard',
  border: '1px solid $border',
  borderRadius: '$lg',
  overflow: 'hidden',
  boxShadow: '$card',
});

const ScrollableTable = styled('div', {
  overflowX: 'auto',
});

const StyledTable = styled('table', {
  width: '100%',
  borderCollapse: 'collapse',
  textAlign: 'left',
});

const Th = styled('th', {
  background: '$tableHeaderBg',
  padding: '16px 20px',
  fontSize: '13px',
  fontWeight: 700,
  color: '$textSecondary',
  borderBottom: '2px solid $border',
  textTransform: 'uppercase',
  letterSpacing: '0.05em',
  variants: {
    highlight: {
      true: {
        color: '$accent',
      }
    }
  }
});

const Tr = styled('tr', {
  borderBottom: '1px solid $border',
  transition: '$smooth',
  '&:hover': {
    background: 'rgba(255, 255, 255, 0.02)',
  }
});

const Td = styled('td', {
  padding: '16px 20px',
  fontSize: '14px',
  color: '$textPrimary',
  variants: {
    highlight: {
      true: {
        color: '$accent',
        fontWeight: 'bold',
      }
    }
  }
});

const CodeText = styled('span', {
  fontFamily: 'monospace',
  background: '#0f172a',
  padding: '4px 8px',
  borderRadius: '$sm',
  fontSize: '13px',
  color: '#38bdf8',
});

const StatusBadge = styled('span', {
  padding: '4px 10px',
  borderRadius: '$full',
  fontSize: '12px',
  fontWeight: 700,
  variants: {
    type: {
      success: {
        background: '$successBg',
        color: '$successText',
      },
      danger: {
        background: '$dangerBg',
        color: '$dangerText',
      }
    }
  }
});

const TextLink = styled('a', {
  color: '$brand',
  textDecoration: 'none',
  fontWeight: 600,
  transition: '$smooth',
  '&:hover': {
    color: '$brandHover',
    textDecoration: 'underline',
  }
});

// -------------------------------------------------------------
// Main Application component
// -------------------------------------------------------------
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
    <AppContainer>
      <Wrapper>
        <Header>
          <Badge>AI-Driven Drug Repurposing</Badge>
          <Title>ReNova Engine</Title>
          <Subtitle>
            Retrieve disease targets, screen bioactive chemical profiles, run deep learning ADMET prediction pipelines, and verify clinical validity.
          </Subtitle>
        </Header>

        <FormCard onSubmit={handleSubmit}>
          <FormGroup>
            <Label htmlFor="disease-input">Disease Query</Label>
            <Input
              id="disease-input"
              type="text"
              value={disease}
              onChange={(e) => setDisease(e.target.value)}
              placeholder="e.g., cystic fibrosis"
              required
            />
          </FormGroup>

          <ToggleContainer onClick={() => setMock(!mock)}>
            <ToggleSwitch active={mock}>
              <ToggleCircle active={mock} />
            </ToggleSwitch>
            <Label style={{ cursor: 'pointer' }}>Use API Simulation (Mock)</Label>
          </ToggleContainer>

          <SubmitButton type="submit" disabled={loading}>
            {loading ? 'Processing...' : 'Execute Pipeline'}
          </SubmitButton>
        </FormCard>

        {loading && (
          <LoadingCard>
            <Spinner />
            <div style={{ fontWeight: 600 }}>Analyzing Biomarkers & Running GNN Inference</div>
            <Subtitle style={{ margin: 0 }}>This can take up to a minute depending on database queries...</Subtitle>
          </LoadingCard>
        )}

        {error && (
          <ErrorCard>
            ⚠️ {error}
          </ErrorCard>
        )}

        {results.length > 0 && (
          <TableSection>
            <TableHeaderContainer>
              <TableTitle>Candidate Rankings</TableTitle>
              <Subtitle style={{ margin: 0 }}>{results.length} compounds identified and analyzed</Subtitle>
            </TableHeaderContainer>
            
            <TableCard>
              <ScrollableTable>
                <StyledTable>
                  <thead>
                    <tr>
                      <Th>Compound</Th>
                      <Th>ChEMBL ID</Th>
                      <Th>SMILES</Th>
                      <Th>Target Genes</Th>
                      <Th>pChEMBL</Th>
                      <Th>Phase</Th>
                      <Th>Tox Score</Th>
                      <Th>RO5 Pass</Th>
                      <Th>BBB Perm.</Th>
                      <Th>Adverse Reactions</Th>
                      <Th>Active Trials</Th>
                      <Th highlight={true}>Composite</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.map((item, idx) => (
                      <Tr key={item.chembl_id || idx}>
                        <Td style={{ fontWeight: 600 }}>{item.compound_name}</Td>
                        <Td>
                          <TextLink href={`https://www.ebi.ac.uk/chembl/compound_report_card/${item.chembl_id}/`} target="_blank" rel="noopener noreferrer">
                            {item.chembl_id}
                          </TextLink>
                        </Td>
                        <Td>
                          <CodeText title={item.smiles}>
                            {item.smiles && item.smiles.length > 12 ? `${item.smiles.slice(0, 12)}...` : item.smiles}
                          </CodeText>
                        </Td>
                        <Td>{item.target_genes}</Td>
                        <Td>{item.pchembl_value !== null && item.pchembl_value !== undefined ? Number(item.pchembl_value).toFixed(2) : 'N/A'}</Td>
                        <Td>{item.clinical_phase}</Td>
                        <Td>{item.toxicity_score !== null && item.toxicity_score !== undefined ? Number(item.toxicity_score).toFixed(2) : 'N/A'}</Td>
                        <Td>
                          <StatusBadge type={item.ro5_pass ? 'success' : 'danger'}>
                            {item.ro5_pass ? 'Pass' : 'Fail'}
                          </StatusBadge>
                        </Td>
                        <Td>{item.bbb_permeability !== null && item.bbb_permeability !== undefined ? Number(item.bbb_permeability).toFixed(2) : 'N/A'}</Td>
                        <Td style={{ color: '$textSecondary', fontSize: '13px' }} title={item.top_adverse_reactions}>
                          {item.top_adverse_reactions && item.top_adverse_reactions.length > 20 ? `${item.top_adverse_reactions.slice(0, 20)}...` : item.top_adverse_reactions || 'None'}
                        </Td>
                        <Td>{item.active_trial_count}</Td>
                        <Td highlight={true}>
                          {item.composite_score !== null && item.composite_score !== undefined ? Number(item.composite_score).toFixed(4) : 'N/A'}
                        </Td>
                      </Tr>
                    ))}
                  </tbody>
                </StyledTable>
              </ScrollableTable>
            </TableCard>
          </TableSection>
        )}
      </Wrapper>
    </AppContainer>
  );
}

export default App;
