#!/usr/bin/env python3
"""Netlist self-check for the two generated gowin-bridge boards.

Run:   python tools/check_netlist.py

Exports each schematic's netlist with kicad-cli and checks three things that
the generator could get wrong without ERC noticing:

 1. every one of the six HDMI sockets maps HDMI signals onto link roles the
    SAME way - that is the symmetry requirement, and it is what lets one
    board A design sit at both ends of a two-radio link;
 2. a straight pin-1-to-pin-1 mini-to-mini cable joining board A's OUT 1 to
    another board A's IN lands every signal on its counterpart;
 3. a mini-to-full-size cable joining board A's OUT 1 to board B's IN 1 does
    the same, across the Type C / Type A pin-order difference.

The HDMI standard pin tables are retyped here from the specification rather
than imported from the generator, so the two can disagree and be caught.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import kisexp as K

KICAD_CLI_CANDIDATES = [
    os.environ.get('KICAD_CLI', ''),
    r'C:/Users/franz/AppData/Local/Programs/KiCad/10.0/bin/kicad-cli.exe',
    r'C:/Program Files/KiCad/10.0/bin/kicad-cli.exe',
    r'C:/Program Files/KiCad/9.0/bin/kicad-cli.exe',
    'kicad-cli',
]

# HDMI receptacle pinouts.  signal -> (Type A pin, Type C pin).
# Type C differs from Type A in exactly four ways: every pair's + leg swaps
# with its shield, DDC/CEC ground moves from 17 to 13, CEC from 13 to 14, and
# Reserved/Utility from 14 to 17.  SCL, SDA, +5 V and HPD do not move.
STD = {
    'D2+': (1, 2),   'D2S': (2, 1),   'D2-': (3, 3),
    'D1+': (4, 5),   'D1S': (5, 4),   'D1-': (6, 6),
    'D0+': (7, 8),   'D0S': (8, 7),   'D0-': (9, 9),
    'CK+': (10, 11), 'CKS': (11, 10), 'CK-': (12, 12),
    'CEC': (13, 14), 'UTIL': (14, 17),
    'SCL': (15, 15), 'SDA': (16, 16),
    'DDCGND': (17, 13), 'P5V': (18, 18), 'HPD': (19, 19),
}
LANES = (('CK', 'CLK'), ('D0', 'D0'), ('D1', 'D1'), ('D2', 'D2'))


# ----------------------------------------------------------------------------
# The header pin maps, retyped from PINMAP.md.  These are the contract with
# the FPGA gateware, so they get asserted rather than trusted.
# ----------------------------------------------------------------------------

# board A, socket J1 on HL2 DB1.  pin -> (net, FPGA pin, what it is)
DB1 = {
    1:  ('HL2_D0_HDR',   '72',  'forward lane 0, via HL2 jumper J25'),
    2:  ('HL2_D1',       '76',  'forward lane 1'),
    3:  ('HL2_D2',       '77',  'forward lane 2'),
    4:  ('HL2_D3',       '80',  'forward lane 3, the 21 pF VREF pin'),
    5:  ('HL2_D4',       '83',  'forward lane 4'),
    6:  ('HL2_D5',       '85',  'forward lane 5'),
    7:  ('VLVDS',        '-',   'HL2 2.5 V rail, breakout only'),
    8:  ('VLVDS',        '-',   'same net as pin 7'),
    9:  ('HL2_CLKA_RAW', '98',  'forward clock A'),
    10: ('<open>',       '90',  'CW/PTT ring, deliberately not connected'),
    11: ('HL2_REV0',     '99',  'reverse lane 0'),
    12: ('<open>',       '91',  'CW/PTT tip, deliberately not connected'),
    13: ('GND',          '-',   'ground'),
    14: ('GND',          '-',   'ground'),
    15: ('HL2_REV1',     '100', 'reverse lane 1'),
    16: ('SCL1',         '103', 'breakout only'),
    17: ('HL2_REV2',     '101', 'reverse lane 2'),
    18: ('SDA1',         '104', 'breakout only'),
    19: ('DB1_3V3',      '-',   'board supply'),
    20: ('DB1_3V3',      '-',   'same net as pin 19'),
}
# board A, socket J2 on HL2 DB12.  NOTE pins 5 and 6: DB12 pin 5 is FPGA
# PIN_89 and pin 6 is PIN_88, per hardware/hl/hermeslite.net.  rev A of
# PINMAP.md had these two swapped.
DB12 = {
    1: ('HL2_SLOW_OUT', '86', 'status UART out'),
    2: ('HL2_CLKB',     '87', 'forward clock B'),
    3: ('GND',          '-',  'ground'),
    4: ('GND',          '-',  'ground'),
    5: ('HL2_SLOW_IN',  '89', 'command channel in, INPUT ONLY'),
    6: ('HL2_REVCLK',   '88', 'reverse clock in, INPUT ONLY'),
}
# board B, socket J1 on Tang dock J14.  Only the pins PINMAP.md uses.
J14 = {
    9:  ('LINK_R0',        'W17', 'reverse lane 0 out'),
    10: ('LINK_D0',        'V17', 'IN 1 lane 0'),
    11: ('P5V_J14',        '-',   '5V_Peripheral'),
    12: ('GND',            '-',   'the only ground pin on J14'),
    13: ('LINK_R1',        'W22', 'reverse lane 1 out'),
    14: ('LINK_D1',        'W21', 'IN 1 lane 1'),
    15: ('LINK_R2',        'P17', 'reverse lane 2 out'),
    16: ('LINK_D2',        'N17', 'IN 1 lane 2'),
    17: ('LINK_SLOW_OUT',  'N14', 'command channel out'),
    18: ('LINK_D3',        'N13', 'IN 2 lane 3'),
    19: ('LINK_SLOW_IN',   'V20', 'status UART in, must be LVTTL33'),
    20: ('LINK_CLK_A',     'U20', 'forward clock A, SGCLKT_5 + BPLL2/3 CLKIN0'),
    31: ('LINK_PRESENT2',  'Y19', 'IN 2 cable detect'),
    32: ('LINK_CLK_B',     'Y18', 'forward clock B, MGCLKT_4'),
    33: ('LINK_PRESENT1',  'T20', 'IN 1 cable detect'),
    34: ('LINK_D5',        'N15', 'IN 2 lane 5, the pairless pin'),
    35: ('LINK_REVCLK',    'U18', 'reverse clock out'),
    36: ('LINK_D4',        'U17', 'IN 2 lane 4'),
}


def check_header(nets, ref, table, label, open_ok=()):
    print('=== %s ===' % label)
    prob = []
    for pin in sorted(table):
        want, fpga, what = table[pin]
        got = nets.get((ref, str(pin)), '<open>')
        if got != want:
            prob.append('%s pin %d = %s, PINMAP.md says %s (%s)'
                        % (label, pin, got, want, what))
        else:
            print('  pin %-2d  %-14s  FPGA %-4s  %s' % (pin, got, fpga, what))
    # every pin the table does not mention must be electrically open
    for pin in open_ok:
        got = nets.get((ref, str(pin)), '<open>')
        if got != '<open>':
            prob.append('%s pin %d should be open, is %s' % (label, pin, got))
    return prob


def find_cli():
    for c in KICAD_CLI_CANDIDATES:
        if c and (os.path.isfile(c) or c == 'kicad-cli'):
            return c
    raise SystemExit('kicad-cli not found; set KICAD_CLI.')


def export(board):
    out = os.path.join(ROOT, board, board + '.net')
    subprocess.run([find_cli(), 'sch', 'export', 'netlist',
                    '--format', 'kicadsexpr', '-o', out,
                    os.path.join(ROOT, board, board + '.kicad_sch')],
                   check=True, capture_output=True)
    return out


def load(path):
    root = K.parse(open(path, encoding='utf-8').read())[0]
    out = {}
    for n in K.kids(root, 'nets'):
        for net in K.kids(n, 'net'):
            nm = K.atoms(K.kid(net, 'name'))[0]
            # KiCad prefixes net names with the sheet path and invents a name
            # for every unconnected pin; normalise both away so the comparison
            # is against the schematic's own labels.
            if nm.startswith('/'):
                nm = nm[1:]
            if nm.startswith('unconnected-'):
                nm = '<open>'
            for node in K.kids(net, 'node'):
                out[(K.atoms(K.kid(node, 'ref'))[0],
                     K.atoms(K.kid(node, 'pin'))[0])] = nm
    return out


def role(net, pfx):
    """Strip a socket prefix, so O1_D2_P and I1_D2_P both give D2_P."""
    p = pfx + '_'
    return net[len(p):] if net.startswith(p) else None


def check_sockets(nets, kind, sockets):
    idx = 0 if kind == 'A' else 1
    prob = []
    for ref, pfx in sorted(sockets.items()):
        row = {s: nets.get((ref, str(v[idx])), '<open>')
               for s, v in STD.items()}
        for l, nm in LANES:
            for leg, suf in (('+', '_P'), ('-', '_N')):
                want = '%s_%s%s' % (pfx, nm, suf)
                if row[l + leg] != want:
                    prob.append('%s %s%s = %s, expected %s'
                                % (ref, l, leg, row[l + leg], want))
            if row[l + 'S'] != 'GND':
                prob.append('%s %s shield = %s' % (ref, l, row[l + 'S']))
        if row['DDCGND'] != 'GND':
            prob.append('%s DDC/CEC ground = %s' % (ref, row['DDCGND']))
        if row['SCL'] != '%s_SLOW' % pfx:
            prob.append('%s SCL = %s' % (ref, row['SCL']))
        if row['HPD'] != '%s_HPD' % pfx:
            prob.append('%s HPD = %s' % (ref, row['HPD']))
        for s in ('CEC', 'UTIL', 'SDA'):
            if row[s] != '<open>':
                prob.append('%s %s should be open, is %s' % (ref, s, row[s]))
        print('  %-3s %-3s clk=%-11s d0=%-10s d1=%-10s d2=%-10s slow=%-10s '
              'hpd=%-8s 5V=%s'
              % (ref, pfx, row['CK+'], row['D0+'], row['D1+'], row['D2+'],
                 row['SCL'], row['HPD'], row['P5V']))
    return prob


def check_cable(label, na, a_ref, a_pfx, a_kind, nb, b_ref, b_pfx, b_kind):
    """Walk a cable signal by signal.  A real HDMI cable wires signal to
    signal, so for a mini-to-full-size cable the pin numbers differ at the two
    ends and the comparison has to be by role, not by pin number."""
    print()
    print('--- %s ---' % label)
    ia = 0 if a_kind == 'A' else 1
    ib = 0 if b_kind == 'A' else 1
    prob = []
    for s, pins in sorted(STD.items(), key=lambda kv: kv[1][ia]):
        pa, pb = str(pins[ia]), str(pins[ib])
        a = na.get((a_ref, pa), '<open>')
        b = nb.get((b_ref, pb), '<open>')
        ra, rb = role(a, a_pfx), role(b, b_pfx)
        if ra is not None and rb is not None:
            if ra == rb:
                mark = 'OK'
            else:
                mark = 'MISMATCH'
                prob.append('%s: %s -> %s' % (s, a, b))
        elif a == b == 'GND':
            mark = 'ok (ground)'
        elif a == '<open>' and b == '<open>':
            mark = 'unused at both ends'
        elif a == '<open>' or b == '<open>':
            mark = 'open at one end (+5 V, by design)'
        else:
            mark = 'UNEXPECTED'
            prob.append('%s: %s -> %s' % (s, a, b))
        print('  %-7s pin %-2s -> pin %-2s   %-12s -> %-13s %s'
              % (s, pa, pb, a, b, mark))
    return prob


def main():
    hl2 = load(export('hl2-bridge'))
    tang = load(export('tang-bridge'))
    prob = []

    prob += check_header(hl2, 'J1', DB1, 'board A J1 on HL2 DB1')
    prob += check_header(hl2, 'J2', DB12, 'board A J2 on HL2 DB12')
    prob += check_header(tang, 'J1', J14, 'board B J1 on Tang dock J14',
                         open_ok=[n for n in range(1, 41)
                                  if n not in J14])
    print('=== hl2-bridge, three mini HDMI (Type C) sockets ===')
    prob += check_sockets(hl2, 'C', {'J3': 'O1', 'J4': 'O2', 'J5': 'I'})
    print('=== tang-bridge, three full-size HDMI (Type A) sockets ===')
    prob += check_sockets(tang, 'A', {'J2': 'I1', 'J3': 'I2', 'J4': 'O'})

    prob += check_cable(
        'straight mini-to-mini: board A OUT 1 -> another board A IN '
        '(the two-radio case)',
        hl2, 'J3', 'O1', 'C', hl2, 'J5', 'I', 'C')
    prob += check_cable(
        'mini-to-full-size: board A OUT 1 -> board B IN 1',
        hl2, 'J3', 'O1', 'C', tang, 'J2', 'I1', 'A')
    prob += check_cable(
        'mini-to-full-size: board B OUT -> board A IN',
        tang, 'J4', 'O', 'A', hl2, 'J5', 'I', 'C')

    print()
    for p in prob:
        print('  !! ' + p)
    print('  %s' % ('OK - all six sockets share one signal-to-role mapping, '
                    'and every cable lands every signal on its counterpart'
                    if not prob else '%d PROBLEMS' % len(prob)))
    return 1 if prob else 0


if __name__ == '__main__':
    sys.exit(main())
