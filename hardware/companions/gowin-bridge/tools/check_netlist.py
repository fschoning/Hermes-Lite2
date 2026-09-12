#!/usr/bin/env python3
"""Netlist self-check for the generated gowin-bridge boards.

Run:   python tools/check_netlist.py

Exports each schematic's netlist with kicad-cli and checks four things that
the generator could get wrong without ERC noticing:

 1. every one of the six HDMI sockets maps HDMI signals onto link roles the
    SAME way - that is the symmetry requirement, and it is what lets one
    board A design sit at both ends of a two-radio link;
 2. a straight pin-1-to-pin-1 mini-to-mini cable joining board A's OUT to
    another board A's IN lands every signal on its counterpart, and the same
    for the two mini-to-full-size cables, across the Type C / Type A pin-order
    difference;
 3. the auxiliary cable is SELF-COMPLEMENTARY: AUX to AUX maps group G1 to
    group G1 and G2 to G2, so a ROLE A board and a ROLE B board fit together
    whichever two boards they are;
 4. THE STRAP CANNOT PRODUCE CONTENTION.  This is the important one.  For
    each auxiliary group, the LVDS driver's active-HIGH enable and the
    buffer/translator port that drives that group toward the host must be
    controlled by the SAME NET, so the group is either driven onto the cable
    or driven toward the host and never both - for any level on that net,
    including a stuck or floating one.  The check also proves that the two
    groups are controlled by a complementary pair produced by ONE inverter
    from ONE strap net, that the complement carries a pull-UP so a dead
    inverter disables a port rather than enabling one, and that no auxiliary
    enable is tied to a constant.

The HDMI standard pin tables and the header pin maps are retyped here from
the specification and from PINMAP.md rather than imported from the generator,
so the two can disagree and be caught.
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

# Which HDMI pairs make up each auxiliary group.  PINMAP.md 2.3: G1 is the
# clock pair plus the data 0 pair, G2 is the data 1 pair plus the data 2 pair,
# and each group carries its own clock, so the two directions are independent.
AUX_G1 = ('CLK', 'D0')
AUX_G2 = ('D1', 'D2')


# ----------------------------------------------------------------------------
# The header pin maps, retyped from PINMAP.md rev C.  These are the contract
# with the FPGA gateware, so they get asserted rather than trusted.
# ----------------------------------------------------------------------------

# board A, socket J1 on HL2 DB1.  pin -> (net, FPGA pin, what it is)
DB1 = {
    1:  ('HL2_AX_G2CLK_HDR', '72',  'AUX G2 clock, BIDIRECTIONAL, via HL2 '
                                    'jumper J25 and sharing uFL pad CL8'),
    2:  ('HL2_O_D0',      '76',  'OUT lane 0'),
    3:  ('HL2_O_D1',      '77',  'OUT lane 1'),
    4:  ('HL2_AX_G2DAT',  '80',  'AUX G2 data, BIDIRECTIONAL, the 21 pF '
                                 'VREF pin'),
    5:  ('HL2_O_D2',      '83',  'OUT lane 2'),
    6:  ('HL2_AX_G1CLK',  '85',  'AUX G1 clock, BIDIRECTIONAL'),
    7:  ('VLVDS',         '-',   'HL2 2.5 V rail, breakout only'),
    8:  ('VLVDS',         '-',   'same net as pin 7'),
    9:  ('HL2_CLK_RAW',   '98',  'OUT clock, before the divider'),
    10: ('<open>',        '90',  'CW/PTT ring, deliberately not connected'),
    11: ('HL2_I_D0',      '99',  'IN lane 0'),
    12: ('<open>',        '91',  'CW/PTT tip, deliberately not connected'),
    13: ('GND',           '-',   'ground'),
    14: ('GND',           '-',   'ground'),
    15: ('HL2_I_D1',      '100', 'IN lane 1'),
    16: ('SCL1',          '103', 'breakout only'),
    17: ('HL2_I_D2',      '101', 'IN lane 2'),
    18: ('SDA1',          '104', 'breakout only'),
    19: ('DB1_3V3',       '-',   'board supply'),
    20: ('DB1_3V3',       '-',   'same net as pin 19'),
}
# board A, socket J2 on HL2 DB12.  NOTE pins 5 and 6: DB12 pin 5 is FPGA
# PIN_89 and pin 6 is PIN_88, per hardware/hl/hermeslite.net.  rev A of
# PINMAP.md had these two swapped.
DB12 = {
    1: ('HL2_SLOW_OUT', '86', 'status UART out'),
    2: ('HL2_AX_G1DAT', '87', 'AUX G1 data, BIDIRECTIONAL'),
    3: ('GND',          '-',  'ground'),
    4: ('GND',          '-',  'ground'),
    5: ('HL2_ROLE_IN',  '89', 'the ROLE strap, read locally. INPUT ONLY'),
    6: ('HL2_INCLK',    '88', 'IN clock, a dedicated clock input. INPUT ONLY'),
}
# board B, socket J1 on Tang dock J14.  Only the pins PINMAP.md uses; pin 36
# (ball U17) is the one spare and must be open.
J14 = {
    9:  ('LINK_R0',          'W17', 'OUT lane 0'),
    10: ('LINK_D0',          'V17', 'IN lane 0'),
    11: ('P5V_J14',          '-',   '5V_Peripheral'),
    12: ('GND',              '-',   'the only ground pin on J14'),
    13: ('LINK_R1',          'W22', 'OUT lane 1'),
    14: ('LINK_D1',          'W21', 'IN lane 1'),
    15: ('LINK_R2',          'P17', 'OUT lane 2'),
    16: ('LINK_D2',          'N17', 'IN lane 2'),
    17: ('LINK_AUX_G2_CLK',  'N14', 'AUX G2 clock'),
    18: ('LINK_AUX_G1_DAT',  'N13', 'AUX G1 data'),
    19: ('LINK_SLOW_IN',     'V20', 'status UART in, must be LVTTL33'),
    20: ('LINK_CLK',         'U20', 'IN clock = the PLL reference, '
                                    'SGCLKT_5 / BPLL2+3 CLKIN0'),
    31: ('LINK_AUX_G2_DAT',  'Y19', 'AUX G2 data'),
    32: ('LINK_AUX_G1_CLK',  'Y18', 'AUX G1 clock received, MGCLKT_4'),
    33: ('LINK_PRESENT',     'T20', 'IN cable detect'),
    34: ('LINK_ROLE',        'N15', 'the ROLE strap, read locally'),
    35: ('LINK_REVCLK',      'U18', 'OUT clock, PLL-derived'),
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
            print('  pin %-2d  %-18s  FPGA %-4s  %s' % (pin, got, fpga, what))
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
    """-> (pin map, value map).  pin map is (ref, pad) -> net name; value map
    is ref -> the part's Value field, which is how the strap check finds the
    inverter, the drivers and the translators without being told their
    reference designators."""
    root = K.parse(open(path, encoding='utf-8').read())[0]
    out = {}
    vals = {}
    for comps in K.kids(root, 'components'):
        for comp in K.kids(comps, 'comp'):
            r = K.atoms(K.kid(comp, 'ref'))[0]
            v = K.kid(comp, 'value')
            vals[r] = K.atoms(v)[0] if v is not None else ''
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
    return out, vals


def role(net, pfx):
    """Strip a socket prefix, so AX_D2_P and I_D2_P both give D2_P."""
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
        if row['P5V'] != '%s_5V_PIN' % pfx:
            prob.append('%s +5 V = %s' % (ref, row['P5V']))
        for s in ('CEC', 'UTIL', 'SDA'):
            if row[s] != '<open>':
                prob.append('%s %s should be open, is %s' % (ref, s, row[s]))
        print('  %-3s %-3s clk=%-11s d0=%-10s d1=%-10s d2=%-10s slow=%-9s '
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
            mark = 'open at one end, by design'
        else:
            mark = 'UNEXPECTED'
            prob.append('%s: %s -> %s' % (s, a, b))
        print('  %-7s pin %-2s -> pin %-2s   %-12s -> %-13s %s'
              % (s, pa, pb, a, b, mark))
    return prob


# ----------------------------------------------------------------------------
#  4. The strap, and the contention case it has to make impossible
# ----------------------------------------------------------------------------
#
# Pad numbers, from the same datasheets the generator uses.
INV_A, INV_Y, INV_GND, INV_VCC = '2', '4', '3', '5'   # SN74LVC1G04DBVR (DBV)
DRV_EN, DRV_ENB = '1', '8'                            # DS90LV047A
DRV_P = {'ch1': '15', 'ch2': '14', 'ch3': '11', 'ch4': '10'}
RCV_P = {'ch1': '2', 'ch2': '3', 'ch3': '6', 'ch4': '7'}
RCV_OUT = {'ch1': '15', 'ch2': '14', 'ch3': '11', 'ch4': '10'}
# SN74AVC4T245PW: port 1 = 1A1/1A2 pads 4,5 -> 1B1/1B2 pads 13,12, 1OE* 15.
#                 port 2 = 2A1/2A2 pads 6,7 -> 2B1/2B2 pads 11,10, 2OE* 14.
X4_PORTS = {1: (('4', '5'), ('13', '12'), '15'),
            2: (('6', '7'), ('11', '10'), '14')}

INV_VALUE = '74LVC1G04'
DRV_VALUE = 'DS90LV047A'
RCV_VALUE = 'DS90LV048A'
X4_VALUE = 'SN74AVC4T245PW'


def _pairs_driven(nets, ref, pfx):
    """Which AUX pairs an LVDS driver actually drives, by looking at which of
    its four + outputs land on an AUX pair net."""
    out = set()
    for ch, pad in sorted(DRV_P.items()):
        n = nets.get((ref, pad), '<open>')
        r = role(n, pfx)
        if r and r.endswith('_P'):
            out.add(r[:-2])
    return out


def check_strap(nets, vals, label, aux_pfx, v3, gnd='GND'):
    """Prove that no level on the strap net can make a translator/buffer port
    drive an auxiliary pin at the same time as the host drives it."""
    print()
    print('=== %s: the ROLE strap and the contention case ===' % label)
    prob = []

    invs = [r for r, v in vals.items() if v == INV_VALUE]
    if len(invs) != 1:
        prob.append('%s: expected exactly ONE single-gate inverter, found %d '
                    '%s. The whole safety argument rests on the complement '
                    'being produced by one gate from one net.'
                    % (label, len(invs), sorted(invs)))
        return prob
    inv = invs[0]
    R_ = nets.get((inv, INV_A), '<open>')
    RN = nets.get((inv, INV_Y), '<open>')
    if nets.get((inv, INV_VCC)) != v3 or nets.get((inv, INV_GND)) != gnd:
        prob.append('%s: inverter %s is not powered from %s / %s'
                    % (label, inv, v3, gnd))
    if R_ == '<open>' or RN == '<open>' or R_ == RN:
        prob.append('%s: inverter %s input/output nets are %s / %s'
                    % (label, inv, R_, RN))
        return prob
    print('  inverter %s: %s -> %s (NOT), powered %s / %s'
          % (inv, R_, RN, v3, gnd))

    # (a) the strap net must come from ONE three-pin header spanning the rails
    strap_hdrs = set()
    for (ref, pad), n in nets.items():
        if n == R_ and ref.startswith('J'):
            strap_hdrs.add(ref)
    if len(strap_hdrs) != 1:
        prob.append('%s: %s is touched by %d connectors %s; it must be one '
                    '1x3 header with ONE shunt' % (label, R_,
                                                   len(strap_hdrs),
                                                   sorted(strap_hdrs)))
    else:
        hdr = sorted(strap_hdrs)[0]
        hp = {nets.get((hdr, p), '<open>') for p in ('1', '2', '3')}
        if hp != {v3, R_, gnd}:
            prob.append('%s: strap header %s pins are %s, expected exactly '
                        '{%s, %s, %s}' % (label, hdr, sorted(hp), v3, R_,
                                          gnd))
        else:
            print('  strap header %s: pin 1 = %s, pin 2 = %s, pin 3 = %s - '
                  'ONE shunt, so the two levels have ONE control point'
                  % (hdr, v3, R_, gnd))

    # (b) the complement must carry a pull-UP, not a pull-down: a dead
    #     inverter has to DISABLE a port, never enable one.
    up = down = 0
    for (ref, pad), n in nets.items():
        if n != RN or not ref.startswith('R'):
            continue
        other = nets.get((ref, '2' if pad == '1' else '1'), '<open>')
        if other == v3:
            up += 1
        elif other == gnd:
            down += 1
    if up < 1 or down:
        prob.append('%s: %s has %d pull-up(s) to %s and %d pull-down(s) to '
                    '%s. It MUST be pulled UP: a missing or dead inverter '
                    'then reads high, which disables the G2 port toward the '
                    'host instead of enabling it.'
                    % (label, RN, up, v3, down, gnd))
    else:
        print('  %s pulled UP to %s (%d resistor(s)), no pull-down - a dead '
              'inverter disables a port, it cannot enable one' % (RN, v3, up))

    # (c) classify every LVDS driver by its enable net
    by_en = {}
    for r, v in sorted(vals.items()):
        if v != DRV_VALUE:
            continue
        en = nets.get((r, DRV_EN), '<open>')
        enb = nets.get((r, DRV_ENB), '<open>')
        if enb != gnd:
            prob.append('%s: driver %s EN* = %s, expected %s'
                        % (label, r, enb, gnd))
        by_en.setdefault(en, []).append(r)
    for want, what in ((v3, 'the always-driven socket'),
                       (R_, 'auxiliary group G1'),
                       (RN, 'auxiliary group G2')):
        if len(by_en.get(want, [])) != 1:
            prob.append('%s: expected exactly one LVDS driver with EN = %s '
                        '(%s), found %s'
                        % (label, want, what, by_en.get(want, [])))
    stray = set(by_en) - {v3, R_, RN}
    if stray:
        prob.append('%s: LVDS driver enable(s) on unexpected net(s) %s'
                    % (label, sorted(stray)))
    if prob:
        return prob

    g1_drv = by_en[R_][0]
    g2_drv = by_en[RN][0]
    grp = {R_: _pairs_driven(nets, g1_drv, aux_pfx),
           RN: _pairs_driven(nets, g2_drv, aux_pfx)}
    if grp[R_] != set(AUX_G1) or grp[RN] != set(AUX_G2):
        prob.append('%s: driver %s (EN=%s) drives pairs %s and %s (EN=%s) '
                    'drives %s; PINMAP.md 2.3 says G1 = %s and G2 = %s'
                    % (label, g1_drv, R_, sorted(grp[R_]), g2_drv, RN,
                       sorted(grp[RN]), list(AUX_G1), list(AUX_G2)))
        return prob
    print('  driver %s EN=%-7s drives AUX %s   (group G1)'
          % (g1_drv, R_, sorted(grp[R_])))
    print('  driver %s EN=%-7s drives AUX %s   (group G2)'
          % (g2_drv, RN, sorted(grp[RN])))

    # (d) map the AUX receiver's outputs back to the pair they came from, so
    #     a buffer port's inputs can be turned into a set of pair names.
    rcv_out_pair = {}
    for r, v in sorted(vals.items()):
        if v != RCV_VALUE:
            continue
        for ch in sorted(RCV_P):
            pin = role(nets.get((r, RCV_P[ch]), '<open>'), aux_pfx)
            if not pin or not pin.endswith('_P'):
                continue
            o = nets.get((r, RCV_OUT[ch]), '<open>')
            if o != '<open>':
                rcv_out_pair[o] = pin[:-2]
    if set(rcv_out_pair.values()) != set(AUX_G1) | set(AUX_G2):
        prob.append('%s: the AUX receiver covers pairs %s, not all four. '
                    'Both groups must have a receive path in both roles or '
                    'the board is not role-switchable.'
                    % (label, sorted(set(rcv_out_pair.values()))))
        return prob

    # (e) every buffer/translator port whose inputs are AUX receiver outputs
    #     must be enabled by the strap, never by a constant - and by the SAME
    #     net as the driver for that group.
    seen = {}
    for r, v in sorted(vals.items()):
        if v != X4_VALUE:
            continue
        for port, (a_pads, b_pads, oe_pad) in sorted(X4_PORTS.items()):
            src = [nets.get((r, p), '<open>') for p in a_pads]
            pairs = {rcv_out_pair[x] for x in src if x in rcv_out_pair}
            oe = nets.get((r, oe_pad), '<open>')
            if not pairs:
                # not an auxiliary port; a constant enable is fine there
                continue
            if oe in (v3, gnd):
                prob.append('%s: %s port %d carries AUX pairs %s toward the '
                            'host but its OE* is tied to the constant %s. '
                            'That is the contention case: the host drives '
                            'those pins in one role.'
                            % (label, r, port, sorted(pairs), oe))
                continue
            if oe not in (R_, RN):
                prob.append('%s: %s port %d carries AUX pairs %s and its OE* '
                            'is on %s, which is neither %s nor %s'
                            % (label, r, port, sorted(pairs), oe, R_, RN))
                continue
            seen.setdefault(oe, set()).update(pairs)
            print('  buffer %s port %d OE*=%-7s carries AUX %s toward the '
                  'host' % (r, port, oe, sorted(pairs)))
    for netname in (R_, RN):
        if netname not in seen:
            prob.append('%s: no buffer port toward the host is enabled by '
                        '%s, so one auxiliary direction can never be '
                        'received' % (label, netname))
    if prob:
        return prob

    # (f) THE INVARIANT.  For each group, the driver's active-HIGH EN and the
    #     toward-host port's active-LOW OE* are the same net.  Enumerate both
    #     levels of the single strap net and show that nothing contends.
    print()
    print('  the invariant, enumerated over every state the ONE strap net '
          'can be in:')
    ok = True
    for lvl in (1, 0):
        levels = {R_: lvl, RN: 1 - lvl}
        rolename = 'ROLE A' if lvl else 'ROLE B'
        for gname, gnet, drv_ref in (('G1', R_, g1_drv),
                                     ('G2', RN, g2_drv)):
            drives_cable = levels[gnet] == 1          # EN active high
            # the toward-host port for this group is the one enabled by gnet
            drives_host = levels[gnet] == 0           # OE* active low
            if gnet not in seen or seen[gnet] != grp[gnet]:
                prob.append('%s: group %s is driven onto the cable by %s '
                            '(EN=%s) for pairs %s, but the port driving it '
                            'toward the host covers %s. The two must be the '
                            'same group.'
                            % (label, gname, drv_ref, gnet, sorted(grp[gnet]),
                               sorted(seen.get(gnet, set()))))
                ok = False
            if drives_cable and drives_host:
                prob.append('%s: CONTENTION - in %s, group %s is driven onto '
                            'the cable AND toward the host at once.'
                            % (label, rolename, gname))
                ok = False
            print('    %s (%s=%d, %s=%d): %s driver %s, toward-host port %s'
                  % (rolename, R_, levels[R_], RN, levels[RN], gname,
                     'ON ' if drives_cable else 'off',
                     'ON ' if drives_host else 'off'))
    # the "both low" state the rejected two-shunt scheme allowed is not
    # reachable at all, and that is the point worth stating.
    if ok:
        print('  %s = NOT %s by construction, so the state that enabled a '
              'host-facing port while the host drove the same pins - the '
              'one a two-shunt changeover allowed - is UNREACHABLE.'
              % (RN, R_))
    return prob


def main():
    hl2, hl2v = load(export('hl2-bridge'))
    tang, tangv = load(export('tang-bridge'))
    prob = []

    prob += check_header(hl2, 'J1', DB1, 'board A J1 on HL2 DB1')
    prob += check_header(hl2, 'J2', DB12, 'board A J2 on HL2 DB12')
    prob += check_header(tang, 'J1', J14, 'board B J1 on Tang dock J14',
                         open_ok=[n for n in range(1, 41) if n not in J14])
    print('=== hl2-bridge, three mini HDMI (Type C) sockets ===')
    prob += check_sockets(hl2, 'C', {'J3': 'O', 'J4': 'AX', 'J5': 'I'})
    print('=== tang-bridge, three full-size HDMI (Type A) sockets ===')
    prob += check_sockets(tang, 'A', {'J2': 'I', 'J3': 'AX', 'J4': 'O'})

    prob += check_cable(
        'straight mini-to-mini: board A OUT -> another board A IN '
        '(the two-radio case, 921.6 Mbit/s each way)',
        hl2, 'J3', 'O', 'C', hl2, 'J5', 'I', 'C')
    prob += check_cable(
        'straight mini-to-mini: board A AUX -> another board A AUX '
        '(self-complementary: G1 must land on G1)',
        hl2, 'J4', 'AX', 'C', hl2, 'J4', 'AX', 'C')
    prob += check_cable(
        'mini-to-full-size: board A OUT -> board B IN (cable 1, forward)',
        hl2, 'J3', 'O', 'C', tang, 'J2', 'I', 'A')
    prob += check_cable(
        'mini-to-full-size: board B OUT -> board A IN (cable 2, reverse)',
        tang, 'J4', 'O', 'A', hl2, 'J5', 'I', 'C')
    prob += check_cable(
        'mini-to-full-size: board A AUX <-> board B AUX (cable 3, auxiliary)',
        hl2, 'J4', 'AX', 'C', tang, 'J3', 'AX', 'A')

    prob += check_strap(hl2, hl2v, 'board A (hl2-bridge)', 'AX', '+3V3')
    prob += check_strap(tang, tangv, 'board B (tang-bridge)', 'AX', '+3V3')

    print()
    for p in prob:
        print('  !! ' + p)
    print('  %s' % ('OK - all six sockets share one signal-to-role mapping, '
                    'every cable lands every signal on its counterpart, the '
                    'auxiliary socket is self-complementary, and no state of '
                    'either strap can produce contention'
                    if not prob else '%d PROBLEMS' % len(prob)))
    return 1 if prob else 0


if __name__ == '__main__':
    sys.exit(main())
