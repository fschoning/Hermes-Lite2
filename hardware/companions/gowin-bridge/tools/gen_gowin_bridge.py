#!/usr/bin/env python3
"""Generate the two gowin-bridge KiCad projects from one netlist description.

Run:   python tools/gen_gowin_bridge.py

Writes, next to this tools/ directory:
    ../hl2-bridge/{hl2-bridge.kicad_pro,.kicad_sch,.kicad_pcb}
    ../hl2-bridge/gowin-bridge.kicad_sym
    ../hl2-bridge/gowin-bridge.pretty/*.kicad_mod
    ../hl2-bridge/hl2-bridge-bom.csv
    ... and the same set under ../tang-bridge/

rev C: three HDMI sockets per board - OUT, AUX, IN - with the two fixed-
direction sockets on the OUTSIDE and the bidirectional auxiliary socket in the
middle.  Every lane runs DDR at 153.6 MHz = 307.2 Mbit/s in both directions.
The auxiliary socket's direction is set by a one-shunt ROLE strap plus a
single-gate inverter, so one board design works at either end of any cable.
See PINMAP.md rev C.

Also emitted: a THIRD KiCad project, ../panel/, holding both boards side by
side on one 94 x 100 mm V-scored production panel with assembly rails, so the
whole set is one JLCPCB order.  The panel is generated from the same part
lists, transformed, so it cannot drift from the two individual boards.

Symbol graphics and most footprint land patterns are lifted from the stock
KiCad libraries and re-emitted as project-local libraries, so the projects are
self-contained.  The mini HDMI (Type C) land pattern is not in the stock
libraries and is built here from the manufacturer's recommended footprint
drawing; every number is in MINI_HDMI below with its source.

The netlist below is the single source of truth for the schematic, the PCB and
the BOM.  PINMAP.md must agree with it.
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

REV = 'C'

# ==========================================================================
#  Mini HDMI (Type C) land pattern - the one footprint not in the stock libs
# ==========================================================================
#
# Part: XKB Connection A71-05H4-111N1, LCSC C2682170.  Mini HDMI (Type C)
# 19-position receptacle, right angle, hybrid mount: 19 SMT signal contacts
# plus four through-hole shell legs in plated slots and two through-hole
# locating pegs.  Chosen over the cheaper SOFNG HDMI-519 (LCSC C136421, which
# is the only mini HDMI at LCSC with a published mating-cycle rating) because
# the XKB drawing is the only one that dimensions its recommended layout
# RELATIVE TO THE PCB EDGE, which is the one dimension a right-angle edge
# connector cannot afford to get wrong.  DESIGN_NOTES.md section 7.
#
# COORDINATE CONVENTION: the footprint origin sits on the board edge at the
# centre of the shell's front (mating) face, and every feature is at NEGATIVE
# y, i.e. inboard.  A socket is therefore placed at (x_centre, board_edge_y)
# with rotation 0.  This matches the stock KiCad right-angle HDMI footprints
# once their front-face offset is applied.
#
# Numbers below are transcribed from the XKB recommended-layout drawing
# (https://www.lcsc.com/datasheet/C2682170.pdf), converted to this
# convention by negating y.  The drawing's own datum is X = connector
# centreline, Y = 0 at the PCB edge, positive onto the board.
#
# *** pin1_at_plus_x IS THE ONE THING TO CHECK BEFORE SENDING GERBERS. ***
# The XKB layout view labels the ends "PIN 1" and "PIN 19" on the front view
# but not on the land-pattern view.  If the part you receive has pin 1 at the
# other end, every signal lands on the wrong cable wire.  Flip this one flag
# and regenerate.
MINI_HDMI = dict(
    # ---- outline ----
    body_w=11.20,        # shell width across the flanges
    body_d=7.00,         # body depth ON the board (front face is 0.50 mm
                         # beyond the edge, total body 7.50 mm)
    height=3.10,         # above the PCB surface (used in the enclosure sums)
    # ---- signal contacts: ONE row of 19, 0.40 mm pitch ----
    n_pins=19,
    pitch=0.40,
    pad_w=0.23,
    pad_l=1.20,
    row_y=-7.15,         # pad centreline; pads occupy y -6.55 .. -7.75
    pin1_at_plus_x=True,
    # ---- through-hole shell legs: plated slots, two rows 4.50 mm apart ----
    leg_dx=5.425,
    leg_rear_y=-6.00, leg_rear_hole=(0.65, 1.40), leg_rear_pad=(1.25, 2.00),
    leg_front_y=-1.50, leg_front_hole=(0.65, 1.20), leg_front_pad=(1.25, 1.80),
    # ---- through-hole locating pegs (shell pegs are 0.80 mm) ----
    peg_dx=3.75, peg_y=-5.20, peg_drill=0.99, peg_pad=1.55,
    depth=8.30,          # total footprint depth inboard of the board edge
)


def build_mini_hdmi_fp(name):
    """Emit the mini HDMI (Type C) right-angle hybrid footprint as text."""
    m = MINI_HDMI
    n = m['n_pins']
    # 19 contacts on a 0.40 mm pitch, centred: span 7.20 mm, x -3.60 .. +3.60.
    half = m['pitch'] * (n - 1) / 2.0
    sgn = 1.0 if m['pin1_at_plus_x'] else -1.0
    xs = {p: sgn * (half - m['pitch'] * (p - 1)) for p in range(1, n + 1)}

    w = W()
    w.open('footprint', q(name))
    w.line('version', '20240108')
    w.line('generator', q('gowin-bridge-gen'))
    w.line('layer', q('F.Cu'))
    w.line('descr', q('Mini HDMI (Type C) 19-pin receptacle, right angle, '
                      'hybrid mount: 19 SMT signal contacts on 0.40 mm pitch '
                      'plus 4 through-hole shell legs in plated slots and 2 '
                      'through-hole locating pegs. XKB A71-05H4-111N1, LCSC '
                      'C2682170. Footprint origin is on the board edge at the '
                      'centre of the shell front face; everything else is at '
                      'negative y, i.e. inboard. Land pattern from the '
                      'manufacturer recommended-layout drawing - see '
                      'MINI_HDMI in tools/gen_gowin_bridge.py, and CHECK THE '
                      'PIN 1 END against the part you order.'))
    w.line('tags', q('hdmi mini type-c right-angle hybrid'))
    # 19 pads on 0.40 mm pitch leave a 0.17 mm gap, so the solder-mask dam
    # between them is thinner than any fab will hold. The manufacturer's land
    # pattern is like this on purpose; tell DRC the bridges are allowed
    # rather than fighting it.
    w.line('attr', 'smd', 'allow_soldermask_bridges')
    w.open('fp_text', 'reference', q('REF**'))
    w.line('at', '0', fmt(-m['depth'] - 1.4), '0')
    w.line('layer', q('F.SilkS'))
    w.raw(effects(1.0))
    w.close_inline()
    w.open('fp_text', 'value', q(name))
    w.line('at', '0', fmt(-m['body_d'] / 2.0), '0')
    w.line('layer', q('F.Fab'))
    w.raw(effects(1.0))
    w.close_inline()

    def rect(layer, x0_, y0_, x1_, y1_, wd=0.12):
        for (a, bb, c, d) in ((x0_, y0_, x1_, y0_), (x1_, y0_, x1_, y1_),
                              (x1_, y1_, x0_, y1_), (x0_, y1_, x0_, y0_)):
            w.open('fp_line')
            w.line('start', fmt(a), fmt(bb))
            w.line('end', fmt(c), fmt(d))
            w.line('stroke', '(width %s)' % fmt(wd), '(type solid)')
            w.line('layer', q(layer))
            w.close_inline()

    hw = m['body_w'] / 2.0
    rect('F.Fab', -hw, -m['body_d'], hw, 0.0)
    rect('F.SilkS', -hw - 0.15, -m['body_d'] - 0.15, hw + 0.15, -0.3)
    rect('F.CrtYd', -hw - 0.5, -m['depth'] - 0.4, hw + 0.5, 0.25, 0.05)
    # pin-1 marker, outboard of pin 1 so it survives the fan-out routing
    w.open('fp_circle')
    w.line('center', fmt(xs[1] * 1.32), fmt(m['row_y'] + 1.1))
    w.line('end', fmt(xs[1] * 1.32 + 0.3), fmt(m['row_y'] + 1.1))
    w.line('stroke', '(width 0.12)', '(type solid)')
    w.line('fill', 'solid')
    w.line('layer', q('F.SilkS'))
    w.close_inline()

    for p in range(1, n + 1):
        w.open('pad', q(str(p)), 'smd', 'roundrect')
        w.line('at', fmt(xs[p]), fmt(m['row_y']))
        w.line('size', fmt(m['pad_w']), fmt(m['pad_l']))
        w.line('layers', q('F.Cu'), q('F.Paste'), q('F.Mask'))
        w.line('roundrect_rratio', '0.25')
        w.close_inline()
    # four shell legs in plated slots
    for dx in (-m['leg_dx'], m['leg_dx']):
        for ykey, hkey, pkey in (('leg_rear_y', 'leg_rear_hole', 'leg_rear_pad'),
                                 ('leg_front_y', 'leg_front_hole',
                                  'leg_front_pad')):
            hx, hy = m[hkey]
            px, py = m[pkey]
            w.open('pad', q('SH'), 'thru_hole', 'oval')
            w.line('at', fmt(dx), fmt(m[ykey]))
            w.line('size', fmt(px), fmt(py))
            w.line('drill', 'oval', fmt(hx), fmt(hy))
            w.line('layers', q('*.Cu'), q('*.Mask'))
            w.close_inline()
    # two round locating pegs
    for dx in (-m['peg_dx'], m['peg_dx']):
        w.open('pad', q('SH'), 'thru_hole', 'circle')
        w.line('at', fmt(dx), fmt(m['peg_y']))
        w.line('size', fmt(m['peg_pad']), fmt(m['peg_pad']))
        w.line('drill', fmt(m['peg_drill']))
        w.line('layers', q('*.Cu'), q('*.Mask'))
        w.close_inline()
    w.close_inline()
    return w.text()


MINI_HDMI_FP = 'HDMI_C_Mini_19P_Horizontal_Hybrid'
TYPEA_FP = 'HDMI_A_Amphenol_10029449-x01xLF_Horizontal'
TYPEA_LCSC = 'C427307'
TYPEA_MFR = 'Amphenol ICC 10029449-111RLF'

# Amphenol ICC 10029449-111RLF, LCSC C427307.  Full-size HDMI (Type A) 19P
# receptacle, right angle, hybrid mount: 19 SMT contacts on 0.50 mm pitch plus
# four through-hole shell legs (1.30 mm drill, 14.50 mm apart at the rear and
# 15.70 mm at the front).  Durability 10,000 cycles, mating force 44.1 N max,
# unmating 9.8-39.2 N (Amphenol HDMI Receptacles overview, GS-12-309).
#
# The stock KiCad footprint Connector_Video:HDMI_A_Amphenol_10029449-x01xLF_
# Horizontal is used AS IS.  It was contributed from this exact dash number
# (kicad-footprints PR #2021, "Amphenol_10029449-111RLF HDMI Connector") and
# every value in it was re-checked against Amphenol drawing 10029449 rev Y
# sheet 3: pads 0.30 x 1.90 on 0.50 pitch spanning 9.00 mm, the contact field
# offset 0.25 mm from the shell centreline (pads run +4.75 to -4.25, which is
# what the drawing dimensions as 4.75 / 0.25 - the field really is off-centre,
# which is normal for a Type A right-angle receptacle), four Ø1.30 shell
# holes at (+/-7.85, 0.9) and (+/-7.25, -4.0), rows 4.90 apart.  Only the
# 1.80 mm annular ring and the courtyard are KiCad's own choice.
#
# From the drawing: overall width 15.70 +/-0.15 mm, depth onto the board
# 9.90 +/-0.25 mm, height above the PCB 6.10 +/-0.20 mm.  The footprint origin
# is the body centre and the courtyard front edge is y = +5.00, so the mating
# face is at y = +4.90: place the origin 4.90 mm inboard of the board edge.
TYPEA = dict(body_w=15.70, body_d=9.90, height=6.10, front_offset=4.90,
             crt_w=18.50, crt_back=6.45, crt_front=5.00)

# ==========================================================================
# Part type catalogue.  key -> (stock symbol lib, stock symbol, stock fp lib,
#                               stock fp)
# ==========================================================================

TYPES = {
    'R':        ('Device', 'R', 'Resistor_SMD', 'R_0402_1005Metric'),
    'R0805':    ('Device', 'R', 'Resistor_SMD', 'R_0805_2012Metric'),
    'C':        ('Device', 'C', 'Capacitor_SMD', 'C_0402_1005Metric'),
    'C0805':    ('Device', 'C', 'Capacitor_SMD', 'C_0805_2012Metric'),
    'TP':       ('Connector', 'TestPoint', 'TestPoint', 'TestPoint_Pad_D1.5mm'),
    'TPBIG':    ('Connector', 'TestPoint', 'TestPoint',
                 'TestPoint_THTPad_D2.0mm_Drill1.0mm'),
    'PWRFLAG':  ('power', 'PWR_FLAG', None, None),
    'LVDS_DRV': (None, 'DS90LV047A', 'Package_SO', 'SOIC-16_3.9x9.9mm_P1.27mm'),
    'LVDS_RCV': (None, 'DS90LV048A', 'Package_SO', 'TSSOP-16_4.4x5mm_P0.65mm'),
    'XLAT8':    ('Logic_LevelTranslator', 'SN74AVC8T245PW', 'Package_SO',
                 'TSSOP-24_4.4x7.8mm_P0.65mm'),
    'XLAT4':    ('Logic_LevelTranslator', 'SN74AVC4T245PW', 'Package_SO',
                 'TSSOP-16_4.4x5mm_P0.65mm'),
    'ESD4':     ('Power_Protection', 'TPD4E05U06DQA', 'Package_SON',
                 'USON-10_2.5x1.0mm_P0.5mm'),
    'LDO25':    ('Regulator_Linear', 'ME6211C25M5', 'Package_TO_SOT_SMD',
                 'SOT-23-5'),
    'LDO33':    ('Regulator_Linear', 'AMS1117-3.3', 'Package_TO_SOT_SMD',
                 'SOT-223-3_TabPin2'),
    'HDMI_C':   ('Connector', 'HDMI_C_1.4', None, MINI_HDMI_FP),
    'HDMI_A':   ('Connector', 'HDMI_A_1.4', 'Connector_Video', TYPEA_FP),
    'SKT2x10':  ('Connector_Generic', 'Conn_02x10_Odd_Even',
                 'Connector_PinSocket_2.54mm', 'PinSocket_2x10_P2.54mm_Vertical'),
    'SKT2x03':  ('Connector_Generic', 'Conn_02x03_Odd_Even',
                 'Connector_PinSocket_2.54mm', 'PinSocket_2x03_P2.54mm_Vertical'),
    'SKT2x20':  ('Connector_Generic', 'Conn_02x20_Odd_Even',
                 'Connector_PinSocket_2.54mm', 'PinSocket_2x20_P2.54mm_Vertical'),
    'HDR1x02':  ('Connector_Generic', 'Conn_01x02',
                 'Connector_PinHeader_2.54mm', 'PinHeader_1x02_P2.54mm_Vertical'),
    'HDR1x03':  ('Connector_Generic', 'Conn_01x03',
                 'Connector_PinHeader_2.54mm', 'PinHeader_1x03_P2.54mm_Vertical'),
    'MH':       ('Mechanical', 'MountingHole_Pad', 'MountingHole',
                 'MountingHole_3.2mm_M3_Pad'),
    # Single-gate inverter making ROLE_N = NOT ROLE.  TI SN74LVC1G04DBVR in
    # DBV (SOT-23-5); LCSC C7827, 150,495 in stock and in JLCPCB's assembly
    # library as an Extended part (checked 12 Sep 2026 - no Basic-tier
    # 74LVC1G04 exists in SOT-23-5 at all, from any of the ten
    # manufacturers JLCPCB lists, so the per-unique-Extended-part fee is
    # unavoidable for this one chip).  Pinout 1 NC / 2 A / 3 GND / 4 Y /
    # 5 VCC, taken from the KiCad 74xGxx symbol, which is drawn from the TI
    # DBV datasheet.  NOTE Nexperia's 74LVC1G04GW is a DIFFERENT pinout
    # (1 A / 2 GND / 3 Y / 5 VCC) - do not substitute it without changing
    # INV_PINS below.
    'INV':      ('74xGxx', '74LVC1G04', 'Package_TO_SOT_SMD', 'SOT-23-5'),
    'FIDUCIAL': ('Mechanical', 'Fiducial', 'Fiducial', 'Fiducial_1mm_Mask2mm'),
}

# SN74LVC1G04DBVR pad numbers, so the netlist reads by function.
INV_A, INV_Y, INV_GND, INV_VCC, INV_NC = '2', '4', '3', '5', '1'

CUSTOM_SYMS = ('DS90LV047A', 'DS90LV048A')

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
          r330='C25104',      # 330R  0402, Basic - 742,400 in stock
          r4k7='C25900',      # 4k7   0402, Basic
          r10k='C25744',      # 10k   0402, Basic
          r100k='C25741',     # 100k  0402, Basic
          c100n='C1525',      # 100nF 0402, Basic
          c1u='C52923',       # 1uF   0402, Basic
          c10u='C15525',      # 10uF  0805, Basic
          c22p='C1555',       # 22pF  0402, Basic
          esd='C138714')      # TPD4E05U06DQAR, USON-10

# Silicon, connectors and the hand-fitted sockets.  Same rule: every number
# verified live.  See STATUS.md for what each one replaced.
LC_DRV = 'C206491'        # DS90LV047ATMX/NOPB, quad LVDS driver, SOIC-16
LC_RCV = 'C87137'         # DS90LV048ATMTCX/NOPB, quad LVDS receiver, TSSOP-16
LC_X8 = 'C465742'         # SN74AVC8T245PWR (rev B's C53535 does not exist)
LC_X4 = 'C81461'          # SN74AVC4T245PWR
LC_INV = 'C7827'          # SN74LVC1G04DBVR, SOT-23-5, Extended
LC_LDO25 = 'C194395'      # ME6211C25M5G-N
LC_LDO33 = 'C6186'         # AMS1117-3.3, Basic
LC_HDR = 'C2337'          # 2.54 mm pin header strip
LC_SKT2x20 = 'C5124634'   # BOOMELE 2.54 2x20P vertical female (C50982: no stock)
LC_SKT2x10 = 'C42431860'  # JXTCONN PM2.54-2X10P-H85 vertical 2x10 female
LC_SHUNT = 'C5305'        # jumper shunt for the ROLE strap and the option headers


# ==========================================================================
#  HDMI socket pin maps.  ONE function per socket *type*, and both connector
#  shells use the same function - only the pin-number table differs.
# ==========================================================================
#
# Standard HDMI receptacle pinouts.  Cross-checked against the KiCad
# Connector library symbols HDMI_A_1.4 and HDMI_C_1.4.  Type C differs from
# Type A in three ways: every pair's + leg swaps with its shield, DDC/CEC
# ground moves from pin 17 to pin 13, CEC from 13 to 14, and Reserved/Utility
# from 14 to 17.  SCL (15), SDA (16), +5 V (18) and HPD (19) are the same.
HDMI_A_PINS = {
    'D2_P': '1', 'D2_SH': '2', 'D2_N': '3',
    'D1_P': '4', 'D1_SH': '5', 'D1_N': '6',
    'D0_P': '7', 'D0_SH': '8', 'D0_N': '9',
    'CLK_P': '10', 'CLK_SH': '11', 'CLK_N': '12',
    'CEC': '13', 'UTIL': '14', 'SCL': '15', 'SDA': '16',
    'DDC_GND': '17', 'P5V': '18', 'HPD': '19', 'SHELL': 'SH',
}
HDMI_C_PINS = {
    'D2_SH': '1', 'D2_P': '2', 'D2_N': '3',
    'D1_SH': '4', 'D1_P': '5', 'D1_N': '6',
    'D0_SH': '7', 'D0_P': '8', 'D0_N': '9',
    'CLK_SH': '10', 'CLK_P': '11', 'CLK_N': '12',
    'DDC_GND': '13', 'CEC': '14', 'SCL': '15', 'SDA': '16',
    'UTIL': '17', 'P5V': '18', 'HPD': '19', 'SHELL': 'SH',
}

LANES = ['CLK', 'D0', 'D1', 'D2']   # one clock pair + three data pairs


def hdmi_socket_pins(kind, pfx, five_volt_net, shield_net):
    """Pad-number -> net for one HDMI socket.

    ``kind`` is 'A' or 'C'.  ``pfx`` is the socket's net prefix, e.g. 'O1'.
    The mapping is IDENTICAL for an OUT socket and an IN socket: that is the
    symmetry requirement, and it is why this is one function.
    """
    t = HDMI_A_PINS if kind == 'A' else HDMI_C_PINS
    out = {}
    for lane in LANES:
        out[t[lane + '_P']] = '%s_%s_P' % (pfx, lane)
        out[t[lane + '_N']] = '%s_%s_N' % (pfx, lane)
        out[t[lane + '_SH']] = 'GND'
    out[t['DDC_GND']] = 'GND'
    out[t['SCL']] = '%s_SLOW' % pfx
    # CEC, SDA and Reserved/Utility are genuinely unused.  They are left
    # OPEN, not grounded: on a real HDMI cable they may be wired to a source
    # that would be shorted out.  An open pin needs no ESD clamp either.
    out[t['SDA']] = None
    out[t['CEC']] = None
    out[t['UTIL']] = None
    out[t['HPD']] = '%s_HPD' % pfx
    out[t['P5V']] = five_volt_net
    out[t['SHELL']] = shield_net
    return out


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


def ac_coupling(ref, pfx, lanes, note_extra=''):
    """DC/AC-coupling option and termination for a set of RECEIVED pairs.

    Per pair and per leg: a 100 nF series coupling capacitor (not fitted) in
    parallel with a 0 R link (fitted).  So the board ships DC-coupled and can
    be converted to AC coupling by moving eight 0402 parts per pair without a
    new board.  Per pair: one 100 R differential termination on the receiver
    side of the option, and two not-fitted 4.7 k resistors from the shared
    VBIAS rail, which is what sets the receiver common mode once the DC path
    is broken.

    Cable-side nets are ``<pfx>_<lane>_P/_N``; receiver-side nets are
    ``<pfx>_<lane>_RX_P/_RX_N``.  Only the receiver-side nets touch the
    receiver.  Both halves keep the ``_P``/``_N`` suffix so EasyEDA Pro's
    automatic differential-pair detection finds all of them.
    """
    parts = []
    for lane in lanes:
        for leg in ('P', 'N'):
            cab = '%s_%s_%s' % (pfx, lane, leg)
            rec = '%s_%s_RX_%s' % (pfx, lane, leg)
            parts.append(C(ref('C'), '100nF', cab, rec, lcsc=LC['c100n'],
                           dnp=True,
                           desc='AC-coupling option, %s %s %s leg'
                                % (pfx, lane, leg),
                           note='NOT FITTED. Fit only together with the VBIAS '
                                'network and remove the parallel 0 R link. '
                                'Needs DC-balanced data; the gateware does '
                                'not guarantee that.' + note_extra))
            parts.append(R(ref('R'), '0R', cab, rec, lcsc=LC['r0'],
                           desc='DC-coupled link (default), %s %s %s leg'
                                % (pfx, lane, leg),
                           note='FITTED. Remove to use the AC-coupling '
                                'capacitor in parallel with it.'))
        parts.append(R(ref('R'), '100R', '%s_%s_RX_P' % (pfx, lane),
                       '%s_%s_RX_N' % (pfx, lane), lcsc=LC['r100'],
                       desc='Differential termination, %s %s. Place within '
                            '5 mm of the receiver pins.' % (pfx, lane)))
        for leg in ('P', 'N'):
            parts.append(R(ref('R'), '4k7', 'VBIAS',
                           '%s_%s_RX_%s' % (pfx, lane, leg), lcsc=LC['r4k7'],
                           dnp=True,
                           desc='AC-coupling common-mode bias, %s %s %s leg'
                                % (pfx, lane, leg),
                           note='NOT FITTED. Part of the AC-coupling option.'))
    return parts


def vbias_network(ref):
    """The ~1.05 V common-mode rail used only by the AC-coupling option.

    rev B used 1k8 / 1k0 for 1.18 V.  Both of those LCSC numbers turned out
    to be a different value than the BOM claimed, so the divider is now
    10 k / 4k7 from confirmed Basic parts: 3.3 x 4.7 / 14.7 = 1.055 V, still
    mid-range for the DS90LV048A's 0.05 - 2.35 V input common mode.  The
    divider carries no steady current, because the per-leg 4k7 bias
    resistors sit in common mode, so the higher 3.2 k Thevenin impedance
    costs nothing.
    """
    return [
        R(ref('R'), '10k', '+3V3', 'VBIAS', lcsc=LC['r10k'], dnp=True,
          desc='VBIAS divider top: 10k / 4k7 from +3V3 gives 1.055 V',
          note='NOT FITTED. Part of the AC-coupling option.'),
        R(ref('R'), '4k7', 'VBIAS', 'GND', lcsc=LC['r4k7'], dnp=True,
          desc='VBIAS divider bottom',
          note='NOT FITTED. Part of the AC-coupling option.'),
        C(ref('C'), '100nF', 'VBIAS', 'GND', lcsc=LC['c100n'], dnp=True,
          desc='VBIAS bypass',
          note='NOT FITTED. Part of the AC-coupling option.'),
    ]


def aux_pairs(ref, pfx, term_fitted, role_a_label):
    """The four AUX pairs: strap-selected 100 R terminations only.

    An AUX pair is BIDIRECTIONAL: on the board side a driver output and a
    receiver input meet at one node, and that node goes STRAIGHT to the
    connector pin.  There is deliberately no series link and no AC-coupling
    option on these pairs, unlike the fixed-direction received pairs:

    * a series 0402 in the middle of a pair that is DRIVEN half the time is
      an impedance discontinuity on the outgoing signal, and
    * a series capacitor would break the driver's DC path to the cable and
      leave the FAR end's receiver common mode undefined, because on a
      bidirectional pair there is no always-DC-coupled end to set it.

    So the only thing fitted per pair is the differential termination, and
    which two of the four are fitted is what the ROLE strap selects.  It is a
    build-time choice, not an electrical one: a switched 100 R would need an
    analogue switch, and if BOTH ends terminated a driven pair the driver
    would see 50 R and the differential swing would halve from about 350 mV
    to about 175 mV against the receiver's 100 mV threshold - 75 mV of margin
    over a 2 m cable, which is not enough.

    ``term_fitted`` is the set of lanes this board RECEIVES in its shipped
    role; the other two 100 R positions are left empty.
    """
    parts = []
    for lane in LANES:
        fit = lane in term_fitted
        parts.append(R(ref('R'), '100R', '%s_%s_P' % (pfx, lane),
                       '%s_%s_N' % (pfx, lane), lcsc=LC['r100'],
                       dnp=not fit,
                       desc='AUX %s differential termination. %s in %s.'
                            % (lane, 'FITTED' if fit else 'NOT FITTED',
                               role_a_label),
                       note=('FITTED. This board RECEIVES this pair in its '
                             'shipped role. Place within 5 mm of the '
                             'receiver pins.' if fit else
                             'NOT FITTED. This board DRIVES this pair in its '
                             'shipped role, and the far end terminates it. '
                             'Fit this one and remove the other two if you '
                             'move the ROLE shunt.')))
    return parts


def slow_line_rx(ref, cable_net, sink_net, pull='up'):
    """Receiving end of a single-ended slow wire: series link, DNP RC pad,
    and a defined idle level while no cable is plugged in."""
    parts = [R(ref('R'), '0R', cable_net, sink_net, lcsc=LC['r0'],
               desc='Slow-line series link, %s' % cable_net,
               note='FITTED. Cut to isolate the slow line.')]
    if pull == 'up':
        parts.append(R(ref('R'), '10k', sink_net, '+3V3', lcsc=LC['r10k'],
                       desc='Idles %s in the UART mark state with no cable'
                            % sink_net))
    else:
        parts.append(R(ref('R'), '10k', sink_net, 'GND', lcsc=LC['r10k'],
                       desc='Holds %s low with no cable, so the far end reads '
                            'a break rather than random data' % sink_net))
    parts.append(C(ref('C'), '22pF', sink_net, 'GND', lcsc=LC['c22p'],
                   dnp=True,
                   desc='Optional ringing damper on %s' % sink_net,
                   note='NOT FITTED. Fit if the unterminated cable wire rings '
                        'enough to double-clock the receiver.'))
    return parts


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
        node = K.parse(build_mini_hdmi_fp(fpname))[0]
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
#  BOARD A  -  hl2-bridge   (HL2 side: 2 x mini HDMI OUT + 1 x mini HDMI IN)
# ==========================================================================
#
# Local origin (0,0) == Hermes-Lite2 main-board coordinate (70.50, 74.00) mm,
# so local x = HL2_x - 70.50 and local y = HL2_y - 74.00.  Verified twice
# against hardware/hl/hermeslite.kicad_pcb:
#   DB1  = footprint HERMESLITE:10x2 at (75.31, 89.39) rotated 270 deg
#          -> odd pins at HL2 x 74.04, even at 76.58, pin 1/2 at y 77.96,
#             stepping +2.54 to pin 19/20 at y 100.82
#   DB12 = footprint HERMESLITE:3x2 at (83.5, 90.0) not rotated
#          -> odd pins at HL2 x 83.50, even at 86.04, rows y 87.46 / 90.00 /
#             92.54
# so in local coordinates: DB1 pin 1 = (3.54, 3.96), DB12 pin 1 = (13.00,
# 13.46).  The two headers are NOT on a common 0.1 inch grid.
BOARD_A_W = 48.0
BOARD_A_H = 66.0

# Where board A's local origin sits on the Hermes-Lite 2 board.  The corridor
# left free by the N2ADR filter board is HL2 x 70.00 to 120.05, so a 48.00 mm
# board can sit anywhere from x 70.00 to 72.05.  70.50 leaves 1.55 mm to the
# filter board's edge; moving it up to 1.5 mm further right buys the same
# amount of clearance between the leftmost cable boot and the extrusion's
# inner wall, at the cost of that gap.  DESIGN_NOTES.md section 6.2 has both
# numbers.  CHANGE THIS ONE CONSTANT AND REGENERATE to move the board.
HL2_ORIGIN = (70.50, 74.00)

# DB1 and DB12 hole positions, derived from the HL2 PCB rather than written
# down.  DB1  = HERMESLITE:10x2 at (75.31, 89.39) rot 270 -> odd pins at HL2
# x 74.04, even at 76.58, pin 1/2 at y 77.96 stepping +2.54.  DB12 =
# HERMESLITE:3x2 at (83.50, 90.00) rot 0 -> odd x 83.50, even 86.04, rows
# y 87.46 / 90.00 / 92.54.  Both read out of hardware/hl/hermeslite.kicad_pcb
# and re-verified against the Excellon export; tools/check_geometry.py
# recomputes them independently.
DB1_PIN1 = (round(74.04 - HL2_ORIGIN[0], 3), round(77.96 - HL2_ORIGIN[1], 3))
DB12_PIN1 = (round(83.50 - HL2_ORIGIN[0], 3), round(87.46 - HL2_ORIGIN[1], 3))

# Socket centre lines along the front edge.  17.40 mm is the LARGEST pitch the
# 48 mm corridor allows: the outer shell-leg pads reach 6.05 mm either side of
# a socket centre, so 24.00 +/- 17.40 +/- 6.05 spans 0.55 .. 47.45 mm, leaving
# 0.55 mm of copper-to-edge against JLCPCB's 0.30 mm minimum.  The pitch is
# set by the CABLE BOOT, not by the socket (the bodies are only 11.20 mm
# wide).  DESIGN_NOTES.md section 6 has the arithmetic.
MINI_PITCH = 17.40
MINI_X = [BOARD_A_W / 2.0 - MINI_PITCH, BOARD_A_W / 2.0,
          BOARD_A_W / 2.0 + MINI_PITCH]
MINI_EDGE_Y = BOARD_A_H          # the front board edge; footprint origin



def board_a():
    OUT = [(0, 0), (BOARD_A_W, 0), (BOARD_A_W, BOARD_A_H), (0, BOARD_A_H)]
    b = Board('hl2-bridge',
              'Hermes Lite 2 <-> Gowin HDMI bridge, board A (HL2 side), rev C',
              OUT, (BOARD_A_W, BOARD_A_H),
              origin_note='local (0,0) = HL2 main board (70.50, 74.00)')
    ref = RefGen()

    # ---------------------------------------------------------------- HL2
    # DB1 socket.  The link uses positions 1-6, 9, 11, 15 and 17; the
    # STACK-THROUGH tails exist ONLY on the other ten positions - 7, 8, 10,
    # 12, 13, 14, 16, 18, 19, 20 - so a companion board stacked on top
    # physically cannot reach a link signal.  On the Samtec long-tail socket
    # that means clipping ten tails flush before fitting it.
    b.add(Part('J1', 'SKT2x10', 'DB1 2x10 stack-through', {
        '1': 'HL2_AX_G2CLK_HDR', '2': 'HL2_O_D0', '3': 'HL2_O_D1',
        '4': 'HL2_AX_G2DAT', '5': 'HL2_O_D2', '6': 'HL2_AX_G1CLK',
        '7': 'VLVDS', '8': 'VLVDS',
        '9': 'HL2_CLK_RAW', '10': None, '11': 'HL2_I_D0', '12': None,
        '13': 'GND', '14': 'GND', '15': 'HL2_I_D1', '16': 'SCL1',
        '17': 'HL2_I_D2', '18': 'SDA1', '19': 'DB1_3V3', '20': 'DB1_3V3',
    }, lcsc='',
        mfr='Samtec SSQ-120-01-G-D (or SSQ-120-01-T-D / Harwin M20), '
            '2.54mm 2x10 female, ~10mm tails',
        desc='Mates HL2 DB1. HAND SOLDERED - LCSC stocks no long-tail 2x10 '
             'socket at all (all seven of their 2x10 female listings are '
             'ordinary ~3.2 mm pins), so this is not a JLCPCB assembly line '
             'item. The ordinary vertical socket LCSC C42431860 fits the same '
             'holes if you do not want to stack anything',
        at=DB1_PIN1, rot=0, layer='B.Cu', mirror=True, dnp=True,
        note='NOT PLACED BY JLCPCB - hand soldered, bottom side. Clip the '
             'tails of positions 1,2,3,4,5,6,9,11,15,17 FLUSH before '
             'fitting: those ten carry the link and must not be passed up to '
             'a stacked board. The ten that remain are 7,8 (Vlvds), 10,12 '
             '(CW/PTT), 13,14 (GND), 16,18 (SCL1/SDA1) and 19,20 (+3V3).'))

    b.add(Part('J2', 'SKT2x03', 'DB12 2x03 socket', {
        '1': 'HL2_SLOW_OUT', '2': 'HL2_AX_G1DAT', '3': 'GND', '4': 'GND',
        '5': 'HL2_ROLE_IN', '6': 'HL2_INCLK',
    }, lcsc='', mfr='2.54mm 2x3P female header, VERTICAL (top entry)',
        desc='Mates HL2 DB12. HAND SOLDERED - LCSC has no vertical 2x3 '
             'female socket (their vertical female headers start at 2x4, and '
             'the 2x3 they do list, C99515, is side entry). Buy a 2x4 and cut '
             'it down, or source a 2x3 outside LCSC. NOTE pin 5 = FPGA '
             'PIN_89 (the ROLE strap read) and pin 6 = FPGA PIN_88 (the IN '
             'clock); rev A had these two swapped',
        at=DB12_PIN1, rot=0, layer='B.Cu', mirror=True, dnp=True,
        note='NOT PLACED BY JLCPCB - hand soldered, bottom side. DB12 is '
             'marked "do not install" in the HL2 BOM, so the male header on '
             'the radio almost certainly has to be soldered too.'))

    # ---------------------------------------------------------- the sockets
    # OUT and IN are the two OUTER sockets, so the two-radio case (which uses
    # only those two) never has three cable boots side by side.
    socket_note = ('Hybrid mount: reflow the SMT contacts, then solder the '
                   'four through-hole shell legs. Mating face is flush with '
                   'the board edge.')
    b.add(Part('J3', 'HDMI_C', 'OUT (mini HDMI)',
               hdmi_socket_pins('C', 'O', 'O_5V_PIN', 'SHLD1'),
               lcsc='C2682170', mfr='XKB Connection A71-05H4-111N1',
               desc='OUT, cable 1: board A drives the 153.6 MHz link clock '
                    'and lanes 0,1,2 at 307.2 Mbit/s, plus the status UART '
                    'on SCL. All four pairs driven',
               at=(MINI_X[0], MINI_EDGE_Y), rot=0, note=socket_note))
    b.add(Part('J4', 'HDMI_C', 'AUX (mini HDMI)',
               hdmi_socket_pins('C', 'AX', 'AX_5V_PIN', 'SHLD2'),
               lcsc='C2682170', mfr='XKB Connection A71-05H4-111N1',
               desc='AUX, cable 3: bidirectional, full duplex. G1 = clock '
                    'pair + data 0 pair, G2 = data 1 pair + data 2 pair. The '
                    'ROLE strap decides which group this board drives. SCL, '
                    'HPD and +5 V are test pads only',
               at=(MINI_X[1], MINI_EDGE_Y), rot=0, note=socket_note))
    b.add(Part('J5', 'HDMI_C', 'IN (mini HDMI)',
               hdmi_socket_pins('C', 'I', 'I_5V_PIN', 'SHLD3'),
               lcsc='C2682170', mfr='XKB Connection A71-05H4-111N1',
               desc='IN, cable 2: board A receives the reverse clock and '
                    'reverse lanes 0,1,2 at 307.2 Mbit/s. Its SCL is a test '
                    'pad only in rev C - PIN_89 reads the ROLE strap now, so '
                    'there is no destination for a received slow line',
               at=(MINI_X[2], MINI_EDGE_Y), rot=0, note=socket_note))

    # ================================================== the ROLE strap
    # One 1x3 header with ONE shunt, plus one single-gate inverter, gives two
    # levels that CANNOT disagree.  PINMAP.md 2.4 has the full argument; the
    # short version is that any independently settable pair of levels allows
    # "both low", which enables a translator port toward a pin the gateware is
    # driving as an output - CMOS against CMOS on PIN_72 and PIN_80.
    b.add(Part('J9', 'HDR1x03', 'ROLE', {
        '1': '+3V3', '2': 'ROLE', '3': 'GND',
    }, lcsc=LC_HDR, mfr='2.54mm 1x3P pin header',
        desc='ROLE strap, ONE shunt: 1-2 = ROLE A (this board drives AUX G1, '
             'receives G2) which is how board A ships; 2-3 = ROLE B (drives '
             'G2, receives G1). The two boards of a link must be strapped '
             'differently',
        at=(45.0, 24.0), rot=0,
        note='Fit ONE shunt (LCSC C5305). Board A ships 1-2 = ROLE A. With '
             'no shunt at all the 100k pull-down makes it ROLE B, which is '
             'a safe state, not a floating one.'))
    b.add(Part('U11', 'INV', '74LVC1G04', {
        INV_A: 'ROLE', INV_Y: 'ROLE_N', INV_GND: 'GND', INV_VCC: '+3V3',
        INV_NC: None,
    }, lcsc=LC_INV, mfr='SN74LVC1G04DBVR',
        desc='Single-gate inverter: ROLE_N = NOT ROLE. This one part is what '
             'makes the complement a property of the circuit instead of a '
             'property of the user remembering to move two shunts the same '
             'way',
        at=(38.0, 13.5), rot=0,
        note='SOT-23-5, TI DBV pinout (1 NC, 2 A, 3 GND, 4 Y, 5 VCC). '
             "Nexperia's 74LVC1G04GW has a DIFFERENT pinout - do not "
             'substitute it.'))

    # ------------------------------------------------- 2.5 V -> 3.3 V shift
    # Every HL2 output that feeds an LVDS driver input goes through ONE
    # package, so the link clock, the three OUT lanes and all four AUX pins
    # pick up the same propagation delay.  The OUT clock (PIN_98) is a 3.3 V
    # pin, above the A-side absolute maximum of VCCA + 0.5 V, so it arrives
    # through a 100 R / 660 R divider first.  DESIGN_NOTES.md 3.2.
    x8 = {'1': '+2V5', '23': '+3V3', '24': '+3V3',
          '11': 'GND', '12': 'GND', '13': 'GND',
          '2': '+2V5',          # DIR high (VCCA referenced) = A -> B
          '22': 'GND'}          # OE* low = enabled
    x8_map = [
        ('HL2_CLK', 'DRVI_O_CLK'), ('HL2_O_D0', 'DRVI_O_D0'),
        ('HL2_O_D1', 'DRVI_O_D1'), ('HL2_O_D2', 'DRVI_O_D2'),
        ('HL2_AX_G1CLK', 'DRVI_AX_CLK'), ('HL2_AX_G1DAT', 'DRVI_AX_D0'),
        ('HL2_AX_G2CLK', 'DRVI_AX_D1'), ('HL2_AX_G2DAT', 'DRVI_AX_D2'),
    ]
    for i, (a, bn) in enumerate(x8_map, start=1):
        x8[X8_A[i]] = a
        x8[X8_B[i]] = bn
    b.add(Part('U1', 'XLAT8', 'SN74AVC8T245PW', x8, lcsc=LC_X8,
               mfr='SN74AVC8T245PWR',
               desc='8-bit dual-supply level translator, VCCA 2.5 V / '
                    'VCCB 3.3 V. Gives the HL2 2.5 V outputs 370 mV of '
                    'GUARANTEED margin into the LVDS driver inputs, which a '
                    'direct connection does not have. All 8 channels used: '
                    'OUT clock + 3 OUT lanes + all 4 AUX pins',
               at=(22.0, 6.0), rot=90,
               note='DIR tied to VCCA (+2V5) = A->B, OE* tied low - ALWAYS '
                    'enabled. The four AUX channels sit on nets that this '
                    "board's own 4-bit translators drive when the HL2 pin is "
                    'an input; a translator A-side input is a ~5 pF load and '
                    'never a driver, so that is not contention. What decides '
                    'whether an AUX signal reaches the cable is the LVDS '
                    "driver's EN, not this part."))

    # ------------------------------------------------------- LVDS drivers
    # THREE drivers, because board A needs three independent enable domains
    # and the DS90LV047A has one enable per package:
    #   U2  OUT     4 channels, always enabled
    #   U3  AUX G1  2 channels, enabled by ROLE
    #   U4  AUX G2  2 channels, enabled by ROLE_N
    drv = [
        ('U2', (6.6, 47.5), '+3V3', {
            'CLK': ('DRVI_O_CLK', 'O_CLK'), 'D0': ('DRVI_O_D0', 'O_D0'),
            'D1': ('DRVI_O_D1', 'O_D1'), 'D2': ('DRVI_O_D2', 'O_D2')},
         'OUT: the forward cable. All four channels used, none spare. EN '
         'tied high - this socket is always driven',
         'EN tied to +3V3 and EN* to GND: permanently enabled.'),
        ('U3', (16.5, 47.5), 'ROLE', {
            'CLK': ('DRVI_AX_CLK', 'AX_CLK'),
            'D0': ('DRVI_AX_D0', 'AX_D0')},
         'AUX group G1 (clock pair + data 0 pair). Two channels used, two '
         'spare. EN = ROLE, so this pair is driven only in ROLE A',
         'EN = ROLE. Enabled in ROLE A, tri-stated in ROLE B. Channels 3 and '
         '4 are unused: inputs grounded, outputs left open.'),
        ('U4', (24.0, 47.5), 'ROLE_N', {
            'CLK': ('DRVI_AX_D1', 'AX_D1'),
            'D0': ('DRVI_AX_D2', 'AX_D2')},
         'AUX group G2 (data 1 pair + data 2 pair). Two channels used, two '
         'spare. EN = ROLE_N, so this pair is driven only in ROLE B',
         'EN = ROLE_N. Enabled in ROLE B, tri-stated in ROLE A. ROLE_N comes '
         'from U11 and carries a 10k pull-UP, so a missing or dead inverter '
         'leaves this driver enabled but its G2 translator port toward the '
         'HL2 DISABLED - the auxiliary link fails to work and nothing is '
         'stressed. Channels 3 and 4 unused.'),
    ]
    for ref_u, at, en, chmap, desc, note in drv:
        pins = {'1': en, '4': '+3V3', '5': 'GND', '8': 'GND'}
        for i, lane in enumerate(LANES):
            if lane in chmap:
                src, pfxlane = chmap[lane]
                pins[DRV_IN[i]] = src
                pins[DRV_P[i]] = '%s_P' % pfxlane
                pins[DRV_N[i]] = '%s_N' % pfxlane
            else:
                pins[DRV_IN[i]] = 'GND'
                pins[DRV_P[i]] = None
                pins[DRV_N[i]] = None
        b.add(Part(ref_u, 'LVDS_DRV', 'DS90LV047A', pins, lcsc=LC_DRV,
                   mfr='DS90LV047ATMX/NOPB',
                   desc='Quad LVDS driver, 400 Mbps, SOIC-16. ' + desc,
                   at=at, rot=0, note=note))

    # ------------------------------------------------------- LVDS receivers
    # TWO receivers.  A receiver is high-impedance on the LINE, so the AUX
    # receiver can sit across all four AUX pairs in both roles; what has to
    # tri-state is its OUTPUT path toward the HL2, and that is done by the
    # 4-bit translator ports below.
    pins = {'9': 'RXEN_N', '16': '+3V3', '12': 'GND', '13': '+3V3'}
    rxo = {'CLK': 'RXO_I_CLK', 'D0': 'RXO_I_D0', 'D1': 'RXO_I_D1',
           'D2': 'RXO_I_D2'}
    for i, lane in enumerate(LANES):
        pins[RCV_P[i]] = 'I_%s_RX_P' % lane
        pins[RCV_N[i]] = 'I_%s_RX_N' % lane
        pins[RCV_OUT[i]] = rxo[lane]
    b.add(Part('U5', 'LVDS_RCV', 'DS90LV048A', pins, lcsc=LC_RCV,
               mfr='DS90LV048ATMTCX/NOPB',
               desc='Quad LVDS receiver, 400 Mbps, TSSOP-16. Receives socket '
                    'IN: reverse clock and reverse lanes 0,1,2. All four '
                    'channels used',
               at=(41.4, 47.5), rot=0,
               note='EN* = RXEN_N, gated by the IN cable detect through J7, '
                    'so the stock HL2 gateware driving DB1 11/15/17 as LED '
                    'outputs cannot meet this receiver driving the same '
                    'pins.'))

    pins = {'9': 'GND', '16': '+3V3', '12': 'GND', '13': '+3V3'}
    rxo = {'CLK': 'RXO_AX_CLK', 'D0': 'RXO_AX_D0', 'D1': 'RXO_AX_D1',
           'D2': 'RXO_AX_D2'}
    for i, lane in enumerate(LANES):
        pins[RCV_P[i]] = 'AX_%s_P' % lane
        pins[RCV_N[i]] = 'AX_%s_N' % lane
        pins[RCV_OUT[i]] = rxo[lane]
    b.add(Part('U6', 'LVDS_RCV', 'DS90LV048A', pins, lcsc=LC_RCV,
               mfr='DS90LV048ATMTCX/NOPB',
               desc='Quad LVDS receiver, 400 Mbps, TSSOP-16. Sits across ALL '
                    'FOUR AUX pairs in both roles - the two it receives and '
                    'the two its own drivers drive',
               at=(32.5, 47.5), rot=0,
               note='EN tied high, EN* tied low: ALWAYS enabled, in both '
                    'roles. That is deliberate and it is safe. A receiver '
                    'input is high impedance, so listening to a pair this '
                    'board is also driving costs nothing; the outputs for '
                    'the driven group simply go to a translator port that is '
                    'disabled, so they reach no HL2 pin.'))

    # --------------------------- 3.3 V -> 2.5 V shift into the HL2's pins
    # U7 port 1: the IN clock and the ROLE level, always on.
    # U7 port 2: AUX G2 toward the HL2, OE* = ROLE_N.
    # U8 port 1: AUX G1 toward the HL2, OE* = ROLE.
    # U8 port 2: unused and disabled.
    #
    # THE INVARIANT, and it is the whole safety argument: for each group the
    # LVDS driver's active-HIGH EN and the translator port's active-LOW OE*
    # are THE SAME NET.  So the group is either driven onto the cable (EN
    # high => OE* high => port off) or driven toward the HL2 (EN low => OE*
    # low => port on), never both, for ANY level on that net - including a
    # stuck one.  tools/check_netlist.py asserts exactly this.
    x4a = {'1': '+3V3', '16': '+2V5', '8': 'GND', '9': 'GND',
           '2': '+3V3', '3': '+3V3',       # 1DIR, 2DIR high = A -> B
           '14': 'ROLE_N', '15': 'GND'}    # 2OE* = ROLE_N; 1OE* always on
    x4a[X4_A[1]] = 'RXO_I_CLK'
    x4a[X4_B[1]] = 'X_INCLK25'
    x4a[X4_A[2]] = 'ROLE'
    x4a[X4_B[2]] = 'X_ROLE25'
    x4a[X4_A[3]] = 'RXO_AX_D1'
    x4a[X4_B[3]] = 'X_AXG2CLK25'
    x4a[X4_A[4]] = 'RXO_AX_D2'
    x4a[X4_B[4]] = 'X_AXG2DAT25'
    b.add(Part('U7', 'XLAT4', 'SN74AVC4T245PW', x4a, lcsc=LC_X4,
               mfr='SN74AVC4T245PWR',
               desc='4-bit dual-supply level translator, VCCA 3.3 V / '
                    'VCCB 2.5 V. Port 1 (always on) = the IN clock into '
                    'PIN_88 and the ROLE level into PIN_89. Port 2 = AUX '
                    'group G2 toward the HL2, enabled only in ROLE A',
               at=(31.0, 6.0), rot=90,
               note='HL2 PIN_88 and PIN_89 are input-only pins in a 2.5 V '
                    'bank whose PCI clamp would inject DC into the HL2 2.5 V '
                    'rail if driven at 3.3 V. 1OE* = GND (always enabled), '
                    '2OE* = ROLE_N: the G2 port drives PIN_72 and PIN_80 '
                    'only in ROLE A, which is exactly when the gateware has '
                    'those two pins as inputs.'))

    x4b = {'1': '+3V3', '16': '+2V5', '8': 'GND', '9': 'GND',
           '2': '+3V3', '3': '+3V3',        # 1DIR, 2DIR high = A -> B
           '14': '+3V3', '15': 'ROLE'}      # 2OE* high = off; 1OE* = ROLE
    x4b[X4_A[1]] = 'RXO_AX_CLK'
    x4b[X4_B[1]] = 'X_AXG1CLK25'
    x4b[X4_A[2]] = 'RXO_AX_D0'
    x4b[X4_B[2]] = 'X_AXG1DAT25'
    x4b[X4_A[3]] = 'GND'
    x4b[X4_B[3]] = 'X_SP1'
    x4b[X4_A[4]] = 'GND'
    x4b[X4_B[4]] = 'X_SP2'
    b.add(Part('U8', 'XLAT4', 'SN74AVC4T245PW', x4b, lcsc=LC_X4,
               mfr='SN74AVC4T245PWR',
               desc='4-bit dual-supply level translator, VCCA 3.3 V / '
                    'VCCB 2.5 V. Port 1 = AUX group G1 toward the HL2, '
                    'enabled only in ROLE B. Port 2 is unused',
               at=(38.0, 6.0), rot=90,
               note='1OE* = ROLE: the G1 port drives PIN_85 and PIN_87 only '
                    'in ROLE B, which is exactly when the gateware has those '
                    'two pins as inputs. Port 2 is disabled (2OE* to +3V3) '
                    'with its inputs grounded and its outputs on test pads.'))

    # ------------------------------------------------------------- power
    b.add(Part('U9', 'LDO25', 'ME6211C25M5G', {
        '1': '+3V3', '2': 'GND', '3': '+3V3', '5': '+2V5',
    }, lcsc=LC_LDO25, mfr='ME6211C25M5G-N',
        desc='2.5 V 400 mA LDO. Supplies only the 2.5 V sides of the three '
             'translators', at=(24.0, 13.5)))
    b.add(Part('U10', 'LDO33', 'AMS1117-3.3', {
        '1': 'GND', '2': 'LDO3V3', '3': 'P5V_IN',
    }, lcsc=LC_LDO33, mfr='AMS1117-3.3',
        desc='Optional 3.3 V from the IN socket\'s +5 V pin. NOT the default '
             'supply: see DESIGN_NOTES.md 5', at=(37.5, 21.5), dnp=True,
        note='NOT FITTED by default. Board A normally runs from HL2 DB1 '
             'pins 19/20. In the two-radio configuration there is no 5 V '
             'source at all.'))

    b.add(Part('J6', 'HDR1x03', '3V3 SRC', {
        '1': 'DB1_3V3', '2': '+3V3', '3': 'LDO3V3',
    }, lcsc=LC_HDR, mfr='2.54mm 1x3P pin header',
        desc='Board supply select: 1-2 = HL2 DB1 +3V3 (DEFAULT), 2-3 = the '
             'on-board LDO fed from the IN socket +5 V pin',
        at=(45.0, 6.0), rot=0))
    b.add(Part('J7', 'HDR1x03', 'RX MODE', {
        '1': '+3V3', '2': 'RXEN_N', '3': 'I_HPD',
    }, lcsc=LC_HDR, mfr='2.54mm 1x3P pin header',
        desc='IN receiver enable: 2-3 = auto, enabled only while a cable is '
             'in the IN socket (DEFAULT); 1-2 = force disabled; no shunt = '
             'always enabled. Does NOT affect the AUX receiver, which is '
             'always on',
        at=(45.0, 15.0), rot=0))
    b.add(Part('J8', 'HDR1x02', 'GND CLIP', {'1': 'GND', '2': 'GND'},
               lcsc=LC_HDR, mfr='2.54mm 1x2P pin header',
               desc='Ground clip / scope reference', at=(45.0, 33.0),
               rot=0))

    # -------------------------------------------------------------- ESD
    lines = []
    for pfx in ('O', 'AX', 'I'):
        for lane in LANES:
            lines += ['%s_%s_P' % (pfx, lane), '%s_%s_N' % (pfx, lane)]
        lines += ['%s_SLOW' % pfx, '%s_HPD' % pfx, '%s_5V_PIN' % pfx]
    arr, _ = esd_arrays('D', 1, lines,
                        'Place within 5 mm of the HDMI connector pins, on the '
                        'connector side of everything else.')
    b.add(*arr)

    # ------------------------------------------- resistors, links, options
    rs = []
    rs.append(R('R1', '0R', 'HL2_AX_G2CLK_HDR', 'HL2_AX_G2CLK',
                lcsc=LC['r0'],
                desc='SL_D0: cuttable link on DB1 pin 1. That HL2 net reaches '
                     'PIN_72 only through the HL2 jumper J25 and also carries '
                     'uFL pad CL8, an unterminated stub no bridge board can '
                     'remove',
                note='FITTED. Cut to isolate board A from DB1 pin 1. HL2 '
                     'jumper J25 must be CLOSED or the AUX G2 clock is '
                     'dead.'))
    # OUT clock divider: 3.3 V PIN_98 down to 2.77 V for the translator A
    # side.  100 R series plus 660 R shunt as two 330 R in series, because
    # 330 R is the JLCPCB Basic part in that range and 100/330 alone would
    # have drawn 7.25 mA and forced PIN_98 to its 16 mA drive setting.
    rs.append(R('R2', '100R', 'HL2_CLK_RAW', 'HL2_CLK', lcsc=LC['r100'],
                desc='OUT clock divider, series leg. 3.3 V PIN_98 -> 2.77 V, '
                     '1.14 V over the translator threshold and 230 mV under '
                     'its 3.0 V absolute maximum'))
    rs.append(R('R3', '330R', 'HL2_CLK', 'CLKDIV_MID', lcsc=LC['r330'],
                desc='OUT clock divider, shunt leg 1 of 2. 660 R total: '
                     '4.2 mA from PIN_98, inside its 8 mA drive setting; '
                     'Thevenin 87 ohm; 0.77 ns into the translator input'))
    rs.append(R('R4', '330R', 'CLKDIV_MID', 'GND', lcsc=LC['r330'],
                desc='OUT clock divider, shunt leg 2 of 2'))
    # Pull-downs so every 2.5 V net into the translator is DEFINED while
    # nothing drives it, including the four bidirectional AUX pins.  The OUT
    # clock does NOT get one: the HL2's own LED pull-up plus the divider
    # already define it, and a pull-down there would park the node in the
    # translator's forbidden band.
    for net, why in (('HL2_O_D0', 'OUT lane 0'), ('HL2_O_D1', 'OUT lane 1'),
                     ('HL2_O_D2', 'OUT lane 2'),
                     ('HL2_AX_G1CLK', 'AUX G1 clock, bidirectional'),
                     ('HL2_AX_G1DAT', 'AUX G1 data, bidirectional'),
                     ('HL2_AX_G2CLK', 'AUX G2 clock, bidirectional'),
                     ('HL2_AX_G2DAT', 'AUX G2 data, bidirectional')):
        rs.append(R(ref('R'), '10k', net, 'GND', lcsc=LC['r10k'],
                    desc='Defines %s (%s) while nothing drives it - the HL2 '
                         'FPGA unconfigured, or the local translator port '
                         'disabled by the strap' % (net, why)))
    # translator bypass links, so the whole level-shift stage can be removed
    for a, bn in x8_map:
        rs.append(R(ref('R'), '0R', a, bn, lcsc=LC['r0'], dnp=True,
                    desc='Translator bypass, %s straight to %s' % (a, bn),
                    note='NOT FITTED. Fitting all eight and removing U1 falls '
                         'back to connecting the HL2 2.5 V outputs directly '
                         'to the LVDS drivers, which works in practice but '
                         'has 0 mV of guaranteed margin (DESIGN_NOTES.md '
                         '3.2). Also remove R3/R4 if you bypass the clock.'))
    # IN lanes into the HL2's 3.3 V bank
    for i, (a, c) in enumerate([('RXO_I_D0', 'HL2_I_D0'),
                                ('RXO_I_D1', 'HL2_I_D1'),
                                ('RXO_I_D2', 'HL2_I_D2')]):
        rs.append(R(ref('R'), '0R', a, c, lcsc=LC['r0'],
                    desc='IN lane %d into DB1 (3.3 V bank). 0402 pads take '
                         '22 R instead if damping is wanted' % i))
    # the 2.5 V translator outputs into the HL2's pins
    for a, c, why in (
            ('X_INCLK25', 'HL2_INCLK',
             'IN clock (2.5 V) into HL2 PIN_88 = DB12 pin 6'),
            ('X_ROLE25', 'HL2_ROLE_IN',
             'the ROLE level (2.5 V) into HL2 PIN_89 = DB12 pin 5, so the '
             'gateware knows its own role and sets its four AUX pin '
             'directions to match'),
            ('X_AXG1CLK25', 'HL2_AX_G1CLK',
             'AUX G1 clock (2.5 V) into HL2 PIN_85 = DB1 pin 6, in ROLE B '
             'only'),
            ('X_AXG1DAT25', 'HL2_AX_G1DAT',
             'AUX G1 data (2.5 V) into HL2 PIN_87 = DB12 pin 2, in ROLE B '
             'only'),
            ('X_AXG2CLK25', 'HL2_AX_G2CLK',
             'AUX G2 clock (2.5 V) into HL2 PIN_72 = DB1 pin 1, in ROLE A '
             'only'),
            ('X_AXG2DAT25', 'HL2_AX_G2DAT',
             'AUX G2 data (2.5 V) into HL2 PIN_80 = DB1 pin 4, in ROLE A '
             'only. PIN_80 is VREFB5N0 with ~21 pF of pin capacitance and is '
             'the slowest lane in the design')):
        rs.append(R(ref('R'), '0R', a, c, lcsc=LC['r0'], desc=why))
    rs.append(R(ref('R'), '100R', 'HL2_SLOW_OUT', 'O_SLOW', lcsc=LC['r100'],
                desc='Status UART out of DB12-1 (2.5 V) onto the OUT socket '
                     'SCL. Source damping for an unterminated cable wire'))
    rs.append(R(ref('R'), '100R', 'O_HPD', 'GND', lcsc=LC['r100'],
                desc='OUT HPD to ground so the far end detects the cable. '
                     '100 R against the far 10 k gives 0.033 V, at 0.33 mA '
                     'of idle current'))
    rs.append(R(ref('R'), '10k', 'I_HPD', '+3V3', lcsc=LC['r10k'],
                desc='IN cable detect pull-up; LOW = cable plugged in'))
    rs.append(R(ref('R'), '100k', 'RXEN_N', 'GND', lcsc=LC['r100k'],
                desc='Holds the IN receiver enabled when J7 has no shunt, so '
                     '"no shunt" is a defined state rather than a floating '
                     'enable pin'))
    rs.append(R(ref('R'), '100k', 'ROLE', 'GND', lcsc=LC['r100k'],
                desc='Makes "no shunt on J9" mean ROLE B rather than a '
                     'floating inverter input. 33 uA through the shunt in '
                     'the ROLE A position'))
    rs.append(R(ref('R'), '10k', 'ROLE_N', '+3V3', lcsc=LC['r10k'],
                desc='ROLE_N pull-UP. THE DIRECTION MATTERS: if U11 is '
                     'missing, unpowered or dead, ROLE_N reads HIGH, which '
                     'DISABLES the G2 translator port toward the HL2. The '
                     'auxiliary link then does not work and nothing is '
                     'stressed. A pull-down would have enabled it instead'))
    rs.append(R(ref('R'), '0R', 'I_5V_PIN', 'P5V_IN', lcsc=LC['r0'], dnp=True,
                desc='SL_5V: lets the IN socket\'s +5 V pin feed U10',
                note='NOT FITTED. See DESIGN_NOTES.md 5 for why this is not '
                     'the default.'))
    rs.append(R(ref('R'), '0R', 'VLVDS', '+2V5', lcsc=LC['r0'], dnp=True,
                desc='SL_VLVDS: reference the translators\' 2.5 V side to the '
                     "HL2's own Vlvds rail (DB1 pins 7/8) instead of U9",
                note='NOT FITTED. Do not fit together with U9. Electrically '
                     'ideal - the thresholds then track the FPGA bank supply '
                     'exactly - but it draws ~10 mA from the HL2 TPS730 whose '
                     'headroom is unverified.'))
    for i, sh in enumerate(('SHLD1', 'SHLD2', 'SHLD3'), start=1):
        rs.append(R(ref('R'), '0R', sh, 'GND', lcsc=LC['r0'], big=True,
                    desc='Socket %d shell to board ground. 0805 so the shield '
                         'can be lifted if a ground loop appears' % i))
    b.add(*rs)

    # DC/AC coupling option and terminations on the four RECEIVED IN pairs
    b.add(*ac_coupling(ref, 'I', LANES))
    b.add(*vbias_network(ref))
    # The four AUX pairs: strap-selected terminations, nothing else in line.
    # Board A ships ROLE A, so it RECEIVES G2 = the D1 and D2 pairs.
    b.add(*aux_pairs(ref, 'AX', {'D1', 'D2'}, 'ROLE A (how board A ships)'))

    # ------------------------------------------------------- decoupling
    cs = [
        ('100nF', '+3V3', 'U1 VCCB', LC['c100n'], False),
        ('100nF', '+2V5', 'U1 VCCA', LC['c100n'], False),
        ('100nF', '+3V3', 'U2 VCC', LC['c100n'], False),
        ('100nF', '+3V3', 'U3 VCC', LC['c100n'], False),
        ('100nF', '+3V3', 'U4 VCC', LC['c100n'], False),
        ('100nF', '+3V3', 'U5 VCC', LC['c100n'], False),
        ('100nF', '+3V3', 'U6 VCC', LC['c100n'], False),
        ('100nF', '+3V3', 'U7 VCCA', LC['c100n'], False),
        ('100nF', '+2V5', 'U7 VCCB', LC['c100n'], False),
        ('100nF', '+3V3', 'U8 VCCA', LC['c100n'], False),
        ('100nF', '+2V5', 'U8 VCCB', LC['c100n'], False),
        ('100nF', '+3V3', 'U11 VCC (the inverter)', LC['c100n'], False),
        ('10uF', '+3V3', '+3V3 bulk', LC['c10u'], True),
        ('100nF', '+3V3', '+3V3 bulk HF', LC['c100n'], False),
        ('1uF', '+2V5', 'U9 output', LC['c1u'], False),
        ('100nF', '+3V3', 'U9 input', LC['c100n'], False),
        ('100nF', 'DB1_3V3', 'DB1 +3V3 entry', LC['c100n'], False),
        ('10uF', 'P5V_IN', 'U10 input bulk (option)', LC['c10u'], True),
        ('10uF', 'LDO3V3', 'U10 output bulk (option)', LC['c10u'], True),
    ]
    for val, net, why, lc, big in cs:
        b.add(C(ref('C'), val, net, 'GND', lcsc=lc, big=big, desc=why))

    # ------------------------------------------------------- test points
    tps = ['HL2_CLK_RAW', 'HL2_CLK', 'HL2_O_D0', 'HL2_O_D1', 'HL2_O_D2',
           'HL2_AX_G1CLK', 'HL2_AX_G1DAT', 'HL2_AX_G2CLK', 'HL2_AX_G2DAT',
           'HL2_SLOW_OUT', 'HL2_I_D0', 'HL2_I_D1', 'HL2_I_D2', 'HL2_INCLK',
           'HL2_ROLE_IN', 'ROLE', 'ROLE_N',
           'DRVI_O_CLK', 'DRVI_AX_CLK', 'DRVI_AX_D1',
           'RXO_I_CLK', 'RXO_I_D0', 'RXO_I_D1', 'RXO_I_D2',
           'RXO_AX_CLK', 'RXO_AX_D0', 'RXO_AX_D1', 'RXO_AX_D2',
           'X_SP1', 'X_SP2',
           'O_HPD', 'AX_HPD', 'I_HPD', 'AX_SLOW', 'I_SLOW',
           'O_5V_PIN', 'AX_5V_PIN', 'I_5V_PIN', 'VBIAS',
           'SCL1', 'SDA1', 'VLVDS', '+3V3', '+2V5', 'DB1_3V3']
    for net in tps:
        b.add(TP(ref('TP'), net))
    for at in ((11.0, 32.5), (11.0, 36.5)):
        g = TP(ref('TP'), 'GND', t='TPBIG')
        g.at = at
        b.add(g)

    # No mounting holes on board A. It is carried by the two 2.54 mm sockets
    # and by the rear panel the three cables come through, and no mounting
    # boss inside the HL2 enclosure was identified that a hole could line up
    # with. Grounding for a scope lead is the J8 header and the two
    # through-hole ground pads instead. DESIGN_NOTES.md section 6.

    for net in ['GND', '+3V3', 'DB1_3V3', 'VLVDS', 'I_5V_PIN', 'P5V_IN',
                'O_5V_PIN', 'AX_5V_PIN']:
        b.add(FLAG(net))

    # The +2V5 island has to reach U1's VCCA, U7 and U8's VCCB, U9's output
    # and the SL_VLVDS link, so it spans the translator row.
    b.zones_extra.append(('In2.Cu', '+2V5', 10,
                          [(17.0, 1.0), (43.0, 1.0), (43.0, 18.0),
                           (17.0, 18.0)],
                          'power plane island: +2V5'))

    autoplace(b, [(8.6, 0.8, 42.6, 28.8),
                  (1.0, 29.2, 42.6, 40.6),
                  (1.0, 41.0, 47.0, 56.8)])

    b.calibration_rule(-1.0, 56.5, 50.0)
    b.texts = [
        ('F.SilkS', 24.0, 39.6, 0, 1.3,
         'gowin-bridge board A  HL2 side  rev %s' % REV),
        ('Dwgs.User', 24.0, 59.0, 0, 1.4,
         'board A = 48.00 x 66.00 mm. Socket centres at x 6.60 / 24.00 / '
         '41.40, front edge y 66.00.'),
        ('Dwgs.User', 24.0, 61.0, 0, 1.4,
         'Local (0,0) = Hermes-Lite 2 main board (70.50, 74.00) mm. '
         'DB1 pin 1 hole at (3.54, 3.96), DB12 pin 1 at (13.00, 13.46).'),
        ('F.SilkS', MINI_X[0], 55.8, 0, 2.2, 'OUT'),
        ('F.SilkS', MINI_X[1], 55.8, 0, 2.2, 'AUX'),
        ('F.SilkS', MINI_X[2], 55.8, 0, 2.2, 'IN'),
        ('F.SilkS', 24.0, 53.8, 0, 1.1, 'OUT GOES TO IN.  AUX GOES TO AUX'),
        ('F.SilkS', 24.0, 41.0, 0, 1.0,
         '2 RADIOS: OUT AND IN ONLY. ONE BOARD ROLE A, THE OTHER ROLE B'),
        ('F.SilkS', 40.6, 26.5, 90, 1.0, 'ROLE 1-2=A 2-3=B'),
        ('F.SilkS', 9.6, 4.0, 90, 1.0, 'DB1 p1'),
        ('F.SilkS', 18.8, 9.6, 0, 1.0, 'DB12 p1'),
        ('B.SilkS', 24.0, 31.0, 0, 1.2, 'SOCKETS J1 J2 ON THIS SIDE'),
        ('B.SilkS', 24.0, 33.5, 0, 1.0, 'DB12 p5=PIN_89(ROLE) p6=PIN_88(CLK)'),
        ('B.SilkS', 24.0, 36.0, 0, 0.9,
         'CLIP DB1 TAILS 1-6 9 11 15 17 FLUSH'),
    ]
    return b


# ==========================================================================
#  BOARD B  -  tang-bridge  (2 x full-size HDMI IN + 1 x full-size HDMI OUT)
# ==========================================================================

BOARD_B_W = 90.0
BOARD_B_H = 46.0
TYPEA_PITCH = 24.0
TYPEA_X = [BOARD_B_W / 2.0 - TYPEA_PITCH, BOARD_B_W / 2.0,
           BOARD_B_W / 2.0 + TYPEA_PITCH]
TYPEA_ORIGIN_Y = BOARD_B_H - TYPEA['front_offset']


def board_b():
    OUT = [(0, 0), (BOARD_B_W, 0), (BOARD_B_W, BOARD_B_H), (0, BOARD_B_H)]
    b = Board('tang-bridge',
              'Hermes Lite 2 <-> Gowin HDMI bridge, board B '
              '(Tang Mega 138K dock), rev C',
              OUT, (BOARD_B_W, BOARD_B_H),
              origin_note='local (0,0) is 4 mm outboard of J14 pin 1 - '
                          'UNVERIFIED, the user must measure the dock')
    ref = RefGen()

    # Every J14 pin not listed is left electrically OPEN, so PMOD0 (1-8),
    # PMOD1 and the DVP camera pins (21-30, 37-40) stay usable.  rev C uses
    # 15 signal pins and leaves pin 36 (ball U17) spare - the first spare
    # J14 pin in any revision.
    j14 = {str(n): None for n in range(1, 41)}
    j14.update({
        '9': 'LINK_R0', '10': 'LINK_D0', '11': 'P5V_J14', '12': 'GND',
        '13': 'LINK_R1', '14': 'LINK_D1', '15': 'LINK_R2', '16': 'LINK_D2',
        '17': 'LINK_AUX_G2_CLK', '18': 'LINK_AUX_G1_DAT',
        '19': 'LINK_SLOW_IN', '20': 'LINK_CLK',
        '31': 'LINK_AUX_G2_DAT', '32': 'LINK_AUX_G1_CLK',
        '33': 'LINK_PRESENT', '34': 'LINK_ROLE',
        '35': 'LINK_REVCLK', '36': None,
    })
    b.add(Part('J1', 'SKT2x20', 'J14 2x20 socket', j14,
               lcsc=LC_SKT2x20, mfr='BOOMELE 2.54mm 2x20P female header, '
                                    'vertical',
               desc='Mates the 2x20 male header the user solders into the '
                    'Tang dock J14 holes (Bank 4)',
               at=(6.0, 8.0), rot=90, layer='B.Cu',
               note='Bottom side. J14 pin 36 (ball U17) is deliberately '
                    'open: it is the one spare pin, and the gateware should '
                    'leave it unconstrained.'))

    socket_note = ('Hybrid mount: reflow the 19 SMT contacts, then solder the '
                   'four through-hole shell legs. Mating face flush with the '
                   'board edge.')
    b.add(Part('J2', 'HDMI_A', 'IN (HDMI)',
               hdmi_socket_pins('A', 'I', 'I_5V_PIN', 'SHLD1'),
               lcsc=TYPEA_LCSC, mfr=TYPEA_MFR,
               desc='IN, cable 1: receives the 153.6 MHz link clock and '
                    'lanes 0,1,2 at 307.2 Mbit/s, plus the HL2 status UART '
                    'on SCL, which is the ONLY slow line with a destination '
                    'in rev C',
               at=(TYPEA_X[0], TYPEA_ORIGIN_Y), rot=0, note=socket_note))
    b.add(Part('J3', 'HDMI_A', 'AUX (HDMI)',
               hdmi_socket_pins('A', 'AX', 'AX_5V_PIN', 'SHLD2'),
               lcsc=TYPEA_LCSC, mfr=TYPEA_MFR,
               desc='AUX, cable 3: bidirectional, full duplex. G1 = clock '
                    'pair + data 0 pair, G2 = data 1 pair + data 2 pair. '
                    'Board B ships strapped ROLE B, so it receives G1 and '
                    'drives G2. SCL, HPD and +5 V are test pads only',
               at=(TYPEA_X[1], TYPEA_ORIGIN_Y), rot=0, note=socket_note))
    b.add(Part('J4', 'HDMI_A', 'OUT (HDMI)',
               hdmi_socket_pins('A', 'O', 'O_5V_PIN', 'SHLD3'),
               lcsc=TYPEA_LCSC, mfr=TYPEA_MFR,
               desc='OUT, cable 2: drives the reverse clock and reverse '
                    'lanes 0,1,2 at 307.2 Mbit/s. Its SCL has no source in '
                    'rev C (J14 pin 36 is left spare) and is a test pad only',
               at=(TYPEA_X[2], TYPEA_ORIGIN_Y), rot=0, note=socket_note))

    # ================================================== the ROLE strap
    b.add(Part('J7', 'HDR1x03', 'ROLE', {
        '1': '+3V3', '2': 'ROLE', '3': 'GND',
    }, lcsc=LC_HDR, mfr='2.54mm 1x3P pin header',
        desc='ROLE strap, ONE shunt: 1-2 = ROLE A (drives AUX G1, receives '
             'G2); 2-3 = ROLE B (drives G2, receives G1) which is how board '
             'B ships. The two boards of a link must be strapped differently',
        at=(70.0, 4.0), rot=0,
        note='Fit ONE shunt (LCSC C5305). Board B ships 2-3 = ROLE B, so '
             'the Gowin reads link_role LOW on J14 pin 34.'))
    b.add(Part('U8', 'INV', '74LVC1G04', {
        INV_A: 'ROLE', INV_Y: 'ROLE_N', INV_GND: 'GND', INV_VCC: '+3V3',
        INV_NC: None,
    }, lcsc=LC_INV, mfr='SN74LVC1G04DBVR',
        desc='Single-gate inverter: ROLE_N = NOT ROLE. Makes the complement '
             'a property of the circuit rather than of the user',
        at=(78.0, 5.0), rot=0,
        note='SOT-23-5, TI DBV pinout (1 NC, 2 A, 3 GND, 4 Y, 5 VCC). '
             "Nexperia's 74LVC1G04GW has a DIFFERENT pinout - do not "
             'substitute it.'))

    # ------------------------------------------------------- receivers
    # U1 = IN, gated by the IN cable detect.  U2 = AUX, always on and sitting
    # across all four AUX pairs in both roles; what tri-states is its OUTPUT
    # path toward the Gowin, which is U6.
    pins = {'9': 'RXEN_N', '16': '+3V3', '12': 'GND', '13': '+3V3'}
    rxo = {'CLK': 'LINK_RX_CLK', 'D0': 'LINK_RX_D0', 'D1': 'LINK_RX_D1',
           'D2': 'LINK_RX_D2'}
    for i, lane in enumerate(LANES):
        pins[RCV_P[i]] = 'I_%s_RX_P' % lane
        pins[RCV_N[i]] = 'I_%s_RX_N' % lane
        pins[RCV_OUT[i]] = rxo[lane]
    b.add(Part('U1', 'LVDS_RCV', 'DS90LV048A', pins, lcsc=LC_RCV,
               mfr='DS90LV048ATMTCX/NOPB',
               desc='Quad LVDS receiver, 400 Mbps, TSSOP-16. Receives socket '
                    'IN: the link clock and lanes 0,1,2. All four channels '
                    'used',
               at=(21.0, 28.0), rot=0,
               note='EN* = RXEN_N, gated by the IN cable detect through J5.'))

    pins = {'9': 'GND', '16': '+3V3', '12': 'GND', '13': '+3V3'}
    rxo = {'CLK': 'RXO_AX_CLK', 'D0': 'RXO_AX_D0', 'D1': 'RXO_AX_D1',
           'D2': 'RXO_AX_D2'}
    for i, lane in enumerate(LANES):
        pins[RCV_P[i]] = 'AX_%s_P' % lane
        pins[RCV_N[i]] = 'AX_%s_N' % lane
        pins[RCV_OUT[i]] = rxo[lane]
    b.add(Part('U2', 'LVDS_RCV', 'DS90LV048A', pins, lcsc=LC_RCV,
               mfr='DS90LV048ATMTCX/NOPB',
               desc='Quad LVDS receiver, 400 Mbps, TSSOP-16. Sits across ALL '
                    'FOUR AUX pairs in both roles',
               at=(45.0, 28.0), rot=0,
               note='EN tied high, EN* tied low: always enabled. Safe, '
                    'because a receiver input is high impedance; it is this '
                    "receiver's OUTPUTS that must not reach a Gowin pin the "
                    'gateware is driving, and U6 is what stops them.'))

    # -------------------------------------------------------- drivers
    # THREE drivers for the same reason as board A: three enable domains and
    # one enable per DS90LV047A package.
    drv = [
        ('U3', (69.0, 28.0), '+3V3', {
            'CLK': ('DRVI_REVCLK', 'O_CLK'), 'D0': ('DRVI_R0', 'O_D0'),
            'D1': ('DRVI_R1', 'O_D1'), 'D2': ('DRVI_R2', 'O_D2')},
         'OUT: the reverse cable. All four channels used, none spare',
         'EN tied to +3V3 and EN* to GND: permanently enabled.'),
        ('U4', (33.0, 28.0), 'ROLE', {
            'CLK': ('DRVI_AX_G1CLK', 'AX_CLK'),
            'D0': ('DRVI_AX_G1DAT', 'AX_D0')},
         'AUX group G1 (clock pair + data 0 pair). Two channels used, two '
         'spare. EN = ROLE, so G1 is driven only in ROLE A',
         'EN = ROLE. Tri-stated in ROLE B, which is how board B ships. '
         'Channels 3 and 4 unused: inputs grounded, outputs open.'),
        ('U5', (57.0, 28.0), 'ROLE_N', {
            'CLK': ('DRVI_AX_G2CLK', 'AX_D1'),
            'D0': ('DRVI_AX_G2DAT', 'AX_D2')},
         'AUX group G2 (data 1 pair + data 2 pair). Two channels used, two '
         'spare. EN = ROLE_N, so G2 is driven only in ROLE B',
         'EN = ROLE_N. Enabled in ROLE B, which is how board B ships. '
         'Channels 3 and 4 unused.'),
    ]
    for ref_u, at, en, chmap, desc, note in drv:
        pins = {'1': en, '4': '+3V3', '5': 'GND', '8': 'GND'}
        for i, lane in enumerate(LANES):
            if lane in chmap:
                src, pfxlane = chmap[lane]
                pins[DRV_IN[i]] = src
                pins[DRV_P[i]] = '%s_P' % pfxlane
                pins[DRV_N[i]] = '%s_N' % pfxlane
            else:
                pins[DRV_IN[i]] = 'GND'
                pins[DRV_P[i]] = None
                pins[DRV_N[i]] = None
        b.add(Part(ref_u, 'LVDS_DRV', 'DS90LV047A', pins, lcsc=LC_DRV,
                   mfr='DS90LV047ATMX/NOPB',
                   desc='Quad LVDS driver, 400 Mbps, SOIC-16. ' + desc,
                   at=at, rot=0, note=note))

    # ------------- the strap-gated buffer between the AUX receiver and J14
    # This part is board B's equivalent of board A's two 4-bit translator
    # ports, and it is NOT optional.  Without it the always-on AUX
    # receiver's outputs for the group this board DRIVES would land on the
    # two Gowin pins the gateware is driving as outputs in that role - CMOS
    # against CMOS, which is exactly the failure PINMAP.md 2.4 exists to
    # prevent.  Board B has no level shift to do (everything is 3.3 V), so
    # both rails are tied to +3V3 and the part is used purely as two
    # independently gated 2-channel buffers.
    #
    # THE INVARIANT, identical to board A: for each group the LVDS driver's
    # active-HIGH EN and this buffer port's active-LOW OE* are THE SAME NET,
    # so the group is either driven onto the cable or driven toward the
    # Gowin, never both, whatever that net does.
    x4 = {'1': '+3V3', '16': '+3V3', '8': 'GND', '9': 'GND',
          '2': '+3V3', '3': '+3V3',          # 1DIR, 2DIR high = A -> B
          '15': 'ROLE', '14': 'ROLE_N'}      # 1OE* = ROLE, 2OE* = ROLE_N
    x4[X4_A[1]] = 'RXO_AX_CLK'
    x4[X4_B[1]] = 'LINK_AUX_G1_CLK'
    x4[X4_A[2]] = 'RXO_AX_D0'
    x4[X4_B[2]] = 'LINK_AUX_G1_DAT'
    x4[X4_A[3]] = 'RXO_AX_D1'
    x4[X4_B[3]] = 'LINK_AUX_G2_CLK'
    x4[X4_A[4]] = 'RXO_AX_D2'
    x4[X4_B[4]] = 'LINK_AUX_G2_DAT'
    b.add(Part('U6', 'XLAT4', 'SN74AVC4T245PW', x4, lcsc=LC_X4,
               mfr='SN74AVC4T245PWR',
               desc='Strap-gated buffer, VCCA = VCCB = 3.3 V, used as two '
                    'independent 2-channel 3-state buffers: port 1 = AUX G1 '
                    'toward the Gowin (enabled in ROLE B), port 2 = AUX G2 '
                    'toward the Gowin (enabled in ROLE A). No level shift - '
                    'this part exists only to tri-state',
               at=(45.0, 16.0), rot=0,
               note='1OE* = ROLE: the G1 port drives J14 pins 32 and 18 only '
                    'in ROLE B. 2OE* = ROLE_N: the G2 port drives J14 pins '
                    '17 and 31 only in ROLE A. ROLE_N carries a 10k pull-UP, '
                    'so a missing or dead inverter disables the G2 port '
                    'rather than enabling it. A 74LVC125A quad buffer with '
                    'four independent enables would also do this job in one '
                    'smaller package; the AVC4T245 was chosen because board '
                    'A already carries two of them, so the panel has one '
                    'fewer unique part.'))

    b.add(Part('U7', 'LDO33', 'AMS1117-3.3', {
        '1': 'GND', '2': '+3V3', '3': 'P5V_J14',
    }, lcsc=LC_LDO33, mfr='AMS1117-3.3',
        desc='3.3 V board supply from J14 pin 11 (5V_Peripheral). Dissipates '
             '(5.0 - 3.3) x 0.15 = 0.26 W: flood the SOT-223 tab to the '
             'power plane with at least six thermal vias',
        at=(84.0, 22.0)))

    b.add(Part('J5', 'HDR1x03', 'RX MODE', {
        '1': '+3V3', '2': 'RXEN_N', '3': 'I_HPD',
    }, lcsc=LC_HDR, mfr='2.54mm 1x3P pin header',
        desc='IN receiver enable: 2-3 = auto, enabled only while a cable is '
             'in the IN socket (DEFAULT); 1-2 = force disabled, which is '
             'what the direct-LVDS experiment needs; no shunt = always '
             'enabled. Does NOT affect the AUX receiver',
        at=(62.0, 4.0), rot=0))
    b.add(Part('J6', 'HDR1x02', 'GND AUX', {'1': 'GND', '2': 'GND'},
               lcsc=LC_HDR, mfr='2.54mm 1x2P pin header',
               desc='Extra ground wire to a dock PMOD GND pin. J14 has only '
                    'one ground pin and that is not enough for eight CMOS '
                    'outputs switching at up to 307 Mbit/s - fit the wire',
               at=(86.0, 4.0), rot=0))

    # -------------------------------------------------------------- ESD
    lines = []
    for pfx in ('I', 'AX', 'O'):
        for lane in LANES:
            lines += ['%s_%s_P' % (pfx, lane), '%s_%s_N' % (pfx, lane)]
        lines += ['%s_SLOW' % pfx, '%s_HPD' % pfx, '%s_5V_PIN' % pfx]
    arr, _ = esd_arrays('D', 1, lines,
                        'Place within 5 mm of the HDMI connector pins, on the '
                        'connector side of everything else.')
    b.add(*arr)

    rs = []
    # IN receiver output damping into the Gowin pins
    for a, c in (('LINK_RX_CLK', 'LINK_CLK'), ('LINK_RX_D0', 'LINK_D0'),
                 ('LINK_RX_D1', 'LINK_D1'), ('LINK_RX_D2', 'LINK_D2')):
        rs.append(R(ref('R'), '22R', a, c, lcsc=LC['r22'],
                    desc='Receiver output damping into J14, %s' % c))
    # direct-LVDS bypass links: SIX pairs, twelve DNP 0 R.  rev C gets all
    # six received pairs onto the A (T) leg of a true Gowin pair, which rev B
    # could not manage for one lane.  PINMAP.md 5.3.
    direct = [('I', 'CLK', 'LINK_CLK', 'LINK_SLOW_IN'),
              ('I', 'D0', 'LINK_D0', 'LINK_R0'),
              ('I', 'D1', 'LINK_D1', 'LINK_R1'),
              ('I', 'D2', 'LINK_D2', 'LINK_R2'),
              ('AX', 'D0', 'LINK_AUX_G1_DAT', 'LINK_AUX_G2_CLK'),
              ('AX', 'CLK', 'LINK_AUX_G1_CLK', 'LINK_AUX_G2_DAT')]
    for pfx, lane, aleg, bleg in direct:
        rs.append(R(ref('R'), '0R', '%s_%s_P' % (pfx, lane), aleg,
                    lcsc=LC['r0'], dnp=True,
                    desc='Direct-LVDS link: %s %s + straight to the J14 A (T) '
                         'leg' % (pfx, lane),
                    note='NOT FITTED. Fit only in direct-LVDS mode; see '
                         'PINMAP.md 5.3.'))
        rs.append(R(ref('R'), '0R', '%s_%s_N' % (pfx, lane), bleg,
                    lcsc=LC['r0'], dnp=True,
                    desc='Direct-LVDS link: %s %s - straight to the J14 B (C) '
                         'leg' % (pfx, lane),
                    note='NOT FITTED. Fitting this disables whatever signal '
                         'normally lives on that B leg (%s).' % bleg))
    # driver input damping and pull-downs.  The AUX ones are on nets the
    # Gowin drives in one role and U6 drives in the other, so the pull-down
    # is what defines them while neither does.
    for src, dst, why in (
            ('LINK_REVCLK', 'DRVI_REVCLK', 'OUT clock'),
            ('LINK_R0', 'DRVI_R0', 'OUT lane 0'),
            ('LINK_R1', 'DRVI_R1', 'OUT lane 1'),
            ('LINK_R2', 'DRVI_R2', 'OUT lane 2'),
            ('LINK_AUX_G1_CLK', 'DRVI_AX_G1CLK', 'AUX G1 clock'),
            ('LINK_AUX_G1_DAT', 'DRVI_AX_G1DAT', 'AUX G1 data'),
            ('LINK_AUX_G2_CLK', 'DRVI_AX_G2CLK', 'AUX G2 clock'),
            ('LINK_AUX_G2_DAT', 'DRVI_AX_G2DAT', 'AUX G2 data')):
        rs.append(R(ref('R'), '22R', src, dst, lcsc=LC['r22'],
                    desc='Driver input damping, %s (%s)' % (dst, why)))
        rs.append(R(ref('R'), '10k', dst, 'GND', lcsc=LC['r10k'],
                    desc='Defines %s while the Gowin is unconfigured' % dst))
    rs.append(R(ref('R'), '0R', 'I_SLOW', 'LINK_SLOW_IN', lcsc=LC['r0'],
                desc='The HL2 status UART arrives on the IN socket SCL and '
                     'goes to J14 pin 19. That pin MUST be constrained '
                     'IO_TYPE=LVTTL33: it is driven by an HL2 2.5 V output '
                     'down an unshielded wire, and LVCMOS33\'s 2.0 V '
                     'threshold would leave zero guaranteed margin where '
                     'LVTTL33\'s 1.7 V leaves 300 mV',
                note='FITTED. Cut to isolate the slow line.'))
    rs.append(R(ref('R'), '10k', 'LINK_SLOW_IN', 'GND', lcsc=LC['r10k'],
                desc='Holds the slow line low with no cable, so the Gowin '
                     'reads a break rather than random data'))
    rs.append(C(ref('C'), '22pF', 'LINK_SLOW_IN', 'GND', lcsc=LC['c22p'],
                dnp=True,
                desc='Optional ringing damper on LINK_SLOW_IN',
                note='NOT FITTED. 22 pF into 100 R is 2.2 ns. Fit if the '
                     'unterminated cable wire rings enough to double-clock '
                     'the receiver.'))
    rs.append(R(ref('R'), '10k', 'I_HPD', '+3V3', lcsc=LC['r10k'],
                desc='IN cable detect pull-up; LOW = cable plugged in'))
    rs.append(R(ref('R'), '0R', 'I_HPD', 'LINK_PRESENT', lcsc=LC['r0'],
                desc='IN cable detect into J14 pin 33. rev C has only one '
                     'cable detect: the AUX cable is detected by clock '
                     'activity in the gateware, not by HPD'))
    rs.append(R(ref('R'), '0R', 'ROLE', 'LINK_ROLE', lcsc=LC['r0'],
                desc='The ROLE level into J14 pin 34, so the gateware knows '
                     'its own role and sets its four AUX pin directions to '
                     'match. Board B ships ROLE B, so this reads LOW'))
    rs.append(R(ref('R'), '100R', 'O_HPD', 'GND', lcsc=LC['r100'],
                desc='OUT HPD to ground so board A detects the cable. 100 R '
                     'against the far 10 k gives 0.033 V'))
    rs.append(R(ref('R'), '100k', 'RXEN_N', 'GND', lcsc=LC['r100k'],
                desc='Holds the IN receiver enabled when J5 has no shunt'))
    rs.append(R(ref('R'), '100k', 'ROLE', 'GND', lcsc=LC['r100k'],
                desc='Makes "no shunt on J7" mean ROLE B rather than a '
                     'floating inverter input - and ROLE B is how board B '
                     'ships, so a lost shunt is not even a change'))
    rs.append(R(ref('R'), '10k', 'ROLE_N', '+3V3', lcsc=LC['r10k'],
                desc='ROLE_N pull-UP. THE DIRECTION MATTERS: if U8 is '
                     'missing, unpowered or dead, ROLE_N reads HIGH, which '
                     'DISABLES the G2 buffer port toward the Gowin. The '
                     'auxiliary link then does not work and nothing is '
                     'stressed'))
    rs.append(R(ref('R'), '0R', 'P5V_J14', 'O_5V_PIN', lcsc=LC['r0'],
                dnp=True,
                desc='SL_5V_OUT: put the dock\'s 5 V on the OUT socket so '
                     'board A could run from it',
                note='NOT FITTED. See DESIGN_NOTES.md 5: board A must be able '
                     'to run from the HL2 anyway, and a 5 V path that only '
                     'exists in one of the two configurations is a trap.'))
    for i, sh in enumerate(('SHLD1', 'SHLD2', 'SHLD3'), start=1):
        rs.append(R(ref('R'), '0R', sh, 'GND', lcsc=LC['r0'], big=True,
                    desc='Socket %d shell to board ground' % i))
    b.add(*rs)

    # DC/AC coupling and terminations on the four RECEIVED IN pairs
    b.add(*ac_coupling(ref, 'I', LANES))
    b.add(*vbias_network(ref))
    # The four AUX pairs.  Board B ships ROLE B, so it RECEIVES G1 = the CLK
    # and D0 pairs, and those two get the 100 R.
    b.add(*aux_pairs(ref, 'AX', {'CLK', 'D0'}, 'ROLE B (how board B ships)'))

    cs = [
        ('100nF', '+3V3', 'U1 VCC', LC['c100n'], False),
        ('100nF', '+3V3', 'U2 VCC', LC['c100n'], False),
        ('100nF', '+3V3', 'U3 VCC', LC['c100n'], False),
        ('100nF', '+3V3', 'U4 VCC', LC['c100n'], False),
        ('100nF', '+3V3', 'U5 VCC', LC['c100n'], False),
        ('100nF', '+3V3', 'U6 VCCA', LC['c100n'], False),
        ('100nF', '+3V3', 'U6 VCCB', LC['c100n'], False),
        ('100nF', '+3V3', 'U8 VCC (the inverter)', LC['c100n'], False),
        ('10uF', '+3V3', '+3V3 bulk', LC['c10u'], True),
        ('100nF', '+3V3', '+3V3 bulk HF', LC['c100n'], False),
        ('10uF', 'P5V_J14', '5 V input bulk', LC['c10u'], True),
        ('100nF', 'P5V_J14', '5 V input HF', LC['c100n'], False),
        ('10uF', '+3V3', 'U7 output bulk', LC['c10u'], True),
        ('100nF', '+3V3', 'extra +3V3', LC['c100n'], False),
    ]
    for val, net, why, lc, big in cs:
        b.add(C(ref('C'), val, net, 'GND', lcsc=lc, big=big, desc=why))

    tps = ['LINK_CLK', 'LINK_D0', 'LINK_D1', 'LINK_D2', 'LINK_SLOW_IN',
           'LINK_AUX_G1_CLK', 'LINK_AUX_G1_DAT', 'LINK_AUX_G2_CLK',
           'LINK_AUX_G2_DAT', 'LINK_PRESENT', 'LINK_ROLE', 'LINK_REVCLK',
           'LINK_R0', 'LINK_R1', 'LINK_R2', 'DRVI_REVCLK',
           'ROLE', 'ROLE_N',
           'RXO_AX_CLK', 'RXO_AX_D0', 'RXO_AX_D1', 'RXO_AX_D2',
           'I_HPD', 'AX_HPD', 'O_HPD', 'AX_SLOW', 'O_SLOW',
           'I_5V_PIN', 'AX_5V_PIN', 'O_5V_PIN', 'VBIAS', '+3V3', 'P5V_J14']
    for net in tps:
        b.add(TP(ref('TP'), net))
    for at in ((86.5, 32.0), (86.5, 15.0)):
        g = TP(ref('TP'), 'GND', t='TPBIG')
        g.at = at
        b.add(g)

    # Local x 6 / 84 rather than 4 / 86: on the panel, board B's local x
    # becomes the distance from a V-score line, and a 3.2 mm mounting pad
    # 4 mm in would sit 0.8 mm from the score.
    for i, at in enumerate(((6.0, 42.0), (84.0, 42.0)), start=1):
        b.add(Part('H%d' % i, 'MH', 'M3', {'1': 'GND'}, at=at,
                   desc='M3 mounting hole, grounded'))

    for net in ['GND', 'P5V_J14', 'I_5V_PIN', 'AX_5V_PIN', 'O_5V_PIN']:
        b.add(FLAG(net))

    autoplace(b, [(1.5, 13.5, 88.5, 34.5), (1.5, 1.2, 59.5, 12.0)])

    b.calibration_rule(20.0, 36.5, 50.0)
    b.texts = [
        ('F.SilkS', 45.0, 2.0, 0, 1.3,
         'gowin-bridge board B  Tang Mega 138K dock  rev %s' % REV),
        ('Dwgs.User', 45.0, 24.0, 0, 1.4,
         'board B = 90.00 x 46.00 mm. Socket centres at x 21.00 / 45.00 / '
         '69.00, front edge y 46.00.'),
        ('Dwgs.User', 45.0, 39.0, 0, 1.4,
         'J14 SOCKET POSITION IS UNVERIFIED. Pin 1 hole at local '
         '(6.00, 8.00); odd pins (J14 silk "N") on the y = 8.00 row, even '
         'pins ("P") on y = 10.54, ascending in +x to pin 39/40 at x 54.26.'),
        ('Dwgs.User', 45.0, 41.0, 0, 1.4,
         'Offer this print up to the dock and check both before ordering.'),
        ('F.SilkS', TYPEA_X[0], 34.8, 0, 2.2, 'IN'),
        ('F.SilkS', TYPEA_X[1], 34.8, 0, 2.2, 'AUX'),
        ('F.SilkS', TYPEA_X[2], 34.8, 0, 2.2, 'OUT'),
        ('F.SilkS', 45.0, 36.5, 0, 1.2, 'OUT GOES TO IN.  AUX GOES TO AUX'),
        ('F.SilkS', 70.0, 12.4, 0, 1.0, 'ROLE 1-2=A 2-3=B (SHIPS B)'),
        ('F.SilkS', 6.0, 6.0, 0, 1.0, 'J14 p1'),
        ('B.SilkS', 45.0, 9.0, 0, 1.2,
         'SOCKET J1 ON THIS SIDE - MATES DOCK J14'),
        ('B.SilkS', 45.0, 11.5, 0, 1.0, 'VERIFY POSITION BY MEASUREMENT'),
    ]
    return b


# ==========================================================================
#  THE PANEL  -  both boards on one 94 x 100 mm production panel
# ==========================================================================
#
# Board B rotated 90 degrees is the ONLY arrangement that fits inside
# 100 x 100 mm.  Every other combination overflows: board B unrotated is
# 138 mm wide side by side and 112 mm tall stacked, and board A rotated gives
# 156 mm.  DESIGN_NOTES.md 10.
#
#   y 100  +-------------------------+--------+   <- top rail, V-score y = 95
#    95    |  board A  48 x 66       | board  |
#          |  socket edge at y = 95  |   B    |
#          |  (V-scored: clean edge, |        |
#          |   no nubs)              | 46 x 90|
#    29    +==== mouse bites ========+ rotated|
#    27    |  coupon 48 x 22         | socket |
#          |  fiducials + label      | edge at|
#     5    +-------------------------+ x = 94 |   <- bottom rail, V-score y = 5
#     0    +-------------------------+--------+
#          x 0                     48       94
#                                   ^
#                        V-score at x = 48, full height
#
# THREE V-SCORES - y = 5, y = 95 and x = 48 - each straight, each running
# edge to edge, each with material on both sides for its whole length.  ONE
# routed separation with mouse bites, at y = 29, which is board A's BACK edge
# and not a socket edge.  Both socket edges land on an outer panel edge or on
# a V-score, so there are no nubs anywhere a plug goes.
#
# The rails are on the y axis, where 10 mm was spare; the x axis had only
# 6 mm.  The coupon is 22 mm tall rather than the 24 mm in the first sketch,
# because the 2 mm routed channel has to come out of something and board A's
# 66 mm and the panel's 100 mm are both fixed.

PANEL_W, PANEL_H = 94.0, 100.0
RAIL = 5.0                          # assembly rail height, top and bottom
A_AT = (0.0, 29.0)                  # board A origin in panel coordinates
B_AT = (48.0, 95.0)                 # board B origin, rotated +90
VSCORE_X = 48.0
VSCORE_Y = (RAIL, PANEL_H - RAIL)   # 5.0 and 95.0
MB_Y = 29.0                         # the mouse-bite break line = board A back
MB_CHANNEL = 2.0                    # routed channel width, taken from the coupon
MB_DRILL = 0.5
MB_PITCH = 1.0
# Tabs, as (x_start, x_end).  The outermost two run right up to x = 0 and
# x = 48 on purpose: every routed gap is then a CLOSED slot inside the panel
# (an outline that opens onto a board edge is not a closed shape and KiCad
# rejects it), and the x = 48 V-score keeps material on its left over the
# whole 100 mm.
MB_TABS = ((0.0, 4.0), (12.0, 17.0), (28.0, 33.0), (43.5, 48.0))
# Fiducials, spread for a long baseline and deliberately not symmetric so the
# placement machine cannot fit the panel the wrong way round.
FIDUCIALS = ((6.0, 10.0), (42.0, 10.0), (89.0, 97.5))


def panel_xform_a(x, y):
    return (x + A_AT[0], y + A_AT[1])


def panel_xform_b(x, y):
    """Board B rotated +90 in KiCad's sense, which maps a footprint offset
    (x, y) to (y, -x).  Local (0,0) lands at (48, 95), so local x runs down
    the panel and local y runs across it: board B occupies x 48..94, y 5..95
    and its socket edge (local y = 46) lands on the outer panel edge x = 94."""
    return (B_AT[0] + y, B_AT[1] - x)


def panel():
    a, bb = board_a(), board_b()
    out = [(0, 0), (PANEL_W, 0), (PANEL_W, PANEL_H), (0, PANEL_H)]
    p = Board('panel',
              'gowin-bridge production panel, 94 x 100 mm, 2 designs, rev %s'
              % REV,
              out, (PANEL_W, PANEL_H),
              origin_note='panel (0,0) = bottom-left corner of the panel; '
                          'board A origin at (0, 29), board B origin at '
                          '(48, 95) rotated 90')

    # A_ / B_ net prefixes keep the two boards electrically separate.  Without
    # them KiCad would treat board A's GND and board B's GND as one net, show
    # a ratsnest across the V-score and demand it be routed.
    def xf(board, idx, pfx, xform, extra_rot):
        rects = []
        for q_ in board.parts:
            pins = {k: (pfx + v if v else v) for k, v in q_.pins.items()}
            ref = q_.ref
            if ref.startswith('#FLG_'):
                ref = '#FLG_' + pfx + ref[len('#FLG_'):]
            else:
                head = ref.rstrip('0123456789')
                num = ref[len(head):]
                ref = '%s%d' % (head, idx * 100 + int(num or 0))
            at = xform(q_.at[0], q_.at[1]) if q_.at else None
            p.add(Part(ref, q_.ptype, q_.value, pins, lcsc=q_.lcsc,
                       mfr=q_.mfr, desc=q_.desc, dnp=q_.dnp, note=q_.note,
                       at=at, rot=(q_.rot + extra_rot) % 360, layer=q_.layer,
                       exclude_bom=q_.exclude_bom, mirror=q_.mirror))
        for (layer, tx, ty, trot, tsize, txt) in board.texts:
            nx, ny = xform(tx, ty)
            p.texts.append((layer, nx, ny, (trot + extra_rot) % 360, tsize,
                            txt))
        for (layer, x0, y0, x1, y1, lw) in board.lines:
            ax, ay = xform(x0, y0)
            cx, cy = xform(x1, y1)
            p.lines.append((layer, ax, ay, cx, cy, lw))
        # the board's own outline, as documentation only - it is a V-score or
        # a panel edge on three sides and mouse bites on the fourth, so none
        # of it is Edge.Cuts except the mouse-bite channel below
        opts = [xform(x, y) for (x, y) in board.outline]
        for i in range(len(opts)):
            (x0, y0), (x1, y1) = opts[i], opts[(i + 1) % len(opts)]
            p.lines.append(('Cmts.User', x0, y0, x1, y1, 0.15))
        for (zlayer, znet, zprio, zpoly, zname) in board.zones_extra:
            p.zones_extra.append((zlayer, pfx + znet, zprio,
                                  [xform(x, y) for (x, y) in zpoly],
                                  '%s %s' % (board.name, zname)))
        rects.append(opts)
        return opts

    a_poly = xf(a, 1, 'A_', panel_xform_a, 0)
    b_poly = xf(bb, 2, 'B_', panel_xform_b, 90)

    # Pour each board's planes over ITS OWN outline only.
    p.zones_full = []
    for poly, pfx, nm in ((a_poly, 'A_', 'board A'), (b_poly, 'B_', 'board B')):
        p.zones_full.append(('In1.Cu', pfx + 'GND', 0, poly,
                             '%s GND plane (layer 2) - DO NOT CUT' % nm))
        p.zones_full.append(('F.Cu', pfx + 'GND', 0, poly,
                             '%s top ground fill' % nm))
        p.zones_full.append(('B.Cu', pfx + 'GND', 0, poly,
                             '%s bottom ground fill' % nm))
        p.zones_full.append(('In2.Cu', pfx + '+3V3', 0, poly,
                             '%s power plane (layer 3): +3V3' % nm))

    # ------------------------------------------------ fiducials and label
    for i, (fx, fy) in enumerate(FIDUCIALS, start=1):
        p.add(Part('FID%d' % i, 'FIDUCIAL', 'Fiducial', {}, at=(fx, fy),
                   exclude_bom=True,
                   desc='Panel fiducial for JLCPCB assembly: 1 mm bare '
                        'copper, 2 mm mask opening. Two on the coupon and '
                        'one on the top rail, so the baseline is long and '
                        'the set is not symmetric'))

    # ------------------------------------------- the mouse-bite separation
    # The only real milling on the panel.  The channel is taken entirely out
    # of the COUPON side, so board A stays exactly 66.00 mm and the nubs
    # protrude OUTWARD from its back edge - which is where the 0.3 mm that
    # eats into the HL2 magjack clearance comes from.
    gaps = [(MB_TABS[i][1], MB_TABS[i + 1][0])
            for i in range(len(MB_TABS) - 1)]
    ch0, ch1 = MB_Y - MB_CHANNEL, MB_Y      # 27.0 .. 29.0
    for (g0, g1) in gaps:
        p.edge_extra.append((g0, ch1, g1, ch1))     # board A side
        p.edge_extra.append((g0, ch0, g1, ch0))     # coupon side
        p.edge_extra.append((g0, ch0, g0, ch1))
        p.edge_extra.append((g1, ch0, g1, ch1))
    for (t0, t1) in MB_TABS:
        n = int((t1 - t0) / MB_PITCH)
        first = t0 + (t1 - t0 - (n - 1) * MB_PITCH) / 2.0
        for k in range(n):
            hx = first + k * MB_PITCH
            # keep the perforations 1.5 mm clear of the x = 48 V-score and
            # 1.0 mm clear of the panel's own left edge
            if hx > VSCORE_X - 1.5 or hx < 1.0:
                continue
            p.npth.append((hx, MB_Y, MB_DRILL))

    # ---------------------------------------------- V-scores and the notes
    for vy in VSCORE_Y:
        p.lines.append(('Eco1.User', 0.0, vy, PANEL_W, vy, 0.2))
        p.texts.append(('Eco1.User', 12.0, vy - 1.4, 0, 1.4,
                        'V-SCORE  y = %.2f' % vy))
    p.lines.append(('Eco1.User', VSCORE_X, 0.0, VSCORE_X, PANEL_H, 0.2))
    p.texts.append(('Eco1.User', VSCORE_X + 1.6, 52.0, 90, 1.4,
                    'V-SCORE  x = %.2f' % VSCORE_X))

    p.texts += [
        ('F.SilkS', 24.0, 9.0, 0, 2.2, 'gowin-bridge  rev %s' % REV),
        ('F.SilkS', 24.0, 12.5, 0, 1.4, 'PANEL 94.00 x 100.00 mm'),
        ('F.SilkS', 24.0, 15.0, 0, 1.4, '2 DIFFERENT DESIGNS IN THIS FILE'),
        ('F.SilkS', 24.0, 17.5, 0, 1.2,
         'A = HL2 SIDE (mini HDMI)   B = TANG DOCK (full-size HDMI)'),
        ('F.SilkS', 24.0, 20.5, 0, 1.2, 'SNAP THE RAILS OFF FIRST, THEN'),
        ('F.SilkS', 24.0, 22.5, 0, 1.2, 'x=48, THEN THE MOUSE BITES AT y=29'),
        ('F.SilkS', 24.0, 24.8, 0, 1.1,
         'FILE THE NUBS FLAT: THAT EDGE FACES THE HL2 MAGJACK'),
        ('Eco1.User', 47.0, 96.8, 0, 1.4, 'ASSEMBLY RAIL - SCRAP'),
        ('Eco1.User', 47.0, 3.6, 0, 1.4, 'ASSEMBLY RAIL - SCRAP'),
        ('Dwgs.User', 24.0, 27.9, 0, 1.0,
         'ROUTED 2.00 mm CHANNEL + MOUSE BITES, BREAK LINE y = 29.00'),
        ('Dwgs.User', 47.0, 99.0, 0, 1.4,
         'FABRICATION: 4 layer, 1.6 mm, HASL, 2 designs. THREE V-SCORES '
         '(y=5.00, y=95.00, x=48.00), each edge to edge with material both '
         'sides. ONE routed separation with mouse bites at y=29.00.'),
    ]
    p.calibration_rule(2.0, 6.0, 50.0)
    return p


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
            pins = DRV_PINS if symname == 'DS90LV047A' else RCV_PINS
            ds = ('https://www.ti.com/lit/ds/symlink/ds90lv047a.pdf'
                  if symname == 'DS90LV047A'
                  else 'https://www.ti.com/lit/ds/symlink/ds90lv048a.pdf')
            build_custom_symbol(w, symname, pins, fpref, ds,
                                'Quad LVDS line driver/receiver, 400 Mbps, '
                                'EN high + EN* low = enabled')
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
            # generated, not lifted: the mini HDMI land pattern
            txt = build_mini_hdmi_fp(fpname)
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
        pins = DRV_PINS if symname == 'DS90LV047A' else RCV_PINS
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
            pins = DRV_PINS if symname == 'DS90LV047A' else RCV_PINS
            ds = ('https://www.ti.com/lit/ds/symlink/ds90lv047a.pdf'
                  if symname == 'DS90LV047A'
                  else 'https://www.ti.com/lit/ds/symlink/ds90lv048a.pdf')
            build_custom_symbol(w, '%s:%s' % (LOCAL_SYM, symname), pins, fpref,
                                ds, 'Quad LVDS line driver/receiver')
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
PAIR_PREFIXES = ('O_', 'AX_', 'I_',
                 'A_O_', 'A_AX_', 'A_I_', 'B_O_', 'B_AX_', 'B_I_')


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
    for name in ('+3V3', '+2V5', 'P5V_IN', 'P5V_J14', 'DB1_3V3', 'LDO3V3'):
        for nm in (name, 'A_' + name, 'B_' + name):
            if nm in allnets:
                pats.append('      { "netclass": "Power", "pattern": "%s" }'
                            % nm)
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
    for b in (board_a(), board_b(), panel()):
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
