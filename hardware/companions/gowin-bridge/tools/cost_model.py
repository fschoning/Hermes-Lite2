#!/usr/bin/env python3
"""Cost model for the gowin-bridge board: the radio end and the Gowin end of
one design, one outline, fabricated together and snapped apart.

Run:   python tools/cost_model.py [boards]

Computes the order total from the GENERATED BOM and the GENERATED PCB, so the
figures in COST.md cannot drift from the board.  Quantities, solder-joint
counts and the unique-Extended-part count are counted here; only the prices
are typed, and every one has its source in COST.md section 6.

The order is N boards (default 5).  Each board is one radio end plus one
Gowin end, so 5 boards = five of each = five complete links.
"""

import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BOARD = 'bridge'

# --------------------------------------------------------------------------
# Prices.  Read 12-13 September 2026; sources in COST.md section 6.
# --------------------------------------------------------------------------
FEES = dict(
    setup=8.18,                 # JLCPCB Economic assembly setup, per order
    stencil=1.53,               # per order
    extended_part=3.07,         # per UNIQUE Extended part, per order
    smt_joint=0.0016,           # per joint
    tht_joint=0.0164,           # per joint, factory through-hole
    hand_solder=3.58,           # per order, only if any factory TH joints
)
# Bare PCB, live JLCPCB instant quote 13 Sep 2026: FR-4, 4 layer, 64.50 x
# 100.00 mm, 5 pcs, 1 design, single PCB, 1.6 mm, green, lead-free HASL,
# 1 oz outer / 0.5 oz inner: special offer (board) 7.00 + surface finish
# 5.10 = 12.10.  The radio-only order paid the same 12.10.
PCB_PARTS = dict(board=7.00, finish=5.10)
PCB_5 = sum(PCB_PARTS.values())
PCB_RADIO_ONLY_5 = 12.10        # the radio end alone, one design
SHIP_DHL = 21.55                # one shipment to Germany, COST.md rev D
CABLE = 15.00                   # 10Gtek CAB-8654/8654-8i-P, 0.5 m
RADIO_ONLY_ORDER = 132.43       # COST.md rev D: five radio ends, all in

# Unit prices from the LCSC pages.
PRICES = {
    'C5432262': 3.17,      # SlimSAS 8i 74P R/A, 10+ (10 per order now)
    'C206491': 1.84,       # DS90LV047ATMX/NOPB
    'C87137': 1.43,        # DS90LV048ATMTCX/NOPB
    'C81461': 0.3096,      # SN74AVC4T245PWR
    'C138714': 0.0696,     # TPD4E05U06DQAR, 50+ (120 per order now)
    'C194395': 0.0561,     # ME6211C25M5G-N
    'C14709': 0.0159,      # BLM18PG121SN1D
    'C15850': 0.085,       # 10 uF 25 V 0805
    'C1525': 0.0046,       # 100 nF 0402
    'C52923': 0.0097,      # 1 uF 0402
    'C17168': 0.0028,      # 0 R 0402
    'C17477': 0.0045,      # 0 R 0805
    'C25076': 0.0037,      # 100 R 0402
    'C25104': 0.0044,      # 330 R 0402
    'C25117': 0.0027,      # 470 R 0402
    'C25744': 0.0031,      # 10 k 0402
    'C11702': 0.0022,      # 1 k 0402
    'C20917': 0.0853,      # AO3400A, Basic, 5+ (LCSC 13 Sep 2026)
}
EXTENDED = {'C5432262', 'C206491', 'C87137', 'C81461', 'C138714', 'C194395'}

# Hand-fitted, per complete link, outside the JLCPCB order.
HAND_RADIO = [
    ('DB1 2x10 female socket (C42431860)', 0.1921),
    ('DB12 2x3 female socket, cut from a 2x4', 0.10),
    ('CN1 2x5 female socket (C492399)', 0.0863),
    ('JTAG pass-through 2x5 male header (C492422)', 0.0682),
    ('ground-clip 1x2 header (C52016390)', 0.0152),
    ('M3 screw and 11.04 mm standoff', 0.40),
]
HAND_GOWIN = {
    'scheme 1, carrier plate, 7.0-7.5 mm stack': [
        ('dock: 2x18 female 5.0 mm, KH-2.54FH-2X18P-H5.0 (C55160396)',
         0.4507),
        ('adapter: 2x18 male HC-PZ254-11.5L-2X18PZ (C41376109), '
         'upside down', 0.1889),
        ('M3 x 7 mm threaded spacer and screw', 0.40),
    ],
    'scheme 2, case floor, 11.0 mm stack': [
        ('dock: 2x18 male HC-PZ254-11.5L-2X18PZ (C41376109)', 0.1889),
        ('adapter: 2x18 female 8.5 mm, HX PM2.54-2x18P ZC (C42372542)',
         0.4672),
        ('M3 x 11 mm threaded spacer and screw', 0.40),
    ],
}
HAND_REFS = {'J2', 'J3', 'J4', 'J5', 'J6', 'J102'}
SHELL_TAILS = 8                 # four per SlimSAS, two SlimSAS per board


def gowin_part(ref):
    digits = ''.join(c for c in ref if c.isdigit())
    return bool(digits) and int(digits) >= 101 and not ref.startswith('FID')


def load_bom():
    path = os.path.join(ROOT, BOARD, BOARD + '-bom.csv')
    qty = {'radio': {}, 'gowin': {}}
    for r in csv.DictReader(open(path, encoding='utf-8')):
        if r['Populate'] == 'DNP' or not r['LCSC']:
            continue
        end = 'gowin' if gowin_part(r['Designator']) else 'radio'
        qty[end][r['LCSC']] = qty[end].get(r['LCSC'], 0) + 1
        if r['LCSC'] not in PRICES:
            raise SystemExit('cost_model: no price for %s' % r['LCSC'])
    return qty


def count_joints():
    """Factory SMT joints per end, counted from the PCB.  Test pads are not
    joints, and the hand-fitted sockets are not the factory's."""
    path = os.path.join(ROOT, BOARD, BOARD + '.kicad_pcb')
    txt = open(path, encoding='utf-8').read()
    bom = {r['Designator']: r for r in
           csv.DictReader(open(os.path.join(ROOT, BOARD, BOARD + '-bom.csv'),
                               encoding='utf-8'))}
    out = {'radio': 0, 'gowin': 0}
    for m in re.split(r'\(footprint ', txt)[1:]:
        mr = re.search(r'fp_text reference "([^"]+)"', m)
        if not mr:
            continue
        ref = mr.group(1)
        row = bom.get(ref)
        if row is None or row['Populate'] == 'DNP':
            continue
        if ref.startswith('TP') or ref in HAND_REFS:
            continue
        end = 'gowin' if gowin_part(ref) else 'radio'
        out[end] += len(re.findall(r'\(pad "[^"]*" smd ', m))
    return out


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    qty = load_bom()
    joints = count_joints()
    allq = {}
    for end in qty:
        for k, v in qty[end].items():
            allq[k] = allq.get(k, 0) + v
    ext = sorted(k for k in allq if k in EXTENDED)
    comp = {e: sum(PRICES[k] * v for k, v in qty[e].items()) for e in qty}

    once = [
        ('bare PCB: board, %d pcs, 4 layer, 64.50 x 100.00 mm' % n,
         PCB_PARTS['board']),
        ('bare PCB: lead-free HASL', PCB_PARTS['finish']),
        ('assembly setup', FEES['setup']),
        ('stencil', FEES['stencil']),
        ('unique Extended parts, %d x $%.2f' % (len(ext),
                                                FEES['extended_part']),
         len(ext) * FEES['extended_part']),
        ('shipping, one DHL shipment to Germany', SHIP_DHL),
    ]
    per_panel = [
        ('components, radio end', comp['radio']),
        ('components, Gowin end', comp['gowin']),
        ('SMT joints, radio end (%d)' % joints['radio'],
         joints['radio'] * FEES['smt_joint']),
        ('SMT joints, Gowin end (%d)' % joints['gowin'],
         joints['gowin'] * FEES['smt_joint']),
    ]
    t_once = sum(v for _, v in once)
    t_panel = sum(v for _, v in per_panel)
    total = t_once + t_panel * n
    print('gowin-bridge: radio end + Gowin end on one board, %d boards' % n)
    print('-' * 72)
    print('PAID ONCE PER ORDER')
    for label, v in once:
        print('  %-54s %10.2f' % (label, v))
    print('  %-54s %10.2f' % ('subtotal', t_once))
    print('PAID PER BOARD (x %d)' % n)
    for label, v in per_panel:
        print('  %-38s %8.2f each %11.2f' % (label, v, v * n))
    print('  %-54s %10.2f' % ('subtotal', t_panel * n))
    print('-' * 72)
    print('  %-54s %10.2f' % ('ORDER TOTAL, delivered', total))
    print('  %-54s %10.2f' % ('one complete link (radio end + Gowin end)',
                              total / n))
    print('  %-54s %10.2f' % ('radio-only order, COST.md rev D',
                              RADIO_ONLY_ORDER))
    print('  %-54s %10.2f' % ('THE GOWIN HALF: the difference',
                              total - RADIO_ONLY_ORDER))
    print()
    print('Extended part numbers: %s - the Gowin end adds none'
          % ', '.join(ext))
    print('Gowin end, per board: %s' % ', '.join(
        '%d x %s' % (v, k) for k, v in sorted(qty['gowin'].items())))
    print()
    print('Where the difference comes from:')
    parts = [
        ('bare PCB, the larger board against the radio end alone',
         PCB_5 - PCB_RADIO_ONLY_5),
        ('Gowin-end components, %d boards' % n, comp['gowin'] * n),
        ('Gowin-end joints, %d boards' % n,
         joints['gowin'] * FEES['smt_joint'] * n),
    ]
    for label, v in parts:
        print('  %-54s %+8.2f' % (label, v))
    rest = total - RADIO_ONLY_ORDER - sum(v for _, v in parts)
    print('  %-54s %+8.2f' % ('radio end re-counted (prices, joints, the '
                              'AUXIO interlock)', rest))
    print()
    print('Outside the order, per link:')
    print('  %-60s %6.2f' % ('SlimSAS cable', CABLE))
    print('  %-60s %6.2f' % ('radio-end hand-fitted parts',
                             sum(v for _, v in HAND_RADIO)))
    for scheme, items in HAND_GOWIN.items():
        print('  Gowin end, %s: %.2f' % (scheme, sum(v for _, v in items)))
        for label, v in items:
            print('    %-58s %6.2f' % (label, v))
    print()
    print('NOT counted, UNVERIFIED: JLCPCB soldering the %d SlimSAS shell '
          'tails per board: %d x %d x $%.4f + $%.2f = $%.2f.'
          % (SHELL_TAILS, SHELL_TAILS, n, FEES['tht_joint'],
             FEES['hand_solder'],
             SHELL_TAILS * n * FEES['tht_joint'] + FEES['hand_solder']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
