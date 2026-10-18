import { useState } from 'react';
import { Chevron, Hosts } from './common.jsx';
import { readableTime } from '../utils/format.js';

export default function SeedList({ seeds, selectedId, onSelect }) {
  const [expanded, setExpanded] = useState(null);
  return (
    <>
      <div className="seed-cols" aria-hidden="true">
        <span />
        <span>User</span>
        <span>Source → destination</span>
        <span>Time</span>
      </div>
      <ul className="seed-list" role="radiogroup" aria-label="Starting event">
        {seeds.map((s) => {
          const selected = s.id === selectedId;
          const open = expanded === s.id;
          return (
            <li key={s.id} className={`seed-item ${selected ? 'selected' : ''}`} data-testid="seed-row">
              <button type="button" className="seed-main" role="radio" aria-checked={selected} onClick={() => onSelect(s)}>
                <span className="radio" />
                <span className="seed-user">{s.user_name}</span>
                <Hosts from={s.src_computer} to={s.dst_computer} />
                <span className="seed-time">{readableTime(s.ts)}</span>
              </button>
              <button
                type="button"
                className="seed-expand"
                aria-expanded={open}
                aria-label={open ? 'Hide details' : 'Show details'}
                onClick={() => setExpanded(open ? null : s.id)}
              >
                <Chevron />
              </button>
              {open && (
                <dl className="facts seed-more">
                  <dt>Event ID</dt>
                  <dd className="mono">#{s.id}</dd>
                  <dt>LANL time</dt>
                  <dd className="mono">{s.ts} s</dd>
                  <dt>Source</dt>
                  <dd className="mono">{s.source_file}, line {s.line_no}</dd>
                  <dt>Raw record</dt>
                  <dd className="mono">{s.raw_line}</dd>
                  <dt>Nearby events</dt>
                  <dd>{s.nearby_evidence} within 30 minutes</dd>
                </dl>
              )}
            </li>
          );
        })}
      </ul>
    </>
  );
}
