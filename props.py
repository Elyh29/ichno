import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty

from . import chains, sheets, titleblock

AUTO = ("auto", "Auto", "Largest standard scale that fits the sheet")
METRIC = [AUTO] + [(str(v), lbl, "") for v, lbl in (
    (10, "10:1"), (5, "5:1"), (2, "2:1"), (1, "1:1"), (0.5, "1:2"), (0.2, "1:5"), (0.1, "1:10"), (0.05, "1:20"), (0.02, "1:50"),
    (0.01, "1:100"), (0.005, "1:200"), (0.002, "1:500"))]
IMPERIAL = [AUTO] + [(repr(1 / d) if d != 1 else "1", f"1:{d}" if d > 1 else f"{1 / d:g}:1", hint) for d, hint in (
    (0.25, ""), (0.5, ""), (1, "Full size"), (2, "6\" = 1'-0\""), (4, "3\" = 1'-0\""), (8, "1 1/2\" = 1'-0\""), (12, "1\" = 1'-0\""),
    (16, "3/4\" = 1'-0\""), (24, "1/2\" = 1'-0\""), (48, "1/4\" = 1'-0\""), (96, "1/8\" = 1'-0\""), (192, "1/16\" = 1'-0\""),
    (384, "1/32\" = 1'-0\""))]
SHEETS = [(k, k, "") for k in ("A4", "A3", "A2", "A1", "A0")] + [
    ("Letter", "Letter", "8.5 × 11 in (ANSI A)"), ("Tabloid", "Tabloid", "11 × 17 in (ANSI B)"),
    ("ANSI C", "ANSI C", "17 × 22 in"), ("ANSI D", "ANSI D", "22 × 34 in")]


def scale_items(self, context):
    return IMPERIAL if self.unit == "in" else METRIC


class IchnoSettings(bpy.types.PropertyGroup):
    source: EnumProperty(name="Objects", items=[
        ("VISIBLE", "Visible", "Objects visible in the viewport"),
        ("SELECTED", "Selected", "Selected objects only"),
        ("COLLECTION", "Collection", "Objects of one collection")], default="VISIBLE")
    collection: PointerProperty(name="Collection", type=bpy.types.Collection)
    front: EnumProperty(name="Front View", description="Side of the model shown as the front view", items=[
        ("front", "Front (-Y)", "Blender's front, numpad 1"), ("back", "Back (+Y)", ""), ("right", "Right (+X)", ""),
        ("left", "Left (-X)", ""), ("top", "Top (+Z)", ""), ("bottom", "Bottom (-Z)", "")], default="front")
    lang: EnumProperty(name="Drawing Language", description="Language of the texts on the drawing", items=[
        ("auto", "Auto", "Same as Blender's interface"), ("en", "English", ""), ("fr", "French", "")], default="auto")
    sheet: EnumProperty(name="Size", items=SHEETS, default="A3")
    landscape: BoolProperty(name="Landscape", default=True)
    projection: EnumProperty(name="Projection", items=[
        ("first", "European (First Angle)", "ISO E, used in Europe and most of the world: left view on the right of the front view, top view below"),
        ("third", "American (Third Angle)", "ISO A, used in the USA and Canada: right view on the right of the front view, top view above")],
        default="first")
    unit: EnumProperty(name="Units", items=[("mm", "Millimeters", ""), ("cm", "Centimeters", ""), ("m", "Meters", ""),
                                            ("in", "Inches", "Inches and imperial scales")], default="mm")
    unit2: EnumProperty(name="Secondary Units", description="Dual dimensioning: second value in brackets, e.g. 254.0 [10.00]", items=[
        ("none", "None", ""), ("mm", "Millimeters", ""), ("cm", "Centimeters", ""), ("m", "Meters", ""), ("in", "Inches", "")], default="none")
    scale: EnumProperty(name="Scale", items=scale_items)
    iso: BoolProperty(name="Isometric view", default=True)
    iso_view: EnumProperty(name="Viewpoint", description="Corner the isometric view is seen from", items=[
        ("auto", "Auto", "Front and the side shown by the side view"), ("fl", "Front Left", ""), ("fr", "Front Right", ""),
        ("bl", "Back Left", ""), ("br", "Back Right", ""),
        ("viewport", "Viewport", "Same angle as the 3D Viewport (orthographic, from the view's direction)")], default="auto")
    view_front: BoolProperty(name="Front", description="Draw the front view", default=True)
    view_side: BoolProperty(name="Side", description="Draw the side view", default=True)
    view_top: BoolProperty(name="Top", description="Draw the top view", default=True)
    hidden: BoolProperty(name="Hidden lines", description="Dashed hidden lines (slow on heavy models)", default=False)
    iso_hidden: BoolProperty(name="On Isometric View", description="Also draw hidden lines on the isometric view (usually cluttered)", default=False)
    fast: BoolProperty(name="Fast", description="About a third faster on heavy models: back faces ignored and no intersection lines "
                       "(lines missing on open surfaces seen from behind and where two objects cross); for drafts", default=False)
    axes: BoolProperty(name="Axes", description="Small X, Y, Z axis triad next to each view title", default=True)
    weight: EnumProperty(name="Line weight", items=[("fine", "Fine", ""), ("normal", "Normal", ""), ("bold", "Bold", "")], default="normal")
    angle: FloatProperty(name="Crease angle", description="Edges sharper than this are drawn", default=30, min=1, max=179, precision=0, step=500)
    title: StringProperty(name="Title")
    project: StringProperty(name="Project")
    number: StringProperty(name="Drawing No.", description="Drawing number, also the file name", default="plan")
    company: StringProperty(name="Company", default="")
    logo: StringProperty(name="Logo", description="Image shown in the title block (PNG, JPEG…)", subtype="FILE_PATH")
    author: StringProperty(name="Author")
    revision: StringProperty(name="Revision", default="A")
    revisions: CollectionProperty(type=titleblock.IchnoRevision)
    revision_index: IntProperty()
    fields: CollectionProperty(type=titleblock.IchnoField)
    field_index: IntProperty()
    legend: CollectionProperty(type=titleblock.IchnoAbbr)
    legend_index: IntProperty()
    remarks: PointerProperty(name="Remarks", description="Text (Text Editor) written above the title block", type=bpy.types.Text)
    owner: StringProperty(name="Ownership", description="Ownership notice at the bottom of the title block, e.g. “This drawing is the property of … — all rights reserved”")
    folder: StringProperty(name="Folder", subtype="DIR_PATH", default="//plan/")
    open_pdf: BoolProperty(name="Open PDF", description="Open the PDF when the plan is done", default=True)
    use_sheets: BoolProperty(name="Sheets by Collection", description="One sheet per group of collections, each with its name and scale")
    sheets: CollectionProperty(type=sheets.IchnoSheet)
    sheet_index: IntProperty()
    grid_mode: EnumProperty(name="Mode", items=[
        ("none", "None", ""), ("ruler", "Ruler", "Graduations in world coordinates above and left of the views"),
        ("grid", "Grid", "Architect grid: axis lines with bubbles 1, 2, 3 and A, B, C")], default="none")
    grid_step: FloatProperty(name="Step", description="Spacing in drawing units; 0 = automatic (about 10 intervals)", default=0, min=0, precision=1)
    grid_origin: PointerProperty(name="Origin", description="Object whose location is the zero of the coordinates (world origin if empty)",
                                 type=bpy.types.Object)
    grid_top: BoolProperty(name="Top", default=True)
    grid_front: BoolProperty(name="Front", default=False)
    grid_side: BoolProperty(name="Side", default=False)
    bom_by: EnumProperty(name="Count by", items=[
        ("none", "None", ""), ("name", "Base Name", "Objects named Seat, Seat.001… count as one row “Seat”"),
        ("collection", "Collection", "One row per collection"), ("property", "Custom Property", "One row per value of a custom property")],
        default="none")
    bom_prop: StringProperty(name="Property", description="Custom property of the objects (Object Properties > Custom Properties)", default="ref")
    chains: CollectionProperty(type=chains.IchnoChain)
    chain_index: IntProperty()


class IchnoJob(bpy.types.PropertyGroup):
    running: BoolProperty(default=False)
    progress: FloatProperty(default=0, min=0, max=1, subtype="FACTOR")
    message: StringProperty(default="")
    last: StringProperty(default="")


CLASSES = (*sheets.DATA, *chains.DATA, *titleblock.DATA, IchnoSettings, IchnoJob)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.ichno_settings = PointerProperty(type=IchnoSettings)
    bpy.types.WindowManager.ichno_job = PointerProperty(type=IchnoJob)


def unregister():
    del bpy.types.WindowManager.ichno_job
    del bpy.types.Scene.ichno_settings
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
