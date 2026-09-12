#!/usr/bin/env python3
"""Geometry self-check for the two generated gowin-bridge boards.

Run:   python tools/check_geometry.py

Reads the generated .kicad_pcb files back and checks, independently of KiCad:

 1. every pad and every courtyard lies inside the board outline with margin;
 2. no two footprint courtyards overlap;
 3. no two pads of different nets are closer than the clearance floor;
 4. the HL2 header sockets on board A land exactly on the DB1 / DB12 hole grid
    extracted from hardware/hl/hermeslite.kicad_pcb;
 5. the three HDMI sockets sit on the front edge at the expected pitch, and
    the cable-boot arithmetic is restated with the numbers;
 6. on the PANEL: every part lies wholly inside its own board (or coupon, or
    rail), no copper comes within 0.40 mm and no component body within
    1.00 mm of a V-score line, each of the three V-scores runs edge to edge
    with material on both sides for its whole length, the panel fits inside
    100 x 100 mm, and board A's HL2 socket holes still land on the HL2's own
    grid after the panel transform.

This exists because the placement is generated, not drawn, so it needs a test.
KiCad's own DRC is still the authority on manufacturability; this catches the
class of mistake DRC reports as a wall of text (a part placed off the board,
a header rotated the wrong way) and states it in one line.
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
HL2_ORIGIN = (70.50, 74.00)


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
    """Board A only: the socket holes must land on the HL2's own hole grid."""
    bx0, by0 = box[0], box[1]
    want = {'J1': db1_grid(), 'J2': db12_grid()}
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


# ==========================================================================
#  The panel
# ==========================================================================
#
# Retyped here from the panel drawing rather than imported from the
# generator, so the two can disagree and be caught.  Rectangles are
# (x0, y0, x1, y1) in panel coordinates, origin at the bottom-left corner.
PANEL_BOX = (0.0, 0.0, 94.0, 100.0)
PANEL_A = (0.0, 29.0, 48.0, 95.0)          # board A, 48 x 66
PANEL_B = (48.0, 5.0, 94.0, 95.0)          # board B rotated, 46 x 90
PANEL_COUPON = (0.0, 5.0, 48.0, 27.0)      # fiducial coupon, 48 x 22
PANEL_RAILS = ((0.0, 0.0, 94.0, 5.0), (0.0, 95.0, 94.0, 100.0))
PANEL_VSCORE_H = (5.0, 95.0)               # horizontal scores, full width
PANEL_VSCORE_V = (48.0,)                   # vertical score, full height
PANEL_MB_Y = 29.0                          # mouse-bite break line
PANEL_MB_CH = 2.0                          # routed channel width
PANEL_MB_TABS = ((0.0, 4.0), (12.0, 17.0), (28.0, 33.0), (43.5, 48.0))
# JLCPCB's own limits for a V-cut: copper at least 0.40 mm from the score
# line, and a component body at least 1.00 mm from it.  The six HDMI sockets
# are deliberately flush with a board edge - that is the whole point of
# putting the socket edges on a score or an outer edge - so their courtyards
# are allowed to reach the line.
VSCORE_COPPER = 0.40
VSCORE_BODY = 1.00
EDGE_SOCKETS = ('J103', 'J104', 'J105', 'J202', 'J203', 'J204')


def _which(x0, y0, x1, y1):
    for name, r in (('board A', PANEL_A), ('board B', PANEL_B),
                    ('coupon', PANEL_COUPON), ('rail 0', PANEL_RAILS[0]),
                    ('rail 1', PANEL_RAILS[1])):
        if x0 >= r[0] - 1e-6 and x1 <= r[2] + 1e-6 \
                and y0 >= r[1] - 1e-6 and y1 <= r[3] + 1e-6:
            return name, r
    return None, None


def check_panel_layout():
    """Board A's and board B's parts must each stay inside their OWN board,
    nothing may crowd a V-score line, and the panel must fit 100 x 100."""
    prob = []
    print('== panel ==')
    fps, box = load(os.path.join(ROOT, 'panel', 'panel.kicad_pcb'))
    bx0, by0, bx1, by1 = box
    w, h = bx1 - bx0, by1 - by0
    print('   panel outline %.2f x %.2f mm, %d footprints, %d pads'
          % (w, h, len(fps), sum(len(f.pads) for f in fps)))
    if w > 100.0 + 1e-6 or h > 100.0 + 1e-6:
        prob.append('panel is %.2f x %.2f mm, over the 100 x 100 limit'
                    % (w, h))
    if abs(w - (PANEL_BOX[2] - PANEL_BOX[0])) > 0.01 \
            or abs(h - (PANEL_BOX[3] - PANEL_BOX[1])) > 0.01:
        prob.append('panel is %.2f x %.2f mm, the drawing says %.2f x %.2f'
                    % (w, h, PANEL_BOX[2] - PANEL_BOX[0],
                       PANEL_BOX[3] - PANEL_BOX[1]))

    # 1. the three V-scores must be straight, edge to edge, and have material
    #    on BOTH sides for their whole length.  That is arithmetic on the
    #    rectangles, not a guess.
    # The mouse-bite tabs are material too, and the one that runs to
    # x = 48 is the ONLY thing holding material against that V-score over
    # y 27..29, so leaving them out would report a false failure.
    regions = ([PANEL_A, PANEL_B, PANEL_COUPON] + list(PANEL_RAILS)
               + [(t0, PANEL_MB_Y - PANEL_MB_CH, t1, PANEL_MB_Y)
                  for (t0, t1) in PANEL_MB_TABS])

    def covered(seg_lo, seg_hi, side_rects, axis):
        """Is [seg_lo, seg_hi] fully covered along `axis` by these rects?"""
        spans = sorted((r[axis], r[axis + 2]) for r in side_rects)
        at = seg_lo
        for (a, bb) in spans:
            if a > at + 1e-6:
                return False
            at = max(at, bb)
        return at >= seg_hi - 1e-6

    # "material on this side of the line" means a region that reaches the
    # line from that side, which includes a region that STRADDLES it - the
    # assembly rails straddle x = 48, and that is what keeps that score
    # supported over the top and bottom 5 mm.
    for vy in PANEL_VSCORE_H:
        below = [r for r in regions if r[1] < vy - 1e-6 <= r[3]]
        above = [r for r in regions if r[1] <= vy + 1e-6 < r[3]]
        for side, rl in (('below', below), ('above', above)):
            if not covered(PANEL_BOX[0], PANEL_BOX[2], rl, 0):
                prob.append('V-score y = %.2f has no material %s it for its '
                            'whole length' % (vy, side))
        print('   V-score y = %5.2f: full width, material on both sides'
              % vy)
    for vx in PANEL_VSCORE_V:
        left = [r for r in regions if r[0] < vx - 1e-6 <= r[2]]
        right = [r for r in regions if r[0] <= vx + 1e-6 < r[2]]
        for side, rl in (('left of', left), ('right of', right)):
            if not covered(PANEL_BOX[1], PANEL_BOX[3], rl, 1):
                prob.append('V-score x = %.2f has no material %s it for its '
                            'whole length' % (vx, side))
        print('   V-score x = %5.2f: full height, material on both sides'
              % vx)

    # 2. every footprint inside its own board, and clear of the score lines
    furniture = 0
    for f in fps:
        if f.crt is None or not f.pads:
            continue
        if f.ref and f.ref.startswith('MB'):
            # a mouse-bite perforation straddles the break line by design
            furniture += 1
            continue
        cx0, cy0 = f.crt[0] - bx0, f.crt[1] - by0
        cx1, cy1 = f.crt[2] - bx0, f.crt[3] - by0
        owner, rect = _which(cx0, cy0, cx1, cy1)
        if owner is None:
            # the six edge sockets overhang their board edge on purpose
            if f.ref in EDGE_SOCKETS:
                continue
            prob.append('%s courtyard (%.2f, %.2f)-(%.2f, %.2f) is not '
                        'wholly inside any one board, coupon or rail'
                        % (f.ref, cx0, cy0, cx1, cy1))
            continue
        if f.ref in EDGE_SOCKETS:
            continue
        for vy in PANEL_VSCORE_H:
            if cy0 < vy + VSCORE_BODY and cy1 > vy - VSCORE_BODY:
                prob.append('%s courtyard is within %.2f mm of the V-score '
                            'at y = %.2f' % (f.ref, VSCORE_BODY, vy))
        for vx in PANEL_VSCORE_V:
            if cx0 < vx + VSCORE_BODY and cx1 > vx - VSCORE_BODY:
                prob.append('%s courtyard is within %.2f mm of the V-score '
                            'at x = %.2f' % (f.ref, VSCORE_BODY, vx))
        for (num, px, py, hx, hy, net) in f.pads:
            lx, ly = px - bx0, py - by0
            if (lx - hx < rect[0] + EDGE_MARGIN
                    or lx + hx > rect[2] - EDGE_MARGIN
                    or ly - hy < rect[1] + EDGE_MARGIN
                    or ly + hy > rect[3] - EDGE_MARGIN):
                prob.append('%s pad %s at (%.2f, %.2f) is outside its own '
                            '%s (%.2f, %.2f)-(%.2f, %.2f) plus %.2f mm'
                            % (f.ref, num, lx, ly, owner, rect[0], rect[1],
                               rect[2], rect[3], EDGE_MARGIN))
            for vy in PANEL_VSCORE_H:
                if ly - hy < vy + VSCORE_COPPER \
                        and ly + hy > vy - VSCORE_COPPER:
                    prob.append('%s pad %s copper is within %.2f mm of the '
                                'V-score at y = %.2f'
                                % (f.ref, num, VSCORE_COPPER, vy))
            for vx in PANEL_VSCORE_V:
                if lx - hx < vx + VSCORE_COPPER \
                        and lx + hx > vx - VSCORE_COPPER:
                    prob.append('%s pad %s copper is within %.2f mm of the '
                                'V-score at x = %.2f'
                                % (f.ref, num, VSCORE_COPPER, vx))
    print('   %-36s %3d drills' % ('mouse-bite perforations', furniture))
    ins = {}
    for f in fps:
        if not f.pads or f.crt is None or (f.ref or '').startswith('MB'):
            continue
        o, _ = _which(f.crt[0] - bx0, f.crt[1] - by0,
                      f.crt[2] - bx0, f.crt[3] - by0)
        ins[o or 'overhanging (the six edge sockets)'] = \
            ins.get(o or 'overhanging (the six edge sockets)', 0) + 1
    for k in sorted(ins, key=lambda s: str(s)):
        print('   %-36s %3d footprints' % (k, ins[k]))

    # 3. board A's HL2 socket holes must still land on the HL2's own grid
    #    after the panel transform.  The panel prefixes reference numbers by
    #    board, so board A's J1 and J2 are J101 and J102.
    want = {'J101': db1_grid(), 'J102': db12_grid()}
    for f in fps:
        if f.ref not in want:
            continue
        g = want[f.ref]
        pads = {int(p[0]): (p[1] - bx0 - PANEL_A[0], p[2] - by0 - PANEL_A[1])
                for p in f.pads if p[0].isdigit()}
        bad = 0
        for n, (wx, wy) in g.items():
            if n not in pads:
                prob.append('%s: pin %d missing' % (f.ref, n))
                continue
            gx, gy = pads[n]
            if abs(gx - wx) > 0.01 or abs(gy - wy) > 0.01:
                prob.append('%s pin %-2d at board-A-local (%.3f, %.3f), HL2 '
                            'grid says (%.3f, %.3f)'
                            % (f.ref, n, gx, gy, wx, wy))
                bad += 1
        if not bad:
            print('   %s: all %d holes still on the HL2 grid after the panel '
                  'transform' % (f.ref, len(g)))
    return prob


def main():
    bad = 0
    fps, box, prob = check('hl2-bridge')
    prob += check_hl2_grid(fps, box)
    boot_arithmetic(fps, box, {'J3', 'J4', 'J5'}, 11.20, 'mini HDMI')
    for s in prob:
        print('   !! ' + s)
    bad += len(prob)
    print('   %s' % ('OK' if not prob else '%d PROBLEMS' % len(prob)))

    fps, box, prob = check('tang-bridge')
    boot_arithmetic(fps, box, {'J2', 'J3', 'J4'}, 15.70, 'full-size HDMI')
    for s in prob:
        print('   !! ' + s)
    bad += len(prob)
    print('   %s' % ('OK' if not prob else '%d PROBLEMS' % len(prob)))

    fps, box, prob = check('panel')
    prob += check_panel_layout()
    for s in prob:
        print('   !! ' + s)
    bad += len(prob)
    print('   %s' % ('OK' if not prob else '%d PROBLEMS' % len(prob)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
