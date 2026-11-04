// Layman-friendly wording for the results UI. Display-only: nothing here affects scoring or the API.
import { offsetFromStart } from './format.js';

// Short, neutral descriptions of common Windows programs (shown in brackets after the name).
const PROCESS_HINTS = {
  'powershell.exe': 'a powerful scripting tool',
  'cmd.exe': 'the Windows command prompt',
  'rundll32.exe': 'a Windows helper that runs code from library files',
  'wmic.exe': 'a Windows management tool',
  'net.exe': 'a tool for managing users and network shares',
  'psexec.exe': 'a tool for running programs on other computers',
  'explorer.exe': 'the Windows desktop and file browser',
  'svchost.exe': 'a Windows background-service host',
  'schtasks.exe': 'a tool for scheduling tasks',
  'reg.exe': 'a tool for editing Windows settings (registry)',
  'whoami.exe': 'a tool that shows which user is signed in',
  'mstsc.exe': 'the Remote Desktop app',
  'certutil.exe': 'a certificate tool that can also download files',
  'mshta.exe': 'a Windows tool that runs HTML applications',
  'regsvr32.exe': 'a Windows tool that registers library files',
};

// What a destination port is usually used for.
const PORT_HINTS = {
  21: 'file transfer (FTP)',
  22: 'remote login (SSH)',
  53: 'address lookups (DNS)',
  80: 'web traffic (HTTP)',
  88: 'Windows sign-in (Kerberos)',
  135: 'Windows remote management (RPC)',
  139: 'Windows file sharing (NetBIOS)',
  389: 'directory lookups (LDAP)',
  443: 'secure web traffic (HTTPS)',
  445: 'Windows file sharing (SMB)',
  3389: 'Remote Desktop',
  5985: 'Windows remote management (WinRM)',
  5986: 'Windows remote management (WinRM)',
};

export const processHint = (name) => PROCESS_HINTS[String(name ?? '').toLowerCase()] ?? null;
export const portHint = (port) => PORT_HINTS[Number(port)] ?? null;

// One plain sentence describing an event, for someone with no security background.
export function plainSentence(t) {
  const a = t.attributes ?? {};
  const user = t.user_name ?? 'An unknown user';
  const src = t.src_computer ?? 'an unknown computer';
  const dst = t.dst_computer ?? 'an unknown computer';
  switch (t.source_type) {
    case 'redteam':
      return `${user} signed in from computer ${src} to computer ${dst}. Security testers (the "red team") `
        + 'marked this sign-in as attacker activity, so the investigation starts here.';
    case 'auth': {
      const orient = (a.authOrient ?? '').toLowerCase();
      if (orient === 'logoff') return `${user} signed out of the connection from ${src} to ${dst}.`;
      if (orient === 'tgs' || orient === 'tgt') {
        return `${user} asked the Windows sign-in service for an access pass (Kerberos ticket) to go from ${src} to ${dst}.`;
      }
      if ((a.outcome ?? '').toLowerCase() === 'fail') return `${user} tried to sign in from ${src} to ${dst}, but it failed.`;
      return `${user} signed in from computer ${src} to computer ${dst}.`;
    }
    case 'proc': {
      const name = a.processName ?? 'a program';
      const hint = processHint(a.processName);
      const verb = (a.eventType ?? '').toLowerCase() === 'end' ? 'closed' : 'started';
      return `${user} ${verb} ${name}${hint ? ` (${hint})` : ''} on computer ${src}.`;
    }
    case 'dns':
      return `Computer ${src} looked up where computer ${dst} is on the network, like checking a phone book before calling.`;
    case 'flow': {
      const hint = portHint(a.dstPort);
      const how = hint ? ` using ${hint}` : a.dstPort != null ? ` on port ${a.dstPort}` : '';
      return `Computer ${src} sent data to computer ${dst}${how}.`;
    }
    default:
      return t.summary ?? '';
  }
}

// Score in words, using the same cut-offs as the details panel ("well above the threshold" = +0.2).
export function strengthWord(value, threshold, rejected = false) {
  if (rejected || value == null || value < threshold) return { text: 'Weak link', tone: 'weak' };
  if (value - threshold >= 0.2) return { text: 'Strong link', tone: 'strong' };
  return { text: 'Likely link', tone: 'likely' };
}

export function whenText(t) {
  if (t.is_seed) return 'Start';
  const s = offsetFromStart(t.seconds_from_seed);
  return s.startsWith('+') ? `${s.slice(1)} later` : s;
}

// Everything the plain-English summary needs, built from the investigation's own timeline.
export function buildStory(timeline, threshold) {
  const seed = timeline.find((t) => t.is_seed) ?? null;
  const accepted = timeline.filter((t) => !t.is_seed && t.status === 'accepted');
  const excluded = timeline.filter((t) => t.status === 'rejected').length;
  const steps = [...(seed ? [seed] : []), ...accepted].sort((a, b) => a.ts - b.ts || (b.is_seed - a.is_seed));

  const users = new Set();
  const computers = new Set();
  for (const t of steps) {
    if (t.user_name) users.add(t.user_name);
    if (t.src_computer) computers.add(t.src_computer);
    if (t.dst_computer) computers.add(t.dst_computer);
  }
  const strong = accepted.filter((t) => strengthWord(t.score, threshold).tone === 'strong').length;
  const deepest = accepted.reduce((m, t) => Math.max(m, t.hop ?? 0), 0);

  return { seed, steps, related: accepted.length, strong, excluded, deepest, users: [...users], computers: [...computers] };
}
