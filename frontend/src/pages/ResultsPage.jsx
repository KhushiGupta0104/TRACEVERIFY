import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../services/api.js';
import Timeline from '../components/Timeline.jsx';
import EvidenceGraph from '../components/EvidenceGraph.jsx';
import EvidenceDetails from '../components/EvidenceDetails.jsx';
import RerunDrawer from '../components/RerunDrawer.jsx';
import StorySummary from '../components/StorySummary.jsx';
import { ErrorState, InfoTip, Loading, SourceBadge } from '../components/common.jsx';
import { readableTime, windowLabel } from '../utils/format.js';

const acceptedIds = (timeline) => new Set(timeline.filter((t) => t.status === 'accepted').map((t) => t.id));

// Default selection: the highest-scoring accepted evidence, so the details panel is never empty.
function defaultSelection(inv, timeline) {
  const top = inv.top_evidence?.[0]?.event?.id;
  if (top && timeline.some((t) => t.id === top)) return { kind: 'event', id: top };
  const seed = timeline.find((t) => t.is_seed);
  return seed ? { kind: 'event', id: seed.id } : null;
}

export default function ResultsPage({ investigationId, initialEventId, onInvestigation }) {
  const [data, setData] = useState(null); // { inv, timeline, relationships }
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selection, setSelection] = useState(initialEventId ? { kind: 'event', id: initialEventId } : null);
  const [centerOn, setCenterOn] = useState(null);
  const [view, setView] = useState('graph');
  const [fitRequest, setFitRequest] = useState(0);
  const [showExcluded, setShowExcluded] = useState(false);
  const [showSupporting, setShowSupporting] = useState(false);
  const [sortBy, setSortBy] = useState('time');
  const [drawer, setDrawer] = useState(false);
  const [rerunning, setRerunning] = useState(false);
  const [rerunError, setRerunError] = useState(null);
  const [change, setChange] = useState(null);

  const load = useCallback(async () => {
    const [inv, timeline, relationships] = await Promise.all([
      api.investigation(investigationId),
      api.timeline(investigationId, true),
      api.relationships(investigationId, 'all'),
    ]);
    setData({ inv, timeline, relationships });
    return { inv, timeline };
  }, [investigationId]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    setChange(null);
    load()
      .then(({ inv, timeline }) => setSelection((sel) => sel ?? defaultSelection(inv, timeline)))
      .catch(setError)
      .finally(() => setLoading(false));
  }, [load]);

  const rerun = async (params) => {
    setRerunning(true);
    setRerunError(null);
    const before = acceptedIds(data.timeline);
    try {
      onInvestigation(await api.rerun(investigationId, params));
      const { inv, timeline } = await load();
      const now = acceptedIds(timeline);
      setChange({
        added: [...now].filter((i) => !before.has(i)).length,
        removed: [...before].filter((i) => !now.has(i)).length,
      });
      setSelection((sel) =>
        sel?.kind === 'event' && timeline.some((t) => t.id === sel.id && t.status !== 'rejected')
          ? sel
          : defaultSelection(inv, timeline));
      setDrawer(false);
    } catch (e) {
      setRerunError(e);
    } finally {
      setRerunning(false);
    }
  };

  const selectEvent = (id) => {
    setSelection({ kind: 'event', id });
    setCenterOn({ id, at: Date.now() });
  };

  const timelineItems = useMemo(() => {
    if (!data) return [];
    const items = data.timeline.filter((t) => showExcluded || t.status !== 'rejected');
    if (sortBy === 'score') {
      return [...items].sort((a, b) => (b.is_seed - a.is_seed) || (b.score ?? 0) - (a.score ?? 0) || a.ts - b.ts);
    }
    return items;
  }, [data, showExcluded, sortBy]);
  const graphItems = useMemo(
    () => (data ? data.timeline.filter((t) => showExcluded || t.status !== 'rejected') : []),
    [data, showExcluded],
  );
  const graphRels = useMemo(
    () => (data ? data.relationships.filter((r) => r.status === 'accepted' && (showSupporting || r.is_primary)) : []),
    [data, showSupporting],
  );

  if (loading) return <main className="container wide"><Loading label="Loading investigation…" /></main>;
  if (error) return <main className="container wide"><ErrorState error={error} onRetry={() => load().catch(setError)} /></main>;

  const { inv } = data;
  const p = inv.params;
  const m = inv.metrics;
  const excludedCount = data.timeline.filter((t) => t.status === 'rejected').length;
  const selectedEventId = selection?.kind === 'event'
    ? selection.id
    : selection?.kind === 'relationship'
      ? data.relationships.find((r) => r.id === selection.id)?.target_event_id
      : null;

  return (
    <main className="container wide results">
      <div className="results-head">
        <div className="title-row">
          <div className="title-block">
            <h1>
              Investigation #{inv.id}
              {inv.run_count > 1 && <span className="run-tag">run {inv.run_count}</span>}
            </h1>
            <div className="start-line" data-testid="start-line">
              <SourceBadge source="redteam" />
              <span className="start-label">Starting event</span>
              <span className="mono start-user">{inv.seed.user_name}</span>
              <span className="mono muted">{inv.seed.src_computer} → {inv.seed.dst_computer}</span>
              <span className="subtle">{readableTime(inv.seed.ts)}</span>
            </div>
          </div>
          <div className="actions">
            <a className="btn" href="#/" data-testid="new-investigation">New investigation</a>
            <button className="btn primary" onClick={() => { setRerunError(null); setDrawer(true); }} data-testid="open-rerun">
              Adjust and re-run
            </button>
          </div>
        </div>

        <div className="stats" data-testid="metrics">
          <div className="stat">
            <span className="stat-value">{m.accepted_events}</span>
            <span className="stat-label">Connected activities</span>
          </div>
          <div className="stat">
            <span className="stat-value">{m.accepted_relationships}</span>
            <span className="stat-label">Links found</span>
          </div>
          <div className="stat">
            <span className="stat-value">{m.candidates_evaluated} <span className="of">of {m.events_in_window}</span></span>
            <span className="stat-label">Activities checked nearby</span>
          </div>
          <div className="stat">
            <span className="stat-value">{m.max_path_depth} {m.max_path_depth === 1 ? 'link' : 'links'}</span>
            <span className="stat-label">
              Longest chain from start
              <InfoTip id="path-tip">The most steps between the starting event and any connected activity.</InfoTip>
            </span>
          </div>
          <span className="divider" />
          <div className="stat">
            <span className="stat-value mono">{p.threshold.toFixed(2)}</span>
            <span className="stat-label">
              Strictness
              <InfoTip id="thr-tip">The minimum score (0 to 1) an activity needs to count as connected.</InfoTip>
            </span>
          </div>
          <div className="stat">
            <span className="stat-value small">{windowLabel(p.window_before, p.window_after)}</span>
            <span className="stat-label">Searched</span>
          </div>
          {change && (
            <div className="change-note" data-testid="change-note" role="status">
              Re-run: {change.added} event{change.added === 1 ? '' : 's'} added, {change.removed} removed
              <button className="icon-btn" onClick={() => setChange(null)} aria-label="Dismiss">✕</button>
            </div>
          )}
        </div>
      </div>

      <StorySummary
        timeline={data.timeline}
        threshold={p.threshold}
        windowText={windowLabel(p.window_before, p.window_after)}
        selectedId={selectedEventId}
        onSelect={selectEvent}
      />

      <div className="results-grid">
        <section className="card view-card">
          <div className="card-head">
            <div className="segmented tabs" role="tablist" aria-label="Evidence view">
              <button role="tab" aria-selected={view === 'graph'} aria-pressed={view === 'graph'} onClick={() => setView('graph')} data-testid="tab-graph">
                Connection map
              </button>
              <button role="tab" aria-selected={view === 'timeline'} aria-pressed={view === 'timeline'} onClick={() => setView('timeline')} data-testid="tab-timeline">
                Timeline
              </button>
            </div>
            <div className="right">
              {view === 'graph' ? (
                <>
                <button className="btn small" onClick={() => setFitRequest((n) => n + 1)} data-testid="reset-view">Reset view</button>
                <label className="switch">
                  <input type="checkbox" checked={showSupporting} onChange={(e) => setShowSupporting(e.target.checked)} data-testid="show-supporting" />
                  Extra supporting links
                </label>
                </>
              ) : (
                <div className="segmented" role="group" aria-label="Sort timeline">
                  <button aria-pressed={sortBy === 'time'} onClick={() => setSortBy('time')} data-testid="sort-time">By time</button>
                  <button aria-pressed={sortBy === 'score'} onClick={() => setSortBy('score')} data-testid="sort-score">Strongest first</button>
                </div>
              )}
              <label className="switch">
                <input type="checkbox" checked={showExcluded} onChange={(e) => setShowExcluded(e.target.checked)} data-testid="show-rejected" />
                Show weak matches ({excludedCount})
              </label>
            </div>
          </div>
          <div className="view-body">
            {view === 'graph' ? (
              m.accepted_events === 0 && !showExcluded ? (
                <div className="state" style={{ height: '100%' }}>
                  Nothing was connected strongly enough. Try a lower strictness or a wider search.
                  <button className="btn" onClick={() => setDrawer(true)}>Adjust settings</button>
                </div>
              ) : (
                <EvidenceGraph
                  timeline={graphItems}
                  relationships={graphRels}
                  showRejected={showExcluded}
                  showSupporting={showSupporting}
                  selection={selection}
                  centerOn={centerOn}
                  fitRequest={fitRequest}
                  onSelectEvent={(id) => setSelection({ kind: 'event', id })}
                  onSelectRelationship={(id) => setSelection({ kind: 'relationship', id })}
                />
              )
            ) : (
              <Timeline items={timelineItems} selectedId={selectedEventId} onSelect={selectEvent} threshold={p.threshold} />
            )}
          </div>
        </section>

        <aside className="card details-card">
          <div className="card-head"><h2>Why is this connected?</h2></div>
          <div className="card-body">
            <EvidenceDetails selection={selection} timeline={data.timeline} relationships={data.relationships}
              params={p} onSelectEvent={selectEvent} />
          </div>
        </aside>
      </div>

      {drawer && (
        <RerunDrawer initial={p} busy={rerunning} error={rerunError} onRerun={rerun} onClose={() => setDrawer(false)} />
      )}
    </main>
  );
}
