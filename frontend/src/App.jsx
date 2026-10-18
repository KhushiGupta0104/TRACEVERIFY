import { useCallback, useEffect, useState } from 'react';
import { api } from './services/api.js';
import Header from './components/Header.jsx';
import SetupPage from './pages/SetupPage.jsx';
import ResultsPage from './pages/ResultsPage.jsx';
import { DEFAULT_PARAMS } from './components/SettingsForm.jsx';

// Hash routes: #/  (setup)  |  #/investigations/<id>[/<eventId>]  (results)
function parseHash() {
  const m = window.location.hash.match(/^#\/investigations\/(\d+)(?:\/(\d+))?/);
  return m ? { view: 'results', id: Number(m[1]), eventId: m[2] ? Number(m[2]) : null } : { view: 'setup' };
}

export default function App() {
  const [route, setRoute] = useState(parseHash);
  const [apiStatus, setApiStatus] = useState('pending');
  const [dataset, setDataset] = useState(null);
  const [seeds, setSeeds] = useState(null);
  const [seedsError, setSeedsError] = useState(null);
  const [selectedSeed, setSelectedSeed] = useState(null);
  const [params, setParams] = useState(DEFAULT_PARAMS);
  const [lastInvestigationId, setLastInvestigationId] = useState(null);

  useEffect(() => {
    const onHash = () => {
      setRoute(parseHash());
      window.scrollTo(0, 0);
    };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  const loadSeeds = useCallback(() => {
    setSeedsError(null);
    api.seeds()
      .then((s) => {
        setSeeds(s);
        setSelectedSeed((cur) => cur ?? s[0] ?? null);
      })
      .catch(setSeedsError);
  }, []);

  useEffect(() => {
    api.health().then(() => setApiStatus('ok')).catch(() => setApiStatus('down'));
    api.dataset().then(setDataset).catch(() => {});
    // Most recent stored investigation, so "Results" stays available after a page reload.
    api.recent().then((list) => setLastInvestigationId((cur) => cur ?? list[0]?.id ?? null)).catch(() => {});
    loadSeeds();
  }, [loadSeeds]);

  useEffect(() => {
    if (route.view === 'results') setLastInvestigationId(route.id);
  }, [route]);

  return (
    <>
      <Header
        view={route.view}
        resultsHref={lastInvestigationId ? `#/investigations/${lastInvestigationId}` : null}
        apiStatus={apiStatus}
        dataset={dataset}
      />
      {route.view === 'results' ? (
        <ResultsPage
          key={route.id}
          investigationId={route.id}
          initialEventId={route.eventId}
          onInvestigation={(inv) => setLastInvestigationId(inv.id)}
        />
      ) : (
        <SetupPage
          seeds={seeds}
          seedsError={seedsError}
          reloadSeeds={loadSeeds}
          params={params}
          setParams={setParams}
          selectedSeed={selectedSeed}
          setSelectedSeed={setSelectedSeed}
          onCreated={(inv) => {
            setLastInvestigationId(inv.id);
            window.location.hash = `#/investigations/${inv.id}`;
          }}
        />
      )}
    </>
  );
}
