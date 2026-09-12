#!/usr/bin/env python3
"""Cost model for the gowin-bridge boards, in the categories JLCPCB bills.

Run:   python tools/cost_model.py

Prints the tables in COST.md.  It exists so the arithmetic is reproducible
and so the answer can be re-derived when a price moves, rather than being a
set of numbers typed into a document once.

Every fee rate and every unit price in FEES and PRICES below was read off a
live JLCPCB or LCSC page; the date and the source are in the comment beside
it.  The part counts, joint counts and unique-part counts are NOT typed in -
they are counted from the generated BOMs and PCBs by count_design(), so they
cannot drift from the boards.

WHAT IS AND IS NOT TRUSTWORTHY, stated up front:

* rev C's figures are quotes and counted values.
* rev B's figures are a RECONSTRUCTION.  rev B was costed before the joint
  fees, the hand-soldering base fee and the second shipment were known about,
  and its BOM contained three LCSC part numbers that do not exist and two
  more that JLCPCB will not place.  So "rev B as published" is an undercount
  of rev B's own design, and the honest comparison is against "rev B
  restated", which applies rev C's fee categories and today's prices to rev
  B's own netlist.  Both are printed.
* The bare-PCB line is the one figure that decides the whole question and it
  is marked with its source and its uncertainty.
"""

import csv
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import kisexp as K

# ===========================================================================
#  Fee schedule.  Source: JLCPCB's published PCBA pricing page, read
#  12 Sep 2026.  Marked (!) where it could not be verified against a
#  finished quote, because JLCPCB will not compute a full quote without a
#  login and an uploaded placement file.
# ===========================================================================
FEES = dict(
    setup_economic=8.18,
    setup_standard=25.56,
    stencil_economic=1.53,
    stencil_standard=8.21,
    panel_fee=8.21,             # charged when the file holds >1 design
    load_extended_economic=3.07,
    load_basic_economic=0.00,
    load_any_standard=1.53,
    joint_smt=0.0016,           # (!) per-joint rate published; not quoted
    joint_tht=0.0164,           # (!) ditto
    handsolder_base=3.58,       # per order
)

# Shipping to Germany, read from the quote form 12 Sep 2026 with the German
# store selected, converted at the rate the two stores' own figures imply.
SHIP_DHL = 21.55                # EUR 18.58, 2-4 days
SHIP_CHEAP = 6.92               # EUR 5.97, Global Standard Direct Line, 9-13 d

# Bare PCB, 4 layer, 1.6 mm, LEAD-FREE HASL, green, 1 oz, 5 pieces.
# *** THIS IS THE LINE THAT DECIDES THE ANSWER, AND IT IS NOW SETTLED. ***
# All four read off JLCPCB's live quote form, US store, 12 Sep 2026.
PCB_PANEL_5 = 52.42       # 94 x 100 mm, "different designs in this file" = 2
PCB_PANEL_5_1DES = 12.20  # the SAME board declared as 1 design
PCB_A_5 = 12.10           # 48 x 66 mm, 1 design
PCB_B_5 = 12.10           # 90 x 46 mm, 1 design
PCB_REVB_PUBLISHED = 14.00  # what rev B booked: 2 x $7.00, no HASL surcharge
PCB_NOTE = (
    "SETTLED. 94 x 100 mm, 4 layer, 5 pcs, lead-free HASL costs $12.20 "
    "declared as ONE design and $52.42 declared as TWO. Of that $40.22 "
    "difference, $16.42 is a PCB-side 'Panel' charge for holding two "
    "designs and $23.80 is the loss of the flat promotional tier, because "
    "a multi-design file cannot use JLCPCB's 'Single PCB' delivery mode. "
    "IT IS NOT A SIZE EFFECT: the flat tier survives while both dimensions "
    "stay under 100 mm and 94 x 100 qualifies, so the panel is already on "
    "the right side of the cap and SHRINKING IT WOULD SAVE NOTHING "
    "(100 x 100 costs $36.40, 100 x 150 costs $39.50). The underlying "
    "$7.00 promotional price is real and reproducible; $12.10 and $12.20 "
    "are $7.00 plus the lead-free HASL surcharge of about $5.10-5.20, "
    "which rev B's $7.00 figure had omitted.")

# LCSC unit prices, at the lowest tier covering quantity 10, read 12 Sep 2026.
PRICES = {
    'C206491': 1.8396, 'C201946': 1.8396,   # quad LVDS driver (same slot)
    'C87137': 1.4348,                       # quad LVDS receiver
    'C465742': 0.9296, 'C53535': 0.9296,    # 8-bit translator (same slot)
    'C81461': 0.3096,                       # 4-bit translator / gated buffer
    'C20917': 0.0800,                       # AO3400A N-MOSFET, Basic
    'C7827': 0.0865,                        # the logic inverter it replaced
    'C138714': 0.0874,                      # quad ESD array
    'C194395': 0.0561,                      # 2.5 V LDO
    'C6186': 0.2198,                        # AMS1117-3.3
    'C2682170': 0.4593,                     # mini HDMI socket
    'C427307': 0.5081,                      # full-size HDMI socket
    'C5124634': 0.3305, 'C50982': 0.3305,   # 2x20 socket (same slot)
    'C42431860': 0.1921, 'C5361769': 0.1921,  # 2x10 socket (same slot)
    'C124413': 0.1417,                      # 2x3 socket
    'C52016391': 0.0239, 'C52016390': 0.0160, 'C2337': 0.1594,  # pin headers
}
HEADERS = {'C52016391', 'C52016390', 'C2337'}

# Reel-only minimum-order batches, once per LCSC order.  The passive figure
# is LCSC's own batch prices summed; the others are the batch price at the
# part's minimum order quantity.
# Reel-only minimums JLCPCB charges as part of the assembly order.  The
# header minimums are gone: those parts are hand-fitted now, so they are
# bought retail instead - see RETAIL below.
BATCH_REVC = [('eleven passive values', 6.50),
              ('0R 0805 C17477, min 100', 0.45)]
# Bought outside the JLCPCB assembly order.  Per set unless marked once.
RETAIL_PER_SET = [('vertical 2x3 socket, HL2 DB12 (Samtec SSQ-103-02-S-D)',
                   1.73),
                  ('long-tail 2x10 socket, HL2 DB1 (Phoenix HWS16492)', 0.99),
                  ('2x20 vertical socket, Tang J14 (C5124634)', 0.3305)]
RETAIL_ONCE = [('one 1x40 2.54 mm header strip, snapped to length', 0.16),
               ('jumper shunts, min 50 (C5305)', 0.50)]
BATCH_REVB = [('fourteen passive values (est.)', 7.40),
              ('pin header strip C2337', 0.16),
              ('jumper shunts C5305, min 50', 0.50)]

# The two sockets that must be bought outside LCSC, per set.
SOCKET_2x3 = 1.73       # Samtec SSQ-103-02-S-D, Mouser, EUR 1.49
SOCKET_2x10 = 0.99      # Phoenix Enterprises HWS16492
RETAIL_SET = sum(v for _, v in RETAIL_PER_SET)
RETAIL_FIX = sum(v for _, v in RETAIL_ONCE)

# JLCPCB Basic/Extended classification, read from their parts library.
EXTENDED = set('''C138714 C194395 C206491 C201946 C2682170 C427307 C465742
C53535 C5124634 C50982 C52016390 C52016391 C7827 C81461 C87137 C2337
C42431860 C5361769 C124413'''.split())
BASIC = set('''C1525 C15850 C17168 C17477 C20917 C25076 C25092 C25104
C25741 C25744 C52923 C6186 C15525 C21190 C25117 C25746 C1555 C25900
C25867'''.split())


def count_design(bom, pcb):
    """Count what the fab bills for, from the generated files."""
    rows = list(csv.DictReader(io.open(bom, encoding='utf-8')))
    placed = {r['Designator'] for r in rows if r['Populate'] == 'yes'}
    lc = {r['Designator']: r['LCSC'] for r in rows}
    uniq = {r['LCSC'] for r in rows
            if r['Populate'] == 'yes' and r['LCSC']}
    ext = {c for c in uniq if c in EXTENDED}
    bas = {c for c in uniq if c in BASIC}
    unknown = uniq - ext - bas
    assert not unknown, 'unclassified LCSC numbers: %s' % sorted(unknown)
    root = K.parse(open(pcb, encoding='utf-8').read())[0]
    smt = tht = 0
    for node in root[1:]:
        if not isinstance(node, list) or K.head(node) != 'footprint':
            continue
        ref = None
        for tx in K.kids(node, 'fp_text'):
            if K.atoms(tx) and K.atoms(tx)[0] == 'reference':
                ref = K.atoms(tx)[1]
        if ref not in placed or not lc.get(ref):
            continue
        for pad in K.kids(node, 'pad'):
            ty = pad[2] if len(pad) > 2 and isinstance(pad[2], str) else ''
            if ty == 'thru_hole':
                tht += 1
            elif ty == 'smd':
                smt += 1
    silicon = sum(PRICES[lc[r]] for r in placed
                  if lc.get(r) in PRICES and lc[r] not in HEADERS)
    return dict(uniq=uniq, ext=ext, bas=bas, smt=smt, tht=tht,
                silicon=silicon)


def table(title, lines, totals):
    w = max(len(a) for a, _, _, _ in lines) + 2
    print()
    print('=' * (w + 46))
    print(title)
    print('=' * (w + 46))
    print('%-*s %12s %12s %12s' % (w, 'charge category', 'rev B pub.',
                                   'rev B rest.', 'rev C'))
    print('-' * (w + 46))
    for name, b0, b1, c in lines:
        f = lambda v: ('-' if v is None else
                       ('not counted' if v == 'nc' else '$%.2f' % v))
        print('%-*s %12s %12s %12s' % (w, name, f(b0), f(b1), f(c)))
    print('-' * (w + 46))
    print('%-*s %12s %12s %12s' % (w, 'TOTAL', '$%.2f' % totals[0],
                                   '$%.2f' % totals[1], '$%.2f' % totals[2]))
    print()
    print('  rev C minus rev B as published : $%+.2f' % (totals[2] - totals[0]))
    print('  rev C minus rev B restated     : $%+.2f' % (totals[2] - totals[1]))
    print('  rev B published understated its own design by $%.2f'
          % (totals[1] - totals[0]))


def build(sets):
    """Both revisions, at `sets` assembled sets, Economic assembly."""
    A = count_design(os.path.join(ROOT, 'hl2-bridge', 'hl2-bridge-bom.csv'),
                     os.path.join(ROOT, 'hl2-bridge', 'hl2-bridge.kicad_pcb'))
    B = count_design(os.path.join(ROOT, 'tang-bridge', 'tang-bridge-bom.csv'),
                     os.path.join(ROOT, 'tang-bridge', 'tang-bridge.kicad_pcb'))
    P = count_design(os.path.join(ROOT, 'panel', 'panel-bom.csv'),
                     os.path.join(ROOT, 'panel', 'panel.kicad_pcb'))
    rb = os.path.join(os.environ.get('REVB_DIR', ''), '')
    # rev B's own counts, from the files checked out of git
    bA = count_design(rb + 'hl2-bridge_hl2-bridge-bom.csv',
                      rb + 'hl2-bridge_hl2-bridge.kicad_pcb')
    bB = count_design(rb + 'tang-bridge_tang-bridge-bom.csv',
                      rb + 'tang-bridge_tang-bridge.kicad_pcb')

    F = FEES
    b_ext = len(bA['ext']) + len(bB['ext'])     # two orders: paid per board
    c_ext = len(P['ext'])                       # one panel: paid once
    b_smt, b_tht = bA['smt'] + bB['smt'], bA['tht'] + bB['tht']
    c_smt, c_tht = A['smt'] + B['smt'], A['tht'] + B['tht']
    b_si = bA['silicon'] + bB['silicon']
    c_si = A['silicon'] + B['silicon']
    b_batch = sum(v for _, v in BATCH_REVB)
    c_batch = sum(v for _, v in BATCH_REVC)

    lines = [
        ('bare PCB, 5 pcs', PCB_REVB_PUBLISHED, PCB_A_5 + PCB_B_5,
         PCB_PANEL_5),
        ('assembly setup', 2 * F['setup_economic'], 2 * F['setup_economic'],
         F['setup_economic']),
        ('stencil', 2 * F['stencil_economic'], 2 * F['stencil_economic'],
         F['stencil_economic']),
        ('panel fee (>1 design)', 0.0, 0.0, F['panel_fee']),
        ('loading, Extended x %d / %d' % (b_ext, c_ext),
         16 * F['load_extended_economic'],
         b_ext * F['load_extended_economic'],
         c_ext * F['load_extended_economic']),
        ('loading, Basic (free on Economic)', 0.0, 0.0, 0.0),
        ('SMT joints %d / %d per set' % (b_smt, c_smt),
         'nc', b_smt * sets * F['joint_smt'], c_smt * sets * F['joint_smt']),
        ('through-hole joints %d / %d' % (b_tht, c_tht),
         'nc', b_tht * sets * F['joint_tht'], c_tht * sets * F['joint_tht']),
        ('hand-solder base fee', 'nc', 2 * F['handsolder_base'],
         F['handsolder_base']),
        ('reel-only minimum batches', 6.50, b_batch, c_batch),
        ('silicon and connectors x %d' % sets,
         sets * b_si, sets * b_si, sets * c_si),
        ('parts bought retail x %d, plus %.2f once'
         % (sets, RETAIL_FIX), 0.0, 0.0,
         sets * RETAIL_SET + RETAIL_FIX),
        ('shipping (2 orders vs 1)', 28.00, 2 * SHIP_DHL, SHIP_DHL),
    ]
    tot = [0.0, 0.0, 0.0]
    for _, b0, b1, c in lines:
        tot[0] += 0.0 if b0 in (None, 'nc') else b0
        tot[1] += 0.0 if b1 in (None, 'nc') else b1
        tot[2] += 0.0 if c in (None, 'nc') else c
    table('%d ASSEMBLED SETS, Economic assembly, shipped DHL Express'
          % sets, lines, tot)

    print()
    print('  delta by line, rev B restated -> rev C (these sum to the total):')
    for name, b0, b1, c in lines:
        v1 = 0.0 if b1 in (None, 'nc') else b1
        v2 = 0.0 if c in (None, 'nc') else c
        if abs(v2 - v1) > 0.005:
            print('    %-44s $%+.2f' % (name, v2 - v1))
    return dict(A=A, B=B, P=P, bA=bA, bB=bB, tot=tot, sets=sets,
                c_si=c_si, b_si=b_si, c_ext=c_ext, b_ext=b_ext,
                c_smt=c_smt, c_tht=c_tht, c_batch=c_batch)


def panel_vs_two_orders(d, sets):
    """Does panelising save money or cost it?  Both, priced."""
    F = FEES
    A, B, P = d['A'], d['B'], d['P']
    ext_two = len(A['ext']) + len(B['ext'])
    ext_one = len(P['ext'])
    si = sets * (A['silicon'] + B['silicon'])
    joints = (sets * (A['smt'] + B['smt']) * F['joint_smt']
              + sets * (A['tht'] + B['tht']) * F['joint_tht'])
    common = (si + joints + d['c_batch'] + sets * RETAIL_SET + RETAIL_FIX)

    one = dict(
        bare=PCB_PANEL_5, setup=F['setup_economic'],
        stencil=F['stencil_economic'], panel=F['panel_fee'],
        loading=ext_one * F['load_extended_economic'],
        hand=F['handsolder_base'], ship=SHIP_DHL)
    two = dict(
        bare=PCB_A_5 + PCB_B_5, setup=2 * F['setup_economic'],
        stencil=2 * F['stencil_economic'], panel=0.0,
        loading=ext_two * F['load_extended_economic'],
        hand=2 * F['handsolder_base'], ship=2 * SHIP_DHL)
    print()
    print('=' * 88)
    print('DOES PANELISING SAVE MONEY?  %d assembled sets, Economic' % sets)
    print('=' * 88)
    print('%-42s %14s %14s %10s' % ('', 'ONE panel', 'TWO orders', 'delta'))
    print('-' * 88)
    rows = [('bare PCB, 5 pcs', 'bare'),
            ('assembly setup', 'setup'), ('stencil', 'stencil'),
            ('panel fee (>1 design)', 'panel'),
            ('Extended loading (%d uniques vs %d)' % (ext_one, ext_two),
             'loading'),
            ('hand-solder base fee', 'hand'),
            ('shipping', 'ship')]
    t1 = t2 = 0.0
    for label, key in rows:
        print('%-42s %14s %14s %10s'
              % (label, '$%.2f' % one[key], '$%.2f' % two[key],
                 '$%+.2f' % (one[key] - two[key])))
        t1 += one[key]
        t2 += two[key]
    print('%-42s %14s %14s %10s'
          % ('identical on both (parts, joints, batches)',
             '$%.2f' % common, '$%.2f' % common, '$0.00'))
    print('-' * 88)
    print('%-42s %14s %14s %10s'
          % ('TOTAL', '$%.2f' % (t1 + common), '$%.2f' % (t2 + common),
             '$%+.2f' % (t1 - t2)))
    print()
    print('  For scale only, NOT AN OPTION: the same panel declared as ONE')
    print('  design would cost $%.2f rather than $%.2f for the bare boards,'
          % (PCB_PANEL_5_1DES, PCB_PANEL_5))
    print('  making the panel route $%.2f. The panel really does hold two'
          % (t1 + common - PCB_PANEL_5 + PCB_PANEL_5_1DES))
    print('  different designs, so declaring one would be a false')
    print('  declaration. It is quoted only to show that $%.2f of the'
          % (PCB_PANEL_5 - PCB_PANEL_5_1DES))
    print('  bare-PCB line is the two-design charge and nothing else.')
    verdict = 'SAVES' if t1 < t2 else 'COSTS'
    print()
    print('  VERDICT: panelising %s $%.2f at %d sets.'
          % (verdict, abs(t1 - t2), sets))
    print('  If the two separate orders can be COMBINED INTO ONE SHIPMENT')
    print('  (unverified), two orders come to $%.2f and panelising %s $%.2f.'
          % (t2 + common - SHIP_DHL,
             'saves' if t1 < t2 - SHIP_DHL else 'costs',
             abs(t1 - (t2 - SHIP_DHL))))
    return t1 + common, t2 + common


def aux_attribution(d):
    """What the bidirectional third cable actually cost, separated from
    everything else that changed."""
    print()
    print('=' * 88)
    print('WHAT THE THIRD CABLE COST, SEPARATED FROM EVERYTHING ELSE')
    print('=' * 88)
    aux = [('2 more quad LVDS drivers on board B, 1 more on board A', 3,
            1.8396),
           ('1 more quad LVDS receiver (board A gains the AUX receiver)', 1,
            1.4348),
           ('2 more 4-bit gated buffers (1 per board)', 2, 0.3096),
           ('2 N-MOSFET strap inverters (1 per board)', 2, 0.0800),
           ('1 more quad ESD array (board A, 8 -> 9)', 1, 0.0874)]
    tot = 0.0
    print('per SET, parts:')
    for label, n, u in aux:
        print('  %-58s %2d x $%.4f = $%5.2f' % (label, n, u, n * u))
        tot += n * u
    print('  %-58s %19s' % ('parts attributable to the third cable, per set',
                            '$%.2f' % tot))
    print()
    print('  extra unique EXTENDED parts = 0. The strap inverter is a')
    print('  Basic-tier MOSFET, and Basic loading is free on Economic.')
    print('  extra board area                              = 0 mm2 '
          '(both boards are the same size as in rev B)')
    print('  extra joints: SMT %+d, through-hole %+d per set'
          % (d['c_smt'] - (d['bA']['smt'] + d['bB']['smt']),
             d['c_tht'] - (d['bA']['tht'] + d['bB']['tht'])))
    for s in (2, 3, 5):
        print('  THIRD CABLE, TOTAL AT %d SETS               = $%.2f'
              % (s, s * tot))
    return tot


def cheapest(sets, leadfree=True, extra_basic=0):
    """The configuration the user has confirmed: no impedance control, the
    slow shipping tier, and the through-hole parts soldered by hand.

    ``extra_basic`` is the number of FURTHER Extended parts that turn out to
    have Basic substitutes, so the effect can be shown before the answer is
    in."""
    A = count_design(os.path.join(ROOT, 'hl2-bridge', 'hl2-bridge-bom.csv'),
                     os.path.join(ROOT, 'hl2-bridge', 'hl2-bridge.kicad_pcb'))
    B = count_design(os.path.join(ROOT, 'tang-bridge', 'tang-bridge-bom.csv'),
                     os.path.join(ROOT, 'tang-bridge', 'tang-bridge.kicad_pcb'))
    P = count_design(os.path.join(ROOT, 'panel', 'panel-bom.csv'),
                     os.path.join(ROOT, 'panel', 'panel.kicad_pcb'))
    F = FEES
    next_ = max(0, len(P['ext']) - extra_basic)
    smt, tht = A['smt'] + B['smt'], A['tht'] + B['tht']
    lines = [
        ('bare PCB, 5 pcs, 94 x 100, 4 layer, %s'
         % ('lead-free HASL' if leadfree else 'leaded HASL'),
         PCB_PANEL_5 if leadfree else PCB_PANEL_5 - 5.20),
        ('assembly setup', F['setup_economic']),
        ('assembly panel fee, 2 designs', F['panel_fee']),
        ('stencil', F['stencil_economic']),
        ('hand-soldering base fee (the HDMI shell legs)',
         F['handsolder_base']),
        ('loading, %d unique Extended parts x $3.07' % next_,
         next_ * F['load_extended_economic']),
        ('loading, %d unique Basic parts' % len(P['bas']), 0.0),
        ('SMT joints, %d per set x %d' % (smt, sets),
         smt * sets * F['joint_smt']),
        ('through-hole joints, %d per set x %d (HDMI shell legs only)'
         % (tht, sets), tht * sets * F['joint_tht']),
        ('silicon and connectors, %d x $%.2f'
         % (sets, A['silicon'] + B['silicon']),
         sets * (A['silicon'] + B['silicon'])),
        ('reel-only minimum batches', sum(v for _, v in BATCH_REVC)),
        ('parts bought and soldered by hand', sets * RETAIL_SET + RETAIL_FIX),
        ('shipping, Global Standard Direct Line (9-13 days)', SHIP_CHEAP),
    ]
    w = max(len(a) for a, _ in lines) + 2
    print()
    print('=' * (w + 14))
    print('CHEAPEST CREDIBLE, %d SETS - no impedance control, slow shipping,'
          % sets)
    print('through-hole parts soldered by hand%s'
          % ('' if leadfree else ', leaded finish'))
    print('=' * (w + 14))
    tot = 0.0
    for name, v in lines:
        print('%-*s %12s' % (w, name, '$%.2f' % v))
        tot += v
    print('-' * (w + 14))
    print('%-*s %12s' % (w, 'TOTAL', '$%.2f' % tot))
    print('%-*s %12s' % (w, 'per set', '$%.2f' % (tot / sets)))
    return tot


def main():
    if not os.environ.get('REVB_DIR'):
        raise SystemExit(
            'Set REVB_DIR to a directory holding rev B\'s files, extracted\n'
            'from git commit a15d05a as:\n'
            '  hl2-bridge_hl2-bridge-bom.csv   hl2-bridge_hl2-bridge.kicad_pcb\n'
            '  tang-bridge_tang-bridge-bom.csv tang-bridge_tang-bridge.kicad_pcb')
    print('BARE-PCB NOTE: ' + PCB_NOTE)
    d2 = build(2)
    d5 = build(5)
    panel_vs_two_orders(d2, 2)
    panel_vs_two_orders(d5, 5)
    aux_attribution(d2)
    cheapest(2)
    cheapest(2, leadfree=False)
    cheapest(2, extra_basic=2)
    cheapest(5)
    print()
    print('=' * 88)
    print('AREA')
    print('=' * 88)
    print('  panel  94 x 100 = %5d mm2' % 9400)
    print('  board A 48 x 66 = %5d mm2' % 3168)
    print('  board B 90 x 46 = %5d mm2' % 4140)
    print('  overhead        = %5d mm2 = %.1f%% of the panel'
          % (9400 - 3168 - 4140, 100.0 * (9400 - 3168 - 4140) / 9400))
    print('    rails  2 x 94 x 5     = %4d mm2' % 940)
    print('    coupon 48 x 22        = %4d mm2' % 1056)
    print('    routed channel 48 x 2 = %4d mm2' % 96)
    print()
    print('  BUT: board B rotated is 90 mm tall, and 2 x 5 mm of rail makes')
    print('  100 mm. Board A is only 66 mm tall, so the 48 x 24 mm under it')
    print('  is dead space the panel carries ANYWAY. The coupon fills 1056')
    print('  of those 1152 mm2, so THE COUPON COSTS NOTHING.')


if __name__ == '__main__':
    main()
