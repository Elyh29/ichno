# SPDX-License-Identifier: GPL-3.0-or-later
# Ichno: drawing engine (views, dimensions, title block, PDF and SVG)
import math
import os
import random
import re
import time

import bpy
from mathutils import Matrix, Vector

if "planlayout" not in globals():
    try:
        from . import planlayout
    except ImportError:
        import planlayout
GEOMETRY = {"MESH", "CURVE", "SURFACE", "META", "FONT"}
WEIGHTS = {"fine": {"contour": 0.25, "detail": 0.13, "cache": 0.13}, "normal": {"contour": 0.35, "detail": 0.18, "cache": 0.18},
           "bold": {"contour": 0.5, "detail": 0.25, "cache": 0.25}}
ASME, DT, D1, EXT_GAP, EXT_OVER, TICKS = False, 3.5, 10, 0, 2, False
ARROW = [3.0, math.radians(15)]
HIDDEN_TRIS = 1_500_000
EXTRA_OUTPUTS = []
HIDDEN_MAX = 150_000
FRONTS = {"front": ((1, 0, 0), (0, 1, 0), (0, 0, 1)), "back": ((-1, 0, 0), (0, -1, 0), (0, 0, 1)),
          "right": ((0, 1, 0), (-1, 0, 0), (0, 0, 1)), "left": ((0, -1, 0), (1, 0, 0), (0, 0, 1)),
          "top": ((1, 0, 0), (0, 0, -1), (0, 1, 0)), "bottom": ((1, 0, 0), (0, 0, 1), (0, -1, 0))}


def trim_hidden(strokes, budget, ext):
    def length(st):
        return sum(math.dist(a, b) for a, b in zip(st, st[1:]))
    tiny = max(ext[1] - ext[0], ext[3] - ext[2]) * 0.01
    ranked = sorted(((length(st), st) for st in strokes), key=lambda x: -x[0])
    keep, n = [], 0
    for ln, st in ranked:
        if ln < tiny or n + len(st) > budget:
            continue
        keep.append(st)
        n += len(st)
    return keep, len(strokes) - len(keep)


def cutters():
    out = set()
    for o in bpy.data.objects:
        for m in getattr(o, "modifiers", []):
            if m.type != "BOOLEAN":
                continue
            if getattr(m, "operand_type", "OBJECT") == "COLLECTION" and m.collection:
                out |= {x.name for x in m.collection.all_objects}
            elif m.object:
                out.add(m.object.name)
    return out


INST = {}


def realize_instances():
    INST.clear()
    sc = bpy.context.scene

    def put(col, mw, root, depth):
        if depth > 8:
            return
        off = Matrix.Translation(-col.instance_offset)
        for ob in col.all_objects:
            m = mw @ off @ ob.matrix_world
            if ob.type == "EMPTY" and ob.instance_type == "COLLECTION" and ob.instance_collection:
                put(ob.instance_collection, m, root, depth + 1)
            elif ob.type in GEOMETRY:
                new = ob.copy()
                new.parent = None
                new.matrix_world = m
                sc.collection.objects.link(new)
                INST[new.name] = root
    for o in list(sc.objects):
        if o.type == "EMPTY" and o.instance_type == "COLLECTION" and o.instance_collection:
            put(o.instance_collection, o.matrix_world.copy(), o.name, 0)


def root_of(o):
    return bpy.context.scene.objects.get(INST.get(o.name, o.name)) or o


def render_visible(o, excluded):
    if o.hide_render or any(c.hide_render or c.name in excluded for c in o.users_collection):
        return False
    return True


def keep_objects(only=None, hide=None):
    sc = bpy.context.scene
    excluded = set()

    def walk(lc):
        if lc.exclude:
            excluded.add(lc.collection.name)
        for ch in lc.children:
            walk(ch)
    walk(bpy.context.view_layer.layer_collection)
    cut = cutters()
    only, hide = (set(only) if only is not None else None), (set(hide) if hide is not None else None)
    keep = []
    for o in list(sc.objects):
        if o.type not in GEOMETRY or o.name in cut:
            continue
        r = root_of(o)
        ok = (r.name in only) if only is not None else (r.name not in hide) if hide is not None else render_visible(r, excluded)
        if ok:
            keep.append(o)
    names = {o.name for o in keep}
    vl = bpy.context.view_layer

    def show(lc):
        lc.exclude = False
        lc.hide_viewport = False
        for ch in lc.children:
            show(ch)
    show(vl.layer_collection)
    for c in bpy.data.collections:
        c.hide_viewport = c.hide_render = False
    for o in sc.objects:
        on = o.name in names
        o.hide_render = o.hide_viewport = not on
        if o.name in vl.objects:
            o.hide_set(not on)
    vl.update()
    return keep


def world_box(objs):
    dg = bpy.context.evaluated_depsgraph_get()
    lo, hi = Vector((1e18,) * 3), Vector((-1e18,) * 3)
    for o in objs:
        ev = o.evaluated_get(dg)
        for c in ev.bound_box:
            w = ev.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    return lo, hi


ISO_CORNERS = {"fl": (1, 1, -1), "fr": (-1, 1, -1), "bl": (1, -1, -1), "br": (-1, -1, -1)}
TILT = 1e-4


def view_matrix(direction, up, ctr, r):
    d = Vector(direction).normalized()
    x0 = Vector(up).cross(-d).normalized()
    d = (d + x0 * TILT + Vector(up).normalized() * TILT).normalized()
    z = -d
    x = Vector(up).cross(z).normalized()
    y = z.cross(x)
    return Matrix.Translation(ctr - d * r * 3) @ Matrix((x, y, z)).transposed().to_4x4()


def view_extent(mw, lo, hi):
    inv = mw.inverted()
    corners = [inv @ Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    return (min(c.x for c in corners), max(c.x for c in corners), min(c.y for c in corners), max(c.y for c in corners))


def view_camera(name, direction, up, ctr, r):
    cam_data = bpy.data.cameras.new(name)
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = r * 2.2
    cam_data.clip_start, cam_data.clip_end = r * 0.01, r * 10
    cam = bpy.data.objects.new(name, cam_data)
    bpy.context.scene.collection.objects.link(cam)
    cam.matrix_world = view_matrix(direction, up, ctr, r)
    return cam


def lineart(cam, hidden, angle_deg=30, fast=False):
    sc = bpy.context.scene
    gpd = getattr(bpy.data, "grease_pencils_v3", bpy.data.grease_pencils).new("plan")
    gp = bpy.data.objects.new("plan", gpd)
    sc.collection.objects.link(gp)
    mat = bpy.data.materials.new("trait")
    bpy.data.materials.create_gpencil_data(mat)
    gpd.materials.append(mat)
    angle = math.radians(180 - float(angle_deg or 30))
    LAYERS = [("contour", {"use_contour": True, "use_loose": True}, 0, 0), ("detail", {"use_crease": True, "use_intersection": not fast}, 0, 0)]
    if hidden:
        LAYERS.append(("cache", {"use_contour": True, "use_crease": True, "use_intersection": True, "use_loose": True}, 1, 64))
    for i, (layer_name, kinds, lo, hi) in enumerate(LAYERS):
        layer = gpd.layers.new(layer_name)
        layer.frames.new(sc.frame_current)
        m = gp.modifiers.new(layer_name, "LINEART")
        m.source_type = "SCENE"
        m.use_custom_camera = True
        m.source_camera = cam
        m.target_layer = layer_name
        m.target_material = mat
        for k in ("use_contour", "use_crease", "use_intersection", "use_loose", "use_material", "use_edge_mark"):
            setattr(m, k, kinds.get(k, False))
        m.crease_threshold = angle
        m.use_overlap_edge_type_support = True
        m.use_edge_overlap = True
        m.use_back_face_culling = fast
        if i:
            m.use_cache = True
        if hi:
            m.use_multiple_levels = True
            m.level_start, m.level_end = lo, hi
    return gp


def strokes_2d(gp, cam):
    dg = bpy.context.evaluated_depsgraph_get()
    dg.update()
    import numpy as np
    M = np.array(cam.matrix_world.inverted())
    out = {}
    for layer in gp.evaluated_get(dg).data.layers:
        fr = layer.current_frame()
        L = []
        dr = fr.drawing if fr else None
        if dr and len(dr.curve_offsets) > 1:
            off = np.empty(len(dr.curve_offsets), dtype=np.int32)
            dr.curve_offsets.foreach_get("value", off)
            pos = np.empty(off[-1] * 3, dtype=np.float64)
            dr.attributes["position"].data.foreach_get("vector", pos)
            xy = (pos.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3])[:, :2].tolist()
            L = [xy[a:b] for a, b in zip(off[:-1].tolist(), off[1:].tolist()) if b - a >= 2]
        out[layer.name] = L
    return out


class Sheet:
    def __init__(self, w, h):
        self.w, self.h, self.items = w, h, []
        self.bom, self.bom_head = [], ()
        self.scale = None
        self.layer, self.layers = "FRAME", []
        self.style = ""

    def colors(self):
        if self.style == "blueprint":
            return (0.12, 0.30, 0.55), (0.96, 0.98, 1), (0.72, 0.82, 0.94), (0.24, 0.42, 0.66)
        if self.style == "sketch":
            return (0.99, 0.98, 0.95), (0.18, 0.18, 0.2), (0.45, 0.45, 0.48), None
        return (1, 1, 1), (0.067, 0.067, 0.067), (0.4, 0.4, 0.4), None

    def sketch(self, pts, closed, k=0):
        rnd = random.Random(round(pts[0][0] * 37 + pts[0][1] * 101 + len(pts)) + k * 7919)
        dx, dy = rnd.uniform(-0.4, 0.4), rnd.uniform(-0.4, 0.4)
        q = [(x + dx, y + dy) for x, y in pts]
        if not closed and len(q) >= 2:
            for i, j in ((0, 1), (-1, -2)):
                (ax, ay), (bx, by) = q[i], q[j]
                d = math.hypot(ax - bx, ay - by)
                if d > 2:
                    o = rnd.uniform(1, 2.5) / d
                    q[i] = (ax + (ax - bx) * o, ay + (ay - by) * o)
        return q

    def add(self, it):
        self.items.append(it)
        self.layers.append(self.layer)

    def poly(self, pts, lw=0.35, dash=None, closed=False):
        self.add(("poly", pts, lw, dash, closed))

    def image(self, x, y, w, h, img):
        k = min(w / img["w"], h / img["h"])
        self.add(("image", x + (w - img["w"] * k) / 2, y + (h - img["h"] * k) / 2, img["w"] * k, img["h"] * k, img))

    def line(self, x1, y1, x2, y2, lw=0.18):
        self.poly([(x1, y1), (x2, y2)], lw)

    def tri(self, pts):
        self.add(("tri", pts))

    def blank(self, x, y, w, h):
        self.add(("blank", x, y, w, h))

    def text(self, x, y, s, size, align="left", bold=False, grey=False, rot=False):
        self.add(("text", x, y, s, size, align, bold, grey, rot))

    def arrow(self, x1, y1, x2, y2, gap=0, out=False):
        L, s2 = ARROW
        a, d = math.atan2(y2 - y1, x2 - x1), math.hypot(x2 - x1, y2 - y1)
        if out and d:
            ux, uy = (x2 - x1) / d * (L + 2), (y2 - y1) / d * (L + 2)
            self.line(x1 - ux, y1 - uy, x2 + ux, y2 + uy)
            a += math.pi
        elif gap and d > gap + 2 * L:
            f = (d - gap) / 2 / d
            self.line(x1, y1, x1 + (x2 - x1) * f, y1 + (y2 - y1) * f)
            self.line(x2 - (x2 - x1) * f, y2 - (y2 - y1) * f, x2, y2)
        else:
            self.line(x1, y1, x2, y2)
        for px, py, aa in ((x1, y1, a), (x2, y2, a + math.pi)):
            self.tri([(px, py), (px + L * math.cos(aa - s2), py + L * math.sin(aa - s2)), (px + L * math.cos(aa + s2), py + L * math.sin(aa + s2))])

    def svg(self):
        esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        hexa = lambda c: "#%02x%02x%02x" % tuple(round(v * 255) for v in c)
        paper, ink, grey_c, grid = (hexa(c) if c else None for c in self.colors())
        lay = self.layers if len(self.layers) == len(self.items) else [""] * len(self.items)
        cls = lambda i, text=False: (f' class="{"TEXT" if text and lay[i] != "DIMENSIONS" else lay[i]}"' if lay[i] else "")
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}mm" height="{self.h}mm" viewBox="0 0 {self.w} {self.h}">',
               f'<rect width="{self.w}" height="{self.h}" fill="{paper}"/>']
        if grid:
            out.append(f'<g stroke="{grid}" stroke-width="0.1">' + "".join(f'<path d="M{x} 0 V{self.h}"/>' for x in range(10, int(self.w), 10))
                       + "".join(f'<path d="M0 {y} H{self.w}"/>' for y in range(10, int(self.h), 10)) + "</g>")
        out.append(f'<g fill="none" stroke="{ink}" stroke-linecap="round" stroke-linejoin="round">')
        for i, it in enumerate(self.items):
            if it[0] == "poly":
                _, pts, lw, dash, closed = it
                if self.style == "sketch":
                    if lw >= 0.3:
                        q = self.sketch(pts, closed, 1)
                        out.append(f'<path d="M{" L".join(f"{x:.3f} {y:.3f}" for x, y in q)}{" Z" if closed else ""}" stroke-width="{lw * 0.5:.3f}"/>')
                    pts = self.sketch(pts, closed)
                d = "M" + " L".join(f"{x:.3f} {y:.3f}" for x, y in pts) + (" Z" if closed else "")
                da = f' stroke-dasharray="{dash[0]} {dash[1]}"' if dash else ""
                out.append(f'<path d="{d}" stroke-width="{lw}"{da}{cls(i)}/>')
        out.append(f'</g><g fill="{paper}" stroke="none">')
        for i, it in enumerate(self.items):
            if it[0] == "blank":
                out.append(f'<rect x="{it[1]:.3f}" y="{it[2]:.3f}" width="{it[3]:.3f}" height="{it[4]:.3f}"{cls(i)}/>')
        out.append(f'</g><g fill="{ink}" stroke="none">')
        for i, it in enumerate(self.items):
            if it[0] == "tri":
                out.append('<path d="M' + " L".join(f"{x:.3f} {y:.3f}" for x, y in it[1]) + f' Z"{cls(i)}/>')
        italic = ' font-style="italic"' if self.style == "sketch" else ""
        out.append(f'</g><g font-family="Helvetica, Arial, sans-serif"{italic}>')
        for i, it in enumerate(self.items):
            if it[0] == "text":
                _, x, y, s, size, align, bold, grey, rot = it
                anchor = {"left": "start", "center": "middle", "right": "end"}[align]
                tr = f' transform="rotate(-90 {x:.3f} {y:.3f})"' if rot else ""
                fw = ' font-weight="bold"' if bold else ""
                out.append(f'<text x="{x:.3f}" y="{y:.3f}" font-size="{size}" text-anchor="{anchor}" dominant-baseline="middle"{tr}'
                           f'{fw} fill="{grey_c if grey else ink}"{cls(i, True)}>{esc(s)}</text>')
        out.append("</g>")
        for i, it in enumerate(self.items):
            if it[0] == "image":
                _, x, y, w, h, img = it
                out.append(f'<image x="{x:.3f}" y="{y:.3f}" width="{w:.3f}" height="{h:.3f}" href="data:image/png;base64,{img["b64"]}"{cls(i)}/>')
        out.append("</svg>")
        return "\n".join(out)

    def pdf_content(self):
        k = 72 / 25.4
        X = lambda x: x * k
        Y = lambda y: (self.h - y) * k
        rgb = lambda c: " ".join(f"{v:.3f}" for v in c)
        paper, ink, grey_c, grid = self.colors()
        INK = f"{rgb(ink)} RG {rgb(ink)} rg"
        ops = ["1 J 1 j"]
        if paper != (1, 1, 1):
            ops.append(f"{rgb(paper)} rg 0 0 {self.w * k:.2f} {self.h * k:.2f} re f")
        if grid:
            ops.append(f"{rgb(grid)} RG {0.1 * k:.3f} w [] 0 d " + " ".join(f"{X(x):.2f} 0 m {X(x):.2f} {self.h * k:.2f} l S" for x in range(10, int(self.w), 10))
                       + " " + " ".join(f"0 {Y(y):.2f} m {self.w * k:.2f} {Y(y):.2f} l S" for y in range(10, int(self.h), 10)))
        ops.append(INK)
        for it in self.items:
            if it[0] == "poly":
                _, pts, lw, dash, closed = it
                if self.style == "sketch":
                    if lw >= 0.3:
                        q = self.sketch(pts, closed, 1)
                        ops.append(f"{lw * 0.5 * k:.3f} w [] 0 d " + " ".join(f"{X(x):.2f} {Y(y):.2f} {'m' if i == 0 else 'l'}" for i, (x, y) in enumerate(q))
                                   + (" h S" if closed else " S"))
                    pts = self.sketch(pts, closed)
                ops.append(f"{lw * k:.3f} w " + (f"[{dash[0] * k:.2f} {dash[1] * k:.2f}] 0 d" if dash else "[] 0 d"))
                ops.append(" ".join(f"{X(x):.2f} {Y(y):.2f} {'m' if i == 0 else 'l'}" for i, (x, y) in enumerate(pts)) + (" h S" if closed else " S"))
            elif it[0] == "tri":
                ops.append(" ".join(f"{X(x):.2f} {Y(y):.2f} {'m' if i == 0 else 'l'}" for i, (x, y) in enumerate(it[1])) + " h f")
            elif it[0] == "blank":
                _, x, y, w, h = it
                ops.append(f"{rgb(paper)} rg {X(x):.2f} {Y(y + h):.2f} {w * k:.2f} {h * k:.2f} re f {rgb(ink)} rg")
            elif it[0] == "image":
                _, x, y, w, h, _img = it
                ops.append(f"q {w * k:.2f} 0 0 {h * k:.2f} {X(x):.2f} {Y(y + h):.2f} cm /Im1 Do Q")
        for it in self.items:
            if it[0] != "text":
                continue
            _, x, y, s, size, align, bold, grey, rot = it
            pt = size * k
            w = text_width(s, bold) * pt
            off = {"left": 0, "center": w / 2, "right": w}[align]
            raw = s.encode("cp1252", "replace").replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
            col = f"{rgb(grey_c)} rg {rgb(grey_c)} RG" if grey else INK
            if rot:
                tm = f"0 1 -1 0 {X(x) + pt * 0.35:.2f} {Y(y) - off:.2f} Tm"
            else:
                tm = f"1 0 0 1 {X(x) - off:.2f} {Y(y) - pt * 0.35:.2f} Tm"
            mode = f"[] 0 d {pt * 0.045:.3f} w 2 Tr" if bold else "0 Tr"
            font = "/F2" if self.style == "sketch" else "/F1"
            ops.append(f"BT {col} {mode} {font} {pt:.2f} Tf {tm} (" + raw.decode("latin-1") + ") Tj ET")
        return "\n".join(ops).encode("latin-1")


def pdf(sheets):
    k = 72 / 25.4
    n = len(sheets)
    objs = ["<< /Type /Catalog /Pages 2 0 R >>",
            f"<< /Type /Pages /Kids [{' '.join(f'{4 + 2 * i} 0 R' for i in range(n))}] /Count {n} >>",
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"]
    img = next((it[5] for sh in sheets for it in sh.items if it[0] == "image"), None)
    xo = f" /XObject << /Im1 {4 + 2 * n} 0 R >>" if img else ""
    f2 = 4 + 2 * n + (1 if img else 0)
    for i, sh in enumerate(sheets):
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {sh.w * k:.2f} {sh.h * k:.2f}] /Resources << /Font << /F1 3 0 R /F2 {f2} 0 R >>{xo} >> "
                    f"/Contents {5 + 2 * i} 0 R >>")
        objs.append(sh.pdf_content())
    if img:
        objs.append((f"/Type /XObject /Subtype /Image /Width {img['w']} /Height {img['h']} /ColorSpace /DeviceRGB "
                     "/BitsPerComponent 8 /Filter /FlateDecode", img["z"]))
    objs.append("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique /Encoding /WinAnsiEncoding >>")
    buf, offs = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"), []
    for i, o in enumerate(objs, 1):
        offs.append(len(buf))
        if isinstance(o, tuple):
            buf += f"{i} 0 obj\n<< {o[0]} /Length {len(o[1])} >>\nstream\n".encode() + o[1] + b"\nendstream\nendobj\n"
        elif isinstance(o, bytes):
            buf += f"{i} 0 obj\n<< /Length {len(o)} >>\nstream\n".encode() + o + b"\nendstream\nendobj\n"
        else:
            buf += f"{i} 0 obj\n{o}\nendobj\n".encode()
    xref = len(buf)
    buf += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode() + "".join(f"{o:010d} 00000 n \n" for o in offs).encode()
    buf += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(buf)


def text_width(s, bold=False):
    w = 0
    for ch in s:
        if ch.isdigit():
            w += 0.556
        elif ch == " ":
            w += 0.278
        elif ch in "il.,:;'|!·":
            w += 0.25
        elif ch in "mwMW":
            w += 0.85
        elif ch.isupper():
            w += 0.68
        else:
            w += 0.53
    return w * (1.05 if bold else 1)


def fmt(v, d=None):
    d = (2 if v < 10 else 1) if d is None else d
    return f"{v:,.{d}f}".replace(",", " ").replace(".", ",")


def load_logo(path, maxpx=600):
    import base64
    import struct
    import zlib

    import numpy as np
    if not path or not os.path.isfile(path):
        return None
    try:
        img = bpy.data.images.load(path, check_existing=False)
    except RuntimeError:
        return None
    try:
        w, h = img.size
        if not w or not h:
            return None
        if max(w, h) > maxpx:
            f = maxpx / max(w, h)
            img.scale(max(1, round(w * f)), max(1, round(h * f)))
            w, h = img.size
        a = np.empty(w * h * 4, np.float32)
        img.pixels.foreach_get(a)
        a = a.reshape(h, w, 4)[::-1]
        rgb = a[..., :3] * a[..., 3:4] + (1 - a[..., 3:4])
        raw = (np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8)
    finally:
        bpy.data.images.remove(img)
    z = zlib.compress(raw.tobytes(), 9)
    rows = zlib.compress(b"".join(b"\0" + r.tobytes() for r in raw), 9)
    chunk = lambda t, d: struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", rows) + chunk(b"IEND", b"")
    return {"w": w, "h": h, "z": z, "b64": base64.b64encode(png).decode()}


TEXTS = {
    "fr": {"Face": "VUE DE FACE", "Gauche": "VUE DE GAUCHE", "Droite": "VUE DE DROITE", "Dessus": "VUE DE DESSUS",
           "Perspective": "PERSPECTIVE", "iso": "ISOMÉTRIQUE · SANS ÉCHELLE", "scale_of": "ÉCHELLE {s}",
           "disclaimer": "PLAN PRODUIT PAR ORDINATEUR (BLENDER LINE ART) — NE PAS MESURER SUR LE TIRAGE, SE FIER AUX COTES",
           "generated": "Document généré par {brand} depuis {file}. Cotes d’encombrement seulement.",
           "TITLE": "TITRE", "PROJECTION": "PROJECTION", "first": "EUROPÉENNE", "third": "AMÉRICAINE", "PROJECT": "PROJET",
           "AUTHOR": "AUTEUR", "FILE": "FICHIER", "UNIT": "UNITÉ", "REV": "RÉV.", "NUMBER": "N° DE PLAN", "SCALE": "ÉCHELLE",
           "SIZE": "FORMAT", "SHEET": "FEUILLE", "DATE": "DATE", "DESC": "DESCRIPTION", "REMARKS": "REMARQUES", "ITEM": "REP.",
           "PART": "DÉSIGNATION", "QTY": "QTÉ", "BOM": "NOMENCLATURE", "LEGEND": "LÉGENDE", "CODE": "ABRÉV.", "TOTAL": "TOTAL", "more": "… {n} autres lignes",
           "CHECKED": "VÉRIFIÉ", "APPROVED": "APPROUVÉ", "TOL": "TOLÉRANCES GÉNÉRALES", "TOL_asme": "TOLÉRANCES SAUF INDICATION",
           "MATERIAL": "MATIÈRE", "annex_see": "NOMENCLATURE : VOIR FEUILLE {n}", "tol_table": "TOLÉRANCES GÉNÉRALES ISO 2768-{c} (mm)",
           "tol_size": "COTE", "tol_dev": "ÉCART", "annex_cont": "NOMENCLATURE (SUITE)",
           "dims": "COTES EN {u} · ENCOMBREMENT (L × P × H) {a} × {b} × {c}", "origin": "DEPUIS L’ORIGINE DU MONDE : ",
           "range": "{a} de {lo} à {hi}", "hidden": "TRAITS CACHÉS EN POINTILLÉS", "hidden_main": " (PRINCIPAUX SEULEMENT)",
           "nothing": "aucun objet à dessiner", "noview": "aucune vue choisie", "nothing_on": "aucun objet à dessiner sur la feuille « {s} »",
           "hidden_skip": "traits cachés non calculés : {n} triangles, trop pour un plan lisible (isole les pièces voulues)",
           "hidden_trim": "{v} : traits cachés simplifiés ({cut} petits traits retirés, {kept} gardés)",
           "hidden_trim_all": "traits cachés simplifiés sur {n} vue{s} : petits traits retirés pour la lisibilité",
           "view_done": "{v} : {n} points en {t:.1f} s",
           "views": {"Face": "face", "Gauche": "gauche", "Droite": "droite", "Dessus": "dessus", "Perspective": "perspective"}},
    "en": {"Face": "FRONT VIEW", "Gauche": "LEFT VIEW", "Droite": "RIGHT VIEW", "Dessus": "TOP VIEW",
           "Perspective": "ISOMETRIC VIEW", "iso": "ISOMETRIC · NOT TO SCALE", "scale_of": "SCALE {s}",
           "disclaimer": "COMPUTER-GENERATED DRAWING (BLENDER LINE ART) — DO NOT SCALE THE PRINT, USE THE DIMENSIONS",
           "generated": "Generated by {brand} from {file}. Overall dimensions only.",
           "TITLE": "TITLE", "PROJECTION": "PROJECTION", "first": "FIRST ANGLE", "third": "THIRD ANGLE", "PROJECT": "PROJECT",
           "AUTHOR": "DRAWN BY", "FILE": "FILE", "UNIT": "UNIT", "REV": "REV.", "NUMBER": "DWG NO.", "SCALE": "SCALE",
           "SIZE": "SIZE", "SHEET": "SHEET", "DATE": "DATE", "DESC": "DESCRIPTION", "REMARKS": "NOTES", "ITEM": "ITEM",
           "PART": "PART", "QTY": "QTY", "BOM": "BILL OF MATERIALS", "LEGEND": "LEGEND", "CODE": "ABBR.", "TOTAL": "TOTAL", "more": "… {n} more rows",
           "CHECKED": "CHECKED", "APPROVED": "APPROVED", "TOL": "GENERAL TOLERANCES", "TOL_asme": "TOLERANCES UNLESS NOTED",
           "MATERIAL": "MATERIAL", "annex_see": "BILL OF MATERIALS: SEE SHEET {n}", "tol_table": "GENERAL TOLERANCES ISO 2768-{c} (mm)",
           "tol_size": "SIZE", "tol_dev": "DEVIATION", "annex_cont": "BILL OF MATERIALS (CONTINUED)",
           "dims": "DIMENSIONS IN {u} · OVERALL (W × D × H) {a} × {b} × {c}", "origin": "FROM WORLD ORIGIN: ",
           "range": "{a} {lo} to {hi}", "hidden": "HIDDEN LINES DASHED", "hidden_main": " (MAIN LINES ONLY)",
           "nothing": "nothing to draw", "noview": "no view selected", "nothing_on": "nothing to draw on sheet “{s}”",
           "hidden_skip": "hidden lines skipped: {n} triangles, too many for a readable drawing (isolate the parts you need)",
           "hidden_trim": "{v}: hidden lines simplified ({cut} small strokes removed, {kept} kept)",
           "hidden_trim_all": "Hidden lines simplified on {n} view{s}: small strokes removed for readability",
           "view_done": "{v}: {n} points in {t:.1f} s",
           "views": {"Face": "front", "Gauche": "left", "Droite": "right", "Dessus": "top", "Perspective": "isometric"}}}

F_ROW, OWN_ROW, REV_ROW, REM_LINE, REM_SIZE = 8, 4.5, 4.5, 3.6, 2.5


def wrap(text, width, size):
    out = []
    for para in (text or "").splitlines():
        line = ""
        for w in para.split():
            t = f"{line} {w}" if line else w
            if line and text_width(t) * size > width:
                out.append(line)
                line = w
            else:
                line = t
        out.append(line)
    while out and not out[-1]:
        out.pop()
    return out


ISO2768_RANGES = ((0.5, 3), (3, 6), (6, 30), (30, 120), (120, 400), (400, 1000), (1000, 2000), (2000, 4000))
ISO2768 = {"f": (0.05, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, None), "m": (0.1, 0.1, 0.2, 0.3, 0.5, 0.8, 1.2, 2),
           "c": (0.2, 0.3, 0.5, 0.8, 1.2, 2, 3, 4), "v": (None, 0.5, 1, 1.5, 2.5, 4, 6, 8)}


def tb_extras(SPEC, TX=None, asme=False):
    revs = [(str(r.get("rev") or ""), str(r.get("desc") or ""), str(r.get("date") or "")) for r in SPEC.get("revisions") or []]
    revs = [r for r in revs if any(r)]
    fields = [(str(f.get("key") or ""), str(f.get("value") or "")) for f in SPEC.get("fields") or []]
    TX = TX or TEXTS["fr"]
    std = [(TX[k], str(SPEC.get(n) or "").strip()) for k, n in (("CHECKED", "checked"), ("APPROVED", "approved"),
                                                                 ("TOL_asme" if asme else "TOL", "tolerances"), ("MATERIAL", "material"))]
    fields = [f for f in std if f[1]] + [f for f in fields if any(f)]
    owner = str(SPEC.get("owner") or "").strip()
    legend = [(str(r.get("code") or ""), str(r.get("desc") or "")) for r in SPEC.get("legend") or []]
    legend = [r for r in legend if any(r)]
    rem = wrap(SPEC.get("remarks") or "", planlayout.TB_W - 4, REM_SIZE)
    tol = SPEC.get("tol_table") if SPEC.get("tol_table") in ISO2768 else ""
    inside = F_ROW * -(-len(fields) // 4) + (OWN_ROW if owner else 0)
    above = ((len(revs) + 1) * REV_ROW + 4 if revs else 0) + (5 + len(rem) * REM_LINE + 2 if rem else 0) + (
        (len(legend) + 1) * REV_ROW + 5 if legend else 0) + (2 * REV_ROW + 5 if tol else 0)
    return {"revs": revs, "fields": fields, "owner": owner, "legend": legend, "rem": rem, "inside": inside, "above": above, "tol": tol}


BOM_MAX = 30


def bom_rows(objs, by="name", prop=""):
    count = {}
    for o in {root_of(x).name: root_of(x) for x in objs}.values():
        k = bom_key(o, by, prop)
        count[k] = count.get(k, 0) + 1
    return sorted(count.items(), key=lambda kv: kv[0].lower())


def bom_key(o, by="name", prop=""):
    import re
    if by == "collection":
        return o.users_collection[0].name if o.users_collection else "—"
    if by == "property":
        return str(o.get(prop, "—")) if prop else "—"
    return re.sub(r"\.\d{3,}$", "", o.name)


def balloon_points(by_root, bom, by="name", prop=""):
    dg = bpy.context.evaluated_depsgraph_get()
    item = {k: str(i) for i, (k, _) in enumerate(bom, 1)}
    cands = {}
    for ro, objs in by_root.values():
        k = bom_key(ro, by, prop)
        if k not in item:
            continue
        pts = []
        for o in objs:
            ev = o.evaluated_get(dg)
            pts += [ev.matrix_world @ Vector(c) for c in ev.bound_box]
        vol = (max(p.x for p in pts) - min(p.x for p in pts)) * (max(p.y for p in pts) - min(p.y for p in pts)) * (max(p.z for p in pts) - min(p.z for p in pts))
        cands.setdefault(k, []).append((vol, objs))
    return [(item[k], [objs for _, objs in sorted(c, key=lambda c: -c[0])]) for k, c in cands.items()]


def balloon_view(cam, bpts, reach):
    dg = bpy.context.evaluated_depsgraph_get()
    inv = cam.matrix_world.inverted()
    d = (cam.matrix_world.to_3x3() @ Vector((0, 0, -1))).normalized()
    out = []
    for t, groups in bpts:
        found = None
        for objs in groups[:12]:
            names = {o.name for o in objs}
            samples = []
            for o in objs:
                ev = o.evaluated_get(dg)
                if ev.type != "MESH":
                    continue
                me = ev.to_mesh()
                step = max(1, len(me.polygons) // 300)
                samples += [ev.matrix_world @ me.polygons[n].center for n in range(0, len(me.polygons), step)]
                ev.to_mesh_clear()
            if not samples:
                continue
            q = [inv @ p for p in samples]
            cx, cy = sum(v.x for v in q) / len(q), sum(v.y for v in q) / len(q)
            w, h = max(v.x for v in q) - min(v.x for v in q), max(v.y for v in q) - min(v.y for v in q)
            tol = max(w, h, 1e-6) * 0.01
            seen = []
            for p, v in zip(samples, q):
                hit, loc, _, _, obj, _ = bpy.context.scene.ray_cast(dg, p - d * reach, d)
                if hit and obj is not None and obj.name in names and (loc - p).length <= tol:
                    seen.append(v)
            if seen and (found is None or len(seen) > found[0]):
                v = min(seen, key=lambda v: (v.x - cx) ** 2 + (v.y - cy) ** 2)
                found = (len(seen), (t, v.xy[:], w, h))
        found = found and found[1]
        if not found:
            pts = [inv @ (o.matrix_world @ Vector(c)) for o in groups[0] for c in o.bound_box]
            xs, ys = [p.x for p in pts], [p.y for p in pts]
            found = (t, ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2), max(xs) - min(xs), max(ys) - min(ys))
        out.append(found)
    return out


LABEL_SIZE = 2
BALLOON_SIZE = 5


def label_points(by_root, by="name", prop="", strip=False):
    import re
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for ro, objs in by_root.values():
        if by == "property":
            if not prop or prop not in ro.keys():
                continue
            t = str(ro[prop]).strip()
        else:
            t = re.sub(r"\.\d{3,}$", "", ro.name) if strip else ro.name
        if not t:
            continue
        pts = []
        for o in objs:
            ev = o.evaluated_get(dg)
            pts += [ev.matrix_world @ Vector(c) for c in ev.bound_box]
        out.append((t, sum(pts, Vector()) / len(pts), pts))
    return out


def label_view(cam, lpts):
    inv = cam.matrix_world.inverted()
    out = []
    for t, c, pts in lpts:
        q = [inv @ p for p in pts]
        xs, ys = [p.x for p in q], [p.y for p in q]
        out.append((t, (inv @ c).xy[:], max(xs) - min(xs), max(ys) - min(ys)))
    return out


def manual_view(cam, dims, unit_mm, key, ext):
    inv = cam.matrix_world.inverted()
    mx, my = (ext[1] - ext[0]) * 0.1 + 1e-6, (ext[3] - ext[2]) * 0.1 + 1e-6
    inside = lambda q: ext[0] - mx <= q.x <= ext[1] + mx and ext[2] - my <= q.y <= ext[3] + my
    out = []
    for d in dims:
        a, b = Vector(d.get("a") or (0, 0, 0)), Vector(d.get("b") or (0, 0, 0))
        qa, qb = inv @ a, inv @ b
        if not (inside(qa) or inside(qb)):
            continue
        view = d.get("view") or "auto"
        if view == "auto":
            L = (b - a).length
            if L > 1e-9 and abs(qa.z - qb.z) <= 0.01 * L:
                out.append((qa.xy[:], qb.xy[:], L * unit_mm))
        elif view == key and (qb.xy - qa.xy).length > 1e-9:
            n = [float(c) for c in cam.matrix_world.col[2][:3]]
            n = [round(c) if abs(abs(c) - 1) < 1e-4 or abs(c) < 1e-4 else c for c in n]
            dv = [float(b[i]) - float(a[i]) for i in range(3)]
            nn = math.sqrt(sum(c * c for c in n))
            dot = sum(dv[i] * n[i] for i in range(3)) / nn
            out.append((qa.xy[:], qb.xy[:], math.sqrt(max(sum(c * c for c in dv) - dot * dot, 0)) * unit_mm))
    return out


def bom_height(rows, annex=False):
    if annex:
        return 7 if rows else 0
    n = min(len(rows), BOM_MAX) + (1 if len(rows) > BOM_MAX else 0)
    return (n + 3) * REV_ROW + 2 if rows else 0


def annex_pages(bom, sw, sh, inside, lang="fr"):
    m, ml = planlayout.MARGIN, planlayout.MARGIN_L
    x0, x1 = ml + planlayout.INSET, sw - m - planlayout.INSET
    cw = min(planlayout.TB_W, x1 - x0)
    ncol = max(1, int((x1 - x0 + 10) // (cw + 10)))
    per = max(5, int((sh - m - planlayout.TB_H - inside - 6 - (m + planlayout.BAND + 6)) // REV_ROW) - 1)
    rows = [(str(i), k, str(q)) for i, (k, q) in enumerate(bom, 1)] + [("", TEXTS[lang]["TOTAL"], str(sum(q for _, q in bom)))]
    pages, cols = [], []
    for i in range(0, len(rows), per):
        cols.append(rows[i:i + per])
    for i in range(0, len(cols), ncol):
        pages.append({"w": sw, "h": sh, "land": sw > sh, "views": [],
                      "annex": [(x0 + j * (cw + 10), c) for j, c in enumerate(cols[i:i + ncol])], "annex_w": cw})
    return pages


UNITS = {"mm": (1, "MM"), "cm": (10, "CM"), "m": (1000, "M"), "in": (25.4, "IN")}


def unit_fmt(unit, lang="fr"):
    k, _ = UNITS.get(unit, UNITS["mm"])

    def f(v, d=None):
        v = v / k
        if d is None:
            d = {"mm": 2 if v < 10 else 1, "cm": 2 if v < 10 else 1, "m": 3}.get(unit, 3 if v < 1 else 2)
        if unit == "in":
            return f'{v:,.{d}f}"'
        if lang != "fr":
            return f"{v:,.{d}f}"
        return f"{v:,.{d}f}".replace(",", " ").replace(".", ",")
    return f


def zone_labels(n, letters):
    if not letters:
        return [str(i + 1) for i in range(n)]
    return [c for c in "ABCDEFGHJKLMNPQRSTUVWXYZ"][:n]


def frame(P, sw, sh):
    m, ml, o = planlayout.MARGIN, planlayout.MARGIN_L, 5
    P.poly([(o, o), (sw - o, o), (sw - o, sh - o), (o, sh - o)], 0.18, closed=True)
    P.poly([(ml, m), (sw - m, m), (sw - m, sh - m), (ml, sh - m)], 0.7, closed=True)
    for horiz in (True, False):
        length = (sw - ml - m) if horiz else sh - 2 * m
        n = max(2, 2 * round(length / 100))
        step = length / n
        for i, lab in enumerate(zone_labels(n, not horiz)):
            a = (ml if horiz else m) + i * step
            if i:
                if horiz:
                    P.line(a, o, a, m, 0.18)
                    P.line(a, sh - m, a, sh - o, 0.18)
                else:
                    P.line(o, a, ml, a, 0.18)
                    P.line(sw - m, a, sw - o, a, 0.18)
            c = a + step / 2
            if horiz:
                P.text(c, (o + m) / 2, lab, 2.5, "center")
                P.text(c, sh - (o + m) / 2, lab, 2.5, "center")
            else:
                P.text((o + ml) / 2, c, lab, 2.5, "center")
                P.text(sw - (o + m) / 2, c, lab, 2.5, "center")
    for x, y, dx, dy, mm in ((sw / 2, 0, 0, 1, m), (sw / 2, sh, 0, -1, m), (0, sh / 2, 1, 0, ml), (sw, sh / 2, -1, 0, m)):
        P.line(x + dx * o, y + dy * o, x + dx * (mm + 2.5), y + dy * (mm + 2.5), 0.7)


def circle(P, cx, cy, r, lw):
    P.poly([(cx + r * math.cos(a * math.pi / 24), cy + r * math.sin(a * math.pi / 24)) for a in range(48)], lw, closed=True)


def angle_symbol(P, x, y, third=False):
    h = 1.5
    tx, cx = (x + 4 * h + 3.5, x + 2 * h) if third else (x, x + 6 + 3.5 + 2 * h)
    P.poly([(tx, y - h), (tx + 6, y - 2 * h), (tx + 6, y + 2 * h), (tx, y + h)], 0.25, closed=True)
    circle(P, cx, y, 2 * h, 0.25)
    circle(P, cx, y, h, 0.25)
    P.line(x - 1, y, x + 6 + 3.5 + 4 * h + 1, y, 0.13)
    P.line(cx, y - 2 * h - 0.8, cx, y + 2 * h + 0.8, 0.13)


def view_axes(cam):
    r = cam.matrix_world.to_3x3().normalized()
    return [(n, r.col[0].dot(a), r.col[1].dot(a), r.col[2].dot(a)) for n, a in (("X", Vector((1, 0, 0))), ("Y", Vector((0, 1, 0))), ("Z", Vector((0, 0, 1))))]


def axes_triad(P, x, y, axes, arm=4.0):
    for n, px, py, pz in axes:
        if abs(pz) > 0.98:
            circle(P, x, y, 0.9, 0.13)
            if pz > 0:
                circle(P, x, y, 0.2, 0.3)
            else:
                P.line(x - 0.64, y - 0.64, x + 0.64, y + 0.64, 0.13)
                P.line(x - 0.64, y + 0.64, x + 0.64, y - 0.64, 0.13)
            P.text(x - 1.6, y + 1.6, n, 1.8, "center", bold=True)
            continue
        ln = math.hypot(px, py)
        if ln < 0.05:
            continue
        ex, ey = x + px * arm, y - py * arm
        P.line(x + px / ln * 0.9, y - py / ln * 0.9, ex, ey, 0.18)
        a = math.atan2(ey - y, ex - x)
        P.tri([(ex, ey), (ex - 1.2 * math.cos(a - 0.4), ey - 1.2 * math.sin(a - 0.4)), (ex - 1.2 * math.cos(a + 0.4), ey - 1.2 * math.sin(a + 0.4))])
        P.text(ex + px / ln * 1.4, ey - py / ln * 1.4, n, 1.8, "center", bold=True)


CHAIN_ROW = 7
POS_ROW = 10


def view_axis(cam):
    r = cam.matrix_world.to_3x3().normalized().col[0]
    i = max(range(3), key=lambda k: abs(r[k]))
    return i, 1 if r[i] > 0 else -1


def chain_positions(cam, groups, ref):
    inv = cam.matrix_world.inverted()
    i, sg = view_axis(cam)
    dg = bpy.context.evaluated_depsgraph_get()
    out = []
    for root, objs in groups:
        if ref == "origin":
            w = root.matrix_world.translation
            out.append(((inv @ w).x, w[i]))
            continue
        pts = []
        for o in objs:
            ev = o.evaluated_get(dg)
            pts += [ev.matrix_world @ Vector(c) for c in ev.bound_box]
        xs, ws = [(inv @ q).x for q in pts], [q[i] for q in pts]
        lo, hi = (min(ws), max(ws)) if sg > 0 else (max(ws), min(ws))
        out.append(((min(xs), lo) if ref == "min" else (max(xs), hi) if ref == "max" else ((min(xs) + max(xs)) / 2, (lo + hi) / 2)))
    return sorted(out)


def chain_groups(pos, unit_mm, tol=0.5, rel=0.01):
    st = []
    for x in pos:
        if not st or (x - st[-1]) * unit_mm > tol:
            st.append(x)
    gaps = [(a, b, (b - a) * unit_mm) for a, b in zip(st, st[1:])]
    if rel is None:
        return [(a, b, 1, d) for a, b, d in gaps]
    segs, i = [], 0
    while i < len(gaps):
        j, total = i, gaps[i][2]
        while j + 1 < len(gaps) and abs(gaps[j + 1][2] - total / (j - i + 1)) <= max(tol, total / (j - i + 1) * rel):
            j += 1
            total += gaps[j][2]
        n = j - i + 1
        if n >= 3:
            segs.append((gaps[i][0], gaps[j][1], n, sum(g[2] for g in gaps[i:j + 1]) / n))
        else:
            segs += [(a, b, 1, d) for a, b, d in gaps[i:j + 1]]
        i = j + 1
    return segs


def chain_info(cam, pairs, rel, pos, unit_mm):
    segs = chain_groups([x for x, _ in pairs], unit_mm, rel=rel)
    st = sorted({a for a, _, _, _ in segs} | {b for _, b, _, _ in segs})
    world = {x: min(pairs, key=lambda p: abs(p[0] - x))[1] * unit_mm for x in st}
    return {"segs": segs, "pos": pos, "world": world, "axis": "XYZ"[view_axis(cam)[0]]}


RULER = 7
GRID_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"


def nice_step(span, n=10):
    raw = max(span, 1e-9) / n
    e = 10 ** math.floor(math.log10(raw))
    return next(m * e for m in (1, 2, 5, 10) if m * e >= raw)


def grid_ticks(cam, lo, hi, ctr, step, org):
    inv, r = cam.matrix_world.inverted(), cam.matrix_world.to_3x3().normalized()
    out = []
    for c in (0, 1):
        i = max(range(3), key=lambda k: abs(r.col[c][k]))
        s, f = step, 0
        while (hi[i] - lo[i]) / s > 40:
            s *= (2, 2.5, 2)[f % 3]
            f += 1
        ticks = []
        for k in range(math.ceil((lo[i] - org[i]) / s - 1e-6), math.floor((hi[i] - org[i]) / s + 1e-6) + 1):
            p = ctr.copy()
            p[i] = org[i] + k * s
            ticks.append(((inv @ p)[c], k * s))
        out.append({"axis": "XYZ"[i], "ticks": ticks})
    return out


def grid_label(n):
    L = GRID_LETTERS
    return L[n] if n < len(L) else L[n // len(L) - 1] + L[n % len(L)]


def scale_bar(P, x1, y, scale, unit="mm", lang="fr"):
    u, name = UNITS.get(unit, UNITS["mm"])
    real = max((k * 10 ** e for e in range(-3, 6) for k in (1, 2, 5) if k * 10 ** e * u * scale <= 55), default=1)
    w = real * u * scale
    x0 = x1 - w
    for i in range(5):
        a, b = x0 + w * i / 5, x0 + w * (i + 1) / 5
        P.poly([(a, y), (b, y), (b, y + 1.4), (a, y + 1.4)], 0.13, closed=True)
        if i % 2 == 0:
            P.tri([(a, y), (b, y), (b, y + 1.4)])
            P.tri([(a, y), (b, y + 1.4), (a, y + 1.4)])
    for i in (0, 5):
        v = real * i / 5
        P.text(x0 + w * i / 5, y - 2, f"{v:g}".replace(".", "," if unit != "in" and lang == "fr" else "."), 1.8, "center")
    P.text(x0 - 3, y + 0.7, name, 1.8, "right", grey=True)


def run(SPEC, OUT, progress=None):
    t0 = time.time()
    W = WEIGHTS.get(SPEC.get("weight") or "normal", WEIGHTS["normal"])
    third = SPEC.get("proj") == "third"
    unit = SPEC.get("unit") if SPEC.get("unit") in UNITS else "mm"
    lang = SPEC.get("lang") if SPEC.get("lang") in TEXTS else "fr"
    TX = TEXTS[lang]
    fmt = unit_fmt(unit, lang)
    unit2 = SPEC.get("unit2") if SPEC.get("unit2") in UNITS and SPEC.get("unit2") != unit else None
    fmt2 = unit_fmt(unit2, lang) if unit2 else None

    DIMV = []

    def dual(v):
        DIMV.append(v)
        return f"{fmt(v)} [{fmt2(v)}]" if unit2 else fmt(v)
    global ASME, DT, D1, EXT_GAP, EXT_OVER, TICKS
    std = SPEC.get("standard") or ("asme" if third else "iso")
    ASME = std == "asme"
    ART = (SPEC.get("art_style") or "present") if std == "art" else ""
    if ART in ("present", "sketch"):
        W = {"present": {"contour": 0.6, "detail": 0.18, "cache": 0.18}, "sketch": {"contour": 0.45, "detail": 0.25, "cache": 0.2}}[ART]
    plain = ART in ("present", "sketch")
    DT = 2.5 if (SPEC.get("sheet") or "A3") in ("A4", "Letter") else 3.5
    D1, EXT_GAP, EXT_OVER = 10, (1.5 if ASME else 0), (3 if ASME else 2)
    TICKS = bool(SPEC.get("chain_ticks"))
    ARROW[:] = [3.0, math.atan(1 / 6) if ASME else math.radians(15)]
    bsize = 3.5 if DT < 3.5 else BALLOON_SIZE
    planlayout.MARGIN_L = 20 if SPEC.get("filing", not ASME) and not ART else planlayout.MARGIN
    XT = tb_extras(SPEC, TX, ASME)
    GR = SPEC.get("grid") or {}
    LB = SPEC.get("labels") or {}
    gmode = GR.get("mode") if GR.get("mode") in ("ruler", "grid") and GR.get("views") else None
    gtop = RULER if gmode else 0
    infos = []
    warnings = []
    tell0 = progress or (lambda f, msg: None)
    gi = [0, 1]
    def tell(f, msg):
        tell0(min(0.97, (gi[0] + f) / gi[1] * 0.95), msg)
    def group(only, hide, label, vw=None, with_bom=True):
        objs = keep_objects(only, hide)
        if not objs:
            raise RuntimeError(TX["nothing_on"].format(s=label) if label else TX["nothing"])
        unit_mm = (bpy.context.scene.unit_settings.scale_length or 1) * 1000
        lo, hi = world_box(objs)
        size, ctr = hi - lo, (lo + hi) / 2
        r = max(size.length, 1e-6)
        M = Matrix(FRONTS.get(SPEC.get("front"), FRONTS["front"])).transposed()
        real = Vector([abs(M.col[i].dot(size)) for i in range(3)]) * unit_mm
        hidden = bool(SPEC.get("hidden"))
        tris = sum(sum(len(pl.vertices) - 2 for pl in o.data.polygons) for o in objs if o.type == "MESH")
        skip_hidden = hidden and tris > HIDDEN_TRIS
        if skip_hidden:
            hidden = False
        side = ("Droite", (-1, 0, 0), (0, 0, 1)) if third else ("Gauche", (1, 0, 0), (0, 0, 1))
        VIEWS = [("Face", (0, 1, 0), (0, 0, 1)), side, ("Dessus", (0, 0, -1), (0, 1, 0))]
        want = SPEC.get("views") if vw is None else [x for x in vw if x != "iso"]
        if want is not None:
            VIEWS = [vw for vw, k in zip(VIEWS, ("front", "side", "top")) if k in want]
        corner = ISO_CORNERS.get(SPEC.get("iso_view")) or ((-1, 1, -1) if third else (1, 1, -1))
        if (SPEC.get("iso", True) if vw is None else "iso" in vw):
            VIEWS.append(("Perspective", corner, (0, 0, 1)))
        VIEWS = [(n, tuple(M @ Vector(d)), tuple(M @ Vector(up))) for n, d, up in VIEWS]
        if SPEC.get("iso_view") == "viewport" and SPEC.get("iso_dir") and VIEWS and VIEWS[-1][0] == "Perspective":
            VIEWS[-1] = ("Perspective", tuple(SPEC["iso_dir"]), tuple(SPEC.get("iso_up") or (0, 0, 1)))
        vmap = {"front": "Face", "side": side[0], "top": "Dessus"}
        by_root = {}
        for o in objs:
            ro = root_of(o)
            by_root.setdefault(ro.name, (ro, []))[1].append(o)
        chains = [(vmap.get(c.get("view"), "Dessus"), [by_root[n] for n in c.get("objects") or [] if n in by_root], c.get("ref") or "min",
                   min(max(float(c.get("tol", 1)), 0), 10) / 100 if c.get("combine", True) else None, bool(c.get("pos", True)))
                  for c in SPEC.get("chains") or []]
        chains = [c for c in chains if len(c[1]) >= 2]
        gviews = {vmap[x] for x in GR.get("views") or [] if x in vmap} if gmode else set()
        lviews = {dict(vmap, iso="Perspective")[x] for x in LB.get("views") or [] if x in vmap or x == "iso"}
        lpts = label_points(by_root, LB.get("by") or "name", LB.get("prop") or "", bool(LB.get("strip"))) if lviews else []
        umain = UNITS[unit][0] / unit_mm
        gstep = float(GR.get("step") or 0) * umain or nice_step(max(size) / umain) * umain
        gorg = Vector(GR.get("origin") or (0, 0, 0))
        BM = (SPEC.get("bom") or {}) if with_bom else {}
        bset = set(BM["only"]) if BM.get("only") is not None else None
        bobjs = [o for o in objs if bset is None or o.name in bset or root_of(o).name in bset]
        bom = bom_rows(bobjs, BM.get("by") or "name", BM.get("prop") or "") if BM.get("by") and bobjs else []
        bviews = {dict(vmap, iso="Perspective")[x] for x in (SPEC.get("balloons") or {}).get("views") or [] if x in vmap or x == "iso"} if bom else set()
        broot = by_root if bset is None else {k: v for k, v in by_root.items() if k in bset or any(o.name in bset for o in v[1])}
        bpts = balloon_points(broot, bom, BM.get("by") or "name", BM.get("prop") or "") if bviews else []
        amode = BM.get("annex") or "auto"
        annex = bool(bom) and (amode == "always" or (amode == "auto" and len(bom) > BOM_MAX))
        rows = max([sum(CHAIN_ROW + (POS_ROW if c[4] else 0) for c in chains if c[0] == n) for n, _, _ in VIEWS] + [0])
        if not VIEWS:
            raise RuntimeError(TX["noview"])
        pv = next((vw for vw in VIEWS if vw[0] == "Perspective"), None)
        ex = view_extent(view_matrix(pv[1], pv[2], ctr, r), lo, hi) if pv else None
        odims = {"Face": (real.x, real.z), side[0]: (real.y, real.z), "Dessus": (real.x, real.y)}
        L = planlayout.layout({n: odims[n] for n, _, _ in VIEWS if n in odims},
                              (ex[1] - ex[0]) / max(ex[3] - ex[2], 1e-9) if ex else None, SPEC.get("sheet") or "A3", SPEC.get("land", True),
                              SPEC.get("scale"), planlayout.IMPERIAL if unit == "in" else planlayout.SCALES, lang, rows,
                              XT["inside"] + XT["above"] + bom_height(bom, annex), gtop, gtop, third,
                              max(0, (text_width(dual(real.z)) * DT + 2) / 2 + D1 - planlayout.RIGHT) if ASME else 0)
        if annex:
            L["pages"] += annex_pages(bom, L["pages"][0]["w"], L["pages"][0]["h"], XT["inside"], lang)
        drawn, trimmed = {}, 0
        steps = [f"{label + ' : ' if label else ''}" + TX["hidden_skip"].format(n=format(tris, ",").replace(",", " " if lang == "fr" else ","))] if skip_hidden else []
        warnings.extend(steps)
        for name, d, up in VIEWS:
            t = time.time()
            cam = view_camera(name, d, up, ctr, r)
            tell(len(drawn) / len(VIEWS), f"{label + ' · ' if label else ''}{TX['views'][name]}")
            gp = lineart(cam, hidden and (name != "Perspective" or bool(SPEC.get("iso_hidden"))), SPEC.get("angle"), bool(SPEC.get("fast")))
            S = strokes_2d(gp, cam)
            ext = view_extent(cam.matrix_world, lo, hi)
            n_hidden = sum(len(x) for x in S.get("cache", []))
            if n_hidden > HIDDEN_MAX:
                S["cache"], cut = trim_hidden(S["cache"], HIDDEN_MAX, ext)
                steps.append(f"{label + ' · ' if label else ''}" + TX["hidden_trim"].format(v=TX["views"][name], cut=cut, kept=len(S["cache"])))
                trimmed += 1
            drawn[name] = {"contour": S.get("contour", []), "detail": S.get("detail", []), "cache": S.get("cache", []), "ext": ext,
                           "axes": view_axes(cam), "chains": [chain_info(cam, chain_positions(cam, co, ref), rel, pos, unit_mm)
                                      for vn, co, ref, rel, pos in chains if vn == name],
                           "grid": grid_ticks(cam, lo, hi, ctr, gstep, gorg) if name in gviews else None,
                           "labels": label_view(cam, lpts) if name in lviews else [],
                           "balloons": balloon_view(cam, bpts, r * 4) if name in bviews else [],
                           "manual": manual_view(cam, SPEC.get("manual_dims") or [], unit_mm, {"Face": "front", "Dessus": "top"}.get(name, "side"), ext)
                           if name != "Perspective" else []}
            bpy.data.objects.remove(gp)
            bpy.data.objects.remove(cam)
            steps.append(f"{label + ' · ' if label else ''}" + TX["view_done"].format(v=TX["views"][name], n=sum(len(x) for k in ("contour", "detail") for x in S.get(k, [])), t=time.time() - t))
        if trimmed:
            infos.append(f"{label + ' : ' if label else ''}" + TX["hidden_trim_all"].format(n=trimmed, s="s" if trimmed > 1 else ""))
        return {"label": label, "drawn": drawn, "scale": L["scale"], "pages": L["pages"], "note": L["note"], "real": real, "lo": lo, "hi": hi,
                "hidden": hidden and any(d["cache"] for d in drawn.values()), "trimmed": trimmed, "steps": steps, "objects": len(objs), "unit_mm": unit_mm, "bom": bom,
                "annex": annex}

    realize_instances()
    groups = SPEC.get("sheets") or [{"name": "", "only": SPEC.get("only"), "hide": SPEC.get("hide")}]
    G = []
    gi[1] = len(groups)
    for i, g in enumerate(groups):
        gi[0] = i
        G.append(group(g.get("only"), g.get("hide"), g.get("name") or "", g.get("views"), g.get("bom", True)))
    steps = [st for g in G for st in g["steps"]]
    jobs = [(g, pg) for g in G for pg in g["pages"]]
    notes = [(f"{g['label']} : " if g["label"] else "") + g["note"] for g in G if g["note"]]
    steps += notes
    warnings += notes
    drawn, k_paper = {}, 1.0
    min_seg = 0.05
    sheet = SPEC.get("sheet") or "A3"

    def place(P, v):
        ex = drawn[v["name"]]["ext"]
        k = v["w"] / max(ex[1] - ex[0], 1e-9) if v["name"] == "Perspective" else k_paper
        for layer, lw, dash in (("cache", W["cache"], (12 * W["cache"], 3 * W["cache"])), ("detail", W["detail"], None), ("contour", W["contour"], None)):
            P.layer = "HIDDEN" if layer == "cache" else "VISIBLE"
            for st in drawn[v["name"]][layer]:
                pts, last = [], None
                for x, y in st:
                    q = (v["x"] + (x - ex[0]) * k, v["y"] + (ex[3] - y) * k)
                    if last is None or abs(q[0] - last[0]) + abs(q[1] - last[1]) >= min_seg:
                        pts.append(q)
                        last = q
                if len(pts) >= 2:
                    P.poly(pts, lw, dash)
        P.layer = "FRAME"

    def labels_of(P, v, balloon=False):
        ex = drawn[v["name"]]["ext"]
        k = v["w"] / max(ex[1] - ex[0], 1e-9) if v["name"] == "Perspective" else k_paper
        size = bsize if balloon else min(max(float(LB.get("size") or LABEL_SIZE), 1), 6)
        h = size * 2 if balloon else size + 0.8
        hit = lambda a, b: a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
        taken, out = [], []
        for t, (x, y), ow, oh in sorted(drawn[v["name"]]["balloons" if balloon else "labels"], key=lambda it: -it[3] * it[2]):
            L = h if balloon else text_width(t) * size + 1.2
            if balloon:
                out.append((t, v["x"] + (x - ex[0]) * k, v["y"] + (ex[3] - y) * k, L))
                continue
            rot = L > ow * k and oh > ow * 1.5
            w, hh = (h, L) if rot else (L, h)
            px, py = v["x"] + (x - ex[0]) * k, v["y"] + (ex[3] - y) * k
            box = (px - w / 2, py - hh / 2, px + w / 2, py + hh / 2)
            if any(hit(box, b) for b in taken):
                out.append((t, px, py, L))
                continue
            taken.append(box)
            P.blank(box[0], box[1], w, hh)
            P.text(px, py, t, size, "center", rot=rot)
        mid = v["x"] + v["w"] / 2
        gap = 4 if v["name"] == "Perspective" else D1 + 6
        lx, rx = v["x"] - 4, v["x"] + v["w"] + gap
        room = lambda side, its: (lx - 1.6 - max(it[3] for it in its) >= planlayout.MARGIN_L + 3 if side < 0
                                  else rx + 1.6 + max(it[3] for it in its) <= P.w - planlayout.MARGIN - 3)
        sides = {-1: [it for it in out if it[1] < mid], 1: [it for it in out if it[1] >= mid]}
        if balloon and v["name"] != "Perspective" and out and room(-1, out):
            sides = {-1: out, 1: []}
        for a in (-1, 1):
            if sides[a] and not room(a, sides[a]) and room(-a, sides[a] + sides[-a]):
                sides[-a] += sides[a]
                sides[a] = []

        def span(side):
            xc = lx if side < 0 else rx
            over_tb = max(xc, xc + side * (1.6 + h)) > tb_x0
            return planlayout.MARGIN + planlayout.BAND, (tb_top if over_tb else P.h - planlayout.MARGIN - 3)
        if balloon:
            fit = min(((span(sd)[1] - span(sd)[0]) / len(sides[sd]) - 0.6) / 2 for sd in (-1, 1) if sides[sd]) if out else size
            size = max(2.5, min(size, fit))
            h = size * 2
        for side in (-1, 1):
            col = sorted(sides[side], key=lambda it: it[2])
            if not col:
                continue
            step = h + 0.6
            ys, last = [], -1e9
            for _, _, py, _ in col:
                last = max(py, last + step)
                ys.append(last)
            y0, y1 = span(side)
            over = ys[-1] - (min(y1 - h / 2, v["y"] + v["h"] + 2 * step) if not balloon else y1 - h / 2)
            if over > 0:
                ys = [yy - over for yy in ys]
                for i in range(len(ys) - 2, -1, -1):
                    ys[i] = min(ys[i], ys[i + 1] - step)
            if balloon and ys[0] < y0 + h / 2:
                ys = [yy + y0 + h / 2 - ys[0] for yy in ys]
            xc = lx if side < 0 else rx
            for (t, px, py, L), yy in zip(col, ys):
                P.line(px, py, xc, yy, 0.12)
                P.line(xc, yy, xc + side * 1.2, yy, 0.12)
                circle(P, px, py, 0.25, 0.2)
                x0 = xc + side * 1.6
                if balloon:
                    cx = x0 + side * h / 2
                    P.blank(cx - h / 2, yy - h / 2, h, h)
                    circle(P, cx, yy, h / 2, 0.25)
                    P.text(cx, yy, t, size, "center", bold=True)
                    continue
                P.blank(x0 - L if side < 0 else x0, yy - h / 2, L, h)
                P.text(x0, yy, t, size, "right" if side < 0 else "left")

    def dimline(P, a, b, t, n):
        a, b = Vector(a), Vector(b)
        d = b - a
        vert = abs(d.x) < 0.02 * d.length

        def put(c, rot=False):
            L = text_width(t) * DT + 0.6
            w, h = (DT, L) if rot else (L, DT)
            P.blank(c.x - w / 2, c.y - h / 2, w, h)
            P.text(c.x, c.y, t, DT, "center", rot=rot)
        if ASME:
            tw = text_width(t) * DT + 2
            gap = (DT + 2) if vert else tw
            fits = d.length > gap + 2 * ARROW[0]
            P.arrow(*a, *b, gap=gap if fits else 0)
            c = (a + b) / 2
            if not fits:
                c = c + Vector((tw / 2 + 0.5, 0)) if vert else c - Vector(n) * (DT * 0.5 + 1.2)
            put(c)
            return
        out = d.length < 2 * ARROW[0] + 1
        P.arrow(*a, *b, out=out)
        c = (a + b) / 2
        tw = text_width(t) * DT + 0.6
        if d.length < tw + 1:
            c = b + d / d.length * ((ARROW[0] + 2 if out else 0) + 1 + tw / 2)
        if vert:
            put(c - Vector((DT * 0.5 + 0.8, 0)), True)
        elif abs(d.y) < 0.02 * d.length:
            put(c - Vector((0, DT * 0.5 + 0.8)))
        else:
            put(c + Vector(n) * (DT * 0.5 + 1.2))

    def ext_line(P, x1, y1, x2, y2):
        d = Vector((x2 - x1, y2 - y1))
        u = d / max(d.length, 1e-9)
        P.line(x1 + u.x * EXT_GAP, y1 + u.y * EXT_GAP, x2 + u.x * EXT_OVER, y2 + u.y * EXT_OVER, W["detail"])

    def dims_of(P, v, w, h, horiz=True, vert=True):
        x0, y0, vw, vh = v["x"], v["y"], v["w"], v["h"]
        yd, xd = y0 + vh + D1, x0 + vw + D1
        if horiz:
            ext_line(P, x0, y0 + vh, x0, yd)
            ext_line(P, x0 + vw, y0 + vh, x0 + vw, yd)
            dimline(P, (x0, yd), (x0 + vw, yd), dual(w), (0, -1))
        if vert:
            ext_line(P, x0 + vw, y0, xd, y0)
            ext_line(P, x0 + vw, y0 + vh, xd, y0 + vh)
            dimline(P, (xd, y0 + vh), (xd, y0), dual(h), (-1, 0))

    def manual_of(P, v, mds, ex, ybase):
        paper = lambda x, y: Vector((v["x"] + (x - ex[0]) * k_paper, v["y"] + (ex[3] - y) * k_paper))
        nh = nv = 0
        for (xa, ya), (xb, yb), val in mds:
            pa, pb = paper(xa, ya), paper(xb, yb)
            d = pb - pa
            if d.length < 1:
                continue
            if abs(d.y) < 0.02 * d.length:
                nh += 1
                y = ybase + 7 * nh
                for p in (pa, pb):
                    ext_line(P, p.x, p.y, p.x, y)
                dimline(P, (min(pa.x, pb.x), y), (max(pa.x, pb.x), y), dual(val), (0, -1))
            elif abs(d.x) < 0.02 * d.length:
                nv += 1
                x = v["x"] - 7 * nv
                for p in (pa, pb):
                    ext_line(P, p.x, p.y, x, p.y)
                dimline(P, (x, max(pa.y, pb.y)), (x, min(pa.y, pb.y)), dual(val), (-1, 0))
            else:
                n = Vector((-d.y, d.x)) / d.length
                if n.dot((pa + pb) / 2 - Vector((v["x"] + v["w"] / 2, v["y"] + v["h"] / 2))) < 0:
                    n = -n
                a1, b1 = pa + n * 7, pb + n * 7
                ext_line(P, *pa, *a1)
                ext_line(P, *pb, *b1)
                dimline(P, a1, b1, dual(val), n)

    def chain_of(P, v, ch, y, ex):
        segs = ch["segs"]
        X = lambda x: v["x"] + (x - ex[0]) * k_paper
        st = sorted({round(X(a), 3) for a, _, _, _ in segs} | {round(X(b), 3) for _, b, _, _ in segs})
        P.line(st[0], y, st[-1], y, W["detail"])
        if ch["pos"]:
            for x, w in ch["world"].items():
                t = fmt(w + 0, 1 if unit == "mm" else None)
                size = max(1.1, min(1.6, (POS_ROW - 2) / max(text_width(t), 1e-6)))
                P.text(X(x) + size * 0.45, y + 1.8 + text_width(t) * size / 2, t, size, "center", rot=True)
            P.text(st[0] - 1.5, y + 3, ch["axis"], 1.8, "right", bold=True)
        AL, s2 = ARROW
        for x in st:
            P.line(x, v["y"] + v["h"] + D1 + 1, x, y + EXT_OVER, W["detail"])
        ticks = set()
        for a, b, n, d in segs:
            xa, xb = X(a), X(b)
            if TICKS or xb - xa < 2 * AL + 1:
                ticks |= {round(xa, 3), round(xb, 3)}
                continue
            for px, sg in ((xa, 1), (xb, -1)):
                P.tri([(px, y), (px + sg * AL * math.cos(s2), y - AL * math.sin(s2)), (px + sg * AL * math.cos(s2), y + AL * math.sin(s2))])
        for x in ticks:
            P.line(x - 0.9, y + 0.9, x + 0.9, y - 0.9, 0.25)
        for a, b, n, d in segs:
            xa, xb = X(a), X(b)
            t = f"{n} × {dual(d)} = {dual(d * n)}" if n > 1 else dual(d)
            if text_width(t) * 2.5 <= (xb - xa) - 1:
                P.text((xa + xb) / 2, y - 1.9, t, 2.5, "center")
            else:
                room = CHAIN_ROW - 1.8
                if text_width(t) * 1.4 > room:
                    t = f"{n} × {fmt(d)}" if n > 1 else fmt(d)
                size = max(1.1, min(1.8, room / max(text_width(t), 1e-6)))
                P.text((xa + xb) / 2 + size * 0.45, y - 1 - text_width(t) * size / 2, t, size, "center", rot=True)

    def grid_of(P, v, gr, ex):
        X = lambda x: v["x"] + (x - ex[0]) * k_paper
        Y = lambda y: v["y"] + (ex[3] - y) * k_paper
        hx = sorted((X(p), w) for p, w in gr[0]["ticks"])
        vy = sorted((Y(p), w) for p, w in gr[1]["ticks"])
        yr, xr = v["y"] - 2, v["x"] - 2
        if gmode == "grid":
            cy, cx, rb = v["y"] - 4.6, v["x"] - 4.6, 2.2
            for n, (x, _) in enumerate(hx, 1):
                P.poly([(x, cy + rb), (x, v["y"] + v["h"])], 0.1, (4, 1))
                circle(P, x, cy, rb, 0.2)
                P.text(x, cy, str(n), 2, "center", bold=True)
            for n, (y, _) in enumerate(vy):
                P.poly([(cx + rb, y), (v["x"] + v["w"], y)], 0.1, (4, 1))
                circle(P, cx, y, rb, 0.2)
                P.text(cx, y, grid_label(n), 2, "center", bold=True)
            return
        def lab(w):
            u = w * unit_mm / UNITS[unit][0]
            return fmt(w * unit_mm + 0, 0 if abs(u - round(u)) < 1e-6 else None)
        if hx:
            P.line(hx[0][0], yr, hx[-1][0], yr, 0.15)
            last = -1e9
            for x, w in hx:
                P.line(x, yr, x, yr - 1.2, 0.15)
                t = lab(w)
                if x - text_width(t) * 0.85 > last + 1:
                    P.text(x, yr - 3, t, 1.8, "center")
                    last = x + text_width(t) * 0.85
            P.text(hx[-1][0] + 1.5, yr - 0.6, gr[0]["axis"], 1.8, bold=True)
        if vy:
            P.line(xr, vy[0][0], xr, vy[-1][0], 0.15)
            last = -1e9
            for y, w in vy:
                P.line(xr, y, xr - 1.2, y, 0.15)
                t = lab(w)
                if y - text_width(t) * 0.85 > last + 1:
                    P.text(xr - 3, y, t, 1.8, "center", rot=True)
                    last = y + text_width(t) * 0.85
            P.text(xr - 0.8, vy[-1][0] + 2.5, gr[1]["axis"], 1.8, "center", bold=True)

    title, project = SPEC.get("title") or "—", SPEC.get("project") or "—"
    number = (SPEC.get("name") or "plan").upper()
    logo = load_logo(SPEC.get("logo"))
    brand, brand_sub = SPEC.get("brand") if SPEC.get("brand") is not None else "Dédale", SPEC.get("brand_sub") if SPEC.get("brand_sub") is not None else "Studio 3D"
    sheets = []
    for n, (g, pg) in enumerate(jobs, 1):
        drawn, scale, real, lo, hi, hidden, unit_mm = g["drawn"], g["scale"], g["real"], g["lo"], g["hi"], g["hidden"], g["unit_mm"]
        k_paper = scale * unit_mm
        real_dims = {"Face": (real.x, real.z), "Gauche": (real.y, real.z), "Droite": (real.y, real.z), "Dessus": (real.x, real.y)}
        sw, sh, m = pg["w"], pg["h"], planlayout.MARGIN
        P = Sheet(sw, sh)
        DIMV.clear()
        P.style = ART
        if plain:
            P.poly([(m, m), (sw - m, m), (sw - m, sh - m), (m, sh - m)], 0.5, closed=True)
        else:
            frame(P, sw, sh)
        tb_x0 = sw - m - min(planlayout.TB_W, sw - 2 * m)
        tb_top = sh - m - planlayout.TB_H - XT["inside"] - planlayout.NOTES - XT["above"] - bom_height(g["bom"], g["annex"]) - 3
        P.text(sw / 2, m + 7, title.upper(), 5, "center", bold=True)
        sub = f"{g['label']} · {project}" if g["label"] else project
        if pg.get("annex"):
            sub = TX["BOM"] + (f" · {sub}" if sub != "—" else "")
        P.text(sw / 2, m + 13, sub, 3.5, "center")
        only_persp = all(v["name"] == "Perspective" for v in pg["views"])
        here = [v["name"] for v in pg["views"] if v["name"] in drawn and v["name"] != "Perspective"]
        own = set()
        for cands in ((("Face", "h"), ("Dessus", "h")), (("Face", "v"), ("Gauche", "v"), ("Droite", "v")),
                      (("Gauche", "h"), ("Droite", "h"), ("Dessus", "v"))):
            own.add(next((c for c in cands if c[0] in here), None))
        every = bool(SPEC.get("dims_all"))
        P.scale = None if only_persp else scale
        P.bom, P.bom_head = g["bom"], (g["label"], TX["ITEM"], TX["PART"], TX["QTY"], TX["TOTAL"])
        for v in pg["views"]:
            if v["name"] not in drawn:
                continue
            place(P, v)
            if drawn[v["name"]].get("labels"):
                labels_of(P, v)
            if drawn[v["name"]].get("balloons"):
                P.layer = "DIMENSIONS"
                labels_of(P, v, balloon=True)
                P.layer = "FRAME"
            persp = v["name"] == "Perspective"
            cx = v["x"] + v["w"] / 2
            head = TX[v["name"]]
            ty0 = v["y"] - (0 if persp else gtop)
            titled = persp or SPEC.get("view_titles", True)
            hw = text_width(head, True) * 3.5
            if titled:
                P.text(cx, ty0 - 7.5, head, 3.5, "center", bold=True)
                P.line(cx - hw / 2, ty0 - 5.3, cx + hw / 2, ty0 - 5.3, W["detail"])
            if SPEC.get("axes", True) and not plain:
                axes_triad(P, cx - max(hw, text_width(TX["scale_of"].format(s="1:500")) * 2.2) / 2 - 7, ty0 - 4.5, drawn[v["name"]]["axes"])
            P.layer = "DIMENSIONS"
            if not persp and drawn[v["name"]].get("grid"):
                grid_of(P, v, drawn[v["name"]]["grid"], drawn[v["name"]]["ext"])
            P.layer = "FRAME"
            if titled:
                P.text(cx, ty0 - 3, TX["iso"] if persp else TX["scale_of"].format(s=planlayout.label(scale)), 2.5, "center", grey=True)
            if not persp:
                P.layer = "DIMENSIONS"
                dims_of(P, v, *real_dims[v["name"]], every or (v["name"], "h") in own, every or (v["name"], "v") in own)
                yc = v["y"] + v["h"] + D1
                for ch in drawn[v["name"]].get("chains", []):
                    yc += CHAIN_ROW
                    if ch["segs"]:
                        chain_of(P, v, ch, yc, drawn[v["name"]]["ext"])
                    if ch["pos"]:
                        yc += POS_ROW
                if drawn[v["name"]].get("manual"):
                    manual_of(P, v, drawn[v["name"]]["manual"], drawn[v["name"]]["ext"], yc)
                P.layer = "FRAME"
        tb_w, tb_h = min(planlayout.TB_W, sw - 2 * m), planlayout.TB_H
        tx, ty = sw - m - tb_w, sh - m - tb_h - XT["inside"]
        X = lambda f: tx + tb_w * f
        r1, r2, r3 = ty + 7, ty + 20, ty + 28
        tb_y0 = r1 if plain else ty
        P.poly([(tx, tb_y0), (tx + tb_w, tb_y0), (tx + tb_w, ty + tb_h + XT["inside"]), (tx, ty + tb_h + XT["inside"])], 0.5, closed=True)
        for y in (r1, r2, r3):
            P.line(tx, y, tx + tb_w, y, 0.25)
        for f, ya, yb in ((0.61, r1, r2), (0.78, r1, r2), (0.30, r2, r3), (0.52, r2, r3), (0.78, r2, r3), (0.89, r2, r3), (0.39, r3, ty + tb_h), (0.56, r3, ty + tb_h),
                          (0.67, r3, ty + tb_h), (0.81, r3, ty + tb_h)):
            P.line(X(f), ya, X(f), yb, 0.25)

        def cell(f, f2, y, label, value, size=3.5, bold=False):
            P.text(X(f) + 1.5, y + 2, label, 1.8, grey=True)
            room = tb_w * (f2 - f) - 3
            P.text(X(f) + 1.5, y + 5.5, value, max(1.4, min(size, room / max(text_width(value, bold), 1e-6))), bold=bold)
        if not plain:
            P.text(tx + 2, ty + 2.6, TX["disclaimer"], 1.8, grey=True)
            P.text(tx + 2, ty + 5.2, TX["generated"].format(brand=brand or "Blender", file=SPEC.get("file") or "—"), 1.8, grey=True)
        P.text(X(0) + 1.5, r1 + 2, TX["TITLE"], 1.8, grey=True)
        tt = f"{title} — {g['label']}" if g["label"] else title
        P.text(X(0) + 1.5, r1 + 8, tt, 5 if text_width(tt) * 5 < tb_w * 0.58 else 3.5 if text_width(tt) * 3.5 < tb_w * 0.58 else 2.5, bold=True)
        P.text(X(0.61) + 1.5, r1 + 2, TX["PROJECTION"], 1.8, grey=True)
        angle_symbol(P, X(0.61) + 7.5, r1 + 6.6, third)
        P.text(X(0.695), r1 + 11.7, TX["third" if third else "first"], 1.8, "center", grey=True)
        bw = tb_w * 0.22 - 3
        if logo:
            P.image(X(0.78) + 1.5, r1 + 1, bw, 11 if not brand else 8, logo)
            if brand:
                P.text(X(0.89), r1 + 10.9, brand.upper(), min(1.8, bw / max(text_width(brand.upper(), True), 1e-6)), "center", bold=True)
        else:
            P.text(X(0.89), r1 + 6.5, brand.upper(), max(1.4, min(4.2, bw / max(text_width(brand.upper(), True), 1e-6))), "center", bold=True)
            P.text(X(0.89), r1 + 10.5, brand_sub.upper(), 1.8, "center", grey=True)
        cell(0, 0.30, r2, TX["PROJECT"], project)
        cell(0.30, 0.52, r2, TX["AUTHOR"], SPEC.get("author") or "—")
        cell(0.52, 0.78, r2, TX["FILE"], SPEC.get("file") or "—")
        cell(0.78, 0.89, r2, TX["UNIT"], f"{unit} [{unit2}]" if unit2 else unit)
        cell(0.89, 1, r2, TX["REV"], (XT["revs"][-1][0] if XT["revs"] and XT["revs"][-1][0] else SPEC.get("rev")) or "—", 3.5, True)
        cell(0, 0.39, r3, TX["NUMBER"], number, 3.5, True)
        cell(0.39, 0.56, r3, TX["SCALE"], "—" if only_persp else planlayout.label(scale), 3.5, True)
        cell(0.56, 0.67, r3, TX["SIZE"], sheet)
        cell(0.67, 0.81, r3, TX["SHEET"], f"{n}/{len(jobs)}")
        cell(0.81, 1, r3, TX["DATE"], SPEC.get("date") or "")
        y = ty + tb_h
        for i in range(0, len(XT["fields"]), 4):
            P.line(tx, y, tx + tb_w, y, 0.25)
            row = XT["fields"][i:i + 4]
            for j, (k, val) in enumerate(row):
                f, f2 = j / len(row), (j + 1) / len(row)
                if j:
                    P.line(X(f), y, X(f), y + F_ROW, 0.25)
                cell(f, f2, y, k.upper(), val or "—")
            y += F_ROW
        if XT["owner"]:
            P.line(tx, y, tx + tb_w, y, 0.25)
            P.text(tx + 2, y + 3.1, XT["owner"], max(1.2, min(1.8, (tb_w - 4) / max(text_width(XT["owner"]), 1e-6))), grey=True)
        if pg.get("annex"):
            first = pg is next(p for gg, p in jobs if gg is g and p.get("annex"))
            cw = pg["annex_w"]
            for cx0, crows in pg["annex"]:
                top = m + planlayout.BAND + 6
                P.text(cx0, top - 2, TX["BOM"] if first else TX["annex_cont"], 2.5, bold=True)
                yb = top + (len(crows) + 1) * REV_ROW
                P.poly([(cx0, top), (cx0 + cw, top), (cx0 + cw, yb), (cx0, yb)], 0.35, closed=True)
                cols = (0, 0.1, 0.86, 1)
                for f in cols[1:3]:
                    P.line(cx0 + cw * f, top, cx0 + cw * f, yb, 0.18)
                for i, r in enumerate([(TX["ITEM"], TX["PART"], TX["QTY"])] + crows):
                    yy = top + i * REV_ROW
                    if i:
                        P.line(cx0, yy, cx0 + cw, yy, 0.35 if i == 1 or r[1] == TX["TOTAL"] and not r[0] else 0.18)
                    for c, t in enumerate(r):
                        room = cw * (cols[c + 1] - cols[c]) - 3
                        sz = 1.8 if not i else max(1.2, min(2.5, room / max(text_width(t), 1e-6)))
                        P.text(cx0 + cw * cols[c] + 1.5, yy + 3.1, t, sz, grey=not i, bold=bool(i) and (c == 2 or not r[0]))
            sheets.append(P)
            continue
        yb = ty - planlayout.NOTES - 1
        if XT["revs"]:
            top = yb - (len(XT["revs"]) + 1) * REV_ROW
            P.poly([(tx, top), (tx + tb_w, top), (tx + tb_w, yb), (tx, yb)], 0.35, closed=True)
            cols = (0, 0.1, 0.82, 1)
            for f in cols[1:3]:
                P.line(X(f), top, X(f), yb, 0.2)
            for i, r in enumerate([(TX["REV"], TX["DESC"], TX["DATE"])] + XT["revs"]):
                yy = top + i * REV_ROW
                if i:
                    P.line(tx, yy, tx + tb_w, yy, 0.2)
                for c, t in enumerate(r):
                    room = tb_w * (cols[c + 1] - cols[c]) - 3
                    sz = 1.8 if not i else max(1.2, min(2.5, room / max(text_width(t), 1e-6)))
                    P.text(X(cols[c]) + 1.5, yy + 3.1, t, sz, grey=not i, bold=bool(i) and c == 0)
            yb = top - 4
        if g["bom"] and g["annex"]:
            na = next(i for i, (gg, p) in enumerate(jobs, 1) if gg is g and p.get("annex"))
            P.text(tx, yb - 2.5, TX["annex_see"].format(n=na), 2.5, bold=True)
            yb -= 7
        elif g["bom"]:
            rows = [(str(i), k, str(q)) for i, (k, q) in enumerate(g["bom"][:BOM_MAX], 1)]
            if len(g["bom"]) > BOM_MAX:
                rest = g["bom"][BOM_MAX:]
                rows.append(("", TX["more"].format(n=len(rest)), str(sum(q for _, q in rest))))
            rows.append(("", TX["TOTAL"], str(sum(q for _, q in g["bom"]))))
            top = yb - (len(rows) + 1) * REV_ROW
            P.text(tx, top - 2, TX["BOM"], 2.5, bold=True)
            P.poly([(tx, top), (tx + tb_w, top), (tx + tb_w, yb), (tx, yb)], 0.35, closed=True)
            cols = (0, 0.1, 0.86, 1)
            for f in cols[1:3]:
                P.line(X(f), top, X(f), yb, 0.18)
            for i, r in enumerate([(TX["ITEM"], TX["PART"], TX["QTY"])] + rows):
                yy = yb - (i + 1) * REV_ROW
                P.line(tx, yy, tx + tb_w, yy, 0.35 if i in (0, len(rows) - 1) else 0.18)
                for c, t in enumerate(r):
                    room = tb_w * (cols[c + 1] - cols[c]) - 3
                    sz = 1.8 if not i else max(1.2, min(2.5, room / max(text_width(t), 1e-6)))
                    P.text(X(cols[c]) + 1.5, yy + 3.1, t, sz, grey=not i, bold=bool(i) and (c == 2 or i == len(rows)))
            yb = top - 5
        if XT["legend"]:
            top = yb - (len(XT["legend"]) + 1) * REV_ROW
            P.text(tx, top - 2, TX["LEGEND"], 2.5, bold=True)
            P.poly([(tx, top), (tx + tb_w, top), (tx + tb_w, yb), (tx, yb)], 0.35, closed=True)
            cols = (0, 0.18, 1)
            P.line(X(cols[1]), top, X(cols[1]), yb, 0.2)
            for i, r in enumerate([(TX["CODE"], TX["DESC"])] + XT["legend"]):
                yy = top + i * REV_ROW
                if i:
                    P.line(tx, yy, tx + tb_w, yy, 0.2)
                for c, tt in enumerate(r):
                    room = tb_w * (cols[c + 1] - cols[c]) - 3
                    sz = 1.8 if not i else max(1.2, min(2.5, room / max(text_width(tt), 1e-6)))
                    P.text(X(cols[c]) + 1.5, yy + 3.1, tt, sz, grey=not i, bold=bool(i) and c == 0)
            yb = top - 5
        if XT["tol"]:
            vals = ISO2768[XT["tol"]]
            used = [i for i, (lo, hi) in enumerate(ISO2768_RANGES) if vals[i] is not None and any(lo <= x <= hi for x in DIMV)]
            used = used or [i for i in range(len(ISO2768_RANGES)) if vals[i] is not None]
            num = lambda x: f"{x:g}".replace(".", ",") if lang == "fr" else f"{x:g}"
            rows = [(TX["tol_size"], *(f"{num(ISO2768_RANGES[i][0])}–{num(ISO2768_RANGES[i][1])}" for i in used)),
                    (TX["tol_dev"], *(f"±{num(vals[i])}" for i in used))]
            top = yb - 2 * REV_ROW
            P.text(tx, top - 2, TX["tol_table"].format(c=XT["tol"]), 2.5, bold=True)
            P.poly([(tx, top), (tx + tb_w, top), (tx + tb_w, yb), (tx, yb)], 0.35, closed=True)
            cols = [0.18 + 0.82 * j / len(used) for j in range(len(used) + 1)]
            cols = [0] + cols
            for f in cols[1:-1]:
                P.line(X(f), top, X(f), yb, 0.2)
            P.line(tx, top + REV_ROW, tx + tb_w, top + REV_ROW, 0.2)
            for i, r in enumerate(rows):
                yy = top + i * REV_ROW
                for c, tt in enumerate(r):
                    room = tb_w * (cols[c + 1] - cols[c]) - 3
                    sz = max(1.2, min(2.5 if c else 1.8, room / max(text_width(tt), 1e-6)))
                    P.text(X(cols[c]) + 1.5, yy + 3.1, tt, sz, grey=not c, bold=bool(c) and i == 1)
            yb = top - 5
        if XT["rem"]:
            top = yb - 5 - len(XT["rem"]) * REM_LINE
            P.text(tx, top + 2.5, TX["REMARKS"], 2.5, bold=True)
            for i, t in enumerate(XT["rem"]):
                P.text(tx, top + 5 + (i + 0.75) * REM_LINE, t, REM_SIZE)
        if not plain:
            P.text(tx, ty - 8.5, TX["dims"].format(u=UNITS[unit][1] + (f" [{UNITS[unit2][1]}]" if unit2 else ""), a=dual(real.x), b=dual(real.y), c=dual(real.z)), 1.8, grey=True)
            wlo, whi = lo * unit_mm, hi * unit_mm
            P.text(tx, ty - 5.5, TX["origin"] + " · ".join(TX["range"].format(a=a, lo=fmt(wlo[i] + 0, 1 if unit == "mm" else None), hi=fmt(whi[i] + 0, 1 if unit == "mm" else None)) for i, a in enumerate("XYZ")), 1.8, grey=True)
            if hidden:
                P.text(tx, ty - 2.5, TX["hidden"] + (TX["hidden_main"] if g["trimmed"] else ""), 1.8, grey=True)
        if not only_persp:
            scale_bar(P, tx + tb_w - 5, ty - 5, scale, unit, lang)
        sheets.append(P)
    tell0(0.97, "PDF / SVG")
    os.makedirs(os.path.join(OUT, "out"), exist_ok=True)
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "-", SPEC.get("name") or "plan").strip(" .") or "plan"
    svgs = [f"{name}.svg"] if len(sheets) == 1 else [f"{name}-{i}.svg" for i in range(1, len(sheets) + 1)]
    for fn, P in zip(svgs, sheets):
        with open(os.path.join(OUT, "out", fn), "w", encoding="utf-8") as f:
            f.write(P.svg())
    with open(os.path.join(OUT, "out", f"{name}.pdf"), "wb") as f:
        f.write(pdf(sheets))
    files = [f"{name}.pdf"] + svgs
    for write in EXTRA_OUTPUTS:
        files += write(sheets, os.path.join(OUT, "out"), name)
    return {"files": files, "sizes": {fn: os.path.getsize(os.path.join(OUT, "out", fn)) for fn in files}, "steps": steps, "warnings": warnings, "infos": infos,
            "scale": G[0]["scale"], "size_mm": [round(v, 1) for v in G[0]["real"]], "objects": sum(g["objects"] for g in G),
            "seconds": round(time.time() - t0, 1),
            "pages": [{"svg": fn, "views": [v["name"] for v in pg["views"]], "land": pg["land"], "sheet": g["label"], "scale": g["scale"]}
                      for fn, (g, pg) in zip(svgs, jobs)]}
