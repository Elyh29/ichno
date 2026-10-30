SHEETS = {"A4": (297, 210), "A3": (420, 297), "A2": (594, 420), "A1": (841, 594), "A0": (1189, 841),
          "Letter": (279.4, 215.9), "Tabloid": (431.8, 279.4), "ANSI C": (558.8, 431.8), "ANSI D": (863.6, 558.8)}
SCALES = [10, 5, 2, 1, 1 / 2, 1 / 5, 1 / 10, 1 / 20, 1 / 50, 1 / 100, 1 / 200, 1 / 500]
IMPERIAL = [4, 2, 1, 1 / 2, 1 / 4, 1 / 8, 1 / 12, 1 / 16, 1 / 24, 1 / 48, 1 / 96, 1 / 192, 1 / 384]
MARGIN = 10
INSET = 5
BAND = 17
TB_W, TB_H = 180, 36
NOTES = 11
TOP, BOTTOM, RIGHT = 11, 11, 12
THIRD = None
LEFT = 0
GAPS = (22, 16, 11, 7)
PERSP_MIN = 40
ORTHO = ("Face", "Gauche", "Dessus")
MSG = {"fr": {"persp": "perspective sur une feuille à part", "big": "modèle trop grand pour la feuille, même au {s}",
              "nofit": "à {s}, la vue de {v} ({w} × {h} mm) ne tient pas sur une feuille {sheet}, même seule",
              "best": " : choisis {b} ou moins, ou l’échelle automatique",
              "split": "une feuille par vue : à {s}, les vues ne tiennent pas ensemble sur une {sheet}"},
       "en": {"persp": "isometric view on a separate sheet", "big": "model too big for the sheet, even at {s}",
              "nofit": "at {s}, the {v} view ({w} × {h} mm) does not fit on the {sheet} sheet, even alone",
              "best": ": choose {b} or less, or the Auto scale",
              "split": "one sheet per view: at {s}, the views do not fit together on one {sheet} sheet"}}
VIEW_EN = {"Face": "front", "Gauche": "left", "Droite": "right", "Dessus": "top", "Perspective": "isometric"}


def sheet_size(sheet, land):
    w, h = SHEETS[sheet]
    return (w, h) if land else (h, w)


def zones(sw, sh):
    area = (MARGIN + INSET, MARGIN + BAND, sw - MARGIN - INSET, sh - MARGIN - INSET)
    keep = (sw - MARGIN - min(TB_W, sw - 2 * MARGIN) - INSET, sh - MARGIN - TB_H - NOTES)
    return area, keep


def block(v, persp=False):
    return (v["x"] - (0 if persp else LEFT), v["y"] - TOP, v["x"] + v["w"] + (2 if persp else RIGHT), v["y"] + v["h"] + (2 if persp else BOTTOM))


def free(rects, area, keep):
    for r in rects:
        if r[0] < area[0] - 1e-6 or r[1] < area[1] - 1e-6 or r[2] > area[2] + 1e-6 or r[3] > area[3] + 1e-6:
            return False
        if r[2] > keep[0] and r[3] > keep[1]:
            return False
    return True


def ortho_sizes(dims, s):
    return {n: (w * s, h * s) for n, (w, h) in dims.items()}


def side_of(dims):
    if THIRD is not None:
        return "Droite" if THIRD else "Gauche"
    return "Droite" if "Droite" in dims else "Gauche"


def place_ortho(dims, s, sw, sh, g):
    area, keep = zones(sw, sh)
    sz = ortho_sizes(dims, s)
    side = side_of(dims)
    has = {n: n in sz for n in ("Face", side, "Dessus")}
    fw, fh = sz.get("Face", (0, 0))
    rw, rh = sz.get(side, (0, 0))
    tw, dh = sz.get("Dessus", (0, 0))
    row_h = max(fh, rh)
    x0, y0 = area[0] + LEFT, area[1] + TOP
    xs = x0 + (fw + RIGHT + g + LEFT if has["Face"] else 0)
    if side == "Droite":
        yf = y0 + (dh + BOTTOM + g + TOP if has["Dessus"] else 0)
        views = [{"name": "Dessus", "x": x0, "y": y0, "w": tw, "h": dh}, {"name": "Face", "x": x0, "y": yf, "w": fw, "h": fh},
                 {"name": side, "x": xs, "y": yf, "w": rw, "h": rh}]
    else:
        views = [{"name": "Face", "x": x0, "y": y0, "w": fw, "h": fh}, {"name": side, "x": xs, "y": y0, "w": rw, "h": rh},
                 {"name": "Dessus", "x": x0, "y": y0 + (row_h + BOTTOM + g + TOP if has["Face"] or has[side] else 0), "w": tw, "h": dh}]
    views = [v for v in views if has[v["name"]]]
    return views if views and free([block(v) for v in views], area, keep) else None


def fit_in(rect, aspect):
    rw, rh = rect[2] - rect[0] - 2, rect[3] - rect[1] - TOP - 2
    if rw <= 0 or rh <= 0:
        return None
    w = min(rw, rh * aspect) * 0.94
    h = w / aspect
    return (w, h) if min(w, h) >= PERSP_MIN else None


def place_persp(views, aspect, sw, sh, g):
    area, keep = zones(sw, sh)
    face = next((v for v in views if v["name"] == "Face"), views[0])
    right = max(block(v)[2] for v in views)
    row2 = block(face)[3] + g
    col2 = block(face)[2] + g
    low = max(block(v)[3] for v in views) + g
    third = any(v["name"] == "Droite" for v in views)
    corner = [(col2, area[1], area[2], block(face)[1] - g)] if third else [
              (col2, row2, area[2], keep[1] - g),
              (col2, row2, keep[0] - g, area[3])]
    cands = [(right + g, area[1], area[2], keep[1] - g),
             (right + g, area[1], keep[0] - g, area[3]),
             *corner,
             (area[0], low, area[2], keep[1] - g),
             (area[0], low, keep[0] - g, area[3])]
    best = None
    for c in cands:
        f = fit_in(c, aspect)
        if f and (best is None or f[0] * f[1] > best[0][0] * best[0][1]):
            best = (f, c)
    if not best:
        return None
    (w, h), c = best
    return {"name": "Perspective", "x": c[0] + (c[2] - c[0] - w - 2) / 2, "y": c[1] + TOP + (c[3] - c[1] - TOP - h - 2) / 2, "w": w, "h": h}


def center(views, sw, sh):
    area, keep = zones(sw, sh)
    rects = [block(v, v["name"] == "Perspective") for v in views]
    sx = area[2] - max(r[2] for r in rects)
    sy = area[3] - max(r[3] for r in rects)

    def ok(dx, dy):
        return free([(r[0] + dx, r[1] + dy, r[2] + dx, r[3] + dy) for r in rects], area, keep)
    dx = next((sx / 2 * (1 - i / 20) for i in range(21) if ok(sx / 2 * (1 - i / 20), 0)), 0)
    dy = next((sy / 2 * (1 - i / 20) for i in range(21) if ok(dx, sy / 2 * (1 - i / 20))), 0)
    for v in views:
        v["x"] += dx
        v["y"] += dy
    return views


def one_page(dims, aspect, s, sw, sh):
    for g in GAPS:
        views = place_ortho(dims, s, sw, sh, g)
        if not views:
            continue
        if aspect:
            p = place_persp(views, aspect, sw, sh, g)
            if not p:
                continue
            views.append(p)
        return center(views, sw, sh)
    return None


def alone(name, w, h, sheet, land, persp=False):
    for ld in (land, not land):
        sw, sh = sheet_size(sheet, ld)
        area, keep = zones(sw, sh)
        for r in ((area[0], area[1], area[2], keep[1]), (area[0], area[1], keep[0], area[3])):
            vw, vh = w, h
            if persp:
                f = fit_in(r, w / h)
                if not f:
                    continue
                vw, vh = f
            lft = 0 if persp else LEFT
            bw, bh = lft + vw + (2 if persp else RIGHT), TOP + vh + (2 if persp else BOTTOM)
            if bw <= r[2] - r[0] and bh <= r[3] - r[1]:
                v = {"name": name, "x": r[0] + lft + (r[2] - r[0] - bw) / 2, "y": r[1] + TOP + (r[3] - r[1] - bh) / 2, "w": vw, "h": vh}
                return {"w": sw, "h": sh, "land": ld, "views": [v]}
    return None


def label(s):
    return f"{s:g}:1" if s >= 1 else f"1:{round(1 / s)}"


def layout(dims, aspect, sheet="A3", land=True, scale="auto", scales=SCALES, lang="fr", extra_bottom=0, extra_tb=0, extra_top=0, extra_left=0,
           third=None):
    global BOTTOM, NOTES, TOP, LEFT, THIRD
    saved = BOTTOM, NOTES, TOP, LEFT, THIRD
    BOTTOM, NOTES, TOP, LEFT, THIRD = BOTTOM + extra_bottom, NOTES + extra_tb, TOP + extra_top, LEFT + extra_left, third
    try:
        if not dims:
            p = alone("Perspective", aspect, 1, sheet, land, True) if aspect else None
            if not p:
                raise ValueError(MSG.get(lang, MSG["fr"])["big"].format(s="—"))
            return {"scale": 1, "pages": [p], "note": ""}
        return _layout(dims, aspect, sheet, land, scale, scales, lang)
    finally:
        BOTTOM, NOTES, TOP, LEFT, THIRD = saved


def _layout(dims, aspect, sheet, land, scale, scales, lang):
    M = MSG.get(lang, MSG["fr"])
    sw, sh = sheet_size(sheet, land)
    if scale in (None, "", "auto"):
        for s in scales:
            v = one_page(dims, aspect, s, sw, sh)
            if v:
                return {"scale": s, "pages": [{"w": sw, "h": sh, "land": land, "views": v}], "note": ""}
        for s in scales:
            v = one_page(dims, None, s, sw, sh)
            if v:
                pages = [{"w": sw, "h": sh, "land": land, "views": v}]
                p = alone("Perspective", aspect, 1, sheet, land, True) if aspect else None
                return {"scale": s, "pages": pages + ([p] if p else []), "note": M["persp"]}
        raise ValueError(M["big"].format(s=label(scales[-1])))
    s = float(scale)
    v = one_page(dims, aspect, s, sw, sh)
    if v:
        return {"scale": s, "pages": [{"w": sw, "h": sh, "land": land, "views": v}], "note": ""}
    v = one_page(dims, None, s, sw, sh)
    if v:
        p = alone("Perspective", aspect, 1, sheet, land, True) if aspect else None
        return {"scale": s, "pages": [{"w": sw, "h": sh, "land": land, "views": v}] + ([p] if p else []),
                "note": M["persp"]}
    sz = ortho_sizes(dims, s)
    names = list(dims)
    pages = [alone(n, *sz[n], sheet, land) for n in names]
    if not all(pages):
        best = next((x for x in scales if x <= s and all(alone(n, *ortho_sizes(dims, x)[n], sheet, land) for n in names)), None)
        big = names[[i for i, p in enumerate(pages) if not p][0]]
        w, h = dims[big]
        v = big.lower() if lang == "fr" else VIEW_EN.get(big, big)
        raise ValueError(M["nofit"].format(s=label(s), v=v, w=round(w), h=round(h), sheet=sheet) + (M["best"].format(b=label(best)) if best else ""))
    if aspect:
        p = alone("Perspective", aspect, 1, sheet, land, True)
        if p:
            pages.append(p)
    return {"scale": s, "pages": pages, "note": M["split"].format(s=label(s), sheet=sheet)}
