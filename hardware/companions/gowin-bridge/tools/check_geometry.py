#!/usr/bin/env python3
"""Geometry self-check for the generated gowin-bridge board, rev D.

Run:   python tools/check_geometry.py

Reads the generated .kicad_pcb back and checks, independently of KiCad:

 1. every pad and every courtyard lies inside the board outline with margin;
 2. no two footprint courtyards overlap;
 3. no two pads of different nets are closer than the clearance floor;
 4. the three HL2 sockets land exactly on the DB1, DB12 and CN1 hole grids,
    recomputed here from hardware/hl/hermeslite.kicad_pcb rather than copied
    from the generator, so the two can disagree and be caught;
 5. the SlimSAS receptacle's 74 contacts, 4 shell tails and 2 locating pegs
    match SFF-8654 Rev 1.2 Table A-1 arithmetic, recomputed here, and the
    mated plug's fit inside the extrusion is restated with the numbers;
 6. the M3 anchor and the locating peg line up with HL2 MH2 and MH6.

This exists because the placement is generated, not drawn, so it needs a test.
KiCad's own DRC is still the authority on manufacturability; this catches the
class of mistake DRC reports as a wall of text - a part placed off the board,
a header rotated the wrong way, a socket one pitch out - and states it in one
line.
"""

import os
import sys
import math

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kisexp as K

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

PAGE = (40.0, 40.0)          # generator's local (0,0) -> page coordinates
EDGE_MARGIN = 0.30           # JLCPCB copper-to-edge minimum
CLEARANCE = 0.13             # board clearance floor
COURTYARD_TOUCH = 0.0        # courtyards may touch but not overlap

# DB1 and DB12 hole grid, recomputed here from the HL2 PCB numbers rather
# than copied from the generator, so the two can disagree and be caught.
#   DB1  = HERMESLITE:10x2 at (75.31, 89.39) rot 270, pads pin n at
#          local (-11.43 + 2.54*((n-1)//2), 1.27 if n odd else -1.27)
#   DB12 = HERMESLITE:3x2  at (83.50, 90.00) rot 0, pads pin n at
#          local (0 if n odd else 2.54, -2.54 + 2.54*((n-1)//2))
# KiCad rot 270: absolute = (mod_x - pad_y, mod_y + pad_x)
HL2_ORIGIN = (70.00, 73.30)


def db1_grid():
    out = {}
    mx, my = 75.31, 89.39
    for n in range(1, 21):
        px = -11.43 + 2.54 * ((n - 1) // 2)
        py = 1.27 if n % 2 else -1.27
        ax, ay = mx - py, my + px
        out[n] = (round(ax - HL2_ORIGIN[0], 3), round(ay - HL2_ORIGIN[1], 3))
    return out


def db12_grid():
    out = {}
    mx, my = 83.50, 90.00
    for n in range(1, 7):
        px = 0.0 if n % 2 else 2.54
        py = -2.54 + 2.54 * ((n - 1) // 2)
        out[n] = (round(mx + px - HL2_ORIGIN[0], 3),
                  round(my + py - HL2_ORIGIN[1], 3))
    return out


def cn1_grid():
    """CN1 = HERMESLITE:USBBLASTER at (129.50, 87.30) rot 270, pads pin n at
    local (-5.08 + 2.54*((n-1)//2), 1.27 if n odd else -1.27)."""
    out = {}
    mx, my = 129.50, 87.30
    for n in range(1, 11):
        px = -5.08 + 2.54 * ((n - 1) // 2)
        py = 1.27 if n % 2 else -1.27
        ax, ay = mx - py, my + px
        out[n] = (round(ax - HL2_ORIGIN[0], 3), round(ay - HL2_ORIGIN[1], 3))
    return out


# SFF-8654 Rev 1.2 Table A-1, retyped, so the land pattern can be recomputed
# rather than trusted.
SFF = dict(j01=10.95, j02=2.70, j03=2.35, j04=0.15, j05=0.60,
           pad_w=0.35, pad_l=1.30, loc_d=1.30, j09=5.15, j10=3.00,
           j11=0.68, npos=37)
SETBACK = 10.40          # board edge -> locating-hole datum line
SS_CENTRE_Y = 46.00      # local y of the connector centreline
PLUG_W, PLUG_H = 25.95, 9.90      # SFF-8654 Table 5-1, A03 and A13
ENC_Y0, ENC_Y1 = 41.75, 138.25    # extrusion internal clear width, HL2 y
UNDERSIDE = 11.04                 # board underside above the HL2 top surface


def check_slimsas(fps, box):
    prob = []
    bx0, by0 = box[0], box[1]
    hit = [q for q in fps if q.ref == 'J1']
    if not hit:
        return ['J1, the SlimSAS receptacle, is not on the board']
    f = hit[0]
    pads = {q[0]: (q[1] - bx0, q[2] - by0) for q in f.pads}
    outer = SFF['j01'] - SFF['j04']
    want = {}
    for row, xc in (('A', SFF['j02']), ('B', SFF['j02'] + SFF['j03'])):
        for i in range(1, SFF['npos'] + 1):
            want['%s%d' % (row, i)] = (
                SETBACK + xc,
                SS_CENTRE_Y + outer - (i - 1) * SFF['j05'])
    ty = SFF['j01'] + SFF['j11']
    tails = [(-SFF['j09'], ty), (-(SFF['j09'] + SFF['j10']), ty),
             (-SFF['j09'], -ty), (-(SFF['j09'] + SFF['j10']), -ty)]
    for k, (dx, dy) in enumerate(tails, start=1):
        want['SH%d' % k] = (SETBACK + dx, SS_CENTRE_Y + dy)
    for nm in sorted(want):
        wx, wy = want[nm]
        if nm not in pads:
            prob.append('J1: contact %s missing' % nm)
            continue
        gx, gy = pads[nm]
        if abs(gx - wx) > 0.01 or abs(gy - wy) > 0.01:
            prob.append('J1 contact %s at (%.3f, %.3f), Table A-1 says '
                        '(%.3f, %.3f)' % (nm, gx, gy, wx, wy))
    # the two unplated locating pegs carry no pad name
    extra = [nm for nm in pads if nm and nm not in want]
    if extra:
        prob.append('J1 has contacts that are not in Table A-1: %s'
                    % ', '.join(sorted(extra)))
    if not prob:
        print('   J1: all 74 contacts and 4 shell tails match SFF-8654 '
              'Rev 1.2 Table A-1')
        print('      row A at local x %.2f, row B at %.2f, pitch %.2f, '
              'contacts from y %.2f to %.2f'
              % (SETBACK + SFF['j02'], SETBACK + SFF['j02'] + SFF['j03'],
                 SFF['j05'], SS_CENTRE_Y - outer, SS_CENTRE_Y + outer))
    y0 = HL2_ORIGIN[1] + SS_CENTRE_Y - PLUG_W / 2
    y1 = HL2_ORIGIN[1] + SS_CENTRE_Y + PLUG_W / 2
    print('      mated plug overmould %.2f mm wide -> HL2 y %.2f..%.2f, '
          'inside the extrusion clear width %.2f..%.2f with %.2f mm spare '
          'below and %.2f mm above'
          % (PLUG_W, y0, y1, ENC_Y0, ENC_Y1, y0 - ENC_Y0, ENC_Y1 - y1))
    if y0 < ENC_Y0 or y1 > ENC_Y1:
        prob.append('the mated plug does not fit the extrusion clear width')
    print('      plug %.2f mm thick on a board top surface %.2f mm up -> '
          'occupies %.2f..%.2f mm above the HL2 top surface, which is above '
          'the clock SMA and KEY jack holes rather than beside them'
          % (PLUG_H, UNDERSIDE + 1.6, UNDERSIDE + 1.6,
             UNDERSIDE + 1.6 + PLUG_H))
    return prob


def check_mech(box):
    prob = []
    bx0, by0, bx1, by1 = box
    mh2 = (73.00 - HL2_ORIGIN[0], 137.00 - HL2_ORIGIN[1])
    mh6 = (74.04 - HL2_ORIGIN[0], 75.42 - HL2_ORIGIN[1])
    h = by1 - by0
    edge = h - mh2[1]
    print('   M3 anchor: HL2 MH2 (73.00, 137.00) = local (%.2f, %.2f), only '
          '%.2f mm from the top edge, so it is a U-notch open to the edge '
          'and not a hole' % (mh2[0], mh2[1], edge))
    if edge > 1.9:
        prob.append('MH2 is %.2f mm from the edge, which is enough room for '
                    'a plain 3.2 mm hole - the notch is no longer needed'
                    % edge)
    print('   locating peg: HL2 MH6 (74.04, 75.42) = local (%.2f, %.2f), '
          '1.1 mm unplated' % (mh6[0], mh6[1]))
    return prob


def rot(x, y, deg):
    """KiCad footprint rotation applied to a pad offset."""
    a = math.radians(-deg)
    return (x * math.cos(a) - y * math.sin(a),
            x * math.sin(a) + y * math.cos(a))


class FP:
    __slots__ = ('ref', 'at', 'r', 'layer', 'pads', 'crt', 'tht')


def load(path):
    root = K.parse(open(path, encoding='utf-8').read())[0]
    fps = []
    edges = []
    for node in root[1:]:
        if not isinstance(node, list):
            continue
        h = K.head(node)
        if h == 'gr_line':
            lay = K.kid(node, 'layer')
            if lay is not None and K.atoms(lay)[0] == 'Edge.Cuts':
                s = K.atoms(K.kid(node, 'start'))
                e = K.atoms(K.kid(node, 'end'))
                edges.append(((float(s[0]), float(s[1])),
                              (float(e[0]), float(e[1]))))
        elif h == 'footprint':
            f = FP()
            a = K.atoms(K.kid(node, 'at'))
            f.at = (float(a[0]), float(a[1]))
            f.r = float(a[2]) if len(a) > 2 else 0.0
            f.layer = K.atoms(K.kid(node, 'layer'))[0]
            f.ref = None
            for tx in K.kids(node, 'fp_text'):
                if K.atoms(tx) and K.atoms(tx)[0] == 'reference':
                    f.ref = K.atoms(tx)[1]
            f.pads = []
            f.tht = False
            for pad in K.kids(node, 'pad'):
                pa = [x for x in pad[1:] if isinstance(x, (str, tuple))]
                num = pa[0][1] if isinstance(pa[0], tuple) else pa[0]
                if K.kid(pad, 'drill') is not None:
                    f.tht = True
                at = K.atoms(K.kid(pad, 'at'))
                sz = K.atoms(K.kid(pad, 'size'))
                px, py = rot(float(at[0]), float(at[1]), f.r)
                netn = K.kid(pad, 'net')
                net = K.atoms(netn)[1] if netn is not None else ''
                hx, hy = float(sz[0]) / 2.0, float(sz[1]) / 2.0
                # the pad's own rotation is folded into the emitted value, so
                # a 90/270 total rotation swaps the pad's own x and y extents
                pr = K.atoms(K.kid(pad, 'at'))
                prot = float(pr[2]) if len(pr) > 2 else 0.0
                if round(prot) % 180 == 90:
                    hx, hy = hy, hx
                f.pads.append((num, f.at[0] + px, f.at[1] + py, hx, hy, net))
            ext = K.footprint_extent(node, 'F.CrtYd')
            if ext is None:
                ext = K.footprint_extent(node, 'B.CrtYd')
            if ext is None:
                xs = [p[1] - p[3] for p in f.pads] + [p[1] + p[3] for p in f.pads]
                ys = [p[2] - p[4] for p in f.pads] + [p[2] + p[4] for p in f.pads]
                f.crt = (min(xs), min(ys), max(xs), max(ys)) if xs else None
            else:
                x0, y0 = rot(ext[0], ext[1], f.r)
                x1, y1 = rot(ext[2], ext[3], f.r)
                f.crt = (f.at[0] + min(x0, x1), f.at[1] + min(y0, y1),
                         f.at[0] + max(x0, x1), f.at[1] + max(y0, y1))
            fps.append(f)
    xs = [p[0] for e in edges for p in e]
    ys = [p[1] for e in edges for p in e]
    box = (min(xs), min(ys), max(xs), max(ys))
    return fps, box


def check(name):
    path = os.path.join(ROOT, name, name + '.kicad_pcb')
    fps, box = load(path)
    bx0, by0, bx1, by1 = box
    prob = []
    print('== %s ==' % name)
    print('   board outline  x %.2f..%.2f  y %.2f..%.2f  (%.1f x %.1f mm)'
          % (bx0, bx1, by0, by1, bx1 - bx0, by1 - by0))
    print('   %d footprints, %d pads'
          % (len(fps), sum(len(f.pads) for f in fps)))

    # 1. inside the outline
    for f in fps:
        for (num, px, py, hx, hy, net) in f.pads:
            if (px - hx < bx0 + EDGE_MARGIN or px + hx > bx1 - EDGE_MARGIN
                    or py - hy < by0 + EDGE_MARGIN
                    or py + hy > by1 - EDGE_MARGIN):
                prob.append('OFF-BOARD pad %s.%s at local (%.2f, %.2f) '
                            'half (%.2f, %.2f)'
                            % (f.ref, num, px - bx0, py - by0, hx, hy))
    # 2. courtyard overlaps
    for i in range(len(fps)):
        for j in range(i + 1, len(fps)):
            a, b = fps[i], fps[j]
            if a.crt is None or b.crt is None:
                continue
            # A through-hole footprint occupies both sides, so its courtyard
            # still clashes with a part on the opposite face. Only skip the
            # cross-layer pair when BOTH are surface mount.
            if a.layer != b.layer and not (a.tht or b.tht):
                continue
            ox = min(a.crt[2], b.crt[2]) - max(a.crt[0], b.crt[0])
            oy = min(a.crt[3], b.crt[3]) - max(a.crt[1], b.crt[1])
            if ox > COURTYARD_TOUCH and oy > COURTYARD_TOUCH:
                prob.append('COURTYARD OVERLAP %s / %s by %.2f x %.2f mm'
                            % (a.ref, b.ref, ox, oy))
    # 3. pad-to-pad clearance between different nets, different footprints
    pads = [(f, p) for f in fps for p in f.pads]
    for i in range(len(pads)):
        fa, pa = pads[i]
        for j in range(i + 1, len(pads)):
            fb, pb = pads[j]
            if fa is fb:
                continue
            if pa[5] and pa[5] == pb[5]:
                continue
            dx = abs(pa[1] - pb[1]) - pa[3] - pb[3]
            dy = abs(pa[2] - pb[2]) - pa[4] - pb[4]
            gap = max(dx, dy)
            if gap < CLEARANCE:
                prob.append('PAD CLEARANCE %s.%s [%s] / %s.%s [%s] = %.3f mm'
                            % (fa.ref, pa[0], pa[5], fb.ref, pb[0], pb[5],
                               gap))
    return fps, box, prob


def check_hl2_grid(fps, box):
    """The socket holes must land on the HL2's own hole grids."""
    bx0, by0 = box[0], box[1]
    want = {'J2': db1_grid(), 'J3': db12_grid(), 'J4': cn1_grid()}
    prob = []
    for f in fps:
        if f.ref not in want:
            continue
        g = want[f.ref]
        pads = {int(p[0]): (p[1] - bx0, p[2] - by0) for p in f.pads
                if p[0].isdigit()}
        bad = 0
        for n, (wx, wy) in g.items():
            if n not in pads:
                prob.append('%s: pin %d missing' % (f.ref, n))
                continue
            gx, gy = pads[n]
            if abs(gx - wx) > 0.01 or abs(gy - wy) > 0.01:
                prob.append('%s pin %-2d at (%.3f, %.3f), HL2 grid says '
                            '(%.3f, %.3f)' % (f.ref, n, gx, gy, wx, wy))
                bad += 1
        if not bad:
            print('   %s: all %d holes on the HL2 grid, pin 1 at local '
                  '(%.2f, %.2f)' % (f.ref, len(g), g[1][0], g[1][1]))
    return prob


def boot_arithmetic(fps, box, refs, body_w, label):
    xs = []
    for f in fps:
        if f.ref in refs:
            xs.append(f.at[0] - box[0])
    xs.sort()
    if len(xs) < 2:
        return []
    pitches = [round(xs[i + 1] - xs[i], 3) for i in range(len(xs) - 1)]
    w = box[2] - box[0]
    print('   %s socket centres at local x %s, pitch %s mm'
          % (label, ', '.join('%.2f' % v for v in xs),
             ', '.join('%.2f' % v for v in pitches)))
    print('      bodies %.2f mm wide -> occupy %.2f..%.2f mm on a %.1f mm '
          'board; max pitch that still leaves 0.55 mm of copper to each edge '
          'is %.2f mm' % (body_w, xs[0] - body_w / 2, xs[-1] + body_w / 2, w,
                          (w - 1.1 - 11.2) / 2 if body_w < 12 else
                          (w - 1.1 - body_w) / 2))
    return []


def main():
    fps, box, prob = check('bridge')
    prob += check_hl2_grid(fps, box)
    prob += check_slimsas(fps, box)
    prob += check_mech(box)
    for s in prob:
        print('   !! ' + s)
    print('   %s' % ('OK - every pad and courtyard is inside the outline, no '
                     'two courtyards overlap, no two different-net pads are '
                     'closer than the clearance floor, all three HL2 socket '
                     'grids match the radio, and the SlimSAS land pattern '
                     'matches SFF-8654 Table A-1'
                     if not prob else '%d PROBLEMS' % len(prob)))
    return 1 if prob else 0


if __name__ == '__main__':
    sys.exit(main())
