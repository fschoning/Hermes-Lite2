"""Minimal KiCad s-expression tooling for the gowin-bridge board generator.

Why this exists
---------------
The two bridge boards are generated from a single netlist description
(``gen_gowin_bridge.py``) rather than drawn by hand, so that the schematic, the
PCB and the BOM can never drift apart.

Symbol and footprint *geometry* is lifted out of the stock KiCad libraries
(so pinouts and land patterns are the vendor-reviewed ones), but it is
re-emitted here in conservative KiCad 7/8 syntax into project-local libraries.
That makes the projects self-contained and openable in KiCad 8, while still
being readable by KiCad 9/10.

Nothing here talks to KiCad; it is pure text in, text out.
"""

import os
import re
import hashlib

# ---------------------------------------------------------------- parser


def parse(text):
    """Parse s-expression text into nested lists. Atoms stay as strings;
    quoted strings are returned as ('str', value) so quoting is preserved."""
    i = 0
    n = len(text)
    stack = [[]]
    while i < n:
        c = text[i]
        if c == '(':
            new = []
            stack[-1].append(new)
            stack.append(new)
            i += 1
        elif c == ')':
            stack.pop()
            i += 1
        elif c == '"':
            j = i + 1
            out = []
            while j < n:
                if text[j] == '\\':
                    out.append(text[j + 1])
                    j += 2
                elif text[j] == '"':
                    break
                else:
                    out.append(text[j])
                    j += 1
            stack[-1].append(('str', ''.join(out)))
            i = j + 1
        elif c in ' \t\r\n':
            i += 1
        else:
            j = i
            while j < n and text[j] not in ' \t\r\n()"':
                j += 1
            stack[-1].append(text[i:j])
            i = j
    return stack[0]


def head(node):
    return node[0] if node and isinstance(node[0], str) else None


def kids(node, name):
    return [k for k in node[1:] if isinstance(k, list) and head(k) == name]


def kid(node, name):
    k = kids(node, name)
    return k[0] if k else None


def atoms(node):
    """Bare atoms of a node, with quoted strings unwrapped."""
    out = []
    for k in node[1:]:
        if isinstance(k, tuple):
            out.append(k[1])
        elif isinstance(k, str):
            out.append(k)
    return out


# ---------------------------------------------------------------- uuids


def uuid_for(*parts):
    """Deterministic UUID so regenerating the project produces no churn."""
    h = hashlib.sha1('|'.join(str(p) for p in parts).encode()).hexdigest()
    return '%s-%s-%s-%s-%s' % (h[0:8], h[8:12], h[12:16], h[16:20], h[20:32])


# ---------------------------------------------------------------- writer


def q(s):
    s = str(s)
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def fmt(v):
    """Trim floats the way KiCad does."""
    if isinstance(v, float):
        t = ('%.6f' % v).rstrip('0').rstrip('.')
        return t if t not in ('', '-0') else '0'
    return str(v)


class W:
    """Tiny indent-aware s-expression writer."""

    def __init__(self):
        self.lines = []
        self.depth = 0

    def open(self, *toks):
        self.lines.append('\t' * self.depth + '(' + ' '.join(str(t) for t in toks))
        self.depth += 1

    def close(self):
        self.depth -= 1
        self.lines[-1] += ')' if self.lines[-1].endswith(')') or True else ')'
        # closing paren goes on its own line for readability
        self.lines.append('\t' * self.depth + ')')

    def close_inline(self):
        self.depth -= 1
        self.lines[-1] += ')'

    def line(self, *toks):
        self.lines.append('\t' * self.depth + '(' + ' '.join(str(t) for t in toks) + ')')

    def raw(self, s):
        self.lines.append('\t' * self.depth + s)

    def text(self):
        return '\n'.join(self.lines) + '\n'


def effects(size=1.27, hide=False, justify=None, mirror=False):
    s = '(effects (font (size %s %s))' % (fmt(size), fmt(size))
    if justify:
        s += ' (justify %s)' % justify
    if hide:
        s += ' (hide yes)'
    return s + ')'


# ------------------------------------------------------- symbol extraction


class SymLib:
    """Reads stock .kicad_sym files and re-emits selected symbols."""

    def __init__(self, search_dirs):
        self.dirs = [d for d in search_dirs if d and os.path.isdir(d)]
        self._cache = {}

    def _load(self, libname):
        if libname in self._cache:
            return self._cache[libname]
        for d in self.dirs:
            p = os.path.join(d, libname + '.kicad_sym')
            if os.path.isfile(p):
                root = parse(open(p, encoding='utf-8').read())[0]
                syms = {}
                for s in kids(root, 'symbol'):
                    syms[atoms(s)[0]] = s
                self._cache[libname] = syms
                return syms
        raise IOError('symbol library not found: %s (looked in %s)' % (libname, self.dirs))

    def get(self, libname, symname):
        """Return a symbol node with any (extends ...) resolved against its parent."""
        syms = self._load(libname)
        if symname not in syms:
            raise KeyError('%s:%s not in library' % (libname, symname))
        sym = syms[symname]
        ext = kid(sym, 'extends')
        if ext is None:
            return sym, None
        parent = syms[atoms(ext)[0]]
        return sym, parent


def emit_symbol(w, name, sym, parent, footprint, datasheet='', description='',
                keywords=''):
    """Write one flattened symbol definition (KiCad 7/8 syntax)."""
    src = parent if parent is not None else sym

    pn = kid(src, 'pin_names')
    pnums = kid(src, 'pin_numbers')

    w.open('symbol', q(name))
    if pnums is not None:
        # KiCad 8 accepts both (pin_numbers hide) and (pin_numbers (hide yes))
        w.line('pin_numbers', 'hide')
    if pn is not None:
        off = kid(pn, 'offset')
        if off is not None:
            w.line('pin_names', '(offset %s)' % fmt(float(atoms(off)[0])))
        else:
            w.line('pin_names', '(offset 0.254)')
    w.line('exclude_from_sim', 'no')
    w.line('in_bom', 'yes')
    w.line('on_board', 'yes')

    props = [
        ('Reference', _prop(sym, src, 'Reference', 'U')),
        ('Value', name.split(':')[-1]),
        ('Footprint', footprint),
        ('Datasheet', datasheet or _prop(sym, src, 'Datasheet', '')),
        ('Description', description or _prop(sym, src, 'Description', '')),
    ]
    y = 0.0
    for i, (k, v) in enumerate(props):
        w.open('property', q(k), q(v))
        w.line('at', '0', fmt(y), '0')
        w.raw(effects(hide=(i >= 2)))
        w.close_inline()
        y -= 2.54
    if keywords:
        w.open('property', q('ki_keywords'), q(keywords))
        w.line('at', '0', '0', '0')
        w.raw(effects(hide=True))
        w.close_inline()

    # graphics: copy every sub-symbol body from the source.
    # Sub-symbol names inside lib_symbols carry NO library prefix.
    base = name.split(':')[-1]
    for sub in kids(src, 'symbol'):
        subname = atoms(sub)[0]
        # rename <src>_a_b -> <base>_a_b
        suffix = subname[subname.rfind('_', 0, subname.rfind('_')):]
        w.open('symbol', q(base + suffix))
        for item in sub[1:]:
            if not isinstance(item, list):
                continue
            h = head(item)
            if h in ('rectangle', 'polyline', 'circle', 'arc'):
                _emit_graphic(w, item)
            elif h == 'pin':
                _emit_pin(w, item)
            elif h == 'text':
                pass
        w.close_inline()
    w.close_inline()


def _prop(sym, src, key, default):
    for node in (sym, src):
        for p in kids(node, 'property'):
            a = atoms(p)
            if a and a[0] == key:
                return a[1] if len(a) > 1 else default
    return default


def _xy(node):
    a = atoms(node)
    return float(a[0]), float(a[1])


def _stroke(w, item, default=0.254):
    st = kid(item, 'stroke')
    width = default
    if st is not None:
        ww = kid(st, 'width')
        if ww is not None:
            width = float(atoms(ww)[0])
    fl = kid(item, 'fill')
    ftype = 'none'
    if fl is not None:
        ft = kid(fl, 'type')
        if ft is not None:
            ftype = atoms(ft)[0]
        else:
            a = atoms(fl)
            if a:
                ftype = a[0]
    return width, ftype


def _emit_graphic(w, item):
    h = head(item)
    width, ftype = _stroke(w, item)
    if h == 'rectangle':
        s = _xy(kid(item, 'start'))
        e = _xy(kid(item, 'end'))
        w.open('rectangle')
        w.line('start', fmt(s[0]), fmt(s[1]))
        w.line('end', fmt(e[0]), fmt(e[1]))
        w.line('stroke', '(width %s)' % fmt(width), '(type default)')
        w.line('fill', '(type %s)' % ftype)
        w.close_inline()
    elif h == 'circle':
        c = _xy(kid(item, 'center'))
        r = float(atoms(kid(item, 'radius'))[0])
        w.open('circle')
        w.line('center', fmt(c[0]), fmt(c[1]))
        w.line('radius', fmt(r))
        w.line('stroke', '(width %s)' % fmt(width), '(type default)')
        w.line('fill', '(type %s)' % ftype)
        w.close_inline()
    elif h == 'arc':
        st = _xy(kid(item, 'start'))
        mi = _xy(kid(item, 'mid'))
        en = _xy(kid(item, 'end'))
        w.open('arc')
        w.line('start', fmt(st[0]), fmt(st[1]))
        w.line('mid', fmt(mi[0]), fmt(mi[1]))
        w.line('end', fmt(en[0]), fmt(en[1]))
        w.line('stroke', '(width %s)' % fmt(width), '(type default)')
        w.line('fill', '(type %s)' % ftype)
        w.close_inline()
    elif h == 'polyline':
        pts = kid(item, 'pts')
        w.open('polyline')
        w.open('pts')
        for p in kids(pts, 'xy'):
            x, y = _xy(p)
            w.line('xy', fmt(x), fmt(y))
        w.close_inline()
        w.line('stroke', '(width %s)' % fmt(width), '(type default)')
        w.line('fill', '(type %s)' % ftype)
        w.close_inline()


def _emit_pin(w, item):
    a = [x for x in item[1:] if isinstance(x, str)]
    etype = a[0]
    style = a[1] if len(a) > 1 else 'line'
    at = kid(item, 'at')
    ax = atoms(at)
    x, y, rot = float(ax[0]), float(ax[1]), int(float(ax[2])) if len(ax) > 2 else 0
    length = float(atoms(kid(item, 'length'))[0])
    name = atoms(kid(item, 'name'))[0]
    number = atoms(kid(item, 'number'))[0]
    w.open('pin', etype, style)
    w.line('at', fmt(x), fmt(y), rot)
    w.line('length', fmt(length))
    w.open('name', q(name))
    w.raw(effects())
    w.close_inline()
    w.open('number', q(number))
    w.raw(effects())
    w.close_inline()
    w.close_inline()


def symbol_pin_geometry(sym, parent):
    """{pin number: (x, y, rot, length, name, etype)} in symbol coordinates."""
    src = parent if parent is not None else sym
    out = {}
    for sub in kids(src, 'symbol'):
        for item in kids(sub, 'pin'):
            a = [x for x in item[1:] if isinstance(x, str)]
            at = atoms(kid(item, 'at'))
            out[atoms(kid(item, 'number'))[0]] = (
                float(at[0]), float(at[1]),
                int(float(at[2])) if len(at) > 2 else 0,
                float(atoms(kid(item, 'length'))[0]),
                atoms(kid(item, 'name'))[0],
                a[0],
            )
    return out


# ----------------------------------------------------- footprint extraction


class FpLib:
    def __init__(self, search_dirs):
        self.dirs = [d for d in search_dirs if d and os.path.isdir(d)]

    def get(self, libname, fpname):
        for d in self.dirs:
            p = os.path.join(d, libname + '.pretty', fpname + '.kicad_mod')
            if os.path.isfile(p):
                return parse(open(p, encoding='utf-8').read())[0]
        raise IOError('footprint not found: %s:%s (looked in %s)'
                      % (libname, fpname, self.dirs))


KEEP_FP = ('descr', 'tags', 'attr', 'fp_line', 'fp_rect', 'fp_circle', 'fp_arc',
           'fp_poly', 'pad')
KEEP_PAD = ('at', 'size', 'drill', 'layers', 'roundrect_rratio', 'options',
            'primitives', 'chamfer', 'chamfer_ratio')


def emit_footprint_lib(path, fpname, node):
    """Re-emit a stock footprint as a clean KiCad 8 .kicad_mod."""
    w = W()
    w.open('footprint', q(fpname))
    w.line('version', '20240108')
    w.line('generator', q('gowin-bridge-gen'))
    w.line('layer', q('F.Cu'))
    d = kid(node, 'descr')
    if d is not None:
        w.line('descr', q(atoms(d)[0]))
    t = kid(node, 'tags')
    if t is not None:
        w.line('tags', q(atoms(t)[0]))
    at = kid(node, 'attr')
    if at is not None:
        w.line('attr', *atoms(at))
    _emit_fp_body(w, node, with_text=True)
    w.close_inline()
    with open(path, 'w', encoding='utf-8') as f:
        f.write(w.text())


def _emit_fp_body(w, node, with_text=False, refdes=None, value=None,
                  net_of_pad=None, rot=0, fp_rot_for_pads=0, mirror_x=False):
    if with_text:
        w.open('fp_text', 'reference', q(refdes or 'REF**'))
        w.line('at', '0', '-3', '0')
        w.line('layer', q('F.SilkS'))
        w.raw(effects(1.0))
        w.close_inline()
        w.open('fp_text', 'value', q(value or 'VAL**'))
        w.line('at', '0', '3', '0')
        w.line('layer', q('F.Fab'))
        w.raw(effects(1.0))
        w.close_inline()
    for item in node[1:]:
        if not isinstance(item, list):
            continue
        h = head(item)
        if h in ('fp_line', 'fp_rect', 'fp_circle', 'fp_arc'):
            _emit_fp_graphic(w, item, mirror_x)
        elif h == 'fp_poly':
            _emit_fp_poly(w, item, mirror_x)
        elif h == 'pad':
            _emit_fp_pad(w, item, net_of_pad, fp_rot_for_pads, mirror_x)


def _lay(item):
    l = kid(item, 'layer')
    if l is None:
        l = kid(item, 'layers')
    a = atoms(l) if l is not None else ['F.SilkS']
    return a


def _fp_stroke(item):
    st = kid(item, 'stroke')
    if st is not None:
        ww = kid(st, 'width')
        if ww is not None:
            return float(atoms(ww)[0])
    ww = kid(item, 'width')
    if ww is not None:
        return float(atoms(ww)[0])
    return 0.12


def _emit_fp_graphic(w, item, mx=False):
    h = head(item)
    width = _fp_stroke(item)
    layer = _lay(item)[0]
    fl = kid(item, 'fill')
    filled = False
    if fl is not None:
        a = atoms(fl)
        ft = kid(fl, 'type')
        v = (atoms(ft)[0] if ft is not None else (a[0] if a else 'none'))
        filled = v in ('solid', 'yes')
    sx = -1.0 if mx else 1.0
    w.open(h)
    if h == 'fp_circle':
        c = _xy(kid(item, 'center'))
        e = _xy(kid(item, 'end'))
        w.line('center', fmt(sx * c[0]), fmt(c[1]))
        w.line('end', fmt(sx * e[0]), fmt(e[1]))
    elif h == 'fp_arc':
        s = _xy(kid(item, 'start'))
        m = _xy(kid(item, 'mid'))
        e = _xy(kid(item, 'end'))
        w.line('start', fmt(sx * s[0]), fmt(s[1]))
        w.line('mid', fmt(sx * m[0]), fmt(m[1]))
        w.line('end', fmt(sx * e[0]), fmt(e[1]))
    else:
        s = _xy(kid(item, 'start'))
        e = _xy(kid(item, 'end'))
        w.line('start', fmt(sx * s[0]), fmt(s[1]))
        w.line('end', fmt(sx * e[0]), fmt(e[1]))
    w.line('stroke', '(width %s)' % fmt(width), '(type solid)')
    if h in ('fp_rect', 'fp_circle'):
        w.line('fill', 'solid' if filled else 'none')
    w.line('layer', q(layer))
    w.close_inline()


def _emit_fp_poly(w, item, mx=False):
    width = _fp_stroke(item)
    layer = _lay(item)[0]
    pts = kid(item, 'pts')
    sx = -1.0 if mx else 1.0
    w.open('fp_poly')
    w.open('pts')
    for p in kids(pts, 'xy'):
        x, y = _xy(p)
        w.line('xy', fmt(sx * x), fmt(y))
    w.close_inline()
    w.line('stroke', '(width %s)' % fmt(width), '(type solid)')
    w.line('fill', 'solid')
    w.line('layer', q(layer))
    w.close_inline()


def _emit_fp_pad(w, item, net_of_pad, fp_rot, mx=False):
    a = [x for x in item[1:] if isinstance(x, (str, tuple))]
    num = a[0][1] if isinstance(a[0], tuple) else a[0]
    ptype = a[1] if isinstance(a[1], str) else a[1][1]
    pshape = a[2] if isinstance(a[2], str) else a[2][1]
    at = atoms(kid(item, 'at'))
    px, py = float(at[0]), float(at[1])
    plocal = float(at[2]) if len(at) > 2 else 0.0
    size = atoms(kid(item, 'size'))
    drill = kid(item, 'drill')
    layers = atoms(kid(item, 'layers'))
    rr = kid(item, 'roundrect_rratio')

    if mx:
        px = -px
        plocal = -plocal
    w.open('pad', q(num), ptype, pshape)
    pad_rot = (plocal + fp_rot) % 360
    if abs(pad_rot) > 1e-9:
        w.line('at', fmt(px), fmt(py), fmt(pad_rot))
    else:
        w.line('at', fmt(px), fmt(py))
    w.line('size', fmt(float(size[0])), fmt(float(size[1])))
    if drill is not None:
        da = [x for x in atoms(drill) if x != 'oval']
        if 'oval' in [x for x in drill[1:] if isinstance(x, str)]:
            # (drill oval <w> <h>): atoms() also yields the 'oval' keyword,
            # so it has to be stripped before the numbers are read.
            w.line('drill', 'oval', fmt(float(da[0])), fmt(float(da[1])))
        else:
            w.line('drill', fmt(float(da[0])))
    w.line('layers', *[q(x) for x in layers])
    if rr is not None:
        w.line('roundrect_rratio', fmt(float(atoms(rr)[0])))
    if net_of_pad is not None:
        net = net_of_pad(num)
        if net is not None:
            w.line('net', net[0], q(net[1]))
    w.close_inline()


def footprint_pad_numbers(node):
    out = []
    for p in kids(node, 'pad'):
        a = [x for x in p[1:] if isinstance(x, (str, tuple))]
        out.append(a[0][1] if isinstance(a[0], tuple) else a[0])
    return out


def footprint_extent(node, layer='F.CrtYd'):
    xs, ys = [], []
    for item in node[1:]:
        if not isinstance(item, list):
            continue
        if head(item) not in ('fp_line', 'fp_rect', 'fp_poly', 'fp_circle', 'fp_arc'):
            continue
        if _lay(item)[0] != layer:
            continue
        if head(item) == 'fp_circle':
            # a circle's (end) is a point ON the circle, not a bounding
            # corner: taking it literally makes a courtyard circle look
            # zero-height, which silently collapsed the autoplacer's shelves.
            c = _xy(kid(item, 'center'))
            e = _xy(kid(item, 'end'))
            r = ((e[0] - c[0]) ** 2 + (e[1] - c[1]) ** 2) ** 0.5
            xs += [c[0] - r, c[0] + r]
            ys += [c[1] - r, c[1] + r]
            continue
        for key in ('start', 'end', 'center', 'mid'):
            k = kid(item, key)
            if k is not None:
                x, y = _xy(k)
                xs.append(x)
                ys.append(y)
        pts = kid(item, 'pts')
        if pts is not None:
            for p in kids(pts, 'xy'):
                x, y = _xy(p)
                xs.append(x)
                ys.append(y)
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)
