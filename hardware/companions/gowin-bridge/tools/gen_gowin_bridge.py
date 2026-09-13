#!/usr/bin/env python3
"""Generate the gowin-bridge KiCad project from one netlist description.

Run:   python tools/gen_gowin_bridge.py

Writes, next to this tools/ directory:
    ../bridge/{bridge.kicad_pro,.kicad_sch,.kicad_pcb}
    ../bridge/gowin-bridge.kicad_sym
    ../bridge/gowin-bridge.pretty/*.kicad_mod
    ../bridge/bridge-bom.csv

rev D: ONE DESIGN.  One board, one schematic, one PCB, one BOM.  Two copies of
that one design make a radio-to-radio link; one copy plus a Gowin-side board
makes a radio-to-FPGA link.  Nothing here is "board A" or "board B" - rev C's
two-design, three-cable, riser-and-panel scheme is in git history.

What the board is: a flat companion board that plugs onto the Hermes-Lite 2's
DB1 (2x10) and DB12 (2x3) headers and onto CN1 (the 2x5 USB-Blaster JTAG
header), and carries ONE SlimSAS SFF-8654 8i receptacle on its front edge.
A single 8i-to-8i cable carries 16 differential pairs plus 16 sideband
conductors.  Every data lane runs DDR at 153.6 MHz = 307.2 Mbit/s.

The cable is a FULL CROSSOVER: SFF-9402 Rev 1.1 implementation note 16 and its
Tables 6-2 / 6-3 map row A pin n at one end to row B pin n at the other, for
every one of the 37 positions per row, sidebands and two-wire management
included.  So this board drives row A and listens on row B, and the same
design at the far end drives its row A into this board's row B.  That is what
makes ONE design work at both ends.  PINMAP.md rev D section 1 has the table.

Symbol graphics and most footprint land patterns are lifted from the stock
KiCad libraries and re-emitted as a project-local library, so the project is
self-contained.  The SlimSAS 8X right-angle land pattern is not in the stock
libraries and is built here from SFF-8654 Rev 1.2 Figure A-1 and Table A-1;
every number is in SLIMSAS below with its source.

The netlist below is the single source of truth for the schematic, the PCB and
the BOM.  PINMAP.md must agree with it, and tools/check_netlist.py asserts it.
"""

import os
import sys
import csv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kisexp as K
from kisexp import W, q, fmt, uuid_for, effects

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

KICAD_SHARE_CANDIDATES = [
    os.environ.get('KICAD_SHARE', ''),
    r'C:/Users/franz/AppData/Local/Programs/KiCad/10.0/share/kicad',
    r'C:/Program Files/KiCad/10.0/share/kicad',
    r'C:/Program Files/KiCad/9.0/share/kicad',
    r'C:/Program Files/KiCad/8.0/share/kicad',
    '/usr/share/kicad',
]


def find_share():
    for c in KICAD_SHARE_CANDIDATES:
        if c and os.path.isdir(os.path.join(c, 'symbols')):
            return c
    raise SystemExit('Could not find a KiCad share directory; set KICAD_SHARE.')


SHARE = find_share()
SYMLIB = K.SymLib([os.path.join(SHARE, 'symbols')])
FPLIB = K.FpLib([os.path.join(SHARE, 'footprints')])

LOCAL_SYM = 'gowin-bridge'
LOCAL_FP = 'gowin-bridge'

REV = 'D'

# ==========================================================================
#  SlimSAS SFF-8654 8X land pattern - the one footprint not in the stock libs
# ==========================================================================
#
# Part: Amphenol ICC U10A474240T, LCSC C5432262.  SlimSAS SFF-8654 8i
# 74-position receptacle, RIGHT ANGLE, 0.60 mm pitch: 74 SMD signal contacts
# plus four through-hole shell tails (2.2 mm long, the reason this dash number
# was chosen over the 1.5 mm U10A474200T) and two through-hole locating pegs.
# 23.50 mm wide, 9.90 mm above the board, 15.80 mm deep including the latch
# shroud.  Mating force 55.5 N max, durability 250 mating cycles min, current
# rating 0.5 A per contact, differential impedance 85 ohm +/-10 (Amphenol U10
# series datasheet).
#
# WHERE THE NUMBERS COME FROM.  Amphenol publish no recommended land pattern
# for this part and their datasheet server refuses automated fetching, so the
# pattern below is built from the GOVERNING SPECIFICATION's own informative
# footprint: SFF-8654 Rev 1.2, Figure A-1 "8X RIGHT ANGLE RECEPTACLE CONNECTOR
# FOOTPRINT" and Table A-1 "8X RIGHT ANGLE RECEPTACLE FOOTPRINT DIMENSIONS".
# Every designator below is that table's own:
#
#   J01  locating hole (datum K & L) to footprint centreline   10.95 +/-0.025
#   J02  locating hole to row A centreline                      2.70  basic
#   J03  row A centreline to row B centreline                   2.35  basic
#   J04  locating hole (datum L) to outer pad centre            0.15  basic
#   J05  pad pitch                                              0.60  basic
#   J06  pad width                                              0.35 +/-0.03
#   J07  pad length                                             1.30 +/-0.03
#   J08  locating hole diameter                                 1.30 +/-0.05
#   J09  locating hole to first solder pin hole                 5.15  basic
#   J10  first solder pin hole to second solder pin hole        3.00  basic
#   J11  locating hole to solder pin holes                      0.68  basic
#   J12  solder pin hole diameter                               0.66 +/-0.05
#
# Cross-checked against Foxconn customer drawing 303-0000-3299 sheet 4/5, the
# "RECOMMEND PCB LAYOUT" view for the 38-position sibling of the same LDL
# family, which prints the identical construction with 0.675 in place of J11's
# 0.68, and confirms that the solder pin holes sit OUTSIDE the locating holes
# (its 12.45 overall = 2 x (5.55 + 0.675) for the 4X part) and on the OPPOSITE
# side of the locating-hole datum line from the contact pads.
#
# COORDINATE CONVENTION: the footprint origin sits on the LOCATING-HOLE DATUM
# LINE, on the connector's own centreline.  +x is INTO the board (the contact
# pads are at positive x); -x is toward the board edge (the four shell tails
# are at negative x); +/-y runs along the board edge.  The connector is
# therefore placed at (SLIMSAS_SETBACK, y_centre) with rotation 0.
#
# *** THE ONE DIMENSION THAT IS NOT IN ANY DOCUMENT I COULD READ ***
# is the distance from the locating-hole datum line to the front face of the
# latch shroud, i.e. how far back from the board edge the footprint must sit
# for the mating face to be flush with the panel.  Derived instead: the
# footprint spans 9.10 mm on the shell-tail side of the datum line and 5.70 mm
# on the pad side (14.80 mm), against a 15.80 mm overall body depth, so the
# body overhangs the footprint by about 1.00 mm and the front face is about
# 10.10 mm ahead of the datum.  SLIMSAS_SETBACK is set to 10.40 mm, which
# places the nominal front face 0.30 mm BEHIND the board edge, keeps the
# footprint's courtyard just inside the outline, and leaves 1.75 mm of
# copper-to-edge clearance on the shell-tail pads.  The panel
# window is clearance-only (no manufacturer publishes a panel cutout for this
# family) and the panel is a PCB the owner re-cuts, so a 0.5 mm error here is
# absorbed by the window, not by the board.  CHECK IT against Amphenol's
# drawing before cutting the panel.
SLIMSAS = dict(
    j01=10.95, j02=2.70, j03=2.35, j04=0.15, j05=0.60,
    pad_w=0.35, pad_l=1.30, loc_d=1.30,
    j09=5.15, j10=3.00, j11=0.68, tail_d=0.70, tail_pad=1.25,
    npos=37,
    shell_w=23.50, body_front=10.10, body_back=6.20, height=9.90,
)
SLIMSAS_FP = 'SlimSAS_SFF-8654_8i_74P_RightAngle'
SLIMSAS_SETBACK = 10.40      # board edge -> locating-hole datum line
SLIMSAS_LCSC = 'C5432262'
SLIMSAS_MFR = 'Amphenol ICC U10A474240T'


def slimsas_pad_y(i):
    """y of contact position i (1..37).  Position 1 is at +y.

    SFF-8654 Rev 1.2 Figure A-1 labels #1(A1) at one end and #37(A37) at the
    other, with the outer pad centres 0.15 mm inside the locating holes, so
    they run from +10.80 to -10.80 on a 0.60 mm pitch.

    WHICH PHYSICAL END CARRIES A1 DOES NOT MATTER, and that is worth knowing
    because it is exactly the class of mistake that threatened earlier
    revisions.  The SFF-8654 8X pinout is MIRROR-SYMMETRIC about the connector
    centreline: n -> 38-n maps ground to ground (1<->37, 4<->34, 7<->31,
    13<->25, 16<->22, 19<->19), pair to pair, and the sideband set
    {8,9,11,12,26,27,29,30} onto itself.  Both ends of the link use this same
    footprint, so a reversed A1 end cancels through the cable.  The only
    residual effect is that P and N swap within every pair, which inverts
    every lane consistently in both directions and is undone in gateware.
    """
    s = SLIMSAS
    outer = s['j01'] - s['j04']          # 10.80
    return round(outer - (i - 1) * s['j05'], 3)


def build_slimsas_fp(name):
    s = SLIMSAS
    L = []
    a = L.append
    a('(footprint "%s"' % name)
    a('  (version 20240108)')
    a('  (generator "gowin-bridge-gen")')
    a('  (layer "F.Cu")')
    a('  (descr "SlimSAS SFF-8654 8X 8i 74-position right-angle receptacle, '
      '0.60 mm pitch, SMD contacts plus 4 through-hole shell tails and 2 '
      'through-hole locating pegs. Land pattern from SFF-8654 Rev 1.2 Figure '
      'A-1 and Table A-1. Origin on the locating-hole datum line, +x into '
      'the board.")')
    a('  (tags "SlimSAS SFF-8654 8i 74P right angle SAS-4 PCIe")')
    a('  (attr smd)')
    hw = s['shell_w'] / 2.0                     # 11.75
    tail_y = s['j01'] + s['j11']                # 11.63
    crt_y = max(hw, tail_y + s['tail_pad'] / 2.0) + 0.25
    crt_x0 = -(s['body_front'] + 0.25)
    crt_x1 = s['body_back'] + 0.25
    for lay, w_, x0, y0, x1, y1 in (
            ('F.CrtYd', 0.05, crt_x0, -crt_y, crt_x1, crt_y),
            ('F.Fab', 0.10, -s['body_front'], -hw, s['body_back'], hw)):
        a('  (fp_rect (start %.3f %.3f) (end %.3f %.3f) (stroke (width %.2f) '
          '(type default)) (fill none) (layer "%s"))'
          % (x0, y0, x1, y1, w_, lay))
    a('  (fp_line (start %.3f %.3f) (end %.3f %.3f) (stroke (width 0.12) '
      '(type default)) (layer "F.SilkS"))' % (-9.90, hw + 0.3, 6.20, hw + 0.3))
    a('  (fp_line (start %.3f %.3f) (end %.3f %.3f) (stroke (width 0.12) '
      '(type default)) (layer "F.SilkS"))'
      % (-9.90, -hw - 0.3, 6.20, -hw - 0.3))
    a('  (fp_poly (pts (xy 7.10 %.3f) (xy 8.30 %.3f) (xy 7.70 %.3f)) '
      '(stroke (width 0.12) (type default)) (fill solid) (layer "F.SilkS"))'
      % (hw - 0.6, hw - 0.6, hw - 1.6))
    a('  (fp_text user "A1" (at 9.60 %.3f 0) (layer "F.SilkS") '
      '(effects (font (size 0.9 0.9) (thickness 0.15))))' % (hw - 1.0))
    a('  (fp_text reference "REF**" (at 0 %.3f 0) (layer "F.SilkS") '
      '(effects (font (size 1 1) (thickness 0.15))))' % (-crt_y - 1.2))
    a('  (fp_text value "SlimSAS_8i" (at 0 %.3f 0) (layer "F.Fab") '
      '(effects (font (size 1 1) (thickness 0.15))))' % (crt_y + 1.2))
    for row, xc in (('A', s['j02']), ('B', s['j02'] + s['j03'])):
        for i in range(1, s['npos'] + 1):
            a('  (pad "%s%d" smd roundrect (at %.3f %.3f) (size %.3f %.3f) '
              '(layers "F.Cu" "F.Paste" "F.Mask") (roundrect_rratio 0.15))'
              % (row, i, xc, slimsas_pad_y(i), s['pad_l'], s['pad_w']))
    for k, (tx, ty) in enumerate(
            [(-s['j09'], tail_y), (-(s['j09'] + s['j10']), tail_y),
             (-s['j09'], -tail_y), (-(s['j09'] + s['j10']), -tail_y)],
            start=1):
        a('  (pad "SH%d" thru_hole circle (at %.3f %.3f) (size %.3f %.3f) '
          '(drill %.3f) (layers "*.Cu" "*.Mask"))'
          % (k, tx, ty, s['tail_pad'], s['tail_pad'], s['tail_d']))
    for ly in (s['j01'], -s['j01']):
        a('  (pad "" np_thru_hole circle (at 0 %.3f) (size %.3f %.3f) '
          '(drill %.3f) (layers "F&B.Cu" "*.Mask"))'
          % (ly, s['loc_d'] + 0.1, s['loc_d'] + 0.1, s['loc_d'] + 0.1))
    a(')')
    return '\n'.join(L) + '\n'

# ==========================================================================
# Part type catalogue.  key -> (stock symbol lib, stock symbol, stock fp lib,
#                               stock fp)
# ==========================================================================

TYPES = {
    'R':        ('Device', 'R', 'Resistor_SMD', 'R_0402_1005Metric'),
    'R0805':    ('Device', 'R', 'Resistor_SMD', 'R_0805_2012Metric'),
    'C':        ('Device', 'C', 'Capacitor_SMD', 'C_0402_1005Metric'),
    'C0805':    ('Device', 'C', 'Capacitor_SMD', 'C_0805_2012Metric'),
    'FB':       ('Device', 'FerriteBead', 'Inductor_SMD',
                 'L_0603_1608Metric'),
    'TP':       ('Connector', 'TestPoint', 'TestPoint',
                 'TestPoint_Pad_D1.5mm'),
    'TPBIG':    ('Connector', 'TestPoint', 'TestPoint',
                 'TestPoint_THTPad_D2.0mm_Drill1.0mm'),
    'PWRFLAG':  ('power', 'PWR_FLAG', None, None),
    'LVDS_DRV': (None, 'DS90LV047A', 'Package_SO', 'SOIC-16_3.9x9.9mm_P1.27mm'),
    'LVDS_RCV': (None, 'DS90LV048A', 'Package_SO', 'TSSOP-16_4.4x5mm_P0.65mm'),
    # The ONLY logic part number on the board.  Every level shift and every
    # gated buffer is one of these, because JLCPCB's assembly library contains
    # no Basic-tier buffer, driver, receiver or transceiver of any family from
    # any manufacturer (checked 12 Sep 2026 across the whole 244 octal family,
    # the 125/126 quad families and the entire Buffers/Drivers/Receivers
    # category), so every extra logic part number would cost its own $3.07
    # per-unique-Extended-part fee.  Seven of one part cost one fee; a
    # 74LVC244 plus a 74LVC125 would have cost two.  COST.md section 3.
    'XLAT4':    ('Logic_LevelTranslator', 'SN74AVC4T245PW', 'Package_SO',
                 'TSSOP-16_4.4x5mm_P0.65mm'),
    'ESD4':     ('Power_Protection', 'TPD4E05U06DQA', 'Package_SON',
                 'USON-10_2.5x1.0mm_P0.5mm'),
    'LDO25':    ('Regulator_Linear', 'ME6211C25M5', 'Package_TO_SOT_SMD',
                 'SOT-23-5'),
    'SLIMSAS':  (None, 'SLIMSAS_8I', None, SLIMSAS_FP),
    'SKT2x10':  ('Connector_Generic', 'Conn_02x10_Odd_Even',
                 'Connector_PinSocket_2.54mm',
                 'PinSocket_2x10_P2.54mm_Vertical'),
    'SKT2x05':  ('Connector_Generic', 'Conn_02x05_Odd_Even',
                 'Connector_PinSocket_2.54mm',
                 'PinSocket_2x05_P2.54mm_Vertical'),
    'SKT2x03':  ('Connector_Generic', 'Conn_02x03_Odd_Even',
                 'Connector_PinSocket_2.54mm',
                 'PinSocket_2x03_P2.54mm_Vertical'),
    'HDR2x05':  ('Connector_Generic', 'Conn_02x05_Odd_Even',
                 'Connector_PinHeader_2.54mm',
                 'PinHeader_2x05_P2.54mm_Vertical'),
    'HDR1x02':  ('Connector_Generic', 'Conn_01x02',
                 'Connector_PinHeader_2.54mm',
                 'PinHeader_1x02_P2.54mm_Vertical'),
    'MH':       ('Mechanical', 'MountingHole_Pad', 'MountingHole',
                 'MountingHole_3.2mm_M3_Pad'),
    'FIDUCIAL': ('Mechanical', 'Fiducial', 'Fiducial', 'Fiducial_1mm_Mask2mm'),
}


# LVDS driver DS90LV047A, verified against TI SNLS044D "Pin Functions":
#   DIN 2,3,6,7 / DOUT+ 10,11,14,15 / DOUT- 9,12,13,16 / EN 1 / EN* 8
#   GND 5 / VCC 4.  Flow-through: DIN pin n pairs with the outputs opposite it.
DRV_PINS = [
    ('1', 'EN', 'input', 'L'), ('2', 'DIN1', 'input', 'L'),
    ('3', 'DIN2', 'input', 'L'), ('4', 'VCC', 'power_in', 'T'),
    ('5', 'GND', 'power_in', 'B'), ('6', 'DIN3', 'input', 'L'),
    ('7', 'DIN4', 'input', 'L'), ('8', '~{EN}', 'input', 'L'),
    ('9', 'DOUT4-', 'output', 'R'), ('10', 'DOUT4+', 'output', 'R'),
    ('11', 'DOUT3+', 'output', 'R'), ('12', 'DOUT3-', 'output', 'R'),
    ('13', 'DOUT2-', 'output', 'R'), ('14', 'DOUT2+', 'output', 'R'),
    ('15', 'DOUT1+', 'output', 'R'), ('16', 'DOUT1-', 'output', 'R'),
]
# LVDS receiver DS90LV048A, verified against TI SNLS045C "Pin Functions":
#   RIN+ 2,3,6,7 / RIN- 1,4,5,8 / ROUT 10,11,14,15 / EN 16 / EN* 9
#   GND 12 / VCC 13.
RCV_PINS = [
    ('1', 'RIN1-', 'input', 'L'), ('2', 'RIN1+', 'input', 'L'),
    ('3', 'RIN2+', 'input', 'L'), ('4', 'RIN2-', 'input', 'L'),
    ('5', 'RIN3-', 'input', 'L'), ('6', 'RIN3+', 'input', 'L'),
    ('7', 'RIN4+', 'input', 'L'), ('8', 'RIN4-', 'input', 'L'),
    ('9', '~{EN}', 'input', 'R'), ('10', 'ROUT4', 'output', 'R'),
    ('11', 'ROUT3', 'output', 'R'), ('12', 'GND', 'power_in', 'B'),
    ('13', 'VCC', 'power_in', 'T'), ('14', 'ROUT2', 'output', 'R'),
    ('15', 'ROUT1', 'output', 'R'), ('16', 'EN', 'input', 'R'),
]

# Channel index -> pad numbers, so the netlist reads by channel not by pad.
DRV_IN = {0: '2', 1: '3', 2: '6', 3: '7'}
DRV_P = {0: '15', 1: '14', 2: '11', 3: '10'}
DRV_N = {0: '16', 1: '13', 2: '12', 3: '9'}
RCV_P = {0: '2', 1: '3', 2: '6', 3: '7'}
RCV_N = {0: '1', 1: '4', 2: '5', 3: '8'}
RCV_OUT = {0: '15', 1: '14', 2: '11', 3: '10'}

# SN74AVC8T245PW (TSSOP-24): 1 VCCA, 2 DIR, 3..10 A1..A8, 11/12/13 GND,
# 14..21 B8..B1, 22 OE*, 23/24 VCCB.  DIR and OE* are referenced to VCCA.
X8_A = {1: '3', 2: '4', 3: '5', 4: '6', 5: '7', 6: '8', 7: '9', 8: '10'}
X8_B = {1: '21', 2: '20', 3: '19', 4: '18', 5: '17', 6: '16', 7: '15', 8: '14'}
# SN74AVC4T245PW (TSSOP-16): 1 VCCA, 2 1DIR, 3 2DIR, 4 1A1, 5 1A2, 6 2A1,
# 7 2A2, 8/9 GND, 10 2B2, 11 2B1, 12 1B2, 13 1B1, 14 2OE*, 15 1OE*, 16 VCCB.
X4_A = {1: '4', 2: '5', 3: '6', 4: '7'}
X4_B = {1: '13', 2: '12', 3: '11', 4: '10'}


def build_custom_symbol(w, name, pins, footprint, datasheet, desc):
    """Emit a plain rectangular symbol with pins on the sides."""
    left = [p for p in pins if p[3] == 'L']
    right = [p for p in pins if p[3] == 'R']
    top = [p for p in pins if p[3] == 'T']
    bot = [p for p in pins if p[3] == 'B']
    rows = max(len(left), len(right))
    half_h = (rows + 1) * 2.54 / 2.0
    half_w = 12.7
    base = name.split(':')[-1]
    w.open('symbol', q(name))
    w.line('pin_names', '(offset 1.016)')
    w.line('exclude_from_sim', 'no')
    w.line('in_bom', 'yes')
    w.line('on_board', 'yes')
    for i, (k, v, hide) in enumerate([
            ('Reference', 'U', False), ('Value', base, False),
            ('Footprint', footprint, True), ('Datasheet', datasheet, True),
            ('Description', desc, True)]):
        w.open('property', q(k), q(v))
        w.line('at', '0', fmt(half_h + 2.54 - i * 2.54), '0')
        w.raw(effects(hide=hide))
        w.close_inline()
    w.open('symbol', q(base + '_0_1'))
    w.open('rectangle')
    w.line('start', fmt(-half_w), fmt(half_h))
    w.line('end', fmt(half_w), fmt(-half_h))
    w.line('stroke', '(width 0.254)', '(type default)')
    w.line('fill', '(type background)')
    w.close_inline()
    w.close_inline()
    w.open('symbol', q(base + '_1_1'))

    def pin(num, nm, etype, x, y, rot):
        w.open('pin', etype, 'line')
        w.line('at', fmt(x), fmt(y), rot)
        w.line('length', '2.54')
        w.open('name', q(nm))
        w.raw(effects())
        w.close_inline()
        w.open('number', q(num))
        w.raw(effects())
        w.close_inline()
        w.close_inline()

    y = half_h - 2.54
    for num, nm, etype, _ in left:
        pin(num, nm, etype, -(half_w + 2.54), y, 0)
        y -= 2.54
    y = half_h - 2.54
    for num, nm, etype, _ in right:
        pin(num, nm, etype, half_w + 2.54, y, 180)
        y -= 2.54
    x = -2.54
    for num, nm, etype, _ in top:
        pin(num, nm, etype, x, half_h + 2.54, 270)
        x += 5.08
    x = -2.54
    for num, nm, etype, _ in bot:
        pin(num, nm, etype, x, -(half_h + 2.54), 90)
        x += 5.08
    w.close_inline()
    w.close_inline()


# ==========================================================================
#  SFF-8654 8X pin assignment - the physical facts, before any net names
# ==========================================================================
#
# SFF-8654 Rev 1.2 defines the connector's mechanics and its pin NUMBERING
# only; section 3.1 says outright "Refer to documents SFF-9400 and SFF-9402
# for the possible pinout signal assignments".  The assignment below therefore
# comes from SFF-9402 Rev 1.1 Table 6-2 and Table 6-3 (the "Multiprotocol
# SAS-4 / Other Protocol (x8) Cables" pair of tables), read together with
# SFF-8654 Rev 1.2 Figure 3-5.
#
# Two rows of 37 contacts, numbered A1..A37 and B1..B37, with A1 and B1 at the
# same physical end.  Looking into the receptacle, row B is the upper row and
# row A the lower; on a right-angle part row A is the row nearer the two
# locating pegs.  Tally: 16 differential pairs (32 pins) + 26 grounds +
# 16 sideband pins = 74.  THERE ARE NO POWER PINS on the 74-circuit connector
# (the POWER 3.3Vact and POWER 5V pins in SFF-9402's tables belong only to the
# 80-circuit SFF-8621 MiniLink), which is why this board takes all its power
# from the HL2's own DB1 header.
#
# THE CROSSOVER, which is what makes one design work at both ends.  SFF-9402
# Rev 1.1 section 5, implementation note 16: "The pinouts in this reference
# guide define full crossover cables (The A row on one end crosses over to the
# B row on the other end) ... a. Based on a full crossover the TX (inputs to
# the cable at one end) crossover to RX (outputs from the cable at the other
# end). b. The sideband signals also implement a full crossover".  Tables 6-2
# and 6-3 then show it pin by pin: A1..A37 at one end map to B1..B37 at the
# other and B1..B37 map to A1..A37, so the rule is simply
#
#       A(n) at one end  <->  B(n) at the other end,  n = 1..37
#
# for EVERY position - high-speed pairs, sidebands, the two-wire management
# pins and the REFCLK/VSP pairs alike, with no exceptions on this connector.
# Independently corroborated by two production cable drawings (IcyDock's
# SFF-8654 4i-to-4i pinout sheet and Dongguan Aiqun drawing AQ03-0219A for an
# 8i end), both of which match the tables exactly.
#
# So this board DRIVES row A and LISTENS on row B, and the identical board at
# the far end drives its row A into this board's row B.  PINMAP.md rev D
# section 1 tabulates it.
#
# STILL UNVERIFIED: 10Gtek publish no pinout or wiring diagram for the
# CAB-8654/8654-8i-P cable itself - not on the product page, not in the
# catalogue, not in any datasheet.  The crossover is therefore inferred from
# the specification the cable claims to comply with plus two third-party
# drawings, not from the vendor.  Ohmmeter the first cable before committing
# to fabrication: confirm that a pin in one plug's row A reaches the OTHER row
# at the far end, same number.

SS_GND = (1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34, 37)
# The eight high-speed pair positions, as (positive, negative) position
# numbers.  Row A carries PERp/PERn (receive, from the root's point of view)
# and row B carries PETp/PETn (transmit); we ignore those names and use the
# rows as "our outputs" (A) and "our inputs" (B).
SS_PAIRS = ((2, 3), (5, 6), (14, 15), (17, 18),
            (20, 21), (23, 24), (32, 33), (35, 36))
# The eight single-ended sideband positions.  In SFF-9402's own naming these
# are BP_TYPE / CWAKE# / RESET / REFCLK+- / 2W-CLK / 2W-DATA / PERST# /
# CPRSNT# depending on row and on which end of the cable is which; we use them
# as eight full-duplex single-ended channels, one output on A(n) and one input
# on B(n) per position.  SFF-9402's own warning applies: sideband use differs
# between protocols, so each sideband must be isolated and never commoned.
SS_SIDEBAND = (8, 9, 11, 12, 26, 27, 29, 30)
SS_NPOS = 37

assert len(SS_GND) + 2 * len(SS_PAIRS) + len(SS_SIDEBAND) == SS_NPOS
assert sorted(SS_GND + tuple(p for pr in SS_PAIRS for p in pr)
              + SS_SIDEBAND) == list(range(1, SS_NPOS + 1))
# The mirror symmetry that makes the A1 end harmless (see slimsas_pad_y):
assert set(SS_GND) == {38 - n for n in SS_GND}
assert set(SS_SIDEBAND) == {38 - n for n in SS_SIDEBAND}


def _ss_pins():
    out = []
    for row, side in (('A', 'L'), ('B', 'R')):
        for i in range(1, SS_NPOS + 1):
            et = 'passive' if i in SS_GND else 'bidirectional'
            out.append(('%s%d' % (row, i), '%s%d' % (row, i), et, side))
    # The four through-hole shell tails.  They are real pads that need a real
    # net, and leaving them off the symbol is how they end up unconnected on
    # the PCB with nothing to notice it.
    for k in range(1, 5):
        out.append(('SH%d' % k, 'SHELL%d' % k, 'passive', 'B'))
    return out


SS_PINS = _ss_pins()

# name -> (pin list, datasheet URL, description).  These are the symbols that
# are drawn here rather than lifted from the stock KiCad libraries.
CUSTOM = {
    'DS90LV047A': (DRV_PINS,
                   'https://www.ti.com/lit/ds/symlink/ds90lv047a.pdf',
                   'Quad LVDS line driver, 400 Mbps, EN high + EN* low '
                   '= enabled'),
    'DS90LV048A': (RCV_PINS,
                   'https://www.ti.com/lit/ds/symlink/ds90lv048a.pdf',
                   'Quad LVDS line receiver, 400 Mbps, EN high + EN* low '
                   '= enabled'),
    'SLIMSAS_8I': (SS_PINS,
                   'https://members.snia.org/document/dl/26744',
                   'SlimSAS SFF-8654 8X (8i) 74-position receptacle, right '
                   'angle. Row A = this board drives, row B = this board '
                   'listens; the cable crosses A(n) to B(n)'),
}
CUSTOM_SYMS = tuple(CUSTOM)

# ==========================================================================
#  Part / design model
# ==========================================================================


class Part:
    def __init__(self, ref, ptype, value, pins, lcsc='', mfr='', desc='',
                 dnp=False, note='', at=None, rot=0, layer='F.Cu',
                 exclude_bom=False, mirror=False, qty=1):
        self.ref = ref
        self.ptype = ptype
        self.value = value
        self.pins = dict(pins)          # pad number (str) -> net name or None
        self.lcsc = lcsc
        self.mfr = mfr
        self.desc = desc
        self.dnp = dnp
        self.note = note
        self.at = at                    # (x, y) on the PCB, mm
        self.rot = rot
        self.layer = layer
        self.exclude_bom = exclude_bom
        self.qty = qty
        # Bottom-side sockets: KiCad does NOT mirror pad coordinates for a
        # B.Cu footprint (verified against the Excellon drill export), so a
        # socket that must mate a male header seen from above has to be
        # mirrored in x here.
        self.mirror = mirror


class Board:
    def __init__(self, name, title, outline, size, origin_note=''):
        self.name = name
        self.title = title
        self.outline = outline          # list of (x, y) polygon points
        self.size = size
        self.parts = []
        self.texts = []                 # (layer, x, y, rot, size, text)
        self.lines = []                 # (layer, x0, y0, x1, y1, width)
        self.origin_note = origin_note
        # (layer, net, priority, polygon, name) for anything that is not a
        # full-board pour: the +2V5 island, and the panel's per-board planes.
        self.zones_extra = []
        # Full-board pours are per board too, because the panel has two
        # independent boards on one outline and must not pour one net across
        # both.  Empty means "the four standard pours over self.outline".
        self.zones_full = None
        # extra graphics the panel needs: V-score lines, mouse-bite drills
        self.npth = []                  # (x, y, drill) plain holes
        self.edge_extra = []            # [(x0,y0,x1,y1)] more Edge.Cuts

    def calibration_rule(self, x, y, length=50.0):
        """A dimension line on Dwgs.User so the user can confirm that a
        printed 1:1 template really is 1:1 before offering it up to the
        hardware. Printer drivers scale to fit without saying so."""
        self.lines.append(('Dwgs.User', x, y, x + length, y, 0.15))
        for tx in (x, x + length):
            self.lines.append(('Dwgs.User', tx, y - 1.2, tx, y + 1.2, 0.15))
        for i in range(1, int(length // 10)):
            self.lines.append(('Dwgs.User', x + 10.0 * i, y - 0.7,
                               x + 10.0 * i, y + 0.7, 0.12))
        self.texts.append(('Dwgs.User', x + length / 2.0, y - 2.4, 0, 1.4,
                           'PRINT AT 100%% AND MEASURE: %.0f.00 mm'
                           % length))

    def add(self, *parts):
        for p in parts:
            self.parts.append(p)
        return parts[0] if len(parts) == 1 else parts

    def nets(self):
        seen = {}
        for p in self.parts:
            for net in p.pins.values():
                if net and net not in seen:
                    seen[net] = len(seen) + 1
        order = ['GND'] + sorted(n for n in seen if n != 'GND')
        return {n: i + 1 for i, n in enumerate(order)}


def R(ref, val, a, b, **kw):
    t = 'R0805' if kw.pop('big', False) else 'R'
    return Part(ref, t, val, {'1': a, '2': b}, **kw)


def R0805(ref, val, a, b, **kw):
    """An 0805 resistor.  Separate from R() only so the 0805 0 ohm jumper
    cannot accidentally be given the 0402 part number, which is what rev B
    did."""
    return Part(ref, 'R0805', val, {'1': a, '2': b}, **kw)


def C(ref, val, a, b, **kw):
    t = 'C0805' if kw.pop('big', False) else 'C'
    return Part(ref, t, val, {'1': a, '2': b}, **kw)


def TP(ref, net, **kw):
    return Part(ref, kw.pop('t', 'TP'), 'TP_' + net, {'1': net}, **kw)


def FLAG(net):
    return Part('#FLG_' + net.replace('+', 'P').replace('-', 'N'), 'PWRFLAG',
                'PWR_FLAG', {'1': net}, exclude_bom=True)


# LCSC numbers for the passives, in one place.
# LCSC numbers for the passives, in one place.  EVERY number here was
# checked against LCSC's live catalogue on 12 Sep 2026; the rev B set had six
# numbers that were wrong, non-existent or unbuyable and four that pointed at
# a different value or package than the BOM claimed.  The surviving set is
# eleven values, all confirmed in stock and all JLCPCB Basic parts except
# where noted.  DO NOT add a value here without looking the number up.
LC = dict(r0='C17168',        # 0R    0402, Basic
          r22='C25092',       # 22R   0402, Basic
          r100='C25076',      # 100R  0402, Basic
          r220='C25091',      # 220R  0402, Basic
          r470='C25117',      # 470R  0402, Basic - now a Basic
                              # part, which it was not in rev C
          r1k='C11702',       # 1k    0402, Basic
          fb='C14709',        # BLM18PG121SN1D ferrite bead
                              # 0603, 120R@100MHz, 2A, 50mOhm,
                              # the ONLY Basic bead combining
                              # >=1A with <=150 mOhm
          r330='C25104',      # 330R  0402, Basic - 742,400 in stock
          r4k7='C25900',      # 4k7   0402, Basic
          r10k='C25744',      # 10k   0402, Basic
          r100k='C25741',     # 100k  0402, Basic
          c100n='C1525',      # 100nF 0402, Basic
          c1u='C52923',       # 1uF   0402, Basic
          # C15525 was in the rev B BOM as "10uF 0805". It is NOT: it is
          # Samsung CL05A106MQ5NUNC, 10 uF 6.3 V X5R in **0402**, checked on
          # LCSC's own page. On 0805 pads that is the wrong part, and 6.3 V
          # on the 5 V input bulk would lose most of its capacitance to DC
          # bias anyway. Replaced by Samsung CL21A106KAYNNNE, 10 uF 25 V X5R
          # 0805, JLCPCB Basic, 2,760,420 in stock, $0.085 at the MOQ of 20.
          c10u='C15850',      # 10uF 25V 0805, Basic
          c22p='C1555',       # 22pF  0402, Basic
          # 0R in 0805 needs its OWN number: C17168 is an 0402 and on 0805
          # pads it is the wrong part. C17477 is UNI-ROYAL 0805W8F0000T5E,
          # 2 A rated, 6,045,800 in stock, and the only Basic 0805 zero-ohm
          # jumper in JLCPCB's library.
          r0_0805='C17477',   # 0R 0805, Basic, MOQ 100
          esd='C138714')      # TPD4E05U06DQAR, USON-10

# Silicon, connectors and the hand-fitted sockets.  Same rule: every number
# verified live.  See STATUS.md for what each one replaced.
LC_DRV = 'C206491'        # DS90LV047ATMX/NOPB, quad LVDS driver, SOIC-16
LC_RCV = 'C87137'         # DS90LV048ATMTCX/NOPB, quad LVDS receiver, TSSOP-16
# SN74AVC8T245PWR was C465742.  No longer used: two SN74AVC4T245
# do the same job for $0.31 less and one fewer unique part number.
LC_X4 = 'C81461'          # SN74AVC4T245PWR
LC_INV = 'C20917'        # AO3400A N-MOSFET, SOT-23, BASIC (replaces
                          # C7827, SN74LVC1G04DBVR, which is Extended)
LC_LDO25 = 'C194395'      # ME6211C25M5G-N
LC_LDO33 = 'C6186'         # AMS1117-3.3, Basic
# Pin headers need DISCRETE part numbers, not a strip: C2337 is a 1x40
# strip and JLCPCB's BOM matcher will not accept a 40-pin part against a
# 3-pin footprint.  Both of these are hanxia PH254 series, 2.54 mm,
# through-hole, straight.  Both are Extended - no Basic 2.54 mm through-hole
# 1x2 or 1x3 vertical header exists in JLCPCB's library at all.
# THE THROUGH-HOLE PARTS ARE NOT ON THE ASSEMBLY BOM.  Every one of them is
# a distinct part number to JLCPCB and every distinct part costs a $3.07
# per-unique-Extended-part fee on the Economic tier - no Basic 2.54 mm
# through-hole header or socket exists in their library at all.  Three fees
# plus their joint fees came to $11.61 for nineteen header pins and one
# forty-pin socket, so the user solders them.  These numbers are recorded so
# the parts can be bought; they appear in the BOM as MFR text with no LCSC
# field, which is how a do-not-place line is flagged.  COST.md section 5.
#   1x3 vertical pin header       C52016391  (hanxia HX PH254-01-03-Z-L11.5)
#   1x2 vertical pin header       C52016390  (hanxia HX PH254-01-02-Z-L11.5)
#   2x20 vertical female, Tang    C5124634   (BOOMELE)
#   2x10 vertical female, DB1     C42431860  (JXTCONN PM2.54-2X10P-H85) -
#                                            the fallback if you never stack
#   jumper shunts                 C5305



def esd_arrays(prefix, start_index, lines, note):
    """Group a flat list of net names into 4-channel TPD4E05U06 arrays."""
    out = []
    idx = start_index
    for i in range(0, len(lines), 4):
        grp = lines[i:i + 4] + [None] * 4
        out.append(Part('%s%d' % (prefix, idx), 'ESD4', 'TPD4E05U06',
                        {'1': grp[0], '2': grp[1], '4': grp[2], '5': grp[3],
                         '3': 'GND', '8': 'GND'},
                        lcsc=LC['esd'], mfr='TPD4E05U06DQAR',
                        desc='Quad 0.5 pF ESD array, 5.5 V, USON-10',
                        note=note))
        idx += 1
    return out, idx


class RefGen:
    """Hands out reference designators so nothing collides."""

    def __init__(self):
        self.n = {}

    def __call__(self, prefix):
        self.n[prefix] = self.n.get(prefix, 0) + 1
        return '%s%d' % (prefix, self.n[prefix])


_CRT_CACHE = {}


def courtyard(ptype, rot=0):
    """(half width, half height) of a part type's courtyard, in mm, read from
    the real footprint rather than from a table, so the placer can never
    disagree with what is emitted."""
    key = (ptype, rot % 180)
    if key in _CRT_CACHE:
        return _CRT_CACHE[key]
    symlib, symname, fplib, fpname = TYPES[ptype]
    if not fpname:
        _CRT_CACHE[key] = (0.0, 0.0)
        return _CRT_CACHE[key]
    if fplib is None:
        node = K.parse(build_slimsas_fp(fpname))[0]
    else:
        node = FPLIB.get(fplib, fpname)
    ext = K.footprint_extent(node, 'F.CrtYd')
    if ext is None:
        xs, ys = [], []
        for pad in K.kids(node, 'pad'):
            at = K.atoms(K.kid(pad, 'at'))
            sz = K.atoms(K.kid(pad, 'size'))
            xs += [float(at[0]) - float(sz[0]) / 2,
                   float(at[0]) + float(sz[0]) / 2]
            ys += [float(at[1]) - float(sz[1]) / 2,
                   float(at[1]) + float(sz[1]) / 2]
        ext = (min(xs), min(ys), max(xs), max(ys))
    hw = max(abs(ext[0]), abs(ext[2]))
    hh = max(abs(ext[1]), abs(ext[3]))
    if rot % 180 == 90:
        hw, hh = hh, hw
    _CRT_CACHE[key] = (hw, hh)
    return _CRT_CACHE[key]


PLACE_GAP = 0.40             # clearance left between neighbouring courtyards
PLACE_TYPES = ('R', 'R0805', 'C', 'C0805', 'TP', 'TPBIG', 'ESD4')


def autoplace(board, regions):
    """Shelf-pack every small part into the free regions using its real
    courtyard, so no two courtyards overlap and no pad lands on another.

    A placement *starting point* only - the board is routed by hand (or in
    EasyEDA Pro) - but it has to be DRC-clean before routing starts, which a
    fixed grid is not: an 0805 courtyard is 3.4 mm wide and would overlap its
    neighbour on any grid fine enough to fit the 0402s.

    Keep-outs are derived from the parts that ALREADY have a position (the
    connectors, the ICs, the headers), so adding or moving a chip cannot leave
    a stale reserved rectangle behind.  Parts are packed tallest-first into
    horizontal shelves.
    """
    if isinstance(regions[0], (int, float)):
        regions = [regions]
    reserved = []
    for q_ in board.parts:
        # Anything already positioned is a keep-out, including a test pad or
        # a capacitor that was placed by hand.
        if q_.at is None or not TYPES[q_.ptype][3]:
            continue
        hw, hh = courtyard(q_.ptype, q_.rot)
        reserved.append((q_.at[0] - hw, q_.at[1] - hh,
                         q_.at[0] + hw, q_.at[1] + hh))
    todo = [q_ for q_ in board.parts
            if q_.ptype in PLACE_TYPES and q_.at is None]
    todo.sort(key=lambda q_: -courtyard(q_.ptype)[1])

    def blocked(x0, y0, x1, y1):
        for (rx0, ry0, rx1, ry1) in reserved:
            if (x0 < rx1 + PLACE_GAP and x1 > rx0 - PLACE_GAP
                    and y0 < ry1 + PLACE_GAP and y1 > ry0 - PLACE_GAP):
                return True
        return False

    i = 0
    for (rx0, ry0, rx1, ry1) in regions:
        y = ry0
        while y < ry1 and i < len(todo):
            shelf_h = 2.0 * courtyard(todo[i].ptype)[1] + PLACE_GAP
            if y + shelf_h > ry1:
                break
            x = rx0
            while x < rx1 and i < len(todo):
                pp = todo[i]
                hw, hh = courtyard(pp.ptype)
                w = 2.0 * hw + PLACE_GAP
                if 2.0 * hh + PLACE_GAP > shelf_h or x + w > rx1:
                    break
                cx, cy = x + w / 2.0, y + shelf_h / 2.0
                if blocked(cx - hw, cy - hh, cx + hw, cy + hh):
                    x += 0.5
                    continue
                pp.at = (round(cx, 3), round(cy, 3))
                reserved.append((cx - hw, cy - hh, cx + hw, cy + hh))
                i += 1
                x += w
            y += shelf_h
    if i < len(todo):
        raise SystemExit('autoplace: %d of %d small parts did not fit on %s; '
                         'enlarge its regions' % (len(todo) - i, len(todo),
                                                  board.name))


# ==========================================================================
#  THE BOARD.  One design, one schematic, one PCB, one BOM.
# ==========================================================================
#
# Local origin (0,0) == Hermes-Lite 2 main-board coordinate (70.00, 73.30) mm,
# so local x = HL2_x - 70.00 and local y = HL2_y - 73.30.  x = 0 is the HL2's
# own front board edge, which is also the plane of the front endcap, so the
# SlimSAS mating face sits at local x ~ 0.  Every HL2 feature below was read
# out of hardware/hl/hermeslite.kicad_pcb and is re-derived independently by
# tools/check_geometry.py:
#
#   DB1  HERMESLITE:10x2  at (75.31, 89.39) rot 270 -> odd pins HL2 x 74.04,
#        even 76.58, pin 1/2 at y 77.96 stepping +2.54 to pin 19/20 at 100.82
#   DB12 HERMESLITE:3x2   at (83.50, 90.00) rot 0   -> odd x 83.50, even
#        86.04, rows y 87.46 / 90.00 / 92.54
#   CN1  HERMESLITE:USBBLASTER at (129.50, 87.30) rot 270 -> odd pins
#        HL2 x 128.23, even 130.77, pin 1/2 at y 82.22 stepping +2.54
#   MH2  DNI M3 hole at (73.00, 137.00), 3.3 mm drill
#   MH6  DNI 1 mm locating hole at (74.04, 75.42)
#
# WHY THE CONNECTOR IS NOT IN FRONT OF DB1.  The obvious place for the
# SlimSAS receptacle is the middle of the front edge, inside the 29.60 mm of
# panel that HL2_MECHANICAL_ENVELOPE.md section 2.5 shows is free at board
# level (HL2 y 72.86 to 102.44).  It cannot go there.  A right-angle
# receptacle's contact pads land 12.35 to 15.35 mm inboard of the board edge
# and its shell tails 1.65 to 8.15 mm inboard, and DB12's six through-holes
# are at local x 13.50 and 16.04 - straight through the middle of a 0.60 mm
# pitch pad field - while DB1's twenty holes at local x 4.04 and 6.58 collide
# with the shell tails.  No setback fixes it: pushing the connector inboard
# far enough to clear both (>= 16.4 mm) puts the mating face 6 mm behind the
# panel, where no plug can reach it.
#
# The connector therefore moves ALONG the front edge, to local y 46.00
# (HL2 y 119.30), past the far end of DB1.  That works because the panel
# opens out with height: section 2.4 and 11.3 show the clear width at the
# board's own level is 29.60 mm, bounded by the magjack and the clock SMAs,
# but above about 14 mm it is the full 96.50 mm of the extrusion's internal
# width (HL2 y 41.75 to 138.25).  This board's underside is at 11.04 mm and
# its top surface at 12.64 mm, so a connector standing on top of it occupies
# 12.64 to 22.54 mm above the main board - entirely inside that band, and
# above the existing clock-SMA and KEY-jack holes rather than beside them.
# What is underneath at that y is the two clock SMAs (HL2 y 103.36 to 123.60,
# 3 to 8 mm tall, measurement M3) and the 3.5 mm KEY jack (y 124.00 to 136.00,
# 6 to 10 mm tall, measurement M2), both of which an 11.04 mm underside
# clears.  DESIGN_NOTES.md section 7 has the arithmetic and the two
# measurements that could still bite.
#
# The floor plan that falls out of it is better than rev C's, not worse: the
# level translators and LVDS chips sit in the local x 8..30, y 0..32 block
# right beside DB1 and DB12, so every single-ended HL2 net stays well under
# the 25 mm rule of section 11.6, and the runs from the chips up to the
# connector are terminated 100 ohm differential pairs over an unbroken ground
# plane, which do not care about 25 or 35 mm.

BOARD_W = 64.50          # local x 0 .. 64.50  = HL2 x 70.00 .. 134.50
BOARD_H = 64.95          # local y 0 .. 64.95  = HL2 y 73.30 .. 138.25
HL2_ORIGIN = (70.00, 73.30)


def _loc(x, y):
    return (round(x - HL2_ORIGIN[0], 3), round(y - HL2_ORIGIN[1], 3))


DB1_PIN1 = _loc(74.04, 77.96)        # (4.04,  4.66)
DB12_PIN1 = _loc(83.50, 87.46)       # (13.50, 14.16)
CN1_PIN1 = _loc(128.23, 82.22)       # (58.23, 8.92)
MH2_AT = _loc(73.00, 137.00)         # (3.00, 63.70)
MH6_AT = _loc(74.04, 75.42)          # (4.04,  2.12)

# The connector's centre along the front edge.  46.00 is not free: the shell
# tails sit 11.63 mm either side of it at local x 2.15 and 5.15, and DB1's pad
# column at local x 4.04 is only 1.11 mm away in x, so the tails have to miss
# DB1's 2.54 mm pad pitch in y.  Moving the connector past the end of DB1
# (local y 27.52 plus clearance) settles it with room to spare, and 46.00 also
# centres the 25.95 mm plug overmould inside the extrusion's internal width
# with 6 mm of margin at the top and 33 mm at the bottom.
SLIMSAS_AT = (SLIMSAS_SETBACK, 46.00)

# A window in the board that keeps two of the radio's own configuration
# headers reachable: DB6 (HL2 x 115.80-120.70, y 117.80-123.80) and DB3
# (x 123.33-125.87, y 114.39-122.01) both carry 2.54 mm shunts about 8.5 mm
# tall.  They clear an 11.04 mm underside by 2.5 mm, so this is about access,
# not collision: without the window you would have to lift the whole board off
# to move a jumper.  131 mm2, 3 % of the board.
CUTOUT = (44.50, 39.50, 57.00, 50.00)


# --------------------------------------------------------------------------
#  The lane map.  THIS IS THE CONTRACT.
# --------------------------------------------------------------------------
#
# Eight full-duplex lanes.  For lane k the connector's row A position carries
# what THIS board drives and the row B position at the SAME number carries
# what this board receives, and the cable's A(n)->B(n) crossover therefore
# lands each output on the input that wants it AT THE FAR END.  The pairing
# below is function-mirrored on purpose, so that two of these boards joined by
# one cable form a working radio-to-radio link:
#
#     forward clock out (FPGA 98)  faces  reverse clock in (FPGA 88)
#     ADC data 0/1/2   (76,77,83)  faces  transmit data 0/1/2 (99,100,101)
#     aux clock out    (85)        faces  aux clock in  (89)
#     aux data out     (86)        faces  aux data in   (87)
#     duplicate forward clock      faces  a second receiver, selectable onto
#                                         the same FPGA pin 88 by one link
#     spare driver channel         faces  a spare receiver channel
#
# So each radio sends its own ADC stream on its forward lanes and receives the
# other radio's stream on its reverse lanes, with no strap, no jumper and no
# configuration step.  tools/check_netlist.py asserts every row of this table
# and asserts the mirroring property itself.
#
# Position order along the connector, for the layout: positions 2..6 and
# 14..24 and 32..36 are the pair fields, with the two sideband blocks at 8..12
# and 26..30 between them.  The forward group - clock plus its three data
# lanes - is deliberately on positions 14/15, 17/18, 20/21 and 23/24, which
# are four CONTIGUOUS pairs each flanked by grounds and uninterrupted by a
# sideband block, because those four are the ones whose skew has to match.
LANES = (
    # pos  out net        in net         description
    (2,  'AUXCLK', 'AUXCLK', 'auxiliary clock, HL2 pin 85 out / pin 89 in'),
    (5,  'AUXDAT', 'AUXDAT', 'auxiliary data, HL2 pin 86 out / pin 87 in'),
    (14, 'FWDCLK', 'REVCLK', 'forward clock 153.6 MHz, HL2 pin 98 out / '
                             'reverse clock into pin 88'),
    (17, 'ADCD0', 'TXD0', 'ADC sample data 0, HL2 pin 76 out / transmit '
                          'data 0 into pin 99'),
    (20, 'ADCD1', 'TXD1', 'ADC sample data 1, HL2 pin 77 out / transmit '
                          'data 1 into pin 100'),
    (23, 'ADCD2', 'TXD2', 'ADC sample data 2, HL2 pin 83 out / transmit '
                          'data 2 into pin 101'),
    (32, 'DUPCLK', 'DUPCLK', 'DUPLICATE forward clock from a second driver '
                             'channel / a second receiver for the far end'
                             "'s duplicate, link-selectable onto pin 88"),
    (35, 'SPARE', 'SPARE', 'spare lane, one driver channel out and one '
                           'receiver channel in, both on test pads'),
)

# The eight single-ended sideband channels, same idea: A(n) is what this board
# drives, B(n) is what it receives.
#
# Two of the eight A positions are deliberately NOT DRIVEN, and that is the
# whole safety argument for JTAG over the cable in a radio-to-radio link.
# Position 9's input is TCK and position 29's input is TMS; because nothing on
# this board ever drives A9 or A29, one radio can never clock or steer the
# other radio's JTAG state machine, whatever the enable does.  TDO is driven
# out on position 30, whose input is TDI - a data line that does nothing
# without a clock.  Report line: with the feature disabled all four JTAG lines
# at the far CN1 see a tri-stated buffer, and with it wrongly enabled in a
# radio-to-radio link TCK and TMS are held static, so no TAP state can change.
SIDEBANDS = (
    # pos  out net           in net            description
    (8,  'PRSNT',      'PRSNT',  'presence and link reset: 1k to +3V3 out, '
                                 '10k to GND in, so each end reads the other '
                                 'as present ONLY when it is powered'),
    (9,  None,         'TCK',    'JTAG TCK into CN1 - the mirrored output is '
                                 'deliberately absent so no radio can clock '
                                 "another radio's TAP"),
    (11, 'AUXIO0',     'AUXIO0', 'spare HL2 pin group, line 0 (DB1-10, FPGA '
                                 '90, CW/PTT ring)'),
    (12, 'AUXIO1',     'AUXIO1', 'spare HL2 pin group, line 1 (DB1-12, FPGA '
                                 '91, CW/PTT tip)'),
    (26, 'AUXIO2',     'AUXIO2', 'spare HL2 pin group, line 2 (DB1-16, FPGA '
                                 '103, I2C1 SCL)'),
    (27, 'AUXIO3',     'AUXIO3', 'spare HL2 pin group, line 3 (DB1-18, FPGA '
                                 '104, I2C1 SDA)'),
    (29, None,         'TMS',    'JTAG TMS into CN1 - mirrored output '
                                 'deliberately absent, same reason as TCK'),
    (30, 'TDO',        'TDI',    'JTAG TDO out of CN1 onto the cable; the '
                                 'input at the same position is TDI, which '
                                 'cannot do anything without TCK'),
)

AUXIO = (
    # idx  DB1 pin  FPGA pin  net at the header  what it REALLY is
    (0, 10, '90', 'HL2_CWR',
     'CW/PTT ring. 2.2k pull-up to +3V3 (R75), 100R to the KEY jack (R77) '
     'and 1 uF to ground (C71) on the radio, so its own time constant is '
     '2.2 ms - a DC/slow input, not a signalling pin'),
    (1, 12, '91', 'HL2_CWT',
     'CW/PTT tip. Same network: 2.2k (R76), 100R (R78), 1 uF (C72)'),
    (2, 16, '103', 'HL2_SCL1',
     'I2C1 SCL. 4.7k pull-up (R43) and it is a BUS: U6, the IDT 5P49V5923 '
     'VersaClock that generates the radio master clock, is on it'),
    (3, 18, '104', 'HL2_SDA1',
     'I2C1 SDA. 4.7k pull-up (R44), same bus as SCL1'),
)


def row(parts, y, x0, rot=0, gap=0.6):
    """Place an ordered list of parts left to right in one band, spacing them
    by their REAL courtyards so two of them cannot overlap however the part
    list changes.  Hand coordinates for eleven ICs is how the first rev D
    build collected 101 shorting-item DRC violations."""
    x = x0
    for p_ in parts:
        hw, hh = courtyard(p_.ptype, rot)
        x += hw
        p_.at = (round(x, 3), round(y, 3))
        p_.rot = rot
        x += hw + gap
    return x


def bridge():
    # THE M3 ANCHOR IS A NOTCH, NOT A HOLE.  HL2's MH2 sits at (73.00,
    # 137.00), i.e. local (3.00, 63.70), only 1.25 mm from this board's top
    # edge - and the top edge cannot move, because HL2_MECHANICAL_ENVELOPE.md
    # 2.5 puts the extrusion's internal clear width at HL2 y 41.75 to 138.25
    # and 138.25 is exactly local 64.95.  A 3.2 mm hole centred 1.25 mm from
    # an edge would break out of it by 0.35 mm.  So the screw passes through a
    # 3.4 mm U-notch open to the edge instead: the screw head and washer still
    # clamp the board down onto the 11.04 mm standoff, and with the connector
    # lying flat there is almost no tipping moment for it to resist anyway.
    NX0, NX1, NY = 3.00 - 1.70, 3.00 + 1.70, BOARD_H - 3.00
    OUT = [(0, 0), (BOARD_W, 0), (BOARD_W, BOARD_H), (NX1, BOARD_H),
           (NX1, NY), (NX0, NY), (NX0, BOARD_H), (0, BOARD_H)]
    b = Board('bridge',
              'Hermes Lite 2 SlimSAS bridge - one design, both ends, rev %s'
              % REV,
              OUT, (BOARD_W, BOARD_H),
              origin_note='local (0,0) = HL2 main board (70.00, 73.30)')
    ref = RefGen()
    cx0, cy0, cx1, cy1 = CUTOUT
    b.edge_extra += [(cx0, cy0, cx1, cy0), (cx1, cy0, cx1, cy1),
                     (cx1, cy1, cx0, cy1), (cx0, cy1, cx0, cy0)]

    # ==================================================== the HL2 headers
    b.add(Part('J2', 'SKT2x10', 'DB1 2x10 socket', {
        '1': 'HL2_AUXIO_EN', '2': 'HL2_ADC_D0', '3': 'HL2_ADC_D1',
        '4': 'HL2_JTAG_EN', '5': 'HL2_ADC_D2', '6': 'HL2_AUX_CLK_OUT',
        '7': 'VLVDS', '8': 'VLVDS',
        '9': 'HL2_FWD_CLK_RAW', '10': 'HL2_CWR',
        '11': 'HL2_TX_D0', '12': 'HL2_CWT',
        '13': 'GND', '14': 'GND',
        '15': 'HL2_TX_D1', '16': 'HL2_SCL1',
        '17': 'HL2_TX_D2', '18': 'HL2_SDA1',
        '19': 'DB1_3V3', '20': 'DB1_3V3',
    }, lcsc='', mfr='JXTCONN PM2.54-2X10P-H85 (LCSC C42431860) or any '
                    '2.54 mm 2x10 vertical female socket',
        desc='Mates HL2 DB1. HAND SOLDERED, bottom side',
        at=DB1_PIN1, rot=0, layer='B.Cu', mirror=True, dnp=True,
        note='NOT PLACED BY JLCPCB - hand soldered on the underside. DB1 is '
             'marked DNI in the HL2 BOM, so the male header on the radio may '
             'need soldering too. Pin 1 (FPGA 72) reaches the FPGA only '
             'through HL2 solder jumper J25 and is used here for a DC enable '
             'level only; if J25 is left open the AUXIO drive feature is '
             'simply unavailable and the board is unaffected.'))

    b.add(Part('J3', 'SKT2x03', 'DB12 2x03 socket', {
        '1': 'HL2_AUX_DAT_OUT', '2': 'HL2_AUX_DAT_IN', '3': 'GND',
        '4': 'GND', '5': 'HL2_AUX_CLK_IN', '6': 'HL2_REV_CLK',
    }, lcsc='', mfr='2.54 mm 2x3P female header, VERTICAL (top entry). LCSC '
                    'stocks no vertical 2x3 socket - buy a 2x4 and cut it '
                    'down, or source outside LCSC',
        desc='Mates HL2 DB12. HAND SOLDERED, bottom side',
        at=DB12_PIN1, rot=0, layer='B.Cu', mirror=True, dnp=True,
        note='NOT PLACED BY JLCPCB. NOTE THE ORDER: pin 5 = FPGA PIN_89 '
             '(auxiliary clock in) and pin 6 = FPGA PIN_88 (reverse clock '
             'in). rev A of PINMAP.md had these two transposed; '
             'check_netlist.py now asserts it. Also: HL2 R17, the optional '
             '100 R LVDS termination between DB12 pins 5 and 6, MUST NOT BE '
             'POPULATED - it shorts the two nets together through 100 R.'))

    # ================================================ the SlimSAS receptacle
    ss = {}
    for i in range(1, SS_NPOS + 1):
        ss['A%d' % i] = 'GND' if i in SS_GND else None
        ss['B%d' % i] = 'GND' if i in SS_GND else None
    for pos, onet, inet, _ in LANES:
        ss['A%d' % pos] = 'A_%s_P' % onet
        ss['A%d' % (pos + 1)] = 'A_%s_N' % onet
        ss['B%d' % pos] = 'B_%s_P' % inet
        ss['B%d' % (pos + 1)] = 'B_%s_N' % inet
    for pos, onet, inet, _ in SIDEBANDS:
        ss['A%d' % pos] = ('SB_%s_OUT' % onet) if onet else 'SB_NC%d' % pos
        ss['B%d' % pos] = 'SB_%s_IN' % inet
    for k in range(1, 5):
        ss['SH%d' % k] = 'SHELL'
    b.add(Part('J1', 'SLIMSAS', 'SlimSAS 8i 74P R/A', ss,
               lcsc=SLIMSAS_LCSC, mfr=SLIMSAS_MFR,
               desc='SlimSAS SFF-8654 8i, 74 position, right angle. 16 '
                    'differential pairs plus 16 sideband contacts. Row A is '
                    'driven by this board, row B is received; the cable '
                    'crosses A(n) to B(n), which is what lets ONE design sit '
                    'at both ends',
               at=SLIMSAS_AT, rot=0,
               note='Reflow the 74 SMD contacts, then solder the four 2.2 mm '
                    'through-hole shell tails. Mating face nominally 0.20 mm '
                    'behind the board edge - see the SLIMSAS comment block '
                    'for the one dimension no document gave and check it '
                    'before cutting the panel window. Insertion force 55.5 N '
                    'max, 250 mating cycles min.'))

    # ======================================= CN1 JTAG tap and pass-through
    # CN1 pinout confirmed from hardware/hl/hermeslite.net by taking every net
    # that touches CN1 and reading the other node on it: 1 TCK (U2 pin 16),
    # 2 GND, 3 TDO (U2 pin 20), 4 +3V3 (the programmer's VTREF sense), 5 TMS
    # (U2 pin 18), 6/7/8 unconnected (nCE/nCS/nCONFIG in Active Serial mode),
    # 9 TDI (U2 pin 15), 10 GND.  R2, R3 and R4 are 10 k PULL-UPS on TMS, TDI
    # and TCK - NOT series resistors, which an earlier note got wrong.
    cn1 = {'1': 'J_TCK', '2': 'GND', '3': 'J_TDO', '4': 'CN1_VTREF',
           '5': 'J_TMS', '6': 'CN1_NC6', '7': 'CN1_NC7', '8': 'CN1_NC8',
           '9': 'J_TDI', '10': 'GND'}
    b.add(Part('J4', 'SKT2x05', 'CN1 2x05 socket', dict(cn1),
               lcsc='', mfr='PM254V-12-10P-H85 (LCSC C492399) or any 2.54 mm '
                            '2x5 vertical female socket',
               desc='Mates HL2 CN1, the USB-Blaster JTAG header',
               at=CN1_PIN1, rot=0, layer='B.Cu', mirror=True, dnp=True,
               note='NOT PLACED BY JLCPCB - hand soldered on the underside. '
                    'THE TOLERANCE WARNING: this is the third rigid 2.54 mm '
                    'socket on one board, 54.19 mm from DB1, and '
                    'HL2_MECHANICAL_ENVELOPE.md 12.2 puts the worst-case '
                    'misalignment at CN1 relative to DB1 at about +/-0.8 mm '
                    'against the +/-0.35 mm a 2.54 mm socket takes '
                    'comfortably. If it will not engage, LEAVE J4 OFF and '
                    'run a flying 10-way IDC ribbon from CN1 to J5 instead - '
                    'J5 carries the same ten nets and needs no other change.'))
    b.add(Part('J5', 'HDR2x05', 'JTAG pass-through', dict(cn1),
               lcsc='', dnp=True,
               mfr='PZ254V-12-10P (LCSC C492422) 2.54 mm 2x5 '
                            'vertical male header, or DC3-2.54-10PAS (LCSC '
                            'C2977596) if a keyed boxed header is preferred',
               desc='Straight passive pass-through of all ten CN1 nets, so a '
                    'USB Blaster still plugs in locally with this board '
                    'fitted. Also the alternative CN1 connection: a flying '
                    '10-way IDC ribbon from CN1 to here replaces J4',
               at=(56.0, 24.5), rot=0,
               note='PURELY PASSIVE: socket straight through to header, ten '
                    'nets, no branches other than the four buffered taps. '
                    'Pins 6, 7 and 8 are left open - unconnected on the HL2 '
                    'today but nCE/nCS/nCONFIG in Active Serial mode. DO NOT '
                    'draw supply current from pin 4: it is the programmer '
                    "VTREF sense line and expects microamps. This board's "
                    'power comes from DB1 pins 19/20.'))

    # ============================================ 2.5 V -> 3.3 V translators
    # The HL2 drives these pins from a 2.5 V bank (Vlvds, FPGA pin 81 through
    # FB28, present on DB1 pins 7/8) whose guaranteed VOH is 2.0 V - exactly
    # the VIH minimum that EVERY discrete LVDS driver in the catalogue
    # specifies, i.e. ZERO guaranteed margin.  One SN74AVC4T245 with VCCA at
    # 2.5 V has a VIH of 0.65 x VCCA = 1.63 V, so the same 2.0 V output now
    # has 370 mV of guaranteed margin.  DESIGN_NOTES.md section 4.
    def x4(a_nets, b_nets, vcca, vccb, dir1, dir2, oe1, oe2):
        d = {'1': vcca, '16': vccb, '8': 'GND', '9': 'GND',
             '2': dir1, '3': dir2, '15': oe1, '14': oe2}
        for k in range(4):
            d[X4_A[k + 1]] = a_nets[k]
            d[X4_B[k + 1]] = b_nets[k]
        return d

    b.add(Part('U1', 'XLAT4', 'SN74AVC4T245PW',
               x4(['HL2_FWD_CLK', 'HL2_ADC_D0', 'HL2_ADC_D1', 'HL2_ADC_D2'],
                  ['DI_FWDCLK', 'DI_ADCD0', 'DI_ADCD1', 'DI_ADCD2'],
                  '+2V5', '+3V3', '+2V5', '+2V5', 'GND', 'GND'),
               lcsc=LC_X4, mfr='SN74AVC4T245PWR',
               desc='4-bit dual-supply translator, VCCA 2.5 V / VCCB 3.3 V. '
                    'THE FORWARD GROUP: the 153.6 MHz forward clock and ADC '
                    'data lanes 0, 1 and 2 - exactly four signals in exactly '
                    'one package, so the clock cannot lead its data by the '
                    '1.1 to 3.7 ns part-to-part propagation delay. Within one '
                    'package they share a channel-to-channel skew instead',
               at=None,
               note='Both DIR tied to VCCA (A->B), both OE* to GND - always '
                    'enabled. The forward clock arrives on FPGA pin 98, which '
                    'is a 3.3 V bank pin, so it comes through the R1/R2 '
                    'divider first: the A-side absolute maximum is VCCA+0.5 = '
                    '3.0 V and 3.3 V direct would be out of spec.'))
    b.add(Part('U2', 'XLAT4', 'SN74AVC4T245PW',
               x4(['HL2_AUX_CLK_OUT', 'HL2_AUX_DAT_OUT',
                   'HL2_JTAG_EN', 'HL2_AUXIO_EN'],
                  ['DI_AUXCLK', 'DI_AUXDAT', 'JTAG_EN_N', 'AUXIO_EN_N'],
                  '+2V5', '+3V3', '+2V5', '+2V5', 'GND', 'GND'),
               lcsc=LC_X4, mfr='SN74AVC4T245PWR',
               desc='4-bit dual-supply translator, VCCA 2.5 V / VCCB 3.3 V. '
                    'Port 1 is the auxiliary transmit pair - clock and data '
                    'in one port so they share a skew. Port 2 carries the two '
                    'ENABLE LEVELS the gateware controls: JTAG over the cable '
                    'and the AUXIO drive direction, both active LOW, both DC',
               at=None,
               note='Both DIR to VCCA (A->B), both OE* to GND. The two enable '
                    'channels are static levels, not signals. Each enable is '
                    'pulled UP at BOTH ends - to +2V5 on the HL2 side and to '
                    '+3V3 on the logic side - so a missing part, an '
                    'unpowered part, an unconfigured FPGA or an open HL2 '
                    'jumper J25 all leave the feature DISABLED.'))

    # ============================================ 3.3 V -> 2.5 V translator
    # HL2 PIN_88 (DB12-6) and PIN_89 (DB12-5) are dedicated INPUT-ONLY pins in
    # a 2.5 V bank with the PCI clamp diode on by default, so a 3.3 V driver
    # held high would inject DC into the radio's 2.5 V rail.  PIN_87 (DB12-2)
    # is in the same bank.  All three get 2.5 V CMOS.
    b.add(Part('U3', 'XLAT4', 'SN74AVC4T245PW',
               x4(['RX_REVCLK', 'RX_DUPCLK', 'RX_AUXCLK', 'RX_AUXDAT'],
                  ['X_REVCLK25', 'X_DUPCLK25', 'X_AUXCLK25', 'X_AUXDAT25'],
                  '+3V3', '+2V5', '+3V3', '+3V3', 'GND', 'GND'),
               lcsc=LC_X4, mfr='SN74AVC4T245PWR',
               desc='4-bit dual-supply translator, VCCA 3.3 V / VCCB 2.5 V. '
                    'Port 1 carries the two candidate reverse clocks - the '
                    'primary and the duplicate - so whichever is selected has '
                    'the same delay. Port 2 carries the auxiliary receive '
                    'pair, clock and data together',
               at=None,
               note='Both DIR to VCCA (A->B), both OE* to GND. The duplicate '
                    'clock output goes nowhere unless R_CLKSEL_B is fitted '
                    'and R_CLKSEL_A removed; driving an open pad is harmless.'))

    # ==================================================== LVDS drivers
    # Eight driven channels, so two quad packages, and the split is not
    # arbitrary.  U4 carries the forward clock and its three data lanes
    # together, for the same reason U1 does: they travel down one cable
    # against one forwarded clock and their skew has to match.  That fills U4.
    #
    # THE DUPLICATE FORWARD CLOCK THEREFORE GOES IN U5, NOT U4.  The brief
    # asked for it on a spare channel of the same driver chip; a quad driver
    # has four channels and the forward group already needs all four, so the
    # request cannot be met as written without splitting the group that must
    # not be split.  U5's channel costs the same one trace, and it also
    # survives a dead U4, so the redundancy is strictly wider.  What it gives
    # up is skew matching to the data - which does not matter, because the
    # duplicate exists to cover a dead trace, contact or solder joint on the
    # primary clock lane, and the far end re-centres whichever lane it trains
    # on with its own input delay.
    drv = [
        ('U4', None, [('FWDCLK', 'DI_FWDCLK'), ('ADCD0', 'DI_ADCD0'),
                              ('ADCD1', 'DI_ADCD1'), ('ADCD2', 'DI_ADCD2')],
         'THE FORWARD GROUP: 153.6 MHz forward clock plus ADC data lanes 0, 1 '
         'and 2 at 307.2 Mbit/s each. Three lanes DDR at 153.6 MHz is '
         '921.6 Mbit/s, the complete raw 12-bit 76.8 MSPS stream. All four '
         'channels used, none spare'),
        ('U5', None, [('DUPCLK', 'DI_FWDCLK'), ('AUXCLK', 'DI_AUXCLK'),
                              ('AUXDAT', 'DI_AUXDAT'), ('SPARE', 'DI_SPARE')],
         'Channel 1 is the DUPLICATE forward clock, fed from the same '
         'translated net as the primary: the forward clock is the single '
         'point of failure for the whole receive path, the far end has spare '
         'pins and trains whichever lane works, and this costs one trace. '
         'Channels 2 and 3 are the auxiliary transmit pair, channel 4 is a '
         'spare brought out to test pads'),
    ]
    for ref_u, at, chmap, desc in drv:
        pins = {'1': 'DRV_EN', '4': '+3V3', '5': 'GND', '8': 'GND'}
        for i, (lane, src) in enumerate(chmap):
            pins[DRV_IN[i]] = src
            pins[DRV_P[i]] = 'A_%s_P' % lane
            pins[DRV_N[i]] = 'A_%s_N' % lane
        b.add(Part(ref_u, 'LVDS_DRV', 'DS90LV047A', pins, lcsc=LC_DRV,
                   mfr='DS90LV047ATMX/NOPB',
                   desc='Quad LVDS driver, 400 Mbps, SOIC-16. ' + desc,
                   at=at, rot=0,
                   note='EN = DRV_EN, EN* = GND. DRV_EN is tied to +3V3 '
                        'through the fitted link R_DRVEN_ON, so the drivers '
                        'are always on. Move the link to R_DRVEN_PRSNT to '
                        'gate them on the far end being present and powered '
                        'instead, which saves about 60 mA with no cable - but '
                        'only if your cable actually wires the sidebands, '
                        'because the no-sideband cable variant exists and '
                        'would leave the link dead.'))

    # ==================================================== LVDS receivers
    rcv = [
        ('U6', None, [('REVCLK', 'RX_REVCLK'), ('TXD0', 'RX_TXD0'),
                              ('TXD1', 'RX_TXD1'), ('TXD2', 'RX_TXD2')],
         'The reverse group: reverse clock plus transmit data lanes 0, 1 and '
         '2 at 307.2 Mbit/s, received simultaneously with the forward group. '
         'All four channels used'),
        ('U7', None, [('DUPCLK', 'RX_DUPCLK'), ('AUXCLK', 'RX_AUXCLK'),
                              ('AUXDAT', 'RX_AUXDAT'), ('SPARE', 'RX_SPARE')],
         "Channel 1 receives the far end's DUPLICATE forward clock, which is "
         'what makes the duplicate symmetric: fit R_CLKSEL_B instead of '
         'R_CLKSEL_A and FPGA pin 88 is fed from this channel instead. '
         'Channels 2 and 3 are the auxiliary receive pair, channel 4 a spare'),
    ]
    for ref_u, at, chmap, desc in rcv:
        pins = {'16': '+3V3', '9': 'GND', '12': 'GND', '13': '+3V3'}
        for i, (lane, dst) in enumerate(chmap):
            pins[RCV_P[i]] = 'B_%s_P' % lane
            pins[RCV_N[i]] = 'B_%s_N' % lane
            pins[RCV_OUT[i]] = dst
        b.add(Part(ref_u, 'LVDS_RCV', 'DS90LV048A', pins, lcsc=LC_RCV,
                   mfr='DS90LV048ATMTCX/NOPB',
                   desc='Quad LVDS receiver, 400 Mbps, TSSOP-16. ' + desc,
                   at=at, rot=0,
                   note='EN tied to +3V3 and EN* to GND: always enabled. A '
                        'receiver input is high impedance, so there is '
                        'nothing to gate.'))

    # ============================== the spare HL2 pin group (AUXIO), and why
    # This is the group the brief calls "the four HL2 indicator LED pins".
    # THEY ARE NOT THE LED PINS.  Read out of hardware/hl/hermeslite.net: the
    # four front-panel LEDs D2-D5 hang on FPGA pins 98, 99, 100 and 101
    # (DB1-9, 11, 15, 17), each through a 1 k resistor R71-R74 to +3V3 - and
    # rev D's link already owns all four of those pins, so the LEDs now blink
    # with link traffic whether anyone wants them to or not, and there is
    # nothing left to tap.  What pins 90, 91, 103 and 104 actually are is in
    # the AUXIO table above: two CW/PTT inputs with a 1 uF capacitor and a
    # 2.2 k pull-up each, and the I2C1 bus that the radio's own FPGA uses to
    # program the VersaClock chip that makes its master clock.
    #
    # The mechanism the brief asked for is built anyway, on those four pins,
    # because a buffered bidirectional tap on them is genuinely useful: it
    # gives the far end remote keying and remote access to the clock
    # generator.  But it is built as TWO ONE-WAY PATHS, not as one
    # bidirectional translator, and that is a deliberate improvement:
    #
    #   READ  path  HL2 pin -> 330 R -> buffer INPUT -> sideband out.  Always
    #               on.  A buffer input is high impedance, so this path
    #               physically cannot drive an HL2 pin.  This is the default
    #               and the zero-risk state.
    #   DRIVE path  sideband in -> buffer OUTPUT -> 330 R -> HL2 pin.  Gated
    #               by AUXIO_EN_N, which is pulled UP at both ends and so is
    #               DISABLED with no gateware, no far end, an unprogrammed
    #               FPGA, an open HL2 jumper J25 or a missing translator.
    #
    # There is no direction net and no inverter, so there is no "both halves
    # disagree" state to analyse - which is the safety property rev C bought
    # with a MOSFET inverter and a one-shunt strap, obtained here for free by
    # not having a direction at all.
    #
    # CONTENTION CURRENT.  If someone loads stock HL2 gateware, which drives
    # pins 90/91 as inputs but could drive 103/104 as an I2C master, while the
    # DRIVE path is enabled, the two outputs fight through ONE 330 R.  A
    # SN74AVC4T245 at 3.3 V specifies VOL 0.7 V at 12 mA and VOH 2.3 V at
    # -12 mA, i.e. about 58 R and 83 R of effective source impedance; a
    # Cyclone IV 3.3-V LVTTL pin at its 8 mA setting is about 56 R.  Worst
    # case 3.3 / (58 + 330 + 56) = 7.4 mA, and on datasheet-typical
    # impedances about 6.6 mA.  The Cyclone IV absolute maximum is 25 mA sink
    # and 40 mA source per pin (Cyclone IV Device Datasheet CYIV-53001-1.8
    # Table 1-1), so that is a factor of 3.4 of margin on the tighter limit.
    # 100 R would have given 3.3 / (58 + 100 + 56) = 15.4 mA, which is inside
    # the limit but with only 1.6x of margin; 330 R costs nothing on lines
    # whose own time constant is 2.2 ms and whose fastest possible use is
    # 400 kHz I2C.
    auxio_rd, auxio_wr = [], []
    for idx, db1pin, fpga, hnet, what in AUXIO:
        auxio_rd.append(('AUXIO%d_T' % idx, 'SB_AUXIO%d_OUT' % idx))
        auxio_wr.append(('SB_AUXIO%d_IN' % idx, 'AUXIO%d_T' % idx))
        b.add(R(ref('R'), '330R', hnet, 'AUXIO%d_T' % idx, lcsc=LC['r330'],
                desc='AUXIO line %d series resistor, DB1-%d = FPGA pin %s. '
                     'Limits contention to 7.4 mA worst case if the radio '
                     'drives this pin while the DRIVE path is enabled. %s'
                     % (idx, db1pin, fpga, what)))
    b.add(Part('U8', 'XLAT4', 'SN74AVC4T245PW',
               x4([a for a, _ in auxio_rd[:2]] + [a for a, _ in auxio_rd[2:]],
                  [c for _, c in auxio_rd[:2]] + [c for _, c in auxio_rd[2:]],
                  '+3V3', '+3V3', 'GND', 'GND', 'GND', 'GND'),
               lcsc=LC_X4, mfr='SN74AVC4T245PWR',
               desc='AUXIO READ path, all four lines. Both rails 3.3 V, both '
                    'DIR LOW so the direction is B->A: the HL2 side is a '
                    'high-impedance input and the cable side is the output. '
                    'ALWAYS ON, and physically incapable of driving an HL2 '
                    'pin',
               at=None,
               note='DIR = GND on both ports, OE* = GND on both ports. This '
                    'is the default and only path that is live without '
                    'gateware.'))
    b.add(Part('U9', 'XLAT4', 'SN74AVC4T245PW',
               x4([a for a, _ in auxio_wr], [c for _, c in auxio_wr],
                  '+3V3', '+3V3', '+3V3', '+3V3', 'AUXIO_EN_N', 'AUXIO_EN_N'),
               lcsc=LC_X4, mfr='SN74AVC4T245PWR',
               desc='AUXIO DRIVE path, all four lines. Both rails 3.3 V, both '
                    'DIR HIGH so the direction is A->B: the cable drives the '
                    'HL2 pins. Both ports gated by AUXIO_EN_N, which is '
                    'pulled up and therefore DISABLED at power-up',
               at=None,
               note='DIR = +3V3 both ports, OE* = AUXIO_EN_N both ports. The '
                    'gateware must tri-state FPGA pins 90, 91, 103 and 104 '
                    'BEFORE asserting the enable - that is a software '
                    'interlock, and the 330 R series resistors are what make '
                    'getting it wrong survivable rather than fatal. Be aware '
                    'that lines 2 and 3 are the I2C bus to the VersaClock '
                    'that generates the radio master clock.'))

    # =================================================== JTAG over the cable
    # THE ANSWER TO "SERIES RESISTORS OR A BUFFER": BOTH, and the buffer is
    # the part that matters.  Series resistors alone bound the current in a
    # fight but leave the logic level undefined, and an undefined TCK is
    # exactly the thing that can walk the TAP controller into an arbitrary
    # state or corrupt a configuration in progress.  A gated buffer makes
    # "the cable cannot touch CN1" a property of the hardware:
    #
    #   TCK, TMS, TDI   cable -> gated buffer -> 330 R -> CN1.  OE* =
    #                   JTAG_EN_N, pulled up at both ends, so DISABLED with no
    #                   gateware and with nothing plugged in.  A USB Blaster
    #                   in the local pass-through therefore never meets
    #                   anything but a tri-stated output.
    #   TDO             CN1 -> 330 R -> buffer INPUT -> cable.  Always on, and
    #                   a buffer input is high impedance, so reading TDO
    #                   cannot fight the FPGA that drives it and cannot load
    #                   it with the cable either.
    #
    # Radio to radio, with the feature disabled: all three of the far radio's
    # TCK, TMS and TDI see a tri-stated buffer output behind 330 R, so CN1
    # sees nothing but its own 10 k pull-ups (HL2 R2/R3/R4), and TDO is read
    # by a high-impedance input.  Neither radio can disturb the other's
    # programming pins.  With the feature WRONGLY enabled radio to radio it is
    # still safe, because this board never drives the sideband positions whose
    # far-end inputs are TCK and TMS: both arrive held static by their pull
    # resistors, and a JTAG TAP with no TCK edge cannot change state at all.
    b.add(R(ref('R'), '330R', 'SB_TCK_IN_B', 'J_TCK', lcsc=LC['r330'],
            desc='JTAG TCK series resistor, buffer output into CN1 pin 1. '
                 'Bounds a fight with a locally plugged USB Blaster to about '
                 '8 mA, and 330 R into the 15 pF of CN1 plus trace is 5 ns '
                 'against the 41.7 ns period of a 24 MHz TCK'))
    b.add(R(ref('R'), '330R', 'SB_TMS_IN_B', 'J_TMS', lcsc=LC['r330'],
            desc='JTAG TMS series resistor, buffer output into CN1 pin 5'))
    b.add(R(ref('R'), '330R', 'SB_TDI_IN_B', 'J_TDI', lcsc=LC['r330'],
            desc='JTAG TDI series resistor, buffer output into CN1 pin 9'))
    b.add(R(ref('R'), '330R', 'J_TDO', 'J_TDO_T', lcsc=LC['r330'],
            desc='JTAG TDO series resistor, CN1 pin 3 into a buffer input. '
                 'Isolates the HL2 FPGA TDO pin from the cable entirely'))
    b.add(Part('U10', 'XLAT4', 'SN74AVC4T245PW',
               x4(['J_TDO_T', 'GND', 'SB_TCK_IN', 'SB_TMS_IN'],
                  ['SB_TDO_OUT', 'J_SPARE1', 'SB_TCK_IN_B', 'SB_TMS_IN_B'],
                  '+3V3', '+3V3', 'GND', '+3V3', 'GND', 'JTAG_EN_N'),
               lcsc=LC_X4, mfr='SN74AVC4T245PWR',
               desc='JTAG buffers, part 1. Port 1 is B->A and ALWAYS ON: it '
                    'reads TDO out of CN1 and drives it onto the cable. Port '
                    '2 is A->B and GATED by JTAG_EN_N: TCK and TMS from the '
                    'cable into CN1',
               at=None,
               note='Port 1: 1DIR = GND (B->A), 1OE* = GND. Port 2: 2DIR = '
                    '+3V3 (A->B), 2OE* = JTAG_EN_N. Reading TDO is '
                    'unconditional and harmless; driving TCK and TMS is not, '
                    'and is off until the gateware says otherwise.'))
    b.add(Part('U11', 'XLAT4', 'SN74AVC4T245PW',
               x4(['SB_TDI_IN', 'GND', 'GND', 'GND'],
                  ['SB_TDI_IN_B', 'J_SPARE2', 'J_SPARE3', 'J_SPARE4'],
                  '+3V3', '+3V3', '+3V3', '+3V3', 'JTAG_EN_N', '+3V3'),
               lcsc=LC_X4, mfr='SN74AVC4T245PWR',
               desc='JTAG buffers, part 2. Port 1 channel 1 is TDI from the '
                    'cable into CN1, gated by the same JTAG_EN_N. The other '
                    'three channels are spare',
               at=None,
               note='Port 1: 2 channels, DIR = +3V3 (A->B), OE* = JTAG_EN_N; '
                    'only channel 1 is used and channel 2 has its input '
                    'grounded. Port 2 is disabled (2OE* to +3V3) with both '
                    'inputs grounded and both outputs on test pads. Three '
                    'spare gated 3.3 V channels are available here if a '
                    'future revision needs them.'))

    # ==================================================== power
    # WHICH RAIL, AND WHY NOT Vlvds.  The board takes 3.3 V from DB1 pins
    # 19/20 and makes its own 2.5 V from it.  The HL2's +3V3 comes from U3, an
    # ST1S10PHR buck rated 3 A through a 2.4 A inductor (L1, SRR4528A-3R3Y),
    # with the designer's own annotation "<=1.5A" beside it on Power.sch and an
    # estimated 450 mA of existing load, so there is about 1 A spare and this
    # board's 300 mA is a third of it.  The 2.5 V rail is a different story:
    # Vlvds on DB1 pins 7/8 comes through ferrite FB28 from U17, a TPS73025
    # LDO in SOT-23-5 rated 200 mA TOTAL, which already feeds the Ethernet
    # PHY's RGMII I/O supply, four Cyclone IV PLL supplies and the FPGA's own
    # bank 5 VCCIO, and whose designer's note says "150 mA sufficient for all
    # 2.5V use".  Perhaps 50 mA is genuinely spare and that figure is a
    # bottom-up estimate, not a measurement - and the thing it would brown out
    # is VCCIO5, the bank that carries the ADC data this board exists to read.
    # So the on-board LDO is FITTED and Vlvds is the option, not the reverse.
    b.add(Part('U12', 'LDO25', 'ME6211C25M5G', {
        '1': '+3V3', '2': 'GND', '3': '+3V3', '5': '+2V5',
    }, lcsc=LC_LDO25, mfr='ME6211C25M5G-N',
        desc='2.5 V 400 mA LDO, the 2.5 V side of U1, U2 and U3 only. '
             'Computed load 50 mA, so 8x of headroom and 40 mW of dissipation',
        at=None,
        note='Output tolerance +/-2%, so VCCA worst case 2.55 V and the '
             'translator VIH worst case 0.65 x 2.55 = 1.66 V against the '
             "HL2's guaranteed 2.0 V VOH: 340 mV of margin. Enable is tied "
             'to the input. If you would rather the thresholds tracked the '
             "FPGA's own bank supply exactly, fit SL_VLVDS and FB2 and remove "
             'U12 - but read the note on SL_VLVDS first.'))

    b.add(Part('FB1', 'FB', '120R/2A', {'1': 'DB1_3V3', '2': '+3V3'},
               lcsc=LC['fb'], mfr='BLM18PG121SN1D',
               desc='Input filter on the 3.3 V the board takes from DB1 pins '
                    '19/20. 120 ohm at 100 MHz, 2 A, 50 mOhm, so 15 mV of '
                    'drop at 300 mA. Keeps this board\'s switching currents '
                    'out of the radio\'s 3.3 V rail, which has no bead, '
                    'resistor, fuse or TVS of its own between the regulator '
                    'and the header',
               at=None,
               note='JLCPCB Basic. The only Basic bead that combines >=1 A '
                    'with <=150 mOhm; no Basic bead reaches 600 ohm at that '
                    'current, and 120 ohm is ample for a rail filter.'))
    b.add(Part('FB2', 'FB', '120R/2A', {'1': 'VLVDS', '2': 'VLVDS_F'},
               lcsc=LC['fb'], mfr='BLM18PG121SN1D', dnp=True,
               desc='Input filter for the OPTIONAL Vlvds tap',
               at=None,
               note='NOT FITTED. Only fit together with SL_VLVDS and only '
                    'with U12 removed.'))

    # ==================================================== resistors & links
    rs = []
    # The forward clock divider.  FPGA pin 98 is a 3.3 V bank output and the
    # translator's A-side absolute maximum is VCCA + 0.5 V = 3.0 V, so it
    # cannot be connected directly.  100 R + 470 R, both JLCPCB Basic:
    #   high level        3.3 x 470/(470+100+50)   = 2.50 V   (3.465 V rail
    #                     and 2.45 V VCCA worst case: 2.63 V against a
    #                     2.95 V absolute maximum, 320 mV of headroom)
    #   margin over VIH   2.50 - 1.63              = 870 mV
    #   current from 98   3.3 / 570                = 5.8 mA, so set pin 98 to
    #                     its 8 mA drive strength in Quartus
    #   Thevenin          100 || 470 + 50          = 132 ohm -> 0.53 ns into
    #                     the translator's ~4 pF
    #   low level with the HL2 FPGA unconfigured: pin 98 carries LED D2 and
    #                     R71, 1 k to +3V3, so it sits at 1.4 V behind 1 k;
    #                     1.4 x 470/(1000+100+470) = 0.42 V against the
    #                     0.875 V VIL limit
    # rev C used 100 R + 660 R as two 330 R because 470 R was not then a
    # Basic part in JLCPCB's library.  It is now (C25117), so this is one
    # resistor instead of two with better margin at every corner.
    rs.append(R('R1', '100R', 'HL2_FWD_CLK_RAW', 'HL2_FWD_CLK',
                lcsc=LC['r100'],
                desc='Forward clock divider, series leg. 3.3 V FPGA pin 98 '
                     'down to 2.50 V for the translator A-side input'))
    rs.append(R('R2', '470R', 'HL2_FWD_CLK', 'GND', lcsc=LC['r470'],
                desc='Forward clock divider, shunt leg. 5.8 mA from pin 98, '
                     'Thevenin 132 ohm, 320 mV under the 3.0 V A-side '
                     'absolute maximum at the worst corner'))
    # Pull-downs so every 2.5 V-bank net into U1/U2 is DEFINED while nothing
    # drives it - the HL2 FPGA unconfigured, or simply absent.  The forward
    # clock deliberately does NOT get one: its own LED pull-up plus the
    # divider already define it at 0.42 V, and adding 10 k would park the node
    # in the translator's forbidden band between VIL 0.875 V and VIH 1.63 V.
    for net, why in (('HL2_ADC_D0', 'ADC data 0'), ('HL2_ADC_D1', 'ADC data 1'),
                     ('HL2_ADC_D2', 'ADC data 2'),
                     ('HL2_AUX_CLK_OUT', 'auxiliary clock out'),
                     ('HL2_AUX_DAT_OUT', 'auxiliary data out')):
        rs.append(R(ref('R'), '10k', net, 'GND', lcsc=LC['r10k'],
                    desc='Defines %s (%s) while nothing drives it'
                         % (net, why)))
    # THE TWO ENABLE LEVELS, and the four pull resistors that make an
    # unprogrammed board safe.  Each enable is active LOW and is pulled UP
    # twice: on the HL2 side to +2V5, so an unconfigured FPGA (whose user I/O
    # carry a ~25 k weak pull-up during configuration anyway), an absent radio
    # or an open HL2 solder jumper J25 all read HIGH; and on the logic side to
    # +3V3, so a missing, unpowered or dead translator also reads HIGH.  HIGH
    # is OE* high is DISABLED.  There is no level and no failure that enables
    # a feature.
    rs.append(R(ref('R'), '10k', 'HL2_JTAG_EN', '+2V5', lcsc=LC['r10k'],
                desc='JTAG-over-cable enable, HL2 side pull-UP. FPGA pin 80 '
                     '(DB1-4) drives this LOW to enable. The direction '
                     'matters: pulled up means disabled'))
    rs.append(R(ref('R'), '10k', 'JTAG_EN_N', '+3V3', lcsc=LC['r10k'],
                desc='JTAG-over-cable enable, logic side pull-UP. A missing '
                     'or unpowered U2 leaves the JTAG buffers tri-stated'))
    rs.append(R(ref('R'), '10k', 'HL2_AUXIO_EN', '+2V5', lcsc=LC['r10k'],
                desc='AUXIO drive enable, HL2 side pull-UP. FPGA pin 72 '
                     '(DB1-1, through HL2 jumper J25) drives this LOW to '
                     'enable. With J25 open the feature is simply unavailable'))
    rs.append(R(ref('R'), '10k', 'AUXIO_EN_N', '+3V3', lcsc=LC['r10k'],
                desc='AUXIO drive enable, logic side pull-UP. READ-ONLY is '
                     'the power-up state and the failure state'))
    rs.append(R(ref('R'), '1k', 'HL2_JTAG_EN', 'GND', lcsc=LC['r1k'],
                dnp=True,
                desc='JTAG_FORCE: fit to enable JTAG over the cable WITHOUT '
                     'working HL2 gateware, which is the case you most want '
                     'it in. 1 k beats the 10 k pull-up (0.23 V) and costs '
                     'the FPGA only 2.5 mA if the gateware drives the pin '
                     'high anyway',
                note='NOT FITTED. This is the recovery path for a radio whose '
                     'gateware will not run: without it, remote reflashing '
                     'depends on the gateware you are trying to replace.'))
    # The reverse-clock select: exactly one of these two is fitted.
    rs.append(R('R_CLKSEL_A', '0R', 'X_REVCLK25', 'HL2_REV_CLK',
                lcsc=LC['r0'],
                desc='Reverse clock into FPGA pin 88 from the PRIMARY clock '
                     'lane. FITTED by default'))
    rs.append(R('R_CLKSEL_B', '0R', 'X_DUPCLK25', 'HL2_REV_CLK',
                lcsc=LC['r0'], dnp=True,
                desc='Reverse clock into FPGA pin 88 from the DUPLICATE clock '
                     'lane instead',
                note='NOT FITTED. FIT EXACTLY ONE OF R_CLKSEL_A AND '
                     'R_CLKSEL_B. This is the hardware half of the duplicate '
                     'clock: if the primary clock lane loses a trace, a '
                     'contact or a solder joint, move the link.'))
    for a, c, why in (('X_AUXCLK25', 'HL2_AUX_CLK_IN',
                       'auxiliary clock (2.5 V) into HL2 pin 89 = DB12-5'),
                      ('X_AUXDAT25', 'HL2_AUX_DAT_IN',
                       'auxiliary data (2.5 V) into HL2 pin 87 = DB12-2')):
        rs.append(R(ref('R'), '0R', a, c, lcsc=LC['r0'], desc=why))
    # The three transmit data lanes into the HL2's 3.3 V bank.  These are the
    # LED pins: each carries an LED and a 1 k resistor to +3V3, so the
    # receiver output has to SINK about (3.3 - 1.9) / 1000 = 1.4 mA when low.
    # DS90LV048A specifies VOL 0.25 V max at IOL = 2 mA, so it is inside spec
    # with the LED lit.  What loads the edge is the FPGA pin (about 7 pF) plus
    # the header and trace, not the LED: the LED's junction capacitance is in
    # SERIES with the 1 k, so at 150 MHz the branch is resistive.
    for i in range(3):
        rs.append(R(ref('R'), '0R', 'RX_TXD%d' % i, 'HL2_TX_D%d' % i,
                    lcsc=LC['r0'],
                    desc='Transmit data lane %d into DB1-%d (FPGA pin %d, a '
                         '3.3 V bank pin carrying LED D%d through 1 k). 0402 '
                         'pads take 22 R instead if damping is ever wanted'
                         % (i, (11, 15, 17)[i], (99, 100, 101)[i], i + 3)))
    # Sideband terminations and pulls.
    rs.append(R(ref('R'), '1k', 'SB_PRSNT_OUT', '+3V3', lcsc=LC['r1k'],
                desc='Presence assert: 1 k to +3V3, so the far end reads this '
                     'board as present ONLY while it is powered. Against the '
                     'far 10 k it gives 3.0 V at 0.3 mA'))
    rs.append(R(ref('R'), '10k', 'SB_PRSNT_IN', 'GND', lcsc=LC['r10k'],
                desc='Presence detect: HIGH = the far end is plugged in AND '
                     'powered. Also the link-reset input - the far end pulls '
                     'it low'))
    rs.append(R(ref('R'), '10k', 'SB_TCK_IN', 'GND', lcsc=LC['r10k'],
                desc='JTAG TCK from the cable, pulled LOW so the buffer input '
                     'is defined and TCK idles low with nothing plugged in'))
    rs.append(R(ref('R'), '10k', 'SB_TMS_IN', '+3V3', lcsc=LC['r10k'],
                desc='JTAG TMS from the cable, pulled HIGH - the direction '
                     'that walks a TAP controller to Test-Logic-Reset rather '
                     'than into it'))
    rs.append(R(ref('R'), '10k', 'SB_TDI_IN', 'GND', lcsc=LC['r10k'],
                desc='JTAG TDI from the cable, pulled low so the buffer input '
                     'is defined'))
    for idx, _, _, _, _ in AUXIO:
        rs.append(R(ref('R'), '10k', 'SB_AUXIO%d_IN' % idx, 'GND',
                    lcsc=LC['r10k'],
                    desc='AUXIO line %d from the cable, pulled low so the '
                         'DRIVE buffer input is defined with no cable' % idx))
    rs.append(R(ref('R'), '10k', 'DI_SPARE', 'GND', lcsc=LC['r10k'],
                desc='Defines the spare driver channel input'))
    # 100 ohm differential terminations on the eight RECEIVED pairs.  There is
    # no termination at a driver output, which is correct for LVDS.
    for pos, onet, inet, why in LANES:
        rs.append(R(ref('R'), '100R', 'B_%s_P' % inet, 'B_%s_N' % inet,
                    lcsc=LC['r100'],
                    desc='100 ohm differential termination on the received '
                         '%s pair (connector B%d/B%d). PLACE WITHIN 5 mm OF '
                         'THE RECEIVER PINS' % (inet, pos, pos + 1)))
    # Driver-enable strapping, and the shield.
    rs.append(R('R_DRVEN_ON', '0R', 'DRV_EN', '+3V3', lcsc=LC['r0'],
                desc='LVDS drivers always enabled. FITTED by default'))
    rs.append(R('R_DRVEN_PRSNT', '0R', 'DRV_EN', 'SB_PRSNT_IN',
                lcsc=LC['r0'], dnp=True,
                desc='LVDS drivers enabled only while the far end is present '
                     'and powered',
                note='NOT FITTED. FIT AT MOST ONE OF R_DRVEN_ON AND '
                     'R_DRVEN_PRSNT. Saves about 60 mA with no cable, but '
                     'depends on the cable wiring its sidebands - and 10Gtek '
                     'sell a no-sideband variant that would leave the link '
                     'dead with no clue why.'))
    rs.append(R0805('R_SHELL', '0R', 'SHELL', 'GND', lcsc=LC['r0_0805'],
                    desc='Connector shell and its four through-hole tails to '
                         'board ground. 0805 so the shield can be lifted if a '
                         'ground loop ever appears'))
    rs.append(R('SL_VLVDS', '0R', 'VLVDS_F', '+2V5', lcsc=LC['r0'], dnp=True,
                desc='Reference the translators\' 2.5 V side to the radio\'s '
                     'own Vlvds rail (DB1 pins 7/8) instead of U12',
                note='NOT FITTED, and think before you do. Electrically ideal '
                     '- the thresholds then track the FPGA bank supply '
                     'exactly - but it draws this board\'s 50 mA from a '
                     '200 mA TPS73025 that already carries the Ethernet PHY '
                     'RGMII I/O supply, four PLL supplies and VCCIO5 itself, '
                     'with maybe 50 mA genuinely spare. Do not fit together '
                     'with U12. Fit FB2 as well if you do.'))
    b.add(*rs)

    # ==================================================== ESD, every line
    # DECISION: every conductor that leaves the enclosure is protected, with
    # low-capacitance arrays, on the connector side of everything else.  That
    # is 32 pair conductors plus all 16 sideband conductors = 48, in twelve
    # 4-channel arrays.
    #
    # TPD4E05U06DQAR, LCSC C138714: 0.5 pF per channel, 5.5 V standoff,
    # unidirectional, USON-10 2.5 x 1.0 mm, 45,345 in stock, $0.0698 at qty
    # 10, JLCPCB Extended.  0.5 pF against a 100 ohm differential pair is
    # 0.5 pF x 50 ohm = 25 ps of added rise time on a 3.26 ns unit interval,
    # i.e. electrically free.
    #
    # Why not something cheaper: no ESD array of ANY channel count is Basic
    # tier in JLCPCB's library, and the four Basic TVS parts that do exist are
    # SMA/SMB power diodes with a 5 to 12 V standoff and unpublished (i.e.
    # 100 pF class) capacitance, which would not clamp a 3.3 V line and would
    # destroy a 307 Mbit/s lane.  Why not fewer, bigger arrays: the 6-channel
    # TPD6E004 is 1.6 pF per channel and the 8-channel TPD8E003 is 9 pF, three
    # to eighteen times over budget, and the 8-channel part also costs 25
    # times more per conductor and has 61 pieces in stock.  SP3012-04UTG
    # (C2987148) is 0.3 pF and would be the better part on capacitance and
    # price, at 4,021 in stock; it is recorded here as the alternative.
    esd_lines = []
    for pos, onet, inet, _ in LANES:
        esd_lines += ['A_%s_P' % onet, 'A_%s_N' % onet,
                      'B_%s_P' % inet, 'B_%s_N' % inet]
    for pos, onet, inet, _ in SIDEBANDS:
        # the two deliberately undriven positions still leave the enclosure
        # on a cable, so they are clamped like everything else
        esd_lines.append(('SB_%s_OUT' % onet) if onet else 'SB_NC%d' % pos)
        esd_lines.append('SB_%s_IN' % inet)
    arr, _ = esd_arrays('D', 1, esd_lines,
                        'PLACE WITHIN 5 mm OF THE SlimSAS CONTACTS, on the '
                        'connector side of the terminations, the series '
                        'resistors and the buffers, with the shortest '
                        'possible ground return.')
    b.add(*arr)

    # ==================================================== decoupling
    cs = [('100nF', '+2V5', 'U1 VCCA'), ('100nF', '+3V3', 'U1 VCCB'),
          ('100nF', '+2V5', 'U2 VCCA'), ('100nF', '+3V3', 'U2 VCCB'),
          ('100nF', '+3V3', 'U3 VCCA'), ('100nF', '+2V5', 'U3 VCCB'),
          ('100nF', '+3V3', 'U4 VCC'), ('100nF', '+3V3', 'U5 VCC'),
          ('100nF', '+3V3', 'U6 VCC'), ('100nF', '+3V3', 'U7 VCC'),
          ('100nF', '+3V3', 'U8 VCCA'), ('100nF', '+3V3', 'U8 VCCB'),
          ('100nF', '+3V3', 'U9 VCCA'), ('100nF', '+3V3', 'U9 VCCB'),
          ('100nF', '+3V3', 'U10 VCCA'), ('100nF', '+3V3', 'U10 VCCB'),
          ('100nF', '+3V3', 'U11 VCCA'), ('100nF', '+3V3', 'U11 VCCB'),
          ('100nF', '+3V3', 'U12 input'), ('1uF', '+2V5', 'U12 output'),
          ('100nF', 'DB1_3V3', 'DB1 +3V3 entry, before FB1'),
          ('100nF', '+3V3', '+3V3 bulk, high frequency'),
          ('100nF', '+2V5', '+2V5 bulk, high frequency')]
    for val, net, why in cs:
        b.add(C(ref('C'), val, net, 'GND', lcsc=LC['c100n'] if val == '100nF'
                else LC['c1u'], desc=why))
    # Bulk.  Deliberately modest: 10 uF on each rail and no more.  INRUSH.
    # At power-up the radio's ST1S10 soft-starts over about 1 ms, so the
    # board's total 22.3 uF draws C dV/dt = 22.3u x 3.3 / 1m = 74 mA of
    # charging current on top of its own load - nothing.  HOT PLUG IS A
    # DIFFERENT MATTER: inserting the board with the radio powered charges
    # that capacitance through FB1's 50 mOhm and the trace, about 3.3 / 0.15 =
    # 22 A for a 3 us time constant, which would dip the radio's 3.3 V rail.
    # DO NOT FIT OR REMOVE THE BOARD WITH THE RADIO POWERED.  That is also
    # why the bulk is 10 uF and not 100 uF.
    b.add(C(ref('C'), '10uF', '+3V3', 'GND', lcsc=LC['c10u'], big=True,
            desc='+3V3 bulk, after FB1. 10 uF 25 V X5R 0805 - kept small on '
                 'purpose, see the inrush note'))
    b.add(C(ref('C'), '10uF', '+2V5', 'GND', lcsc=LC['c10u'], big=True,
            desc='+2V5 bulk, U12 output'))
    b.add(C(ref('C'), '10uF', 'DB1_3V3', 'GND', lcsc=LC['c10u'], big=True,
            desc='+3V3 bulk on the DB1 side of FB1, so the bead sees a '
                 'capacitor on both sides'))

    # ==================================================== test points
    # Test points, trimmed to what the bring-up sequence in ROUTING.md
    # actually probes plus every net that would otherwise have only one
    # connection.  A 1.5 mm pad with its courtyard costs 8.4 mm2 of placeable
    # area, so sixty of them is half the free board.
    tps = ['HL2_FWD_CLK_RAW', 'HL2_FWD_CLK', 'DI_FWDCLK',
           'HL2_ADC_D0', 'HL2_ADC_D1', 'HL2_ADC_D2',
           'HL2_AUX_CLK_OUT', 'HL2_AUX_DAT_OUT',
           'HL2_AUX_CLK_IN', 'HL2_AUX_DAT_IN', 'HL2_REV_CLK',
           'HL2_TX_D0', 'HL2_TX_D1', 'HL2_TX_D2',
           'RX_REVCLK', 'RX_DUPCLK', 'RX_SPARE', 'X_REVCLK25',
           'HL2_JTAG_EN', 'HL2_AUXIO_EN', 'JTAG_EN_N', 'AUXIO_EN_N',
           'DRV_EN', 'DI_SPARE',
           'SB_PRSNT_OUT', 'SB_PRSNT_IN', 'SB_TDO_OUT',
           'SB_TCK_IN', 'SB_TMS_IN', 'SB_TDI_IN', 'SB_NC9', 'SB_NC29',
           'J_TCK', 'J_TMS', 'J_TDI', 'J_TDO', 'CN1_VTREF',
           'J_SPARE1', 'J_SPARE2', 'J_SPARE3', 'J_SPARE4',
           'AUXIO0_T', 'AUXIO1_T', 'AUXIO2_T', 'AUXIO3_T',
           'VLVDS', 'DB1_3V3', '+3V3', '+2V5']
    for net in tps:
        b.add(TP(ref('TP'), net))
    for at in ((30.0, 60.0), (34.0, 60.0)):
        g = TP(ref('TP'), 'GND', t='TPBIG')
        g.at = at
        b.add(g)
    b.add(Part('J6', 'HDR1x02', 'GND CLIP', {'1': 'GND', '2': 'GND'},
               lcsc='', dnp=True,
               mfr='2.54 mm 1x2P vertical pin header (LCSC C52016390)',
               desc='Ground clip / scope reference', at=(41.0, 60.0), rot=0,
               note='Hand soldered.'))

    # ==================================================== mechanical
    # One unplated 1.1 mm hole for the optional locating peg into HL2 MH6 at
    # (74.04, 75.42), which lines the board up before any header engages.  No
    # footprint and no pad: it is a hole, and a hole is all it is.  The M3
    # anchor is the U-notch in the outline above, not a part.
    b.npth.append((MH6_AT[0], MH6_AT[1], 1.1))

    # No PWR_FLAG on +2V5: U12's output pin is itself a power output, and two
    # power outputs on one net is an ERC error.
    for net in ['GND', '+3V3', 'DB1_3V3', 'VLVDS', 'VLVDS_F',
                'CN1_VTREF', 'SHELL']:
        b.add(FLAG(net))

    # The +2V5 island: it has to reach U1 and U2's VCCA, U3's VCCB, U12's
    # output and the SL_VLVDS link, so it spans the translator row.
    b.zones_extra.append(('In2.Cu', '+2V5', 10,
                          [(8.0, 1.0), (33.0, 1.0), (33.0, 12.0),
                           (8.0, 12.0)],
                          'power plane island: +2V5'))

    # ---------------------------------------------------- the floor plan
    # Three bands, packed by real courtyards, and every band chosen to clear
    # the four socket keep-outs (DB1 reaches local y 29.3 at x < 8.4, DB12
    # occupies x 9.2-17.8 / y 7.3-21.0, the CN1 socket x 53.9-62.5 / y < 20.9
    # and the JTAG header x 51.7-60.3 / y 18.1-41.9) and the SlimSAS
    # receptacle (x < 20.8, y 33.5-58.5).
    #
    # Band B holds the LVDS silicon and band A the translators, both inside
    # local x 18..53 and y 12..28 - i.e. within about 25 mm of DB1 and DB12,
    # which is what section 11.6's rule asks for: every single-ended HL2 net
    # stays short, and the only long runs are the terminated 100 ohm
    # differential pairs up to the connector, which do not care.
    P = {p_.ref: p_ for p_ in b.parts}
    row([P['U1'], P['U2'], P['U3'], P['U8'], P['U9']], 25.0, 9.0)
    row([P['U4'], P['U5'], P['U6'], P['U7']], 16.0, 18.6, rot=90)
    row([P['FB1'], P['FB2'], P['U12']], 31.5, 9.0)
    row([P['U10'], P['U11']], 31.5, 22.0)

    autoplace(b, [(9.5, 1.0, 51.0, 6.8),
                  (18.2, 7.6, 51.0, 11.6),
                  (22.0, 35.0, 44.0, 49.5),
                  (22.0, 50.5, 44.0, 58.0),
                  (45.0, 50.5, 63.5, 58.0),
                  (1.0, 58.8, 28.0, 63.2),
                  (43.5, 58.8, 63.5, 63.2),
                  (44.0, 27.5, 51.2, 38.5),
                  (57.5, 42.2, 63.5, 49.5),
                  (60.8, 21.5, 63.5, 41.5)])

    b.calibration_rule(30.0, 64.2, 30.0)
    b.texts = [
        ('F.SilkS', 32.0, 31.0, 0, 1.6,
         'HERMES LITE 2 SlimSAS BRIDGE  rev %s  ONE DESIGN, BOTH ENDS' % REV),
        ('F.SilkS', 24.0, 46.0, 0, 1.2, 'SlimSAS SFF-8654 8i'),
        ('F.SilkS', 24.0, 48.5, 0, 1.0,
         'ROW A = DRIVEN   ROW B = RECEIVED   CABLE CROSSES A(n)-B(n)'),
        ('F.SilkS', 57.3, 21.5, 0, 1.0, 'JTAG PASS-THRU'),
        ('F.SilkS', 50.75, 44.75, 0, 1.0, 'DB6 / DB3 ACCESS'),
        ('Dwgs.User', 32.0, 58.0, 0, 1.4,
         'Board = 64.50 x 64.95 mm. Local (0,0) = Hermes-Lite 2 main board '
         '(70.00, 73.30) mm. Underside 11.04 mm above the HL2 top surface.'),
        ('Dwgs.User', 32.0, 60.0, 0, 1.4,
         'SlimSAS locating-hole datum at local x 10.40, y 46.00 = HL2 '
         '(80.40, 119.30). Mating face nominally 0.30 mm behind the board '
         'edge - VERIFY BEFORE CUTTING THE PANEL.'),
        ('Dwgs.User', 32.0, 62.0, 0, 1.4,
         'Panel window: 26.5 x 10.5 mm centred on HL2 y 119.30, from 19.6 to '
         '30.2 mm above the enclosure floor. FABRICATION: 4 layer, 1.6 mm, '
         'HASL, ONE design.'),
        ('B.SilkS', 32.0, 33.0, 0, 1.2, 'SOCKETS J2 J3 J4 ON THIS SIDE'),
        ('B.SilkS', 32.0, 35.5, 0, 1.0,
         'DB12 p5=PIN_89(AUX CLK IN)  p6=PIN_88(REV CLK)'),
        ('B.SilkS', 32.0, 38.0, 0, 1.0,
         'HL2 R17 MUST NOT BE FITTED.  DO NOT PLUG OR UNPLUG POWERED.'),
        ('F.SilkS', 9.0, 3.0, 90, 1.0, 'DB1 p1'),
        ('F.SilkS', 18.0, 11.0, 0, 1.0, 'DB12 p1'),
        ('F.SilkS', 60.0, 6.0, 90, 1.0, 'CN1 p1'),
    ]
    return b

# ==========================================================================
#  Library emission
# ==========================================================================


def write_libs(outdir, board):
    used = sorted({p.ptype for p in board.parts})
    w = W()
    w.open('kicad_symbol_lib')
    w.line('version', '20231120')
    w.line('generator', q('gowin-bridge-gen'))
    for t in used:
        symlib, symname, fplib, fpname = TYPES[t]
        fpref = '%s:%s' % (LOCAL_FP, fpname) if fpname else ''
        if symlib is None:
            pins, ds, desc = CUSTOM[symname]
            build_custom_symbol(w, symname, pins, fpref, ds, desc)
        else:
            sym, parent = SYMLIB.get(symlib, symname)
            K.emit_symbol(w, symname, sym, parent, fpref)
    w.close_inline()
    with open(os.path.join(outdir, LOCAL_SYM + '.kicad_sym'), 'w',
              encoding='utf-8') as f:
        f.write(w.text())

    pretty = os.path.join(outdir, LOCAL_FP + '.pretty')
    os.makedirs(pretty, exist_ok=True)
    # Prune footprints this board no longer uses, so a part dropped from the
    # netlist does not leave a stale land pattern behind in the library.
    wanted = {TYPES[t2][3] + '.kicad_mod' for t2 in used if TYPES[t2][3]}
    for f in os.listdir(pretty):
        if f.endswith('.kicad_mod') and f not in wanted:
            os.remove(os.path.join(pretty, f))
            print('   pruned stale footprint %s from %s'
                  % (f, os.path.basename(outdir)))
    fps = {}
    for t in used:
        symlib, symname, fplib, fpname = TYPES[t]
        if not fpname:
            continue
        path = os.path.join(pretty, fpname + '.kicad_mod')
        if fplib is None:
            # generated, not lifted: the SlimSAS land pattern
            txt = build_slimsas_fp(fpname)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(txt)
            node = K.parse(txt)[0]
        else:
            node = FPLIB.get(fplib, fpname)
            K.emit_footprint_lib(path, fpname, node)
            node = K.parse(open(path, encoding='utf-8').read())[0]
        fps[fpname] = node
    return fps


# ==========================================================================
#  Schematic emission
# ==========================================================================

SHEET = (1189.0, 841.0)     # A0


def symbol_geometry(ptype):
    symlib, symname, fplib, fpname = TYPES[ptype]
    if symlib is None:
        pins = CUSTOM[symname][0]
        left = [p for p in pins if p[3] == 'L']
        right = [p for p in pins if p[3] == 'R']
        rows = max(len(left), len(right))
        half_h = (rows + 1) * 2.54 / 2.0
        g = {}
        y = half_h - 2.54
        for num, nm, et, _ in left:
            g[num] = (-(12.7 + 2.54), y, 0, 2.54, nm, et)
            y -= 2.54
        y = half_h - 2.54
        for num, nm, et, _ in right:
            g[num] = (12.7 + 2.54, y, 180, 2.54, nm, et)
            y -= 2.54
        x = -2.54
        for num, nm, et, _ in [p for p in pins if p[3] == 'T']:
            g[num] = (x, half_h + 2.54, 270, 2.54, nm, et)
            x += 5.08
        x = -2.54
        for num, nm, et, _ in [p for p in pins if p[3] == 'B']:
            g[num] = (x, -(half_h + 2.54), 90, 2.54, nm, et)
            x += 5.08
        return g
    sym, parent = SYMLIB.get(symlib, symname)
    return K.symbol_pin_geometry(sym, parent)


def write_sch(outdir, board):
    path = os.path.join(outdir, board.name + '.kicad_sch')
    geo = {t: symbol_geometry(t) for t in sorted({p.ptype for p in board.parts})}

    placed = []
    cursor_x, cursor_y, row_h = 20.0, 30.0, 0.0
    LBL = 34.0
    for p in board.parts:
        g = geo[p.ptype]
        if not g:
            wpx = wpy = 10.0
            minx = maxy = 0.0
        else:
            xs = [v[0] for v in g.values()]
            ys = [v[1] for v in g.values()]
            minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
            wpx = (maxx - minx) + 2 * LBL
            wpy = (maxy - miny) + 20.0
        if cursor_x + wpx > SHEET[0] - 20.0:
            cursor_x = 20.0
            cursor_y += row_h + 10.0
            row_h = 0.0
        snap = lambda v: round(v / 1.27) * 1.27
        ox = snap(cursor_x + LBL - minx)
        oy = snap(cursor_y + 10.0 + maxy)
        placed.append((p, ox, oy))
        cursor_x += wpx + 5.0
        row_h = max(row_h, wpy)

    w = W()
    w.open('kicad_sch')
    w.line('version', '20231120')
    w.line('generator', q('eeschema'))
    w.line('generator_version', q('8.0'))
    w.line('uuid', q(uuid_for(board.name, 'sch')))
    w.line('paper', q('A0'))
    w.open('title_block')
    w.line('title', q(board.title))
    w.line('date', q('2026-09-12'))
    w.line('rev', q(REV))
    w.line('company', q('Hermes-Lite 2 companion - gowin-bridge'))
    w.line('comment', '1', q('Generated by tools/gen_gowin_bridge.py - do not '
                             'hand-edit; edit the generator instead'))
    w.line('comment', '2', q('Nets are joined by local labels on every pin '
                             '(netlist-style schematic)'))
    w.line('comment', '3', q('Authoritative pin map: '
                             'hardware/companions/gowin-bridge/PINMAP.md'))
    w.close_inline()

    w.open('lib_symbols')
    for t in sorted({p.ptype for p in board.parts}):
        symlib, symname, fplib, fpname = TYPES[t]
        fpref = '%s:%s' % (LOCAL_FP, fpname) if fpname else ''
        if symlib is None:
            pins, ds, desc = CUSTOM[symname]
            build_custom_symbol(w, '%s:%s' % (LOCAL_SYM, symname), pins, fpref,
                                ds, desc)
        else:
            sym, parent = SYMLIB.get(symlib, symname)
            K.emit_symbol(w, '%s:%s' % (LOCAL_SYM, symname), sym, parent, fpref)
    w.close_inline()

    for p, ox, oy in placed:
        symlib, symname, fplib, fpname = TYPES[p.ptype]
        g = geo[p.ptype]
        u = uuid_for(board.name, p.ref)
        w.open('symbol')
        w.line('lib_id', q('%s:%s' % (LOCAL_SYM, symname)))
        w.line('at', fmt(ox), fmt(oy), '0')
        w.line('unit', '1')
        w.line('exclude_from_sim', 'no')
        w.line('in_bom', 'no' if p.exclude_bom else 'yes')
        w.line('on_board', 'yes')
        w.line('dnp', 'yes' if p.dnp else 'no')
        w.line('uuid', q(u))
        ys = [v[1] for v in g.values()] or [0]
        w.open('property', q('Reference'), q(p.ref))
        w.line('at', fmt(ox), fmt(oy - max(ys) - 4.0), '0')
        w.raw(effects(1.27, justify='left'))
        w.close_inline()
        w.open('property', q('Value'), q(p.value))
        w.line('at', fmt(ox), fmt(oy - max(ys) - 1.5), '0')
        w.raw(effects(1.27, justify='left'))
        w.close_inline()
        w.open('property', q('Footprint'),
               q('%s:%s' % (LOCAL_FP, fpname) if fpname else ''))
        w.line('at', fmt(ox), fmt(oy), '0')
        w.raw(effects(1.27, hide=True))
        w.close_inline()
        for k, v in (('LCSC', p.lcsc), ('MFR', p.mfr), ('Note', p.note),
                     ('Description', p.desc)):
            if not v:
                continue
            w.open('property', q(k), q(v))
            w.line('at', fmt(ox), fmt(oy), '0')
            w.raw(effects(1.27, hide=True))
            w.close_inline()
        for num in sorted(g, key=lambda s: (len(s), s)):
            w.open('pin', q(num))
            w.line('uuid', q(uuid_for(board.name, p.ref, 'pin', num)))
            w.close_inline()
        w.open('instances')
        w.open('project', q(board.name))
        w.open('path', q('/' + uuid_for(board.name, 'sch')))
        w.line('reference', q(p.ref))
        w.line('unit', '1')
        w.close_inline()
        w.close_inline()
        w.close_inline()
        w.close_inline()

        for num, (sx, sy, rot, length, nm, et) in g.items():
            px = ox + sx
            py = oy - sy
            d = {0: (-2.54, 0.0), 180: (2.54, 0.0), 90: (0.0, 2.54),
                 270: (0.0, -2.54)}[rot % 360]
            ex, ey = px + d[0], py + d[1]
            net = p.pins.get(num)
            if net is None and et == 'no_connect':
                w.open('no_connect')
                w.line('at', fmt(px), fmt(py))
                w.line('uuid', q(uuid_for(board.name, p.ref, 'nc', num)))
                w.close_inline()
                continue
            w.open('wire')
            w.open('pts')
            w.line('xy', fmt(px), fmt(py))
            w.line('xy', fmt(ex), fmt(ey))
            w.close_inline()
            w.line('stroke', '(width 0)', '(type default)')
            w.line('uuid', q(uuid_for(board.name, p.ref, 'w', num)))
            w.close_inline()
            if net:
                ang = {0: 180, 180: 0, 90: 270, 270: 90}[rot % 360]
                w.open('label', q(net))
                w.line('at', fmt(ex), fmt(ey), ang)
                w.raw(effects(1.0, justify='left bottom'))
                w.line('uuid', q(uuid_for(board.name, p.ref, 'l', num)))
                w.close_inline()
            else:
                w.open('no_connect')
                w.line('at', fmt(ex), fmt(ey))
                w.line('uuid', q(uuid_for(board.name, p.ref, 'nc', num)))
                w.close_inline()

    w.open('sheet_instances')
    w.open('path', q('/'))
    w.line('page', q('1'))
    w.close_inline()
    w.close_inline()
    w.close_inline()
    with open(path, 'w', encoding='utf-8') as f:
        f.write(w.text())


# ==========================================================================
#  PCB emission
# ==========================================================================

PCB_LAYERS = [
    (0, 'F.Cu', 'signal'), (1, 'In1.Cu', 'signal'), (2, 'In2.Cu', 'signal'),
    (31, 'B.Cu', 'signal'),
    (32, 'B.Adhes', 'user', 'B.Adhesive'), (33, 'F.Adhes', 'user', 'F.Adhesive'),
    (34, 'B.Paste', 'user'), (35, 'F.Paste', 'user'),
    (36, 'B.SilkS', 'user', 'B.Silkscreen'), (37, 'F.SilkS', 'user', 'F.Silkscreen'),
    (38, 'B.Mask', 'user'), (39, 'F.Mask', 'user'),
    (40, 'Dwgs.User', 'user', 'User.Drawings'),
    (41, 'Cmts.User', 'user', 'User.Comments'),
    (42, 'Eco1.User', 'user', 'User.Eco1'), (43, 'Eco2.User', 'user', 'User.Eco2'),
    (44, 'Edge.Cuts', 'user'), (45, 'Margin', 'user'),
    (46, 'B.CrtYd', 'user', 'B.Courtyard'), (47, 'F.CrtYd', 'user', 'F.Courtyard'),
    (48, 'B.Fab', 'user'), (49, 'F.Fab', 'user'),
]

PCB_OFFSET = (40.0, 40.0)   # local (0,0) -> page coordinates


def write_pcb(outdir, board, fps):
    path = os.path.join(outdir, board.name + '.kicad_pcb')
    nets = board.nets()
    ox, oy = PCB_OFFSET

    w = W()
    w.open('kicad_pcb')
    w.line('version', '20240108')
    w.line('generator', q('pcbnew'))
    w.line('generator_version', q('8.0'))
    w.open('general')
    w.line('thickness', '1.6')
    w.line('legacy_teardrops', 'no')
    w.close_inline()
    w.line('paper', q('A3'))
    w.open('layers')
    for l in PCB_LAYERS:
        if len(l) == 4:
            w.line(str(l[0]), q(l[1]), l[2], q(l[3]))
        else:
            w.line(str(l[0]), q(l[1]), l[2])
    w.close_inline()

    w.open('setup')
    w.open('stackup')
    for nm, ty, th in (('F.SilkS', 'Top Silk Screen', None),
                       ('F.Paste', 'Top Solder Paste', None),
                       ('F.Mask', 'Top Solder Mask', '0.01'),
                       ('F.Cu', 'copper', '0.035')):
        w.open('layer', q(nm))
        w.line('type', q(ty))
        if th:
            w.line('thickness', th)
        w.close_inline()
    for i, (dname, dty, dth) in enumerate(
            (('dielectric 1', 'core', '0.2'),
             ('dielectric 2', 'prepreg', '1.065'),
             ('dielectric 3', 'core', '0.2')), start=1):
        if i > 1:
            pass
        if i == 1:
            pass
        w.open('layer', q(dname))
        w.line('type', q(dty))
        w.line('thickness', dth)
        w.line('material', q('FR4'))
        w.line('epsilon_r', '4.5')
        w.line('loss_tangent', '0.02')
        w.close_inline()
        if i == 1:
            w.open('layer', q('In1.Cu'))
            w.line('type', q('copper'))
            w.line('thickness', '0.0152')
            w.close_inline()
        elif i == 2:
            w.open('layer', q('In2.Cu'))
            w.line('type', q('copper'))
            w.line('thickness', '0.0152')
            w.close_inline()
    for nm, ty, th in (('B.Cu', 'copper', '0.035'),
                       ('B.Mask', 'Bottom Solder Mask', '0.01'),
                       ('B.Paste', 'Bottom Solder Paste', None),
                       ('B.SilkS', 'Bottom Silk Screen', None)):
        w.open('layer', q(nm))
        w.line('type', q(ty))
        if th:
            w.line('thickness', th)
        w.close_inline()
    w.line('copper_finish', q('None'))
    w.line('dielectric_constraints', 'no')
    w.close_inline()
    w.line('pad_to_mask_clearance', '0.05')
    w.line('allow_soldermask_bridges_in_footprints', 'no')
    w.open('pcbplotparams')
    for k, v in (('layerselection', '0x00000000_00000000_55555555_5755f5ff'),
                 ('plot_on_all_layers_selection',
                  '0x00000000_00000000_00000000_00000000'),
                 ('disableapertmacros', 'no'), ('usegerberextensions', 'no'),
                 ('usegerberattributes', 'yes'),
                 ('usegerberadvancedattributes', 'yes'),
                 ('creategerberjobfile', 'yes'),
                 ('dashed_line_dash_ratio', '12.000000'),
                 ('dashed_line_gap_ratio', '3.000000'), ('svgprecision', '4'),
                 ('plotframeref', 'no'), ('mode', '1'), ('useauxorigin', 'no'),
                 ('hpglpennumber', '1'), ('hpglpenspeed', '20'),
                 ('hpglpendiameter', '15.000000'),
                 ('pdf_front_fp_property_popups', 'yes'),
                 ('pdf_back_fp_property_popups', 'yes'),
                 ('dxfpolygonmode', 'yes'), ('dxfimperialunits', 'yes'),
                 ('dxfusepcbnewfont', 'yes'), ('psnegative', 'no'),
                 ('psa4output', 'no'), ('plotreference', 'yes'),
                 ('plotvalue', 'yes'), ('plotfptext', 'yes'),
                 ('plotinvisibletext', 'no'), ('sketchpadsonfab', 'no'),
                 ('subtractmaskfromsilk', 'no'), ('outputformat', '1'),
                 ('mirror', 'no'), ('drillshape', '1'),
                 ('scaleselection', '1')):
        w.line(k, v)
    w.line('outputdirectory', q('gerbers/'))
    w.close_inline()
    w.close_inline()

    w.line('net', '0', q(''))
    for name, code in sorted(nets.items(), key=lambda kv: kv[1]):
        w.line('net', str(code), q(name))

    for p in board.parts:
        symlib, symname, fplib, fpname = TYPES[p.ptype]
        if not fpname:
            continue
        node = fps[fpname]
        px = ox + (p.at[0] if p.at else 0.0)
        py = oy + (p.at[1] if p.at else 0.0)
        rot = p.rot % 360
        w.open('footprint', q('%s:%s' % (LOCAL_FP, fpname)))
        w.line('layer', q(p.layer))
        w.line('uuid', q(uuid_for(board.name, 'fp', p.ref)))
        if rot:
            w.line('at', fmt(px), fmt(py), fmt(rot))
        else:
            w.line('at', fmt(px), fmt(py))
        d = K.kid(node, 'descr')
        if d is not None:
            w.line('descr', q(K.atoms(d)[0]))
        t = K.kid(node, 'tags')
        if t is not None:
            w.line('tags', q(K.atoms(t)[0]))
        w.line('path', q('/%s/%s' % (uuid_for(board.name, 'sch'),
                                     uuid_for(board.name, p.ref))))
        at = K.kid(node, 'attr')
        if at is not None:
            w.line('attr', *K.atoms(at))
        if p.dnp:
            w.line('attr', 'dnp')

        def net_of(padnum, _p=p):
            n = _p.pins.get(padnum)
            if not n:
                return None
            return (nets[n], n)

        sidefx = 'B' if p.layer == 'B.Cu' else 'F'
        w.open('fp_text', 'reference', q(p.ref))
        w.line('at', '0', '-3.2', '0')
        w.line('layer', q('%s.SilkS' % sidefx))
        w.line('uuid', q(uuid_for(board.name, 'fpr', p.ref)))
        w.raw(effects(1.0))
        w.close_inline()
        w.open('fp_text', 'value', q(p.value))
        w.line('at', '0', '3.2', '0')
        w.line('layer', q('%s.Fab' % sidefx))
        w.line('uuid', q(uuid_for(board.name, 'fpv', p.ref)))
        w.raw(effects(1.0))
        w.close_inline()
        K._emit_fp_body(w, node, with_text=False, net_of_pad=net_of,
                        fp_rot_for_pads=rot, mirror_x=p.mirror)
        w.close_inline()

    pts = board.outline
    for i in range(len(pts)):
        a = pts[i]
        c = pts[(i + 1) % len(pts)]
        w.open('gr_line')
        w.line('start', fmt(ox + a[0]), fmt(oy + a[1]))
        w.line('end', fmt(ox + c[0]), fmt(oy + c[1]))
        w.line('stroke', '(width 0.1)', '(type default)')
        w.line('layer', q('Edge.Cuts'))
        w.line('uuid', q(uuid_for(board.name, 'edge', i)))
        w.close_inline()

    for i, (ex0, ey0, ex1, ey1) in enumerate(board.edge_extra):
        w.open('gr_line')
        w.line('start', fmt(ox + ex0), fmt(oy + ey0))
        w.line('end', fmt(ox + ex1), fmt(oy + ey1))
        w.line('stroke', '(width 0.1)', '(type default)')
        w.line('layer', q('Edge.Cuts'))
        w.line('uuid', q(uuid_for(board.name, 'edgex', i)))
        w.close_inline()

    # Unplated holes with no footprint: the mouse-bite perforations.  Emitted
    # as a footprint per hole, because KiCad has no bare-drill primitive.
    for i, (hx, hy, hd) in enumerate(board.npth):
        w.open('footprint', q('MouseBite:Drill'))
        w.line('layer', q('F.Cu'))
        w.line('uuid', q(uuid_for(board.name, 'mb', i)))
        w.line('at', fmt(ox + hx), fmt(oy + hy))
        w.line('descr', q('Mouse-bite perforation, unplated'))
        w.line('attr', 'exclude_from_pos_files', 'exclude_from_bom',
               'allow_missing_courtyard')
        w.open('fp_text', 'reference', q('MB%d' % (i + 1)))
        w.line('at', '0', '-1.2', '0')
        w.line('layer', q('F.Fab'))
        w.line('hide', 'yes')
        w.line('uuid', q(uuid_for(board.name, 'mbr', i)))
        w.raw(effects(0.6))
        w.close_inline()
        w.open('pad', q(''), 'np_thru_hole', 'circle')
        w.line('at', '0', '0')
        w.line('size', fmt(hd), fmt(hd))
        w.line('drill', fmt(hd))
        w.line('layers', q('F&B.Cu'), q('*.Mask'))
        w.close_inline()
        w.close_inline()

    for (layer, lx0, ly0, lx1, ly1, lw) in board.lines:
        w.open('gr_line')
        w.line('start', fmt(ox + lx0), fmt(oy + ly0))
        w.line('end', fmt(ox + lx1), fmt(oy + ly1))
        w.line('stroke', '(width %s)' % fmt(lw), '(type default)')
        w.line('layer', q(layer))
        w.line('uuid', q(uuid_for(board.name, 'gline', lx0, ly0, lx1, ly1)))
        w.close_inline()

    for layer, tx, ty, trot, tsize, txt in board.texts:
        w.open('gr_text', q(txt))
        w.line('at', fmt(ox + tx), fmt(oy + ty), fmt(trot))
        w.line('layer', q(layer))
        w.line('uuid', q(uuid_for(board.name, 'txt', txt)))
        w.raw('(effects (font (size %s %s) (thickness %s))%s)'
              % (fmt(tsize), fmt(tsize), fmt(tsize / 6.0),
                 ' (justify mirror)' if layer.startswith('B.') else ''))
        w.close_inline()

    def zone(layer, net, prio, poly, name):
        w.open('zone')
        w.line('net', str(nets[net]))
        w.line('net_name', q(net))
        w.line('layer', q(layer))
        w.line('uuid', q(uuid_for(board.name, 'zone', layer, net, name)))
        w.line('name', q(name))
        w.line('hatch', 'edge', '0.5')
        w.line('priority', str(prio))
        # Solid pad connection, not thermal reliefs: a 4-spoke relief on
        # a 0.5 mm-pitch IC pad or a 1 mm connector hole comes out starved,
        # and on a ground plane carrying 300 Mbit/s returns a solid
        # connection is what you want anyway.
        w.open('connect_pads', 'yes')
        w.line('clearance', '0.25')
        w.close_inline()
        w.line('min_thickness', '0.25')
        w.line('filled_areas_thickness', 'no')
        w.open('fill', 'yes')
        w.line('thermal_gap', '0.35')
        w.line('thermal_bridge_width', '0.4')
        w.close_inline()
        w.open('polygon')
        w.open('pts')
        for (zx, zy) in poly:
            w.line('xy', fmt(ox + zx), fmt(oy + zy))
        w.close_inline()
        w.close_inline()
        w.close_inline()

    # Full-board pours.  ``board.zones_full`` lets the panel pour each of its
    # two boards separately, because a panel is one outline carrying two
    # electrically independent boards and one net must not cross from one to
    # the other.
    if board.zones_full is None:
        zone('In1.Cu', 'GND', 0, pts, 'GND plane (layer 2) - DO NOT CUT')
        zone('F.Cu', 'GND', 0, pts, 'top ground fill')
        zone('B.Cu', 'GND', 0, pts, 'bottom ground fill')
        zone('In2.Cu', '+3V3', 0, pts, 'power plane (layer 3): +3V3')
    else:
        for (zlayer, znet, zprio, zpoly, zname) in board.zones_full:
            zone(zlayer, znet, zprio, zpoly, zname)
    for (zlayer, znet, zprio, zpoly, zname) in board.zones_extra:
        zone(zlayer, znet, zprio, zpoly, zname)

    w.close_inline()
    with open(path, 'w', encoding='utf-8') as f:
        f.write(w.text())


# ==========================================================================
#  Project file, BOM
# ==========================================================================

PRO_TEMPLATE = '''{
  "board": {
    "3dviewports": [],
    "design_settings": {
      "defaults": {
        "board_outline_line_width": 0.1,
        "copper_line_width": 0.15,
        "copper_text_size_h": 1.0,
        "copper_text_size_v": 1.0,
        "copper_text_thickness": 0.15,
        "other_line_width": 0.15,
        "silk_line_width": 0.12,
        "silk_text_size_h": 1.0,
        "silk_text_size_v": 1.0,
        "silk_text_thickness": 0.15
      },
      "diff_pair_dimensions": [
        { "gap": 0.2, "via_gap": 0.25, "width": 0.25 },
        { "gap": 0.17, "via_gap": 0.25, "width": 0.15 }
      ],
      "rules": {
        "min_clearance": 0.13,
        "min_copper_edge_clearance": 0.3,
        "min_hole_clearance": 0.25,
        "min_through_hole_diameter": 0.3,
        "min_track_width": 0.127,
        "min_via_annular_width": 0.075,
        "min_via_diameter": 0.45
      },
      "track_widths": [ 0.0, 0.2, 0.25, 0.4, 0.8 ],
      "via_dimensions": [ { "diameter": 0.0, "drill": 0.0 }, { "diameter": 0.45, "drill": 0.25 } ]
    }
  },
  "libraries": { "pinned_footprint_libs": [], "pinned_symbol_libs": [] },
  "meta": { "filename": "%(name)s.kicad_pro", "version": 1 },
  "net_settings": { "classes": [
      { "bus_width": 12, "clearance": 0.15, "diff_pair_gap": 0.2,
        "diff_pair_via_gap": 0.25, "diff_pair_width": 0.25, "line_style": 0,
        "microvia_diameter": 0.3, "microvia_drill": 0.1, "name": "Default",
        "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)",
        "track_width": 0.25, "via_diameter": 0.6, "via_drill": 0.3, "wire_width": 6 },
      { "bus_width": 12, "clearance": 0.13, "diff_pair_gap": 0.2,
        "diff_pair_via_gap": 0.25, "diff_pair_width": 0.25, "line_style": 0,
        "microvia_diameter": 0.3, "microvia_drill": 0.1, "name": "LVDS100",
        "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)",
        "track_width": 0.25, "via_diameter": 0.45, "via_drill": 0.25, "wire_width": 6 },
      { "bus_width": 12, "clearance": 0.2, "diff_pair_gap": 0.2,
        "diff_pair_via_gap": 0.25, "diff_pair_width": 0.25, "line_style": 0,
        "microvia_diameter": 0.3, "microvia_drill": 0.1, "name": "Power",
        "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)",
        "track_width": 0.6, "via_diameter": 0.8, "via_drill": 0.4, "wire_width": 6 }
    ],
    "meta": { "version": 3 },
    "net_colors": null,
    "netclass_assignments": null,
    "netclass_patterns": [
%(patterns)s
    ]
  },
  "pcbnew": { "last_paths": { "gencad": "", "idf": "", "netlist": "",
      "plot": "gerbers/", "pos_files": "", "specctra_dsn": "", "step": "",
      "svg": "", "vrml": "" }, "page_layout_descr_file": "" },
  "schematic": {
    "legacy_lib_dir": "",
    "legacy_lib_list": [],
    "meta": { "version": 1 },
    "net_format_name": "",
    "page_layout_descr_file": "",
    "spice_current_sheet_as_root": false,
    "spice_external_command": "spice \\"%%I\\"",
    "spice_model_current_sheet_as_root": true,
    "spice_save_all_currents": false,
    "spice_save_all_dissipations": false,
    "spice_save_all_voltages": false,
    "subpart_first_id": 65,
    "subpart_id_separator": 0
  },
  "sheets": [ [ "%(schuuid)s", "Root" ] ],
  "text_variables": {}
}
'''

# Net-name prefixes that mark a differential pair, so the project file can
# put them in the LVDS100 net class.  rev C: three sockets per board, OUT /
# AUX / IN, and the panel prefixes every net with its board letter.
# Every net whose name starts with A_ or B_ and ends in _P or _N is one leg
# of a 100 ohm differential pair: A_ is a pair this board drives onto the
# cable, B_ is a pair it receives.  That is the whole naming convention, and
# write_pro turns it into the LVDS100 net class.
PAIR_PREFIXES = ('A_', 'B_')


def is_pair_net(name):
    if not name.startswith(PAIR_PREFIXES):
        return False
    return name.endswith('_P') or name.endswith('_N')


def write_pro(outdir, board):
    pats = []
    for name in sorted(board.nets()):
        if is_pair_net(name):
            pats.append('      { "netclass": "LVDS100", "pattern": "%s" }' % name)
    allnets = board.nets()
    for nm in ('+3V3', '+2V5', 'DB1_3V3', 'VLVDS', 'VLVDS_F'):
        if nm in allnets:
            pats.append('      { "netclass": "Power", "pattern": "%s" }' % nm)
    txt = PRO_TEMPLATE % {'name': board.name,
                          'patterns': ',\n'.join(pats),
                          'schuuid': uuid_for(board.name, 'sch')}
    with open(os.path.join(outdir, board.name + '.kicad_pro'), 'w',
              encoding='utf-8') as f:
        f.write(txt)
    with open(os.path.join(outdir, 'sym-lib-table'), 'w', encoding='utf-8') as f:
        f.write('(sym_lib_table\n  (version 7)\n'
                '  (lib (name "%s")(type "KiCad")(uri "${KIPRJMOD}/%s.kicad_sym")'
                '(options "")(descr "gowin-bridge project symbols"))\n)\n'
                % (LOCAL_SYM, LOCAL_SYM))
    with open(os.path.join(outdir, 'fp-lib-table'), 'w', encoding='utf-8') as f:
        f.write('(fp_lib_table\n  (version 7)\n'
                '  (lib (name "%s")(type "KiCad")(uri "${KIPRJMOD}/%s.pretty")'
                '(options "")(descr "gowin-bridge project footprints"))\n)\n'
                % (LOCAL_FP, LOCAL_FP))


def write_bom(outdir, board):
    rows = []
    for p in board.parts:
        if p.exclude_bom:
            continue
        symlib, symname, fplib, fpname = TYPES[p.ptype]
        rows.append({
            'Designator': p.ref,
            'Value': p.value,
            'Footprint': fpname or '',
            'LCSC': p.lcsc,
            'MfrPart': p.mfr,
            'Populate': 'DNP' if p.dnp else 'yes',
            'Function': p.desc,
            'Note': p.note,
        })
    path = os.path.join(outdir, board.name + '-bom.csv')
    with open(path, 'w', newline='', encoding='utf-8') as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        for r in sorted(rows, key=lambda r: (r['Designator'][0],
                                             int(''.join(c for c in r['Designator']
                                                         if c.isdigit()) or 0))):
            wr.writerow(r)
    return rows


def main():
    for b in (bridge(),):
        outdir = os.path.join(ROOT, b.name)
        os.makedirs(outdir, exist_ok=True)
        fps = write_libs(outdir, b)
        write_sch(outdir, b)
        write_pcb(outdir, b, fps)
        write_pro(outdir, b)
        rows = write_bom(outdir, b)
        nets = b.nets()
        fitted = sum(1 for p in b.parts if not p.dnp and not p.exclude_bom)
        print('%-12s %3d parts (%3d fitted), %3d nets, %3d BOM lines -> %s'
              % (b.name, len(b.parts), fitted, len(nets), len(rows), outdir))


if __name__ == '__main__':
    main()
