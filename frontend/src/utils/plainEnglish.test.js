import { describe, expect, it } from 'vitest';
import { buildStory, plainSentence, strengthWord, whenText } from './plainEnglish.js';

describe('plain-English wording', () => {
  it('describes events without jargon', () => {
    expect(plainSentence({ source_type: 'proc', user_name: 'U1', src_computer: 'C1',
      attributes: { processName: 'powershell.exe', eventType: 'Start' } }))
      .toBe('U1 started powershell.exe (a powerful scripting tool) on computer C1.');
    expect(plainSentence({ source_type: 'flow', src_computer: 'C1', dst_computer: 'C2', attributes: { dstPort: 445 } }))
      .toBe('Computer C1 sent data to computer C2 using Windows file sharing (SMB).');
    expect(plainSentence({ source_type: 'auth', user_name: 'U1', src_computer: 'C1', dst_computer: 'C2',
      attributes: { outcome: 'Fail' } })).toBe('U1 tried to sign in from C1 to C2, but it failed.');
  });

  it('puts scores into words relative to the threshold', () => {
    expect(strengthWord(0.9, 0.6).text).toBe('Strong link');
    expect(strengthWord(0.65, 0.6).text).toBe('Likely link');
    expect(strengthWord(0.5, 0.6).text).toBe('Weak link');
    expect(strengthWord(0.9, 0.6, true).text).toBe('Weak link');
  });

  it('describes timing relative to the start', () => {
    expect(whenText({ is_seed: true })).toBe('Start');
    expect(whenText({ seconds_from_seed: 5 })).toBe('5 s later');
    expect(whenText({ seconds_from_seed: -8 })).toBe('8 s before start');
  });

  it('builds a time-ordered story from accepted events only', () => {
    const story = buildStory([
      { id: 2, ts: 110, status: 'accepted', score: 0.95, hop: 1, user_name: 'U1', src_computer: 'C2' },
      { id: 1, ts: 100, is_seed: true, status: 'accepted', user_name: 'U1', src_computer: 'C1', dst_computer: 'C2' },
      { id: 3, ts: 105, status: 'rejected', score: 0.3, hop: 1 },
      { id: 4, ts: 120, status: 'accepted', score: 0.65, hop: 2, src_computer: 'C3' },
    ], 0.6);
    expect(story.steps.map((s) => s.id)).toEqual([1, 2, 4]);
    expect(story).toMatchObject({ related: 2, strong: 1, excluded: 1, deepest: 2, users: ['U1'] });
    expect(story.computers).toEqual(['C1', 'C2', 'C3']);
  });
});
