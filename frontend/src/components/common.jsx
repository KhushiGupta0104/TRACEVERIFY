import { SOURCE_META } from '../utils/format.js';

export function SourceBadge({ source }) {
  const meta = SOURCE_META[source] ?? { label: source?.toUpperCase(), color: 'var(--text-2)' };
  return (
    <span className="badge" style={{ color: meta.color }} title={meta.name}>
      {meta.label}
    </span>
  );
}

export function ScoreBar({ value, threshold, rejected }) {
  return (
    <div className={`scorebar ${rejected ? 'rejected' : ''}`} aria-hidden="true">
      {value != null && <span style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }} />}
      {threshold != null && <i className="thr" style={{ left: `calc(${threshold * 100}% - 1px)` }} />}
    </div>
  );
}

export function Loading({ label = 'Loading…' }) {
  return (
    <div className="state" role="status">
      <div className="spinner" />
      <div>{label}</div>
    </div>
  );
}

export function Empty({ children }) {
  return <div className="state">{children}</div>;
}

export function ErrorState({ error, onRetry }) {
  return (
    <div className="state error" role="alert">
      <div>{error?.message ?? String(error)}</div>
      {onRetry && (
        <button className="btn small" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function Hosts({ from, to }) {
  return (
    <span className="seed-hosts">
      {from}
      <span className="arrow">→</span>
      {to}
    </span>
  );
}

export function Chevron() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
      <path d="M3 5l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// Small "i" button with a short tooltip, shown on hover and keyboard focus.
export function InfoTip({ id, children }) {
  return (
    <span className="info-tip">
      <button type="button" className="info-btn" aria-describedby={id} aria-label="More information">i</button>
      <span role="tooltip" id={id} className="info-bubble">{children}</span>
    </span>
  );
}
