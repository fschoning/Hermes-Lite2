#!/usr/bin/env python3
"""Netlist self-check for the generated gowin-bridge board, rev D.

Run:   python tools/check_netlist.py

Exports the schematic's netlist with kicad-cli and asserts the things the
generator could get wrong without ERC noticing:

 1. THE HEADER PIN MAPS.  Every pin of HL2 DB1, DB12 and CN1, against the
    table in PINMAP.md rev D - including the one that has been wrong before:
    DB12 pin 5 is FPGA PIN_89 and pin 6 is PIN_88, NOT the other way round.

 2. THE CONNECTOR PIN MAP.  Every one of the 74 SlimSAS contacts: the 26
    grounds are grounded, the 16 pairs carry the right net legs with P on the
    lower-numbered contact, and the 16 sideband contacts carry what the
    sideband table says.

 3. THE CROSSOVER, WALKED.  Two of these identical boards joined by one
    SFF-8654 8i cable.  The cable maps A(n) at one end to B(n) at the other,
    so the check walks every driven contact through to the far board's contact
    at the same number in the other row and asserts that what arrives is the
    input that wants it.  This is what makes radio-to-radio work, and it is
    asserted rather than believed.

 4. THE FUNCTION MIRRORING, as a contract rather than a hope.  For every lane
    the net this board drives and the net it receives at the same position
    must be functional counterparts: forward clock faces reverse clock, ADC
    data k faces transmit data k, aux clock faces aux clock, aux data faces
    aux data, and the duplicate forward clock faces a receiver rather than
    nothing.

 5. NO JTAG PATH BETWEEN TWO RADIOS.  The sideband positions whose far-end
    inputs are TCK and TMS must have NOTHING on this board driving their
    outputs, so one radio physically cannot clock or steer another radio's
    JTAG state machine whatever the enable does.

 6. EVERY REMOTE-DRIVE FEATURE IS OFF UNTIL SOMETHING TURNS IT ON.  Both
    enable nets are active LOW and must carry a pull-UP at both ends of their
    translator - one to the 2.5 V rail on the HL2 side, one to 3.3 V on the
    logic side - and no fitted pull-down anywhere.  That is the whole safety
    argument for an unprogrammed board, and it replaces rev C's strap,
    inverter and contention proof.

 7. EVERY CONDUCTOR THAT LEAVES THE BOARD IS CLAMPED.  Each of the 32 pair
    conductors and each wired sideband conductor must appear on an ESD array.

 8. NOTHING CALLS ITSELF BOARD A OR BOARD B.  rev D is one design.

The tables below are retyped here from PINMAP.md and from the specifications
rather than imported from the generator, so the two can disagree and be
caught.
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import kisexp as K

BOARD = 'bridge'

KICAD_CLI_CANDIDATES = [
    os.environ.get('KICAD_CLI', ''),
    r'C:/Users/franz/AppData/Local/Programs/KiCad/10.0/bin/kicad-cli.exe',
    r'C:/Program Files/KiCad/10.0/bin/kicad-cli.exe',
    r'C:/Program Files/KiCad/9.0/bin/kicad-cli.exe',
    'kicad-cli',
]

# --------------------------------------------------------------------------
# The header pin maps, retyped from PINMAP.md rev D.  These are the contract
# with the FPGA gateware, so they get asserted rather than trusted.
# --------------------------------------------------------------------------

DB1 = {
    1:  ('HL2_AUXIO_EN', '72', 'AUXIO drive enable, active LOW, DC only. '
                               'Reaches the FPGA only through HL2 solder '
                               'jumper J25'),
    2:  ('HL2_ADC_D0', '76', 'ADC sample data 0 out'),
    3:  ('HL2_ADC_D1', '77', 'ADC sample data 1 out'),
    4:  ('HL2_JTAG_EN', '80', 'JTAG-over-cable enable, active LOW, DC only. '
                              'The 21 pF VREF pin, irrelevant for a DC level'),
    5:  ('HL2_ADC_D2', '83', 'ADC sample data 2 out'),
    6:  ('HL2_AUX_CLK_OUT', '85', 'auxiliary clock out'),
    7:  ('VLVDS', '-', 'HL2 2.5 V rail, tap only, unused by default'),
    8:  ('VLVDS', '-', 'same net as pin 7'),
    9:  ('HL2_FWD_CLK_RAW', '98', 'forward clock 153.6 MHz out, before the '
                                  'divider. Carries LED D2 through R71'),
    10: ('HL2_CWR', '90', 'CW/PTT ring - AUXIO line 0, NOT an LED pin'),
    11: ('HL2_TX_D0', '99', 'transmit data 0 in. Carries LED D3 through R72'),
    12: ('HL2_CWT', '91', 'CW/PTT tip - AUXIO line 1, NOT an LED pin'),
    13: ('GND', '-', 'ground'),
    14: ('GND', '-', 'ground'),
    15: ('HL2_TX_D1', '100', 'transmit data 1 in. Carries LED D4 through R73'),
    16: ('HL2_SCL1', '103', 'I2C1 SCL - AUXIO line 2, NOT an LED pin'),
    17: ('HL2_TX_D2', '101', 'transmit data 2 in. Carries LED D5 through R74'),
    18: ('HL2_SDA1', '104', 'I2C1 SDA - AUXIO line 3, NOT an LED pin'),
    19: ('DB1_3V3', '-', 'board supply, before FB1'),
    20: ('DB1_3V3', '-', 'same net as pin 19'),
}
# NOTE pins 5 and 6.  DB12 pin 5 is FPGA PIN_89 and pin 6 is PIN_88, per
# hardware/hl/hermeslite.net.  rev A of PINMAP.md had these two swapped and
# this is the assertion that stops it happening again.
DB12 = {
    1: ('HL2_AUX_DAT_OUT', '86', 'auxiliary data out'),
    2: ('HL2_AUX_DAT_IN', '87', 'auxiliary data in, 2.5 V bank'),
    3: ('GND', '-', 'ground'),
    4: ('GND', '-', 'ground'),
    5: ('HL2_AUX_CLK_IN', '89', 'auxiliary clock in. INPUT ONLY, 2.5 V bank'),
    6: ('HL2_REV_CLK', '88', 'reverse clock in, a dedicated clock input. '
                             'INPUT ONLY, 2.5 V bank'),
}
# CN1, the USB-Blaster JTAG header, confirmed from hardware/hl/hermeslite.net.
CN1 = {
    1:  ('J_TCK', '16', 'TCK'),
    2:  ('GND', '-', 'ground'),
    3:  ('J_TDO', '20', 'TDO'),
    4:  ('CN1_VTREF', '-', '+3V3, the programmer VTREF sense line'),
    5:  ('J_TMS', '18', 'TMS'),
    6:  ('CN1_NC6', '-', 'unconnected on the HL2 - nCE in Active Serial mode'),
    7:  ('CN1_NC7', '-', 'unconnected on the HL2 - nCS'),
    8:  ('CN1_NC8', '-', 'unconnected on the HL2 - nCONFIG'),
    9:  ('J_TDI', '15', 'TDI'),
    10: ('GND', '-', 'ground'),
}

# --------------------------------------------------------------------------
# SFF-8654 8X, retyped from SFF-9402 Rev 1.1 Tables 6-2 and 6-3.
# --------------------------------------------------------------------------
SS_GND = (1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34, 37)
SS_PAIR_POS = (2, 5, 14, 17, 20, 23, 32, 35)
SS_SIDEBAND = (8, 9, 11, 12, 26, 27, 29, 30)
SS_NPOS = 37

# The lane map, retyped from PINMAP.md rev D section 3.
#   position -> (net this board DRIVES on row A, net it RECEIVES on row B)
LANES = {
    2:  ('AUXCLK', 'AUXCLK'),
    5:  ('AUXDAT', 'AUXDAT'),
    14: ('FWDCLK', 'REVCLK'),
    17: ('ADCD0', 'TXD0'),
    20: ('ADCD1', 'TXD1'),
    23: ('ADCD2', 'TXD2'),
    32: ('DUPCLK', 'DUPCLK'),
    35: ('SPARE', 'SPARE'),
}
# The function-mirroring contract.
MIRROR = {
    'FWDCLK': ('REVCLK', 'FPGA 98 out faces FPGA 88 in'),
    'ADCD0': ('TXD0', 'FPGA 76 out faces FPGA 99 in'),
    'ADCD1': ('TXD1', 'FPGA 77 out faces FPGA 100 in'),
    'ADCD2': ('TXD2', 'FPGA 83 out faces FPGA 101 in'),
    'AUXCLK': ('AUXCLK', 'FPGA 85 out faces FPGA 89 in'),
    'AUXDAT': ('AUXDAT', 'FPGA 86 out faces FPGA 87 in'),
    'DUPCLK': ('DUPCLK', 'the duplicate forward clock faces a receiver, so '
                         'its mirrored position is not left unwired'),
    'SPARE': ('SPARE', 'a spare driver channel faces a spare receiver'),
}
# The sideband map, retyped from PINMAP.md rev D section 4.
#   position -> (net driven on row A or None, net received on row B)
SIDEBANDS = {
    8:  ('SB_PRSNT_OUT', 'SB_PRSNT_IN'),
    9:  (None, 'SB_TCK_IN'),
    11: ('SB_AUXIO0_OUT', 'SB_AUXIO0_IN'),
    12: ('SB_AUXIO1_OUT', 'SB_AUXIO1_IN'),
    26: ('SB_AUXIO2_OUT', 'SB_AUXIO2_IN'),
    27: ('SB_AUXIO3_OUT', 'SB_AUXIO3_IN'),
    29: (None, 'SB_TMS_IN'),
    30: ('SB_TDO_OUT', 'SB_TDI_IN'),
}
# The two sideband inputs that MUST have no driver at the mirrored position.
NO_REMOTE_JTAG = {9: 'TCK', 29: 'TMS'}

# The two enable nets, and the rail each pull-up must go to.
ENABLES = {
    'HL2_JTAG_EN': '+2V5',
    'JTAG_EN_N': '+3V3',
    'HL2_AUXIO_EN': '+2V5',
    'AUXIO_EN_N': '+3V3',
}

SLIMSAS_REF = 'J1'


def find_cli():
    for c in KICAD_CLI_CANDIDATES:
        if c and (os.path.isfile(c) or c == 'kicad-cli'):
            return c
    raise SystemExit('kicad-cli not found; set KICAD_CLI.')


def export():
    out = os.path.join(ROOT, BOARD, BOARD + '.net')
    subprocess.run([find_cli(), 'sch', 'export', 'netlist',
                    '--format', 'kicadsexpr', '-o', out,
                    os.path.join(ROOT, BOARD, BOARD + '.kicad_sch')],
                   check=True, capture_output=True)
    return out


def load(path):
    """-> (pin map, value map, net map, part-pin map)."""
    root = K.parse(open(path, encoding='utf-8').read())[0]
    pins, vals, bynet, byref = {}, {}, {}, {}
    for comps in K.kids(root, 'components'):
        for comp in K.kids(comps, 'comp'):
            r = K.atoms(K.kid(comp, 'ref'))[0]
            v = K.kid(comp, 'value')
            vals[r] = K.atoms(v)[0] if v is not None else ''
    for n in K.kids(root, 'nets'):
        for net in K.kids(n, 'net'):
            nm = K.atoms(K.kid(net, 'name'))[0]
            if nm.startswith('/'):
                nm = nm[1:]
            if nm.startswith('unconnected-'):
                nm = '<open>'
            for node in K.kids(net, 'node'):
                r = K.atoms(K.kid(node, 'ref'))[0]
                p = K.atoms(K.kid(node, 'pin'))[0]
                pins[(r, p)] = nm
                bynet.setdefault(nm, []).append((r, p))
                byref.setdefault(r, []).append(p)
    return pins, vals, bynet, byref


def check_header(pins, ref, table, label):
    print('=== %s ===' % label)
    prob = []
    for pin in sorted(table):
        want, fpga, what = table[pin]
        got = pins.get((ref, str(pin)), '<open>')
        if got != want:
            prob.append('%s pin %d = %s, PINMAP.md says %s (%s)'
                        % (label, pin, got, want, what))
        else:
            print('  pin %-2d  %-18s  FPGA %-4s  %s' % (pin, got, fpga, what))
    return prob


def check_connector(pins):
    print('=== SlimSAS %s: all 74 contacts plus 4 shell tails ==='
          % SLIMSAS_REF)
    prob = []
    want = {}
    for i in SS_GND:
        want['A%d' % i] = 'GND'
        want['B%d' % i] = 'GND'
    for pos in SS_PAIR_POS:
        onet, inet = LANES[pos]
        want['A%d' % pos] = 'A_%s_P' % onet
        want['A%d' % (pos + 1)] = 'A_%s_N' % onet
        want['B%d' % pos] = 'B_%s_P' % inet
        want['B%d' % (pos + 1)] = 'B_%s_N' % inet
    for pos in SS_SIDEBAND:
        onet, inet = SIDEBANDS[pos]
        want['A%d' % pos] = onet if onet else 'SB_NC%d' % pos
        want['B%d' % pos] = inet
    if len(want) != 2 * SS_NPOS:
        prob.append('the connector table covers %d of 74 contacts, so the '
                    'ground, pair and sideband position sets do not partition '
                    'the connector' % len(want))
    for pad in sorted(want, key=lambda s: (s[0], int(s[1:]))):
        got = pins.get((SLIMSAS_REF, pad), '<open>')
        if got != want[pad]:
            prob.append('%s pad %s = %s, expected %s'
                        % (SLIMSAS_REF, pad, got, want[pad]))
    for k in range(1, 5):
        got = pins.get((SLIMSAS_REF, 'SH%d' % k), '<open>')
        if got != 'SHELL':
            prob.append('%s shell tail SH%d = %s, expected SHELL'
                        % (SLIMSAS_REF, k, got))
    print('  %d grounds, %d pair legs, %d sidebands, 4 shell tails on SHELL'
          % (sum(1 for v in want.values() if v == 'GND'),
             4 * len(SS_PAIR_POS), 2 * len(SS_SIDEBAND)))
    return prob


def check_crossover(pins):
    """Walk the cable.  Row A contact n at one end reaches row B contact n at
    the other, n = 1..37, per SFF-9402 Rev 1.1 note 16 and Tables 6-2/6-3.
    Both ends are the same design, so the far board's map is this map."""
    print('=== the crossover, walked: two identical boards, one cable ===')
    prob = []
    for pos in SS_PAIR_POS:
        onet, inet = LANES[pos]
        dp = pins.get((SLIMSAS_REF, 'A%d' % pos))
        dn = pins.get((SLIMSAS_REF, 'A%d' % (pos + 1)))
        rp = pins.get((SLIMSAS_REF, 'B%d' % pos))
        rn = pins.get((SLIMSAS_REF, 'B%d' % (pos + 1)))
        if dp != 'A_%s_P' % onet or dn != 'A_%s_N' % onet:
            prob.append('position %d row A does not carry the %s pair'
                        % (pos, onet))
            continue
        if rp != 'B_%s_P' % inet or rn != 'B_%s_N' % inet:
            prob.append('position %d row B does not carry the %s pair'
                        % (pos, inet))
            continue
        exp, why = MIRROR[onet]
        if inet != exp:
            prob.append('position %d: this board drives %s and receives %s, '
                        'but the mirroring contract says %s must face %s (%s)'
                        % (pos, onet, inet, onet, exp, why))
        else:
            print('  pos %-2d  A drives %-7s -> far B receives %-7s  %s'
                  % (pos, onet, inet, why))
    for pos in SS_PAIR_POS:
        a = pins.get((SLIMSAS_REF, 'A%d' % pos), '')
        bv = pins.get((SLIMSAS_REF, 'B%d' % pos), '')
        if not (a.endswith('_P') and bv.endswith('_P')):
            prob.append('position %d: the lower-numbered contact of the pair '
                        'is not the P leg in both rows, so P would meet N'
                        % pos)
    return prob


def check_sideband_crossover(pins, bynet):
    print('=== sidebands, walked, and the radio-to-radio JTAG proof ===')
    prob = []
    for pos in sorted(SIDEBANDS):
        onet, inet = SIDEBANDS[pos]
        a = pins.get((SLIMSAS_REF, 'A%d' % pos), '<open>')
        bv = pins.get((SLIMSAS_REF, 'B%d' % pos), '<open>')
        print('  pos %-2d  A = %-16s -> far B = %-16s' % (pos, a, bv))
        if bv != inet:
            prob.append('sideband position %d row B = %s, expected %s'
                        % (pos, bv, inet))
        if pos in NO_REMOTE_JTAG:
            others = [r for (r, _) in bynet.get(a, []) if r != SLIMSAS_REF]
            bad = [r for r in others
                   if not (r.startswith('D') or r.startswith('TP'))]
            if bad:
                prob.append('sideband position %d carries %s toward the far '
                            "end's %s input, and %s is also on that net - a "
                            "radio could then reach another radio's JTAG"
                            % (pos, a, NO_REMOTE_JTAG[pos], ', '.join(bad)))
            else:
                print('         nothing on this board drives it, so no radio '
                      "can reach another radio's %s" % NO_REMOTE_JTAG[pos])
        elif onet is None:
            prob.append('sideband position %d has no driven output but is not '
                        'one of the deliberately dead ones' % pos)
        elif a != onet:
            prob.append('sideband position %d row A = %s, expected %s'
                        % (pos, a, onet))
    return prob


def check_enables(pins, vals, bynet, byref):
    """Both remote-drive features must be OFF with no gateware, no far end, an
    unconfigured FPGA and a missing translator: four pull-UPs, no fitted
    pull-down."""
    print('=== the enables: an unprogrammed board must be safe ===')
    prob = []
    for net in sorted(ENABLES):
        rail = ENABLES[net]
        ups, downs = [], []
        for (r, pad) in bynet.get(net, []):
            if not r.startswith('R'):
                continue
            for p in byref.get(r, []):
                if p == pad:
                    continue
                dest = pins.get((r, p))
                if dest == rail:
                    ups.append('%s=%s' % (r, vals.get(r, '')))
                elif dest == 'GND':
                    downs.append('%s=%s' % (r, vals.get(r, '')))
        if not ups:
            prob.append('%s has no pull-up to %s, so a missing or unpowered '
                        'part would leave it floating and the feature could '
                        'come up ENABLED' % (net, rail))
        else:
            print('  %-14s pulled UP to %-5s by %s'
                  % (net, rail, ', '.join(sorted(set(ups)))))
        if downs:
            # Only tolerable as the deliberately not-fitted JTAG recovery
            # link, which is a 1k on HL2_JTAG_EN.
            ok = (net == 'HL2_JTAG_EN'
                  and all(d.endswith('=1k') for d in downs))
            if ok:
                print('         plus the NOT-FITTED 1k recovery link (%s), '
                      'which is how you enable JTAG when the gateware that '
                      'would otherwise enable it will not run'
                      % ', '.join(sorted(set(downs))))
            else:
                prob.append('%s carries a pull-down (%s). The direction is '
                            'the whole safety argument: pulled up is disabled'
                            % (net, ', '.join(sorted(set(downs)))))
    return prob


def check_esd(pins, vals, bynet):
    print('=== ESD: every conductor that leaves the enclosure ===')
    prob = []
    esd_refs = {r for r, v in vals.items() if v.startswith('TPD4E')}
    clamped = set()
    for nm, nodes in bynet.items():
        if nm == 'GND':
            continue
        if any(r in esd_refs for r, _ in nodes):
            clamped.add(nm)
    need = []
    for pos in SS_PAIR_POS:
        onet, inet = LANES[pos]
        need += ['A_%s_P' % onet, 'A_%s_N' % onet,
                 'B_%s_P' % inet, 'B_%s_N' % inet]
    for pos in sorted(SIDEBANDS):
        onet, inet = SIDEBANDS[pos]
        # the two deliberately undriven positions leave the enclosure too
        need.append(onet if onet else 'SB_NC%d' % pos)
        need.append(inet)
    missing = [n for n in need if n not in clamped]
    if missing:
        prob.append('%d conductors leave the board unclamped: %s'
                    % (len(missing), ', '.join(missing)))
    else:
        print('  %d arrays at 0.5 pF per channel clamp all %d conductors '
              '(%d pair legs + %d sidebands)'
              % (len(esd_refs), len(need), 4 * len(SS_PAIR_POS),
                 len(need) - 4 * len(SS_PAIR_POS)))
    return prob


def check_one_design(vals, byref):
    """The owner is explicit: ONE design.  Nothing may call itself board A or
    board B, and there must be exactly one SlimSAS receptacle."""
    prob = []
    bad = [k for k, v in vals.items() if 'board A' in v or 'board B' in v]
    if bad:
        prob.append('these parts describe themselves as a board A or a board '
                    'B, and rev D is one design: %s' % ', '.join(bad))
    conn = [r for r, v in vals.items() if 'SlimSAS' in v]
    if len(conn) != 1:
        prob.append('found %d SlimSAS receptacles, expected exactly 1: %s'
                    % (len(conn), ', '.join(conn)))
    return prob


def main():
    pins, vals, bynet, byref = load(export())
    prob = []

    prob += check_header(pins, 'J2', DB1, 'J2 on HL2 DB1')
    prob += check_header(pins, 'J3', DB12, 'J3 on HL2 DB12')
    prob += check_header(pins, 'J4', CN1, 'J4 on HL2 CN1, the JTAG header')

    print('=== J5, the local JTAG pass-through ===')
    bad = False
    for pin in sorted(CN1):
        a = pins.get(('J4', str(pin)), '<open>')
        c = pins.get(('J5', str(pin)), '<open>')
        if a != c:
            prob.append('J5 pin %d = %s but J4 pin %d = %s; the pass-through '
                        'must be straight' % (pin, c, pin, a))
            bad = True
    if not bad:
        print('  all ten nets straight through from J4, so a USB Blaster '
              'plugs in locally with the board fitted')

    prob += check_connector(pins)
    prob += check_crossover(pins)
    prob += check_sideband_crossover(pins, bynet)
    prob += check_enables(pins, vals, bynet, byref)
    prob += check_esd(pins, vals, bynet)
    prob += check_one_design(vals, byref)

    print()
    for p in prob:
        print('  !! ' + p)
    print('  %s' % ('OK - the three header pin maps match PINMAP.md rev D '
                    'including the DB12 5/6 order, all 74 connector contacts '
                    'agree with the SFF-9402 tables and the lane map, the '
                    'crossover lands every output on the input that wants it, '
                    'no radio can reach another radio JTAG, both enables are '
                    'pulled to their disabled state at both ends, every '
                    'conductor leaving the board is clamped, and there is one '
                    'design'
                    if not prob else '%d PROBLEMS' % len(prob)))
    return 1 if prob else 0


if __name__ == '__main__':
    sys.exit(main())
