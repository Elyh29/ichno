# SPDX-License-Identifier: GPL-3.0-or-later
# Ichno: Online Manual (F1) opens the wiki
import bpy

WIKI = "https://github.com/Elyh29/ichno/wiki/"
S = "bpy.types.ichnosettings."
PAGES = (
    ("Installation#your-first-drawing", ("bpy.ops.ichno.make*", "bpy.ops.ichno.cancel*", "bpy.ops.ichno.open*", S + "source", S + "collection")),
    ("Panel#output", (S + "folder", S + "subfolder", S + "open_pdf")),
    ("Views-and-Style#views", (S + "view_*", S + "iso", S + "iso_view", S + "front", S + "projection", S + "standard")),
    ("Views-and-Style#style", (S + "fast", S + "weight", S + "angle", S + "hidden", S + "iso_hidden", S + "axes", S + "view_titles",
                               S + "dims_all", S + "filing_margin")),
    ("Sheets#sheets-by-collection", (S + "use_sheets", S + "sheets", "bpy.types.ichnosheet*", "bpy.ops.ichno.sheet_*")),
    ("Sheets#sheet", (S + "sheet", S + "landscape", S + "scale", S + "unit", S + "unit2", S + "lang")),
    ("Title-Block#approval-and-manufacturing", (S + "checked", S + "approved", S + "material", S + "tol*")),
    ("Title-Block#other-blocks", (S + "revisions", S + "fields", S + "legend", S + "remarks", S + "owner", "bpy.types.ichnorevision*",
                                  "bpy.types.ichnofield*", "bpy.types.ichnoabbr*", "bpy.ops.ichno.tb_*")),
    ("Title-Block", (S + "title", S + "project", S + "number", S + "company", S + "logo", S + "author", S + "revision")),
    ("Dimensions#chain-dimensions", (S + "chain*", "bpy.types.ichnochain*", "bpy.ops.ichno.chain_*")),
    ("Dimensions#ruler-or-grid", (S + "grid_*",)),
    ("Bill-of-Materials", (S + "bom_*", "bpy.ops.ichno.bom_*")),
    ("Home", (S + "*",)),
)


def manual_map():
    return WIKI, tuple((pattern, page) for page, patterns in PAGES for pattern in patterns)


def register():
    bpy.utils.register_manual_map(manual_map)


def unregister():
    bpy.utils.unregister_manual_map(manual_map)
