import { useMemo, useState } from 'react';
import { buildStory, plainSentence, strengthWord, whenText } from '../utils/plainEnglish.js';

const KEY = 'traceverify.storyHidden';
const readHidden = () => {
  try { return window.localStorage.getItem(KEY) === '1'; } catch { return false; }
};
const writeHidden = (v) => {
  try { window.localStorage.setItem(KEY, v ? '1' : '0'); } catch { /* storage unavailable */ }
};

const STEP_LIMIT = 8;
const plural = (n, one, many = `${one}s`) => `${n} ${n === 1 ? one : many}`;

// Plain-English summary of an investigation, for readers without a security background.
export default function StorySummary({ timeline, threshold, windowText, selectedId, onSelect }) {
  const story = useMemo(() => buildStory(timeline, threshold), [timeline, threshold]);
  const [hidden, setHidden] = useState(readHidden);
  const [showAll, setShowAll] = useState(false);
  const toggle = (v) => { setHidden(v); writeHidden(v); };

  if (hidden) {
    return (
      <button className="btn small story-show" onClick={() => toggle(false)} data-testid="show-story">
        Show plain-English summary
      </button>
    );
  }

  const steps = showAll ? story.steps : story.steps.slice(0, STEP_LIMIT);

  return (
    <section className="card story" aria-labelledby="story-title" data-testid="story-summary">
      <div className="story-head">
        <div>
          <h2 id="story-title">What we found, in plain English</h2>
          <p className="story-lead" data-testid="story-lead">
            {story.related === 0 ? (
              <>Nothing nearby was connected strongly enough to the starting event. Try <b>Adjust and re-run</b> with a
                lower threshold or a wider time window.</>
            ) : (
              <>Starting from one suspicious sign-in, we searched {windowText} and found{' '}
                <b>{plural(story.related, 'activity', 'activities')}</b> that are likely connected to it
                {story.strong > 0 && <> ({story.strong} strongly)</>}. In time order, here is what happened:</>
            )}
          </p>
        </div>
        <button className="icon-btn" onClick={() => toggle(true)} aria-label="Hide summary" data-testid="hide-story">✕</button>
      </div>

      <div className="story-body">
        <ol className="story-steps">
          {steps.map((t, i) => {
            const w = t.is_seed ? null : strengthWord(t.score, threshold);
            return (
              <li key={t.id}>
                <button type="button" className={`story-step ${t.id === selectedId ? 'selected' : ''} ${t.is_seed ? 'seed' : ''}`}
                  onClick={() => onSelect(t.id)} data-testid="story-step">
                  <span className="story-num">{i + 1}</span>
                  <span className="story-when">{whenText(t)}</span>
                  <span className="story-text">{plainSentence(t)}</span>
                  {t.is_seed
                    ? <span className="pill danger">Starting point</span>
                    : <span className={`pill strength-${w.tone}`}>{w.text}</span>}
                </button>
              </li>
            );
          })}
        </ol>
        {story.steps.length > STEP_LIMIT && (
          <button className="btn ghost small" onClick={() => setShowAll((v) => !v)}>
            {showAll ? 'Show fewer' : `Show all ${story.steps.length} steps`}
          </button>
        )}

        <aside className="story-side">
          <div>
            <h3>Who and what was involved</h3>
            <p><span className="subtle">User accounts:</span> <span className="mono">{story.users.join(', ') || '—'}</span></p>
            <p><span className="subtle">Computers:</span> <span className="mono">{story.computers.join(', ') || '—'}</span></p>
            {story.deepest > 1 && (
              <p className="subtle small">The longest chain is {story.deepest} steps away from the starting event.</p>
            )}
          </div>
          {story.excluded > 0 && (
            <p className="small">
              {plural(story.excluded, 'other activity', 'other activities')} happened nearby but {story.excluded === 1 ? 'was' : 'were'} only
              loosely related, so {story.excluded === 1 ? 'it was' : 'they were'} <b>left out</b>.
            </p>
          )}
          <p className="small subtle">
            How to read this: events are “linked” when they share a user or computer, happen close in time, and follow a
            known attack pattern. A link suggests the events belong together. It does not prove one caused the other.
            Click any step to see the evidence behind it.
          </p>
        </aside>
      </div>
    </section>
  );
}
