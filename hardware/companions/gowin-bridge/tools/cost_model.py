#!/usr/bin/env python3
"""Cost model for the gowin-bridge board, rev D.

Run:   python tools/cost_model.py [quantity]

Computes the order total from the GENERATED BOM and the GENERATED PCB, so the
figures in COST.md cannot drift from the board.  Quantities, solder-joint
counts and the unique-Extended-part count are all counted here rather than
typed in; only the prices are typed, and every one of them has its source in
COST.md section 7.

rev C's model, which compared two designs on a V-scored panel against two
separate orders, is in git history.  rev D is one design, so there is nothing
to compare: the panel charge and the multi-design engineering fee do not
arise.
"""

import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
BOARD = 'bridge'

# --------------------------------------------------------------------------
# Prices.  Every one from COST.md section 7; read 12-13 September 2026.
# --------------------------------------------------------------------------
FEES = dict(
    setup=8.18,                 # JLCPCB Economic assembly setup, per order
    stencil=1.53,               # per order
    extended_part=3.07,         # per UNIQUE Extended part, per order
    smt_joint=0.0016,           # per joint, 1-100k
    tht_joint=0.0164,           # per joint, factory through-hole
    hand_solder=3.58,           # base fee, only if there are any TH joints
)
PCB_5PC = 12.10                 # 4 layer, 1.6 mm, <=100x100, 5 pcs, lead-free
PCB_5PC_LEADED = 7.00           # the same board with leaded HASL
SHIP_DHL = 21.55                # one shipment to Germany, 2-4 days
SHIP_CHEAP = 6.92               # Global Standard Direct Line, 9-13 days
CABLE = 15.00                   # 10Gtek CAB-8654/8654-8i-P, 0.5 m

# Unit prices at qty 10, from the LCSC pages.
PRICES = {
    'C5432262': 3.17,      # SlimSAS SFF-8654 8i 74P right-angle receptacle
    'C206491': 1.84,       # DS90LV047ATMX/NOPB quad LVDS driver, SOIC-16
    'C87137': 1.43,        # DS90LV048ATMTCX/NOPB quad LVDS receiver
    'C81461': 0.3096,      # SN74AVC4T245PWR
    'C138714': 0.0698,     # TPD4E05U06DQAR, 0.5 pF quad ESD array
    'C194395': 0.0561,     # ME6211C25M5G-N 2.5 V LDO
    'C14709': 0.0159,      # BLM18PG121SN1D ferrite bead
    'C15850': 0.085,       # 10 uF 25 V X5R 0805
    'C1525': 0.0046,       # 100 nF 0402
    'C52923': 0.0097,      # 1 uF 0402
    'C17168': 0.0028,      # 0 R 0402
    'C17477': 0.0045,      # 0 R 0805
    'C25076': 0.0029,      # 100 R 0402
    'C25104': 0.0044,      # 330 R 0402
    'C25117': 0.0027,      # 470 R 0402
    'C25744': 0.0031,      # 10 k 0402
    'C11702': 0.0022,      # 1 k 0402
}
# Tier, from the JLCPCB part pages.  Basic parts never pay the loading fee.
EXTENDED = {'C5432262', 'C206491', 'C87137', 'C81461', 'C138714', 'C194395'}
BASIC = set(PRICES) - EXTENDED

# The through-hole parts the owner fits, so they are NOT on the assembly BOM.
# Five distinct part numbers, and no Basic 2.54 mm through-hole header or
# socket exists in JLCPCB's library at all, so having the factory fit them
# would cost five loading fees on top of their joints.
HAND_FITTED = [
    ('DB1 2x10 female socket, underside (C42431860)', 0.1921),
    ('DB12 2x3 female socket - NOT AT LCSC, cut down a 2x4', 0.10),
    ('CN1 2x5 female socket, underside (C492399)', 0.0863),
    ('JTAG pass-through 2x5 male header (C492422)', 0.0682),
    ('ground-clip 1x2 header (C52016390)', 0.0152),
    ('M3 screw and an 11.04 mm standoff', 0.40),
]
# Not counted as a factory through-hole joint by default: whether JLCPCB will
# solder an SMD-flagged connector's four 2.2 mm shell tails is UNVERIFIED.
SHELL_TAILS = 4


def load_bom():
    path = os.path.join(ROOT, BOARD, BOARD + '-bom.csv')
    qty, unknown = {}, set()
    for r in csv.DictReader(open(path, encoding='utf-8')):
        if r['Populate'] == 'DNP' or not r['LCSC']:
            continue
        qty[r['LCSC']] = qty.get(r['LCSC'], 0) + 1
        if r['LCSC'] not in PRICES:
            unknown.add(r['LCSC'])
    return qty, unknown


def count_joints():
    """SMT and factory through-hole joints, counted from the PCB.  Test pads
    are not solder joints, and the five hand-fitted through-hole parts are
    not the factory's problem."""
    path = os.path.join(ROOT, BOARD, BOARD + '.kicad_pcb')
    txt = open(path, encoding='utf-8').read()
    bom = {r['Designator']: r for r in
           csv.DictReader(open(os.path.join(ROOT, BOARD, BOARD + '-bom.csv'),
                               encoding='utf-8'))}
    hand = {'J2', 'J3', 'J4', 'J5', 'J6'}
    smt = tht = parts = 0
    for m in re.split(r'\(footprint ', txt)[1:]:
        mr = re.search(r'fp_text reference "([^"]+)"', m)
        if not mr:
            continue
        ref = mr.group(1)
        row = bom.get(ref)
        if row is None or row['Populate'] == 'DNP':
            continue
        if ref.startswith('TP') or ref in hand:
            continue
        smt += len(re.findall(r'\(pad "[^"]*" smd ', m))
        if ref != 'J1':
            # J1 is the SlimSAS receptacle: 74 SMD contacts, which the
            # factory reflows, plus four 2.2 mm through-hole shell tails,
            # which the owner solders.  Whether JLCPCB would do them on an
            # SMD-flagged part is UNVERIFIED, so the default assumes not.
            tht += len(re.findall(r'\(pad "[^"]*" thru_hole ', m))
        parts += 1
    return smt, tht, parts


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    if n < 2 or n > 30:
        print('NOTE: JLCPCB Economic assembly is 2 to 30 pieces per design.')
    qty, unknown = load_bom()
    if unknown:
        raise SystemExit('cost_model: no price for %s - add it to PRICES with '
                         'its source' % ', '.join(sorted(unknown)))
    smt, tht, parts = count_joints()
    ext = sorted(k for k in qty if k in EXTENDED)
    per_board = sum(PRICES[k] * v for k, v in qty.items())

    print('gowin-bridge rev D, ONE DESIGN, quantity %d' % n)
    print('-' * 66)
    print('%-44s %10s %10s' % ('', 'per board', 'order'))
    rows = [
        ('bare PCB, 64.50 x 64.95 mm, 4 layer, lead-free HASL',
         None, PCB_5PC),
        ('assembly setup fee', None, FEES['setup']),
        ('stencil', None, FEES['stencil']),
        ('unique Extended part loading, %d x $%.2f' % (len(ext),
                                                       FEES['extended_part']),
         None, len(ext) * FEES['extended_part']),
        ('components (%d placed parts, %d part numbers)'
         % (sum(qty.values()), len(qty)), per_board, per_board * n),
        ('SMT solder joints, %d per board' % smt,
         smt * FEES['smt_joint'], smt * FEES['smt_joint'] * n),
    ]
    if tht:
        rows.append(('factory through-hole joints, %d per board' % tht,
                     tht * FEES['tht_joint'], tht * FEES['tht_joint'] * n))
        rows.append(('hand-soldering base fee', None, FEES['hand_solder']))
    rows.append(('shipping, one shipment to Germany (DHL)', None, SHIP_DHL))
    total = 0.0
    for label, pb, order in rows:
        total += order
        print('%-44s %10s %10.2f'
              % (label, '' if pb is None else '%.2f' % pb, order))
    print('-' * 66)
    print('%-44s %10s %10.2f' % ('TOTAL, delivered', '', total))
    print('%-44s %10s %10.2f' % ('  per board', '', total / n))
    print()
    print('Extended parts paying a loading fee: %s' % ', '.join(ext))
    print('Basic parts, no fee: %s'
          % ', '.join(sorted(k for k in qty if k in BASIC)))
    print()
    hand = sum(v for _, v in HAND_FITTED)
    print('Plus, outside the order:')
    print('  %-42s %19.2f' % ('one SlimSAS 8i cable, 0.5 m', CABLE))
    for label, v in HAND_FITTED:
        print('  %-42s %19.2f' % (label, v * n))
    print('  %-42s %19.2f' % ('hand-fitted parts, subtotal', hand * n))
    print('  %-42s %19.2f' % ('GRAND TOTAL for a working link',
                              total + CABLE + hand * n))
    print()
    print('Options:')
    print('  leaded HASL instead of lead-free            %+9.2f'
          % (PCB_5PC_LEADED - PCB_5PC))
    print('  DS90LV047A in TSSOP-16 (C87097) not SOIC-16 %+9.2f'
          % (-0.43 * 2 * n))
    print('  Global Standard shipping instead of DHL     %+9.2f'
          % (SHIP_CHEAP - SHIP_DHL))
    print('  impedance control (32.84 + 1.04 mandatory)  %+9.2f' % 33.88)
    print('  ENIG instead of lead-free HASL              %+9.2f' % 12.30)
    print()
    print('NOT counted, and UNVERIFIED: whether JLCPCB will solder the')
    print('connector\'s four 2.2 mm through-hole shell tails on an')
    print('SMD-flagged part. If they do, add %d joints at $%.4f plus the'
          % (SHELL_TAILS * n, FEES['tht_joint']))
    print('$%.2f hand-soldering base fee = $%.2f.'
          % (FEES['hand_solder'],
             SHELL_TAILS * n * FEES['tht_joint'] + FEES['hand_solder']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
