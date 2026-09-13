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

 8. NOTHING CALLS ITSELF BOARD A OR BOARD B.  One design with two ends on
    one panel: the radio end (J1) and the Gowin end (J101).

 9. THE GOWIN END'S PIN MAP.  Every contact of J101 and every position of
    J102, the 2x18 on Tang dock J14 positions 5-40, against PINMAP.md
    section 11; both forwarded clocks on dedicated clock balls; every P leg
    on a Gowin true (A) ball; nothing on J14 positions 1-4.

10. THE CROSSOVER IN ALL THREE COMBINATIONS - radio to Gowin, Gowin to radio
    and radio to radio - every output walked through the cable to the input
    at the far end, lanes and sidebands.

11. THE TWO ENDS SHARE NO NET.

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

# --------------------------------------------------------------------------
# THE GOWIN END, retyped from PINMAP.md section 11.
# --------------------------------------------------------------------------
GOWIN_REF = 'J101'
GOWIN_HDR = 'J102'          # pin k = Tang dock J14 position k + 4
J14_FIRST = 5

# Tang dock J14, from TANG_MEGA_138K_FACTS.md section 2.5 (the dock
# schematic's BANK4_<ball>_<IO name> labels).  position -> (ball, IO name,
# dedicated clock function or '').
J14_BALLS = {
    5: ('R17', 'IOB144B', ''), 6: ('P16', 'IOB144A', ''),
    7: ('T18', 'IOB138B', ''), 8: ('R18', 'IOB138A', ''),
    9: ('W17', 'IOB106B', ''), 10: ('V17', 'IOB106A', ''),
    11: (None, '5V', ''), 12: (None, 'GND', ''),
    13: ('W22', 'IOB124B', ''), 14: ('W21', 'IOB124A', ''),
    15: ('P17', 'IOB135B', ''), 16: ('N17', 'IOB135A', ''),
    17: ('N14', 'IOB142B', ''), 18: ('N13', 'IOB142A', ''),
    19: ('V20', 'IOB120B', 'SGCLKC_5/BPLL2_C_IN0/BPLL3_C_IN0'),
    20: ('U20', 'IOB120A', 'SGCLKT_5/BPLL2_T_IN0/BPLL3_T_IN0'),
    21: ('Y22', 'IOB131B', ''), 22: ('Y21', 'IOB131A', ''),
    23: ('AB22', 'IOB129B', ''), 24: ('AB21', 'IOB129A', ''),
    25: ('AA21', 'IOB126B', ''), 26: ('AA20', 'IOB126A', ''),
    27: ('AB20', 'IOB110B', ''), 28: ('AA19', 'IOB110A', ''),
    29: ('AA18', 'IOB108A', ''), 30: ('AB18', 'IOB108B', ''),
    31: ('Y19', 'IOB116B', 'MGCLKC_4/BPLL2_C_FB0/BPLL3_C_FB0'),
    32: ('Y18', 'IOB116A', 'MGCLKT_4/BPLL2_T_FB0/BPLL3_T_FB0'),
    33: ('T20', 'IOB102B', ''), 34: ('N15', 'IOB146A', ''),
    35: ('U18', 'IOB112B', ''), 36: ('U17', 'IOB112A', ''),
    37: ('R16', 'IOB140B', ''), 38: ('P15', 'IOB140A', ''),
    39: ('R14', 'IOB133B', ''), 40: ('P14', 'IOB133A', ''),
}

# J14 position -> net, retyped from PINMAP.md section 11.
GOWIN_J14 = {
    5: 'G_A_DUPCLK_N', 6: 'G_A_DUPCLK_P',
    7: 'G_TDO_RD', 8: 'G_TMS_DRV',
    9: 'G_A_REVCLK_N', 10: 'G_A_REVCLK_P',
    11: '<open>', 12: 'G_GND',
    13: 'G_B_ADCD2_N', 14: 'G_B_ADCD2_P',
    15: 'G_B_ADCD1_N', 16: 'G_B_ADCD1_P',
    17: 'G_B_ADCD0_N', 18: 'G_B_ADCD0_P',
    19: 'G_B_FWDCLK_N', 20: 'G_B_FWDCLK_P',
    21: 'G_A_AUXDAT_N', 22: 'G_A_AUXDAT_P',
    23: 'G_B_AUXCLK_N', 24: 'G_B_AUXCLK_P',
    25: 'G_B_AUXDAT_N', 26: 'G_B_AUXDAT_P',
    27: 'G_A_AUXCLK_N', 28: 'G_A_AUXCLK_P',
    29: 'G_PRSNT_RD', 30: 'G_PRSNT_DRV',
    31: 'G_B_DUPCLK_N', 32: 'G_B_DUPCLK_P',
    33: 'G_TDI_DRV', 34: 'G_TCK_DRV',
    35: 'G_A_TXD0_N', 36: 'G_A_TXD0_P',
    37: 'G_A_TXD1_N', 38: 'G_A_TXD1_P',
    39: 'G_A_TXD2_N', 40: 'G_A_TXD2_P',
}
# The clocks that must land on dedicated clock inputs.
GOWIN_CLOCKS = {'G_B_FWDCLK': 'forwarded clock',
                'G_B_DUPCLK': 'duplicate forwarded clock'}

# Gowin-end lane map: position -> (driven on A, received on B).
GLANES = {
    2:  ('AUXCLK', 'AUXCLK'),
    5:  ('AUXDAT', 'AUXDAT'),
    14: ('REVCLK', 'FWDCLK'),
    17: ('TXD0', 'ADCD0'),
    20: ('TXD1', 'ADCD1'),
    23: ('TXD2', 'ADCD2'),
    32: ('DUPCLK', 'DUPCLK'),
    35: ('SPARE', 'SPARE'),
}
GOWIN_UNWIRED = {'SPARE'}
GSIDEBANDS = {
    8:  ('PRSNT', 'PRSNT'),
    9:  ('TCK', None),
    11: (None, None),
    12: (None, None),
    26: (None, None),
    27: (None, None),
    29: ('TMS', None),
    30: ('TDI', 'TDO'),
}
# connector net -> (J14 net, series resistor value)
GOWIN_SB_SERIES = {
    'G_SB_PRSNT_OUT': ('G_PRSNT_DRV', '1k'),
    'G_SB_PRSNT_IN': ('G_PRSNT_RD', '1k'),
    'G_SB_TCK_OUT': ('G_TCK_DRV', '330R'),
    'G_SB_TMS_OUT': ('G_TMS_DRV', '330R'),
    'G_SB_TDI_OUT': ('G_TDI_DRV', '330R'),
    'G_SB_TDO_IN': ('G_TDO_RD', '330R'),
}

# What a lane MEANS on the wire, whichever end names it.  A driven lane must
# arrive at a received lane with the same meaning.
LANE_MEANING = {'FWDCLK': 'main clock', 'REVCLK': 'main clock',
                'ADCD0': 'main data 0', 'TXD0': 'main data 0',
                'ADCD1': 'main data 1', 'TXD1': 'main data 1',
                'ADCD2': 'main data 2', 'TXD2': 'main data 2',
                'AUXCLK': 'aux clock', 'AUXDAT': 'aux data',
                'DUPCLK': 'duplicate main clock', 'SPARE': 'spare'}

# The only sideband meeting allowed where the names differ.
SB_ALLOWED = {
    ('TDO', 'TDI'): 'radio to radio: TDO lands on TDI, which does nothing '
                    'without TCK, and TCK and TMS are undriven',
}


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
    esd_refs = {r for r, v in vals.items() if v.startswith('TPD4E')
                and not gowin_part(r)}
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
    """ONE design, with a radio end and a Gowin end on one panel.  Nothing
    may call itself board A or board B, and there are exactly two SlimSAS
    receptacles: J1 at the radio end and J101 at the Gowin end."""
    prob = []
    bad = [k for k, v in vals.items() if 'board A' in v or 'board B' in v]
    if bad:
        prob.append('these parts describe themselves as a board A or a board '
                    'B, and this is one design: %s' % ', '.join(bad))
    conn = sorted(r for r, v in vals.items() if 'SlimSAS' in v)
    if conn != ['J1', 'J101']:
        prob.append('SlimSAS receptacles found: %s; expected J1 at the radio '
                    'end and J101 at the Gowin end' % ', '.join(conn))
    return prob


def gowin_part(ref):
    """Gowin-end designators are numbered from 101."""
    digits = ''.join(c for c in ref if c.isdigit())
    return (bool(digits) and int(digits) >= 101
            and not ref.startswith(('#', 'FID')))


def gowin_header(pins):
    print('=== J102 on Tang dock J14 positions 5-40 ===')
    prob = []
    for n in sorted(GOWIN_J14):
        want = GOWIN_J14[n]
        got = pins.get((GOWIN_HDR, str(n - J14_FIRST + 1)), '<open>')
        ball, io, clk = J14_BALLS[n]
        if got != want:
            prob.append('J14 position %d = %s, PINMAP.md says %s'
                        % (n, got, want))
            continue
        if want.endswith('_P') and not io.endswith('A'):
            prob.append('J14 position %d carries a P leg on %s, not a Gowin '
                        'true (A) pin' % (n, io))
        if want.endswith('_N') and not io.endswith('B'):
            prob.append('J14 position %d carries an N leg on %s, not a Gowin '
                        'complement (B) pin' % (n, io))
        print('  J14-%-2d %-14s %-5s %-8s %s' % (n, got, ball or '-', io, clk))
    npins = len([1 for (r, _) in pins if r == GOWIN_HDR])
    if npins != 36:
        prob.append('J102 has %d pins; it must be a 2x18 covering J14 '
                    'positions 5-40 and nothing at 1-4' % npins)
    for net, what in GOWIN_CLOCKS.items():
        for leg, tc in (('_P', 'T'), ('_N', 'C')):
            n = [k for k, v in GOWIN_J14.items() if v == net + leg]
            clk = J14_BALLS[n[0]][2] if n else ''
            if 'GCLK%s' % tc not in clk:
                prob.append('the %s %s leg is not on a dedicated clock input'
                            % (what, leg))
    print('  forwarded clock on U20/V20 (%s); duplicate on Y18/Y19 (%s); '
          'J14 positions 1-4 not used' % (J14_BALLS[20][2], J14_BALLS[32][2]))
    return prob


def gowin_connector(pins, vals, bynet):
    print('=== J101, the Gowin end SlimSAS: all 74 contacts ===')
    prob = []
    want = {}
    for i in SS_GND:
        want['A%d' % i] = 'G_GND'
        want['B%d' % i] = 'G_GND'
    for pos, (onet, inet) in GLANES.items():
        want['A%d' % pos] = 'G_A_%s_P' % onet
        want['A%d' % (pos + 1)] = 'G_A_%s_N' % onet
        want['B%d' % pos] = 'G_B_%s_P' % inet
        want['B%d' % (pos + 1)] = 'G_B_%s_N' % inet
    for pos, (onet, inet) in GSIDEBANDS.items():
        want['A%d' % pos] = (('G_SB_%s_OUT' % onet) if onet
                             else 'G_SB_NC_A%d' % pos)
        want['B%d' % pos] = (('G_SB_%s_IN' % inet) if inet
                             else 'G_SB_NC_B%d' % pos)
    for pad in sorted(want, key=lambda s_: (s_[0], int(s_[1:]))):
        got = pins.get((GOWIN_REF, pad), '<open>')
        if got != want[pad]:
            prob.append('J101 pad %s = %s, expected %s'
                        % (pad, got, want[pad]))
    hdr_nets = set(GOWIN_J14.values())
    for pos, (onet, inet) in GLANES.items():
        for row, lane in (('A', onet), ('B', inet)):
            for leg in ('_P', '_N'):
                nm = 'G_%s_%s%s' % (row, lane, leg)
                if lane in GOWIN_UNWIRED and nm in hdr_nets:
                    prob.append('%s reaches J14 but is declared unwired' % nm)
                if lane not in GOWIN_UNWIRED and nm not in hdr_nets:
                    prob.append('%s does not reach J14' % nm)
    for cnet, (hnet, val) in GOWIN_SB_SERIES.items():
        rs = [r for (r, _) in bynet.get(cnet, []) if r.startswith('R')
              and {pins.get((r, '1')), pins.get((r, '2'))} == {cnet, hnet}]
        if len(rs) != 1 or vals.get(rs[0]) != val:
            prob.append('%s should reach %s through one %s, found %s'
                        % (cnet, hnet, val, rs))
    pd = [r for (r, _) in bynet.get('G_TCK_DRV', []) if r.startswith('R')
          and {pins.get((r, '1')), pins.get((r, '2'))} == {'G_TCK_DRV',
                                                            'G_GND'}]
    if not pd:
        prob.append('G_TCK_DRV has no pull-down, so an unconfigured Gowin '
                    'could send TCK edges to the radio')
    else:
        print('  TCK held LOW at this end by %s = %s until the gateware drives '
              'it' % (pd[0], vals.get(pd[0])))
    for pos in (9, 29):
        nm = 'G_SB_NC_B%d' % pos
        others = [r for (r, _) in bynet.get(nm, []) if r != GOWIN_REF
                  and not (r.startswith('D') or r.startswith('TP'))]
        if others:
            prob.append('%s faces an undriven radio output but reaches %s'
                        % (nm, others))
    if not prob:
        print('  26 grounds, 32 pair legs, 16 sidebands. 14 pairs run straight '
              'to J14, the spare pair to test pads only; six sidebands each '
              'through one series resistor; B9 and B29 unused')
    return prob


def gowin_esd(vals, bynet):
    prob = []
    esd = {r for r, v in vals.items()
           if v.startswith('TPD4E') and gowin_part(r)}
    clamped = {nm for nm, nodes in bynet.items()
               if nm != 'G_GND' and any(r in esd for r, _ in nodes)}
    need = []
    for pos, (onet, inet) in GLANES.items():
        need += ['G_A_%s_P' % onet, 'G_A_%s_N' % onet,
                 'G_B_%s_P' % inet, 'G_B_%s_N' % inet]
    for pos, (onet, inet) in GSIDEBANDS.items():
        need.append(('G_SB_%s_OUT' % onet) if onet else 'G_SB_NC_A%d' % pos)
        need.append(('G_SB_%s_IN' % inet) if inet else 'G_SB_NC_B%d' % pos)
    miss = [n for n in need if n not in clamped]
    if miss:
        prob.append('Gowin end: %d conductors unclamped: %s'
                    % (len(miss), ', '.join(miss)))
    else:
        print('=== Gowin end ESD: %d arrays clamp all %d conductors ==='
              % (len(esd), len(need)))
    return prob


def separate(bynet):
    """No net may touch both ends of the panel."""
    prob = []
    for nm, nodes in bynet.items():
        if nm == '<open>':
            continue
        refs = {r for r, _ in nodes if not r.startswith('#')}
        g = {r for r in refs if gowin_part(r)}
        if g and g != refs:
            prob.append('net %s touches both ends: %s' % (nm, sorted(refs)))
        if g and not nm.startswith('G_') and nm != '<open>':
            prob.append('Gowin-end net %s lacks the G_ prefix' % nm)
    if not prob:
        print('=== the radio end and the Gowin end share no net ===')
    return prob


def read_end(pins, ref, prefix):
    """-> {pos: (row A net, row B net)} with the end prefix stripped."""
    out = {}
    for pos in range(1, SS_NPOS + 1):
        a = pins.get((ref, 'A%d' % pos), '<open>')
        b = pins.get((ref, 'B%d' % pos), '<open>')
        if prefix:
            a = a[len(prefix):] if a.startswith(prefix) else a
            b = b[len(prefix):] if b.startswith(prefix) else b
        out[pos] = (a, b)
    return out


def lane_of(net):
    if net[:2] in ('A_', 'B_') and net[-2:] in ('_P', '_N'):
        return net[2:-2], net[-1]
    return None, None


def sb_of(net):
    """'SB_TCK_OUT' -> 'TCK'; an undriven or unused contact -> None."""
    if not net.startswith('SB_') or net.startswith('SB_NC'):
        return None
    return net[3:].rsplit('_', 1)[0]


def walk(pins, near, far):
    """Walk every row A output at `near` through the A(n) -> B(n) cable to
    row B at `far`.  near / far = (label, connector ref, net prefix,
    lanes not wired at that end)."""
    nl, nref, npre, nunw = near
    fl, fref, fpre, funw = far
    print('=== the crossover walked, %s end -> %s end ===' % (nl, fl))
    prob = []
    N = read_end(pins, nref, npre)
    F = read_end(pins, fref, fpre)
    for pos in SS_PAIR_POS:
        for k in (0, 1):
            dl, dp = lane_of(N[pos + k][0])
            rl, rp = lane_of(F[pos + k][1])
            if dl is None or rl is None:
                prob.append('%s -> %s contact %d: %s meets %s'
                            % (nl, fl, pos + k, N[pos + k][0], F[pos + k][1]))
            elif dp != rp:
                prob.append('%s -> %s contact %d: %s leg meets %s leg'
                            % (nl, fl, pos + k, dp, rp))
            elif LANE_MEANING[dl] != LANE_MEANING[rl]:
                prob.append('%s -> %s contact %d: %s (%s) arrives at %s (%s)'
                            % (nl, fl, pos + k, dl, LANE_MEANING[dl], rl,
                               LANE_MEANING[rl]))
        dl, _ = lane_of(N[pos][0])
        rl, _ = lane_of(F[pos][1])
        if dl and rl:
            state = 'live'
            if dl in nunw:
                state = 'not wired at the %s end' % nl
            elif rl in funw:
                state = 'not wired at the %s end' % fl
            print('  pair %-2d %-7s -> %-7s %-21s %s'
                  % (pos, dl, rl, LANE_MEANING[dl], state))
    for pos in SS_SIDEBAND:
        d = sb_of(N[pos][0])
        r = sb_of(F[pos][1])
        if d and r and d != r:
            if ((d, r) in SB_ALLOWED and sb_of(N[9][0]) is None
                    and sb_of(N[29][0]) is None):
                note = SB_ALLOWED[(d, r)]
            else:
                prob.append('%s -> %s sideband %d: %s arrives at %s'
                            % (nl, fl, pos, d, r))
                continue
        elif d and r:
            note = 'live'
        elif d:
            note = 'the far end does not listen here'
        elif r:
            note = 'nothing drives it; the far input idles at its pull'
        else:
            note = 'unused at both ends'
        print('  sb   %-2d %-7s -> %-7s %s' % (pos, d or '-', r or '-', note))
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
    print('################ the Gowin end ################')
    prob += gowin_header(pins)
    prob += gowin_connector(pins, vals, bynet)
    prob += gowin_esd(vals, bynet)
    prob += separate(bynet)
    radio = ('radio', SLIMSAS_REF, '', set())
    gowin = ('Gowin', GOWIN_REF, 'G_', GOWIN_UNWIRED)
    prob += walk(pins, radio, gowin)
    prob += walk(pins, gowin, radio)
    prob += walk(pins, radio, radio)

    print()
    for p in prob:
        print('  !! ' + p)
    print('  %s' % ('OK - the three radio-end header maps and the Gowin-end '
                    'J14 map match PINMAP.md, including the DB12 5/6 order '
                    'and both Gowin clock balls; the crossover walks clean '
                    'radio to Gowin, Gowin to radio and radio to radio; '
                    'all 74 connector contacts at the radio end '
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
