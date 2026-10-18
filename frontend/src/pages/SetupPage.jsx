import { useMemo, useState } from 'react';
import { api } from '../services/api.js';
import SeedList from '../components/SeedList.jsx';
import SettingsForm, { paramsValid } from '../components/SettingsForm.jsx';
import HowItWorks from '../components/HowItWorks.jsx';
import { ErrorState, InfoTip, Loading } from '../components/common.jsx';

const GUIDE_KEY = 'traceverify.guideHidden';
const readGuideHidden = () => {
  try { return window.localStorage.getItem(GUIDE_KEY) === '1'; } catch { return false; }
};
const writeGuideHidden = (hidden) => {
  try { window.localStorage.setItem(GUIDE_KEY, hidden ? '1' : '0'); } catch { /* storage unavailable: session-only */ }
};

export default function SetupPage({ seeds, seedsError, reloadSeeds, params, setParams, selectedSeed, setSelectedSeed, onCreated }) {
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState('');
  const [guideHidden, setGuideHidden] = useState(readGuideHidden);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!seeds || !q) return seeds;
    return seeds.filter((s) =>
      [s.user_name, s.src_computer, s.dst_computer].some((v) => (v ?? '').toLowerCase().includes(q)));
  }, [seeds, query]);

  const toggleGuide = (hidden) => {
    setGuideHidden(hidden);
    writeGuideHidden(hidden);
  };

  const run = async () => {
    setRunning(true);
    setError(null);
    try {
      onCreated(await api.start({ seed_event_id: selectedSeed.id, ...params }));
    } catch (e) {
      setError(e);
      setRunning(false);
    }
  };

  return (
    <main className="container setup">
      <header className="page-head">
        <div>
          <h1>New investigation</h1>
          <p>Find and explain evidence related to a known security event.</p>
        </div>
        {guideHidden && (
          <button className="btn ghost small" onClick={() => toggleGuide(false)} data-testid="show-guide">
            How it works
          </button>
        )}
      </header>

      {!guideHidden && <HowItWorks onDismiss={() => toggleGuide(true)} />}

      <div className="setup-grid">
        <section className="card seed-card">
          <div className="card-head">
            <h2>Starting event</h2>
            <InfoTip id="seed-tip">
              A known red-team event. The investigation searches around it for related authentication, process, DNS
              and network evidence.
            </InfoTip>
            {seeds && <span className="right subtle">{filtered.length === seeds.length ? `${seeds.length} events` : `${filtered.length} of ${seeds.length}`}</span>}
          </div>
          <div className="seed-search">
            <label className="search-field">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
                <circle cx="11" cy="11" r="7" />
                <path d="M20 20l-3.5-3.5" strokeLinecap="round" />
              </svg>
              <input
                type="text"
                placeholder="Search by user or computer, e.g. U748 or C1493"
                aria-label="Search starting events by user, source or destination computer"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Escape' && setQuery('')}
                data-testid="seed-search"
              />
              {query && (
                <button type="button" className="icon-btn" onClick={() => setQuery('')} aria-label="Clear search" data-testid="clear-search">
                  ✕
                </button>
              )}
            </label>
          </div>
          {seedsError && <ErrorState error={seedsError} onRetry={reloadSeeds} />}
          {!seeds && !seedsError && <Loading label="Loading events…" />}
          {seeds?.length === 0 && <div className="state">No red-team events have been ingested yet.</div>}
          {filtered?.length === 0 && seeds?.length > 0 && (
            <div className="state" data-testid="no-match">
              No events match “{query}”.
              <button className="btn small" onClick={() => setQuery('')}>Clear search</button>
            </div>
          )}
          {filtered?.length > 0 && <SeedList seeds={filtered} selectedId={selectedSeed?.id} onSelect={setSelectedSeed} />}
        </section>

        <aside className="card settings-card">
          <div className="card-head">
            <h2>Settings</h2>
          </div>
          <div className="card-body form">
            <SettingsForm params={params} onChange={setParams} idPrefix="setup" />
            {error && <div className="notice error" role="alert">{error.message}</div>}
            <button className="btn primary large" disabled={!selectedSeed || !paramsValid(params) || running}
              onClick={run} data-testid="run-investigation">
              {running ? <><span className="spinner" /> Running analysis…</> : 'Run investigation'}
            </button>
          </div>
        </aside>
      </div>
    </main>
  );
}
