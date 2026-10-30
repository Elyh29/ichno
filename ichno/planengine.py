import math
import os
import time

import bpy
from mathutils import Matrix, Vector

if "planlayout" not in globals():
    try:
        from . import planlayout
    except ImportError:
        import planlayout
GEOMETRY = {"MESH", "CURVE", "SURFACE", "META", "FONT"}
WEIGHTS = {"fine": {"contour": 0.25, "detail": 0.09, "cache": 0.07}, "normal": {"contour": 0.35, "detail": 0.13, "cache": 0.1},
           "bold": {"contour": 0.5, "detail": 0.25, "cache": 0.18}}
HIDDEN_TRIS = 1_500_000
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

    def poly(self, pts, lw=0.35, dash=None, closed=False):
        self.items.append(("poly", pts, lw, dash, closed))

    def image(self, x, y, w, h, img):
        k = min(w / img["w"], h / img["h"])
        self.items.append(("image", x + (w - img["w"] * k) / 2, y + (h - img["h"] * k) / 2, img["w"] * k, img["h"] * k, img))

    def line(self, x1, y1, x2, y2, lw=0.18):
        self.poly([(x1, y1), (x2, y2)], lw)

    def tri(self, pts):
        self.items.append(("tri", pts))

    def blank(self, x, y, w, h):
        self.items.append(("blank", x, y, w, h))

    def text(self, x, y, s, size, align="left", bold=False, grey=False, rot=False):
        self.items.append(("text", x, y, s, size, align, bold, grey, rot))

    def arrow(self, x1, y1, x2, y2):
        self.line(x1, y1, x2, y2)
        a, L, s2 = math.atan2(y2 - y1, x2 - x1), 2.4, 0.45
        for px, py, aa in ((x1, y1, a), (x2, y2, a + math.pi)):
            self.tri([(px, py), (px + L * math.cos(aa - s2), py + L * math.sin(aa - s2)), (px + L * math.cos(aa + s2), py + L * math.sin(aa + s2))])

    def svg(self):
        esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}mm" height="{self.h}mm" viewBox="0 0 {self.w} {self.h}">',
               f'<rect width="{self.w}" height="{self.h}" fill="#fff"/><g fill="none" stroke="#111" stroke-linecap="round" stroke-linejoin="round">']
        for it in self.items:
            if it[0] == "poly":
                _, pts, lw, dash, closed = it
                d = "M" + " L".join(f"{x:.3f} {y:.3f}" for x, y in pts) + (" Z" if closed else "")
                da = f' stroke-dasharray="{dash[0]} {dash[1]}"' if dash else ""
                out.append(f'<path d="{d}" stroke-width="{lw}"{da}/>')
        out.append('</g><g fill="#fff" stroke="none">')
        for it in self.items:
            if it[0] == "blank":
                out.append(f'<rect x="{it[1]:.3f}" y="{it[2]:.3f}" width="{it[3]:.3f}" height="{it[4]:.3f}"/>')
        out.append('</g><g fill="#111" stroke="none">')
        for it in self.items:
            if it[0] == "tri":
                out.append('<path d="M' + " L".join(f"{x:.3f} {y:.3f}" for x, y in it[1]) + ' Z"/>')
        out.append('</g><g font-family="Helvetica, Arial, sans-serif">')
        for it in self.items:
            if it[0] == "text":
                _, x, y, s, size, align, bold, grey, rot = it
                anchor = {"left": "start", "center": "middle", "right": "end"}[align]
                tr = f' transform="rotate(-90 {x:.3f} {y:.3f})"' if rot else ""
                fw = ' font-weight="bold"' if bold else ""
                out.append(f'<text x="{x:.3f}" y="{y:.3f}" font-size="{size}" text-anchor="{anchor}" dominant-baseline="middle"{tr}'
                           f'{fw} fill="{"#666" if grey else "#111"}">{esc(s)}</text>')
        out.append("</g>")
        for it in self.items:
            if it[0] == "image":
                _, x, y, w, h, img = it
                out.append(f'<image x="{x:.3f}" y="{y:.3f}" width="{w:.3f}" height="{h:.3f}" href="data:image/png;base64,{img["b64"]}"/>')
        out.append("</svg>")
        return "\n".join(out)

    def pdf_content(self):
        k = 72 / 25.4
        X = lambda x: x * k
        Y = lambda y: (self.h - y) * k
        ops = ["1 J 1 j 0.067 0.067 0.067 RG 0.067 0.067 0.067 rg"]
        for it in self.items:
            if it[0] == "poly":
                _, pts, lw, dash, closed = it
                ops.append(f"{lw * k:.3f} w " + (f"[{dash[0] * k:.2f} {dash[1] * k:.2f}] 0 d" if dash else "[] 0 d"))
                ops.append(" ".join(f"{X(x):.2f} {Y(y):.2f} {'m' if i == 0 else 'l'}" for i, (x, y) in enumerate(pts)) + (" h S" if closed else " S"))
            elif it[0] == "tri":
                ops.append(" ".join(f"{X(x):.2f} {Y(y):.2f} {'m' if i == 0 else 'l'}" for i, (x, y) in enumerate(it[1])) + " h f")
            elif it[0] == "blank":
                _, x, y, w, h = it
                ops.append(f"1 g {X(x):.2f} {Y(y + h):.2f} {w * k:.2f} {h * k:.2f} re f 0.067 0.067 0.067 rg")
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
            col = "0.4 0.4 0.4 rg 0.4 0.4 0.4 RG" if grey else "0.067 0.067 0.067 rg 0.067 0.067 0.067 RG"
            if rot:
                tm = f"0 1 -1 0 {X(x) + pt * 0.35:.2f} {Y(y) - off:.2f} Tm"
            else:
                tm = f"1 0 0 1 {X(x) - off:.2f} {Y(y) - pt * 0.35:.2f} Tm"
            mode = f"[] 0 d {pt * 0.045:.3f} w 2 Tr" if bold else "0 Tr"
            ops.append(f"BT {col} {mode} /F1 {pt:.2f} Tf {tm} (" + raw.decode("latin-1") + ") Tj ET")
        return "\n".join(ops).encode("latin-1")


def pdf(sheets):
    k = 72 / 25.4
    n = len(sheets)
    objs = ["<< /Type /Catalog /Pages 2 0 R >>",
            f"<< /Type /Pages /Kids [{' '.join(f'{4 + 2 * i} 0 R' for i in range(n))}] /Count {n} >>",
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"]
    img = next((it[5] for sh in sheets for it in sh.items if it[0] == "image"), None)
    xo = f" /XObject << /Im1 {4 + 2 * n} 0 R >>" if img else ""
    for i, sh in enumerate(sheets):
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {sh.w * k:.2f} {sh.h * k:.2f}] /Resources << /Font << /F1 3 0 R >>{xo} >> "
                    f"/Contents {5 + 2 * i} 0 R >>")
        objs.append(sh.pdf_content())
    if img:
        objs.append((f"/Type /XObject /Subtype /Image /Width {img['w']} /Height {img['h']} /ColorSpace /DeviceRGB "
                     "/BitsPerComponent 8 /Filter /FlateDecode", img["z"]))
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
           "dims": "COTES EN {u} · ENCOMBREMENT (L × P × H) {a} × {b} × {c}", "origin": "DEPUIS L’ORIGINE DU MONDE : ",
           "range": "{a} de {lo} à {hi}", "hidden": "TRAITS CACHÉS EN POINTILLÉS", "hidden_main": " (PRINCIPAUX SEULEMENT)",
           "nothing": "aucun objet à dessiner", "noview": "aucune vue choisie", "nothing_on": "aucun objet à dessiner sur la feuille « {s} »",
           "hidden_skip": "traits cachés non calculés : {n} triangles, trop pour un plan lisible (isole les pièces voulues)",
           "hidden_trim": "{v} : traits cachés simplifiés ({cut} petits traits retirés, {kept} gardés)",
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
           "dims": "DIMENSIONS IN {u} · OVERALL (W × D × H) {a} × {b} × {c}", "origin": "FROM WORLD ORIGIN: ",
           "range": "{a} {lo} to {hi}", "hidden": "HIDDEN LINES DASHED", "hidden_main": " (MAIN LINES ONLY)",
           "nothing": "nothing to draw", "noview": "no view selected", "nothing_on": "nothing to draw on sheet “{s}”",
           "hidden_skip": "hidden lines skipped: {n} triangles, too many for a readable drawing (isolate the parts you need)",
           "hidden_trim": "{v}: hidden lines simplified ({cut} small strokes removed, {kept} kept)",
           "view_done": "{v}: {n} points in {t:.1f} s",
           "views": {"Face": "front", "Gauche": "left", "Droite": "right", "Dessus": "top", "Perspective": "isometric"}}}

F_ROW, OWN_ROW, REV_ROW, REM_LINE, REM_SIZE = 8, 4.5, 4.5, 3.2, 2.2


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


def tb_extras(SPEC):
    revs = [(str(r.get("rev") or ""), str(r.get("desc") or ""), str(r.get("date") or "")) for r in SPEC.get("revisions") or []]
    revs = [r for r in revs if any(r)]
    fields = [(str(f.get("key") or ""), str(f.get("value") or "")) for f in SPEC.get("fields") or []]
    fields = [f for f in fields if any(f)]
    owner = str(SPEC.get("owner") or "").strip()
    legend = [(str(r.get("code") or ""), str(r.get("desc") or "")) for r in SPEC.get("legend") or []]
    legend = [r for r in legend if any(r)]
    rem = wrap(SPEC.get("remarks") or "", planlayout.TB_W - 4, REM_SIZE)
    inside = F_ROW * -(-len(fields) // 4) + (OWN_ROW if owner else 0)
    above = ((len(revs) + 1) * REV_ROW + 4 if revs else 0) + (5 + len(rem) * REM_LINE + 2 if rem else 0) + (
        (len(legend) + 1) * REV_ROW + 5 if legend else 0)
    return {"revs": revs, "fields": fields, "owner": owner, "legend": legend, "rem": rem, "inside": inside, "above": above}


BOM_MAX = 30


def bom_rows(objs, by="name", prop=""):
    import re
    count = {}
    for o in {root_of(x).name: root_of(x) for x in objs}.values():
        if by == "collection":
            k = o.users_collection[0].name if o.users_collection else "—"
        elif by == "property":
            k = str(o.get(prop, "—")) if prop else "—"
        else:
            k = re.sub(r"\.\d{3,}$", "", o.name)
        count[k] = count.get(k, 0) + 1
    return sorted(count.items(), key=lambda kv: kv[0].lower())


LABEL_SIZE = 2


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


def bom_height(rows):
    n = min(len(rows), BOM_MAX) + (1 if len(rows) > BOM_MAX else 0)
    return (n + 3) * REV_ROW + 2 if rows else 0


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
    m, o = planlayout.MARGIN, 5
    P.poly([(o, o), (sw - o, o), (sw - o, sh - o), (o, sh - o)], 0.18, closed=True)
    P.poly([(m, m), (sw - m, m), (sw - m, sh - m), (m, sh - m)], 0.5, closed=True)
    for horiz in (True, False):
        length = (sw if horiz else sh) - 2 * m
        n = max(2, 2 * round(length / 100))
        step = length / n
        for i, lab in enumerate(zone_labels(n, not horiz)):
            a = m + i * step
            if i:
                if horiz:
                    P.line(a, o, a, m, 0.18)
                    P.line(a, sh - m, a, sh - o, 0.18)
                else:
                    P.line(o, a, m, a, 0.18)
                    P.line(sw - m, a, sw - o, a, 0.18)
            c = a + step / 2
            if horiz:
                P.text(c, (o + m) / 2, lab, 2.5, "center")
                P.text(c, sh - (o + m) / 2, lab, 2.5, "center")
            else:
                P.text((o + m) / 2, c, lab, 2.5, "center")
                P.text(sw - (o + m) / 2, c, lab, 2.5, "center")
    for x, y, dx, dy in ((sw / 2, 0, 0, 1), (sw / 2, sh, 0, -1), (0, sh / 2, 1, 0), (sw, sh / 2, -1, 0)):
        P.line(x + dx * 2, y + dy * 2, x + dx * (m + 1.5), y + dy * (m + 1.5), 0.6)


def circle(P, cx, cy, r, lw):
    P.poly([(cx + r * math.cos(a * math.pi / 24), cy + r * math.sin(a * math.pi / 24)) for a in range(48)], lw, closed=True)


def angle_symbol(P, x, y, third=False):
    h = 1.5
    tx, cx = (x + 4 * h + 3.5, x + 2 * h) if third else (x, x + 6 + 3.5 + 2 * h)
    P.poly([(tx, y - h), (tx + 6, y - 2 * h), (tx + 6, y + 2 * h), (tx, y + h)], 0.25, closed=True)
    circle(P, cx, y, 2 * h, 0.25)
    circle(P, cx, y, h, 0.25)
    P.line(x - 1, y, x + 6 + 3.5 + 4 * h + 1, y, 0.09)
    P.line(cx, y - 2 * h - 0.8, cx, y + 2 * h + 0.8, 0.09)


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
        P.text(x0 + w * i / 5, y - 2, f"{v:g}".replace(".", "," if unit != "in" and lang == "fr" else "."), 2, "center")
    P.text(x0 - 3, y + 0.7, name, 2, "right", grey=True)


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

    def dual(v):
        return f"{fmt(v)} [{fmt2(v)}]" if unit2 else fmt(v)
    XT = tb_extras(SPEC)
    GR = SPEC.get("grid") or {}
    LB = SPEC.get("labels") or {}
    gmode = GR.get("mode") if GR.get("mode") in ("ruler", "grid") and GR.get("views") else None
    gtop = RULER if gmode else 0
    warnings = []
    tell0 = progress or (lambda f, msg: None)
    gi = [0, 1]
    def tell(f, msg):
        tell0(min(0.97, (gi[0] + f) / gi[1] * 0.95), msg)
    def group(only, hide, label, vw=None):
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
        BM = SPEC.get("bom") or {}
        bom = bom_rows(objs, BM.get("by") or "name", BM.get("prop") or "") if BM.get("by") else []
        rows = max([sum(CHAIN_ROW + (POS_ROW if c[4] else 0) for c in chains if c[0] == n) for n, _, _ in VIEWS] + [0])
        if not VIEWS:
            raise RuntimeError(TX["noview"])
        pv = next((vw for vw in VIEWS if vw[0] == "Perspective"), None)
        ex = view_extent(view_matrix(pv[1], pv[2], ctr, r), lo, hi) if pv else None
        odims = {"Face": (real.x, real.z), side[0]: (real.y, real.z), "Dessus": (real.x, real.y)}
        L = planlayout.layout({n: odims[n] for n, _, _ in VIEWS if n in odims},
                              (ex[1] - ex[0]) / max(ex[3] - ex[2], 1e-9) if ex else None, SPEC.get("sheet") or "A3", SPEC.get("land", True),
                              SPEC.get("scale"), planlayout.IMPERIAL if unit == "in" else planlayout.SCALES, lang, rows,
                              XT["inside"] + XT["above"] + bom_height(bom), gtop, gtop, third)
        drawn, trimmed = {}, False
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
                trimmed = True
                steps.append(f"{label + ' · ' if label else ''}" + TX["hidden_trim"].format(v=TX["views"][name], cut=cut, kept=len(S["cache"])))
                warnings.append(steps[-1])
            drawn[name] = {"contour": S.get("contour", []), "detail": S.get("detail", []), "cache": S.get("cache", []), "ext": ext,
                           "axes": view_axes(cam), "chains": [chain_info(cam, chain_positions(cam, co, ref), rel, pos, unit_mm)
                                      for vn, co, ref, rel, pos in chains if vn == name],
                           "grid": grid_ticks(cam, lo, hi, ctr, gstep, gorg) if name in gviews else None,
                           "labels": label_view(cam, lpts) if name in lviews else []}
            bpy.data.objects.remove(gp)
            bpy.data.objects.remove(cam)
            steps.append(f"{label + ' · ' if label else ''}" + TX["view_done"].format(v=TX["views"][name], n=sum(len(x) for k in ("contour", "detail") for x in S.get(k, [])), t=time.time() - t))
        return {"label": label, "drawn": drawn, "scale": L["scale"], "pages": L["pages"], "note": L["note"], "real": real, "lo": lo, "hi": hi,
                "hidden": hidden and any(d["cache"] for d in drawn.values()), "trimmed": trimmed, "steps": steps, "objects": len(objs), "unit_mm": unit_mm, "bom": bom}

    realize_instances()
    groups = SPEC.get("sheets") or [{"name": "", "only": SPEC.get("only"), "hide": SPEC.get("hide")}]
    G = []
    gi[1] = len(groups)
    for i, g in enumerate(groups):
        gi[0] = i
        G.append(group(g.get("only"), g.get("hide"), g.get("name") or "", g.get("views")))
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
        for layer, lw, dash in (("cache", W["cache"], (1.0, 0.7)), ("detail", W["detail"], None), ("contour", W["contour"], None)):
            for st in drawn[v["name"]][layer]:
                pts, last = [], None
                for x, y in st:
                    q = (v["x"] + (x - ex[0]) * k, v["y"] + (ex[3] - y) * k)
                    if last is None or abs(q[0] - last[0]) + abs(q[1] - last[1]) >= min_seg:
                        pts.append(q)
                        last = q
                if len(pts) >= 2:
                    P.poly(pts, lw, dash)

    def labels_of(P, v):
        ex = drawn[v["name"]]["ext"]
        k = v["w"] / max(ex[1] - ex[0], 1e-9) if v["name"] == "Perspective" else k_paper
        size = min(max(float(LB.get("size") or LABEL_SIZE), 1), 6)
        h = size + 0.8
        hit = lambda a, b: a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]
        taken, out = [], []
        for t, (x, y), ow, oh in sorted(drawn[v["name"]]["labels"], key=lambda it: -it[3] * it[2]):
            L = text_width(t) * size + 1.2
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
        gap = 4 if v["name"] == "Perspective" else 13
        lx, rx = v["x"] - 4, v["x"] + v["w"] + gap
        room = lambda side, its: (lx - 1.6 - max(it[3] for it in its) >= planlayout.MARGIN + 3 if side < 0
                                  else rx + 1.6 + max(it[3] for it in its) <= P.w - planlayout.MARGIN - 3)
        sides = {-1: [it for it in out if it[1] < mid], 1: [it for it in out if it[1] >= mid]}
        for a in (-1, 1):
            if sides[a] and not room(a, sides[a]) and room(-a, sides[a] + sides[-a]):
                sides[-a] += sides[a]
                sides[a] = []
        for side in (-1, 1):
            col = sorted(sides[side], key=lambda it: it[2])
            if not col:
                continue
            step = h + 0.6
            ys, last = [], -1e9
            for _, _, py, _ in col:
                last = max(py, last + step)
                ys.append(last)
            over = ys[-1] - (v["y"] + v["h"] + 2 * step)
            if over > 0:
                ys = [yy - over for yy in ys]
                for i in range(len(ys) - 2, -1, -1):
                    ys[i] = min(ys[i], ys[i + 1] - step)
            xc = lx if side < 0 else rx
            for (t, px, py, L), yy in zip(col, ys):
                P.line(px, py, xc, yy, 0.12)
                P.line(xc, yy, xc + side * 1.2, yy, 0.12)
                circle(P, px, py, 0.25, 0.2)
                x0 = xc + side * 1.6
                P.blank(x0 - L if side < 0 else x0, yy - h / 2, L, h)
                P.text(x0, yy, t, size, "right" if side < 0 else "left")

    def dims_of(P, v, w, h):
        x0, y0, vw, vh = v["x"], v["y"], v["w"], v["h"]
        yd, xd = y0 + vh + 6, x0 + vw + 6
        P.line(x0, y0 + vh + 1, x0, yd + 1.5, 0.13)
        P.line(x0 + vw, y0 + vh + 1, x0 + vw, yd + 1.5, 0.13)
        P.line(x0 + vw + 1, y0, xd + 1.5, y0, 0.13)
        P.line(x0 + vw + 1, y0 + vh, xd + 1.5, y0 + vh, 0.13)
        P.arrow(x0, yd, x0 + vw, yd)
        P.text(x0 + vw / 2, yd - 2.2, dual(w), 2.8, "center")
        P.arrow(xd, y0, xd, y0 + vh)
        P.text(xd + 2.6, y0 + vh / 2, dual(h), 2.8, "center", rot=True)

    def chain_of(P, v, ch, y, ex):
        segs = ch["segs"]
        X = lambda x: v["x"] + (x - ex[0]) * k_paper
        st = sorted({round(X(a), 3) for a, _, _, _ in segs} | {round(X(b), 3) for _, b, _, _ in segs})
        P.line(st[0], y, st[-1], y, 0.13)
        if ch["pos"]:
            for x, w in ch["world"].items():
                t = fmt(w + 0, 1 if unit == "mm" else None)
                size = max(1.1, min(1.6, (POS_ROW - 2) / max(text_width(t), 1e-6)))
                P.text(X(x) + size * 0.45, y + 1.8 + text_width(t) * size / 2, t, size, "center", rot=True)
            P.text(st[0] - 1.5, y + 3, ch["axis"], 1.8, "right", bold=True)
        for x in st:
            P.line(x, v["y"] + v["h"] + 7, x, y + 1.5, 0.09)
            P.line(x - 0.9, y + 0.9, x + 0.9, y - 0.9, 0.25)
        for a, b, n, d in segs:
            xa, xb = X(a), X(b)
            t = f"{n} × {dual(d)} = {dual(d * n)}" if n > 1 else dual(d)
            if text_width(t) * 2.2 <= (xb - xa) - 1:
                P.text((xa + xb) / 2, y - 1.6, t, 2.2, "center")
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
                    P.text(x, yr - 3, t, 1.7, "center")
                    last = x + text_width(t) * 0.85
            P.text(hx[-1][0] + 1.5, yr - 0.6, gr[0]["axis"], 1.8, bold=True)
        if vy:
            P.line(xr, vy[0][0], xr, vy[-1][0], 0.15)
            last = -1e9
            for y, w in vy:
                P.line(xr, y, xr - 1.2, y, 0.15)
                t = lab(w)
                if y - text_width(t) * 0.85 > last + 1:
                    P.text(xr - 3, y, t, 1.7, "center", rot=True)
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
        frame(P, sw, sh)
        P.text(sw / 2, m + 7, title.upper(), 5, "center", bold=True)
        P.text(sw / 2, m + 13, f"{g['label']} · {project}" if g["label"] else project, 3.2, "center")
        only_persp = all(v["name"] == "Perspective" for v in pg["views"])
        for v in pg["views"]:
            if v["name"] not in drawn:
                continue
            place(P, v)
            if drawn[v["name"]].get("labels"):
                labels_of(P, v)
            persp = v["name"] == "Perspective"
            cx = v["x"] + v["w"] / 2
            head = TX[v["name"]]
            ty0 = v["y"] - (0 if persp else gtop)
            P.text(cx, ty0 - 7.5, head, 3.5, "center", bold=True)
            hw = text_width(head, True) * 3.5
            P.line(cx - hw / 2, ty0 - 5.3, cx + hw / 2, ty0 - 5.3, 0.25)
            if SPEC.get("axes", True):
                axes_triad(P, cx - max(hw, text_width(TX["scale_of"].format(s="1:500")) * 2.2) / 2 - 7, ty0 - 4.5, drawn[v["name"]]["axes"])
            if not persp and drawn[v["name"]].get("grid"):
                grid_of(P, v, drawn[v["name"]]["grid"], drawn[v["name"]]["ext"])
            P.text(cx, ty0 - 3, TX["iso"] if persp else TX["scale_of"].format(s=planlayout.label(scale)), 2.2, "center", grey=True)
            if not persp:
                dims_of(P, v, *real_dims[v["name"]])
                yc = v["y"] + v["h"] + 6
                for ch in drawn[v["name"]].get("chains", []):
                    yc += CHAIN_ROW
                    if ch["segs"]:
                        chain_of(P, v, ch, yc, drawn[v["name"]]["ext"])
                    if ch["pos"]:
                        yc += POS_ROW
        tb_w, tb_h = min(planlayout.TB_W, sw - 2 * m), planlayout.TB_H
        tx, ty = sw - m - tb_w, sh - m - tb_h - XT["inside"]
        X = lambda f: tx + tb_w * f
        r1, r2, r3 = ty + 7, ty + 20, ty + 28
        P.poly([(tx, ty), (tx + tb_w, ty), (tx + tb_w, ty + tb_h + XT["inside"]), (tx, ty + tb_h + XT["inside"])], 0.5, closed=True)
        for y in (r1, r2, r3):
            P.line(tx, y, tx + tb_w, y, 0.25)
        for f, ya, yb in ((0.61, r1, r2), (0.78, r1, r2), (0.30, r2, r3), (0.52, r2, r3), (0.78, r2, r3), (0.89, r2, r3), (0.39, r3, ty + tb_h), (0.56, r3, ty + tb_h),
                          (0.67, r3, ty + tb_h), (0.81, r3, ty + tb_h)):
            P.line(X(f), ya, X(f), yb, 0.25)

        def cell(f, f2, y, label, value, size=2.8, bold=False):
            P.text(X(f) + 1.5, y + 2, label, 1.7, grey=True)
            room = tb_w * (f2 - f) - 3
            P.text(X(f) + 1.5, y + 5.5, value, max(1.4, min(size, room / max(text_width(value, bold), 1e-6))), bold=bold)
        P.text(tx + 2, ty + 2.6, TX["disclaimer"], 1.8, grey=True)
        P.text(tx + 2, ty + 5.2, TX["generated"].format(brand=brand or "Blender", file=SPEC.get("file") or "—"), 1.8, grey=True)
        P.text(X(0) + 1.5, r1 + 2, TX["TITLE"], 1.7, grey=True)
        tt = f"{title} — {g['label']}" if g["label"] else title
        P.text(X(0) + 1.5, r1 + 8, tt, 5 if text_width(tt) * 5 < tb_w * 0.58 else 3.5 if text_width(tt) * 3.5 < tb_w * 0.58 else 2.6, bold=True)
        P.text(X(0.61) + 1.5, r1 + 2, TX["PROJECTION"], 1.7, grey=True)
        angle_symbol(P, X(0.61) + 7.5, r1 + 6.6, third)
        P.text(X(0.695), r1 + 11.7, TX["third" if third else "first"], 1.6, "center", grey=True)
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
        cell(0, 0.39, r3, TX["NUMBER"], number)
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
                    sz = 1.7 if not i else max(1.2, min(2.2, room / max(text_width(t), 1e-6)))
                    P.text(X(cols[c]) + 1.5, yy + 3.1, t, sz, grey=not i, bold=bool(i) and c == 0)
            yb = top - 4
        if g["bom"]:
            rows = [(str(i), k, str(q)) for i, (k, q) in enumerate(g["bom"][:BOM_MAX], 1)]
            if len(g["bom"]) > BOM_MAX:
                rest = g["bom"][BOM_MAX:]
                rows.append(("", TX["more"].format(n=len(rest)), str(sum(q for _, q in rest))))
            rows.append(("", TX["TOTAL"], str(sum(q for _, q in g["bom"]))))
            top = yb - (len(rows) + 1) * REV_ROW
            P.text(tx, top - 2, TX["BOM"], 2.2, bold=True)
            P.poly([(tx, top), (tx + tb_w, top), (tx + tb_w, yb), (tx, yb)], 0.35, closed=True)
            cols = (0, 0.1, 0.86, 1)
            for f in cols[1:3]:
                P.line(X(f), top, X(f), yb, 0.2)
            for i, r in enumerate([(TX["ITEM"], TX["PART"], TX["QTY"])] + rows):
                yy = top + i * REV_ROW
                if i:
                    P.line(tx, yy, tx + tb_w, yy, 0.35 if i == len(rows) else 0.2)
                for c, t in enumerate(r):
                    room = tb_w * (cols[c + 1] - cols[c]) - 3
                    sz = 1.7 if not i else max(1.2, min(2.2, room / max(text_width(t), 1e-6)))
                    P.text(X(cols[c]) + 1.5, yy + 3.1, t, sz, grey=not i, bold=bool(i) and (c == 2 or i == len(rows)))
            yb = top - 5
        if XT["legend"]:
            top = yb - (len(XT["legend"]) + 1) * REV_ROW
            P.text(tx, top - 2, TX["LEGEND"], 2.2, bold=True)
            P.poly([(tx, top), (tx + tb_w, top), (tx + tb_w, yb), (tx, yb)], 0.35, closed=True)
            cols = (0, 0.18, 1)
            P.line(X(cols[1]), top, X(cols[1]), yb, 0.2)
            for i, r in enumerate([(TX["CODE"], TX["DESC"])] + XT["legend"]):
                yy = top + i * REV_ROW
                if i:
                    P.line(tx, yy, tx + tb_w, yy, 0.2)
                for c, tt in enumerate(r):
                    room = tb_w * (cols[c + 1] - cols[c]) - 3
                    sz = 1.7 if not i else max(1.2, min(2.2, room / max(text_width(tt), 1e-6)))
                    P.text(X(cols[c]) + 1.5, yy + 3.1, tt, sz, grey=not i, bold=bool(i) and c == 0)
            yb = top - 5
        if XT["rem"]:
            top = yb - 5 - len(XT["rem"]) * REM_LINE
            P.text(tx, top + 2.5, TX["REMARKS"], 2.2, bold=True)
            for i, t in enumerate(XT["rem"]):
                P.text(tx, top + 5 + (i + 0.75) * REM_LINE, t, REM_SIZE)
        P.text(tx, ty - 8.5, TX["dims"].format(u=UNITS[unit][1] + (f" [{UNITS[unit2][1]}]" if unit2 else ""), a=dual(real.x), b=dual(real.y), c=dual(real.z)), 2, grey=True)
        wlo, whi = lo * unit_mm, hi * unit_mm
        P.text(tx, ty - 5.5, TX["origin"] + " · ".join(TX["range"].format(a=a, lo=fmt(wlo[i] + 0, 1 if unit == "mm" else None), hi=fmt(whi[i] + 0, 1 if unit == "mm" else None)) for i, a in enumerate("XYZ")), 2, grey=True)
        if hidden:
            P.text(tx, ty - 2.5, TX["hidden"] + (TX["hidden_main"] if g["trimmed"] else ""), 2, grey=True)
        if not only_persp:
            scale_bar(P, tx + tb_w - 5, ty - 5, scale, unit, lang)
        sheets.append(P)
    tell0(0.97, "PDF / SVG")
    os.makedirs(os.path.join(OUT, "out"), exist_ok=True)
    name = (SPEC.get("name") or "plan").replace("/", "-")
    svgs = [f"{name}.svg"] if len(sheets) == 1 else [f"{name}-{i}.svg" for i in range(1, len(sheets) + 1)]
    for fn, P in zip(svgs, sheets):
        with open(os.path.join(OUT, "out", fn), "w", encoding="utf-8") as f:
            f.write(P.svg())
    with open(os.path.join(OUT, "out", f"{name}.pdf"), "wb") as f:
        f.write(pdf(sheets))
    files = [f"{name}.pdf"] + svgs
    return {"files": files, "sizes": {fn: os.path.getsize(os.path.join(OUT, "out", fn)) for fn in files}, "steps": steps, "warnings": warnings,
            "scale": G[0]["scale"], "size_mm": [round(v, 1) for v in G[0]["real"]], "objects": sum(g["objects"] for g in G),
            "seconds": round(time.time() - t0, 1),
            "pages": [{"svg": fn, "views": [v["name"] for v in pg["views"]], "land": pg["land"], "sheet": g["label"], "scale": g["scale"]}
                      for fn, (g, pg) in zip(svgs, jobs)]}
