// Formatting helpers. LANL timestamps are seconds relative to the dataset start.

export const SOURCE_META = {
  redteam: { label: 'SEED', name: 'Red-team seed', color: 'var(--src-seed)' },
  auth: { label: 'AUTH', name: 'Authentication', color: 'var(--src-auth)' },
  proc: { label: 'PROC', name: 'Process', color: 'var(--src-proc)' },
  dns: { label: 'DNS', name: 'DNS', color: 'var(--src-dns)' },
  flow: { label: 'FLOW', name: 'Network flow', color: 'var(--src-flow)' },
};

const pad = (n) => String(n).padStart(2, '0');

export function lanlClock(ts) {
  const day = Math.floor(ts / 86400) + 1;
  const rem = ts % 86400;
  return `D${day} ${pad(Math.floor(rem / 3600))}:${pad(Math.floor((rem % 3600) / 60))}:${pad(rem % 60)}`;
}

export function signedDelta(seconds) {
  if (seconds === 0) return '±0s';
  const sign = seconds > 0 ? '+' : '−';
  const s = Math.abs(seconds);
  if (s < 120) return `${sign}${s}s`;
  if (s < 7200) return `${sign}${Math.floor(s / 60)}m${pad(s % 60)}s`;
  return `${sign}${Math.floor(s / 3600)}h${pad(Math.floor((s % 3600) / 60))}m`;
}

export function duration(seconds) {
  if (seconds < 120) return `${seconds}s`;
  if (seconds < 7200) return `${Math.round(seconds / 60)} min`;
  if (seconds % 3600 === 0) return `${seconds / 3600} h`;
  return `${(seconds / 3600).toFixed(1)} h`;
}

export const score = (v, digits = 3) => (v == null ? '—' : Number(v).toFixed(digits));
export const pct = (v) => `${(v * 100).toFixed(1)}%`;

export function weightsSum(w) {
  return Math.round((Number(w.entity) + Number(w.temporal) + Number(w.rule)) * 1000) / 1000;
}

export function normalizeWeights(w) {
  const total = Number(w.entity) + Number(w.temporal) + Number(w.rule);
  if (total <= 0) return { entity: 0.4, temporal: 0.3, rule: 0.3 };
  const entity = Math.round((w.entity / total) * 100) / 100;
  const temporal = Math.round((w.temporal / total) * 100) / 100;
  return { entity, temporal, rule: Math.round((1 - entity - temporal) * 100) / 100 };
}

// "Day 2, 17:54:45" — readable form of a LANL relative timestamp
export function readableTime(ts) {
  const [day, clock] = lanlClock(ts).split(' ');
  return `Day ${day.slice(1)}, ${clock}`;
}

export const clockOnly = (ts) => lanlClock(ts).split(' ')[1];

export function windowLabel(before, after) {
  if (before === after) return `${duration(before)} either side`;
  return `${duration(before)} before · ${duration(after)} after`;
}

// Short, untruncated description of an event for compact displays (graph nodes).
export function compactSummary(t) {
  const a = t.attributes ?? {};
  switch (t.source_type) {
    case 'redteam':
    case 'auth':
      return `${t.user_name ?? '?'} · ${t.src_computer ?? '?'} → ${t.dst_computer ?? '?'}`;
    case 'proc':
      return `${a.processName ?? 'process'} on ${t.src_computer ?? '?'}`;
    case 'dns':
      return `${t.src_computer ?? '?'} resolved ${t.dst_computer ?? '?'}`;
    case 'flow':
      return `${t.src_computer ?? '?'} → ${t.dst_computer ?? '?'}:${a.dstPort ?? '?'}`;
    default:
      return t.summary ?? '';
  }
}

// Word-wrap into at most `lines` lines of `max` characters; the last line gets an ellipsis if needed.
export function wrapText(text, max, lines = 2) {
  const words = String(text ?? '').split(' ');
  const out = [''];
  for (const w of words) {
    const cur = out[out.length - 1];
    if (!cur.length) out[out.length - 1] = w;
    else if (cur.length + 1 + w.length <= max) out[out.length - 1] = `${cur} ${w}`;
    else out.push(w);
  }
  const fitted = out.map((l) => (l.length > max ? `${l.slice(0, max - 1)}…` : l));
  if (fitted.length <= lines) return fitted;
  const kept = fitted.slice(0, lines);
  const last = kept[lines - 1];
  kept[lines - 1] = last.length >= max ? `${last.slice(0, max - 1)}…` : `${last}…`;
  return kept;
}

// "8 s before start", "+5 s", "+2 min 04 s"
export function offsetFromStart(seconds) {
  if (seconds === 0) return 'start';
  const s = Math.abs(seconds);
  const text = s < 120 ? `${s} s` : s < 7200 ? `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, '0')} s` : `${(s / 3600).toFixed(1)} h`;
  return seconds < 0 ? `${text} before start` : `+${text}`;
}

export function relativeTo(seconds) {
  const s = Math.abs(seconds);
  const text = s < 120 ? `${s} s` : s < 7200 ? `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, '0')} s` : `${(s / 3600).toFixed(1)} h`;
  return seconds === 0 ? 'at the same second' : text;
}
