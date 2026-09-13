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

12. AN ABSENT FAR END CANNOT KEY THE TRANSMITTER.  With the far end's
    connector pins treated as unconnected, every one of the four AUXIO lines
    - CW/PTT ring and tip (active LOW, keyed when low) and the I2C SCL/SDA
    bus to the radio's clock generator (idle HIGH) - is biased on the radio
    end itself to its safe HIGH level, can only pass that level through the
    drive buffer, and the drive buffer is tri-stated unless a powered far end
    asserts presence.  Walked for radio-to-Gowin, Gowin-to-radio and
    radio-to-radio.

13. EVERY TRANSLATOR AND BUFFER RUNS THE WAY PINMAP.md SAYS.  For every
    SN74AVC4T245 (and any SN74AVC8T245) the direction and enable of each port
    are DERIVED from its DIR and OE* nets and TI's truth table, and every
    channel's input and output net is compared with PINMAP.md section 12; the
    DS90LV047A and DS90LV048A enables likewise.  rev D as first built had U8
    and U10 port 1 wired backwards and nothing noticed.

14. THE SAFE STATE.  The board's logic is evaluated for all sixteen
    combinations of forward clock on/off, far end present/absent and FPGA
    pins 72 and 80 HIGH/LOW.  Whenever the clock is off (stock gateware, no
    gateware) or no far end is present (far end absent, cable unplugged),
    nothing on the board may drive a radio FPGA pin, the JTAG buffers and the
    AUXIO drive must be off, and with no far end every cable-facing buffer
    and both LVDS drivers must be off.  With the clock on, a far end present
    and the enables asserted, all of it must come on.

15. THE PRESENCE GATING in all three pairings: the radio end's drivers
    follow B8; a radio far end asserts A8 only while powered, a Gowin far end
    only while its gateware drives it; the Gowin end reads presence through
    10 k.

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
    'AUXIO_OE_N': '+3V3',
    'RX_EN_N': '+3V3',
    'PRSNT_OE_N': '+3V3',
}

# The four AUXIO lines, retyped from the HL2 schematic (hardware/hl,
# InputOutput sheet and hermeslite.net) and the HL2 gateware.
#   sideband position -> (HL2 net at DB1, DB1 pin, FPGA pin, function,
#                         what is ACTIVE, the SAFE level)
# CW/PTT: R75/R76 2.2 k to +3V3, R77/R78 100 R to KEY jack CN4, C71/C72 1 uF,
# D8 SM05; sheet note "Ground to key"; gateware debounces ~io_phone_tip and
# ~io_phone_ring.  I2C1: R43/R44 4.7 k to +3V3, U6 = 5P49V5923 at 0x6A.
AUXIO_LINES = {
    11: ('HL2_CWR', 10, 90, 'CW/PTT ring (PTT or dash)', 'LOW = keyed',
         'HIGH'),
    12: ('HL2_CWT', 12, 91, 'CW/PTT tip (CW key or dot)', 'LOW = keyed',
         'HIGH'),
    26: ('HL2_SCL1', 16, 103, 'I2C1 SCL to U6, the master clock generator',
         'idle HIGH, clocks LOW', 'HIGH'),
    27: ('HL2_SDA1', 18, 104, 'I2C1 SDA to U6, the master clock generator',
         'idle HIGH, START = falls while SCL HIGH', 'HIGH'),
}
AUXIO_DRIVE_BUF = 'U9'
# SN74AVC4T245 A-side pin -> B-side pin, retyped from TI SCES576.
X4_A_TO_B = {'4': '13', '5': '12', '6': '11', '7': '10'}
X4_OE = ('14', '15')
X4_DIR = ('2', '3')

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
    'G_SB_PRSNT_IN': ('G_PRSNT_RD', '10k'),
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


DNP = set()


def load(path):
    """-> (pin map, value map, net map, part-pin map); DNP is filled in."""
    root = K.parse(open(path, encoding='utf-8').read())[0]
    pins, vals, bynet, byref = {}, {}, {}, {}
    DNP.clear()
    for comps in K.kids(root, 'components'):
        for comp in K.kids(comps, 'comp'):
            r = K.atoms(K.kid(comp, 'ref'))[0]
            v = K.kid(comp, 'value')
            vals[r] = K.atoms(v)[0] if v is not None else ''
            for pr in K.kids(comp, 'property'):
                nm = K.kid(pr, 'name')
                if nm is not None and K.atoms(nm) and K.atoms(nm)[0] == 'dnp':
                    DNP.add(r)
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
            # link, a 1k on JTAG_EN_N (behind the link-alive gate, because a
            # radio with no link gateware makes no forward clock).
            ok = (net == 'JTAG_EN_N'
                  and all(d.endswith('=1k') and d.split('=')[0] in DNP
                          for d in downs))
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


def passive(ref):
    return ref.startswith(('D', 'TP', '#'))


def pulls(net, pins, vals, bynet, byref):
    """-> (pull-up refs to +3V3, pull-down refs to GND) on a net."""
    ups, downs = [], []
    for (r, pad) in bynet.get(net, []):
        if not r.startswith('R'):
            continue
        for p_ in byref.get(r, []):
            if p_ == pad:
                continue
            dest = pins.get((r, p_))
            if dest == '+3V3':
                ups.append('%s=%s' % (r, vals.get(r, '')))
            elif dest == 'GND':
                downs.append('%s=%s' % (r, vals.get(r, '')))
    return ups, downs


def auxio_failsafe(pins, vals, bynet, byref, near, far):
    """With the far end's connector pins UNCONNECTED - cable unplugged, far
    end unpowered, unwired or tri-stated - every AUXIO line at `near` must sit
    at its safe level, decided on `near` alone.  near / far = (label,
    connector ref, net prefix)."""
    nl, nref, npre = near
    fl, fref, fpre = far
    print('=== AUXIO fail-safe, %s end with the %s end absent or undriven ==='
          % (nl, fl))
    prob = []
    for pos in sorted(AUXIO_LINES):
        hnet, db1, fpga, what, active, safe = AUXIO_LINES[pos]
        n_in = pins.get((nref, 'B%d' % pos), '<open>')
        f_out = pins.get((fref, 'A%d' % pos), '<open>')
        f_drv = sorted({r for (r, _) in bynet.get(f_out, [])
                        if r != fref and not passive(r)
                        and not r.startswith('R')})
        far_state = ('driven by %s' % ', '.join(f_drv) if f_drv
                     else 'not driven at all')
        others = sorted({r for (r, _) in bynet.get(n_in, [])
                         if r != nref and not passive(r)})
        if npre:                       # the Gowin end has no AUXIO path
            if others:
                prob.append('%s end: AUXIO contact B%d reaches %s; the Gowin '
                            'end implements no AUXIO input'
                            % (nl, pos, ', '.join(others)))
            else:
                print('  B%-2d %-8s reaches nothing at this end: no key or bus '
                      'input to disturb (far end %s)' % (pos, hnet[4:], far_state))
            continue
        ups, downs = pulls(n_in, pins, vals, bynet, byref)
        if downs or not ups:
            prob.append('%s -> %s: %s (%s, FPGA %d, %s) is not biased to its '
                        'safe %s level on the radio end: pull-ups %s, '
                        'pull-downs %s. A far end that is %s would leave it '
                        '%s' % (fl, nl, n_in, what, fpga, active, safe, ups
                                or 'none', downs or 'none', far_state,
                                'LOW = KEYED' if downs else 'FLOATING'))
            continue
        level = 'HIGH'
        # through the drive buffer: the only active part on the net
        bufpins = [pd for (r, pd) in bynet.get(n_in, [])
                   if r == AUXIO_DRIVE_BUF]
        stray = [r for r in others if r not in (AUXIO_DRIVE_BUF,)
                 and not r.startswith('R')]
        if stray or len(bufpins) != 1 or bufpins[0] not in X4_A_TO_B:
            prob.append('%s must reach only the A side of %s, found %s / %s'
                        % (n_in, AUXIO_DRIVE_BUF, others, bufpins))
            continue
        tnet = pins.get((AUXIO_DRIVE_BUF, X4_A_TO_B[bufpins[0]]))
        hl2 = [pins.get((r, '2' if pd == '1' else '1'))
               for (r, pd) in bynet.get(tnet, []) if r.startswith('R')
               and vals.get(r) == '330R']
        if hl2 != [hnet]:
            prob.append('%s drive output %s does not reach %s through one '
                        '330 R (found %s)' % (n_in, tnet, hnet, hl2))
            continue
        if level != safe:
            prob.append('%s would pass %s to %s, whose safe level is %s'
                        % (n_in, level, hnet, safe))
            continue
        print('  B%-2d %-16s 10 k UP (%s) -> %s -> 330 R -> %-8s FPGA %-3d '
              '%s: %s passed = %s. Far end %s'
              % (pos, n_in, ', '.join(ups), AUXIO_DRIVE_BUF, hnet, fpga,
                 active, level, 'NOT KEYED' if pos in (11, 12) else 'bus idle',
                 far_state))
    if npre:
        return prob
    # The drive buffer's enable, with the far end absent.
    for pd in X4_DIR:
        if pins.get((AUXIO_DRIVE_BUF, pd)) != '+3V3':
            prob.append('%s DIR pin %s is not +3V3, so the drive path does '
                        'not run cable -> radio' % (AUXIO_DRIVE_BUF, pd))
    oe = {pins.get((AUXIO_DRIVE_BUF, pd)) for pd in X4_OE}
    if oe != {'AUXIO_OE_N'}:
        prob.append('%s OE* is %s, not the presence-interlocked AUXIO_OE_N'
                    % (AUXIO_DRIVE_BUF, sorted(oe)))
        return prob
    ups, downs = pulls('AUXIO_OE_N', pins, vals, bynet, byref)
    q = [r for (r, pd) in bynet.get('AUXIO_OE_N', [])
         if r.startswith('Q') and pd == '3']
    other = [r for (r, _) in bynet.get('AUXIO_OE_N', [])
             if r not in q and r != AUXIO_DRIVE_BUF and not passive(r)
             and not r.startswith('R')]
    if downs or not ups or len(q) != 1 or other:
        prob.append('AUXIO_OE_N must be pulled up and pulled down ONLY through '
                    'one MOSFET drain: pull-ups %s, pull-downs %s, drains %s, '
                    'other %s' % (ups, downs, q, other))
        return prob
    gate = pins.get((q[0], '1'))
    src = pins.get((q[0], '2'))
    gu, gd = pulls(gate, pins, vals, bynet, byref)
    # the source reaches the gateware enable AUXIO_EN_N through the
    # link-alive gate (a second MOSFET whose gate is LINK_ALIVE)
    q2 = [r for (r, pd) in bynet.get(src, []) if r.startswith('Q')
          and pd == '3']
    via_la = (len(q2) == 1 and pins.get((q2[0], '1')) == 'LINK_ALIVE'
              and pins.get((q2[0], '2')) == 'AUXIO_EN_N')
    if gate != 'SB_PRSNT_IN' or not via_la or gu or not gd:
        prob.append('the interlock %s must have gate SB_PRSNT_IN (pulled '
                    'DOWN, so LOW with the far end absent) and its source must '
                    'reach AUXIO_EN_N only through a MOSFET gated by '
                    'LINK_ALIVE: gate %s (up %s, down %s), source %s via %s'
                    % (q[0], gate, gu, gd, src, q2))
        return prob
    f_prs = pins.get((fref, 'A8'), '<open>')
    print('  drive enable: %s OE* = AUXIO_OE_N, pulled UP by %s; pulled low '
          'only through %s (gate %s, held LOW by %s with the %s end '
          'absent) in series with %s (gate LINK_ALIVE), so the drive path is '
          'TRI-STATED whatever the gateware does'
          % (AUXIO_DRIVE_BUF, ', '.join(ups), q[0], gate, ', '.join(gd), fl,
             q2[0]))
    if f_prs == '<open>':
        prob.append('the %s end has nothing on A8, so it can never assert '
                    'presence' % fl)
    return prob



# ==========================================================================
#  13 SEP 2026: EVERY BUFFER'S DIRECTION AND ENABLE, FROM THE TRUTH TABLE,
#  THE SAFE STATE, AND THE PRESENCE GATING
# ==========================================================================
#
# rev D as first built had two SN74AVC4T245s wired backwards (U8, and U10
# port 1): DIR LOW is B data to A bus, so both drove radio pins from the
# cable.  The old check looked only at U9's DIR pins.  This one derives every
# channel of every translator and LVDS part from its DIR and enable nets and
# the datasheet truth tables, and compares it with the table in PINMAP.md
# section 12, retyped here.
#
# SN74AVC4T245, TI SCES576I Table 7-1 (each 2-bit section):
#   OE* L, DIR L -> A port outputs enabled, B hi-Z: B data to A bus
#   OE* L, DIR H -> A hi-Z, B outputs enabled: A data to B bus
#   OE* H        -> both hi-Z (isolation)
# PW pinout (SCES576I, Pin Functions): 1 VCCA, 2 1DIR, 3 2DIR, 4 1A1, 5 1A2,
# 6 2A1, 7 2A2, 8/9 GND, 10 2B2, 11 2B1, 12 1B2, 13 1B1, 14 2OE*, 15 1OE*,
# 16 VCCB.  DIR and OE* are referenced to VCCA.
X4_PORT = {1: dict(dir='2', oe='15', ch=(('4', '13'), ('5', '12'))),
           2: dict(dir='3', oe='14', ch=(('6', '11'), ('7', '10')))}
# DS90LV048A, TI SNLS045C Table 1: outputs enabled only for EN (16) HIGH and
# EN* (9) LOW or open; every other combination TRI-STATE.  ROUT 15/14/11/10.
# DS90LV047A, TI SNLS044D: EN (1) HIGH and EN* (8) LOW enables the drivers.
RAILS = {'+3V3': 1, '+2V5': 1, 'GND': 0}

# PINMAP.md section 12, retyped.  ref -> port -> (intended direction,
# intended enable, [(input net, output net) per channel]).  Direction 'A>B'
# means the A side is the input.  Enable 'always' = OE* tied LOW; otherwise
# the active-LOW enable net.  An output of None is a spare left unconnected.
XLAT = {
    'U1': {1: ('A>B', 'always', [('HL2_FWD_CLK', 'DI_FWDCLK'),
                                 ('HL2_ADC_D0', 'DI_ADCD0')]),
           2: ('A>B', 'always', [('HL2_ADC_D1', 'DI_ADCD1'),
                                 ('HL2_ADC_D2', 'DI_ADCD2')])},
    'U2': {1: ('A>B', 'always', [('HL2_AUX_CLK_OUT', 'DI_AUXCLK'),
                                 ('HL2_AUX_DAT_OUT', 'DI_AUXDAT')]),
           2: ('A>B', 'always', [('HL2_JTAG_EN', 'JTAG_EN_RAW_N'),
                                 ('HL2_AUXIO_EN', 'AUXIO_EN_N')])},
    'U3': {1: ('A>B', 'RX_EN_N', [('RX_REVCLK', 'X_REVCLK25'),
                                  ('RX_DUPCLK', 'X_DUPCLK25')]),
           2: ('A>B', 'RX_EN_N', [('RX_AUXCLK', 'X_AUXCLK25'),
                                  ('RX_AUXDAT', 'X_AUXDAT25')])},
    'U8': {1: ('A>B', 'PRSNT_OE_N', [('AUXIO0_T', 'SB_AUXIO0_OUT'),
                                     ('AUXIO1_T', 'SB_AUXIO1_OUT')]),
           2: ('A>B', 'PRSNT_OE_N', [('AUXIO2_T', 'SB_AUXIO2_OUT'),
                                     ('AUXIO3_T', 'SB_AUXIO3_OUT')])},
    'U9': {1: ('A>B', 'AUXIO_OE_N', [('SB_AUXIO0_IN', 'AUXIO0_T'),
                                     ('SB_AUXIO1_IN', 'AUXIO1_T')]),
           2: ('A>B', 'AUXIO_OE_N', [('SB_AUXIO2_IN', 'AUXIO2_T'),
                                     ('SB_AUXIO3_IN', 'AUXIO3_T')])},
    'U10': {1: ('A>B', 'PRSNT_OE_N', [('J_TDO_T', 'SB_TDO_OUT'),
                                      ('GND', None)]),
            2: ('A>B', 'JTAG_EN_N', [('SB_TCK_IN', 'SB_TCK_IN_B'),
                                     ('SB_TMS_IN', 'SB_TMS_IN_B')])},
    'U11': {1: ('A>B', 'JTAG_EN_N', [('SB_TDI_IN', 'SB_TDI_IN_B'),
                                     ('GND', None)]),
            2: ('A>B', 'always', [('DI_FWDCLK', 'LA_CLK'), ('GND', None)])},
}
# What each translator is FOR, in words, and which side faces what.
XLAT_WHY = {
    'U1': 'forward group, radio pins 98/76/77/83 -> LVDS drivers',
    'U2': 'aux out and the two gateware enables, radio -> board',
    'U3': 'reverse/aux clocks and aux data, receivers -> radio pins 88/89/87',
    'U8': 'AUXIO READ, radio pins 90/91/103/104 -> cable',
    'U9': 'AUXIO DRIVE, cable -> radio pins 90/91/103/104',
    'U10': 'port 1 TDO radio -> cable; port 2 TCK/TMS cable -> radio',
    'U11': 'port 1 TDI cable -> radio; port 2 forward-clock copy -> detector',
}
# LVDS parts: ref -> (kind, EN pin, EN* pin, intended enable net after 0 R
# links, outputs).
LVDS = {
    'U4': ('driver', '1', '8', 'SB_PRSNT_IN', 'cable pairs'),
    'U5': ('driver', '1', '8', 'SB_PRSNT_IN', 'cable pairs'),
    'U6': ('receiver', '16', '9', 'RX_EN_N', ('15', '14', '11', '10')),
    'U7': ('receiver', '16', '9', 'RX_EN_N', ('15', '14', '11', '10')),
}
# The scenario model's inputs: what the radio FPGA can do to the enables and
# the forward clock, and what the far end does to presence.
RADIO_CLOCK_NET = 'HL2_FWD_CLK'          # after the pin 98 divider
GATEWARE_ENABLE_NETS = {'HL2_JTAG_EN': 'pin80', 'HL2_AUXIO_EN': 'pin72'}
PRESENCE_NET = 'SB_PRSNT_IN'             # J1 contact B8
DETECTOR_OUT = 'LINK_ALIVE'
HL2_HEADERS = ('J2', 'J3', 'J4')
POWER_NETS = ('GND', '+3V3', '+2V5', 'DB1_3V3', 'P3V3_FB', 'VLVDS', 'VLVDS_F',
              'CN1_VTREF')


class Net:
    """The netlist as the logic engine sees it: fitted parts only."""

    def __init__(self, pins, vals, bynet, byref, dnp):
        self.pins, self.vals, self.bynet, self.byref = pins, vals, bynet, byref
        self.dnp = dnp

    def fitted(self, r):
        return r not in self.dnp

    def on(self, net, prefix=None):
        return [(r, p) for (r, p) in self.bynet.get(net, [])
                if self.fitted(r) and (prefix is None or r.startswith(prefix))]

    def other(self, r, p):
        return self.pins.get((r, '2' if p == '1' else '1'))


def rail_level(n, net, vcca):
    """A static control net -> 'H', 'L' or None (not static)."""
    if net == 'GND':
        return 'L'
    if net == vcca:
        return 'H'
    if net in ('+3V3', '+2V5'):
        return 'OVER' if (net == '+3V3' and vcca == '+2V5') else 'H'
    return None


def derive_x4(n, ref):
    """-> {port: (direction 'A>B'/'B>A', enable 'always'/'off'/net,
    [(input net, output net)], vcca)} from the truth table."""
    vcca = n.pins.get((ref, '1'))
    out = {}
    for port, d in X4_PORT.items():
        dnet = n.pins.get((ref, d['dir']))
        onet = n.pins.get((ref, d['oe']))
        dl = rail_level(n, dnet, vcca)
        ol = rail_level(n, onet, vcca)
        direction = {'H': 'A>B', 'L': 'B>A'}.get(dl, 'DIR=%s' % dnet)
        enable = {'L': 'always', 'H': 'off'}.get(ol, onet)
        chans = []
        for a, b_ in d['ch']:
            na, nb = n.pins.get((ref, a)), n.pins.get((ref, b_))
            na = None if na == '<open>' else na
            nb = None if nb == '<open>' else nb
            chans.append((na, nb) if direction == 'A>B' else (nb, na))
        out[port] = (direction, enable, chans, dnet, onet)
    return out


def resolve_links(n, net):
    """Follow fitted 0 R links: -> the set of nets joined to `net`."""
    seen, todo = {net}, [net]
    while todo:
        cur = todo.pop()
        for (r, p) in n.on(cur, 'R'):
            if n.vals.get(r) in ('0R', '0') and n.other(r, p) not in RAILS:
                o = n.other(r, p)
                if o and o not in seen:
                    seen.add(o)
                    todo.append(o)
            elif n.vals.get(r) in ('0R', '0') and n.other(r, p) in RAILS:
                seen.add(n.other(r, p))
    return seen


def check_buffers(n):
    print('=== every translator and buffer: direction and enable derived from '
          'its DIR/OE nets and the truth table ===')
    prob = []
    x4s = sorted((r for r, v in n.vals.items() if v.startswith('SN74AVC4T245')),
                 key=lambda s: int(s[1:]))
    if sorted(x4s) != sorted(XLAT):
        prob.append('SN74AVC4T245 instances %s do not match the PINMAP.md '
                    'table %s' % (x4s, sorted(XLAT)))
    x8 = sorted(r for r, v in n.vals.items() if v.startswith('SN74AVC8T245'))
    print('  SN74AVC8T245 instances: %s' % (', '.join(x8) or 'none'))
    if x8:
        prob.append('SN74AVC8T245 instances %s are not in the PINMAP.md table'
                    % x8)
    for ref in x4s:
        if ref not in XLAT:
            continue
        got = derive_x4(n, ref)
        print('  %s  (%s)' % (ref, XLAT_WHY[ref]))
        for port in (1, 2):
            direction, enable, chans, dnet, onet = got[port]
            wdir, wen, wch = XLAT[ref][port]
            print('     port %d: DIR = %-6s -> %s;  OE* = %-10s -> %s'
                  % (port, dnet, direction, onet,
                     'always enabled' if enable == 'always' else
                     'always off' if enable == 'off' else
                     'enabled only while %s is LOW' % enable))
            if direction != wdir:
                prob.append('%s port %d runs %s (DIR = %s), PINMAP.md says %s'
                            % (ref, port, direction, dnet, wdir))
            if enable != wen:
                prob.append('%s port %d enable is %s (OE* = %s), PINMAP.md '
                            'says %s' % (ref, port, enable, onet, wen))
            for k, ((gi, go), (wi, wo)) in enumerate(zip(chans, wch), 1):
                ok = gi == wi and (go == wo or (wo is None and go is None))
                print('        ch %d: %-14s -> %-14s %s'
                      % (k, gi, go or '(unconnected)',
                         'OK' if ok else '!! intended %s -> %s' % (wi, wo)))
                if not ok:
                    prob.append('%s port %d channel %d carries %s -> %s, '
                                'PINMAP.md says %s -> %s'
                                % (ref, port, k, gi, go, wi, wo))
    for ref, (kind, en, enb, want, outs) in sorted(LVDS.items()):
        enn, enbn = n.pins.get((ref, en)), n.pins.get((ref, enb))
        en_nets = resolve_links(n, enn)
        if kind == 'driver':
            ok_b = enbn == 'GND'
            ctrl = want if want in en_nets and '+3V3' not in en_nets else None
            state = ('always on' if '+3V3' in en_nets else
                     'enabled only while %s is HIGH' % ctrl if ctrl else
                     'EN = %s' % enn)
        else:
            ok_b = enn == '+3V3'
            ctrl = want if enbn == want else None
            state = ('always on' if enbn == 'GND' else
                     'enabled only while %s is LOW' % ctrl if ctrl else
                     'EN* = %s' % enbn)
        print('  %s  %s, EN = %s (via fitted links: %s), EN* = %s -> %s'
              % (ref, n.vals.get(ref), enn, ', '.join(sorted(en_nets)), enbn,
                 state))
        if not ok_b or not ctrl:
            prob.append('%s enable is "%s"; PINMAP.md says it is gated by %s'
                        % (ref, state, want))
    return prob


class Scenario:
    """Evaluate the board's logic for one assignment of the outside world:
    clock = the forward clock runs on pin 98; far = a powered far end drives
    presence; pin72 / pin80 = the level the radio FPGA puts on its enable
    pins (0 = asking for the feature, which is what stock gateware does)."""

    def __init__(self, n, clock, far, pin72, pin80):
        self.n, self.clock, self.far = n, clock, far
        self.gw = {'pin72': pin72, 'pin80': pin80}
        self.x4 = {r: derive_x4(n, r) for r, v in n.vals.items()
                   if v.startswith('SN74AVC4T245')}
        self.memo = {}

    def port_enabled(self, ref, port):
        _d, enable, _c, _dn, _on = self.x4[ref][port]
        if enable == 'always':
            return True
        if enable == 'off':
            return False
        return self.val(enable) == 0

    def lvds_enabled(self, ref):
        kind, en, enb, _w, _o = LVDS[ref]
        e = self.val(self.n.pins.get((ref, en)))
        eb = self.val(self.n.pins.get((ref, enb)))
        return e == 1 and eb == 0

    def val(self, net):
        """-> 1, 0, 'CLK' (a running clock), 'DATA' or 'Z'."""
        if net in RAILS:
            return RAILS[net]
        if net in self.memo:
            return self.memo[net]
        self.memo[net] = 'Z'                     # break loops
        v = self._val(net)
        self.memo[net] = v
        return v

    def _val(self, net):
        n = self.n
        if net == RADIO_CLOCK_NET:
            return 'CLK' if self.clock else 0
        if net in GATEWARE_ENABLE_NETS:
            return self.gw[GATEWARE_ENABLE_NETS[net]]
        # a MOSFET pulling it low wins
        for (r, p) in n.on(net, 'Q'):
            if p == '3':
                g = self.val(n.pins.get((r, '1')))
                s = self.val(n.pins.get((r, '2')))
                if g == 1 and s == 0:
                    return 0
        # a buffer output driving it
        for (r, p) in n.on(net, 'U'):
            if r in self.x4:
                for port, (d, _e, chans, _dn, _on) in self.x4[r].items():
                    for gi, go in chans:
                        if go == net and self.port_enabled(r, port):
                            return self.val(gi)
        # the link-alive detector: a diode cathode on this net, its anode on
        # a node that is a capacitor away from a running clock
        for (r, p) in n.on(net, 'D'):
            if n.vals.get(r, '').startswith('RB751') and p == '1':
                pump = n.pins.get((r, '2'))
                for (c, cp) in n.on(pump, 'C'):
                    src = n.other(c, cp)
                    if src and self.val(src) == 'CLK':
                        return 1
        # the presence contact
        if net == PRESENCE_NET:
            return 1 if self.far else 0
        # a fitted 0 R link to another signal net
        for (r, p) in n.on(net, 'R'):
            o = n.other(r, p)
            if n.vals.get(r) in ('0R', '0') and o and o not in RAILS:
                v = self.val(o)
                if v != 'Z':
                    return v
        ups = [r for (r, p) in n.on(net, 'R')
               if n.other(r, p) in ('+3V3', '+2V5')]
        downs = [r for (r, p) in n.on(net, 'R') if n.other(r, p) == 'GND']
        if ups and not downs:
            return 1
        if downs and not ups:
            return 0
        return 'DATA' if not (ups or downs) else 'Z'


def radio_facing_outputs(n):
    """Every buffer channel or receiver output that can drive a radio FPGA
    pin: its output net reaches a J2/J3/J4 pin directly or through fitted
    series resistors.  -> [(label, ref, port or None, output net, pin)]"""
    hdr = {}
    for ref in HL2_HEADERS:
        for (r, p), net in n.pins.items():
            if r == ref and net not in POWER_NETS and net != '<open>':
                hdr.setdefault(net, '%s-%s' % (ref, p))
    reach = dict(hdr)
    for net, pin in list(hdr.items()):
        for (r, p) in n.on(net, 'R'):
            o = n.other(r, p)
            if o and o not in RAILS and o not in POWER_NETS:
                reach.setdefault(o, pin + ' via ' + r)
    outs = []
    for ref, v in sorted(n.vals.items()):
        if not n.fitted(ref):
            continue
        if v.startswith('SN74AVC4T245'):
            for port, (d, _e, chans, _dn, _on) in derive_x4(n, ref).items():
                for gi, go in chans:
                    if go in reach:
                        outs.append(('%s port %d' % (ref, port), ref, port, go,
                                     reach[go]))
        elif ref in LVDS and LVDS[ref][0] == 'receiver':
            for pd in LVDS[ref][4]:
                go = n.pins.get((ref, pd))
                if go in reach:
                    outs.append(('%s ROUT' % ref, ref, None, go, reach[go]))
    return outs


def check_safe_state(n):
    """With stock gateware, no gateware, no far end or no cable, nothing on
    the board may drive a radio FPGA pin; the JTAG buffers and the AUXIO drive
    must be off; and every cable-facing driver must be off without a far
    end.  Checked by evaluating all sixteen combinations."""
    print('=== the safe state: stock gateware, no gateware, far end absent, '
          'cable unplugged ===')
    prob = []
    outs = radio_facing_outputs(n)
    seen = set()
    for label, ref, port, go, pin in outs:
        if (label, go) in seen:
            continue
        seen.add((label, go))
        print('  can drive the radio: %-12s -> %-14s -> %s' % (label, go, pin))
    jtag = [(r, p) for r, ports in XLAT.items() for p, (_d, e, _c) in
            ports.items() if e == 'JTAG_EN_N']
    auxio = [(r, p) for r, ports in XLAT.items() for p, (_d, e, _c) in
             ports.items() if e == 'AUXIO_OE_N']
    cable = [(r, p) for r, ports in XLAT.items() for p, (_d, e, _c) in
             ports.items() if e == 'PRSNT_OE_N']
    live = {}
    for clock in (False, True):
        for far in (False, True):
            for p72 in (0, 1):
                for p80 in (0, 1):
                    s = Scenario(n, clock, far, p72, p80)
                    tag = ('clock %-3s far end %-7s pin72 %d pin80 %d'
                           % ('on' if clock else 'off',
                              'present' if far else 'absent', p72, p80))
                    en_out = sorted({label for label, ref, port, go, pin
                                     in outs if (s.port_enabled(ref, port)
                                                 if port else
                                                 s.lvds_enabled(ref))})
                    en_jtag = sorted({r for r, p in jtag
                                      if s.port_enabled(r, p)})
                    en_aux = sorted({r for r, p in auxio
                                     if s.port_enabled(r, p)})
                    en_cab = sorted({r for r, p in cable
                                     if s.port_enabled(r, p)})
                    en_drv = [r for r in ('U4', 'U5') if s.lvds_enabled(r)]
                    live[(clock, far, p72, p80)] = (en_out, en_jtag, en_aux,
                                                    en_cab, en_drv)
                    if not (clock and far):
                        if en_out or en_jtag or en_aux:
                            prob.append('%s: still enabled toward the radio: '
                                        '%s' % (tag, sorted(set(
                                            en_out + en_jtag + en_aux))))
                    if not far and (en_cab or en_drv):
                        prob.append('%s: cable-facing drivers enabled with no '
                                    'far end: %s' % (tag, en_cab + en_drv))
    # the value the detector and the enables take in each named case
    cases = (('stock gateware (clock off, pins 72/80 LOW), far end present',
              (False, True, 0, 0)),
             ('no gateware (clock off, pins pulled HIGH), far end present',
              (False, True, 1, 1)),
             ('link gateware running, far end absent or cable unplugged',
              (True, False, 0, 0)),
             ('link gateware running, far end present, both enables LOW',
              (True, True, 0, 0)))
    for label, key in cases:
        s = Scenario(n, *key)
        en_out, en_jtag, en_aux, en_cab, en_drv = live[key]
        print('  %s:' % label)
        print('     LINK_ALIVE %s, RX_EN_N %s, JTAG_EN_N %s, AUXIO_OE_N %s, '
              'PRSNT_OE_N %s' % (s.val(DETECTOR_OUT), s.val('RX_EN_N'),
                                 s.val('JTAG_EN_N'), s.val('AUXIO_OE_N'),
                                 s.val('PRSNT_OE_N')))
        print('     driving the radio: %s; JTAG buffers %s; AUXIO drive %s; '
              'cable buffers %s; LVDS drivers %s'
              % (', '.join(sorted(set(en_out))) or 'NOTHING (all hi-Z)',
                 'ON' if en_jtag else 'off', 'ON' if en_aux else 'off',
                 'ON' if en_cab else 'off', 'ON' if en_drv else 'off'))
    # and the link must still work when it should
    en_out, en_jtag, en_aux, en_cab, en_drv = live[(True, True, 0, 0)]
    if not (en_out and en_jtag and en_aux and en_cab and en_drv):
        prob.append('with the clock running, a far end present and both '
                    'enables asserted, something needed stays off: outputs %s, '
                    'JTAG %s, AUXIO %s, cable %s, drivers %s'
                    % (en_out, en_jtag, en_aux, en_cab, en_drv))
    en_out, en_jtag, en_aux, en_cab, en_drv = live[(True, True, 1, 1)]
    if en_jtag or en_aux:
        prob.append('with both enables HIGH the JTAG or AUXIO path is on')
    # LINK_ALIVE must have no DC source: only the detector diode and pulls to
    # ground; RX_EN_N, PRSNT_OE_N pulled up and pulled low only by MOSFETs
    la = n.on(DETECTOR_OUT)
    bad = [(r, p) for (r, p) in la if not (
        r.startswith('TP') or (r.startswith('R') and n.other(r, p) == 'GND')
        or (r.startswith('C') and n.other(r, p) == 'GND')
        or (r.startswith('D') and p == '1')
        or (r.startswith('Q') and p in ('1', '3')))]
    if bad:
        prob.append('LINK_ALIVE has a DC path other than the detector: %s'
                    % bad)
    if not prob:
        print('  OK: in all 12 combinations where the forward clock is off or '
              'no far end is present, nothing drives a radio pin, the JTAG '
              'buffers and the AUXIO drive are off; with no far end every '
              'cable-facing buffer and both LVDS drivers are off')
    return prob


def check_presence_pairings(n):
    """The presence gating, for radio to Gowin, Gowin to radio and radio to
    radio.  A near end's cable drivers may run only while its B8 input reads
    HIGH, and that input may be HIGH only while the far end is powered (radio)
    or its gateware drives HIGH (Gowin)."""
    print('=== presence gating in all three pairings ===')
    prob = []
    # the radio end as the near end: its gated parts
    gated = []
    for r in ('U4', 'U5'):
        if 'SB_PRSNT_IN' in resolve_links(n, n.pins.get((r, '1'))):
            gated.append(r)
    if any(n.fitted(r) and n.vals.get(r) == '0R' and {
            n.pins.get((r, '1')), n.pins.get((r, '2'))} == {'DRV_EN', '+3V3'}
            for r in n.byref):
        prob.append('a FITTED 0 R ties DRV_EN to +3V3: the LVDS drivers run '
                    'with no far end')
    b8 = n.pins.get(('J1', 'B8'))
    downs = [r for (r, p) in n.on(b8, 'R') if n.other(r, p) == 'GND']
    ups = [r for (r, p) in n.on(b8, 'R') if n.other(r, p) in ('+3V3', '+2V5')]
    if b8 != 'SB_PRSNT_IN' or not downs or ups:
        prob.append('radio end B8 must be SB_PRSNT_IN, pulled down only')
    for far_label, far_ref, a8_ok in (
            ('radio', 'J1', lambda a8: any(
                n.other(r, p) == '+3V3' for (r, p) in n.on(a8, 'R'))),
            ('Gowin', 'J101', lambda a8: any(
                n.other(r, p) == 'G_PRSNT_DRV' for (r, p) in n.on(a8, 'R'))
                and not any(n.other(r, p) in ('+3V3', '+2V5', 'G_5V')
                            for (r, p) in n.on(a8, 'R')))):
        a8 = n.pins.get((far_ref, 'A8'))
        if not a8_ok(a8):
            prob.append('%s far end: A8 (%s) does not assert presence only '
                        'when powered/configured' % (far_label, a8))
            continue
        how = ('1 k to its own +3V3: HIGH only while that radio is powered'
               if far_label == 'radio' else
               '1 k from gateware ball AB18 with no pull-up: HIGH only while '
               'the Gowin is powered AND configured')
        print('  radio end <- %s end: far A8 = %s, %s. Radio end drivers U4, U5 '
              '(DRV_EN via R_DRVEN_PRSNT), U8 and U10 port 1 (PRSNT_OE_N) and '
              'LINK_ALIVE (clamped by PRSNT_OE_N) all follow it'
              % (far_label, a8, how))
    if sorted(gated) != ['U4', 'U5']:
        prob.append('LVDS drivers gated on presence: %s, expected U4 and U5'
                    % gated)
    # Gowin end as the near end: no on-board drivers; the FPGA is the driver.
    rd = [r for (r, p) in n.on('G_SB_PRSNT_IN', 'R')
          if n.other(r, p) == 'G_PRSNT_RD']
    if len(rd) != 1 or n.vals.get(rd[0]) != '10k':
        prob.append('Gowin end presence input must reach ball AA18 through '
                    'one 10 k (was 1 k): found %s'
                    % [(r, n.vals.get(r)) for r in rd])
    else:
        print('  Gowin end <- radio end: radio A8 = SB_PRSNT_OUT, 1 k to the '
              'radio +3V3; read on ball AA18 through %s = 10 k with R102 '
              '10 k to ground, so a powered radio injects about 0.25 mA into '
              'an unpowered Tang. The Gowin drives nothing on this board: its '
              'gateware must keep LVDS and JTAG outputs off until AA18 reads '
              'HIGH (PINMAP.md 11.4)' % rd[0])
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
    print('################ AUXIO fail-safe: no far end can key the radio '
          '################')
    r3 = ('radio', SLIMSAS_REF, '')
    g3 = ('Gowin', GOWIN_REF, 'G_')
    prob += auxio_failsafe(pins, vals, bynet, byref, r3, g3)   # radio-to-Gowin
    prob += auxio_failsafe(pins, vals, bynet, byref, g3, r3)   # Gowin-to-radio
    prob += auxio_failsafe(pins, vals, bynet, byref, r3, r3)   # radio-to-radio

    print()
    print('################ buffers, safe state and presence gating '
          '################')
    n = Net(pins, vals, bynet, byref, DNP)
    prob += check_buffers(n)
    prob += check_safe_state(n)
    prob += check_presence_pairings(n)

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
                    'pulled to their disabled state at both ends, no absent '
                    'or undriven far end can key CW/PTT or disturb the clock '
                    'chip bus in any of the three pairings, every '
                    'translator and LVDS part runs the direction and enable '
                    'PINMAP.md section 12 gives it, nothing drives a radio pin '
                    'and the JTAG and AUXIO paths are off unless the forward '
                    'clock runs and a far end is present, every cable-facing '
                    'driver is gated on presence in all three pairings, every '
                    'conductor leaving the board is clamped, and there is one '
                    'design'
                    if not prob else '%d PROBLEMS' % len(prob)))
    return 1 if prob else 0


if __name__ == '__main__':
    sys.exit(main())
