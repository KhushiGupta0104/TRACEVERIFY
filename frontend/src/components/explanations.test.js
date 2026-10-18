import { describe, expect, it } from 'vitest';
import { whatHappened } from './EvidenceDetails.jsx';

describe('plain-English event descriptions', () => {
  it('describes each source from its own fields', () => {
    expect(whatHappened({ source_type: 'proc', user_name: 'U620@DOM1', src_computer: 'C1003',
      attributes: { processName: 'powershell.exe', eventType: 'Start' } })).toBe('U620@DOM1 started powershell.exe on C1003.');
    expect(whatHappened({ source_type: 'auth', user_name: 'U1@D', src_computer: 'C1', dst_computer: 'C2',
      attributes: { authOrient: 'LogOn', outcome: 'Fail', authType: 'NTLM' } })).toBe('U1@D failed to log on from C1 to C2 using NTLM.');
    expect(whatHappened({ source_type: 'dns', src_computer: 'C1003', dst_computer: 'C901', attributes: {} }))
      .toBe('C1003 looked up the address of C901 (DNS).');
    expect(whatHappened({ source_type: 'flow', src_computer: 'C1', dst_computer: 'C2',
      attributes: { dstPort: '443', packets: 18, bytes: 2840 } })).toBe('C1 sent network traffic to C2 on port 443 (18 packets, 2840 bytes).');
  });
});
