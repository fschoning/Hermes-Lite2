#!/usr/bin/env python3
"""Generate the two gowin-bridge KiCad 8 projects from one netlist description.

Run:   python gen_gowin_bridge.py

Writes, next to this tools/ directory:
    ../hl2-bridge/{hl2-bridge.kicad_pro,.kicad_sch,.kicad_pcb}
    ../hl2-bridge/gowin-bridge.kicad_sym
    ../hl2-bridge/gowin-bridge.pretty/*.kicad_mod
    ../hl2-bridge/hl2-bridge-bom.csv
    ... and the same set under ../tang-bridge/

Symbol graphics and footprint land patterns are lifted from the stock KiCad
libraries and re-emitted as project-local libraries in conservative KiCad 7/8
syntax, so the projects are self-contained and open in KiCad 8 as well as 9/10.

The netlist below is the single source of truth for both the schematic and the
PCB; PINMAP.md must agree with it.
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

# --------------------------------------------------------------------------
# Part type catalogue.  key -> (stock symbol lib, stock symbol, stock fp lib,
#                               stock fp, local symbol name, local fp name)
# --------------------------------------------------------------------------

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
    'XLAT':     ('Logic_LevelTranslator', 'SN74AVC4T245PW', 'Package_SO',
                 'TSSOP-16_4.4x5mm_P0.65mm'),
    'ESD4':     ('Power_Protection', 'TPD4E05U06DQA', 'Package_SON',
                 'USON-10_2.5x1.0mm_P0.5mm'),
    'LDO25':    ('Regulator_Linear', 'ME6211C25M5', 'Package_TO_SOT_SMD',
                 'SOT-23-5'),
    'LDO33':    ('Regulator_Linear', 'AMS1117-3.3', 'Package_TO_SOT_SMD',
                 'SOT-223-3_TabPin2'),
    'DVI':      ('Connector', 'DVI-D_Dual_Link', 'Connector_Video',
                 'DVI-D_Molex_74320-4004_Horizontal'),
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
    'HDR2x02':  ('Connector_Generic', 'Conn_02x02_Odd_Even',
                 'Connector_PinHeader_2.54mm', 'PinHeader_2x02_P2.54mm_Vertical'),
    'MH':       ('Mechanical', 'MountingHole_Pad', 'MountingHole',
                 'MountingHole_3.2mm_M3_Pad'),
}

# Custom symbols that are not in the stock libraries: built from scratch below.
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
            ('Reference', 'U', False), ('Value', name.split(':')[-1], False),
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


# --------------------------------------------------------------------------
# Part / design model
# --------------------------------------------------------------------------


class Part:
    def __init__(self, ref, ptype, value, pins, lcsc='', mfr='', desc='',
                 dnp=False, note='', at=None, rot=0, layer='F.Cu', exclude_bom=False):
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


class Board:
    def __init__(self, name, title, outline, size, origin_note=''):
        self.name = name
        self.title = title
        self.outline = outline          # list of (x, y) polygon points
        self.size = size
        self.parts = []
        self.texts = []                 # (layer, x, y, rot, size, text)
        self.origin_note = origin_note

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
        # net 0 is the unconnected net
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


# --------------------------------------------------------------------------
# DVI-D dual link pin map, shared by both boards.
# ``pfx`` is 'C1' or 'C2'.  Unused pins map to None.
# --------------------------------------------------------------------------


def dvi_pins(pfx, five_volt_net, hpd_net, scl_net, sda_net, shield_net):
    p = {
        '1': pfx + '_D2_N', '2': pfx + '_D2_P', '3': 'GND',
        '4': pfx + '_D4_N', '5': pfx + '_D4_P',
        '6': scl_net, '7': sda_net, '8': None,
        '9': pfx + '_D1_N', '10': pfx + '_D1_P', '11': 'GND',
        '12': pfx + '_D3_N', '13': pfx + '_D3_P',
        '14': five_volt_net, '15': 'GND', '16': hpd_net,
        '17': pfx + '_D0_N', '18': pfx + '_D0_P', '19': 'GND',
        '20': pfx + '_D5_N', '21': pfx + '_D5_P', '22': 'GND',
        '23': pfx + '_CLK_P', '24': pfx + '_CLK_N', 'SH': shield_net,
    }
    return p


DVI_LANES = ['CLK', 'D0', 'D1', 'D2', 'D3', 'D4', 'D5']


def esd_arrays(prefix, start_index, lines, note):
    """Group a flat list of net names into 4-channel TPD4E05U06 arrays."""
    out = []
    idx = start_index
    for i in range(0, len(lines), 4):
        grp = lines[i:i + 4] + [None] * 4
        out.append(Part('%s%d' % (prefix, idx), 'ESD4', 'TPD4E05U06',
                        {'1': grp[0], '2': grp[1], '4': grp[2], '5': grp[3],
                         '3': 'GND', '8': 'GND'},
                        lcsc='C138714', mfr='TPD4E05U06DQAR',
                        desc='Quad 0.5 pF ESD array, 5.5 V, USON-10',
                        note=note))
        idx += 1
    return out, idx


def autoplace(board, regions, reserved, pitch=3.2, types=('R', 'R0805', 'C',
                                                         'C0805', 'TP', 'ESD4')):
    """Drop every small part on a coarse grid inside `region`, skipping the
    rectangles in `reserved`.  This is a placement *starting point* only: the
    board is meant to be routed by hand (or in EasyEDA Pro), and the grid keeps
    courtyards clear so DRC is quiet before routing begins."""
    slots = []
    if isinstance(regions[0], (int, float)):
        regions = [regions]
    for (x0, y0, x1, y1) in regions:
        y = y0
        while y <= y1:
            x = x0
            while x <= x1:
                ok = True
                for (rx0, ry0, rx1, ry1) in reserved:
                    if (rx0 - 1.6 <= x <= rx1 + 1.6
                            and ry0 - 1.6 <= y <= ry1 + 1.6):
                        ok = False
                        break
                if ok:
                    slots.append((x, y))
                x += pitch
            y += pitch
    todo = [p for p in board.parts if p.ptype in types]
    if len(todo) > len(slots):
        raise SystemExit('autoplace: %d parts but only %d slots'
                         % (len(todo), len(slots)))
    for p, sl in zip(todo, slots):
        p.at = sl


# ==========================================================================
#  BOARD A  -  hl2-bridge
# ==========================================================================

def board_a():
    # Board outline in LOCAL coordinates.  Local origin (0,0) corresponds to
    # Hermes-Lite2 main-board coordinate (70.50, 74.00) mm, so local
    # x = HL2_x - 70.50 and local y = HL2_y - 74.00.
    #
    # The narrow part of the board (0..48 mm wide) is the corridor left free by
    # the N2ADR filter board; the wide tab at the front edge carries the two
    # DVI sockets.  See DESIGN_NOTES.md section 6.
    OUT = [(0, 0), (48, 0), (48, 47), (80, 47), (80, 66), (0, 66)]
    b = Board('hl2-bridge', 'Hermes Lite 2 <-> Gowin DVI bridge, board A (HL2 side)',
              OUT, (80, 66),
              origin_note='local (0,0) = HL2 main board (70.50, 74.00)')

    # ---- HL2 header sockets (bottom side, positions fixed by the HL2 PCB) ----
    # DB1 pin 1 is at HL2 (74.04, 77.96) -> local (3.54, 3.96); pins step
    # +2.54 mm in y, odd pins at local x 3.54, even pins at local x 6.08.
    b.add(Part('J1', 'SKT2x10', 'DB1 2x10 stack-through socket', {
        '1': 'HL2_D0_HDR', '2': 'HL2_D1', '3': 'HL2_D2', '4': 'HL2_D3',
        '5': 'HL2_D4', '6': 'HL2_D5', '7': 'VLVDS', '8': 'VLVDS',
        '9': 'HL2_CLK', '10': None, '11': 'HL2_REV0', '12': None,
        '13': 'GND', '14': 'GND', '15': 'HL2_REV1', '16': 'SCL1',
        '17': 'HL2_REV2', '18': 'SDA1', '19': 'DB1_3V3', '20': 'DB1_3V3',
    }, lcsc='C5361769', mfr='2.54mm 2x10P stack-through female header, H>=8.5mm',
        desc='Mates HL2 DB1; long tails pass DB1 pins 7,8,10,12,13,14,16,18,19,20 '
             'up to a stacked companion board',
        at=(4.81, 15.39), rot=90, layer='B.Cu',
        note='Bottom side. Clip the tails of positions 1-6, 9, 11, 15, 17 '
             '(used by the link) before stacking anything above.'))

    b.add(Part('J2', 'SKT2x03', 'DB12 2x03 socket', {
        '1': 'HL2_STAT', '2': 'HL2_AUX', '3': 'GND', '4': 'GND',
        '5': 'HL2_REVCLK', '6': 'HL2_FSER',
    }, lcsc='C124413', mfr='2.54mm 2x3P female header',
        desc='Mates HL2 DB12', at=(14.27, 16.54), rot=0, layer='B.Cu',
        note='Bottom side.'))

    # ---- DVI sockets ----
    b.add(Part('J3', 'DVI', 'DVI-D dual link FWD',
               dvi_pins('C1', 'P5V_DVI', 'C1_HPD', 'C1_SCL', 'C1_SDA', 'SHLD1'),
               mfr='Molex 74320-4004 or equivalent DVI-D dual-link receptacle, '
                   'right angle, through hole',
               desc='Cable 1 "FWD": HL2 -> Gowin, 7 pairs driven by this board',
               at=(22.0, 64.0), rot=0,
               note='Hand-solder if JLCPCB cannot source it. Mating face '
                    'protrudes 2.4 mm past the board edge.'))
    b.add(Part('J4', 'DVI', 'DVI-D dual link REV',
               dvi_pins('C2', None, 'C2_HPD', 'C2_SCL', 'C2_SDA', 'SHLD2'),
               mfr='Molex 74320-4004 or equivalent DVI-D dual-link receptacle, '
                   'right angle, through hole',
               desc='Cable 2 "REV": Gowin -> HL2, 7 pairs received by this board',
               at=(60.0, 64.0), rot=0,
               note='Hand-solder if JLCPCB cannot source it.'))
    # J4 pin 14 (+5 V) is deliberately left open; give it a test pad so it is
    # not a one-pin net.
    b.parts[-1].pins['14'] = 'C2_5V_NC'

    # ---- LVDS drivers: cable 1, 7 channels + 1 spare ----
    drv_map = [('U1', ['CLK', 'D0', 'D1', 'D2'], (14.0, 34.0)),
               ('U2', ['D3', 'D4', 'D5', 'SPARE'], (14.0, 42.0))]
    for ref, lanes, at in drv_map:
        pins = {'1': '+3V3', '4': '+3V3', '5': 'GND', '8': 'GND'}
        din = {0: '2', 1: '3', 2: '6', 3: '7'}
        dp = {0: '15', 1: '14', 2: '11', 3: '10'}
        dn = {0: '16', 1: '13', 2: '12', 3: '9'}
        for i, lane in enumerate(lanes):
            if lane == 'SPARE':
                pins[din[i]] = 'GND'
                pins[dp[i]] = 'DRV_SP_P'
                pins[dn[i]] = 'DRV_SP_N'
            else:
                pins[din[i]] = 'DRVI_' + lane
                pins[dp[i]] = 'C1_%s_P' % lane
                pins[dn[i]] = 'C1_%s_N' % lane
        b.add(Part(ref, 'LVDS_DRV', 'DS90LV047A', pins, lcsc='C201946',
                   mfr='DS90LV047ATM/NOPB',
                   desc='Quad LVDS driver, >=400 Mbps, SOIC-16', at=at))

    # ---- LVDS receivers: cable 2, 7 channels + 1 spare ----
    rcv_map = [('U3', ['CLK', 'D0', 'D1', 'D2'], (34.0, 34.0)),
               ('U4', ['D3', 'D4', 'D5', 'UNUSED'], (34.0, 42.0))]
    outname = {'CLK': 'RXO_REVCLK', 'D0': 'RXO_R0', 'D1': 'RXO_R1',
               'D2': 'RXO_R2', 'D3': 'RXO_FSER', 'D4': 'RXO_SP0',
               'D5': 'RXO_SP1'}
    for ref, lanes, at in rcv_map:
        pins = {'9': 'RXEN_N', '16': '+3V3', '12': 'GND', '13': '+3V3'}
        rp = {0: '2', 1: '3', 2: '6', 3: '7'}
        rn = {0: '1', 1: '4', 2: '5', 3: '8'}
        ro = {0: '15', 1: '14', 2: '11', 3: '10'}
        for i, lane in enumerate(lanes):
            if lane == 'UNUSED':
                pins[rp[i]] = 'RX_UNUSED_P'
                pins[rn[i]] = 'RX_UNUSED_N'
                pins[ro[i]] = 'RXO_UNUSED'
            else:
                pins[rp[i]] = 'C2_%s_P' % lane
                pins[rn[i]] = 'C2_%s_N' % lane
                pins[ro[i]] = outname[lane]
        b.add(Part(ref, 'LVDS_RCV', 'DS90LV048A', pins, lcsc='C87137',
                   mfr='DS90LV048ATMTCX/NOPB',
                   desc='Quad LVDS receiver, >=400 Mbps, TSSOP-16', at=at))

    # ---- 3.3 V -> 2.5 V translator for the two input-only HL2 pins ----
    b.add(Part('U5', 'XLAT', 'SN74AVC4T245PW', {
        '1': '+3V3', '16': '+2V5', '8': 'GND', '9': 'GND',
        '2': '+3V3', '3': '+3V3', '14': 'GND', '15': 'GND',
        '4': 'RXO_REVCLK', '13': 'X_REVCLK25',
        '5': 'RXO_FSER', '12': 'X_FSER25',
        '6': 'C2_SDA', '11': 'X_CMD25',
        '7': 'X_SPARE_IN', '10': 'X_SPARE25',
    }, lcsc='C81461', mfr='SN74AVC4T245PWR',
        desc='4-bit dual-supply level translator, VCCA 3.3 V / VCCB 2.5 V, '
             'up to 380 Mbps; DIR high = A->B, OE low = enabled',
        at=(24.0, 24.0)))

    # ---- power ----
    b.add(Part('U6', 'LDO25', 'ME6211C25M5G', {
        '1': '+3V3', '2': 'GND', '3': '+3V3', '5': '+2V5',
    }, lcsc='C194395', mfr='ME6211C25M5G-N',
        desc='2.5 V 400 mA LDO, 110 mV dropout, SOT-23-5; supplies only the '
             'translator B side', at=(6.0, 24.0)))
    b.add(Part('U7', 'LDO33', 'AMS1117-3.3', {
        '1': 'GND', '2': 'LDO3V3', '3': 'P5V_DVI',
    }, lcsc='C6186', mfr='AMS1117-3.3',
        desc='3.3 V LDO from the DVI +5 V rail; alternative board supply',
        at=(70.0, 30.0)))

    b.add(Part('J6', 'HDR1x03', '3V3 SRC', {
        '1': 'DB1_3V3', '2': '+3V3', '3': 'LDO3V3',
    }, lcsc='C2337', mfr='2.54mm 1x3P pin header',
        desc='Board supply select: 1-2 = HL2 DB1 +3V3 (default), '
             '2-3 = on-board LDO from DVI +5 V', at=(60.0, 24.0), rot=90))
    b.add(Part('J5', 'HDR1x03', 'RX MODE', {
        '1': '+3V3', '2': 'RXEN_N', '3': 'C2_HPD',
    }, lcsc='C2337', mfr='2.54mm 1x3P pin header',
        desc='Cable-2 receiver enable: 2-3 = auto (enabled only while cable 2 '
             'is plugged in, default), 1-2 = force disabled, open = always '
             'enabled', at=(44.0, 24.0), rot=90))
    b.add(Part('J7', 'HDR2x02', 'SPARE OUT', {
        '1': 'RXO_SP0', '2': 'RXO_SP1', '3': 'GND', '4': 'GND',
    }, lcsc='C124375', mfr='2.54mm 2x2P pin header', dnp=True,
        desc='Optional header on the two spare cable-2 lanes',
        at=(74.0, 56.0)))

    # ---- ESD protection on every DVI line ----
    lines = []
    for lane in DVI_LANES:
        lines += ['C1_%s_P' % lane, 'C1_%s_N' % lane]
    lines += ['C1_SCL', 'C1_SDA', 'C1_HPD', 'P5V_DVI']
    for lane in DVI_LANES:
        lines += ['C2_%s_P' % lane, 'C2_%s_N' % lane]
    lines += ['C2_SCL', 'C2_SDA', 'C2_HPD']
    arr, _ = esd_arrays('D', 1, lines, 'Place within 5 mm of the DVI connector pins.')
    xs = 6.0
    for i, a in enumerate(arr):
        a.at = (6.0 + (i % 5) * 8.0, 52.0 + (i // 5) * 5.0)
    b.add(*arr)

    # ---- series / link / termination resistors ----
    rs = []
    # cuttable link in series with DB1 pin 1 (shared with the HL2 PLL clock net)
    rs.append(R('R1', '0R', 'HL2_D0_HDR', 'HL2_D0', lcsc='C17168',
                desc='SL_D0: cuttable link, DB1 pin 1 (HL2 PLL clock output net, '
                     'reaches uFL pad CL8 through HL2 jumper J25)',
                note='Fitted. Remove to isolate board A from DB1 pin 1.'))
    # driver input series resistors + pull-downs
    for i, lane in enumerate(DVI_LANES):
        src = 'HL2_CLK' if lane == 'CLK' else 'HL2_' + lane
        rs.append(R('R%d' % (2 + i), '22R', src, 'DRVI_' + lane, lcsc='C25092',
                    desc='Driver input damping, lane %s' % lane))
        rs.append(R('R%d' % (9 + i), '10k', 'DRVI_' + lane, 'GND', lcsc='C25744',
                    desc='Defines lane %s while the HL2 FPGA is unconfigured' % lane))
    # reverse-link output links into the HL2
    for i, (a, c) in enumerate([('RXO_R0', 'HL2_REV0'), ('RXO_R1', 'HL2_REV1'),
                                ('RXO_R2', 'HL2_REV2')]):
        rs.append(R('R%d' % (16 + i), '0R', a, c, lcsc='C17168',
                    desc='REV%d into DB1 (3.3 V bank). 22R pads if damping is '
                         'needed.' % i))
    rs.append(R('R19', '0R', 'X_REVCLK25', 'HL2_REVCLK', lcsc='C17168',
                desc='SL_REVCLK: 2.5 V reverse clock into HL2 PIN_88'))
    rs.append(R('R20', '0R', 'X_FSER25', 'HL2_FSER', lcsc='C17168',
                desc='SL_FSER: fast serial into HL2 PIN_89 (default path)'))
    rs.append(R('R21', '0R', 'X_CMD25', 'HL2_FSER', lcsc='C17168', dnp=True,
                desc='SL_CMD: slow command UART into HL2 PIN_89 instead of the '
                     'fast serial lane', note='Do not fit together with R20.'))
    rs.append(R('R22', '100R', 'HL2_STAT', 'C1_SCL', lcsc='C25076',
                desc='Status UART out of DB12-1 (2.5 V) onto cable 1 DDC SCL'))
    rs.append(R('R23', '100R', 'HL2_AUX', 'C1_SDA', lcsc='C25076',
                desc='Aux slow line out of DB12-2 (2.5 V) onto cable 1 DDC SDA'))
    rs.append(R('R24', '1k', 'C1_HPD', 'GND', lcsc='C21190',
                desc='Ties cable-1 HPD low so board B sees "cable present"'))
    rs.append(R('R25', '10k', 'C2_HPD', '+3V3', lcsc='C25744',
                desc='Cable-2 detect pull-up; low = cable 2 plugged in'))
    # 100 R differential terminations at the cable-2 receiver inputs
    for i, lane in enumerate(DVI_LANES):
        rs.append(R('R%d' % (26 + i), '100R', 'C2_%s_P' % lane, 'C2_%s_N' % lane,
                    lcsc='C25076',
                    desc='Differential termination, cable 2 lane %s; place '
                         'within 5 mm of the receiver pins' % lane))
    rs.append(R('R33', '10k', 'RX_UNUSED_P', '+3V3', lcsc='C25744',
                desc='Bias for the unused receiver channel'))
    rs.append(R('R34', '10k', 'RX_UNUSED_N', 'GND', lcsc='C25744',
                desc='Bias for the unused receiver channel'))
    rs.append(R('R35', '10k', 'C2_SDA', 'GND', lcsc='C25744',
                desc='Defines the cable-2 command UART line when cable 2 is out'))
    rs.append(R('R36', '0R', 'VLVDS', '+2V5', lcsc='C17168', dnp=True,
                desc='SL_VLVDS: take the translator B-side supply from the HL2 '
                     'Vlvds rail (DB1 7/8) instead of U6',
                note='Do not fit together with U6.'))
    rs.append(R('R39', '0R', 'X_SPARE_IN', 'GND', lcsc='C17168',
                desc='Ties the spare translator channel input low'))
    rs.append(R('R37', '0R', 'SHLD1', 'GND', lcsc='C17168', big=True,
                desc='Cable-1 shell to board ground'))
    rs.append(R('R38', '0R', 'SHLD2', 'GND', lcsc='C17168', big=True,
                desc='Cable-2 shell to board ground'))
    for i, r in enumerate(rs):
        if r.at is None:
            r.at = (2.0 + (i % 18) * 2.4, 29.0 + (i // 18) * 2.2)
    b.add(*rs)

    # ---- decoupling ----
    cs = [
        C('C1', '100nF', '+3V3', 'GND', lcsc='C1525', desc='U1 VCC'),
        C('C2', '100nF', '+3V3', 'GND', lcsc='C1525', desc='U2 VCC'),
        C('C3', '100nF', '+3V3', 'GND', lcsc='C1525', desc='U3 VCC'),
        C('C4', '100nF', '+3V3', 'GND', lcsc='C1525', desc='U4 VCC'),
        C('C5', '100nF', '+3V3', 'GND', lcsc='C1525', desc='U5 VCCA'),
        C('C6', '100nF', '+2V5', 'GND', lcsc='C1525', desc='U5 VCCB'),
        C('C7', '10uF', '+3V3', 'GND', lcsc='C15525', big=True, desc='+3V3 bulk'),
        C('C8', '100nF', '+3V3', 'GND', lcsc='C1525', desc='+3V3 bulk HF'),
        C('C9', '1uF', '+2V5', 'GND', lcsc='C52923', desc='U6 output'),
        C('C10', '100nF', '+3V3', 'GND', lcsc='C1525', desc='U6 input'),
        C('C11', '10uF', 'P5V_DVI', 'GND', lcsc='C15525', big=True,
          desc='DVI +5 V bulk'),
        C('C12', '100nF', 'P5V_DVI', 'GND', lcsc='C1525', desc='DVI +5 V HF'),
        C('C13', '10uF', 'LDO3V3', 'GND', lcsc='C15525', big=True,
          desc='U7 output'),
        C('C14', '100nF', 'DB1_3V3', 'GND', lcsc='C1525', desc='DB1 +3V3 entry'),
    ]
    for i, c in enumerate(cs):
        c.at = (2.0 + (i % 14) * 2.4, 26.0)
    b.add(*cs)

    # ---- test points ----
    tps = ['HL2_CLK', 'HL2_D0', 'HL2_D1', 'HL2_D2', 'HL2_D3', 'HL2_D4', 'HL2_D5',
           'HL2_STAT', 'HL2_AUX', 'HL2_REV0', 'HL2_REV1', 'HL2_REV2',
           'HL2_REVCLK', 'HL2_FSER', 'SCL1', 'SDA1', 'VLVDS', 'C1_HPD',
           'C2_HPD', 'C2_SCL', '+3V3', '+2V5', 'P5V_DVI', 'DB1_3V3',
           'RXO_SP0', 'RXO_SP1', 'RXO_UNUSED', 'DRV_SP_P', 'DRV_SP_N',
           'X_SPARE25', 'C2_5V_NC', 'X_SPARE_IN']
    for i, net in enumerate(tps):
        p = TP('TP%d' % (i + 1), net, lcsc='')
        p.at = (2.0 + (i % 16) * 2.6, 44.0 + (i // 16) * 2.6)
        b.add(p)
    g1 = TP('TP101', 'GND', t='TPBIG')
    g1.at = (76.0, 50.0)
    g2 = TP('TP102', 'GND', t='TPBIG')
    g2.at = (76.0, 62.0)
    b.add(g1, g2)

    # ---- mechanical ----
    h1 = Part('H1', 'MH', 'M3', {'1': 'GND'}, at=(44.0, 3.0),
              desc='M3 mounting hole, grounded')
    h2 = Part('H2', 'MH', 'M3', {'1': 'GND'}, at=(44.0, 44.0),
              desc='M3 mounting hole, grounded')
    b.add(h1, h2)

    # A PWR_FLAG only where no component already provides a power-output pin
    # (U6 drives +2V5 and U7 drives LDO3V3, so those must not get a flag).
    for net in ['GND', '+3V3', 'P5V_DVI', 'DB1_3V3', 'VLVDS', 'C2_5V_NC']:
        b.add(FLAG(net))

    # Reserved: DB1 socket, DB12 socket, the two DVI sockets, the ICs,
    # the three headers and the mounting holes.
    autoplace(b, [(2.0, 2.0, 78.0, 45.0), (2.0, 48.0, 70.0, 52.0)], [
        (0.0, 0.0, 12.0, 32.0),      # DB1 stack-through socket + its keep-out
        (11.0, 13.0, 19.0, 21.0),    # DB12 socket
        (2.0, 53.0, 78.0, 66.0),     # both DVI sockets
        (8.0, 30.0, 22.0, 46.0),     # U1, U2
        (28.0, 30.0, 42.0, 46.0),    # U3, U4
        (16.0, 20.0, 32.0, 28.0),    # U5
        (2.0, 20.0, 11.0, 28.0),     # U6
        (64.0, 26.0, 78.0, 34.0),    # U7
        (42.0, 20.0, 62.0, 28.0),    # J5, J6
        (70.0, 52.0, 78.0, 60.0),    # J7
        (41.0, 0.0, 47.0, 6.0),      # H1
        (41.0, 41.0, 47.0, 47.0),    # H2
        (73.0, 46.0, 79.0, 66.0),    # ground clip pads
    ])

    b.texts = [
        ('F.SilkS', 40.0, 2.0, 0, 1.5, 'gowin-bridge board A  (HL2 side)  rev A'),
        ('F.SilkS', 22.0, 55.0, 0, 2.5, 'OUT / FWD'),
        ('F.SilkS', 60.0, 55.0, 0, 2.5, 'IN / REV'),
        ('F.SilkS', 40.0, 58.5, 0, 1.2, 'always connect OUT to IN'),
        ('F.SilkS', 12.0, 5.0, 90, 1.2, 'DB1 pin1'),
        ('F.SilkS', 20.0, 16.5, 0, 1.2, 'DB12 pin1'),
        ('F.SilkS', 4.0, 31.0, 0, 1.0, 'CLIP TAILS 1-6,9,11,15,17 = USED BY LINK'),
        ('B.SilkS', 24.0, 33.0, 0, 1.2, 'SOCKETS J1 J2 ON THIS SIDE'),
    ]
    return b


# ==========================================================================
#  BOARD B  -  tang-bridge
# ==========================================================================

def board_b():
    OUT = [(0, 0), (90, 0), (90, 46), (0, 46)]
    b = Board('tang-bridge',
              'Hermes Lite 2 <-> Gowin DVI bridge, board B (Tang Mega 138K side)',
              OUT, (90, 46),
              origin_note='local (0,0) = 4 mm outboard of J14 pin 1 '
                          '(user must verify against the dock)')

    # J14 socket: 2x20, pin 1 at local (6.0, 8.0), pins step +2.54 mm in x,
    # odd row at y 8.0, even row at y 10.54.
    j14 = {str(n): None for n in range(1, 41)}
    j14.update({
        '9': 'LINK_R0', '10': 'LINK_D0', '11': 'P5V_J14', '12': 'GND',
        '13': 'LINK_R1', '14': 'LINK_D1', '15': 'LINK_R2', '16': 'LINK_D2',
        '17': 'LINK_CMD', '18': 'LINK_D3', '19': 'LINK_STAT', '20': 'LINK_CLK',
        '31': 'LINK_FSER', '32': 'LINK_D4', '33': 'LINK_PRESENT',
        '34': 'LINK_AUX', '35': 'LINK_REVCLK', '36': 'LINK_D5',
        '39': 'SPARE1_J14', '40': 'SPARE0_J14',
    })
    b.add(Part('J1', 'SKT2x20', 'J14 2x20 socket', j14,
               lcsc='C50982', mfr='2.54mm 2x20P female header',
               desc='Mates the 2x20 male header the user solders into the Tang '
                    'dock J14 holes (Bank 4)',
               at=(6.0 + 19 * 2.54 / 2.0, 9.27), rot=0, layer='B.Cu',
               note='Bottom side. Every J14 pin not in PINMAP.md is left open '
                    'so PMOD0, PMOD1 and the DVP camera stay usable.'))

    b.add(Part('J2', 'DVI', 'DVI-D dual link FWD',
               dvi_pins('C1', 'C1_5V_NC', 'C1_HPD', 'C1_SCL', 'C1_SDA', 'SHLD1'),
               mfr='Molex 74320-4004 or equivalent DVI-D dual-link receptacle, '
                   'right angle, through hole',
               desc='Cable 1 "FWD": HL2 -> Gowin, 7 pairs received by this board',
               at=(22.0, 44.0), rot=0))
    b.add(Part('J3', 'DVI', 'DVI-D dual link REV',
               dvi_pins('C2', None, 'C2_HPD', 'C2_SCL', 'C2_SDA', 'SHLD2'),
               mfr='Molex 74320-4004 or equivalent DVI-D dual-link receptacle, '
                   'right angle, through hole',
               desc='Cable 2 "REV": Gowin -> HL2, 7 pairs driven by this board',
               at=(64.0, 44.0), rot=0))
    b.parts[-1].pins['14'] = 'C2_5V_NC'

    # ---- receivers for cable 1 ----
    rcv_map = [('U1', ['CLK', 'D0', 'D1', 'D2'], (18.0, 30.0)),
               ('U2', ['D3', 'D4', 'D5', 'UNUSED'], (18.0, 36.0))]
    for ref, lanes, at in rcv_map:
        pins = {'9': 'RXEN_N', '16': '+3V3', '12': 'GND', '13': '+3V3'}
        rp = {0: '2', 1: '3', 2: '6', 3: '7'}
        rn = {0: '1', 1: '4', 2: '5', 3: '8'}
        ro = {0: '15', 1: '14', 2: '11', 3: '10'}
        for i, lane in enumerate(lanes):
            if lane == 'UNUSED':
                pins[rp[i]] = 'RX_UNUSED_P'
                pins[rn[i]] = 'RX_UNUSED_N'
                pins[ro[i]] = 'RXO_UNUSED'
            else:
                pins[rp[i]] = 'C1_%s_P' % lane
                pins[rn[i]] = 'C1_%s_N' % lane
                pins[ro[i]] = 'RXO_' + lane
        b.add(Part(ref, 'LVDS_RCV', 'DS90LV048A', pins, lcsc='C87137',
                   mfr='DS90LV048ATMTCX/NOPB',
                   desc='Quad LVDS receiver, >=400 Mbps, TSSOP-16', at=at))

    # ---- drivers for cable 2 ----
    drv_lanes = [('U3', ['REVCLK', 'R0', 'R1', 'R2'],
                  ['CLK', 'D0', 'D1', 'D2'], (60.0, 30.0)),
                 ('U4', ['FSER', 'SP0', 'SP1', 'SPARE'],
                  ['D3', 'D4', 'D5', 'SPARE'], (60.0, 36.0))]
    for ref, srcs, lanes, at in drv_lanes:
        pins = {'1': '+3V3', '4': '+3V3', '5': 'GND', '8': 'GND'}
        din = {0: '2', 1: '3', 2: '6', 3: '7'}
        dp = {0: '15', 1: '14', 2: '11', 3: '10'}
        dn = {0: '16', 1: '13', 2: '12', 3: '9'}
        for i, (s, lane) in enumerate(zip(srcs, lanes)):
            if lane == 'SPARE':
                pins[din[i]] = 'GND'
                pins[dp[i]] = 'DRV_SP_P'
                pins[dn[i]] = 'DRV_SP_N'
            else:
                pins[din[i]] = 'DRVI_' + s
                pins[dp[i]] = 'C2_%s_P' % lane
                pins[dn[i]] = 'C2_%s_N' % lane
        b.add(Part(ref, 'LVDS_DRV', 'DS90LV047A', pins, lcsc='C201946',
                   mfr='DS90LV047ATM/NOPB',
                   desc='Quad LVDS driver, >=400 Mbps, SOIC-16', at=at))

    b.add(Part('U5', 'LDO33', 'AMS1117-3.3', {
        '1': 'GND', '2': '+3V3', '3': 'P5V_J14',
    }, lcsc='C6186', mfr='AMS1117-3.3',
        desc='3.3 V board supply from J14 pin 11 (5V_Peripheral)',
        at=(84.0, 20.0)))

    b.add(Part('J4', 'HDR1x03', 'RX MODE', {
        '1': '+3V3', '2': 'RXEN_N', '3': 'C1_HPD',
    }, lcsc='C2337', mfr='2.54mm 1x3P pin header',
        desc='Cable-1 receiver enable: 2-3 = auto (default), 1-2 = force '
             'disabled (needed for the direct-LVDS mode), open = always enabled',
        at=(44.0, 20.0), rot=90))
    b.add(Part('J5', 'HDR2x02', 'SPARE IN', {
              '1': 'DRVI_SP0', '2': 'DRVI_SP1', '3': 'GND', '4': 'GND',
    }, lcsc='C124375', mfr='2.54mm 2x2P pin header', dnp=True,
        desc='Drives the two spare cable-2 lanes from a flying lead',
        at=(50.0, 20.0)))
    b.add(Part('J6', 'HDR1x02', 'GND AUX', {
        '1': 'GND', '2': 'GND',
    }, lcsc='C2337', mfr='2.54mm 1x2P pin header',
        desc='Extra ground wire to a dock PMOD GND pin; J14 has only one '
             'ground pin', at=(88.0, 6.0), rot=90))

    # ---- ESD ----
    lines = []
    for lane in DVI_LANES:
        lines += ['C1_%s_P' % lane, 'C1_%s_N' % lane]
    lines += ['C1_SCL', 'C1_SDA', 'C1_HPD', 'C1_5V_NC']
    for lane in DVI_LANES:
        lines += ['C2_%s_P' % lane, 'C2_%s_N' % lane]
    lines += ['C2_SCL', 'C2_SDA', 'C2_HPD']
    arr, _ = esd_arrays('D', 1, lines, 'Place within 5 mm of the DVI connector pins.')
    for i, a in enumerate(arr):
        a.at = (6.0 + (i % 5) * 8.0, 41.0 + (i // 5) * 4.0)
    b.add(*arr)

    rs = []
    # receiver output damping into the Gowin pins
    for i, lane in enumerate(DVI_LANES):
        rs.append(R('R%d' % (1 + i), '22R', 'RXO_' + lane, 'LINK_' + lane,
                    lcsc='C25092',
                    desc='Receiver output damping into J14, lane %s' % lane))
    # direct-LVDS bypass links (all DNP)
    bleg = {'CLK': 'LINK_STAT', 'D0': 'LINK_R0', 'D1': 'LINK_R1',
            'D2': 'LINK_R2', 'D3': 'LINK_CMD', 'D4': 'LINK_FSER',
            'D5': 'LINK_REVCLK'}
    for i, lane in enumerate(DVI_LANES):
        rs.append(R('R%d' % (10 + 2 * i), '0R', 'C1_%s_P' % lane,
                    'LINK_' + lane, lcsc='C17168', dnp=True,
                    desc='Direct-LVDS link, cable-1 %s+ straight to the J14 '
                         'A (T) leg' % lane,
                    note='Fit only in direct-LVDS mode; see PINMAP.md 4.3.'))
        rs.append(R('R%d' % (11 + 2 * i), '0R', 'C1_%s_N' % lane, bleg[lane],
                    lcsc='C17168', dnp=True,
                    desc='Direct-LVDS link, cable-1 %s- straight to the J14 '
                         'B (C) leg' % lane,
                    note='Fit only in direct-LVDS mode; disables the signal '
                         'normally on that B leg.'))
    # driver input damping and pull-downs
    for i, (src, dst) in enumerate([('LINK_REVCLK', 'DRVI_REVCLK'),
                                    ('LINK_R0', 'DRVI_R0'),
                                    ('LINK_R1', 'DRVI_R1'),
                                    ('LINK_R2', 'DRVI_R2'),
                                    ('LINK_FSER', 'DRVI_FSER')]):
        rs.append(R('R%d' % (40 + i), '22R', src, dst, lcsc='C25092',
                    desc='Driver input damping, %s' % dst))
    for i, net in enumerate(['DRVI_REVCLK', 'DRVI_R0', 'DRVI_R1', 'DRVI_R2',
                             'DRVI_FSER', 'DRVI_SP0', 'DRVI_SP1']):
        rs.append(R('R%d' % (50 + i), '10k', net, 'GND', lcsc='C25744',
                    desc='Defines %s while the Gowin is unconfigured' % net))
    rs.append(R('R60', '0R', 'SPARE0_J14', 'DRVI_SP0', lcsc='C17168', dnp=True,
                desc='Optional: drive spare lane 0 from J14 pin 40 (P14, '
                     'shared with the DVP camera)'))
    rs.append(R('R61', '0R', 'SPARE1_J14', 'DRVI_SP1', lcsc='C17168', dnp=True,
                desc='Optional: drive spare lane 1 from J14 pin 39 (R14, '
                     'shared with the DVP camera)'))
    rs.append(R('R62', '0R', 'C1_SCL', 'LINK_STAT', lcsc='C17168',
                desc='Status UART from the HL2 into J14 pin 19; remove in '
                     'direct-LVDS mode'))
    rs.append(R('R63', '0R', 'C1_SDA', 'LINK_AUX', lcsc='C17168',
                desc='Aux slow line from the HL2 into J14 pin 34'))
    rs.append(R('R64', '0R', 'C1_HPD', 'LINK_PRESENT', lcsc='C17168',
                desc='Cable-1 detect into J14 pin 33'))
    rs.append(R('R65', '10k', 'C1_HPD', '+3V3', lcsc='C25744',
                desc='Cable-1 detect pull-up; low = cable 1 plugged in'))
    rs.append(R('R66', '1k', 'C2_HPD', 'GND', lcsc='C21190',
                desc='Ties cable-2 HPD low so board A sees "cable present"'))
    rs.append(R('R67', '100R', 'LINK_CMD', 'C2_SDA', lcsc='C25076',
                desc='Slow command UART out of J14 pin 17 onto cable 2 DDC SDA'))
    for i, lane in enumerate(DVI_LANES):
        rs.append(R('R%d' % (70 + i), '100R', 'C1_%s_P' % lane, 'C1_%s_N' % lane,
                    lcsc='C25076',
                    desc='Differential termination, cable 1 lane %s. Keep fitted '
                         'in direct-LVDS mode and set DIFF_RESISTOR=OFF.' % lane))
    rs.append(R('R80', '10k', 'RX_UNUSED_P', '+3V3', lcsc='C25744',
                desc='Bias for the unused receiver channel'))
    rs.append(R('R81', '10k', 'RX_UNUSED_N', 'GND', lcsc='C25744',
                desc='Bias for the unused receiver channel'))
    rs.append(R('R82', '0R', 'SHLD1', 'GND', lcsc='C17168', big=True,
                desc='Cable-1 shell to board ground'))
    rs.append(R('R83', '0R', 'SHLD2', 'GND', lcsc='C17168', big=True,
                desc='Cable-2 shell to board ground'))
    for i, r in enumerate(rs):
        if r.at is None:
            r.at = (3.0 + (i % 30) * 2.8, 14.0 + (i // 30) * 2.2)
    b.add(*rs)

    cs = [
        C('C1', '100nF', '+3V3', 'GND', lcsc='C1525', desc='U1 VCC'),
        C('C2', '100nF', '+3V3', 'GND', lcsc='C1525', desc='U2 VCC'),
        C('C3', '100nF', '+3V3', 'GND', lcsc='C1525', desc='U3 VCC'),
        C('C4', '100nF', '+3V3', 'GND', lcsc='C1525', desc='U4 VCC'),
        C('C5', '10uF', '+3V3', 'GND', lcsc='C15525', big=True, desc='+3V3 bulk'),
        C('C6', '100nF', '+3V3', 'GND', lcsc='C1525', desc='+3V3 bulk HF'),
        C('C7', '10uF', 'P5V_J14', 'GND', lcsc='C15525', big=True,
          desc='5 V input bulk'),
        C('C8', '100nF', 'P5V_J14', 'GND', lcsc='C1525', desc='5 V input HF'),
        C('C9', '10uF', '+3V3', 'GND', lcsc='C15525', big=True,
          desc='U5 output bulk'),
        C('C10', '100nF', '+3V3', 'GND', lcsc='C1525', desc='extra +3V3'),
    ]
    for i, c in enumerate(cs):
        c.at = (3.0 + i * 2.6, 11.5)
    b.add(*cs)

    tps = ['LINK_CLK', 'LINK_D0', 'LINK_D1', 'LINK_D2', 'LINK_D3', 'LINK_D4',
           'LINK_D5', 'LINK_STAT', 'LINK_AUX', 'LINK_PRESENT', 'LINK_CMD',
           'LINK_REVCLK', 'LINK_R0', 'LINK_R1', 'LINK_R2', 'LINK_FSER',
           'C1_HPD', 'C2_HPD', 'C2_SCL', 'C1_5V_NC', 'C2_5V_NC',
           '+3V3', 'P5V_J14', 'RXO_UNUSED', 'DRV_SP_P', 'DRV_SP_N',
           'DRVI_SP0', 'DRVI_SP1']
    for i, net in enumerate(tps):
        p = TP('TP%d' % (i + 1), net)
        p.at = (3.0 + (i % 20) * 2.8, 25.0 + (i // 20) * 2.8)
        b.add(p)
    for i, at in enumerate([(86.0, 30.0), (86.0, 40.0)]):
        g = TP('TP10%d' % (1 + i), 'GND', t='TPBIG')
        g.at = at
        b.add(g)

    for i, at in enumerate([(3.0, 3.0), (87.0, 43.0)]):
        h = Part('H%d' % (i + 1), 'MH', 'M3', {'1': 'GND'}, at=at,
                 desc='M3 mounting hole, grounded')
        b.add(h)

    # U5 drives +3V3, so only the passively-fed rails need a flag.
    for net in ['GND', 'P5V_J14', 'C1_5V_NC', 'C2_5V_NC']:
        b.add(FLAG(net))

    autoplace(b, [(2.0, 2.0, 88.0, 28.0), (2.0, 30.0, 88.0, 33.0)], [
        (2.0, 5.0, 88.0, 13.0),      # J14 socket + keep-out
        (2.0, 34.0, 88.0, 46.0),     # DVI sockets
        (12.0, 26.0, 26.0, 40.0),    # U1, U2
        (54.0, 26.0, 68.0, 40.0),    # U3, U4
        (78.0, 16.0, 88.0, 24.0),    # U5
        (41.0, 16.0, 54.0, 24.0),    # J4, J5
        (85.0, 2.0, 90.0, 10.0),     # J6
        (0.0, 0.0, 7.0, 7.0),        # H1
        (83.0, 39.0, 90.0, 46.0),    # H2
    ])

    b.texts = [
        ('F.SilkS', 45.0, 3.0, 0, 1.5, 'gowin-bridge board B  (Tang Mega 138K)  rev A'),
        ('F.SilkS', 22.0, 36.0, 0, 2.5, 'IN / FWD'),
        ('F.SilkS', 64.0, 36.0, 0, 2.5, 'OUT / REV'),
        ('F.SilkS', 6.0, 6.0, 0, 1.2, 'J14 pin1'),
        ('B.SilkS', 45.0, 9.0, 0, 1.2, 'SOCKET J1 ON THIS SIDE - MATES DOCK J14'),
    ]
    return b


# ==========================================================================
#  Library emission
# ==========================================================================


def write_libs(outdir, board):
    used = sorted({p.ptype for p in board.parts})
    # ---- symbols ----
    w = W()
    w.open('kicad_symbol_lib')
    w.line('version', '20231120')
    w.line('generator', q('gowin-bridge-gen'))
    for t in used:
        symlib, symname, fplib, fpname = TYPES[t]
        fpref = '%s:%s' % (LOCAL_FP, fpname) if fpname else ''
        if symlib is None:
            if symname == 'DS90LV047A':
                build_custom_symbol(
                    w, symname, DRV_PINS, fpref,
                    'https://www.ti.com/lit/ds/symlink/ds90lv047a.pdf',
                    'Quad LVDS differential line driver, 400 Mbps, '
                    'EN high + EN* low = enabled')
            else:
                build_custom_symbol(
                    w, symname, RCV_PINS, fpref,
                    'https://www.ti.com/lit/ds/symlink/ds90lv048a.pdf',
                    'Quad LVDS differential line receiver, 400 Mbps, '
                    'EN high + EN* low = enabled')
        else:
            sym, parent = SYMLIB.get(symlib, symname)
            K.emit_symbol(w, symname, sym, parent, fpref)
    w.close_inline()
    with open(os.path.join(outdir, LOCAL_SYM + '.kicad_sym'), 'w',
              encoding='utf-8') as f:
        f.write(w.text())

    # ---- footprints ----
    pretty = os.path.join(outdir, LOCAL_FP + '.pretty')
    os.makedirs(pretty, exist_ok=True)
    fps = {}
    for t in used:
        symlib, symname, fplib, fpname = TYPES[t]
        if not fpname:
            continue
        node = FPLIB.get(fplib, fpname)
        fps[fpname] = node
        K.emit_footprint_lib(os.path.join(pretty, fpname + '.kicad_mod'),
                             fpname, node)
    return fps


# ==========================================================================
#  Schematic emission
# ==========================================================================

SHEET = (1189.0, 841.0)     # A0


def write_sch(outdir, board):
    path = os.path.join(outdir, board.name + '.kicad_sch')
    # gather symbol geometry
    geo = {}
    for t in sorted({p.ptype for p in board.parts}):
        symlib, symname, fplib, fpname = TYPES[t]
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
            geo[t] = g
        else:
            sym, parent = SYMLIB.get(symlib, symname)
            geo[t] = K.symbol_pin_geometry(sym, parent)

    # pack parts into rows
    placed = []
    cursor_x, cursor_y, row_h = 20.0, 30.0, 0.0
    LBL = 34.0
    for p in board.parts:
        g = geo[p.ptype]
        if not g:
            wpx = wpy = 10.0
            minx = miny = 0.0
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
        # symbol origin so that the leftmost pin sits LBL from the cell edge
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
    w.line('rev', q('A'))
    w.line('company', q('Hermes-Lite 2 companion - gowin-bridge'))
    w.line('comment', '1', q('Generated by tools/gen_gowin_bridge.py - do not '
                             'hand-edit; edit the generator instead'))
    w.line('comment', '2', q('Nets are joined by local labels on every pin '
                             '(netlist-style schematic)'))
    w.line('comment', '3', q('Authoritative pin map: '
                             'hardware/companions/gowin-bridge/PINMAP.md'))
    w.close_inline()

    # lib_symbols
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

    # symbol instances, wires, labels
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

        # wire + label per pin
        for num, (sx, sy, rot, length, nm, et) in g.items():  # noqa: E501
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
    w.open('layer', q('F.SilkS'))
    w.line('type', q('Top Silk Screen'))
    w.close_inline()
    w.open('layer', q('F.Paste'))
    w.line('type', q('Top Solder Paste'))
    w.close_inline()
    w.open('layer', q('F.Mask'))
    w.line('type', q('Top Solder Mask'))
    w.line('thickness', '0.01')
    w.close_inline()
    w.open('layer', q('F.Cu'))
    w.line('type', q('copper'))
    w.line('thickness', '0.035')
    w.close_inline()
    w.open('layer', q('dielectric 1'))
    w.line('type', q('core'))
    w.line('thickness', '0.2')
    w.line('material', q('FR4'))
    w.line('epsilon_r', '4.5')
    w.line('loss_tangent', '0.02')
    w.close_inline()
    w.open('layer', q('In1.Cu'))
    w.line('type', q('copper'))
    w.line('thickness', '0.0152')
    w.close_inline()
    w.open('layer', q('dielectric 2'))
    w.line('type', q('prepreg'))
    w.line('thickness', '1.065'), w.line('material', q('FR4'))
    w.line('epsilon_r', '4.5')
    w.line('loss_tangent', '0.02')
    w.close_inline()
    w.open('layer', q('In2.Cu'))
    w.line('type', q('copper'))
    w.line('thickness', '0.0152')
    w.close_inline()
    w.open('layer', q('dielectric 3'))
    w.line('type', q('core'))
    w.line('thickness', '0.2')
    w.line('material', q('FR4'))
    w.line('epsilon_r', '4.5')
    w.line('loss_tangent', '0.02')
    w.close_inline()
    w.open('layer', q('B.Cu'))
    w.line('type', q('copper'))
    w.line('thickness', '0.035')
    w.close_inline()
    w.open('layer', q('B.Mask'))
    w.line('type', q('Bottom Solder Mask'))
    w.line('thickness', '0.01')
    w.close_inline()
    w.open('layer', q('B.Paste'))
    w.line('type', q('Bottom Solder Paste'))
    w.close_inline()
    w.open('layer', q('B.SilkS'))
    w.line('type', q('Bottom Silk Screen'))
    w.close_inline()
    w.line('copper_finish', q('None'))
    w.line('dielectric_constraints', 'no')
    w.close_inline()
    w.line('pad_to_mask_clearance', '0.05')
    w.line('allow_soldermask_bridges_in_footprints', 'no')
    w.open('pcbplotparams')
    w.line('layerselection', '0x00000000_00000000_55555555_5755f5ff')
    w.line('plot_on_all_layers_selection', '0x00000000_00000000_00000000_00000000')
    w.line('disableapertmacros', 'no')
    w.line('usegerberextensions', 'no')
    w.line('usegerberattributes', 'yes')
    w.line('usegerberadvancedattributes', 'yes')
    w.line('creategerberjobfile', 'yes')
    w.line('dashed_line_dash_ratio', '12.000000')
    w.line('dashed_line_gap_ratio', '3.000000')
    w.line('svgprecision', '4')
    w.line('plotframeref', 'no')
    w.line('mode', '1')
    w.line('useauxorigin', 'no')
    w.line('hpglpennumber', '1')
    w.line('hpglpenspeed', '20')
    w.line('hpglpendiameter', '15.000000')
    w.line('pdf_front_fp_property_popups', 'yes')
    w.line('pdf_back_fp_property_popups', 'yes')
    w.line('dxfpolygonmode', 'yes')
    w.line('dxfimperialunits', 'yes')
    w.line('dxfusepcbnewfont', 'yes')
    w.line('psnegative', 'no')
    w.line('psa4output', 'no')
    w.line('plotreference', 'yes')
    w.line('plotvalue', 'yes')
    w.line('plotfptext', 'yes')
    w.line('plotinvisibletext', 'no')
    w.line('sketchpadsonfab', 'no')
    w.line('subtractmaskfromsilk', 'no')
    w.line('outputformat', '1')
    w.line('mirror', 'no')
    w.line('drillshape', '1')
    w.line('scaleselection', '1')
    w.line('outputdirectory', q('gerbers/'))
    w.close_inline()
    w.close_inline()

    w.line('net', '0', q(''))
    for name, code in sorted(nets.items(), key=lambda kv: kv[1]):
        w.line('net', str(code), q(name))

    # footprints
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

        def net_of(padnum):
            n = p.pins.get(padnum)
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
                        fp_rot_for_pads=rot)
        w.close_inline()

    # board outline
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

    # silkscreen text
    for layer, tx, ty, trot, tsize, txt in board.texts:
        w.open('gr_text', q(txt))
        w.line('at', fmt(ox + tx), fmt(oy + ty), fmt(trot))
        w.line('layer', q(layer))
        w.line('uuid', q(uuid_for(board.name, 'txt', txt)))
        w.raw('(effects (font (size %s %s) (thickness %s))%s)'
              % (fmt(tsize), fmt(tsize), fmt(tsize / 6.0),
                 ' (justify mirror)' if layer.startswith('B.') else ''))
        w.close_inline()

    # copper zones: GND on F/B/In1, split power plane on In2
    def zone(layer, net, prio, poly, name):
        w.open('zone')
        w.line('net', str(nets[net]))
        w.line('net_name', q(net))
        w.line('layer', q(layer))
        w.line('uuid', q(uuid_for(board.name, 'zone', layer, net, name)))
        w.line('name', q(name))
        w.line('hatch', 'edge', '0.5')
        w.line('priority', str(prio))
        w.open('connect_pads')
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

    zone('In1.Cu', 'GND', 0, pts, 'GND plane (layer 2)')
    zone('F.Cu', 'GND', 0, pts, 'top ground fill')
    zone('B.Cu', 'GND', 0, pts, 'bottom ground fill')
    # layer 3 = power. Main rail across the whole board, plus a small +2V5
    # island at higher priority where board A needs it.
    main = '+3V3'
    zone('In2.Cu', main, 0, pts, 'power plane (layer 3): ' + main)
    if '+2V5' in nets:
        isl = [(18.0, 20.0), (34.0, 20.0), (34.0, 29.0), (18.0, 29.0)]
        zone('In2.Cu', '+2V5', 10, isl, 'power plane island: +2V5')

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
        { "gap": 0.13, "via_gap": 0.25, "width": 0.2 },
        { "gap": 0.2, "via_gap": 0.25, "width": 0.2 }
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
      { "bus_width": 12, "clearance": 0.15, "diff_pair_gap": 0.13,
        "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2, "line_style": 0,
        "microvia_diameter": 0.3, "microvia_drill": 0.1, "name": "Default",
        "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)",
        "track_width": 0.25, "via_diameter": 0.6, "via_drill": 0.3, "wire_width": 6 },
      { "bus_width": 12, "clearance": 0.2, "diff_pair_gap": 0.13,
        "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2, "line_style": 0,
        "microvia_diameter": 0.3, "microvia_drill": 0.1, "name": "LVDS100",
        "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)",
        "track_width": 0.2, "via_diameter": 0.45, "via_drill": 0.25, "wire_width": 6 },
      { "bus_width": 12, "clearance": 0.2, "diff_pair_gap": 0.13,
        "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2, "line_style": 0,
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


def write_pro(outdir, board):
    pats = []
    for name in sorted(board.nets()):
        if name.startswith(('C1_', 'C2_')) and (name.endswith('_P') or
                                                name.endswith('_N')):
            pats.append('      { "netclass": "LVDS100", "pattern": "%s" }' % name)
    for name in ('GND', '+3V3', '+2V5', 'P5V_DVI', 'P5V_J14', 'DB1_3V3',
                 'LDO3V3'):
        if name in board.nets():
            pats.append('      { "netclass": "Power", "pattern": "%s" }' % name)
    txt = PRO_TEMPLATE % {'name': board.name,
                          'patterns': ',\n'.join(pats),
                          'schuuid': uuid_for(board.name, 'sch')}
    with open(os.path.join(outdir, board.name + '.kicad_pro'), 'w',
              encoding='utf-8') as f:
        f.write(txt)
    # local library tables so the project finds its own libs
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
    # group identical passives for the ordering BOM
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
    for b in (board_a(), board_b()):
        outdir = os.path.join(ROOT, b.name)
        os.makedirs(outdir, exist_ok=True)
        fps = write_libs(outdir, b)
        write_sch(outdir, b)
        write_pcb(outdir, b, fps)
        write_pro(outdir, b)
        rows = write_bom(outdir, b)
        nets = b.nets()
        print('%-12s %3d parts, %3d nets, %3d BOM lines -> %s'
              % (b.name, len(b.parts), len(nets), len(rows), outdir))


if __name__ == '__main__':
    main()
